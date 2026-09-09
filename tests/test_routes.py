"""The route ranker: what it measures, and the one thing it deliberately refuses to do.

`graph/routes.py` exists because of the phase 7 scope doc's risk -- *"pick the tour route from measured
density, not from taste"* -- and the tests here mostly protect the shape of the answer rather than the
numbers, because the numbers move with the corpus and the shape must not.

**The shape being protected: it ranks, it does not decide.** A single blended score over incommensurable
columns is taste with a decimal point on it. The sort key is asserted to be lexicographic over separate
components so nobody quietly folds them into one.
"""

from __future__ import annotations

import pytest

from musical_mycelium.graph.memory import default_store
from musical_mycelium.graph.routes import (
    MAX_HOPS,
    MIN_HOPS,
    TIER_RANK,
    Route,
    candidates,
    contested_keys,
    load_artifact,
    render,
)


@pytest.fixture(scope="module")
def routes() -> list[Route]:
    return candidates(load_artifact(), contested_keys())


def test_the_sweep_finds_routes(routes: list[Route]) -> None:
    assert routes, "no candidate routes at all: the sweep or the corpus is broken"


def test_every_route_is_within_the_hop_bounds(routes: list[Route]) -> None:
    assert all(MIN_HOPS <= r.hops <= MAX_HOPS for r in routes)


def test_every_route_is_contiguous_and_real(routes: list[Route]) -> None:
    """Sampled rather than exhaustive: 20k routes through the store is minutes, and a break in the
    chain-building is systematic rather than occasional, so a sample finds it."""
    from musical_mycelium.graph.store import Direction

    store = default_store()
    for route in routes[:200]:
        assert len(route.chain) == route.hops + 1
        assert len(route.labels) == len(route.chain)
        for subject, obj in zip(route.chain, route.chain[1:], strict=False):
            edge = next(
                (
                    e
                    for e in store.neighbors(subject, Direction.INFLUENCED_BY)
                    if e.object_id == obj
                ),
                None,
            )
            assert edge is not None, f"{subject} -> {obj} is not an edge"


def test_the_weakest_tier_is_the_weakest_tier(routes: list[Route]) -> None:
    """`min_tier` is the headline because a chain is exactly as checkable as its worst hop. If it ever
    became the mean, one HAND edge would flatter four INFOBOX ones and the ranking would recommend
    routes that cannot be defended."""
    for route in routes[:200]:
        assert TIER_RANK.get(route.min_tier, 0) <= route.mean_tier + 1e-9


def test_the_ranking_is_not_a_blended_score(routes: list[Route]) -> None:
    """**The property this module exists to keep.** The key is a tuple compared lexicographically, so a
    strong tier cannot be bought with extra hops. If someone replaces it with a weighted sum, this fails."""
    key = routes[0].sort_key()
    assert isinstance(key, tuple)
    assert len(key) == 4

    strong_short = Route(("a", "b", "c"), ("a", "b", "c"), 2, "HAND", 5.0, 0, False, 0)
    weak_long = Route(("a",) * 7, ("a",) * 7, 6, "INFOBOX_AUTO", 1.0, 99, True, 999)
    assert strong_short.sort_key() > weak_long.sort_key(), (
        "length or corroboration outranked evidence: the key has become a blended score"
    )


def test_the_chosen_demo_route_is_in_the_candidate_set(routes: list[Route]) -> None:
    """Step 8's pick, asserted to be a thing the ranker actually produced rather than a route someone
    typed into a doc. If the corpus moves so this route stops existing, the demo is stale and this says
    so before a visitor finds out."""
    chosen = (
        "groove metal",
        "thrash metal",
        "speed metal",
        "heavy metal music",
        "blues rock",
        "blues",
    )
    assert any(route.labels == chosen for route in routes)


def test_the_chosen_route_still_beats_the_one_it_replaced(routes: list[Route]) -> None:
    """The measurement the choice rested on, kept as an assertion. `Detroit techno -> ... -> blues` was a
    step 5 taste pick; this ranked it 11,218th of 20,095 with every hop at the tier floor. If that ever
    inverts, the decision is worth re-reading rather than inheriting."""
    by_labels = {route.labels: route for route in routes}
    chosen = by_labels[
        ("groove metal", "thrash metal", "speed metal", "heavy metal music", "blues rock", "blues")
    ]
    replaced = by_labels[
        ("Detroit techno", "Chicago house", "hip-hop", "rhythm and blues", "blues")
    ]
    assert chosen.sort_key() > replaced.sort_key()
    assert replaced.mean_tier < chosen.mean_tier
    assert replaced.corroborated == 0


def test_the_report_names_the_artist_column_as_coverage(routes: list[Route]) -> None:
    """**A measured-and-rejected proxy has to keep its warning attached.** Artist counts look like a
    prominence signal and are not: Detroit techno and Chicago house both record zero. Printing the number
    without the caveat is how it becomes a ranking input again six months from now."""
    text = "\n".join(render(routes, top=3))
    assert "COVERAGE" in text
    assert "not a prominence figure" in text
    assert "NOT a blended score" in text
