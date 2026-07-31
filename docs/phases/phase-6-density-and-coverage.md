# Phase 6 — Density and Coverage (v0.6)

> **Scope doc.** Written 2026-07-31, after the P279/P737 hand-validation and before building. Held back
> from the 2026-07-30 scope pass on purpose, so it could be written against measurements rather than
> assumptions. Re-read it at the start of phase 6 and amend it — phases 1 through 5 will have taught
> things this doc cannot know.

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
- **Whether the artist axis changes the component picture.** It plausibly does — artist-level influence is
  ~100x denser than genre-level, and artists may bridge genre components that have no direct genre edge.
  **This should be measured early in the phase, because a positive result reshapes the whole decision.**

## Definition of done

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
- **Wikipedia prose-check defects carried forward.** The mention counter over-reports because it counts
  category tags and navbox templates as prose (`docs/graph-semantics.md` §4.5). Fix before any number
  from it is displayed to a user or published as an eval result.
- **Geography and time are thinner than they look.** `P571` reaches back millennia, but sparse ancient
  coverage against dense modern coverage is exactly the slice where an aggregate looks healthy while the
  interesting part is empty.
