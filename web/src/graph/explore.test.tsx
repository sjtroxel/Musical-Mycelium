import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import type { Artifact } from "./staticGraph";
import { resetStaticGraphCache } from "./staticGraph";

/**
 * Step 8a's interactions, exercised through the **real app** rather than through `GraphView` alone.
 *
 * This file exists because of step 7. Twelve tests passed while two real defects shipped to a
 * browser, and both were invisible for the same reason: the tests rendered `GraphView` bare and the
 * app never does — it mounts inside `StrictMode`, inside `StepPanel`, with a stream arriving. So the
 * camera work gets a test that clicks a chip on the actual first screen.
 *
 * **The canvas stub is what makes that possible.** jsdom has no 2D context, so `getContext` returns
 * null, `GraphView`'s effect returns early, and every handler here would no-op — a test suite that
 * passes because nothing ran. The stub is a recording context: it answers `getContext`, no-ops the
 * drawing calls, and keeps every `arc` centre. Since every node, badge and ring on this map is an
 * arc, recording them is enough to assert **where the map actually drew things**, which is the only
 * assertion that proves a pointer event reached the pixels.
 *
 * It is deliberately local to this file. `map.test.tsx` documents that it runs without a context and
 * asserts the structure around the pixels; installing a global stub would silently change what that
 * file is testing.
 */

interface Arc {
  x: number;
  y: number;
  r: number;
}

function installCanvas(): { arcs: Arc[]; clear: () => void } {
  const arcs: Arc[] = [];

  const context = {
    save: () => {},
    restore: () => {},
    setTransform: () => {},
    clearRect: () => {},
    beginPath: () => {},
    closePath: () => {},
    moveTo: () => {},
    lineTo: () => {},
    stroke: () => {},
    fill: () => {},
    fillText: () => {},
    strokeText: () => {},
    arc: (x: number, y: number, r: number) => arcs.push({ x, y, r }),
    // Label width drives the right-hand padding in `viewFor`. A fixed per-character estimate keeps
    // the projection deterministic across machines, which a real font would not.
    measureText: (text: string) => ({ width: text.length * 6 }),
    font: "",
    textAlign: "left",
    textBaseline: "alphabetic",
    globalAlpha: 1,
    lineWidth: 1,
    fillStyle: "",
    strokeStyle: "",
  };

  vi.spyOn(HTMLCanvasElement.prototype, "getContext").mockReturnValue(
    context as unknown as CanvasRenderingContext2D,
  );

  // jsdom implements none of the pointer-capture API, and `GraphView` calls all three. Without these
  // the first pointerdown throws and every assertion below fails for the wrong reason.
  HTMLCanvasElement.prototype.setPointerCapture = () => {};
  HTMLCanvasElement.prototype.releasePointerCapture = () => {};
  HTMLCanvasElement.prototype.hasPointerCapture = () => true;

  return { arcs, clear: () => arcs.splice(0, arcs.length) };
}

/**
 * Reduced motion, so the map draws once and settles instead of running an animation loop.
 *
 * Not a convenience. `requestAnimationFrame` in a test environment makes the number of draws a race,
 * and these assertions compare one draw against the next. DoD 6's `none` mode is a real, shipped code
 * path, so this is testing something the product does rather than a test-only shortcut.
 */
function stubReducedMotion(): void {
  vi.stubGlobal("matchMedia", (query: string) => ({
    matches: query.includes("prefers-reduced-motion"),
    media: query,
    addEventListener: () => {},
    removeEventListener: () => {},
  }));
}

const ARTIFACT: Artifact = {
  nodes: [
    ["Q221772", "acid jazz"],
    ["Q11401", "hip-hop"],
    ["Q131272", "soul"],
    ["Q164444", "funk"],
    ["Q8341", "jazz"],
    ["Q9759", "blues"],
    // Two hops past anything the answer walked. The automatic neighbourhood is one hop from each
    // walked node, so `blues` is drawn but `ragtime` is not — which makes `ragtime` the only proof
    // available that following an edge reaches corpus the answer never showed.
    ["Q4", "ragtime"],
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
    ["Q221772", "Q131272"],
    ["Q221772", "Q164444"],
    ["Q221772", "Q8341"],
    ["Q8341", "Q9759"],
    ["Q9759", "Q4"],
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

function stubFetch(body: string) {
  return vi.fn(async (input: unknown) => {
    if (String(input).includes("/graph/")) {
      return { ok: true, status: 200, json: async () => ARTIFACT } as unknown as Response;
    }
    const encoder = new TextEncoder();
    return {
      ok: true,
      status: 200,
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          controller.enqueue(encoder.encode(body));
          controller.close();
        },
      }),
    } as unknown as Response;
  });
}

/** Click the headline chip and wait until the map has actually painted something. */
async function drawnMap(recorder: { arcs: Arc[] }): Promise<HTMLCanvasElement> {
  const body = readFileSync(resolve(process.cwd(), "src/fixtures/acid-jazz-answer.sse"), "utf8");
  vi.stubGlobal("fetch", stubFetch(body));
  render(<App />);
  screen.getByRole("button", { name: /Where did acid jazz come from/i }).click();

  await waitFor(() => {
    expect(recorder.arcs.length).toBeGreaterThan(0);
  });
  return document.querySelector("canvas") as HTMLCanvasElement;
}

const drag = (canvas: HTMLCanvasElement, from: [number, number], to: [number, number]) => {
  fireEvent.pointerDown(canvas, { pointerId: 1, clientX: from[0], clientY: from[1], button: 0 });
  fireEvent.pointerMove(canvas, { pointerId: 1, clientX: to[0], clientY: to[1] });
  fireEvent.pointerUp(canvas, { pointerId: 1, clientX: to[0], clientY: to[1], button: 0 });
};

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  resetStaticGraphCache();
});

describe("panning", () => {
  it("moves everything the map drew by exactly the distance dragged", async () => {
    // The assertion that proves a pointer event reached the pixels. Every earlier check in this
    // repo could pass with the camera wired to nothing.
    stubReducedMotion();
    const recorder = installCanvas();
    const canvas = await drawnMap(recorder);

    recorder.clear();
    fireEvent.pointerDown(canvas, { pointerId: 1, clientX: 100, clientY: 100, button: 0 });
    fireEvent.pointerMove(canvas, { pointerId: 1, clientX: 140, clientY: 110 });
    const first = [...recorder.arcs];

    recorder.clear();
    fireEvent.pointerMove(canvas, { pointerId: 1, clientX: 180, clientY: 120 });
    const second = [...recorder.arcs];
    fireEvent.pointerUp(canvas, { pointerId: 1, clientX: 180, clientY: 120, button: 0 });

    expect(first.length).toBeGreaterThan(0);
    expect(second).toHaveLength(first.length);
    second.forEach((arc, index) => {
      const was = first[index];
      expect(was).toBeDefined();
      if (was === undefined) return;
      expect(arc.x - was.x).toBeCloseTo(40, 6);
      expect(arc.y - was.y).toBeCloseTo(10, 6);
    });
  });

  it("offers Recenter only once the camera has been taken, and puts the map back where it was", async () => {
    stubReducedMotion();
    const recorder = installCanvas();
    const canvas = await drawnMap(recorder);

    // D1: the map fits itself until someone touches it, and only then is there anything to undo.
    expect(screen.queryByRole("button", { name: "Recenter" })).toBeNull();

    // The picture before anyone touches it, which is what Recenter has to restore. Forced by a
    // one-pixel drag and its own undo, because the settled draw has already happened by now.
    recorder.clear();
    drag(canvas, [100, 100], [101, 100]);
    drag(canvas, [101, 100], [100, 100]);
    const settled = [...recorder.arcs.slice(-1 * (recorder.arcs.length / 2))];

    drag(canvas, [100, 100], [180, 140]);
    const recenter = await screen.findByRole("button", { name: "Recenter" });

    recorder.clear();
    recenter.click();
    const restored = [...recorder.arcs];

    await waitFor(() => {
      expect(screen.queryByRole("button", { name: "Recenter" })).toBeNull();
    });

    // Asserting the PIXELS, not the button. An earlier version of this test checked only that the
    // control disappeared, and it passed with the camera reset deleted — the button vanished while
    // the map stayed exactly where it had been dragged to.
    expect(restored).toHaveLength(settled.length);
    restored.forEach((arc, index) => {
      const was = settled[index];
      expect(was).toBeDefined();
      if (was === undefined) return;
      expect(arc.x).toBeCloseTo(was.x, 6);
      expect(arc.y).toBeCloseTo(was.y, 6);
    });
  });
});

describe("zooming", () => {
  it("spreads the map out from its middle when the zoom-in button is pressed", async () => {
    stubReducedMotion();
    const recorder = installCanvas();
    await drawnMap(recorder);

    recorder.clear();
    screen.getByRole("button", { name: "Zoom in" }).click();
    const zoomed = [...recorder.arcs];

    expect(zoomed.length).toBeGreaterThan(1);
    const spread = (arcs: Arc[]) =>
      Math.max(...arcs.map((a) => a.x)) - Math.min(...arcs.map((a) => a.x));

    recorder.clear();
    screen.getByRole("button", { name: "Zoom out" }).click();
    const back = [...recorder.arcs];

    expect(spread(zoomed)).toBeGreaterThan(spread(back));
  });
});

describe("selecting a node", () => {
  /** The centre of a walked node, read off what the map actually drew. Walked nodes have radius 6. */
  const walkedNode = (arcs: Arc[]): Arc => {
    const node = arcs.find((arc) => arc.r === 6);
    if (node === undefined) throw new Error("no walked node was drawn");
    return node;
  };

  it("names the node, and says whether the answer went there", async () => {
    stubReducedMotion();
    const recorder = installCanvas();
    const canvas = await drawnMap(recorder);
    const node = walkedNode(recorder.arcs);

    fireEvent.pointerDown(canvas, { pointerId: 1, clientX: node.x, clientY: node.y, button: 0 });
    fireEvent.pointerUp(canvas, { pointerId: 1, clientX: node.x, clientY: node.y, button: 0 });

    // A walked node is one the run reached, and the readout has to say so in words rather than
    // leaving a visitor to infer it from a ring.
    const readout = await screen.findByText(/Reached by this answer/);
    expect(readout.textContent).toMatch(/Q\d+/);
  });

  it("clears the selection when the same node is clicked again", async () => {
    stubReducedMotion();
    const recorder = installCanvas();
    const canvas = await drawnMap(recorder);
    const node = walkedNode(recorder.arcs);

    const click = () => {
      fireEvent.pointerDown(canvas, { pointerId: 1, clientX: node.x, clientY: node.y, button: 0 });
      fireEvent.pointerUp(canvas, { pointerId: 1, clientX: node.x, clientY: node.y, button: 0 });
    };

    click();
    await screen.findByText(/Reached by this answer/);
    click();
    await waitFor(() => {
      expect(screen.queryByText(/Reached by this answer/)).toBeNull();
    });
  });

  it("does not select the node a pan happened to start on", async () => {
    // The `CLICK_SLOP` rule, at the level it actually matters. A drag ends with the pointer up, and
    // the pointer is usually still over whatever it started on — so without the threshold every pan
    // beginning on a node also selects it, which no unit test of `hitTest` can notice.
    stubReducedMotion();
    const recorder = installCanvas();
    const canvas = await drawnMap(recorder);
    const node = walkedNode(recorder.arcs);

    drag(canvas, [node.x, node.y], [node.x + 60, node.y + 20]);

    await waitFor(() => {
      expect(screen.queryByText(/Reached by this answer/)).toBeNull();
      expect(screen.queryByText(/not walked by it/)).toBeNull();
    });
  });

  it("clears the selection when empty canvas is clicked", async () => {
    stubReducedMotion();
    const recorder = installCanvas();
    const canvas = await drawnMap(recorder);
    const node = walkedNode(recorder.arcs);

    fireEvent.pointerDown(canvas, { pointerId: 1, clientX: node.x, clientY: node.y, button: 0 });
    fireEvent.pointerUp(canvas, { pointerId: 1, clientX: node.x, clientY: node.y, button: 0 });
    await screen.findByText(/Reached by this answer/);

    // Far from anything the map drew.
    fireEvent.pointerDown(canvas, { pointerId: 1, clientX: 5, clientY: 5, button: 0 });
    fireEvent.pointerUp(canvas, { pointerId: 1, clientX: 5, clientY: 5, button: 0 });

    await waitFor(() => {
      expect(screen.queryByText(/Reached by this answer/)).toBeNull();
    });
  });
});

/**
 * Step 8b: following an edge, and asking the agent about where you ended up.
 *
 * Driven through the **DOM** rather than the canvas on purpose. Every action here is one a keyboard
 * user can reach, so a test that can only perform them by clicking pixels would be testing the half
 * of D4 that was never in question. If these pass, the accessible path works.
 */
describe("following an edge", () => {
  /** Open the keyboard entry point and land on a named node the answer reached. */
  async function selectWalked(label: string): Promise<void> {
    const entry = await screen.findByText(/Explore this map without pointing at it/);
    fireEvent.click(entry);
    const list = entry.parentElement as HTMLElement;
    const button = [...list.querySelectorAll("button")].find(
      (candidate) => candidate.textContent === label,
    );
    expect(button).toBeDefined();
    fireEvent.click(button as HTMLButtonElement);
  }

  /** Click a named neighbour under one of the inspector's two direction headings. */
  async function followTo(heading: string, label: string): Promise<void> {
    const group = await screen.findByRole("heading", { name: heading });
    const button = [...(group.parentElement as HTMLElement).querySelectorAll("button")].find(
      (candidate) => candidate.textContent === label,
    );
    expect(button).toBeDefined();
    fireEvent.click(button as HTMLButtonElement);
  }

  const caption = (): string => document.querySelector(".map__caption")?.textContent ?? "";

  it("can be reached without pointing at the map at all", async () => {
    // D4. The canvas is a picture with a description; if this is the only way in, it has to work.
    stubReducedMotion();
    const recorder = installCanvas();
    await drawnMap(recorder);

    await selectWalked("jazz");
    await screen.findByRole("complementary", { name: "About jazz" });
    await screen.findByText(/Reached by this answer/);
  });

  it("reveals more corpus without changing a single cited connection", async () => {
    // Invariant 1 at the level a visitor can actually break it. The unit property test in
    // `subgraph.test.ts` proves `buildRenderGraph` cannot do it; this proves the interface wired
    // around that function cannot either.
    stubReducedMotion();
    const recorder = installCanvas();
    await drawnMap(recorder);
    await selectWalked("jazz");

    const citedBefore = /(\d+) cited/.exec(caption())?.[1];
    expect(citedBefore).toBeDefined();
    expect(caption()).not.toMatch(/You have opened/);

    // "Came out of" lists what influenced this node. blues is already drawn; what is NOT drawn is
    // ragtime, one hop past it, and arriving at blues is what reveals it.
    await followTo("Came out of", "blues");

    await waitFor(() => {
      expect(caption()).toMatch(/You have opened a further/);
    });

    // The claimed count is the thing that must not move. Everything a visitor uncovers is corpus.
    expect(/(\d+) cited/.exec(caption())?.[1]).toBe(citedBefore);
    expect(caption()).toMatch(/no more part of this answer than the rest/);
  });

  it("moves to the node it followed to", async () => {
    stubReducedMotion();
    const recorder = installCanvas();
    await drawnMap(recorder);
    await selectWalked("jazz");
    await followTo("Came out of", "blues");

    await screen.findByRole("complementary", { name: "About blues" });
    // And the node it came from is still on the map, so the edge just followed is visible.
    expect(caption()).toMatch(/You have opened a further/);
  });
});

describe("asking the agent about a node", () => {
  it("appends a real query below the answer instead of replacing it", async () => {
    // DoD 4's "request an annotation". It must go to /lineage and come back through the gate —
    // the static corpus in the browser is for navigation and can never produce a claim.
    stubReducedMotion();
    const recorder = installCanvas();
    await drawnMap(recorder);

    const entry = await screen.findByText(/Explore this map without pointing at it/);
    fireEvent.click(entry);
    // Deliberately NOT the subject of the answer already on screen. Annotating `acid jazz` asks
    // "Where did acid jazz come from?", which is the chip's own question, and two identical
    // headings would make this test unable to tell an appended panel from the original one.
    const label = "jazz";
    const button = [...(entry.parentElement as HTMLElement).querySelectorAll("button")].find(
      (candidate) => candidate.textContent === label,
    );
    expect(button).toBeDefined();
    fireEvent.click(button as HTMLButtonElement);

    // `annotate` refuses while a stream is in flight, and the button says so by being disabled.
    // Waiting for that is not test hygiene — it is the guard doing its job.
    const ask = await screen.findByRole("button", { name: `Ask the agent about ${label}` });
    await waitFor(() => {
      expect((ask as HTMLButtonElement).disabled).toBe(false);
    });
    fireEvent.click(ask);

    // A new panel, with the original still on screen above it. Replacing would throw away the
    // answer the visitor was reading in order to answer a question about it.
    await screen.findByRole("heading", { name: `Where did ${label} come from?` });
    expect(screen.getByRole("heading", { name: /Where did acid jazz come from\?/ })).toBeTruthy();
  });
});
