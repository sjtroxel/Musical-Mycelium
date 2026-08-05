# Phase 2 — Corpus and Traversal (v0.2)

> **Scope doc.** Written 2026-07-29, before building. Re-read it at the start of phase 2 and amend it where
> phase 1 taught something different — it was written before any of this existed.
>
> **AMENDED 2026-08-04, approved by sjtroxel.** It was written two days before the P279/P737 validation,
> and four items rested on an assumption that validation falsified. Amendments A1 (corpus numbers), A2
> (MusicBrainz to phase 6), A3 (P279 to phase 6) and A4 (DoD #6 restated) are applied below and marked
> inline. The reasoning is in `phase-2-corpus-and-traversal-IMPLEMENTATION.md` §1 — that is the record,
> this is the map.

## What this phase is for

To make the graph real. Phase 1 proves the pipeline end to end on a few hundred genres and one hardcoded hop;
this phase replaces both with the full corpus and genuine multi-hop traversal. The agent loop itself is
deliberately untouched — this phase thickens the `GraphStore` implementation and the ingestion artifact
behind an interface the agent already talks to.

This is the first test of whether the seams from phase 1 actually hold. If adding the full corpus requires
editing the agent, a seam broke and that is the finding.

## Delivers

- **Full ingestion of the P737 lineage corpus** — all 351 genre-out edges, type-filtered on both ends and
  passed through the automated Wikipedia prose check, yielding a target of **120–160 sourced edges over
  roughly 200 genres**, plus the **artist axis (P737 artist-to-artist, Wikidata only)**.

  > **A1, 2026-08-04.** This line originally read *"~6,324 Wikidata genres and ~7,936 derivation edges,
  > plus MusicBrainz CC0 core tables for artists and releases."* Those are **P279** counts, and P279 is
  > category membership, not derivation — the word "derivation" was the exact conflation `04` §4.4 warned
  > about. The lineage corpus is 351 P737 edges, of which 158 held a PROSE tier and 158 is an upper bound.
  > **A2:** MusicBrainz moves to phase 6; nothing in `SPEC.md` §2 needs a release, and it carries a new
  > client, a 1-req/s budget and a CC0-vs-CC-BY-NC-SA licensing surface for no current query.

- **Real multi-hop traversal** through `GraphStore` — `path`, `neighbors`, and search that work over the
  whole graph rather than one hardcoded hop.
- **A versioned, immutable artifact with a manifest**, built locally, baked into the container image and
  published to S3.
- **Bounded type filtering on both ends of every edge** — a membership test against `Q188451` via
  `P31/P279*`, with rejected entities recorded by reason.

  > **A3, 2026-08-04.** This line originally promised *"the genre-domain boundary predicate, so P279
  > chains stop climbing out of music and into 'art form.'"* P279 is **not ingested** at v0.1 and moves to
  > phase 6 with the rest of the taxonomy work: its only payoffs are taxonomic connectivity and a taxonomy
  > display, and `docs/graph-semantics.md` §5 assigns the connectivity question to phase 6 explicitly.
  > The boundary problem is contained rather than solved — asking P279 only "does this climb reach
  > Q188451" makes both the vertical escape (`bebop -> … -> oscillation`) and the lateral one
  > (`blues -> music of North America`) unreachable by construction.

- Coverage measured and recorded per era and region, so the documented skew becomes a number.

## Explicitly not in this phase

Agent planning and tool expansion (phase 3), the eval suite proper (phase 4), the SPA and any visualization
(phase 5), density beyond the base graph (phase 6). Contested-claim handling is *represented* in the data
here but not surfaced in a UI.

**Added 2026-08-04 by A2 and A3:** MusicBrainz in any form, and P279 ingestion. Both move to phase 6.
Resolving the 46-component connectivity question moves with them — this phase *measures* the component
structure and states the constraint honestly; it does not fix it.

## Key decisions this phase makes

- **The storage backend**, picked from the $0 options: serialized graph in S3 loaded at Lambda init, SQLite
  baked into the container image, DuckDB over Parquet in S3, or a DynamoDB adjacency list (whose 25GB free
  tier is always-free, not 12-month). This is an explicit **two-way door** — it sits behind `GraphStore`, so
  picking wrong costs one new implementation of four methods, not a rewrite.
- **How the artifact is versioned and pinned**, because evals must run against a pinned version or every
  corpus change silently invalidates every prior benchmark.
- **Whether P279 and P737 stay separate predicates end to end.** They must. "Bebop subclass-of jazz" is not
  "bebop derived from swing," and an artist influence is not a genre derivation. *(A3: at v0.2 this is
  enforced by absence — P279 is not in the artifact, and `agent/claims.py:36` is a second lock. The
  decision returns when phase 6 ingests it.)*

## Definition of done

1. The full corpus ingests locally, runs the prose check in-pipeline, and produces a versioned artifact,
   a manifest, and an **exclusions file with a per-edge reason for every rejected candidate**.
2. A multi-hop query returns **the longest sourced path the corpus contains between the two genres**,
   with a source on every edge, and the corpus publishes how deep that can go.

   > **A5, 2026-08-05, decided by sjtroxel.** This read *"a path of three or more hops."* **The corpus
   > cannot supply three.** Measured over artifact v0.2.0 (`docs/graph-semantics.md` §5.1): of 28,392
   > ordered pairs, **133 are one hop apart, 13 are two, and none are three or more.**
   >
   > The original number came from reading the graph's **diameter** — 14 hops on the 7/31 estimate, 10
   > on the real corpus — as though it were the available path depth. It is not. Diameter is measured
   > *ignoring* edge direction; a path has to *follow* it. The two differ by a factor of five here.
   >
   > This is not an ingestion gap that more crawling closes. `ingest/discovery.py`'s query is already
   > global over every music genre carrying a P737 statement, so there is no unexplored frontier —
   > Wikidata's genre-level P737 is flat, and the graph is broad and shallow by nature, not by omission.
   >
   > So the item is amended to what the data supports, and the flatness becomes a **published number**
   > rather than a missed target: `/health` and the `done` frame carry `structure`, including
   > `max_path_hops`. Depth is a corpus problem, and the artist axis is where it plausibly comes from.
   > Restating a two-hop result as "multi-hop" would be the exact overclaim `CLAUDE.md` exists to
   > prevent.
3. The artist axis answers at least one artist-influence query end to end, from Wikidata P737 only.
4. **The type filter is a bounded membership test against `Q188451` on both ends of every edge**, with
   rejected entities recorded by reason. *(A3 — was: "P279 chains terminate at the genre-domain
   boundary." P279 is not ingested, so the original item had nothing to apply to.)*
5. Phase 1's five gold cases still pass against the new pinned artifact, and the pin is recorded.
6. **`agent/loop.py`'s `run()` and `agent/claims.py`'s `gate()` were not edited** to accommodate the
   corpus.

   > **A4, 2026-08-04.** This read *"the agent package was not edited to accommodate any of this."* That
   > is stricter than the invariant it protects: `CLAUDE.md` invariant 4 forbids editing **the loop**,
   > and `tools.py` lives inside `agent/`, so the original wording would have forbidden registering a
   > tool — the one thing invariant 4 explicitly permits. Tool registrations and the multi-subject
   > synthesis path are expected changes. The seam that must not move is `synthesize()` taking exactly
   > one `ApprovedClaimSet` and having no way to reach the graph, the query, or the rejected claims.

7. Coverage by era and region is a recorded number, not a disclaimer.
8. The artifact is published to S3, versioned and immutable, **and still baked into the container image** —
   the image copy keeps the cold path free of a network fetch; the S3 copy is what makes a pin provable
   months later.

## Data rules that govern this phase

- **Never query Wikidata live from the agent.** WDQS is materially degraded — queries that once took 9
  seconds now time out, under a 60s-per-minute-per-IP budget. Ingestion runs locally against it; the agent
  only ever reads the artifact.
- **Ingestion is not a Lambda.** The 15-minute ceiling rules it out. Build locally, upload the artifact.
- **MusicBrainz CC0 core tables only.** Contributor-generated data is CC BY-NC-SA 3.0 and is out of scope.
  1 request/second, contactable User-Agent, both mandatory.
- **Wikipedia text is CC BY-SA** — display the attribution, not in a buried credits page.
- Where `01-DATA-SOURCES.md` and `04-RISK-REGISTER.md` disagree on licensing, **`04`'s stricter rule governs**.

## Known risks

- **P737 is not uniformly historical, and the prose check structurally cannot catch it.** *(Replaces the
  original "P279 semantics at scale" risk, which the 2026-07-31 validation answered decisively — 47 edges
  read, zero historical.)* Some P737 edges encode taxonomy: `extreme metal <- heavy metal` is supported
  only by *"an umbrella term for a number of related heavy metal subgenres,"* and "is a subgenre of Y"
  contains a real, findable mention of Y. The check flags a taxonomic lead sentence for triage; it cannot
  reject on it. See `docs/graph-semantics.md` §4.8.
- **The hardened check will shrink the corpus, not grow it.** Every defect fixed in step 1 removes *false*
  PROSE, so the corpus likely lands below 158. If it lands near v0.1's 21, that is a finding about the
  data rather than a failure of the phase — and it makes phase 6's second-source work urgent.
- **Artifact size versus Lambda memory.** Tens of MB is fine; verify rather than assume, and remember the
  `GraphStore` seam exists precisely so this is recoverable.
- **The sparse ancient end.** His design rule is scope the density, never the structure — so thin coverage
  for early eras is expected and must be rendered honestly rather than hidden or amputated.
- **Ingestion reproducibility.** A rebuild that produces a different graph from the same sources means the
  artifact is not really versioned.
