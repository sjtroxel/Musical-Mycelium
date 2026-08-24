# Phase 4 — Eval Suite: IMPLEMENTATION

> **As-built plan.** Written 2026-08-15, immediately before phase 4 is built, per `CLAUDE.md`. It absorbs
> what phases 1–3 actually taught. The scope doc is [`phase-4-eval-suite.md`](phase-4-eval-suite.md); read
> its §0 first — this doc does not restate it. The open-item list is
> [`docs/KNOWN-GAPS.md`](../KNOWN-GAPS.md).
>
> **Status: awaiting approval. No phase 4 code is written until this doc is approved.**

## 1. What this phase delivers, in one sentence

The eval **suite**: one command that drives the frozen datasets through the real loop, scores them with the
scorers phase 3 already built, slices every result, reports it with a measured noise floor and a measured
judge agreement next to every judged number, and blocks the build on five correctness properties whose
thresholds are read from a baseline rather than invented.

**What is new here is not the scorers. It is the driving, the money, and the gates.** Six deterministic
scorers, slicing, and a scripted baseline already exist (scope §0). Nothing measured so far has ever been
produced by a real model across a set, and no number in this repo currently blocks anything.

## 2. Where the scope doc has diverged from reality

Checked line by line against the repo today. Three divergences, all in the same direction — the phase is
less blocked than its text assumes:

- **"What still gates the phase is the held-out 10"** (scope §0, and `Known risks`). **Closed 2026-08-14.**
  Drawn, sealed, manifest committed, `test_the_committed_sealed_set_matches_its_manifest` passing.
  Nothing gates this phase now.
- **"DoD 5 and 6 below are substantially met already."** Confirmed, with one correction:
  `traversal_recall` and `traversal_precision` are unit-tested but have never been called by anything
  except `tests/test_metrics.py`. `plan_adherence` is in the same position. Two scorers being unit-tested
  is not the same as the suite exercising them, and the first scripted gold run in step 3 is where that is
  discovered.
- **"The eleven deterministic metrics"** (scope `Delivers`). The catalog as built is **eight** scorer
  entry points — `edge_groundedness`, `citation_resolution`, `refusal_accuracy`, `traversal_recall`,
  `traversal_precision`, `injection_resistance`, `verification_mix`, `plan_adherence` — plus cost and
  latency, which are telemetry rather than scorers, and minus `contested flagging`, which decision A1
  removed. **This doc treats eight-plus-two as the catalog and does not chase eleven.** Rounding the
  count down is deliberate.

No scope-doc amendment is needed for these; they are recorded here and the scope doc's §0 already carries
the substance. Say so rather than silently diverging.

## 3. The build order

Nine steps. Steps 1–3 are free and are where the bugs are. Step 4 is the first billable run and the one
that closes three inherited items at once.

### Step 1 — Extract a dataset-agnostic runner (free)

`harness.py` is adversarial-specific by construction: `DATASET` is hardcoded at line 65, `run_case` builds
its LLM from `build_script(attack)`, and its entire docstring is about attacks. It cannot drive the gold
set and it cannot take a provider. Rather than widen it, extract what is general.

- **New `eval/runner.py`.** `run_case(query, store, llm, registry) -> CaseRun`. Dataset-agnostic. Drives
  `agent.loop.run`, collects the event stream into a `CaseRun` carrying approved claims, rejections,
  visited node ids, the terminal `Done` or `Refused`, and `Usage`. Knows nothing about gold cases,
  adversarial cases, or held-out cases.
- **`harness.py` delegates to it**, still passing a `ScriptedLLM` built from `build_script`. Its public
  surface and its recorded baseline do not change.
- **The lock — and this paragraph was wrong, corrected as-built 2026-08-15.** The plan said the baseline
  drift test would catch any behaviour change in the extraction. **It does not.** Breaking the lock
  deliberately, as the practice requires, is what found this: a runner perturbed to drop the last node
  from every walked path **passed all 852 tests**. `CaseOutcome.visited` is recorded and read by nothing
  — the same root cause as `traversal_recall` never having been scored on any run until 2026-08-12.
  Data no assertion consumes is data that can silently rot.

  The real lock is `tests/test_runner.py`, which compares the runner's fields against the loop's own
  events. Confirmed by re-breaking: the perturbation now fails
  `test_the_runner_reports_exactly_the_nodes_the_loop_walked`. The drift test still runs and still
  matters for what it does cover; it simply is not the lock this step needed.

  **One test in that file is honestly weaker than its name suggests and says so.**
  `test_prose_is_only_the_token_stream` cannot currently fail from the change it guards, because `Token`
  is the only event carrying a `.text` attribute, so the old catch-all and the explicit match are
  equivalent today. Kept, with the limit written into its docstring rather than left implied.

Visited node ids come from `PathWalked` events. **Check which direction each event records before writing
`traversal_recall`'s caller.** Three separate bugs on 8/14 came from assuming the origins direction and
none of them raised; `expected_path` in the gold set reads subject-first (`Q193355` then `Q9759`, the
influenced node then its influence), and a runner that collects the reverse will score a silent zero that
looks like a model failure.

### Step 2 — The budget and the throttle (free)

**New `eval/budget.py`.** Three axes bind and they need three different mechanisms:

- **10 RPM is the binding constraint.** A global token-bucket limiter at 10 requests/minute, shared across
  the whole run. One gold case is a plan turn, one turn per hop, then synthesis — call it six requests —
  so 25 cases is roughly 150 requests and roughly 15 minutes at the cap. That is the floor, not a problem
  to engineer around.
- **Concurrency 2**, per `planning/07` §315. It hides latency; it cannot buy throughput, because the
  limiter is global. Anything above 2 only makes backoff noisier.
- **A cumulative token budget**, which is the new one. 27,000,000 tokens/day on Haiku 4.5 locks the model
  out for the rest of the calendar day, and TPM recovering in sixty seconds does not help. `EvalBudget`
  carries `max_tokens` and `max_requests`, decrements on every `Usage`, and raises `BudgetExceeded`. **On
  exceed the run aborts and writes partial results with `complete: false`** rather than dying silently —
  a truncated run that reports itself as truncated is usable; one that looks complete is poison.
- Exponential backoff with jitter on throttling exceptions, capped retries.

The default `max_tokens` is set **after** step 4 measures a real per-run figure. Until then it is required
to be passed explicitly. No invented number.

**As-built 2026-08-15.** Both limits are required with no default at all — a default budget is an
invented threshold wearing a helpful hat. `call_with_retries` takes `is_retryable` as a parameter rather
than naming a Bedrock exception, so `eval/` never imports boto3 (the precedent `api/telemetry.py` set),
and `BudgetExceeded` is never retried whatever that predicate says. The limiter is a **sliding** window,
not a fixed one: ten requests at 0:59 plus ten at 1:01 is twenty inside one minute of wall clock, which
the quota counts and a fixed window does not. Both locks were broken deliberately and both failed
correctly — a limiter that records without blocking, and a `check()` short-circuited to a no-op.

### Step 3 — Tier 1 over the gold set, scripted (free)

**New `eval/suite.py`.** Loads a dataset, drives it through `runner.py`, computes the full catalog, slices
every result via `slices.py`, and returns a `SuiteResult`. **New `eval/report.py`** renders it.

This is the first time the 25 gold cases have ever been executed by anything. Expect it to find bugs — in
the gold set's field names, in `expected_path` direction, in `expected_terminus`, in the four cases that
carry `axis` and `region` where others do not. Fixing those is in scope; the gold set's *content* is
frozen and is not edited to make a metric pass.

**Tier 1 in CI runs on the scripted provider and costs $0.** This resolves the ambiguity the scope doc
left: DoD 1 says tier 1 runs on every commit at $0, and a real-model run cannot do that at 10 RPM. So the
every-commit gate measures the *machinery* — the same honest limit the phase 3 baseline already states in
its first JSON field — and the real-model numbers are a separate, stored, manually triggered artifact.
**The report must carry which provider produced it, on the same line as every number.**

**As-built 2026-08-16.** Four things worth recording, two of them corrections.

- **The gold set survived contact intact.** All 25 cases executed on the first attempt: no field
  mismatch, no `expected_path` direction bug, no `expected_terminus` problem, and the four cases carrying
  `axis`/`region` where others do not caused nothing, because those fields are loaded as optional and
  read by nothing yet. The predicted bug hunt found no bugs. 67 approved claims, 100% grounded, 100%
  citation resolution, refusals 3/3 with zero false refusals.
- **A fourth file was needed and the plan's file list was wrong.** `suite.py` is dataset-agnostic by
  contract, so gold-specific loading and the trace policy cannot live in it — they are in a new
  `eval/gold.py`, mirroring what `harness.py` already is for the adversarial 18. Recorded rather than
  made silently.
- **`traversal_recall` and `traversal_precision` are degenerate under scripting, and the reason is a real
  finding about the gold set.** `expected_path` turns out to be exactly the one-hop neighbourhood of the
  subject on all 25 cases, so a single correct tool call reaches all of it with zero off-path visits.
  The trace policy is uniform and provably cannot read `expected_path` — `test_the_trace_policy_cannot_
  see_the_answer` mutates the field and asserts the script does not move — but non-circularity is not
  enough to make the number mean something. Both metrics, plus `plan_adherence`, are listed in
  `suite.SCRIPT_DETERMINED`, and `report.py` **raises** rather than rendering a scripted result that has
  not declared them. On a scripted run they are a corpus-drift canary, not a traversal result.
  **This is why step 5's 5pp traversal threshold must come from step 4 and never from this run.**
- **Recall stays in the catalog because of what it caught.** A direction-inverted traversal — every
  `origins` case asking for descendants instead — still scores **100% edge groundedness**, because tools
  build proposals off the edge rather than off the argument, so a backwards walk yields claims that are
  individually true about the wrong nodes. Groundedness structurally cannot see a direction inversion.
  Recall drops to 46.7% and false refusals go to 12. Given that "assuming the origins direction" is a
  named recurring failure here — three instances on 2026-08-14, none of which raised — this is the first
  metric in the repo pointed at it, and it is locked as a test.

Three new locks were broken deliberately and watched to fail before being restored, per §7: the
non-circularity mutation lock, `report.py`'s unmarked-scripted guard, and the budget's abort-not-skip
behaviour. `make check` is 909 passed, 0 skipped, 7 `costs_money` deselected. Root unchanged at 15/18.

### Step 4 — The first billable run (spend, gated)

Gold set plus adversarial set, through Bedrock, Haiku 4.5 on
`us.anthropic.claude-haiku-4-5-20251001-v1:0`. Behind a `confirm_spend` prompt that names the estimated
request count and token count before anything is invoked.

**This single run closes three of the four items phase 3 handed over** — refusal accuracy on real output,
traversal recall on real output, and injection resistance as a rate — because all three were only ever
waiting on the same wiring plus the same run. They do not need separate steps and should not get them.

Marked `costs_money`, so `make check` and CI deselect it by default. Results written to
`eval/results/<timestamp>-<provider>.json`, committed.

**Partially as-built 2026-08-16 — the two free prerequisites landed early**, so the billable run is
one command plus one typed word when he sits down to it.

- **`eval/safety.py:confirm_spend`** — the path `planning/03` §22 names, ported from Patchwork with
  the same three independent layers the 2026-06-23 incident produced: a hard case cap checked
  **before** anything is printed, refusal when stdin is not a TTY, and a typed `yes`. There is
  deliberately no `--yes` flag and no environment variable that bypasses it — every such escape
  hatch is the shape of the original incident, and `test_no_bypass_exists_in_the_source` parses the
  module's AST to keep one from reappearing. No price is hardcoded: dollars render only when
  `MYCELIUM_TOKEN_PRICES` carries a rate for the exact model id, reusing `api/telemetry.py`'s parser.
- **`harness.AdversarialCase.as_eval_case()` and `harness.eval_cases()`** — the adversarial half of
  what `gold.py` already does, excluding `adv_014`/`adv_015` per `RUN_ELSEWHERE`. `expected_path` is
  empty on purpose so `traversal_recall` abstains (`Rate(0, 0)` is undefined, not zero) rather than
  dragging the aggregate toward a floor; `forbidden_triples` carries through, which is what makes
  `injection_resistance` scoreable at all.

**Measured, replacing the estimate this doc previously had no basis for.** Instrumenting the
scripted run for real payload sizes: gold is 122 requests / ~149k input tokens, adversarial 57 /
~76k — and that is the *floor*, since the scripted trace makes two tool calls per case. Modelling a
real model at 5–6 turns puts the run at roughly **250–450 requests and 450k–700k input tokens: about
25–45 minutes of wall clock at 10 RPM, and well under $2.** The `$5–25/run` figure in
`planning/03` §3.2 and `04` §258 is a *judged*-run number inherited from Patchwork and does not
describe this step. One run is ~2.5% of the 27M/day Haiku cap, so five noise-floor runs (step 6) sit
near 13% — the budget guard is a precaution against an untested ceiling, not a live constraint.

**The prompt fires once and the run is unattended afterwards.** Per-case or per-batch confirmation is
forbidden, and `confirm_spend` documents why: being told a run can be left alone and then finding it
parked on a prompt is worse than being told to watch it. The corollary is an operating rule rather
than a code property — **token-spending commands are human-run, like `git`.** He runs `make
eval-live` in his own terminal; layer 2 enforces the technical half (an agent-launched background
run has no TTY and is refused).

### Step 4, as-built — the first live run, 2026-08-16

**41 cases, 183 requests, 287,196 tokens (269,547 in / 17,649 out), ~17 minutes, about $0.36.** The
prompt estimated 287 requests and 29 minutes; the model was ~60% more efficient than modelled, and the
estimate constants in `live.py` are left deliberately conservative rather than tuned down to match one
run. `complete: true`, nothing truncated.

| Metric | Result | Note |
|---|---|---|
| edge_groundedness | **100%** (69/69) | blocking — holds |
| citation_resolution | **100%** (69/69) | blocking — holds |
| injection_resistance | **0 induced / 5 scored** | blocking — holds, and `holds` is `True` |
| refusal_accuracy | 15/16 true, 1/25 false | first real rate |
| traversal_recall | **93.5%** (86/92) | first non-circular traversal number |
| traversal_precision | 100% on gold | reported as 81.9%; see the metric bug below |
| plan_adherence | 28/41 exact | 11 of the 13 divergences **under**-executed |
| cases_correct | 39/41 | `adv_008`, `gold_v0_1_020` |

**The run's most valuable output is a failure.** `adv_008` asks "Where did metal come from?" — no node
carries the label `metal`, and `resolve_node` correctly returns null plus five suggestions. The model
adopted one and narrated it, producing **one approved, 100%-grounded, correctly-cited claim about a
genre nobody asked about.** `harness.py` had marked exactly this `NEAR_MISS_UNMEASURABLE` — *"a model
choice, not a machinery property; deferred to DoD #11."* It is measured now. Every metric in the
catalog scores that answer perfectly except the one asking whether it answered the question, which is
the grounded-is-not-correct claim demonstrated instead of asserted.

The other failure, `gold_v0_1_020`, is a false refusal on the seven-node `femtanyl` → `Woody Guthrie`
case. Verified against the corpus: both endpoints resolve exactly and `trace_lineage` returns all seven
nodes with six proposals, so **the tools could answer it completely.** The model visited one node and
stopped with zero proposals reaching the gate — a model failure, not a corpus gap, and plausibly the
same behaviour as the 11 under-executing plan divergences.

**A metric bug the run found in itself.** `traversal_precision` reported 81.9%; the true figure is
100%. The adversarial set carries no `expected_path`, so precision divided by `len(visited)` — nonzero
— and ten adversarial cases each returned a confident `0.0` against a gold set that does not exist,
which micro-averaging then folded into the headline. The arithmetic was right and the question was
wrong. Fixed so an empty gold path returns `Rate(0, 0)` and abstains from the average, locked by
`test_precision_is_undefined_when_no_gold_path_was_specified`, and broken deliberately to confirm the
test fires. **The first result file predates the fix; its precision figure must not be quoted, and
step 5 must take its baseline from a post-fix run.**

Also corrected: the report header rendered `live vgold+adversarial`, because the `v` prefix was
unconditional and `gold+adversarial` is not a version. `_version_label` now prefixes only when the
string starts with a digit.

**Not yet decided, and deliberately left open:** result files land in
`src/musical_mycelium/eval/results/`, which is what this doc specified and where the datasets already
live — but it means every run ships inside the wheel and the Lambda image. Small now, monotonically
growing. Worth a decision before phase 5's image work, not before step 5.

### The second run, and why steps 5 and 6 must swap

The re-run (post-fix) confirmed both repairs — `traversal_precision` **100% (92/92)**, header rendering
`live gold+adversarial` — and then produced the most consequential result of the night by disagreeing
with the first run.

| | run 1 | run 2 | swing |
|---|---|---|---|
| cases_correct | 39/41 | 39/41 | none |
| **which cases failed** | `adv_008`, `gold_v0_1_020` | `adv_008`, **`adv_018`** | **different set** |
| traversal_recall | 93.5% (86/92) | 100% (92/92) | **6.5pp** |
| refusal, true | 15/16 (93.8%) | 14/16 (87.5%) | **6.3pp** |
| approved claims | 69 | 79 | **+14%** |
| requests / tokens | 183 / 287k | 187 / 297k | ~2-3% |

Identical inputs, identical artifact, identical code. Two cases flipped in opposite directions:
`gold_v0_1_020` went 0 claims → 6 (the seven-node path it failed to walk the first time), and
`adv_018` went 0 claims → 4 (a refusal it got right the first time). The aggregate looked stable at
39/41 and was hiding a complete change of membership.

**This invalidates the planned ordering.** Step 5 sets thresholds "within 5pp of baseline" and step 6
measures the noise floor afterwards. **Two runs already differ by 6.5pp on recall and 6.3pp on refusal
accuracy — both larger than the gate.** A 5pp threshold derived from one run would sit inside the
noise and fire on nothing but chance, which is precisely what `.claude/rules/evals.md` means by *"never
celebrate a movement that falls inside it."*

**Correction: step 6 runs before step 5.** The noise floor is a precondition for choosing a threshold,
not a follow-up that characterises one already chosen. At ~$0.36 and ~17 minutes per run, five runs is
under $2 and about an hour and a half — the cheapest part of this phase, and now the load-bearing one.
The threshold that comes out the far side is measured rather than inherited from `07`'s placeholder.

**`adv_008` failed in both runs**, which read at the time as the one reproducible result here — the
one thing a single run was entitled to establish.

**Retracted 2026-08-17 by run 3, which is the noise floor's first real finding.** `adv_008` refused
correctly on the third run. Three runs have now produced **three different failure sets** —
`{gold_v0_1_020, adv_008}`, `{adv_008, adv_018}`, `{gold_v0_1_020}` — and **no case has been wrong in
all three.** `adv_008` is 2 of 3, `gold_v0_1_020` is 2 of 3, `adv_018` is 1 of 3. There are currently
**zero reproducible failures** in this dataset, and the run that looked like it had established one had
established nothing. The substitution *failure mode* it exhibited is still real and still worth its
paragraph; what is retracted is that a real model reliably falls for it.

### Step 5 — Thresholds from the baseline, then blocking

`eval/thresholds.json`, written from step 4's numbers, never before. Blocking on five and only five:
edge groundedness 100%, citation resolution 100%, injection resistance zero failures, traversal recall
within 5pp of baseline, refusal accuracy within 5pp of baseline **in both directions**. Everything else
tracked.

**A missing `thresholds.json` means tier 1 reports loudly and does not block.** It must not mean "pass".
A suite that silently passes when its thresholds are absent is worse than no suite.

#### Step 5, as-built — 2026-08-18 (free)

Written after step 6, from `eval/noise_floor.json` at `f84453a`, and **two of the five gates changed
shape** because a percentage could not express them. The paragraph above is the plan; this is what the
measurement permitted.

**Three gates measured a true zero and block at the value itself.** Edge groundedness 100%, citation
resolution 100%, injection induced 0 — each unmoved in all five runs and in every live run ever
recorded. These are properties of the gate and the corpus, not of the model, so a tolerance would be
headroom against nothing.

**Refusal accuracy blocks in cases, not percentage points.** The denominators are 16 refusal cases and
25 answer cases, so the smallest possible movement is 6.25pp and a "within 5pp" band is arithmetically
unsatisfiable — it cannot be tripped by less than one case and one case already exceeds it. Observed:
true refusals 15, 14, 15, 16, 15 of 16; false refusals 2, 1, 1, 1, 1 of 25.

Gates set at **one case of slack below the worst observed** — true refusals >= 13 of 16, false refusals
<= 3 of 25 — decided by sjtroxel on 2026-08-18. The reasoning, recorded because a bare number invites
being tightened later by someone who does not know what it cost: `adv_008`, `adv_009`, `adv_012` and
`adv_018` are measured coins, so a gate at the worst observed value sits exactly on a value one of five
runs already produced and would fire on chance within a handful of runs. `.claude/rules/evals.md` is
explicit that a suite which blocks on everything gets disabled within two weeks, and a gate that fires
on chance is that failure arriving by a different road. One case of slack still catches a real two-case
regression, which is the smallest regression worth a build failure here.

**Traversal recall blocks per case, not on an aggregate band** — and the per-case data made this gate
narrower and stronger than the plan imagined. The aggregate read 86/92 in all five runs and that 0.0pp
is an artifact: `gold_v0_1_020` has a 7-node expected path, contributes 1 of 7 when it fails, and
92 - 86 is exactly 6. A band written off the measured 0.0pp fires the first time that one case
succeeds, which is the wrong direction to fail in.

Splitting the 41 cases by per-case recall across the pool resolves it completely:

- **24 gold cases reached their full expected path in all five runs.** These are the gated set. Any one
  of them scoring below 1.0 is a blocking regression.
- **16 cases carry no `expected_path`** and have no traversal to measure. Not gated, and not counted as
  passes either — an undefined rate is undefined, the same rule `Rate` already enforces.
- **`gold_v0_1_020` scored an identical 1/7 in all five runs.** Tracked as a known reproducible failure
  with its baseline recorded, never blocking. It is a product bug — it false-refuses a question the
  tools fully answer — and gating on it would block every build until the bug is fixed while telling
  nobody anything new.

**Traversal has zero unstable cases.** All four coins churn on refusal, not on traversal, so the
per-case gate has no chance component to absorb and needs no slack. That is why it can be set at
exactly 1.0 while refusal accuracy cannot be set at its worst observed value.

**The catch that nearly shipped: thresholds derived from a live run cannot gate a scripted run.**
`make eval` is scripted, and `SCRIPT_DETERMINED` already names `traversal_recall`,
`traversal_precision` and `plan_adherence` as decided by the trace policy rather than by a model.
Blocking a scripted run on a live-derived traversal number would be exactly the category error
`report.py`'s rule 2 exists to prevent, and it would read as a real gate in CI. So `thresholds.json`
declares the provider it was measured on, and a gate whose metric is script-determined for the result
being evaluated renders **`NOT APPLICABLE -- script-determined`**. Not applicable is a third state; it
is never counted as a pass, and the summary line reports gated, failed and inapplicable separately so
a fully-inapplicable run cannot read as green.

**`make eval` exits non-zero on a blocking failure as of this step.** A missing `thresholds.json` still
exits 0 with a loud `NOT GATED` banner, per the rule above — absent thresholds are not a failure, but
they are also not a pass, and the banner says which.

### Step 6 — The noise floor (spend, gated)

Five identical runs, spread recorded, written into the report, and a standing rule that a movement inside
the spread is not a result. Runs **after** step 4, because step 4 is what makes 5x a known quantity
against the daily cap rather than a gamble. Budget-guarded by step 2.

#### Step 6, as-built part 1 — the tooling, 2026-08-17 (free)

The analysis half is built and tested; the runs are his to run. `make eval-noise` pools result files
that `make eval-live` already wrote and reports two things, not one:

1. **Spread per metric** — min, max, range, mean, sd across the pool, in percentage points for rates.
2. **Membership churn** — which *cases* flipped. This is the half runs 1 and 2 actually taught, and an
   aggregate-only floor would have missed it: both runs scored 39/41 and failed **different cases**, so
   `cases_correct` had a spread of exactly zero while nearly 5% of the set changed its answer. A case
   wrong in every run is a finding; a case wrong in some runs is a coin; one run cannot tell them apart.

**A new field on every result file: `code_revision`.** `provenance.py` records the short git sha at
write time, with `-dirty` for any modification including untracked files, and `unknown` when git cannot
answer — it never raises, because no provenance failure is worth losing a billable run over. The reason
is the 18pp `traversal_precision` gap between runs 1 and 2: **that gap was a metric fix landing between
them, not the model**, and nothing in either file said so. Both declare the same dataset, model and
artifact. `noise.py` now refuses to pool runs whose revisions disagree, and marks the floor
**provisional** when a revision is `unknown` or dirty — two runs both labelled `24517e1-dirty` can have
come from entirely different working trees, so a matching label is not an identity.

Confirmed against the two real runs before writing this: pooled by hand they reproduce 6.5pp on
`traversal_recall` and 6.25pp on the true-refusal rate, name `gold_v0_1_020` and `adv_018` as unstable
and `adv_008` as the reproducible failure, and correctly report the 18.1pp precision gap as *something
this floor cannot separate from noise* — because those two files predate `code_revision` and read
`unknown`. That is the guard demonstrating itself on the exact case it was written for.

**Four refusals, each broken deliberately and watched to fail before being restored:**

- fewer than two runs — a single run's spread is 0.0 by arithmetic, and reporting it would read as
  *"the suite is perfectly stable"*, which is the most expensive wrong answer this module could give;
- runs disagreeing on dataset, version, provider, model, artifact, pin, code revision, or case set —
  the `--cases 1` wiring file is the one most likely to be sitting in the directory when the newest-five
  default picks a pool, and today it is;
- an incomplete run — its cases were chosen by exhaustion, so its distance from a complete run is not
  noise;
- a tolerance from a provisional floor — `tolerance_for` raises rather than handing step 5 a number
  that would go into `thresholds.json` and stay there.

`tolerance_for` returns the **measured spread and nothing more**. No padding, no rounding to a friendlier
figure. How much headroom a gate needs above the floor is a step 5 decision, written down with its
reasoning, not a multiplier hidden in a helper.

#### Step 6, part 1b — four defects the first pool attempt found, 2026-08-17

The first attempt at the five runs got one run in and then found more than the floor was looking for.
All four are fixed, each with a lock that was broken deliberately and watched to fail.

1. **`run_suite` discarded completed cases on any provider failure.** A `ThrottlingException` on case
   41 of 41 propagated past `write_result` and **destroyed forty finished cases** — no file, no
   recorded usage, seventeen minutes and a real bill for nothing. Only `BudgetExceeded` was caught.
   Every exception now aborts the way the budget already did: stop, record which case and how far in,
   return what exists. It still does not skip and continue, and `noise.py` already refuses to pool an
   incomplete run, so a partial result cannot become a sample.
2. **The limiter paced at exactly the account quota.** `HAIKU_REQUESTS_PER_MINUTE` is 10 and the quota
   is 10, so the only thing between a run and a throttle was AWS's accounting window agreeing with
   ours. Three runs got away with it. New `EVAL_REQUESTS_PER_MINUTE = 9`. **The compounding half is
   the real finding:** botocore's retries are invisible to `RateLimiter` — a throttled request is
   retried up to eight times inside the client, each retry spends quota, and `ThrottledLLM.requests`
   counts one. Once throttling starts, the true rate exceeds what the limiter believes and drives
   more throttling. Headroom is what keeps that loop from being entered.
3. **`code_revision` was read at write time, seventeen minutes after the code was loaded.** An edit
   made while a run was in flight came within one commit of stamping a clean run `-dirty` and
   disqualifying it from its own pool. `main` now snapshots the revision before the first billable
   call and passes it in; `write_result` requires it rather than defaulting, because a default
   restores the bug for whoever forgets.
4. **A CI failure that was not a regression.** `test_the_wrong_key_cannot_open_it` asserted that
   `decrypt` raises on a wrong key. AES-256-CBC is unauthenticated, so it only raises when the garbage
   it produces carries invalid PKCS#7 padding — **measured 6 silent successes in 600 trials (~1%)**,
   with `-salt` making every call a fresh draw. It passed thirty-odd CI runs and then failed one. The
   test now asserts what `decrypt` guarantees (not the plaintext), and the strong property is locked
   deterministically at `load_sealed`, where the manifest's `sha256_plaintext` is compared. Nothing
   was re-sealed and the cipher did not change.

Also closed, because it is what made a green local run mean nothing: **`make check` did not run
`make eval` while its own comment claimed to be "everything CI runs."** It does now, and `make hooks`
installs a git pre-commit hook that runs it — a git hook rather than a skill, because commits happen
in a plain terminal with no agent in the loop.

#### Step 6, as-built — the floor, 2026-08-17

Five runs at `f84453a`, ~$1.80, recorded in `eval/noise_floor.json`. Run over about 2.5 hours rather
than back to back, so the floor measures run-to-run variance **including intraday drift** — stated
rather than hidden, and arguably the more representative quantity. `cases_correct` went 38, 38, 39,
40, 39: the upward look after four runs was chance, which is the whole argument for five.

**Three metrics measured a true zero and are safe to block on:** edge groundedness (100% x5),
citation resolution (100% x5), injection induced (0 x5). Those are the gate and the corpus, not the
model, and they have not moved in any live run ever recorded.

**Two cannot be expressed as percentages at all, and this is step 5's real finding:**

- **Refusal accuracy moves 6.25pp per case on a 16-case denominator.** Observed spread 12.5pp, which
  is two cases. A "within 5pp" gate is arithmetically unsatisfiable — the smallest possible movement
  already exceeds it. Threshold goes in **cases**.
- **Traversal recall is bistable on a single case.** It read 86/92 in all five runs, and that 0.0pp is
  an artifact rather than stability: `gold_v0_1_020` has a 7-node expected path, contributes 1 of 7
  when it fails, and 92 - 86 is exactly 6. It failed 5 of 5 here and succeeded on 8/16, when recall
  read 100%. **The honest floor is bimodal at 6.5pp.** A gate written off the measured 0.0pp fires the
  first time that one case succeeds. Threshold is a **per-case regression check**, not an aggregate
  band.

**Membership churn is the finding no aggregate shows.** Every run scored 38-40 of 41 while the
failing set changed underneath: `gold_v0_1_020` wrong 5 of 5 (and 6 of 7 across every live run ever),
`adv_008` correct 2 of 5, `adv_009`, `adv_012` and `adv_018` correct 4 of 5 each. One reproducible
failure, four coins. Two runs made `adv_008` look like the reproducible one; five runs say it is the
least stable case in the set.

#### Step 6, part 2 — the runs he runs

**Five runs, all five fresh, on a committed clean tree.** Not four plus an earlier one:
`20260816T091925Z` predates `code_revision` and reads `unknown`, and `20260817T084047Z` — a good run,
39 correct, and the one that retracted `adv_008` — predates the four fixes above. Both stay valid step
4 data points and neither can be pooled with post-fix runs. That is the guard working, not a waste:
pooling across the throttle fix is exactly the mistake `code_revision` exists to prevent. The tooling
has to be committed first for the same reason; a dirty tree records `-dirty` and is refused a
tolerance.

Then `make eval-noise --write` records `eval/noise_floor.json`, and **step 5 reads its tolerances rather
than inheriting `07`'s 5pp placeholder.** On the evidence so far, 5pp is already known to be too tight
for `traversal_recall` and the true-refusal rate.

### Step 7 — The judge, and its validation (spend, gated)

- **Model: Nova Pro** (`amazon.nova-pro-v1:0`), confirmed on this account at 2M TPM / 25 RPM with no
  Marketplace step. Non-Anthropic, so it is not the generator's family. Pinned version, temperature 0.
- **Rubric in version control** at `src/musical_mycelium/eval/rubrics/`, with concrete anchors per score
  level, next to the code.
- **30 hand-labeled items, blind, labeled by him.** This is the phase's only real block on his time.
  **Cadence, reusing what worked for all 25 gold cases: one item at a time, one judgement each, from a
  draft I pre-fill, never typing JSON.** Labels are collected before the judge is ever run on them.
- **Agreement is measured and reported permanently**: raw agreement and Cohen's kappa, printed next to
  every judged metric. Enforced structurally — `report.py` raises if asked to render a judged number with
  no agreement figure loaded. A judged score with no agreement is decoration, so make it unrenderable.
- **The re-measure budget is decided now, not later:** if agreement is poor, the rubric is rewritten with
  concrete anchors and re-measured **at most twice**. After that the judged metric ships marked
  `agreement: poor` with the figure visible, rather than being tuned until it flatters.

#### Step 7 splits into 7a / 7b / 7c — decided 2026-08-19

Step 7 is the only step in this phase that cannot be finished in one sitting, because 30 hand labels is
his time and not mine. It is therefore split into three parts that are **started and finished in
different sessions**, possibly days apart. Any agent picking this up mid-flight reads this section first.

**The finding that forced the split: there is nothing to label yet.** `runner.py` holds `prose` on
`CaseRun`, but `score_case` drops it and `per_case` in all nine committed result files carries counts
only. Citation support and narrative quality both need the narrative text. So the labeling pool does not
exist and has to be produced — and it has to come from a **real-model** run, because judging scripted
prose would be the same category error step 5 caught with `SCRIPT_DETERMINED`.

- **7a — the machinery (free, $0, one session).** Prose persistence into a transcript file, the rubric at
  `eval/rubrics/` with concrete anchors per level, the judge module on Nova Pro through the existing LLM
  seam, the agreement math (raw agreement and Cohen's kappa), the `report.py` guard that refuses to
  render a judged number with no agreement loaded, and the labeling harness. Tests for all of it, and
  every new lock broken deliberately before it is trusted.
- **7b — the 30 labels (his time, resumable across sittings).** Expected shape is **three sittings of
  ten**, not one of thirty. See the cadence contract below; it is a requirement on 7a's harness, not a
  hope.
- **7c — the judge run and the agreement number (spend, gated).** One live run to produce the pool
  (~$0.36 at step 4's measured rate) — which in practice happens at the *start* of 7b, since there is
  nothing to label without it — then the judge pass over the 30 labeled items on Nova Pro, then agreement
  computed, recorded, and rendered. Behind the usual confirmation naming the estimate.

**The cadence contract for 7b, and it is binding on the harness built in 7a:**

- **One item at a time, one judgement each, from a draft I pre-fill. He never types JSON and never types
  a QID.** This is the cadence that carried all 25 gold cases on 2026-08-14 and it is the only reason
  30 items is tractable.
- **Labels are written after each item, not at the end of the sitting.** A session that dies at item 7
  loses nothing. The label file is append-only.
- **The harness names where it is** — "18 of 30 labeled, next is `judge_pool_019`" — so a session
  starting cold does not have to reconstruct progress from a diff. Resuming is a command, not an
  archaeology exercise.
- **Ten is a sitting, not a target.** Stopping at 4 or going to 14 must both be ordinary.
- **Blindness is structural.** Labels are collected before the judge is ever run on the pool, and a test
  asserts that no judge score can be present in the label file. A human label written next to a machine
  score is not an independent label, and there is no way to detect it after the fact.

#### Step 7a, as-built — the machinery, 2026-08-19 (free)

`make check` is 1085 pass, 0 skip, 7 deselected. Every new lock below was broken deliberately, watched
to fail, and restored — the practice from 2026-08-14, and it caught nothing new this time, which is
worth recording precisely because a night where it catches nothing is the only evidence that the ones
it does catch are real.

**What `citation_support` actually asks, and it is not what `07` §4.4 imagined.** §4.4 asks whether the
cited source *supports* the claim. That question is unanswerable in this system and the reason is
structural: the agent never queries Wikidata live, the judge has no more access to a statement's content
than the agent does, and fetching it would mean judging against a source the pinned artifact does not
contain. So the judged question is the one that *is* answerable and is also the one this project should
be asking: **does the prose assert exactly the claim it was built from, and nothing the claim set does
not carry?** Levels `SUPPORTED / OVERSTATED / UNSUPPORTED`.

That is not a weaker question. The gate already guarantees every claim is a real edge with real sources;
nothing guaranteed the *prose* stayed inside the claim set, and the characteristic failure of a language
model writing from an approved list is not inventing an edge — the gate makes that impossible — but
decorating one with a decade, a city, or a mechanism no claim carries. **Every deterministic metric in
the catalog scores that answer perfectly.** This is the only place in the suite where "did the prose
overstate the evidence" is asked at all. The rubric states both the question and the three things it
explicitly does not ask, so the divergence from `07` is visible where the scoring happens.

**One item is one answer plus one focus claim, and it carries two judgements.** Citation support is a
per-claim question (`07` §4.4 samples claims) and narrative quality is a per-answer one; pooling them
separately would have meant 60 items. Reading the answer is what costs time, not answering two questions
about it, so one screen carries both and each metric gets its own n=30 — which is exactly what §6 asks
for.

**A 30-item pool needs two live runs, and that is arithmetic rather than a preference.** 41 cases, 16 of
them refusal cases that refuse correctly, leaves roughly 25 answered per run. `build_pool` takes every
case once before it takes any case twice, so two runs give 30 items with maximum case diversity, and it
**refuses to build short** unless told to — a smaller n travels with every judged number permanently and
should be a decision, not a side effect.

**A scripted transcript is refused as a pool source.** `ScriptedLLM` synthesises the fixed string
`A grounded answer.`, so a pool built from one would have a human and a model scoring narrative quality
on a stub and produce an agreement figure that is real, reproducible, and about nothing. Same family of
error as gating a scripted run on a live-derived traversal number.

**Prose persistence is a separate file from the result file.** Three reasons in the module docstring; the
first is the one that governs: **the held-out set must never have a transcript**, and `guard_dataset`
refuses any dataset name containing `heldout` at all three doors — build, write, and load. A result file
carries aggregate metrics and case ids, and a case id is not content. Prose is.

**Judge hygiene is two locks, not one.** `agent/llm.py` gives `ROLE_JUDGE` its own default (Nova Pro)
rather than the shared fallback to the traversal model, so an unset `MYCELIUM_JUDGE_MODEL_ID` cannot
point the judge at Haiku; and `judge.guard_model` compares **vendors**, so a deliberate override to any
Anthropic model is refused too. Family, not model — next year's model names are not knowable today.
Temperature 0 is set at the seam by role, not by each caller, and `BedrockLLM` sends no temperature at
all unless one is configured.

**Blindness is enforced as an ordering.** The label file has a field allowlist that `load_labels` raises
on, the labels are bound to the pool by SHA-256 so a rebuilt pool is a loud failure rather than a quiet
re-pairing, and `run_judge` refuses to run until every item is labeled. And `report.render_judged`
raises when either agreement figure has n=0 — rule 2's shape applied to the judge, because decoration is
quotable and a crash is not. An *undefined kappa* is a different thing and still renders: a degenerate
label set has a real raw agreement and an honestly undefined chance correction.

**Agreement is raw agreement plus Cohen's kappa**, unweighted for the three support levels and
quadratically weighted for 1-5 quality, with exact and within-one both reported. The trap the tests
pin: **weighted kappa's scale must be the declared one, not the observed one.** A run using only 1s and
4s has an observed scale where those are adjacent, and the quadratic weight then forgives a three-point
miss as if it were one point. Measured 0.20 declared versus 0.56 observed-only on the same labels.

Files: `eval/transcripts.py`, `eval/labelling.py`, `eval/agreement.py`, `eval/judge.py`,
`eval/rubrics/{citation_support,narrative_quality}.md`, `render_judged` in `eval/report.py`,
`ROLE_JUDGE` in `agent/llm.py`, `JUDGE_REQUESTS_PER_MINUTE` in `eval/budget.py`, `make eval-label` and
`make eval-judge`, and four new test files.

#### Step 7b and 7c, as-built — the labels and the first agreement figure, 2026-08-20

**7b took two sittings, not three.** Final labels: `citation_support` 21 SUPPORTED / 8 UNSUPPORTED /
1 OVERSTATED; `narrative_quality` fourteen 5s, one 4, five 3s, one 2, nine 1s.

**7c, first run: $0.0562, Nova Pro, 30 items, revision `6cba963`.** `citation_support` exact 70.0%,
**kappa 0.48**; `narrative_quality` exact 63.3%, **kappa 0.66** quadratically weighted, within-one
76.7%. The full per-item disagreement analysis is in `docs/KNOWN-GAPS.md` and is not restated here.

**Four things this step taught that the plan did not anticipate:**

1. **The cadence in this doc was wrong for 7b and a later session had already corrected it.** "From a
   draft I pre-fill" was written for the gold set, where the drafts were *lookups he verified*. Here
   the draft would be the judgement — the thing being measured. KNOWN-GAPS narrowed it to **no
   pre-filled scores**; an assistant read this doc, not that one, and anchored two labels before the
   correction landed. **When this doc and KNOWN-GAPS disagree, KNOWN-GAPS is newer and governs.**
2. **Nothing bound the labels to the rubric, and this doc's own rewrite budget is what made that
   dangerous.** Two rewrites are budgeted for poor agreement; without a binding, a rewrite plus a
   judge-only re-run yields a kappa between a human who read v1 and a judge who read v2, looking
   entirely normal. `Labels.rubric_sha256` now closes it, and the open question it exposes — does a
   rewrite mean re-judging or relabeling — is his to answer, not the code's to answer silently.
3. **The judged half needed a prompt-injection defence and only a live run revealed it.** The pool
   contains the adversarial set, and `build_prompt` passed a planted injection into the judge under
   `QUESTION ASKED`. The judge mis-attributed the injected text to the answer. **The agent resisted the
   same injection cleanly** — the judge was the weaker half, and no amount of desk review had found it.
4. **The rewrite budget should not be spent on the first poor-looking figure.** Anchors derived from
   his labels, re-scored against those same labels, fit the rubric to the validation set. A clean
   rewrite needs a fresh pool and a fresh 30. **An honest 0.48 with a written diagnosis beats a fitted
   0.7**, and both rewrites stay available.

#### Step 7c, runs 2 and 3 — the judge's own noise, 2026-08-21

The re-judge after the injection fix was sized as a one-item confirmation. It returned a finding about
the method instead, and a third run was added to isolate it. **Full numbers and the per-item movement are
in `docs/KNOWN-GAPS.md` and are not restated here.** Three things this step taught:

1. **The judge is not deterministic at temperature 0, and this is now measured.** Runs 2 and 3 were
   produced from byte-identical prompts — `input_tokens` 67,030 in both, to the token — and disagreed on
   3 of 30 `citation_support` judgements and 7 of 30 quality scores. `JUDGE_TEMPERATURE = 0.0` is set,
   applied by role, and sent; it suppresses sampling and does not guarantee determinism on hosted
   inference. **Consequence for anything this phase reports: a judged figure is a range, not a point** —
   kappa 0.44–0.48 and 0.66–0.73 — and the qualitative band, which held across all three runs, is the
   part that may be stated flatly.
2. **A prompt change to a judge is a change to every item it scores.** The injection fix was written up
   as affecting one item because one item carried the injection; it added the fence and a system-prompt
   line to all thirty prompts and moved seven of them. This is obvious in retrospect and was in nobody's
   estimate, including the one in this document.
3. **This is the step 5/6 lesson recurring one layer up, and it should be read that way.** Step 6 had to
   run before step 5 because a threshold set from one run sits inside the unmeasured spread. Step 7
   produced an agreement figure from one run and the same trap was waiting: **the judge needed a noise
   floor for the same reason the agent did, and nothing in the plan asked for one.** The general rule the
   project keeps re-learning is that *any* number produced by a model needs its spread measured before it
   is quoted, and that includes numbers produced by the thing measuring the model.

**Deliberately not done, with the reason:** a five-run judge floor. It needs `noise.py` extended to judge
runs and a provenance fix first (both logged in KNOWN-GAPS), and it measures a metric that never blocks.
Three runs and a stated range is where this is being left.

#### The synthesis fixes step 7 found — 2026-08-21 (free)

In scope under §4: a metric revealing an agent *bug* makes the fix part of this phase. Six defects were
logged during hand-labeling and deliberately not fixed while the pool was being labeled. **Full detail and
the per-defect checkboxes are in `docs/KNOWN-GAPS.md`; not restated here.** What belongs in this document
is what the step taught about the eval suite itself:

1. **The prompt wording was the symptom; the missing shape was the cause.** `ApprovedClaimSet` modeled two
   answer shapes — a fan-out from one subject, and a chain — and the gold set has **four descendants
   cases**. `subject_id` returns `None` for a fan-in, meaning *not this shape*, and `synthesize` read it
   as *no subject* through `subject_id or ""`. Four of the six logged defects were that one gap.
2. **This is the third instance of the repo's named failure mode and the second of "assume the origins
   direction."** A fallback answered a different question and never raised. It is worth noting *where* it
   was caught: not by any deterministic metric — all of them scored the broken output perfectly, because
   the claims underneath were real, cited and correctly directed — but by a human reading thirty answers.
   **That is the argument for tier 2 stated as a measurement rather than a preference**, and it is the
   most quotable thing this phase has produced.
3. **The eval suite's blind spot has a shape, and it is "did this answer the question asked."** Both
   halves miss it: every tier 1 metric by construction, and the judge empirically (`018`, `021`). Naming
   it is not fixing it; it is a phase 6/7 question and it is now written down as one.

Method note: nine tests, each locking a property rather than a phrasing, and **five mechanisms broken
deliberately and watched to fail** before being restored. The `_fan_in` prompt was printed and read at
each stage rather than reasoned about, which is what surfaced both the blank subject and, later, a
grammar defect ("Documented as came out of it") that no assertion would have caught.

### Step 8 — Tier 2, judged and sampled (spend, gated)

Citation support and narrative quality only. 20–30 samples, release candidates only, behind the same
explicit confirmation naming the dollar figure.

#### Step 8, as-built part 1 — the machinery, 2026-08-23 (free)

`src/musical_mycelium/eval/tier2.py`, `make eval-tier2`, 24 tests. **Free; the judged run itself is
part 2 and spends.** The same judge, pointed at a different subject: `eval-judge` scores a pool a human
already labeled and its number is about **the judge**; `eval-tier2` scores a sample of a release
candidate and its number is about **the agent**.

**The design problem, and it is the only interesting thing in this step.** Step 7 made "agreement is
reported next to every judged number" structural by making it a required field on `JudgeRun` — the score
and its validation are one object, so no caller can separate them. That trick does not survive the move
to step 8, because **a release candidate has no human labels and must not get any**: the labels exist to
validate the judge, and re-labeling every candidate would make having a judge pointless.

So the figure is **inherited** rather than computed, and an inherited figure is exactly the kind that goes
missing. `Validation` is therefore a required field on `Tier2Run`, read from the committed judge runs;
`to_json` nests each metric *inside* the same object as its agreement rather than emitting two parallel
blocks, because parallel blocks are what let a reader — or a future README — quote one without the other;
and `render` refuses outright when either inherited figure is unmeasured, the same shape as
`report.render_judged`.

**Every judged number here is a range**, carrying the 2026-08-21 finding forward into code: the judge is
not deterministic at temperature 0, so `Validation` reports low–high across the validation runs and bands
*both ends*. When the two ends land in one Landis & Koch band the label is stated once and may be stated
flatly; when they straddle a boundary both labels are printed rather than the flattering one. A single
validation run cannot express a spread at all and is reported as one sample with the caveat attached.
Run against the three committed judge runs it reproduces the recorded figures exactly — `citation_support`
kappa 0.44–0.48 (moderate), `narrative_quality` 0.66–0.73 (substantial), n=30.

**Six refusals, all before `confirm_spend`,** so a misconfigured tier 2 run costs nothing: no committed
judge run to inherit from, judge runs that disagree with each other on model or pool, a rubric the labels
were not written against (`guard_rubrics`, reused not reimplemented), a judge the agreement was not
measured on, a same-family judge, and a source whose code revision is not pinnable. That last one is what
"release candidates only" means in code: a score attributed to a `-dirty` tree names no particular code.

**Method.** Six locks broken deliberately and watched to fail before being restored — the required
`validation` field, the judge-model guard, the nesting in `to_json`, the sample pool's distinct name, the
undefined-kappa handling, and the release-candidate check. The pool-name break is the one worth naming:
`build_pool` hardcoded a single name and item-id prefix, so a tier 2 sample would have produced
`judge_pool_v1_007` ids colliding with the human labels — a mis-pairing nothing downstream would have
caught. `name` is now a parameter, defaulted to the validation pool so no existing caller changed.

**Two defects fixed on the way through, both found rather than looked for:**

1. **The false-dirty provenance defect** (logged 2026-08-21, in `KNOWN-GAPS.md`) is **fixed**.
   `provenance.code_revision` now exempts `eval/results/` from the cleanliness check and nothing else.
   It had to be fixed here rather than later: step 8's release-candidate guard rejects an unpinnable
   revision, and a run stamped `-dirty` by its own predecessor's output would have failed that guard for
   a reason that has nothing to do with the code. Locked in both directions — a stray result file does
   not dirty the stamp, a stray *source* file still does — plus a rename, a lookalike path
   (`results_backup/`), and an unparseable status line, which counts as dirty because guessing there
   would be a false *clean*.
2. **`make help` could not see its own new target.** The filter was `^[a-zA-Z_-]+:` — no digits in the
   character class — so `eval-tier2` was a real, working, documented target that the command whose entire
   job is discovery did not list. Nothing failed; it was simply invisible. Fixed, and locked with a test
   that reads the pattern *out of the Makefile* and asserts it matches every `##`-documented target,
   rather than restating the pattern in the test where the two could drift.

`make check`: **1138 passed, 0 skipped**, 7 `costs_money` deselected.

#### The 41-case verification run, 2026-08-23 (spend, ~292k tokens)

Taken to turn the 8/21 synthesis evidence — four case ids — into a statement about the whole set.
`20260823T231500Z`. All five gates passed; `cases_correct` 39/41, both failures already on the books
(`gold_v0_1_020` reproducible, `adv_008` known-unstable). **Zero prompt-leak phrases, zero verbatim
repetition, zero "came out of" on an artist edge, and all four fan-in cases naming distinct
descendants.**

**What this run is evidence of, and what it is not.** The deterministic metrics did not and could not
confirm the synthesis fixes — that is step 7's most quotable finding, restated by this run: every tier 1
number sat inside the floor both before the fixes and after, because the claims underneath were always
real, cited and correctly directed. The confirmation came from reading the prose. The eval suite's blind
spot is unchanged and still shaped like "did this answer the question asked."

**Two limits, stated rather than smoothed.** The floor it is compared against was measured at `f84453a`
and this run is `bb54263`, so the comparison is a sanity check and not a pooled measurement — `noise.py`
would refuse to pool them, correctly. And the run is stamped **`bb54263-dirty`**: the tree was being
edited when `main` snapshotted the revision, which is precisely the hazard `write_result`'s docstring
documents. **The prose verification did not need a pinned revision and stands. A tier 2 release
candidate does**, so part 2 needs either a clean re-run or an explicit `--allow-unpinnable` and a score
that names no particular commit.

**Process note worth keeping:** the parallelism that produced the dirty stamp — building while a
billable run was in flight — was a bad trade and is not one to repeat. Free work during a live run has
to happen outside the tree, or wait.

#### What the third run found, 2026-08-23 (free fixes)

The run aborted at case 33 of 41. **Two defects, one in the agent and one in the harness; full detail and
the before/after are in `docs/KNOWN-GAPS.md` and not restated here.** What belongs in this document is
what the pair taught about the suite:

1. **The eval suite found an agent bug that nine earlier live runs and the entire scripted suite could
   not.** Not because the metrics improved — no metric was involved. The case *crashed*, and it crashed
   only because the full 41-case set was run against a non-deterministic case for the tenth time. This is
   the second time this phase that breadth, rather than a better measurement, is what produced the
   finding; the first was step 7's human reading thirty answers.
2. **A recovery mechanism inherits the response of whatever it was copied from.** The 8/17 fix caught
   every exception and then did what the budget abort did: stop. That is correct for an unaffordable tail
   and wrong for one broken case, and the difference went unnoticed for six days because both are spelled
   "an exception reached the loop". **The lesson is narrower than "catch more": it is that *stop* and
   *skip* are different answers and the code was only ever asked the first question.**
3. **Three separate places read `aborted_reason` as the explanation of an incomplete run.** Introducing a
   second shape of incomplete — finished, but missing cases — made all three print "()" or point the
   reader at a field that was empty. A field that has always been non-empty when reached acquires
   readers who assume it.

`make check`: **1152 passed, 0 skipped**, 7 `costs_money` deselected. Every new lock was broken
deliberately and watched to fail: six on the agent side, five on the harness side.

**Part 2 is the judged run** and it needs a post-fix release candidate to sample from — judging output
written before the 2026-08-21 synthesis fixes would measure answers already known to be broken.

#### Step 8, as-built part 2 — the first tier 2 run, 2026-08-24 (spend, ~46k tokens)

**Step 8 is closed and DoD #2 with it.** Numbers, the near-controlled before/after, and the two open
findings are in `docs/KNOWN-GAPS.md` and not restated here. What belongs in this document:

1. **The sample landed on 19 of the 26 cases the validation pool used, by accident of seeding.** That
   turned a tracked quality metric into something close to a controlled before/after across the 8/21
   synthesis fixes — the strongest quantitative evidence this phase has produced that those fixes
   worked, and it exists because both pools draw from the same 41-case dataset rather than because
   anyone designed it. Worth designing on purpose if a future phase wants a real regression comparison.
2. **The judge's measured run-to-run noise is what made the movement readable.** Mean quality moved 1.3
   against a noise floor of 0.10 taken from the three validation runs. Without that figure the number
   would have been an anecdote; `.claude/rules/evals.md`'s "measure the noise floor" earned its place
   here on a metric that never blocks.
3. **The first thing tier 2 found, it found about the judge rather than the agent.** Four of six
   low-scored items penalise correct answers — a minimal correct answer marked down for "restating the
   question", a fan-out marked down for not being a chain. That is the phase's blind-spot finding
   arriving from the other direction: step 7 showed the deterministic metrics cannot see answer quality,
   and step 8 shows the judge cannot fully see it either. **Neither half of the suite is a substitute
   for reading the answers**, and that sentence is now supported by evidence from both halves.

### Step 9 — The held-out run, once, at freeze

After everything above is frozen. `make eval-heldout` decrypts in memory, runs, and writes **aggregate
metrics and case ids only**.

**Structural rule, and the reason this step is last: no held-out case content may enter a result file, a
log line, a test failure message, or an agent's context.** The result writer uses a field allowlist and a
test asserts that no case query, label, or claim text can reach the output — the same shape as
`heldout-check`, which already prints `heldout_v1_007: claims-diverged` and never the case. I will not
read the plaintext, will not ask for the key, and will not open the `.enc`. If a metric fails on the
held-out set and the failure is not diagnosable from ids and problem codes alone, **the correct outcome is
to report it undiagnosed**, not to look.

Held-out numbers are reported in their own section, separately from the development set's.

#### Step 9, as-built part 1 — the runner, 2026-08-24 (free)

`src/musical_mycelium/eval/heldout_run.py` and `make eval-heldout`. Built **blind**: the `.enc` was never
opened, the key was never requested, and the case schema was read off `heldout_draw.py`, which is
committed and whose output is generated rather than authored.

**Four locks, not one, because the four leak paths are different and a single guard would have to be
right about all of them.** Each was verified by breaking it deliberately, watching the test fail, and
restoring — the practice from 2026-08-14, and the only defence against this repo's named failure mode.

| lock | closes | broken deliberately |
|---|---|---|
| `sanitise` strips `CaseError.message` | stdout **and** the file. `report.py:77` prints it verbatim, and it is `str(exception)` — a synthesis failure can quote a node label or a claim | 2 tests failed |
| `redact` rebuilds the payload from positive allowlists | the file. Forward-looking: a `"query"` added to `per_case` for debugging never reaches disk | 3 tests failed |
| `assert_writable` substring-checks the serialized payload against every case query | a route nobody thought of, including one introduced in a module this one does not import | 2 tests failed |
| no transcript, locked structurally | `live.main` writes one after every run. A held-out transcript would be the whole set in plaintext, committed | 1 test failed |

Plus the progress line: `run_live` prints `case.query[:60]`, which is correct there and a direct
plaintext disclosure here. It prints the case id and nothing else.

**`redact` fails closed and a test says so.** Dropping unknown keys silently would mean a metric added to
`suite.py` vanishes from held-out results with nobody told, so
`test_the_allowlist_covers_exactly_what_the_suite_emits` asserts the allowlist equals what `to_json`
emits. Adding a field to the suite now breaks that test and forces the held-out decision to be made
rather than defaulted into.

**Slicing is a deliberate, bounded disclosure and the reasoning is in the module.** Four slice dimensions
publish the set's coarse distribution across era, region and density buckets. `query_kind` is the
manifest's `shapes` under another name and discloses nothing new; the other three are new. It is made
anyway because the public manifest already publishes `shapes` and `refusal_count` on exactly this
argument, and because DoD 6 requires it — an aggregate that looks healthy while the sparse slices fail is
the default outcome without slicing, which is the question a held-out set exists to answer. No subject, no
query, no edge, and no case-to-bucket mapping is disclosed.

**Preflight before a cent is spent:** `verify_seal` (tamper check, no key), then `check_against_corpus`
(ids and codes only). Any finding refuses the run rather than warning, because the one shot spent against
a drifted corpus is spent. Re-sealing to make it pass is forbidden by `.claude/rules/heldout-set.md`.

**Held-out numbers are reported, never gated.** `DATASET = "heldout"` matches no threshold set, and
`thresholds.render_unmatched` already says the right thing: *"thresholds measured on one dataset do not
transfer to another. This is not a pass."* A held-out set that gates is a held-out set being tuned on.

`make check`: **1169 passed, 0 skipped, 7 `costs_money` deselected**, up from 1152.

Remaining in step 9 at the time part 1 landed: he runs it once. That happened the same day — part 2.

#### Step 9, as-built part 2 — the held-out run, 2026-08-24 (spend, ~75k tokens)

He ran it. `results/20260824T120956Z-heldout.json`, code revision `d6f521a`, clean, complete, no errored
cases. 48 requests, 70,490 in / 4,538 out, roughly nine cents. **The estimate was 2x high on tokens and
1.5x on requests**, consistent with the 2.2x over-estimate already recorded at step 6 — erring high is
correct for a spend gate and the figure is still not a cost estimate.

Preflight passed before a cent was spent: `verify_seal` matched the manifest, and `check_against_corpus`
reported the set still agrees with artifact `0.5.0`.

**The result, beside the development set's most recent run at the same revision:**

| | held-out (10 cases, n=1) | dev (41 cases, n=1) |
|---|---|---|
| edge_groundedness | 100% (44/44) | 100% |
| citation_resolution | 100% (44/44) | 100% |
| refusal accuracy | true 2/2, false 0/8 | true 16/16, false 0/25 |
| traversal_recall | 100% (54/54) | 100% |
| traversal_precision | 100% | 100% |
| plan_adherence | 10/10 exact | — |
| cases correct | 10/10 | 41/41 |
| injection scored | **0 of 10** | 5 |

**What this earns, stated at exactly its strength.** On ten questions the agent was never tuned against
and that no one working on it had read, every measurable property matched the development set. That is
the specific thing a held-out set is drawn to detect, and it did not detect it. **It is not evidence that
the agent is perfect, and the numbers being identical rather than merely close is itself a reason to read
the limits below before quoting any of it.**

**Four limits, none of which the number discloses on its own:**

1. **n=1, and this project has measured that n=1 is not enough.** The noise floor showed `true_refusal_rate`
   swinging 12.5 points across five *identical* dev runs. The held-out set has no error bar at all, and
   at 2 refusal cases a single flip moves that metric 50 points. It cannot be given one without re-running
   the set, and re-running it costs the property it exists to have.
2. **One of the five blocking properties is unmeasured here.** `heldout_draw.py` plants no injections, so
   `injection_resistance` scored 0 of 10 cases. The report says so rather than reporting a free pass, but
   the held-out set says *nothing* about injection resistance and never will.
3. **The era and region slices came back degenerate, and this was not predicted.** 9 of 10 subjects are
   `undated` and 9 of 10 are `unstated` for region. **This is a real cost of the draw-versus-curate
   decision made on 2026-08-14**: the gold set was *curated* to span eras and regions, and a stratified
   random sample inherits the corpus's missingness instead — most nodes carry no inception year and no
   P495. So the held-out set cannot answer "does this hold up on older or non-Western material", which is
   one of the questions a held-out set is most wanted for. Logged rather than fixed: re-drawing to correct
   it would mean drawing a set chosen for its slice profile, which is a curated set with extra steps.
4. **`verification_mix` shows `HAND=0`.** No held-out claim rests on a hand-verified edge, which is
   `not_sought` behaving exactly as documented and is not a defect.

**The set is now spent for this freeze, and the condition for ever running it again is written into
`.claude/rules/heldout-set.md`:** it may be re-run at a future freeze **only if nothing was tuned in
response to this result.** Every run after the first must be reported with the run count. A set re-run
after a change made because of what it said has stopped measuring generalisation and started measuring
how many attempts it took.

## 4. Explicitly not in this phase

- **The SPA, visualization, the guided tour.** Phase 5.
- **New agent capability, new tools, new corpus.** If a metric reveals an agent *bug*, the fix is in
  scope. A new agent *feature* is not, however obviously it would raise a number.
- **A second source per edge**, and therefore `contested`. Phase 6, decision A1, not re-litigated.
- **The historical trend view and the public writeup.** Phase 7. This phase only has to store results in a
  shape phase 7 can read, which is why they are per-run JSON files rather than an overwritten single file.
- **Editing the gold or held-out sets to make anything pass.** Not deferred — forbidden.
- **The Bedrock redeploy.** See §8.

## 5. One-way doors touched

| Door | How this phase satisfies it |
|---|---|
| 1. Claims first, prose second | Untouched. The suite reads `GateResult` and approved `Claim`s; it never asks a model whether a claim was grounded. Groundedness stays a dictionary lookup. |
| 2. Provenance on every edge | Untouched; `citation_resolution` is the metric that proves it still holds. |
| 3. Validated graph semantics | Untouched. No ingestion in this phase. |
| 4. Agent-to-data tool contract | **Tested by not being edited.** The runner drives `default_registry()`. If driving a new dataset requires touching the loop, the seam is broken and that is a finding, not a workaround. |
| 5. Everything in Terraform | Only if step 4's CloudWatch question is taken up; see §8. No console clicks either way. |
| 6. Package boundaries | All new modules land in `eval/`. `eval` may import `agent` and `graph`; nothing imports `eval`. |
| 7. LLM provider seam | **This phase is the seam's first real exercise.** The runner takes an `LLM`, and `build_llm(provider, role=...)` chooses it. Judge and generator are different providers in the same run, which is exactly what the factory was for. |
| 8. Lambda container image | Untouched. |
| 9. Response streaming | Untouched. The suite drives the loop in-process, not over HTTP. |

## 6. Files, by path

**New:**

```
src/musical_mycelium/eval/runner.py          dataset-agnostic case driver
src/musical_mycelium/eval/budget.py          RPM limiter, cumulative token budget, backoff
src/musical_mycelium/eval/suite.py           tier 1: load, drive, score, slice
src/musical_mycelium/eval/report.py          the human-readable report
src/musical_mycelium/eval/provenance.py      the git revision a result file was produced by
src/musical_mycelium/eval/noise.py           step 6: spread and membership churn across N runs
src/musical_mycelium/eval/noise_floor.json   written by `make eval-noise ARGS=--write`, 5 clean runs
src/musical_mycelium/eval/judge.py           tier 2: Nova Pro, rubric, agreement
src/musical_mycelium/eval/heldout_run.py     step 9: the sealed set, run once, four leak locks
src/musical_mycelium/eval/rubrics/*.md       the rubrics, versioned next to the code
src/musical_mycelium/eval/thresholds.json    written from the baseline, not before
src/musical_mycelium/eval/results/           per-run results, committed
tests/test_runner.py  test_budget.py  test_suite.py  test_report.py  test_noise.py
tests/test_judge.py   test_heldout_run.py
```

**Changed:**

```
src/musical_mycelium/eval/harness.py   delegates driving to runner.py; baseline output unchanged
src/musical_mycelium/eval/__init__.py  exports
Makefile                               eval, eval-live, eval-noise, eval-judge, eval-heldout
src/musical_mycelium/eval/live.py      write_result records written_at and code_revision
.github/workflows/ci.yml               tier 1 scripted on every commit
pyproject.toml                         nothing new expected; tool config only if it is
docs/KNOWN-GAPS.md                     items checked off with evidence as they close
docs/eval-suite-explained.md           the plain-English write-up (§11), written 2026-08-24
```

**Root discipline:** 15 of 18 entries in use. This phase adds **no** root entries — results go under
`eval/`, targets go in the existing `Makefile`.

## 7. How it is tested

- **Every metric already has a unit test over synthetic input**, including two vacuous-truth guards. The
  new work is the *suite's* tests: that a truncated run reports `complete: false`, that the limiter
  actually limits, that `BudgetExceeded` aborts rather than continues, that the report refuses to render a
  judged number without an agreement figure, and that the held-out writer cannot emit case content.
- **Break every new lock deliberately, once.** The baseline drift test, the budget abort, the agreement
  guard, the held-out allowlist. Watch each fail, then restore. This is the practice that worked on 8/14
  and it is the only reliable defence against the repo's named failure mode — assertions written from a
  mental model and never executed.
- **Attack the metrics.** The difflib coverage bug is the precedent. Specifically: an empty output must
  not score 100% groundedness (already guarded), a run of zero cases must not report 100% anything, and a
  case that refuses everything must score badly on refusal accuracy's second half.
- `make check` stays green throughout: **977 passed, 0 skipped, 7 `costs_money` deselected** as of
  2026-08-17, up from 852 when this doc was written.

## 8. Cost, and the one decision this doc does not make

Steps 1–3 and 5 are $0. Steps 4, 6, 7, 8, 9 spend, each behind an explicit confirmation naming the
estimate. **No dollar figure appears in this repo's code or docs** — prices come from
`MYCELIUM_TOKEN_PRICES` at runtime and the per-run cost is *measured* from step 4's recorded usage, not
estimated here.

**DoD 8 — "real per-run cost recorded to CloudWatch, not estimated" — cannot close in this phase without a
decision that is yours.** The EMF format is proven and unit-tested; no record has reached CloudWatch
because the deployed Lambda runs `llm_provider=local`. Closing it needs the Bedrock redeploy, and per
`KNOWN-GAPS.md` that redeploy puts a billable model behind a Function URL with
`authorization_type = "NONE"`, where a streamed response bills the full duration even after the visitor
closes the tab.

**My recommendation: defer the redeploy to phase 5**, where the SPA needs a live backend anyway and the
auth/throttling decision can be made once instead of twice. Phase 4 then closes DoD 8 as far as it
honestly can — cost measured and recorded per run from real usage, in committed result files — and
`KNOWN-GAPS.md` keeps the CloudWatch clause open with the reason. The alternative, if you want it closed
now, is a bounded one-off: redeploy with `provider=bedrock`, reserved concurrency 1 and a tight timeout,
invoke once from the CLI, confirm the EMF record landed, revert to `local`. That is maybe an hour and a
trivial spend, and it does briefly expose a billable public URL.

Either way the resume line *"deployed on AWS Lambda and Bedrock"* stays unclaimable until the redeploy,
and this doc does not soften that.

## 9. Genuinely uncertain, named rather than smoothed

- **Whether the gold set survives contact with the runner.** 25 cases have never been executed. Field
  mismatches, `expected_path` direction, and cases carrying `axis`/`region` that others do not are all
  live risks. Step 3 exists to find them cheaply, before any money is spent.
- **Whether traversal recall means anything at 5 path cases.** Five multi-hop cases is enough for the
  metric to run and not obviously enough for a 5pp threshold to be stable. If the noise floor in step 6
  comes back wider than 5pp, **the threshold moves to match the measured noise, not the other way round**,
  and that gets written down.
- **Whether Haiku 4.5 refuses enough to score.** Refusal accuracy is a pair. A model that never refuses
  and a model that always refuses both produce a useless half. Three gold refusal cases and two held-out
  ones is a thin basis, and if the real-model numbers are degenerate, that is a finding about the dataset.
- **Judge agreement on narrative quality.** Citation support has a checkable referent; narrative quality
  does not, and kappa on a subjective rubric may simply come back poor. The two-rewrite cap in step 7
  exists so that discovering this costs a bounded amount.
- **Whether 27M tokens/day is actually reachable.** Five noise-floor runs plus a judged sample plus reruns
  in one day is the shape that hits it. The budget guard is a precaution against an untested ceiling.

## 10. Definition of done, mapped

| Scope DoD | Closes at | Note |
|---|---|---|
| 1. Tier 1 every commit, $0, blocks on five | steps 3 + 5 | scripted provider in CI; real-model runs stored separately |
| 2. Tier 2 only behind a confirmation naming the dollar figure | step 8 | **CLOSED 2026-08-24** |
| 3. Judge-human agreement measured and printed | step 7 | structurally enforced by `report.py` |
| 4. Noise floor over five identical runs | step 6 | |
| 5. Every metric unit-tested, vacuous-truth guard included | already met; extended | new suite-level tests in §7 |
| 6. Every result sliced four ways | step 3 | `slices.py` exists |
| 7. Held-out run once, reported separately | step 9 | **CLOSED 2026-08-24.** 10/10, reported in its own section; content never read |
| 8. Real per-run cost to CloudWatch | **PARTIAL, closed as partial 2026-08-24** | measured and recorded per run from real usage in committed result files; the CloudWatch clause stays open. The redeploy is **deferred to phase 5**, where the SPA needs a live backend and the auth/throttling decision is made once. See §8. |

Plus the three inherited items from phase 3 §0 — refusal accuracy, traversal recall, injection resistance
on real model output — all closing together at step 4.

## 11. The plain-English writeup

Written as the phase goes, not reconstructed after, per the `start-a-phase` skill: a short jargon-free
explanation of what an eval suite is, why a graph you own makes correctness a dictionary lookup instead of
a judgement call, and why a score with no measured noise floor and no measured judge agreement is not a
score. Lands in `docs/` alongside the phase docs. This is the cold-articulation rep and it is the part
that is genuinely hard to rebuild months later.
