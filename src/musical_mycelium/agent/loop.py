"""The hand-built Converse tool loop, as an event stream.

**Claims first, prose second, enforced by signature.** ``synthesize()`` takes exactly one argument — an
``ApprovedClaimSet`` — and that object is constructible only from claims the gate approved plus the
labels of those claims' own endpoints. It cannot reach the graph, the query, the rejected claims, or the
tool transcript, because none of them are in scope. This is the leak the 7/27 review caught: the
original design let the model emit claims *alongside* prose, so prose could assert an edge that never
became a claim and groundedness would read 100% while the text hallucinated.

**Refusal never goes through the model.** When the gate approves nothing there is nothing to ground
prose in, so the refusal is a deterministic template. That makes refusal reliable rather than
probabilistic, and it is free.

**The loop is a generator of events, not a function returning an answer.** The API layer in step 7 maps
these one-to-one onto SSE frames and owns no logic, which is what ``CLAUDE.md`` requires of ``api``. It
also means the walked path and each claim reach the client *as they happen*, which is the demo.
"""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from dataclasses import dataclass, field

from musical_mycelium.agent.claims import Claim, ClaimProposal, GateResult, Rejection, gate
from musical_mycelium.agent.llm import (
    LLM,
    Usage,
    assistant_tool_use_message,
    dumps,
    tool_result_message,
    user_message,
)
from musical_mycelium.agent.tools import ToolRegistry
from musical_mycelium.graph.store import GraphStore

#: Hard ceiling on model turns. v0.1 needs two (resolve, then influences); the rest is slack for a
#: retry. It is a **cost control** as much as a safety one — an agentic loop re-sends its accumulated
#: context every turn, so an unbounded loop is an unbounded bill (``.claude/rules/aws-and-cost.md``).
MAX_TURNS = 4

SYSTEM_PROMPT = """You answer questions about where music genres came from, using only a graph of \
documented influences.

Use resolve_genre to turn the genre the user named into a node id, then get_influences to list what \
that genre came out of. Then stop and summarise what you found.

Two rules matter more than being helpful:
- If resolve_genre returns null, this graph does not cover that genre. Say so. Do not substitute a \
similar genre.
- If get_influences returns an empty list, this graph has no sourced influences for that genre. Say so. \
Do not fill the gap from your own knowledge.

You are not the final word: everything you say is checked against the graph before the user sees it, \
and anything the graph does not support is discarded."""

SYNTHESIS_PROMPT = """Write two sentences stating what the genre came out of, using only the influences \
listed below. Name every one of them. Add nothing else: no dates, no places, no artists, no context \
that is not in the list. Do not hedge and do not editorialise."""


# --- events ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class ToolCalled:
    name: str
    arguments: dict[str, object]
    is_error: bool = False


@dataclass(frozen=True, slots=True)
class ClaimApproved:
    claim: Claim


@dataclass(frozen=True, slots=True)
class ClaimRejected:
    rejection: Rejection


@dataclass(frozen=True, slots=True)
class PathWalked:
    """The nodes visited, in order. ``SPEC.md`` 5.3 makes this non-negotiable at v0.1 — retrofitting
    path-in-payload once the schema has consumers is the annoying kind of rework, and phase 5's guided
    tour is built on it."""

    node_ids: tuple[str, ...]
    labels: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class Token:
    text: str


@dataclass(frozen=True, slots=True)
class Refused:
    """Not an error. The correct answer when the graph cannot support one."""

    reason: str
    query: str


@dataclass(frozen=True, slots=True)
class Done:
    usage: Usage
    claim_count: int
    rejection_count: int
    model_id: str


Event = ToolCalled | ClaimApproved | ClaimRejected | PathWalked | Token | Refused | Done


# --- the approved claim set: the only thing synthesis is allowed to see ------------------------------


@dataclass(frozen=True, slots=True)
class ApprovedClaimSet:
    """Approved claims plus the labels of their own endpoints. Nothing else.

    ``__post_init__`` rejects any label that does not belong to a claim in the set, so the object cannot
    be used to smuggle context past the gate. That is what makes "enforced by signature" true rather
    than aspirational: ``synthesize`` takes one of these and has no other parameter to leak through.
    """

    claims: tuple[Claim, ...]
    labels: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        endpoints = {c.subject_id for c in self.claims} | {c.object_id for c in self.claims}
        extra = set(self.labels) - endpoints
        if extra:
            raise ValueError(
                f"labels contain node(s) no approved claim mentions: {sorted(extra)}. "
                f"Synthesis may only see the approved claim set."
            )

    @property
    def subject_id(self) -> str | None:
        """The genre being asked about. At v0.1 every claim shares one subject."""
        subjects = {c.subject_id for c in self.claims}
        return subjects.pop() if len(subjects) == 1 else None

    def label_of(self, node_id: str) -> str:
        return self.labels.get(node_id, node_id)

    def __bool__(self) -> bool:
        return bool(self.claims)


def synthesize(claim_set: ApprovedClaimSet, llm: LLM) -> Iterator[str]:
    """Prose from approved claims, and nothing but approved claims.

    Note the signature. There is no ``query`` parameter, no ``store``, no ``GateResult``, no message
    history. If a future change needs one of those here, that change is reintroducing the leak.
    """
    if not claim_set:
        raise ValueError(
            "synthesize() called with no approved claims; the caller must refuse instead"
        )

    subject = claim_set.label_of(claim_set.subject_id or "")
    influences = [claim_set.label_of(c.object_id) for c in claim_set.claims]

    prompt = f"{SYNTHESIS_PROMPT}\n\nGenre: {subject}\nDocumented influences: {dumps(influences)}"
    yield from llm.stream([user_message(prompt)], max_tokens=200)


def refusal_text(query: str, reason: str) -> str:
    """Deterministic. No model call, so it cannot hallucinate the thing it is declining to state."""
    return (
        f"This graph has no sourced answer for {query!r}: {reason}. "
        f"Every claim here has to trace to a checkable source, and there is none to trace — so rather "
        f"than fill the gap, it is left open."
    )


# --- the loop -------------------------------------------------------------------------------------


def run(
    query: str,
    *,
    store: GraphStore,
    llm: LLM,
    registry: ToolRegistry,
    max_turns: int = MAX_TURNS,
) -> Iterator[Event]:
    """Answer one question, emitting events as it goes.

    Order is deliberate: tools, then gating, then the path, then prose. Prose is generated **after** the
    gate has run and only from what survived it.
    """
    messages: list[dict[str, object]] = [user_message(query)]
    tool_config = registry.tool_config()
    usage = Usage()
    proposals: list[ClaimProposal] = []
    visited: list[str] = []

    for _turn in range(max_turns):
        response = llm.converse(messages, system=SYSTEM_PROMPT, tool_config=tool_config)
        usage = usage + response.usage

        if not response.wants_tools:
            break

        messages.append(assistant_tool_use_message(response))
        for use in response.tool_uses:
            result = registry.invoke(use.name, use.arguments)
            yield ToolCalled(name=use.name, arguments=use.arguments, is_error=result.is_error)

            proposals.extend(result.proposals)
            for node_id in result.visited:
                if node_id not in visited:
                    visited.append(node_id)

            messages.append(tool_result_message(use.id, result.content, is_error=result.is_error))

    decision: GateResult = gate(proposals, store)
    for claim in decision.approved:
        yield ClaimApproved(claim)
    for rejection in decision.rejected:
        yield ClaimRejected(rejection)

    labels = {node_id: _label(store, node_id) for node_id in visited}
    yield PathWalked(node_ids=tuple(visited), labels=tuple(labels[node_id] for node_id in visited))

    if not decision.approved:
        reason = (
            "the genre resolved but carries no sourced influences"
            if visited
            else "the genre is not in this graph"
        )
        text = refusal_text(query, reason)
        yield Refused(reason=reason, query=query)
        yield Token(text)
    else:
        claim_set = ApprovedClaimSet(
            claims=decision.approved,
            labels={
                node_id: labels.get(node_id, _label(store, node_id))
                for claim in decision.approved
                for node_id in (claim.subject_id, claim.object_id)
            },
        )
        for chunk in synthesize(claim_set, llm):
            yield Token(chunk)

    yield Done(
        usage=usage,
        claim_count=len(decision.approved),
        rejection_count=len(decision.rejected),
        model_id=llm.model_id,
    )


def _label(store: GraphStore, node_id: str) -> str:
    node = store.get_node(node_id)
    return node.label if node else node_id
