"""``InMemoryGraphStore.path`` — shortest sourced chains, and the ways they are allowed to be empty.

Two failure modes get most of the attention here, because both produce output that looks right.

The first is **inverting direction**. A path walked the wrong way returns the same edges, the same
count and the same sources, and narrates heavy metal as an influence on the blues. No type checker and
no smoke test catches it; only an assertion about which genre is at which end does.

The second is **an empty list read as an answer**. ``[]`` means "no sourced chain in that direction" and
covers three genuinely different situations, none of which is an error. Every one of them is asserted
below so that a future refactor that starts raising on unknown ids fails here rather than in the
refusal metrics, where it would look like a model problem.
"""

from __future__ import annotations

import itertools

import pytest

from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import Edge, Node
from musical_mycelium.graph.store import Direction

BLUES = "Q9759"
BLUES_ROCK = "Q193355"
HEAVY_METAL = "Q38848"
ACID_JAZZ = "Q221772"
JAZZ = "Q8341"
POST_ROCK = "Q209137"
SHOEGAZE = "Q272167"


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


def labels(store: InMemoryGraphStore, chain: list[Edge], direction: Direction) -> list[str]:
    """The chain as genre names in traversal order, so an assertion reads like the claim it encodes."""
    if not chain:
        return []
    first = chain[0].subject_id if direction is Direction.INFLUENCED_BY else chain[0].object_id
    walked = [first]
    for edge in chain:
        nxt = edge.object_id if direction is Direction.INFLUENCED_BY else edge.subject_id
        walked.append(nxt)
    return [node.label for nid in walked if (node := store.get_node(nid)) is not None]


# --- the signature chain, in both directions -------------------------------------------------------


def test_ancestry_walks_back_in_time(store: InMemoryGraphStore) -> None:
    """``SPEC.md`` 2's signature chain, asked the way a person asks it: where did heavy metal come from.

    Two hops, both sourced. This is the phase's product value in one assertion.
    """
    chain = store.path(HEAVY_METAL, BLUES)
    assert labels(store, chain, Direction.INFLUENCED_BY) == [
        "heavy metal music",
        "blues rock",
        "blues",
    ]


def test_descent_walks_forward_in_time(store: InMemoryGraphStore) -> None:
    """The same chain from the other end — ``SPEC.md`` 2.2's "how is the blues connected to heavy
    metal?" — which is the phrasing the ``direction`` parameter exists to serve."""
    chain = store.path(BLUES, HEAVY_METAL, Direction.INFLUENCED)
    assert labels(store, chain, Direction.INFLUENCED) == [
        "blues",
        "blues rock",
        "heavy metal music",
    ]


def test_the_two_directions_return_the_same_edges_reversed(store: InMemoryGraphStore) -> None:
    """Same rows, opposite order. If these ever diverge, one of the two indexes is being walked with
    the other one's accessor and half the product is quietly wrong."""
    up = store.path(HEAVY_METAL, BLUES, Direction.INFLUENCED_BY)
    down = store.path(BLUES, HEAVY_METAL, Direction.INFLUENCED)
    assert up == list(reversed(down))


def test_walking_the_wrong_way_finds_nothing(store: InMemoryGraphStore) -> None:
    """The one that matters most. Blues did not come out of heavy metal, so asking for that chain must
    return nothing rather than the real chain reversed.

    A traversal that ignored direction would pass every other test in this file and fail this one.
    """
    assert store.path(BLUES, HEAVY_METAL, Direction.INFLUENCED_BY) == []
    assert store.path(HEAVY_METAL, BLUES, Direction.INFLUENCED) == []


def test_influenced_by_is_the_default_direction(store: InMemoryGraphStore) -> None:
    assert store.path(HEAVY_METAL, BLUES) == store.path(HEAVY_METAL, BLUES, Direction.INFLUENCED_BY)


# --- provenance survives the walk ------------------------------------------------------------------


def test_every_hop_carries_its_own_source(store: InMemoryGraphStore) -> None:
    """Why ``path`` returns edges and not node ids. A chain of ids would be unciteable, and a claim per
    hop is what the gate checks in step 5."""
    chain = store.path(HEAVY_METAL, BLUES)
    assert len(chain) == 2
    for edge in chain:
        assert edge.source_id.startswith("http://www.wikidata.org/entity/statement/")
        assert edge.retrieved_at
        assert edge.verification in {"HAND", "PROSE_AUTO"}


def test_the_chain_is_contiguous(store: InMemoryGraphStore) -> None:
    """Each hop starts where the last one ended. A chain with a gap would still render as prose and
    would assert a connection the graph does not contain."""
    chain = store.path(HEAVY_METAL, BLUES)
    for earlier, later in itertools.pairwise(chain):
        assert earlier.object_id == later.subject_id


# --- the three ways of being empty, none of which is an error --------------------------------------


def test_an_unknown_id_is_empty_not_an_exception(store: InMemoryGraphStore) -> None:
    """Refusal is correct behaviour, so absence must not arrive as an exception."""
    assert store.path("Q511054", BLUES) == []  # griot: real entity, not in this artifact
    assert store.path(BLUES, "Q511054") == []
    assert store.path("", "") == []


def test_a_node_has_no_path_to_itself(store: InMemoryGraphStore) -> None:
    """Zero hops is not a chain. It collapses into the same ``[]`` as a genuine absence, which the
    protocol docstring states outright rather than leaving to be discovered."""
    assert store.path(BLUES, BLUES) == []


def test_two_genres_in_different_components_have_no_path(store: InMemoryGraphStore) -> None:
    """The connectivity limit, asserted rather than described. ``acid jazz`` and ``heavy metal`` are
    both real, both well-sourced, and the graph simply does not connect them."""
    assert store.path(ACID_JAZZ, HEAVY_METAL) == []
    assert store.path(HEAVY_METAL, ACID_JAZZ) == []
    assert store.path(ACID_JAZZ, HEAVY_METAL, Direction.INFLUENCED) == []


def test_same_component_does_not_imply_a_path() -> None:
    """The distinction ``structure.py`` warns about, on a graph built to isolate it.

    ``a -> c <- b``: one undirected component of three, and no directed chain between ``a`` and ``b`` in
    either direction. Components answer "could these be related at all"; paths answer "did one come out
    of the other", and conflating them is how a shared ancestor becomes a claimed descent.
    """
    store = _tiny_store([("a", "c"), ("b", "c")])
    assert store.path("a", "b") == []
    assert store.path("a", "b", Direction.INFLUENCED) == []
    assert store.structure.component_count == 1
    assert store.structure.largest_component == 3


# --- shape guarantees ------------------------------------------------------------------------------


def test_the_chain_is_the_shortest_one() -> None:
    """A long way round and a short way round between the same pair. BFS must take the short one:
    every extra hop is another edge the narrative has to defend."""
    store = _tiny_store([("d", "a"), ("d", "c"), ("c", "b"), ("b", "a")])
    assert len(store.path("d", "a")) == 1
    assert len(store.path("d", "b")) == 2


def test_a_cycle_terminates(store: InMemoryGraphStore) -> None:
    """v0.2.0 contains a real mutual-influence cycle — ``post-rock`` and ``shoegaze`` each cite the
    other under P737 — so the graph is not a DAG and nothing here may assume it is.

    Mutual influence is a legitimate thing for a source to claim, so this is a corpus property to
    survive rather than a defect to clean up.
    """
    assert {e.object_id for e in store.neighbors(POST_ROCK)} >= {SHOEGAZE}
    assert {e.object_id for e in store.neighbors(SHOEGAZE)} >= {POST_ROCK}
    assert len(store.path(POST_ROCK, SHOEGAZE)) == 1
    assert len(store.path(SHOEGAZE, POST_ROCK)) == 1
    assert store.path(POST_ROCK, "Q511054") == []  # unreachable: must terminate, not spin


def test_repeated_calls_return_the_same_chain(store: InMemoryGraphStore) -> None:
    """Ties break by artifact order, which is stable within a pinned version. An eval that scored a
    different equally-short chain on each run would measure nothing."""
    assert store.path(HEAVY_METAL, BLUES) == store.path(HEAVY_METAL, BLUES)


def test_the_returned_chain_cannot_mutate_the_index(store: InMemoryGraphStore) -> None:
    before = store.path(HEAVY_METAL, BLUES)
    before.clear()
    assert len(store.path(HEAVY_METAL, BLUES)) == 2


# --- helpers ---------------------------------------------------------------------------------------


def _tiny_store(pairs: list[tuple[str, str]]) -> InMemoryGraphStore:
    """A hand-built store where the answer is known by construction.

    The pinned corpus is the right fixture for "does this work on the real thing"; it is the wrong one
    for "does this handle a shape the real thing happens not to contain today". Both are needed, and a
    shape the corpus lacks now can arrive with any re-ingest.
    """
    from musical_mycelium.graph.schema import Artifact

    ids = sorted({nid for pair in pairs for nid in pair})
    nodes = tuple(
        Node(id=i, label=i, source="test", source_id=i, retrieved_at="2026-08-05") for i in ids
    )
    edges = tuple(
        Edge(
            subject_id=s,
            predicate="influenced_by",
            object_id=o,
            source="test",
            source_id=f"urn:{s}-{o}",
            retrieved_at="2026-08-05",
            prose_tier="PROSE",
            verification="HAND",
        )
        for s, o in pairs
    )
    return InMemoryGraphStore(Artifact(nodes=nodes, edges=edges))
