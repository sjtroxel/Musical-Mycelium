# Phase 1 — Walking Skeleton (v0.1): IMPLEMENTATION

> **Plan, not an as-built record.** Written 2026-08-01, immediately before the build, per the two-layer rule
> in `CLAUDE.md`. It absorbs what phase 0 and the 2026-07-31 P279/P737 validation actually taught. This doc
> is allowed to be wrong; it is not allowed to be silently wrong — update it as reality diverges.
>
> **The AWS steps are gated; the build is not.** All Bedrock daily-token quotas read 0 across every
> vendor; support case `178545883500013` is escalated. The scope doc's "everything waits" rule dates from
> 2026-07-29, when the risk was an AWS account that might never materialize. That risk is retired: the
> account exists, streaming is verified by a real deploy, and model access is granted (the block is one
> quota dimension). Amended 2026-08-01 (see `docs/reviews/2026-08-01-fable-status-review.md` §4.1): the
> `converse` smoke call gates AWS spend and deploy — steps 1 and 9 of §12 — and steps 2–8 proceed now.

## 1. What this phase delivers

A public URL that streams a grounded, cited, two-sentence answer about **one genre's documented influences**,
generated only from claims a deterministic gate approved, deployed by CI, provisioned by Terraform, with one
eval metric passing and budget alarms armed.

A deeply unimpressive product and a completely correct skeleton.

### Definition of done

Unchanged from the scope doc except where noted:

1. One successful Bedrock `converse` call, made and logged.
2. `terraform apply` provisions everything; `terraform destroy` removes everything.
3. A public URL returns a **streamed** response.
4. That response is generated from gated claims, and every claim resolves to a real source.
5. One eval metric runs in CI against a pinned artifact and passes.
6. Budget alarms armed; CloudWatch log retention set explicitly in Terraform.
7. Token cost is measured and logged, not estimated.

## 2. The predicate decision, and the scope-doc amendments it forces

**Decided 2026-08-01 by sjtroxel.** The scope doc and `graph-semantics.md` contradicted each other and the
contradiction was load-bearing.

- `phase-1-walking-skeleton.md:34` promised an answer about a genre's **origins**.
- `graph-semantics.md:186` assigned phase 1 to **P279 only**, and required that "the gate must already refuse
  to narrate P279 as derivation."

Both cannot hold. P279 is category membership; a gate that correctly refuses to narrate it as derivation
makes an origins answer impossible from P279 data. **Resolution: v0.1 uses P737 (`influenced by`)
genre-to-genre edges**, hand-verified against the PROSE tier, in a deliberately tiny artifact.

Why this over the alternatives: it preserves the **real claim shape** (`influenced_by`), so the gate, the
`Claim` model, and the prose templates built here survive into phase 2 unchanged. Building v0.1 on
`subclass_of` would have meant reworking all three once the corpus arrived, which is exactly the rework a
walking skeleton exists to prevent. The full 351-edge prose-check pipeline stays in phase 2 where
`graph-semantics.md` §4.5 assigns it.

### Amendments owed before this doc is approved — applied 2026-08-01

| Doc | Line | Current | Becomes |
|---|---|---|---|
| `phase-1-walking-skeleton.md` | 55 | "A few hundred genres, not the full ~6,324" | "~15 hand-verified edges, not the full corpus" |
| `phase-1-walking-skeleton.md` | 59 | "Genre axis only (P279). The artist axis (P737) is phase 2" | "Genre axis only. P737 genre-to-genre; the **artist** axis is phase 2" |
| `phase-1-walking-skeleton.md` | 45 | "Hand-check 20 P279 edges … **before** ingesting" | Mark DONE 2026-07-31; link `docs/graph-semantics.md` |
| `graph-semantics.md` | 186 | "Phase 1 — genre axis only, P279" | Amended in place, dated, with the reasoning above |

Two further drift items found while reading, **not** fixed here because `SPEC.md` §2 is explicitly his to
edit and still unapproved:

- `SPEC.md:60` says P737 is "the artist axis … not the genre axis (P279)." `graph-semantics.md` §3 shows
  P737 runs genre-to-genre as well. The note is now misleading.
- `SPEC.md:50` lists "What did bebop grow out of?" as a canonical query, but `graph-semantics.md` §3.2 found
  **the `bebop <- swing` edge is not in the corpus at all.** That query cannot be answered from sourced data
  as written. It is a good adversarial or coverage-honesty case; it is a bad demo chip.

## 3. Explicitly not in this phase

The scope fence, which does more work than the feature list. Unchanged from the scope doc, restated because
it is the thing most likely to erode:

The full corpus. The Wikipedia prose-check pipeline (phase 2). Real multi-hop planning. The artist axis. The
SPA and any visualization. More than one eval metric. The LLM judge. Contested-claim UI. Caching. Any density
or coverage work. The 46-component question — it belongs to phase 6 and merely **constrains** phase 2.

Also not in this phase, and worth naming because they are tempting: retry/backoff sophistication, more than
two tools, a real query parser, and any attempt to make the two-sentence answer good.

## 4. One-way doors, and how each is satisfied here

All nine from `CLAUDE.md`. Reversing any is a rewrite, so each gets a real v0.1 form rather than a stub.

| # | Invariant | v0.1 form |
|---|---|---|
| 1 | Claims first, prose second | Gate is deterministic Python. `synthesize()` receives only the approved claim list — it has no access to the graph, the query, or rejected claims. Enforced by signature, not convention |
| 2 | Provenance on every edge | `source`, `source_id`, `retrieved_at` on every node and edge in the artifact, written by the generator, asserted by a test |
| 3 | Validated graph semantics | Done 2026-07-31. P737 only; `subclass_of` is not ingested at v0.1, so it cannot be narrated as derivation by construction |
| 4 | Agent-to-data tool contract | `Tool` protocol + `ToolResult` carrying `sources`. Two tools registered through it. Adding a third must not edit the loop |
| 5 | Everything in Terraform | Nothing clicked except account setup and Bedrock access. `terraform destroy` verified clean on 2026-07-31 |
| 6 | Package boundaries | Done in phase 0 and guarded by `tests/test_architecture.py` |
| 7 | LLM provider seam | `build_llm()` factory returning a protocol. One implementation (`BedrockLLM`). This is the seam that makes the OpenRouter fallback real |
| 8 | Lambda container image | Required by the 250MB limit. `--provenance=false --sbom=false` is mandatory or Lambda rejects the image |
| 9 | Response streaming | FastAPI + uvicorn behind the Lambda Web Adapter, `AWS_LWA_INVOKE_MODE=response_stream`, Function URL `invoke_mode = "RESPONSE_STREAM"`. Verified 2026-07-31, TTFB 0.214s vs 10.22s |

## 5. Contracts this phase decides

`SPEC.md` §5, §6, and §7 are marked OPEN and owned by this doc. **The settled contracts land in `SPEC.md`
when this doc is approved** — they are worked out here and live there, per the define-once rule.

### 5.1 Artifact schema

Single JSON file plus a manifest, both immutable and versioned. At ~15 edges the format is irrelevant to
performance and is chosen for legibility and diffability.

```
src/musical_mycelium/artifacts/v0.1.0/
  graph.json      nodes[] + edges[], every row carrying provenance
  manifest.json   artifact_version, generated_at, source snapshot ids, edge/node counts, sha256 of graph.json
```

*(Path settled 2026-08-02 during the build; this section originally read `artifacts/v0.1.0/` at the repo
root. Three reasons it moved into the package: the root is CI-capped at 18 and this spends headroom on
data; phase 0 already decided in `.gitignore` that data directories stay off the root listing, and its
`data/` pattern matches at any depth so it cannot hold a tracked artifact; and hatchling ships everything
under the package directory, so `pip install` carries the artifact into the container image with no COPY
step and no S3 fetch on the cold path.)*

*(Also settled: **the schema lives in `graph/schema.py`, not `ingest/`.** `ingest` may import `graph`;
`graph` must never import `ingest`, or the Lambda image carries the network-fetching ingestion code.
`tests/test_architecture.py` enforces the direction. The artifact is the seam between the two.)*

**Provenance is enforced at construction, not by a test.** `Node` and `Edge` are frozen dataclasses whose
`__post_init__` raises `ProvenanceError` on a missing or blank `source` / `source_id` / `retrieved_at`. A
test that checks provenance can be deleted; a constructor that refuses to build the row cannot be.

**An edge's `source_id` is the Wikidata *statement* URI, not the subject QID** — e.g.
`.../entity/statement/Q193355-032451F3-...`. It resolves to the specific assertion, which is the
difference between a citation that can be checked and one that gestures. Every node additionally carries
the `revision_id` it was read from, so `retrieved_at` has something behind it.

Edge rows carry `subject_id`, `predicate` (`influenced_by`), `object_id`, `source`, `source_id`,
`retrieved_at`, and `prose_tier` (`PROSE` for all v0.1 rows, present so phase 2 does not alter the schema).

The **pinned artifact version is a constant in code**, not "latest." Evals run against the pin; that is what
stops a corpus change from silently invalidating a benchmark.

### 5.2 Graph store

`GraphStore` protocol with `get_node`, `neighbors`, `search`, `path`. One implementation at v0.1:
`InMemoryGraphStore`, loading `graph.json` at **module scope** so the parse is paid once per container, not
per request. `path` may raise `NotImplementedError` at v0.1 — it is on the protocol because phase 5's C-shaped
queries need it and adding a protocol method later touches every implementation.

The artifact ships **inside the container image** at v0.1 rather than being fetched from S3. It is a few KB,
it removes an IAM permission and a network call from the cold path, and the S3 loader is a phase-2 concern
when the artifact stops being trivially small. This is a two-way door behind the protocol.

**As built, 2026-08-02.** Three additions to the above, each because retrofitting it would touch every
implementation:

- **`neighbors` takes a `Direction`**, not just a node id. `SPEC.md` §2.2 commits to descendant queries,
  and a one-argument `neighbors` would have to grow a second method later. The enum members are
  `INFLUENCED_BY` and `INFLUENCED` rather than incoming/outgoing — an edge reads *subject
  `influenced_by` object*, so graph-theoretic naming here is an invitation to invert music history
  while every count stays identical.
- **`artifact_version` is on the protocol.** Evals report against the pin, so the store has to be able
  to say what it loaded.
- **Loading verifies the sha256** against the manifest. A corpus that has drifted fails at boot instead
  of quietly serving edges nobody signed off on. This forced the *read* side of the artifact —
  `verify`, `read_manifest`, `sha256_of` — to move from `ingest/artifact.py` into `graph/schema.py`,
  since `graph` must not import `ingest`. `ingest` now owns writing only.

One deviation from the wording above: loading is a **memoised function** (`default_store()`), not a true
import-time side effect. Same "parsed once per container" property, but importing the module never does
file I/O — an import that can fail on a missing file is a bad cold start and an worse test fixture. The
API module calls it at module scope in step 7 so the parse still lands in the Lambda INIT phase.

### 5.3 API contract

`GET /lineage?q=<genre>`, `text/event-stream`. Event types: `claim` (each approved claim as it is gated),
`token` (prose deltas), `path` (the walked path, in order), `done` (usage and cost). The path event is
non-negotiable at v0.1 — `SPEC.md` §1 commits to B and C, and retrofitting path-in-payload after the schema
has consumers is the annoying kind of rework.

### 5.4 Claim model

`Claim(subject_id, predicate, object_id, source_ids, span)` exactly as `SPEC.md` §7 fixes it. Frozen dataclass.
`span` is the character range in the emitted prose that the claim underwrites, which is what makes the phase-4
claim-coverage audit possible.

## 6. Files and modules that will change

| Path | What lands |
|---|---|
| `src/musical_mycelium/ingest/wikidata.py` | One-shot P737 fetch + type filter on both ends; writes the artifact. Runs locally, never in Lambda. **Built 2026-08-02** |
| `src/musical_mycelium/ingest/artifact.py` | Artifact + manifest writer, sha256, immutability guard, hash verification. **Built 2026-08-02** |
| `src/musical_mycelium/graph/schema.py` | **Added during the build, not in the original plan.** The artifact contract: `Node`, `Edge`, `Manifest`, `Artifact`. Lives in `graph` because `ingest -> graph` is the only safe direction |
| `src/musical_mycelium/graph/store.py` | `GraphStore` protocol + the `Direction` enum. **Built 2026-08-02** |
| `src/musical_mycelium/graph/memory.py` | `InMemoryGraphStore`, name normalisation, the memoised `default_store()`. **Built 2026-08-02** |
| `src/musical_mycelium/agent/claims.py` | `Claim`, and the deterministic `gate()` |
| `src/musical_mycelium/agent/tools.py` | `Tool` protocol, `ToolResult`, the two tools, the registry |
| `src/musical_mycelium/agent/llm.py` | `build_llm()` + `BedrockLLM` (Converse/ConverseStream) |
| `src/musical_mycelium/agent/loop.py` | The hand-built tool loop; emits claims, then prose from approved claims |
| `src/musical_mycelium/api/app.py` | FastAPI app, the SSE endpoint. Owns no logic |
| `src/musical_mycelium/eval/metrics.py` | `edge_groundedness`, plus its own unit tests |
| `src/musical_mycelium/eval/datasets/gold_v0_1.json` | Five hand-authored gold cases |
| `infra/docker/Dockerfile` | Python 3.13 base, LWA copied to `/opt/extensions/`, artifact baked in |
| `infra/terraform/` | ECR, Lambda, Function URL, IAM role, CloudWatch log group **with explicit retention**, budget, anomaly detection |
| `.github/workflows/deploy.yml` | OIDC role assumption, build, push, two-stage apply |
| `docs/SPEC.md` | §5, §6, §7 filled from section 5 above |

## 7. The two tools

Deliberately two, behind the `Tool` protocol.

1. `resolve_genre(name) -> node_id | None` — string to Wikidata QID against the artifact. Returns `None`
   rather than guessing; an unresolvable genre is a **refusal**, not an error.
2. `get_influences(node_id) -> list[edge]` — one hop along `influenced_by`, each edge carrying its sources.

One hardcoded hop, no planning. The loop calls 1 then 2, emits a claim per returned edge, gates them, and
synthesizes from the survivors.

## 8. Testing

| Layer | What |
|---|---|
| Architecture | `tests/test_architecture.py` from phase 0, extended: `agent` must not import `api`; `api` must not import `ingest` |
| Unit | Gate accepts a real edge, rejects a fabricated one, rejects a real edge with an unresolvable source |
| Metric unit tests | Per `.claude/rules/evals.md` §"unit-test the metrics themselves", including the **vacuous-truth guard: an empty output must not score 100% groundedness** |
| Integration | Loop against a fixture `GraphStore` and a stub LLM — no Bedrock call in CI |
| Eval (Tier 1) | `edge_groundedness` over the five gold cases. Deterministic, $0, every commit |

**Only `edge_groundedness` is in scope.** It is blocking at 100% per `.claude/rules/evals.md`, and it can be
because it is a dictionary lookup against a graph we own. No thresholds are invented for anything else —
there is no baseline yet.

The five gold cases are hand-authored from the same verification pass that produces the artifact, **before**
the agent is coded. That ordering is required: a gold set written after the agent exists is contaminated by
its output.

## 9. Cost

Fixed infrastructure is ~$0/month by design — Lambda's always-free tier, a few KB in S3 and ECR, no managed
database, no VPC, no NAT gateway, no provisioned concurrency. The only spend is Bedrock tokens, and at v0.1
volumes that is cents.

Guardrails, all already required by `.claude/rules/aws-and-cost.md`: the $20 budget with the $5/$10/$20
ladder is armed; Cost Anomaly Detection is **still owed and lands in this phase's Terraform**; CloudWatch log
retention is set explicitly because the default never expires.

**The Lambda timeout is a cost control, not just a reliability setting.** AWS bills the full duration of a
streamed response even when the client disconnects, so a visitor who triggers the loop and closes the tab
bills the whole timeout. Set it as tight as the workload allows — start at 30s and measure.

Token cost goes to CloudWatch from the first call, so phase 4 has measured numbers instead of estimates.

## 10. Genuinely uncertain

Named rather than smoothed over.

- **Which model, and US vs Global inference profile.** Cannot be settled until quota clears. It sits behind
  `build_llm()`, which is what the seam is for, but it is a real open item — and the 8/1 diagnosis sharpened
  it: if the cross-region row is restored and the on-demand row is not, a cross-region profile becomes
  mandatory rather than a cost preference. First `converse` call decides it.
- **Whether ~15 edges can produce a non-embarrassing two-sentence answer.** The corpus skews to recent
  electronic and hip-hop micro-genres, so the demo genre may not be one anyone recognizes. If so the honest
  move is to say the coverage is thin, not to pick a genre the data does not support.
- **SSE through the Lambda Web Adapter specifically.** Streaming is verified; streaming *SSE with typed
  events* through LWA is not. This is the phase's fiddliest part and the most likely source of a lost session.
- **Two-stage Terraform apply.** ECR must exist and hold an image before the Lambda can reference it. The
  ordering is known; whether it wants two workspaces, a `null_resource`, or just a documented two-command
  sequence is not decided. Simplest thing that works.

## 11. Inherited assignments discharged

From `planning/09` §6, the list that exists so nothing is lost between planning and building:

| Assignment | Where it lands |
|---|---|
| Claims-first → prose-from-claims pipeline | §4 row 1, §5.4 |
| P279/P737 validation + boundary predicate | Done 2026-07-31; boundary predicate deferred to phase 2 with the corpus |
| v1 scope + explicit not-in-v1 list; v0.1 DoD | §1, §3 |
| Graph store pick among the $0 options | §5.2 |
| Terraform vs CDK | Terraform, settled by invariant 5 |
| Judge-model choice | Phase 4. Unblocked early — the 8/1 catalog check confirmed Nova, Llama, Mistral, DeepSeek, Qwen are all in-region |
| Streaming shape + path-in-payload | §5.3 |
| Testing strategy, metric unit tests in CI from v0.1 | §8 |
| Eval build order; gold set authored before agent coding | §8 |

## 12. Order of work, once unblocked

1. `converse` smoke call, logged — as soon as the quota clears. It gates step 9 and any Bedrock spend;
   steps 2–8 do not wait for it (amended 2026-08-01, consistent with the header).
2. Hand-verify ~15 P737 PROSE edges; author the five gold cases from the same pass.
3. Ingestion → artifact + manifest, locally.
4. `GraphStore` + `InMemoryGraphStore`, with tests.
5. `Claim` + gate + metric + metric unit tests. **Before** the loop, so the gate is not shaped to fit it.
6. Tools, `build_llm`, the loop.
7. FastAPI SSE endpoint; verify streaming locally.
8. Dockerfile, Terraform, CI deploy with OIDC.
9. Public URL, end to end, cost logged.
10. Plain-English write-up of what this phase does — the cold-articulation rep, per the skill's step 7.

Steps 2 through 8 need no AWS. If the quota clears mid-build, step 1 slots in ahead of step 9.
