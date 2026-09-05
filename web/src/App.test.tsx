import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";

/**
 * The DoD checks that need a rendered document: **DoD 2** (clicking a chip streams a cited lineage,
 * citations appearing as claims are made) and **DoD 10** (a refusal renders as an answer about the
 * evidence, never as an error).
 *
 * `fetch` is replaced with a replay of real captured server bytes — the same fixtures `contract.test.ts`
 * uses — so this exercises the whole path from stream to DOM without a network or a model.
 *
 * DoD 10 requirement 1 is *"no error chrome, ever"*, and that is an absence. Asserting an absence is
 * worth doing carefully: the check below is that the refusal panel carries the same class as an answer
 * panel and no failure styling, which is what would actually break if someone gave refusals their own
 * component later.
 */

function fixture(name: string): string {
  return readFileSync(resolve(process.cwd(), "src/fixtures", name), "utf8");
}

/** A `fetch` that answers every `/lineage` call with the given capture, one chunk at a time. */
function stubFetch(captures: string[]) {
  let call = 0;
  return vi.fn(async () => {
    const body = captures[Math.min(call++, captures.length - 1)] ?? "";
    const encoder = new TextEncoder();
    return {
      ok: true,
      status: 200,
      body: new ReadableStream<Uint8Array>({
        start(controller) {
          // Deliberately small chunks that do not align with frame boundaries.
          for (let i = 0; i < body.length; i += 37) {
            controller.enqueue(encoder.encode(body.slice(i, i + 37)));
          }
          controller.close();
        },
      }),
    } as unknown as Response;
  });
}

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
});

describe("the first screen", () => {
  it("renders a search box and the canonical chips before any request", () => {
    render(<App />);
    expect(screen.getByLabelText(/ask about a genre/i)).toBeDefined();
    // DoD 1. Five chips, matching chips.json — the count itself is asserted in tests/test_chips.py.
    expect(screen.getAllByRole("button", { name: /come from|connected|Kate Bush/i })).toHaveLength(
      5,
    );
  });

  it("makes no network request on load", () => {
    const fetcher = stubFetch([]);
    vi.stubGlobal("fetch", fetcher);
    render(<App />);
    // DoD 5: the frontend loads instantly and independently of the agent. A first paint that waits on
    // a request is exactly what that item forbids, and it is invisible on a fast connection.
    expect(fetcher).not.toHaveBeenCalled();
  });
});

describe("clicking a chip", () => {
  it("streams an answer and renders its citations", async () => {
    vi.stubGlobal("fetch", stubFetch([fixture("acid-jazz-answer.sse")]));
    const { container } = render(<App />);

    screen.getByRole("button", { name: /Where did acid jazz come from/i }).click();

    await waitFor(() => {
      expect(screen.getByText(/5 cited claims/i)).toBeDefined();
    });

    // Every rendered claim carries at least one source link. "Citation resolution" is a blocking eval
    // metric on the backend; the client's half is not dropping them on the floor.
    const sources = container.querySelectorAll(".claim__sources a");
    expect(sources.length).toBeGreaterThanOrEqual(4);
    for (const anchor of sources) {
      expect(anchor.getAttribute("href")).toMatch(/^https:\/\/www\.wikidata\.org\/wiki\/Q\d+/);
    }
  });
});

describe("a refusal", () => {
  it("renders in the same card as an answer, with no error chrome", async () => {
    vi.stubGlobal(
      "fetch",
      stubFetch([fixture("kate-bush-refusal.sse"), fixture("kate-bush-descendants.sse")]),
    );
    const { container } = render(<App />);

    screen.getByRole("button", { name: /Kate Bush/i }).click();

    await waitFor(() => {
      expect(screen.getByText(/no sourced answer/i)).toBeDefined();
    });

    // Requirement 1: same card, no failure styling anywhere in the panel.
    expect(container.querySelectorAll(".panel").length).toBeGreaterThan(0);
    expect(container.querySelector(".status--failed")).toBeNull();
  });

  it("says a missing edge is not evidence of a missing influence", async () => {
    // Requirement 5, kept as its OWN test on purpose. It shared a test with requirement 1 until both
    // were broken deliberately and a single failure came back — one signal for two unrelated
    // requirements tells you something is wrong without telling you which thing.
    vi.stubGlobal(
      "fetch",
      stubFetch([fixture("kate-bush-refusal.sse"), fixture("kate-bush-descendants.sse")]),
    );
    render(<App />);

    screen.getByRole("button", { name: /Kate Bush/i }).click();

    await waitFor(() => {
      expect(screen.getByText(/not evidence of a missing influence/i)).toBeDefined();
    });
  });

  it("is never the last thing on screen — the pair continues to an answer", async () => {
    vi.stubGlobal(
      "fetch",
      stubFetch([fixture("kate-bush-refusal.sse"), fixture("kate-bush-descendants.sse")]),
    );
    const { container } = render(<App />);

    screen.getByRole("button", { name: /Kate Bush/i }).click();

    // Requirement 4: no reachable dead end. The paired chip runs a second query after the refusal, so
    // two panels must appear and the last one must carry claims.
    //
    // **The second fixture must be this chip's own second query.** It was `acid-jazz-answer.sse` until
    // 2026-08-26 — a capture of a completely different question — and that made the test a lie: it
    // proved the UI renders a second panel, and proved nothing about whether "Who did Kate Bush
    // influence?" answers. It does answer, with seven claims, but only against a real model; the local
    // stub refuses it, so the pair really was a dead end everywhere the stub runs.
    await waitFor(() => {
      expect(container.querySelectorAll(".panel")).toHaveLength(2);
    });
    await waitFor(() => {
      const panels = container.querySelectorAll(".panel");
      expect(panels[panels.length - 1]?.querySelector(".claims")).not.toBeNull();
    });
    // The claims rendered are Kate Bush's, not some other query's.
    expect(screen.getByText(/7 cited claims/i)).toBeDefined();
  });
});
