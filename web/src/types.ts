// The SSE frame shapes, mirroring the dataclasses in `agent/loop.py` as `api/app.py` serialises them
// with `asdict`. `SPEC.md` 5.3 fixes `claim`, `token`, `path` and `done`; the rest are additive.
//
// These are hand-written rather than generated. The API is the contract between two halves that are
// deployed separately, and a generated type would hide a backend change behind a rebuild instead of
// surfacing it as a type error here.

/**
 * How strongly the ONE source behind an edge was checked. Mirrors `graph/schema.py`.
 *
 * **Widened at phase 6 step 8, and it was stale before that.** Artifact v0.7.0 added `INFOBOX_AUTO`
 * and v0.6.0 the two `MEMBERSHIP_*` tiers, while this union still listed the original four — so a
 * real claim carrying `INFOBOX_AUTO` had no type for it and `ClaimList` fell through to printing the
 * raw constant at a reader. `contract.test.ts` caught it on the re-pin, which is exactly the job that
 * file exists to do.
 *
 * **`INFOBOX_AUTO` is weaker than `PROSE_AUTO`, not stronger, and never a second source.** It means
 * DBpedia took the edge from an article's infobox and the same article's prose confirmed it: one page
 * agreeing with itself. The `MEMBERSHIP_*` pair applies to `plays_genre` edges, which the gate never
 * approves, so they reach the interface only on context edges the map draws.
 */
export type Verification =
  | "HAND"
  | "PROSE_AUTO"
  | "ASSERTS_AUTO"
  | "EXPOSURE_AUTO"
  | "INFOBOX_AUTO"
  | "MEMBERSHIP_CITED"
  | "MEMBERSHIP_BARE";

export interface Span {
  start: number;
  end: number;
}

export interface Claim {
  subject_id: string;
  predicate: string;
  object_id: string;
  source_ids: string[];
  /**
   * How strongly this claim's ONE source was checked. **Not a count of agreeing sources and not a
   * disputed flag.** Corroboration is a separate field on the edge and the two must never be
   * collapsed: a corroborated `PROSE_AUTO` edge is not thereby a `HAND` edge. Any UI that renders
   * this as consensus is stating the opposite of the truth — see
   * `.claude/rules/grounding-and-claims.md`.
   *
   * *(This said "every edge in this corpus has exactly one source, always Wikidata" until phase 6
   * step 8. That was true through artifact v0.5.0 and false from v0.7.0, which ingested DBpedia:
   * 82 influence edges now carry a second source. The great majority — 2,202 of 2,284 — are still
   * single-source, so the correction is to the absolute, not to the emphasis.)*
   */
  verification: Verification;
  span: Span | null;
}

export interface ClaimProposal {
  subject_id: string;
  predicate: string;
  object_id: string;
}

export interface Rejection {
  proposal: ClaimProposal;
  reason: string;
  detail: string;
}

export interface PlanStep {
  tool: string;
  reason: string;
  arguments: Record<string, unknown>;
}

export interface Plan {
  query_kind: string;
  steps: PlanStep[];
  asserted_premise: unknown | null;
}

export interface Usage {
  input_tokens: number;
  output_tokens: number;
}

export interface Coverage {
  genres: number;
  without_inception: number;
  without_country: number;
  eras: Record<string, number>;
  coarser_than_year: number;
  countries: Record<string, number>;
  distinct_countries: number;
  genres_without_us_or_uk: number;
  top_country: string;
  top_country_share: number;
}

export interface CorpusSummary {
  artifact_version: string;
  nodes: number;
  edges: number;
  verification: Record<string, number>;
  structure: Record<string, number>;
  coverage: Coverage;
  predicate: string;
}

/** `complete` is the only value that may be presented as a finished answer. See `DoneFrame`. */
export type StopReason = "complete" | "max_turns" | "max_tokens";

export interface PlanFrame {
  type: "plan";
  plan: Plan;
  unregistered: string[];
}

export interface ToolFrame {
  type: "tool";
  name: string;
  arguments: Record<string, unknown>;
  is_error: boolean;
}

export interface ClaimFrame {
  type: "claim";
  claim: Claim;
}

export interface RejectedFrame {
  type: "rejected";
  rejection: Rejection;
}

export interface PathFrame {
  type: "path";
  node_ids: string[];
  labels: string[];
  /**
   * The approved chain, descendant-first, and **it is not the same list as `node_ids`.** Visit order
   * resolves both endpoints before tracing between them, so drawing an arrow down `node_ids` narrates
   * false history. `loop.py:PathWalked` spells this out. Empty for an origins query and empty when a
   * hop was rejected — a broken chain is not displayed as a chain.
   */
  chain: string[];
  chain_labels: string[];
}

export interface TokenFrame {
  type: "token";
  text: string;
}

/** Not an error. The correct answer when the graph cannot support one. */
export interface RefusedFrame {
  type: "refused";
  reason: string;
  query: string;
}

export interface DoneFrame {
  type: "done";
  usage: Usage;
  claim_count: number;
  rejection_count: number;
  model_id: string;
  planned_steps: number;
  executed_steps: number;
  synthesis_usage: Usage;
  synthesis_model_id: string;
  /** Anything other than `complete` means the answer may be missing a hop. Say so; never hide it. */
  stop_reason: StopReason;
  elapsed_seconds: number;
  artifact_version: string;
  corpus: CorpusSummary;
}

export type Frame =
  | PlanFrame
  | ToolFrame
  | ClaimFrame
  | RejectedFrame
  | PathFrame
  | TokenFrame
  | RefusedFrame
  | DoneFrame;
