# Phase 5 — SPA and Visualization (v0.5): IMPLEMENTATION

> **As-built plan.** Written 2026-08-24, immediately before phase 5 is built, per `CLAUDE.md`. It absorbs
> what phases 0–4 actually taught. The scope doc is [`phase-5-spa-and-visualization.md`](phase-5-spa-and-visualization.md),
> written 2026-07-30 — before the corpus, the agent, the eval suite, or a single Bedrock call existed. It
> is the oldest unamended plan in the repo and §1 below says where it has gone stale.
>
> **Status: APPROVED 2026-08-24 by sjtroxel. Step 0 — the Bedrock redeploy — is next.**
>
> Nine decisions were made point by point at approval and are recorded in §4 and §3: the static graph data
> path, two origins rather than CloudFront fronting the API, the spend posture, the five-chip row, the
> paired refusal chip, previews for both the engine and the time axis, and the checkpoint after step 2.

## 1. What this phase delivers, in one sentence

A public CloudFront URL where a music-curious visitor clicks a chip, watches a cited lineage stream in
from a **real model on Bedrock**, and can then wander the graph it came from — with the corpus's thinness
visible rather than disclaimed.

The clause that is new relative to the scope doc is **"from a real model on Bedrock."** That is inherited
work, not SPA work, and it is step 0.

## 2. Where the scope doc has gone stale

Four places. None of them invalidate it; all four change what the first steps are.

### 2.1 It does not know it inherits the Bedrock redeploy

Phase 4 closed DoD #8 as **partial** on 2026-08-24 and deferred the redeploy here, on the reasoning that
phase 5 needs a live backend anyway so the auth-and-throttling decision gets made once. The scope doc
predates that decision by 25 days and does not mention it.

This is the highest-priority item in the phase by `ROADMAP.md` §1's own ordering — priority 2 is *a
deployed URL plus real eval numbers*, the eval numbers closed on 2026-08-24, and this is the other half.
**It goes first** (his call, 2026-08-24), and until it lands the resume line stays unclaimable.

### 2.2 "the subgraph the API already returns" — the API does not return a subgraph

The scope doc says graph visualization renders *"the subgraph the API already returns"* and that surface B
*"falls out of rendering a graph the API already returns."* Verified against the repo: `api/app.py`
registers exactly **two routes**, `/health` and `/lineage`. Neither returns a subgraph.

What `/lineage` streams is a *trace*: `plan`, `tool`, `claim`, `rejected`, `path`, `token`, `done`. A
client can reconstruct the walked path and the approved claims from that, which is enough for **DoD #3**
(render the returned subgraph, highlight the walked path in order). It is **not** enough for **DoD #4** —
pan, zoom, **follow an edge** — because following an edge to a node the query never touched requires
neighbour data the stream never sent.

`GraphStore.neighbors(node_id, direction)` has existed since phase 2. Nothing exposes it over HTTP.
Resolution is §4.2.

### 2.3 The chip set it assumes is mostly unbuildable

The scope doc promises *"5–7 canonical query chips"* and points at `SPEC.md` §2.2 for the set. Of the six
rows there, **one answers** (blues → heavy metal), **one refuses correctly and deliberately** (Kate Bush),
and **four are blocked on phase 6's second source** (Detroit techno, bebop, Jamaican ska, tropicália).

So the chip row cannot be filled from §2.2. It has to be filled from §2.1's validated five plus the two
working §2.2 rows, and §2.1 was authored to be *deliberately boring* — "Where did trip hop come from?" is
a correct gold case and a weak chip. Resolution is §4.3.

### 2.4 Two of its four "key decisions" are already made

- **"The imagined user — `SPEC.md` §4, left open on purpose and due here."** Answered 2026-08-24: **a
  music-curious adult.** No music theory assumed, no Wikidata literacy assumed, every genre gets a
  one-clause gloss, and `P737` never appears on screen. `SPEC.md` §4 gets updated in step 2.
- **"Whether time is a spatial axis."** Still open and still this phase's call — but it is no longer a
  free choice. The largest component holds **458 nodes**, and force-directed placement of 458 nodes is the
  mush `planning/06` §5.2 warns about. The layout previews in step 5 decide it against real data.

## 3. The step sequence

Eleven steps. The fence the scope doc asks for is the ordering itself — **engine, then layout, then
palette, then motion** — and the fact that the guided tour is v1.0.

| # | step | closes | needs money |
|---|---|---|---|
| 0 | **The Bedrock redeploy** and its spend guardrails | phase 4 DoD #8; the resume line | **yes** |
| 1 | S3 + CloudFront + deploy job, serving a placeholder | DoD 8 | pennies |
| 2 | SPA skeleton: first screen, chips, streaming answer, citations inline, refusal staging | DoD 1, 2, 5, 10 | no |
| — | **CHECKPOINT — an explicit decision to continue, not a soft intention** | — | no |
| 3 | The rendering engine decision, via throwaway previews | — | no |
| 4 | The graph data path and the first real render | DoD 3 | no |
| 5 | Layout previews; **whether time is a spatial axis** | — | no |
| 6 | Palette previews (via the `dataviz` skill) | — | no |
| 7 | Motion previews; `prefers-reduced-motion` | DoD 6 | no |
| 8 | The explorable map — pan, zoom, follow an edge, annotate | DoD 4 | no |
| 9 | Coverage rendered honestly | DoD 7 | no |
| 10 | Favicon, logo, `v0.5.0` tag, KNOWN-GAPS, plain-English writeup | DoD 9 | no |

**Steps 0–2 are the whole of priority 2.** If the phase stalls after step 2, the deployed URL is real, the
resume line is true, and a recruiter has something to click. Everything from step 3 on is priority 3. That
split is deliberate and it is the answer to the scope doc's first named risk.

**The checkpoint is a step, not a mood** (decided by sjtroxel 2026-08-24). At that point the phase stops
and the question is asked out loud: continue into the design work, or bank priority 2 and let the job
search have the time? `ROADMAP.md` §1 already says how to answer it on a tired week — *on a tired week, 2
beats 3, and 1 beats both*. Writing the checkpoint into the sequence means that ordering gets applied
deliberately rather than discovered three weeks into a palette.

## 4. The decisions this doc makes

### 4.1 CloudFront serves the SPA. It does NOT front the API.

Two origins, two hostnames: the SPA on CloudFront over an S3 bucket, and `/lineage` called directly on the
existing Lambda Function URL.

The alternative — putting the Function URL behind CloudFront as a second origin under a path pattern —
buys same-origin requests and no CORS, and costs an unverified assumption about whether CloudFront
preserves SSE framing end to end. **Invariant 9 is a one-way door that cost a whole verification spike to
establish** (`docs/streaming-verification.md`: TTFB 0.214s against 10.22s total, a 48x ratio). Introducing
an untested intermediary in front of it is the one place in this phase where a wrong call is expensive.

CORS is already provisioned for exactly this shape. `infra/terraform/main/variables.tf` says so in its own
words:

> `["*"]` while the only client is curl and the eventual SPA has no domain yet. **Narrow this to the
> CloudFront domain when phase 5 ships a frontend** — CORS is not a security boundary for a public
> read-only endpoint, but a wildcard that outlives its reason is how one stops being noticed.

So step 1 narrows `cors_allowed_origins` from `["*"]` to the CloudFront distribution domain. That is a
**variable value**, not a backend edit, and DoD #9 survives intact.

### 4.2 The whole graph ships to the browser as a static asset

**Measured: `artifacts/v0.5.0/graph.json` is 640 KB raw and 56 KB gzipped.** That is smaller than a
typical JS bundle. The corpus is 973 nodes and 950 edges and it is not going to grow inside this phase —
the artifact pin is `v0.5.0`, unchanged, and phase 6 is the next cut.

So: publish the pinned artifact to the SPA's S3 bucket alongside the app, fetch it once, and let the map
be entirely client-side. This is chosen over the two alternatives:

- **Add a `/neighbors` or `/subgraph` route.** Thin transport over an existing `GraphStore` method, and
  defensible — but it is an edit to the backend made to accommodate the frontend, which is exactly what
  DoD #9 forbids. Phase 2 had to state honestly that `gate()` was edited once; there is no reason to
  volunteer for the same footnote when a better option exists.
- **Confine wandering to what a `/lineage` run returned.** No backend edit, but it guts surface B: you can
  only walk where the agent already walked, which is not an explorable map.

What the static artifact buys beyond DoD #9: **pan, zoom and follow-an-edge cost zero Lambda invocations
and zero dollars**, and they are instant rather than round-tripping to a cold function. That is directly
in service of DoD #5 — the frontend loads and responds instantly even when the agent takes twenty seconds.

**The agent stays the only source of claims.** The static graph is for *navigation*; the moment a visitor
asks a question — "request an annotation", DoD #4 — it goes to `/lineage` and comes back through the gate
like everything else. Rendering an edge from the static file is not narrating it, and the SPA must never
present an unqueried edge as a claim. That distinction is the invariant-1 surface of this phase and it
gets a test in step 8.

### 4.3 The chip row, resolved

**Five chips. Four answer outright; the fifth is a paired chip that refuses and then answers.** Decided by
sjtroxel 2026-08-24 across two calls — first six chips with one refusal rather than seven with two, then
the Kate Bush pair merged into a single chip.

| # | chip | source | why it is on the screen |
|---|---|---|---|
| 1 | "How is the blues connected to heavy metal?" | §2.2 | The signature demo. Two hops, both gated and cited, and the strongest argument in the corpus for the project's thesis |
| 2 | "Where did acid jazz come from?" | §2.1 | The showpiece fan-out — four parents, the richest node in the artifact |
| 3 | "Where did trip hop come from?" | §2.1 | A boring middle. `.claude/rules/evals.md` requires them in the gold set for a reason and the same reason applies here |
| 4 | "Where did Western swing come from?" | §2.1 | The second boring middle, and it carries the taxonomic-first-sentence trap |
| 5 | **"Kate Bush"** — paired | §2.2 + phase 3 | One click, two beats: *who influenced her* refuses, then *who did she influence* answers with seven cited claims. §4.5 |

**Two consequences of these calls, recorded rather than glossed.**

- **The resolved-but-unsourced refusal shape is not on the first screen.** The dropped seventh chip was
  "Where did the blues come from?" — the shape where the system *knows* the node, cites it elsewhere in
  answers, and still declines. 13 of the artifact's nodes are in that position and the gold set carries
  the shape deliberately because it is the stronger of the two. Kate Bush is the *wrong-direction*
  refusal. The first screen now demonstrates one shape, not both. This is a deliberate product call about
  what a non-technical visitor should meet first, not a gap in the system.
- **Five is the floor of `SPEC.md` §2.1's "5–7" range**, and it landed there as a side effect of merging
  the pair rather than as a count decision. A sixth slot is open. If step 2 wants one, "Who influenced
  U2?" answers with six gated claims and would put a recognisable name on the screen — but it is not
  needed for the DoD and does not block.

**Every chip is validated against the pinned artifact before it ships**, per the standing rule adopted
2026-08-02, and the check becomes a test so a corpus change fails the build rather than a demo.

### 4.5 The refusal must not read as a broken app

Raised by sjtroxel 2026-08-24 and it is the correct product concern: a casual visitor's first read of a
declined answer is *this thing is broken*. Hiding refusals entirely is not the answer — a system that
always answers is indistinguishable from one that invents — so the refusal is staged instead. **Five
requirements, and they are testable rather than aspirational.**

1. **No error chrome, ever.** Same card, same typography, same weight as a successful answer. No red, no
   warning glyph, no empty state, no "0 results". Inheriting error styling loses the argument before a
   word is read.
2. **Show what the graph does know.** Kate Bush resolves and carries **seven incoming edges**. The screen
   shows her node as connected and lists the artists who cite her. "Cannot answer" is a broken app;
   "here is what the sources record, and it runs the other way" is an answer about the evidence.
3. **The gap is attributed to the sources, not the software.** "Wikidata records nobody as having
   influenced Kate Bush." That sentence is the project thesis in miniature — most connections are not
   written down in one place.
4. **No dead end is reachable.** The pairing makes this structural rather than a matter of good copy: one
   click runs the refusal and then the answer, so a refusal is never the last thing on screen.
5. **It is never a negative claim.** "Nobody influenced Kate Bush" is false and this corpus cannot support
   it — 542 of 973 nodes have no outgoing edges, so a missing edge is overwhelmingly not evidence of a
   missing influence. The copy says what is *recorded*, never what is *true*.

This is **DoD item 10** and it is the one piece of frontend copy that carries an invariant.

### 4.4 Spend guardrails for a billable public URL

This is the part of step 0 that is not a deploy step. Today the URL is free to abuse because the provider
is `local`. Afterwards it is not.

- **Auth stays off.** The scope doc is explicit: public, read-only data, statelessness is an invariant.
  Adding auth to a portfolio demo defeats its only purpose. The exposure is bounded by concurrency,
  timeout and budget instead of by a credential — which is what `lambda.tf` already says it does.
- **The timeout is the exposure, and it is a cost control.** AWS bills the *full function duration* on a
  streamed response even when the client disconnects. Default is **30s**. Step 0 measures a real
  end-to-end `/lineage` run against Bedrock and **tightens it to the measured p99 plus headroom**, rather
  than leaving it at a number chosen before the loop existed.
- **Reserved concurrency must be re-checked.** The variable defaults to `5`, but the 2026-08-03 apply
  found this account's entire concurrency ceiling was **~10**, so a reservation of 5 was refused and the
  stack runs at `-1`. Step 0 re-tests whether a real reservation now applies; if it still does not, that
  is recorded rather than assumed, and the budget ladder carries the load.
- **Budget ladder is already armed** at $5/$10/$20 with Cost Anomaly Detection. No change needed; verified
  before the redeploy, not after.
- **CloudWatch cost telemetry already exists** — `api/telemetry.py` emits per-query cost as EMF on every
  `done`. It has never run against real usage because the deployed provider is `local`. Step 0 is what
  makes it real, and that is precisely what closes phase 4 DoD #8's open clause.

**Measured basis for the risk:** a live tier 1 run cost about **$0.36 for 41 cases**, so a single query is
comfortably under a cent. A thousand curious visitors is single-digit dollars, and the budget alarm fires
long before anything interesting happens.

## 5. One-way doors this phase touches

Seven of the nine are untouched. Two are, and neither is being reversed.

| door | touched? | how it is satisfied |
|---|---|---|
| 1. Claims first, prose second | **yes** | The SPA renders claims from `claim` frames and prose from `token` frames. It must never compose prose from the static graph, and never render an unqueried edge as a claim (§4.2). Tested in step 8 |
| 2. Provenance on every edge | no | Read-only consumer |
| 3. Validated graph semantics | no | P279 still not ingested |
| 4. Agent-to-data tool contract | no | **No tool is added and the loop is not edited.** If the SPA needs a tool, a seam broke, and that is the finding |
| 5. Everything in Terraform | **yes** | S3, CloudFront, OAC, and the deploy job are all Terraform. `terraform destroy` must still remove the frontend. Verified in step 10 |
| 6. Package boundaries | no | `web/` is a new top-level directory, already reserved. No Python package changes |
| 7. LLM provider seam | no | Step 0 flips `llm_provider` from `local` to `bedrock` — that is the seam being *used* as designed, which is the opposite of violating it |
| 8. Lambda container image | no | Unchanged |
| 9. Response streaming | **yes, and protected** | §4.1: CloudFront does not front the API, specifically so the verified streaming path is not disturbed |

## 6. Files and modules that change

```
web/                                    ALL new. Vite + React + TS. package.json NEVER reaches the root
  package.json, tsconfig.json, vite.config.ts, index.html
  src/                                  app, chips, stream client, graph view, coverage panel
  previews/                             throwaway preview files for steps 3, 5, 6, 7 — gitignored
infra/terraform/main/
  frontend.tf                           NEW: S3 bucket, OAC, CloudFront distribution, bucket policy
  placeholder.html                      NEW: step 1's placeholder, shipped by Terraform. Deleted at step 2
  variables.tf                          cors_allowed_origins narrowed; timeout_seconds retightened
  outputs.tf                            CloudFront domain name
infra/terraform/bootstrap/
  oidc.tf                               NOT ANTICIPATED — see the step 1 as-built note in §12. The deploy
                                        role names its ARNs explicitly, so main/ cannot create a bucket
                                        or a distribution until bootstrap grants it. Applied LOCALLY.
.github/workflows/deploy.yml            add the web build-and-sync job
docs/SPEC.md                            §4 answered (imagined user); §2.2 chip row resolved
docs/phases/phase-5-...-IMPLEMENTATION.md   this doc, kept as the as-built record
docs/KNOWN-GAPS.md                      updated at the release step
docs/spa-explained.md                   NEW: the plain-English write-up, written as we go
```

**Backend Python is not edited.** If that turns out to be false, it gets recorded here as a named
exception the way phase 2 recorded its `gate()` edit — not quietly done.

**Root entry count stays 15.** `web/` already exists and is already counted.

## 7. How this is tested

The eval suite does not measure a frontend, and pretending otherwise would be decoration. What applies:

- **Tier 1 is unchanged and must stay green.** `make check` is 1170 passed / 0 skipped / 7 deselected
  today. No phase 5 change may move it except by adding tests.
- **The chip row gets a deterministic test** — every chip resolves against the pinned artifact, or is a
  declared coverage-honesty refusal. A corpus change breaks CI rather than a demo (standing rule,
  2026-08-02).
- **A test that the SPA cannot narrate the static graph** (§4.2). This is the invariant-1 guard and it is
  the one frontend test that is genuinely load-bearing. Written to fail first, then made to pass.
- **Frontend unit tests are thin on purpose** — the stream parser and the claim/prose separation, not
  component snapshots. The frontend is a two-way door; over-testing a thing designed to be thrown away
  twice is waste.
- **Step 0 re-runs `make eval-live` once** after the redeploy, to confirm the deployed configuration
  produces the same numbers as the local one. That is a **spend** and it goes behind the existing
  confirmation prompt.
- **`terraform destroy` then `terraform apply`** at step 10, because invariant 5 says the off-switch must
  be real and a frontend is the easiest thing to accidentally make un-destroyable.

## 8. Cost impact

| item | cost | guardrail |
|---|---|---|
| S3 (SPA + artifact, well under 10 MB) | pennies | — |
| CloudFront | free tier covers 1 TB/month out | — |
| Lambda invocations | free tier, 1M/month | reserved concurrency, ~10 account ceiling |
| **Bedrock behind a public URL** | **under a cent per query, measured** | tight timeout, concurrency cap, budget ladder at $5/$10/$20 |
| `make eval-live` once at step 0 | ~$0.36 | existing confirmation prompt |

Fixed monthly cost stays approximately $0. **No always-on resources are added.** CloudFront and S3 are
usage-billed, there is still no database, no VPC and no NAT gateway.

## 9. Named uncertainties

Stated as uncertain rather than smoothed over.

1. **Whether a 458-node component renders legibly at all.** The largest component is 458 nodes and the
   whole graph is 973 in 169 components. Nobody has drawn this yet. It is plausible the honest answer is
   that the map shows a *neighbourhood* rather than the graph, and that would be a finding rather than a
   failure. Step 4 draws it before step 5 designs around it.
2. **Whether the engine choice survives contact.** `planning/06` §6 argues WebGL because v1.0's signature
   moment wants smooth camera work at scale. But 973 nodes is small, and canvas would be materially less
   work. The previews in step 3 decide it, and **the decision is recorded with its reasoning either way**
   because v1.0 inherits it and cannot cheaply revisit it.
3. **Time as a spatial axis may not survive the data.** 28 of 169 genres carry no inception date and the
   artist axis carries none at all. An axis anchored to chronology has to put 804 undated artist nodes
   somewhere, and "somewhere" is a design problem that could sink the idea. Measure in step 5.
4. **Reserved concurrency may still be un-settable** on this account (§4.4). Unknown until step 0 tries.
5. **Cold start behind a real model is unmeasured.** TTFB was 0.214s on the stub. Bedrock adds a real
   model call before the first token, and the "loads instantly" promise in DoD #5 is about the *frontend*,
   not the answer — but the gap between them is now visible to a visitor for the first time.
6. **The `dataviz` skill's palette work has never been run in this repo.** `planning/06` §4 says load it
   and do not hand-roll a palette. Step 6 is the first time that instruction gets exercised here.

## 10. Definition of done

The scope doc's nine, unchanged, plus one inherited item that the scope doc could not know about.

0. **`llm_provider = bedrock` on the deployed stack**, per-query cost reaching CloudWatch, and the resume
   line "deployed on AWS Lambda and Bedrock with a deterministic groundedness gate at 100%" **true**.
1. A public CloudFront URL loads the SPA and the first screen renders a search box with the canonical chips.
2. Clicking a chip streams a cited lineage, with citations appearing as claims are made.
3. The graph renders the returned subgraph and highlights the walked path in the order it was walked.
4. The map is explorable: pan, zoom, follow an edge, request an annotation.
5. The frontend loads instantly even when the agent takes twenty seconds to think.
6. `prefers-reduced-motion` is respected.
7. Coverage is visible in the interface, not disclaimed in a footnote.
8. `web/` contains the entire frontend and the root entry count is unchanged.
9. The backend was not edited to accommodate the frontend — or the exception is named here.
10. **A refusal renders as an answer about the evidence, never as an error** — no error chrome, the node's
    real connections shown, the gap attributed to the sources, no reachable dead end, and no negative
    claim. §4.5.

## 11. Explicitly not in this phase

The guided tour and the synchronized narration-and-camera moment — **v1.0, and pulling them forward is how
v0.5 becomes v1.0 with no eval work in between.** No new agent capability, no new tool, no new corpus, no
new metrics, no new artifact cut. No auth. No custom domain. No geographic-diffusion view (`planning/06`
§5.4 — a second view over the same graph, and it belongs with phase 6's density work). No trend view over
historical eval runs (phase 7 DoD #4).

**And one that is easy to smuggle in:** phase 6's second source. Four of the six aspirational chips are
blocked on it, the temptation to fix that from inside this phase will be real, and it is a corpus job that
would invalidate the pin every published eval number depends on.

## 12. As-built record

Per-step notes get appended here as the phase is built, the way phases 2, 3 and 4 did. The doc is allowed
to be wrong; it is not allowed to be silently wrong.

### Step 0 — the Bedrock redeploy — DONE 2026-08-24

Deploy run `32780499772` via `deploy.yml`, `llm_provider=bedrock`, `reserved_concurrency=-1`, image built
from `main` at dispatch. Verified from the `done` frame rather than inferred: `model_id`
`us.anthropic.claude-haiku-4-5-20251001-v1:0`, traversal usage 6,700/349, synthesis 90/12,
`stop_reason: complete`, plan adherence 2/2. Streaming TTFB **0.242s** against **6.41s**, ratio **0.038**.
Four EMF records in `MusicalMycelium`. **DoD 0 met; phase 4 DoD #8 fully closed; the resume line is true.**

**Four things this doc got wrong or did not know, recorded because they cost real risk:**

1. **§4.4 said the flip was environment-variable only. It was not.** The deployed image was `deaa548`
   from 2026-08-06 — **37 commits stale, predating `700bad3`, the multi-tool-turn fix.** Flipping that
   image to `bedrock` would have deployed a loop that breaks on any multi-tool turn: green `/health`,
   broken `/lineage`. Caught by reading `terraform plan` before applying, because the plan wanted to move
   `image_uri`. **The lesson is not "check the image" — it is that a plan carrying more changes than you
   predicted is the signal, and the fix is to read it rather than to reconcile it.**
2. **A hand `terraform apply` was the wrong path and CI was the right one.** `deploy.yml` already passed
   all three load-bearing vars, tagged with the git sha for traceability, and smoke-tested the stream.
   The hand-apply would have taken `reserved_concurrency`'s default of 5 against a ~10 account ceiling
   and failed **after** mutating the function.
3. **The smoke test cannot catch a synthesis regression.** It queries a bare noun (`thrash metal`), and
   both its calls emitted a traversal EMF record and **no synthesis record** — nothing was narrated. The
   streaming ratio passes anyway because TTFB is the `plan` frame. Confirmed live: the planner returns
   `query_kind: "coverage"`, approves two claims, emits `refused`, and never synthesises — **correct loop
   behaviour on a query that asks nothing**, and a badly chosen gate query. Owed: a real question as the
   smoke query, with the coverage-shaped one kept as a second check rather than discarded.
4. **The buffering assertion warns rather than fails**, and the `/lineage` calls omit `curl -f`, so a 500
   would pass too. A green smoke test does not prove streaming; the numbers did.

Items 3 and 4 are logged in `docs/KNOWN-GAPS.md` and are not fixed here — they are deploy-pipeline
defects rather than step 0 blockers, and fixing a check in the same breath as trusting it is how a check
gets fitted to the result it just produced.

### Step 0 follow-up — the smoke test, fixed 2026-08-25

A separate session, deliberately, for the reason the paragraph above gives. Items 3 and 4 are both closed
in `deploy.yml`: the smoke query is now chip 1 (*"How is the blues connected to heavy metal?"*) and the
step asserts `claim`, `token` and `done` frames in the body; the coverage-shaped query is kept as a second
call so the refusal path stays exercised; `r > 0.9` fails instead of warning; both `/lineage` calls carry
`-f`. Two calls became one per query, halving the Bedrock spend per deploy and computing the ratio from a
single run rather than across two.

Each lock was verified by breaking it — missing frame, 500, and a buffered response whose body contained
valid frames — and each failed as intended. **Not yet exercised against the deployed URL**; step 1's
deploy is the first real run. This matters for step 1 specifically: step 1 adds a web sync job to the same
workflow, so it inherits this smoke test as its verification.

### Step 1 — S3 + CloudFront — WRITTEN 2026-08-25, NOT YET APPLIED

`terraform fmt` and `terraform validate` pass on both roots. **Nothing has been applied**, no bucket and
no distribution exist yet, and the CloudFront domain in every output below is still a plan-time unknown.

**Three things this doc did not anticipate, recorded before they are applied rather than after.**

1. **§4.1's "that is a variable value, not a backend edit" is not achievable as written.** The CloudFront
   domain does not exist until the apply that creates the distribution, so passing it as a variable value
   needs two applies with the wildcard live in between, and the value goes stale if the distribution is
   ever replaced. `lambda.tf` reads `aws_cloudfront_distribution.spa.domain_name` off the resource
   instead — one apply, no wildcard window, no drift. There is no cycle, precisely because §4.1 decided
   CloudFront does not front the Function URL. Still a Terraform edit rather than a Python one, so
   **DoD #9 is intact**; the deviation is in the *mechanism*, not the boundary.

   `cors_allowed_origins` is gone, replaced by **`cors_extra_origins`** defaulting to `[]`. What is left
   for a variable is the exception — a Vite dev server on localhost calling the deployed backend — and it
   now has to be asked for out loud.

2. **§6's file list is incomplete: `infra/terraform/bootstrap/oidc.tf` changes too, and it is applied by
   a different identity.** The OIDC deploy role names its ARNs statement by statement on purpose, so it
   cannot create an S3 bucket or a CloudFront distribution until bootstrap grants it. **`bootstrap` is
   applied locally with an admin credential, not by CI** — which collides with the standing rule in
   `.claude/rules/aws-and-cost.md` that the `mycelium-dev` key is time-boxed and deleted after use. A key
   has to exist for this step. The CloudFront invalidation verbs step 2 will need are therefore included
   **now**, so this is one bootstrap apply rather than two.

   The grants follow the two shapes already in that file, and they are opposite trades made for opposite
   reasons: `s3:*` scoped to the one SPA bucket ARN (the `LambdaFunction` statement's argument — the
   provider's read path alone calls a dozen `Get*` actions nothing in the config mentions), and an
   **enumerated** CloudFront action list on `*`, because CloudFront supports no resource-level
   permissions for `CreateDistribution` and none at all for Origin Access Controls. Where resource
   scoping is unavailable the action list has to be the bound.

3. **The bucket lives in `main/`, not `bootstrap/`, unlike the state and artifact buckets.** Those are
   records that must outlive a teardown. The frontend is the application, and invariant 5 says
   `terraform destroy` on `main/` has to take it with it — §7 already names a frontend as the easiest
   thing to accidentally make un-destroyable. `bootstrap` mirrors the bucket *name* only, to scope the
   grant, the same coupling that file already documents for the function and log group.

**What step 1 does not do.** No `deploy.yml` web sync job — Terraform ships `placeholder.html` directly,
so `terraform apply` alone produces a working URL with no build step involved, which makes the
destroy-then-apply check §7 demands a single operation. Node, Vite and the sync job land in step 2 when
there is a real build to sync, and `aws_s3_object.placeholder` is deleted in the same commit. If that
resource still exists when the SPA ships, something was skipped.

The distribution carries `custom_error_response` for 403 and 404 already, before there is a single route
to deep-link to: it is a property of the distribution rather than of the app, and a distribution update is
a slow thing to discover you need. 403 is there alongside 404 because a private bucket answers a missing
key with `AccessDenied` — S3 will not confirm that an object it will not serve you also does not exist.

**Order of operations when this is applied:** `bootstrap` locally first, then `main` via `deploy.yml`. A
`main` apply before the bootstrap one fails on `s3:CreateBucket`, and per step 0's own lesson the first
sign will be a plan carrying more changes than expected — read it rather than reconcile it.

**Still open from step 0, by decision:** `timeout_seconds` stays at 30. Two observed runs at 7.4s and
6.4s give roughly 4x headroom, and two samples is not a p99. It tightens from real CloudWatch
`ElapsedSeconds` once there is traffic.

### Step 1 — S3 + CloudFront — APPLIED 2026-08-26

Live at **`https://d2vtdkpgmecreg.cloudfront.net`**, bucket `musical-mycelium-web-178870257607`. Deploy
run `32979468111`, 1m49s, image built from `main` at `01b9cfed7bee`.

**Order as the previous section specified: `bootstrap` locally first, then `main` via `deploy.yml`.** The
bootstrap plan was `0 to add, 1 to change, 0 to destroy` — `aws_iam_role_policy.github_deploy` in place
and nothing else, which is the whole of what `01b9cfe` added to that root. Applied with `mycelium-dev`,
which was still live from a previous session.

The `main` plan was **6 to add, 2 to change, 0 to destroy**:

- created: `aws_s3_bucket.spa`, `aws_s3_bucket_public_access_block.spa`,
  `aws_cloudfront_origin_access_control.spa`, `aws_cloudfront_distribution.spa`,
  `aws_s3_bucket_policy.spa`, `aws_s3_object.placeholder`
- updated in place: `aws_lambda_function.app` (new image digest) and `aws_lambda_function_url.app`

**That second in-place update is the §4.1 deviation working.** Because `lambda.tf` reads
`aws_cloudfront_distribution.spa.domain_name` off the resource rather than taking it as a variable value,
the Function URL's CORS origin picked up the real CloudFront domain in the *same* apply that created the
distribution. One apply, no wildcard window, nothing to remember to come back for.

**Verified after the apply, not assumed:**

| check | result |
|---|---|
| CloudFront root | `200`, `content-type: text/html; charset=utf-8` |
| the object read directly from S3 | **`403`** — the OAC is the only read path, as designed |
| a deep link to a path with no object | `200` — `custom_error_response` returns `/index.html` |

The 403 is the one worth stating plainly: the bucket policy conditions on `AWS:SourceArn` and all four
public-access-block settings are on, so the private-bucket-plus-OAC shape is confirmed by behaviour
rather than by reading the config back.

**The smoke test ran against the deployed URL for the first time** — step 0's follow-up built it but
could not exercise it. `/health` returned the pinned `0.5.0` corpus; the real question streamed with
`claim`, `token` and `done` frames present; the coverage-shaped query took the refusal path. Timings:
**TTFB 0.170s, total 9.80s, ratio 0.017** against a `> 0.9` failure bound. The response is genuinely
incremental, not a buffered body that happens to contain valid frames.

**Two small things observed rather than predicted.**

1. `aws_s3_object.placeholder`'s explicit `content_type` earned its keep. The header came back correct,
   which is only true because it was set — the key is `index.html` while the file on disk is
   `placeholder.html`, and the provider infers from the key.
2. **The first request to the new domain failed with `Could not resolve host`, and succeeded about a
   minute later.** This is exactly the cost `wait_for_deployment = false` documents in `frontend.tf` —
   the apply reports success before the edge serves anything. Worth knowing at step 2, when a sync
   followed immediately by a fetch would look like a broken deploy.

**Unchanged by this step:** `timeout_seconds` is still 30, still awaiting real CloudWatch
`ElapsedSeconds`. The two new samples above (9.80s and 7.51s) join the step 0 pair; four samples is
still not a p99, though 9.80s is the closest anything has come to the ceiling so far.

**Next is step 2** — the SPA skeleton — and it deletes `aws_s3_object.placeholder` in the same commit
that adds the web sync job.

### Step 2 — the SPA skeleton — 2026-08-26

Closes DoD 1, 2, 5 and 10. `web/` is Vite + React 19 + TypeScript, built and synced by `deploy.yml`.
`aws_s3_object.placeholder` is gone, in this same commit, as step 1 said it would be.

**What §6's file list did not anticipate: `.github/workflows/ci.yml` changes too.** The SPA needs types,
tests and a build on every commit, and none of that shares a toolchain with the Python half. It is a
separate `web` job rather than steps inside `check` — no uv, no venv — so a frontend failure does not
read as a backend one in the checks list. §6 also listed `docs/SPEC.md` §4 as owed; §4 was already
answered on 2026-08-24, so only §2.2 needed the chip-row resolution.

**Three decisions this step made that the plan did not reach.**

1. **`EventSource` is not used, and the reason is money.** It reconnects automatically when the server
   closes the stream — which is what ends every successful `/lineage` run. On a one-shot query that
   reconnect re-runs the whole agent loop, indefinitely, in a tab someone left open. The token budget is
   the per-visitor ceiling (`.claude/rules/aws-and-cost.md`), and an auto-reconnecting client multiplies
   that ceiling by tab lifetime, which is not a ceiling. `fetch` + `ReadableStream` + `AbortController`
   gives one request and an explicit stop; the abort also fires on unmount, because AWS bills the full
   duration of a stream whose client has already hung up.

2. **The chips and the corpus figures ship as JSON, validated by Python tests.** `web/src/chips.json`
   and `web/src/corpus-facts.json` are read by the SPA and asserted against the pinned artifact by
   `tests/test_chips.py` (10 tests) and `tests/test_corpus_facts.py` (4). That is what makes 4.3's
   "validated before it ships" a build failure rather than an intention. A chip list written in
   TypeScript could not have been checked by the Python suite at all.

   **It earned itself immediately.** The blues-to-metal chip stores `start_id: Q38848` (heavy metal) and
   `end_id: Q9759` (blues) — backwards from how the label reads. `path("Q9759", "Q38848")` returns `[]`;
   the edges run descendant-to-ancestor. Writing the endpoints in the order the question suggests would
   have shipped the headline chip rendering nothing. That is the fourth instance of this project's
   named ORIGINS-direction failure mode, and the first one caught before it was written.

3. **The refusal and the answer are the same React component.** DoD 10 requirement 1 is "no error
   chrome, ever", and an absence enforced by convention decays. One component makes it structural: the
   only thing that differs is wording. There is no colour, border or weight in `.panel` that keys off
   refusal.

**Verified by breaking, per the practice adopted 2026-08-14.** Every lock here was deliberately broken,
watched to fail, and restored: the chip refusal-direction assertion (flipped to the direction with 7
edges — failed, naming the chip and the count), and both DoD 10 assertions.

**That practice found a defect in the tests themselves.** Requirements 1 and 5 were asserted inside one
test, so breaking *both* produced a single failure. One signal for two unrelated requirements says
something is wrong without saying which. They are separate tests now — and this is the argument for
breaking locks rather than reading them.

**Tested, and how little.** 29 frontend tests across four files: the stream parser (including frames
split one character at a time), the claim/prose separation, the DoD-10 absences, and a **contract test
over real captured API bytes** rather than hand-written strings — `web/src/fixtures/*.sse`, from a local
run of `api/app.py` on v0.5.0. The two halves deploy on different schedules, so a renamed field has no
other place to fail loudly. No component snapshots: the frontend is a two-way door and over-testing it
is waste (§7).

**CORS verified live, not assumed.** `https://d2vtdkpgmecreg.cloudfront.net` gets
`Access-Control-Allow-Origin`; an arbitrary origin gets no header at all. The request stays *simple* —
`Accept` is CORS-safelisted, so it never preflights, which matters because `allow_headers` is
`["content-type"]` only. Any non-safelisted header added later will preflight, fail in production, and
work perfectly in `npm run dev` where the Vite proxy makes it same-origin. Noted in `stream.ts`.

**Backend Python was not edited.** DoD 9 intact, no exception to record. The two new files under
`tests/` test data in `web/`; they add no `src/` change.

**Root entry count unchanged at 15**, as §6 required. `web/` was already counted.

**Deploy ordering, decided here:** the frontend gate (`npm ci && npm run check`) runs *before*
`terraform apply`, and the build-and-sync *after* it. The build needs `function_url`, which is an
output — but the apply in this commit deletes the placeholder, so a build that failed after the apply
would leave the public site with no `index.html` at all. Failing before it costs a red deploy and
changes nothing. The site smoke test then asserts CloudFront is serving *this* build by name, with a
retry loop, because an invalidation does not propagate instantly and a single immediate fetch tests the
previous deploy.

#### Step 2 correction, same day — the paired chip was a dead end and every free test said otherwise

**Found by sjtroxel looking at the running app, not by the suite.** He typed *"who did elvis presley
influence"*, got a refusal, and said it looked wrong. It was.

Against `make dev`'s local stub, **both** halves of the Kate Bush pair refuse — so the chip that exists
specifically to satisfy DoD 10 requirement 4 (*no reachable dead end*) was itself a dead end everywhere
the stub runs. Against Bedrock the same chip answers with **7 cited claims**, and Elvis Presley (`Q303`,
5 outgoing edges) answers with **5**.

**Cause: `LocalLLM` is a fixture that walks one fixed path** — resolve, then `get_influences`, then stop.
It has no route to `get_descendants` at all, so *every* "who did X influence?" query refuses under it
regardless of what the corpus holds. Its own docstring says it is not a model and says not to extend it,
and it has not been extended: the fix is that the limitation is now stated where someone will hit it
(`make dev`'s comment, `make dev-live` beside it, and `web/README.md`).

**Two things about this are worth more than the bug.**

1. **The free tests could not have caught it and did not.** `tests/test_chips.py` validates the chip set
   against the *corpus*, which was right about everything: the node exists, the edges run that way, the
   pairing ends on an answer *as declared*. None of that is evidence about what the agent does.
   `tests/test_chips_live.py` now closes exactly that loop — the declared expectation, checked by running
   it — and is `costs_money`, seven queries, under a dime. **It passes 7/7.**

2. **One of my own tests was constructed so it could not fail.** `App.test.tsx`'s "the pair continues to
   an answer" case stubbed the *second* response with `acid-jazz-answer.sse` — a capture of an entirely
   different question. It proved the UI renders a second panel with claims and proved nothing about the
   query it named. That is this project's named failure mode (*assertions written from a mental model and
   never executed*) appearing inside the test written to prevent it. The fixture is now
   `kate-bush-descendants.sse`, captured from Bedrock, and the test additionally asserts the panel shows
   **7** claims so a substituted fixture fails instead of passing.

**The lesson to carry, and it is not "add more tests":** a fixture that cannot perform the behaviour
under test will make the whole suite agree with itself. Before believing a green suite about agent
behaviour, ask which provider produced the evidence.

**Not changed:** the product. DoD 1, 2, 5 and 10 hold on the deployed stack, and did throughout.

### The CHECKPOINT — answered 2026-08-28: continue

Answered by sjtroxel, out loud, as §3 required: **continue into the design work.** His reasoning is that
the deployed URL on its own is not what gets a project looked at, and the design steps are the difference
between a thing that works and a thing worth posting. Priority 2 is banked and intact either way — steps
0-2 delivered it — so this spends priority 3 time deliberately rather than by drift.

Recorded because §3 said the checkpoint is a step and not a mood, and a decision that is never written
down cannot later be distinguished from having wandered past it.

### Step 3 — the rendering engine — DECIDED 2026-08-28: Canvas 2D + d3-force

**The decision is Canvas 2D with `d3-force` for layout.** Recorded with its reasoning per §9 uncertainty
2, because v1.0 inherits it and the scope doc (§142) is explicit that swapping renderers after the motion
system exists is the one expensive reversal in this phase.

Three previews were built against real corpus data and looked at on real hardware — `web/previews/`,
gitignored per §6, with `build-data.py` extracting the three targets from the pinned artifact.

| | engine | verdict |
|---|---|---|
| A | SVG + d3-force | Viable. Crisp text and DOM interactions for free; the one that dies first when motion lands on 458 nodes |
| **B** | **Canvas 2D + d3-force** | **Chosen** |
| C | WebGL — sigma 3.0.3 + graphology | Its advantage is unspent here, and it costs a test seam. See below |

**Why B.** The WebGL argument in `planning/06` §6 was scale, and the measurement removes it: the largest
component in the artifact is **458 nodes** and the demo surfaces are **3 and 31**. Canvas is comfortable
an order of magnitude above that. What canvas charges is hit-testing, drag and label placement by hand —
about **forty lines, written once, now written**. What it buys is that every bespoke visual in steps 5-7
is just drawing, with no renderer to negotiate with and no shader between an idea and the screen. Given
that steps 5, 6 and 7 are the entire remaining design arc, that is the trade worth making.

**Rejected, with reasons, so they are not re-litigated:**

- **Cosmograph — licence, not merit.** npm reports `CC-BY-NC-4.0`. A public site backing a job search is
  at best ambiguous under a non-commercial licence, and this project's pitch is correct attribution
  (`.claude/rules/graph-semantics.md`). Not evaluated further.
- **Sigma v4 — beta only.** npm `latest` is `3.0.3`; the newest v4 is `4.0.0-beta.5`. Portfolio
  infrastructure that has to stay live through a job search does not run a beta renderer.
- **Sigma 3 — a real test-seam cost, found by trying to import it.** Sigma touches
  `WebGL2RenderingContext` at **module scope**, so it throws on import anywhere without WebGL. jsdom does
  not define that symbol (verified). The existing 29 frontend tests run in vitest/jsdom, so choosing
  sigma means a WebGL stub or a mock on every test whose module graph reaches the graph component — which
  would directly weaken step 8's load-bearing test that the SPA cannot narrate the static graph. A
  renderer that has to be mocked out to be tested is the wrong renderer for the one test in this phase
  that carries weight.
- **Cytoscape.js — MIT and excellent, and redundant.** Its value is layout and graph algorithms, which
  `GraphStore` already owns server-side. A second graph engine in the browser buys nothing here.

**Dependencies are not added in this step.** `d3-force`, `d3-selection`, `d3-zoom` and `d3-drag` land in
step 4 alongside the code that imports them. Step 3's deliverable is the decision; shipping unused
dependencies to look decisive is how a `package.json` accumulates things nobody can later explain.

#### What the measurement found, and it is bigger than the engine pick

Measured from the pinned artifact before anything was drawn, to answer §9 uncertainty 1:

- **973 nodes, 950 edges, 169 components.** Largest is **458**; then 31, 13, 11, 8. No singletons.
- **The 458-node component is 100% artists and contains zero genres.**
- **Artists and genres are in disjoint components. 128 pure-artist, 41 pure-genre, ZERO mixed.**
- **The signature blues → heavy metal chip's entire component is 3 nodes** — `blues`, `blues rock`,
  `heavy metal music`. Not a slice of a larger graph; that is the whole island.
- Degree: max 25 (Sum 41, Bridgit Mendler, The Beatles), **median 1**.
- **All 141 dated nodes are genres.** All 804 artists are undated, which is §9 uncertainty 3 confirmed
  before step 5 rather than during it.

The cause is not a defect: only **P737** is ingested, and P737 does not cross the artist/genre boundary.
Genre membership is **P136**, which is not in the corpus. `CLAUDE.md` states the thesis as *"underneath
they are one connected organism"* — **on artifact v0.5.0 that is not drawable**, and the honest answer to
§9 uncertainty 1 is that the map shows a *neighbourhood*, which the uncertainty explicitly allowed for as
a finding rather than a failure. Steps 4, 5 and 9 are all shaped by this. Whether it is worth a P136 cut
is a **phase 6** question and is not smuggled into this phase (§11).

#### The process failure that nearly decided a one-way door

**The canvas preview shipped with no `d3-drag` import.** SVG imported four d3 modules; canvas imported
three. `d3.drag` was `undefined`, `d3.drag()` threw, and because drag was registered one line before
zoom, the same exception killed zoom registration too. The simulation had already started, so the page
**rendered and looked finished while being completely inert.**

sjtroxel looked at it and reported that canvas was "not as much fun to flip and drag around" as SVG. That
was an accurate report of a broken preview, and it was **about to be the reason a one-way door went the
other way.** The engine comparison was, for one round, a comparison between an engine and a bug.

Three compounding causes, all the same shape as this project's named failure mode — *assertions written
from a mental model and never executed*:

1. **The previews were handed over having never been rendered.** There was no browser on the box and I
   proceeded anyway, verifying library APIs in Node and treating that as sufficient. It was not: every
   API call was correct and the page was still dead.
2. **The first verification script produced a false FAIL** on canvas/headline once a browser existed. It
   sampled every thousandth pixel to decide whether anything had drawn, and three small circles on a
   1280x800 canvas fell between the samples. Re-run with full screenshot hashing: all nine
   engine x target combinations pass. **A checker too insensitive to see the subject is not evidence.**
3. **Headless FPS numbers are worthless here.** Software WebGL in a headless shell put SVG at 60 and
   WebGL at a worst of 20 — the reverse of what real hardware says. They were not quoted as evidence.

**Two things changed as a result.** `harness.js` now installs global `error` and `unhandledrejection`
handlers that surface any uncaught exception as the same visible banner the import failures already got —
a preview that renders but does not respond is worse than a blank one, because it looks finished. And
**playwright-core plus a headless chromium shell are now available locally** for steps 5, 6 and 7, whose
previews are the same trap again.

**The lesson, stated for the steps that follow:** a design preview is an instrument, and an unverified
instrument produces a confident wrong reading rather than no reading. Before treating a preview's feel as
evidence about an engine, confirm the preview can perform the behaviour being judged. This is the same
finding as step 2's `acid-jazz-answer.sse` fixture, arriving from a different direction, two days later.

### Step 4 — the graph data path and the first real render — DONE 2026-08-29

**DoD 3 is closed.** The pinned corpus reaches the browser, the map draws what a run returned, and the
approved connections are numbered in the order the gate approved them. Verified in a real browser on
all three chip shapes before being called done, per the step 3 lesson.

**The two calls sjtroxel made, both on 2026-08-29.** The artifact ships **verbatim, not slimmed**:
measured 640 KB raw / 55 KB gzipped against a slim shape's 20 KB, and 35 KB is not worth a second
representation of the corpus that can diverge from the pin, or losing `source_id`, which is the citation
itself and which step 8's follow-an-edge annotation will want. And the **refusal keeps a map**, strictly
bounded — same component, same code path, nothing highlighted, cut on the spot if it wants its own
anything. His framing was that visitors only care about the happy path; the counterweight recorded here
is that the Kate Bush refusal is **one of the five chips on the first screen**, not a wrong turn a
visitor stumbles into.

#### The data path

`web/scripts/stage-graph.mjs` copies the artifact into `web/public/graph/v<pin>/graph.json` as a
`prebuild` and `predev` step; the copy is gitignored. The pin is read from `chips.json`, which
`tests/test_chips.py` already validates against the corpus, so the version is written down in one place.

**`deploy.yml` needed no change, and the version-pinned path is why.** Vite copies `public/` into
`dist/`, the existing sync ships `web/dist` with `--cache-control immutable`, and a corpus cut is a new
URL rather than a stale cache. Confirmed by building: `dist/graph/v0.5.0/graph.json` is the artifact
byte for byte.

**The fetch is lazy and starts when a run starts.** `App.test.tsx`'s "makes no network request on load"
is DoD 5's guard, and 640 KB in front of first paint is exactly what DoD 5 forbids. A second test in
`graph/map.test.tsx` now asserts the same thing from the map's side, because this is the easiest thing in
the new directory to break by accident.

#### What is drawn, and the line it must not cross

Claimed and context edges are **two types in `subgraph.ts`, not one type with a style flag.** A flag is
one careless `.filter()` away from putting an ungated corpus edge in front of a visitor as an approved
one. Claimed edges come only from `claim` frames; context comes only from the static artifact, is drawn
faint, and the caption says so in words: *"shown for bearings and not part of this answer."* Step 8's
test is the formal guard; this is the structure it will test.

The arrow runs **object to subject**, the way history ran. That has its own test, and **the test was
verified by breaking it** — the direction was reversed, one test failed and only that one, then it was
restored. Same for the version guard below. This project's named failure mode is assertions written from
a mental model and never executed, and the counter-practice is to break the lock and watch it fail.

**A version guard was added that the plan did not have.** If the `done` frame's `artifact_version` is not
the version the browser downloaded, the map is not drawn at all. Every id would still resolve and the
picture would look entirely reasonable while showing a graph that was never walked, which is the
quietest way this screen could lie. One comparison.

#### Three findings from building it

1. **The refusal has no node id in it, so on the local stub it gets no map.** `kate-bush-refusal.sse`
   carries an empty `path` frame, a `refused` frame holding only a reason and the query string, and one
   `resolve_node` call whose argument is the whole question. There is no id anywhere. `chips.json` holds
   Q636 and using it would have filled the hole — and would have been the interface asserting it knew
   which node the run meant when the run never established it. **No map is the honest answer**, and it
   is what ships. Against Bedrock the same query resolves the node first and the refusal *would* draw a
   neighbourhood, which is why `toolNodeIds` exists at all.
2. **`forceCenter` is wrong for this corpus and `forceX`/`forceY` are right.** 169 disjoint components
   (step 3) means a disconnected piece under `forceCenter` drifts off screen with nothing pulling it
   back.
3. **The layout had to be fitted to the box, and that is not cosmetic.** The headline chip's whole
   component is three nodes, and a force layout of three nodes occupies a fraction of a 650x300 canvas —
   the first render put the signature demo in a tiny cluster with its labels overlapping. Positions are
   projected to fit while radii and type stay fixed, which is the thing canvas makes easy.

#### What was deliberately not done

No pan, zoom, drag or follow-an-edge (step 8). No palette work (step 6) — every colour is read from the
CSS custom properties so step 6 has one place to change. No motion (step 7), though
`prefers-reduced-motion` settles the layout without animating rather than being retrofitted later.
`d3-force` is the only dependency added: step 3 said four d3 modules would land here, and the other
three are imported by step 8's code, not this step's.

**Left for step 5, named rather than polished away:** label placement is per-node side-selection and
nothing more, so on a dense hub an ordinal can still clip the end of a label. Layout is step 5's remit
and this is its problem, not a defect to fix twice.

#### Verified

`make check` **1184 passed, 14 deselected**, mypy clean over 89 files, root 15/18, terraform valid,
eval gates unchanged at 3 passed / 0 failed / 2 not applicable — **no Python was edited in this step.**
The frontend suite is **48 passed**, up from 29. In a headless Chromium against `make dev` and the dev
server: acid jazz draws 4 cited and 10 context connections, blues-to-heavy-metal draws 2 cited and 0
context (the 3-node island, exactly as step 3 measured), Kate Bush draws no map on either panel and
raises no page error. The checker reads **every pixel** of the canvas rather than sampling, because step
3's first checker sampled every thousandth pixel and produced a confident false FAIL.

**One pre-existing 404 was found and is not step 4's:** there is no favicon, so `/favicon.ico` 404s and
Chromium logs it. That is step 10's item. It is named and skipped explicitly in the checker rather than
ignored wholesale, so the checker stays sensitive to everything else.

### Step 5 — layout — DECIDED 2026-08-30: influence depth, deterministic, no time axis

**The decision: x is influence depth, y is year within the column, and there is no simulation.**
Recorded per §9 uncertainty 3. `web/src/graph/layout.ts` is the whole of it and `GraphView` no longer
decides where anything goes.

**This was decided by me, not by sjtroxel, at his explicit request** — he was overwhelmed and asked
me to pick and record the reasoning so he could overturn it later. It is therefore a weaker decision
than step 3's, which he made by looking. **It is reversible**: the previews still describe all four
candidates, and `layout()` is one pure function behind one call site.

#### The question was wrong, and the measurement is the real deliverable

§9 uncertainty 3 and the scope doc (§51) both framed this as *"where do 832 undated nodes go"*. They
never share a map. Step 3 measured artists and genres into disjoint components; the consequence
nobody had drawn out is that **every chip renders either a pure-genre map or a pure-artist map**, so
the undated nodes are never mixed in among dated ones. There is no placement problem to solve.

Measured on what `subgraph.ts` actually draws, with `web/previews/measure-time.py`:

| chip | nodes | dated | edges |
|---|---|---|---|
| blues → heavy metal | 3 | 100% | 2 forward |
| acid jazz | 15 | 80% | 11 forward, 3 undatable |
| trip hop | 8 | 62% | 4 forward, 3 undatable |
| Western swing | 5 | 100% | 3 forward, **1 backwards** |
| Kate Bush, both panels | 8 / 16 | **0%** | all undatable |

**Two findings with consequences beyond the layout.**

1. **6 of the 102 datable edges in the corpus run backwards in time** — the object is younger than
   the thing it influenced. `electroclash (1995) -> electropop (1978)` is the worst at 17 years, and
   **one of the six is inside a chip**: `swing (1930) -> Western swing (1928)`. A force layout hides
   this. A year axis draws it as an arrow pointing left, which is the map asserting an influence
   arrived before its own cause. This is not a data defect to fix — an `inception_year` is a Wikidata
   field, not a measurement, and a genre does not begin on a date. It is a reason not to build
   geometry on top of those numbers.
2. **The three undated genres are the same three in every genre map** — Na mele paleoleo, Pinoy hip
   hop, sampledelia. Hawaiian, Filipino, and one technique. **The undated nodes are the non-Western
   ones**, which is step 9's coverage-honesty work arriving early and unasked. `layout.ts` sorts a
   missing year to the END of its column rather than treating it as year 0, with a test, because
   sorting them to the ancient end would be the map inventing dates for exactly the nodes the corpus
   is thinnest on.

#### The four previews, and why B lost

`web/previews/layout.html`, gitignored, four layouts x five real targets, switchable in the page.

| | x means | verdict |
|---|---|---|
| A | nothing — the step 4 force baseline | the control |
| B | **the year** | **rejected** — see below |
| C | influence depth, force-relaxed y | viable |
| **D** | **influence depth, year within the column** | **chosen** |

**B is rejected because it stops existing for 40% of the demo surface.** It is the better picture on
the genre chips — jazz 1917 on the left through skweee 2005 on the right reads well — and it is still
worth looking at. But not one node on either Kate Bush panel carries a date, so B silently falls back
to A there. A design system that becomes a different design system on two of six panels is worse than
one that never claimed chronology, and steps 6 and 7 would have to be built twice.

**D over C** on the value this codebase already committed to one layer down: `subgraph.ts` sorts the
context neighbourhood by label *"so the same answer draws the same map twice"*, and a settling
simulation put that straight back. D is a pure function of the graph. A screenshot in a writeup now
matches what a visitor sees, `prefers-reduced-motion` needs no branch because there is no settling
animation to suppress, and step 7's motion animates between known positions rather than racing a
simulation. Measured column widths on the five targets are 1, 11, 3, 7 and 259 — the 259 is the
whole-component stress case, which **no chip can reach** because `subgraph.ts` caps context at 40.

**Time survives as ordering, not geometry.** The dates still sort each column, oldest at the top. That
is the only claim an inception year can carry.

#### What changed in the SPA

`layout.ts` + `layout.test.ts` are new; `GraphView` lost the simulation, the position cache and the
`prefersReducedMotion` branch, and gained a height that follows the busiest column (a fixed 300px
squeezed acid jazz's eleven-node column into a stack of anonymous dots). **`d3-force` and
`@types/d3-force` are uninstalled** — nothing imports d3 any more, and step 3's own rule was that
shipping unused dependencies is how a `package.json` accumulates things nobody can later explain.
Step 8 can reinstate what it needs. Frontend suite **48 -> 60**; `make check` **1184**, unchanged, no
Python edited.

**Two locks verified by breaking them**, per the standing counter-practice: reversing the edge
direction in `layerOf` fails 4 tests and only those; treating a missing year as `0` fails exactly 1.

#### Three process failures in this step, all the same shape

1. **Layout D shipped drawing ZERO edges.** `d3.forceLink` is what replaces string endpoint ids with
   node objects, and D deliberately has no simulation, so its endpoints stayed strings while nodes
   and axis furniture still painted. **My checker passed it on pixel count.** Fixed by resolving
   endpoints once, up front, for every layout.
2. **Node drag did not work in any preview, and my checker reported that it did.** Zoom and drag were
   bound to the same canvas, so mousedown started a pan before drag saw it. The check dragged from
   the middle of an empty canvas and asserted the picture changed — **but panning changes the picture
   too**, so a pan passed as a drag. **Found by sjtroxel using the running app.** The check now aims
   at a real node and asserts that node moved and the camera did not.
3. That rewritten check immediately caught a **third** bug: D's drag set `fy`, which only the
   simulation reads, so with no simulation nothing moved.

This is 2026-08-28 for the third time, and the lesson has now been re-learned twice at the same cost.
**The rule that actually generalises: a check must be able to distinguish the behaviour it is
asserting from the nearest thing that looks like it.** "Pixels changed" cannot tell a drag from a
pan, and "pixels were lit" cannot tell a drawn graph from a drawn axis with no graph on it. Both
passed. Both were wrong. Write the check so the near-miss fails it.

#### Open after this step

- **The context column reads as a regimented stack.** Ten unlabelled context nodes at one x are a
  vertical line rather than a neighbourhood. The force layout scattered them, which read better; the
  caption carries the meaning either way. Step 6 or 8's item, named rather than fixed here.
- **The 458-node component is a hairball in every one of the four layouts**, and in C and D nodes
  overflow the box vertically. It is unreachable from any chip and was not designed for.
- **The map is still not deployed.** Everything in this step is local, as at step 4. No AWS resource
  was touched and no money was spent.
- **B is worth revisiting if phase 6 ever dates the artists.** A second source that carries artist
  dates would make the year axis drawable across the whole demo surface, and it is the better picture
  where it works.

#### Step 6 inputs, banked 2026-08-30

Recorded when they came up rather than fixed on the spot, because type and palette are step 6's remit
and `planning/06` §4 says to run the `dataviz` skill rather than hand-roll them.

- **sjtroxel does not want the body serif.** `styles.css:47` is `ui-serif, Georgia, "Times New Roman",
  serif` on `body`, set at step 2 and never chosen deliberately. One line, one place.
- **The page and the map already disagree**, which nobody decided: the body is serif and
  `GraphView`'s node labels are `ui-sans-serif, system-ui`. Step 6 picks one relationship between the
  two on purpose — matching, or a deliberate pairing — instead of inheriting this one by accident.

### Step 6 — type chosen, palette briefed — 2026-08-30

**Type is decided and applied. Colour is briefed, not built.**

#### Type — option A, system sans

Chosen by sjtroxel from a three-way specimen (`web/previews/type.html`, gitignored): system sans,
Source Sans 3 on one webfont request, and a sans-body/serif-title pairing. `styles.css` body is now
`ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, sans-serif`.

Two things it fixes that were never decided in the first place. The serif was set at step 2 as
placeholder styling and inherited ever since. And **the page and the map had been disagreeing** —
body serif, canvas labels sans — so the stack now matches `GraphView`'s label font deliberately
rather than by accident. **No webfont**: a portfolio site that must stay live through a job search
should not put its text rendering behind another CDN and another person's connection.

**The specimen's own check was wrong first and it is worth recording.** It compared the three
columns by measuring each `h1`'s bounding box, which is the *column* width for a block element — all
three read 447px and it reported that the webfont had failed to load when it had loaded fine.
Measuring the text with a `Range` gave 295 / 223 / 304 and the real answer. Same family as the step 5
failures: **a check that cannot distinguish the thing it is asserting from something adjacent.**

#### Palette — the brief, in his words, recorded before anything is drawn

> *"a music venue, lights, camera, showtime and neons, rich colors and hues... performing arts feel...
> cinematic."*

**The structural consequence, stated once so it is decided rather than discovered: neon requires a
dark ground.** Neon reads as emitted light, and a saturated hue on a near-white `#fbfbf9` paper
ground reads as a bright sticker instead. Taking this brief seriously means **the SPA becomes
dark-primary**, with light as the secondary mode rather than the reverse. That inverts the map's ink
logic (claimed and context are currently dark-on-light), retires most of the current light palette,
and is a materially bigger change than a hue swap. It is a good direction and it is not a small one.

**The trade worth naming, because it is genuinely two-sided.** The current design signals rigour
through restraint, which suits a project whose central claim is *grounded means provenance, not
truth*. A cinematic treatment risks reading as louder than the claim. Against that: **this portfolio
has one unique visitor and it is him.** Memorability is not a luxury for a site nobody has opened,
and sober-and-unvisited is the outcome that is already happening. His instinct has the stronger
argument on current evidence.

**Deliberately NOT decided here: verification tiers stay uncoded.** `HAND` / `PROSE_AUTO` /
`ASSERTS_AUTO` / `EXPOSURE_AUTO` are the obvious next thing to put on a colour ramp, and a
light-to-dark ramp reads as confidence. The tiers say **how hard ONE source was checked, never how
many sources agree** (`.claude/rules/grounding-and-claims.md`). Encoding them as a ramp would make
the picture assert the opposite of the truth to anyone who does not read the caption. If a later step
wants them visible, it needs a non-ramp encoding and its own justification.

#### Also open from the palette check

**`--rule` is 1.25:1 against the ground in BOTH light and dark**, measured with the `dataviz`
validator. That colour does two different jobs: page borders, where 1.25:1 is correct because a
separator is not information, and **map context edges, where it is content the caption counts out
loud** — "the faint lines are 10 further connections." At 1.25:1 a visitor cannot find them. The fix
is to split the token by job rather than to lift it globally. Folded into the palette work.

*(The validator's other FAILs do not apply and were not actioned: its scope line says categorical
palettes, where every series needs its own hue. This palette is one accent plus neutrals, so "reads
gray" is the design working. Making the neutrals chromatic to satisfy that check would be wrong.)*

#### Palette — decided and applied, 2026-08-30

**Hot magenta `#ff5cae` on a venue-dark `#0d0a14`, and the theme is DARK ONLY.** Chosen by sjtroxel
from three accents rendered in the real running app — the palette was injected before each query ran
and the page screenshotted, so the comparison was the actual product rather than a mock-up.

**Dark-only is a decision, not an omission.** Neon reads as emitted light; the same hue on a
paper-white ground reads as a bright sticker. A light variant would not be a tint of this design, it
would be a second and different one, and two designs is real maintenance for a portfolio site. The
`@media (prefers-color-scheme: dark)` token block is gone and `color-scheme: dark` is declared.
**Verified with the OS preference forced to light: the body still resolves to `rgb(13, 10, 20)`.**

**Every value was validated, not eyeballed** (`dataviz` `validate_palette.js`, `--surface #0d0a14`).
All six candidate accents cleared contrast, so the check did not pick the hue — it only proved none
of them were disqualified, and sjtroxel picked on the brief.

*(The validator's lightness-band and chroma FAILs were not actioned. Its scope line says categorical
palettes, where each series needs its own hue; this is one accent plus neutrals, so "reads gray" is
the design working. Making the neutrals chromatic to satisfy that check would be wrong.)*

##### The refusal gets NO special treatment, and this was nearly lost

sjtroxel proposed an orange refusal state with warning glyphs, then withdrew it when §4.5 was quoted
back. Recording the exchange because the reasoning is worth more than the outcome:

- **DoD 10 requirement 1 forbids exactly that** — "no red, no warning glyph" — and the reason is that
  **a refusal is the system working correctly.** Wikidata genuinely records nobody as having
  influenced Kate Bush. Warning chrome on a true statement about the sources reports a fault where
  none occurred, and converts a provenance statement into an error message.
- **The proposed fix would have introduced the problem it was aimed at.** Amber and red are the alert
  conventions; magenta is not. Of the three candidates, **marquee amber was the one most at risk of
  reading as a warning**, and the chosen magenta is the safest on that axis. The original concern was
  stated too strongly by me and pointed the other way.
- What distinguishes a refusal is **what it says and what it shows** — Kate Bush drawn as connected,
  her seven incoming edges listed, the gap attributed to Wikidata, and the paired query answering
  immediately after. A sentence does not have to be learned; a colour does.

**`.status--failed` keeps its own colour and that is not an exception.** A transport failure is a
real error and is allowed to look like one. The distinction between "the request broke" and "the
sources are silent" predates this palette and survives it.

##### Open

- ~~The refusal has never been seen in this palette.~~ **DONE — checked live 2026-08-30 against
  Bedrock, on sjtroxel's explicit approval to spend. DoD 10 holds in the neon palette, all five
  requirements, and it is the first time the refusal has been seen against a real model at all.**
  Detail below.
- **The "Trace it" button is solid accent**, making it the loudest element above the fold — louder
  than the answer, and on a neon palette it competes with the map. An outline treatment is likely
  right. Not done.
- Nothing here is deployed. Still local, as at steps 4 and 5.

##### The refusal, verified live — 2026-08-30

`make dev-live`, the Kate Bush pair, **$0.0258 across 4 queries** (20,363 input / 1,097 output,
Haiku 4.5). The live API was stopped immediately afterwards and confirmed not listening.

**All five DoD 10 requirements hold, in the neon palette, against the real model:**

1. **No error chrome.** Same card, same type, same weight as the answer beneath it. No red, no glyph,
   no empty state. Confirmed by assertion, not by looking.
2. **It shows what the graph knows.** Kate Bush resolves and draws with **7 context edges radiating
   out of her**. Step 4 predicted this would happen against Bedrock and could not test it; it does.
3. **The gap is attributed to the sources.** *"A missing edge is not evidence of a missing influence.
   542 of the corpus's 973 nodes record no influences at all, so silence here is the state of the
   sources rather than a finding about the music."*
4. **No dead end.** The paired second query returns **7 cited claims**.
5. **No negative claim.** The copy says what is recorded, never what is true.

**An unplanned property worth keeping.** The refusal panel contains **no magenta except the node
itself**, because magenta is reserved for gate-approved claims and a refusal has none. The answer
panel below it is vivid. So the two states are visually distinct **as a consequence of the accent
meaning something**, not because a refusal was given its own colour. That is the distinction
sjtroxel's orange-and-warning proposal was reaching for, arrived at without borrowing the alert
vocabulary — and it is free, because it falls out of the rule that hue encodes gate approval.

**A third check-that-could-not-see-its-subject, in one day.** The DoD 10 harness reported
requirement 3 as FAILED. The copy satisfies it well; the regex looked for "sources record" as
adjacent words and the sentence reads "the state of the sources". Following the first two, the
pattern is now unmistakable and is written at the top of step 5's record: **a check must be able to
distinguish the behaviour it asserts from the nearest thing that resembles it** — and, added here,
**a check written against remembered copy will fail on real copy.** Assert the property, not the
phrasing.

**Cost note, reported against the estimate:** quoted as "about a cent", actual **2.6 cents**. The
overrun is entirely the failed check — the pair was run a second time to read the copy the assertion
should have read the first time.

### Step 7 — motion, and DoD 6 closed — 2026-08-31

**Decision: one motion mode, `animated`, at 850ms per edge. DoD 6 is closed.** Nothing deployed —
still local, as at steps 4, 5 and 6.

#### The step was not what the sequence said it was

The plan called this "motion previews", which assumed a still picture that motion would be added to.
Replaying the three captured fixtures frame by frame through `buildRenderGraph` and `layout` — before
writing anything — showed **the map was already moving, and nobody had designed how.** Two motions,
both hard cuts:

| | acid jazz | Kate Bush descendants |
|---|---|---|
| map first appears | tool frame, 5 nodes | tool frame, 8 nodes |
| grows to | 15 nodes over 4 claim frames | 16 over 7 |
| subject's y | `0 -> -110 -> -88 -> -88 -> -44` | unchanged |
| context edges | 4 -> 10 | **10 -> 9 -> 8 -> 7** |

The second column is the interesting one: **faint context edges converting into numbered claimed
edges, one at a time, as the gate approves them.** That is the claims-first invariant becoming
visible to a visitor, and it was arriving unannounced. So the step was not "add motion" but "decide
which of the two motions already here is worth being able to see".

#### The previews ran in the real app, not in a preview renderer

Steps 3 and 5 built throwaway HTML previews with hand-rolled drawing, correctly — the real component
did not exist yet. Step 6 changed the pattern by injecting palettes into the running app, and step 7
follows step 6. **A hand-rolled motion preview would have been a third renderer**, and motion tuned in
a fake renderer then applied to the real one is precisely the check-that-cannot-see-its-subject
failure this phase has hit four times. The three modes were built into `GraphView` behind a
`?motion=` switch and compared on free `make dev` stub queries. The switch and the losing modes are
gone; nothing in `web/previews/` was added for this step.

#### Two defects, both found by sjtroxel using it, both invisible to a green suite

He ran all three modes and reported them **looking exactly the same**. They did.

1. **StrictMode.** `main.tsx` mounts inside `StrictMode`, so React invokes the effect twice on mount.
   With one slot of memory, the first pass recorded every edge as drawn and the second found nothing
   new and painted the finished picture instantly. Fixed with **two** slots — the picture on screen
   and the one before it — so a repeat invocation animates from the earlier state.
2. **The animation was keyed to a React object identity.** `buildRenderGraph` returns a fresh object
   every render, so each prose token produced a "new" graph that was byte-for-byte the same picture,
   tearing down the running animation and restarting it with nothing left to enter. The edge snapped
   to full length mid-draw. **This one was not a dev-only artifact and would have shipped.** Now keyed
   to `graphSignature`, a content hash, and the clock survives unrelated re-renders.

**Twelve tests passed against both defects** because they rendered `GraphView` bare and the app never
does. Same family as steps 5 and 6, and worth stating plainly: the test file carried a docstring
about that exact failure mode while committing it.

#### The camera moves more than the nodes do

With those fixed he reported `reveal` and `full` still indistinguishable. Measured rather than
argued, and he was right about the screen:

| frame | nodes | canvas height | zoom `k` | subject on screen |
|---|---|---|---|---|
| tool | 5 | 260 | 1.576 | (411, 130) |
| claim 1 | 10 | 260 | 0.945 | (361, 26) |
| claim 2 | 11 | 270 | 0.826 | (351, 62) |
| claim 3 | 13 | 330 | 0.790 | (348, 96) |
| claim 4 | 15 | 390 | 0.768 | (346, 161) |

`full` tweened **layout** coordinates, but most of the travel is the camera: on the last transition
the subject moves 65px on screen and only 34 come from its layout position changing. It smoothed half
and hard-cut the other half, so the eye saw a jump either way. **`full` was not losing a fair
comparison — it was not doing its own job.** Fixed by making the camera data (`View`) and
interpolating scale, centre, origin and canvas height per frame. Only then were the two modes
genuinely different, and `full` was the immediate pick.

**The general lesson, and it is the one to carry into step 8:** *"they look the same"* is a report
about the screen, never a verdict on the design. Twice in one step the honest response was to find
out why they looked the same rather than to accept the comparison.

#### What shipped

- **`animated`**, the only motion mode. A newly approved claim edge grows from the object toward the
  subject — the direction influence runs — with its arrowhead landing only on arrival and its
  approval ordinal held back until the line exists. New nodes fade in. The camera glides.
- **850ms per edge, 526ms for the camera**, chosen by eye in the running app. 420 read as "kind of
  fast", 700 was better, 850 was the pick. Deliberately slower than a UI transition, because it is
  not one: it is the gate approving a claim.
- **`none`**, which is what `prefers-reduced-motion` resolves to: a single draw, **no loop started at
  all** — not a loop running at zero duration. There is no override; the `?motion=` switch went with
  the losing modes, because a switch that can turn an accessibility preference back on is worth not
  having. **DoD 6 closed.** The CSS blanket rule in `styles.css` never reached this: it zeroes
  transition and animation durations, and a canvas driven by `requestAnimationFrame` has neither.
- **Motion may change how the map arrives and may not change what it says.** A test asserts the
  animation converges on byte-identical geometry to the still image step 6 committed.

Frontend suite **60 -> 76**. No Python edited, no backend touched, root entry count unchanged.

#### On the tests, since this step is the reason to trust them

`jsdom` returns `null` from `getContext`, so a completely dead animation loop passes every other test
in this repo. The canvas context is stubbed with a recorder and `requestAnimationFrame` driven by
hand. **Every assertion was watched failing before it was kept**, and three caught real defects that
way — the two above plus a camera that never moved.

One is worth recording because it nearly went the other way: the camera test **failed against a
working implementation** at first. Its fixture added two nodes, which is too few — with a short
column the scale is bound by the horizontal fit and both heights clamp to the 260px minimum, so `k`
was 1.713 for both pictures and there was no camera movement to smooth. A fixture too small to
exercise the behaviour looks exactly like a broken implementation. It now grows a column to thirteen,
which is the shape the real acid jazz answer has.

#### Open

- **Nothing here is deployed.** Steps 4, 5, 6 and 7 are all local.
- **The "Trace it" button is still solid accent**, the loudest element above the fold. Named at step 6,
  still not done.
- *(Corrected: the `--rule` contrast split was recorded as open at step 6 and is in fact **done** —
  `--edge-context: #4a4160` at 2.07:1. Read the code, not the doc's open list.)*

### Step 8 — the explorable map, and DoD 4 closed — 2026-09-01

**Split into 8a (pan, zoom, select) and 8b (follow an edge, annotate)**, approved before either was
built, so there was a working half to look at before the second was stacked on it. Both shipped the
same day. **The deploy gap closed first**: steps 4–7 went live before any of this was written, on the
principle that four undeployed steps is the wrong foundation to add a fifth to.

#### The decisions

- **D1 — the camera becomes the visitor's the moment they touch it.** Auto-fit until the first pan or
  zoom, theirs from then on, and arriving claims stop moving it. A **Recenter** control gives it
  back, as a cut rather than a glide: it is a movement someone asked for, and animating those makes
  them wait. The collision this resolves is step 7's own finding — the camera travels further than
  the nodes do, so an auto-recentre mid-answer would be the largest motion on screen and would fire
  while someone was reading.
- **D2 — following an edge grows `context` and can never grow `walked`.** `walked` keeps meaning
  exactly one thing: the agent reached this. A node clicked to, three hops out, is context like any
  other unwalked node. This is the invariant-1 surface §5 names, and it is a **property** rather than
  a promise: `openedIds` is not read anywhere in the claimed pass, asserted over all 128 subsets of a
  seven-node corpus.
- **D3 — the caption gained a clause, or D2 would have leaked through the prose.** The sentence said
  the faint lines are what the corpus holds *"around them"*, meaning around the answer, and three
  hops into a wander that is false. `RenderGraph` now carries `opened` alongside `context` and the
  caption reports them separately. The honest data model would still have produced a dishonest
  sentence without this.
- **D4 — the inspector is DOM, and it is the accessible path rather than a panel beside the map.**
  A canvas has no elements. Choosing a node, following an edge, revealing connections and asking the
  agent are all real `<button>`s; the canvas keeps `role="img"` and is the shortcut. It also carries
  a no-selection state listing the walked nodes, because without one a keyboard user could operate
  the inspector but never open it.
- **D5 — no node dragging.** Step 5 made position mean influence depth and year, so dragging a node
  moves it to a position that says something false.
- **D6 — a plain wheel scrolls the page; ctrl/cmd zooms.** The map sits above the claims, so trapping
  the scroll there would be actively hostile. Trackpad pinch arrives as ctrl+wheel from the browser,
  so pinch-to-zoom came free with no gesture handling.
- **D7 — annotation goes to `/lineage` and through the gate.** `useLineageRun` gained `annotate`,
  which **appends** a step rather than replacing the run — replacing would throw away the answer
  someone was reading in order to answer a question about it. Refused while a stream is in flight,
  because aborting one would leave its step showing "running" forever. Frontend only; DoD 9 intact.

#### What the break-it pass found, and it is the reason to trust any of the above

Every lock was broken on purpose, run, and restored. **Three of them did not fail, and each was a
real defect in the test rather than in the code:**

1. **`clampView`'s first rule had a docstring describing behaviour it did not have, and the test
   guarding it passed with the rule deleted.** It asserted a *minimum overlap* — an inequality that
   held either way. Replaced with a rule that is provably conflict-free (the content's centre stays
   on screen, which is a point clamped into a rectangle) and an assertion that is an *equality* on
   where the map comes to rest.
2. **The Recenter test asserted that the button disappeared, not that the camera reset.** It passed
   with the reset removed: the control vanished while the map stayed exactly where it had been
   dragged to. It now compares drawn positions before and after.
3. **Two break patterns silently failed to match** because the file had been reformatted, so the
   "test caught it" reading was unearned. Both were re-run against the real text.

**The tell in cases 1 and 2 is the same and it generalises: each assertion was weaker than the
behaviour it was named after** — a bound instead of a resting place, a label instead of a pixel.

#### One design flaw found by a failing test, and fixed rather than asserted around

`follow` originally opened the node you came *from*. Following an edge out of a walked node then
revealed nothing at all, because the automatic pass has already expanded every walked node's
neighbourhood — `opened` stayed 0 and the test asserting that wandering reaches new corpus failed.
The map was behaving exactly as written and the writing was wrong. It now opens **both** ends, so
arriving somewhere shows what is there.

The test fixture had the matching problem: at six nodes, nothing in it is more than one hop from a
walked node, so no implementation could have discovered anything. It gained a node two hops out. **A
fixture too small to exercise the behaviour looks exactly like a broken implementation** — the same
sentence step 7 ended on, arrived at independently.

#### A formatting mistake worth recording so it is not repeated

Running `prettier --write` across `src/` reformatted **14 files that had no functional change**, to
80 columns. There is no prettier config in this repo and `npm run check` never runs it: formatting
here is hand-maintained and not uniform — three sampled files match prettier at width 100 exactly and
`layout.test.ts` does not. **Any blanket formatter run in `web/` produces churn.** The 14 files were
reverted and the semantic edits re-applied by hand.

**This was already true at 8a and went unnoticed:** that commit reformatted `GraphView.tsx` and
`styles.css` to 80 columns as a side effect. Both are still in that state and are now inconsistent
with the rest of `web/`. Left alone deliberately rather than folded into this step's diff — a
formatting-only change belongs in its own commit.

#### Measurements

- **Highest degree in artifact v0.5.0 is 25, and no node exceeds 30.** So `NEIGHBOURS_PER_OPEN = 30`
  cannot truncate any single node's neighbourhood: opening a node shows all of its connections or
  the corpus does not hold them. The automatic neighbourhood keeps its own separate cap of 40.
- Auto-fit `k` runs 0.77–1.58 on the real chips against a 2.2 cap, which is what the absolute zoom
  bounds of 0.1–10 were calibrated against.

#### What shipped

`viewport.ts`, a pure module holding the whole camera — project, unproject, pan, zoom-about-a-point,
clamp, hit-test — for the third application of the same lesson: jsdom has no canvas, so arithmetic
inside the draw closure cannot be tested. `NodeInspector.tsx`, the DOM half. Pointer, wheel and
button wiring in `GraphView`, which stays the thin driver.

**And a test file that mounts the real `App` with a recording canvas stub**, so a pointer event is
traced all the way to the coordinates the map actually drew. That layer was completely untested when
step 7's two defects shipped, and it is where both of them lived.

Frontend suite **76 -> 116** over 10 files. `make check` **1184 passed, 14 deselected**, unchanged —
no Python edited, no backend touched, root entry count unchanged at 15/18. **DoD 4 closed.**

#### Open

- ~~**`GraphView.tsx` and `styles.css` are formatted to 80 columns.**~~ **Closed at 8c** — and the
  claim was half wrong: only `GraphView.tsx` was affected. Prettier's CSS output is identical at 80
  and 100 columns, so `styles.css` was never damaged. Measured rather than assumed.
- **On touch, panning is horizontal only.** `touch-action: pan-y` keeps vertical page scrolling with
  the browser, which was worth more than two-axis touch panning.
- ~~**The "Trace it" button is still solid accent.**~~ **Closed at 8c.**

### Step 8c — the formatter, and the button step 6 flagged — 2026-09-01

Two items carried forward, done together because both were open loops rather than new work.

#### The formatter, and the actual root cause

The 8a and 8b sessions each ran `prettier --write` and each produced churn in files with no
functional change — 14 of them the second time. The reason was not carelessness with a flag. **There
was no prettier config and no prettier dependency**: every invocation was `npx` fetching it fresh and
running at its default 80 columns, against a codebase written at 100.

Measured before deciding anything: **21 of 29 files in `web/src` already matched prettier at width
100**, so that was the de-facto standard and the fix was to write it down rather than to pick one.

- `prettier@^3.9.6` is now a **devDependency**, not an ad-hoc download.
- The config lives in **`package.json`**, not a `.prettierrc`, for the same reason ruff and mypy live
  in `pyproject.toml`: one manifest per language rather than a config file per tool.
- `npm run format` and `npm run format:check` exist, and **`check` runs `format:check` first** — a
  formatting failure is the cheapest one to produce and the cheapest to fix, and finding it after a
  full typecheck-test-build cycle wastes the difference. `make web-check` and the deploy workflow's
  "Install and check the SPA" step both inherit it, so this cannot drift again silently.
- **`.prettierignore` covers `dist`, `public/graph`, `previews`, and `*.md`.** The middle two matter.
  `public/graph/v0.5.0/graph.json` is the staged copy of the pinned artifact and must stay
  byte-identical to what `stage-graph.mjs` writes — reformatting a 640 KB generated file would be
  churn in the one place where churn is indistinguishable from corpus drift. Verified after the run:
  655,641 bytes, 973 nodes, 950 edges, matching what CloudFront serves. `previews/` is recorded as
  disposable and is kept as the record of how a decision was made, not as maintained code. Markdown
  is hand-wrapped throughout this repo, deliberately, and prettier reflows it.

Eight files were reformatted. **The guard was verified by breaking it**: an unformatted file makes
`npm run check` exit 1, and restoring it returns 0.

#### The button

`.ask__submit` was a solid `--accent` fill, which step 6 named as the loudest element above the fold
and suggested an outline for. The reason is stronger than loudness: **step 6 gave `--accent` a
meaning — this was approved by the gate — and a submit button has not been approved by anything.**
The map already respects that (the step 8a selection ring is drawn in `--ink`, not the accent,
precisely so clicking a faint node cannot look like the gate passed it), and the chrome was
contradicting it.

Now an outline: `--accent` text and border on a transparent ground, measured at **6.91:1**, well past
the 4.5:1 AA bar for normal text, so nothing was traded for the change. It is deliberately the same
treatment as the inspector's "Ask the agent about X" — **the two controls on the page that spend
money and come back through the gate now read as one kind of thing.**

One defect found while doing it: `.inspector__action:hover` set `color: var(--ink)`, which won over
`--ask`'s accent, so the one accent-carrying control lost its accent at the moment it was pointed at.
Fixed with a specific hover rule.

`make check` **1184 passed, 14 deselected**, mypy clean over 89 files, root **15/18** unchanged, eval
gates 3 passed / 0 failed / 2 not applicable. Frontend **116**, unchanged — this step added no
behaviour and no test, which is the correct shape for it.
