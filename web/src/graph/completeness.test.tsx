import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GraphView } from "./GraphView";
import type { RenderGraph } from "./subgraph";

/**
 * **Step 9, DoD 7: a closed outline means a closed record.**
 *
 * A node whose corpus connections are all drawn gets a solid stroke; one with connections still off
 * screen gets a broken one. Three encodings were compared in the running app on 2026-09-01 and the
 * broken stroke won on a channel argument rather than on legibility — a faint outer ring read better
 * alone but stacked with the `--ink` selection ring into three concentric circles, so selection
 * stopped being its own state. Rings mean selection; the outline means completeness.
 *
 * These tests exist because of 2026-08-31, when three motion modes were handed over, sjtroxel ran
 * them and reported they looked exactly the same — and he was right, while twelve tests passed.
 * jsdom has no canvas, so the only thing assertable here is what was asked of the context. That is
 * enough to catch the failure that actually matters: the marking silently applying to everything, or
 * to nothing.
 */

interface Call {
  op: string;
  args: number[];
}

function recorder() {
  const calls: Call[] = [];
  const rec =
    (op: string) =>
    (...args: unknown[]) => {
      calls.push({ op, args: args.filter((a): a is number => typeof a === "number") });
    };
  const ctx = {
    save: rec("save"),
    restore: rec("restore"),
    beginPath: rec("beginPath"),
    closePath: rec("closePath"),
    moveTo: rec("moveTo"),
    lineTo: rec("lineTo"),
    stroke: rec("stroke"),
    // Recorded with its pattern intact, because an empty pattern is the RESET and a non-empty one is
    // the marking. Collapsing the two would make "every node is marked" indistinguishable from
    // "no node is marked", which is exactly the pair of failures this file is for.
    setLineDash: (pattern: number[]) => calls.push({ op: "setLineDash", args: pattern }),
    fill: rec("fill"),
    arc: rec("arc"),
    clearRect: rec("clearRect"),
    setTransform: rec("setTransform"),
    fillText: rec("fillText"),
    strokeText: rec("strokeText"),
    measureText: () => ({ width: 42 }),
    font: "",
    textAlign: "left",
    textBaseline: "middle",
    globalAlpha: 1,
    strokeStyle: "",
    fillStyle: "",
    lineWidth: 1,
  };
  return { ctx, calls };
}

/**
 * Two walked nodes and one context node with two connections the map never drew.
 *
 * `hidden: 2` on exactly one of three nodes is the whole fixture, and the mix is the point. The step
 * 7 and step 8 lesson, hit twice independently: a fixture too small to exercise the behaviour looks
 * exactly like a broken implementation. A graph where every node read `hidden: 0` would pass a test
 * that asserted "nothing is marked" while proving nothing at all.
 */
const GRAPH: RenderGraph = {
  nodes: [
    { id: "Q1", label: "acid jazz", kind: "genre", year: 1987, role: "walked", hidden: 0 },
    { id: "Q2", label: "hip-hop", kind: "genre", year: 1979, role: "walked", hidden: 0 },
    { id: "Q3", label: "jazz", kind: "genre", year: 1900, role: "context", hidden: 2 },
  ],
  edges: [
    {
      from: "Q2",
      to: "Q1",
      kind: "claimed",
      predicate: "influenced_by",
      order: 1,
      verification: "HAND",
    },
    {
      from: "Q3",
      to: "Q2",
      kind: "context",
      predicate: "influenced_by",
      order: null,
      verification: null,
    },
  ],
  claimed: 1,
  context: 1,
  opened: 0,
  truncated: false,
};

function draw(graph: RenderGraph = GRAPH): Call[] {
  const { ctx, calls } = recorder();
  const outer = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = ((): unknown => ctx) as HTMLCanvasElement["getContext"];

  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  // `motion="none"` so what is asserted is the encoding and not a frame of an animation.
  act(() => root.render(<GraphView graph={graph} motion="none" />));
  act(() => root.unmount());
  host.remove();

  HTMLCanvasElement.prototype.getContext = outer;
  return calls;
}

const dashes = (calls: Call[]) =>
  calls.filter((call) => call.op === "setLineDash" && call.args.length > 0);

afterEach(() => {
  vi.restoreAllMocks();
});

describe("a closed outline means a closed record", () => {
  it("breaks the outline of the node with connections off screen, and only that node", () => {
    // One of the three nodes has hidden connections, so exactly one dash pattern is set. A marking
    // that applied to every node would say the corpus is endless everywhere, which is the opposite
    // of what this corpus is and the opposite of what DoD 7 asks the map to show.
    expect(dashes(draw())).toHaveLength(1);
  });

  it("resets the dash so the marking cannot leak onto whatever is drawn next", () => {
    // Canvas state is global and sticky. Without the reset the first incomplete node would break
    // every stroke after it — labels, rings, the next node — and the whole picture would read as
    // incomplete. The reset must therefore be at least as frequent as the marking.
    const calls = draw();
    const resets = calls.filter((call) => call.op === "setLineDash" && call.args.length === 0);
    expect(resets.length).toBeGreaterThanOrEqual(dashes(calls).length);
  });

  it("draws nothing at all when the map is showing everything the corpus holds", () => {
    // The half that makes the encoding mean something. On a complete picture the map must be
    // byte-for-byte what it was before step 9: a marker that never clears would say every map is
    // incomplete forever, which is a different lie from the one this step is fixing.
    const complete: RenderGraph = {
      ...GRAPH,
      nodes: GRAPH.nodes.map((node) => ({ ...node, hidden: 0 })),
    };
    expect(dashes(draw(complete))).toHaveLength(0);
  });

  it("marks every incomplete node when there is more than one", () => {
    // Guards the opposite mistake from the first test: an implementation that marked only the first
    // one it met, or only a context node, would pass everything above.
    const many: RenderGraph = {
      ...GRAPH,
      nodes: GRAPH.nodes.map((node) => ({ ...node, hidden: node.id === "Q2" ? 0 : 3 })),
    };
    expect(dashes(draw(many))).toHaveLength(2);
  });
});

describe("the caption explains the marking, and only when there is one", () => {
  function captionOf(graph: RenderGraph): string {
    const { ctx } = recorder();
    const outer = HTMLCanvasElement.prototype.getContext;
    HTMLCanvasElement.prototype.getContext = ((): unknown =>
      ctx) as HTMLCanvasElement["getContext"];
    const host = document.createElement("div");
    document.body.append(host);
    const root = createRoot(host);
    act(() => root.render(<GraphView graph={graph} motion="none" />));
    const text = host.querySelector(".map__caption")?.textContent ?? "";
    act(() => root.unmount());
    host.remove();
    HTMLCanvasElement.prototype.getContext = outer;
    return text;
  }

  it("says what a broken outline means when something is actually marked", () => {
    expect(captionOf(GRAPH)).toMatch(/broken outline/);
  });

  it("does not teach a visitor to look for a mark that is not on screen", () => {
    // On a complete map the sentence would send someone hunting for a broken outline that does not
    // exist. What replaces it is the finding itself, and it is the more interesting half: on this
    // corpus, two of the five canonical chips draw a picture with nothing hidden behind it at all.
    const complete: RenderGraph = {
      ...GRAPH,
      nodes: GRAPH.nodes.map((node) => ({ ...node, hidden: 0 })),
    };
    const caption = captionOf(complete);
    expect(caption).not.toMatch(/broken outline/);
    expect(caption).toMatch(/everything the corpus holds around this answer/);
  });
});
