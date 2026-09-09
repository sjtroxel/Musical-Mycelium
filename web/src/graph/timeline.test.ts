/**
 * The one-timeline property, asserted over generated runs rather than three hand-picked ones.
 *
 * **What is actually being proved, because it is easy to write a tautology here.** `stateAt` folds one
 * reducer over one prefix, so asking it whether its own two halves agree proves nothing. Instead each
 * property recomputes the narration and the claim set **independently** from the cue list and checks
 * both against the single state. If `stateAt` ever derived text from one prefix and claims from
 * another, these fail; today it structurally cannot, and that is the point of asserting it rather than
 * observing it.
 *
 * **Generated, not enumerated, and seeded rather than random.** A property that holds for three
 * examples is three examples. A property that fails on a different run each night is worse than no
 * property, so the generator is a small deterministic PRNG in this file — no dependency, same
 * sequences on every machine, and a failing seed is quotable in a bug report.
 */

import { describe, expect, it } from "vitest";

import type { Claim, Frame } from "../types";
import { applyFrame, emptyStep } from "../useLineageRun";
import { EDGE_MS } from "./motion";
import { CLAIM_MS, cuesFrom, cursorAt, durationOf, stateAt, type Cue } from "./timeline";

/** Mulberry32. Deterministic, tiny, and good enough to shuffle frame kinds. */
function rng(seed: number): () => number {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function claim(n: number): Claim {
  return {
    subject_id: `Q${n}`,
    predicate: "influenced_by",
    object_id: `Q${n + 1}`,
    subject_label: `subject ${n}`,
    object_label: `object ${n}`,
    source_ids: [`src-${n}`],
    span: null,
    verification: "PROSE_AUTO",
    corroboration: null,
  } as unknown as Claim;
}

/** A plausible run: some machinery, some claims, a path, some prose, an ending. */
function generate(seed: number): Frame[] {
  const next = rng(seed);
  const frames: Frame[] = [
    {
      type: "plan",
      plan: { query_kind: "lineage", steps: [], asserted_premise: null },
      unregistered: [],
    } as unknown as Frame,
  ];
  const claimCount = 1 + Math.floor(next() * 5);
  for (let i = 0; i < claimCount; i++) {
    if (next() < 0.5) {
      frames.push({ type: "tool", name: "trace_lineage", arguments: {}, is_error: false } as Frame);
    }
    frames.push({ type: "claim", claim: claim(i) } as Frame);
  }
  frames.push({
    type: "path",
    node_ids: [],
    labels: [],
    chain: [],
    chain_labels: [],
  } as unknown as Frame);
  const tokenCount = 1 + Math.floor(next() * 12);
  for (let i = 0; i < tokenCount; i++) {
    frames.push({ type: "token", text: `w${i} ` } as Frame);
  }
  return frames;
}

const SEEDS = Array.from({ length: 40 }, (_, i) => i + 1);

/** The narration, recomputed from the cue list alone. */
function proseFrom(cues: readonly Cue[], upTo: number): string {
  return cues
    .slice(0, upTo + 1)
    .filter((cue) => cue.payload.type === "token")
    .map((cue) => (cue.payload.type === "token" ? cue.payload.text : ""))
    .join("");
}

/** The claim set, recomputed from the cue list alone. */
function claimsFrom(cues: readonly Cue[], upTo: number): Claim[] {
  return cues
    .slice(0, upTo + 1)
    .flatMap((cue) => (cue.payload.type === "claim" ? [cue.payload.claim] : []));
}

/** Every millisecond is too many; these are the ones where something can change. */
function probes(cues: readonly Cue[]): number[] {
  const edges = cues.flatMap((cue) => [cue.atMs - 1, cue.atMs, cue.atMs + 1]);
  return [-1, 0, ...edges, durationOf(cues), durationOf(cues) + 5_000];
}

describe("the cue list", () => {
  it.each(SEEDS)("is ordered in time (seed %i)", (seed) => {
    const cues = cuesFrom(generate(seed));
    for (const [index, cue] of cues.entries()) {
      if (index === 0) continue;
      expect(cue.atMs).toBeGreaterThanOrEqual(cues[index - 1]!.atMs);
    }
  });

  it.each(SEEDS)("carries every frame exactly once, in order (seed %i)", (seed) => {
    const frames = generate(seed);
    expect(cuesFrom(frames).map((cue) => cue.payload)).toEqual(frames);
  });

  it.each(SEEDS.slice(0, 10))("honours a token pace override (seed %i)", (seed) => {
    // The parameter exists for the dev-only comparison in `useTour.ts`, which is how `TOKEN_MS` gets
    // the sitting `ENTER_MS` got. If it silently ignored the argument, that comparison would show the
    // same tour three times and read as "the number does not matter".
    const frames = generate(seed);
    const slow = cuesFrom(frames, 200);
    const fast = cuesFrom(frames, 10);
    expect(durationOf(slow, 200)).toBeGreaterThan(durationOf(fast, 10));
    expect(slow.map((c) => c.kind)).toEqual(fast.map((c) => c.kind));
  });

  it("paces claims no faster than the edge animation draws them", () => {
    // Not a taste question. A claim cue firing inside EDGE_MS would start the next edge before the
    // last had finished arriving, so the camera would never once come to rest.
    expect(CLAIM_MS).toBeGreaterThanOrEqual(EDGE_MS);
  });
});

describe("one cursor, one state", () => {
  it.each(SEEDS)("never lets narration and claims read different prefixes (seed %i)", (seed) => {
    const cues = cuesFrom(generate(seed));
    for (const t of probes(cues)) {
      const cursor = cursorAt(cues, t);
      const state = stateAt(cues, t, "q");
      // Both halves recomputed independently, from the same cursor. This is the DoD item.
      expect(state.prose).toBe(proseFrom(cues, cursor));
      expect(state.claims).toEqual(claimsFrom(cues, cursor));
    }
  });

  it.each(SEEDS)("moves forward and never backward (seed %i)", (seed) => {
    const cues = cuesFrom(generate(seed));
    const times = probes(cues).sort((a, b) => a - b);
    for (const [index, t] of times.entries()) {
      if (index === 0) continue;
      const earlier = stateAt(cues, times[index - 1]!, "q");
      const later = stateAt(cues, t, "q");
      expect(cursorAt(cues, times[index - 1]!)).toBeLessThanOrEqual(cursorAt(cues, t));
      expect(later.prose.startsWith(earlier.prose)).toBe(true);
      expect(later.claims.slice(0, earlier.claims.length)).toEqual(earlier.claims);
    }
  });

  it.each(SEEDS)("is empty before the first cue and complete after the last (seed %i)", (seed) => {
    const frames = generate(seed);
    const cues = cuesFrom(frames);
    expect(stateAt(cues, -1, "q")).toEqual(emptyStep("q"));
    expect(stateAt(cues, durationOf(cues) + 10_000, "q")).toEqual(
      frames.reduce(applyFrame, emptyStep("q")),
    );
  });

  it("holds for an empty run rather than throwing", () => {
    expect(cuesFrom([])).toEqual([]);
    expect(durationOf([])).toBe(0);
    expect(cursorAt([], 0)).toBe(-1);
    expect(stateAt([], 5_000, "q")).toEqual(emptyStep("q"));
  });
});
