# Phase 2 — Corpus and Traversal (v0.2)

> **Scope doc.** Written 2026-07-29, before building. Re-read it at the start of phase 2 and amend it where
> phase 1 taught something different — it was written before any of this existed.

## What this phase is for

To make the graph real. Phase 1 proves the pipeline end to end on a few hundred genres and one hardcoded hop;
this phase replaces both with the full corpus and genuine multi-hop traversal. The agent loop itself is
deliberately untouched — this phase thickens the `GraphStore` implementation and the ingestion artifact
behind an interface the agent already talks to.

This is the first test of whether the seams from phase 1 actually hold. If adding the full corpus requires
editing the agent, a seam broke and that is the finding.

## Delivers

- **Full ingestion:** ~6,324 Wikidata genres and ~7,936 derivation edges, plus the **artist axis (P737)**,
  plus MusicBrainz CC0 core tables for artists and releases.
- **Real multi-hop traversal** through `GraphStore` — `path`, `neighbors`, and search that work over the
  whole graph rather than one hardcoded hop.
- **A versioned, immutable artifact with a manifest**, built locally and uploaded to S3.
- **The genre-domain boundary predicate**, so P279 chains stop climbing out of music and into "art form."
- Coverage measured and recorded per era and region, so the documented skew becomes a number.

## Explicitly not in this phase

Agent planning and tool expansion (phase 3), the eval suite proper (phase 4), the SPA and any visualization
(phase 5), density beyond the base graph (phase 6). Contested-claim handling is *represented* in the data
here but not surfaced in a UI.

## Key decisions this phase makes

- **The storage backend**, picked from the $0 options: serialized graph in S3 loaded at Lambda init, SQLite
  baked into the container image, DuckDB over Parquet in S3, or a DynamoDB adjacency list (whose 25GB free
  tier is always-free, not 12-month). This is an explicit **two-way door** — it sits behind `GraphStore`, so
  picking wrong costs one new implementation of four methods, not a rewrite.
- **How the artifact is versioned and pinned**, because evals must run against a pinned version or every
  corpus change silently invalidates every prior benchmark.
- **Whether P279 and P737 stay separate predicates end to end.** They must. "Bebop subclass-of jazz" is not
  "bebop derived from swing," and an artist influence is not a genre derivation.

## Definition of done

1. The full corpus ingests locally and produces a versioned artifact plus manifest in S3.
2. A multi-hop query returns a path of three or more hops, with a source on every edge.
3. The artist axis answers at least one artist-influence query end to end.
4. P279 chains terminate at the genre-domain boundary rather than climbing to abstractions.
5. Phase 1's eval still passes against the new pinned artifact, and the pin is recorded.
6. **The agent package was not edited** to accommodate any of this.
7. Coverage by era and region is a recorded number, not a disclaimer.

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

- **P279 semantics at scale.** Twenty hand-validated edges in phase 1 is a sample, not a proof. The taxonomy
  may carry lineage well in dense modern genres and badly in sparse or ancient ones, which is exactly where
  slicing matters.
- **Artifact size versus Lambda memory.** Tens of MB is fine; verify rather than assume, and remember the
  `GraphStore` seam exists precisely so this is recoverable.
- **The sparse ancient end.** His design rule is scope the density, never the structure — so thin coverage
  for early eras is expected and must be rendered honestly rather than hidden or amputated.
- **Ingestion reproducibility.** A rebuild that produces a different graph from the same sources means the
  artifact is not really versioned.
