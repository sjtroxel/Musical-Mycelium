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
    query_kind_slice,
    region_slice,
    slice_rates,
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
    """``isolated`` is the bucket this dimension exists for: 542 of 973 nodes have no outgoing edges, so
    a system can look accurate overall while only ever answering the dense questions."""
    assert density_slice(store.get_node("Q9759"), store) == "isolated"  # blues, no outgoing
    assert density_slice(store.get_node("Q221772"), store) == "connected"  # acid jazz, four


def test_query_kind_passes_through_and_degrades_to_unknown() -> None:
    assert query_kind_slice("origins") == "origins"
    assert query_kind_slice("") == UNKNOWN


def test_slicing_of_nothing_produces_no_slices() -> None:
    """Not a zero, not a 100% — no buckets at all. An empty run has no shape to report."""
    assert slice_rates("d", [], lambda _: "k", lambda _: True).rates == {}
