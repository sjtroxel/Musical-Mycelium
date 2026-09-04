"""Slice tests — the reporting rules that stop an aggregate from flattering.

Two of these are the whole point of the module: a sparse slice must not print a percentage, and an
unknown bucket must not be a dropped row. Both are cases where the *tidier* output is the dishonest one.
"""

from __future__ import annotations

import pytest

from musical_mycelium.eval.slices import (
    SPARSE_SLICE,
    UNDATED,
    UNKNOWN,
    density_slice,
    dimensions_of,
    era_slice,
    predicate_slice,
    query_kind_slice,
    region_slice,
    slice_rates,
    source_slice,
)
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import NODE_KIND_GENRE, Node

WHEN = "2026-01-01T00:00:00+00:00"


def node(
    node_id: str = "Q1",
    *,
    year: int | None = None,
    countries: tuple[str, ...] = (),
) -> Node:
    return Node(
        id=node_id,
        label=f"genre {node_id}",
        source="wikidata",
        source_id=node_id,
        retrieved_at=WHEN,
        kind=NODE_KIND_GENRE,
        inception_year=year,
        countries=countries,
    )


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


# --- the sparse rule ------------------------------------------------------------------------------


def test_a_sparse_slice_reports_its_count_instead_of_a_percentage() -> None:
    """The rule with teeth. Two out of two is not a 100%, and rendering it as one teaches the reader
    something false about a slice that holds almost no evidence."""
    report = slice_rates("dim", [1, 2], lambda _: "tiny", lambda _: True)
    rendered = "\n".join(report.render())

    assert "2 of 2" in rendered
    assert "100.0%" not in rendered
    assert report.is_sparse("tiny")


def test_a_populated_slice_reports_a_percentage() -> None:
    report = slice_rates("dim", range(10), lambda _: "big", lambda n: n < 5)
    rendered = "\n".join(report.render())

    assert "50.0%" in rendered
    assert not report.is_sparse("big")


def test_the_sparse_boundary_is_inclusive_of_the_named_figure() -> None:
    """``SPARSE_SLICE`` items is enough; one fewer is not. Pinned so the boundary cannot drift by one
    without a test saying so."""
    assert not slice_rates("d", range(SPARSE_SLICE), lambda _: "k", lambda _: True).is_sparse("k")
    assert slice_rates("d", range(SPARSE_SLICE - 1), lambda _: "k", lambda _: True).is_sparse("k")


def test_slices_render_heaviest_first() -> None:
    """So the slices carrying real weight are read before the ones that carry almost none."""
    report = slice_rates("d", [*["a"] * 9, *["b"] * 2], lambda s: s, lambda _: True)
    assert report.render()[1].strip().startswith("a:")


# --- the unknown buckets --------------------------------------------------------------------------


def test_an_undated_node_gets_its_own_bucket_rather_than_being_dropped() -> None:
    """``graph.coverage`` already reports ``without_inception`` before the era histogram, because
    dropping the undated makes the dated eras look more complete than they are. Same rule here."""
    assert era_slice(node(year=None)) == UNDATED


def test_undated_is_not_the_same_bucket_as_unresolved() -> None:
    """A node with no inception year is a real node with a real gap. A node that never resolved is a
    different problem, and collapsing the two would hide which one the corpus has."""
    assert era_slice(node(year=None)) == UNDATED
    assert era_slice(None) == UNKNOWN
    assert UNDATED != UNKNOWN


def test_a_node_with_no_country_is_unstated_not_elsewhere() -> None:
    """The direction this project must never round in. Missing data is not evidence of breadth, and
    folding ``unstated`` into ``elsewhere`` would let absent P495 values inflate non-anglophone coverage.
    """
    assert region_slice(node(countries=())) == "unstated"


def test_the_anglophone_split_normalises_place_labels_first() -> None:
    """``Brixton`` is in the UK. That map exists because reading it as "names no UK" put the published
    corpus-coverage figure out by one."""
    assert region_slice(node(countries=("Brixton",))) == "anglophone_core"
    assert region_slice(node(countries=("United States",))) == "anglophone_core"
    assert region_slice(node(countries=("Jamaica",))) == "elsewhere"


def test_every_dimension_has_an_unknown_for_an_unresolved_node(store: InMemoryGraphStore) -> None:
    dimensions = dimensions_of(None, store, "")
    assert dimensions["era"] == UNKNOWN
    assert dimensions["region"] == UNKNOWN
    assert dimensions["density"] == UNKNOWN
    assert dimensions["query_kind"] == UNKNOWN


# --- the dimensions themselves ----------------------------------------------------------------------


def test_era_reads_off_the_shared_boundaries() -> None:
    assert era_slice(node(year=1955)) == "1950-1969"
    assert era_slice(node(year=1880)) == "pre-1900"


def test_density_separates_isolated_from_connected(store: InMemoryGraphStore) -> None:
    """``isolated`` is the bucket this dimension exists for: a large share of nodes have no outgoing
    edges, so a system can look accurate overall while only ever answering the dense questions.

    **``blues`` was the isolated fixture until v0.7.1** and is now connected -- the DBpedia axis gave it
    spirituals, folk music and work song. ``turntablism`` is one of 146 genres still isolated on the
    influence axis, so the bucket is as real as it ever was; the corpus simply moved one well-known
    genre out of it.
    """
    assert density_slice(store.get_node("Q1046801"), store) == "isolated"  # turntablism
    assert density_slice(store.get_node("Q221772"), store) == "connected"  # acid jazz, four


def test_query_kind_passes_through_and_degrades_to_unknown() -> None:
    assert query_kind_slice("origins") == "origins"
    assert query_kind_slice("") == UNKNOWN


def test_slicing_of_nothing_produces_no_slices() -> None:
    """Not a zero, not a 100% — no buckets at all. An empty run has no shape to report."""
    assert slice_rates("d", [], lambda _: "k", lambda _: True).rates == {}


# --- the two dimensions phase 6 created ----------------------------------------------------------


def test_source_separates_the_two_halves_of_the_corpus(store: InMemoryGraphStore) -> None:
    """**The dimension phase 6 made possible and therefore has to be sliced by.**

    Until v0.7.0 every edge was Wikidata, so this question had one answer. The corpus is now 949
    Wikidata influence edges against 1,336 from DBpedia, and an aggregate that looks healthy while the
    ``dbpedia_only`` slice fails is the default outcome without this.
    """
    # blues rock: rock music and electric blues from DBpedia, blues from Wikidata.
    assert source_slice(store.get_node("Q193355"), store) == "both"
    # turntablism has no origins at all -- the isolated bucket, not a gap in the slicing.
    assert source_slice(store.get_node("Q1046801"), store) == "none"
    assert source_slice(None, store) == "unknown"


def test_source_reports_a_single_source_node_as_that_source_only(
    store: InMemoryGraphStore,
) -> None:
    """The two buckets that matter are the pure ones: a node whose whole account of itself comes from
    one source is where a source-specific failure would show first."""
    from musical_mycelium.graph.schema import SOURCE_DBPEDIA, SOURCE_WIKIDATA
    from musical_mycelium.graph.store import Direction

    seen = {}
    for node in store._artifact.nodes:
        if node.kind != "genre":
            continue
        sources = {e.source for e in store.neighbors(node.id, Direction.INFLUENCED_BY)}
        if sources == {SOURCE_DBPEDIA}:
            seen["dbpedia_only"] = node
        elif sources == {SOURCE_WIKIDATA}:
            seen["wikidata_only"] = node
        if len(seen) == 2:
            break

    assert set(seen) == {"dbpedia_only", "wikidata_only"}, "the corpus must hold both pure cases"
    for expected, node in seen.items():
        assert source_slice(node, store) == expected


def test_predicate_marks_a_node_the_corpus_cannot_narrate(store: InMemoryGraphStore) -> None:
    """``membership_only`` is the bucket to watch, and it is the reason this dimension exists.

    ``plays_genre`` is absent from ``agent.claims.ALLOWED_PREDICATES``, so a genre the corpus knows only
    through the artists who play it **must always refuse**, however many edges touch it. That is correct
    behaviour, and in an aggregate it looks identical to a system refusing because it is broken. 177 of
    675 genres are in this state at v0.7.1 -- 26% of the corpus, invisible until now.
    """
    from musical_mycelium.graph.store import Direction

    membership_only = next(
        n
        for n in store._artifact.nodes
        if n.kind == "genre"
        and not store.neighbors(n.id, Direction.INFLUENCED_BY)
        and not store.neighbors(n.id, Direction.INFLUENCED)
        and predicate_slice(n, store) == "membership_only"
    )
    assert predicate_slice(membership_only, store) == "membership_only"
    assert predicate_slice(None, store) == "unknown"


def test_dimensions_of_returns_all_six_so_a_caller_cannot_forget_one(
    store: InMemoryGraphStore,
) -> None:
    """Four until v0.7.1. DoD #5 is re-judged rather than carried, and a corpus that grew a second
    source and a second predicate has two axes the slicer had never seen."""
    dimensions = dimensions_of(store.get_node("Q193355"), store, "origins")
    assert set(dimensions) == {"era", "region", "density", "source", "predicate", "query_kind"}
    assert dimensions["source"] == "both"
