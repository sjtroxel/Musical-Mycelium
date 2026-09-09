/**
 * The guided tour: one recorded run, replayed on one timeline. Phase 7 step 6.
 *
 * **Replay rather than a live call, decided 2026-09-09 on cost.** `.claude/rules/aws-and-cost.md` is
 * explicit that *"streamed responses are not interrupted when the invoking client connection is broken.
 * Customers are billed for the full function duration."* A tour that plays on load would bill a Bedrock
 * run per page view, from visitors who never asked a question. A replay is $0 and deterministic, which
 * is what a demo wants and what a live model cannot promise.
 *
 * **Live-on-demand is deferred, not rejected, and the seam is already here:** `timeline.ts` takes a cue
 * list, and a cue list can come from a recording (times baked in) or from a live run (times from
 * arrival). A "run it live" button is a second *input*, not a second implementation. It is also mostly
 * built already -- anyone who wants to watch it happen for real can type the query into the ask box.
 *
 * **This hook owns no loop.** It subscribes to `ticker.ts`, the page's single `requestAnimationFrame`,
 * and turns a timestamp into an elapsed count. Everything downstream of that is `timeline.ts`, which is
 * pure.
 */

import { useEffect, useMemo, useRef, useState } from "react";

import recording from "../fixtures/tour-techno-to-blues.sse?raw";
import { SseParser } from "../stream";
import type { StepState } from "../useLineageRun";
import { emptyStep } from "../useLineageRun";
import { onFrame } from "./ticker";
import { cuesFrom, durationOf, stateAt, TOKEN_MS, type Cue } from "./timeline";

/**
 * The query the recording answers, worded exactly as `SPEC.md` §1 words surface C.
 *
 * **Imperative on purpose, and re-captured to make it so — 2026-09-09.** The first capture used the
 * interrogative form because that is what was typed, which left the tour's own heading disagreeing with
 * the query its documentation advertises. `tour_v1.json` exists to defend the imperative phrasing, so
 * the showcase using the other one would have been the dataset guarding something the product did not do.
 */
export const TOUR_QUERY = "Take me from Detroit techno back to the blues.";

/**
 * Parsed once, at module scope.
 *
 * **Inlined at 5.5 KB rather than fetched, which is a deviation from the step 6 plan and is recorded as
 * one.** That plan assumed the recording would be big enough to belong in the `graph` byte class and be
 * fetched like the corpus. It is 5,539 bytes. Fetching it would cost a staging script, a loading state
 * and an error state to save five kilobytes against ~51 KB of script headroom, and it would introduce
 * the one thing DoD 5 forbids -- a request on load -- unless gated behind yet another `enabled` flag.
 * Inlining has neither problem: there is no request at all.
 */
const FRAMES = new SseParser().push(recording);

/**
 * The pace the tour is currently built at. Only ever `TOKEN_MS` in a build; see `replayTour` below.
 */
let pace = TOKEN_MS;
let CUES: Cue[] = cuesFrom(FRAMES, pace);

/** How long the whole tour takes, in milliseconds, at the pace it is currently built at. */
export const tourMs = (): number => durationOf(CUES, pace);

/** How long the whole tour takes at the shipped pace. */
export const TOUR_MS: number = durationOf(CUES, TOKEN_MS);

/**
 * **Dev-only, and it ships nothing.** `TOKEN_MS` is the tour's reading pace and it was derived rather
 * than looked at, which is the same state `ENTER_MS` was in before it was compared in the running app
 * against 420, 700 and 850. This is the equivalent handle for this number, and it follows that
 * precedent exactly: **no preview page and no shipped switch**, one function on `window` behind
 * `import.meta.env.DEV`, used from the devtools console on `make dev`.
 *
 *     replayTour(25); replayTour(45); replayTour(80)
 *
 * Vite's `DEV` is a compile-time constant, so this whole block is dropped from a production bundle by
 * dead-code elimination rather than merely going unused -- which is why it costs no bytes against the
 * script cap.
 */
if (import.meta.env.DEV) {
  (globalThis as unknown as { replayTour?: (ms: number) => string }).replayTour = (ms: number) => {
    pace = ms;
    CUES = cuesFrom(FRAMES, pace);
    globalThis.dispatchEvent(new CustomEvent("mycelium:tour-pace"));
    return `${ms}ms per token, tour is ${Math.round(tourMs() / 100) / 10}s`;
  };
}

/**
 * Replay the tour while `playing`, and report the state at the current moment.
 *
 * The returned `state` is the **only** state: the narration and the map are two readings of it, not two
 * things kept in step. See `timeline.ts` for why that distinction is the whole of DoD 2.
 */
export function useTour(playing: boolean): { state: StepState; elapsedMs: number; done: boolean } {
  const [elapsedMs, setElapsed] = useState(0);
  const [generation, setGeneration] = useState(0);
  const startedAt = useRef<number | null>(null);

  // Dev-only: `replayTour(ms)` rebuilds the cue list, and this restarts the tour so the new pace is
  // actually watched rather than merely set. No listener is attached in a production build.
  useEffect(() => {
    if (!import.meta.env.DEV) return;
    const restart = () => {
      startedAt.current = null;
      setElapsed(0);
      setGeneration((n) => n + 1);
    };
    globalThis.addEventListener("mycelium:tour-pace", restart);
    return () => {
      globalThis.removeEventListener("mycelium:tour-pace", restart);
    };
  }, []);

  useEffect(() => {
    if (!playing) {
      startedAt.current = null;
      setElapsed(0);
      return;
    }

    const off = onFrame((now: number) => {
      startedAt.current ??= now;
      const elapsed = now - startedAt.current;
      setElapsed(elapsed);
      // Unsubscribe from inside the tick once the last cue has played, which `ticker.ts` explicitly
      // supports and calls "how a finite animation ends". Leaving it subscribed would keep the page's
      // rAF loop alive for nothing.
      if (elapsed >= tourMs()) off();
    });

    return off;
  }, [playing, generation]);

  const state = useMemo(
    () => stateAt(CUES, elapsedMs, TOUR_QUERY),
    // `generation` is not unused: it is what makes a dev pace change rebuild the state off the new
    // cue list. `CUES` is module state, so nothing else in this dependency list can notice.
    [elapsedMs, generation],
  );

  return { state: playing ? state : emptyStep(TOUR_QUERY), elapsedMs, done: elapsedMs >= tourMs() };
}
