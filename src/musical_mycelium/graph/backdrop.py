"""Solve the backdrop layout offline and emit it as a packed TypeScript module.

Phase 7 step 3. Run it with ``make backdrop``; the output is committed, the way
``web/src/corpus-facts.json`` is, so the SPA build needs no Python.

Three decisions, all forced rather than chosen.

1. **The layout is solved HERE, not in the browser.** A backdrop is ambient and may never compete for
   the main thread with the thing it sits behind. Positions are solved once, offline, and the page
   only draws them.

2. **The result is INLINED into the bundle, not fetched.** ``web/src/App.test.tsx`` asserts the page
   makes no network request on load -- phase 5 DoD 5, whose reason is that first paint must not wait
   on anything. A backdrop that fetches its positions would break that test, and the honest options
   were to weaken DoD 5 or to make the data small enough to ship inline. **Small enough won**, because
   a decorative layer is a bad reason to relax a guarantee about first paint. Packed binary in base64
   costs roughly 35 KB against a 320 KB script budget.

3. **Deterministic from a seed, with no wall clock.** Same picture from the same artifact and seed,
   every time, so the committed file is verifiable against the corpus rather than trusted. See
   ``tests/test_backdrop.py``.

The layout is grid-accelerated force-directed: repulsion between nodes sharing or adjoining a cell,
attraction along edges. ``numpy`` is not a dependency of this project and an O(n^2) repulsion over
1,465 nodes in pure Python is minutes per run; the grid makes it seconds. It is an approximation and
does not need to be better -- the picture goes behind text at low alpha and what a reader perceives is
clusters and filaments, both of which survive it.
"""

from __future__ import annotations

import base64
import json
import math
import random
import struct
from collections import defaultdict
from pathlib import Path
from typing import TypedDict

from musical_mycelium.graph.memory import PINNED_ARTIFACT_VERSION as ARTIFACT_VERSION

REPO = Path(__file__).resolve().parents[3]
ARTIFACT = REPO / f"src/musical_mycelium/artifacts/v{ARTIFACT_VERSION}/graph.json"
OUT = REPO / "web/src/graph/backdropData.ts"

SEED = 7
ITERATIONS = 320
WIDTH = 1600.0
HEIGHT = 900.0
CELL = 44.0
REPULSION = 340.0
ATTRACTION = 0.0055
DAMPING = 0.86
MAX_STEP = 24.0
# Positions are quantised to 16 bits over the unit box: a 65,536-step grid across a 1,600px render is
# forty times finer than a pixel, so the quantisation is invisible and the file halves.
SCALE = 65535


#: Which edges the backdrop DRAWS. **Decided by sjtroxel on 2026-09-11, phase 7.6 step 6.** Every edge in
#: the largest component still shapes the layout, membership included; only these are shipped and drawn.
#: At artifact v0.10.0 drawing everything would be about 68 KB inlined, leaving ~9 KB of a script cap that
#: is deliberately too small for an animation library; drawing the lineage lines (influence and teaching,
#: 4,700 of 9,198 in the component) is about 45 KB and every node still appears. On v0.7.1 the positions
#: are byte-identical to the all-edges build, because the solve did not change; only fewer lines ship.
DRAWN_PREDICATES = frozenset({"influenced_by", "studied_with"})


def largest_component(nodes: list[dict], edges: list[dict]) -> list[str]:
    """Node ids of the largest component, undirected over every edge, sorted for determinism."""
    adjacent: dict[str, set[str]] = defaultdict(set)
    for edge in edges:
        adjacent[edge["subject_id"]].add(edge["object_id"])
        adjacent[edge["object_id"]].add(edge["subject_id"])

    seen: set[str] = set()
    components: list[list[str]] = []
    for node in nodes:
        if node["id"] in seen:
            continue
        stack, group = [node["id"]], []
        seen.add(node["id"])
        while stack:
            current = stack.pop()
            group.append(current)
            for neighbor in adjacent[current]:
                if neighbor not in seen:
                    seen.add(neighbor)
                    stack.append(neighbor)
        components.append(group)
    components.sort(key=len, reverse=True)
    return sorted(components[0])


def solve(count: int, links: list[tuple[int, int]]) -> tuple[list[float], list[float]]:
    """Grid-accelerated force layout. Pure function of ``count``, ``links`` and ``SEED``."""
    rng = random.Random(SEED)
    # A ring start rather than a uniform square: from a square the densest cluster spends the first
    # hundred iterations fighting its way out of the middle, and 320 is not enough to recover.
    px, py = [0.0] * count, [0.0] * count
    for i in range(count):
        angle = rng.random() * math.tau
        radius = math.sqrt(rng.random()) * min(WIDTH, HEIGHT) * 0.46
        px[i] = WIDTH / 2 + math.cos(angle) * radius
        py[i] = HEIGHT / 2 + math.sin(angle) * radius
    vx, vy = [0.0] * count, [0.0] * count

    for step in range(ITERATIONS):
        heat = 1.0 - (step / ITERATIONS) * 0.75
        buckets: dict[tuple[int, int], list[int]] = defaultdict(list)
        for i in range(count):
            buckets[(int(px[i] // CELL), int(py[i] // CELL))].append(i)

        fx, fy = [0.0] * count, [0.0] * count
        for (cx, cy), members in buckets.items():
            near: list[int] = []
            for ox in (-1, 0, 1):
                for oy in (-1, 0, 1):
                    near.extend(buckets.get((cx + ox, cy + oy), ()))
            for i in members:
                for j in near:
                    if i == j:
                        continue
                    dx, dy = px[i] - px[j], py[i] - py[j]
                    d2 = dx * dx + dy * dy
                    if d2 < 1e-6:
                        # Coincident nodes need a DETERMINISTIC nudge. A random one would make the
                        # committed file unverifiable against the artifact, which is the whole point.
                        dx, dy, d2 = (i - j) * 1e-3, (j - i) * 1e-3, 1e-6
                    force = REPULSION / d2
                    fx[i] += dx * force
                    fy[i] += dy * force

        for a, b in links:
            dx, dy = px[b] - px[a], py[b] - py[a]
            fx[a] += dx * ATTRACTION
            fy[a] += dy * ATTRACTION
            fx[b] -= dx * ATTRACTION
            fy[b] -= dy * ATTRACTION

        for i in range(count):
            vx[i] = (vx[i] + fx[i]) * DAMPING
            vy[i] = (vy[i] + fy[i]) * DAMPING
            # Clamped travel per step. Without it a node in the densest cell is flung off the canvas
            # on iteration one and never comes back.
            px[i] += max(-MAX_STEP, min(MAX_STEP, vx[i] * heat))
            py[i] += max(-MAX_STEP, min(MAX_STEP, vy[i] * heat))
    return px, py


class Packed(TypedDict):
    """What `build` returns. A TypedDict rather than a bare dict so the counts stay integers to mypy:
    `dict[str, object]` made every comparison in `tests/test_backdrop.py` an error against `object`."""

    artifact_version: str
    seed: int
    iterations: int
    node_count: int
    edge_count: int
    xy: str
    kinds: str
    edges: str


def build() -> Packed:
    """Solve, normalise into the unit box, and pack. Returns the manifest that gets emitted."""
    graph = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    nodes, edges = graph["nodes"], graph["edges"]
    keep = largest_component(nodes, edges)
    index = {node_id: i for i, node_id in enumerate(keep)}
    kind_of = {n["id"]: n["kind"] for n in nodes if n["id"] in index}
    inside = [e for e in edges if e["subject_id"] in index and e["object_id"] in index]
    # Every edge in the component shapes the picture; only the lineage lines are drawn and shipped.
    layout = [(index[e["subject_id"]], index[e["object_id"]]) for e in inside]
    links = [
        (index[e["subject_id"]], index[e["object_id"]])
        for e in inside
        if e["predicate"] in DRAWN_PREDICATES
    ]

    px, py = solve(len(keep), layout)
    min_x, max_x = min(px), max(px)
    min_y, max_y = min(py), max(py)
    span = max(max_x - min_x, max_y - min_y) or 1.0

    xy = bytearray()
    for i in range(len(keep)):
        xy += struct.pack(
            "<HH",
            round((px[i] - min_x) / span * SCALE),
            round((py[i] - min_y) / span * SCALE),
        )
    # Kinds as a bitfield: 1,465 bits is 184 bytes, against 1,465 bytes for one byte each.
    kinds = bytearray((len(keep) + 7) // 8)
    for i, node_id in enumerate(keep):
        if kind_of[node_id] == "artist":
            kinds[i // 8] |= 1 << (i % 8)
    packed_edges = bytearray()
    for a, b in links:
        packed_edges += struct.pack("<HH", a, b)

    # Degree is NOT shipped: it is one pass over the edge list in the browser, and 1,465 more bytes
    # for something derivable is the kind of thing an asset budget exists to catch.
    return Packed(
        artifact_version=ARTIFACT_VERSION,
        seed=SEED,
        iterations=ITERATIONS,
        node_count=len(keep),
        edge_count=len(links),
        xy=base64.b64encode(bytes(xy)).decode("ascii"),
        kinds=base64.b64encode(bytes(kinds)).decode("ascii"),
        edges=base64.b64encode(bytes(packed_edges)).decode("ascii"),
    )


TEMPLATE = """// GENERATED by `make backdrop` -- do not edit. Source: src/musical_mycelium/graph/backdrop.py
//
// The backdrop's node positions, solved offline from artifact v{version} and packed. Committed and
// INLINED rather than fetched, because `App.test.tsx` asserts the page makes no network request on
// load and a decorative layer is a bad reason to relax a guarantee about first paint.
//
// {nodes} nodes, {edges} lineage edges drawn (influence and teaching; membership shapes the layout\n// but is not drawn), seed {seed}. `tests/test_backdrop.py` re-solves from the pinned
// artifact and fails if this file and the corpus have drifted apart.

export const BACKDROP = {{
  artifactVersion: "{version}",
  seed: {seed},
  nodeCount: {nodes},
  edgeCount: {edges},
  /** uint16 x, uint16 y per node, little-endian, over a 0..65535 unit box. */
  xy: "{xy}",
  /** One bit per node: 0 genre, 1 artist. */
  kinds: "{kinds}",
  /** uint16 subject index, uint16 object index per edge. */
  edges: "{edgelist}",
}} as const;
"""


def emit() -> Path:
    data = build()
    OUT.write_text(
        TEMPLATE.format(
            version=data["artifact_version"],
            seed=data["seed"],
            nodes=data["node_count"],
            edges=data["edge_count"],
            xy=data["xy"],
            kinds=data["kinds"],
            edgelist=data["edges"],
        ),
        encoding="utf-8",
    )
    return OUT


if __name__ == "__main__":
    path = emit()
    kb = path.stat().st_size / 1024
    print(f"wrote {path.relative_to(REPO)} ({kb:.0f} KB) from artifact v{ARTIFACT_VERSION}")
