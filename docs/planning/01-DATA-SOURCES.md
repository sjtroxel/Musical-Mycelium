# Music Lineage Project — Data Sources (verified live 2026-07-24)

**Rule honored:** verify the source is real, free, and accessible *before* building anything on it. Done live on 2026-07-24 via direct SPARQL queries and a check of MusicBrainz's data terms.

---

## Primary: Wikidata — the lineage backbone (CC0, free)

Endpoint: `https://query.wikidata.org/sparql` (SPARQL, GET or POST, JSON results, requires a descriptive `User-Agent` header, **no API key**). The lineage sjtroxel wants to map is **already encoded as graph edges** here.

Key entities / properties:

| Item | Meaning |
|---|---|
| `Q188451` | "music genre" (the instance-of target) |
| `P279` | subclass of — genre → parent-genre derivation (the genre family tree) |
| `P737` | "influenced by" — artist→artist and work influence edges |
| `P571` | inception — dates genres/forms |
| `P106` / `Q639669` | occupation / musician |

**Verified live results (2026-07-24):**

- **6,324** music genres (`COUNT DISTINCT` instance-of `Q188451`).
- **~7,936** genre→genre derivation edges (`P279` between two genres) — a real, sizable family tree.
- **"Influenced by" (`P737`) edges are populated and real** — live sample: Chopin ← Mozart, Rachel Portman ← Mozart, Alanis Morissette ← Patti Smith, Carina Round ← Patti Smith, and a cluster ← Kate Bush.
- **Temporal reach:** ordering genres by inception (`P571`) ascending, the oldest nodes land at **~2000 BCE** (a `-1999` timestamp) plus a **medieval cluster 200–1000 CE**, thickening from there. The skeleton genuinely spans millennia — **sparse at the ancient end, dense at the modern end**, which is exactly the full-history-skeleton design shape (see `00-DESIGN-BRIEF` §3.1).

## Secondary: MusicBrainz — relational depth (mostly CC0 / public domain)

- **Free full database dumps twice weekly** + a public API (`https://musicbrainz.org/ws/2/`), with relationship includes (`artist-rels`, `work-rels`, `recording-rels`, etc.).
- **Scale (as of May 2026):** ~2.8M artists, ~5.4M releases, ~38.7M recordings, plus relationships.
- **Licensing:** most content is **CC0** (effectively public domain); some per-item fields are CC BY-NC-SA 3.0 — check per field before any *commercial* use (portfolio/non-commercial = fine).
- Docs: `musicbrainz.org/doc/MusicBrainz_Database/Download`, `metabrainz.org/datasets`.

## Tertiary: Wikipedia / DBpedia — narrative for explanations

- The *why* behind each edge, in cited prose. RAG target for generating grounded, cited explanations of a given lineage.

---

## Honest caveats (named, not hidden)

- **"Influence" is subjective and contested.** Handle by grounding + citing *sourced* edges only, never asserting, and flagging contested claims (design principle §3.2). This is the bias-by-construction guarantee.
- **Ancient / pre-notation eras are sparse.** By design — that is the fill-in-later part of the skeleton, not a gap to hide.
- **Old-genre inception dates are approximate/contested.** Surface them as sourced/approximate, never as precise fact.

## Step zero of the build (before any architecture commit)

Re-run representative Wikidata queries and pull a MusicBrainz sample **through the actual ingestion path**; confirm rate limits and dump sizes; sanity-check the graph shape on one real slice (e.g., a single genre family) before committing the storage/architecture decision. Verify the source before building on it — every time.
