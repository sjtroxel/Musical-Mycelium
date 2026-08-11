# Phase 1 — Walking Skeleton (v0.1): IMPLEMENTATION

> **Plan, not an as-built record.** Written 2026-08-01, immediately before the build, per the two-layer rule
> in `CLAUDE.md`. It absorbs what phase 0 and the 2026-07-31 P279/P737 validation actually taught. This doc
> is allowed to be wrong; it is not allowed to be silently wrong — update it as reality diverges.
>
> **The AWS steps were gated; the build was not.** *(Written 2026-08-01, when all Bedrock daily-token
> quotas read 0 and support case `178545883500013` was escalated.)* The scope doc's "everything waits"
> rule dates from 2026-07-29, when the risk was an AWS account that might never materialize. That risk is
> retired: the account exists, streaming is verified by a real deploy, and model access is granted (the
> block is one quota dimension). Amended 2026-08-01 (see
> `docs/reviews/2026-08-01-fable-status-review.md` §4.1): the `converse` smoke call gates AWS spend and
> deploy — steps 1 and 9 of §12 — and steps 2–8 proceed now.
>
> **UNGATED 2026-08-11.** Quota restored; a real `converse` call made and logged; **DoD #1 closed and
> #7 unblocked**. `BedrockLLM` has been executed and all three of its guessed shapes were correct. The
> decision to proceed on steps 2–8 rather than wait is vindicated by the outcome: phases 1–3's local work
> was finished and committed before access arrived. See `ROADMAP.md` §3 and §4 for the resolution,
> including the separate Marketplace-subscription gate that followed the quota fix.
> **Still open: the loop has never run end to end against a real model, and the deployed URL has not been
> redeployed onto Bedrock.**

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

**As built, 2026-08-02. Verified streaming locally over real HTTP**, not just through `TestClient` —
`TestClient` buffers, so it proves the frames are correct and proves nothing about streaming. Under
uvicorn with `curl -N`, frames arrive incrementally in the expected order.

- **Three event types beyond the four `SPEC.md` fixes**: `tool`, `rejected`, `refused`. Additive, and
  they exist because the demo is watching the machinery work — a visitor seeing tool calls and rejected
  claims is *seeing* the grounding happen rather than being told about it afterwards.
- **A refusal is a 200 with a `refused` frame**, not a 4xx. It is a correct answer; a 4xx would tell the
  client its request was malformed.
- **`done` carries `usage`, `elapsed_seconds`, `artifact_version` and `corpus`.** The corpus block is
  Fable's §5.2 suggestion taken up: 21 edges and 28 nodes stated on the wire rather than left for a
  visitor to assume. `/health` returns the same block and gives step 8's Function URL a smoke target.
- **`elapsed_seconds` uses `time.monotonic`**, per the spike's finding that WSL2 wall-clock resync
  under-reported a run by 30%. Latency is a planned eval metric, so this is not a detail.
- **A test asserts `api/app.py` contains no logic** — no `gate(`, no `.neighbors(`, no `Claim(`, no
  `ingest` import. Invariant 6 calls an agent growing inside an HTTP handler a rewrite, so it gets a
  test rather than a convention.

**New dependency note.** `fastapi` + `uvicorn` were added now rather than up front, per the
"structure now, content when its subject exists" rule. `uvicorn` **without** `[standard]`: httptools and
uvloop are a throughput optimisation, and the binding constraint here is the 250MB image limit
(invariant 8), not per-request performance.

**`LocalLLM` (`MYCELIUM_LLM_PROVIDER=local`, the `make dev` default).** A deterministic stand-in that
walks the fixed v0.1 tool sequence and renders template prose, so the whole stack — loop, gate, SSE —
runs with no AWS account, no credentials and no spend. It is a fixture, not a model, and it says so: if
it ever starts making decisions a real model should make, delete it rather than extend it.

### 5.4 Claim model

`Claim(subject_id, predicate, object_id, source_ids, span)` exactly as `SPEC.md` §7 fixes it. Frozen dataclass.
`span` is the character range in the emitted prose that the claim underwrites, which is what makes the phase-4
claim-coverage audit possible.

**As built, 2026-08-02. There are two types, not one, and that is the load-bearing decision.**

- **`ClaimProposal(subject_id, predicate, object_id)`** is what the model may emit. It carries **no
  sources**. A model that cannot name a citation cannot fabricate one.
- **`Claim`** carries `source_ids`, and the only thing that can produce one is `gate()`, which reads the
  sources off the artifact edge. The type system enforces the boundary rather than a code review.

`span` defaults to `None` and is attached by `with_span()` at synthesis time. That is not a convenience —
at gate time there is no prose to point at, and that ordering *is* the claims-first rule.

Two structural refusals, both at construction: a `Claim` with empty `source_ids` raises (an uncited claim
is a refusal, not a claim), and a `Span` with a backwards range raises.

**Source resolution is checkable, not aspirational.** A Wikidata statement URI encodes the QID of the
entity the statement belongs to, so a citation on an `influenced_by` edge must name that edge's *subject*.
A well-formed URI pointing at some other entity is rejected — which is exactly what a plausible fabricated
citation looks like, and what a prefix check alone would wave through. Verified true across all 21 edges.

**Not built, deliberately: the contested state.** `.claude/rules/grounding-and-claims.md` makes contested
first-class, and it will need a third outcome beside approved and rejected. Nothing in the v0.1 corpus can
mark an edge as disputed, so a state nothing can produce would be speculative structure. It arrives with
the data that justifies it, in phase 2 or 6. Recorded here so its absence is a decision.

### 5.5 Deployment shape

**Built 2026-08-03 (step 8).** §10 left the two-stage apply undecided between two workspaces, a
`null_resource`, and a documented two-command sequence. **Resolved: two Terraform roots.**

```
infra/terraform/bootstrap/   LOCAL state. S3 state bucket, ECR repository, GitHub OIDC provider + role.
infra/terraform/main/        S3 backend. Lambda, Function URL, exec role, log group, budgets, anomaly detection.
```

The ordering constraint is real in two places, not one: a `package_type = "IMAGE"` function cannot be
created before an image exists at the URI it names, **and** CI cannot assume a deploy role that CI has
not yet created. A `-target` sequence solves the first and not the second. Splitting the roots makes
both an artifact of the directory layout rather than a procedure someone has to remember, and it means
the ugly ordering is executed exactly once instead of on every apply.

`main/` reads the ECR repository with a `data` source rather than a remote-state lookup, so the two
roots share no lock and `main/` can be destroyed and reapplied without touching `bootstrap/`.

Decisions inside that shape, each because the alternative is worse:

- **S3 native locking (`use_lockfile = true`), not DynamoDB.** The conventional answer adds a DynamoDB
  table to hold a single lock row. Terraform 1.10+ can hold the lock as an object in the state bucket,
  which deletes an entire resource whose only job was to protect a solo project's state.
- **The backend is a partial configuration.** The bucket name contains the account id, backend blocks
  cannot interpolate variables, and hardcoding an account id into a public repository is a small,
  permanent, avoidable disclosure. `make tf-init` resolves it from `sts:GetCallerIdentity`.
- **The execution role does not use `AWSLambdaBasicExecutionRole`.** That managed policy grants
  `logs:CreateLogGroup`, which lets the function create a replacement log group **with no retention**
  if the managed one is ever missing — quietly reintroducing the never-expire default this project has
  a hard rule against. The role gets `CreateLogStream` and `PutLogEvents` on one log group ARN.
- **`reserved_concurrent_executions = 5`.** Not to be confused with provisioned concurrency, which is
  banned because it bills whether or not anyone visits. Reserved concurrency is free and is the blast-
  radius cap on a public unauthenticated URL. It may need to be `-1` until the account's concurrency
  ceiling is raised; the variable documents that failure message verbatim.
- **The OIDC trust policy is pinned to one repo AND one branch ref.** Pinned to the repo alone, a pull
  request from a fork can mint credentials for the account. The deploy policy is scoped to specific
  ARNs, with `iam:PassRole` constrained to the one execution role and to `lambda.amazonaws.com`.
- **`deploy.yml` is `workflow_dispatch` only for now.** Bootstrap had not been applied and the Bedrock
  quota was still 0, so a push trigger would fail on every commit — and a workflow that is always red is
  a workflow that gets ignored inside a week. The `push:` block is written and commented out; enabling
  it belongs to step 9, after a live `converse` call works. **That precondition was met 2026-08-11**, so
  the reason for `workflow_dispatch` is now cost and blast radius rather than a failing call — decide it
  on those terms, not by treating the old constraint as still binding.
- **`llm_provider` is a Terraform variable, not a constant.** This is what decouples *deploying* from
  the Bedrock quota. `-var llm_provider=local` deploys a real public streaming endpoint that walks the
  graph, gates every claim, and cites real statement URIs, with no model call and no spend — proving
  the infrastructure, the grounding path, and SSE-through-LWA while every daily-token quota read 0.
  It closes five of the seven definition-of-done items in §1. **#1 was closed separately on 2026-08-11
  by a live `converse` call; #7 (measured token cost) is unblocked but not yet done, because the
  deployed function still runs `local` and its token counts are synthetic.** Invariant 7 is the reason
  flipping it is a one-flag change rather than a fork of the deployment.
- **CI gained a credential-free Terraform job.** `init -backend=false` skips the only part of `init`
  that authenticates, so `fmt -check` and `validate` run on every commit against no AWS account.
  `make check` runs the same thing.

**What the local container run does and does not prove.** `make image-run` serves the built image on
:8099 and was used to verify, on 2026-08-03, that the image starts, `/health` reports the pinned
corpus (21 edges, 28 nodes), and `/lineage?q=thrash%20metal` emits `tool`, `claim`, `path`, `token`,
`done` in order with real source URIs. That is the image and the application. **It is not evidence
about LWA**, which is a Lambda extension in `/opt/extensions` and does not run outside the Lambda
runtime. §10's "SSE with typed events through LWA specifically" is therefore still open and is step
9's first measurement, by TTFB against total — not by status code.

One bug worth recording because it costs a session and produces a working build: a uv virtualenv built
at `/build/.venv` and copied to `/opt/venv` yields `exec /opt/venv/bin/uvicorn: no such file or
directory`, because console scripts carry an absolute shebang. `UV_PROJECT_ENVIRONMENT=/opt/venv`
builds it where it will live. The image is ~256MB on disk, ~67MB compressed.

**A correction to a claim this project has been repeating.** The 250MB unzipped limit behind invariant
8 is the ceiling on **.zip deployment packages**, and it is the reason this project ships a container
at all — container images get 10GB. `docs/streaming-verification.md` describes 216MB as "comfortably
inside the 250 MB unzipped limit", which reads as though the limit applies to the image. It does not.
Image size still matters, because it is cold-start latency on a public URL with no provisioned
concurrency, but it is not a correctness ceiling and should not be described as one.

## 6. Files and modules that will change

| Path | What lands |
|---|---|
| `src/musical_mycelium/ingest/wikidata.py` | One-shot P737 fetch + type filter on both ends; writes the artifact. Runs locally, never in Lambda. **Built 2026-08-02** |
| `src/musical_mycelium/ingest/artifact.py` | Artifact + manifest writer, sha256, immutability guard, hash verification. **Built 2026-08-02** |
| `src/musical_mycelium/graph/schema.py` | **Added during the build, not in the original plan.** The artifact contract: `Node`, `Edge`, `Manifest`, `Artifact`. Lives in `graph` because `ingest -> graph` is the only safe direction |
| `src/musical_mycelium/graph/store.py` | `GraphStore` protocol + the `Direction` enum. **Built 2026-08-02** |
| `src/musical_mycelium/graph/memory.py` | `InMemoryGraphStore`, name normalisation, the memoised `default_store()`. **Built 2026-08-02** |
| `src/musical_mycelium/agent/claims.py` | `ClaimProposal`, `Claim`, `Rejection`, `GateResult`, and the deterministic `gate()`. **Built 2026-08-02** |
| `src/musical_mycelium/agent/tools.py` | `Tool` protocol, `ToolResult`, the two tools, the registry. **Built 2026-08-02** |
| `src/musical_mycelium/agent/llm.py` | `build_llm()` + `BedrockLLM` (Converse/ConverseStream) + `ScriptedLLM`. **Built 2026-08-02; `BedrockLLM` unexecuted** |
| `src/musical_mycelium/agent/loop.py` | The hand-built tool loop as an event generator; emits claims, then prose from approved claims. **Built 2026-08-02** |
| `src/musical_mycelium/api/app.py` | FastAPI app, the SSE endpoint, `/health`. Owns no logic, and a test enforces it. **Built 2026-08-02** |
| `src/musical_mycelium/eval/metrics.py` | `edge_groundedness` + `Groundedness`, plus its own unit tests. **Built 2026-08-02** |
| `src/musical_mycelium/eval/datasets/gold_v0_1.json` | Five hand-authored gold cases |
| `infra/docker/Dockerfile` | Multi-stage: uv builds the venv at `/opt/venv` from `uv.lock`, LWA copied to `/opt/extensions/`, artifact baked in via the wheel. **Built 2026-08-03** |
| `infra/docker/Dockerfile.dockerignore` | **Added during the build.** BuildKit reads this in preference to a context-root `.dockerignore`, which keeps the ignore rules out of the capped repo root |
| `infra/terraform/bootstrap/` | **Added during the build.** State bucket, ECR + lifecycle policy, GitHub OIDC provider and deploy role. Local state, applied once. **Built 2026-08-03** |
| `infra/terraform/main/` | Lambda, Function URL (`RESPONSE_STREAM`), exec role, log group **with explicit retention**, the $5/$10/$20 budgets, Cost Anomaly Detection. **Built 2026-08-03** |
| `.github/workflows/deploy.yml` | OIDC role assumption, build, push, apply, and a TTFB-vs-total streaming smoke test. `workflow_dispatch` only until step 9. **Built 2026-08-03** |
| `.github/workflows/ci.yml` | **Changed during the build.** Gained a credential-free `terraform fmt -check` + `validate` job |
| `Makefile` | **Changed during the build.** `image`, `image-run`, `image-push`, `tf-fmt`, `tf-validate`, `tf-bootstrap`, `tf-init`, `tf-plan`, `tf-apply`, `tf-destroy`. `check` now includes `tf-validate` |
| `infra/README.md` | **Changed during the build.** The first-deploy runbook, the budget-import procedure, and the destroy order |
| `docs/SPEC.md` | §5, §6, §7 filled from section 5 above |

## 7. The two tools

Deliberately two, behind the `Tool` protocol.

1. `resolve_genre(name) -> node_id | None` — string to Wikidata QID against the artifact. Returns `None`
   rather than guessing; an unresolvable genre is a **refusal**, not an error.
2. `get_influences(node_id) -> list[edge]` — one hop along `influenced_by`, each edge carrying its sources.

One hardcoded hop, no planning. The loop calls 1 then 2, emits a claim per returned edge, gates them, and
synthesizes from the survivors.

**As built, 2026-08-02.**

- **The model selects the tools; the *claims* come from tool results, not from model output.** A
  `ToolResult` carries `proposals` (the claims its data supports), `sources`, and `visited` (node ids,
  for the path event). The loop harvests all three generically and never branches on a tool's name, so
  a third tool is a registration rather than a loop edit — that is invariant 4, and a test adds a
  throwaway third tool and asserts the loop gates its proposal without modification.
- **`synthesize()` takes exactly one argument, an `ApprovedClaimSet`.** No query, no store, no
  `GateResult`, no message history — there is no parameter to leak through. The object's
  `__post_init__` rejects a labels map containing any node no approved claim mentions, so context
  cannot be smuggled in alongside the labels. A test drives a tool that proposes one real edge and one
  fabricated one, then asserts the rejected genre never appears in the synthesis prompt.
- **Refusal never calls the model.** With no approved claims there is nothing to ground prose in, so
  the refusal is a deterministic template — reliable rather than probabilistic, and free. A test
  asserts the loop does not consume a model turn on the gold case 5 path.
- **The loop is an event generator** (`ToolCalled`, `ClaimApproved`, `ClaimRejected`, `PathWalked`,
  `Token`, `Refused`, `Done`), which maps one-to-one onto §5.3's SSE frames. That is what lets the API
  layer in step 7 own no logic.
- **`MAX_TURNS = 4` is a cost control, not just a safety net.** An agentic loop re-sends its
  accumulated context every turn, so an unbounded loop is an unbounded bill.

**The model ID is configuration, not a constant.** `agent/llm.py` reads `MYCELIUM_MODEL_ID` with a
documented default rather than hardcoding an ID. **§10's open question was settled 2026-08-11:** Claude
Haiku 4.5 on the `us.` geo cross-region profile, confirmed by the first live call. It stays configuration
because the model choice is a two-way door, not because the answer is unknown.
`MYCELIUM_LLM_PROVIDER=scripted` still runs the whole stack with no AWS at all — now the free local-dev
path rather than the only available one.

**`BedrockLLM` was executed for the first time on 2026-08-11**, after being written on 08-02 against the
documentation with no way to check it. **All three shapes were correct:** single-turn `converse`,
streaming with a populated `Usage` from the trailing `metadata` event, and a real `tool_use` turn.
`_parse_converse` was factored out and unit-tested against a hand-built payload precisely so the parsing
was exercised during the block; that fixture has since been **replaced with a verbatim capture of a real
response**, which surfaced three envelope fields the documented shape had not mentioned (`role`, a
`metrics` block, and cache-token keys). None broke the parser.

**What step 1 did not prove.** It is a single turn. The loop above the seam has still never run end to
end against a real model, so real-model *behaviour* — tool selection, injection resistance — remains
untested and is tracked in the phase 3 IMPLEMENTATION doc, not here.

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

**As built, 2026-08-02.**

- **The metric does not call the gate.** It re-derives its own verdict from the artifact, because a
  measurement that asks the gate whether the gate was right measures nothing. One test asserts the two
  agree on real data; if they ever diverge, the divergence is the finding.
- **Groundedness is `None`, not `1.0`, for an empty claim set** — the vacuous-truth guard, and
  `is_fully_grounded` requires `total > 0` so the empty case cannot reach the passing branch. `__str__`
  prints "undefined (0 claims)" rather than a percentage.
- **A grounded claim needs a real edge *and* a citation that edge actually carries.** A claim can name a
  true triple and cite a statement the edge does not hold — a plausible citation on a true statement —
  and a triple-only metric scores that 1.0. That check is what keeps `edge_groundedness` from decaying
  into a lookup.
- **The gold set is validated against the pinned artifact in CI** (`tests/test_gold_set.py`), which
  discharges the standing rule adopted in `SPEC.md` §2.1. It caught a real drift on its first run: the
  gold set pinned `"v0.1.0"` while the manifest records `"0.1.0"` — the `v` belongs to the directory name
  only.
- **The suite was mutation-tested.** Four deliberate breaks — a direction-blind gate, an empty output
  scoring 100%, a gate skipping the citation-ownership check, and a metric ignoring citations — were each
  caught by between two and eight tests. Tests that have never failed have not been shown to have teeth.

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

- **Which model, and US vs Global inference profile. RESOLVED 2026-08-11.** Claude Haiku 4.5 on the
  `us.` geo cross-region profile, confirmed by the first live `converse` call. The 8/1 worry — that a
  cross-region profile might become *mandatory* rather than a cost preference if only the cross-region
  row were restored — did not materialise: both the geo and global cross-region rows came back at 5M TPM
  / 10 RPM. **The genuinely useful finding was different from the one anticipated: RPM binds, not TPM.**
  10 requests per minute against 5M tokens per minute means a fan-out workload exhausts requests first,
  which makes throttling and backoff a phase 4 design input rather than a tuning detail.
- **Whether ~15 edges can produce a non-embarrassing two-sentence answer.** The corpus skews to recent
  electronic and hip-hop micro-genres, so the demo genre may not be one anyone recognizes. If so the honest
  move is to say the coverage is thin, not to pick a genre the data does not support.
- **SSE through the Lambda Web Adapter specifically.** Streaming is verified; streaming *SSE with typed
  events* through LWA is not. This is the phase's fiddliest part and the most likely source of a lost session.
  **Still open after step 8** — running the container locally exercises uvicorn and the app, not the
  adapter, which only runs under the Lambda runtime. Step 9 settles it by TTFB against total.
- ~~**Two-stage Terraform apply.**~~ **Resolved 2026-08-03: two Terraform roots, `bootstrap/` and
  `main/`.** See §5.5. It turned out the ordering constraint was two constraints — the image must
  precede the function, *and* the OIDC role must precede the CI job that assumes it — which is what
  ruled out a `-target` sequence.
- **Whether the hand-armed budgets import cleanly.** `main/cost.tf` declares the $5/$10/$20 ladder that
  was created outside Terraform, and the import only works if the existing names match
  `musical-mycelium-monthly-{5,10,20}`. The names are not known without credentials. Procedure, both
  branches, in `infra/README.md`.
- **Whether `reserved_concurrent_executions = 5` applies on this account.** AWS refuses any reservation
  that drops unreserved concurrency below 100, which a new account's default ceiling can trigger. The
  fallback is `-1` and the budget ladder.

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
   **DONE 2026-08-11.** Quota restored; Claude Haiku 4.5 returned `Usage(input_tokens=10,
   output_tokens=5)` on the `us.` geo cross-region profile. Steps 2–8 had all completed by then, which
   is the amendment paying out — this step landed last rather than first and cost the build nothing.
2. Hand-verify ~15 P737 PROSE edges; author the five gold cases from the same pass.
3. Ingestion → artifact + manifest, locally.
4. `GraphStore` + `InMemoryGraphStore`, with tests.
5. `Claim` + gate + metric + metric unit tests. **Before** the loop, so the gate is not shaped to fit it.
6. Tools, `build_llm`, the loop.
7. FastAPI SSE endpoint; verify streaming locally.
8. Dockerfile, Terraform, CI deploy with OIDC. **Authored and validated 2026-08-03; nothing applied.**
   The image builds and runs; both Terraform roots pass `fmt -check` and `validate`; CI enforces both
   on every commit. Everything past this point needs credentials.
9. Public URL, end to end, cost logged. **Runbook in `infra/README.md`.** First real measurement is
   TTFB against total on the deployed URL, which is also what closes the last §10 uncertainty.
10. Plain-English write-up of what this phase does — the cold-articulation rep, per the skill's step 7.

Steps 2 through 8 need no AWS. If the quota clears mid-build, step 1 slots in ahead of step 9.

**What actually happened:** the quota did not clear mid-build. It cleared on 2026-08-11, after steps 2–8
were complete and after phases 2 and 3's local work had shipped on top of them, so step 1 ran last of all.
The ordering rule was never exercised and the plan still worked, because the thing it protected — not
serialising the whole build behind an external dependency — was the part that mattered.
