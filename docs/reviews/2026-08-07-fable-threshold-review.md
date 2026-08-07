# Threshold review — 2026-08-07 (Fable)

> Second independent review, requested at the phase 2 → phase 3 boundary, before any phase 3 code.
> The first (`2026-08-01-fable-status-review.md`) covered scaffolding through the phase-1 plan; this one
> covers everything since — the phase 1 and 2 builds, artifact v0.1.0 → v0.5.0, the deploy pipeline, the
> AWS case, and the phase 3 plan written this morning, including decisions A1–A4.
>
> Every claim below was verified against the repo and the v0.5.0 artifact on 2026-08-07, not recalled.
> Findings are numbered; recommendations are marked. Decisions stay with sjtroxel.
>
> **Headline:** the project is in excellent shape and the phase 3 plan is structurally right. But one of
> this morning's four decisions — A1 — rests on a factual premise the artifact falsifies, and one
> sequencing rule in the plan closes an eval-contamination window later than it should. Both are cheap to
> fix now and expensive to fix after code exists. That is what a threshold review is for.

## 1. Verdict

Six days ago this project had an empty `src/` tree and an unapproved phase-1 plan. Today it has a
deployed, streaming, Terraform-provisioned product on AWS; a 973-node / 950-edge corpus built through a
measured, hand-validated filter pipeline; 333 green tests; a claims-first gate with two independent
locks on each of its two known conflation hazards; and a phase 3 plan that correctly refuses to let an
AWS provisioning fault dictate the build order. The velocity is high and — more unusual — the honesty
kept up with it. The two DoD partials in phase 2 are *named as partials* in the ROADMAP rather than
rounded up, and yesterday's retroactive A7 correction to a closed phase's scope doc is exactly the
discipline most projects lose first.

Three things deserve to be said plainly:

- **The held-out measurement (A6.5) is the single most impressive artifact in the repo.** A frozen
  deterministic filter, committed before the test set was drawn, held 97% precision on unseen data, and
  the objective/subjective tier framing *predicted* the failure shape rather than describing it after.
  That is real evaluation methodology, done before the agent exists, on a $0 budget. It is also the
  strongest interview material this project has produced so far.
- **The assertion filter refusing 486 prose-accepted edges (37%)** is the corpus-quality number that
  justifies the whole two-day detour, and it is published rather than buried.
- **The Bedrock situation was handled exactly right**: a reproducible two-region defect report, a
  confirmed root-cause reply from AWS, and a build that routed around the block instead of parking on
  it. Nothing further is owed on the case, and the phase 3 plan's local/Bedrock split is the correct
  structural response.

The findings below do not change that verdict. They change details of the phase 3 plan — before those
details become code.

## 2. Verified current state

| Item | State |
|---|---|
| `make check` | Green: format, lint, mypy over 40 files, **333 tests**, root cap 15/18, terraform fmt + validate |
| Git | 15 commits on `main`; working tree carries this morning's doc changes, **uncommitted** |
| Deployed | Lambda + Function URL live; `llm_provider=local`, so prose is a template — stated honestly in README/ROADMAP |
| Artifact | v0.5.0 pinned: 973 nodes / 950 edges; verification 22 `HAND` / 111 `PROSE_AUTO` / 760 `ASSERTS_AUTO` / 57 `EXPOSURE_AUTO`; **every edge and node `source: wikidata`** — the plan's one-source-per-edge premise is verified true |
| Gold set | 5 cases, pinned `0.5.0`, with a test asserting the pin matches the loaded store — the standing rule from review 1 finding 4.4 is now CI-enforced. Good |
| Cost guardrails | Verified in Terraform, not just docs: `aws_budgets_budget`, `aws_ce_anomaly_monitor` + subscription, explicit `retention_in_days`, timeout as a variable whose comment names it as the exposure |
| CI | Push-triggered CI plus `workflow_dispatch`; deploy is dispatch-only (a GitHub webhook outage is documented in-file as the reason) |
| AWS case | `178545883500013`: root cause confirmed by AWS 2026-08-06 23:48, restore in progress, no action owed |
| Phase 3 | Scope doc amended (A1–A5), IMPLEMENTATION doc written and approved, **zero code** — reviewed in §4 |

## 3. Review 1's ledger — closed, open, and overtaken

Accountability pass on the 2026-08-01 recommendations:

| Item | Status |
|---|---|
| 4.1 build steps 2–8 without AWS | **Done, emphatically** — phases 1 and 2 were built almost entirely under the block |
| 4.2 approve/commit the phase-1 doc + amendments | Done |
| 4.3 scratchpad rescue | `prosecheck.py` now lives in `ingest/` (830 lines, tested). Backup dir still exists; `citations30.json` / `full351.log` / `population331.json` still have no repo home — carried forward, §7 |
| 4.4 SPEC chip edit pass + validate-against-artifact rule | Done 2026-08-02, and the rule became a Tier-1 test |
| 4.5 frozen datasets before the agent exists | **Partially done, and the remainder is now urgent** — see finding 4.3 below, the most consequential item in this review |
| 4.6 artist-bridge measurement | **Overtaken by the real thing**: the artist ingest moved `max_path_hops` 2 → 6 and the largest component 31 → 458. The thesis question ("do artists bridge the islands?") is answered *yes, measurably* |
| 5.1 `dbo:stylisticOrigin` count | Still open, still phase 6, still worth one query before that phase is planned |
| 5.2 corpus number on screen | Done and exceeded — `/health` and `done` carry verification, structure, and coverage |
| Housekeeping (0-byte file, 2nd MFA, anomaly detection) | Anomaly detection: **done, in Terraform**. 0-byte `~/bedrock-quotas-2026-08-01.json`: **still there**. Second root MFA: unverifiable from the repo, presumed still owed |

## 4. The phase 3 plan, reviewed

I was asked to review this morning's decisions independently rather than ratify them. Verdicts: **A2,
A3, A4 endorsed as decided. A1 endorsed in direction, wrong in premise — it needs a recalibration
before code.** Plus one plan bug and one sequencing correction.

### 4.1 A1's factual premise is falsified by the artifact: `checks_disagree` has population ZERO, not 6

The plan (IMPLEMENTATION §1.3, scope A1) builds the `checks_disagree` state on this premise: *"at step
3, `select_edges()` re-admitted 6 of 7 hand-REJECTED edges — cases where the human and the automated
check reached opposite conclusions on the same edge,"* population "6 edges out of 950."

**The code and the artifact both say otherwise.** `ingest/wikidata.py`'s `select_edges()` rule 2:
everything in `REJECTED_EDGES` is **out**, *"even though the automated check accepts six of the seven"*
— the hand rejection wins, and the function returns those pairs on a separate **overruled** list
precisely so the over-accept rate is published. Verified directly: all three spot-checked rejected pairs
(`groove metal <- heavy metal`, `heavy metal <- hard rock`, `heavy metal <- classical music`) are
**absent from v0.5.0's edges**. And the full cross-tab of the two per-edge check fields is unanimous:
all 950 edges are `prose_tier: PROSE`, so **no edge in the shipped corpus carries a recorded
disagreement between checks.** Phase 2's policy resolved every disagreement by exclusion. The plan's
own hedge ("may be too rare to show up") understates it: the state is not rare, it is *structurally
unreachable*, for the same class of reason `contested` is.

The error's origin appears to be a memory-index line ("the check re-admits 6 of 7 hand-REJECTED edges"),
which inverts what the code does. The memory should be corrected too, or this will recur.

Two knock-on problems in the same section:

- **`multiply_checked` as specified would over-claim.** If "two or more independent checks" counts the
  prose check plus the assertion filter, then 760 of 950 edges (80%) become "multiply checked" — but
  those are *sequential stages of one automated pipeline over the same article text*, not independent
  checks. The only genuinely independent pair in the corpus is human + automated, i.e. the 22 `HAND`
  edges. A corroboration field where 80% of the corpus reads as corroborated would be the inflation the
  enum exists to prevent.
- **The "hand-label record" the gate is supposed to read has no runtime home.** The hand verdicts live
  in ingest code (`HAND_VERIFIED_EDGES` / `REJECTED_EDGES`) and a phase-1 doc — not in the artifact, and
  the gate runs in Lambda against the artifact. The plan never says where this data comes from at
  runtime, and for the rejected edges it would not matter anyway: they are not corpus edges, and the
  gate only ever sees corpus edges.

**Recommendation — keep A1's decision, change its implementation.** The decision that matters —
*never ship the word "contested" over a one-source corpus* — is right, is his, and stands. But rather
than building a `Corroboration` enum with two reachable states, two empty ones, and an inflation
hazard, do the simpler, more honest thing the corpus actually supports:

1. **Put `verification` on `Claim`**, copied by the gate from the edge exactly as `source_ids` already
   is, and surface it per-claim in the SSE stream. This is the real gap DoD #3 points at: today an
   individual claim in the output does not say whether it rests on a human reading or on documented
   exposure — only the aggregate counts do. Per-claim verification gives **four genuinely
   distinguishable, all-reachable evidential states** in the output, from data that exists, with no new
   enum and no empty states. It satisfies DoD #3's shape (*"distinguishable in the output"*) more
   honestly than the planned enum does.
2. **`checks_disagree` joins `contested` in the reserved set** — defined, documented, test-locked
   unreachable. It becomes populatable if a future corpus policy ingests overruled edges flagged
   instead of dropping them (a phase 6 decision that pairs naturally with second sources; it would be a
   corpus policy reversal and a new artifact cut, both out of phase 3's scope by the plan's own fence).
3. **Publish the overruled list as the ingest-time disagreement number** (it is 6-of-7, it is real, and
   it is a *pipeline* statistic, not an edge property) — in the manifest or the coverage payload, where
   ingest statistics already live.

This is less code than the planned enum, uses only data the artifact carries, and cannot over-claim.

### 4.2 Plan bug: `describe_node` must not emit proposals

IMPLEMENTATION §4.2: *"`describe_node` and `get_descendants` both emit proposals."* For `get_descendants`
that is right — it returns edges. For `describe_node` it is wrong: the tool returns node metadata
(`kind`, `inception_year`, `countries`), no edge is involved, and `ALLOWED_PREDICATES` contains only
`influenced_by` — any proposal it emitted would be a guaranteed `UNSUPPORTED_PREDICATE` rejection,
polluting the rejection stream that refusal accuracy is measured on. `describe_node` belongs with
`resolve_source` and `corpus_coverage` in the emits-none group — which strengthens the seam test, since
three no-proposal tools check the loop's no-assumption property harder than two.

Related, worth one sentence in the plan so nobody trips on it later: `describe_node`'s dates and places
can inform the agent's *tool-loop reasoning* but can never reach *prose* — `synthesize()` sees only the
approved claim set, and the synthesis prompts explicitly forbid dates and places. That is the leak
protection working as designed, not a bug; wanting dates in answers is a claim-model extension (new
predicates) and belongs to phase 6 at the earliest.

### 4.3 The eval-contamination window closes at step 8, and the plan leaves two datasets outside it

`.claude/rules/evals.md`: the **three** frozen datasets — gold 20–30, adversarial 15–20, held-out 10 —
are hand-built *before the agent exists*, or they are contaminated by model output. `planning/09` §6
carries the same assignment ("gold-set authoring session scheduled **before** agent coding starts").

The plan hand-authors the adversarial 18 as step 1 — correct, and correctly first. But it explicitly
defers the held-out set to phase 4 and says nothing about extending the gold set beyond the v0.1 five.
**Phase 4 comes after step 8, and step 8 is the moment the first real model output ever exists.** Right
now the project is in an unusual, unplanned state of grace: because Bedrock has never completed a call,
*nothing* can be contaminated by model output yet. Datasets authored today are clean by construction.
Datasets authored after step 8 are authored by people who have watched the real agent behave — the exact
shaping the rule exists to prevent.

**Recommendation:** amend the plan so the full gold set (20–30, every edge cited, with the boring
middles the rule demands and — per the rule — sources *independent of Wikidata* so divergence surfaces)
and the sealed held-out 10 are authored **any time before step 8 runs**, as a hard precondition on step
8 rather than a step-1 blocker. They can trail steps 2–7; they cannot trail the first `converse` call.
Note the corpus is 46× larger than when the v0.1 five were written, so the gold set finally has real
material — including artist-axis and multi-hop cases the five cannot cover. And once the held-out 10
exist: sealed means sealed, including from me and from Opus.

### 4.4 A2, A3, A4 — endorsed, with three small notes

- **A2 (seven tools):** right list, right drops. Semantic search over a 973-node corpus with working
  label resolution would be complexity spent making the honest-refusal behaviour *worse*, and text
  retrieval has no text to retrieve. `get_descendants` genuinely closes a hole (`Direction.INFLUENCED`
  has had zero tool exposure since phase 2 — confirmed in `tools.py`). One note: the loop's
  `SYSTEM_PROMPT` still opens *"You answer questions about where music **genres** came from"* — written
  before the artist axis existed. Phase 3's planning step rewrites the prompt anyway; make axis
  neutrality an explicit acceptance item so a U2 query is not being answered under a genres-only prompt.
- **A3 (version lines):** correct and now consistently applied across ROADMAP/README/scope docs.
- **A4 (the split):** the deferral mechanics are genuinely good — tests-that-exist-but-skip beats a
  backlog item, and naming phase 4 as the home beats "later." Two mechanical notes: `pyproject.toml`
  already registers a **`costs_money`** marker ("makes a billable Bedrock call; never runs unattended"),
  so the planned `@pytest.mark.bedrock` should either reuse it or be added to the registry —
  `--strict-markers` is set, so an unregistered marker fails the suite (a good trap, working as
  intended). And the `Planned` SSE frame is additive under SPEC §6's "the rest are additive" rule, but
  SPEC should gain the frame name when it lands, since SPEC is where the frame vocabulary lives.

## 5. Findings in the shipped work

Ordered by how much they matter. Nothing here is structural; two touch published honesty numbers, which
this project treats as load-bearing — because its entire pitch is that its numbers can be trusted.

### 5.1 The "44 genres name no US/UK" counterweight is inflated: UK drill's origin is Brixton

`graph/coverage.py` computes `genres_without_us_or_uk` by exact string membership against
`ANGLOPHONE_CORE = {"United States", "United Kingdom"}`. But P495 values are whatever Wikidata holds,
and the v0.5.0 artifact contains `UK drill -> ['Brixton']` — a district of London. UK drill therefore
counts toward "names no US or UK," which is false on its face. Other non-country values exist
(`Europe`, `Scandinavia`, `Hawaii`, `French West Indies`) but none of the others flips the US/UK test;
Brixton is the one that does. The same wart makes `distinct_countries: 29` really "29 place labels."

This number is quoted in the ROADMAP, the memory index, and the phase 2 record as the flagship
concentration-is-not-absence figure. **Recommendation:** a small, documented normalization map in
`coverage.py` (`Brixton → United Kingdom` at minimum; optionally fold the region labels with a comment),
turning 44 → 43. Coverage is recomputed at runtime from the pinned artifact, so this is a code change
with **no artifact rebuild** — but it changes a published number, so it should land as its own commit
with the reason in the message, and the quoted figures in docs/memory updated in the same pass. Cheap,
and exactly the kind of correction this project's credibility is built on.

### 5.2 The retracted "77%" figure survives in `api/app.py`'s docstring — in the honesty module

`api/app.py:117` (the `corpus_summary` docstring): *"the United States and United Kingdom account for
77% of the genres that name any country of origin."* That is the 2026-08-06 double-counting-era claim,
already caught and corrected elsewhere — the true statement is **77 of 121 genres, which is 64%**. The
number 77 survived the correction by changing units from count to percentage. It is a docstring, not
computed output — but it sits in the module whose stated job is displayed honesty, and it is precisely
the figure the correction memory says not to repeat. **Recommendation:** fix the sentence; grep the repo
for `77%` while at it.

### 5.3 SPEC drift — the canonical contract no longer matches the shipped contract, in three places

SPEC's charter is "defined once and referenced, never duplicated," which makes drift here worse than
drift anywhere else:

1. **§5's verification table lists two tiers** (`HAND`, `PROSE_AUTO`); the corpus has carried four since
   v0.4.0. Anyone implementing against SPEC builds a two-value enum.
2. **§6's `corpus` payload omits the `coverage` object** that `/health` and `done` have emitted since
   step 8. The deployed contract is a superset of the canonical one.
3. **§2.2's Kate Bush row** still reads "Blocked on: the ~31k artist-level P737 edges. Phase 2." The
   axis shipped; the query now *correctly refuses* (zero outgoing P737). The ROADMAP explicitly parked
   this as "a decision, not a fix" — fine, but the decision is now owed, because a canonical doc
   asserting a stale blocker is drift regardless of whose decision resolves it. Options: annotate the
   row as resolved-by-refusal (my lean — the refusal is a *good* demo of the thesis's honesty), or swap
   the chip for an artist with outgoing edges (U2 answers with six gated claims).

### 5.4 v0.5.0's manifest `notes` field contains its own text twice

The coverage-stamp paragraph appears verbatim twice before the inherited v0.4.0 notes — an artifact of
`ingest/coverage.py`'s `notes=(... f"Source notes follow. {manifest.notes}")` concatenation pattern
being applied to an already-stamped source. Harmless, and the frozen manifest should **not** be
rewritten (immutability is the point). But the generator should deduplicate or bound the chain before
the next artifact cut, or v0.6.0's notes will carry the whole lineage twice over.

### 5.5 Small items

- **This morning's doc work is uncommitted** — six files including the approved IMPLEMENTATION doc. An
  approved plan that exists only in a working tree is one `git checkout` from gone. Commit before
  anything else happens today.
- The review-1 leftovers: the 0-byte `~/bedrock-quotas-2026-08-01.json`, the backup dir whose three
  data files (`citations30.json`, `full351.log`, `population331.json`) still lack a repo decision, and
  the presumed-owed second root MFA device.
- `data/artist_screening.json` is gitignored by design (memory: a 25-minute recrawl if lost). Fine —
  but it is also input to a *frozen, published* measurement. A copy alongside the backup dir costs
  nothing and makes A6.5 re-derivable even if WSL eats the working tree.

## 6. What the plan gets right that reviews usually have to ask for

Recorded so the calibration is two-sided, and because several of these should be *kept* when the plan
is amended per §4:

- Adversarial set first, tools second — the contamination-aware ordering, applied before I could ask
  for it (§4.3 extends it to the other two datasets; the instinct was already right).
- The invariant-4 seam test as a mechanical assertion (loop file unchanged across the last tool's
  commit), not a code-review vibe.
- A token budget alongside `MAX_TURNS`, with the correct reasoning that turns are a poor proxy for
  spend in an input-heavy loop.
- Slices under n=5 print their n, never a percentage.
- The refusal metric stays a pair everywhere it appears.
- "No first-party per-token figure may be quoted as a Bedrock cost in this repo" — a rule that will
  quietly prevent a whole class of future doc bugs.
- The A7 retro-correction to phase 2's scope doc: the record says what happened, not what was planned.

## 7. Recommended order — the pre-code punch list

1. **Commit the working tree** (this morning's six files, plus this review).
2. **Amend the phase 3 plan per §4.1–§4.3** — the corroboration recalibration (per-claim
   `verification`, reserved `checks_disagree`, published overruled count), the `describe_node`
   proposals fix, and the gold/held-out-before-step-8 precondition. Also correct the memory line that
   says the six edges were re-admitted. These are text edits; an hour, not a day.
3. **The two honesty-number fixes** (§5.1 Brixton, §5.2 the 77%) — small, self-contained, and worth
   doing before phase 3 code so the numbers the new tools surface are already right.
4. **SPEC sync** (§5.3) — four tiers, the `coverage` object, and the Kate Bush row decision.
5. **Then phase 3 step 1**, exactly as planned: the adversarial 18 — with the gold-set extension and
   held-out 10 scheduled anywhere before step 8.
6. Housekeeping (§5.5) whenever convenient; none of it blocks.

Items 2–4 are collectively a morning. None requires re-approval of the phase's shape — the split, the
tools, the budgets, and the deferral structure all stand as decided.

## 8. Housekeeping ledger v2

- Delete the 0-byte `~/bedrock-quotas-2026-08-01.json` (carried from review 1).
- Decide homes for `citations30.json` / `full351.log` / `population331.json`; then delete
  `~/mm-validation-scripts-backup-2026-07-31/` (carried from review 1).
- Back up `data/artist_screening.json` and `data/screening.json` outside the WSL working tree.
- Second root MFA device, next console visit (carried from review 1, unverifiable from here).
- Fix the manifest-notes concatenation in `ingest/coverage.py` before the next artifact cut (§5.4).
- Register or reuse the Bedrock test marker in `pyproject.toml` when step-8 tests are written (§4.4).
- One query, before phase 6 planning: the `dbo:stylisticOrigin` count (carried from review 1, §5.1).
