# Phase 2 — Corpus and Traversal (v0.2): IMPLEMENTATION

> **As-built plan.** Written 2026-08-04, immediately before building, so it absorbs what phases 0 and 1
> actually taught. The scope doc (`phase-2-corpus-and-traversal.md`) was written 2026-07-29, **two days
> before the P279/P737 validation**, and parts of it rest on an assumption that validation falsified.
> Section 1 is the reckoning. Nothing below silently contradicts the scope doc; where they differ, the
> amendment is named and needs approval.

---

## 1. Where the scope doc has gone stale

The scope doc told us to re-read it and amend where phase 1 taught something different. It did, in four
places. Three are shrinkages and one is a definitional fix.

### 1.1 The corpus numbers in the scope doc are the wrong corpus

> Scope doc, Delivers: *"~6,324 Wikidata genres and ~7,936 derivation edges"*

Those are **P279** counts, and P279 is not derivation — it is category membership
(`docs/graph-semantics.md` §2). The word "derivation" in that line is the exact conflation
`planning/04` §4.4 warned about, and `01-DATA-SOURCES.md:16` carried the same error until it was amended.

The real lineage corpus is **351 P737 genre-out edges**, of which 331 land on something typed as a genre,
of which **158 hold a PROSE tier — and 158 is an upper bound, not the corpus size** (§4.6, §4.7). Phase 1
hand-read 28 PROSE-tier candidates and rejected 7.

**Realistic phase-2 target: 120–160 sourced edges over roughly 200 genres.** Not 7,936. Phase 2 grows the
corpus by roughly **6x** over v0.1's 21, not by 400x.

**Amendment A1 — proposed:** rewrite the scope doc's Delivers line to name the P737 corpus and its
measured size, and strike the word "derivation" from the P279 count.

### 1.2 MusicBrainz is a widening, not a delivery

> Scope doc, Delivers: *"plus MusicBrainz CC0 core tables for artists and releases"*

Nothing in `SPEC.md` §2 — neither the five validated v0.1 queries nor the seven aspirational v0.5 chips —
needs a MusicBrainz release. The one artist-shaped chip ("Who influenced Kate Bush?") is answerable from
Wikidata's ~31k artist-level P737 edges alone.

MusicBrainz brings a new HTTP client, a 1-request-per-second budget, a contactable User-Agent obligation,
and a **licensing surface where core tables are CC0 but contributor data is CC BY-NC-SA 3.0** — a
distinction this project cannot be sloppy about, since correct attribution is the entire pitch. That is
real work buying nothing any current query needs.

**Amendment A2 — proposed:** MusicBrainz moves to phase 6 (`density-and-coverage`), where releases,
geography and time are the subject. The artist axis **stays in phase 2** but is Wikidata-P737-only and
bounded (§4.6 below).

### 1.3 DoD #4 assumes P279 is being ingested. It should not be.

> Scope doc, DoD #4: *"P279 chains terminate at the genre-domain boundary rather than climbing to
> abstractions."*

That item exists because the plan assumed P279 was the corpus. It is not, and **P279 is not ingested at
v0.1 at all** — `graph/schema.py:26` and `agent/claims.py:36` are two independent locks on that door,
deliberately.

Ingesting P279 in phase 2 would buy exactly two things: taxonomic connectivity as a mitigation for the
46-components problem (§5), and a taxonomy display. **Both are phase 6's subject**, and `graph-semantics.md`
§5 says so in as many words: the components question "is the substance of phase 6."

The boundary problem does not disappear, it just gets contained. The type filter already walks
`P31/P279*` to test whether an entity reaches `Q188451` — that is a **bounded** use of the taxonomy, asking
"does this climb reach music genre," never walking upward freely. The vertical escape (`bebop -> ... ->
oscillation`) and the lateral escape (`blues -> music of North America`) are both impossible when the only
question asked of P279 is a membership test against a fixed target.

**Amendment A3 — proposed:** P279 ingestion moves to phase 6. DoD #4 is restated as: *the type filter is
bounded to a membership test against Q188451, applied to both ends of every edge, with the rejected
entities recorded by reason.*

### 1.4 DoD #6 is stricter than the invariant it is protecting

> Scope doc, DoD #6: *"The agent package was not edited to accommodate any of this."*

`CLAUDE.md` invariant 4 says **adding a tool must never require editing the loop.** But `tools.py` lives
inside `agent/`, so "the agent package was not edited" would forbid registering a new tool — which is the
one thing invariant 4 explicitly permits.

And phase 2 *will* need agent-package edits, for a reason worth naming precisely rather than discovering
mid-build. **`ApprovedClaimSet.subject_id` (`agent/loop.py:140`) returns `None` when the approved claims
do not share one subject**, and its docstring says why: *"At v0.1 every claim shares one subject."* A
multi-hop chain (`heavy metal <- blues rock`, `blues rock <- blues`) has two subjects, so `subject_id`
goes `None`, `label_of("")` returns `""`, and synthesis is handed `Genre: ` with an empty name. The
`SYNTHESIS_PROMPT` has the same single-genre framing: *"what the genre came out of."*

This is not a broken seam. It is a **correctly-scoped v0.1 assumption meeting the phase that invalidates
it**, and it is exactly the "first test of whether the seams hold" the scope doc predicted. The seam that
matters — `synthesize(claim_set)` taking one argument and having no way to reach the graph, the query, or
the rejected claims — is untouched by any of this.

**Amendment A4 — proposed:** DoD #6 becomes *"`agent/loop.py`'s `run()` and `agent/claims.py`'s `gate()`
were not edited to accommodate the corpus. Tool registrations and the multi-subject synthesis path are
expected changes and are what invariant 4 permits."*

### 1.5 Two other docs contradict this phase and need one-line fixes

Not amendments to the scope doc, but they will be wrong the moment phase 2 ships:

- **`SPEC.md` §2.2**, last row: *"It needs `GraphStore.path()`, which lands in phase 5."*
- **`graph/store.py:74-80`**, `path()` docstring: *"Declared now, implemented in phase 5."*

Both were written while `path()` was a phase-1 deferral. The ROADMAP row for phase 2 says "real multi-hop
traversal" and the scope doc's DoD #2 requires a 3+ hop path, so **`path()` belongs to phase 2.** Phase 5
consumes it for the guided tour; it does not introduce it.

---

## 2. What this phase delivers, in one sentence

Replace v0.1's 21 hand-verified edges with the full P737 corpus filtered by an automated, hardened
Wikipedia prose check, add genuine multi-hop traversal over it, and publish the result as a versioned
immutable artifact whose exclusion rate is a displayed number.

## 3. Definition of done (amended)

1. The full P737 corpus ingests locally, runs the prose check in-pipeline, and produces a versioned
   artifact, a manifest, and an **exclusions file carrying a per-edge reason for every rejected candidate**.
2. `GraphStore.path()` is implemented, and a query returns a path of **three or more** hops with a
   resolving source on every edge.
3. The artist axis answers "Who influenced Kate Bush?" end to end, from Wikidata P737 only.
4. The type filter is a bounded membership test against `Q188451` on both ends of every edge, with
   rejected entities recorded by reason. *(was: P279 boundary predicate)*
5. Phase 1's five gold cases still pass against the new pinned artifact, and the new pin is recorded in
   `PINNED_ARTIFACT_VERSION` and the manifest.
6. `run()` and `gate()` were not edited to accommodate the corpus. *(restated per §1.4)*
7. Coverage is a recorded number: corpus size, exclusion rate by tier, component count and largest
   component, and per-node era where `P571` exists.
8. The artifact is published to S3, versioned and immutable, **and still baked into the container image**
   (§4.7 explains why both).

## 4. The build

Eight steps. **Steps 1–5 are the spine; 6–8 are the tail and are the cuttable part** if the session runs
out. There is a natural checkpoint after step 5: at that point the deployed URL answers multi-hop lineage
questions over a 6x corpus, which is the phase's product value.

### 4.1 Step 1 — harden the prose check and move it into `ingest/`

New module: `src/musical_mycelium/ingest/prosecheck.py`. Stdlib only, no LLM, no cost, deterministic —
which is what lets it be a corpus filter, a displayed coverage metric, and a Tier 1 eval simultaneously
(`graph-semantics.md` §4.5).

The 7/31 scripts are at `~/mm-validation-scripts-backup-2026-07-31/` (`wikicheck.py`, `prosecheck.py`).
They are the starting point, not the deliverable — **all three known defects inflate the tier and all
three must be fixed before this runs on 351 edges:**

| Defect | Fix |
|---|---|
| Markup counted as prose (`groove metal` scored PROSE with **zero** genuine prose) | Strip `[[Category:…]]`, navboxes, external-link sections and reference blocks before counting |
| Self-match (`Western swing <- swing` scored 28 on its own title) | Mask the subject label in the article body before searching for the object |
| **Redirect collapse** (`disco house` read the *French house* article and scored confident false support) | Resolve sitelink redirects; reject or flag any subject article resolving to a different title |
| Counter-defect: exact-label matching under-accepts ("fuses rock and country") | Try label variants and aliases; accept that it errs both ways and **report the rate with an error bar rather than claiming exactness** |

**Unit tests come from the known cases, not from synthetic fixtures.** Each defect above has a real edge
that reproduces it and a known correct answer, which is the strongest fixture available.

### 4.2 Step 2 — full discovery replaces the hand-verified list

`ingest/wikidata.py` keeps its shape — **fetch, type-filter, stamp provenance, write** — which is what its
own docstring promised phase 2 would inherit. What changes is only where the candidate pairs come from:
`VERIFIED_EDGES` becomes a SPARQL discovery query over all P737 genre-out edges.

Both ends type-filtered against `Q188451`. Roughly 6% of P737 objects are not genres — `drone music <-
pedal` is a technique, `doom metal <- Black Sabbath` is a band.

`REJECTED_EDGES` grows into `exclusions.json` beside the artifact: every candidate that did not make it,
with its tier and reason. The exclusion rate is a displayed number, never a silent filter.

**Rate discipline:** 351 subject articles at 1 request/second with a contactable User-Agent, plus backoff
on 429/503. The existing `_get()` already does this. Budget ~15 minutes of wall time; it runs locally and
is not a Lambda.

### 4.3 Step 3 — the schema carries verification strength

The honest problem: v0.1's 21 edges were **hand-read**, and §4.7 measured the automated PROSE tier
over-accepting by roughly a fifth — 4 of 7 rejections failed on a gate the checker structurally cannot
apply, whether the sentence *asserts influence* rather than merely mentioning the object. `extreme metal
<- heavy metal` is the canonical case: taxonomy riding on the influence predicate, and "is a subgenre of Y"
contains a real, findable mention of Y (§4.8).

So a 160-edge machine-verified corpus is **noisier per edge** than a 21-edge hand-verified one. Pretending
otherwise would be exactly the "grounded slides into correct" failure `CLAUDE.md` forbids.

**Proposed: make it visible instead of resolving it.** `Edge` gains one field:

```python
verification: str  # "HAND" | "PROSE_AUTO"
```

The 21 phase-1 edges keep `HAND` and their record in `phase-1-edge-verification.md`. Everything new is
`PROSE_AUTO`. The manifest carries both counts, the API states them, and the measured ~1-in-4 over-accept
rate is published next to the corpus size.

This is the provenance-not-truth thesis working as designed, and it is a better interview answer than
either alternative — a silently noisy corpus, or four hours of hand-reading that does not scale past this
phase.

**Also arriving here, if the data justifies it:** `agent/claims.py:19-22` reserves a **contested** state
for "phase 2 or 6." A P737 edge whose prose *contradicts* it (`heavy metal <- classical music`, where the
article says the two are "rooted in different cultural traditions") is a genuine contested candidate rather
than a plain exclusion. If step 2 turns up a usable number of these, contested becomes a third gate
outcome; if it turns up two, it waits for phase 6. **Decided by the data, not now.**

### 4.4 Step 4 — `path()` and the component structure

`InMemoryGraphStore.path()` — BFS for the shortest sourced chain, returning `list[Edge]` so every hop
carries its own provenance. Empty list when no path exists, which is a refusal, not an error.

Direction matters and is easy to get silently wrong: `Direction.INFLUENCED_BY` walks toward ancestors.
"How is the blues connected to heavy metal?" walks **descendants** from blues, so `path()` searches the
`INFLUENCED` index. The `Direction` enum was named after the claim rather than the graph precisely to make
this hard to invert (`store.py:23-36`); the tests must still assert it explicitly in both directions.

Also computed here and written to the manifest: **component count, largest component size, and diameter.**
At the 158-edge scale that was 46 components, largest 44 genres, diameter 14 hops. Those numbers move when
the hardened checker changes the corpus, and they are the raw material phase 6 inherits.

**The connectivity constraint is real and must be stated in the product, not hidden:** "trace the lineage
between two genres" is a capability *within a component*, not a general one. Two genres in different
components have no sourced path, and the honest answer is that the graph cannot connect them.

### 4.5 Step 5 — multi-hop through the agent, without touching the loop

A third tool in `agent/tools.py`: **`trace_lineage(from_id, to_id)`**, returning the path edges plus one
`ClaimProposal` per hop. The loop harvests `result.proposals` generically and never learns the tool
exists — that is invariant 4 paying out, and it is the phase's real seam test.

Then the two v0.1 assumptions from §1.4 get fixed:

- `ApprovedClaimSet` learns to describe a **chain** rather than one subject. `subject_id` keeps its
  single-subject meaning for origins queries and gains a chain representation for path queries.
  **The constructor's guarantee does not change:** labels must still belong to endpoints of approved
  claims, and `synthesize()` still takes exactly one argument. If a change here needs `query` or `store`
  in that signature, the change is reintroducing the 7/27 leak and must stop.
- `SYNTHESIS_PROMPT` gains a chain form. Same rules — name only what is listed, no dates, no places, no
  artists, no context not in the list.

### 4.6 Step 6 — the artist axis, bounded

`SPEC.md` §2.2 assigns "Who influenced Kate Bush?" to phase 2, and DoD #3 requires it. The whole ~31k
artist-level P737 edge set is **not** the deliverable — prose-checking 31k articles at 1/second is 8.6
hours, and the artist axis has no consumer beyond one chip until phase 5.

**Bounded scope:** artists reachable from genres already in the corpus, both ends typed as human or musical
group, both ends holding an English Wikipedia article, prose-checked by the same hardened checker. Target a
few hundred edges, publish the count.

**Genre and artist stay structurally distinct axes of the same predicate.** Conflating them is the
invariant-3 failure in a different costume: "Kate Bush influenced by Peter Gabriel" and "trip hop
influenced by hip-hop" are not the same kind of assertion and must never be narrated as interchangeable.
Node type is explicit in the schema; the gate treats them separately.

**This is the step to cut first** if the phase runs long. Cutting it leaves DoD #3 open and it moves to
phase 6 with the rest of the density work.

### 4.7 Step 7 — publish to S3, keep the image copy

Scope-doc DoD #1 says the artifact lands in S3. Phase 1 baked it into the container image instead
(`ingest/wikidata.py:281-288`), for a good reason: no S3 fetch on the cold path, no IAM round trip, no
network dependency at INIT.

**Both, not either.** The image copy stays and remains what the Lambda reads. S3 becomes the versioned
immutable record: a versioning-enabled bucket in `infra/terraform/main/`, one object per artifact version,
never overwritten. That is what "pinned" means when an eval run months from now has to prove which corpus
it scored.

Cost: pennies. A few MB with versioning enabled is inside the S3 free tier and nowhere near a rounding
error against the $20 ceiling. **No new always-on resource.**

### 4.8 Step 8 — coverage as a number

DoD #7 requires era and region to be recorded quantities rather than a disclaimer. Genre nodes gain
optional `inception` (P571) and `country_of_origin` (P495) where Wikidata has them — **optional, because
absence is itself the coverage finding.** The share of nodes with no inception date is the honest measure
of how thin the early eras are.

The corpus skews Western, anglophone and recent by construction, and §3.2 of `graph-semantics.md` found it
skews further: a fair sample of the 351 is dominated by recent electronic and hip-hop micro-genres, and
**`bebop <- swing`, the edge the product was originally pitched on, is not in the corpus at all.** That
goes on the screen, not in a footnote.

---

## 5. One-way doors this phase touches

| Invariant | How it is satisfied |
|---|---|
| **1. Claims first, prose second** | `synthesize()` keeps its one-argument signature. `ApprovedClaimSet` gains a chain shape but not a new input channel. Multi-hop claims are gated per hop before any prose exists |
| **2. Provenance on every edge** | `Edge.__post_init__` already refuses to construct an unsourced row. `verification` is additive and does not weaken it. Every path hop carries its own statement URI |
| **3. Validated graph semantics** | The whole phase. P279 stays out (§1.3); P737 is known to be non-uniformly historical (§4.8) and the prose check plus the `PROSE_AUTO` label make that visible rather than assumed |
| **4. Tool contract** | `trace_lineage` is a registration. If adding it requires editing `run()`, the seam broke and that is the phase's headline finding |
| **6. Package boundaries** | `graph` must not import `ingest`; `tests/test_architecture.py` enforces it. `prosecheck.py` is ingest-side and never ships to Lambda |
| **5, 7, 8, 9** | Untouched. No Terraform change beyond one S3 bucket; no LLM, image or streaming change |

---

## 6. Testing

- **Unit:** prose-checker defect cases (each of the three known defects has a real reproducing edge);
  `path()` in both directions, including the no-path refusal and the same-node case; type-filter rejection;
  `ApprovedClaimSet` still refusing labels that no approved claim mentions.
- **Integration:** all five `SPEC.md` §2.1 gold cases against the new pinned artifact — including **case 5,
  the refusal**, which is the one most likely to silently break, because a bigger corpus may give `blues` a
  parent edge and turn a correct refusal into an answer. If that happens the gold set changes, deliberately
  and on the record; it does not get quietly re-scored.
- **Tier 1 eval rows added:** exclusion rate by tier, corpus size, component count, traversal recall on the
  gold paths, share of `HAND` vs `PROSE_AUTO` edges.
- **Metric unit tests**, including the vacuous-truth guard: an empty output must not score 100%
  groundedness.
- `make check` — format, lint, types, tests, root cap, terraform fmt+validate. CI's exact commands, run
  before any claim that this is ready to push.

**No threshold is invented here.** `.claude/rules/evals.md` forbids inventing thresholds before a baseline
exists, and phase 2 is where several of these numbers get their first measurement.

---

## 7. Cost

**$0.** No Bedrock call anywhere in this phase: the prose check is deterministic stdlib string work, and
ingestion runs locally against WDQS and the Wikipedia API. The only new AWS resource is one S3 bucket
holding a few MB.

The deployed Lambda stays on `llm_provider=local` until the Bedrock quota clears, so a larger corpus
changes the artifact the container carries and nothing about spend. Image growth from ~64MB is a few MB —
irrelevant against ECR's 500MB free allowance.

---

## 8. Genuinely uncertain — named, not smoothed over

1. **What the hardened checker actually yields.** Every fix in §4.1 removes false PROSE, so the corpus
   likely lands **below** 158, not above. If the redirect fix alone disqualifies a large share, phase 2
   could deliver a corpus not much larger than v0.1's 21. That would be a real finding about the data, not
   a failure of the phase, and it would make phase 6's second-source work urgent rather than optional.
2. **Whether `bebop <- swing`-class edges can be recovered at all** from Wikidata. If not, the product's
   most quotable example stays unavailable until a second source lands.
3. **Whether a 3+ hop path exists after re-filtering.** Today's known chain is `blues -> blues rock ->
   heavy metal music` — **two hops**, because `extreme metal <- heavy metal` was rejected as taxonomic.
   DoD #2 asks for three. The 44-genre largest component had 14-hop traversals at the 158-edge scale, so
   this is probable, not certain, and it depends on step 1's output.
4. **Whether contested has enough data to become a real gate state** (§4.3).
5. **Whether the artist axis fits in this phase at all.** It is the declared cut (§4.6).

---

## 9. Approval needed before any code

Four scope-doc amendments — **A1** (corpus numbers), **A2** (MusicBrainz to phase 6), **A3** (P279 to
phase 6), **A4** (DoD #6 restated) — plus the two cross-doc fixes in §1.5, plus the `verification` field
in §4.3.
