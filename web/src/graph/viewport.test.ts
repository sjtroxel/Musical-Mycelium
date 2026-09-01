import { describe, expect, it } from "vitest";
import type { View } from "./motion";
import {
  CLICK_SLOP,
  EDGE_INSET,
  HIT_SLOP,
  MAX_K,
  MIN_K,
  clampScale,
  clampView,
  hitTest,
  panBy,
  project,
  projectedBounds,
  unproject,
  wheelFactor,
  zoomAbout,
} from "./viewport";

/**
 * The camera's arithmetic, tested where it can actually be reached.
 *
 * Step 7's lesson written down as a practice: the two defects that shipped to a browser and were
 * caught by hand lived inside the draw closure, where the twelve tests that passed could not see
 * them. Everything here is a pure function for that reason, and these tests assert the properties
 * that make the camera feel right — an anchor that stays under the cursor, a drag that tracks the
 * pointer — rather than re-stating the formulas.
 */

const WIDTH = 640;

/** A camera roughly like the one measured on the acid jazz chip mid-answer. */
const view: View = { k: 0.945, cx: 320, cy: 0, originX: 300, height: 260 };

describe("project and unproject", () => {
  it("are exact inverses", () => {
    for (const point of [
      { x: 0, y: 0 },
      { x: 960, y: -240 },
      { x: -160, y: 132 },
      { x: 17.5, y: -3.25 },
    ]) {
      const back = unproject(view, project(view, point));
      expect(back.x).toBeCloseTo(point.x, 9);
      expect(back.y).toBeCloseTo(point.y, 9);
    }
  });

  it("puts the camera centre at the canvas centre", () => {
    const centre = project(view, { x: view.cx, y: view.cy });
    expect(centre.x).toBeCloseTo(view.originX, 9);
    expect(centre.y).toBeCloseTo(view.height / 2, 9);
  });
});

describe("panBy", () => {
  it("moves content by exactly the pixel delta it is given, at any zoom", () => {
    // The property that makes a drag track the pointer. If the division by k is dropped, this holds
    // at k=1 and nowhere else — which is why the assertion sweeps scales rather than using one.
    for (const k of [0.1, 0.945, 2.2, 7]) {
      const at = { ...view, k };
      const before = project(at, { x: 480, y: 60 });
      const after = project(panBy(at, 37, -12), { x: 480, y: 60 });
      expect(after.x - before.x).toBeCloseTo(37, 9);
      expect(after.y - before.y).toBeCloseTo(-12, 9);
    }
  });

  it("does not change the scale", () => {
    expect(panBy(view, 100, 100).k).toBe(view.k);
  });
});

describe("zoomAbout", () => {
  it("keeps the graph point under the cursor under the cursor", () => {
    const cursor = { x: 512, y: 71 };
    for (const factor of [1.35, 1 / 1.35, 4, 0.25]) {
      const zoomed = zoomAbout(view, cursor, factor);
      const anchorBefore = unproject(view, cursor);
      const anchorAfter = unproject(zoomed, cursor);
      expect(anchorAfter.x).toBeCloseTo(anchorBefore.x, 6);
      expect(anchorAfter.y).toBeCloseTo(anchorBefore.y, 6);
    }
  });

  it("actually changes the scale by the factor", () => {
    expect(zoomAbout(view, { x: 300, y: 130 }, 2).k).toBeCloseTo(view.k * 2, 9);
  });

  it("is exactly the identity at factor 1", () => {
    expect(zoomAbout(view, { x: 400, y: 40 }, 1)).toEqual(view);
  });

  it("refuses to zoom past the bounds, and returns the view unchanged when it does", () => {
    const wayIn = zoomAbout(view, { x: 300, y: 130 }, 1e6);
    expect(wayIn.k).toBe(MAX_K);

    // Already at the ceiling: a further zoom-in is a no-op rather than a camera that drifts while
    // the scale stays put. Drifting on a refused zoom is the bug this asserts against.
    const further = zoomAbout(wayIn, { x: 10, y: 10 }, 2);
    expect(further).toEqual(wayIn);

    expect(zoomAbout(view, { x: 300, y: 130 }, 1e-6).k).toBe(MIN_K);
  });
});

describe("clampScale", () => {
  it("bounds on both sides and leaves the middle alone", () => {
    expect(clampScale(1e9)).toBe(MAX_K);
    expect(clampScale(0)).toBe(MIN_K);
    expect(clampScale(-5)).toBe(MIN_K);
    expect(clampScale(1.5)).toBe(1.5);
  });
});

describe("clampView", () => {
  const points = [
    { x: 0, y: -88 },
    { x: 160, y: 0 },
    { x: 320, y: 88 },
  ];

  /** Where the middle of the drawn content lands on screen. */
  const centreOf = (v: View, p: readonly { x: number; y: number }[]) => {
    const bounds = projectedBounds(v, p);
    if (bounds === null) throw new Error("no bounds");
    return { x: (bounds.minX + bounds.maxX) / 2, y: (bounds.minY + bounds.maxY) / 2 };
  };

  it("leaves a centred map alone", () => {
    expect(clampView(view, points, WIDTH)).toEqual(view);
  });

  it("parks the content's centre exactly on the inset, whichever edge it went off", () => {
    // An equality, not an inequality. The previous version of this test asserted a minimum overlap
    // and passed with the rule it was guarding deleted — see EDGE_INSET's docstring. Asserting the
    // exact resting place is what makes the assertion able to fail.
    // The axis that was not pushed must not move at all, so its expectation is the centre this map
    // already had. Writing `view.originX` there instead is wrong and was the first draft's mistake:
    // `originX` is where the CAMERA centre lands, and the content is not centred on the camera.
    const rest = centreOf(view, points);
    const cases: [number, number, number, number][] = [
      [5000, 0, WIDTH - EDGE_INSET, rest.y],
      [-5000, 0, EDGE_INSET, rest.y],
      [0, 5000, rest.x, view.height - EDGE_INSET],
      [0, -5000, rest.x, EDGE_INSET],
      [4000, -4000, WIDTH - EDGE_INSET, EDGE_INSET],
    ];

    for (const [dx, dy, wantX, wantY] of cases) {
      const centre = centreOf(clampView(panBy(view, dx, dy), points, WIDTH), points);
      expect(centre.x).toBeCloseTo(wantX, 6);
      expect(centre.y).toBeCloseTo(wantY, 6);
    }
  });

  it("keeps a single node on screen, not parked on the edge", () => {
    // A one-node map projects to a zero-size box, which is the degenerate case the rule has to
    // survive. It is also a real one: the headline chip's whole component is three nodes.
    const single = [{ x: 0, y: 0 }];
    const clamped = clampView(panBy(view, 9000, 9000), single, WIDTH);
    const centre = centreOf(clamped, single);
    expect(centre.x).toBeCloseTo(WIDTH - EDGE_INSET, 6);
    expect(centre.y).toBeCloseTo(clamped.height - EDGE_INSET, 6);
  });

  it("collapses to the middle on a canvas too small to hold two insets", () => {
    // A 20px canvas cannot have a 48px inset at both ends. Without the cap at half the extent the
    // clamp range inverts, and an inverted range silently returns whichever bound was applied last.
    const narrow: View = { ...view, height: 20 };
    const clamped = clampView(panBy(narrow, 800, 800), points, 20);
    const centre = centreOf(clamped, points);
    expect(centre.x).toBeCloseTo(10, 6);
    expect(centre.y).toBeCloseTo(10, 6);
  });

  it("has nothing to say about an empty map", () => {
    expect(clampView(view, [], WIDTH)).toEqual(view);
    expect(projectedBounds(view, [])).toBeNull();
  });
});

describe("hitTest", () => {
  // Named rather than indexed: `noUncheckedIndexedAccess` is on, and a test that has to placate the
  // type checker at every use reads worse than one that names its fixtures.
  const walked = { id: "Q1", x: 0, y: 0, radius: 6 };
  const context = { id: "Q2", x: 160, y: 0, radius: 3.5 };
  const below = { id: "Q3", x: 160, y: 44, radius: 3.5 };
  const candidates = [walked, context, below];

  it("finds the node under the point", () => {
    const at = project(view, context);
    expect(hitTest(view, candidates, at)).toBe("Q2");
  });

  it("returns null on empty canvas and for an empty candidate list", () => {
    expect(hitTest(view, candidates, { x: 5, y: 5 })).toBeNull();
    expect(hitTest(view, [], project(view, walked))).toBeNull();
  });

  it("gives a small dot a clickable target", () => {
    // A context node is drawn at radius 3.5. Without the slop this misses, and a map whose faint
    // nodes cannot be clicked has no follow-an-edge at all.
    const at = project(view, context);
    expect(hitTest(view, candidates, { x: at.x + 3.5 + HIT_SLOP - 1, y: at.y })).toBe("Q2");
    expect(hitTest(view, candidates, { x: at.x + 3.5 + HIT_SLOP + 2, y: at.y })).toBeNull();
  });

  it("keeps the target the same size on screen as the map zooms out", () => {
    // The slop is added in screen space on purpose: layout-space slop shrinks exactly when the dots
    // are hardest to hit. At k=0.15 two nodes 160 units apart are 24px apart, and the target must
    // still be reachable.
    const far: View = { ...view, k: 0.15 };
    const at = project(far, context);
    expect(hitTest(far, candidates, { x: at.x + 6, y: at.y })).toBe("Q2");
  });

  it("returns the nearest node, not the first one that matches", () => {
    // Overlapping targets are normal: `layout.ts` puts a whole column at one x, so at low zoom a
    // busy column's dots are a few pixels apart. First-wins would return whichever happened to be
    // earlier in the array.
    const tight: View = { ...view, k: 0.1 };
    const q2 = project(tight, context);
    const q3 = project(tight, below);
    expect(Math.abs(q3.y - q2.y)).toBeLessThan(HIT_SLOP * 2);
    expect(hitTest(tight, candidates, { x: q3.x, y: q3.y })).toBe("Q3");
    expect(hitTest(tight, candidates, { x: q2.x, y: q2.y })).toBe("Q2");
  });
});

describe("wheelFactor", () => {
  it("zooms in when the wheel scrolls up and out when it scrolls down", () => {
    // deltaY is negative scrolling up, which is the direction every map application zooms in on.
    expect(wheelFactor(-100)).toBeGreaterThan(1);
    expect(wheelFactor(100)).toBeLessThan(1);
    expect(wheelFactor(0)).toBe(1);
  });

  it("is multiplicative, so a trackpad's many small deltas equal one big one", () => {
    // Ten 10px nudges and one 100px notch must land on the same scale, or a trackpad and a mouse
    // zoom at wildly different rates.
    const nudges = Array.from({ length: 10 }, () => wheelFactor(-10)).reduce((a, b) => a * b, 1);
    expect(nudges).toBeCloseTo(wheelFactor(-100), 9);
  });

  it("is symmetric, so scrolling back returns to the same scale", () => {
    expect(wheelFactor(-120) * wheelFactor(120)).toBeCloseTo(1, 9);
  });
});

describe("the click threshold", () => {
  it("is small enough to be a click and not zero", () => {
    // Zero would make every pan that begins on a node also select it, since a drag ends with the
    // pointer up over wherever it started.
    expect(CLICK_SLOP).toBeGreaterThan(0);
    expect(CLICK_SLOP).toBeLessThan(HIT_SLOP);
  });
});
