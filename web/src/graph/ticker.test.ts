import { afterEach, describe, expect, it, vi } from "vitest";
import { frameRunning, frameSubscribers, onFrame } from "./ticker";

/**
 * `requestAnimationFrame` under manual control, the same shape `motion.test.tsx` uses. Frames land at
 * timestamps a test chooses, so nothing here is a race.
 */
function frameQueue() {
  let pending: FrameRequestCallback[] = [];
  let requests = 0;
  vi.stubGlobal("requestAnimationFrame", (cb: FrameRequestCallback) => {
    pending.push(cb);
    requests += 1;
    return requests;
  });
  vi.stubGlobal("cancelAnimationFrame", () => {
    pending = [];
  });
  return {
    step(now: number) {
      const due = pending;
      pending = [];
      for (const cb of due) cb(now);
    },
    get waiting() {
      return pending.length;
    },
    get requests() {
      return requests;
    },
  };
}

/**
 * The ticker is a module singleton, which is the point of it and also the one thing that could leak
 * between tests. Every subscription taken out below is handed here and released afterwards, so a
 * forgotten unsubscribe fails the next test rather than the one that caused it.
 */
const open: (() => void)[] = [];
const track = (off: () => void) => {
  open.push(off);
  return off;
};

afterEach(() => {
  for (const off of open.splice(0)) off();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

describe("the shared frame ticker", () => {
  it("runs ONE loop no matter how many subscribers there are", () => {
    const q = frameQueue();
    const a = vi.fn();
    const b = vi.fn();
    track(onFrame(a));
    track(onFrame(b));

    // Two subscribers, one outstanding rAF request. This is the whole reason the file exists: before
    // it, two canvases meant two loops scheduled against each other rather than against one budget.
    expect(q.waiting).toBe(1);
    expect(frameSubscribers()).toBe(2);

    q.step(16);
    expect(a).toHaveBeenCalledWith(16);
    expect(b).toHaveBeenCalledWith(16);
    expect(q.waiting).toBe(1);
  });

  it("keeps ticking the others when one unsubscribes from inside its own tick", () => {
    // The copy-on-iterate rule, and it is not hypothetical: a finite animation ends exactly this way,
    // and deleting from a Set mid-iteration would silently skip whichever subscriber came next.
    const q = frameQueue();
    const after = vi.fn();
    const off = onFrame(() => off());
    track(off);
    track(onFrame(after));

    q.step(16);
    expect(after).toHaveBeenCalledTimes(1);
    expect(frameSubscribers()).toBe(1);

    q.step(32);
    expect(after).toHaveBeenCalledTimes(2);
  });

  it("stops the loop when the last subscriber leaves, and starts nothing before the first arrives", () => {
    const q = frameQueue();
    expect(frameRunning()).toBe(false);
    expect(q.requests).toBe(0);

    const off = onFrame(vi.fn());
    expect(frameRunning()).toBe(true);

    off();
    expect(frameRunning()).toBe(false);
    expect(frameSubscribers()).toBe(0);
  });

  it("tolerates the same unsubscribe being called twice", () => {
    // Not defensive coding for its own sake. A React effect cleanup and a self-ending animation both
    // routinely release the same subscription.
    frameQueue();
    const off = onFrame(vi.fn());
    off();
    expect(() => off()).not.toThrow();
    expect(frameSubscribers()).toBe(0);
  });

  it("stops in a hidden tab and starts again when the tab comes back", () => {
    const q = frameQueue();
    const tick = vi.fn();
    track(onFrame(tick));
    expect(frameRunning()).toBe(true);

    const visibility = vi.spyOn(document, "hidden", "get").mockReturnValue(true);
    document.dispatchEvent(new Event("visibilitychange"));
    expect(frameRunning()).toBe(false);

    // And it does not quietly restart itself on the next pump either.
    q.step(16);
    expect(tick).not.toHaveBeenCalled();

    visibility.mockReturnValue(false);
    document.dispatchEvent(new Event("visibilitychange"));
    expect(frameRunning()).toBe(true);
    q.step(32);
    expect(tick).toHaveBeenCalledWith(32);
  });

  it("hands every subscriber the same timestamp within one frame", () => {
    // Two consumers reading one clock. Step 6's timeline rests on this being true of the loop rather
    // than on two loops happening to agree.
    const q = frameQueue();
    const seen: number[] = [];
    track(onFrame((t) => seen.push(t)));
    track(onFrame((t) => seen.push(t)));

    q.step(1234.5);
    expect(seen).toEqual([1234.5, 1234.5]);
  });
});
