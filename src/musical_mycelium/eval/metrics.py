"""Tier 1 metrics: deterministic, free, and run on every commit.

The headline correctness metric is a dictionary lookup rather than a model call, because the ground truth
is a graph we own. That is the whole reason "grounded" is a provable property here instead of a marketing
word (``.claude/rules/evals.md``).

**These metrics deliberately re-derive what the gate already decided, and do not call the gate.** A
measurement that asks the gate whether the gate was right measures nothing. ``edge_groundedness`` reads
the artifact directly and reaches its own verdict; if it and the gate ever disagree, that disagreement is
a finding rather than an inconsistency to paper over. The type ``Claim`` is imported because it is the
subject of the measurement; none of the gate's logic is.

Only ``edge_groundedness`` is in scope for v0.1. No thresholds are invented for anything else, because
there is no baseline yet.
"""

from __future__ import annotations

from dataclasses import dataclass

from musical_mycelium.agent.claims import Claim
from musical_mycelium.graph.schema import Edge
from musical_mycelium.graph.store import Direction, GraphStore


@dataclass(frozen=True, slots=True)
class Groundedness:
    """The result of one groundedness measurement.

    ``score`` is **``None``, not ``1.0``, when there are no claims.** An answer that asserts nothing has
    an undefined groundedness, not a perfect one, and this is the guard
    ``.claude/rules/evals.md`` names explicitly: *"an empty output must not score 100% groundedness."*
    Returning a float there would make a system that refuses everything look flawless, which is the exact
    failure the rule about reporting refusal as a pair exists to prevent.
    """

    grounded: int
    total: int
    ungrounded: tuple[Claim, ...] = ()

    @property
    def score(self) -> float | None:
        if self.total == 0:
            return None
        return self.grounded / self.total

    @property
    def is_fully_grounded(self) -> bool:
        """The blocking condition. ``.claude/rules/evals.md`` sets it at 100%, so it is not invented here.

        Note the ``total > 0``: a claim set that is empty is **not** fully grounded. That keeps the
        vacuous case out of the passing branch rather than relying on every caller to remember.
        """
        return self.total > 0 and self.grounded == self.total

    def __str__(self) -> str:
        if self.score is None:
            return "groundedness: undefined (0 claims)"
        return f"groundedness: {self.score:.1%} ({self.grounded}/{self.total})"


def edge_groundedness(claims: list[Claim], store: GraphStore) -> Groundedness:
    """What fraction of the asserted claims exist as edges in the pinned artifact, with the cited sources.

    A claim is grounded when both hold:

    1. the artifact contains an edge matching its ``(subject, predicate, object)``, and
    2. every ``source_id`` the claim cites is actually carried by that edge.

    Check 2 is what stops the metric from degrading into a triple lookup. A claim can name a real edge and
    still cite a source that edge does not carry — a plausible citation attached to a true statement — and
    that is a citation failure, not a grounding success.
    """
    grounded = 0
    ungrounded: list[Claim] = []

    for claim in claims:
        edge = _matching_edge(claim, store)
        if edge is not None and set(claim.source_ids) <= {edge.source_id}:
            grounded += 1
        else:
            ungrounded.append(claim)

    return Groundedness(grounded=grounded, total=len(claims), ungrounded=tuple(ungrounded))


def _matching_edge(claim: Claim, store: GraphStore) -> Edge | None:
    for edge in store.neighbors(claim.subject_id, Direction.INFLUENCED_BY):
        if edge.object_id == claim.object_id and edge.predicate == claim.predicate:
            return edge
    return None
