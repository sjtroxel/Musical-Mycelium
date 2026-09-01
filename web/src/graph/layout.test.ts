import { describe, expect, it } from "vitest";
import { layerOf, layout } from "./layout";
import type { RenderEdge, RenderGraph, RenderNode } from "./subgraph";

const node = (id: string, year: number | null = null): RenderNode => ({
  id,
  label: id,
  kind: "genre",
  year,
  role: "walked",
  hidden: 0,
});

/** `from` is the object and `to` is the subject: the influence runs from -> to, older -> newer. */
const edge = (from: string, to: string): RenderEdge => ({
  from,
  to,
  kind: "claimed",
  order: 1,
  verification: "HAND",
});

const graph = (nodes: RenderNode[], edges: RenderEdge[]): RenderGraph => ({
  nodes,
  edges,
  claimed: edges.length,
  context: 0,
  opened: 0,
  truncated: false,
});

describe("layerOf", () => {
  it("puts a chain in one column per hop", () => {
    const layer = layerOf([node("a"), node("b"), node("c")], [edge("a", "b"), edge("b", "c")]);
    expect(layer.get("a")).toBe(0);
    expect(layer.get("b")).toBe(1);
    expect(layer.get("c")).toBe(2);
  });

  /**
   * This project's second named failure mode is assuming the direction of an edge — three separate
   * pieces of code answered the opposite question on 2026-08-14 and none of them raised. So this is
   * asserted from the meaning rather than from the implementation: `blues influenced heavy metal`
   * is written `edge("blues", "heavy metal")`, and BLUES is the one that must land on the left.
   */
  it("puts the influence earlier than the thing it influenced", () => {
    const layer = layerOf([node("blues"), node("heavy metal")], [edge("blues", "heavy metal")]);
    expect(layer.get("blues")).toBeLessThan(layer.get("heavy metal") as number);
  });

  it("takes the longest path when a node has two ancestors of different depths", () => {
    // a -> c directly, and a -> b -> c. c belongs past the deeper of the two, not the shallower.
    const layer = layerOf(
      [node("a"), node("b"), node("c")],
      [edge("a", "b"), edge("b", "c"), edge("a", "c")],
    );
    expect(layer.get("c")).toBe(2);
  });

  it("places a node with no edges at all in the first column", () => {
    expect(layerOf([node("lonely")], []).get("lonely")).toBe(0);
  });

  it("ignores an edge pointing at a node that is not on the map", () => {
    // subgraph.ts can hand over an edge whose endpoint was cut by the context cap.
    const layer = layerOf([node("a")], [edge("a", "not-drawn")]);
    expect(layer.get("a")).toBe(0);
  });

  it("terminates on a cycle instead of hanging the browser", () => {
    // v0.5.0 has no cycles; a later corpus cut could. A wrong column beats a locked-up tab.
    const layer = layerOf([node("a"), node("b")], [edge("a", "b"), edge("b", "a")]);
    expect(layer.size).toBe(2);
  });
});

describe("layout", () => {
  it("draws the same picture twice for the same graph", () => {
    // The whole reason the simulation was dropped at step 5. `subgraph.ts` already sorts the
    // neighbourhood so one answer yields one map; a settling simulation put that back.
    const g = graph(
      [node("a", 1950), node("b", 1960), node("c", 1970)],
      [edge("a", "b"), edge("b", "c")],
    );
    expect([...layout(g)]).toEqual([...layout(g)]);
  });

  it("advances x by column and never backwards along an edge", () => {
    const g = graph([node("a"), node("b"), node("c")], [edge("a", "b"), edge("b", "c")]);
    const placed = layout(g);
    for (const e of g.edges) {
      expect((placed.get(e.from) as { x: number }).x).toBeLessThan(
        (placed.get(e.to) as { x: number }).x,
      );
    }
  });

  it("orders a column oldest at the top", () => {
    const g = graph([node("young", 1990), node("old", 1920)], []);
    const placed = layout(g);
    expect((placed.get("old") as { y: number }).y).toBeLessThan(
      (placed.get("young") as { y: number }).y,
    );
  });

  /**
   * The one that matters most, and the reason the sort uses `Infinity` rather than `?? 0`.
   *
   * A missing `inception_year` means "the sources do not say", not "year zero". Sorting undated
   * nodes to the ancient end of the column would be the map inventing a date for exactly the nodes
   * the corpus is thinnest on — which here are the non-Western ones. Measured on artifact v0.5.0:
   * the three undated genres in the acid jazz and trip hop maps are Na mele paleoleo, Pinoy hip hop
   * and sampledelia.
   */
  it("sinks an undated node to the bottom of its column rather than treating it as year zero", () => {
    const g = graph([node("undated", null), node("ancient", 500)], []);
    const placed = layout(g);
    expect((placed.get("undated") as { y: number }).y).toBeGreaterThan(
      (placed.get("ancient") as { y: number }).y,
    );
  });

  it("centres a column on zero so the projection has nothing to correct", () => {
    const g = graph([node("a", 1), node("b", 2), node("c", 3)], []);
    const ys = [...layout(g).values()].map((p) => p.y);
    expect(ys.reduce((sum, y) => sum + y, 0)).toBeCloseTo(0);
  });

  it("places every node it was given", () => {
    const g = graph([node("a"), node("b"), node("c")], [edge("a", "b")]);
    expect(layout(g).size).toBe(3);
  });
});
