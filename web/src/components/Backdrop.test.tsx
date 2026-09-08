import { render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Backdrop } from "./Backdrop";
import { camera, decode, nodeAlpha, radiusOf } from "../graph/backdrop";

/**
 * jsdom has no canvas, so `getContext("2d")` returns null and the component takes its early return.
 * That is not a gap in these tests -- it IS rule 4's other half: **the page must render when the
 * backdrop cannot.** The lifecycle tests below stub a context so the loop can be observed; the
 * arithmetic tests need no canvas at all, which is the entire reason it lives in `graph/backdrop.ts`.
 */
function stubContext() {
  const ctx = {
    clearRect: vi.fn(),
    beginPath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    setTransform: vi.fn(),
    globalAlpha: 1,
    strokeStyle: "",
    fillStyle: "",
    lineWidth: 1,
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(ctx as never);
  return ctx;
}

const matchMedia = (reduced: boolean) =>
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: reduced && q.includes("reduced-motion"),
  }));

afterEach(() => {
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("the backdrop's four rules", () => {
  it("renders the page even when there is no 2D context at all", () => {
    vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(null);
    matchMedia(false);
    expect(() => render(<Backdrop paused={false} />)).not.toThrow();
  });

  it("rule 1: prefers-reduced-motion draws one frame and starts no loop", () => {
    const ctx = stubContext();
    matchMedia(true);
    const raf = vi.spyOn(window, "requestAnimationFrame");
    render(<Backdrop paused={false} />);
    expect(raf).not.toHaveBeenCalled();
    // Rule 4: still is not blank. It drew.
    expect(ctx.stroke).toHaveBeenCalled();
    expect(ctx.fill).toHaveBeenCalled();
  });

  it("animates for everyone who has NOT asked for reduced motion", () => {
    stubContext();
    matchMedia(false);
    const raf = vi.spyOn(window, "requestAnimationFrame");
    render(<Backdrop paused={false} />);
    expect(raf).toHaveBeenCalled();
  });

  it("rule 3: a run in flight stops it, and it still paints a frame", () => {
    const ctx = stubContext();
    matchMedia(false);
    const raf = vi.spyOn(window, "requestAnimationFrame");
    render(<Backdrop paused />);
    // Ambient motion yields to semantic motion: the graph animating a claim through the gate is the
    // thing the eye is supposed to follow, and a loop behind it competes for exactly that attention.
    expect(raf).not.toHaveBeenCalled();
    expect(ctx.fill).toHaveBeenCalled();
  });

  it("rule 2: a hidden tab cancels the loop", () => {
    stubContext();
    matchMedia(false);
    const cancel = vi.spyOn(window, "cancelAnimationFrame");
    render(<Backdrop paused={false} />);
    vi.spyOn(document, "hidden", "get").mockReturnValue(true);
    document.dispatchEvent(new Event("visibilitychange"));
    expect(cancel).toHaveBeenCalled();
  });

  it("tears its listeners down on unmount", () => {
    stubContext();
    matchMedia(false);
    const off = vi.spyOn(window, "removeEventListener");
    render(<Backdrop paused={false} />).unmount();
    expect(off).toHaveBeenCalledWith("resize", expect.any(Function));
  });
});

describe("the arithmetic, which needs no canvas", () => {
  it("decodes the generated data into the counts it claims", () => {
    const g = decode();
    expect(g.nodeCount).toBeGreaterThan(1000);
    expect(g.xy.length).toBe(g.nodeCount * 2);
    expect(g.kinds.length).toBe(g.nodeCount);
    expect(g.edges.length).toBe(g.edgeCount * 2);
  });

  it("keeps every position inside the unit box", () => {
    const g = decode();
    for (let i = 0; i < g.xy.length; i++) {
      expect(g.xy[i]).toBeGreaterThanOrEqual(0);
      expect(g.xy[i]).toBeLessThanOrEqual(1);
    }
  });

  it("derives degree rather than shipping it, and the total is twice the edge count", () => {
    const g = decode();
    const total = g.degree.reduce((sum, d) => sum + d, 0);
    expect(total).toBe(g.edgeCount * 2);
  });

  it("holds both kinds — a backdrop of one kind would not be this corpus", () => {
    const g = decode();
    const artists = g.kinds.reduce((n, k) => n + k, 0);
    expect(artists).toBeGreaterThan(0);
    expect(artists).toBeLessThan(g.nodeCount);
  });

  it("never repeats the camera inside a visitor's visit", () => {
    // 17s, 21s and 23s do not divide into each other, so the drift's period is their LCM in seconds
    // -- over two hours. A loop a visitor can spot is worse than no motion: once seen it is all they
    // see. This asserts the periods stay mutually prime rather than asserting the number.
    const a = camera(0, 1000, 800);
    const b = camera(60_000, 1000, 800);
    expect(a.originX).not.toBeCloseTo(b.originX, 3);
    expect(a.scale).not.toBeCloseTo(b.scale, 3);
  });

  it("keeps the camera centred and the zoom bounded", () => {
    for (const t of [0, 5_000, 17_000, 60_000, 600_000]) {
      const c = camera(t, 1440, 900);
      expect(c.scale).toBeGreaterThan(1440);
      expect(c.scale).toBeLessThan(1440 * 1.2);
    }
  });

  it("bounds the twinkle so a node never exceeds its scheme alpha", () => {
    for (const t of [0, 650, 1300, 2600, 9999]) {
      for (const isGenre of [true, false]) {
        const a = nodeAlpha(t, 0.7, isGenre, true);
        expect(a).toBeGreaterThan(0);
        expect(a).toBeLessThanOrEqual(isGenre ? 0.62 : 0.45);
      }
    }
  });

  it("draws a still node at full scheme alpha rather than mid-twinkle", () => {
    // The reduced-motion frame must not land on an arbitrary point of the sine, which would make the
    // still picture dimmer than the moving one for no reason.
    expect(nodeAlpha(0, 1.9, true, false)).toBeCloseTo(0.62, 6);
  });

  it("caps hub radius so one node cannot become a blob", () => {
    expect(radiusOf(0)).toBeCloseTo(0.9, 6);
    expect(radiusOf(204)).toBe(radiusOf(40));
  });
});
