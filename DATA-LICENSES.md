# Data licences

`LICENSE` is MIT and covers **the code**. It does not cover the corpus, and from artifact **v0.7.0** the
corpus is no longer under a single licence: it is a mixture of CC0 and CC BY-SA material. This file says
which parts are under which, because stating it now is cheap and stating it later is awkward —
`docs/planning/04-RISK-REGISTER.md` §4.3 predicts exactly that.

Written 2026-09-04, at phase 6 step 4, when DBpedia became the second source.

## What is in the artifact, and under what terms

| part | source | licence | attribution carried |
|---|---|---|---|
| Genre and artist **nodes** — id, label, inception, country | Wikidata | **CC0 1.0** (public domain dedication) | `source_id` (QID) + `revision_id` |
| `influenced_by` edges from **P737** | Wikidata | **CC0 1.0** | `source_id` = statement URI |
| `plays_genre` edges from **P136** | Wikidata | **CC0 1.0** | `source_id` = statement URI |
| `influenced_by` edges from **`dbo:stylisticOrigin`** (v0.7.0+) | DBpedia | **CC BY-SA 3.0** | `source_id` = resolvable DBpedia resource URI |
| `infobox_year` / `infobox_countries` on genre nodes (v0.7.1+) | English Wikipedia, `cultural_origins` infobox field | **CC BY-SA 4.0** | `infobox_source` = the article URL |

CC0 imposes no attribution requirement. This project attributes Wikidata anyway, because provenance is
the product rather than a compliance step.

**CC BY-SA does impose one, and it is met structurally.** Every DBpedia-sourced edge carries a resolvable
`http://dbpedia.org/resource/...` URI in `source_id` — the same field a Wikidata edge uses for its
statement URI. The attribution is therefore on the row itself and travels with the data, rather than
living in a credits page. `.claude/rules/graph-semantics.md` requires the attribution be displayed and
**not** buried; the SPA's visible attribution and link back is phase 6 step 8.

## Wikipedia text, which is no longer only a footnote

The ingestion reads English Wikipedia article text for two purposes: the prose check
(`ingest/prosecheck.py`), and **from v0.7.1, parsing the `cultural_origins` infobox field into
`infobox_year`, `infobox_precision` and `infobox_countries`** (`ingest/culturalorigins.py`). 107 genres
carry a date from that field and 91 a country — values Wikidata's `P571` and `P495` do not have.

Those are **facts extracted from CC BY-SA 4.0 text**, not prose copied from it, and each carries the
article URL in `infobox_source` as the attribution and link back. They are deliberately in their own
fields rather than merged into `inception_year` / `countries`, which remain Wikidata-only — so the
licence of any given value is determined by which field it sits in, not by inspection.

**Article prose itself is still not stored in the artifact** — `graph.json` holds identifiers, labels,
dates and countries, and no sentences.

It is stored in one place: `artifacts/*/exclusions.json` quotes a short excerpt of the subject article's
infobox `stylistic_origins` field in the `reason` of an `INFOBOX_ONLY` row, so a rejection can be
checked rather than taken on trust. 32 such rows at v0.2.0, a line or two each. **Wikipedia text is
CC BY-SA 4.0**, the excerpts are brief and factual, and the row names the subject article they came
from. Recorded here rather than omitted.

## What is *not* a source, despite appearing in the planning docs

**MusicBrainz is not ingested.** `docs/planning/01-DATA-SOURCES.md` and
`.claude/rules/graph-semantics.md` both discuss it — including the real trap that MusicBrainz is not
uniformly CC0, since core tables are CC0 while contributor-generated data is CC BY-NC-SA 3.0 — but no
MusicBrainz data has ever reached an artifact, and no code in `src/` references it. Verified 2026-09-04
by checking every `source` value in v0.5.0 and v0.6.0 (all `wikidata`) and grepping the package.

If MusicBrainz is ever ingested, the CC BY-NC-SA half is the thing to stay off: a **non-commercial**
share-alike clause is a materially different obligation from DBpedia's CC BY-SA, and it would be the
first term in this corpus that restricts *use* rather than requiring credit.

## The open question, stated rather than smoothed over

Whether incorporating CC BY-SA data into a committed artifact inside an MIT-licensed repository creates
a share-alike obligation on **the artifact** is a real question, and one this project is not qualified to
answer. It is recorded as named uncertainty §9.1 in
`docs/phases/phase-6-density-and-coverage-IMPLEMENTATION.md`.

The position taken is the conservative one, and it is defensible however the question resolves:

- per-source licences are stated (this file),
- every CC BY-SA row carries a resolvable link back to its source,
- the attribution is displayed in the product rather than buried,
- and the code licence is left alone, because MIT covers the code and the code is not derived from
  DBpedia.

Worth a real answer before v1.0. It is not worth guessing at now.
