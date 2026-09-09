/**
 * One `requestAnimationFrame` loop for the whole page. Phase 7 step 4.4, item 1.
 *
 * **Why this exists, and it is not a micro-optimization.** After step 3 the page ran two independent
 * rAF loops -- the backdrop's drift and `GraphView`'s claim animation -- and they were scheduled
 * against each other by the browser rather than against one budget. Two loops is also two places that
 * have to agree about when nothing should be painting, and §6's rule (*the backdrop yields the moment
 * a run starts streaming*) is exactly the kind of invariant that survives while it lives in one place
 * and rots once it lives in two.
 *
 * **The scope, stated so it stays small.** Subscribe, unsubscribe, one callback taking a timestamp,
 * and one rule about hidden tabs. **If this file ever grows priorities, ordering guarantees, or a
 * scheduler, step 4 has failed** -- that is written into the plan (§4.4) rather than left to taste,
 * because a frame scheduler is a thing that grows if nobody says out loud that it must not.
 *
 * **What it deliberately does NOT do:** decide whether a subscriber wants to animate. Reduced motion,
 * `paused`, and "this animation has finished" are all the subscriber's business -- it simply does not
 * subscribe, or it unsubscribes from inside its own tick. The ticker has no opinion about motion; it
 * only owns the loop.
 */

/** One frame's worth of work. `now` is the `requestAnimationFrame` timestamp, unmodified. */
export type Tick = (now: number) => void;

const subscribers = new Set<Tick>();

/**
 * The in-flight frame id, or 0 for "not running".
 *
 * 0 is safe as the sentinel because `requestAnimationFrame` ids start at 1 in every browser and in
 * jsdom. Using `null` would read better and would cost a wider type on a hot path for nothing.
 */
let frame = 0;

/** Frames are pointless in a hidden tab, and browsers throttle them there anyway. */
const hidden = (): boolean => typeof document !== "undefined" && document.hidden;

function pump(now: number): void {
  frame = 0;

  // Iterate a copy. A subscriber is allowed to unsubscribe from inside its own tick -- that is how a
  // finite animation ends, and it is what `GraphView` does when `frame.done` -- and deleting from a
  // Set while iterating it would silently skip whichever subscriber came next.
  for (const tick of [...subscribers]) tick(now);

  start();
}

function start(): void {
  if (frame !== 0 || subscribers.size === 0 || hidden()) return;
  // Looked up on `window` at call time rather than captured at module load, so a test that stubs or
  // spies on rAF is actually observing this loop. Capturing the reference is how a shared ticker
  // becomes invisible to the suite that is supposed to cover it.
  frame = window.requestAnimationFrame(pump);
}

function stop(): void {
  if (frame === 0) return;
  window.cancelAnimationFrame(frame);
  frame = 0;
}

/**
 * Run `tick` once per frame until the returned function is called.
 *
 * Calling the returned function twice is harmless, which matters because React effect cleanups and a
 * self-unsubscribing animation both routinely call it for the same subscription.
 */
export function onFrame(tick: Tick): () => void {
  subscribers.add(tick);
  start();
  return () => {
    subscribers.delete(tick);
    if (subscribers.size === 0) stop();
  };
}

/** How many subscribers are attached. For tests and for nothing else. */
export const frameSubscribers = (): number => subscribers.size;

/** True while a frame is actually scheduled. For tests and for nothing else. */
export const frameRunning = (): boolean => frame !== 0;

/**
 * The hidden-tab rule, owned here rather than by each canvas.
 *
 * Registered at module scope on purpose. A listener attached on first subscribe and removed on last
 * is more lifecycle to get wrong than it is worth, and with no subscribers the handler does nothing:
 * `start` returns immediately on an empty set.
 */
if (typeof document !== "undefined") {
  document.addEventListener("visibilitychange", () => {
    if (hidden()) stop();
    else start();
  });
}
