# Known gaps at `v0.3.0-local`

Written 2026-08-12, at the phase 3 release step. Required by
`docs/phases/phase-3-agent-loop-IMPLEMENTATION.md` §5.1, which asks that the tag ship with the open items
named and the residual gaps stated plainly.

**Updated 2026-08-14** when the gold set was completed and again when the held-out 10 was drawn and
sealed. Every claim below was re-derived against the repo rather than copied forward.

**Verified state:** `make check` green — 852 passed, **0 skipped**, 7 `costs_money` tests deselected, mypy
clean, root 15/18, terraform valid. The former skip was the held-out seal; that set now exists, so
`test_the_committed_sealed_set_matches_its_manifest` runs and passes.

**Bedrock is not a blocker.** Access was restored 2026-08-11 after a twelve-day account-level quota fault.
Nothing here is waiting on AWS. What remains is unrun work, one undrawn dataset, and a small number of
standing facts about the corpus.

---

## Part 1 — open items, closable

Each of these can be finished. Mark `[x]` when it is, with the evidence.

### DoD #11 — refusal accuracy and traversal recall on real model output

The item is open and its two halves are open for different reasons. They do not close together.

- [ ] **Refusal accuracy against a real model.** Unrun, not unbuilt. `eval/harness.py:65` hardcodes
  `DATASET` to the adversarial set and takes no provider argument, so every recorded number in
  `eval/datasets/baseline_v0_3_0_local.json` is scripted. Two live anecdotes exist
  (`test_an_unresolvable_name_is_refused_rather_than_invented`, and the gate test beside it) but an
  anecdote is not a rate. Closing this is a wiring change plus one billable run.
- [ ] **Traversal recall against a real model.** It has **never been scored on a real run**, and until
  2026-08-12 it had never been scored on any run at all — its only callers were `tests/test_metrics.py`,
  because the gold schema had no field it could read. `expected_path` fixed that, and the gold set now
  holds **25 cases including 5 multi-hop path cases**, so the metric has real chains to walk. What remains
  is the live half: **this is now blocked behind Bedrock only, not behind the gold set.**

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
- [ ] **Injection resistance is not reported as a rate against a real model.** Five cases score locally;
  one scores live. Closing this is the same billable harness run as DoD #11's first half.

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

**No thresholds and no judge exist, deliberately.** Phase 3 records baselines; phase 4 sets gates. Per
`.claude/rules/evals.md`, thresholds invented before a baseline exists are worthless, and an LLM-judge
score with no measured human agreement is decoration.

---

## What closing these is worth

The resume line *"deployed on AWS Lambda and Bedrock with a deterministic groundedness gate at 100%"* is
**not claimable at `v0.3.0-local`**, because what is deployed runs a template. It becomes claimable at the
redeploy, and not before.

The interview-facing statement, rounded **down** rather than up: the loop works end to end against a real
model, what is deployed is still a stub, and the eval numbers measure the machinery rather than the model.
