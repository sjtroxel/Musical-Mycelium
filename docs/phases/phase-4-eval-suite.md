# Phase 4 — Eval Suite (v0.4)

> **Scope doc.** Written 2026-07-30, before building. Re-read it at the start of phase 4 and amend it where
> phases 1–3 taught something different — it was written before any of this existed.
>
> **Amended 2026-08-12 at the phase 3 release step.** Phase 3 built more of this phase than the original
> text assumes, and it hands over four open items with names. See §0.
>
> **PHASE COMPLETE 2026-08-24, tagged `v0.4.0`.** The IMPLEMENTATION doc was written 2026-08-15, approved,
> and all 9 steps built. Two definition-of-done items below did not land exactly as written — see the note
> under "Definition of done". The rest of this doc is left as it was.

## 0. What phase 3 handed over

Read this before the sections below, which were written when none of it existed. The canonical list of
open items is [`docs/KNOWN-GAPS.md`](../KNOWN-GAPS.md); this section says what each one means *for phase
4* rather than restating it.

### Already built, so do not re-plan it

- **Six deterministic scorers exist** in `eval/metrics.py`: `citation_resolution`, `refusal_accuracy`,
  `traversal_recall` / `traversal_precision`, `injection_resistance`, `verification_mix`, `plan_adherence`,
  alongside the earlier `Groundedness`. All unit-tested, including two vacuous-truth guards.
- **Slicing exists** in `eval/slices.py` — era, region, density, query type.
- **A harness exists** in `eval/harness.py`, and a recorded scripted baseline in
  `eval/datasets/baseline_v0_3_0_local.json`, drift-tested.
- **Cost telemetry exists** in `api/telemetry.py` — EMF on stdout, no boto3 client, dollars only when
  `MYCELIUM_TOKEN_PRICES` is set.

So DoD 5 and 6 below are substantially met already, and DoD 8 is built but unproven end to end.

### Inherited open, with what each actually needs

1. **Refusal accuracy on real model output** (phase 3 DoD #11a). `harness.py` hardcodes its dataset and
   takes no provider argument. Needs a provider seam through the harness, then one billable run.
2. **Traversal recall on real model output** (phase 3 DoD #11b). **Never scored on a real run.** It had
   never scored *any* run until `expected_path` was added on 2026-08-12; the scorers' only callers were
   their own unit tests. **No longer gated on authoring** — the gold set was completed on 2026-08-14 with
   five multi-hop path cases, so the metric has real chains to walk. Same billable run as item 1.
3. **Injection resistance as a rate against a real model** (phase 3 DoD #10, breadth). One case scores
   live; `adv_015` has no live counterpart at all. Same billable run as item 1.
4. **Token cost verified into CloudWatch** (phase 3 DoD #12). The EMF format is proven; no record has ever
   reached CloudWatch, because the deployed Lambda runs `llm_provider=local`. Needs the Bedrock redeploy,
   which is a spend decision paired with the public unauthenticated Function URL — not a free step.

### Two corrections to the text below

- **"Contested flagging" cannot be a metric on this corpus.** It is listed in the Tier 1 catalog because
  `planning/07` assumed multiple sources per edge. This corpus has **exactly one**, so genuine
  disagreement is undetectable and `contested` is test-locked as unreachable (decision A1, not to be
  re-litigated). What is measurable in its place is **`verification_mix`** — how strongly each single
  source was checked — and `checks_disagree`, where two independent checks on one edge reached opposite
  verdicts. Do not carry "contested flagging" into the IMPLEMENTATION doc as a deliverable.
- **The gold set is DONE — 25 cases, 67 claims, completed 2026-08-14.** Superseding the 2026-08-12 note
  that it held 5 of a planned 20–30. 16 origins, 5 path, 4 descendants; 10 genre and 10 artist; 3
  refusals; all four verification tiers exercised. **What remains of this precondition is the sealed
  held-out 10, which does not exist.** It is *drawn*, not hand-authored — `make heldout-draw` takes a seed
  only the author knows — because its job is detecting overfitting to the gold set, and a curated held-out
  set inherits the same blind spots the gold set has. Three things the authoring pass established that
  this doc should carry forward: **8 of the 67 claims carry no independent citation and say so via
  `citation_status`** with the sources searched recorded; **the `ASSERTS_AUTO` filter has a characterised
  failure mode** (it fires on covers, collaborations and shared bills, four confirmed instances); and the
  "authored while no model output exists" property is now **clean by procedure rather than by
  construction**, since the loop first ran live on 2026-08-12.

### Three quota facts that are design inputs, not trivia

**10 RPM is the binding constraint**, not the 5M TPM — one query is a plan turn, one turn per hop, then
synthesis, so a fan-out eval run exhausts requests first. `planning/07` §315's cap of 2–4 concurrent with
exponential backoff is now a measured requirement. **A third axis surfaced on 2026-08-12: 27,000,000
tokens per day on Haiku 4.5.** TPM recovers in sixty seconds; a blown daily cap locks the model out for
the rest of the calendar day. The suite therefore needs a **cumulative-token budget**, not only
per-request backoff — a five-times-repeated noise-floor run over 30 gold cases is exactly the shape that
hits it.

### One dataset gap that skews everything measured so far

**Every claim the adversarial set produces is `HAND` verified — all seven of them.** The set never touches
a `PROSE_AUTO` edge, which is the overwhelming majority of the corpus, so nothing measured to date says
anything about behaviour on machine-verified edges. That is a gap in the **dataset**, and closing it is a
gold-set authoring requirement: the gold set must include `PROSE_AUTO` and `EXPOSURE_AUTO` edges, not only
hand-read ones.

## What this phase is for

To turn "grounded" from a word in the README into a number with a confidence interval, a measured judge, and
a known noise floor. Every phase before this one has shipped a metric or two alongside the behavior it
introduced. This phase builds the **suite**: the thing that runs, reports, blocks, and can be shown to
someone who evaluates models for a living without embarrassment.

This is the stated differentiator (`planning/02` §2, `.claude/rules/evals.md`) and the second half of the
resume claim. It is also the only line item that spends real money, which is why it is gated rather than
ambient.

The honest framing to hold onto: the eval suite is not a test suite. Tests assert that code does what it was
written to do. These measure whether a system that is allowed to be wrong is wrong less often than a
baseline, and by how much, and where.

## Delivers

- **The full metric catalog** from `planning/07` §4 — the eleven deterministic metrics plus the two judged
  ones, each with the tier it belongs to.
- **Tier 1: deterministic, free, every commit.** Edge groundedness, hallucinated-edge rate, citation
  resolution, traversal recall@k and precision, refusal accuracy, ~~contested flagging~~ verification mix
  (see §0 — contested is undetectable on a one-source-per-edge corpus), coverage honesty, injection
  resistance, cost and latency. No approval, $0.
- **Tier 2: judged, sampled, gated.** Citation support and narrative quality only. 20–30 samples, release
  candidates only, behind an explicit spend confirmation ported from Patchwork's `confirm_spend`.
- **A validated judge.** 30 hand-labeled items, blind, agreement measured and **reported permanently next to
  every judged number**. A non-Anthropic model on Bedrock, so the judge is not the generator's family.
- **The measured noise floor.** The identical suite run five times, the spread recorded, and a standing rule
  that a movement inside the spread is not a result.
- **Thresholds set from baseline, not invented.** Blocking on correctness properties, tracking quality
  preferences (`planning/07` §5).
- **Metric unit tests**, including the **vacuous-truth guard: an empty output must not score 100%
  groundedness.**
- **The held-out set's first and only look** — 10 cases never examined during development.
- **A report** that a human reads: per-metric, per-slice, with the agreement figure and the noise floor on
  the page.

## Explicitly not in this phase

The SPA, visualization, the guided tour, new agent capability, new corpus. If a metric reveals an agent bug,
the fix is in scope; a new agent *feature* is not. Historical trend view and the public writeup are phase 7.

## Key decisions this phase makes

- **The thresholds themselves.** Measured first, then fixed. Blocking: edge groundedness 100%, citation
  resolution 100%, injection resistance zero failures, traversal recall within 5pp of baseline, refusal
  accuracy within 5pp of baseline both directions. Everything else tracked. **Do not set any number before
  the baseline run exists.**
- **Which judge model.** Nova, Llama, Mistral, or DeepSeek on Bedrock. Pinned version, temperature 0, rubric
  in version control next to the code.
- **What happens when judge-human agreement is poor.** The rubric is the problem, not the human: rewrite it
  with concrete anchors per score level and re-measure. Decide the re-measure budget up front so this does
  not become an open-ended spend.
- **How the pin is enforced.** Evals run against a pinned artifact version, and a run against an unpinned or
  mismatched artifact should fail loudly rather than silently produce an incomparable number.
- **What the suite costs per run**, measured, so the $5–25 estimate from Patchwork's actual $4.57 and $10.55
  runs is replaced by this project's real figure.

## Definition of done

1. Tier 1 runs on every commit, costs $0, and blocks the build on the five correctness properties.
2. Tier 2 runs only behind an explicit confirmation that names the estimated dollar figure.
3. Judge-human agreement is measured, recorded, and printed next to every judged metric.
4. The noise floor is measured over five identical runs and written into the report.
5. Every metric has a unit test over synthetic input whose answer is known by construction, and the
   vacuous-truth guard is one of them.
6. Every result is sliced by era, region, density, and query type. No headline number is reported without
   its slices available.
7. The held-out set is run **once**, after everything else is frozen, and its numbers are reported
   separately from the development set's.
8. Real per-run cost is recorded to CloudWatch, not estimated.

> **As built, 2026-08-24. Six of eight landed as written; two did not, and both are recorded rather than
> rounded.**
>
> **#1 — "blocks the build on the five correctness properties" is not what shipped.** Five gates exist,
> and the free every-commit run can only block on **three**. Traversal recall is script-determined on a
> scripted run and injection resistance scores zero cases there — the planted injections live in the
> adversarial set and the free run is gold-only. Both return `N/A`, which is never counted as a pass;
> `render` reports gated, failed and inapplicable as three separate counts so an all-inapplicable run
> cannot look green. **The other two gates need money.** This is a limit of a free deterministic tier,
> not a defect, but the DoD as written overstates it. `eval/thresholds.py` is the authority.
>
> **#8 — closed as PARTIAL, deliberately.** Per-run cost is **measured** from real usage and recorded in
> committed result files; it does **not** reach CloudWatch, because that needs a redeploy, and the
> redeploy was deferred to phase 5 (`KNOWN-GAPS.md`). Phase 5 needs a live backend for the SPA anyway, so
> the auth and throttling decision gets made once instead of twice, and no billable public URL is exposed
> in the meantime. **The resume line "deployed on AWS Lambda and Bedrock" stays unclaimable until that
> redeploy** — nothing about this partial close softens that.
>
> **#7 landed as written and is now governed by a rule.** The held-out set was run once, at the freeze,
> and reported separately. `.claude/rules/heldout-set.md` records the run and forbids a second one at any
> freeze where something was tuned in response to what the first said.

## Known risks

- **Spend.** This is the only phase where a mistake costs meaningful money. Every judged path goes behind
  confirmation; there is a documented history of a real slip (`memory: spending incident 2026-06-23`).
- **The gold set was the hard part and it is done** (`planning/04` §5.1). Hand-built before the agent's
  output existed — a gold set that is "what I believe about music" is worthless, and it must include
  boring middles where a step is easy to skip. **Completed 2026-08-14 at 25 cases / 67 claims** (§0),
  superseding the 2026-08-12 count of 5. Both things this bullet predicted turned out to matter and both
  were done: it includes `PROSE_AUTO` and `EXPOSURE_AUTO` edges rather than only hand-read ones (21 and 2
  claims respectively, against 15 `HAND` and 29 `ASSERTS_AUTO`), and **traversal recall now has five
  multi-hop path cases to walk**, which it never had before. What still gates the phase is the held-out
  10.
- **Redeploying onto Bedrock is a spend decision, not a deploy step.** The Function URL is
  `authorization_type = "NONE"`, and per `.claude/rules/aws-and-cost.md` a streamed response bills the
  full function duration even when the visitor closes the tab. Today that is free to abuse because the
  deployed provider is `local`. The redeploy that closes phase 3 DoD #12 also puts a billable model behind
  a public unauthenticated URL, bounded only by reserved concurrency and the timeout. The two are one
  decision.
- **Blocking on too much.** A suite that blocks on everything gets disabled within two weeks. A suite that
  blocks on nothing gets ignored. The five-and-only-five blocking list is the guard.
- **An unvalidated judge is decoration.** A score with no measured agreement should not appear in the
  report, on the site, or in an interview answer.
- **Celebrating noise.** Without the noise floor, every rerun looks like progress or regression. Measure it
  before the first improvement is attempted, or there is nothing to compare against.
- **Metrics that were never attacked.** The difflib coverage bug in Patchwork is the precedent: a metric
  nobody tried to break is not a metric.

## Left for the IMPLEMENTATION doc

The judge model pick and its rubric; the report format and where it is published; the CI wiring for tier 1
and the manual trigger for tier 2; the confirmation prompt's exact shape; the slice keys; the baseline run's
schedule; how historical results are stored so phase 7's trend view has something to read.

**Added 2026-08-12:** how the provider seam reaches `eval/harness.py` so a run can be driven against
Bedrock; the cumulative-token budget's shape and where it lives; whether phase 3's four inherited items
(§0) open the phase or are folded into its first real run; and whether the Bedrock redeploy happens in
this phase at all or waits for the SPA in phase 5.

**Nova Pro is confirmed available on this account** (2M TPM / 25 RPM, no Marketplace step required), which
makes the non-Anthropic judge `.claude/rules/evals.md` requires a settled question rather than an open
one. The pick still has to be made and recorded; the availability risk is gone.
