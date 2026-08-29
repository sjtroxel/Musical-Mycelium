import { describe, expect, it } from "vitest";
import { applyFrame } from "./useLineageRun";
import type { StepState } from "./useLineageRun";
import type { Claim, Frame } from "./types";

/**
 * The invariant-1 guard, at the surface step 2 actually has.
 *
 * `.claude/rules/grounding-and-claims.md`: claims first, prose second, never side by side. The gate
 * decides; the model proposes. The client's share of that contract is narrow but real — it must not
 * render a rejected proposal as a claim, and it must not manufacture prose from anything other than the
 * tokens synthesis emitted. Both are one-line mistakes to make and neither is visible by eye.
 *
 * The static-graph half of this guard (a rendered edge is not a narrated one) arrives with the graph
 * itself at step 4 and is tested at step 8, per IMPLEMENTATION 4.2.
 */

function blank(): StepState {
  return {
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
}

const claim: Claim = {
  subject_id: "Q38848",
  predicate: "influenced_by",
  object_id: "Q193355",
  source_ids: ["http://www.wikidata.org/entity/statement/Q38848-abc"],
  verification: "HAND",
  span: null,
};

const rejected: Frame = {
  type: "rejected",
  rejection: {
    proposal: { subject_id: "Q1", predicate: "influenced_by", object_id: "Q2" },
    reason: "not_in_graph",
    detail: "",
  },
};

describe("applyFrame", () => {
  it("adds an approved claim to the rendered set", () => {
    const state = applyFrame(blank(), { type: "claim", claim });
    expect(state.claims).toEqual([claim]);
  });

  it("NEVER adds a rejected proposal to the rendered claim set", () => {
    const state = applyFrame(blank(), rejected);
    expect(state.claims).toEqual([]);
    expect(state.rejectionCount).toBe(1);
  });

  it("counts rejections without ever exposing the proposed triple as a claim", () => {
    // The rejected proposal names Q1 -> Q2. If that pair can be found anywhere in the claim set, the
    // gate has been routed around in the client, which is the leak the claims-first rule exists for.
    let state = blank();
    state = applyFrame(state, { type: "claim", claim });
    state = applyFrame(state, rejected);
    const rendered = state.claims.flatMap((c) => [c.subject_id, c.object_id]);
    expect(rendered).not.toContain("Q1");
    expect(rendered).not.toContain("Q2");
  });

  it("builds prose only from token frames", () => {
    let state = blank();
    state = applyFrame(state, { type: "claim", claim });
    state = applyFrame(state, rejected);
    state = applyFrame(state, {
      type: "path",
      node_ids: ["Q38848"],
      labels: ["heavy metal music"],
      chain: [],
      chain_labels: [],
    });
    // Three frames carrying node labels and a triple, and not one character of prose.
    expect(state.prose).toBe("");

    state = applyFrame(state, { type: "token", text: "Heavy metal " });
    state = applyFrame(state, { type: "token", text: "came out of blues rock." });
    expect(state.prose).toBe("Heavy metal came out of blues rock.");
  });

  it("commits to a refusal the moment the frame arrives and does not revert at done", () => {
    let state = applyFrame(blank(), {
      type: "refused",
      reason: "it resolved but carries no sourced influences",
      query: "Who influenced Kate Bush?",
    });
    expect(state.outcome).toBe("refusal");

    state = applyFrame(state, {
      type: "done",
      usage: { input_tokens: 1, output_tokens: 1 },
      claim_count: 0,
      rejection_count: 0,
      model_id: "m",
      planned_steps: 1,
      executed_steps: 1,
      synthesis_usage: { input_tokens: 0, output_tokens: 0 },
      synthesis_model_id: "",
      stop_reason: "complete",
      elapsed_seconds: 1,
      artifact_version: "0.5.0",
      corpus: {} as never,
    });
    expect(state.outcome).toBe("refusal");
    expect(state.phase).toBe("settled");
  });

  it("treats a run with no refusal frame as an answer once done arrives", () => {
    const state = applyFrame(blank(), {
      type: "done",
      usage: { input_tokens: 1, output_tokens: 1 },
      claim_count: 1,
      rejection_count: 0,
      model_id: "m",
      planned_steps: 1,
      executed_steps: 1,
      synthesis_usage: { input_tokens: 0, output_tokens: 0 },
      synthesis_model_id: "",
      stop_reason: "complete",
      elapsed_seconds: 1,
      artifact_version: "0.5.0",
      corpus: {} as never,
    });
    expect(state.outcome).toBe("answer");
  });
});
