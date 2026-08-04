"""Build the versioned graph artifact from Wikidata and MusicBrainz.

Runs **locally**, not in Lambda — the 15-minute Lambda ceiling rules it out, and building locally then
uploading to S3 costs nothing and removes a class of complexity.

Contract (``docs/planning/01-DATA-SOURCES.md``, ``04-RISK-REGISTER.md`` section 4):

- Output is an immutable, versioned artifact plus a manifest. Everything downstream reads a pinned
  version of that artifact and never the internet.
- Every node and edge carries ``source``, ``source_id``, ``retrieved_at`` from the first row written.
  Provenance is structural here, not a feature bolted on later.
- Wikidata P279 is ``subclass of`` (taxonomic), P737 is ``influenced by``. These are not the same thing
  and conflating them produces a graph of Wikidata's category structure rather than of music history.
  **Hand-validated 2026-07-31 across 47 edges: P279 carried lineage in ZERO of them.** P279 is therefore
  not ingested at all, and the findings are in ``docs/graph-semantics.md``.
- MusicBrainz core tables only (CC0). Contributor data is CC BY-NC-SA 3.0 and is out of scope. 1
  request/second, contactable User-Agent. *(Deferred to phase 6 — no v0.x query needs a release.)*

**Built as of 2026-08-02 (phase 1, step 3).** ``artifact.py`` writes and verifies a versioned artifact;
``wikidata.py`` fetches P737 genre-to-genre edges, type-filters both ends, and stamps provenance. The
schema itself lives in ``graph.schema`` — see that module for why the dependency points that way.

**Added 2026-08-04 (phase 2, step 1).** ``prosecheck.py`` is the hardened Wikipedia disconfirmation
check: three evidence tiers, markup stripping, self-match masking and redirect detection, split into a
pure analysis layer and a thin fetch layer so it is testable without a network. It is deterministic and
free, which is what lets one piece of code be a corpus filter, a displayed coverage metric and a Tier 1
eval at once.

v0.1 ingests a **hand-verified list** of 21 edges rather than running a discovery query; the record is
``docs/phases/phase-1-edge-verification.md``. The pipeline shape is the real one, so phase 2 step 2
replaces only where the candidate pairs come from.
"""
