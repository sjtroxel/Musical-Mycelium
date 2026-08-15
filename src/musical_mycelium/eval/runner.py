"""Drive one query through the real loop and collect what happened. Dataset-agnostic, provider-agnostic.

This module exists because `harness.py` could not be reused. It is the adversarial baseline and it is
adversarial all the way down: `DATASET` is a module constant, `run_case` builds its own `ScriptedLLM`
from an `Attack`, and its result type carries `forbidden_triples` bookkeeping that means nothing to a
gold case. Phase 4 needs the same driving for three different datasets against two different providers,
so the general half moves here and `harness.py` keeps the adversarial half.

**What this module knows: a query, a store, an LLM, a registry.** It does not know what a gold case is,
what an adversarial case is, or that a held-out set exists. Scoring lives in `metrics.py`, dataset
loading lives with each dataset, and the decision of which model to build lives in `agent/llm.py`
behind `build_llm`. This is the seam invariant 7 asks for finally being exercised by something other
than the API handler: the caller passes an `LLM` and this module never asks which one it is.

**Nothing here is allowed to interpret the events.** `CaseRun` is a transcript, not a verdict. Every
property on it is a projection of what the loop emitted, so that a metric computed from it is computed
from the run rather than from this module's opinion of the run. The one thing it does assert is that a
`Done` arrived, because a loop that ended without one is broken in a way that would otherwise show up
as a plausible-looking zero.
"""

from __future__ import annotations

from dataclasses import dataclass

from musical_mycelium.agent.claims import Claim, Rejection
from musical_mycelium.agent.llm import LLM, Usage
from musical_mycelium.agent.loop import (
    MAX_ACCUMULATED_TOKENS,
    MAX_TURNS,
    STOP_COMPLETE,
    ClaimApproved,
    ClaimRejected,
    Done,
    PathWalked,
    Planned,
    Refused,
    Token,
    ToolCalled,
    run,
)
from musical_mycelium.agent.plan import Plan
from musical_mycelium.agent.tools import ToolRegistry, default_registry
from musical_mycelium.graph.store import GraphStore


class RunIncomplete(RuntimeError):
    """The loop ended without a ``Done``. Raised rather than tolerated.

    A run with no ``Done`` has no usage, no stop reason, and no claim count, and every metric computed
    from it would still return a number — a confident zero that reads exactly like a model that found
    nothing. Failing loudly here is the difference between a broken harness and a bad score.
    """


@dataclass(frozen=True, slots=True)
class CaseRun:
    """One query's transcript. A record of what the loop did, with no judgement attached.

    ``visited`` is **visit order, not descent order** — see ``PathWalked``'s docstring, which is
    emphatic about it. A lineage query resolves both endpoints before tracing between them, so reading
    this list as a lineage states the history in the wrong order. ``traversal_recall`` and
    ``traversal_precision`` are both set-valued for exactly this reason and are safe to compute from it;
    anything order-sensitive is not, and must read the approved chain instead.
    """

    query: str
    plan: Plan
    #: Tools the plan named that do not exist. A measurement, not a failure — the plan never drives
    #: execution, so a model being wrong about its own toolbox is data.
    unregistered: tuple[str, ...]
    tool_calls: tuple[ToolCalled, ...]
    approved: tuple[Claim, ...]
    rejections: tuple[Rejection, ...]
    visited: tuple[str, ...]
    refused: bool
    #: Why, when it refused. Empty otherwise. Refusal is correct behaviour, not an error state.
    refusal_reason: str
    prose: str
    done: Done

    @property
    def traversal_usage(self) -> Usage:
        return self.done.usage

    @property
    def synthesis_usage(self) -> Usage:
        return self.done.synthesis_usage

    @property
    def total_tokens(self) -> int:
        """Both halves summed, for budgeting only.

        ``Done`` keeps traversal and synthesis usage separate on purpose, because two models price
        differently and a combined count cannot be turned into dollars by anyone downstream. Summing is
        admissible *here* because a token budget counts tokens against a per-model daily cap and asks no
        question about money. Do not reach for this when computing cost.
        """
        return self.traversal_usage.total_tokens + self.synthesis_usage.total_tokens

    @property
    def truncated(self) -> bool:
        """Whether the traversal stopped early. A truncated answer must never be reported as a complete
        one — it may have stopped one tool call short of the edge that mattered and will read like a
        confident short answer unless something says otherwise."""
        return self.done.stop_reason != STOP_COMPLETE

    @property
    def rejection_reasons(self) -> tuple[str, ...]:
        return tuple(str(rejection.reason) for rejection in self.rejections)


def run_case(
    query: str,
    *,
    store: GraphStore,
    llm: LLM,
    registry: ToolRegistry | None = None,
    synthesis_llm: LLM | None = None,
    max_turns: int = MAX_TURNS,
    max_accumulated_tokens: int = MAX_ACCUMULATED_TOKENS,
) -> CaseRun:
    """Drive one query through ``agent.loop.run`` and collect the event stream into a ``CaseRun``.

    ``registry`` defaults to ``default_registry(store)`` — the same registry the API uses. Driving a new
    dataset must never require a bespoke registry, because invariant 4 says adding a tool cannot require
    editing the loop and the converse holds too: driving the loop cannot require editing the tools. A
    caller passing its own registry is doing something deliberate, such as the hostile stub tool in
    ``tests/test_untrusted.py``.
    """
    tools = registry if registry is not None else default_registry(store)

    plan = Plan()
    unregistered: tuple[str, ...] = ()
    tool_calls: list[ToolCalled] = []
    approved: list[Claim] = []
    rejections: list[Rejection] = []
    visited: tuple[str, ...] = ()
    refused = False
    refusal_reason = ""
    prose_parts: list[str] = []
    done: Done | None = None

    events = run(
        query,
        llm=llm,
        store=store,
        registry=tools,
        synthesis_llm=synthesis_llm,
        max_turns=max_turns,
        max_accumulated_tokens=max_accumulated_tokens,
    )
    for event in events:
        match event:
            case Planned():
                plan = event.plan
                unregistered = event.unregistered
            case ToolCalled():
                tool_calls.append(event)
            case ClaimApproved():
                approved.append(event.claim)
            case ClaimRejected():
                rejections.append(event.rejection)
            case PathWalked():
                visited = event.node_ids
            case Token():
                prose_parts.append(event.text)
            case Refused():
                refused = True
                refusal_reason = event.reason
            case Done():
                done = event

    if done is None:
        raise RunIncomplete(f"the loop ended without a Done event: {query!r}")

    return CaseRun(
        query=query,
        plan=plan,
        unregistered=unregistered,
        tool_calls=tuple(tool_calls),
        approved=tuple(approved),
        rejections=tuple(rejections),
        visited=visited,
        refused=refused,
        refusal_reason=refusal_reason,
        prose="".join(prose_parts),
        done=done,
    )
