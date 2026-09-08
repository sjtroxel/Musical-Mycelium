# Phase 6.5 — Debt and Disagreement (v0.6.5)

> **Scope doc.** Written 2026-09-06, at the phase 6 step 9 close, before step 10 and before any of this is
> built. It is a **map, not a contract** — the IMPLEMENTATION doc is written immediately before the phase
> is built and is allowed to disagree with this one, in writing.
>
> **This phase was conceived on the day it is written**, which is why it has a scope doc at all: `CLAUDE.md`
> says a phase conceived later gets its own scope doc when it is conceived, and phases can be inserted
> mid-arc. Patchwork gained 4.5 and 4.6 exactly this way.

## 0. Why this phase exists, and why it is not phase 7

Phase 6 recorded more debt than it could close, for one structural reason: **its own DoD #6 forbids editing
the agent package.** That rule was correct — it is what kept a corpus phase from silently becoming an agent
phase — and it means the findings phase 6 produced about the agent could only be written down, not fixed.

Phase 7's scope doc independently refuses this work. It excludes *"a new agent capability that is not the
tour"* and says *"if something here requires editing a seam, that is a finding and it belongs in its own
phase."* Taking the debt into phase 7 would violate the phase 7 scope doc on the first day.

So the debt has nowhere to live unless it gets a phase. This is that phase.

**The honest framing, because it will be asked in an interview:** this is not a cleanup sprint. Two of its
four agent items are *correctness and honesty* defects — a system that false-refuses questions it can
answer, and one that reports "I found nothing" in words that mean "the corpus contains nothing". A third is
the missing half of the capability phase 6 exists to deliver. Calling that polish would be the same
overstatement in the other direction.

## 1. What this phase is for

To close the gap between **what the corpus can now support** and **what the agent can actually say**, and
to put the resulting behavior under measurement.

Phase 6 grew the corpus from one source to two and made `contested` reachable in the data. The agent never
learned about it. The eval suite never learned about it. A user asking a question about a genuinely
disputed pair gets an answer that reads exactly like an undisputed one. **That is the shape of this whole
phase: phase 6 delivered the data half of its own thesis and the behavioral half is still owed.**

## 2. The question this phase answers

**Can the system tell a user that its sources disagree, refuse only when refusing is right, and prove both
with numbers?**

Today the answers are no, no, and no:

- **Disagreement:** `graph/corroboration.py:89` derives `contested_pairs`, `api/app.py:183` serves them, and
  `web/src/components/CoveragePanel.tsx:242` displays them **as a corpus-level statistic**. Nothing in
  `agent/` reads `corroboration`. An answer cannot say the sources disagree.
  **DELIVERED 2026-09-07, phase 6.5 step 4** — a `contested` event, decision 5.1.
- **Refusal:** `gold_v0_1_020` has false-refused a fully answerable question in **7 of 7 recorded runs**
  since 2026-08-18, and `thresholds.json` excludes it from the traversal gate as *"a tracked reproducible
  product bug"*. It survived a 3x corpus, so thinness was never the cause.

  > **AMENDED 2026-09-07, phase 6.5 step 3 — this bullet is wrong in three ways and the corrections are
  > the useful part.** It is **not 7 of 7**: across all 13 recorded runs the case has answered completely
  > twice, and `eval/noise.py`'s own docstring has recorded one of those since 2026-08-16. It is **not
  > reproducible**: the five identical failures behind that wording were one afternoon on one revision.
  > It is **not a product bug**: read from a recorded trace, the model calls
  > `resolve_node(name="fentanyl")` — the opioid — for a query that says *femtanyl*, then has one
  > endpoint, cannot call `trace_lineage`, and stops. The corpus, `store.path()` and every tool answer
  > this case correctly and deterministically. The last sentence above survives intact and was the one
  > clue that pointed the right way: thinness was never the cause.
  > Full diagnosis in `phase-6.5-debt-and-disagreement-IMPLEMENTATION.md` §3.0 and §3.3.
- **Proof:** the live suite reports `NOT GATED` at v0.7.1, and no eval case anywhere exercises `contested`.

> **ALL THREE ANSWERED, 2026-09-07 — the phase closed on its own question.** Disagreement: a `contested`
> event names both directions and both sources (step 4). Refusal: `gold_v0_1_020` is diagnosed from a
> recorded trace — the model types *fentanyl* for *femtanyl* — and is excluded from the gates with the
> cause written down (step 3). Proof: the live suite gates all six properties against bounds measured
> over five identical runs (step 7), and two gold cases plus a gated `contested_disclosure` metric
> exercise disagreement end to end (steps 5 and 6).

## 3. Delivers

Ordered by dependency. Tier 2 cannot start before tier 1; tier 3 cannot be measured before tier 2 settles.

### Tier 1 — the agent package, which only this phase may touch

1. **`contested` reachable in an answer.** The keystone. When a traversal crosses a contested pair, the
   response says the sources disagree, names **both** directions and **both** sources, and picks no winner.
   `contested` remains a property of a **pair**, derived in `graph/`, **never** a claim, **never** proposed
   by the model, and `checks_disagree` stays declared in `agent/claims.py:UNREACHABLE`. The likely shape is
   an addition to the response envelope rather than to the claim set, and choosing that shape is a decision
   this phase makes (§5).
2. **The `gold_v0_1_020` false refusal — diagnosed, then fixed or recorded as unfixable with the reason.**
   Diagnosis first and separately: this phase does not get to guess. It has failed identically 7 of 7 runs,
   which makes it the most reproducible bug in the repo and therefore the cheapest to study.
3. **The refusal wording at `agent/loop.py:770`.** *"it resolved but carries no sourced influences"* is
   emitted whenever the gate approves zero claims, so **"this run gathered nothing" reaches the user as
   "the graph holds nothing"** — the coverage-honesty rule inverted, asserting an absence the corpus does
   not have. The two states must be distinguishable in the text a user reads.
4. **`ResolveSource` verifying a DBpedia URI.** It cannot today; it needs a reverse lookup `GraphStore`
   does not expose. This touches `graph/` as well as `agent/`, and it is the reason citation resolution on
   the DBpedia half of the corpus is presently unverifiable at the tool level.

### Tier 2 — the frozen datasets, once tier 1 makes them writable

5. **The two contested gold cases** — electropop/electroclash, western music/New Mexico music. Deferred
   twice on purpose, correctly, because before item 1 they would assert an ordinary origins answer and
   test nothing.
6. **A case exercising the `ambiguous` branch**, reachable since `big band` / `big band music`.
7. **Gold cases whose subjects are `dbpedia_only`.** The step 7 slicing audit measured the gold set
   over-sampling the Wikidata half **~12x**: `dbpedia_only` is 48% of corpus genres and 13% of gold cases,
   and the live run's slice came back **n=4**, below the slicer's own n<5 reporting floor. **This is the
   largest single piece of work in the phase and it is real authoring** — each case needs an independent,
   non-Wikidata citation. It is inside the fence deliberately (§4), not left ambiguous a third time.

### Tier 3 — measurement, once the datasets stop moving

8. **A v0.7.x live threshold set, measured not invented.** Five identical live runs, the noise floor
   re-measured from them, bounds written from the floor with their observations recorded beside them, per
   the pattern `eval/thresholds.json` already uses. **The existing set is not edited to fit.**
9. **The `xfail` marker removed** from `tests/test_thresholds.py::test_a_full_live_run_can_be_gated_at_all`,
   which will announce itself by turning the build red the moment the counts agree.
10. **The `_ungateable` message corrected** (`eval/thresholds.py:492`). It says *"A subset is not a smaller
    version of the same measurement"* and fires equally for a run of a **larger** set — 45 is not a subset
    of 41. The guard is right; the sentence describes a case that did not happen.
11. **Eval coverage for `contested`**, which is what items 1 and 5 exist to make possible. Whether it
    becomes a gated metric is a decision (§5), and `.claude/rules/evals.md` already warns about the
    denominator: 2,202 of 2,284 influence edges are single-source, so a contested rate over all edges
    measures DBpedia's coverage far more than it measures disagreement.

### Tier 4 — hygiene, independent of everything above

12. **`MYCELIUM_TOKEN_PRICES` set**, so runs record dollars instead of printing *"cost not shown"*.
    `.claude/rules/aws-and-cost.md` asks for real token cost tracked so measured numbers replace estimates,
    and on 2026-09-06 two billable runs recorded token counts and no dollar figure.

## 4. Explicitly not in this phase

The fence, which does more work than the list above.

- **No new corpus and no new source.** The artifact stays pinned at **v0.7.1**. If a fix appears to need
  more data, that is a finding for a later phase, not a re-ingestion. This phase is about behavior over the
  corpus that exists.
- **No re-authoring of the existing gold cases.** Item 7 **adds** cases. The 67 hand-authored claims stay
  as they are, and the split contract decided on 2026-09-04 stands.
- **The held-out set is not run, not opened, not re-sealed, and not drawn again.** Whether it is ever run
  at v0.7.x is a decision at a freeze (§5), it is his alone, and no part of this phase depends on it.
- **No frontend work beyond what item 1 forces.** If an answer can now say the sources disagree, the SPA
  must be able to show that, and nothing more. The layout, palette and motion decided in phase 5 stand.
- **No guided tour, no camera, no writeup, no portfolio surface.** That is phase 7 and this phase must not
  start eating it.
- **No threshold tuning ahead of a measurement.** Item 8 measures first and writes bounds second. Any bound
  written before its five runs exist is invented, which `.claude/rules/evals.md` forbids by name.
- **No new AWS resource, no always-on anything.** Unchanged from every previous phase.
- **P279 is still not ingested.** Unchanged, and the genre-domain boundary predicate is still owed if a
  later phase wants it.

## 5. Key decisions this phase makes

Each of these is a real fork, and none should be settled by whoever happens to be typing.

1. **The shape of `contested` in a response.** Envelope field, a distinct event in the stream, or a
   property attached to the affected claims? The last option is the tempting one and the dangerous one:
   `contested` is a property of a **pair**, and stamping it on a claim is how `verification` and
   `corroboration` get collapsed, which this repo has already had to correct in three files once.
2. **Whether a contested metric joins the tier 1 catalog, and at what threshold** — or whether it stays
   tracked. Note the denominator problem before proposing a rate.
3. ~~**Whether `gold_v0_1_020` is fixable at all.**~~ **CLOSED 2026-09-07.** The cause is model
   behavior, and not on the axis this bullet guessed: the model mistypes the subject's name before any
   traversal happens. **The outcome this bullet named is exactly the outcome taken** — a recorded
   finding, a case that stays excluded, and no prompt tweaked. The near-miss resolver that would have
   "fixed" it was measured and rejected: 8 label pairs sit one edit apart, including
   `Joy Orbison`/`Roy Orbison`, so suggesting near labels trades an honest refusal for an undetectable
   grounded wrong answer. IMPLEMENTATION §3.3 to §3.5.
4. **How many `dbpedia_only` gold cases.** Five were proposed on 2026-09-04. Fewer is defensible; zero is
   not, since that leaves 48% of the corpus measured by four cases.
5. **The held-out set at the phase 6.5 freeze.** Run count is 1, and re-running it after a corpus change
   measures something the first run did not. The default remains **do not run**. His call, at the freeze,
   deliberately.
6. **Whether `-bedrock.json` runs stay gitignored.** `.gitignore:79` excludes them as reproducible, yet
   `eval/noise_floor.json` names five source runs that consequently exist on one laptop — the same
   objection that comment raises against ignoring judge runs. A decision, not a tidy-up, and item 8
   creates five more of them.

## 6. Definition of done

1. An answer that crosses a contested pair says so, names both directions and both sources, and picks no
   winner — and `contested` is still never a claim and never proposed by the model.
2. `gold_v0_1_020` either passes, or has a written diagnosis naming the cause and a recorded decision that
   it stays excluded.
3. A refusal caused by an empty traversal is distinguishable, in the text a user reads, from a refusal
   caused by a corpus with nothing in it.
4. `ResolveSource` resolves a DBpedia URI, or the reason it cannot is recorded with the seam that would
   have to change.
5. The frozen datasets exercise `contested`, the `ambiguous` branch, and the `dbpedia_only` slice at n>=5
   so the slicer reports a rate rather than a count.
6. A live run at the pinned artifact is **gated** — a threshold set matches it, and the set was measured
   over five runs, not written.
7. The `xfail` in `test_a_full_live_run_can_be_gated_at_all` is gone because the invariant holds, not
   because the test was deleted.
8. Every billable run records a dollar figure.
9. **No copy anywhere claims the system surfaces disagreement in an answer if it does not**, and the
   corpus-level-only wording from phase 6 step 10 is updated the day item 1 lands, not later.
10. The ROADMAP spine carries a 6.5 row, and `KNOWN-GAPS.md` shows this phase's debt closed or explicitly
    re-deferred with a reason.

## 7. Rules that govern this phase

- **`verification` and `corroboration` are different fields and must never be collapsed.** One says how
  strongly ONE source was checked; the other says whether a second source agrees. A corroborated
  `PROSE_AUTO` edge is not a `HAND` edge.
- **`contested` means two DIFFERENT sources assert opposite directions for one pair.** Not "a reciprocal
  pair exists" — 6 reciprocal pairs against 2 contested at v0.7.1, and the loose reading overcounts by 3x.
- **Claims first, prose second.** Nothing in item 1 may let prose assert an edge the gate did not pass.
- **Refusal is correct behavior**, and refusal accuracy is reported as a pair — true and false refusals —
  always. A system that refuses everything scores perfectly on hallucination and is useless.
- **Do not invent thresholds before a baseline exists**, and do not re-tune an existing one to accommodate
  a changed dataset.
- **Evals run against a pinned artifact version.** The pin does not move in this phase.
- **The held-out set is never read.** `.claude/rules/heldout-set.md` governs in full.
- **Verify a lock by breaking it.** Every new lock in this phase gets broken once, watched to fail, and
  restored — the practice `tests/test_thresholds.py` already documents.

## 8. Known risks

- **The keystone invites collapsing two fields.** Item 1 puts `contested` next to `verification` in the
  same response for the first time. This repo has already corrected three files for blurring those, from
  the other direction. If a UI or an envelope ever shows one number where there are two, the defect is back.
- **`gold_v0_1_020` may not be a code bug.** 7 of 7 identical failures reads like determinism, and the
  cause may still be the model declining a 7-node path. The failure mode to avoid is tuning a prompt until
  the case passes and calling that a fix; that is fitting to a test case, and the gold set stops measuring
  the day it happens.
- **Item 7 is the item most likely to be deferred a third time.** It is genuine authoring, it is the least
  interesting work in the phase, and it has been postponed twice for good reasons. If it slips again, the
  honest move is to say the `dbpedia_only` slice is unmeasured and mean it, not to carry it forward
  silently.
- **Tier 3 is gated behind tier 2 by arithmetic, not by preference.** Every case added moves `case_count`
  and invalidates a threshold set measured before it. Measuring the baseline early would waste ~$2.50 and
  three hours, and produce a set that un-gates itself the moment case 6 lands.
- **Scope creep into phase 7.** "While we are in the agent anyway" is how the guided tour gets started
  early and half-finished. The fence in §4 exists for that sentence specifically.
- **This phase has no new corpus and no new visual, so it will feel less rewarding than phase 6 did.**
  That is not a reason to shorten it. It is the phase where the project stops overstating what it can say.

## 9. Cost

| item | cost |
|---|---|
| Tier 1 and tier 2 work | $0 — code and hand-authoring |
| Wiring checks during development (`make eval-live ARGS='--cases 1'`) | a few cents each |
| Tier 3: five live runs for the floor and the set | **~$2.50**, and roughly **3 hours** of wall clock at 9 RPM |
| A judged tier 2 at the freeze | a few cents |
| **Phase total** | **under $4** |

**ACTUAL, 2026-09-07: $2.61 across five runs of the 56-case set, ~2.4 hours** — inside the estimate
below, and cheaper per case than projected because the model issued ~4.7 requests per case rather than
the estimated 7. Wall clock was the real cost exactly as predicted. The figure below is the estimate as
it stood before the runs and is kept as a record of it.

The measured per-run figure is **~$0.42** at 45 cases against the v0.7.1 corpus, scaled from the
2026-09-06 run's 348,625 tokens. It will rise as tier 2 adds cases. **Wall clock, not dollars, is the real
cost of tier 3** — five sequential runs that cannot be paused.

## 10. The inherited debt, in full, with its disposition

Everything `KNOWN-GAPS.md` carried as owed on 2026-09-06, so nothing is lost by being unlisted above.

| # | item | disposition |
|---|---|---|
| 1 | `contested` unreachable in an answer | **In** — tier 1, the keystone |
| 2 | `gold_v0_1_020` false refusal, 7 of 7 runs | **In** — tier 1, diagnose then decide |
| 3 | `agent/loop.py:770` refusal wording | **In** — tier 1 |
| 4 | `ResolveSource` cannot verify a DBpedia URI | **In** — tier 1 |
| 5 | Two contested gold cases | **In** — tier 2, unblocked by item 1 |
| 6 | `ambiguous`-branch case | **In** — tier 2 |
| 7 | `dbpedia_only` gold cases (~12x oversample) | **In** — tier 2, deliberately, count is a decision |
| 8 | v0.7.x live threshold set + noise floor | **In** — tier 3, after tier 2 settles |
| 9 | `xfail` marker on the gateability lock | **In** — tier 3, removed by the invariant holding |
| 10 | `_ungateable` "subset" wording | **In** — tier 3, trivial |
| 11 | Contested eval coverage | **In** — tier 3, gated-or-tracked is a decision |
| 12 | `MYCELIUM_TOKEN_PRICES` unset | **In** — tier 4 |
| 13 | Held-out set pinned at 0.5.0, run once | **Decision only** — §5.5, his, at the freeze |
| 14 | `-bedrock.json` runs gitignored | **Decision only** — §5.6 |
| 15 | Phase 6 step 10 copy sweep | **Out** — belongs to phase 6 and is done before this phase starts |
| 16 | P279 genre-domain boundary predicate | **Out** — owed only if a later phase ingests P279 |
| 17 | Guided tour, writeup, portfolio surface | **Out** — phase 7 |
