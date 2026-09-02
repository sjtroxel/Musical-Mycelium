"""The P136 membership layer, phase 6 step 2.

The tests that matter here are the ones about **what must not happen**: a deprecated statement being
ingested, a non-genre object becoming a genre node, an edge pointing at a node that does not exist, and
the verification tier depending on the order rows came back in. Each of those is a silent failure —
the artifact would build, the suite would pass, and the corpus would be wrong.
"""

from __future__ import annotations

import pytest

from musical_mycelium.graph.schema import (
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    PREDICATE_PLAYS_GENRE,
    PREDICATES,
    PROSE_TIER_NOT_APPLICABLE,
    VERIFICATION_LEVELS,
    VERIFICATION_MEMBERSHIP_BARE,
    VERIFICATION_MEMBERSHIP_CITED,
    VERIFICATION_MEMBERSHIP_LEVELS,
)
from musical_mycelium.ingest.membership import (
    Membership,
    build,
    membership_query,
    parse,
)

WD = "http://www.wikidata.org/entity/"
ST = "http://www.wikidata.org/entity/statement/"


def row(
    artist: str, genre: str, statement: str, referenced: bool, in_axis: bool = True
) -> dict[str, dict[str, str]]:
    return {
        "a": {"value": f"{WD}{artist}"},
        "g": {"value": f"{WD}{genre}"},
        "statement": {"value": f"{ST}{statement}"},
        "referenced": {"value": "true" if referenced else "false"},
        "objInAxis": {"value": "true" if in_axis else "false"},
    }


# --- the query ------------------------------------------------------------------------------------


def test_the_query_excludes_deprecated_statements() -> None:
    """The whole reason this filter exists. A deprecated rank is Wikidata recording that editors judged
    the statement wrong, and a corpus whose pitch is provenance cannot ingest one.

    Verified live on 2026-09-02 by breaking it rather than by reading it: the same subject returns 4
    P737 statements without the filter and 3 with it, and the missing one is the deprecated
    ``Nine Inch Nails influenced_by Pink Floyd``."""
    query = membership_query(["Q1"])
    assert "FILTER NOT EXISTS" in query
    assert "wikibase:DeprecatedRank" in query


def test_the_query_uses_statement_form_not_the_truthy_shortcut() -> None:
    """``wdt:`` returns only truthy statements, which hides rank — and rank is what this query has to
    see. It also does not expose a statement URI, which is what an edge cites."""
    query = membership_query(["Q1"])
    assert "p:P136" in query and "ps:P136" in query
    assert "wdt:P136" not in query


def test_the_object_type_test_is_a_bind_so_rejects_come_back() -> None:
    """A filtering triple would drop non-genre objects silently and the exclusion rate could then only
    be inferred from a missing count. Same choice both other axes made."""
    assert "BIND(EXISTS" in membership_query(["Q1"])


def test_an_unbounded_query_is_refused() -> None:
    with pytest.raises(ValueError, match="every tagged musician"):
        membership_query([])


# --- parsing --------------------------------------------------------------------------------------


def test_one_pair_with_two_statements_keeps_the_referenced_one() -> None:
    """A pair can carry a preferred and a normal statement. If either is referenced the pair has a
    reference, and taking whichever row arrived last would make the verification tier depend on result
    ordering — the same class of bug as letting ``Node.kind`` depend on it."""
    both_orders = [
        [row("Q1", "Q2", "s-bare", False), row("Q1", "Q2", "s-ref", True)],
        [row("Q1", "Q2", "s-ref", True), row("Q1", "Q2", "s-bare", False)],
    ]
    for rows in both_orders:
        (m,) = parse(rows)
        assert m.referenced is True
        assert m.verification == VERIFICATION_MEMBERSHIP_CITED


def test_the_tier_follows_the_reference_and_nothing_else() -> None:
    assert Membership("Q1", "Q2", "s", True, True).verification == VERIFICATION_MEMBERSHIP_CITED
    assert Membership("Q1", "Q2", "s", False, True).verification == VERIFICATION_MEMBERSHIP_BARE


def test_parse_is_ordered_so_a_build_is_reproducible() -> None:
    rows = [row("Q9", "Q2", "c", False), row("Q1", "Q8", "a", False), row("Q1", "Q3", "b", False)]
    assert [(m.artist_id, m.genre_id) for m in parse(rows)] == [
        ("Q1", "Q3"),
        ("Q1", "Q8"),
        ("Q9", "Q2"),
    ]


# --- building -------------------------------------------------------------------------------------


def test_a_non_genre_object_produces_neither_a_node_nor_an_edge() -> None:
    """P136 objects include things that are not music genres. The type test is a real filter."""
    memberships = parse([row("Q1", "Q2", "s", True, in_axis=False)])
    artifact = build(memberships, {"Q2": "not a genre"}, {}, frozenset())
    assert artifact.nodes == ()
    assert artifact.edges == ()


def test_a_genre_already_in_the_corpus_gains_an_edge_but_not_a_duplicate_node() -> None:
    memberships = parse([row("Q1", "Q2", "s", True)])
    artifact = build(memberships, {}, {}, frozenset({"Q2"}))
    assert artifact.nodes == ()
    assert len(artifact.edges) == 1
    assert artifact.edges[0].object_id == "Q2"


def test_a_genre_not_in_the_corpus_arrives_as_a_genre_node() -> None:
    """The unbounded decision. Without this the bound keeps whichever of an artist's genres happens to
    be among the 169, which is arbitrary rather than coarser — Red Hot Chili Peppers would ship as
    heavy metal and nothing else."""
    memberships = parse([row("Q1", "Q2", "s", True)])
    artifact = build(memberships, {"Q2": "funk rock"}, {"Q2": 123}, frozenset())
    (node,) = artifact.nodes
    assert (node.id, node.label, node.kind) == ("Q2", "funk rock", NODE_KIND_GENRE)
    assert node.revision_id == 123


def test_an_edge_is_never_written_without_a_node_for_its_object() -> None:
    """``merge_axes`` refuses dangling endpoints, so this would fail the build rather than corrupt the
    corpus — but failing here says which layer produced it."""
    memberships = parse([row("Q1", "Q2", "s", True)])
    artifact = build(memberships, {}, {}, frozenset())  # no label -> no node
    assert artifact.nodes == ()
    assert artifact.edges == ()


def test_membership_edges_carry_the_membership_predicate_and_no_prose_tier() -> None:
    """The prose check asks whether the subject's article names the object in body prose, which is a
    question about an influence claim. Recording ``ORPHAN`` would say the check ran and found nothing."""
    memberships = parse([row("Q1", "Q2", "s", False)])
    (edge,) = build(memberships, {"Q2": "g"}, {}, frozenset()).edges
    assert edge.predicate == PREDICATE_PLAYS_GENRE
    assert edge.prose_tier == PROSE_TIER_NOT_APPLICABLE
    assert edge.verification == VERIFICATION_MEMBERSHIP_BARE


def test_the_layer_carries_its_own_retrieved_at() -> None:
    """Provenance is per row. The P737 crawl and this layer are weeks apart and the corpus should say
    so rather than pretend to one moment — a Wikidata edit between the two reads is exactly how
    ``Villano Antillano`` ended up in the artifact with no surviving corpus-genre P136."""
    memberships = parse([row("Q1", "Q2", "s", False)])
    artifact = build(
        memberships, {"Q2": "g"}, {}, frozenset(), retrieved_at="2026-09-02T00:00:00+00:00"
    )
    assert artifact.edges[0].retrieved_at == "2026-09-02T00:00:00+00:00"
    assert artifact.nodes[0].retrieved_at == "2026-09-02T00:00:00+00:00"


# --- the schema locks -----------------------------------------------------------------------------


def test_the_membership_predicate_is_a_known_predicate() -> None:
    assert PREDICATE_PLAYS_GENRE in PREDICATES
    assert PREDICATE_INFLUENCED_BY in PREDICATES


def test_the_membership_tiers_are_real_verification_levels() -> None:
    assert VERIFICATION_MEMBERSHIP_LEVELS <= VERIFICATION_LEVELS
    assert PREDICATE_INFLUENCED_BY not in VERIFICATION_LEVELS


def test_the_gate_cannot_narrate_a_membership_edge() -> None:
    """DoD #6 in one assertion. ``plays_genre`` is absent from ``ALLOWED_PREDICATES`` and that omission
    is the feature: the gate refuses it without ``agent/`` being edited at all. If someone adds the
    predicate to that set to make a metric move, this fails."""
    from musical_mycelium.agent.claims import ALLOWED_PREDICATES

    assert PREDICATE_PLAYS_GENRE not in ALLOWED_PREDICATES
    assert frozenset({PREDICATE_INFLUENCED_BY}) == ALLOWED_PREDICATES


# --- the artifact-level lock this step owes -------------------------------------------------------


@pytest.mark.parametrize("version", ["0.5.0", "0.6.0"])
def test_no_influence_edge_in_any_artifact_crosses_the_axes(version: str) -> None:
    """The lock this step **tightened rather than removed**.

    ``tests/test_claims.py:253`` says a cross-axis edge reaching the artifact "should be impossible",
    and until now nothing asserted it -- the gate refused such a claim at runtime, but no test checked
    the corpus itself. Adding ``plays_genre`` makes cross-axis edges a deliberate, correct state for
    one predicate, which is exactly the situation in which an unasserted invariant goes quietly false.

    So the property is narrowed to what is actually true and then asserted: **an ``influenced_by`` edge
    never crosses the axes.** Membership edges always do, by definition, which the next test states so
    the two cannot be confused.
    """
    from musical_mycelium.graph.schema import Artifact
    from musical_mycelium.ingest.wikidata import artifact_dir

    artifact = Artifact.load(artifact_dir(version))
    kind = {node.id: node.kind for node in artifact.nodes}
    crossing = [
        (e.subject_id, e.object_id)
        for e in artifact.edges
        if e.predicate == PREDICATE_INFLUENCED_BY and kind[e.subject_id] != kind[e.object_id]
    ]
    assert not crossing, (
        f"v{version} has {len(crossing)} cross-axis influence edges: {crossing[:3]}"
    )


def test_every_membership_edge_crosses_the_axes_by_construction() -> None:
    """The other half, so "cross-axis" cannot quietly come to mean "broken" again. A membership edge
    runs artist -> genre always; one that did not would be a genre tagged with a genre."""
    from musical_mycelium.graph.schema import NODE_KIND_ARTIST, Artifact
    from musical_mycelium.ingest.wikidata import artifact_dir

    artifact = Artifact.load(artifact_dir("0.6.0"))
    kind = {node.id: node.kind for node in artifact.nodes}
    membership = [e for e in artifact.edges if e.predicate == PREDICATE_PLAYS_GENRE]
    assert membership, "v0.6.0 has no membership edges; the layer did not land"
    for edge in membership:
        assert kind[edge.subject_id] == NODE_KIND_ARTIST
        assert kind[edge.object_id] == NODE_KIND_GENRE


def test_density_counts_influence_edges_and_ignores_membership() -> None:
    """The honesty guard on the absorbed density figures, and the reason they were worth moving.

    Membership edges outnumber influence edges roughly three to one at v0.6.0. If they reached the
    degree histogram the panel would report a corpus three times denser in the single dimension this
    project claims to measure. Verified against phase 5's independently-computed frontend figures:
    ``analyse`` reproduces 85 / 108 / 6 on v0.5.0 exactly.
    """
    from musical_mycelium.graph.coverage import analyse
    from musical_mycelium.graph.schema import Artifact
    from musical_mycelium.ingest.wikidata import artifact_dir

    old = analyse(Artifact.load(artifact_dir("0.5.0")))
    assert (old.genres_without_recorded_origins, old.genres_with_one_connection) == (85, 108)
    assert old.busiest_genre_connections == 6

    new = analyse(Artifact.load(artifact_dir("0.6.0")))
    # 2,782 membership edges arrived and not one of them moved a density figure that already existed.
    assert new.genres_with_one_connection == old.genres_with_one_connection
    assert new.busiest_genre_connections == old.busiest_genre_connections
    # What DID move is the honest part: 340 genres now have no sourced origin at all.
    assert new.connections["0"] == 340
    assert "0" not in old.connections
    assert sum(new.connections.values()) == new.genres
