/**
 * One ordered timeline, and one cursor into it. Phase 7 step 6.
 *
 * Scope doc DoD 2: *"Narration and camera are driven by one timeline, demonstrably — desynchronization
 * should be impossible by construction, not merely unobserved."*
 *
 * **How that is made structural rather than promised.** The tempting shape is two functions — one
 * telling the panel what text to show, one telling the map where to point — and a test asserting they
 * agree. That test can only ever observe agreement on the cases it enumerates. Instead there is exactly
 * one function, `stateAt`, returning exactly one `StepState`, and the panel and the map are two
 * *readings of the same value*. There is no second thing to disagree with.
 *
 * **It reuses `applyFrame` rather than reimplementing it**, which is the other half of the same idea. A
 * tour's state at time t is the live reducer folded over the cues that have fired by t. Not a parallel
 * implementation that behaves the same; the same implementation, over a prefix. A change to how a frame
 * updates state cannot land in one and miss the other.
 *
 * **This file owns no loop.** `ticker.ts` owns the only `requestAnimationFrame` on the page and its
 * docstring forbids it growing priorities or a scheduler; a cue list is neither, and it does not live
 * there. This module is pure arithmetic over an elapsed millisecond count, for the same reason
 * `motion.ts` is: jsdom has no canvas, so the timing is checkable even though the pixels are not.
 */

import type { Frame } from "../types";
import { applyFrame, emptyStep, type StepState } from "../useLineageRun";
import { EDGE_MS } from "./motion";

/** One frame, and when the tour shows it. */
export interface Cue {
  /** Milliseconds from the start of the tour. Monotonically non-decreasing across a cue list. */
  atMs: number;
  kind: Frame["type"];
  payload: Frame;
}

/**
 * How long a claim holds the screen before the next cue.
 *
 * **Reused from `motion.ts` rather than chosen**, and the reuse is the point: `EDGE_MS` is how long a
 * newly approved claim edge takes to draw itself in. Pacing claims faster than that would start the
 * next one before the last had finished arriving, so the camera would never once come to rest. Any
 * future tuning of the tour's pace has to keep this relationship, not just this number.
 */
export const CLAIM_MS = EDGE_MS;

/**
 * Milliseconds per prose token.
 *
 * **Derived, not decided — and this comment exists so nobody later reads it as decided.** `EDGE_MS` and
 * `ENTER_MS` were both compared in the running app against alternatives; this number has not been. 45ms
 * is roughly unhurried reading speed for the short tokens this model emits, and it is a knob precisely
 * so that looking at it later is cheap. **Timings are derived rather than captured on purpose:** real
 * arrival times carry model latency, so replaying them faithfully would reproduce the dead air.
 */
export const TOKEN_MS = 45;

/** What the machinery says about itself: shown, but not dwelt on. */
export const STEP_MS = 220;

/** A pause before the narration starts, so the map is legible before words compete with it. */
export const SETTLE_MS = 400;

/** How long one cue holds the screen before the next may fire. */
function dwell(frame: Frame): number {
  switch (frame.type) {
    case "claim":
      return CLAIM_MS;
    case "token":
      return TOKEN_MS;
    // The last claim has landed and the camera is settling; let it, before prose starts.
    case "path":
      return SETTLE_MS;
    case "plan":
    case "tool":
    case "rejected":
    case "contested":
    case "refused":
      return STEP_MS;
    // `done` is the end. Nothing waits on it, and giving it a dwell would pad the tour's tail with a
    // silence that reads as a hang rather than as an ending.
    case "done":
      return 0;
  }
}

/**
 * Assign a time to every frame, in order.
 *
 * Pure and total: same frames in, same cues out, no clock read and no randomness. That is what lets the
 * property test generate sequences instead of enumerating three of them.
 */
export function cuesFrom(frames: readonly Frame[], tokenMs: number = TOKEN_MS): Cue[] {
  const cues: Cue[] = [];
  let atMs = 0;
  for (const frame of frames) {
    cues.push({ atMs, kind: frame.type, payload: frame });
    atMs += frame.type === "token" ? tokenMs : dwell(frame);
  }
  return cues;
}

/** Where the tour has reached: the index of the last cue that has fired, or -1 before the first. */
export function cursorAt(cues: readonly Cue[], elapsedMs: number): number {
  let last = -1;
  for (const [index, cue] of cues.entries()) {
    if (cue.atMs > elapsedMs) break;
    last = index;
  }
  return last;
}

/** The total run time of a cue list, including the last cue's dwell. */
export function durationOf(cues: readonly Cue[], tokenMs: number = TOKEN_MS): number {
  const last = cues.at(-1);
  if (last === undefined) return 0;
  return last.atMs + (last.payload.type === "token" ? tokenMs : dwell(last.payload));
}

/**
 * **The whole point of this module.** The one state at a moment, from which both the narration and the
 * camera are read.
 *
 * Callers do not get a cursor and go fetch two things with it. They get the state, and there is only
 * one, so there is nothing for a second consumer to be out of step with.
 */
export function stateAt(cues: readonly Cue[], elapsedMs: number, query: string): StepState {
  const cursor = cursorAt(cues, elapsedMs);
  let step = emptyStep(query);
  for (const cue of cues.slice(0, cursor + 1)) step = applyFrame(step, cue.payload);
  return step;
}
