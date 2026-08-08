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

**The plan is inspectable, and it is not an authority.** Phase 3 step 3 puts a planning turn ahead of the
traversal, so a run opens by saying what it intends to do. Execution never consults it: the model drives
the registry turn by turn exactly as before. That split is the point — a plan that decided control flow
would be a second, ungated way for the model to steer the answer, and it would make divergence
unmeasurable by making it impossible.

Step 3b reads exactly one field of it back, ``asserted_premise``, and reads it into the **proposal list**
rather than into a branch. What the question assumed is language, so the model is the right author; what
the graph holds is data, so ``gate()`` is the right judge. The premise arrives with no privileges — same
gate, same rejection reasons, same event — and the correction it can produce asserts nothing beyond the
claims that gate already approved.

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
from musical_mycelium.agent.plan import Plan, parse_plan, planning_prompt
from musical_mycelium.agent.tools import ToolRegistry
from musical_mycelium.graph.memory import resolve_exact
from musical_mycelium.graph.schema import PREDICATE_INFLUENCED_BY
from musical_mycelium.graph.store import GraphStore

#: Hard ceiling on model turns, **planning turn included**. It is a **cost control** as much as a safety
#: one — an agentic loop re-sends its accumulated context every turn, so an unbounded loop is an
#: unbounded bill (``.claude/rules/aws-and-cost.md``).
#:
#: Raised from 4 to 5 at phase 2 step 5. A lineage question needs **three** tool turns — resolve, resolve,
#: trace — plus a final text turn, which consumed the whole v0.1 budget and left a real model no room to
#: recover from one bad argument. One turn of slack, not a blank cheque.
#:
#: Raised from 5 to 6 at phase 3 step 3, which is the plan turn and nothing else: the ceiling counts
#: total model turns, so adding planning without this would have silently spent the slack rather than
#: added a turn.
#:
#: Raised from 6 to 8 at phase 3 step 4, sized against the shape a run now has: one plan turn, up to six
#: tool turns, one text turn. Seven registered tools and a graph that reaches six hops mean a real
#: question can legitimately need more than the three tool turns v0.1 was sized for.
MAX_TURNS = 8

#: The other half of the budget, and the half that actually bounds spend. **A turn count is a poor proxy
#: for cost**: an agentic loop re-sends its whole accumulated context every turn, so eight turns carrying
#: large tool payloads can cost many multiples of eight ordinary ones. One pathological query — a
#: coverage dump followed by a wide fan-out — bills far more than the turn cap suggests it can.
#:
#: Checked against the running ``Usage`` after each turn, so it bounds what has *already* been spent
#: rather than predicting what the next turn will cost. Exceeding it stops the loop cleanly and gates
#: whatever was collected; a truncated run still answers from its approved claims rather than erroring.
#:
#: The number is a ceiling on the pathological case, not a target. A normal lineage run is well under it.
MAX_ACCUMULATED_TOKENS = 60_000

#: A plan is a small JSON object. Capping it separately keeps a model that decides to think out loud
#: from billing a full answer's worth of output before the traversal has even started.
PLAN_MAX_TOKENS = 400

#: The model stopped asking for tools, which is the ordinary ending: **the stop condition is a judgment,
#: not a step count**. The caps below are the failure endings, and they are named rather than inferred
#: from a count so that "this answer may be incomplete" is a fact the run reports about itself.
STOP_COMPLETE = "complete"
STOP_MAX_TURNS = "max_turns"
STOP_MAX_TOKENS = "max_tokens"

#: Deliberately free of tool names. v0.1's prompt hard-coded the two-step procedure — "use resolve_node,
#: then get_influences" — which meant a third tool needed a prompt edit inside the loop module to ever be
#: called. That is invariant 4 leaking through the prose door rather than the code door. Each tool
#: describes itself in its own ``toolSpec``; this states the rules that hold no matter which one runs.
SYSTEM_PROMPT = """You answer questions about where music came from and how it connects, using only a \
graph of documented influences between genres and between artists.

Start by resolving every genre or artist the user named to a node id. Then use whichever tools answer \
the question that was actually asked. Then stop and summarise what you found.

Rules that matter more than being helpful:
- If a name does not resolve, this graph does not cover it. Say so. Do not substitute something \
similar, even when close matches are suggested to you.
- If a tool comes back empty, this graph has no sourced answer. Say so. Do not fill the gap from your \
own knowledge.
- Influence runs between two genres, or between two artists. Never between a genre and an artist.
- This graph's coverage is uneven. Where it is thin on what was asked, say what is missing rather than \
answering as though it were complete.

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

#: The one addition to a synthesis prompt, appended when the question had it backwards. It reads as an
#: exception to the "add nothing else" rule above and is worded to say so, since it *is* one.
#:
#: **The forbidden sentence is a negative claim, and this corpus cannot support one.** "Heavy metal did
#: not influence the blues" sounds like the obvious answer and is unsupportable: **542 of the 973 nodes
#: have no outgoing edges at all**, so a missing edge is overwhelmingly not evidence of a missing
#: influence. That is CONCENTRATION IS NOT ABSENCE and "grounded means traceable, not correct" landing on
#: one sentence, and shipping the confident "no" would put the exact slide this project exists to prevent
#: into the user-facing copy.
#:
#: Note what the permitted framing costs: nothing. It selects an opening for a chain the gate already
#: approved, and asserts nothing beyond it. That is why this field does not touch invariant 1.
INVERTED_PREMISE_PROMPT = """The question asked whether the first name below came out of the second. \
This graph documents the influence running the other way.

Open by saying that — that in this graph the influence runs the other way — and then state what the \
graph does document, as instructed above. That opening is the one addition permitted.

State only the direction this graph documents. Do not repeat the question's direction as though it were \
so, and do not deny it either: this graph records the influences it holds sources for and says nothing \
whatever about the rest, so "did not influence" would claim far more than it can support."""


# --- events ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Planned:
    """What the agent said it would do, emitted before it does any of it.

    First event of every run, without exception — including when the plan failed to parse, because a run
    with no ``query_kind`` is a run that cannot be sliced by query type (DoD #7). The degraded value is
    ``unknown``, never absent.

    ``unregistered`` is the plan naming a tool that does not exist. Reported here rather than raised: the
    plan is a proposal and never drives execution, so the model being wrong about its own toolbox is a
    measurement, not a failure.
    """

    plan: Plan
    unregistered: tuple[str, ...] = ()


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
    """**Divergence is data, not an error.** An agent that plans three steps and takes five has told us
    something worth measuring, so both counts ride here rather than the loop enforcing agreement. This
    is what ``plan_adherence`` is computed from in phase 4."""

    usage: Usage
    claim_count: int
    rejection_count: int
    model_id: str
    planned_steps: int
    executed_steps: int
    #: Why the traversal stopped. **A truncated answer must never be presented as a complete one** — a
    #: run that hit a cap may have stopped one tool call short of the edge that mattered, and it will
    #: read exactly like a confident short answer unless it says so. This is the field that lets a
    #: client, and the eval harness, tell the two apart.
    stop_reason: str = STOP_COMPLETE


Event = Planned | ToolCalled | ClaimApproved | ClaimRejected | PathWalked | Token | Refused | Done


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
    #: ``(subject, object)`` as the **question** put it, when the question had the direction backwards.
    #: Empty otherwise, which is the overwhelming majority of runs. Annotated ``tuple[str, ...]`` rather
    #: than the ``tuple[str, str]`` §4.3 wrote, so that the empty default is not a type error; the
    #: length is checked below instead, where the admissibility rule already lives.
    #:
    #: It rides here rather than arriving as a second argument to ``synthesize`` for the same reason
    #: ``chain`` does, and it is admissible under the same rule: **only when the approved claims
    #: establish the reverse**. A correction the gate did not produce cannot be constructed.
    inverted_premise: tuple[str, ...] = ()

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
        if self.inverted_premise and not self._premise_is_approved():
            raise ValueError(
                f"inverted premise {list(self.inverted_premise)} is not established in reverse by the "
                f"approved claims. Synthesis may only see the approved claim set."
            )

    def _premise_is_approved(self) -> bool:
        if len(self.inverted_premise) != 2:
            return False
        subject, obj = self.inverted_premise
        return descent_is_approved(obj, subject, self.claims)

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


def descent_is_approved(descendant: str, ancestor: str, claims: tuple[Claim, ...]) -> bool:
    """Do the approved claims establish that ``descendant`` came out of ``ancestor``, at any depth?

    Reachability rather than adjacency, because a premise can be backwards across two hops
    (``adv_012``: heavy metal, blues rock, blues) as readily as one (``adv_013``). Orientation follows
    the same rule ``chain_is_approved`` obeys — a claim ``(s, o)`` means *s came out of o*, so the walk
    steps subject to object and never the other way.

    This is deliberately **not** ``chain``. A chain is one ordering a tool asserted and the gate then
    confirmed; this asks a question of the approved set itself, so a reverse established by a fan-out of
    claims that never formed a chain still counts. Nothing is narrated from it either way: it only
    decides whether a framing is admissible.
    """
    if descendant == ancestor:
        return False
    ancestors_of: dict[str, list[str]] = {}
    for claim in claims:
        ancestors_of.setdefault(claim.subject_id, []).append(claim.object_id)

    seen = {descendant}
    frontier = [descendant]
    while frontier:
        node = frontier.pop()
        for next_node in ancestors_of.get(node, ()):
            if next_node == ancestor:
                return True
            if next_node not in seen:
                seen.add(next_node)
                frontier.append(next_node)
    return False


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
        prompt = f"{CHAIN_SYNTHESIS_PROMPT}{_reversal(claim_set)}\n\nChain: {dumps(labelled)}"
    else:
        subject = claim_set.label_of(claim_set.subject_id or "")
        influences = [claim_set.label_of(c.object_id) for c in claim_set.claims]
        prompt = (
            f"{SYNTHESIS_PROMPT}{_reversal(claim_set)}"
            f"\n\nGenre: {subject}\nDocumented influences: {dumps(influences)}"
        )

    yield from llm.stream([user_message(prompt)], max_tokens=200)


def _reversal(claim_set: ApprovedClaimSet) -> str:
    """The reversal block, or nothing at all. Appended to either synthesis prompt rather than forking a
    third: the instruction is the same whether the answer is a chain or a fan-out, and the two prompts
    already differ for a reason that has nothing to do with the premise.

    ``Asked as`` carries labels, never ids — synthesis has never seen a node id and does not start now.
    Both labels come off the approved claim set, where ``__post_init__`` already established that every
    node named here is an endpoint of an approved claim.
    """
    if not claim_set.inverted_premise:
        return ""
    asked = [claim_set.label_of(node_id) for node_id in claim_set.inverted_premise]
    return f"\n\n{INVERTED_PREMISE_PROMPT}\n\nAsked as: {dumps(asked)}"


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
    max_accumulated_tokens: int = MAX_ACCUMULATED_TOKENS,
) -> Iterator[Event]:
    """Answer one question, emitting events as it goes.

    Order is deliberate: plan, then tools, then gating, then the path, then prose. Prose is generated
    **after** the gate has run and only from what survived it.

    The plan turn is the one addition phase 3 step 3 makes here, and note what it is *not*: no branch
    below reads ``plan``. Execution is unchanged — the model still drives the registry turn by turn — so
    the plan is inspectable without becoming a control-flow mechanism. Step 3b's ``asserted_premise`` is
    read into the proposals and nowhere else. If a later change makes the loop branch on ``plan.steps``,
    the plan has stopped being a proposal and that change is wrong.
    """
    messages: list[dict[str, object]] = [user_message(query)]
    tool_config = registry.tool_config()
    usage = Usage()
    proposals: list[ClaimProposal] = []
    visited: list[str] = []
    chain: tuple[str, ...] = ()
    executed = 0

    # Its own call, with its own system prompt and **no tool config**: the planning turn is asked for
    # JSON, not for tool use, and handing it the toolbox invites it to start walking mid-plan.
    plan_response = llm.converse(
        [user_message(query)], system=planning_prompt(registry), max_tokens=PLAN_MAX_TOKENS
    )
    usage = usage + plan_response.usage
    plan = parse_plan(plan_response.text)
    yield Planned(plan=plan, unregistered=plan.unregistered(registry))

    # The one thing below that reads the plan back, and note what it reads: not a step, not a tool, not
    # an argument. Nothing here touches control flow — ``premise`` is a proposal that goes through the
    # same gate as every proposal a tool made, with no special path and no privileged outcome.
    premise = premise_proposal(plan, store)

    # Falling out of the loop without breaking means the turns ran out, so this is the pessimistic
    # default and the ordinary ending has to be claimed explicitly. The other way round, a future edit
    # that adds an exit path gets ``complete`` for free and reports a truncated run as a finished one.
    stop_reason = STOP_MAX_TURNS

    # ``max_turns`` counts the plan turn, so what is left is the execution budget. Spending it here
    # rather than adding a turn is what keeps the ceiling an honest statement of what a run can cost.
    for _turn in range(max_turns - 1):
        response = llm.converse(messages, system=SYSTEM_PROMPT, tool_config=tool_config)
        usage = usage + response.usage

        # **The stop condition is a judgment, not a step count.** The model deciding it has enough is
        # the ordinary ending; the two caps below are the failure endings.
        if not response.wants_tools:
            stop_reason = STOP_COMPLETE
            break

        messages.append(assistant_tool_use_message(response))
        for use in response.tool_uses:
            result = registry.invoke(use.name, use.arguments)
            executed += 1
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

        # Checked *after* the turn, against what has already been spent rather than a prediction of the
        # next turn's cost. Stopping here is clean rather than exceptional: everything collected so far
        # still goes through the gate below and still produces a grounded answer — the run just says on
        # the way out that it stopped early, so the answer is not read as a complete one.
        if usage.total_tokens >= max_accumulated_tokens:
            stop_reason = STOP_MAX_TOKENS
            break

    # The premise goes first so its verdict is the substantive one. Gated last, a premise a tool
    # happened to propose too would come back DUPLICATE, and "already claimed" is not an answer to
    # "is this what the question assumed".
    decision: GateResult = gate([*([premise] if premise else []), *proposals], store)
    for claim in decision.approved:
        yield ClaimApproved(claim)
    for rejection in decision.rejected:
        yield ClaimRejected(rejection)

    # A hop the gate rejected breaks the chain, and a broken chain must not be told as one — the honest
    # fallback is the claims that did survive, listed rather than sequenced.
    approved_chain = chain if chain_is_approved(chain, decision.approved) else ()
    inverted_premise = _inverted_premise(premise, decision)

    labels = {node_id: _label(store, node_id) for node_id in (*visited, *approved_chain)}
    yield PathWalked(
        node_ids=tuple(visited),
        labels=tuple(labels[node_id] for node_id in visited),
        chain=approved_chain,
        chain_labels=tuple(labels[node_id] for node_id in approved_chain),
    )

    if not decision.approved:
        # Axis-neutral wording. These strings said "genre" until the artist axis landed at v0.4.0, at
        # which point a refusal on "U2" told the user the graph has no such *genre* — true of a word
        # nobody used, and misleading about what was actually asked.
        reason = (
            "it resolved but carries no sourced influences"
            if visited
            else "it is not in this graph"
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
            inverted_premise=inverted_premise,
        )
        for chunk in synthesize(claim_set, llm):
            yield Token(chunk)

    yield Done(
        usage=usage,
        claim_count=len(decision.approved),
        rejection_count=len(decision.rejected),
        model_id=llm.model_id,
        planned_steps=len(plan.steps),
        executed_steps=executed,
        stop_reason=stop_reason,
    )


def premise_proposal(plan: Plan, store: GraphStore) -> ClaimProposal | None:
    """The question's asserted premise as a gateable proposal, or ``None``.

    Two names become two node ids through ``resolve_exact``, which is the same rule the resolving tool
    answers the model with — so the premise resolves no more loosely than the traversal did, and the
    loop borrows the rule from ``graph`` rather than learning which tool owns it. Either name failing
    to resolve yields ``None``, and ``None`` means no premise, no rejection to notice, and no
    correction. **The degraded outcome is saying nothing**, which is the right one: the cost of missing
    a backwards question is a slightly worse answer, and the cost of inventing one is telling a user
    they asked something they did not.
    """
    if plan.asserted_premise is None:
        return None
    subject = resolve_exact(store, plan.asserted_premise.subject)
    obj = resolve_exact(store, plan.asserted_premise.object)
    if subject is None or obj is None:
        return None
    return ClaimProposal(subject_id=subject.id, predicate=PREDICATE_INFLUENCED_BY, object_id=obj.id)


def _inverted_premise(premise: ClaimProposal | None, decision: GateResult) -> tuple[str, ...]:
    """``(subject, object)`` as asked, when the question was backwards. Empty otherwise.

    **Both conditions, deliberately.** The gate must have *rejected* the premise, and the approved
    claims must establish the *reverse*. A premise the gate approved needs no correction; a premise
    rejected with no reverse available — "did polka influence hip-hop?" — is an ordinary refusal with
    nothing to correct, and dressing it up as a reversal would assert a direction nobody sourced.
    """
    if premise is None:
        return ()
    if not any(rejection.proposal == premise for rejection in decision.rejected):
        return ()
    if not descent_is_approved(premise.object_id, premise.subject_id, decision.approved):
        return ()
    return (premise.subject_id, premise.object_id)


def _label(store: GraphStore, node_id: str) -> str:
    node = store.get_node(node_id)
    return node.label if node else node_id
