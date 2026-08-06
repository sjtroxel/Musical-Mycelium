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

### Build log — updated 2026-08-04, end of day

**Steps 1–3 are built and committed. Step 4 is next.** Where the plan below turned out to be wrong, the
correction is recorded here rather than by editing the plan, so the two stay comparable.

| step | state | what the plan did not predict |
|---|---|---|
| 1 | done | groove metal had 6–7 genuine prose sentences, not zero; `groove metal <- thrash metal` was a **false rejection** |
| 2 | done | the population is **351 → 138 accepted**, not 158; redirect collapse was **8% of the corpus**; the derived-stem rule scored 0 true / 3 false and was deleted |
| 3 | done | the hand-rejection list is **load-bearing** — the check re-admits 6 of the 7; corpus ships at **133**, not 138 |
| 4 | done 2026-08-05 | **the corpus is broad and shallow: the deepest chain `path()` can return is 2 hops, so DoD #2 is not satisfiable from P737** |
| 5 | done 2026-08-05 | **the signature query refused when worded the way the SPEC words it** — 32 of 169 labels carry a trailing "music" |
| 6 | **replanned 2026-08-05, not built** | §4.6 assumed the prose check transfers to artists. It half-does — see 6a |
| 6a | **built + training-measured 2026-08-05** | the filter exists and scores 98% precision / **80% recall**. The recall gap is the finding: **EXPOSURE has no lexical signature** |
| 6b | **NEXT — blocked on one decision** | settle the EXPOSURE tier, *then* label the 35 sealed held-out rows and get the real number |
| 6c | blocked on 6b | the artist ingest itself |

Three plan assumptions that did not survive contact:

1. **§4.2 budgeted ~15 minutes of crawl for "351 subject articles."** The crawl is per *subject*, not per
   edge — 331 candidates cost ~114 article fetches, about 3 minutes. Re-running the checker is therefore
   cheap, which is what made the stem-rule decision measurable rather than arguable.
2. **§4.3 said "the 21 phase-1 edges keep `HAND` and everything new is `PROSE_AUTO`."** Incomplete: it did
   not say what happens to the seven hand *rejections*, and the automated check accepts six of them.
   `select_edges` applies both lists as an override. It is 22 `HAND` now, not 21.
3. **§4.3's contested question resolves to "the data cannot decide it."** Contested means prose
   *contradicting* an edge, and the prose check structurally cannot tell contradiction from support, so
   the screening produces no count to decide on. Deferred to phase 6 for that reason, not for lack of
   appetite.

Adding a field to `Edge` also forced a corpus cutover in one commit: the pinned artifact had no
`verification` key, so the field, the rebuild, `exclusions.json`, the `PINNED_ARTIFACT_VERSION` bump and
the gold-set re-pin all had to land together or the runtime would load a corpus its schema rejects.

#### Step 4 found a problem with the phase, not with the code — DECISION OWED

**`path()` works. The corpus cannot feed it.** Measured over v0.2.0 (`docs/graph-semantics.md` §5.1):
133 ordered pairs are one hop apart, **13 are two hops apart, and none are three or more.**

§4.4 above assumed the diameter *was* the available path depth — it quoted "diameter 14 hops" as the
raw material for traversal. That conflated two different measurements. **Diameter ignores edge
direction; a path must follow it.** Recomputed over v0.2.0 the diameter is 10 and the deepest directed
chain is **2**. The error was in the plan, not in the ingestion: the discovery query is already global
over every genre carrying a P737 statement, so there is no frontier left to crawl. Wikidata's
genre-level P737 is simply flat.

**So DoD #2 — "a multi-hop query returns a path of three or more hops" — cannot be met by this phase as
scoped.** Three ways forward, and this is sjtroxel's call:

1. **Amend DoD #2 to two hops and publish the flatness.** Cheapest and most consistent with the
   project's thesis: the honest claim becomes "the corpus supports 2-hop lineage, here is the measured
   reason, here is what would deepen it." `structure` is already on `/health`, so the limit is stated
   rather than hidden. Costs nothing and gives up the headline "multi-hop" demo.
2. **Get depth from the artist axis (steps 6–8).** Artist-level influence is far denser than
   genre-level, and chaining artist edges through their genres is where three-hop lineage plausibly
   exists. This is the real fix and it is already in the phase, currently marked cuttable. It stops
   being cuttable if DoD #2 stands.
3. **Add a second genre-level predicate.** P279 is banned as taxonomic and that is a one-way door
   (invariant 3), so this means a *new* source, not a new Wikidata property. Largest scope, and it is
   phase 6's job, not this phase's.

**Recommendation: 1 now, 2 as the phase's stretch.** Amending a DoD because the data said so — with the
measurement written down — is the project working as designed. Quietly reporting a 2-hop path as
"multi-hop" is the failure mode `CLAUDE.md` names.

> **DECIDED 2026-08-05: option 1.** DoD #2 is amended in the scope doc as **A5**, which is where the
> measurement and the diameter-versus-depth error now live, because the scope doc is what the phase is
> judged against. The flatness ships as `structure` on `/health` and the `done` frame. **The artist axis
> stays in steps 6–8 and stays cuttable** — it is the identified route to depth, not an obligation, and
> if it is cut the honest claim is a two-hop corpus with the reason published.

Two corpus properties the plan also assumed away, both now asserted in tests rather than hoped for: the
graph **contains a cycle** (`post-rock` and `shoegaze` cite each other under P737, so it is not a DAG),
and **same component does not imply a path** (a shared ancestor connects two genres undirected while
leaving no directed chain either way).

One deviation from §4.4 worth flagging: it said the structure numbers are "written to the manifest."
They are — `build_manifest` derives them for every future build — but **v0.2.0's own manifest was not
rewritten**, because artifacts are immutable and rewriting one under the same version is precisely what
the pin exists to prevent. The store recomputes structure at load instead, which is strictly better: it
cannot drift, and it works on an artifact built before the field existed.

#### Step 5 shipped, and running it found three things the plan did not

`trace_lineage` landed as a registration — `default_registry` gained one entry and no branch of the loop
names it, which is invariant 4 paying out on its first real test. 269 tests, `make check` green, root
15/18. Four things are worth recording because the plan did not anticipate them.

**1. The seam had a prose door as well as a code door.** §4.5 said a third tool must not require editing
the loop. It did not — but v0.1's `SYSTEM_PROMPT` hard-coded the procedure, *"use resolve_genre, then
get_influences"*, so a tool could be registered without a loop edit and still never be called. The prompt
now states rules rather than a tool sequence, and `test_the_system_prompt_names_no_tool` asserts that no
registered tool name appears in it. The tools describe themselves in their own `toolSpec`.

**2. Visit order is not descent order, and the `path` frame was quietly conflating them.** A lineage
question resolves both endpoints *before* it traces between them, so the walk for "how is the blues
connected to heavy metal" opens `blues, heavy metal music, blues rock` — a client drawing arrows down
that list states the descent backwards. The approved chain now rides as its own field
(`chain`, `chain_labels`), empty for an origins query and empty when any hop was rejected. This is the
same distinction `graph/structure.py` drew between undirected components and directed paths, one layer
up. Found by running it, not by reading it.

**3. The signature query in `SPEC.md` 2.2 refused when typed verbatim.** "How is the blues connected to
heavy metal?" — `the blues` resolves, `heavy metal` does not, because the node is labelled *heavy metal
music*. **32 of the 169 nodes carry that suffix**, so roughly one node in five was unreachable by its own
name. `label_key` makes a trailing "music" optional on both sides; it produces **zero** collisions across
v0.2.0, checked before it was written, and two nodes agreeing under it is a refusal rather than a coin
flip. It is the same category of rule as the existing leading-"the" strip, and the near-miss tests
(`metal`, `blues r`) still refuse.

**4. `MAX_TURNS` went 4 to 5.** A lineage answer needs three tool turns plus a text turn, which consumed
the entire v0.1 budget and left a real model no room to recover from one bad argument.

Two decisions inside step 5 that are worth defending rather than assuming:

- **`ToolResult` gained a generic `chain` field, and that *is* a loop edit** — a small honest one. The
  loop reads `result.chain` the way it already reads `result.visited`, without naming a tool, so the seam
  holds; but the mechanism had to be added once. Inferring a chain from the approved claims instead was
  the alternative and it is worse: four sibling influences would infer as a line of descent.
- **`trace_lineage` searches both directions and reports the chain descendant-first.** The same question
  arrives with the arguments in either order, and the model should not have to guess which. This is safe
  only because a proposal is built from the **edge**, never from argument order, so a reversed query
  cannot manufacture a reversed influence claim — `test_the_reversed_question_finds_the_same_chain_
  without_inverting_it` is the assertion that keeps it true.

The local provider also had to learn the lineage script (resolve, resolve, trace), because
`llm_provider=local` is what the deployed URL runs while Bedrock is at zero — without it there would be
nothing multi-hop to redeploy. `LocalLLM`'s docstring says to delete rather than extend it if it starts
making decisions a real model should make; a second fixed script sequenced off the calls already made is
still a fixture, but it is now two scripts away from that line rather than one.

**Redeploy is now owed for two steps** (step 4's `structure`, step 5's chain and third tool).

#### Step 6 was replanned before it was built, on measurements — 2026-08-05

**Nothing was ingested.** Every number below came from bounded measurement runs, which is the whole
reason the step was replanned instead of debugged after the fact.

**What §4.6 got right.** The bound works and the population is real: **4,549 distinct artist-subject
P737 statements** where the artist's `P136` is one of the 169 corpus genres, of which **4,426 have an
artist object**. The pipeline reuses `discovery`'s stages unchanged — only the query and the type test
differ — and `Candidate.object_is_genre` was renamed `object_in_axis` so the artist axis could reuse it
without the field name being a lie.

**What §4.6 got wrong, and it is the load-bearing assumption.** It planned to prose-check artist
articles "by the same hardened checker" and treated that as settled. It is not. On a 300-candidate
slice: **123 NO_ARTICLE, 100 ORPHAN, 73 PROSE, 4 REDIRECTED** — a 24% acceptance rate that looks
perfectly healthy and is mostly junk. The five accepted edges that make the point are quoted in the
scope doc's **A6**; the short version is a recording truck, an English pronoun, a cover version, a
support slot and a membership list.

**Three requirements, where the plan assumed one.** Reading the accepted evidence, an artist edge needs
all of:

1. **A name match** — exists today, but needs a guard for names that are common English words. `Them`
   is a real band and `find_mentions` cannot currently tell it from the pronoun.
2. **Influence language in the same sentence.** Measured on the 73 accepted: **49 (67%) contain an
   influence cue, 24 (33%) contain none at all.** So a cue requirement removes a third of the
   accepted set immediately.
3. **The asserted direction matching the edge direction.** This is the hard one and it is why a cue
   rule alone is *necessary but not sufficient*. `Deep Purple <- Led Zeppelin` survives the cue test on
   *"Deep Purple are **cited** as one of the pioneers of hard rock and heavy metal, along with Led
   Zeppelin and Black Sabbath"* — influence language, zero assertion about Led Zeppelin influencing
   anyone. They are listed as peers.

**Whether requirement 3 can be met deterministically is the open question of this step, and it is
allowed to answer no** (scope doc A6). "This needs a model in the loop" is a publishable finding, not
a failure — but it would be a finding about a Tier-1 filter that is currently free and deterministic,
so it is a real architectural fork rather than a detail.

**Four defects found by hand-labelling, three of them in this project's own code.** Every one was
surfaced by sjtroxel reading evidence and asking why it looked wrong, and none would have been found by
running the pipeline and inspecting counts:

| defect | how it surfaced | fix |
|---|---|---|
| **sentences truncated at abbreviations** | *"…all became friends of C."* — the splitter cut at the initial in **C. L. Franklin**, leaving a row nobody could label | `_NON_TERMINAL_ABBREVIATIONS` + `split_sentences`. **The list is never complete**: `Sgt.` was missing on the first pass and truncated *Sgt. Pepper* mid-title on the one article where the rest of that sentence was the whole case |
| **section headings served as prose** | `==== 1964 world tour, meeting Bob Dylan ====` was handed over as a supporting sentence | `_HEADING_LINE_RE`, applied after the appendix truncation, which needs the headings to find where prose ends |
| **only the first matching sentence was used** | he asked whether Sam Ryder's article mentioned Elton John anywhere else. It did — *"cites … Elton John … among his music influences"*, the opposite of the shown sentence's meaning | `classify_all()` takes the strongest verdict across all sentences. **38% of accepted edges have more than one** |
| **mislinked entity** (upstream, not ours) | see below | `sitelink_matches_subject` |

The third one is the reason the first conclusion was wrong, and it is worth stating plainly: **a
sampling artifact in the evidence display produced a false finding about the data**, and it survived
until a human read the underlying article. Counts and rates would never have caught it.

**A defect found on the way, and it is a keeper regardless of how the filter turns out.**
`Tier.MISLINKED`: Wikidata's `Q58462848` is labelled **TheGrefg** and its English sitelink points at the
**Lola Índigo** article. Real collaborators, two different people, confirmed independently. The redirect
guard structurally cannot see this — the sitelink resolves cleanly, so requested and resolved titles
agree, and the divergence is between the entity's *label* and its *link*. Worse, `check_edge` folds the
sitelinked title into the subject's own names, so the wrong person's name gets **masked out of the
search as though it were the subject's**. Fixed by `sitelink_matches_subject`, which runs before the
name variants are built, errs toward flagging, and checks curated aliases so a stage name is not
mistaken for a mislink. It applies to the genre axis too; genre labels and sitelinks nearly always
agree, which is why the genre axis never surfaced it.

**Two measurement corrections worth keeping.** The pre-build estimate of **10,504 in-scope outgoing
statements was inflated** — `COUNT(*)` over a `?s wdt:P136 ?corpusGenre` join multiplies a row per
matching genre, so an artist in three corpus genres counted three times. The distinct figure is 4,549.
And **WDQS timed out on three separate heavier queries** during this step, so the incoming direction's
article count is still unmeasured and nothing should be planned against it.

**Direction asymmetry, measured.** Kate Bush — the artist `SPEC.md` 2.2 names — has **zero outgoing
P737** and **44 incoming**. The scope doc's DoD #3 says "at least one artist-influence query" rather
than naming her, so this needs no amendment; but any demo built on her must run descendant-first, which
step 5's `trace_lineage` already supports.

---

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

> **REPLANNED 2026-08-05, before any ingest.** Everything below the horizontal rule is the original
> plan and is kept for comparison, as this doc does with every falsified assumption. Its fatal line is
> "prose-checked by the same hardened checker" — measured, that produces a corpus of recording trucks
> and pronouns. Step 6 is now **6a, the influence-assertion filter**, then **6b, the ingest**.

#### 6a — the influence-assertion filter

**The question, stated so it can come back "no":** can "this sentence asserts that X was influenced by
Y" be decided deterministically, at Tier-1 cost, well enough to build a corpus on? Scope doc A6 makes a
measured no a publishable outcome.

**Ground truth first, and it is not optional.** The derived-stem rule died on 2026-08-04 because it was
finally measured — zero true positives, three false. The same trap is open here and wider, because a
cue list is easy to write and feels obviously right. So:

1. **A hand-labelled sample of ~100 candidate artist edges**, drawn from the 300-slice already crawled
   (73 accepted, plus ORPHAN cases so recall is measurable and not just precision). Each labelled
   **ASSERTS / DOES NOT**, by hand, against the actual sentence. Nothing is built until this exists.
   The sample is committed, because a filter measured against a sample nobody can re-inspect is a
   number with no provenance.
2. **He labels, or confirms proposed labels with the sentence in view.** Not me alone: a filter tuned
   against labels the tuner invented measures agreement with itself.

**Then the filter, in three parts, each measured separately against that sample** so it is knowable
which part earns its place:

| part | rule | the failure it targets |
|---|---|---|
| **common-word name guard** | a name that is a common English word must match **case-sensitively** | `Them` matching the pronoun "them" |
| **cue requirement** | the supporting sentence must contain influence language | the truck, the cover, the support slot, the membership list |
| **direction test** | the assertion must run **subject influenced-by object**, not the reverse and not peer co-mention | `Deep Purple <- Led Zeppelin` from "*cited as pioneers … along with Led Zeppelin*" |

**Report precision and recall as a pair, always**, for the same reason refusal accuracy is reported as
a pair (`.claude/rules/grounding-and-claims.md`): a filter that rejects everything scores perfectly on
precision and is useless. **No threshold is invented before the baseline exists**
(`.claude/rules/evals.md`).

**The honest risk, named rather than smoothed over:** part 3 is the one that decides this. Parts 1 and
2 are pattern work and will improve precision. Direction is a **semantic** judgment, and English
expresses it in ways a sentence-level pattern will struggle with — "*X, an influence on Y*" and
"*X, influenced by Y*" differ by one word and invert the claim. If the direction test cannot reach
usable precision, the fork is: an LLM in the ingest path (offline, one-time, not in the agent loop —
so it does not touch Tier-1 eval cost or the deterministic gate), or the artist axis ships as
**flagged-and-separate** rather than as claim-grade edges, or it moves to phase 6 with the measurement
published. **That decision is his, and it should be made on the measured number rather than in
advance.**

#### 6a — WHERE IT ACTUALLY LANDED, 2026-08-05

Built, and measured against the gold set. **The plan above was right that a filter was needed and wrong
about which half of the problem was hard.**

**The first conclusion was overstated and is corrected in scope doc A6.2.** It rested on judging each
edge by one supporting sentence, and **38% of prose-accepted artist edges carry more than one** (one
carries sixteen). Re-labelled on full evidence the sample is **43 ASSERTS / 12 EXPOSURE / 5 NO**, so
the prose check accepts something genuinely supported **92%** of the time and the junk rate is **8%**,
not the ~25% first reported. `classify_all()` now takes the strongest verdict across all sentences,
which is the correct unit; `classify()` alone is not.

**Measured against the corrected labels — a TRAINING number, since the patterns were derived from this
same set:**

| | |
|---|---|
| keep-vs-drop precision | 98% |
| keep-vs-drop recall | **80%** |
| three-way exact agreement | 72% |
| `ASSERTS` recall specifically | 81% |

**The result that matters is the shape of the errors, not the headline.** One false positive; eleven
false negatives. Every false negative is the same thing: an edge sjtroxel labelled `EXPOSURE` under the
rule that **collaboration, touring together, covering a song and shared presence all count**. Wu-Tang
as guest stars; Mahalia Jackson in the Franklin household; a Big Star cover; Cartel on a tour; a Kanye
verse; twelve sentences of Stones-versus-Beatles rivalry.

> **`ASSERTS` is detectable. `EXPOSURE`, as defined, is not.** Influence assertions use a bounded
> vocabulary — *influenced, inspired, cited, credits, idol*. Proximity does not: *"guest stars on the
> album included"* and *"took turns helping with the children"* mean the same thing to a reader and
> share nothing a pattern can see. Proximity is a semantic category about human relationships, not a
> linguistic one, and no cue list will close that gap.

#### 6b — the decision, then the held-out number. **THE NEXT SESSION'S WORK.**

**The 35 unlabelled held-out rows are sealed and must stay sealed until the decision below is made.**
Labelling them under a standard that is about to change spends a set that can only be spent once.

**The decision, and it is a product decision as much as a technical one** — it sets what "grounded"
means on the artist axis:

1. ~~**Ingest `ASSERTS` only**, dropping `EXPOSURE` as un-automatable.~~ **RULED OUT 2026-08-05 by
   sjtroxel: the exposure tier is necessary even though it is hard to define. Do not re-propose it.**
2. **Narrow `EXPOSURE` to its lexical core** — *listened to, fan of, grew up with, discovered* — and
   put collaboration and proximity out of scope entirely. Keeps a tier, at the cost of a definition
   narrower than the one A6.1 recorded, which means A6.1 gets amended and the 60-row gold set gets
   re-labelled against the narrower rule.
3. **An LLM in the ingest path, for the `EXPOSURE` tier only.** Offline, one-time, local — never in the
   agent loop, so invariant 1, the deterministic gate and Tier-1 eval cost are untouched. It would need
   validating against this same gold set, which is why the labelling was worth doing either way.
4. **Keep the broad definition, accept the under-catch, and publish the miss rate.** No amendment, no
   re-label, no spend: ingest what the patterns reach and state plainly that proximity expressed in
   ways a pattern cannot see is missed. **This is the option most in keeping with how this project has
   handled every other limit** — `max_path_hops`, the `HAND`/`PROSE_AUTO` split, the exclusion rate —
   all published rather than hidden. It is also the cheapest, and it leaves 2 and 3 available later.

Then, and only then: label the 35 sealed rows under the settled standard, and measure. **That number
is the one that decides whether 6c happens at all**, and it is the first non-training figure this
filter will have.

#### 6c — the ingest, unchanged in shape

Only reachable if 6b's held-out number holds up. Then: the bounded population from the original plan
below, run through prose check **and** filter, `verification` recording which tier each edge cleared,
`Node.kind` separating the axes, and the gate refusing cross-axis claims. Publish the counts at every
stage — discovered, on-axis, prose-accepted, filter-accepted — because the drop from 4,549 to whatever
survives *is* the finding.

> **6c STARTED 2026-08-06. The held-out number held (A6.5), so the axis is cleared for ingest.** The
> work splits into a deterministic half that touches no network and no spend, and a batch half that
> does. The deterministic half is **DONE**:
>
> | | | |
> |---|---|---|
> | 1 | `Node.kind`, required, two values | **DONE** — `graph/schema.py`, decision recorded as scope-doc A6.7 |
> | 2 | v0.3.0 by stamping, no refetch | **DONE** — 169 nodes / 133 edges, structure identical to v0.2.0 |
> | 3 | the gate refuses cross-axis claims | **DONE** — `RejectionReason.CROSS_AXIS` in `agent/claims.py` |
> | 4 | the artist ingest itself | **DONE** — crawled 2026-08-06, v0.4.0 written; counts below |
> | 5 | `workflow_dispatch` redeploy | **DONE** — run 31128726969, 2026-08-06; `/health` serves 0.4.0 |
>
> `make check` green at **290 tests**, up from 269. Pins moved together and must stay together:
> `ingest/wikidata.py` `ARTIFACT_VERSION`, `graph/memory.py` `PINNED_ARTIFACT_VERSION`, and
> `eval/datasets/gold_v0_1.json` `artifact_version_pin` — `tests/test_graph_store.py` asserts the first
> two agree and `tests/test_gold_set.py` asserts the third matches what the suite loads.
>
> **Step 3 landed before step 4 on purpose.** The gate is the thing that makes a cross-axis edge
> unnarratable; putting it in before any artist data exists means the artist ingest cannot quietly
> introduce one during development.
>
> **Deploy note — RESOLVED 2026-08-06.** The live Lambda reads an artifact baked into its image, so it
> served v0.2.0 until redeployed. Run **31128726969** (`llm_provider=local`, `reserved_concurrency=-1`,
> both passed explicitly so CI could not take `main/variables.tf`'s defaults) went green, and `/health`
> now reports `artifact_version 0.4.0`, 973 nodes, 950 edges, all four verification tiers.
>
> Verified live rather than assumed: `?q=U2` resolves `Q396` and returns six gated claims, each citing a
> real Wikidata statement URI. **The artist axis is in production.**
>
> **Two copy defects the axis exposed — both FIXED same day, 2026-08-06, before the first Bedrock call.**
>
> **`resolve_genre` → `resolve_node`, and the payload now carries `kind`.** The rename was the smaller
> half. The real defect was that the tool returned `{node_id, label}` and nothing else, so a model could
> resolve "U2", hold an artist, and have no way to know it — then propose a genre-to-artist claim, get
> `CROSS_AXIS` back from the gate, and burn a turn on a rejection it had no information to avoid.
> **The gate is the enforcement; `kind` in the payload is what lets the model cooperate with it instead
> of discovering it by failing.** The description now names both axes and states the same-kind rule
> outright, and `test_the_tool_contract_tells_the_model_both_axes_exist_and_must_not_be_mixed` pins that
> text — it is the only thing about this tool a real model ever reads.
>
> **Timing was the argument for doing it immediately rather than filing it.** Changing a tool's name,
> description, or return shape after Bedrock works invalidates any eval baseline that measured tool-use
> behaviour. No such baseline exists yet, because no real model has ever run. The change cost 33
> mechanical references and one `make check`; in three weeks it would have cost a re-baseline.
>
> **The refusal strings are axis-neutral now** — they said "the genre is not in this graph", which on a
> query for `U2` denied the existence of a genre nobody had asked about.
>
> 316 tests.
>
> ---
>
> #### 6c.4 — the crawl, 2026-08-06. **The drop is the finding, so here is every stage of it.**
>
> One WDQS query bounded by the 169 corpus genres, then ~1,200 Wikipedia article fetches at the
> mandated 1/second. About 25 minutes, $0, no Bedrock.
>
> | stage | count | what removed the rest |
> |---|---|---|
> | discovered | 4,555 | distinct subject-object P737 pairs |
> | on-axis | 4,432 | 123 `NOT_AN_ARTIST` — P737 objects include genres, works, labels |
> | prose-accepted | 1,320 | 1,422 `NO_ARTICLE`, 1,611 `ORPHAN`, 42 `REDIRECTED`, 37 `MISLINKED` |
> | filter `ASSERTS` | 777 | |
> | filter `EXPOSURE` | 57 | |
> | filter `NONE` | **486 refused** | **the number that says what 6a was worth** |
> | build-time drops | 17 | 14 `NO_LABEL`, 3 `UNCITABLE_STATEMENT` |
> | **ingested** | **817 edges / 804 nodes** | 760 `ASSERTS_AUTO` + 57 `EXPOSURE_AUTO` |
>
> **486 edges cleared the prose check and the filter threw them out** — 37% of everything prose
> accepted. Without 6a those would be in the corpus right now, cited as influence. That is the
> justification for the whole 6a/6b detour, measured rather than argued.
>
> **v0.4.0: 973 nodes, 950 edges.** Verification counts `{HAND: 22, PROSE_AUTO: 111, ASSERTS_AUTO: 760,
> EXPOSURE_AUTO: 57}`.
>
> **THE STRUCTURAL RESULT — `max_path_hops` went from 2 to 6.** Step 4 found the genre axis could not
> supply depth and said so in a test: *"the depth has to come from somewhere other than P737 among
> genres."* The artist axis is that somewhere. Largest component 31 → 458, diameter 10 → 16, components
> 41 → 169. `tests/test_structure.py::test_the_depth_arrived_with_the_artist_axis` records both halves
> so neither the old finding nor its overturning is lost.
>
> **Two defects the crawl surfaced, both now enforced in code rather than remembered:**
> - **14 endpoints with no English label** — row 41's evidence-inheritance defect at scale. An early
>   `artist_rows` *raised* on the first one, which would have thrown away 834 good edges over 14 bad
>   endpoints, on input that costs a 20-minute crawl to regenerate. Now excluded and reported.
> - **3 edges whose statement URI does not name their subject.** `agent.claims.resolve_sources`
>   resolves a citation by exactly that match, so these would have sat in the corpus present in every
>   count and absent from every answer. Refused at build time.
>
> **A Wikidata error worth keeping as the honest example:** `AC/DC <- Airbourne` is ingested, and the
> supporting sentence says AC/DC were among the influences *on* the next generation. The edge points
> the wrong way in Wikidata itself. It stays, with its citation, because grounded means traceable and
> not true — this is that distinction with a name attached.
>
> **Known gap, deliberately not closed today:** artist nodes carry no `revision_id`. Genre nodes pin the
> exact Wikidata revision read; artists do not, because the build reads labels off the crawl rather than
> re-reading entities. `wikidata.fetch_entities` would supply them but front-loads a SPARQL query with
> 800+ `VALUES` bindings purely to compute a genre-ness flag the artist axis discards, which is a heavy
> ask of a degraded WDQS. `tests/test_artifact.py::test_manifest_records_a_revision_for_every_node` is
> written to **fail the day this is fixed**, so it cannot be quietly forgotten.

---

*Original §4.6, superseded above. Kept because the comparison is the point.*

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
