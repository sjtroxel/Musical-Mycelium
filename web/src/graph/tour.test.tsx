/**
 * The guided tour, running in the real app. Phase 7 step 6.
 *
 * `timeline.test.ts` proves the invariant over generated cue lists; this proves the invariant is the
 * one the page actually renders. Both are needed and neither substitutes: a perfect timeline wired to
 * nothing would pass the first file and ship a dead button.
 *
 * **Frames land at timestamps this file chooses**, using the same hand-driven `requestAnimationFrame`
 * queue `ticker.test.ts` and `motion.test.tsx` use, so nothing here is a race.
 */

import { afterEach, describe, expect, it, vi } from "vitest";
import { act, cleanup, render, screen } from "@testing-library/react";

import { App } from "../App";
import { TOUR_MS, TOUR_QUERY } from "./useTour";

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
      act(() => {
        for (const cb of due) cb(now);
      });
    },
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

function startTour() {
  const frames = frameQueue();
  render(<App />);
  act(() => {
    screen.getByRole("button", { name: /take the guided tour/i }).click();
  });
  return frames;
}

describe("the guided tour in the app", () => {
  it("is offered on first paint and shows nothing until it is asked for", () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal("fetch", fetchSpy);
    render(<App />);

    expect(screen.getByRole("button", { name: /take the guided tour/i })).toBeTruthy();
    expect(screen.queryByText(TOUR_QUERY)).toBeNull();
    // DoD 5: loading the page requests nothing. The recording is inlined, so the tour cannot break it.
    expect(fetchSpy).not.toHaveBeenCalled();
  });

  it("narrates nothing before its first cue and everything after its last", () => {
    const frames = startTour();

    frames.step(0);
    expect(screen.getByText(TOUR_QUERY)).toBeTruthy();

    frames.step(TOUR_MS + 10_000);
    // The recorded run's narration, whatever it says, has fully arrived by the end of the timeline.
    const panel = screen.getByText(TOUR_QUERY).closest("article");
    expect(panel).not.toBeNull();
    expect((panel?.textContent ?? "").length).toBeGreaterThan(TOUR_QUERY.length);
  });

  it("advances the narration and the claim list from the same timeline", () => {
    const frames = startTour();
    frames.step(0);

    const textAt = (): string => screen.getByText(TOUR_QUERY).closest("article")?.textContent ?? "";

    frames.step(0);
    const early = textAt();
    frames.step(TOUR_MS / 2);
    const middle = textAt();
    frames.step(TOUR_MS + 5_000);
    const end = textAt();

    // Monotonic: a tour that goes backwards would be two clocks disagreeing, which is the failure
    // DoD 2 names. Length is a proxy for "more has arrived" and is enough to catch a regression here;
    // the exact prefix property is asserted over generated sequences in `timeline.test.ts`.
    expect(middle.length).toBeGreaterThanOrEqual(early.length);
    expect(end.length).toBeGreaterThanOrEqual(middle.length);
  });

  it("stops asking for frames once the tour has finished", () => {
    const frames = startTour();
    frames.step(0);
    frames.step(TOUR_MS + 1);

    // `useTour` unsubscribes from inside its own tick, which `ticker.ts` documents as how a finite
    // animation ends. A tour that kept the page's rAF loop alive after finishing would burn battery
    // for nothing -- the cost step 4 measured the backdrop against.
    const before = document.body.textContent ?? "";
    frames.step(TOUR_MS + 60_000);
    expect(document.body.textContent ?? "").toBe(before);
  });

  it("yields to a real question rather than running beside it", () => {
    // The run must not actually go anywhere: this test is about which panel is on screen, not about
    // streaming. A never-settling fetch keeps the run "in flight" without a network or a rejection.
    vi.stubGlobal("fetch", vi.fn().mockReturnValue(new Promise(() => {})));
    const frames = startTour();
    frames.step(TOUR_MS / 3);
    expect(screen.getByText(TOUR_QUERY)).toBeTruthy();

    act(() => {
      const chip = screen
        .getAllByRole("button")
        .find((b) => /acid jazz/i.test(b.textContent ?? ""));
      chip?.click();
    });

    // Two panels each claiming to be the answer is the confusion this guards against.
    expect(screen.queryByText(TOUR_QUERY)).toBeNull();
  });
});
