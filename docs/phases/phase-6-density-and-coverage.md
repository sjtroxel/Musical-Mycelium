# Phase 6 — Density and Coverage (v0.6)

> **Scope doc.** Written 2026-07-31, after the P279/P737 hand-validation and before building. Held back
> from the 2026-07-30 scope pass on purpose, so it could be written against measurements rather than
> assumptions. Re-read it at the start of phase 6 and amend it — phases 1 through 5 will have taught
> things this doc cannot know.
>
> **Amended 2026-08-24, at the phase 4 close.** That is exactly what happened: phases 2 through 4
> answered a substantial part of this doc, including its central "measure this early" decision. See §0.
> The sections below are unedited except where a marked blockquote says otherwise — this doc is a map,
> and the record of what was assumed on 2026-07-31 is worth keeping.

## 0. What phases 2–4 already answered

Read this before the sections below. They were written when the corpus was 158 genre edges and the
artist axis was still a phase 6 deliverable.

### Delivered already, so do not re-plan it

- **The artist axis shipped in phase 2, step 6c** — Wikidata P737 artist-to-artist, not MusicBrainz. It
  is listed under "Delivers" below as a phase 6 job and it is not one.
- **Component structure is already queryable** (`graph/structure.py`, phase 2 step 4). It is recomputed
  at load rather than read from the manifest, and `component_count`, `largest_component`, `diameter`,
  `isolated_nodes` and `max_path_hops` ship on `/health` and the `done` frame. **DoD #3 is met.**
- **Slicing by era, region, density and query type exists** (`eval/slices.py`, phase 3 step 7b, carried
  through the whole phase 4 suite). **DoD #5 is met.**
- **Coverage is already a recorded, displayed number** (`graph/coverage.py`, phase 2 step 8): 169 genres,
  28 without inception, 48 without country, 29 distinct countries, 43 naming no US or UK connection.
  DoD #2 is partly met — the number exists and ships; what is unmet is coverage rendered to a *user*,
  which is phase 5's surface, not a corpus job.
- **The prose-check markup defect under "Known risks" is fixed.** `ingest.prosecheck.strip_markup`
  (phase 2 step 1) removes refs, templates and tables, category and file links, and appendix sections.
  The risk entry stands as a record; the work is done.

### The numbers below are superseded

| this doc says | artifact v0.5.0 says |
|---|---|
| 158 sourced influence edges | **950 edges** |
| 198 genres | **973 nodes** — 169 genres and 804 artists |
| 46 disconnected components | **169 components**, largest **458** |
| — | diameter **16**; deepest chain `path()` can return: **6 hops** |

The genre-only picture the doc was written against still exists inside that: 41 components, largest 31,
deepest chain **two** hops. The artist axis is the entire difference.

### The central decision is already made, and it came back positive

Under "Key decisions": *"Whether the artist axis changes the component picture. It plausibly does...
**This should be measured early in the phase, because a positive result reshapes the whole decision.**"*

It was measured in phase 2 and it was positive. Genre-level P737 could not supply depth at all — DoD #2
of phase 2 originally promised a three-hop path and the genre corpus tops out at two. The artist axis
supplied six. So the reshaping this bullet anticipated has already happened, one phase early, and the
three candidate resolutions should be re-read in that light:

1. **Narrow to component-local lineage** — much weaker now. The largest component holds 458 nodes rather
   than 44, so "refuse across components" refuses far less than it would have in July.
2. **P279 supplies connectivity** — unchanged and still unbuilt. P279 is still not ingested, and
   `.claude/rules/graph-semantics.md` still owes a real boundary predicate if this phase ingests it.
3. **A second source** — still open, and now open for a *different reason than connectivity*. Connectivity
   was largely solved by the artist axis. What a second source buys is **`contested`**, which is
   arithmetically unreachable while every edge has exactly one source, always Wikidata.
   `agent/claims.py:UNREACHABLE` declares `contested` and `checks_disagree` with a test locking both, so
   this phase is what makes one of them reachable or leaves it honestly unreachable forever.
   **MusicBrainz cannot be that source** — it has no influence relationship in its schema at all, so it
   can add releases and identifiers and not one lineage edge. `dbo:stylisticOrigin` is the named
   candidate (`SPEC.md` §2.2).

### What phase 5 will add to this before it starts

The chip row. Of the six aspirational chips in `SPEC.md` §2.2, one answers, one refuses correctly and
deliberately, and **four are blocked on this phase's second source**. Whatever phase 5 decides to put on
the first screen is a direct statement about what this phase is for, and it should be read here first.

### What phase 5 ANSWERED — added 2026-09-02 at the phase 5 close

Phase 5 is complete and `v0.5.0` is tagged. Five things it settled that this phase inherits:

1. **DoD #2 is now fully met, and it is not this phase's job.** Phase 5 step 9 shipped a drawn coverage
   panel — when, where, and how densely, in counts, open on arrival, **below** the results so the answer
   is never pushed off-screen. The half that was outstanding on 2026-08-24 is done. What this phase owes
   DoD #2 is only that any *new* corpus cut keeps the panel honest.
2. **The chip row landed at five, not six** (`web/src/chips.json`, the single source of truth, validated
   against the pinned artifact by `tests/test_chips.py`): four answer outright, and the Kate Bush pair
   was merged into one chip that refuses and then answers. **The four aspirational chips are still
   blocked on this phase's second source** — that is unchanged and it is the clearest statement of what
   this phase is for.
3. **A third thinness axis was measured and it is the sharpest one: 85 of the 169 genres have no
   recorded origin at all, 108 have exactly one connection, and the busiest has six.** It lives in
   `web/src/corpus-facts.json` with `tests/test_corpus_facts.py` asserting it against the pinned
   artifact, because putting it in `graph/coverage.py` during phase 5 would have been a backend edit to
   a serialized contract, which phase 5's DoD 9 forbade. **This phase should move it into `Coverage`
   proper**, at the same time it cuts the new artifact.
4. **The corpus is 169 disjoint islands and artists and genres NEVER touch** — 128 components are purely
   artists, 41 purely genres, none mixed, because only P737 is ingested and it does not link the two.
   The consequence phase 5 had to design around: **"one connected organism" is not drawable on v0.5.0**,
   and the map can only ever show a neighbourhood and say so. **`P136` is the property that would change
   this**, and it is a bigger lever on the product's central claim than the second source is. Neither is
   free: both mean a new cut, and a new cut invalidates every published eval number.
5. **Six of the 102 datable edges run backwards in time** — the influence recorded as older than its own
   cause, worst `electroclash (1995) -> electropop (1978)` at 17 years, and one inside a demo chip
   (`swing (1930) -> Western swing (1928)`). Phase 5 declined to build geometry on those numbers. **If
   this phase does anything temporal, that is the finding to start from**: a Wikidata `inception year` is
   a field somebody typed, not a measurement, and a genre does not begin on a date. Relatedly, the three
   undated genres are the same three every time and they are the non-Western ones — Na mele paleoleo,
   Pinoy hip hop, sampledelia.

**One operational item, not a corpus one, before any infrastructure work here:** `make tf-plan`,
`make tf-apply` and `make tf-destroy` pass none of `image_tag`, `llm_provider` or
`reserved_concurrency`, so **a bare `make tf-apply` reverts the deployed function to the stub LLM.**
`docs/KNOWN-GAPS.md` carries the detail; guarding those targets belongs in this phase.

## What this phase is for

Two jobs, and the second one only became visible on 2026-07-31.

**The first is density.** Phases 1 and 2 build the genre graph. This phase thickens it along the axes
that make a lineage claim specific rather than generic: **artists, geography, and time**. A traversal
that says "bebop relates to jazz" is a schema demo. One that says "bebop, New York, mid-1940s, via these
players" is the product.

**The second is coverage as a displayed property, and it is now the harder job.** The corpus is skewed
Western, anglophone, and recent by construction, and `04` §4.5 requires that skew be a visible number
rather than a disclaimer. The measurements in `docs/graph-semantics.md` §4.4 and §5 turned that from a
principle into a specific, uncomfortable problem — which is what this phase exists to resolve.

## The question this phase answers

**The 158 sourced influence edges connect 198 genres in 46 disconnected components.** The largest holds
44 genres; 24 of the 46 are a single pair. Full detail in `docs/graph-semantics.md` §5.

> **Superseded 2026-08-24 — see §0.** Artifact v0.5.0 is 973 nodes and 950 edges in 169 components,
> largest 458. The figures above are the genre-only corpus of 2026-07-31, kept because the question below
> was posed against them.

`CLAUDE.md` states the project thesis as: *"Genres look like separate things; underneath they are one
connected organism, and most of the connections are not written down in one place."* The second clause is
confirmed emphatically by the data. **The first is not currently demonstrable from sourced influence
edges alone.**

This is the open question, and this phase is where it gets decided. It is stated here rather than
answered because answering it requires knowing how phases 1 through 5 actually went — how traversal
performs, what the agent does when a path does not exist, and whether refusal reads as rigor or as
brokenness to someone looking at the deployed URL.

Three candidate resolutions, none preselected:

1. **Narrow the claim to component-local lineage.** The product traces lineage *within* a documented
   region of the graph and refuses across components. Smallest change, strongest grounding claim, and it
   makes refusal accuracy a headline metric. Risk: `.claude/rules/evals.md` warns that a system which
   refuses everything is useless, and 46 components is a lot of refusing.
2. **P279 supplies connectivity, P737 supplies lineage.** The taxonomy connects the graph; influence
   claims stay scarce and separately labelled. Requires the gate to hold two claim types apart in output
   without ever letting one read as the other — see `.claude/rules/grounding-and-claims.md`.
3. **Supplement the corpus with a second source** to thicken the influence layer. Largest scope, and it
   opens a licensing surface: MusicBrainz is CC0 on core tables only, Wikipedia text is CC BY-SA and
   requires displayed attribution.

## Delivers

- **The connectivity decision, recorded with its reasoning**, and whatever ingestion or product change
  follows from it.
- **Density along three axes:** artists (P737's artist edges, which are far more numerous than the genre
  edges — 31,691 P737 edges exist in total), geography, and time (`P571` inception, which reaches back to
  roughly 2000 BCE).

  > **Amended 2026-08-24.** The **artists** axis is delivered — phase 2 step 6c, 804 artist nodes on
  > Wikidata P737. Geography and time remain, and remain thin: 28 of 169 genres carry no inception date
  > and 48 no country of origin.
- **Coverage rendered as a first-class displayed metric** — not a footnote, not a README caveat. The
  exclusion rate from the ingestion prose check (`docs/graph-semantics.md` §4.5) is part of this.
- **Component structure as a queryable, sliceable property** of the artifact, so "is this genre reachable"
  is answerable before a traversal is attempted rather than after it fails.
- **Slicing by era, region, density, and query type** across every eval metric, per `.claude/rules/evals.md`.

## Explicitly not in this phase

Architecture change of any kind — no new one-way doors, and the nine in `CLAUDE.md` are settled. No agent
loop edits; if density requires editing the agent, a seam broke and that is the finding, exactly as in
phase 2. No new model or provider. No SPA rebuild — phase 5 owns the visualization, and this phase feeds
it data rather than redesigning it. No retroactive change to a pinned artifact version that a published
eval number depends on.

## Key decisions this phase makes

- **The connectivity resolution** above. This is the phase's central decision and everything else follows
  from it.
- **Whether a second data source is added at all**, and if so which, under `04`'s stricter licensing rule
  where it conflicts with `01`.
- **How coverage renders.** A number on the screen is the requirement; the form is open. It must be
  legible to someone who has not read any of these docs.
- ~~**Whether the artist axis changes the component picture.**~~ It plausibly does — artist-level influence is
  ~100x denser than genre-level, and artists may bridge genre components that have no direct genre edge.
  **This should be measured early in the phase, because a positive result reshapes the whole decision.**

  > **Answered 2026-08-06, in phase 2 — see §0.** Measured, and positive: the deepest chain went from two
  > hops to six. This decision is closed and this phase inherits its consequences rather than making it.

## Definition of done

> **Status as of 2026-09-02 (§0):** **#2, #3 and #5 are already met.** #3 by phase 2 step 4, #5 by
> phase 3 step 7b, and **#2 by phase 5 step 9**, which rendered coverage to a user as a drawn panel
> rather than a footnote. *(This note read "#2 is half met" until the phase 5 close.)* What #2 still
> asks of this phase is that a new corpus cut keeps that panel honest. The items are left unedited so
> the phase is still judged against the whole list.

1. The connectivity question has a recorded answer with reasoning, and the product's claim matches it.
2. Coverage and density are displayed to a user, in numbers, without needing a footnote to be honest.
3. Component structure is queryable from the artifact.
4. Density along artists, geography, and time is real enough that a traversal names specific people,
   places, and dates rather than only genre labels.
5. Every eval metric is sliced by era, region, density, and query type.
6. **The agent package was not edited** to accommodate any of this.
7. Artifact schema changes are **additive** — no field removed or repurposed that a pinned version depends on.
8. No project copy anywhere claims coverage the graph does not have.

## Rules that govern this phase

- **"Grounded" is a provenance guarantee, not a truth guarantee.** This phase is where the temptation to
  overstate is strongest, because thin coverage is uncomfortable and inflating it is one adjective away.
- **The corpus skew must be visible in output, not disclaimed in a footnote** (`04` §4.5).
- **Contested is a first-class state**, not an error and not something to resolve.
- **Refusal is correct behavior**, and refusal accuracy is reported as a pair — true refusals and false
  refusals — always.
- **Evals run against a pinned artifact version.** A density change that moves the corpus without moving
  the pin silently invalidates every prior benchmark.
- **MusicBrainz CC0 core tables only**, 1 request/second, contactable User-Agent. **Wikipedia text is
  CC BY-SA** and the attribution is displayed.

## Known risks

- **The honest-number risk, and it is the main one.** A 46-component graph with 158 sourced edges is a
  modest artifact described accurately, and an impressive one described loosely. The second version is
  always one word away and would destroy the only claim this project actually makes.
- **Scope inflation into a second ingestion pipeline.** Resolution 3 is the most interesting option and
  the most expensive. v0.6 sits well past resume-ready (v0.3–v0.4), so the honest question at phase start
  is whether this phase should run at all yet, or whether the job search wants the time. `ROADMAP.md` §1
  already ranks this: on a tired week, the deployed URL beats the density work.
- **Artist-axis density may not bridge components**, in which case resolution 3 becomes materially more
  attractive and the phase gets more expensive. Measure before committing.
- ~~**Wikipedia prose-check defects carried forward.**~~ The mention counter over-reports because it counts
  category tags and navbox templates as prose (`docs/graph-semantics.md` §4.5). Fix before any number
  from it is displayed to a user or published as an eval result.

  > **Closed 2026-08-04, in phase 2 step 1.** `ingest.prosecheck.strip_markup` removes refs, templates
  > and tables, category and file links, and appendix sections. It retains 29% of the raw wikitext on a
  > typical genre article and roughly halves the hit count.
- **Geography and time are thinner than they look.** `P571` reaches back millennia, but sparse ancient
  coverage against dense modern coverage is exactly the slice where an aggregate looks healthy while the
  interesting part is empty.
