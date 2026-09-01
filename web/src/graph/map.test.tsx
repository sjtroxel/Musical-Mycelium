import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "../App";
import { StepPanel } from "../components/StepPanel";
import type { StepState } from "../useLineageRun";
import type { Artifact } from "./staticGraph";
import { indexArtifact, resetStaticGraphCache } from "./staticGraph";

/**
 * DoD 3 end to end: the graph reaches the browser, renders what the run returned, and marks the
 * approved connections in the order the gate approved them.
 *
 * The canvas itself is not asserted here — jsdom has no 2D context, so `GraphView` draws nothing and
 * returns early. What this file can check is everything around the pixels: that the corpus is fetched
 * at the right moment and not before, that the caption states the claimed/context split honestly, and
 * that the two cases where the map must refuse to draw actually refuse. The picture is checked in a
 * real browser, per the step 3 lesson about unverified previews.
 */

function fixture(name: string): string {
  return readFileSync(resolve(process.cwd(), "src/fixtures", name), "utf8");
}

/** acid jazz and its four parents, plus one edge the answer never claimed. */
const ARTIFACT: Artifact = {
  nodes: [
    ["Q221772", "acid jazz"],
    ["Q11401", "hip-hop"],
    ["Q131272", "soul"],
    ["Q164444", "funk"],
    ["Q8341", "jazz"],
    ["Q9759", "blues"],
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

/** Answers `/graph/...` with the artifact and everything else with an SSE capture. */
function stubFetch(captures: string[]) {
  let call = 0;
  return vi.fn(async (input: unknown) => {
    if (String(input).includes("/graph/")) {
      return { ok: true, status: 200, json: async () => ARTIFACT } as unknown as Response;
    }
    const body = captures[Math.min(call++, captures.length - 1)] ?? "";
    const encoder = new TextEncoder();
    return {
      ok: true,
      status: 200,
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          for (let i = 0; i < body.length; i += 37) {
            controller.enqueue(encoder.encode(body.slice(i, i + 37)));
          }
          controller.close();
        },
      }),
    } as unknown as Response;
  });
}

/** Just enough of a `done` frame for the panel to render its meta line. */
function done(version: string): StepState["done"] {
  return {
    type: "done",
    usage: { input_tokens: 0, output_tokens: 0 },
    claim_count: 0,
    rejection_count: 0,
    model_id: "stub",
    planned_steps: 1,
    executed_steps: 1,
    synthesis_usage: { input_tokens: 0, output_tokens: 0 },
    synthesis_model_id: "stub",
    stop_reason: "complete",
    elapsed_seconds: 1,
    artifact_version: version,
  } as unknown as StepState["done"];
}

function step(overrides: Partial<StepState> = {}): StepState {
  return {
    query: "Where did acid jazz come from?",
    phase: "settled",
    outcome: "answer",
    prose: "",
    claims: [],
    rejectionCount: 0,
    path: null,
    toolNodeIds: [],
    refusal: null,
    done: null,
    error: null,
    ...overrides,
  };
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  resetStaticGraphCache();
});

describe("the corpus download", () => {
  it("does not start until a run does", async () => {
    const fetcher = stubFetch([fixture("acid-jazz-answer.sse")]);
    vi.stubGlobal("fetch", fetcher);
    render(<App />);

    // DoD 5 again, from the angle step 4 could break it from. 640 KB in front of first paint is
    // exactly what that item forbids, and it is invisible on a fast connection.
    expect(fetcher).not.toHaveBeenCalled();

    screen.getByRole("button", { name: /Where did acid jazz come from/i }).click();
    await waitFor(() => {
      expect(fetcher.mock.calls.some(([url]) => String(url).includes("/graph/"))).toBe(true);
    });
  });

  it("asks for the version the chips are pinned to", async () => {
    const fetcher = stubFetch([fixture("acid-jazz-answer.sse")]);
    vi.stubGlobal("fetch", fetcher);
    render(<App />);
    screen.getByRole("button", { name: /Where did acid jazz come from/i }).click();

    await waitFor(() => {
      const asked = fetcher.mock.calls
        .map(([url]) => String(url))
        .find((u) => u.includes("/graph/"));
      expect(asked).toContain("/graph/v0.5.0/graph.json");
    });
  });
});

describe("the map on an answer", () => {
  it("renders, and says which connections are cited and which are only nearby", async () => {
    vi.stubGlobal("fetch", stubFetch([fixture("acid-jazz-answer.sse")]));
    const { container } = render(<App />);
    screen.getByRole("button", { name: /Where did acid jazz come from/i }).click();

    await waitFor(() => {
      expect(container.querySelector(".map__canvas")).not.toBeNull();
    });

    // The four approved claims, and the one corpus edge around them that this answer did not claim.
    // The caption carrying that split in words is the thing that stops the faint lines reading as
    // part of the answer, which would be the map quietly narrating an ungated edge.
    const caption = container.querySelector(".map__caption")?.textContent ?? "";
    expect(caption).toMatch(/4\s*cited connections/);
    expect(caption).toMatch(/not.*part of this answer/i);

    const label = container.querySelector(".map__canvas")?.getAttribute("aria-label") ?? "";
    expect(label).toMatch(/4 approved connections numbered in the order they were approved/);
  });
});

describe("the map on a refusal", () => {
  it("draws nothing when the run never resolved a node", async () => {
    // The local stub passes the whole question to `resolve_node`, so no id appears anywhere in the
    // stream. `chips.json` holds Kate Bush's Q636 and using it here would be the interface claiming to
    // know which node the run meant when the run never established it. No map is the honest answer.
    vi.stubGlobal(
      "fetch",
      stubFetch([fixture("kate-bush-refusal.sse"), fixture("kate-bush-descendants.sse")]),
    );
    const { container } = render(<App />);
    screen.getByRole("button", { name: /Kate Bush/i }).click();

    await waitFor(() => {
      expect(screen.getByText(/not evidence of a missing influence/i)).toBeDefined();
    });
    expect(container.querySelectorAll(".panel")[0]?.querySelector(".map")).toBeNull();
  });
});

describe("the version guard", () => {
  it("refuses to draw a corpus the answer did not come from", () => {
    const { container } = render(
      <StepPanel
        step={step({
          toolNodeIds: ["Q221772"],
          done: done("0.5.0"),
        })}
        graph={indexArtifact("0.4.0", ARTIFACT)}
      />,
    );

    // Every id resolves in both corpora, so this would draw a perfectly plausible picture of a graph
    // that was never walked. That is the quietest way this screen could lie, and it costs one
    // comparison to prevent.
    expect(container.querySelector(".map__canvas")).toBeNull();
    expect(container.querySelector(".map__mismatch")?.textContent).toMatch(/not drawn/i);
  });

  it("draws when the versions agree", () => {
    const { container } = render(
      <StepPanel
        step={step({
          toolNodeIds: ["Q221772"],
          done: done("0.5.0"),
        })}
        graph={indexArtifact("0.5.0", ARTIFACT)}
      />,
    );
    expect(container.querySelector(".map__canvas")).not.toBeNull();
  });
});
