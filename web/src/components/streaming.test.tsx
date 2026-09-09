import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { StepPanel } from "./StepPanel";
import type { StepState } from "../useLineageRun";
import type { Artifact } from "../graph/staticGraph";
import { indexArtifact, resetStaticGraphCache } from "../graph/staticGraph";

/**
 * Phase 7 step 4.4, item 2: **a prose token must not redraw the canvas.**
 *
 * This is a performance property and it is tested rather than measured because the failure is
 * invisible. Every token of every answer re-renders `App` and through it every `StepPanel`; before
 * this step that rebuilt the whole `RenderGraph` and re-ran `GraphView`'s effect -- layout, camera
 * fit, and one full draw over every node and edge -- tens of times a second, to render text that is
 * not on the canvas. Nothing looked wrong. It was simply paying for the picture on every character.
 *
 * `graphSignature` already stopped the *animation* restarting on those renders (`motion.ts`), which
 * is why this was easy to believe was already handled. Restarting an animation and re-running a
 * render are different costs and only one of them was covered.
 *
 * **Draws are counted by `clearRect`**, which starts every frame, and the second test is the control:
 * a change that genuinely alters the picture must still redraw it, or this file would pass against a
 * component that draws nothing at all.
 */

const ARTIFACT: Artifact = {
  nodes: [
    ["Q221772", "acid jazz"],
    ["Q11401", "hip-hop"],
    ["Q8341", "jazz"],
  ].map(([id, label]) => ({
    id: id as string,
    label: label as string,
    kind: "genre",
    inception_year: null,
    inception_precision: null,
    countries: [],
    source: "wikidata",
    source_id: id as string,
    retrieved_at: "2026-08-05T00:00:00+00:00",
    revision_id: null,
  })),
  edges: [
    ["Q221772", "Q11401"],
    ["Q221772", "Q8341"],
  ].map(([subject, object]) => ({
    subject_id: subject as string,
    object_id: object as string,
    predicate: "influenced_by",
    verification: "HAND" as const,
    prose_tier: "PROSE",
    source: "wikidata",
    source_id: `http://www.wikidata.org/entity/statement/${subject}-x`,
    retrieved_at: "2026-08-05T00:00:00+00:00",
  })),
};

function step(overrides: Partial<StepState> = {}): StepState {
  return {
    query: "Where did acid jazz come from?",
    phase: "running",
    outcome: "answer",
    prose: "",
    claims: [],
    rejectionCount: 0,
    path: null,
    toolNodeIds: ["Q221772"],
    refusal: null,
    contested: [],
    done: null,
    error: null,
    ...overrides,
  };
}

/**
 * Counts frames. Scoped to the map's own canvas by way of there being only one here -- and the step 3
 * lesson about `querySelector("canvas")` silently asserting a page holds one canvas is why that is
 * said out loud rather than assumed.
 */
function countingContext() {
  const ctx = {
    clearRect: vi.fn(),
    save: vi.fn(),
    restore: vi.fn(),
    beginPath: vi.fn(),
    closePath: vi.fn(),
    moveTo: vi.fn(),
    lineTo: vi.fn(),
    quadraticCurveTo: vi.fn(),
    bezierCurveTo: vi.fn(),
    stroke: vi.fn(),
    arc: vi.fn(),
    fill: vi.fn(),
    fillText: vi.fn(),
    strokeText: vi.fn(),
    measureText: vi.fn(() => ({ width: 10 })),
    setTransform: vi.fn(),
    setLineDash: vi.fn(),
    translate: vi.fn(),
    scale: vi.fn(),
    globalAlpha: 1,
    strokeStyle: "",
    fillStyle: "",
    lineWidth: 1,
    font: "",
    textAlign: "left",
    textBaseline: "middle",
  };
  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(ctx as never);
  return ctx;
}

/** Reduced motion, so a draw is one draw and the count is not a race against a loop. */
function stillMap() {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("prefers-reduced-motion"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
  resetStaticGraphCache();
});

describe("streaming prose and the canvas", () => {
  it("does not redraw the map when only the prose grew", () => {
    stillMap();
    const ctx = countingContext();
    const graph = indexArtifact("0.5.0", ARTIFACT);
    const first = step();

    const { rerender } = render(<StepPanel step={first} graph={graph} />);
    const drawnOnMount = ctx.clearRect.mock.calls.length;
    expect(drawnOnMount).toBeGreaterThan(0);

    // Exactly what `useLineageRun` does on a `token` frame: spread the step, append to `prose`. Every
    // other field keeps its identity, which is what the memo in `StepPanel` depends on.
    for (const text of ["Acid ", "jazz ", "came ", "out ", "of ", "several ", "things."]) {
      rerender(<StepPanel step={{ ...first, prose: first.prose + text }} graph={graph} />);
    }

    expect(ctx.clearRect.mock.calls.length).toBe(drawnOnMount);
  });

  it("still redraws when the picture itself changes — the control", () => {
    stillMap();
    const ctx = countingContext();
    const graph = indexArtifact("0.5.0", ARTIFACT);
    const first = step();

    const { rerender } = render(<StepPanel step={first} graph={graph} />);
    const drawnOnMount = ctx.clearRect.mock.calls.length;

    // A claim landing is a new picture: the gate approved an edge and the map has to show it.
    rerender(
      <StepPanel
        step={{
          ...first,
          claims: [
            {
              subject_id: "Q221772",
              predicate: "influenced_by",
              object_id: "Q8341",
              source_ids: ["http://www.wikidata.org/entity/statement/Q221772-x"],
              span: null,
            } as unknown as StepState["claims"][number],
          ],
        }}
        graph={graph}
      />,
    );

    expect(ctx.clearRect.mock.calls.length).toBeGreaterThan(drawnOnMount);
  });
});
