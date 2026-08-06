"""``graph.structure`` — the connectivity numbers, and the guards that keep them honest.

The tests that matter here are the ones on **synthetic graphs whose answer is known by construction**
(``.claude/rules/evals.md``: a metric you have not tried to break is not a metric). The assertions
against the pinned corpus are a second, weaker layer: they pin what v0.2.0 actually measures so that a
corpus change has to be acknowledged rather than absorbed.

Those pinned numbers are **measurements, not targets.** When a re-ingest moves them, the right response
is to update them here and say so in ``docs/graph-semantics.md``, not to treat the change as a failure.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import NODE_KIND_GENRE, Artifact, Edge, Node
from musical_mycelium.graph.structure import analyse, components

# What the pinned corpus measures. 41 islands over 169 genres, the biggest holding 31 of them.
#
# Identical to v0.2.0, and that is the point rather than a coincidence: v0.3.0 was derived by stamping
# ``kind`` onto v0.2.0's rows with no refetch, so any movement in these four numbers would mean the
# migration changed the corpus when it was supposed to change only the schema.
V020_COMPONENTS = 41
V020_LARGEST = 31
V020_DIAMETER = 10
V020_MAX_PATH_HOPS = 2


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


def _artifact(pairs: list[tuple[str, str]], extra_nodes: list[str] | None = None) -> Artifact:
    ids = sorted({n for pair in pairs for n in pair} | set(extra_nodes or []))
    return Artifact(
        nodes=tuple(
            Node(
                id=i,
                label=i,
                source="t",
                source_id=i,
                retrieved_at="2026-08-05",
                kind=NODE_KIND_GENRE,
            )
            for i in ids
        ),
        edges=tuple(
            Edge(
                subject_id=s,
                predicate="influenced_by",
                object_id=o,
                source="t",
                source_id=f"urn:{s}-{o}",
                retrieved_at="2026-08-05",
                prose_tier="PROSE",
                verification="HAND",
            )
            for s, o in pairs
        ),
    )


# --- known by construction -------------------------------------------------------------------------


def test_an_empty_artifact_measures_zero_not_an_error() -> None:
    """The vacuous case. An empty corpus must report emptiness rather than crash or, worse, report a
    healthy-looking default — the same instinct as the eval suite's vacuous-truth guard."""
    result = analyse(Artifact(nodes=(), edges=()))
    assert result.component_count == 0
    assert result.largest_component == 0
    assert result.diameter == 0
    assert result.max_path_hops == 0


def test_components_ignore_direction_but_paths_do_not() -> None:
    """``a -> c <- b`` is **one** component and **zero** directed hops between ``a`` and ``b``.

    This is the single most important assertion in the file. Counting these two notions of connectivity
    as the same thing is what would let a shared ancestor be narrated as descent.
    """
    result = analyse(_artifact([("a", "c"), ("b", "c")]))
    assert result.component_count == 1
    assert result.largest_component == 3
    assert result.diameter == 2  # a -- c -- b, ignoring arrows
    assert result.max_path_hops == 1  # no chain is longer than a single edge


def test_two_islands_are_two_components() -> None:
    result = analyse(_artifact([("a", "b"), ("c", "d")]))
    assert result.component_count == 2
    assert result.largest_component == 2


def test_diameter_is_measured_inside_the_largest_component_only() -> None:
    """A four-node chain plus a two-node island. The diameter is the chain's 3, not something averaged
    across both and not infinity — which is what the diameter of a disconnected graph actually is."""
    result = analyse(_artifact([("b", "a"), ("c", "b"), ("d", "c"), ("z", "y")]))
    assert result.component_count == 2
    assert result.largest_component == 4
    assert result.diameter == 3


def test_a_node_with_no_edges_is_its_own_component_and_counted_as_isolated() -> None:
    result = analyse(_artifact([("a", "b")], extra_nodes=["lonely"]))
    assert result.component_count == 2
    assert result.isolated_nodes == 1


def test_max_path_hops_follows_the_arrows() -> None:
    """A three-edge chain all pointing the same way gives three hops. The same three edges with one
    reversed gives fewer, even though the component and the diameter are unchanged."""
    aligned = analyse(_artifact([("b", "a"), ("c", "b"), ("d", "c")]))
    assert aligned.max_path_hops == 3
    assert aligned.diameter == 3

    broken = analyse(_artifact([("b", "a"), ("b", "c"), ("d", "c")]))
    assert broken.diameter == 3
    assert broken.max_path_hops == 1


def test_a_cycle_does_not_hang_or_inflate() -> None:
    """Mutual influence is a real claim a source can make, and v0.2.0 contains one. Two nodes citing
    each other are one hop apart, not infinitely many."""
    result = analyse(_artifact([("a", "b"), ("b", "a")]))
    assert result.component_count == 1
    assert result.max_path_hops == 1
    assert result.diameter == 1


def test_component_ordering_is_total_and_reproducible() -> None:
    """Equal-sized components must not swap places between runs, or an assertion about "the largest
    component" flaps for no reason."""
    artifact = _artifact([("b", "a"), ("d", "c"), ("f", "e")])
    assert components(artifact) == components(artifact)
    assert [sorted(c) for c in components(artifact)] == [["a", "b"], ["c", "d"], ["e", "f"]]


# --- the pinned corpus -----------------------------------------------------------------------------


def test_the_pinned_corpus_structure(store: InMemoryGraphStore) -> None:
    """v0.2.0 as measured 2026-08-05. Update deliberately when the corpus moves; do not delete."""
    result = store.structure
    assert result.component_count == V020_COMPONENTS
    assert result.largest_component == V020_LARGEST
    assert result.diameter == V020_DIAMETER
    assert result.max_path_hops == V020_MAX_PATH_HOPS
    assert result.isolated_nodes == 0


def test_the_corpus_is_broad_and_shallow_and_says_so(store: InMemoryGraphStore) -> None:
    """The finding of step 4, asserted so it cannot be quietly forgotten.

    133 edges over 169 genres in 41 components, and the deepest chain ``path()`` can return anywhere in
    the corpus is **two hops**. Phase 2's DoD #2 asks for three or more, and this is the assertion that
    says the corpus cannot supply it — the depth has to come from somewhere other than P737 among
    genres. See ``docs/graph-semantics.md`` 5.
    """
    assert store.structure.max_path_hops < 3
    assert store.structure.component_count > store.structure.largest_component // 2


def test_components_partition_every_node(store: InMemoryGraphStore) -> None:
    """No node in two components, no node missing. The cheapest possible check that the traversal
    underneath every other number here is not dropping rows."""
    found = components(store._artifact)
    covered = [nid for component in found for nid in component]
    assert len(covered) == len(set(covered)) == len(store)


def test_structure_is_computed_not_read_from_the_manifest(store: InMemoryGraphStore) -> None:
    """The manifest is a record of a build, not an input to the runtime.

    This assertion used to lean on v0.2.0 happening to predate the field, so its manifest carried no
    structure at all. That stopped testing anything the moment a manifest had one — v0.3.0's does. The
    real property is stronger and survives the corpus changing underneath it: hand the store a manifest
    whose structure block is *wrong* and it must still answer with what the corpus actually says.
    """
    assert store._manifest is not None
    lying = replace(store._manifest, structure={"component_count": 1, "diameter": 999})
    lied_to = InMemoryGraphStore(store._artifact, lying)
    assert lied_to.structure.component_count == V020_COMPONENTS
    assert lied_to.structure.diameter == V020_DIAMETER
