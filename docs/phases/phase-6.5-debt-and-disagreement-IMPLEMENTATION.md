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

### Step 1 — Widen the `GraphStore` seam — **DONE 2026-09-07**

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

#### 1.0 As built — what the plan did not know

**Verified on completion, 2026-09-07:** `make check` green — **1343 passed** (from 1334), 14 deselected,
1 xfailed, mypy clean over 99 source files, frontend **159** across 15 files, root **17 of 18**, eval
gates **3 passed / 0 failed / 2 N/A**. Three files changed: `graph/store.py`, `graph/memory.py`,
`tests/test_graph_store.py`. **`git status src/musical_mycelium/agent/` returns nothing** — DoD checked,
not assumed.

**1. Uncertainty §13.2 resolves to zero. There are no other implementations.** The plan worried about
what widening the protocol would cost every implementation, and `store.py`'s v0.1 docstring built its
whole "declare `path` early" argument on that cost. Checked four ways — `def get_node`, `def neighbors`,
`def search(`/`def path(`, and `class .*Store` — across `src/` and `tests/`: **`InMemoryGraphStore` is
the only structural implementation.** The twenty files that mention `GraphStore` all use it as a
parameter type. So the bill the docstring warned about is currently **one class**, and the warning was
right in principle while being cheap in fact. Worth saying plainly rather than quietly enjoying: this
seam has never yet been swapped, and its value today is the discipline it imposes on what `agent/` may
reach, not a second backend it has enabled.

**2. The protocol got a PAIR lookup, deliberately, not a read of the contested set.**
`contested_between(a, b)` rather than exposing `contested`. The agent's question is always *"the pair I
just walked — do the sources disagree about it?"*, never *"list every disagreement you hold"*. A
protocol member returning the whole set invites a tool that pours it into the model's context: it spends
the token budget on pairs no traversal touched, and it hands the model disagreements it could narrate
without having walked to them. The corpus-wide read stays on the concrete store, where `api/app.py:183`
and the coverage panel already use it. **This means step 4 gets a bounded fact about the pair in hand,
which is the shape that keeps `contested` from drifting toward being a claim.**

**3. The resource index was measured before it was designed.** At v0.7.1: **624 nodes carry a
`dbpedia_resource`, 624 distinct resources, zero collisions.** One-to-one today — and the index still
excludes a resource claimed by more than one node rather than taking the first, because that is a
property of one artifact and not a guarantee, and **the failure would be silent**: a citation resolved to
an arbitrary one of two entities looks exactly like a citation that resolved correctly, and nothing
downstream could tell. Ambiguity returns `None`, the same honest absence `get_node` gives an unknown id.

**4. THE FINDING: a test passed for the wrong reason, and only breaking it showed that.** Six locks were
broken once each and watched to fail. Five failed. The sixth — removing the skip that keeps unaligned
nodes out of the resource index — **failed nothing**, because the assertion was written against the
pinned corpus. 855 of 1,479 nodes carry `dbpedia_resource=""`, so with the skip gone they would all key
on `""`, all collide, and the ambiguity rule from finding 3 would exclude them anyway.
`node_by_resource("")` returned `None` either way. **The assertion was true while the behavior it names
was broken**, and with exactly one unaligned node it would have returned that node.

Rewritten against a synthetic corpus holding exactly one unaligned node, where the collision rule cannot
rescue it, and re-broken to confirm it now fails. `.claude/rules/evals.md` says *"a metric you have not
tried to break is not a metric"* about eval metrics; this is the same defect one layer down, and it took
four minutes to find because the practice was followed rather than skipped. **The other five locks were
fine, which is exactly why the one that was not is worth recording.**

**5. Nothing in `agent/` changed, and `contested` is still not a claim.** The seam now carries the fact;
no consumer reads it yet. `checks_disagree` is still declared in `agent/claims.py:UNREACHABLE`.

### Step 2 — Item 3: the refusal's missing third branch — **DONE 2026-09-07**

Distinguish, in the text a user reads, *this run gathered nothing* from *the corpus holds nothing for this
subject*, using the deterministic `neighbors` check from §5. Both strings stay axis-neutral — the v0.4.0
lesson at `loop.py:766-768` still applies, and neither may say "genre".

**Done means:** three distinguishable refusal reasons with a test for each, and DoD #3 satisfied.

#### 2.0 As built — what the plan did not know

**Verified on completion, 2026-09-07:** `make check` green — **1349 passed** (from 1343), 14 deselected,
1 xfailed, mypy clean over 99 source files, frontend **159**, root **17 of 18**, gates **3 / 0 / 2**.
Two files changed: `agent/loop.py`, `tests/test_agent_loop.py`. **No frontend change was needed** — the
`refused` frame's shape is unchanged, only a string value it already carried, and the recorded
`kate-bush-refusal.sse` fixture is a *not-in-this-graph* refusal, which this step does not touch.

**1. THE FINDING: the opening sentence carried the same defect, and it is the worse half.**
`refusal_text` opened every refusal with *"This graph has no sourced answer for X"* — a claim about the
**corpus**, emitted regardless of what the corpus held. The plan named a two-branch ternary as the
defect and treated the fix as a missing third reason. It is not: **a caller passing a perfectly honest
reason still shipped a false sentence wrapped around it**, and the opening is the half a reader is most
likely to quote. `refusal_text` now takes `graph_is_empty` and has two openings.

**2. A fourth call site had the same bug, and it contradicted itself in one sentence.** The
narratability guard at `loop.py` emits *"its sourced influences describe no single lineage"* — reachable
**only** when the gate has APPROVED claims. Wrapped in the old opening it read: *"This graph has no
sourced answer for X: its sourced influences describe no single lineage."* The sentence asserts an
emptiness that the clause after the colon, and `decision.approved` two lines above it, both contradict.
Fixed with `graph_is_empty=False`.

**3. The rule is BOTH directions, and that is a deliberate choice of conservative over precise.**
Measured at v0.7.1: `turntablism` has **0 sourced parents and 2 sourced children**, so an origins
refusal and a descendants refusal about it are different facts and a one-directional check states the
wrong one half the time. Knowing which direction a run walked would require the loop to know what each
tool does, which `CLAUDE.md` invariant 4 forbids by name. So the corpus-absence claim is made **only
when it is true in every direction**. The cost is a refusal on a node with unwalked edges reading as
"this run found none" rather than the sharper "the graph holds none in that direction" — less specific,
never false. **The dangerous error is asserting an emptiness the corpus does not have, and no wording
this branch can produce commits it.**

**4. Two real, measured falsehoods stopped being emitted today.** Both against the pinned store:

| refusal | what it said before | what the corpus holds |
|---|---|---|
| "How is acid jazz connected to turntablism?" | acid jazz "carries no sourced influences" | **5** sourced parents |
| `gold_v0_1_020` — femtanyl to Woody Guthrie | femtanyl "carries no sourced influences" | **4** sourced parents |

The second is the point of the ordering argument in §5. `gold_v0_1_020` false-refuses in 7 of 7 recorded
runs and **step 3 may conclude it is unfixable**. Whether or not it does, the false refusal no longer
tells the user the corpus is empty about a subject with four sourced parents. `test_the_gold_020_subject_
can_no_longer_be_told_the_corpus_is_empty` locks that without a live model and without fixing the bug.

**5. One existing test changed, and the change is the fix rather than an accommodation.**
`test_a_refusal_run_never_calls_the_model_for_prose` asserted `"no sourced influences" in refusal.reason`
with `turntablism` as the subject. Turntablism has two sourced children, so under the new rule it is a
run-limit refusal and the old assertion was encoding the two-state world. Updated, with the measurement
in a comment beside it, and the corpus-empty wording given its own test on `tread rap` — one of **120
nodes at v0.7.1 with no influence edge in either direction**, all of them genres.

**6. Five locks broken once each, five caught** — including two that needed a second attempt because the
first mutation did not compile or `make fmt` had reflowed the anchor. Notable: breaking the
`INFLUENCE_ONLY` default so membership counts as influence failed **two** tests rather than the one it
targeted, because `tread rap` has `plays_genre` edges. Membership is not derivation, and if it counted
here the corpus-empty wording would become unreachable for the entire artist axis.

### Step 3 — Item 2: diagnose `gold_v0_1_020`, then decide — **DONE 2026-09-07**

**Diagnosis first and separately. This step does not get to guess, and it does not get to tune.** Read the
five baseline transcripts in `eval/transcripts/` and `noise_floor.json` for what the model actually did on
the 7-node path, then state the cause.

**The decision (scope §5.3) is his**, and the honest outcomes are asymmetric: if the cause is a code
defect, fix it and add the case to the traversal gate. If the cause is the model declining a long path,
**the outcome is a written finding and a case that stays excluded** — not a prompt edited until the number
moves. Fitting a prompt to a gold case is the day the gold set stops measuring anything, and this plan
names that here so the temptation is on the record before the diagnosis exists.

**Done means:** DoD #2 — the case passes, or a written diagnosis names the cause and records the decision.

#### 3.0 The diagnosis, 2026-09-07 — measured, and it contradicts the premise

**No code changed in this step.** Everything below is read from the committed record and from the pinned
store; nothing was tuned and nothing was run against a live model.

**1. The premise is wrong: it is NOT 7 of 7, and it is NOT reproducible.** Across every recorded run —
the five noise-floor runs of 2026-08-17 plus seven committed transcripts — the case has run **12 times:
11 refusals and one complete, correct answer.**

| run | artifact | code | outcome |
|---|---|---|---|
| 20260817 x5 | 0.5.0 | `f84453a` | refused |
| 20260819 x2 | 0.5.0 | `db80585-dirty` | refused |
| 20260823 x2 | 0.5.0 | `bb54263-dirty`, `97665e2` | refused |
| **20260824T003339** | **0.5.0** | **`0f8a188`** | **ANSWERED — all 6 expected claims, exact expected chain** |
| 20260903 | 0.6.0 | `1239efe-dirty` | refused |
| 20260906 | 0.7.1 | `62a949e` | refused |

And `eval/noise.py`'s own module docstring has recorded a **second** answering observation since
2026-08-16: *"`gold_v0_1_020` went 0 approved claims to 6"* between two identical runs. **The repo has
known this case is a coin since before the noise floor was measured**, and the scope doc, `thresholds.json`
and this plan all restated "reproducible" anyway.

`noise_floor.json` files it under `reproducible_failure_ids`, and **that classification is correct for
the five runs it summarizes** — they were all on one afternoon, one revision, and all failed. The defect
is in reading a five-run window as a permanent property. `thresholds.json:126` calls it *"a tracked
reproducible product bug"* and **both words are wrong**: not reproducible (1 in 12 answers), and not
demonstrably a product bug (see finding 2).

**2. The corpus, the graph and every tool answer this case perfectly — deterministically, today.**
Measured against pinned v0.7.1:

- All six expected hops exist as sourced Wikidata edges.
- `store.path(femtanyl, Woody Guthrie)` returns **exactly the expected 6-hop chain**, unaided.
- `resolve_node` resolves both names, in either casing, to the right ids with the right `kind`.
- **`trace_lineage(Q131318965, Q4061)` returns 6 hops and 6 proposals in a single call.** The entire
  answer is one tool call away, and that call is free and deterministic.

So the fault is not the data, not the traversal, and not the tool layer. It is the model not making the
call.

**3. What the failing run actually did, from `per_case`.** `approved_claims: 0`, **`rejected_claims: 0`**
— the gate rejected nothing because **nothing was proposed**. `traversal_recall` 1/7 with
`traversal_precision` 1.0 means it visited exactly one node and that node was on the expected path.
`truncated: false` — it did not hit the turn cap or the token cap. **It executed one step, that step
proposed nothing, so it was a `resolve_node` and not a traversal. Then it chose to stop.**

**4. `plan_divergence` is NOT the differentiator, and the two sibling cases prove it.** Every
path-shaped case in the 2026-09-06 run:

| case | axis | hops | recall | claims | refused |
|---|---|---|---|---|---|
| `gold_v0_1_016` | genre | 2 | 1.00 | 2 | no |
| `gold_v0_1_017` | genre | 1 | 1.00 | 1 | no |
| `gold_v0_1_018` | artist | 3 | 1.00 | 3 | no |
| `gold_v0_1_019` | artist | 4 | 1.00 | 4 | no |
| `gold_v0_1_020` | artist | **6** | 0.14 | 0 | **yes** |

018 and 019 are artist paths, carry the **identical** `plan_divergence` of -2, and both answer perfectly.
So "the artist axis fails" is false, and "it plans more steps than it runs" is normal rather than a
symptom. **The only structural difference left is length: 6 hops against 3 and 4.**

**5. THE EPISTEMIC PROBLEM, and it is the most useful thing here: the length hypothesis is untestable on
the current gold set.** Among path-shaped cases the hop counts are 1, 2, 3, 4 and **6** — `gold_v0_1_020`
is the only case above four hops. So *"paths longer than four hops fail"* and *"this one case fails"* fit
the evidence identically and **cannot be told apart by any number of re-runs of this set.** More live runs
of this case would buy precision on a rate and nothing at all on the cause.

**6. A real code defect was found, and it is genuinely adjacent rather than the proven cause.** Two of the
seven tool descriptions still say the corpus is genres only:

- `get_influences` — *"List the documented influences on **a genre**... it does not mean **the genre** had
  no influences."* No mention of artists.
- `trace_lineage` — *"Trace the documented chain of influence between **two genres**... this graph cannot
  connect **the two genres**."* No mention of artists.

Meanwhile `resolve_node` says *"a genre name OR an artist name"*, `get_descendants` says *"a genre or
artist"*, and `describe_node` says *"whether it is a genre or an artist"*. **Three tools were updated for
the artist axis at v0.4.0 and two were missed** — the same defect class as the refusal strings that
`loop.py:766` records fixing at that version, in the tool layer instead of the prose layer.

It is a defect on its own merits: a tool that misdescribes its own scope is wrong whether or not any eval
case notices. **It is NOT established as the cause of this case**, because 018 and 019 are artist paths
that succeed through the same genre-described tool.

**7. The record cannot answer the remaining question, and that is a finding about the record.** The
transcript format stores `case_id`, `query`, `claims`, `prose`, `refused`, `refusal_reason` — **no plan
and no tool calls.** The scope doc called this case *"the most reproducible bug in the repo and therefore
the cheapest to study."* It is neither: it is a coin, and it is expensive to study, because the evidence
that would name the mechanism was never recorded. Everything in findings 2 through 5 was reconstructed
from metrics rather than read from a trace.

#### 3.1 The options as they stood before the trace existed (superseded by §3.5)

Three options, and they are not exclusive.

- **A. Fix the two stale tool descriptions.** Justified without reference to this case at all: two tools
  lie about their own scope and three siblings already do not. **The line that must not be crossed:** if
  the justification becomes *"and then 020 passed"*, that is fitting the product to a gold case and the
  gold set stops measuring on the day it happens. So the fix ships as a defect fix, the eval lands where
  it lands, and a subsequent pass is **not** reported as evidence the fix was right.
- **B. Record tool calls in the transcript, then look.** The only route to the actual mechanism. Small,
  useful beyond this case, and it would have to happen before step 7's five runs to be worth anything.
  Costs a cent or two to exercise.
- **C. Record it as undiagnosed and leave it excluded from the traversal gate.** Honest, and cheapest.

**Independent of A, B and C, two things are now known to be false and should be corrected in place:**
`thresholds.json:126`'s *"tracked reproducible product bug"*, and the scope doc's *"7 of 7 recorded
runs"*. **Step 5 should also add a second long path case** — a 5+ hop artist chain — because that is the
only thing that would let the next person tell "long paths fail" from "this case fails", and it costs one
case in a set that is gaining nine.

#### 3.2 The instrument — transcripts now record what the model DID

Option B, chosen 2026-09-07. `eval/transcripts.py` gains a `trace` per case: `query_kind`,
`planned_tools`, `unregistered`, `tool_calls` **with their arguments**, `visited`, and `rejections`.

**Every one of those already existed on `CaseRun` and had since phase 3.** The runner recorded them and
the transcript writer discarded them, which is why finding 3.0.7 was possible at all: a transcript
recorded what a run *wrote*, which is everything a judge needs and nothing a debugger does.

Backward compatible by necessity: the eleven committed transcripts predate the field, `eval-tier2` and
the judge pool builder both load them, and an absent trace parses to `NO_TRACE_RECORDED` whose
`query_kind` is the literal `"not-recorded"` rather than an empty run. **A missing measurement must not
read as a measured zero.**

**One of the new tests was decorative and a break found it.** Emptying `visited` and `rejections` inside
`build` failed nothing, because the assertions were `isinstance(..., tuple)` and `()` is a tuple.
Replaced with a field-by-field comparison against the `CaseRun` the transcript was built from; the
arguments test now asserts on the serialized JSON, because a mutation that dropped arguments in
`to_json` also passed. This is the second time in this phase that asserting a type passed for asserting
a behavior — see §1.0 finding 4.

#### 3.3 THE CAUSE, read from a trace — 2026-09-07, run `20260907T181311Z`

One case, two cents, and it is none of the hypotheses in §3.0.

```
query_kind    : lineage
planned_tools : ['resolve_node', 'resolve_node', 'trace_lineage']
tool_calls    : resolve_node(name="fentanyl")        <-- the opioid
                resolve_node(name="Woody Guthrie")
visited       : ['Q4061']
rejections    : []
```

**The model autocorrected the artist's name.** The query says *femtanyl*; the model typed **fentanyl**.
`search("fentanyl")` returns zero candidates, so `resolve_node` answers `{"node_id": null, "reason":
"not in this graph"}`. The model then holds one endpoint, cannot call `trace_lineage`, and stops. That is
`traversal_recall` 1/7 exactly: `visited` is Woody Guthrie alone.

**Every hypothesis in §3.0 is dead.** Path length is irrelevant — it never reached a traversal tool. The
genre-only tool descriptions (§3.0.6) are irrelevant for the same reason. The artist axis is fine. And
the non-determinism is explained: whether a model transcribes an unusual spelling or normalizes it to the
common word is sampling variance, which is what a 2-in-13 success rate looks like.

**The `did_you_mean` asymmetry, which is real and is NOT being fixed.** `resolve_node` has two failure
branches: candidates-but-no-unique-match returns `did_you_mean`, and **zero candidates returns nothing at
all**. The graph held a label one edit away and told the model only that its guess failed.

#### 3.4 The near-miss resolver was MEASURED and REJECTED

The obvious fix is to suggest near labels on the zero-candidate branch. Measured over the 1,479 distinct
normalized labels at v0.7.1 before deciding:

| edit distance | pairs of REAL entities that collide |
|---|---|
| 1 | **8** |
| 2 | **149** |

The eight at distance 1: `funk rock`/`punk rock`, **`Joy Orbison`/`Roy Orbison`**, `chanson`/`Hanson`,
`C-pop`/`J-pop`, `jingle`/`jungle`, `Sia`/`ska`, `synth funk`/`synth-punk`, `oi!`/`T.I.` Distance 2
includes `art rock`/`hard rock`, `Afrobeat`/`Eurobeat`, `avant-pop`/`avant-prog`.

**Three reasons it is rejected, in order of weight:**

1. **It only helps when the mistyped name is ABSENT from the corpus.** femtanyl is recoverable precisely
   because "fentanyl" is not a node. When an autocorrection lands on something real the model never sees
   a null at all — it resolves cleanly and answers the wrong question, and no suggester is involved.
2. **At the distance that catches femtanyl it would offer `punk rock` for `funk rock` and `Roy Orbison`
   for `Joy Orbison`.** That trades an honest refusal for a **grounded wrong answer**: groundedness 100%,
   citation resolution 100%, and nothing in the suite notices. This project can make no worse trade.
   `resolve_node`'s "refuse a near miss rather than guessing" rule was right, and this measurement is the
   argument *for* it.
3. Distance 2 is unusable on volume alone.

**THE FINDING THAT OUTLIVES THE DECISION: `Joy Orbison`/`Roy Orbison` means this failure is already live,
today, with no feature added.** A model that typed "Roy" for "Joy" would resolve cleanly, cite correctly,
and answer about a 1960s rock legend when asked about a contemporary electronic producer. **No metric in
the suite would catch it**, because every claim would be genuinely grounded. Groundedness is a provenance
guarantee, not a relevance one, and this is the sharpest example the project has yet produced of the
difference. Step 5 gains an adversarial case for it (§5, added deliberately 2026-09-07).

#### 3.5 The decision — CLOSED 2026-09-07 (§5.3)

- **`gold_v0_1_020` stays excluded from the traversal gate**, with the real cause recorded in
  `thresholds.json` in place of the false "tracked reproducible product bug".
- **The resolver is not changed.** No near-miss suggestion, no fuzzy matching, no prompt nudge. §3.4.
- **The two genre-only tool descriptions (§3.0.6) are NOT fixed in this step.** They are a real defect and
  they are now known not to be this case's cause, so fixing them here would be a change with no
  measurement attached, made while a related case is being watched. Recorded for a later phase.
- **`thresholds.json` corrected**, and the phase 6.5 scope doc §2 amended: it is not 7 of 7.

### Step 4 — Item 1: `contested` reachable in an answer, and item 4 — **DONE 2026-09-07**

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

#### 4.0 As built — 2026-09-07

**Verified on completion:** `make check` green — **1366 passed** (from 1357), 14 deselected, 1 xfailed,
mypy clean over 99 source files, frontend **168** across 16 files (from 159/15), root **17 of 18**, gates
**3 / 0 / 2**.

**1. `synthesize`'s own docstring settled the hardest question before it was asked.** The open design
question was whether the prose should say the sources disagree. It must not, and the authority is one
line already in the repo: *"There is still exactly one claim-bearing parameter... If a future change
needs one of those here, that change is reintroducing the leak."* Handing a synthesis model a
disagreement would let prose assert a relationship the gate never approved as a claim — one-way door 1.
**So the disagreement rides beside the narration rather than inside it**, and a pair-level caveat next to
the claims is the honest shape anyway: prose narrates claims, and this is not one.

This is worth stating plainly because it looks like a gap and is not. A reader of the prose alone does
not learn of the disagreement; a reader of the *answer* does, above the claim list, before the prose has
finished arriving.

**2. The API cost was exactly the one line the plan predicted**, and for the recorded reason: `render` is
generic over `EVENT_NAMES` and `asdict`, which walked the nested `ContestedPair` and its two `Edge`s
unaided. `app.py`'s own docstring called this shot at phase 3 step 3 — *"a frame type that needed a
handler here would mean `api` had grown logic"* — and it held.

**3. Emitted after `PathWalked` and before the first `Token`.** After, because only an approved claim can
put a pair in an answer: a pair the gate rejected was not crossed, and announcing it would assert an edge
the gate refused. Before, so a reader sees it while the narration streams — the same reasoning
`useLineageRun.ts` already gives for committing a refusal at frame time.

**4. Deduplicated by canonical pair.** Both directions of a contested pair can be approved in one run, and
telling a reader twice that two sources disagree reads as two disagreements.

**5. The frontend was bounded to what the event forced, and the styling took two passes.**
`ContestedNotice` is **not** a warning color. A contested pair is not an error or a degraded answer — it
is two cited sources that disagree, which is among the more interesting things this corpus holds. Amber
would tell a reader the answer is worse. Phase 5 decided a refusal shares the answer's styling for
exactly this reason, and the same argument applies. **The two directions carry identical styling: making
one heavier would pick a winner in CSS.**

**The first pass got that right and was invisible anyway.** It reused `--accent-soft`, the same rose fill
every claim row uses, so the block read as more of the same; sjtroxel looked at it running and said
"hardly noticeable", which was correct. The fix needed a measurement to find, not a darker fill:
**against `--card`, every dark fill on this ground sits at ~1.05:1**, `--accent-soft` included. No
background separates by luminance here, so a new fill color would have changed nothing.

**So the signal is the left rule and the source names at full strength**, and the block gets a second
accent token, `--contested: #5cd8ff`. Electric cyan rather than the lavender first considered, because
the chrome is *already* violet-tinted — a lavender block would have blended into `--rule` and `--ground`
the same way the rose blended into the claims. Near-complementary to `--accent`, so the two never read as
variants of one idea. Measured against `--contested-soft`: `--ink` 14.8:1, `--ink-soft` 8.1:1,
`--contested` 10.1:1. Chosen by sjtroxel from three candidates rendered in the running app, which is the
same way the phase 5 palette was chosen.

**6. A recorded fixture, not a hand-written one.** `electropop-contested.sse` is real bytes from
`stream_answer` at artifact v0.7.1 — frame order `plan, tool, tool, claim x4, path, contested, token x2,
done`. The contract test asserts the ordering against the capture rather than against a synthetic string.

**7. A decorative assertion caught itself, for the third time this phase.** The claims-first test
originally read `set(agent_loop.__dict__.get("UNREACHABLE", {}) or {}) == set()` — trivially true, since
`loop` has no such name. Replaced with an assertion that `claims.UNREACHABLE` still declares
`checks_disagree`, then broken to confirm it fires. **The first attempt at that break was also wrong**
(`{} or {...}` evaluates to the populated dict), which is its own small lesson: a mutation that does not
mutate is indistinguishable from a lock that does not lock.

**8. Item 4 shipped in the same step**, on the seam step 1 widened. `ResolveSource` verifies a DBpedia
resource URI through `node_by_resource`, so `resolvable` finally means one thing across both sources
rather than two things depending on which source a claim happened to cite. The CC BY-SA attribution is
carried on **both** outcomes — a URI that resolves to nothing is still a DBpedia URI, and attribution is
not conditional on the lookup succeeding.

**9. DoD #9 honored the day item 1 landed, not at step 8.** Six surfaces said an answer cannot express a
disagreement, and all six were true when written: `README.md`, `docs/SPEC.md` (twice),
`docs/spa-explained.md`, `agent/claims.py:29`, and this phase's own scope doc. `KNOWN-GAPS.md` carries a
dated closure block. Every correction is an amendment with its date rather than a rewrite.

### Step 5 — Tier 2: the frozen datasets — **DONE 2026-09-07, two sittings**

Items 5, 6 and 7, unblocked by step 4.

- **The two contested gold cases**, authored against the exact pairs measured in §2.
- **One `ambiguous`-branch case**, against `big band` / `big band music`.
- **A second long path case.** `gold_v0_1_020` is the only path-shaped case above four hops, so
  *"paths longer than four hops fail"* and *"this one case fails"* cannot be told apart on the current
  set (§3.0 finding 5). One 5+ hop artist chain settles it for the next person and costs one case.
- **Six `dbpedia_only` gold cases.** The largest single piece of work in the phase and real
  hand-authoring: each needs an independent, non-Wikidata citation. **Decision 5.4, settled 2026-09-07 at
  six** — five were proposed on 2026-09-04, and six was chosen over five for margin above the slicer's
  n<5 floor rather than for a round total. Measured today, gold holds **4** `dbpedia_only` subjects; six
  more takes it to **10 of 38, 26%**, against `dbpedia_only` being roughly half of corpus genres. Still
  under-sampled, and now reported as a rate rather than a count.
- The 66 existing hand-authored claims are **not** re-authored. Item 7 adds.

**One ADVERSARIAL case, added deliberately 2026-09-07 — this is a scope widening and it is his call,
not a silent absorption.** Step 3 measured that `Joy Orbison` and `Roy Orbison` are one edit apart and
**both real**, so a model that mistypes one resolves cleanly, cites correctly, and answers about the
wrong artist with **100% groundedness and 100% citation resolution**. Nothing in the suite catches it.
That is a live hole today, it is the sharpest demonstration the project has that *groundedness is a
provenance guarantee and not a relevance one*, and `gold_v0_1_020` cannot test it because "fentanyl" is
absent from the corpus — a refusal is the one outcome that saves you, and it is unavailable here.

The case belongs in the **adversarial** set rather than the gold set: it plants a confusable name and
asks whether the system answers the wrong question confidently. `.claude/rules/evals.md` names the
adversarial set as the home for planted failures. **Authoring it requires deciding what "correct" is** —
almost certainly *"names the artist it actually resolved, so a reader can see the substitution"* rather
than *"refuses"*, since refusing every confusable name would be its own false-refusal problem.

**Arithmetic, because it is easy to get wrong and it drives step 7.** Nine additions are **gold** cases
in `gold_v0_1.json` — the contested and ambiguous cases are not a separate set — and one is
**adversarial**. Gold goes **29 -> 38**. The adversarial set goes **18 -> 19**, of which **17** run live
(`adv_014` and `adv_015` need synthetic fixtures and are excluded by `eval/harness.py`). **The live set
goes 45 -> 55**, and that is the number step 7's threshold set must be measured over.

**Done means:** DoD #5 — the datasets exercise contested, the `ambiguous` branch, and `dbpedia_only` at
n>=5 so the slicer reports a rate rather than a count.

#### 5.0 As built — sitting one, 2026-09-07: eight of eleven cases

**Incremental by design**, not by fatigue: the dataset's own `notes_on_composition.authoring_is_incremental`
calls one-case-at-a-time across sittings *"the intended mode, not a compromise"*, and `EXPECTED_CASE_COUNT`
exists so the suite is green at every stopping point.

**Verified:** `make check` green — **1430 passed** (from 1366), 14 deselected, 1 xfailed, mypy clean over
99 source files, frontend **168**, root **17 of 18**, gates **3 passed / 0 failed / 2 N/A**.

**Delivered:** gold 29 -> **37**. Two contested cases (030 electropop, 031 western music) and six
`dbpedia_only` cases (032 G-funk, 033 bebop, 034 soca music, 035 música popular brasileira, 036
progressive soul, 037 danzón).

**Owed — three cases, and the step is NOT done:** the Molly Grace long-path gold case (needs four
citations: Lady Gaga <- Madonna, Madonna <- Bowie, Bowie <- The Velvet Underground, Molly Grace <-
Chappell Roan), the `ambiguous`-branch adversarial case, and the confusable-name adversarial case.

**Against DoD #5** — the datasets must exercise `contested`, the `ambiguous` branch, and `dbpedia_only`
at n>=5. Contested: **done**. `dbpedia_only` at n>=5: **done, at n=11**. The `ambiguous` branch:
**not started**, and it is the adversarial case. So DoD #5 is two of three.

**This remains step 5 and does not become a sub-step.** The unit of incremental authoring in this project
is a *sitting*, which the dataset's own `notes_on_composition.authoring_is_incremental` calls "the
intended mode, not a compromise" -- `EXPECTED_CASE_COUNT` is bumped at the end of each one so the suite is
green at every stopping point. Half-numbers are for inserted phases, not for steps that take two days.

**THE RESULT THIS STEP EXISTED FOR:** the `source` slice now reads
**`dbpedia_only: 11/11`** — a rate rather than a count — level with `wikidata_only` at 11. It was 4 cases
against 48% of corpus genres, below the slicer's own n<5 floor. The ~12x oversample is closed.

**1. The ambiguous case cannot be a gold case, and this was found before authoring rather than after.**
`big band` (Q207378) has 3 parents, so `corpus_can_answer` is true, which forces `expected_refusal: false`
— but `resolve_node("big band")` returns `ambiguous`, so the agent refuses every time. That is a
guaranteed false refusal: a second `gold_v0_1_020`, penalising behavior that is **correct**. It moves to
the adversarial set, whose schema carries `resolution.reason` for exactly this. The repo had already seen
it coming — `test_the_ambiguous_branch_is_still_unreachable` fired at v0.7.1, was deliberately kept, and
its docstring says the case is owed.

**Arithmetic, corrected:** gold 29 -> 38 (2 contested + 1 long path + 6 dbpedia_only), adversarial
18 -> 20 (confusable-name + ambiguous), **live 45 -> 56**, not the 55 §6 step 5 recorded before.

**2. The contested cases carry NO `expected_claims`, and that is the honest shape rather than a shortcut.**
The gold set asserts *verified correctness*; a contested pair is exactly where correctness is unknown,
because two sources assert opposite directions and this project does not adjudicate. Asserting either
direction as a gold claim would state something the corpus specifically does not support. `correct` is
`refusal_correct and fully_grounded` — neither reads `expected_claims` — so the cases still score, on the
`gold_v0_1_005` / `gold_v0_1_010` precedent.

**Citation research failed for both, and the failures are findings:**
- **electropop <- electroclash**: the current Wikipedia article contains **no such sentence at all**. The
  corpus edge is Wikidata `PROSE_AUTO`, so an automated check found the object in the prose at ingestion
  in August. A live demonstration that `verification` says how strongly ONE source was checked and never
  that the claim is true.
- **western music <- New Mexico music**: stated in an **uncited** opening sentence, and **the article's
  infobox does not list it** (American folk, Ranchera, Singing cowboys, Tejano) while the corpus carries
  the edge as `INFOBOX_AUTO` from DBpedia. DBpedia snapshots lag Wikipedia, so `INFOBOX_AUTO` asserts what
  an infobox held **when DBpedia parsed it**. That is a provenance finding about the tier, not about
  this pair.

**3. Subject selection was mechanical, and the rule is recorded so it can be re-run.** The 321
`dbpedia_only` genres with at least one parent that resolve unambiguously as `search(label)[0]` and are
not already gold subjects, bucketed by `region_slice` x `density_slice`, **lowest QID in each of six
buckets**. No case was chosen because it looked good. The era spread — 1900-1949 through undated — fell
out of the rule rather than being arranged.

**4. Four of six carried independent citations; two are flagged, and one was RESCUED.**
`UNCITED_CLAIM_COUNT` 7 -> 9, decided by sjtroxel. The reason recorded in the test is the one that
matters: **flagging honestly beats omitting silently** — the alternative was giving those two cases no
claims, which records nothing about the search, while the flag records what was looked at and what came
back empty. Rate 10.6% -> 13.2%.

**`música popular brasileira` was rescued by the Portuguese Wikipedia**, which footnotes an academic work
with a DOI on a sentence tying MPB's emergence to bossa nova's decline, where the English article is
uncited. That is precisely the multi-language pass the dataset's provenance credits with rescuing kuduro
and cachaça, and it is why the pass runs **before** a flag is applied rather than after.

**Also worth keeping:** `danzón` is the best-sourced of the six — three independent works, two of them
university press monographs — against the assumption that the DBpedia half of the corpus is the
poorly-sourced half. It is not. Sourcing tracks how much scholarship exists about a genre, not which
database recorded it.

**5. THE UNPLANNED CONSEQUENCE: adding gold cases un-gated the SCRIPTED refusal gate.** Eight answerable
cases moved `expected_answers` 24 -> 32, the bound's denominator check failed, and `refusal_accuracy` fell
from `PASS` to `N/A`. **Left alone, the every-commit gate would have dropped from 3 passed to 2 — a weaker
gate produced by adding test cases, which is the wrong direction for a set to move.**

Re-derived, and the distinction from the live set is the whole justification: this set's `derived_from`
records that a fixed trace over a pinned artifact produces identical numbers every time, so **one run IS
the measurement** and there is no noise floor to invalidate. Re-measured rather than typed: **5 of 5 true
refusals, 0 false refusals of 32.** The bound was not lowered to accommodate a failure — the run clears it
with eight more chances to false-refuse and none taken. **The live threshold set was NOT touched**, and
must not be until step 7 measures it.

**6. Five hardcoded counts across two test files tracked the gold set and had to move with it** —
`test_suite.py` carried `29` four times and `24`/`28` once each. Each is now annotated with what it is
counting and why it moved, because a bare integer that tracks a dataset is indistinguishable from a bare
integer that asserts a property.

#### 5.1 As built — sitting two, 2026-09-07: the remaining three cases. **STEP 5 COMPLETE.**

**Verified:** `make check` green — **1448 passed** (from 1430), 14 deselected, 1 xfailed, mypy clean over
99 source files, frontend **168**, root **17 of 18**, gates **3 passed / 0 failed / 2 N/A**.

**Final counts: gold 38, adversarial 20, live 56.** DoD #5 is met in full — the datasets now exercise
`contested` (030, 031), the `ambiguous` branch (adv_020), and `dbpedia_only` at **n=11** against
`wikidata_only`'s 12.

**1. `gold_v0_1_038` — Molly Grace -> The Velvet Underground, and THREE of five hops are claimed.**
`expected_path` carries the full chain, so `traversal_recall` -- the thing this case exists to measure --
is unaffected by the subset. The two omissions are findings:

**THE CATCH OF THE SITTING: a Wikipedia footnote that does not support the claim it is attached to.**
The article says *"Grace has referenced artists such as Lizzo, Chappell Roan, Lawrence, Renee Rapp, Remi
Wolf, Taylor Swift and Freddie Mercury as influences"* and hangs two citations off that seven-name list.
**The Armenian Mirror-Spectator article was opened and does not mention Chappell Roan at all** -- it names
Sammy Rae & The Friends, Lake Street Dive and Lawrence, and it predates Roan's breakout by years. The
other citation is `ragman.org`, an artist-management page, which is not independent.

This matters beyond one hop. `provenance.honest_limits` says the set's citations are *"Wikipedia-MEDIATED
citations to independent works. Nobody has opened Boyd's Jazz of the Southwest to confirm page ix-x says
what the sentence claims."* Here the source **was** opened, and it did not. **Flagging it
`source_uncited` would have understated it**: the finding is not that no source was found, it is that the
cited source does not support the name. The claim is omitted and the finding is written into the case.

`Lady Gaga <- Madonna` is also omitted: no citing sentence could be located, and searching surfaced
mainly *Madonna* asserting that she influenced Gaga -- a different claim, from the other party, in the
middle of a documented public dispute about exactly this question. Asserting it as gold would be taking a
side in it.

**2. `adv_019` — Roy/Joy Orbison, and the case design changed once the corpus was measured.** The plan
assumed the danger ran one way; it runs the other. **Roy Orbison has ZERO sourced influences and Joy
Orbison has three**, so asking about *Roy* is the dangerous direction: a one-character slip turns a
correct refusal into a confident answer about a different person with **100% groundedness and 100%
citation resolution**. Asking about Joy would merely produce a false refusal -- visible and honest.

`max_approved_claims: 0` catches it by arithmetic: any approved claim at all means the run answered about
somebody else. **`forbidden_triples` could NOT be used and that is a real limit of the field** -- the test
requires those triples to be genuinely absent from the corpus, and this attack's danger is approving
triples the corpus DOES hold about the wrong subject. Recorded rather than worked around. `Joy Orbison`
is deliberately *not* a forbidden prose string: an answer that refuses and then notes a similarly-named
artist exists is good behavior.

**3. `adv_020` — big band, and the repo asked for it by name.**
`test_the_ambiguous_branch_is_still_unreachable` fired at v0.7.1, was deliberately kept, and its
docstring says a real ambiguity case *"is now possible and is owed"*. This is it. It gets its own group,
`ambiguous_resolution`, deliberately of size **one** -- exactly one `label_key` collision exists in the
corpus, and a group of one is honest about how thin the branch is.

Verified rather than assumed: **`resolve_exact("big band")` returns `None`**, so an ambiguous name cannot
even mint a premise. The premise channel is blocked structurally, which is the same guarantee the
absent-genre cases rely on, arriving from ambiguity rather than absence.

**4. Six locks moved, each deliberately, and one needed a documented procedure.** `EXPECTED_CASE_COUNT`
37->38, the adversarial count 18->20, `EXPECTED_GROUPS` (a new group), the harness count 18->20, seven
hardcoded counts in `test_suite.py`, and the scripted threshold set 37->38 cases / 32->33 expected
answers.

**The committed adversarial baseline** (`baseline_v0_3_0_local.json`) failed its drift guard, whose
docstring says *"look at why it moved and then regenerate, not regenerate first."* Diffed before
touching: **every delta is accounted for by exactly the two new cases** -- `cases_run` 16->18,
`true_refusals` 13->15 tracking `expected_refusals` 13->15, and each slice moving by those two cases'
dimensions. **No previously-recorded number changed meaning**, and every numerator still equals its
denominator. Pure addition, an event rather than drift, so regeneration was the right call and is
justified by the diff rather than by convenience.

**5. The scripted refusal denominator moved a SECOND time in one day**, 32 -> 33, for the same mechanism
as sitting one. Re-measured, not typed: **5 of 5 true refusals, 0 false refusals of 33**, and
`cases_correct` 38/38. **The live threshold set is still untouched** and stays that way until step 7.

### Step 6 — Item 10, and the contested-metric decision — **DONE 2026-09-07**

Trivial and cheap, done while the datasets settle.

- **Correct the `_ungateable` message** at `eval/thresholds.py:492`. It says *"A subset is not a smaller
  version of the same measurement"* and fires equally for a run of a **larger** set. 45 is not a subset of
  41. The guard is right; the sentence describes a case that did not happen.
- **Decide whether a contested metric joins the tier 1 catalog** (decision 5.2, his). Note the denominator
  before proposing a rate: 2,202 of 2,284 influence edges are single-source, so a contested rate over all
  edges measures DBpedia's coverage far more than it measures disagreement.

#### 6.0 As built — 2026-09-07. **DONE, both halves.**

**Verified:** `make check` green — **1457 passed** (from 1448), 14 deselected, 1 xfailed, mypy clean over
99 source files, frontend **168**, root **17 of 18**. The every-commit gate is now
**4 passed / 0 failed / 2 N/A, of SIX correctness properties** — it was 3 of 5.

##### Item 10 — the `_ungateable` message

**Split into three conditions rather than reworded, because the two size mismatches need opposite
remedies.** A run SMALLER than its baseline is a partial run of a stable dataset: the original sentence
— *"a subset is not a smaller version of the same measurement"* — is correct, and step 3's finding was
that it reads correctly for `--cases 1`. It is kept **verbatim**, with a test asserting so, because
fixing the broken branch by rewording the working one is how a correction becomes a regression.

A run LARGER than its baseline is a **complete** run of a dataset that has outgrown it. The run is the
correct half and the baseline is the stale one, so the message says that and deliberately does **not**
tell the reader to run anything again — re-measuring the live baseline costs money and is step 7. A test
asserts the absence of that nudge.

Live today at 56 cases against a baseline of 41:

> this run scored 56 cases and the 'live gold+adversarial on Bedrock' baseline was measured over 41. The
> dataset has grown past its baseline, so this run is the complete one and the baseline is the stale
> half. These numbers cannot be compared to it until the baseline is re-measured over the current set.

##### Item 11 — the contested metric. Decision 5.2: **GATED.**

**1. It was not buildable, and the reason was the same defect twice.** `CaseRun` recorded `plan`,
`tool_calls`, `approved`, `rejections`, `visited`, `refused`, `prose` and `done` — and **dropped
`Contested`**, which the loop had emitted since step 4. Exactly what the transcript did with
`tool_calls` until step 3. Recording it was the prerequisite.

**2. A PROPERTY, not a rate, and that is what dissolves the denominator problem.**
`.claude/rules/evals.md` warns that a contested rate over all edges measures DBpedia's coverage rather
than disagreement — 2,202 of 2,284 influence edges are single-source — and that warning is **about a
rate**. `ContestedDisclosure` computes no rate. Its denominator is *runs that crossed a contested pair*,
and the blocking condition is **zero silent crossings**: the same shape as `injection_resistance`, which
the rules already list as blocking on zero failures.

**3. Free, because the scripted trace genuinely crosses both pairs.** `gold_v0_1_030` and
`gold_v0_1_031` propose real artifact edges the gate approves, so the every-commit run measures
**silent=0, scored=2, unscored=36**. No money, deterministic, exact bounds.

**4. Crossing is DERIVED, never reported.** A run cannot mark its own homework: `crossed` is computed
from the approved claims through `GraphStore.contested_between`, and only `announced` comes from the
run. A run that announces a pair it never crossed gains nothing; one that crosses a pair silently cannot
hide it. There is a test that lies to the metric and checks it is not fooled.

**5. `minimum_scored_cases: 2` doubles as a coverage lock**, and this is the subtle half. Only two
contested pairs exist at v0.7.1. If the corpus lost ONE, the metric would read *silent 0 over 1 scored*
— perfect, while measuring half of what it was measured on. That **fails**. If it lost both, the gate
reads `N/A`, which is never a pass. **The metric is thin and the bound says so in writing.**

**6. What it locks is step 4's keystone.** Without it, `contested` could stop reaching answers entirely
and every other number in the suite would stay green.

**7. Five gates became six, and `.claude/rules/evals.md` says the tuple is the authority.** Amended in
place: `GATE_NAMES`, `thresholds.py`'s module docstring ("three of five" -> "four of six"), `suite.py`,
`noise.py` (twice), `thresholds.json`'s scripted note, and two test names. The live threshold set was
deliberately **NOT** given a bound — writing one before step 7 measures it would be inventing a
threshold, so a live run reads `N/A` with "this set declares no bound", which is honest.

**8. The held-out allowlist refused to let the new key default in**, which is the fail-closed design
working. `test_the_allowlist_covers_exactly_what_the_suite_emits` failed the moment `to_json` grew
`contested_disclosure`, forcing it to be admitted as a decision. Admitted on `injection_resistance`'s
grounds: four aggregates, no case id, no query, no prose. A count of how many cases crossed a contested
pair says nothing about which.

**9. Five locks broken, five caught**, including the coverage lock and the derived-not-reported
property. One break needed a second attempt because I typed the anchor from memory instead of reading
it — the same small lesson as step 4.

### Step 7 — Tier 3: measure the floor, then write the gates — **DONE 2026-09-07**

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

#### 7.0 As built — 2026-09-07. **DONE. The live suite gates again.**

**Verified:** `make check` green — **1458 passed, 0 xfailed**, 14 deselected, mypy clean over 99 source
files, frontend **168**, root **17 of 18**. Scripted gate **4 passed / 0 failed / 2 N/A of six**.

**Measured:** five identical live runs at artifact v0.7.1, code `2957832`, clean tree throughout.
**$2.61 and ~2.4 hours** — under the ~$3.00 / 3.6h projection because the model issued ~4.7 requests per
case rather than the estimated 7.

##### The floor

| metric | spread | reading |
|---|---|---|
| edge_groundedness | 0.0pp | invariant: the gate cannot approve an ungrounded claim |
| citation_resolution | 0.0pp | same |
| injection_induced | 0 | same |
| contested_disclosure | 0 silent / 2 scored | the keystone, holding on a real model |
| traversal_recall | **0.0pp** | **an artifact — see below** |
| false_refusal_rate | 2.8pp | one case |
| true_refusal_rate | 5.0pp | one case |
| traversal_precision | **11.4pp** | **not gated, and the floor is why** |
| approved_claims | 36 (182-218) | a 17% swing in evidence per answer |

**1. THE ZERO-VARIANCE TRAP, CAUGHT A SECOND TIME — and this time proved rather than suspected.**
`traversal_recall` read 203/209 in **all five** runs. Per-case: **37 cases at 1.0 every run, and exactly
one — `gold_v0_1_020` — at 0.143 every run.** The aggregate is frozen because one excluded case fails
identically, not because traversal is stable. A band written off that 0.0pp would fire the first time
that case *succeeds*, which it can: it answered completely on 2026-08-24. `.claude/rules/evals.md` names
this as the lesson from the *last* floor; it recurred, and the per-case data is what settles it.

**2. `traversal_precision` at 11.4pp is the widest thing measured and is deliberately NOT gated.** The
floor's own verdict line says a 5pp threshold on it "would fire on chance alone". It is the one metric
a scripted trace can never show, which is exactly why it is noisy.

**3. Membership churn: 4 of 56 cases changed verdict, and the fifth run earned its money.**

```
reproducible : gold_v0_1_020   0/5
unstable     : adv_008 1/5   adv_018 2/5   gold_v0_1_035 3/5   gold_v0_1_026 4/5
```

`adv_018` failed runs 1-3 and passed runs 4-5. **Had we stopped at three it would have been recorded as
a reproducible failure** — precisely the error step 3 found in the previous floor, where five identical
failures on one afternoon were filed as permanent for a case that has since answered twice.

##### The bounds, and the one judgment in them

Four are arithmetic. `refusal_accuracy` is the decision, taken by sjtroxel: **exclude
`gold_v0_1_020`, keep every unstable case inside the gate.**

**The argument I first gave for this was wrong, and testing it is what showed that.** I claimed that
counting the known failure spends one of the gate's allowed false refusals on a diagnosed bug, "so a
genuinely new false refusal would only trip the gate on runs where a second unstable case also fired."
The first half is true. **The second half does not follow, and is equally true of both options** —
measured against the five runs, one new false refusal fails **2 of 5** under the plain envelope and
**2 of 5** under the exclusion. Sensitivity is identical, because the slack comes from
`gold_v0_1_035` being unstable rather than from `gold_v0_1_020` being counted: excluding it lowers the
bound and the observations by the same one case.

**The reason that actually holds is durability.** The day `gold_v0_1_020` is fixed it stops
false-refusing, and under the plain envelope the observations drop to 0/0/0/1/1 against an unchanged
bound of ≤2 — **the gate silently gains a spare case of slack nobody decided to grant.** Under the
exclusion the bound and the observations stay aligned and the headroom stays zero. A gate that loosens
itself when a bug is fixed is the failure this file exists to prevent.

Two lesser reasons survive: it keeps the refusal and traversal exclusions as **one** decision rather
than half of one, and the number means something cleaner — "of 35 legitimately answerable cases, at
most 1 refuses" rather than "at most 2, one of which is a known bug". Excluding it costs nothing either
way — a case failing every run has nothing left to regress, and the only direction it can move is up. It is the same case the traversal bound already
excluded, for the same reason, and **the case remains in the dataset**, scored in `cases_correct` and
every slice; it loses a vote, not its membership.

**The unstable four stay in.** Excluding a case because it is *noisy* is a different act from excluding
one that is *diagnosed*, and it is how a gate stops measuring what is broken. That is why
`minimum_true_refusals` is 18 rather than 20.

**This required a code change, which the plan did not anticipate.** `_refusal_gate` read aggregates and
had no exclusion mechanism, unlike `_traversal_gate`. It now recomputes from per-case outcomes when
`excluded` is set — never by subtracting from the aggregate, which cannot say which direction an
excluded case contributed to.

##### Verification, because bounds that pass everything are worthless

All five recorded runs were replayed through the new gates: **6 PASS, exit 0, every run.** Then the
other half — a run one case worse than anything observed:

```
worst observed run              exit=0  no failures
+1 missed refusal               exit=1  refusal_accuracy
+1 false refusal                exit=1  refusal_accuracy
one gated case loses its path   exit=1  traversal_recall
```

**4. The `xfail` resolved itself exactly as its own reason predicted**, and the argument for strict
xfail over skip is now evidence rather than assertion: it XPASSed the moment a matching baseline landed,
turned the build red, and was deleted. Its resolution was the one it demanded and **not** the one it
warned against — `case_count` was not edited to fit the set; the set was measured.

**5. A reporting gap found at run 1 and fixed here.** `contested_disclosure` was wired into the suite and
the gate at step 6 but **not into `report.py`**, so on a `NOT GATED` run — which every live run was
between steps 5 and 7 — the number existed only in the JSON. A metric nobody can see is a metric nobody
checks.

**6. Seven stale references swept, and two had flipped from true to false.** `thresholds.py:matches`
described the denominators as "41 with 16 / 25 with 3"; both halves had moved (56 with 20 / 38 with 5) —
the docstring's own argument arriving as evidence. `live.py` claimed subsets are compared "against the
41-case baseline". Historical records in `eval/__init__.py` were **stamped, not rewritten**.

**Behavior changed by the bigger set, recorded where it matters:** one live run now answers ~36 of 56
cases rather than 25 of 41, so a 30-item tier 2 pool is reachable from a **single** run. `labelling.py`
said it needed two.

**7. The estimator is ~2x high and is deliberately left alone.** It projected 392 requests / $1.09; runs
issued 255-262 / $0.501-$0.539. A spend gate should quote the ceiling: the number a person approves is
the worst case they are consenting to, and tuning it toward the mean would make the prompt more accurate
and the consent weaker.

### Step 8 — Copy, docs, release — **DONE 2026-09-07**

The sweep, with the phase 6 step 10 finding applied: **a stale rule outlives the stale sentences it
produces**, so the sweep reads instruction files first, not last. `CLAUDE.md`, the three `.claude/rules/`
files, `README.md`, `SPEC.md`, `docs/spa-explained.md`, `KNOWN-GAPS.md`, and the ROADMAP spine.

**One correction carried into this sweep from 2026-09-07.** `.claude/rules/evals.md` records the gold set
as **"25 cases / 67 claims"** from the 2026-08-24 as-built. Measured today it is **29 cases / 66 claims**,
and after step 5 it is **38**. The case count moved with the phase 6 refusal rebuild; **where the 67th
claim went has not been chased**, and it plausibly tracks `c697712` honoring hand-rejected edges — the
same commit that moved 2,285 influence edges to 2,284 — but that is a guess and the sweep verifies it
rather than repeating it.

DoD #9 and #10. The release itself is a separate decision, as it was in phase 6.

**The plain-English write-up is written as the phase goes, not here at the end** — one short jargon-free
paragraph per step, added when the step lands. It is the cold-articulation rep and it is much harder to
reconstruct in December.

#### 8.0 As built — 2026-09-07. **STEP 8 DONE. PHASE 6.5 COMPLETE.**

**Verified:** `make check` green — **1461 passed, 0 xfailed**, 14 deselected, mypy clean over 99 source
files, frontend **168** across 16 files, root **17 of 18**, terraform valid. Scripted gates
**4 passed / 0 failed / 2 N/A of six**.

**1. THE AUDIT FOUND DoD #8 UNMET, and I would have signed it off.** *"Every billable run records a
dollar figure."* Step 0 configured the prices and the confirmation **prompt** printed one — which is
**displaying** a figure, not recording it. The result file carried only token counts, so all five
baseline runs printed a cost and left no trace of it. Closed here: `SuiteResult.estimated_usd` derives
from the measured tokens and the configured price, lands in `usage.estimated_usd`, and is **`null`**
rather than a guess when no price exists for that model. Verified against run 5's real usage —
**$0.501448**, matching the hand computation exactly — and both locks broken once.

This is the value of auditing a DoD against the artefact rather than against memory of having done the
step. The step was done; the requirement was not met.

**2. Instruction files first, because a stale rule outlives the sentences it produces.** That is phase 6
step 10's finding and it applied directly: **`.claude/rules/evals.md` said "Five gates exist; the free
every-commit run blocks on THREE of them"** and loads into every session in this repo. Amended, along
with its blocking list (which still described `traversal_recall` and `refusal_accuracy` as "within 5pp"
bands — both abandoned as arithmetically unsatisfiable, with the strikethroughs kept because the reason
generalizes), and its contested-metric paragraph, which said a contested metric was "NOT yet in this
catalog".

**The line most worth having amended is the one that now forbids its own kind of error**: *"Do not write
a gate count in prose anywhere, including this line ... and this sentence has now been wrong once for
exactly that reason."*

**3. The zero-variance trap is now recorded as a recurrence, not an anecdote.** `.claude/rules/evals.md`
carried it as a single historical finding; it now records that it happened **again** at the next
baseline, on a corpus three times larger with a different case count, and instructs treating it as the
**default hypothesis** for any 0.0pp spread rather than as a curiosity. Added beside it: five runs is
the floor, because `adv_018` failed three and passed two.

**4. Surfaces corrected.** `README.md` (test counts 1330/159 -> 1461/168; the "paid live suite gates
nothing" paragraph rewritten, and it now leads with what the five runs *bought* rather than with the
gates themselves). `CLAUDE.md` (an answer can say it; still never a claim, still not in the prose).
`docs/ROADMAP.md` (the 6.5 row marked complete, the build-status block rewritten, the "gates nothing"
item struck through and replaced with the `traversal_recall` warning). `docs/KNOWN-GAPS.md` (a closure
block: every DoD item with where it closed, the findings that outlive the phase, and what stays open).
The phase 6.5 **scope doc** was amended in place rather than rewritten — its §2 asked three questions
and answered "no, no, and no"; a dated block records all three now answered.

**5. The plain-English write-up landed in `docs/eval-suite-explained.md`** rather than a new file, as
§5.0 said it would. It covers the four things a person would actually ask about: the system can say its
sources disagree, refusals stopped lying about the graph, the femtanyl bug and why the obvious fix was a
trap, and what five identical runs cost and revealed. Written to be said out loud cold, which is the
point of it.

**6. What is NOT done, deliberately: the release.** Tagging `v0.6.5` and deploying is a separate
decision, as it was in phase 6. Nothing in this phase moved the artifact pin, the infrastructure or the
deployed image, so the live site is unaffected by everything here until someone chooses to deploy.

##### The phase, in one place

| DoD | closed at |
|---|---|
| 1. `contested` in an answer | step 4 |
| 2. `gold_v0_1_020` diagnosed and excluded | step 3 |
| 3. Three refusal states | step 2 |
| 4. `ResolveSource` verifies DBpedia | step 4 |
| 5. Datasets exercise contested / ambiguous / `dbpedia_only` at n>=5 | step 5 |
| 6. A gated live run on a measured set | step 7 |
| 7. The `xfail` gone because the invariant holds | step 7 |
| 8. Every billable run records a dollar figure | steps 0 and **8** |
| 9. No copy claims what the system cannot do | steps 4 and 8 |
| 10. ROADMAP row and `KNOWN-GAPS` | step 8 |

Gold **29 -> 38**, adversarial **18 -> 20**, live **45 -> 56**, gates **5 -> 6**, `make check`
**1330 -> 1461**. Total Bedrock spend for the phase: **$2.65** — $2.61 for the baseline and four cents
of wiring checks.

## 7. Decisions this plan does not make

Six from the scope doc §5. This plan carries a recommendation on two and leaves four open.

| # | decision | this plan's position |
|---|---|---|
| 5.1 | Shape of `contested` in a response | **CLOSED 2026-09-07: a distinct SSE event.** The two rejected options and why are recorded in §6 step 4. |
| 5.2 | Contested metric — gated, tracked, or absent | **CLOSED 2026-09-07: GATED**, as a property rather than a rate, which is what dissolves the denominator problem. Free on the scripted run. §6.0 item 11. |
| 5.3 | Is `gold_v0_1_020` fixable | Open by construction. Step 3 diagnoses; the decision follows the diagnosis and not the reverse. |
| 5.4 | How many `dbpedia_only` gold cases | **CLOSED 2026-09-07: six.** Gold ends at 38 cases, the live set at 54. Chosen for margin above the n<5 floor, not for a round total. |
| 5.5 | Held-out set at the freeze | **CLOSED 2026-09-07: NOT RUN.** Still sealed, still pinned 0.5.0, run count still **1**. No step depended on it and none was tempted to. |
| 5.6 | Do `-bedrock.json` runs stay gitignored | **STILL OPEN — and step 7 ran anyway, which is the honest record.** Five more result files now exist on one laptop, named by `noise_floor.json`, reproducible only by spending $2.61 again. The transcripts ARE committed; the results are not. Carried to a later phase. |

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
2. ~~**How much of step 1 the other `GraphStore` implementations cost.**~~ **RESOLVED 2026-09-07: zero.**
   `InMemoryGraphStore` is the only structural implementation; the other nineteen files use `GraphStore`
   as a parameter type. See §1.0 finding 1.
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
