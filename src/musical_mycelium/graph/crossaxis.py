"""Routes that cross from a genre to the musicians who played it and back out. Phase 8 step 4.

The measurement this module exists for, taken on artifact v0.10.0: **`delta blues` and `Detroit techno`
have no influence path at all**, in either direction, not even ignoring direction. Add membership and a
five-hop route appears. That gap is the whole premise of phase 8 and
`docs/phases/phase-8-membership-tour.md` §0 carries it.

**A cross-axis route is NOT a chain and this module will not produce one.** `ToolResult.chain` has a
contract — every consecutive pair is the `(subject_id, object_id)` of one of the result's own proposals,
and `loop.chain_is_approved` states that `(a, b)` means *a came out of b*. A cross-axis route cannot
satisfy that and must not be made to:

    Delta blues -> Chicago blues -> Freddie King -> funk -> electro -> Detroit techno

Hop 2 walks from a genre to an artist, but the claim underneath it is *Freddie King plays Chicago blues*
— subject artist, object genre, the other way round. Feeding that route through `chain` would assert
that Chicago blues came out of Freddie King, and that funk came out of him too. Fluent, cited, and
false, which is the failure `CLAUDE.md` names first for this phase.

So the walk is undirected and each hop records **which way its own edge actually runs**. Nothing here
decides how it is narrated; it reports what the corpus holds and the gate decides what survives.

**Why undirected is correct rather than a concession.** Influence and teaching run forward in time, so a
directed walk is meaningful for them. Membership does not run in time at all: an artist playing a genre
is a standing fact, and "traverse it backwards" is not a reversal of anything. A route through musicians
is a statement about *shared personnel*, never about descent, and orienting it would imply a direction
the relationship does not have.
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heappop, heappush

from musical_mycelium.graph.schema import (
    PREDICATE_INFLUENCED_BY,
    PREDICATE_PLAYS_GENRE,
    PREDICATE_STUDIED_WITH,
    Edge,
)
from musical_mycelium.graph.store import Direction, GraphStore

#: Everything a cross-axis route may walk. Membership is the point; influence and teaching are here so a
#: route can pass through a stretch of ordinary lineage rather than being forced through an artist at
#: every step.
ROUTE_PREDICATES = frozenset(
    {PREDICATE_INFLUENCED_BY, PREDICATE_PLAYS_GENRE, PREDICATE_STUDIED_WITH}
)

#: A route longer than this is not an answer, it is a demonstration that the graph is connected. Six
#: hops is already at the edge of legible -- scope doc risk 3: *"four influence hops read as a story;
#: genre to artist to genre to artist to genre may read as a graph traversal, which is what it is and
#: not what a demo wants."* The cap is a product judgement, not a graph one.
MAX_ROUTE_HOPS = 6


@dataclass(frozen=True, slots=True)
class Hop:
    """One step of a route, with the edge that justifies it and the direction that edge runs.

    ``forward`` is the field that keeps this honest. It is ``True`` when the route steps the same way
    the edge points (``edge.subject_id`` -> ``edge.object_id``) and ``False`` when the route walks
    against it. **A consumer that ignores it will state the reverse of what the source says** for every
    backwards hop, which on a membership edge means announcing that a genre performed an artist.
    """

    #: Where the route is at the start of this hop.
    from_id: str
    #: Where the route is after it.
    to_id: str
    #: The artifact edge underneath, whichever way it points.
    edge: Edge
    #: True when ``from_id`` is the edge's subject.
    forward: bool

    @property
    def predicate(self) -> str:
        return self.edge.predicate

    @property
    def claim_pair(self) -> tuple[str, str]:
        """The pair a ``ClaimProposal`` for this hop must carry: **the edge's own orientation**, never
        the route's. This is the one place the two can be confused and the only place it matters."""
        return (self.edge.subject_id, self.edge.object_id)


def _edges_both_ways(store: GraphStore, node_id: str) -> list[tuple[Edge, bool]]:
    """Every route-walkable edge touching ``node_id``, paired with whether it points away from it."""
    out = [
        (e, True)
        for e in store.neighbors(node_id, Direction.INFLUENCED_BY, predicates=ROUTE_PREDICATES)
    ]
    out += [
        (e, False)
        for e in store.neighbors(node_id, Direction.INFLUENCED, predicates=ROUTE_PREDICATES)
    ]
    return out


def genre_count(store: GraphStore, node_id: str, memo: dict[str, int] | None = None) -> int:
    """How many genres this artist is documented in. 0 for a genre node.

    **The specificity signal, and it is not a quality judgement.** A musician documented in three genres
    tells you something when they appear between two of them; one documented in eighteen connects
    almost anything to almost anything, and a route through them is a fact about the tagging rather than
    about music. Corpus measured 2026-09-18: median 1, mean 2.4, max 18.
    """
    if memo is not None and node_id in memo:
        return memo[node_id]
    count = len(
        store.neighbors(
            node_id, Direction.INFLUENCED_BY, predicates=frozenset({PREDICATE_PLAYS_GENRE})
        )
    )
    if memo is not None:
        memo[node_id] = count
    return count


def cross_axis_route(
    store: GraphStore, from_id: str, to_id: str, *, max_hops: int = MAX_ROUTE_HOPS
) -> tuple[Hop, ...]:
    """The shortest route between two nodes, ignoring direction, breaking ties by pivot specificity.

    **Shortest first, and among equally short routes the one through the most specific musicians.**

    *(Ranking added 2026-09-18, phase 8 step 4c. The first cut returned whichever route the BFS reached
    first and argued that "shortest rather than best" avoided a hidden taste judgement. That argument
    was wrong, and measurably: `delta blues` to `Detroit techno` has **seven** routes tied at five hops,
    so shortest does not choose -- edge order chose, which hides the judgement instead of declining to
    make one. Six of the seven pivoted through an artist documented in ten genres, producing a fully
    sourced answer that no reader would accept.)*

    **Why specificity and not evidence strength**, which was the obvious first answer and was tested and
    rejected: on that pair the sensible route and the absurd ones rest on **identical** provenance --
    every membership hop is a Wikidata statement whose only reference is `imported from Russian
    Wikipedia`. Ranking by citation quality would have been a coin flip between them.

    **Why this is not the blended score ``graph/routes.py`` refuses.** That module declines to fold
    incommensurable things into one number because the trade it hides is real. This folds nothing: it is
    lexicographic, ``(hops, worst pivot, total pivots)``, each term exact and each reportable on its own.
    ``route_specificity`` returns the numbers so a caller can show them rather than trusting the order.

    The search is uniform-cost rather than breadth-first because the cost is lexicographic and
    **monotone** -- hops only increase along a path and the worst pivot only gets worse -- which is
    exactly the condition that makes a priority-first search correct here.
    """
    if from_id == to_id or store.get_node(from_id) is None or store.get_node(to_id) is None:
        return ()

    memo: dict[str, int] = {}
    previous: dict[str, tuple[str, Edge, bool]] = {}
    # (hops, worst pivot degree, total pivot degree, tie-break id) -> the node
    start = (0, 0, 0, from_id)
    frontier: list[tuple[int, int, int, str]] = [start]
    best: dict[str, tuple[int, int, int]] = {from_id: (0, 0, 0)}

    while frontier:
        hops, worst, total, node_id = heappop(frontier)
        if (hops, worst, total) > best.get(node_id, (hops, worst, total)):
            continue
        if node_id == to_id:
            return _rebuild(previous, from_id, to_id)
        if hops >= max_hops:
            continue
        for edge, forward in _edges_both_ways(store, node_id):
            next_id = edge.object_id if forward else edge.subject_id
            # The pivot's own promiscuity is charged when the route ARRIVES at it, and the endpoints are
            # never charged: a route is not worse for the genres its destination happens to carry.
            degree = 0 if next_id == to_id else genre_count(store, next_id, memo)
            cost = (hops + 1, max(worst, degree), total + degree)
            if next_id in best and cost >= best[next_id]:
                continue
            best[next_id] = cost
            previous[next_id] = (node_id, edge, forward)
            heappush(frontier, (*cost, next_id))
    return ()


def route_specificity(store: GraphStore, hops: tuple[Hop, ...]) -> tuple[int, int]:
    """``(worst pivot, total pivots)`` for a route: the numbers the ranking used, for reporting.

    Returned rather than folded away because the honest form of this is *"connected through Freddie
    King, documented in 4 genres"* -- a reader can weigh that. A rank with no visible basis is the thing
    ``graph/routes.py`` spent a whole module refusing.
    """
    memo: dict[str, int] = {}
    degrees = [
        genre_count(store, hop.to_id, memo)
        for hop in hops[:-1]  # every interior node; the destination is not a pivot
    ]
    return (max(degrees, default=0), sum(degrees))


def _rebuild(
    previous: dict[str, tuple[str, Edge, bool]], from_id: str, to_id: str
) -> tuple[Hop, ...]:
    hops: list[Hop] = []
    node_id = to_id
    while node_id != from_id:
        prior, edge, forward = previous[node_id]
        hops.append(Hop(from_id=prior, to_id=node_id, edge=edge, forward=forward))
        node_id = prior
    return tuple(reversed(hops))


def crosses_axes(hops: tuple[Hop, ...]) -> bool:
    """Whether this route actually leaves the influence layer. A route that does not is an ordinary
    lineage answer that arrived through the wrong tool, and the tool says so rather than dressing it
    up as something it is not."""
    return any(hop.predicate == PREDICATE_PLAYS_GENRE for hop in hops)
