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
  variables.tf                          cors_allowed_origins narrowed; timeout_seconds retightened
  outputs.tf                            CloudFront domain name
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

**Still open from step 0, by decision:** `timeout_seconds` stays at 30. Two observed runs at 7.4s and
6.4s give roughly 4x headroom, and two samples is not a p99. It tightens from real CloudWatch
`ElapsedSeconds` once there is traffic.
