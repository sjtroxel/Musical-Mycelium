"""Component structure of a pinned artifact — how connected the graph actually is.

This exists because "trace the lineage between two genres" is a capability **within a component**, not
a general one, and that limit has to be a published number rather than something a visitor discovers by
getting an empty answer. ``docs/planning/04`` 4.5 makes coverage a displayed metric; this is the
connectivity half of it.

**Everything here is derived, never stored.** The same failure mode that ``Manifest.verification_counts``
guards against applies harder to structure: a component count recorded by hand and then left behind by a
corpus change is worse than no number, because it reads as measured. ``ingest.artifact.build_manifest``
records what these functions return, and ``InMemoryGraphStore`` recomputes them at load, so the manifest
is a record of a build rather than an input to the runtime. If the two ever disagree, the computed one is
right by construction.

**Two different notions of "connected" live here and they are not interchangeable:**

- **Components ignore edge direction.** ``blues`` and ``heavy metal`` are in one component because a
  chain of influence links them, regardless of which way the arrows run. This is the right question for
  "could these two genres possibly be related at all".
- **Paths respect edge direction** (``memory.InMemoryGraphStore.path``). Influence runs one way in time,
  and a path that ignored direction would narrate heavy metal as an influence on the blues.

So two genres in the same component may still have no path between them, and that is not a bug in
either. ``max_path_hops`` is the honest product number: the deepest chain ``path()`` can return anywhere
in this corpus.
"""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict, dataclass

from musical_mycelium.graph.schema import Artifact


@dataclass(frozen=True, slots=True)
class GraphStructure:
    """The connectivity of one artifact, in five integers.

    Every field is a **measured** property of the pinned corpus. None of them is a target, and none
    should be quoted without the corpus version it was measured on — they move whenever the corpus does,
    which is exactly why they are recomputed rather than remembered.
    """

    #: How many disconnected islands the graph is in, ignoring edge direction. A high count against a
    #: modest node count is the signature of a corpus that is broad and shallow.
    component_count: int

    #: Nodes in the biggest island. The practical ceiling on "which genres can be related to each other
    #: at all" — nothing outside it can ever be connected to anything inside it.
    largest_component: int

    #: The longest shortest-hop distance **inside the largest component**, ignoring direction.
    #:
    #: Scoped to one component deliberately: the diameter of a disconnected graph is infinite, so a
    #: single number for the whole artifact would either be meaningless or quietly computed over one
    #: component without saying so. This says so.
    diameter: int

    #: Nodes carrying no edges in either direction. Should be zero for an artifact built from edges —
    #: a non-zero value means nodes arrived from somewhere other than the edge set, which is worth
    #: knowing rather than assuming.
    isolated_nodes: int

    #: The longest chain ``path()`` can return anywhere in the corpus, **respecting direction**.
    #:
    #: The number that says whether "multi-hop lineage" is a real capability or an aspiration. It is
    #: bounded by ``diameter`` and is usually far below it, because influence arrows have to agree in
    #: direction to chain and undirected neighbours do not.
    max_path_hops: int

    def as_dict(self) -> dict[str, int]:
        return asdict(self)


def _undirected_adjacency(artifact: Artifact) -> dict[str, set[str]]:
    adjacency: defaultdict[str, set[str]] = defaultdict(set)
    for node in artifact.nodes:
        adjacency[node.id] = set()
    for edge in artifact.edges:
        adjacency[edge.subject_id].add(edge.object_id)
        adjacency[edge.object_id].add(edge.subject_id)
    return dict(adjacency)


def _descendant_adjacency(artifact: Artifact) -> dict[str, list[str]]:
    """Ancestor -> the genres it influenced. One direction is enough for ``max_path_hops``: the
    distance from a to b down the arrows equals the distance from b to a up them, so the maximum over
    all ordered pairs is the same number either way."""
    adjacency: defaultdict[str, list[str]] = defaultdict(list)
    for edge in artifact.edges:
        adjacency[edge.object_id].append(edge.subject_id)
    return dict(adjacency)


def _distances(start: str, adjacency: dict[str, set[str]] | dict[str, list[str]]) -> dict[str, int]:
    """Breadth-first hop counts from ``start``. Unreachable nodes are simply absent."""
    seen = {start: 0}
    queue = deque([start])
    while queue:
        current = queue.popleft()
        for neighbour in adjacency.get(current, ()):
            if neighbour not in seen:
                seen[neighbour] = seen[current] + 1
                queue.append(neighbour)
    return seen


def components(artifact: Artifact) -> list[frozenset[str]]:
    """The connected components, **ignoring edge direction**, largest first.

    Ties are broken by the alphabetically smallest member so the ordering is total and reproducible.
    Without that, two components of equal size could swap places between runs and a test asserting "the
    largest component" would flap for no reason.
    """
    adjacency = _undirected_adjacency(artifact)
    seen: set[str] = set()
    found: list[frozenset[str]] = []
    for node_id in adjacency:
        if node_id in seen:
            continue
        reached = set(_distances(node_id, adjacency))
        seen |= reached
        found.append(frozenset(reached))
    found.sort(key=lambda component: (-len(component), min(component)))
    return found


def analyse(artifact: Artifact) -> GraphStructure:
    """Measure the artifact's connectivity. Pure, cheap, and safe to run on every cold start.

    Cheap is load-bearing rather than incidental: this runs an all-pairs breadth-first search, which is
    fine at 169 nodes and would not be at a hundred thousand. A backend behind a real database computes
    this at build time and reads it off the manifest instead. The seam already allows that; the manifest
    field already exists for it.
    """
    undirected = _undirected_adjacency(artifact)
    found = components(artifact)

    largest = found[0] if found else frozenset()
    diameter = 0
    for node_id in largest:
        reach = _distances(node_id, undirected)
        diameter = max(diameter, max(reach.values(), default=0))

    descendants = _descendant_adjacency(artifact)
    max_path_hops = 0
    for node_id in undirected:
        reach = _distances(node_id, descendants)
        max_path_hops = max(max_path_hops, max(reach.values(), default=0))

    return GraphStructure(
        component_count=len(found),
        largest_component=len(largest),
        diameter=diameter,
        isolated_nodes=sum(1 for node_id, near in undirected.items() if not near),
        max_path_hops=max_path_hops,
    )
