"""``graph.structure`` — the connectivity numbers, and the guards that keep them honest.

The tests that matter here are the ones on **synthetic graphs whose answer is known by construction**
(``.claude/rules/evals.md``: a metric you have not tried to break is not a metric). The assertions
against the pinned corpus are a second, weaker layer: they pin what v0.6.0 actually measures so that a
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

# What the pinned corpus measures, at v0.6.0: 1,313 nodes over both axes, 12 components, the biggest
# holding 1,286 of them.
#
# The history is the point of keeping these, so it is recorded rather than overwritten. Through v0.3.0:
# 41 / 31 / 10 / 2 over 169 genre nodes, identical across the v0.2.0-to-v0.3.0 migration, which is what
# proved that migration changed the schema and not the corpus. At v0.4.0 the artist axis landed and they
# went to 169 / 458 / 16 / 6 over 973 nodes.
#
# **v0.6.0 is the sharpest move of the three: 169 components to 12.** P136 membership joined the axes,
# and it did so through the people who play across them -- CLAUDE.md decision C1. Read what it means
# carefully: the corpus became *connected*, not more *derived*. Not one of these 12 components is a
# chain of sourced influence, and a component count is not evidence that it is.
#
# **v0.7.1: 12 components to 7, and the deepest chain 7 hops to 12.** That depth is the DBpedia axis and
# it is the first time the *genre* side has supplied any: through v0.6.0 the depth came entirely from
# artists, and this test's own docstring recorded that P737 among genres could not provide it. 1,336
# sourced genre-to-genre edges changed that. The islands finding and the shallowness finding have now
# both been overturned, by different steps, three phases apart.
PINNED_COMPONENTS = 7
PINNED_LARGEST = 1465
PINNED_DIAMETER = 10
PINNED_MAX_PATH_HOPS = 12


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
    """v0.7.1 as measured 2026-09-04. Update deliberately when the corpus moves; do not delete."""
    result = store.structure
    assert result.component_count == PINNED_COMPONENTS
    assert result.largest_component == PINNED_LARGEST
    assert result.diameter == PINNED_DIAMETER
    assert result.max_path_hops == PINNED_MAX_PATH_HOPS
    assert result.isolated_nodes == 0


def test_the_depth_arrived_with_the_artist_axis(store: InMemoryGraphStore) -> None:
    """Step 4's finding, and then step 6c overturning half of it. Asserted so neither is forgotten.

    Through v0.3.0 this test read ``max_path_hops < 3`` and recorded that **the genre axis cannot
    supply depth**: 133 edges over 169 genres in 41 components, deepest chain two hops, against a DoD
    #2 that asks for three or more. It said the depth would have to come from somewhere other than
    P737 among genres.

    v0.4.0 is that somewhere. The artist axis took the deepest chain from **2 hops to 6** and the
    largest component from 31 nodes to 458. The corpus is no longer shallow; it is still broad, and
    169 components over 973 nodes means it is still mostly islands.

    v0.6.0 ended the islands -- 12 components, 1,286 of 1,313 nodes in the largest -- and took the
    deepest chain to 7. The islands half went stale there; the shallowness finding did not, because
    membership is one hop wide and carries no derivation.

    **v0.7.1 overturns the shallowness finding too, and this is the sentence that changes.** The DBpedia
    axis added 1,336 sourced genre-to-genre influence edges and the deepest chain went 7 hops to 12,
    with components 12 -> 7. Depth now *does* come from the genre axis -- not from P737, which still
    cannot supply it, but from a second source for the same relation. The original claim was about P737
    specifically and it remains true; the broader reading, that the genre axis is inherently shallow,
    was a property of having one source rather than of genres.
    """
    assert store.structure.max_path_hops >= 3, "DoD #2 wants three or more hops"
    assert store.structure.max_path_hops == PINNED_MAX_PATH_HOPS
    assert store.structure.component_count > 1, (
        "one connected blob would be its own kind of surprise"
    )


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
    assert lied_to.structure.component_count == PINNED_COMPONENTS
    assert lied_to.structure.diameter == PINNED_DIAMETER
