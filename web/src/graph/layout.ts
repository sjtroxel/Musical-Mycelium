import { PREDICATE_INFLUENCED_BY } from "./staticGraph";
import type { RenderEdge, RenderGraph, RenderNode } from "./subgraph";

/**
 * Where each node goes, as a pure function.
 *
 * **Step 5's decision: x is influence depth, not the year, and there is no simulation.** The
 * reasoning is recorded in full in the phase 5 IMPLEMENTATION doc; the short version is that a
 * chronological axis cannot be drawn on this corpus. All 141 dated nodes are genres and all 804
 * artists are undated, and artists and genres sit in disjoint components, so a map is either
 * entirely dated or entirely undated. A time axis would work on four chips and have literally
 * nothing to place on the two Kate Bush panels.
 *
 * Influence depth is derived from the edges instead, which every node has. It also makes "every
 * arrow points left to right" a property of the layout rather than a hope about the data — and that
 * matters, because 6 of the 102 datable edges in the corpus run BACKWARDS in time (swing 1930
 * influencing Western swing 1928, and five more). On a year axis those draw as arrows pointing back
 * the way they came, which is the map asserting an influence arrived before its own cause.
 *
 * The dates are not thrown away: they order nodes *within* a column. Time survives as sequence
 * rather than as distance, which is the only claim an `inception_year` can actually support — it is
 * a Wikidata field, not a measurement.
 *
 * Positions here are in an abstract space. `GraphView` projects them into the canvas box, the same
 * way it did with the simulation's output.
 */

/** Arbitrary units. The projection rescales both, so only their ratio sets the aspect. */
const COLUMN_GAP = 160;
const ROW_GAP = 44;

export interface Point {
  x: number;
  y: number;
}

/**
 * Longest-path layering. `from` is the object and `to` is the subject, so an edge runs older to
 * newer and a node sits one column past the deepest thing that influenced it.
 *
 * Kahn's algorithm, and a node inside a cycle simply keeps the layer it had when the queue drained.
 *
 * **The cycle tolerance is load-bearing, and the claim that used to be here was wrong.** This read
 * "there are no cycles in artifact v0.5.0 — measured, not assumed" until 2026-09-04. Re-measured at
 * phase 6 step 5: v0.5.0 contains `post-rock <-> shoegaze`, a two-cycle, both edges from Wikidata, and
 * it has been there since the first genre cut. v0.7.0 has six such reciprocal pairs, two of which are
 * genuinely contested between sources. Nothing rendered wrongly, because the defensive branch below was
 * already correct — but it was defending against something the comment said could not happen.
 */
export function layerOf(
  nodes: readonly RenderNode[],
  edges: readonly RenderEdge[],
): Map<string, number> {
  const known = new Set(nodes.map((node) => node.id));
  const indegree = new Map(nodes.map((node) => [node.id, 0]));
  const outgoing = new Map<string, string[]>(nodes.map((node) => [node.id, []]));

  for (const edge of edges) {
    // **Membership creates no depth, and this line is the whole reason the map can show artists and
    // genres together honestly.** x is influence depth, so a node's column asserts "everything to my
    // left came before me". `plays_genre` carries no such claim: an artist who played bebop is not
    // downstream of bebop, and laying them out as though they were would draw derivation the corpus
    // never recorded -- the exact thing `CLAUDE.md` forbids when it says membership must never read
    // as derivation. Skipped here rather than filtered by the caller so every caller gets it.
    if (edge.predicate !== PREDICATE_INFLUENCED_BY) continue;
    if (!known.has(edge.from) || !known.has(edge.to)) continue;
    indegree.set(edge.to, (indegree.get(edge.to) ?? 0) + 1);
    outgoing.get(edge.from)?.push(edge.to);
  }

  const layer = new Map(nodes.map((node) => [node.id, 0]));
  const queue = [...indegree].filter(([, degree]) => degree === 0).map(([id]) => id);

  while (queue.length > 0) {
    const id = queue.shift() as string;
    for (const next of outgoing.get(id) ?? []) {
      layer.set(next, Math.max(layer.get(next) ?? 0, (layer.get(id) ?? 0) + 1));
      const remaining = (indegree.get(next) ?? 0) - 1;
      indegree.set(next, remaining);
      if (remaining === 0) queue.push(next);
    }
  }

  return layer;
}

/**
 * Deterministic positions: the same graph draws the same picture every single time.
 *
 * That is a deliberate property and not a side effect. `subgraph.ts` already sorts the context
 * neighbourhood by label so that one answer draws one map twice; a force simulation put that back
 * by settling somewhere new on every load. A screenshot in a writeup now matches what a visitor
 * sees, and `prefers-reduced-motion` is satisfied by there being no settling animation to suppress
 * rather than by suppressing one.
 */
/**
 * How many nodes land in the busiest column.
 *
 * The map's height follows this. A column layout puts every node at a fixed x, so a wide column has
 * only the vertical to spread into — and at a fixed 300px the acid jazz answer squeezed eleven nodes
 * into a stack of anonymous dots that read as an artefact of the layout rather than as the
 * neighbourhood it is. Measured across the five chips the worst column is 11; the corpus-wide worst
 * is 259, which no chip can reach because `subgraph.ts` caps context at 40.
 */
export function tallestColumn(graph: RenderGraph): number {
  const layer = layerOf(graph.nodes, graph.edges);
  const counts = new Map<number, number>();
  for (const node of graph.nodes) {
    const index = layer.get(node.id) ?? 0;
    counts.set(index, (counts.get(index) ?? 0) + 1);
  }
  return Math.max(1, ...counts.values());
}

export function layout(graph: RenderGraph): Map<string, Point> {
  const layer = layerOf(graph.nodes, graph.edges);

  const columns = new Map<number, RenderNode[]>();
  for (const node of graph.nodes) {
    const index = layer.get(node.id) ?? 0;
    columns.set(index, [...(columns.get(index) ?? []), node]);
  }

  const placed = new Map<string, Point>();
  for (const [index, column] of columns) {
    // Oldest at the top; undated nodes sink to the bottom of their column in label order. Sorting
    // undated nodes to the END rather than treating a missing year as 0 matters: a missing year is
    // "the sources do not say", and putting those nodes at the ancient end of the column would be
    // the map inventing a date for them.
    const ordered = [...column].sort(
      (left, right) =>
        (left.year ?? Number.POSITIVE_INFINITY) - (right.year ?? Number.POSITIVE_INFINITY) ||
        left.label.localeCompare(right.label),
    );
    const offset = ((ordered.length - 1) * ROW_GAP) / 2;
    ordered.forEach((node, row) => {
      placed.set(node.id, { x: index * COLUMN_GAP, y: row * ROW_GAP - offset });
    });
  }

  return placed;
}
