# Phase 4 — Eval Suite (v0.4)

> **Scope doc.** Written 2026-07-30, before building. Re-read it at the start of phase 4 and amend it where
> phases 1–3 taught something different — it was written before any of this existed.

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
  resolution, traversal recall@k and precision, refusal accuracy, contested flagging, coverage honesty,
  injection resistance, cost and latency. No approval, $0.
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

## Known risks

- **Spend.** This is the only phase where a mistake costs meaningful money. Every judged path goes behind
  confirmation; there is a documented history of a real slip (`memory: spending incident 2026-06-23`).
- **The gold set is the hard part and it gates everything** (`planning/04` §5.1). It is hand-built before the
  agent exists — a gold set that is "what I believe about music" is worthless, and it must include boring
  middles where a step is easy to skip.
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
