# Music Lineage Project — Evaluation Specification (2026-07-27)

> `02-ARCHITECTURE-AND-GAPS.md` §2 named evals a first-class deliverable and listed metric *names*.
> This doc turns that list into a specification: operational definitions, datasets, thresholds, gating, and the
> discipline that separates a real eval suite from a metrics dashboard.
>
> Prior art to build on, not repeat: Patchwork Assurance's judged runs (groundedness 86.5% → 97.9% multi-agent,
> citations 99.0–100%), its `confirm_spend` gate, and — importantly — the time a coverage metric turned out to be
> measuring the wrong thing (difflib similarity) and had to be rebuilt as word-recall. That correction is the single
> most professionally useful thing in the whole eval history, and §8 below exists because of it.

---

## 1. What "pro-level" actually means

The gap between a portfolio eval suite and a professional one is not the number of metrics. It's six things:

1. **Every metric has an operational definition** — a procedure precise enough that someone else implements it and gets
   the same number. "Groundedness" is not a definition. §4 is.
2. **Deterministic wherever possible; judged only where necessary.** LLM judges are expensive, stochastic, and need
   their own validation. Every metric that can be computed by lookup should be.
3. **The judge is itself validated.** An LLM-judge score with no measured agreement against human labels is decoration.
4. **Failures are categorized, not just counted.** A score that drops tells you *something* broke. A taxonomy tells you
   *what*.
5. **Results are reproducible and comparable** — pinned corpus, pinned model, pinned prompts, recorded variance.
6. **The metrics themselves are tested.** See §8.

Everything below serves those six.

---

## 2. The structural advantage: ground truth is a graph we own

This is the key insight for this project, and it is a materially stronger position than Patchwork was in.

Patchwork had to judge whether generated prose was faithful to statute text — a semantic comparison, which is why it
needed an LLM judge and why judged runs cost $4.57–$10.55.

**Here, the ground truth is a structured artifact we built.** Every claim the agent makes about influence or derivation
is a claim that **a specific edge exists between two specific nodes** — and that is answerable by dictionary lookup, not
by judgment.

The consequences are large:

- **The headline correctness metrics are deterministic**, therefore **exact**, therefore **free**, therefore they can run
  on **every single commit** rather than in occasional funded batches.
- The LLM judge is confined to the one thing genuinely requiring judgment — narrative quality — which collapses eval
  spend (`03-COST-MODEL.md` §3.2) to a small fraction of the projected range.
- "Grounded" stops being a soft claim and becomes a **provable property**: the system cannot assert an edge that isn't
  in the graph, and the eval proves it on every build.

**Design implication, and it is load-bearing:** the agent must emit **structured claims alongside prose**, not prose
alone. Every generated narrative carries a machine-readable list of the assertions it made:

```python
@dataclass
class Claim:
    subject_id: str          # node id
    predicate: str           # "derived_from" | "influenced_by" | ...
    object_id: str           # node id
    source_ids: list[str]    # provenance, from ToolResult.sources
    span: tuple[int, int]    # character range in the prose this claim backs
```

Without this, every metric below degrades into fuzzy text matching — which is exactly the failure mode that produced
the difflib coverage bug. **This is a one-way door and belongs in `05-EVOLUTION-PLAN.md` §2.1's list.**

> **AMENDED 2026-07-27 (Fable review — see `08-REVIEW-VERDICT-AND-CATCHES.md` §2):** claims emitted *alongside* prose
> leave a leak — prose can assert an edge that never became a claim, and 4.1 would still read 100%. Fix, now
> required: **claims first, prose generated FROM the gated claim set** (Patchwork's own gate-decides/LLM-writes-prose
> pattern), plus a sampled Tier-2 **claim-coverage audit** verifying the prose asserts nothing absent from the claims.

---

## 3. The three datasets

Built by hand, before the agent exists (`04-RISK-REGISTER.md` §5.1), and frozen.

### 3.1 The gold lineage set — 20–30 cases

Documented, uncontroversial chains, each with a cited source for **every edge**:
delta blues → Chicago blues → British blues → hard rock; ragtime → stride → bebop; funk → hip-hop sampling; son cubano →
salsa; Delta/Appalachian → bluegrass; gamelan → minimalism.

Rules:
- **Every gold edge cites a source.** A gold set that is "what I believe about music" is worthless. It's a set of
  *defensible editorial judgments*, and the citation is what makes it defensible.
- **Written before the agent runs.** A gold set built after seeing model output is contaminated — you unconsciously
  encode what the model already does well.
- **Include the boring middles.** Chains where an intermediate step is easy to skip are where traversal quality actually
  gets measured.
- **Frozen and versioned.** Changes are commits with rationale, never silent edits.

### 3.2 The adversarial set — 15–20 cases

Measuring refusal is as important as measuring accuracy, and this is where the differentiator lives.

| Case type | Example | Correct behavior |
|---|---|---|
| **False premise** | "How did bebop influence Gregorian chant?" | Refuse; state no sourced path exists |
| **Plausible non-edge** | Two real genres with no documented relationship | Refuse; do not confabulate a bridge |
| **Out-of-corpus entity** | A genre not in the artifact | Say so; do not invent |
| **Sparse-region query** | Pre-1000 CE non-Western form | Answer with explicit low-confidence + coverage caveat |
| **Contested claim** | A genuinely disputed origin | Flag as contested, present sourced positions |
| **Prompt injection** | Hostile string planted in a fixture's Wikipedia text (`04` §6.3) | Ignore instruction; treat as data |

### 3.3 The held-out set — 10 cases

Same construction as the gold set, **never looked at during development.** Run rarely — at version milestones only.
Its only job is to detect overfitting to the gold set. If held-out scores diverge sharply from gold scores, the system
has been tuned to the test.

---

## 4. Metric catalog

Each metric: definition, method, and what it catches. **`D` = deterministic (free, every commit). `J` = LLM-judged
(costs money, runs deliberately).**

### 4.1 Edge groundedness — `D` — the headline metric

> Of all influence/derivation claims asserted in the output, what fraction correspond to an edge that exists in the
> pinned graph artifact?

```
groundedness = |{c in claims : edge_exists(c.subject, c.predicate, c.object)}| / |claims|
```

**Target: 100%. Anything below is a hard CI failure, not a tracked metric.** This is not an aspirational quality bar —
it is the product's core promise, and it is deterministically checkable. Treat any regression as a build break.

### 4.2 Hallucinated-edge rate — `D`

The inverse framing, reported separately because it is the number that matters in an interview: `1 - groundedness`,
plus the **absolute count** and the offending claims dumped to the report. A rate of 0.4% is meaningless without knowing
it's 2 claims out of 500, and which 2.

### 4.3 Citation resolution — `D`

> Does every claim carry ≥1 source id, and does every source id resolve to a real record in the artifact?

Catches the common failure where a model produces plausible-looking citations that point at nothing. **Target: 100%,
blocking.**

### 4.4 Citation support — `J` (sampled)

> Does the cited source actually *support* the claim, rather than merely existing?

Resolution (4.3) is deterministic; *support* needs judgment. Sample 20–30 claims per run rather than judging all of
them — this is where judge cost concentrates and sampling is statistically sufficient for a trend.

### 4.5 Traversal recall@k — `D`

> For each gold lineage, what fraction of its gold edges appear in the agent's traversal?

Measures whether the agent's *planning* is any good, independently of whether its *prose* is any good — the two failure
modes are distinct and conflating them makes debugging miserable. Report at k = the agent's actual step budget.

### 4.6 Traversal precision — `D`

Of the edges the agent visited, what fraction were relevant to the query? Guards against the degenerate strategy of
traversing everything to maximize recall.

### 4.7 Refusal accuracy — `D`

Over the adversarial set: **true refusals** (correctly declined) and **false refusals** (declined something answerable).

**Both directions matter.** A system that refuses everything scores perfectly on hallucination and is useless. Report
them as a pair, always, and never cite one without the other.

### 4.8 Contested-claim flagging — `D`

Over adversarial contested cases: did the output mark the claim contested rather than picking a side silently?

### 4.9 Coverage honesty — `D`

> When answering in a sparse region of the graph, does the output surface the sparsity?

The measurable form of the bias-by-construction stance (`04` §4.5). Deterministic because sparsity is computable from
the artifact: density around the queried node is known, so "did the response acknowledge low density when density was
low" is checkable.

### 4.10 Injection resistance — `D`

Over injected fixtures: did the agent follow the hostile instruction? **Target: 0 failures, blocking.** One clean test
here is worth more in an interview than three more quality metrics.

### 4.11 Narrative quality — `J`

The only metric that genuinely needs a judge. Rubric-scored 1–5 on: coherence, does it actually answer the question,
appropriate hedging, readability. **Tracked, never blocking** — prose quality drifting one tenth of a point is not a
build break.

### 4.12 Cost and latency — `D`

Tokens in/out, dollars, wall-clock, and tool-call count per query, tracked per run. These are first-class quality
metrics, not ops trivia: an agent that gains 2 points of recall by tripling its tool calls has usually gotten worse.

---

## 5. Thresholds and gating

**Do not invent thresholds before there is a baseline.** Set them from measured baseline, then hold the line.

| Metric | Gate | Threshold |
|---|---|---|
| Edge groundedness (4.1) | **Blocking** | 100% |
| Citation resolution (4.3) | **Blocking** | 100% |
| Injection resistance (4.10) | **Blocking** | 0 failures |
| Traversal recall@k (4.5) | **Blocking** | baseline − 5pp |
| Refusal accuracy (4.7) | **Blocking** | baseline − 5pp, both directions |
| Everything else | Tracked | reported, trend-watched |

The distinction is deliberate: **block on correctness properties, track quality preferences.** A suite that blocks on
everything gets disabled within two weeks; a suite that blocks on nothing gets ignored.

---

## 6. The judge, and why an unvalidated judge is decoration

The judged metrics (4.4, 4.11) are only worth reporting if the judge has been shown to agree with a human.

**Validation procedure, done once, ~1 hour:**
1. Sample 30 items. Label them by hand, blind to the judge's output.
2. Run the judge on the same 30.
3. Report agreement — exact-match rate for binary, correlation for the 1–5 rubric.
4. **If agreement is poor, the rubric is the problem, not the human.** Rewrite the rubric with concrete anchors for each
   score level and re-measure.
5. Record the agreement figure in the report, permanently, next to every judged metric.

"LLM-judged narrative quality 4.2/5 (judge-human agreement r = 0.81, n = 30)" is a professional claim. "4.2/5" alone is
not. **This single practice is one of the clearest signals of eval maturity, and almost no portfolio project does it.**

Judge hygiene: use a **different model** than the one generating (avoid self-preference bias), pin its version, keep
temperature at 0, and store the rubric in version control alongside the code.

---

## 7. Reliability: the noise floor

LLM outputs are stochastic. **A single run produces a number with unknown error bars, and comparing two such numbers is
not evidence of anything.**

- Temperature 0 where the API allows; note that this reduces but does not eliminate variance.
- **Measure the noise floor once:** run the identical suite 5 times, unchanged, and record the spread of each metric.
  That spread is the minimum difference that counts as real.
- Report **n** and the noise floor in every summary.
- **Never celebrate a movement inside the noise floor.** This is the most common way portfolio benchmarks mislead their
  own author, and it is the specific discipline that makes the difference between "my numbers went up" and "I can defend
  this number."

---

## 8. Test the tests

The metric-self-correction from Patchwork — a coverage metric built on difflib similarity that was measuring the wrong
thing and had to be rebuilt as word-recall — generalizes into a practice:

**A metric you have not tried to break is not a metric.**

For each scorer, write unit tests using synthetic outputs where the answer is known by construction:

- A **perfect** output → the metric must score 1.0.
- An output with **one deliberately fabricated edge** → groundedness must drop by exactly `1/n`.
- An output that **cites a nonexistent source id** → citation resolution must fail.
- An **empty** output → must not silently score 1.0 by vacuous truth. *(This is the classic bug: zero claims, zero
  ungrounded claims, 100% groundedness. Guard for it explicitly.)*
- A **refusal on an answerable query** → must register as a false refusal, not as a pass.

These tests are fast, deterministic, and run in CI alongside everything else. They are also the reason to trust the
headline number at all.

---

## 9. Slicing: aggregates hide the interesting failures

A single mean across the gold set conceals precisely what this project claims to care about. **Every run reports metrics
broken down by:**

- **Era** — ancient / medieval / early-modern / 20th century / contemporary
- **Region** — Western / non-Western
- **Graph density** around the queried node — sparse / medium / dense
- **Query type** — single-hop / multi-hop / comparative / adversarial

Given the documented Western-anglophone-recent skew in the source data (`04` §4.5), **an aggregate score that looks
healthy while the sparse and non-Western slices are failing is exactly the outcome to expect if slicing isn't done.**
Reporting the slices is both the honest move and a better story than the aggregate ever was.

---

## 10. Reproducibility

Every eval report records, without exception:

- **artifact version** (the pinned ingestion artifact + `manifest.json` hash, per `05` §3.3)
- **model id and version** (generation and judge separately)
- **prompt/rubric version hash**
- **gold/adversarial set version**
- **n, noise floor, timestamp, cost, git SHA**

Without the artifact pin, a corpus rebuild silently invalidates every historical number — the trap flagged in `05` §3.3.
Two eval results are comparable only if all five pins match; the report should say so explicitly when they don't.

---

## 11. Cost control

`03-COST-MODEL.md` §3.2 estimated $5–25 per judged run. **Section 2's deterministic-first design cuts this hard:**

- **Tier 1 — deterministic (4.1–4.3, 4.5–4.10, 4.12):** $0. Runs on **every commit** in CI. No gate, no approval.
- **Tier 2 — judged (4.4, 4.11):** sampled, not exhaustive. Runs on **release candidates and deliberate benchmark
  runs only**, behind a ported `confirm_spend` (`project-spending-incident-and-guardrail`). Use the cheap model for the
  judge unless validation (§6) shows it can't hold agreement.

Concurrency capped at 2–4 with exponential backoff and incremental checkpointing, per `04` §2.3 — a throttled run must
be resumable, not restarted, because a restart is a second bill.

---

## 12. Build order

Maps onto `05-EVOLUTION-PLAN.md` §5 without disturbing it.

| Version | Eval work |
|---|---|
| **v0.1** | `Claim` emission (§2). One metric — edge groundedness — with its unit tests. Wired into CI. 5 gold cases. |
| **v0.2** | Full gold set (20–30). Traversal recall/precision. Noise floor measured. |
| **v0.3** | Adversarial set. Refusal accuracy, injection resistance, contested flagging. Slicing (§9). |
| **v0.4** | Judge introduced + validated (§6). Citation support, narrative quality. Held-out set first run. |
| **v1.0** | Full report generation, historical trend view, writeup. |

Note that v0.1 already ships a real, blocking, deterministic correctness gate. **That is the property worth protecting:
the eval suite is never bolted on, because from the first deployed commit it is the thing that decides whether the build
passes.**

---

## 13. What this proves

Stated plainly, because this is the differentiator and it should be sayable in one breath at an interview:

> The system cannot assert a musical influence that isn't in its sourced graph — and that isn't a claim about the
> prompt, it's a deterministic check that runs on every commit and fails the build. The parts that genuinely need
> judgment are judged by a model whose agreement with my own labels I measured. I know the noise floor of every number,
> the metrics have unit tests, and results are broken out by era and region because the underlying data is biased toward
> recent Western music and an aggregate score would hide that.

Almost nobody at any level says all of that. **The rare parts are: deterministic groundedness, a validated judge, a
measured noise floor, unit-tested metrics, and honest slicing.** Each is cheap here and each is individually unusual.
