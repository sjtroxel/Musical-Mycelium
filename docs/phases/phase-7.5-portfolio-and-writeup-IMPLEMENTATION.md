# Phase 7.5 — Portfolio and Writeup (v1.0) — IMPLEMENTATION

> **As-built plan.** Written 2026-09-09, immediately after phase 7 closed and before anything here is
> built, against measurements taken the same evening rather than recalled. The scope doc
> `phase-7.5-portfolio-and-writeup.md` was written 2026-09-08 at the moment the phase was conceived;
> nothing in it is withdrawn, but §3 below records four places where phase 7 moved out from under it.
>
> **On the timing, once.** The convention is that this doc is written *immediately before* phase N is
> built so it can absorb what 1..N-1 taught. Phase 7 closed an hour before this was written with nothing
> scheduled in between, so this is that moment; the lessons are as fresh as they will ever be.
>
> **Approved 2026-09-10, as written.** None of the five §8 decisions blocks step 0. Two were closed the
> same morning — the held-out number is published, and `_sentences` is fixed as an inserted step 0.5
> ahead of the report — and the other three are settled by the step that has the information.
>
> Steps are marked `[done]` as they land, and each carries an as-built subsection recording where reality
> disagreed with this plan. The doc is allowed to be wrong. It is not allowed to be silently wrong.

## 1. What this phase delivers, in one sentence

**The release.** Everything the project knows about itself, published where a skeptical stranger can read
it and check it — the eval report including the parts that do not flatter it, the trend view, the README,
the recruiter path, a verified infrastructure round-trip and a verified bill, and **the writeup, in his
words.**

This is **v1.0**. Phase 7 was v0.8. Product v0.7 is deliberately never used — the artifact pin is v0.7.1
and `ROADMAP.md` §2 already names reading one version line as the other as the confusion it exists to
prevent.

## 2. Baseline, measured 2026-09-09, not recalled

Everything below was run this evening on a clean tree at `948dec8`.

| measurement | value | how |
|---|---|---|
| Python suite | **1522 passed**, 14 deselected, 0 xfailed | `make check` |
| mypy | clean over **106** source files | `make check` |
| Frontend suite | **428 passed** across 24 files | `npm test` in `web/` |
| Repo root | **17 entries**, cap 18 | `make root-check` |
| Scripted eval gates | **4 passed / 0 failed / 2 N/A** of six, plus an ungated tour run | `make eval` |
| Artifact pin | **0.7.1** | `graph/memory.py` |
| Corpus | 1,479 nodes, **5,066 edges** | `/health` |
| Influence edges | **2,284**, of which **82 corroborated** and **2,202 single-source** | `store.corroboration` |
| Contested pairs | **2** (6 reciprocal pairs, only 2 contested) | `graph/corroboration.py` |
| Datasets | gold **38**, adversarial **20**, live **56**, tour **6** | the dataset files |
| Held-out | sealed, pinned 0.5.0, **run count 1** | not opened, and not opened by this plan |
| Asset budget | script **276.1 KB of 320**, style 11.2 of 40, graph 2.57 MB of 3.00, media **0 of 0** | `npm run budget` |
| Stored eval runs | **32 result files**, 26 of them `live` | `eval/results/` |

## 3. Four things phase 7 moved, and one it did not touch

### 3.1 The deployed site is still the `v0.6.0` build

**Nothing from phase 6.5 or phase 7 is live.** Not the contested disclosure, not the backdrop, not the
motion system, not the guided tour. A visitor today sees a build from 2026-09-06.

**This phase is the one where that stops being acceptable**, because this is the phase that points a
recruiter at a URL. A portfolio phase whose live artifact predates two phases of work is the failure the
phase exists to prevent. DoD 4 — *"`terraform destroy` still removes everything, and `terraform apply`
still rebuilds it"* — **is a deploy by definition**, so the deploy is inside this phase whether or not the
scope doc named it. Step 3 owns it.

### 3.2 The report has no publishable form at all

`eval/report.py` is 274 lines and exposes exactly two functions, `render` and `render_judged`. Both emit
**terminal text**. There is no HTML, no route, no build step, nothing a browser can open.

So DoD 1 is not "add slices to the report" — the slices are already computed and printed. It is **build a
published surface that did not exist**, and phase 7's byte budget now gates whatever it emits. Named here
because the step looked like a formatting pass and is not.

### 3.3 Judge-human agreement is moderate, and DoD 1 requires publishing it anyway

Measured across the three judge runs in `eval/results/`, all `amazon.nova-pro-v1:0` over `judge_pool_v1`,
n=30:

| metric | exact agreement | Cohen's kappa |
|---|---|---|
| `citation_support` | 0.63 – 0.70 | **0.44 – 0.48** |
| `narrative_quality` | 0.60 – 0.67 | 0.66 – 0.73 |

**Kappa 0.44 is moderate at best**, and it is the metric on the more consequential question. Publishing it
is not optional: `.claude/rules/evals.md` says *"an LLM-judge score with no measured agreement is
decoration"*, and DoD 7 requires the report to show what did not work.

**A fourth number belongs beside those and is not currently in DoD 7's list.** The same pool judged three
times scored **14/30, then 12/30, then 11/30** supported. That is the **judge disagreeing with itself** on
identical inputs, which is a different and larger caveat than its disagreement with a human. Step 1 adds
it to what the report shows.

### 3.4 Reader-facing numbers rot, and this repo has now been bitten three times

The README currently claims **"1465 Python tests and 210 frontend tests."** Measured today: **1522 and
428.** It was true when written and is wrong now.

That is the **third instance of one pattern**, and phase 7 named the other two:

1. The asset budget's `observed` fields sat at step 0's numbers while step 3 added 35 KB, and a plan was
   written off them.
2. `SPEC.md` advertised a demo route with no path for six weeks, because **a demo query written in prose
   is not data and nothing executed it**.
3. This.

**The fix that worked twice is the same one:** `tests/test_chips.py`, `tests/test_gold_set.py` and
`tests/test_canonical_surfaces.py` all make a claim fail the build rather than the reader. Step 0 applies
it to reader-facing counts. **This phase publishes more prose containing more numbers than any phase so
far**, and it publishes it to strangers, so the pattern gets closed before the prose is written rather
than after.

### 3.5 What phase 7 did not touch, and this phase must not either

The live eval baseline. 56 cases, bounds measured over five identical runs at $2.61 and ~2.4 hours.
**Nothing in this phase adds a live case**, because `thresholds.py:_ungateable` returns before any
per-metric check the moment the count moves. The held-out set stays sealed at run count 1.

## 4. The finding this plan adds: only 5 of 26 stored live runs are comparable

Read out of `eval/results/` today, not recalled. The trend view's difficulty is not drawing a line; it is
that **most of the history cannot honestly be on the same line.**

| artifact pin | cases run | runs | what they are |
|---|---|---|---|
| 0.5.0 | 41 | **12** | the old comparable cohort |
| 0.5.0 | 1 or 3 | 4 | smoke tests |
| 0.5.0 | 32 | 1 | **incomplete** (`complete: false`) |
| 0.6.0 | 41 | 1 | a single run on a corpus nothing else shares |
| 0.7.1 | 45 | 1 | superseded by the 56-case set |
| 0.7.1 | 1 | 2 | smoke tests |
| **0.7.1** | **56** | **5** | **the current comparable cohort — the noise floor** |

A naive line over all 26 would join three corpora, five case counts, four smoke tests of a single case,
and one aborted run. The scope doc's risk — *"a chart that lies more easily than a sentence"* — is not
hypothetical here; it is what the default implementation produces.

**The admission rule already exists in code and must be reused rather than reinvented.**
`ThresholdSet.matches` keys on dataset **and** provider; `_ungateable` refuses a run whose case count has
moved off its baseline. **If the gate would not judge two runs against the same bounds, the trend view
must not join them with a line.** That is the scope doc's own wording — *"does not join points that the
gate logic itself would refuse to compare"* — and the cheapest correct implementation is to call the
existing predicate rather than write a second one that drifts.

**Consequence for the shape: cohorts, not a line.** The view shows comparable groups as separate series
with their case count and pin on the label, and shows the incomparable runs as points that are
deliberately not connected. Five points is a short series and it must be *drawn* as a short series rather
than stretched to look like a trend.

**Three files carry no `written_at` at all** — the earliest 0.5.0 runs, from before the field was added.
The timestamp is in the filename. Step 2 reads the filename as a fallback and says so on the page, or
excludes them and says so; it does not silently guess.

## 5. Steps

### Step 0 — Make reader-facing numbers fail the build — [done]

The pattern from §3.4, closed before the prose is written. Inventory every number and factual claim in
reader-facing prose — README, and whatever step 1 and step 4 produce — and for each one decide: **derived
at build time, asserted by a test, or deleted.** A number that is none of those does not ship.

**Done when:** a stale count in the README fails `make check`, and the current counts are correct.

#### 0.0 As built, 2026-09-10

**Derived, not asserted.** His question was whether the numbers could update themselves rather than
become a standing chore. They can: every current-state figure in the README sits between invisible
markers — `<!-- n:influence_edges -->2,284<!-- /n -->` — and `make readme` rewrites all of them from
their sources. `eval/published.py` is the generator; it lives in `eval` because that is the one package
allowed to import the graph, the tool registry and the datasets together. It is the `graph/facts.py`
arrangement extended to the page a stranger reads first.

**Two checkers, split by toolchain.** `tests/test_published_numbers.py` checks every marked figure the
backend can compute, in both directions: a stale value fails, an unknown key fails, and a figure the
generator computes but the README no longer marks fails — so deleting a marker and retyping the number
by hand is caught too. The frontend count needs Node and the backend CI job has none, so
`web/scripts/readme-count.mjs` checks it inside `npm run check`, reading the JSON report the test run
already writes rather than collecting twice.

**Test counts are floors — decided by him.** "At least 1,500", rounded down to the hundred. An exact
count would fail every commit that adds a test; a floor is true the moment it is written and fails only
when the suite crosses the next hundred and the sentence starts understating it.

**35 markers over 28 figures. The inventory found more rot than §3.4 knew about:**
- the test counts (1465 / 210 against 1522 / 428), as expected;
- **"43 of its genres name no US or UK origin" across "29 places" — the v0.5.0 figures, two artifact
  versions stale.** v0.7.1 reads **136 across 65**. This one *understated* the corpus's reach, in the
  sentence whose whole job is the counterweight to its skew;
- "45 development cases against a live model" — the live set is 56.

**Deliberately not marked.** Dated measurements (the 2026-09-06 latencies, $2.61, the single held-out
run) are history and need only their date. **Facts about the deployed site** — "the live URL serves …
artifact v0.7.1" — change on a deploy, not a commit, so a repo-side derivation would be the wrong
source. Step 3 owns those.

**What this step cannot catch, and it is the larger half.** Markers protect numbers. They do nothing for
a false *sentence*, and the README carries at least five, all left for step 4 because the prose is his:
"Phase 7 is under way" (it closed 9/9); "the agent does not read them … no eval case exercises it" (6.5
made both false); "the noise floor [was] measured at artifact v0.5.0 … neither has been re-measured"
(re-measured 2026-09-07 at v0.7.1); "the frontend, which arrives at v0.5"; and MusicBrainz as "a phase 6
question". Also unmarked: "**four** of six" gates, which would need a scripted eval run to derive and
which `evals.md` already says not to write in prose — step 4 should delete it rather than mark it — and
"20% recall", a measurement with no date beside it.

**Verified by deliberate breakage, both halves.** A README reading 1,478 nodes is reported as
`n:nodes -- README says 1,478, the source says 1,479`; a frontend floor edited to 300 fails
`npm run readme-count` with exit 1. `make check`: **1530 passed** (1522 + 8 new), frontend 428,
mypy clean over 108 files.

### Step 0.5 — Fix `loop.py:_sentences`, before anything is published — **inserted 2026-09-10** — [done]

Decided by sjtroxel 2026-09-10, closing the fourth §8 decision. The diagnosis is phase 7 §8.0: a
four-claim chain is padded into two sentences and the model fills the second by restating the chain
backwards. **It goes here rather than later because of ordering, not tidiness.** Step 1 publishes
`narrative_quality`; fixing the padding after that means publishing twice and re-measuring once more.

**What the fix invalidates is a question to measure, not assume.** Claims are emitted and gated before
prose exists, so the gated correctness metrics should not move when only the sentence budget changes.
That is a hypothesis. `narrative_quality` is judged, so it moves by design, and a judged tier 2 run is
cents. If the change reaches anything a live gate reads, the $2.61 / ~2.4 hour re-baseline is back on the
table, and it runs behind the usual spend confirmation or not at all.

**Done when:** a four-claim chain no longer restates itself in live captures, and the invalidation
question has a measured answer written here.

#### 0.5.0 As built, 2026-09-10

**The fix is one line.** Chains of two to four claims are now told "one or two sentences", the same
permission a fan-out gets. Chains above four keep "two or three": that branch already produced clean
prose, and changing it would move a thing nobody measured as broken.

**The "before" cost nothing, because it was already on disk.** `eval/transcripts/` holds the narration
of all five 2026-09-07 baseline runs. The four gold chain cases, five runs each:

| case | claims | asked for | padded |
|---|---|---|---|
| `gold_v0_1_016` | 2 | "two sentences" | 0 of 5 — two claims, two sentences, naturally |
| `gold_v0_1_018` | 3 | "two sentences" | 0 of 5 — four of five wrote one sentence anyway |
| **`gold_v0_1_019`** | **4** | **"two sentences"** | **4 of 5** |
| `gold_v0_1_038` | 5 | "two or three" | 0 of 5 — one clean sentence every run |

**The baseline found a worse variant than phase 7 did.** Phase 7's four-claim captures *restated* the
chain backwards, which is harmless. The baseline's four-claim padding is *editorial*: "connects five
artists across generations", "a direct line of musical influence", and once **"each shaping the artistic
direction of the one before them"**, which states the influence in the wrong direction. The embellishment
ban forbids exactly this and the fixed count overrode it. Nothing gated saw it, because nothing gated
reads prose.

**The invalidation question, answered by reading the code.** Synthesis runs after the gate, over
approved claims only, so it cannot change what any gate reads. Checked per gate:
`edge_groundedness` and `citation_resolution` read approved claims; `refusal_accuracy` reads whether the
run refused; `traversal_recall` reads claims against the expected path; `injection_resistance` and
`contested_disclosure` are both exact set operations over claim triples and announced pairs, each
documented as "no text matching". **So the live bounds stay valid and the $2.61 re-baseline is not
needed.** That is an answer by construction. The measurement that confirms it is step 1's live run, which
gates all six anyway. What *can* move is tracked, not gated: output tokens, slightly, and
`narrative_quality`.

**`narrative_quality` is measured at step 1, not here.** A judged score over three chain cases has no
power: the judge's own agreement is kappa 0.66-0.73 on that rubric and it disagrees with itself between
runs. Step 1 needs a fresh release-candidate run and tier 2 anyway to publish a current number, so that
is where the effect is measured, once, instead of paying for it twice.

**The "after": three live runs of the three short chains, run by him, about 6 cents total.** Transcripts
`20260910T150827Z`, `T151013Z` and `T151214Z`, each recording revision `c11d97e-dirty` because the fix
was not yet committed when they ran. The revision that contains it is the commit that lands this
as-built.

| case | claims | before (5 runs) | after (3 runs) |
|---|---|---|---|
| **`gold_v0_1_019`** | **4** | **padded 4 of 5** | **clean 3 of 3**: one sentence, the chain and nothing else |
| `gold_v0_1_018` | 3 | clean 5 of 5 | clean 3 of 3 |
| `gold_v0_1_016` | 2 | two sentences, one fact each | one sentence carrying both facts |

Under the old behavior three clean four-claim runs in a row is about a 1-in-125 event (0.2 cubed), which
is why this was three runs rather than one: the old behavior was clean once in five by itself. **The
`016` change is a style change, not a defect fixed.** Two one-fact sentences were never padding, and one
sentence is what a permission produces when the model is not pushed. All three runs scored 3/3 correct
with 100% groundedness and citation resolution, and gated nothing, correctly, as a subset.

**Confirmed by measurement at step 1, 2026-09-10.** The full 56-case live run on committed revision
`0dd653b` passed **all six gates** against the unchanged 2026-09-07 bounds, and `gold_v0_1_019` narrated
clean again: **four clean runs of four** since the fix. Tier 2 over that run read `narrative_quality`
4.15, against 4.25 on 2026-09-06. That is a different sample of a different-sized run, judged by a judge
that scored the *same* 30 items 14, 12 and 11 across three runs, so **the judged number neither shows the
fix nor argues against it.** The transcripts are the evidence; the judged score is a tracked reading
beside them.

### Step 1 — The published eval report — [done]

DoD 1 and DoD 7 together, and 7 is the harder half. Per-metric and per-slice, judge-human agreement
printed next to every judged metric, the measured noise floor on the page, and **an explicit section for
what did not work**: `gold_v0_1_020` with its diagnosed cause, the `Joy Orbison` / `Roy Orbison` failure
that scores 100% on groundedness and citation resolution while being about a different person, **the two
`N/A` gates that are not passes**, the judge's own run-to-run variance from §3.3, and **2,202 of 2,284
influence edges being single-source.**

Format, route and byte class are decided in the step, from what the existing `render` already computes.

**Done when:** the report is reachable in the built site, contains all seven items above, and `make check`
still passes its byte budget.

#### 1.0 As built, 2026-09-10

**Format: one static HTML page, generated by Python, chosen by him from three.** `make report` writes
`web/public/report/index.html` from committed files; Vite copies `public/` into the build unchanged, so it
ships at `/report/index.html` with **no JavaScript, no router, and no second copy of any metric**. Rejected:
a view inside the SPA (spends the scarce script bytes, adds the routing the app decided against, and
renders every number through a second code path) and a Markdown file in `docs/` (fails this step's
done-when: not in the built site). `tests/test_report_page.py` byte-compares the committed page with the
generator, so a stale report fails `make check`. Its own byte class, `report`, **11.8 KB of 64**.

**Every section reuses the code that already decides its number.** Scripted gates are computed fresh by
`run_gold_suite` and `gate` (0.2 s). Metric values go through `noise.METRICS`, the extractors the floor
was computed with. The floor is `noise_floor.json` as written. A judged number without its agreement
range raises `NoAgreement`, the rule `report.render_judged` already enforced in the terminal.

**Live gate verdicts are STORED, not re-derived — the one behavior change.** Stored live results carried
metrics but no verdict, and re-deriving one from bounds on the page would have been a second
implementation of `thresholds.py`. So `eval-live` now gates **before** writing and stores the outcome in
the result file (`live.gate_record`); a run the gate refused records `set: None` and why. The page shows
a run as gated only if its own stored verdict names the live set — the gate's comparability judgement,
reused rather than restated, which is what §4 asks of step 2 as well. **The first such run is 2026-09-10
16:41 UTC on committed revision `0dd653b`: 6 passed, 0 failed, 0 not applicable.**

**The seven items, each present:** per-metric beside the five-run range; per-slice with n<5 marked;
agreement beside both judged metrics; the noise floor; the held-out result with its run count and its
older pin; the judge's self-disagreement (14, 12, 11 of 30); and a "what did not work" list —
`gold_v0_1_020` with its cause and exclusions, the four unstable cases, both N/A gates, 2,202 of 2,284
edges single-source, the held-out set untested at the current corpus, and Joy/Roy Orbison.

**The plan's wording on Orbison was corrected before it reached the page.** Step 1's text calls it "the
failure that scores 100% on groundedness". It is not an observed failure: `adv_019` asserts Joy's
influences about Roy and is **refused**. What phase 6.5 recorded is a failure mode **no metric can
catch** — a model that typed one name for the other would answer, fully grounded, about the wrong person.
The page says that.

**Tier 2 over the fresh run: `citation_support` 14 of 20, `narrative_quality` 4.15.** On 2026-09-06 it
read 18 of 20 and 4.25. **Neither movement is a finding.** Different run, different case count (45 then,
56 now), therefore a different sample; a judge at kappa 0.44–0.48 on citation support that scored the
same 30 items 14, 12 and 11. The page prints the numbers with their agreement and claims no trend.

**The `unknown` slice is not what it looks like.** Every dimension carries an `unknown` bucket of 9 cases.
`eval/slices.py` defines it as **the case's subject never resolved to a node** — absent subjects such as
the refusal cases — and keeps it distinct from `undated`, a real node with no inception year. It is a
correct bucket, but on a public page it reads like missing data. Step 4 or the `COPY` rewrite should
say what it is in one line.

**Owed, and not blocking this step:**
- **`COPY` in `eval/report_page.py` is my draft, and he decided on 2026-09-10 to keep it for now.** It
  does **not** block step 3. Every explanatory sentence on the page lives in that one block, so a later
  rewrite in his words is a single edit plus `make report`.
- **`/report/index.html`, not `/report/`**, is linked from the app footer, on the understanding that
  CloudFront's default root object covers only the site root. **Verified at step 3's deploy, not here.**
- The Lambda image copies `src/` whole and so carries results and transcripts (§8, step 3).

### Step 2 — The trend view — [done]

§4 is the plan. Cohorts keyed by the existing gate predicate, incomparable runs shown and not joined, the
noise floor drawn so a movement inside it is visibly inside it, per-case data available because
**an aggregate hiding a per-case constant has bitten this project twice.**

**Done when:** the view reads `eval/results/` rather than a hand-maintained table, refuses to join what
the gate would refuse to compare, and a test asserts that refusal.

#### 2.0 As built, 2026-09-10

**On the report page, not its own page** — §8's first decision, closed. One generator, one byte class,
no script. Small multiples as inline SVG from `eval/trend.py`; the sentences stay in
`report_page.COPY`. The page is **46.1 KB of 64**, and most of the growth is the table twins, which add
roughly one row per future run.

**The cohort rule is borrowed from the noise floor, and it is STRICTER than the gate — a finding.** §4
said to key cohorts on the gate's predicate. Read closely, `thresholds._ungateable` checks that a run
finished and that its case count matches the baseline. **It never checks the corpus pin.** So by the
gate's rule alone, the single 41-case run at artifact 0.6.0 would share a line with the twelve 41-case
runs at 0.5.0, across a corpus change. `noise.POOLING_FIELDS` refuses exactly that. So a cohort is
every pooling field **except `code_revision`**, which is released on purpose because a trend exists to
cross code changes, plus an identical case list and a finished run. `tests/test_trend.py` asserts the
implication the plan asked for over every committed run — nothing joined is a pair the gate would
refuse — and pins each refusal synthetically: a different corpus, a subset, the same size with
different cases, an unfinished run.

**Charted at `noise.MINIMUM_RUNS` or more, and nothing else is drawn.** Two cohorts qualify: **0.7.1 at
56 cases, 6 runs** (the five-run baseline plus today) and **0.5.0 at 41 cases, 12 runs**. Eight more are
listed under "shown, and not joined" with the reason: smoke tests, subset runs, the unfinished run,
the lone 0.6.0 run and the lone 45-case run. §4's table was 26 runs counted by hand; the page now counts
30 by code.

**The noise band is drawn only on the cohort that contains the measured floor's runs.** The 0.5.0 floor
was replaced at re-measurement and survives only in git history, so that cohort has no band, and the
page says so rather than borrowing one.

**The x-axis is run order, not time, and the page says so in words.** Five of the six 0.7.1 runs are
from one evening, so equal spacing hides a three-day gap before the sixth.

**The chart color failed the dataviz validator and was snapped, not argued.** The app's accent
`#ff5cae` sits at OKLCH lightness 0.712, above the dark-mode band of 0.48–0.67. The line and dots use
`#ec4a9e`: the same hue and chroma at 0.66, and it passes all five checks against the card surface. The
app's accent is unchanged.

**Rendered and looked at**, at 1280 and 400 wide with headless Chromium: three columns on desktop, one
on a phone, no label collisions, every end label inside its frame.

**What the charts show, read without inflation.**
- **Today's `approved_claims` (224) sits above the five-run range (182–218).** Not a finding. A sixth
  run from the same distribution lands above the maximum of five about one time in six, and the
  `_sentences` fix touched prose, which is generated after claims are approved.
- **`traversal_recall` draws a zero-width band** at 97.1%: the zero-variance trap, on the page. The
  per-case table under it answers the question the flat line raises: `gold_v0_1_020` is wrong in 6 of
  6 runs. **51 of 56 cases were correct in all six runs**, and 36 of 41 in the 0.5.0 cohort.

### Step 3 — Deploy v1.0, then prove the round-trip and the bill

DoD 4 and 5, and §3.1's correction. Build and deploy the current tree so the live URL serves what this
repo describes. Then run `terraform destroy` and `terraform apply` **for real** and confirm the site comes
back.

**The bill has a timing constraint worth naming rather than discovering.** DoD 5 asks for cost verified
against a real invoice. An invoice covering a month that has not happened yet does not exist, so this is
verified against the **most recent complete invoice** plus the current month-to-date, and the sentence on
the page says which. If a domain is registered, the number and the sentence both change.

**Done when:** the live URL serves this tree, the round-trip is run rather than asserted, and the cost
claim cites a real invoice with its period.

### Step 4 — The README and the recruiter path

The shape a stranger meets first. Structured here; **the narrative prose is his** — see §6.

**Done when:** the README describes what is deployed, every number in it is covered by step 0, and the
path from landing to report to repo is walkable in one sitting.

### Step 5 — The writeup

DoD 3, and the constraint in §6 is absolute. **Interview, structure, and let him write.** The material
exists: every phase has an as-built with its findings, and the good ones are findings a reader would not
guess.

**Done when:** it exists, it is his words, and he can walk through it cold.

### Step 6 — The definition-of-done audit, and the close

**A pass, not a checklist**, for the reason phase 7 proved: every DoD item there had a test, and the test
for item 9 passed the entire time while the item was broken, because it tested a component in isolation
and the defect was in a caller that did not exist when the test was written. **A component test cannot see
a new caller that forgot to call it.**

**Done when:** each of the seven items has a verdict with evidence, defects found are fixed or recorded,
and the phase is closed in `ROADMAP.md` and `docs/KNOWN-GAPS.md`.

## 6. The writeup is his, and this is not negotiable

Restated from the scope doc §6 because it governs steps 1, 4 and 5 and is the easiest thing here to
violate by being helpful.

Claude's prose carries an invisible SynthID watermark. **It is in the word choices, not the clipboard** —
retyping by hand does not remove it; only rewriting in his own words does. Code is largely exempt, prose
is not.

**So: every word a human reads as his is written by him.** The writeup, the README's narrative sections,
any recruiter-facing copy. The correct support is to **interview him and structure bullets he rewrites**,
never to hand him finished paragraphs. Flag it in one line at the moment prose bound for such a field is
handed over.

It is also right on the merits. DoD 3 is *"he can walk through it cold,"* and prose he did not write is
prose he cannot walk through cold.

**What this does not cover:** code, config, commit messages, test docstrings, and this document. Those are
mine to write and always have been.

## 7. Testing, and which eval metrics apply

**No new eval metrics, and no new live cases.** The scope doc's not-list forbids the first and
`_ungateable` prices the second at $2.61 and ~2.4 hours. The tour set stays at 6 and stays ungated; gold
stays at 38; live stays at 56 and its baseline stays valid.

**What does get tests:** step 0's claim assertions, step 2's refusal-to-join predicate, and whatever step
1 renders — the report is a surface that states numbers, so the numbers it states are exactly the class
step 0 exists to protect.

**The frontend suite is at 428 across 24 files** and steps 1, 2 and 4 add to it.

**Known and not this phase's job:** the suite emits React `act` warnings, 20 from `App.test.tsx` alone
before phase 7 and 3 more from the tour. Real, pre-existing, and named so it is not rediscovered as new.

## 8. Decisions this plan does not make

- **The report's published location and route**, and whether the trend view is part of it or its own page.
  Step 1 decides from what `render` already computes.
  **Decided 2026-09-10:** one static page at `/report/index.html` (step 1, his pick of three), and the
  trend view is a section of it (step 2), not a page of its own.
- **Whether the held-out number is published.** It is a single run of ten cases and publishing it invites
  a reader to ask for more, which is the one thing that set can never survive. Scope doc §8 left it open
  and it stays open until step 1.
  **Decided 2026-09-10: published**, with the run count and the n=1 caveat beside it. It is derived by
  code from the stored result's aggregates, never typed and never opened into an agent's context. It
  cannot rot on its own: it changes only when the set is run, and running it is itself a gated act.
- **The domain.** Registering one changes DoD 5's number and its sentence. Not decided here.
- **Whether `loop.py:_sentences` gets fixed.** Diagnosed in phase 7 §8.0 across three live captures: a
  four-claim chain is padded into two sentences and the model fills the second by restating the chain
  backwards. It governs every chain answer and `narrative_quality` is judged, so it is a freeze decision —
  and **this phase is a freeze.** If it is taken, it is taken deliberately with a re-measure priced in,
  not as a tidy-up before publishing.
  **Decided 2026-09-10: fixed, before step 1.** It is step 0.5, with the re-measure question inside it.
- **Whether to deploy before or after the report exists.** Step 3 as written deploys first so the README
  can point at something true; a reader might reasonably want the report live on the same push.
- **Whether live result files start being committed. Added 2026-09-10, found at step 0.5, and it bears
  on steps 1 and 2 directly.** `.gitignore` ignores every `-bedrock.json` on purpose — *"they cost about
  36 cents and re-running one answers the same question again"* — and commits only judge, tier 2 and
  held-out runs. So **the five 2026-09-07 baseline runs the live gates were measured on exist only on
  his disk**, and so does every run §4's "5 of 26 comparable" was counted from. The gates survive that,
  because `thresholds.json` records its measured values beside each bound. **The trend view does not:**
  step 2 says it reads `eval/results/`, and from a clone or in CI that directory holds judge files and
  nothing else. The rule's reasoning also fits a *benchmark* better than a *history*: re-running
  answers the same question again but produces different numbers — the noise floor exists because it
  does — and a trend view is exactly the thing that needs the old numbers rather than new ones. Either
  answer is defensible. Committing the comparable cohort, or a derived summary of it, keeps the published
  view rebuildable; leaving the rule alone means the view is built locally and its data is published
  with it. **Settled at step 1, before step 2 builds on either assumption.**
  **Decided 2026-09-10 at the start of step 1: all of them are committed**, smoke tests and subset runs
  included — 29 files, 452 KB, checked for account ids, keys and held-out content first, and none found.
  `.gitignore` carries the reasoning. So step 2's trend view reads a directory a clone actually has.
  **Owed at step 3:** `infra/docker/Dockerfile` copies all of `src/` and its dockerignore excludes
  nothing under `eval/`, so the Lambda image already carries the transcripts and will now carry the
  results. About 1.5 MB total and harmless against the limit, but runtime has no use for either.
