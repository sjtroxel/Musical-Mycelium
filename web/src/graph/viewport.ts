import type { View } from "./motion";
import type { Point } from "./layout";

/**
 * Step 8's camera, as arithmetic.
 *
 * Split out of `GraphView` for the third time and for the same reason `layout.ts`, `motion.ts` and
 * `subgraph.ts` are: jsdom has no canvas, so anything computed inside the render loop cannot be
 * tested at all. Step 7 is the standing argument for doing this without being asked — twelve passing
 * tests missed two real defects because they rendered the component bare, and the arithmetic those
 * defects lived in was inside the draw closure where nothing could reach it.
 *
 * So every decision this file makes about where the camera may go is a pure function of a `View`,
 * and `GraphView` is left holding pointer events and `ctx` calls.
 *
 * **What this file does NOT do: move a node.** Pan and zoom move the camera; nothing moves the
 * graph. Step 5 decided that x is influence depth and y is year within the column, so a node's
 * position is a claim about the music. A visitor dragging a node would be dragging it to a position
 * that says something false, and no amount of "it is obviously just a picture" makes that not the
 * case. This is decision D5 of step 8 and it is the reason there is no `dragNode` here.
 */

/** The projected extent of the drawn content, in screen pixels. */
export interface Bounds {
  minX: number;
  maxX: number;
  minY: number;
  maxY: number;
}

/**
 * How far in and out a visitor may zoom, as absolute values of `View.k`.
 *
 * Absolute rather than relative to the auto-fit scale, which was the first thing tried. Relative
 * bounds sound better — they behave the same on a 3-node chip and a 40-node one — but the auto-fit
 * scale keeps changing while an answer streams, so the *bounds themselves* would move under a
 * visitor who had already taken the camera, which is the exact yank D1 exists to prevent. A fixed
 * pair of numbers cannot do that.
 *
 * Calibrated against the measured range: `layout.ts` places columns 160 units apart and rows 44
 * apart, and the auto-fit `k` across the real chips runs 0.77 to 1.58 with a 2.2 cap. At k=10 one
 * column gap is 1600px, which is one node filling the frame; at k=0.1 a seven-column map is 96px
 * wide, which is as far out as is any use.
 */
export const MIN_K = 0.1;
export const MAX_K = 10;

/**
 * How far inside the canvas edge the middle of the map is kept, in pixels.
 *
 * Without a rule of some kind a visitor can pan the graph entirely out of frame and be left holding
 * an empty box with no way to know which direction to drag back. Not a hypothetical: it is the first
 * thing that happens when you flick a trackpad on a small map.
 *
 * **The rule is "the centre of the drawn content stays on screen", and it replaced a more elaborate
 * one that could not be tested.** The first version demanded a minimum *overlap* between the content
 * box and the canvas, with the demand capped at the content's own size so a one-node map could not
 * be asked to show 72px of itself. Deleting that cap changed where the map came to rest and broke
 * nothing, which the break-it pass caught: the test written to guard it passed with the guard
 * removed. A rule whose violation is invisible is not a rule.
 *
 * Clamping a single point into a rectangle cannot conflict with itself and cannot fail to terminate,
 * so the property is now one sentence and the test for it is an equality rather than an inequality.
 * It is also a better guarantee than the one it replaced. If the content is larger than the canvas,
 * its centre being on screen means the canvas is entirely covered; if it is smaller, its centre
 * being on screen means the whole thing is roughly in view.
 */
export const EDGE_INSET = 48;

/** Layout coordinates to screen pixels. The same transform `GraphView` draws with. */
export function project(view: View, point: Point): Point {
  return {
    x: (point.x - view.cx) * view.k + view.originX,
    y: (point.y - view.cy) * view.k + view.height / 2,
  };
}

/**
 * Screen pixels back to layout coordinates.
 *
 * The exact inverse of `project`, and it has to stay that way: zooming about the pointer works by
 * asking what graph point sits under the cursor and then solving for the camera that keeps it there.
 * A projection whose inverse is even slightly off makes the map creep under the cursor while you
 * zoom, which reads as the map being slippery rather than as a rounding error.
 */
export function unproject(view: View, point: Point): Point {
  return {
    x: (point.x - view.originX) / view.k + view.cx,
    y: (point.y - view.height / 2) / view.k + view.cy,
  };
}

/**
 * Move the camera by a screen-pixel delta.
 *
 * Dragging content to the right means moving the camera to the left, hence the subtraction, and the
 * division by `k` converts screen pixels to layout units so a drag tracks the pointer exactly at
 * every zoom level. Content that lags or outruns the cursor is this division being missed.
 */
export function panBy(view: View, dxScreen: number, dyScreen: number): View {
  return { ...view, cx: view.cx - dxScreen / view.k, cy: view.cy - dyScreen / view.k };
}

/**
 * Zoom by `factor` about a fixed screen point, so whatever is under the cursor stays under it.
 *
 * Zooming about the centre instead is one line shorter and feels broken: the thing you are pointing
 * at slides away exactly when you are trying to look at it. The graph point under the cursor is
 * solved for before the scale changes and the camera centre is then chosen to put it back.
 */
export function zoomAbout(view: View, screenPoint: Point, factor: number): View {
  const k = clampScale(view.k * factor);
  // Nothing to solve if the clamp refused the change; returning early also keeps the identity
  // `zoomAbout(v, p, 1) === v` exactly true rather than true to within floating point.
  if (k === view.k) return view;

  const anchor = unproject(view, screenPoint);
  return {
    ...view,
    k,
    cx: anchor.x - (screenPoint.x - view.originX) / k,
    cy: anchor.y - (screenPoint.y - view.height / 2) / k,
  };
}

export const clampScale = (k: number): number => Math.min(MAX_K, Math.max(MIN_K, k));

/** Where the drawn nodes land on screen under this camera. */
export function projectedBounds(view: View, points: readonly Point[]): Bounds | null {
  if (points.length === 0) return null;
  const screen = points.map((point) => project(view, point));
  return {
    minX: Math.min(...screen.map((p) => p.x)),
    maxX: Math.max(...screen.map((p) => p.x)),
    minY: Math.min(...screen.map((p) => p.y)),
    maxY: Math.max(...screen.map((p) => p.y)),
  };
}

/**
 * Pull the camera back until the centre of the drawn content is on screen.
 *
 * Applied per axis, as a clamp of one point into one rectangle. The inset is capped at half the
 * canvas in each axis so that a canvas narrower than `2 * EDGE_INSET` collapses to "keep the centre
 * at the middle" rather than producing an inverted range — the only way this could have gone wrong,
 * and the reason the cap is here rather than assumed away.
 */
export function clampView(view: View, points: readonly Point[], width: number): View {
  const bounds = projectedBounds(view, points);
  if (bounds === null) return view;

  const pull = (min: number, max: number, extent: number): number => {
    const inset = Math.min(EDGE_INSET, extent / 2);
    const centre = (min + max) / 2;
    return Math.min(Math.max(centre, inset), extent - inset) - centre;
  };

  const dx = pull(bounds.minX, bounds.maxX, width);
  const dy = pull(bounds.minY, bounds.maxY, view.height);
  if (dx === 0 && dy === 0) return view;
  return panBy(view, dx, dy);
}

/** A node as the hit-tester needs it: an id, a layout position, and how big it is drawn. */
export interface HitCandidate {
  id: string;
  x: number;
  y: number;
  radius: number;
}

/**
 * How much bigger than its dot a node's click target is, in screen pixels.
 *
 * Context nodes are drawn at radius 3.5 and a 3.5px target is not clickable by a person with a
 * trackpad, let alone a finger. The slop is added in *screen* space rather than layout space so the
 * target does not shrink as you zoom out — which is precisely when the dots are hardest to hit.
 */
export const HIT_SLOP = 9;

/**
 * The node under a screen point, or `null`.
 *
 * Nearest-wins rather than first-wins. Overlapping targets are normal here: `layout.ts` places a
 * whole column at one x, and at low zoom a busy column's dots are a few pixels apart, so first-wins
 * would return whichever node happened to be earlier in the array and feel arbitrary.
 */
export function hitTest(
  view: View,
  candidates: readonly HitCandidate[],
  screenPoint: Point,
): string | null {
  let best: string | null = null;
  let bestDistance = Number.POSITIVE_INFINITY;

  for (const candidate of candidates) {
    const at = project(view, candidate);
    const distance = Math.hypot(at.x - screenPoint.x, at.y - screenPoint.y);
    if (distance <= candidate.radius + HIT_SLOP && distance < bestDistance) {
      best = candidate.id;
      bestDistance = distance;
    }
  }

  return best;
}

/**
 * How far a pointer may travel between down and up and still count as a click rather than a drag.
 *
 * Without a threshold every pan that starts on a node also selects it, because a drag ends with the
 * pointer up and the pointer is still over the node it started on. 4px is enough to absorb the
 * wobble of a physical click without swallowing a deliberate short drag.
 */
export const CLICK_SLOP = 4;

/**
 * One wheel notch, as a scale factor.
 *
 * Applied as `SCALE_PER_NOTCH ** -(deltaY / 100)` so a trackpad's many small deltas and a mouse
 * wheel's few large ones both end up proportional rather than one of them being unusable. Zoom has
 * to be multiplicative: adding a constant to `k` is fast at the near end and imperceptible at the
 * far end, because what the eye reads is the ratio.
 */
export const SCALE_PER_NOTCH = 1.35;

export const wheelFactor = (deltaY: number): number => SCALE_PER_NOTCH ** (-deltaY / 100);

/** What the +/- buttons and the keyboard do. One press is a little less than a wheel notch. */
export const STEP_IN = 1.25;
export const STEP_OUT = 1 / STEP_IN;
