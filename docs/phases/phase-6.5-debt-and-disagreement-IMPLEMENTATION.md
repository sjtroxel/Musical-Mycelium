# Phase 6.5 — Debt and Disagreement (v0.6.5) — IMPLEMENTATION

> **As-built plan.** Written 2026-09-07, immediately before building, against measurements taken the same
> morning rather than recalled. The scope doc `phase-6.5-debt-and-disagreement.md` was written 2026-09-06
> and nothing in it is withdrawn. What this doc adds is the part a scope doc written before reading the
> seam could not know, and it is in §3: **two of the four tier 1 items land on the same protocol, and
> neither can start until it is widened.**
>
> Steps are marked `[done]` as they land, and each carries an as-built subsection recording where reality
> disagreed with this plan. The doc is allowed to be wrong. It is not allowed to be silently wrong.

## 1. What this phase delivers, in one sentence

**The behavioral half of phase 6:** an answer that can say the sources disagree, a refusal that says what
it actually means, and a live eval suite that gates again on numbers measured rather than invented.

Definition of done is the scope doc's §6, ten items, unchanged. This plan does not restate it and does not
relax it.

## 2. Baseline, measured 2026-09-07, not recalled

Everything below was run this morning on a clean tree at `400eea1`, with `README.md` modified.

| measurement | value | how |
|---|---|---|
| Python suite | **1330 passed, 14 deselected, 1 xfailed** | `uv run pytest` |
| Frontend suite | **159 passed** across 15 files | `npm test` in `web/` |
| `make check` | green end to end | `make check` |
| Scripted eval gates | **3 passed, 0 failed, 2 N/A** of 5 | the `eval` target inside `make check` |
| Artifact pin | **0.7.1** — 1,479 nodes, 5,066 edges | `graph/memory.py:34`, `default_store()` |
| Live dataset | **45 cases**; live threshold set measured over **41** | `eval.live.live_cases()`, `thresholds.json` |
| Gold set | **29 cases, 66 expected claims** | `eval/datasets/gold_v0_1.json` |
| Gold `dbpedia_only` subjects | **4** of 29 | `eval.slices.source_slice` over each case's `expected_resolution` |

**The live set is 45 rather than 47** because `adv_014` and `adv_015` are deliberately excluded from it
(`eval/harness.py:64-65`) — they need a poisoned artifact and a hostile stub tool, and are driven by
`tests/test_untrusted.py` instead. All 29 gold cases run live, so **every case step 5 adds moves the live
count too**: 45 becomes 54.

The `xfailed` is the deliberate live-gateability lock at `tests/test_thresholds.py:143`. It is
`strict=True`, so the day tier 3 lands a matching baseline it XPASSes and turns the build red until the
marker is deleted. That is item 9 announcing itself, exactly as designed.

**The two contested pairs, read out of the pinned store by hand this morning** — these are the subjects
tier 2 must author against, and neither was written down anywhere as a pair of QIDs before now:

| pair | edge | source |
|---|---|---|
| western music / New Mexico music | `western music influenced_by New Mexico music` | dbpedia |
| | `New Mexico music influenced_by western music` | wikidata |
| electropop / electroclash | `electropop influenced_by electroclash` | wikidata |
| | `electroclash influenced_by electropop` | dbpedia |

**The `ambiguous` branch is reachable and confirmed:** `search("big band")` returns exactly two nodes,
`Q207378` *big band* and `Q105756581` *big band music*, which is the two-match state
`agent/tools.py:211` reports as `"ambiguous"`.

## 3. The finding this plan adds: the seam is the gate on tier 1

The scope doc named a `GraphStore` widening as a cost of **item 4** only. It is a cost of **item 1** as
well, and item 1 is the keystone.

**What the protocol actually exposes** (`graph/store.py`): `artifact_version`, `get_node`, `neighbors`,
`search`, `path`, `coverage`. That is all.

**What `contested` lives on:** `InMemoryGraphStore.contested` at `graph/memory.py:285` and
`InMemoryGraphStore.corroboration` at `:266` — **concrete-class properties, not protocol members**. The
API can read them because `api/app.py` holds the concrete store. `agent/` cannot, because every seat in
`agent/loop.py`, `agent/tools.py` and `agent/claims.py` is typed `GraphStore`.

So `agent/claims.py:29` is exactly right when it says *"today nothing in this package reads corroboration
at all"*, and the reason is structural rather than an oversight: **there is nothing on the seam to read.**

**Both items land on the same seam, so it is widened once, first, in its own step.** Item 1 needs
contested pairs; item 4 needs a resource-URI reverse lookup that `ResolveSource` already documents as
missing (`agent/tools.py:588-600`, *"resolving one needs a reverse lookup from resource to node, and
`GraphStore` exposes no way to scan nodes"*).

**This is a prediction from v0.1 arriving, and it should be recorded as one.** `graph/store.py`'s own
docstring says every method exists at v0.1 *"even though v0.1 does not need all of them"*, because
*"adding a method to a protocol later means touching every implementation"* — which is why `path` was
declared and left raising `NotImplementedError` rather than being absent. That reasoning was correct and
it did not go far enough: the shapes it knew about were `path` and `neighbors`, and a second source was
three phases away. The lesson is not "declare more methods speculatively"; it is that **the seam is
correctly the expensive thing to change, so changes to it get their own step and their own review**, which
is what step 1 is.

**One-way door 4 is satisfied, not violated.** The invariant is *"adding a tool must never require editing
the loop."* Step 1 adds nothing to the loop and nothing to any tool's dispatch; it adds read methods to
the data seam, which is the layer the invariant says tools are allowed to depend on.

## 4. A second finding: tier 4 is not independent of tier 3

The scope doc files item 12 (`MYCELIUM_TOKEN_PRICES`) as *"tier 4 — hygiene, independent of everything
above."* It has a hard ordering constraint. **Tier 3 spends ~$2.50 across the five most expensive runs in
the phase**, and with the variable unset every one of them records token counts and prints *"cost not
shown"* (`eval/safety.py:129`). Setting it afterwards does not retroactively price a finished run.

**Item 12 moves to step 0, before anything billable runs.** It is fifteen minutes of work and it is the
difference between the phase's headline measurement carrying a dollar figure or not.

## 5. A third finding: items 2 and 3 are one user-visible failure seen from two sides

`agent/loop.py:765-773` is a two-branch ternary keyed on `visited`:

```python
reason = (
    "it resolved but carries no sourced influences"
    if visited
    else "it is not in this graph"
)
```

The defect is **a missing third branch, not a bad string.** The `visited` branch reports a *run* fact
(the gate approved nothing) in the words of a *corpus* fact (the node has no sourced influences). Those
are different states and only one of them is checkable — and it is checkable cheaply and deterministically
via `store.neighbors(...)` on the visited subject, which needs no new seam and no model call.

**And `gold_v0_1_020` is the case that hits this branch.** It has false-refused a fully answerable
question in 7 of 7 recorded runs since 2026-08-18 (`thresholds.json:126`, `noise_floor.json:195`), which
means the user-facing symptom of the repo's most reproducible bug is *the corpus holds nothing* about a
subject the corpus holds plenty about. That inverts the coverage-honesty rule in
`.claude/rules/grounding-and-claims.md` — *never claim coverage the graph does not have* — by asserting an
absence the graph does not have.

**This gives the ordering an argument rather than a preference: item 3 lands before item 2's diagnosis.**
If diagnosis concludes item 2 is unfixable (decision 5.3, a real possible outcome), item 3 is what stops
that outcome from lying to the user. Fixing the wording first means the honest floor exists whether or not
the bug is fixable, and the diagnosis is not under pressure to succeed.

## 6. Step plan

Ordered by dependency. Steps 0-4 are tier 1 plus the moved item 12; step 5 is tier 2; steps 6-7 are tier
3; step 8 closes.

**Steps 0 and 1 were renumbered on 2026-09-07, after the price step was built.** The seam was numbered
0 and the price table 1 when this plan was written. They do not depend on each other, the price table was
built first because it had to precede any billable run, and the numbers now match the order things
actually happened in. Nothing else moved, and no other step changed number. A plan that records a
different sequence from the one that occurred is the small kind of wrongness this repo pays for months
later.

### Step 0 — `MYCELIUM_TOKEN_PRICES`, before anything billable runs — **DONE 2026-09-07**

Item 12, moved forward for the reason in §4. Set the variable where the eval targets and the deployed
Lambda read it, with Haiku 4.5 and Nova Pro rates recorded **with the date they were looked up**, because
`api/telemetry.py:22` is right that dollars are an interpretation with an expiry date and tokens are not.

**Done means:** a two-cent `make eval-live ARGS='--cases 1'` run prints a dollar figure instead of
*"cost not shown"*.

#### 0.0 As built — what the plan did not know

**Verified on completion, 2026-09-07:** `make check` green — **1334 passed** (from 1330), 14 deselected,
1 xfailed, mypy clean over **99** source files, frontend **159** across 15 files, root **17 of 18**, eval
gates **3 passed / 0 failed / 2 N/A**. Terraform validates and is formatted.

The plan called this fifteen minutes. The typing was; the deciding was not. Six things worth keeping.

**1. The real work was picking where one source of truth lives.** Two surfaces read this table — the
Makefile's billable targets, locally, and the deployed Lambda through Terraform — and the obvious
implementation gives each its own copy. Two copies of a price table is how two surfaces come to disagree
without anyone noticing, and the disagreement would be invisible: both would report plausible dollars.
So `infra/token-prices.json` is read by the Makefile **and** exported as `TF_VAR_token_prices` by
`.github/workflows/deploy.yml`. One file, two consumers, no second copy.

**2. The table is corroborated against a number that predates it, not just looked up.** At $1.00/$5.00
per million, the measured average query recorded in `.claude/rules/aws-and-cost.md` — 6,624 input + 421
output tokens, measured 2026-08-24 — prices at **$0.008729**, and that rule file says **~$0.009**. The
table reproduces a figure computed months before the table existed. `test_the_table_reproduces_the_
projects_own_measured_per_query_cost` locks that, because **a typo that parses is the failure mode here**:
`1.0` mistyped as `10.0` is valid JSON, valid schema, and silently multiplies every dollar figure the
project reports by ten. Nothing else in the repo would notice.

**3. A secondary source was wrong and the AWS docs settled it.** A search result asserted that
cross-region inference *"adds approximately 10% to the base pricing"*, which would matter — this project
calls Haiku through the `us.` geo profile on every request. The AWS documentation is explicit that it
does not: *"The price for using an inference profile is calculated based on the price of the model in the
Region from which you call the inference profile."* No surcharge, no routing charge. **The finding is
recorded in the price file itself** so nobody re-derives it from the same bad blog next year. This is the
`.claude/rules` "verify against the source, not the summary" habit paying for itself in fifteen minutes.

**4. The `_`-prefixed metadata key worked by accident and now works by design.** JSON has no comments, so
the file carries its own provenance — where the numbers came from, the date, and finding 3 — in a
`_provenance` key. That parsed cleanly *before* any code changed, by falling through the `isinstance`
check in `load_prices`. Working by luck is not the same as working, and the next person to tighten that
parser would have deleted the provenance without a test to stop them. `load_prices` now has an explicit
branch and a comment saying why, and `test_metadata_keys_are_not_read_as_prices` locks it.

**5. A Terraform description was one deploy away from the phase 6 step 10 failure.** `variables.tf`
said *"the default is empty on purpose... so this variable exists to make the silence deliberate"* — true
when written, and about to become a standing instruction that the deploy says nothing about dollars, on
the day CI started setting it. That is exactly the shape of the `169 disjoint components` defect: **a
stale rule outlives the stale sentences it produces, and it is invisible to a grep for the thing it
protects.** Amended in place with a dated note, keeping the original paragraph because it is still true
of the default.

**6. These are LIST prices, and the file says so.** Batch inference is 50% off and prompt caching
discounts cached input; this project uses neither today, so every dollar figure it now reports is an
**upper bound**, not an estimate. That is the right direction to be wrong in, and it is written down
rather than assumed.

#### 0.1 Confirmed by a real billable run, 2026-09-07 — DoD #8 is measured, not predicted

`make eval-live ARGS='--cases 1'`, run by hand in a real terminal because `confirm_spend` layer 2 refuses
a non-TTY and there is deliberately no bypass. Result `20260907T150448Z-bedrock`, one case,
`gold_v0_1_001`, artifact 0.7.1.

**The line this step existed to produce:** `cost      ~$0.02 at the configured price`, where every
billable run since phase 3 had printed *"not shown: no price configured for this model in
MYCELIUM_TOKEN_PRICES"*.

**Three things measured on the way through, none of them predicted here.**

1. **The estimator runs about 2x conservative, in the safe direction.** It projected ~7 requests and
   15,100 tokens; the run issued **5 requests and 7,245 tokens** (6,852 in, 393 out), which prices at
   **$0.008817** against the **~$0.02** shown at the prompt. A spend gate that over-estimates is correct
   by design — the number a person approves should be the ceiling, not the hope — and this is the first
   time the two have been comparable, because before today the estimate had no dollar figure at all.
2. **$0.008817 for one query lands on the measured average again.** `.claude/rules/aws-and-cost.md`
   records ~$0.009 from 2026-08-24 at a corpus a third this size. Third independent agreement on the
   price table, this one from a live run rather than arithmetic.
3. **The `_ungateable` message fired and was CORRECT here**, which sharpens item 10. It said *"this run
   scored 1 cases and the baseline was measured over 41. A subset is not a smaller version of the same
   measurement"* — and 1 of 41 genuinely **is** a subset, so the sentence is right in this case and wrong
   only for the case step 6 fixes: a **complete** run of a **larger** set. The wording defect is narrower
   than "the message is wrong", and step 6 must not break the case that works.

**Still not verified, and it belongs to the release rather than to this step.** The deployed Lambda picks
this up only on the **next** `terraform apply`, so the live function still has an empty
`MYCELIUM_TOKEN_PRICES` and still reports token counts without dollars — the working degraded state, not
a regression. `api/telemetry.py`'s own path (the EMF `EstimatedCostUsd` record) is unit-tested with
configured prices in `tests/test_telemetry.py:106` and `:150`, including the case where one role has a
price and the other does not, so what remains unproven is only Terraform's `TF_VAR_token_prices` reaching
the function's environment. That is confirmed at the deploy, and a local `make dev-live` would not
confirm it — it exercises a third configuration (local env into uvicorn), not the deployed one.

#### 0.2 In plain English

The system already counted exactly how many words it sent to and received from the AI model on every
question, and wrote those counts down. What it could not do was turn them into money, because nobody had
told it what a word costs — and it deliberately refuses to guess, since a made-up price does not look
broken, it looks like a real number. So every run said "cost not shown."

This step told it the prices. They live in one small file that both the local test runs and the deployed
website read, so the two can never drift apart, and the file records where the numbers came from and the
day they were looked up, because prices change and a number without a date is a trap. There is a test
that catches the specific mistake of typing a price ten times too large, by checking that the new table
reproduces a cost figure the project measured back in August, before the table existed.

*(These paragraphs accumulate per step and are consolidated into the right `docs/*-explained.md` at
step 8. A new explainer doc is not created mid-phase.)*

### Step 1 — Widen the `GraphStore` seam

The prerequisite for items 1 and 4, done once so it is reviewed once.

- Add to the `GraphStore` protocol in `graph/store.py`: a contested-pairs read and a resource-to-node
  reverse lookup. Names decided at build time against the existing naming style; the protocol reads in
  the language of the claim, not the storage.
- Implement on `InMemoryGraphStore` by delegating to what already exists (`graph/corroboration.py`) plus
  a resource index built at load. **No recomputation per call** — `contested_pairs` walks all 5,066 edges
  and a tool may call it repeatedly.
- Update every other implementation and test fake. `grep -l "GraphStore"` names 20 files today; the ones
  that structurally implement it are the ones step 1 has to touch, and the count goes in the as-built.
- **Break each new method once**, watch a test fail, restore it. `.claude/rules` and
  `tests/test_thresholds.py` both require this and it is cheap here.

**Done means:** the protocol exposes both reads, `mypy` is clean over the package, every implementation
satisfies it, and no file in `agent/` has changed yet.

### Step 2 — Item 3: the refusal's missing third branch

Distinguish, in the text a user reads, *this run gathered nothing* from *the corpus holds nothing for this
subject*, using the deterministic `neighbors` check from §5. Both strings stay axis-neutral — the v0.4.0
lesson at `loop.py:766-768` still applies, and neither may say "genre".

**Done means:** three distinguishable refusal reasons with a test for each, and DoD #3 satisfied.

### Step 3 — Item 2: diagnose `gold_v0_1_020`, then decide

**Diagnosis first and separately. This step does not get to guess, and it does not get to tune.** Read the
five baseline transcripts in `eval/transcripts/` and `noise_floor.json` for what the model actually did on
the 7-node path, then state the cause.

**The decision (scope §5.3) is his**, and the honest outcomes are asymmetric: if the cause is a code
defect, fix it and add the case to the traversal gate. If the cause is the model declining a long path,
**the outcome is a written finding and a case that stays excluded** — not a prompt edited until the number
moves. Fitting a prompt to a gold case is the day the gold set stops measuring anything, and this plan
names that here so the temptation is on the record before the diagnosis exists.

**Done means:** DoD #2 — the case passes, or a written diagnosis names the cause and records the decision.

### Step 4 — Item 1: `contested` reachable in an answer, and item 4

The keystone. **Decision 5.1, closed 2026-09-07: a distinct SSE event.** The two options not taken are
recorded here, because the reason C was rejected is the reason this step is dangerous.

- **Rejected — a field on the `Done` envelope.** Two problems. It arrives **last**, after every prose
  token, so a reader finishes the narration and only then learns the sources disagreed; the SPA already
  refuses that shape for refusals at `web/src/useLineageRun.ts:68-70`, committing the outcome at frame
  time *"so the panel can commit to the refusal presentation without a flash of empty answer."* And
  `Done` is the **measurement** envelope — `api/app.py:108` special-cases it to emit CloudWatch cost
  metrics and `eval.metrics.plan_adherence` reads it. A fact about music history does not belong there.
- **Rejected — a property on the affected claims.** The cheapest to render and structurally wrong twice.
  A contested pair is **two** edges in opposite directions; a traversal walks one, so typically only one
  of the two is in the approved claim set, and stamping the marker on that claim makes it assert
  something about an edge that is not in the answer. It also seats `contested` and `verification` in the
  same row of the same list, which is the collapse this repo has already corrected three files for, and
  `agent/claims.py:26-28` already says a `contested` field on a `Claim` *"would still be the wrong
  shape."*
- **The accepted option's honest cost:** additive frames are not free. `SPEC.md` 5.3 fixes four frame
  names and the rest are additive, and every additive frame is one more thing the SPA, the three recorded
  `.sse` fixtures and the eval transcripts must handle. §8 fences this phase at exactly one new frame.

- A **distinct event** from the loop, carrying both directions and both sources, picking no winner.
  Not a field on `Claim`, and not a property attached to approved claims.
- The API cost of a new event type is **one line** in `EVENT_NAMES` (`api/app.py:62`). `render` is generic
  over `asdict`, and `app.py:59-61` says so explicitly: `plan` cost exactly one line, and *"a frame type
  that needed a handler here would mean `api` had grown logic."* `ContestedPair` is a frozen dataclass of
  two `Edge` dataclasses, so `asdict` walks it unaided.
- **Frontend, bounded to what item 1 forces** and nothing else: a frame type in `web/src/types.ts`, a case
  in `web/src/useLineageRun.ts`, one display, one recorded `.sse` fixture alongside the three that exist.
- **Item 4 in the same step**, because it is the same seam and the same review: `ResolveSource` resolves a
  DBpedia resource URI through step 1's reverse lookup, and the standing comment at `agent/tools.py:588`
  is replaced by the capability it describes as missing.

**The risk this step carries is the one the scope doc calls known risk 1**, and it is real: this is the
first time `contested` and `verification` appear in the same response. A corroborated `PROSE_AUTO` edge is
not a `HAND` edge, `contested` is a property of a **pair**, and a UI that shows one number where there are
two has reintroduced a defect this repo has already corrected in three files. A test asserts the two
fields are separately represented.

**Done means:** DoD #1 and #4. `checks_disagree` is still declared in `agent/claims.py:UNREACHABLE`, still
never proposed by the model, and the copy from phase 6 step 10 saying contested is corpus-level-only is
updated **the day this lands** (DoD #9), not at step 8.

### Step 5 — Tier 2: the frozen datasets

Items 5, 6 and 7, unblocked by step 4.

- **The two contested gold cases**, authored against the exact pairs measured in §2.
- **One `ambiguous`-branch case**, against `big band` / `big band music`.
- **Six `dbpedia_only` gold cases.** The largest single piece of work in the phase and real
  hand-authoring: each needs an independent, non-Wikidata citation. **Decision 5.4, settled 2026-09-07 at
  six** — five were proposed on 2026-09-04, and six was chosen over five for margin above the slicer's
  n<5 floor rather than for a round total. Measured today, gold holds **4** `dbpedia_only` subjects; six
  more takes it to **10 of 38, 26%**, against `dbpedia_only` being roughly half of corpus genres. Still
  under-sampled, and now reported as a rate rather than a count.
- The 66 existing hand-authored claims are **not** re-authored. Item 7 adds.

**Arithmetic, because it is easy to get wrong and it drives step 7.** All nine additions are **gold**
cases in `gold_v0_1.json` — the contested and ambiguous cases are not a separate set. Gold goes
**29 -> 38**, and the live set goes **45 -> 54**. The adversarial set stays at 18 and this phase adds
nothing to it.

**Done means:** DoD #5 — the datasets exercise contested, the `ambiguous` branch, and `dbpedia_only` at
n>=5 so the slicer reports a rate rather than a count.

### Step 6 — Item 10, and the contested-metric decision

Trivial and cheap, done while the datasets settle.

- **Correct the `_ungateable` message** at `eval/thresholds.py:492`. It says *"A subset is not a smaller
  version of the same measurement"* and fires equally for a run of a **larger** set. 45 is not a subset of
  41. The guard is right; the sentence describes a case that did not happen.
- **Decide whether a contested metric joins the tier 1 catalog** (decision 5.2, his). Note the denominator
  before proposing a rate: 2,202 of 2,284 influence edges are single-source, so a contested rate over all
  edges measures DBpedia's coverage far more than it measures disagreement.

### Step 7 — Tier 3: measure the floor, then write the gates

**Nothing here starts until step 5's case count stops moving.** This is arithmetic, not preference: every
case added moves `case_count` and invalidates a set measured before it.

Five identical live runs at the pinned artifact, the noise floor re-measured from them (the current one is
stale at v0.5.0), bounds written **from the floor** with their observations recorded beside them, in the
pattern `thresholds.json` already uses. **The existing set is not edited to fit.** Then item 9: the
`xfail` at `tests/test_thresholds.py:143` goes away because the invariant holds — it will XPASS and turn
the build red on its own, which is the marker doing its job.

**The trap named in `.claude/rules/evals.md` applies directly here** and it applies to this exact metric:
`traversal_recall` measured a 0.0pp spread last time and that read as a rock-solid number when it was one
case failing identically every run. A zero-variance number is a reason to ask what is constant.

**Done means:** DoD #6 and #7 — a live run at the pinned artifact is gated by a set that was measured, and
the xfail is gone because the invariant holds rather than because a test was deleted.

### Step 8 — Copy, docs, release

The sweep, with the phase 6 step 10 finding applied: **a stale rule outlives the stale sentences it
produces**, so the sweep reads instruction files first, not last. `CLAUDE.md`, the three `.claude/rules/`
files, `README.md`, `SPEC.md`, `docs/spa-explained.md`, `KNOWN-GAPS.md`, and the ROADMAP spine.

**One correction carried into this sweep from 2026-09-07.** `.claude/rules/evals.md` records the gold set
as **"25 cases / 67 claims"** from the 2026-08-24 as-built. Measured today it is **29 cases / 66 claims**,
and after step 5 it is **38**. The case count moved with the phase 6 refusal rebuild; **where the 67th
claim went has not been chased**, and it plausibly tracks `c697712` honouring hand-rejected edges — the
same commit that moved 2,285 influence edges to 2,284 — but that is a guess and the sweep verifies it
rather than repeating it.

DoD #9 and #10. The release itself is a separate decision, as it was in phase 6.

**The plain-English write-up is written as the phase goes, not here at the end** — one short jargon-free
paragraph per step, added when the step lands. It is the cold-articulation rep and it is much harder to
reconstruct in December.

## 7. Decisions this plan does not make

Six from the scope doc §5. This plan carries a recommendation on two and leaves four open.

| # | decision | this plan's position |
|---|---|---|
| 5.1 | Shape of `contested` in a response | **CLOSED 2026-09-07: a distinct SSE event.** The two rejected options and why are recorded in §6 step 4. |
| 5.2 | Contested metric — gated, tracked, or absent | Open. Decided at step 6, with the denominator problem stated first. |
| 5.3 | Is `gold_v0_1_020` fixable | Open by construction. Step 3 diagnoses; the decision follows the diagnosis and not the reverse. |
| 5.4 | How many `dbpedia_only` gold cases | **CLOSED 2026-09-07: six.** Gold ends at 38 cases, the live set at 54. Chosen for margin above the n<5 floor, not for a round total. |
| 5.5 | Held-out set at the freeze | **Not made here, and no step depends on it.** Run count is 1. Default remains **do not run**. His alone, at the freeze. |
| 5.6 | Do `-bedrock.json` runs stay gitignored | Open. Step 7 creates five more of them, so it is decided **before** step 7 runs, not after. |

## 8. Not in this phase

The scope doc §4 fence stands in full and is not restated. Two additions this plan makes:

- **No speculative protocol methods.** Step 1 adds exactly what items 1 and 4 need. "While we are in the
  seam anyway" is the same sentence as "while we are in the agent anyway", one layer down.
- **No new SSE frame beyond the one item 1 forces.** `SPEC.md` 5.3 fixes four frame names and the rest are
  additive; additive is not free, because every frame is a thing the SPA and three fixtures must handle.

## 9. One-way doors touched

| door | touched? | how it stays satisfied |
|---|---|---|
| 1. Claims first, prose second | **Yes** | `contested` is not a claim and does not enter the claim set. Prose still generates from approved claims only. A contested notice is a separate statement about a pair, and it can say nothing the gate did not already approve about the edges involved. |
| 2. Provenance on every edge | No | No ingestion. The pin does not move. |
| 3. Validated graph semantics | No | P279 still not ingested. |
| 4. Agent-to-data tool contract | **Yes** | Step 1 widens the data seam; no tool dispatch and no loop edit. Item 4 makes an existing tool able to do what its docstring says it cannot. |
| 5. Everything in Terraform | No | No new AWS resource. Item 12 is configuration on paths that already read it. |
| 6. Package boundaries | **Yes, and watch it** | Step 1 is `graph/`, step 4 is `agent/` + a bounded `web/`. The one to watch is `contested` logic leaking into `agent/` — it is derived in `graph/` and read by `agent/`, never re-derived there. |
| 7. LLM provider seam | No | Unchanged. |
| 8. Lambda container image | No | Unchanged. |
| 9. Response streaming | **Yes** | A new event type flows through the existing stream. No request/response path is added. |

## 10. Files expected to change, by path

Predicted, not exhaustive; the as-built records what actually moved.

- `src/musical_mycelium/graph/store.py` — protocol, step 1
- `src/musical_mycelium/graph/memory.py` — implementation and the resource index, step 1
- `src/musical_mycelium/agent/loop.py` — refusal branch (step 2), contested event (step 4)
- `src/musical_mycelium/agent/tools.py` — `ResolveSource`, step 4
- `src/musical_mycelium/api/app.py` — one line in `EVENT_NAMES`, step 4
- `src/musical_mycelium/eval/thresholds.py` — `_ungateable` message, step 6
- `src/musical_mycelium/eval/thresholds.json`, `eval/noise_floor.json` — step 7, written from measurement
- `src/musical_mycelium/eval/datasets/gold_v0_1.json` — step 5, additive only
- `tests/test_thresholds.py` — the xfail marker, step 7
- `web/src/types.ts`, `web/src/useLineageRun.ts`, one component, one new `src/fixtures/*.sse` — step 4
- `docs/KNOWN-GAPS.md`, `docs/ROADMAP.md`, `CLAUDE.md`, `.claude/rules/*.md`, `README.md`, `docs/SPEC.md`,
  `docs/spa-explained.md` — step 8, and the contested copy at step 4 rather than step 8

## 11. Testing, and which eval metrics apply

- **Unit:** every new protocol method, the third refusal branch, the contested event's shape, the DBpedia
  reverse lookup, and the two-fields-never-collapsed assertion from step 4.
- **Every new lock gets broken once**, watched to fail, and restored.
- **Scripted tier 1 stays green on every commit** — 3 passed / 0 failed / 2 N/A is the floor, and N/A is
  never counted as a pass.
- **Metric unit tests**, if step 6 adds a contested metric: synthetic inputs where the answer is known by
  construction, including the vacuous-truth guard.
- **Live tier 1** is step 7 and only step 7, plus two-cent wiring checks during development.
- **The held-out set is not run, not opened, not re-sealed, not drawn again.** `.claude/rules/heldout-set.md`
  governs in full.

## 12. Cost, and the guardrail

Scope doc §9 stands in shape and **rises with decision 5.4**. It priced step 7 at ~$2.50 for five runs of
**45** cases at ~$0.42 each; step 5 now takes the live set to **54**, so the same five runs are roughly
**$0.50 each, about $3.00**. Phase total stays **under $5** with wiring checks and a judged tier 2 at the
freeze. The scope doc's ~$0.42 figure is a record of 2026-09-06 and is not wrong; it is measured against a
smaller set.

**Wall clock is the real cost of step 7, not dollars** — roughly three hours of sequential runs at the
10 RPM Bedrock ceiling for 45 cases, and **nine more cases per run adds to that**, which cannot be
parallelised away because RPM is the binding constraint.

Guardrail unchanged: every billable target stays behind `confirm_spend`, and the deny-list gap phase 6
step 9 found stays closed. **Step 0 moves item 12 ahead of every billable run so the money the phase spends
is recorded in dollars**, which is the whole reason it moved.

## 13. Genuinely uncertain

Named as uncertain rather than smoothed over.

1. **Whether `gold_v0_1_020` is a code defect at all.** 7 of 7 identical failures reads like determinism,
   and determinism is equally consistent with a model reliably declining a 7-node path. The plan is built
   so that "unfixable, recorded" is a clean outcome and not a failure of the phase.
2. **How much of step 1 the other `GraphStore` implementations cost.** Twenty files mention the protocol;
   how many structurally implement it is not yet counted, and the fakes in `tests/` are the uncertainty.
3. **Whether two contested pairs are enough to author two useful gold cases.** Both are real disagreements,
   and both are also thin and peripheral — *New Mexico music* and *electroclash* are not central subjects.
   A case built on a thin pair may measure the plumbing rather than the behavior. If that turns out true,
   say it in the case's own notes rather than pretending otherwise.
4. **Whether six `dbpedia_only` cases are findable with independent non-Wikidata citations.** The
   requirement is real and the sourcing is hand work, and the count may prove to be bounded by what can be
   honestly cited rather than by what was chosen. **If the sixth cannot be sourced without reaching, the
   right outcome is five cases and a written note saying so** — not a sixth case carrying a weak citation.
   A gold set is worth exactly what its citations are worth.
5. **Whether the five step 7 runs produce a floor stable enough to write bounds from.** The corpus tripled
   since the last floor. If the spread comes back wide, the honest outcome is a wider gate or a tracked
   metric, not a tighter one.
