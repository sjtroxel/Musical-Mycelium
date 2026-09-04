"""Corroboration and ``contested``, phase 6 step 5.

**These tests exist to hold one distinction that is easy to lose and expensive to lose quietly:**
``contested`` means *two sources disagree*, not *a reciprocal pair exists*. Measured on v0.7.0 the corpus
holds 6 reciprocal pairs and only 2 are contested, so the loose definition overcounts by 3x and would
report "our sources disagree" about four pairs where one source is describing mutual influence.

The other job here is the mirror of ``test_claims``'s old unreachability lock. That test asserted no
artifact edge could produce ``contested``; this one asserts it now can, and on exactly the right pairs.
A state that moves from unreachable to reachable needs a test on **both** sides of the move, or the
declaration was never load-bearing.
"""

from __future__ import annotations

from musical_mycelium.graph.corroboration import (
    ContestedPair,
    contested_pairs,
    corroborated_edges,
    reciprocal_pairs,
    summary,
)
from musical_mycelium.graph.schema import (
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    PREDICATE_PLAYS_GENRE,
    SOURCE_DBPEDIA,
    SOURCE_WIKIDATA,
    VERIFICATION_INFOBOX_AUTO,
    VERIFICATION_PROSE_AUTO,
    Artifact,
    Edge,
    Node,
)

STAMP = "2026-09-04T00:00:00+00:00"


def _node(qid: str) -> Node:
    return Node(
        id=qid,
        label=qid.lower(),
        kind=NODE_KIND_GENRE,
        source=SOURCE_WIKIDATA,
        source_id=qid,
        retrieved_at=STAMP,
    )


def _edge(
    subject: str,
    obj: str,
    source: str = SOURCE_WIKIDATA,
    corroboration: str | None = None,
    predicate: str = PREDICATE_INFLUENCED_BY,
) -> Edge:
    return Edge(
        subject_id=subject,
        predicate=predicate,
        object_id=obj,
        source=source,
        source_id=f"http://example/{subject}",
        retrieved_at=STAMP,
        prose_tier="PROSE",
        verification=(
            VERIFICATION_INFOBOX_AUTO if source == SOURCE_DBPEDIA else VERIFICATION_PROSE_AUTO
        ),
        corroboration=corroboration,
    )


def _artifact(*edges: Edge) -> Artifact:
    ids = {e.subject_id for e in edges} | {e.object_id for e in edges}
    return Artifact(nodes=tuple(_node(q) for q in sorted(ids)), edges=edges)


# --- the definition ------------------------------------------------------------------------------


def test_contested_requires_two_different_sources() -> None:
    """**The load-bearing test.** One source asserting both directions is not a disagreement.

    On v0.7.0 this is the difference between 2 and 6. A single source describing mutual influence
    between two genres is often a real claim, and reporting it as "our sources disagree" would state
    something false about where the corpus's information came from.
    """
    artifact = _artifact(
        _edge("Q1", "Q2", SOURCE_WIKIDATA),
        _edge("Q2", "Q1", SOURCE_DBPEDIA),
        _edge("Q3", "Q4", SOURCE_DBPEDIA),
        _edge("Q4", "Q3", SOURCE_DBPEDIA),
    )
    assert len(reciprocal_pairs(artifact)) == 2, "both pairs point both ways"
    contested = contested_pairs(artifact)
    assert len(contested) == 1, "only the cross-source pair is contested"
    assert {contested[0].a, contested[0].b} == {"Q1", "Q2"}
    assert set(contested[0].sources) == {SOURCE_WIKIDATA, SOURCE_DBPEDIA}


def test_a_single_source_asserting_both_directions_is_reciprocal_but_not_contested() -> None:
    """``post-rock <-> shoegaze`` is this case, it is Wikidata-only, and it predates DBpedia entirely."""
    artifact = _artifact(
        _edge("Q1", "Q2", SOURCE_WIKIDATA),
        _edge("Q2", "Q1", SOURCE_WIKIDATA),
    )
    assert len(reciprocal_pairs(artifact)) == 1
    assert contested_pairs(artifact) == ()


def test_a_pair_is_reported_once_not_once_from_each_end() -> None:
    """A pair reported twice would double every contested count that is ever published."""
    artifact = _artifact(
        _edge("Q2", "Q1", SOURCE_WIKIDATA),
        _edge("Q1", "Q2", SOURCE_DBPEDIA),
    )
    assert len(contested_pairs(artifact)) == 1


def test_one_directional_edges_are_not_contested() -> None:
    """The ordinary case: the overwhelming majority of the corpus points one way only."""
    artifact = _artifact(_edge("Q1", "Q2"), _edge("Q2", "Q3"), _edge("Q3", "Q4"))
    assert reciprocal_pairs(artifact) == ()
    assert contested_pairs(artifact) == ()


def test_membership_edges_are_never_reciprocal_or_contested() -> None:
    """``plays_genre`` is structural and makes no derivation claim, so it cannot disagree about one.

    Letting it in here would be the "membership reads as derivation" failure decision C1 forbids,
    arriving through a different door than the traversal filter closed in step 3.
    """
    artifact = _artifact(
        _edge("Q1", "Q2", predicate=PREDICATE_PLAYS_GENRE),
        _edge("Q2", "Q1", predicate=PREDICATE_PLAYS_GENRE),
    )
    assert reciprocal_pairs(artifact) == ()
    assert contested_pairs(artifact) == ()


def test_contested_direction_is_recorded_not_resolved() -> None:
    """The corpus flags the disagreement; it does not pick a winner.

    ``.claude/rules/grounding-and-claims.md``: musical influence is genuinely disputed, and the honest
    move is to surface the dispute rather than silently choose. Both edges survive and both are reachable
    from the pair.
    """
    forward = _edge("Q1", "Q2", SOURCE_WIKIDATA)
    reverse = _edge("Q2", "Q1", SOURCE_DBPEDIA)
    pair = contested_pairs(_artifact(forward, reverse))[0]
    assert isinstance(pair, ContestedPair)
    assert pair.a_from_b in (forward, reverse)
    assert pair.b_from_a in (forward, reverse)
    assert pair.a_from_b != pair.b_from_a


# --- corroboration -------------------------------------------------------------------------------


def test_corroboration_is_recorded_on_the_edge_and_does_not_touch_verification() -> None:
    """**The thing that must not happen.** A second source agreeing does not upgrade how well the first
    was checked. ``verification`` answers "how strongly was one source checked"; ``corroboration``
    answers "does a second source agree". Collapsing them is the error three files were corrected for.
    """
    edge = _edge("Q1", "Q2", SOURCE_WIKIDATA, corroboration="http://dbpedia.org/resource/Bebop")
    assert edge.verification == VERIFICATION_PROSE_AUTO, "unchanged by corroboration"
    assert corroborated_edges(_artifact(edge)) == (edge,)


def test_an_uncorroborated_edge_defaults_to_none_and_keeps_its_prior_meaning() -> None:
    """Additive, so every edge written before this field existed means exactly what it always did."""
    edge = _edge("Q1", "Q2")
    assert edge.corroboration is None
    assert corroborated_edges(_artifact(edge)) == ()


def test_summary_reports_reciprocal_beside_contested() -> None:
    """Never one without the other. A contested count alone cannot be read: a reader cannot tell whether
    the corpus has no mutual-influence pairs or four of them, and that gap is the finding."""
    artifact = _artifact(
        _edge("Q1", "Q2", SOURCE_WIKIDATA, corroboration="http://dbpedia.org/resource/X"),
        _edge("Q2", "Q1", SOURCE_DBPEDIA),
        _edge("Q3", "Q4", SOURCE_DBPEDIA),
        _edge("Q4", "Q3", SOURCE_DBPEDIA),
    )
    counts = summary(artifact)
    assert counts["contested_pairs"] == 1
    assert counts["reciprocal_pairs"] == 2
    assert counts["corroborated"] == 1
    assert counts["single_source"] == 3
    assert counts["influence_edges"] == 4
