import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ChipRow } from "../components/ChipRow";
import {
  ENTER_MS,
  STAGGER_MAX_STEPS,
  STAGGER_MS,
  STREAMED_DELAY,
  enterDelay,
  staggerDelay,
} from "./motion";

/**
 * The DOM motion system, phase 7 step 4.
 *
 * **What can and cannot be checked here, stated once.** jsdom has no CSS engine and no Web Animations
 * API -- `element.animate`, `getAnimations` and `CSS.supports` are all `undefined`, measured
 * 2026-09-09 -- so nothing in this repo can observe an animation running, and a test that claimed to
 * would be asserting its own stub. What IS checkable is the half the arithmetic owns: the delay each
 * element is given, and that the element actually carries it. Assert the number, never the pixel.
 *
 * That is why the delays live in `motion.ts` as pure functions rather than inside a component or
 * inside a library. It is the same argument that put `frameAt` there in phase 5.
 */

afterEach(cleanup);

describe("the stagger arithmetic", () => {
  it("puts the first item at zero and each next one a step later", () => {
    expect(staggerDelay(0)).toBe(0);
    expect(staggerDelay(1)).toBe(STAGGER_MS);
    expect(staggerDelay(3)).toBe(3 * STAGGER_MS);
  });

  it("caps the wait so a long list never becomes a queue", () => {
    // The one number here that is not a taste decision. Without the cap a 30-claim answer would put
    // its last row two seconds behind its first, and a visitor reading downward would arrive at a
    // blank space and wait.
    expect(staggerDelay(STAGGER_MAX_STEPS)).toBe(STAGGER_MAX_STEPS * STAGGER_MS);
    expect(staggerDelay(STAGGER_MAX_STEPS + 1)).toBe(STAGGER_MAX_STEPS * STAGGER_MS);
    expect(staggerDelay(500)).toBe(STAGGER_MAX_STEPS * STAGGER_MS);
  });

  it("clamps below zero rather than pulling an element in early", () => {
    expect(staggerDelay(-1)).toBe(0);
    expect(staggerDelay(-99)).toBe(0);
  });

  it("floors a fractional index instead of producing a fractional delay", () => {
    expect(staggerDelay(2.7)).toBe(2 * STAGGER_MS);
  });

  it("hands the delay over as the custom property CSS reads", () => {
    expect(enterDelay(2)).toEqual({ "--enter-delay": `${2 * STAGGER_MS}ms` });
  });

  it("gives a streamed arrival no invented delay at all", () => {
    // Claims arrive seconds apart as the gate approves them. They are already staggered, by the
    // stream, with the real timing of the real work.
    expect(STREAMED_DELAY).toEqual({ "--enter-delay": "0ms" });
  });

  it("keeps the entrance shorter than a claim edge draws itself in", () => {
    // Chrome must not compete with content. `EDGE_MS` is 850 and is the thing the eye should follow;
    // an entrance that lasts as long is a second thing asking for the same attention.
    expect(ENTER_MS).toBeLessThan(850);
  });
});

describe("the elements that carry it", () => {
  it("gives every chip its own delay, in order", () => {
    render(<ChipRow disabled={false} activeId={null} onPick={() => {}} />);
    const chips = screen.getAllByRole("button");
    expect(chips.length).toBeGreaterThan(1);

    chips.forEach((chip, index) => {
      expect(chip.className).toContain("enter");
      expect(chip.style.getPropertyValue("--enter-delay")).toBe(`${staggerDelay(index)}ms`);
    });
  });
});

describe("the reduced-motion rule, read from the stylesheet", () => {
  /**
   * **A text assertion, and it is here deliberately rather than as a shortcut.** jsdom applies no
   * CSS, so the only alternative to reading the file is not checking this at all -- and what it
   * guards is a real regression with an invisible failure mode.
   *
   * `.enter` uses `both` fill, which holds the `from` keyframe -- fully transparent -- for the whole
   * of the delay. Zeroing only `animation-duration`, which is what this block did until 2026-09-09,
   * leaves a visitor who asked for reduced motion watching chips blink into existence one after
   * another over half a second: more distracting than the animation they turned off, and reachable
   * only by someone who has set the preference.
   */
  const css = readFileSync(resolve(process.cwd(), "src/styles.css"), "utf8");
  const block = css.slice(css.indexOf("@media (prefers-reduced-motion: reduce)"));

  it("zeroes delay as well as duration", () => {
    expect(block).toContain("animation-duration: 0.01ms !important");
    expect(block).toContain("animation-delay: 0ms !important");
    expect(block).toContain("transition-duration: 0.01ms !important");
    expect(block).toContain("transition-delay: 0ms !important");
  });

  it("animates only compositor-friendly properties", () => {
    // The step 4 discipline: `transform` and `opacity` composite off the main thread, and nothing
    // else does. A keyframe that animated `width`, `top`, `filter` or `box-shadow` would be jank
    // regardless of what drew it.
    const keyframes = css.slice(css.indexOf("@keyframes enter"), css.indexOf(".enter {"));
    for (const banned of [
      "width:",
      "height:",
      "top:",
      "left:",
      "filter:",
      "box-shadow:",
      "margin",
    ]) {
      expect(keyframes).not.toContain(banned);
    }
    expect(keyframes).toContain("opacity");
    expect(keyframes).toContain("transform");
  });
});
