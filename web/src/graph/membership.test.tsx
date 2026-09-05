import { act } from "react";
import { createRoot } from "react-dom/client";
import { describe, expect, it } from "vitest";
import { GraphView } from "./GraphView";
import { layerOf } from "./layout";
import { PREDICATE_INFLUENCED_BY, PREDICATE_PLAYS_GENRE } from "./staticGraph";
import type { RenderEdge, RenderGraph, RenderNode } from "./subgraph";

/**
 * **Membership is not derivation, and the map must not be able to say it is.**
 *
 * Artifact v0.7.1 added 2,782 `plays_genre` edges against 2,284 `influenced_by` — membership became
 * the MAJORITY of the corpus — and every part of the map had been written when "every edge is an
 * influence edge" was a true assumption. Re-pinning without this file would have made the map state
 * that Miles Davis was derived from jazz: `layerOf` puts x = influence depth, so a membership edge
 * fed into it asserts that the artist came after the genre, and a solid line drawn between them
 * looks exactly like the arrow of history next to it.
 *
 * `CLAUDE.md` forbids precisely this — membership must never read as derivation — and the gate
 * cannot help here, because the map reads the static artifact directly and never passes through it.
 *
 * Both halves are asserted, and each is asserted in the form that FAILS when the guard is removed
 * rather than in the form that merely passes today.
 */

const node = (id: string, label: string, kind: string, year: number | null): RenderNode => ({
  id,
  label,
  kind,
  year,
  role: "walked",
  hidden: 0,
});

const influence = (from: string, to: string): RenderEdge => ({
  from,
  to,
  kind: "context",
  predicate: PREDICATE_INFLUENCED_BY,
  order: null,
  verification: null,
});

const membership = (genre: string, artist: string): RenderEdge => ({
  from: genre,
  to: artist,
  kind: "context",
  predicate: PREDICATE_PLAYS_GENRE,
  order: null,
  verification: null,
});

/** Two genres in an influence chain, and an artist who plays the later one. */
const NODES = [
  node("Q_blues", "blues", "genre", 1890),
  node("Q_jazz", "jazz", "genre", 1900),
  node("Q_miles", "Miles Davis", "artist", null),
];

describe("membership creates no influence depth", () => {
  it("does not move any node into a later column", () => {
    // The assertion that matters. `blues -> jazz` is one hop, so jazz sits at layer 1. Miles Davis
    // plays jazz, and if that membership edge were layered he would land at layer 2 -- one column
    // PAST the genre, which on this map means "came out of it". He did not come out of jazz.
    const layers = layerOf(NODES, [influence("Q_blues", "Q_jazz"), membership("Q_jazz", "Q_miles")]);

    expect(layers.get("Q_blues")).toBe(0);
    expect(layers.get("Q_jazz")).toBe(1);
    expect(layers.get("Q_miles")).toBe(0);
  });

  it("gives the identical layering with the membership edges removed", () => {
    // The stronger form of the same claim, and the one that survives a refactor: membership edges
    // must be INERT to layout, not merely handled. Adding or removing them cannot move anything.
    const withMembership = layerOf(NODES, [
      influence("Q_blues", "Q_jazz"),
      membership("Q_jazz", "Q_miles"),
    ]);
    const without = layerOf(NODES, [influence("Q_blues", "Q_jazz")]);

    expect([...withMembership.entries()].sort()).toEqual([...without.entries()].sort());
  });

  it("still layers an artist by the influence edges it does have", () => {
    // The counterweight. All 804 artists in v0.7.1 carry at least one artist-to-artist influence
    // edge, so ignoring membership must not mean ignoring artists: a system that refused to place
    // any artist would be as wrong as one that placed them by membership, and would look correct
    // on the test above.
    const layers = layerOf(
      [...NODES, node("Q_bird", "Charlie Parker", "artist", null)],
      [influence("Q_bird", "Q_miles"), membership("Q_jazz", "Q_miles")],
    );

    expect(layers.get("Q_miles")).toBe(1);
  });
});

interface Call {
  op: string;
  args: number[];
}

function draw(edges: RenderEdge[]): Call[] {
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

  const graph: RenderGraph = {
    nodes: NODES,
    edges,
    claimed: 0,
    context: edges.length,
    opened: 0,
    truncated: false,
  };

  const outer = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = ((): unknown => ctx) as HTMLCanvasElement["getContext"];
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  act(() => root.render(<GraphView graph={graph} motion="none" />));
  act(() => root.unmount());
  host.remove();
  HTMLCanvasElement.prototype.getContext = outer;
  return calls;
}

/** The dotted pattern membership uses. `[2, 2]` is the node ring's "incomplete record" and is not this. */
const DOTTED = [1, 3];

const dotted = (calls: Call[]) =>
  calls.filter(
    (call) =>
      call.op === "setLineDash" &&
      call.args.length === DOTTED.length &&
      call.args.every((value, index) => value === DOTTED[index]),
  );

describe("membership is drawn as a different kind of line", () => {
  it("dots a membership edge", () => {
    // jsdom has no canvas, so what is assertable is what was ASKED of the context -- which is
    // exactly the failure that matters here: the encoding applying to everything, or to nothing.
    // This is the 2026-08-31 lesson, where three motion modes looked identical and twelve tests
    // passed.
    expect(dotted(draw([membership("Q_jazz", "Q_miles")]))).not.toHaveLength(0);
  });

  it("leaves an influence edge solid", () => {
    // The half that makes the encoding mean something. If influence were dotted too, the two would
    // be indistinguishable again and the test above would still pass.
    expect(dotted(draw([influence("Q_blues", "Q_jazz")]))).toHaveLength(0);
  });

  it("resets the dash so membership cannot leak onto the rest of the picture", () => {
    // Canvas state is global and sticky. Without the reset, one membership edge would break every
    // stroke drawn after it and the whole map would read as dotted.
    const calls = draw([membership("Q_jazz", "Q_miles"), influence("Q_blues", "Q_jazz")]);
    const resets = calls.filter((call) => call.op === "setLineDash" && call.args.length === 0);
    expect(resets.length).toBeGreaterThanOrEqual(dotted(calls).length);
  });
});
