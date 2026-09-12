import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { GRAPH_PIN } from "./graph/staticGraph";
import { SseParser } from "./stream";
import { applyFrame } from "./useLineageRun";
import type { StepState } from "./useLineageRun";
import type { Frame, OfferFrame } from "./types";

/**
 * The contract test between two separately-deployed halves.
 *
 * The fixtures are **real bytes captured from the API**, not hand-written strings: `/lineage` against a
 * local run of `api/app.py`. **Re-captured on artifact v0.10.0 on 2026-09-11** (phase 7.6 step 9), because
 * the app refuses to draw a map for an answer from a corpus other than the staged one and a recording is
 * never re-stamped by hand. Three of these are `LocalLLM` captures and cost nothing; the tour recording
 * is a real Bedrock run, re-captured the same day for about a cent. `kate-bush-descendants.sse` is
 * deliberately left at artifact v0.5.0: it is a Bedrock capture whose value is the 7-claim descendants
 * shape, no test pins its version, and re-capturing it would spend money to replace a historical record.
 * `mozart-offer.sse` and `metal-offer-over-cap.sse` were captured on **2026-09-12** (phase 7.7 step 4),
 * both `LocalLLM` and therefore free. Two rather than one because the `offer` frame has **two** wire
 * shapes — a listed set, and a capped-away set whose `candidates` is empty while `total` is 34 — and
 * hand-typing the second is exactly what these fixtures exist to avoid. Synthetic frames test the parser against my idea of the
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
    contested: [],
    offers: [],
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
    // Read from the pin rather than written out, since 2026-09-11: a capture comes from the pinned
    // corpus, so pinning the literal made this fail at the re-pin for a reason that is not the property.
    expect(state.done?.artifact_version).toBe(GRAPH_PIN);
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

describe("a real contested capture", () => {
  const raw = fixture("electropop-contested.sse");

  it("carries the disagreement as its own frame, not as a field on a claim", () => {
    const state = fold(replay(raw, 29));
    expect(state.contested).toHaveLength(1);
    // `contested` is a property of a PAIR. A claim that grew the marker would seat it beside
    // `verification`, which says how strongly ONE source was checked — the collapse this repo has
    // already corrected three files for.
    for (const claim of state.claims) {
      expect(claim).not.toHaveProperty("contested");
    }
  });

  it("names both directions and both sources and picks no winner", () => {
    const { contested } = fold(replay(raw, 29));
    expect(contested).toHaveLength(1);
    const pair = contested[0]!;
    const sources = [pair.pair.a_from_b.source, pair.pair.b_from_a.source].sort();
    expect(sources).toEqual(["dbpedia", "wikidata"]);
    expect(pair.pair.a_from_b.subject_id).toBe(pair.pair.b_from_a.object_id);
    expect(pair.pair.b_from_a.subject_id).toBe(pair.pair.a_from_b.object_id);
  });

  it("arrives before the first token, so it can be read while the prose streams", () => {
    const frames = replay(raw, 29);
    const contestedAt = frames.findIndex((f) => f.type === "contested");
    const firstTokenAt = frames.findIndex((f) => f.type === "token");
    expect(contestedAt).toBeGreaterThan(-1);
    expect(contestedAt).toBeLessThan(firstTokenAt);
  });

  it("is absent from the prose, which the model wrote from approved claims alone", () => {
    const state = fold(replay(raw, 29));
    expect(state.prose.length).toBeGreaterThan(0);
    for (const word of ["disagree", "contested", "dbpedia", "wikidata"]) {
      expect(state.prose.toLowerCase()).not.toContain(word);
    }
  });

  it("still answers — a disagreement is not a refusal", () => {
    const state = fold(replay(raw, 29));
    expect(state.outcome).toBe("answer");
    expect(state.claims.length).toBeGreaterThan(0);
  });
});

describe("a real offer capture", () => {
  const raw = fixture("mozart-offer.sse");

  it("carries the offer as its own frame, before the refusal it accompanies", () => {
    const frames = replay(raw, 29);
    const names = frames.map((f) => f.type);
    expect(names).toContain("offer");
    expect(names).toContain("refused");
    // D3, on the wire rather than in the loop: an offer accompanies a refusal and never replaces it.
    // `eval.runner` reads `refused` off this frame and `refusal_accuracy` was baselined on it.
    expect(names.indexOf("offer")).toBeLessThan(names.indexOf("refused"));
    expect(names.indexOf("offer")).toBeLessThan(names.indexOf("token"));
  });

  it("approves no claims, because an offer is not a claim", () => {
    const state = fold(replay(raw, 29));
    expect(state.claims).toHaveLength(0);
    expect(state.refusal).not.toBeNull();
  });

  it("says why each candidate is there, including the noisy ones", () => {
    const frames = replay(raw, 29);
    const offer = frames.find((f): f is OfferFrame => f.type === "offer")!;
    expect(offer.term).toBe("mozart");
    expect(offer.total).toBe(5);
    expect(offer.shown).toBe(5);
    expect(offer.candidates).toHaveLength(5);

    for (const candidate of offer.candidates) {
      expect(["label", "alias"]).toContain(candidate.via);
      // The alias text rides along exactly when it is the reason, and is null otherwise. Timbaland
      // under "mozart" has to be legible rather than mysterious.
      expect(candidate.alias === null).toBe(candidate.via === "label");
    }
    const byAlias = offer.candidates.filter((c) => c.via === "alias");
    expect(byAlias.map((c) => [c.label, c.alias])).toEqual([
      ["Timbaland", "Mozart Timadeas"],
      ["Samuel Wesley", "The English Mozart"],
    ]);
  });

  it("reads `total` rather than `candidates.length` when the list is capped away", () => {
    // The other wire shape, captured rather than hand-typed: over the cap of 25 the list is EMPTY and
    // the count is still true. A client reading `candidates.length` reports 0 where the answer is 34.
    const frames = replay(fixture("metal-offer-over-cap.sse"), 29);
    const offer = frames.find((f): f is OfferFrame => f.type === "offer")!;
    expect(offer.term).toBe("metal");
    expect(offer.candidates).toEqual([]);
    expect(offer.shown).toBe(0);
    expect(offer.total).toBe(34);
    expect(offer.total).not.toBe(offer.candidates.length);
  });
});
