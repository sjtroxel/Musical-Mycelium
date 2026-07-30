# Rule: Graph semantics, data sources, and licensing

Canonical detail: `docs/planning/01-DATA-SOURCES.md` and `04-RISK-REGISTER.md` §4. Where `01` and `04`
disagree on licensing, **`04`'s stricter rule governs**. Hard rules:

- **P279 is `subclass of` — taxonomic, not historical.** "Bebop subclass-of jazz" is not "bebop derived
  from swing." The whole graph's meaning rests on this, and getting it wrong produces a graph of Wikidata's
  category structure rather than a graph of music history. Hand-validate 20 edges and write down what each
  predicate actually means **before** ingestion is coded. P737 is `influenced by`.
- **P279 chains climb out of the genre domain** (genre → "art form" → …). Ingestion needs an explicit
  boundary predicate or the graph grows a ceiling of meaningless abstractions.
- **The agent never queries Wikidata live.** WDQS is materially degraded in 2026 — queries that took 9
  seconds now time out, with a 60s query-time-per-minute-per-IP budget and 5 parallel queries per IP. Every
  agent tool call hits the pre-built local artifact. This is a good constraint: fast, deterministic, free,
  reproducible.
- **Stay on MusicBrainz CC0 core tables.** MusicBrainz is *not* uniformly CC0 — core data is CC0 but
  contributor-generated data is CC BY-NC-SA 3.0. A project whose entire pitch is *cited, correctly
  attributed grounding* cannot be sloppy about its own licenses. Also mandatory: 1 request/second and a
  contactable User-Agent.
- **Wikipedia text is CC BY-SA — display the attribution.** Not in a buried credits page.
- **Ingestion is not a Lambda.** The 15-minute ceiling rules it out. Build the artifact locally, upload it
  to S3. That is $0 and removes a whole class of complexity.
- **The artifact is versioned and immutable, with a manifest.** Everything downstream reads a pinned
  artifact version, never the internet. Evals that run against a moving corpus silently invalidate every
  prior benchmark.
- **Provenance is structural, not a feature.** Every node and edge carries `source`, `source_id`,
  `retrieved_at` from the first row written.
