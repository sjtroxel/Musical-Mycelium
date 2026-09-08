# Phase 7.5 — Portfolio and Writeup (v1.0)

> **Scope doc.** Written 2026-09-08, at the moment the phase was conceived, which is the rule: *"A phase
> conceived later gets its own scope doc when it is conceived."* Written before anything in it is built and
> before its IMPLEMENTATION doc exists — that doc is written immediately before phase 7.5 is built, not now,
> so it can absorb what phase 7 actually teaches.

## 0. Why this phase exists, and why it is not phase 7

**It was phase 7, until 2026-09-08.** `phase-7-cinematic-surface.md` §0 records the split and is the
authority on it. The short version: phase 7's own first named risk is *"polish is unbounded,"* and on
2026-09-08 the design half stopped being a styling pass and became a build — full-page backdrop, motion
system, renderer, asset pipeline, byte budget. Four deliverables under an unbounded-scope risk is how the
risk collects, so the phase was carved in two along the line that was already there: **things that move**
went to 7, **things that are read** came here.

**This phase inherits DoD items 3, 4, 5, 6 and 7 from the phase 7 scope doc, unchanged.** They are restated
in §5 rather than referenced, because a definition of done that lives in another file gets skipped.

**Product version v1.0, and this is the release.** Phase 7 is v0.8. v0.7 is deliberately never used — the
artifact pin is v0.7.1 and `ROADMAP.md` §2 already names reading one version line as the other as the
confusion it exists to prevent. v1.0 is the thing a recruiter is pointed at, which is the writeup, the
report and the README, not the day the camera first moves.

## 1. What this phase is for

To make the project **legible to someone who will never run it**, and to make its honesty checkable rather
than claimed.

Everything by the end of phase 7 is correct, measured, and now memorable. None of that helps if the only
way to learn what the eval suite found is to clone the repo and read `thresholds.json`. This phase publishes
what the project actually knows about itself — including the parts that do not flatter it — and produces the
one artifact that has to be in his own words.

## 2. Delivers

- **The published eval report.** Per-metric and per-slice, with judge-human agreement printed next to every
  judged metric and the measured noise floor on the page. Not a badge. A page a skeptical reader can argue
  with.
- **The trend view.** Reads the stored per-run result files rather than a hand-maintained table. The storage
  format was chosen for this in phase 4 — `eval/results/` is per-run JSON specifically so this phase can
  plot it, recorded at `phase-4-eval-suite-IMPLEMENTATION.md` §972 and locked by `tests/test_live.py`.
- **The writeup.** Assembled from the per-phase plain-English explanations written as each phase was built,
  not reconstructed at the end. **He writes it.** See §6.
- **The portfolio surface:** README, the recruiter path, the demo script, and the media.
- **A stated coverage position.** What the graph covers, what it does not, and why — visible on the page,
  not disclaimed in a footnote.
- **The infrastructure round-trip, verified.** `terraform destroy` removes everything and `terraform apply`
  rebuilds it, run for real rather than asserted.
- **The bill.** Fixed monthly cost confirmed against an actual AWS invoice, replacing the estimate.

## 3. Explicitly not in this phase

New corpus. New metrics. New agent capability. New tools. Any architectural change. Anything that moves the
artifact pin. Re-running the held-out set. Re-measuring the live noise floor.

**Specifically not: tuning anything because the report made a number look bad.** A metric published and then
improved is fine; a metric improved *so that it publishes well* is the failure this whole eval suite exists
to prevent. If the report makes something look bad and the honest fix is a code change, that is a finding
and it gets its own phase.

## 4. Key decisions this phase makes

- **Where the report lives.** A route inside the SPA, or a separate static page. The SPA already loads a
  2.6 MB graph; a report route inherits that cost for a reader who came for numbers.
- **What the trend view plots, and over what history.** Not every stored run is comparable — a run against a
  different case count is explicitly not comparable, which `thresholds.py:592` enforces by refusing to gate
  it. A trend line that silently joins those points would state something false in a chart, which is harder
  to catch than a false sentence.
- **How the coverage position is worded.** Inherited from the phase 7 scope doc. This is where "grounded" is
  most likely to slide into "correct" under the pressure of writing marketing copy about your own work. It
  must not.
- **What the recruiter sees in thirty seconds**, and what is one click deeper.
- **Whether to register a real domain, and whether that is worth breaking the $0 claim for.** A domain is
  roughly $12–15/year and a Route 53 hosted zone is $0.50/month. That is small and it is **not zero**, and
  `.claude/rules/aws-and-cost.md` says fixed infrastructure is approximately $0/month. If a domain is
  registered, the claim gets amended rather than rounded.
- **Whether the held-out result is published**, and if so, with its run count beside it. Publishing the
  number is allowed and honest. Reading the set is not, and nothing in this phase needs to.

## 5. Definition of done

Items 1 through 5 are phase 7's DoD items 3 through 7, restated verbatim in intent.

1. The published eval report includes slices, judge-human agreement, and the noise floor.
2. The trend view reads stored historical runs rather than a hand-maintained table, and does not join
   points that the gate logic itself would refuse to compare.
3. The writeup exists and he can walk through it cold. This is the articulation rep, and it is the point of
   having written it phase by phase.
4. `terraform destroy` still removes everything, and `terraform apply` still rebuilds it — run, not asserted.
5. Fixed monthly infrastructure cost is still approximately $0, verified against a real bill rather than the
   estimate. If a domain was registered, the number and the sentence both change.
6. **Nothing in the repo overstates what "grounded" means.** Shared with phase 7, and this phase owns the
   copy audit half.
7. **The report shows what did not work, not only what did.** Named, at minimum: `gold_v0_1_020` and its
   diagnosed cause, the `Joy Orbison` / `Roy Orbison` failure that scores 100% on both groundedness and
   citation resolution while being about a different person, the two `N/A` gates that are not passes, and
   the fact that 2,202 of 2,284 influence edges are single-source. A report that shows only green numbers is
   the exact dishonesty this suite was built to make impossible.

## 6. The writeup is his, and this is a hard constraint

Claude's generated prose carries an invisible SynthID watermark. It is in the word choices rather than the
clipboard, so retyping it by hand does not remove it — only rewriting in his own words does. Code is largely
exempt; prose is not.

**Therefore: every word of the writeup, the README's narrative sections, and any recruiter-facing copy is
written by him.** The correct support is to interview him and structure the bullets he then rewrites, not to
hand him finished paragraphs. This is not a preference; it is the standing rule and it predates this repo.

It also happens to be the right thing on the merits. DoD item 3 is *"he can walk through it cold,"* and
prose he did not write is prose he cannot walk through cold.

## 7. Known risks

- **The honest-claim slide.** Inherited from phase 7 and it lands here, because this is the phase that
  actually writes the marketing copy. "Every edge traces to a checkable source" is one careless edit away
  from "every edge is correct." Wikidata can be wrong, musical influence is genuinely contested, and
  contested pairs are disclosed rather than resolved — 2 of them, at artifact v0.7.1.
- **Cold articulation, one last time.** This is the phase whose output is most likely to be read by someone
  who will then ask him about it in a live round.
- **A chart that lies more easily than a sentence.** The trend view is the first place in this project where
  a wrong number is *drawn* rather than written. Incomparable runs joined by a line, a truncated y-axis
  flattering a movement inside the noise floor, an aggregate hiding a per-case constant — the last of which
  this project has now been bitten by twice.
- **Publishing invites the reader to check.** That is the point, and it means the numbers on the page have
  to survive someone opening the repo. Round down on every one of them.
- **This phase competes with the job search and has the weakest claim on the time.** Items 2 and 3 of the
  priority stack, and 1 beats both (`ROADMAP.md` §1). Unlike phase 7, this phase produces the artifacts the
  job search actually uses, so the competition is less sharp than it looks.

## 8. Left for the IMPLEMENTATION doc

The report's published location and route; the trend view's aggregation and which runs it admits; the
writeup's structure and the interview order that produces it; the README's shape; the media list and the
demo script; the domain decision and its cost amendment; whether the held-out number is published.

Written immediately before phase 7.5 is built, not now — so it can absorb what phase 7 actually taught.
