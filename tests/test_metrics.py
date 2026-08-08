"""Metric tests — the metrics measuring themselves.

``.claude/rules/evals.md`` requires this and says why: *"A metric you have not tried to break is not a
metric."* That section exists because of a real difflib coverage bug in a previous project, where the
number looked healthy and meant nothing.

So every case here is **synthetic, with the answer known by construction**: a claim set assembled to make
the score obviously 1.0, 0.5, 0.0 or undefined, checked against a graph small enough to hold in your head.
The pinned artifact appears only where the point is that the metric agrees with real data.
"""

from __future__ import annotations

import pytest

from musical_mycelium.agent.claims import Claim, ClaimProposal, gate
from musical_mycelium.eval.metrics import Groundedness, edge_groundedness
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import (
    NODE_KIND_GENRE,
    VERIFICATION_PROSE_AUTO,
    Artifact,
    Edge,
    Node,
)

INFLUENCED_BY = "influenced_by"
WHEN = "2026-01-01T00:00:00+00:00"

# A three-edge graph where every answer is countable by eye:
#   Q2 <- Q1,  Q3 <- Q1,  Q3 <- Q2
STATEMENTS = {
    ("Q2", "Q1"): "http://www.wikidata.org/entity/statement/Q2-AAA",
    ("Q3", "Q1"): "http://www.wikidata.org/entity/statement/Q3-BBB",
    ("Q3", "Q2"): "http://www.wikidata.org/entity/statement/Q3-CCC",
}


@pytest.fixture(scope="module")
def toy() -> InMemoryGraphStore:
    nodes = tuple(
        Node(
            id=q,
            label=f"genre {q}",
            source="wikidata",
            source_id=q,
            retrieved_at=WHEN,
            kind=NODE_KIND_GENRE,
        )
        for q in ("Q1", "Q2", "Q3", "Q4")
    )
    edges = tuple(
        Edge(
            subject_id=subject,
            predicate=INFLUENCED_BY,
            object_id=obj,
            source="wikidata",
            source_id=statement,
            retrieved_at=WHEN,
            prose_tier="PROSE",
            verification=VERIFICATION_PROSE_AUTO,
        )
        for (subject, obj), statement in STATEMENTS.items()
    )
    return InMemoryGraphStore(Artifact(nodes=nodes, edges=edges))


def claim(subject: str, obj: str, source: str | None = None) -> Claim:
    return Claim(
        subject_id=subject,
        predicate=INFLUENCED_BY,
        object_id=obj,
        source_ids=(source or STATEMENTS.get((subject, obj), "http://example.invalid/made-up"),),
        verification=VERIFICATION_PROSE_AUTO,
    )


# --- the vacuous-truth guard --------------------------------------------------------------------


def test_an_empty_output_does_not_score_one_hundred_percent(toy: InMemoryGraphStore) -> None:
    """The guard ``.claude/rules/evals.md`` names by name. A system that asserts nothing is not perfectly
    grounded; its groundedness is undefined. Scoring it 1.0 would make "refuse everything" the winning
    strategy on the headline metric."""
    result = edge_groundedness([], toy)
    assert result.total == 0
    assert result.score is None
    assert result.score != 1.0


def test_an_empty_output_does_not_pass_the_blocking_check(toy: InMemoryGraphStore) -> None:
    """The other half of the guard, and the one that actually protects CI. ``score is None`` is only
    useful if the pass/fail branch treats it as a failure rather than tripping over it."""
    assert not edge_groundedness([], toy).is_fully_grounded


def test_undefined_renders_as_undefined_not_as_a_number(toy: InMemoryGraphStore) -> None:
    """A report that prints "0.0%" or "100.0%" for an empty run teaches the reader the wrong thing."""
    assert str(edge_groundedness([], toy)) == "groundedness: undefined (0 claims)"


# --- scores known by construction ---------------------------------------------------------------


def test_all_grounded_scores_one(toy: InMemoryGraphStore) -> None:
    result = edge_groundedness([claim("Q2", "Q1"), claim("Q3", "Q1"), claim("Q3", "Q2")], toy)
    assert result.score == 1.0
    assert result.is_fully_grounded
    assert result.ungrounded == ()


def test_none_grounded_scores_zero(toy: InMemoryGraphStore) -> None:
    result = edge_groundedness([claim("Q1", "Q2"), claim("Q1", "Q3")], toy)
    assert result.score == 0.0
    assert not result.is_fully_grounded
    assert len(result.ungrounded) == 2


def test_half_grounded_scores_one_half(toy: InMemoryGraphStore) -> None:
    result = edge_groundedness([claim("Q2", "Q1"), claim("Q1", "Q2")], toy)
    assert result.score == 0.5
    assert result.grounded == 1
    assert result.total == 2


def test_one_of_three_scores_one_third(toy: InMemoryGraphStore) -> None:
    result = edge_groundedness([claim("Q2", "Q1"), claim("Q1", "Q2"), claim("Q4", "Q1")], toy)
    assert result.score == pytest.approx(1 / 3)


# --- the ways a claim can fail to be grounded ----------------------------------------------------


def test_a_reversed_edge_is_not_grounded(toy: InMemoryGraphStore) -> None:
    """``Q2 <- Q1`` is in the graph; ``Q1 <- Q2`` is the same row read backwards. A metric that ignored
    direction would score an inverted history at 100%."""
    assert edge_groundedness([claim("Q1", "Q2")], toy).score == 0.0


def test_an_edge_between_unconnected_real_nodes_is_not_grounded(toy: InMemoryGraphStore) -> None:
    assert edge_groundedness([claim("Q4", "Q1")], toy).score == 0.0


def test_a_true_edge_with_a_fabricated_citation_is_not_grounded(toy: InMemoryGraphStore) -> None:
    """The subtle one. The triple is real, so a triple-only metric scores it 1.0 — but the citation names
    a statement that edge does not carry, and an unfollowable citation is a grounding failure. This is
    the case that keeps ``edge_groundedness`` from decaying into a lookup."""
    forged = claim("Q2", "Q1", source="http://www.wikidata.org/entity/statement/Q2-NOPE")
    result = edge_groundedness([forged], toy)
    assert result.score == 0.0
    assert result.ungrounded == (forged,)


def test_a_claim_citing_an_unrelated_real_statement_is_not_grounded(
    toy: InMemoryGraphStore,
) -> None:
    """Citing Q3's statement in support of Q2's edge. Both exist; the pairing does not."""
    mismatched = claim("Q2", "Q1", source=STATEMENTS[("Q3", "Q1")])
    assert edge_groundedness([mismatched], toy).score == 0.0


# --- independence from the gate -------------------------------------------------------------------


def test_the_metric_agrees_with_the_gate_on_real_data() -> None:
    """They are computed independently and must reach the same verdict on the pinned artifact.

    If this ever fails, the disagreement is the finding. The metric does not call the gate precisely so
    that this test can mean something.
    """
    store = InMemoryGraphStore.from_directory(artifact_directory())
    proposals = [
        ClaimProposal("Q193355", INFLUENCED_BY, "Q9759"),  # real
        ClaimProposal("Q221772", INFLUENCED_BY, "Q8341"),  # real
        ClaimProposal("Q9759", INFLUENCED_BY, "Q38848"),  # fabricated
    ]
    approved = gate(proposals, store).approved
    assert len(approved) == 2

    result = edge_groundedness(list(approved), store)
    assert result.is_fully_grounded, "everything the gate approved must measure as grounded"
    assert result.score == 1.0


def test_gated_output_for_a_refusal_case_is_undefined_not_perfect() -> None:
    """End to end on gold case 5. ``blues`` resolves, has no sourced parents, so the loop will propose
    nothing and the gate will approve nothing — and the metric must report undefined rather than handing
    a refusal a perfect score."""
    store = InMemoryGraphStore.from_directory(artifact_directory())
    assert store.neighbors("Q9759") == []

    result = edge_groundedness(list(gate([], store).approved), store)
    assert result.score is None
    assert not result.is_fully_grounded


# --- the result object itself -----------------------------------------------------------------------


def test_groundedness_formats_a_real_score() -> None:
    assert str(Groundedness(grounded=3, total=4)) == "groundedness: 75.0% (3/4)"
