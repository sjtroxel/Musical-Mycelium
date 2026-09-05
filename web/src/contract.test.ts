import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { SseParser } from "./stream";
import { applyFrame } from "./useLineageRun";
import type { StepState } from "./useLineageRun";
import type { Frame } from "./types";

/**
 * The contract test between two separately-deployed halves.
 *
 * The fixtures are **real bytes captured from the API**, not hand-written strings: `/lineage` against a
 * local run of `api/app.py` on artifact v0.7.1. Synthetic frames test the parser against my idea of the
 * protocol; these test it against the protocol. The backend and the frontend ship on different
 * schedules — Lambda through `deploy.yml`, the SPA through an S3 sync — so a field that quietly changes
 * name has no other place to fail loudly.
 *
 * Free, offline, and deterministic. Regenerate with:
 *   make dev  # in one shell
 *   curl -sN --get --data-urlencode "q=..." http://127.0.0.1:8000/lineage -o web/src/fixtures/<name>.sse
 */

// Resolved from the Vitest root (`web/`) rather than from `import.meta.url`: under the jsdom
// environment that URL is not a filesystem path, and reading it fails with a misleading ENOENT.
function fixture(name: string): string {
  return readFileSync(resolve(process.cwd(), "src/fixtures", name), "utf8");
}

/** Feed a whole capture through the parser in awkward chunks, the way a network delivers it. */
function replay(text: string, chunkSize: number): Frame[] {
  const parser = new SseParser();
  const frames: Frame[] = [];
  for (let i = 0; i < text.length; i += chunkSize) {
    frames.push(...parser.push(text.slice(i, i + chunkSize)));
  }
  return frames;
}

function fold(frames: Frame[]): StepState {
  const start: StepState = {
    query: "q",
    phase: "running",
    outcome: null,
    prose: "",
    claims: [],
    rejectionCount: 0,
    path: null,
    toolNodeIds: [],
    refusal: null,
    done: null,
    error: null,
  };
  return frames.reduce(applyFrame, start);
}

describe("a real answer capture", () => {
  const raw = fixture("acid-jazz-answer.sse");

  it("parses every frame the server sent, at any chunk boundary", () => {
    const whole = replay(raw, raw.length);
    expect(whole.length).toBeGreaterThan(0);
    for (const chunkSize of [1, 7, 64, 500]) {
      expect(replay(raw, chunkSize)).toEqual(whole);
    }
  });

  it("yields the five approved claims acid jazz actually has", () => {
    // **Four until the phase 6 re-pin, five from artifact v0.7.1.** The fifth is `jazz fusion`, and
    // it is the first time the headline chip's own answer contains an edge DBpedia supplied
    // (`INFOBOX_AUTO`, `http://dbpedia.org/resource/Acid_jazz`). The corpus grew under this capture
    // and lost nothing: the original four Wikidata `HAND` edges are all still here.
    const state = fold(replay(raw, 64));
    expect(state.claims).toHaveLength(5);
    expect(state.outcome).toBe("answer");
    for (const claim of state.claims) {
      expect(claim.subject_id).toBe("Q221772");
      expect(claim.source_ids.length).toBeGreaterThan(0);
    }
  });

  it("carries a verification tier on every claim, never absent", () => {
    // `Claim.verification` is required with no default in `agent/claims.py` precisely because any
    // default would be wrong for half the corpus. A client that let it go undefined would render
    // "undefined" as a strength-of-check, which is worse than rendering nothing.
    //
    // **The list widened at the phase 6 re-pin and that is the whole value of this assertion.** It
    // held the original four tiers, a real claim arrived carrying `INFOBOX_AUTO`, and this test is
    // what surfaced that `types.ts` and `ClaimList`'s wording map had both gone stale against the
    // backend -- so the interface was printing a raw constant where a sentence belongs. The
    // `MEMBERSHIP_*` pair cannot reach a claim, because the gate never approves `plays_genre`.
    const state = fold(replay(raw, 64));
    for (const claim of state.claims) {
      expect(["HAND", "PROSE_AUTO", "ASSERTS_AUTO", "EXPOSURE_AUTO", "INFOBOX_AUTO"]).toContain(
        claim.verification,
      );
    }
  });

  it("reports a corpus summary on done", () => {
    const state = fold(replay(raw, 64));
    expect(state.done?.artifact_version).toBe("0.7.1");
    expect(state.done?.corpus.nodes).toBeGreaterThan(0);
  });
});

describe("a real refusal capture", () => {
  const raw = fixture("kate-bush-refusal.sse");

  it("is a refusal with no claims and real prose", () => {
    const state = fold(replay(raw, 13));
    expect(state.outcome).toBe("refusal");
    expect(state.claims).toHaveLength(0);
    // The refusal text is deterministic and server-side (`loop.py:refusal_text`) — no model call, so
    // it cannot hallucinate the thing it is declining to state. The client renders it, never writes it.
    expect(state.prose).toContain("no sourced answer");
  });

  it("still completes normally — a refusal is not an error", () => {
    const state = fold(replay(raw, 13));
    expect(state.phase).toBe("settled");
    expect(state.done?.stop_reason).toBe("complete");
    expect(state.error).toBeNull();
  });
});
