import { StrictMode } from "react";
import { act, cleanup, render } from "@testing-library/react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it, vi } from "vitest";
import { GraphView } from "./GraphView";
import {
  EDGE_MS,
  POSITION_MS,
  frameAt,
  graphSignature,
  lerpView,
  resolveMotionMode,
} from "./motion";
import type { RenderGraph } from "./subgraph";

/**
 * Step 7's motion, checked twice over: the arithmetic on its own, and the drawing that consumes it.
 *
 * **The second half exists because of a specific, repeated failure in this phase.** Steps 5 and 6
 * each shipped a check that could not distinguish the behaviour it asserted from something adjacent —
 * a bounding box that measured a column instead of a word, a regex that matched remembered copy
 * instead of real copy — and step 3 nearly decided a one-way door on a preview that rendered and was
 * inert. `map.test.tsx` says the pixels are checked in a real browser, and for a still image that was
 * a reasonable division. It stops being reasonable here: jsdom returns `null` from `getContext`, so
 * `GraphView` returns on its third line and **a completely dead animation loop passes every other
 * test in this repo.** A green suite would have meant nothing at all.
 *
 * So the context is stubbed with a recorder and `requestAnimationFrame` with a hand-driven queue.
 * That does not check that the motion looks good — nothing here can, and sjtroxel decided that by
 * running it. What it checks is that motion *happens*, that it *converges on the still image step 6
 * committed*, and that reduced motion means no loop rather than a fast one.
 *
 * **Every assertion below was watched failing before it was kept.** Three of them caught real
 * defects that way: a StrictMode double-mount that made all three preview modes identical, an
 * animation keyed to a React object identity that snapped mid-draw on every prose token, and a
 * camera that never moved.
 */

/** acid jazz, one parent the gate approved, and one unwalked neighbour. */
const GRAPH: RenderGraph = {
  nodes: [
    { id: "Q221772", label: "acid jazz", kind: "genre", year: 1987, role: "walked" },
    { id: "Q11401", label: "hip-hop", kind: "genre", year: 1979, role: "walked" },
    { id: "Q8341", label: "jazz", kind: "genre", year: 1900, role: "context" },
  ],
  edges: [
    { from: "Q11401", to: "Q221772", kind: "claimed", order: 1, verification: "HAND" },
    { from: "Q8341", to: "Q11401", kind: "context", order: null, verification: null },
  ],
  claimed: 1,
  context: 1,
  truncated: false,
};

/**
 * The same answer many claims later, sized so the CAMERA actually has to move.
 *
 * Twelve extra parents, not one or two. The first attempt at this fixture added two and the camera
 * test failed against a working implementation: with a short column the scale is bound by the
 * horizontal fit and both heights clamp to the 260px minimum, so `k` came out 1.713 for both
 * pictures and there was no camera movement to smooth. At thirteen nodes in a column the vertical
 * term binds instead and the canvas grows 260 -> 450, which is the shape the real acid jazz answer
 * has and the reason a fixture that is too small proves nothing.
 */
const GROWN: RenderGraph = {
  nodes: [
    ...GRAPH.nodes,
    ...Array.from({ length: 12 }, (_, i) => ({
      id: `Q90${i}`,
      label: `parent ${i}`,
      kind: "genre",
      year: 1960 + i,
      role: "walked" as const,
    })),
  ],
  edges: [
    ...GRAPH.edges,
    ...Array.from({ length: 12 }, (_, i) => ({
      from: `Q90${i}`,
      to: "Q221772",
      kind: "claimed" as const,
      order: i + 2,
      verification: "HAND" as const,
    })),
  ],
  claimed: 13,
  context: 1,
  truncated: false,
};

/** Past the longest duration, so a stepped frame is guaranteed to be the final one. */
const AFTER_END = Math.max(EDGE_MS, POSITION_MS) + 1;

interface Call {
  op: string;
  args: number[];
}

/** A 2D context that records the geometry it is asked to draw and answers text measurement. */
function recordingContext(): { ctx: unknown; calls: Call[] } {
  const calls: Call[] = [];
  const rec =
    (op: string) =>
    (...args: unknown[]) =>
      calls.push({ op, args: args.filter((a): a is number => typeof a === "number") });

  const ctx = {
    save: rec("save"),
    restore: rec("restore"),
    beginPath: rec("beginPath"),
    closePath: rec("closePath"),
    moveTo: rec("moveTo"),
    lineTo: rec("lineTo"),
    stroke: rec("stroke"),
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

/** `requestAnimationFrame` under manual control, so frames land at timestamps a test chooses. */
function frameQueue() {
  let pending: FrameRequestCallback[] = [];
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    pending.push(cb);
    return pending.length;
  });
  vi.stubGlobal("cancelAnimationFrame", () => {
    pending = [];
  });
  return {
    /** Run every callback waiting, at time `now`. */
    step(now: number) {
      const due = pending;
      pending = [];
      for (const cb of due) cb(now);
    },
    get waiting() {
      return pending.length;
    },
  };
}

function install() {
  const { ctx, calls } = recordingContext();
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    ctx as unknown as CanvasRenderingContext2D,
  );
  return calls;
}

/** Every `lineTo` endpoint drawn since the last `clearRect`, i.e. the most recent frame only. */
function lastFrameLines(calls: Call[]): string[] {
  const start = calls.map((c) => c.op).lastIndexOf("clearRect");
  return calls
    .slice(start)
    .filter((c) => c.op === "lineTo")
    .map((c) => c.args.map((n) => n.toFixed(2)).join(","));
}

const frames = (calls: Call[]) => calls.filter((c) => c.op === "clearRect").length;

/**
 * The finished picture, i.e. exactly what step 6 committed.
 *
 * Rendered in its own throwaway root so it cannot disturb the render under test, and used as the
 * target every animation must converge on and must not have reached while it is still running.
 */
function stillImage(graph: RenderGraph): string[] {
  const { ctx, calls } = recordingContext();
  // Swapped and put back by hand rather than with `spyOn`. A second spy's `mockRestore` reinstates
  // the ORIGINAL method, which would silently tear down the recorder the test under test is using.
  const outer = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = ((): unknown =>
    ctx) as HTMLCanvasElement["getContext"];

  const host = document.createElement("div");
  document.body.appendChild(host);
  const root = createRoot(host);
  act(() => root.render(<GraphView graph={graph} motion="none" />));
  act(() => root.unmount());
  host.remove();

  HTMLCanvasElement.prototype.getContext = outer;
  return lastFrameLines(calls);
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("the timing, as arithmetic", () => {
  it("none is finished before it starts", () => {
    expect(frameAt("none", 0)).toEqual({ positionT: 1, edgeT: 1, done: true });
  });

  it("animated grows an edge over its full duration", () => {
    expect(frameAt("animated", 0).edgeT).toBe(0);
    expect(frameAt("animated", EDGE_MS / 2).edgeT).toBeGreaterThan(0);
    expect(frameAt("animated", EDGE_MS / 2).edgeT).toBeLessThan(1);
    expect(frameAt("animated", EDGE_MS).edgeT).toBe(1);
  });

  it("settles the camera before the edge finishes drawing", () => {
    // The proportion is the design, not an accident: the camera arriving first is what makes the
    // edge, rather than the rescale, the thing the eye follows.
    expect(POSITION_MS).toBeLessThan(EDGE_MS);
    expect(frameAt("animated", POSITION_MS).positionT).toBe(1);
    expect(frameAt("animated", POSITION_MS).done).toBe(false);
    expect(frameAt("animated", EDGE_MS).done).toBe(true);
  });

  it("clamps rather than overshooting when a frame lands late", () => {
    // A backgrounded tab can deliver the next frame seconds later. Overshoot would put a node past
    // where it belongs and a line past its own target.
    expect(frameAt("animated", 10_000)).toEqual({ positionT: 1, edgeT: 1, done: true });
  });
});

describe("which mode runs", () => {
  it("animates by default and stops dead for reduced motion", () => {
    // DoD 6, and the whole of it. There is no override: the `?motion=` switch used to compare the
    // preview modes is gone, because a switch that can turn an accessibility preference back on is
    // a switch worth not having.
    expect(resolveMotionMode(false)).toBe("animated");
    expect(resolveMotionMode(true)).toBe("none");
  });
});

describe("the camera", () => {
  const A = { k: 1, cx: 0, cy: 0, originX: 10, height: 260 };
  const B = { k: 2, cx: 100, cy: 50, originX: 30, height: 460 };

  it("interpolates every component, not just some of them", () => {
    expect(lerpView(A, B, 0)).toEqual(A);
    expect(lerpView(A, B, 1)).toEqual(B);
    expect(lerpView(A, B, 0.5)).toEqual({ k: 1.5, cx: 50, cy: 25, originX: 20, height: 360 });
  });
});

describe("the picture's identity", () => {
  it("ignores object identity and notices real change", () => {
    expect(graphSignature(GRAPH)).toBe(graphSignature({ ...GRAPH }));
    expect(graphSignature(GRAPH)).not.toBe(graphSignature(GROWN));
  });

  it("notices a claim being approved between two otherwise identical pictures", () => {
    const promoted: RenderGraph = {
      ...GRAPH,
      edges: [{ ...GRAPH.edges[0]!, order: 2 }, GRAPH.edges[1]!],
    };
    expect(graphSignature(promoted)).not.toBe(graphSignature(GRAPH));
  });
});

describe("the drawing that consumes it", () => {
  it("draws once and starts no loop in none", () => {
    const calls = install();
    const raf = frameQueue();

    render(<GraphView graph={GRAPH} motion="none" />);

    expect(frames(calls)).toBe(1);
    expect(raf.waiting).toBe(0);
  });

  it("actually animates: the claimed edge is shorter early than it ends up", () => {
    const calls = install();
    const raf = frameQueue();

    render(<GraphView graph={GRAPH} motion="animated" />);
    raf.step(0);
    const first = lastFrameLines(calls);

    raf.step(AFTER_END);

    // The assertion that would have caught a dead loop: the geometry is not the same twice.
    expect(first).not.toEqual(lastFrameLines(calls));
    expect(raf.waiting).toBe(0);
  });

  it("converges on exactly the still image none draws", () => {
    // The point of the whole step. Motion is allowed to change how the map arrives and forbidden to
    // change what it says once it has. If these ever diverge, the animation is drawing its own graph.
    const calls = install();
    const raf = frameQueue();

    render(<GraphView graph={GRAPH} motion="animated" />);
    raf.step(0);
    raf.step(AFTER_END);

    expect(lastFrameLines(calls)).toEqual(stillImage(GRAPH));
  });

  it("still animates under StrictMode, which is how the app actually mounts", () => {
    // `main.tsx` wraps the app in StrictMode, so React invokes this effect TWICE on mount in dev.
    // A single slot of memory meant the first pass recorded every edge as drawn and the second found
    // nothing new and painted the finished picture instantly. All three preview modes looked
    // identical in the browser while every test passed, because they rendered GraphView bare and the
    // app never does.
    const calls = install();
    const raf = frameQueue();

    render(
      <StrictMode>
        <GraphView graph={GRAPH} motion="animated" />
      </StrictMode>,
    );
    raf.step(0);
    const first = lastFrameLines(calls);
    raf.step(AFTER_END);

    expect(first).not.toEqual(lastFrameLines(calls));
  });

  it("keeps animating across a re-render that changes nothing", () => {
    // Prose tokens re-render the panel while an edge is still drawing itself in. The graph's content
    // is identical but `buildRenderGraph` returns a new object every time, so an effect keyed on
    // object identity tears the animation down and restarts it with nothing left to enter — the edge
    // snaps to full length mid-draw. This is a production bug, not a StrictMode artifact.
    const calls = install();
    const raf = frameQueue();

    const { rerender } = render(<GraphView graph={GRAPH} motion="animated" />);
    raf.step(0);

    rerender(<GraphView graph={{ ...GRAPH }} motion="animated" />);
    raf.step(EDGE_MS / 3);

    // Asserted against the FINISHED picture, not against the previous frame. "The geometry changed"
    // passes whether the edge is still growing or snapped straight to full length, which is the
    // check-that-cannot-see-its-subject failure this whole file exists because of.
    expect(lastFrameLines(calls)).not.toEqual(stillImage(GRAPH));
    expect(raf.waiting).toBeGreaterThan(0);
  });

  it("moves the camera, not only the nodes", () => {
    /**
     * The assertion that was missing when sjtroxel reported two of the preview modes looking
     * identical, and it would have caught the reason. The earlier version tweened node coordinates
     * only, but the nodes are not what moves: as claims arrive the map rescales and the canvas grows,
     * and that rescale was hard-cut. Roughly half a node's travel on screen was smoothed and half was
     * not, so the eye saw a jump either way.
     *
     * The canvas element's own height isolates it. Node tweening cannot produce a height between the
     * two pictures' heights; only an interpolated camera can.
     */
    install();
    const raf = frameQueue();

    const { container, rerender } = render(<GraphView graph={GRAPH} motion="animated" />);
    raf.step(0);
    raf.step(AFTER_END); // finish the first picture, so there is a camera to move away from
    const canvas = container.querySelector("canvas") as HTMLCanvasElement;
    const startHeight = Number.parseFloat(canvas.style.height);

    rerender(<GraphView graph={GROWN} motion="animated" />);
    raf.step(0);
    raf.step(POSITION_MS / 4);
    const midHeight = Number.parseFloat(canvas.style.height);

    raf.step(AFTER_END);
    const endHeight = Number.parseFloat(canvas.style.height);

    expect(endHeight).toBeGreaterThan(startHeight);
    expect(midHeight).toBeGreaterThan(startHeight);
    expect(midHeight).toBeLessThan(endHeight);
  });

  it("reduced motion draws the still image and starts no loop", () => {
    const calls = install();
    const raf = frameQueue();
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: query.includes("prefers-reduced-motion"),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));

    // No `motion` prop, so the component resolves it the way a real visitor would.
    render(<GraphView graph={GRAPH} />);

    // Not "a loop that finishes instantly" — no loop at all.
    expect(frames(calls)).toBe(1);
    expect(raf.waiting).toBe(0);
  });

  it("respects reduced motion turned on between two claims, not only at mount", () => {
    const calls = install();
    const raf = frameQueue();
    let reduced = false;
    vi.stubGlobal("matchMedia", (query: string) => ({
      matches: reduced && query.includes("prefers-reduced-motion"),
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
    }));

    const { rerender } = render(<GraphView graph={GRAPH} />);
    raf.step(0);
    const before = frames(calls);

    reduced = true;
    rerender(<GraphView graph={GROWN} />);

    // One more draw for the new picture, and nothing queued behind it.
    expect(frames(calls)).toBe(before + 1);
    expect(raf.waiting).toBe(0);
  });
});
