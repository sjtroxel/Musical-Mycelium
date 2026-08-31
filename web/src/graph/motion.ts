/**
 * Step 7's motion, as arithmetic.
 *
 * Split out of `GraphView` for the same reason `subgraph.ts` is: jsdom has no canvas, so anything
 * computed inside the render loop cannot be tested at all. Everything here is a pure function of
 * elapsed milliseconds, so the *timing* is checkable even though the pixels are not, and the canvas
 * code is left with nothing but `ctx` calls.
 *
 * **What step 7 found, and why this file exists at all.** The map was never static. Replaying the
 * captured fixtures frame by frame through `buildRenderGraph` and `layout` showed two different
 * motions already happening as hard cuts: the acid jazz subject reflows vertically four times as its
 * column fills (y = 0, -110, -88, -88, -44), and on the Kate Bush descendants answer faint context
 * edges convert into numbered claimed edges one at a time as the gate approves them — context 10, 9,
 * 8, 7. The second of those is the claims-first invariant becoming visible to a visitor, and it was
 * arriving unannounced. Step 7 was not adding motion to a still picture; it was deciding which of
 * the two motions already there was worth being able to see.
 *
 * **Decided by sjtroxel on 2026-08-31, from three modes compared in the real running app.** A third
 * mode, `reveal`, animated the claim edges but cut the camera; it is gone. It lost because it was
 * indistinguishable from this one until the camera tween existed, and once the camera moved too,
 * this one was the clear pick. The reasoning is in the phase 5 IMPLEMENTATION doc, step 7.
 */

/**
 * `none` is the still image step 6 committed: one draw, hard cuts, no loop.
 * `animated` draws a newly approved claim edge in and moves the camera with it.
 */
export type MotionMode = "none" | "animated";

/**
 * How long a newly approved claim edge takes to draw itself in.
 *
 * **850ms, chosen by eye in the running app**, not derived. The previews ran at 420 and sjtroxel's
 * read was "kind of fast"; 700 was better and 850 was the pick. It is deliberately slower than a UI
 * transition would be, because this is not a UI transition — it is the gate approving a claim, and
 * the whole argument for animating it at all is that a visitor gets to watch the grounding happen.
 */
export const EDGE_MS = 850;

/**
 * How long the camera takes to settle after the picture changes shape.
 *
 * 526 is 850 x the 260/420 proportion the previews ran at. The two were picked against each other
 * rather than independently: the camera arriving before the edge finishes is what makes the edge,
 * not the rescale, the thing the eye follows. Change one and this proportion is what to preserve.
 */
export const POSITION_MS = 526;

export interface MotionFrame {
  /** 0..1, how far the camera and any moved node have travelled from where they were last drawn. */
  positionT: number;
  /** 0..1, how much of a newly approved claim edge is drawn, and the alpha of a new node. */
  edgeT: number;
  /** True when nothing further will change and the loop can stop. */
  done: boolean;
}

const clamp01 = (value: number): number => (value < 0 ? 0 : value > 1 ? 1 : value);

/** Decelerating. Motion that starts fast and settles reads as a thing arriving, not a thing sliding. */
export function easeOutCubic(t: number): number {
  const c = clamp01(t);
  return 1 - (1 - c) ** 3;
}

export const lerp = (from: number, to: number, t: number): number => from + (to - from) * t;

/** The state of one animation frame, `elapsed` ms after the picture last changed. */
export function frameAt(mode: MotionMode, elapsed: number): MotionFrame {
  if (mode === "none") return { positionT: 1, edgeT: 1, done: true };

  return {
    positionT: easeOutCubic(elapsed / POSITION_MS),
    edgeT: easeOutCubic(elapsed / EDGE_MS),
    done: elapsed >= Math.max(EDGE_MS, POSITION_MS),
  };
}

/**
 * The camera: how the laid-out coordinates are fitted into the box for one picture.
 *
 * Kept as data rather than baked into a closure because **the camera moves more than the nodes do,**
 * which is the measurement that decided this step. On the acid jazz answer, as claims arrive the map
 * rescales from k=1.576 to 0.768 and the canvas grows from 260px to 390px; on the last claim the
 * subject travels 65px on screen and only 34 of those come from its layout position changing. An
 * earlier version tweened node coordinates alone, smoothed about half the travel, hard-cut the rest,
 * and was reported as looking identical to the mode that smoothed nothing — correctly, because the
 * eye saw the same jump either way.
 */
export interface View {
  k: number;
  cx: number;
  cy: number;
  originX: number;
  height: number;
}

export const lerpView = (from: View, to: View, t: number): View => ({
  k: lerp(from.k, to.k, t),
  cx: lerp(from.cx, to.cx, t),
  cy: lerp(from.cy, to.cy, t),
  originX: lerp(from.originX, to.originX, t),
  height: lerp(from.height, to.height, t),
});

/**
 * Which mode to run in.
 *
 * **`prefers-reduced-motion` is the only input, and it is the whole of DoD 6.** The CSS blanket rule
 * in `styles.css` cannot reach this: it zeroes transition and animation durations, and a canvas
 * driven by `requestAnimationFrame` has neither. That is the gap step 5 named when it said DoD 6
 * "lands properly at step 7".
 *
 * There was a `?motion=` override while the three modes were being compared. It is gone with them —
 * a switch that can turn an accessibility preference back on is a switch worth not having.
 */
export function resolveMotionMode(reducedMotion: boolean): MotionMode {
  return reducedMotion ? "none" : "animated";
}

/** True when this browser asks for reduced motion. False anywhere `matchMedia` does not exist. */
export function prefersReducedMotion(): boolean {
  return (
    typeof window !== "undefined" &&
    typeof window.matchMedia === "function" &&
    window.matchMedia("(prefers-reduced-motion: reduce)").matches
  );
}

/**
 * Everything about a picture that the drawing depends on, as one comparable string.
 *
 * **The animation is keyed to this, never to the `RenderGraph` object.** `buildRenderGraph` runs on
 * every React render and returns a fresh object each time, so object identity changes when nothing
 * has: a prose token arriving mid-answer produces a new graph that is byte-for-byte the same picture.
 * Keyed on identity, that tears down the running animation and restarts it with nothing left to
 * enter, and the edge being drawn snaps instantly to full length. Keyed on content, an unrelated
 * re-render is a no-op and the edge keeps drawing.
 *
 * Labels are deliberately absent. They are stable per id in the artifact, and a picture whose labels
 * somehow changed still redraws correctly — the signature decides when the animation *restarts*, not
 * whether a draw happens.
 */
export function graphSignature(graph: {
  nodes: readonly { id: string; role: string; year: number | null }[];
  edges: readonly { kind: string; from: string; to: string; order: number | null }[];
}): string {
  const nodes = graph.nodes.map((n) => `${n.id}:${n.role}:${n.year ?? ""}`).join(",");
  const edges = graph.edges.map((e) => `${e.kind}:${e.from}>${e.to}:${e.order ?? ""}`).join(",");
  return `${nodes}|${edges}`;
}

/**
 * The identity of a drawn claim edge, used to tell a newly approved one from one already on screen.
 *
 * Deliberately **not** the approval ordinal. Ordinals renumber — an edge that was 3 in one render can
 * be 3 in the next while being a different edge — and keying on the ordinal would animate the wrong
 * line. The endpoint pair is what `subgraph.ts` already de-duplicates on.
 */
export const edgeKey = (from: string, to: string): string => `${from}>${to}`;
