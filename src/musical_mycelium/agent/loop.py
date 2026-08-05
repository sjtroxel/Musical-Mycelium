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
from itertools import pairwise

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

#: Hard ceiling on model turns. It is a **cost control** as much as a safety one — an agentic loop
#: re-sends its accumulated context every turn, so an unbounded loop is an unbounded bill
#: (``.claude/rules/aws-and-cost.md``).
#:
#: Raised from 4 to 5 at phase 2 step 5. A lineage question needs **three** tool turns — resolve, resolve,
#: trace — plus a final text turn, which consumed the whole v0.1 budget and left a real model no room to
#: recover from one bad argument. One turn of slack, not a blank cheque.
MAX_TURNS = 5

#: Deliberately free of tool names. v0.1's prompt hard-coded the two-step procedure — "use resolve_genre,
#: then get_influences" — which meant a third tool needed a prompt edit inside the loop module to ever be
#: called. That is invariant 4 leaking through the prose door rather than the code door. Each tool
#: describes itself in its own ``toolSpec``; this states the rules that hold no matter which one runs.
SYSTEM_PROMPT = """You answer questions about where music genres came from and how they connect, using \
only a graph of documented influences.

Start by resolving every genre the user named to a node id. Then use whichever tool answers the question \
that was actually asked — one genre's origins, or the chain between two of them. Then stop and summarise \
what you found.

Two rules matter more than being helpful:
- If a genre does not resolve, this graph does not cover it. Say so. Do not substitute a similar genre.
- If a tool comes back empty, this graph has no sourced answer. Say so. Do not fill the gap from your \
own knowledge.

You are not the final word: everything you say is checked against the graph before the user sees it, \
and anything the graph does not support is discarded."""

SYNTHESIS_PROMPT = """Write two sentences stating what the genre came out of, using only the influences \
listed below. Name every one of them. Add nothing else: no dates, no places, no artists, no context \
that is not in the list. Do not hedge and do not editorialise."""

#: The chain form. Same rules, different shape: a sequence to walk rather than a set to list. It is a
#: separate constant rather than a branch inside one prompt because the failure modes differ — the risk
#: here is the model reordering the chain or inverting a hop, which is the one error that turns a correct
#: claim set into false music history.
CHAIN_SYNTHESIS_PROMPT = """Write two or three sentences tracing the chain of influence below, in the \
order given. Each genre listed came out of the one after it. Name every genre in the chain and keep them \
in that order. Add nothing else: no dates, no places, no artists, no context that is not in the chain. \
Do not hedge and do not editorialise."""


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
    tour is built on it.

    **Visit order is not descent order, and conflating them narrates false history.** A lineage query
    resolves both endpoints before it traces between them, so the visit order of
    "how is blues connected to heavy metal" starts *blues, heavy metal* — a client drawing an arrow
    down that list would state that heavy metal came out of the blues via blues rock in the wrong
    order. So the approved chain rides alongside as its own field rather than being inferred from this
    one, and it is empty whenever the answer is not a chain. Same distinction ``graph/structure.py``
    draws between undirected components and directed paths, at the event layer.
    """

    node_ids: tuple[str, ...]
    labels: tuple[str, ...]
    #: The approved chain, descendant-first. Empty for an origins query, and empty when a hop was
    #: rejected — a broken chain is not displayed as a chain.
    chain: tuple[str, ...] = ()
    chain_labels: tuple[str, ...] = ()


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
    #: Node ids descendant-first, when the approved claims form a chain the answer should be told as one.
    #: Empty for an origins query. **Every consecutive pair must itself be an approved claim** — checked
    #: below, because a chain is an ordering assertion about music history and an unchecked one could
    #: state a descent the gate never approved.
    chain: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        endpoints = {c.subject_id for c in self.claims} | {c.object_id for c in self.claims}
        extra = set(self.labels) - endpoints
        if extra:
            raise ValueError(
                f"labels contain node(s) no approved claim mentions: {sorted(extra)}. "
                f"Synthesis may only see the approved claim set."
            )
        if self.chain and not chain_is_approved(self.chain, self.claims):
            raise ValueError(
                f"chain {list(self.chain)} contains a hop no approved claim supports. "
                f"Synthesis may only see the approved claim set."
            )

    @property
    def subject_id(self) -> str | None:
        """The genre being asked about. At v0.1 every claim shares one subject.

        Unchanged by the chain, deliberately: a chain has no single subject, so this returns ``None``
        there — which is what ``synthesize`` branches on rather than inventing a head node.
        """
        subjects = {c.subject_id for c in self.claims}
        return subjects.pop() if len(subjects) == 1 else None

    def label_of(self, node_id: str) -> str:
        return self.labels.get(node_id, node_id)

    def __bool__(self) -> bool:
        return bool(self.claims)


def chain_is_approved(chain: tuple[str, ...], claims: tuple[Claim, ...]) -> bool:
    """Is every hop of ``chain`` an approved claim, in that orientation?

    A chain of one node or none is not a chain. Orientation is not negotiable: ``(a, b)`` means *a came
    out of b*, and accepting the reverse would let a chain narrate influence backwards in time out of a
    claim set that never said so.
    """
    if len(chain) < 2:
        return False
    approved = {(c.subject_id, c.object_id) for c in claims}
    return all(pair in approved for pair in pairwise(chain))


def synthesize(claim_set: ApprovedClaimSet, llm: LLM) -> Iterator[str]:
    """Prose from approved claims, and nothing but approved claims.

    Note the signature. There is no ``query`` parameter, no ``store``, no ``GateResult``, no message
    history. If a future change needs one of those here, that change is reintroducing the leak. The
    chain form added in phase 2 obeys that: the ordering rides *inside* the claim set, where it was
    validated against the approved claims, rather than arriving as a second argument.
    """
    if not claim_set:
        raise ValueError(
            "synthesize() called with no approved claims; the caller must refuse instead"
        )

    if claim_set.chain:
        labelled = [claim_set.label_of(node_id) for node_id in claim_set.chain]
        prompt = f"{CHAIN_SYNTHESIS_PROMPT}\n\nChain: {dumps(labelled)}"
    else:
        subject = claim_set.label_of(claim_set.subject_id or "")
        influences = [claim_set.label_of(c.object_id) for c in claim_set.claims]
        prompt = (
            f"{SYNTHESIS_PROMPT}\n\nGenre: {subject}\nDocumented influences: {dumps(influences)}"
        )

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
    chain: tuple[str, ...] = ()

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
            # The longest chain any single tool asserted. Read generically off ``ToolResult`` — the loop
            # does not know which tool sets it, which is what keeps invariant 4 intact while the answer
            # gains an ordering. It is a *candidate* only: nothing is narrated as a chain until the gate
            # has approved every hop, checked below.
            if len(result.chain) > len(chain):
                chain = result.chain
            for node_id in result.visited:
                if node_id not in visited:
                    visited.append(node_id)

            messages.append(tool_result_message(use.id, result.content, is_error=result.is_error))

    decision: GateResult = gate(proposals, store)
    for claim in decision.approved:
        yield ClaimApproved(claim)
    for rejection in decision.rejected:
        yield ClaimRejected(rejection)

    # A hop the gate rejected breaks the chain, and a broken chain must not be told as one — the honest
    # fallback is the claims that did survive, listed rather than sequenced.
    approved_chain = chain if chain_is_approved(chain, decision.approved) else ()

    labels = {node_id: _label(store, node_id) for node_id in (*visited, *approved_chain)}
    yield PathWalked(
        node_ids=tuple(visited),
        labels=tuple(labels[node_id] for node_id in visited),
        chain=approved_chain,
        chain_labels=tuple(labels[node_id] for node_id in approved_chain),
    )

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
            chain=approved_chain,
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
