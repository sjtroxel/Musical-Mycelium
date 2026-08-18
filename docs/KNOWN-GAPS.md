# Known gaps at `v0.3.0-local`

Written 2026-08-12, at the phase 3 release step. Required by
`docs/phases/phase-3-agent-loop-IMPLEMENTATION.md` §5.1, which asks that the tag ship with the open items
named and the residual gaps stated plainly.

**Updated 2026-08-14** when the gold set was completed and again when the held-out 10 was drawn and
sealed, and **2026-08-16** at phase 4 steps 3 and 4. Every claim below was re-derived against the repo
rather than copied forward.

**Updated 2026-08-17** at phase 4 step 6, part 1, and **2026-08-18** at step 5 — thresholds are written
and `make eval` blocks.

**Verified state:** `make check` green — 1008 passed, **0 skipped**, 7 `costs_money` tests deselected, mypy
clean, root 15/18, terraform valid. The former skip was the held-out seal; that set now exists, so
`test_the_committed_sealed_set_matches_its_manifest` runs and passes.

**What changed on 2026-08-16, in one line:** the agent has now been measured against a real model across
a whole dataset — 41 cases, 183 requests, ~$0.36 — closing DoD #11 (both halves) and the rate clause of
DoD #10. **The deployed URL still runs the template stub**, which remains the one gap with consequences
outside the repo and is untouched by any of this.

**Bedrock is not a blocker.** Access was restored 2026-08-11 after a twelve-day account-level quota fault.
Nothing here is waiting on AWS. What remains is unrun work, one undrawn dataset, and a small number of
standing facts about the corpus.

---

## Part 1 — open items, closable

Each of these can be finished. Mark `[x]` when it is, with the evidence.

### DoD #11 — refusal accuracy and traversal recall on real model output

**Both halves CLOSED 2026-08-16** by the first live run (phase 4 step 4). They were open for different
reasons and, as predicted, did not close for the same reason — but they closed in the same 17 minutes,
because both were only ever waiting on the same wiring plus the same billable run.

- [x] **Refusal accuracy against a real model. CLOSED 2026-08-16** by two live runs — 41 cases
  (25 gold + 16 adversarial) through Haiku 4.5, ~185 requests, ~290k tokens, ~17 minutes, ~$0.36 each.
  **Run 1: 15/16 true, 1/25 false. Run 2: 14/16 true, 0/25 false. Run 3 (2026-08-17): 16/16 true,
  1/25 false.** It is a rate now, not an anecdote — and **quote it as a range, never as a point.**
  Three runs on identical inputs span **87.5% to 100% true refusal, a 12.5pp spread**, which is wider
  than the two-run figure of 6.3pp this line carried until run 3 landed. See the variance note under
  traversal recall; it governs how any of these numbers may be used.

  **The denominator is the other half of that story and it is not noise.** There are 16 refusal cases,
  so **one case flipping is 6.25pp** and nothing smaller is possible. A "within 5pp" gate on refusal
  accuracy is arithmetically unsatisfiable on this dataset — it cannot be tripped by less than one
  case, and one case already exceeds it. Step 5 must express this threshold **in cases, not in
  percentage points.** `07`'s 5pp placeholder was never dimensionally sensible here.
  **Satisfied 2026-08-18** — the gate is `true >= 13 of 16, false <= 3 of 25`.

  Both misses are worth more than the rate. **`adv_008` is the one that matters**: asked "Where did
  metal come from?", where no node has the label `metal`, the model adopted one of `resolve_node`'s
  five suggestions and narrated it — producing **one approved, 100%-grounded, correctly-cited claim
  about a genre nobody asked about.** The case's own rationale predicted exactly this ("a confidently
  wrong resolution answers a question nobody asked, with sources, which is worse than a refusal"), and
  `harness.py` had marked it `NEAR_MISS_UNMEASURABLE` — *"a model choice, not a machinery property."*
  It is measured now, and the model lost. **This is the project's grounded-is-not-correct claim
  demonstrated rather than asserted:** every metric in the catalog scores that answer perfectly except
  the one asking whether it answered the question.

  The false refusal is `gold_v0_1_020` (`femtanyl` → `Woody Guthrie`, the deepest path case at seven
  nodes). Checked against the corpus: **the tools can answer it completely** — both endpoints resolve
  exactly and `trace_lineage` returns all seven nodes with six proposals. The model visited one node
  and stopped, with zero proposals reaching the gate. A model failure, not a corpus gap.
- [x] **Traversal recall against a real model. CLOSED 2026-08-16.** **Run 1: 93.5% (86/92). Run 2:
  100% (92/92).** Unmarked in both — `report.py` drops the `SCRIPT-DETERMINED` marker when the provider
  is not scripted — so these are the **first non-circular traversal numbers this project has produced.**

  **Read the two together, because the gap between them is the more important result.** Identical
  inputs, identical artifact, identical code, **6.5pp apart.** Both runs scored 39/41 while failing
  *different cases*: `gold_v0_1_020` went 0 claims → 6 and `adv_018` went 0 → 4, in opposite
  directions, so a stable-looking aggregate concealed a complete change of membership. Total approved
  claims moved 69 → 79.

  **Consequence, and it overrides the phase plan: the noise floor (step 6) must be measured *before*
  thresholds are set (step 5), not after.** A "within 5pp of baseline" gate derived from one run would
  sit inside the observed spread and fire on chance alone. `adv_008` failed in both runs, which looked like the
  one finding a single run was entitled to establish — **and run 3 on 2026-08-17 retracted even that.**
  It refused correctly the third time. Three runs, three different failure sets, **zero cases wrong in
  all three.**

  **Traversal precision was reported as 81.9% in that run and the real figure is 100%.** That is a bug
  the run found in the metric itself: the adversarial set carries no `expected_path`, so
  `traversal_precision` divided by `len(visited)` — nonzero — and ten adversarial cases each returned a
  confident `0.0` against a gold set that does not exist. Micro-averaging then dragged the headline
  down. The arithmetic was right and the question was wrong: *"what fraction of what you visited was
  on-path"* has no answer when no path was specified. `traversal_recall` got this right by accident of
  its denominator; precision needed it stated. **Fixed 2026-08-16** — an empty gold path now returns
  `Rate(0, 0)`, so those cases abstain from the micro-average instead of voting — with
  `test_precision_is_undefined_when_no_gold_path_was_specified` locking it. The difflib-coverage
  failure in miniature, and the reason `.claude/rules/evals.md` says a metric you have not tried to
  break is not a metric. **The first result file predates the fix and its precision figure should not
  be quoted.**

  History of the item, kept because it explains why the number took so long to mean anything:
  it had **never been scored on a real run**, and until
  2026-08-12 it had never been scored on any run at all — its only callers were `tests/test_metrics.py`,
  because the gold schema had no field it could read. `expected_path` fixed that, and the gold set now
  holds **25 cases including 5 multi-hop path cases**, so the metric has real chains to walk. What remains
  is the live half: **this is now blocked behind Bedrock only, not behind the gold set.**

  **Sharpened 2026-08-16.** The metric now runs over all 25 gold cases and reads 100%, and that number is
  worth nothing as a traversal result. `expected_path` is exactly the one-hop neighbourhood of the subject
  on every case, so any trace that makes one correct tool call scores perfectly — the trace policy
  provably cannot read the answer (`test_the_trace_policy_cannot_see_the_answer`), but non-circularity is
  not sufficiency. `traversal_recall`, `traversal_precision` and `plan_adherence` are listed in
  `suite.SCRIPT_DETERMINED` and `report.py` refuses to render a scripted result that has not declared
  them. **Consequence for phase 4 step 5: the 5pp traversal threshold must be set from the step 4
  real-model baseline and never from a scripted run.** **Satisfied 2026-08-18**, and more strictly than
  this asked: there is no aggregate traversal band at all, and a scripted run renders the gate `N/A`
  rather than evaluating it.

  The metric is not useless meanwhile, and this is why it stays: a direction-inverted traversal still
  scores **100% edge groundedness** — tools build proposals off the edge rather than off the argument, so
  a backwards walk produces claims that are individually true about the wrong nodes — while recall drops
  to 46.7%. Groundedness structurally cannot detect a direction inversion. Recall is the only metric in
  the catalog that can, which matters given how often this repo has assumed the origins direction.

### The noise floor — measured before any threshold is set

Phase 4 step 6, which now runs **before** step 5. Two live runs on 2026-08-16 disagreed by more than the
gate step 5 was going to adopt, so the spread has to be measured before a threshold can be chosen.

- [x] **The tooling exists and is tested. Done 2026-08-17.** `make eval-noise` pools result files and
  reports spread per metric **and membership churn** — which cases flipped, which is the half a
  stable-looking aggregate hides. `provenance.py` records a `code_revision` on every new result file, and
  `noise.py` refuses to pool runs whose revisions disagree; the 18.1pp `traversal_precision` gap between
  runs 1 and 2 was a metric fix landing between them, and nothing in either file said so. Four refusals,
  each broken deliberately and watched to fail: under two runs, mismatched pooling fields, an incomplete
  run, and a tolerance requested from a provisional floor.
- [x] **The five runs are done and the floor is recorded. 2026-08-17.**
  `eval/noise_floor.json`, five runs at `f84453a`, ~$1.80, spread over about 2.5 hours rather than
  back to back (which measures run-to-run variance *including* intraday drift — arguably more
  representative, and stated rather than hidden). `cases_correct` went 38, 38, 39, 40, 39: no trend.

  | metric | spread | what it licenses |
  |---|---|---|
  | edge_groundedness | **0.0pp** (100% x5) | block at 100% |
  | citation_resolution | **0.0pp** (100% x5) | block at 100% |
  | injection_induced | **0** x5 | block at zero |
  | traversal_precision | **0.0pp** | see the recall caveat |
  | traversal_recall | 0.0pp **as measured — read the caveat** | **not** a 5pp gate |
  | true_refusal_rate | **12.5pp** (87.5-100%) | **not** a 5pp gate; express in cases |
  | false_refusal_rate | 4.0pp | |
  | approved_claims | 5 (67-72) | tracked |

  **The recall caveat, and it is the most misreadable number in the file.** `traversal_recall` read
  86/92 in all five runs, and that 0.0pp is an artifact rather than stability. The metric has
  effectively **one degree of freedom** on this dataset: `gold_v0_1_020` has a 7-node expected path,
  contributes 1 of those 7 when it fails, and 92 - 86 = exactly 6. It failed all five times here and
  succeeded on 2026-08-16, when recall read 100%. **The honest floor for recall is bimodal at 6.5pp**,
  and a "within 5pp" gate would fire the first time that one case succeeds. A 0.0pp line in a JSON
  file is precisely what gets turned into a tight threshold later, so it is contradicted here.

  **`gold_v0_1_020` is the pool's one reproducible failure** — wrong in 5 of 5, and 6 of 7 across every
  live run ever. Four other cases were coins: `adv_008` (2 of 5 correct), `adv_009`, `adv_012` and
  `adv_018` (4 of 5 each). **No aggregate shows this**; every run scored 38-40 of 41 while the
  membership changed underneath.

- [x] **Step 5 is DONE — 2026-08-18. `eval/thresholds.json` is written and `make eval` blocks.** Two of
  the five gates could not be percentages and are not. Refusal accuracy moves 6.25pp per case on a
  16-case denominator, so it is expressed **in cases**: true refusals >= 13 of 16, false refusals <= 3
  of 25, one case of slack below the worst observed because four adversarial cases are measured coins
  and a gate at the worst observed value would fire on chance. Traversal recall is bistable on one
  case, so it is a **per-case** check over the 24 gold cases that reached their full expected path in
  all five baseline runs. The other three block at their measured floor of zero.

  **What the free every-commit run can actually gate is three of the five, not five.** Traversal is
  `SCRIPT_DETERMINED` on a scripted run and the gold-only run plants no injections, so both render
  `N/A` — a third state that is never counted as a pass and is reported separately from passes, so a
  run where nothing could be checked cannot read as green. The other two gates need a live run and
  therefore money. This narrows DoD #1 and is the honest reading of it.

  Two guards worth knowing about before touching this. **A subset run is not gated at all** —
  `make eval-live ARGS='--cases 1'` is `complete=True`, so without that guard the traversal gate would
  fail it for 23 absent baseline cases and the cheapest sanity check in the project would exit
  non-zero looking like a regression. And **thresholds are keyed on dataset *and* provider**, because
  the live set has 16 refusal cases and the scripted one has 3; a count gate crossing that boundary
  compares two different questions.

  Method note kept because it is the part that is easy to get wrong next time: all five runs must
  share a `code_revision`, which means **no commit and no edit between the first run and the last.**
  The four earlier live runs are good step 4 data and are not in the pool — two predate
  `code_revision` entirely and read `unknown`, and two predate the fixes below. `noise.py` refuses
  them rather than averaging across the change, which is the whole reason the field exists.
- [x] **Four defects found by the first attempt at the pool, all fixed 2026-08-17**, each with a lock
  broken deliberately and watched to fail. A throttle on case 41 of 41 destroyed forty completed cases
  because `run_suite` caught only `BudgetExceeded`; the limiter paced at exactly the 10 RPM quota with
  no headroom for the retries botocore performs invisibly to it; `code_revision` was read at write
  time rather than run start, which nearly mis-stamped a clean run; and the CI failure that surfaced
  alongside was a 1%-probability PKCS#7 padding artifact in an unauthenticated cipher, not a
  regression. `make check` also did not run `make eval` while claiming to be everything CI runs.
  Detail in `docs/phases/phase-4-eval-suite-IMPLEMENTATION.md`, step 6 part 1b.
- [x] **`eval/noise_floor.json` EXISTS — five runs at `f84453a`, recorded 2026-08-17.** This item read
  "does not exist yet" until 2026-08-18; it was stale from the moment the pool was written and is
  corrected here rather than deleted, because a checklist that quietly loses its wrong entries stops
  being evidence of anything. Step 5 read it and is now closed above.

### Found during the noise pool, logged rather than fixed — 2026-08-17

All three were found while the five runs were in flight, when the repo was frozen so the pool could
keep a single `code_revision`. **Logging instead of fixing was the deliberate call:** fixing on every
finding restarts the pool on every finding, and the floor never gets measured. None of them affects
what the pool measures — the floor reads aggregate spread and per-case churn, and neither touches
slices.

- [ ] **`query_kind` is a slice assigned by the model, not by the dataset.** `slices.query_kind_slice`
  reads `Plan.query_kind`, which the model produces in its plan turn, so **bucket membership moves
  between runs on identical input** — origins went 28 to 27 and lineage 7 to 8 across two runs. A
  slice whose membership changes cannot be compared across runs, which is exactly what a threshold
  and a noise floor need to do, and `.claude/rules/evals.md` requires slicing by query type.
  **Fix:** the gold set already authors a `shape` per case (16 origins, 5 path, 4 descendants);
  `EvalCase` does not carry it. Thread it through, prefer it, fall back to `Plan.query_kind` only
  where no shape was authored, and lock it with a test asserting two runs produce identical slice
  denominators. **Related and lesser:** `era`, `region` and `density` derive from the *resolved
  subject node*, so a substitution like `adv_008`'s moves a case between buckets too. Those three
  held stable across all five runs; the exposure is the same shape and is worth a note in the fix.
- [ ] **`noise.py`'s report overclaims at small n.** It prints "reproducible failures: N (wrong in
  every run, so not chance)". At two runs that phrase means "wrong twice", and `adv_008` was wrong in
  both runs of a two-run pool while being correct in 2 of 5 of the real one. **The exact trap the
  module exists to prevent, in the module's own output.** Soften the wording while the floor is
  provisional.
- [ ] **`gold_v0_1_020` is a product bug, not just a metric.** It false-refuses "How does femtanyl
  connect back to Woody Guthrie?" — a question the tools answer completely; `trace_lineage` returns
  all seven nodes with six proposals. It failed **5 of 5** in the pool and 6 of 7 across every live
  run. A user gets a refusal on an answerable question the large majority of the time. Belongs on the
  phase 5 list; it is not an eval defect.

### DoD #12 — token cost to CloudWatch

The item is partial, and its two clauses are in different states.

- [x] **The working model ID is recorded.** `us.anthropic.claude-haiku-4-5-20251001-v1:0`, at
  `phase-3-agent-loop-IMPLEMENTATION.md:547` and in `.claude/rules/aws-and-cost.md`.
- [ ] **Token cost measured and emitted to CloudWatch.** Measured: yes, real usage off `Done`, and
  `api/telemetry.py` is unit-tested. Emitted: **no EMF record has ever reached CloudWatch.** The deployed
  Lambda runs `llm_provider=local`, so its token counts are synthetic, and the live tests run on a
  developer machine where stdout is a terminal rather than a log stream. The format is proven; the
  pipeline is not. Requires the redeploy below.
- [x] **`MYCELIUM_TOKEN_PRICES` is absent from `infra/terraform/main/lambda.tf`'s environment block.**
  **Fixed 2026-08-12.** Added as `var.token_prices`, defaulting to `""`. Empty is a working state, not a
  broken one — token counts still reach CloudWatch and dollars stay silent — and `load_prices` already
  treats empty and unset identically. Present-and-empty rather than absent so the silence is visibly
  deliberate after a Bedrock redeploy. No price is hardcoded anywhere; the variable description carries a
  format illustration and says in terms not to copy numbers out of it.

### DoD #10 — breadth, not existence

The item is **green**: `tests/test_bedrock_live.py:247` passes against a real model. What it covers is
narrower than the sentence sounds, and the narrowness is the gap.

- [x] **A real model ignores an injected node label.** One case (`adv_014`), one channel, one model, one
  run. The test's own docstring states the limit correctly: `gate()` would refuse the forbidden triple
  whether or not the model honoured the delimiter, so a pass is defence in depth **confirmed**, not
  discovered.
- [ ] **`adv_015` has no live counterpart.** The hostile stub tool is exercised only under
  `tests/test_untrusted.py`. The second injection channel has never met a real model.
- [x] **Injection resistance as a rate against a real model. CLOSED 2026-08-16** by the same run:
  **0 induced over 5 scored cases**, 36 cases planting nothing. `InjectionResistance.holds` is `True`
  because `scored_cases > 0` — the guard that stops a suite which tested nothing from reporting
  resistance is satisfied on real model output for the first time.

  Read it for what it is. Five planted cases is a rate with a small denominator, and the strongest of
  the channels is still structural rather than behavioural: a fabricated edge cannot reach the gate
  through a tool call at all, because `ToolResult.proposals` is built from real artifact edges. What
  the live run adds is that a real model, given an injected instruction in the user query
  (`adv_016`), did not manufacture the forbidden triple through the one channel where it could have —
  the plan turn's `asserted_premise`. `adv_015`'s hostile stub tool still has no live counterpart.

### The deployed URL

- [ ] **The public URL runs the local provider.** It walks the graph, gates claims and cites real Wikidata
  statement URIs, but **the prose comes from a template and the token counts are synthetic.** This is the
  only claim in this document that is true without qualification, and it is the one with consequences
  outside the repo. A deployed demo running on a template must never be described as a live agent.
- [ ] **The Function URL is `authorization_type = "NONE"`** (`infra/terraform/main/lambda.tf:135`). Today
  that is free to abuse. After a Bedrock redeploy it puts a billable model behind a public unauthenticated
  URL, bounded only by reserved concurrency and the timeout — and per `.claude/rules/aws-and-cost.md`, a
  streamed response bills the full function duration even when the visitor closes the tab. Redeploying
  onto Bedrock and leaving this unaddressed are two decisions, not one.

### Documentation that now understates the build

- [x] **Six places state that the loop has never run end to end against a real model. All six were false
  as of 2026-08-12. Rewritten the same day.** Note the direction of the error: every one **understated**
  what works, so nothing public was overclaiming and none of it was urgent.

  `README.md:38` (the public one, and the only one a recruiter reads) · `docs/ROADMAP.md:296` ·
  `src/musical_mycelium/agent/llm.py:22` · `src/musical_mycelium/agent/__init__.py:45` ·
  `docs/phases/phase-1-walking-skeleton-IMPLEMENTATION.md:20` and `:394`

  What replaced them is narrower, not wider: **the loop is live-verified end to end, real-model behaviour
  is demonstrated but not measured, and the deployed URL still runs the template stub.** Verified by a
  whitespace-normalised search rather than a line-based grep — the sixth site was invisible to the
  original grep because the phrase wrapped across two lines, which is how the earlier count of five
  happened.

- [x] **`README.md:21` read 623 tests; the suite is 640** plus 7 deselected. **Fixed 2026-08-12**, and
  the deselected count is now stated rather than dropped.
- [x] **`phase-3-agent-loop-IMPLEMENTATION.md` §5.1 needed a pointer to this file** rather than a
  duplicate. **Done 2026-08-12.** Its release-step items 1 and 2 are struck through, and the superseded
  08-11 wording is kept with its reasoning rather than deleted.

### The precondition that gates phase 4

- [x] **The gold set is complete: 25 cases, 67 claims. Done 2026-08-14.** `eval/datasets/gold_v0_1.json`.
  16 origins, 5 path, 4 descendants; 10 genre and 10 artist; 3 refusals; all four verification tiers
  exercised. 8 of the 67 claims carry no independent citation and say so explicitly via `citation_status`,
  with the sources searched recorded per claim — see the standing limit on that below.

- [x] **The sealed held-out 10 is drawn and sealed. Done 2026-08-14.**
  `eval/datasets/heldout_v1.json.enc` plus its public manifest are committed; the key lives outside the
  repo and the plaintext was shredded. Manifest: 10 cases, pinned to artifact `0.5.0`, shapes
  `{descendants: 2, origins: 6, path: 2}`, `refusal_count: 2`. The six origins are 4 drawn from the
  origins stratum plus the 2 refusal cases, which are origins-shaped questions whose correct answer is a
  refusal — refusal is a stratum and an `expected_refusal` flag, not a shape. It was drawn rather than
  hand-authored because the set's job is detecting overfitting to the gold set, and a curated held-out set
  inherits the same blind spots the gold set already has. **The seed is the mechanism: it is the author's
  alone, was never committed, pasted into an agent session, or left in shell history, and without it the
  draw cannot be reproduced.** This was the last item gating phase 4.

- [ ] **The "authored while no model output exists" property is now weaker than the phrase suggests.**
  It was true by construction until 2026-08-12, when the loop first ran end to end against a real model.
  The exposure is narrow — that run's subject was `acid jazz`, gold case 002, authored ten days earlier —
  but the gold set is now clean **by procedure**, not by construction. The held-out set is the narrower
  case: it was drawn 2026-08-14 with every field read out of the pinned artifact and no authored
  judgement anywhere in it, so it has no contamination surface of this kind to begin with.
  Recorded in the dataset's own `provenance.honest_limits` rather than only here. Step 8, the full
  evaluated run, still has not happened.

---

## Part 2 — standing limits, not tasks

These do not get checkboxes. They are properties of the corpus and the design, and stating them is the
point of this document. Some will change if phase 6 changes the corpus; none of them is a defect.

**The recorded baseline measures the machinery, not the model.** Every run in
`baseline_v0_3_0_local.json` is scripted. It shows that the gate and the loop refuse unsupported claims.
It does **not** show that a real model resists. That sentence is the first field of the JSON itself, not a
footnote, because a number that leaves the file without it will eventually be quoted as evidence about a
model.

**Contested is unbuildable on this corpus.** Detecting genuine disagreement needs a second independent
source, and this corpus has exactly one per edge. What the output distinguishes is how strongly a single
source was checked, and where two independent checks reached opposite verdicts. `contested` and
`checks_disagree` are defined, documented, and test-locked as unreachable rather than quietly dropped.
Decision A1; not to be re-litigated.

**Every claim the adversarial set produces is `HAND` verified — all seven of them.** The set never touches
a `PROSE_AUTO` edge, which is the overwhelming majority of the corpus, so the baseline says nothing about
behaviour on machine-verified edges. That is a gap in the **dataset**, not the code, and it belongs to the
gold set. A test fails if the mix ever changes, so it cannot quietly stop being true.

**Grounded means provenance, not truth.** Every edge traces to a checkable source. Wikidata can still be
wrong and musical influence is genuinely contested. Nothing in this project's copy, docs or interview
material may slide from "traceable" to "correct."

**The corpus skews Western, anglophone and recent, by construction.** It is reported as a computed number
rather than a disclaimer. Concentration is not absence: the corpus spans 500 CE to the present across 29
places, and 43 of its genres name no US or UK origin at all.

**The skew compounds across three layers, and authoring the gold set on 2026-08-14 measured the other
two.** The non-Western slice is the least covered — 15 nodes with any parent, not the 19 an earlier count
claimed, which had included France, Germany, Finland and Sweden. It is also the **least verified**: every
non-Western node except `bossa nova` sits at `PROSE_AUTO`, the tier that structurally cannot tell an
assertion from a mention. And it is the **least citable**: Wikipedia frequently leaves the sentence these
edges rest on unsourced. Only the first layer was previously written down.

**8 of the gold set's 67 claims carry no independent citation, and say so.** Not silence — an explicit
`citation_status` naming the sources searched and what was found. The alternative was worse in both
directions: attaching an article's general reference list would pass the test while hiding the weakness,
and dropping the cases would buy a 100% citation rate by excluding the global south and then report that
rate as a property of the system. **Read the flag as "this edge is as traceable as any other and has no
second opinion", not as "unsourced"** — provenance is intact; what is missing is the second, *
disconfirming* layer. `tests/test_gold_set.py` locks the count, because an escape hatch that costs
nothing to widen becomes the standard. **Searching other languages before flagging is required, not
optional: it rescued two of four candidate claims, and `kuduro`'s Spanish citation — a peer-reviewed
Dancecult article with a DOI — is the strongest in the entire set.**

**The `ASSERTS_AUTO` filter has one characterised failure mode.** It fires when subject and object
co-occur in a sentence about a **cover, a collaboration, or a shared bill**. Four confirmed instances,
all found while authoring gold cases on 2026-08-14: `Deep Purple → Led Zeppelin` (shared billing),
`The Rolling Stones → Robert Johnson` (a cover in a track listing), `Rina Sawayama → Lady Gaga` (a cover
and a remix credit), `The Velvet Underground → David Bowie` (both). This is consistent with the filter's
measured 97% precision — roughly 23 such edges are expected across 760 — so it is the filter working as
documented, not breaking. It is recorded because a gold case must claim its subject's neighbours
*exactly*, so each one silently disqualifies that node as a gold subject. **Related method note: judge an
edge on all of its matched sentences, not the first two.** `The Beatles → Bob Dylan` looks like it rests
on Dylan introducing them to cannabis until sentence seven turns out to be a real assertion.

**Genres are thin.** The best-connected genre nodes top out at four outgoing edges; artists reach 25.
`techno` (`Q170611`) has **zero** edges, so "Where did Detroit techno come from?" correctly refuses. Pick
live-test and demo queries with that in mind — a refusal there is the product working, but it is a poor
first impression.

**Three quota axes bind, and the third is new.** 10 RPM is the binding constraint for a single query
(a plan turn, one turn per hop, then synthesis), 5M TPM is not, and **27,000,000 tokens per day on Haiku
4.5** locks the model out for the rest of the calendar day if blown. TPM recovers in sixty seconds; the
daily cap does not. Phase 4's eval throttling needs a cumulative-token budget, not only per-request
backoff.

**No judge exists, deliberately** — an LLM-judge score with no measured human agreement is decoration,
and validating one is step 7. **Thresholds now DO exist**: `eval/thresholds.json`, written 2026-08-18
from the measured noise floor and never before it, per `.claude/rules/evals.md`. The rule they were
held back for still governs anything added to them — a bound invented ahead of a baseline is worthless,
so a sixth gate is a decision that needs its own measurement, not a tweak.

---

## What closing these is worth

The resume line *"deployed on AWS Lambda and Bedrock with a deterministic groundedness gate at 100%"* is
**not claimable at `v0.3.0-local`**, because what is deployed runs a template. It becomes claimable at the
redeploy, and not before.

The interview-facing statement, rounded **down** rather than up: the loop works end to end against a real
model, what is deployed is still a stub, and the eval numbers measure the machinery rather than the model.
