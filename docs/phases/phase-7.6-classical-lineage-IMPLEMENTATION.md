# Phase 7.6 — Classical Lineage (v0.9) — IMPLEMENTATION

> **As-built plan.** Written 2026-09-11, immediately after the scope doc `phase-7.6-classical-lineage.md`
> was approved, against code read and measurements taken the same day rather than recalled.
> **APPROVED 2026-09-11 by sjtroxel** ("approved and cleared for takeoff"), with two changes of his
> folded in before approval: mixed chains with typed hops (D4), and influence questions also checking
> teachers (D5).
>
> Steps are marked `[done]` as they land, and each gets an as-built subsection recording where reality
> disagreed with this plan. The doc is allowed to be wrong. It is not allowed to be silently wrong.
>
> **Three things a cold session must not get wrong, before anything else:**
> 1. **The new artifact is v0.10.0 and it follows v0.7.1 on purpose.** Not a typo; `ROADMAP.md` §2
>    under the version table has the reasoning. Compare versions numerically; as text "0.10.0" sorts
>    before "0.7.1".
> 2. **Typing "mozart" into the site will still refuse when this phase ends.** Resolution needs an exact
>    full label. Phase 7.7 fixes that. It is not a 7.6 defect.
> 3. **This phase does not deploy and does not run the live re-baseline.** Both happen once, at phase
>    7.7's close (his decision, 2026-09-11). The public site stays on v0.7.1 until then.

## 1. What this phase delivers, in one sentence

**Artifact v0.10.0, with the Wikidata `mul` label bug fixed, a hand-validated `studied_with` predicate
from P1066, birth years and aliases on artist nodes, and a gate, tools, prose and UI that can say
"Beethoven studied with Haydn" and structurally cannot say it as influence.**

### 1.1 Definition of done

Restated from the scope doc as amended on 2026-09-11, so it cannot be skipped:

1. Wolfgang Amadeus Mozart is in the corpus, and so is every entity the `mul` bug excluded that passes
   the rest of screening. A test fixes a `mul`-only entity and asserts it gets its label.
2. P1066 was hand-checked on a sample **before** ingestion, with findings recorded in
   `docs/graph-semantics.md` the way P279 and P136 were.
3. "Who did Beethoven study with?" returns a gated, cited answer that says "studied with", verified in
   the running app against the local stub and in one live capture.
4. A test asserts that no prose path narrates a `studied_with` claim as influence, including on a claim
   set that mixes predicates.
5. `verification` and `corroboration` remain two fields, and no verification tier means two different
   things.
6. Artist nodes carry a birth year where Wikidata has one, and the coverage panel and the report's era
   slice show what the corpus holds by birth before 1900, with its skew stated.
7. The free scripted gates read **4 passed, 0 failed, 2 not applicable, of six**, and no live result on
   v0.10.0 is reported as gated before phase 7.7's re-baseline.
8. v0.10.0 is built and deployable: the Lambda image builds and serves it locally. `make check` is
   green, every asset budget holds, and the repo root is inside its cap.
9. `agent/loop.py` is unmodified, or the edit is a finding recorded in bold here. **It will be edited;
   see §3.2. That is recorded now, before the build, not discovered during it.**

## 2. Baseline, measured 2026-09-11, not recalled

On a clean tree at `2b1eb02`, plus the uncommitted doc and footer edits of the same morning.

| measurement | value | how |
|---|---|---|
| Python suite | **1556 passed**, 14 deselected | `make check` |
| mypy | clean over **112** source files | `make check` |
| Frontend suite | **429 passed** across 23 files | `make check` |
| Repo root | **17 of 18** | `make check` |
| Scripted eval gates | **4 passed / 0 failed / 2 N/A** of six | `make check` |
| Asset budget | script **277.4 KB of 320**, graph **2.57 MB of 3.00**, report 46.5 of 64, style 11.5 of 40, shell 10.0 of 32, media 0 of 0 | `make check` |
| Artifact pin | **0.7.1**: 1,479 nodes (675 genres, 804 artists), 5,066 edges | `graph.json` |
| Edges by predicate | `influenced_by` **2,284**, `plays_genre` **2,782** | `graph.json` |
| Artists with any date | **0 of 804** | `graph.json` |
| Datasets | gold **38**, adversarial **20**, live **56**, tour **6** | dataset files |
| Held-out | sealed, pinned **0.5.0**, run count **1** | not opened |
| Graph file size | **2,694,624 bytes**, about 410 bytes per node or edge | `ls` |
| Backdrop inlined in the bundle | **35,918 bytes** | `web/src/graph/backdropData.ts` |

**Wikidata, measured live the same day** (read-only queries; see scope doc §0):

| population | count |
|---|---|
| entities that came back unlabelled but have an English article (`mul` bug) | **44**, touching 92 exclusion rows |
| composers born before 1880 with an English article | 9,212 |
| of those, with any P737 (`influenced by`) | **56** |
| of those, with P1066 (`student of`) naming another composer | **1,766** |
| **bound A**: composer students born before 1900, composer teachers, both with an English article, deprecated statements excluded | **3,606 statements, 2,035 students, 1,319 teachers** |
| bound B: the same with any musical occupation | **not measured**: the query service timed out twice. Step 3 measures it in chunks. |

## 3. What the code reading found — every trap, with its location

This section exists because the user asked that nothing be left open for mistakes. Each item is a
place where the obvious implementation is wrong. Each has a step that fixes it and a test that proves
the fix.

### 3.1 Traps that would silently pass the wrong thing

1. **The gate cannot see a `studied_with` edge even after the predicate is allowed.**
   `agent/claims.py:_find_edge` calls `store.neighbors(...)` with no `predicates` argument, and the
   store's default is `INFLUENCE_ONLY` (`graph/schema.py:60`). Adding the predicate to
   `ALLOWED_PREDICATES` alone would reject every teaching claim as `NOT_IN_GRAPH`. **Fix:** `_find_edge`
   passes `predicates=ALLOWED_PREDICATES`. Step 7.
2. **The groundedness metric has the same blind spot.** `eval/metrics.py:_matching_edge` (line 137) uses
   the same default, so a correct teaching claim would score as **ungrounded** and fail the 100% gate.
   **Fix:** the same widening, from the same constant, so the gate and the metric cannot disagree about
   what exists. Step 9.
3. **Prose picks its verb from the axis, never from the predicate.** `agent/loop.py:synthesize` chooses
   between "came out of" (genre) and "was influenced by" (anything else). An artist-to-artist teaching
   claim would be narrated **"Beethoven was influenced by Haydn"**: fluent, cited, and false as stated.
   Every grounding metric would score it perfectly. **Fix:** step 7, §3.2.
4. **The "your question had it backwards" logic treats every approved claim as influence.**
   `loop.py:descent_is_approved` walks all approved claims subject-to-object. A teaching claim could
   "establish" the reverse of an influence premise, and the answer would then correct the user's
   question with a claim the gate never approved as influence. **Fix:** the premise check reads
   `influenced_by` claims only. Step 7.
5. **A chain could mix predicates without saying so.** `loop.py:chain_is_approved` checks pairs, not
   predicates, and `ApprovedClaimSet.chain` is node ids only, so a mixed chain would reach synthesis with
   one verb for every hop. **Fix:** mixed chains are allowed (his decision, D4) with **typed hops**: each
   hop's predicate is read off its approved claim and handed to synthesis beside the hop. Step 7.
6. **The frontend would show teaching as influence or as membership.**
   - `web/src/components/ClaimList.tsx:65` hardcodes the words " influenced by " on every claim.
   - `web/src/graph/subgraph.ts:224-227` stamps every claimed edge as `influenced_by` and says so in a
     comment ("the gate approves nothing else"), which stops being true in this phase.
   - `web/src/graph/GraphView.tsx:469` draws **anything not `influenced_by` in the membership style**, so
     a teaching line would look like "plays genre".
   - `web/src/components/NodeInspector.tsx:44-51` sorts incident edges into influence and membership
     only; teaching edges would vanish from the inspector.
   **Fix:** step 8, each with a test.
7. **The live gate never checks the corpus version.** `eval/thresholds.py:ThresholdSet.matches` keys on
   dataset and provider, and `_ungateable` checks completeness and case count. A live run on v0.10.0
   over the same 56 cases would be graded against bounds measured on v0.7.1 and could print "pass".
   Phase 7.5 step 2 already noted "the gate never checks the corpus pin". **Fix:** a fourth `_ungateable`
   condition: when a threshold set records the artifact its bounds were measured on
   (`thresholds.json:22`, live set only), a run on any other artifact is not gated, with the reason in
   words. The scripted set records no artifact and stays gated. Step 0.
8. **Refusal wording asserts influence.** `loop.py:REASON_NO_INFLUENCES` and
   `_graph_holds_influences` speak only of influence. A refused teaching question would say "this graph
   holds no sourced influences", which answers a question nobody asked. **Fix:** step 7.

### 3.2 The `loop.py` edit, recorded in bold before the build, as scope doc DoD 9 requires

**`agent/loop.py` will be edited in this phase, and the reason is prose, not dispatch.** Invariant 4 is
about tools: adding a tool must never require editing the loop. That holds. The three new tools in step
7 are registrations and the loop harvests their proposals without learning they exist. **What cannot
stay untouched is synthesis wording**, because `synthesize`, its templates, the system prompt's rule
about what influence connects, and the refusal reasons all live in `loop.py` and all assume one
predicate. Leaving them alone is trap 3. The edits are confined to: the verb and heading choice in
`synthesize`, the templates, `ApprovedClaimSet` (a `predicate` property and the single-predicate chain
rule), `descent_is_approved`, the refusal reasons, and one sentence of the system prompt. **No change
to the run loop, tool dispatch, gating order or event emission.** A test asserts the tool-harvesting
path is unchanged.

### 3.3 Traps in the data and the build

9. **Three English-only label fetches, not one.** `ingest/prosecheck.py:fetch_entities` (755, 766, 769),
   `ingest/wikidata.py:fetch_entities` (322, 329) and the SPARQL label service in `ingest/coverage.py:55`
   all read `en` only. The membership layer labels genres through the second one, so the bug may also
   have dropped membership genres. **Fix:** one shared helper that all three use. Step 1.
10. **A full re-crawl would mix a month of unrelated Wikidata edits into the diff.** The ingest is
    layered: each module reads a pinned artifact and writes the next version (`--source`/`--version`).
    **Fix:** v0.10.0 is one new layer over v0.7.1, and every change it makes is classified (§4, D2). Any
    change outside the classes is a bug. Step 5.
11. **`inception_year` means P571 and only P571** (`graph/schema.py:261`, and the field's own docstring
    forbids laundering another source into it). A person's birth year is P569. **Fix:** new fields,
    `birth_year` and `birth_precision`, on artist nodes. Groups keep using `inception_year`, which for a
    group already means P571 (formation). Step 4.
12. **Edge sort order ignores the predicate** (`ingest/artifact.py:97` sorts by subject and object).
    Harmless while no pair carried two predicates. Beethoven will now carry both `influenced_by` Haydn
    and `studied_with` Haydn. **Fix:** sort by subject, predicate, object. No existing v0.7.1 pair has two
    predicates, so no existing edge moves; a test asserts both. Step 4.
13. **The map and the bundle have size caps this phase can break.** Bound A alone could add a few
    thousand nodes and edges at about 410 bytes each against 0.43 MB of graph headroom, and the backdrop
    is solved "undirected over every edge" (`graph/backdrop.py:62`), so teaching edges join the component
    that is inlined into a bundle with 42.6 KB of headroom. **Fix:** decided from measurements in step 6
    (§4, D6), before any cap moves.
14. **New names can make old names ambiguous.** Resolution needs exactly one exact match; two nodes with
    one label refuse as ambiguous. A newly ingested 19th-century "John Williams" would break every case
    that resolves the film composer. **Fix:** a test that every name used by the chips, the gold,
    adversarial, tour and live sets and the README resolves to the same node on v0.10.0 as on v0.7.1.
    Step 9.
15. **The gold set has a written re-pin rule** (`gold_v0_1.json` provenance): re-pin only when every
    touched node's neighbour set is unchanged, checked pair by pair in both directions; otherwise
    re-author. `gold_v0_1_029` is a **pre-1900 classical music** refusal case, the slice this phase
    touches most. **Fix:** step 9 runs that check before any pin in a dataset moves.
16. **Teaching can run backwards in the data.** A teacher recorded as younger than the student is
    usually an inverted statement. Direction is the one error that turns correct claims into false
    history. **Fix:** step 5 lists every such edge, and each is hand-read and either kept with a recorded
    reason or excluded through the existing hand-rejection mechanism.
17. **`Direction` is named for influence.** `Direction.INFLUENCED_BY` means "the subject side", so
    "who X studied with" is `neighbors(x, Direction.INFLUENCED_BY, predicates={studied_with})`. That
    reads wrong and will be written wrong. **Fix:** the teaching tools own the only calls, and a test
    asserts teachers and students are not swapped. `Direction` is not renamed in this phase.

### 3.4 The pin map — every place "0.7.1" lives, and what happens to each

Audited 2026-09-11. **Nothing in the repo sorts or orders artifact versions**: every reader matches
one exact pinned string, Terraform uploads every `v*/` directory without ordering, and the one version
pattern (`web/scripts/stage-graph.mjs:31`, `^\d+\.\d+\.\d+$`) accepts two-digit parts.

| class | files | what happens |
|---|---|---|
| **The pin** (moved once, together, in step 9) | `ingest/wikidata.py:ARTIFACT_VERSION`, `graph/memory.py:PINNED_ARTIFACT_VERSION`, `web/src/chips.json:artifact_version`, `gold_v0_1.json`, `adversarial_v1.json` and `tour_v1.json` `artifact_version_pin` | set to `0.10.0`, each dataset only after its re-pin check |
| **Regenerated by a command, never hand-edited** | `web/src/corpus-facts.json` (`make facts`), `web/src/graph/backdropData.ts` (`make backdrop`), README markers (`make readme`), `web/public/report/index.html` (`make report`), `eval/datasets/baseline_v0_3_0_local.json` (its generator; a drift test locks it) | regenerated after the re-pin |
| **Measurement records, never edited by hand** | `eval/thresholds.json` live set `artifact_version`, `eval/noise_floor.json` | change only at phase 7.7's re-baseline |
| **Sealed, never touched** | `eval/datasets/heldout_v1.manifest.json` (pinned 0.5.0) | untouched; `make heldout-check` will report pin drift, which is expected and is not fixed by re-sealing |
| **History** | `eval/results/*`, `eval/transcripts/*`, dated doc passages | untouched |
| **A shipped recording** | `web/src/fixtures/tour-groove-metal-to-blues.sse` | never re-stamped by hand. Step 8 checks the route's five edges on v0.10.0 and re-captures it live if anything the tour shows depends on the version (about a cent, behind confirmation) |
| **Test fixtures and comments** | `web/src/fixtures/*.sse` other than the tour, code comments | a comment that states a present-tense fact is corrected in step 10; a dated one is left |

A test added in step 0 asserts the pin and every mirror agree, and that the pinned version is the
**numerically** greatest directory under `artifacts/`, with a fixture proving the string order
disagrees (so the test cannot pass by accident).

## 4. Decisions

### 4.1 Taken by him, 2026-09-11

- Full scope: `studied_with` is narrated, not only stored. Before the launch post. Phase 7.6, product
  v0.9. Artifact v0.10.0.
- Name resolution is phase 7.7. Partial names are **offered, never resolved** by the system.
- One live re-baseline and one deploy, both at 7.7's close.
- Prose in this phase may be written by Claude (the 7.5 permission extends to the phase inserted
  inside it; the scope doc and this plan are Claude's to write in any case).

### 4.2 Taken by this plan, open to his veto at approval

- **D1. Predicate name and direction.** `studied_with`, stored as *student* `studied_with` *teacher*,
  mirroring `influenced_by`'s *later* `influenced_by` *earlier*. The P1066 statement lives on the
  student's item, so its URI encodes the subject's QID and `claims.resolve_sources` verifies it
  unchanged.
- **D2. One layer, four classified changes.** v0.10.0 is v0.7.1 plus exactly: **(a)** `mul` recovery
  (entities and rows the bug excluded, re-screened), **(b)** the `studied_with` layer, **(c)** artist
  dates, **(d)** aliases. A diff report classifies every added, removed or changed row into (a) to (d).
  An unclassifiable change stops the step.
- **D3. Verification tiers are predicate-scoped.** `studied_with` gets its own tier(s), never an
  influence tier. The name and count are fixed after the hand check (step 2), because the check says
  what the prose check actually confirms for teaching. The working name is `TEACHING_PROSE_AUTO`: a P1066
  statement whose student's English article names the teacher in body prose.
- **D4. Which claim sets may be narrated.**
  - A single-predicate set in any of the three existing shapes (fan-out, fan-in, chain): yes.
  - A **mixed** fan-out or fan-in (the model asked both "influences" and "teachers" of one person):
    yes, with the claims **grouped by predicate** under separate headings in the synthesis prompt, and
    an instruction never to describe a teacher as an influence or the reverse.
  - A **mixed chain** (Czerny studied with Beethoven, Beethoven influenced by Haydn): **yes, with typed
    hops. DECIDED BY HIM 2026-09-11**, overriding this plan's first draft, which refused mixed chains
    and left them to phase 8. Sound because both predicates run the same way in time (the later person
    learned from, or was shaped by, the earlier one), which is not true of membership. The rules:
    - Each hop carries its own predicate into synthesis, read off its approved claim, and the prose
      keeps each hop's verb. The chain template names both verbs and forbids collapsing them.
    - A pair approved under **both** predicates (Beethoven studied with Haydn and was influenced by
      him) is narrated with both, never one picked.
    - **No summary may name the chain as influence** ("a line of influence from Haydn to Czerny"). The
      embellishment ban names that phrasing, because the 7.5 step 0.5 transcripts showed exactly this
      kind of editorial summary ("a direct line of musical influence") appearing unprompted.
    - The existing `trace_lineage` stays **influence-only and unchanged**, so no gold path case can
      silently acquire a shorter route through a teaching hop. The new chain tool walks both predicates.
    Phase 8 inherits the typed-hop mechanism for membership rather than designing it.
- **D5. Three new tools, no new loop branches.** `get_teachers`, `get_students` and
  `trace_teaching_lineage`, mirroring `get_influences`, `get_descendants` and `trace_lineage`.
  `trace_teaching_lineage` walks `studied_with` **and** `influenced_by` (D4); `trace_lineage` is not
  touched.
  **Influence questions also check teachers — his decision, 2026-09-11.** He put it that teaching is a
  strong kind of influence. `get_influences`'s description gains one sentence telling the model that
  teachers are often a strong influence, to also call `get_teachers`, and to report them **as
  teachers**. So "who influenced Chopin?" can answer with his influences and, grouped separately, "he
  studied with Józef Elsner". This changes a tool description, not the loop.
- **Why the predicates stay separate even though teaching is usually influence.** Recorded so nobody
  later rebuilds this on the weaker argument. The deciding reason is **sourcing**: P1066 says "student
  of", and a claim must state what its source asserts. Storing it as `influenced_by` would make the system
  assert an inference no source made, which is the "grounded slides into correct" failure. The secondary
  reason, that some students reacted against a teacher, he judged rare, and the step 2 hand check
  measures it rather than assuming it either way. Three
  rather than one because the three narratable shapes need a single subject, a single object or an
  ordered chain, and one tool returning both directions produces a set that is none of those. Cost:
  every tool description is re-sent each turn, so input tokens per query rise. Tracked, not gated, and
  measured at 7.7's re-baseline.
- **D6. Budgets are decided from measurements, and the default is to keep the caps.** Step 6 measures
  the real v0.10.0 graph and backdrop sizes first. If over:
  - **graph**: the SPA's staged copy becomes a named **projection** (fields the map does not read,
    such as aliases, are dropped by `stage-graph.mjs`, and the file says it is a projection), before
    any cap is raised. If the projection is still over, the cap moves with its recorded reasoning
    updated, which is the budget file's own rule.
  - **backdrop**: the backdrop keeps a fixed node ceiling chosen by a stated rule, the README sentence
    that says "that component … is the backdrop" is rewritten to match, and the ceiling is a named
    constant with a test.
  Raising the script cap to fit a bigger backdrop is **not** an option: the script cap is "deliberately
  too small for an animation library", and a decorative layer is the wrong reason to move it.
- **D7. Bound A unless step 3's measurement says otherwise.** Composer students born before 1900,
  composer teachers, both with an English article. Many pre-1900 performers are also recorded as
  composers: checked 2026-09-11, all five of Liszt's recorded teachers (Czerny, Reicha, Adam Liszt, Paer,
  Salieri) carry the composer occupation, so the Czerny to Liszt line survives bound A. Widening to every musical occupation
  is taken only if step 3 shows the added population is small enough for the budgets and the hand check
  covers it.
- **D8. Birth years go on every artist node, not only new ones**, from P569 for people and P571 for
  groups (into `inception_year`, which is already P571's field). Coverage reports "born before 1900" and
  never "active before 1900": a birth year is not an era of activity, and the wording must not pretend.
- **D9. The pin guard of trap 7 lands in step 0**, before the pin moves, so the first live run on
  v0.10.0 is refused as ungated by construction rather than by memory.

### 4.3 Genuinely uncertain, named rather than smoothed

- **What P1066 actually asserts, per row.** The hand check is where that stops being a guess. If it finds
  a high rate of non-teaching relations, the plan changes (step 2 has the stop rule).
- **The final size of v0.10.0.** 3,606 raw statements shrink under screening by an unknown fraction. The
  artist axis passed **1,320 of 4,432** checked P737 candidates (about 30%, `data/artist_screening.json`);
  teaching may pass at a very different rate, because "studied with X" is exactly what a biography says.
- **How many of the 44 `mul` victims get in.** Some will fail other checks; Victor Hugo is on the list
  and is not a musician.
- **Whether gold cases move.** Mozart's recovery can add influence edges touching nodes gold cases use.
  The pair-by-pair check decides re-pin versus re-author, and either outcome is correct.
- **Whether the model uses the teaching tools well.** Only a live capture shows it, and 7.6 takes at most
  a few. The real measurement is 7.7's re-baseline.

## 5. Explicitly not in this phase

The scope doc's list, plus what this plan adds:

- Membership narration (phase 8). Changing `influenced_by`. New sources. Works, recordings, instruments.
  A new tour route. The held-out set. P279, `checks_disagree`, contested.
- **Name resolution of any kind beyond exact labels.** Aliases are stored, not used. Phase 7.7.
- **Deploying, and the live re-baseline.** Phase 7.7's close.
- **Renaming `Direction`.** Trap 17 is handled in the tools and a test.
- **A teaching-assertion filter** analogous to the influence one (`ingest/assertion.py`). Only if the
  hand check shows the prose check alone is too weak to label honestly; then it is proposed as its own
  step with its own measurement, not slipped in.
- **Presentation-only polish.** Anything that changes only how the page looks can happen after the
  re-baseline without invalidating it; the live evals never read the frontend. A possible phase 7.8 goes
  there, not here.

## 6. The one-way doors this phase touches

| invariant | how it is satisfied |
|---|---|
| 1. Claims first, prose second | Unchanged. `synthesize` still takes exactly one claim-bearing parameter. Prose learns the predicate from the approved claims it already receives, never from a new input. |
| 2. Provenance on every edge | Every `studied_with` row carries `source=wikidata`, the P1066 **statement** URI as `source_id`, and `retrieved_at`, enforced by the `Edge` constructor. Birth years and aliases are Wikidata reads on nodes that already carry provenance. |
| 3. Validated graph semantics | P1066 is hand-checked before a row is ingested (step 2). The gate's same-axis check already covers teaching: both ends are artists. |
| 4. Tool contract | Three tools are registrations. The loop edit is prose, recorded in §3.2, with a test that dispatch is unchanged. |
| 5. Everything in Terraform | No infrastructure change. `artifacts.tf` uploads `v0.10.0/` automatically. |
| 6. Package boundaries | New ingest code in `ingest/`, schema in `graph/schema.py`, tools in `agent/tools.py`. `tests/test_architecture.py` still passes. |
| 7. LLM provider seam | Untouched. |
| 8. Container image | Untouched; the new artifact rides in the package as before. |
| 9. Streaming | Untouched. Claim frames already carry `predicate`. |

**`ALLOWED_PREDICATES` is opened on purpose**, and the property preserved is the one phase 8's scope
doc names: after this phase there is still no path by which a non-influence edge reaches prose **as an
influence claim**. `plays_genre` stays out.

## 7. Steps

Every step ends green on `make check` or does not end. Stopping between steps is fine; stopping inside
one is not.

### Step 0 — Guards before anything moves — [done]

- The **pin guard** (trap 7, D9) in `eval/thresholds.py:_ungateable`, with tests: a run on the recorded
  artifact gates; a run on another artifact is refused with a reason naming both versions; the scripted
  set, which records none, is unaffected.
- The **version-order test**: the pin and every mirror in §3.4 agree, and the pinned version is the
  numerically greatest directory under `artifacts/`, with a fixture proving string order disagrees.
- The **resolution-stability fixture** for trap 14: every name used by chips, datasets and the README,
  and the node it resolves to on v0.7.1, written to a committed file now so step 9 compares against it.

**Done when:** all three are committed and green on v0.7.1.

#### 0.0 As built, 2026-09-11

**The pin guard** is a fourth condition in `eval/thresholds.py:_ungateable`, placed after the
completeness check and before the size checks, so a run on another corpus is reported as that rather
than as a size mismatch. It reads `derived_from.artifact_version`, which only the live set records.
Four tests in `tests/test_thresholds.py`: a control (a live run on the measured corpus gates), the
refusal naming both versions, un-gateable being neither pass nor failure, and the scripted set staying
gated on any corpus.

**Found while writing it, and fixed in the same step:** the test helper `as_live` relabels a scripted
run as live to exercise the live bounds, and the scripted run follows the repo pin. After the re-pin
every live-bound test would have hit the new guard and stopped testing its bound, passing or failing
for the wrong reason. `as_live` now stamps the artifact the live bounds were measured on, read from
the committed file (the same "derive, don't write down" lesson `live_case_count` records).

**The version-order test** is `tests/test_artifact_versions.py`: a control proving string order and
numeric order disagree on 0.7.1/0.9.0/0.10.0, every cut named MAJOR.MINOR.PATCH, the pin equal to the
numerically newest cut, and one list of every copy of the pin (§3.4). **One deviation from the plan,
deliberate:** step 5 writes `v0.10.0/` before step 9 moves the pin, which a strict "pin is newest" test
would turn red mid-phase. So the test carries `UNPINNED_CUTS`, a named list of cuts in flight, each
with a reason. Empty now; step 5 adds 0.10.0 and step 9 removes it.

**The resolution snapshot** is `tests/resolution_snapshot_v0_7_1.json`, 185 names written on v0.7.1
by `tests/test_resolution_stability.py` (which refuses to rewrite it on any other corpus): 176 resolve
to a node, **8 must stay unresolved** (vaporwave, chillwave, zeuhl, dastgah, juju, quantum jazz, black,
metal, the adversarial set's refusals) and **1 must stay ambiguous** (big band). The one label that
resolves to a differently labelled node, "heavy metal" to "heavy metal music", is the resolver's
documented optional-"music" fold, not a defect.

**Measured:** `make check` exit 0: 1568 passed (12 new), 14 deselected, mypy clean over 114 files,
frontend 429 across 23, scripted gates 4 passed / 0 failed / 2 N/A of six, root 17 of 18.

### Step 1 — The `mul` label fix — [done]

- One helper, used by all three fetch paths (trap 9): request `languages=en|mul`; the label is `en` if
  present, else `mul`; aliases are the union of `en` and `mul` aliases, deduplicated, label excluded.
- The SPARQL label service in `ingest/coverage.py` asks for `"en,mul"` (the service's own fallback
  syntax).
- Tests with recorded API payloads: a `mul`-only entity (Mozart's shape), an `en`-and-`mul` entity (en
  wins), neither (empty, as before, and still refused by the `Node` constructor), aliases merged.

**Done when:** the tests pass and no network call is needed to run them.

#### 1.0 As built, 2026-09-11

**`ingest/labels.py`** holds the rule once: `entity_label` (`en`, else `mul`, else the empty string it
always was), `entity_aliases` (`en` then `mul`, deduplicated, never repeating the label), and the two
language strings (`en|mul` for `wbgetentities`, `en,mul` for the SPARQL label service's fallback list).
`prosecheck.fetch_entities`, `wikidata.fetch_entities` and `coverage.coverage_query` use it. Nothing
else needed an edit: the membership, DBpedia and cultural-origins layers all fetch through one of the
two fixed functions.

**`en` wins when both exist, on purpose.** Every artifact so far was labelled from `en`; letting `mul`
win would relabel existing nodes and move resolution under the eval datasets, which step 0's snapshot
would then have to explain.

**Tests:** `tests/test_labels.py`, 8, over payloads recorded from Wikidata that morning (Mozart's real
`mul`-only shape, Beethoven's `en`-and-`mul`, a synthetic disagreement, an unlabelled entity), including
each fetch path with its network call replaced, asserting both the language requested and the label
read. No test touches the network.

**Measured:** `make check` exit 0: 1576 passed (8 new), mypy clean over 116 files, frontend 429,
scripted gates 4 / 0 / 2 of six, root 17 of 18. **No artifact changed**: the fix only matters to the
next ingest, which is step 5.

### Step 2 — The P1066 hand check, before any ingestion

**The rule is `.claude/rules/graph-semantics.md`: hand-check before ingesting.** P279 was read at 47
edges and changed the design; P136 at 30.

- **Sample:** 40 statements from bound A, drawn with a recorded seed, stratified by the student's birth
  century (up to 1699, 1700s, 1800s) and by whether the statement carries a Wikidata reference.
- **Each is read** against the student's English Wikipedia article (and the teacher's where needed) and
  put in one category: *formal study* (years, a conservatory, an apprenticeship); *lessons* (real but
  brief); *disputed or legendary*; *wrong relation* (a colleague, patron, relative or rival recorded as a
  teacher); *inverted* (the teacher studied with the student); *unverifiable* from the article.
- **Also recorded per row:** whether the existing prose check (the student's article names the teacher
  in body prose) passes, so the tier can be named for what it actually confirms (D3).
- **Stop rule, set before reading:** *wrong relation* plus *inverted* at **3 or fewer of 40** proceeds;
  **4 to 8** proceeds only with the tier split or exclusion the data points to, stated in this doc;
  **more than 8 stops the phase** for a redesign, the way P279's 47 of 47 did.
- **Who reads:** Claude reads and records each row with the sentence it relied on; sjtroxel reviews
  every row not judged *formal study*. The result is reported as a direction, not a rate (n=40), as
  P136's was.
- **Recorded in `docs/graph-semantics.md`**, in a new section beside P279 and P136.

**Done when:** the 40 rows and the verdict are committed, and he has reviewed the flagged ones.

### Step 3 — The bound, from measurements

- Bound A measured again with the step 2 exclusions applied; bound B (any musical occupation) measured
  in chunks by birth century so the query service does not time out.
- For each: students, teachers, statements, how many endpoints are already in the corpus, and the
  projected graph bytes at about 410 per row.
- The chosen bound is written here with its numbers. Bound A is the default (D7).

**Done when:** the bound is recorded and he has seen the numbers.

### Step 4 — Schema

- `graph/schema.py`: `PREDICATE_STUDIED_WITH`; `PREDICATES` widened; `INFLUENCE_ONLY` **unchanged**; the
  teaching tier(s) from D3 added to `VERIFICATION_LEVELS` with docstrings saying what they do and do not
  mean; a `VERIFICATION_TEACHING_LEVELS` set on the `VERIFICATION_MEMBERSHIP_LEVELS` precedent.
- `Node`: `birth_year`, `birth_precision` (P569, optional, same precision codes as P571), and `aliases`
  (a tuple, JSON round-trip normalised like `countries`).
- `ingest/artifact.py`: edge sort key includes the predicate (trap 12).
- `counts_agree` already tolerates a widening; a test confirms v0.7.1's manifest still verifies.
- Tests: every earlier artifact still loads and verifies; a teaching edge constructs; a node with the
  new fields round-trips; no existing edge reorders.

**Done when:** v0.1.0 through v0.7.1 all still load, and `make check` is green with no artifact change.

### Step 5 — The v0.10.0 layer

A new module, `ingest/lineage.py`, `--source 0.7.1 --version 0.10.0`, on the `membership.py` and
`dbpedia.py` pattern. Local only, never in CI, $0, 1 request per second to Wikipedia with the
project's contactable User-Agent.

- **(a) `mul` recovery.** Re-fetch entities for every QID that came back unlabelled, re-run the existing
  screening (`discovery.check_candidate`, `prosecheck.check_edge`) on every candidate row touching one,
  and admit what passes, with the same verification tiers the artist axis already uses. Recovered
  artists get their P136 membership edges through the existing membership code, so they do not enter
  half-connected. Genres the membership layer dropped for an empty label are re-checked the same way.
- **(b) `studied_with`.** Discovery within the step 3 bound, excluding deprecated statements; the prose
  check on the student's article; the step 2 exclusions honoured; edges built with statement URIs.
  **Every edge whose teacher is recorded as younger than the student is listed and hand-read** (trap 16).
- **(c) Dates** for every artist node (D8).
- **(d) Aliases** for every node, `en` and `mul`.
- **The diff report** v0.7.1 to v0.10.0: counts per class (a) to (d), every removed row listed (there
  should be none), and a hard failure on any change it cannot classify.
- Tests over recorded fixtures: the layer is deterministic, the classification catches a planted
  unclassified change, and a teacher-younger-than-student edge is flagged.

**Done when:** `artifacts/v0.10.0/` exists with its manifest, the diff report is committed in this doc's
as-built, and Mozart is in it. **The pin has not moved yet.**

### Step 6 — Graph, derived views and budgets

- `graph/structure.py`, `graph/coverage.py` and `graph/facts.py` read the new predicate correctly:
  coverage gains artists by birth era and a "born before 1900" count; `corroboration.py` is asserted by
  test to ignore `studied_with` (a teacher never corroborates an influence).
- Measure the staged graph and the backdrop against their caps on v0.10.0, then apply D6.
- `make facts`, `make backdrop`: regenerated.

**Done when:** every budget holds, with any cap change carrying updated reasoning, and the structure,
coverage and corroboration numbers are recorded here.

### Step 7 — The gate, the tools and the prose

- `agent/claims.py`: `ALLOWED_PREDICATES = {influenced_by, studied_with}`; `_find_edge` passes
  `predicates=ALLOWED_PREDICATES` (trap 1). The comment above the constant is rewritten to say it is now
  two predicates on purpose and why `plays_genre` is still out.
- `agent/tools.py`: `GetTeachers`, `GetStudents`, `TraceTeachingLineage` (D5). Descriptions say
  **"studied with; this is teaching, not influence"**, and each proposes `studied_with` only. The existing
  influence tools are unchanged and still propose `influenced_by` only.
- `agent/plan.py`: the planning prompt's "graph of documented musical influences" names teaching too.
  `QUERY_KINDS` is **unchanged**: kinds are shapes (origins, lineage, descendants), and a teaching
  question is one of those shapes.
- `agent/loop.py` (§3.2): the verb, participle and headings come from the predicate; `ApprovedClaimSet`
  gains `predicate` (the single predicate, or `None` when mixed) and a typed-hop view of `chain`
  (each hop's predicate or predicates, read off the approved claims, never supplied from outside);
  mixed fan-outs are grouped by predicate and mixed chains carry typed hops (D4); `descent_is_approved`
  reads influence claims only (trap 4); the refusal reasons stop asserting influence (trap 8); the
  system prompt gains one rule: teaching is between two artists and is never influence.
- **The disclosure test (DoD 4)**, in the shape of `ContestedDisclosure`, over every synthesis path: a
  teaching claim never reaches a prompt under an influence verb or heading; a mixed fan-out keeps its
  groups apart; **every hop of a mixed chain reaches the prompt with its own verb, a pair approved under
  both predicates carries both, and the chain template forbids naming the whole chain as influence**;
  and an inverted influence premise cannot be "established" by a teaching claim. It tests the prompt construction, which is deterministic. **What it cannot test** is
  the model ignoring the instruction; that is what the live capture and 7.7's judged pass watch, and it
  is recorded as the residual risk rather than claimed away.

**Done when:** the disclosure test and a scripted run of "who did Beethoven study with" pass locally.

### Step 8 — API contract and frontend

- `docs/SPEC.md` §6 and §7: `studied_with` in the claim contract, the new tier(s) in the verification
  list, and the rule that a claim's predicate is always shown.
- `web/src/types.ts`, `staticGraph.ts`: the predicate constant. `ClaimList.tsx`: the verb from the
  predicate. `subgraph.ts`: the claimed edge's predicate read from the claim. `GraphView.tsx`: a **third**
  edge style for teaching, distinct from both influence and membership. `NodeInspector.tsx`: a teaching
  section ("studied with", "taught"). `CoveragePanel.tsx`: the born-before-1900 figure. Each with a test.
- `layout.ts` keeps ordering by influence only. Teaching is not added to the time ordering in this phase.
- **The tour recording**: the route's five edges are checked on v0.10.0; the recording is re-captured live
  only if a check fails or the page shows its version (about a cent, behind confirmation). It is never
  edited by hand.
- The asset budget is re-run.

**Done when:** the running app, on the local stub, shows a teaching answer with its own verb, its own
line style and its own inspector section, and the frontend suite is green.

### Step 9 — The re-pin, datasets and free evals

- **The gold re-pin rule, applied** (trap 15): every node each case touches, both directions, every
  predicate the gate now admits, v0.7.1 against v0.10.0. A moved neighbour set means that case is
  re-authored, never re-pinned. `gold_v0_1_029` is checked first.
- **Resolution stability** (trap 14): the step 0 fixture compared; any name that now resolves differently
  or ambiguously is a finding handled case by case, never by quietly editing the dataset.
- **The pin moves**, in the one commit, in every "pin" row of §3.4.
- `eval/metrics.py:_matching_edge` widened from `ALLOWED_PREDICATES` (trap 2);
  `eval/slices.py:predicate_slice` gains a teaching bucket; `verification_mix` reports the new tier(s).
- **New gold cases**, a `teaching_lineage` slot: a teachers fan-out, a students fan-in, a pure teaching
  chain, and a teaching refusal. Subjects chosen by a mechanical rule written into the file before
  choosing, claims read off the artifact, prose and citations quoted from Wikipedia and the works it
  cites. Drafted by Claude and reviewed by him, **named as the weakening it is**, on the case 030
  precedent.
- **New adversarial cases**: an influence premise that only a teaching edge could "support" ("Was
  Beethoven influenced by Salieri?" where the corpus holds only that he studied with him), and a
  **transitive premise**: "Was Czerny influenced by Haydn?", where the corpus connects them only through
  Beethoven (studied with, then influenced by). The answer may walk the chain with typed hops; it must
  not state a direct influence the corpus does not hold. Both subjects checked against v0.10.0 before
  the case is written; if the edges are not there, the case uses a pair that is.
- **A new gold case for a mixed chain**, beside the four teaching cases, with its hops' predicates in
  `expected_claims`.
- `EXPECTED_CASE_COUNT` and the composition plan updated. **The live set grows, so the live suite is
  ungated until 7.7's re-baseline**, and the pin guard from step 0 says so independently.
- `make eval`: **4 passed, 0 failed, 2 N/A of six.** `baseline_v0_3_0_local.json` regenerated.
- The held-out set is not touched. `make heldout-verify` still passes; `make heldout-check` reports the
  pin drift, and that is recorded, not fixed.

**Done when:** `make check` is green on the new pin, and every dataset change is explained here.

### Step 10 — Copy truth, and the close

The phase 7.5 lesson: markers catch numbers, not sentences.

- `make readme`, `make report`.
- **Sentences made false by this phase**, found by grep, not memory: "two predicates", "two kinds of edge
  that are never mixed", "2,202 of 2,284", "82 edges", "7 components", "1,465 in the largest", "every
  edge is influence", "v0.7.1" as the current corpus, in `README.md`, `CLAUDE.md`, every `.claude/rules/` file,
  `SPEC.md`, the report `COPY` and code comments. Each is corrected with a date, or the number is marked.
- `docs/graph-semantics.md`: the P1066 section (from step 2) and the bound (step 3).
- `DATA-LICENSES.md`: confirmed unchanged (Wikidata CC0; Wikipedia is read for the check and not
  displayed as text). If anything is displayed, it is attributed there.
- The Lambda image built and run locally on v0.10.0 (`make image-run`), and one live capture of a
  teaching question behind confirmation, a few cents, reported as **exploratory and ungated**.
- The plain-English explainer, `docs/classical-lineage-explained.md`, written as the phase goes (the
  `start-a-phase` skill's step 7), for the cold walk-through.
- `ROADMAP.md`, `docs/KNOWN-GAPS.md`, the memory router: 7.6 closed, 7.7 next.

**Done when:** every DoD item in §1.1 has a verdict with evidence.

## 8. Testing, and which eval metrics apply

- **Unit tests** for every trap in §3, named after it, so a future reader can find why each exists.
- **The disclosure test** (DoD 4) is the centre of the phase.
- **Tier 1, scripted, free, every commit:** all six properties apply; four gate as before. Edge
  groundedness and citation resolution now cover teaching claims, because trap 2 is fixed.
- **Tier 1, live:** not gated in this phase. The pin guard refuses it and the case count has moved.
  Re-baselined once at 7.7's close.
- **Tier 2, judged:** not run in this phase. `narrative_quality` over teaching answers is the natural
  place to watch the residual risk in step 7, at 7.7's close.
- **Slices:** the era slice gains dated artists, so era numbers move by construction. Tracked, not gated,
  and explained in the report rather than presented as a result.

## 9. Cost, and the guardrails

- **Wikidata and Wikipedia: $0.** Rate-limited as the rules require. The Wikipedia crawl for bound A is
  roughly one article per student, around 2,000 at one per second, a little over half an hour.
- **Bedrock in this phase: a few cents at most.** One or two live captures and possibly the tour
  re-capture, each behind an explicit confirmation. No suite runs.
- **Per-query cost rises slightly** with three more tool descriptions re-sent each turn. The token budget
  (`MAX_ACCUMULATED_TOKENS`) still caps it; the new average is measured at 7.7's re-baseline.
- **The re-baseline itself** (about $3 and 2.5 hours at the current case count, somewhat more with the new
  cases) is **phase 7.7's**, behind its own confirmation.

## 10. What happens after

Phase 7.7 `name-resolution` (its scope doc is written), then one re-baseline and one deploy, then phase
7.5 resumes at step 5, the launch post, on v0.10.0.
