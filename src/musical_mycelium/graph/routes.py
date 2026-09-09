"""Rank candidate tour routes by measured properties. Phase 7 step 8.

Scope doc risk: *"If phase 6's density work did not reach the region a demo walks through, the demo shows
the corpus skew rather than the system. Pick the tour route from measured density, not from taste."*

**This module deliberately does NOT emit one score.** It ranks on evidence strength -- the property the
demo's honesty actually rests on -- and prints every other component as its own column. A single number
folded out of incommensurable things is taste with a decimal point on it: it hides the trade instead of
showing it, and the trade here is real and does not resolve. See ``RECOGNITION``.

**Reads the artifact directly rather than through ``GraphStore``**, the same choice ``backdrop.py`` makes
and for the same reason: the store answers node and neighbour questions, and this is a whole-corpus sweep
that wants the rows.

Run it with ``make routes``. Free, offline, reads the pinned artifact and nothing else.
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from musical_mycelium.graph.memory import PINNED_ARTIFACT_VERSION, artifact_directory

#: How strongly ONE source was checked, as a rank. **Not corroboration** -- that is a different field
#: answering a different question, and collapsing the two is an error this repo has already corrected
#: three files for. See ``.claude/rules/grounding-and-claims.md``.
TIER_RANK = {
    "HAND": 5,
    "PROSE_AUTO": 4,
    "ASSERTS_AUTO": 3,
    "EXPOSURE_AUTO": 2,
    "INFOBOX_AUTO": 1,
}

#: **A proxy that was measured and REJECTED as a score, kept as a printed column with its warning.**
#: The obvious stand-in for "would a visitor recognise this genre" is how many artists the corpus records
#: playing it. Measured 2026-09-09 it does not mean that at all: **Detroit techno has 0 artists and
#: Chicago house has 0**, while pop music has 158 and rock music 113. Neither of the first two is
#: obscure; the corpus's artists simply skew anglophone rock and pop. Ranking on this would have rejected
#: the route the tour is built on and systematically promoted exactly the region
#: ``.claude/rules/evals.md`` warns about. It is printed because a route whose nodes carry no artists at
#: all is worth knowing about before choosing it -- it just is not evidence of obscurity.
RECOGNITION = "artists recorded playing the genre -- a COVERAGE figure, not a prominence figure"

MIN_HOPS = 2
MAX_HOPS = 6
TOP_N = 15


@dataclass(frozen=True, slots=True)
class Route:
    """One candidate walk, with every component of its quality kept separate."""

    chain: tuple[str, ...]
    labels: tuple[str, ...]
    hops: int
    #: The WEAKEST edge on the route. A chain is exactly as checkable as its worst hop, so this is the
    #: honest headline rather than the mean, which lets one HAND edge flatter four INFOBOX ones.
    min_tier: str
    mean_tier: float
    corroborated: int
    crosses_contested: bool
    #: The least-covered node on the route. See ``RECOGNITION``: coverage, not prominence.
    min_artists: int

    def sort_key(self) -> tuple[int, float, int, int]:
        """Evidence first, then corroboration, then length. **Explicitly not a blended score.**"""
        return (TIER_RANK.get(self.min_tier, 0), self.mean_tier, self.corroborated, self.hops)


def load_artifact(version: str = PINNED_ARTIFACT_VERSION) -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(
        (Path(artifact_directory(version)) / "graph.json").read_text(encoding="utf-8")
    )
    return payload


def candidates(graph: dict[str, Any], contested: set[tuple[str, str]]) -> list[Route]:
    """Every genre-to-genre shortest ancestry walk between ``MIN_HOPS`` and ``MAX_HOPS`` hops.

    One BFS per source rather than a path call per pair: the corpus holds hundreds of genres, so pairwise
    shortest-path calls would be hundreds of thousands of searches to answer what one sweep answers.
    """
    nodes = {n["id"]: n for n in graph["nodes"]}
    influence = [e for e in graph["edges"] if e["predicate"] == "influenced_by"]

    up: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for edge in influence:
        up[edge["subject_id"]].append(edge)

    artists: dict[str, int] = defaultdict(int)
    for edge in graph["edges"]:
        if edge["predicate"] == "plays_genre":
            artists[edge["object_id"]] += 1

    genres = [nid for nid, node in nodes.items() if node.get("kind") == "genre"]
    routes: list[Route] = []

    for source in genres:
        previous: dict[str, dict[str, Any]] = {}
        seen = {source}
        queue = deque([source])
        while queue:
            current = queue.popleft()
            for edge in up.get(current, []):
                nxt = edge["object_id"]
                if nxt in seen:
                    continue
                seen.add(nxt)
                previous[nxt] = edge
                queue.append(nxt)

        for target in seen - {source}:
            edges: list[dict[str, Any]] = []
            cursor = target
            while cursor != source:
                edge = previous[cursor]
                edges.append(edge)
                cursor = edge["subject_id"]
            edges.reverse()
            if not MIN_HOPS <= len(edges) <= MAX_HOPS:
                continue
            if any(nodes[e["object_id"]].get("kind") != "genre" for e in edges):
                continue

            tiers = [str(e.get("verification") or "") for e in edges]
            ranks = [TIER_RANK.get(t, 0) for t in tiers]
            chain = (source, *(e["object_id"] for e in edges))
            routes.append(
                Route(
                    chain=chain,
                    labels=tuple(nodes[n]["label"] for n in chain),
                    hops=len(edges),
                    min_tier=min(tiers, key=lambda t: TIER_RANK.get(t, 0)),
                    mean_tier=sum(ranks) / len(ranks),
                    corroborated=sum(1 for e in edges if e.get("corroboration")),
                    crosses_contested=any(
                        tuple(sorted((e["subject_id"], e["object_id"]))) in contested for e in edges
                    ),
                    min_artists=min(artists.get(n, 0) for n in chain),
                )
            )

    return routes


def contested_keys() -> set[tuple[str, str]]:
    """The contested pairs as sorted id tuples, derived in ``graph/`` where the definition lives."""
    from musical_mycelium.graph.memory import default_store

    pairs = default_store().contested
    return {(min(p.a, p.b), max(p.a, p.b)) for p in pairs}


def render(routes: list[Route], top: int = TOP_N) -> list[str]:
    """The ranked list, with the components a chooser needs kept visible."""
    ranked = sorted(routes, key=lambda r: r.sort_key(), reverse=True)
    header = (
        f"{'hops':>4}  {'weakest':<14}{'mean':>5}  {'corrob':>6}  "
        f"{'contested':>9}  {'artists':>7}  route"
    )
    lines = [
        f"candidate tour routes: {len(routes)} genre-to-genre walks of {MIN_HOPS}-{MAX_HOPS} hops",
        "",
        "Ranked by WEAKEST edge tier, then mean tier, then corroboration, then length.",
        "NOT a blended score. Choosing is a judgement someone makes with these columns in front of",
        "them, and the trade between evidence strength and recognisability does not resolve.",
        "",
        f"  artists = {RECOGNITION}",
        "",
        header,
    ]
    for route in ranked[:top]:
        lines.append(
            f"{route.hops:>4}  {route.min_tier:<14}{route.mean_tier:>5.2f}  "
            f"{route.corroborated:>6}  {'yes' if route.crosses_contested else '-':>9}  "
            f"{route.min_artists:>7}  " + " -> ".join(route.labels)
        )
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank candidate guided-tour routes.")
    parser.add_argument("--top", type=int, default=TOP_N, help="how many routes to print")
    parser.add_argument(
        "--min-artists", type=int, default=0, help="drop routes below this coverage"
    )
    args = parser.parse_args()

    routes = candidates(load_artifact(), contested_keys())
    if args.min_artists:
        routes = [r for r in routes if r.min_artists >= args.min_artists]
    print("\n".join(render(routes, top=args.top)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
