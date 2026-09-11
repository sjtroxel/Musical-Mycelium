"""The v0.10.0 schema, phase 7.6 step 4: a teaching predicate, its tier, and dates and aliases on nodes.

Nothing here builds v0.10.0; that is step 5. These tests fix the contract it will be built against, and
prove that widening the schema left every artifact already on disk exactly as it was.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from musical_mycelium.graph.memory import artifact_directory
from musical_mycelium.graph.schema import (
    NODE_KIND_ARTIST,
    PREDICATE_INFLUENCED_BY,
    PREDICATE_PLAYS_GENRE,
    PREDICATE_STUDIED_WITH,
    PREDICATES,
    PROSE_TIER_NOT_APPLICABLE,
    SOURCE_WIKIDATA,
    TIERS_BY_PREDICATE,
    VERIFICATION_INFLUENCE_LEVELS,
    VERIFICATION_LEVELS,
    VERIFICATION_MEMBERSHIP_CITED,
    VERIFICATION_MEMBERSHIP_LEVELS,
    VERIFICATION_PROSE_AUTO,
    VERIFICATION_TEACHING_LEVELS,
    VERIFICATION_TEACHING_PROSE_AUTO,
    Artifact,
    Edge,
    Node,
    counts_agree,
    read_manifest,
    verify,
)
from musical_mycelium.ingest.artifact import merge_axes

STAMP = "2026-09-11T00:00:00+00:00"
ARTIFACTS = artifact_directory().parent

#: Every artifact the current schema can load. v0.1.0 and v0.2.0 predate ``Node.kind`` and could not
#: load before phase 7.6 either (measured 2026-09-11, before and after the change).
LOADABLE = ("0.3.0", "0.4.0", "0.5.0", "0.6.0", "0.7.0", "0.7.1")


def _edge(
    predicate: str, verification: str, prose_tier: str = "PROSE", subject: str = "Q255"
) -> Edge:
    return Edge(
        subject_id=subject,
        predicate=predicate,
        object_id="Q7349",
        source=SOURCE_WIKIDATA,
        source_id=f"http://www.wikidata.org/entity/statement/{subject}-0",
        retrieved_at=STAMP,
        prose_tier=prose_tier,
        verification=verification,
    )


def _artist(qid: str, **extra: object) -> Node:
    return Node(
        id=qid,
        label=f"artist {qid}",
        kind=NODE_KIND_ARTIST,
        source=SOURCE_WIKIDATA,
        source_id=qid,
        retrieved_at=STAMP,
        **extra,  # type: ignore[arg-type]
    )


# --- the predicate and its tier ------------------------------------------------------------------------


def test_studied_with_is_a_predicate_and_not_an_influence_default() -> None:
    from musical_mycelium.graph.schema import INFLUENCE_ONLY

    assert PREDICATE_STUDIED_WITH in PREDICATES
    assert frozenset({PREDICATE_INFLUENCED_BY}) == INFLUENCE_ONLY, (
        "the traversal default must not widen"
    )


def test_a_teaching_edge_constructs_with_its_own_tier() -> None:
    edge = _edge(PREDICATE_STUDIED_WITH, VERIFICATION_TEACHING_PROSE_AUTO)
    assert edge.verification == VERIFICATION_TEACHING_PROSE_AUTO


@pytest.mark.parametrize(
    ("predicate", "verification", "prose_tier"),
    [
        # A teaching edge wearing an influence tier: the collapse phase 7.6 DoD 5 forbids.
        (PREDICATE_STUDIED_WITH, VERIFICATION_PROSE_AUTO, "PROSE"),
        (PREDICATE_STUDIED_WITH, VERIFICATION_MEMBERSHIP_CITED, "PROSE"),
        # And the reverse: an influence or membership edge wearing the teaching tier.
        (PREDICATE_INFLUENCED_BY, VERIFICATION_TEACHING_PROSE_AUTO, "PROSE"),
        (PREDICATE_PLAYS_GENRE, VERIFICATION_TEACHING_PROSE_AUTO, PROSE_TIER_NOT_APPLICABLE),
        # The pre-existing pairs, now enforced rather than conventional.
        (PREDICATE_PLAYS_GENRE, VERIFICATION_PROSE_AUTO, PROSE_TIER_NOT_APPLICABLE),
        (PREDICATE_INFLUENCED_BY, VERIFICATION_MEMBERSHIP_CITED, "PROSE"),
    ],
)
def test_no_tier_can_be_worn_by_another_predicate(
    predicate: str, verification: str, prose_tier: str
) -> None:
    with pytest.raises(ValueError, match=r"not a \w+ tier"):
        _edge(predicate, verification, prose_tier)


def test_an_unknown_predicate_is_refused() -> None:
    """``PREDICATES``' comment has said "validated on ``Edge``" since v0.6.0, and until phase 7.6 step 4
    nothing validated it: a typo'd predicate constructed without complaint."""
    with pytest.raises(ValueError, match="has predicate"):
        _edge("studied_under", VERIFICATION_TEACHING_PROSE_AUTO)


def test_the_tier_map_covers_every_predicate_and_partitions_every_tier() -> None:
    """Each tier belongs to exactly one predicate, and every tier belongs to one. A tier left out would be
    unconstructible; a tier in two sets would mean two things."""
    assert set(TIERS_BY_PREDICATE) == set(PREDICATES)
    groups = list(TIERS_BY_PREDICATE.values())
    assert frozenset().union(*groups) == VERIFICATION_LEVELS
    assert sum(len(g) for g in groups) == len(VERIFICATION_LEVELS), "a tier is in two groups"
    assert TIERS_BY_PREDICATE[PREDICATE_STUDIED_WITH] == VERIFICATION_TEACHING_LEVELS
    assert TIERS_BY_PREDICATE[PREDICATE_PLAYS_GENRE] == VERIFICATION_MEMBERSHIP_LEVELS
    assert TIERS_BY_PREDICATE[PREDICATE_INFLUENCED_BY] == VERIFICATION_INFLUENCE_LEVELS


# --- dates and aliases on nodes -----------------------------------------------------------------------


def test_birth_year_and_aliases_round_trip_through_the_artifact() -> None:
    mozart = _artist(
        "Q254", birth_year=1756, birth_precision=11, aliases=("Mozart", "W. A. Mozart")
    )
    other = _artist("Q7349")
    artifact = Artifact(nodes=(mozart, other), edges=())
    restored = Artifact.from_json(artifact.to_json())
    assert restored.nodes[0] == mozart, (
        "JSON turns the aliases tuple into a list; the node must not"
    )
    assert restored.nodes[0].aliases == ("Mozart", "W. A. Mozart")
    assert restored.nodes[0].birth_year == 1756


def test_new_node_fields_default_to_absent() -> None:
    """Every node written before v0.10.0 lacks these keys and must load as "unknown", not as a guess."""
    node = _artist("Q1")
    assert (node.birth_year, node.birth_precision, node.aliases) == (None, None, ())


# --- nothing already on disk moved -------------------------------------------------------------------


@pytest.mark.parametrize("version", LOADABLE)
def test_every_loadable_artifact_still_loads_and_verifies(version: str) -> None:
    """Widening the schema must not change what an immutable artifact means. It loads, every edge passes
    the new tier rule, and it still hashes to the value its manifest recorded."""
    directory = ARTIFACTS / f"v{version}"
    artifact = Artifact.load(directory)
    verify(directory)
    manifest = read_manifest(directory)
    assert counts_agree(manifest.verification_counts, artifact.verification_counts())


def test_the_predicate_in_the_sort_key_moves_no_existing_edge() -> None:
    """Trap 12. Adding the predicate to the edge sort key orders pairs that carry two predicates; no pair
    in v0.7.1 carries two, so re-merging it must reproduce the edge order **stored in its file**."""
    directory = ARTIFACTS / "v0.7.1"
    artifact = Artifact.load(directory)
    assert merge_axes(artifact).edges == artifact.edges


def test_one_pair_with_two_predicates_orders_deterministically() -> None:
    """Beethoven will carry both ``influenced_by`` and ``studied_with`` Haydn at v0.10.0."""
    nodes = (_artist("Q255"), _artist("Q7349"))
    teaching = _edge(PREDICATE_STUDIED_WITH, VERIFICATION_TEACHING_PROSE_AUTO)
    influence = _edge(PREDICATE_INFLUENCED_BY, VERIFICATION_PROSE_AUTO)
    one = merge_axes(
        Artifact(nodes=nodes, edges=(teaching,)), Artifact(nodes=(), edges=(influence,))
    )
    two = merge_axes(
        Artifact(nodes=nodes, edges=(influence,)), Artifact(nodes=(), edges=(teaching,))
    )
    assert one.edges == two.edges
    assert [e.predicate for e in one.edges] == [PREDICATE_INFLUENCED_BY, PREDICATE_STUDIED_WITH]


def test_the_artifacts_directory_is_where_the_loadable_list_says() -> None:
    """Guards LOADABLE against drifting from what is on disk as new cuts arrive."""
    on_disk = {p.name.removeprefix("v") for p in Path(ARTIFACTS).iterdir() if p.is_dir()}
    assert set(LOADABLE) <= on_disk
