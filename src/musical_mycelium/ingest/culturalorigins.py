"""Dates and places from the English Wikipedia ``cultural_origins`` infobox field. Phase 6 step 6.

DoD #4 wants a traversal to name specific places and dates rather than only genre labels, and at v0.7.0
**198 of 675 genres carry no inception year and 222 carry no country** — because Wikidata's ``P571`` and
``P495`` simply have no value for them. Re-reading Wikidata does not fix that; it was already re-read for
every genre in steps 2 and 4, and the gap is the source's, not the crawl's.

## Why not DBpedia, which already exposes this field

DBpedia extracts the same infobox into ``dbp:culturalOrigins``, and **it is not ingestable.** Measured on
2026-09-04 over the 167 undated genres that have a DBpedia resource: 69 have a value, and of those 54 are
numeric with **5 negative** and 20 are not numbers at all. The extraction is lossy in a way that would put
real errors into a corpus whose whole pitch is provenance:

    Wikipedia "17th century"                    -> DBpedia  17
    Wikipedia "Early 2010s, Brooklyn, New York" -> DBpedia  2010.0 AND 2020.0
    Wikipedia "late 1980s" (sampledelia)        -> DBpedia  -1980.0
    Wikipedia "Ancient, worldwide"              -> DBpedia  "Ancient, worldwide"

Both Wikipedia readings above were checked against the live article text rather than inferred. So this
module parses the **raw wikitext** instead, where the distinction between "1990s" and "1990" survives.

## The precision rule, which is the reason this is worth doing carefully

``cultural_origins`` says "1950s" and "17th century" far more often than it says a year.
``Node.inception_precision`` exists precisely because *"rendering a decade-precision value as 1975 states
something Wikidata does not"* — so a parser that flattened "1950s" to the year 1950 would commit the exact
error the field was added to prevent, just with a new source to blame. Every value here carries the
precision it was stated at, using the **same codes P571 uses**: 7 century, 8 decade, 9 year.

Century convention matched to the corpus rather than invented: ``opera`` is 1600 at precision 7 and means
the 17th century, ``mariachi`` 1800 means the 19th. So *N*th century maps to ``(N - 1) * 100``.

## Provenance: these are NOT Wikidata dates and never overwrite one

``inception_year`` and ``countries`` stay exactly what ``P571`` and ``P495`` said, untouched. What this
module fills is a **parallel, separately-named set** — ``infobox_year``, ``infobox_precision``,
``infobox_countries``, ``infobox_source`` — so nothing can read a Wikipedia infobox date as a Wikidata
statement. That is the same rule step 4 applied when it declined to mark DBpedia-discovered nodes
``SOURCE_DBPEDIA``: the field records where the data actually came from, and merging two sources into one
field to make a number look fuller is the failure both rules exist to prevent.

**Wikipedia text is CC BY-SA 4.0**, so ``infobox_source`` carries the article URL and ``DATA-LICENSES.md``
states the terms. Attribution is structural here for the same reason it is on DBpedia edges.

## What it deliberately refuses

"Ancient", "worldwide", "Indigenous music worldwide" and a bare place with no date all parse to nothing
rather than to a guess. A range — "Late 1950s-Early 1960s" — takes the **earliest** value, because the
field is about where a genre *began*, and records it at the precision that earliest value was stated at.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: Wikidata's precision codes, reused rather than re-invented so a consumer needs one vocabulary.
PRECISION_CENTURY = 7
PRECISION_DECADE = 8
PRECISION_YEAR = 9

#: ``<ref>...</ref>``, HTML comments and the ``{{...}}`` templates that wrap citations. Stripped first
#: because a citation frequently contains a four-digit year and would otherwise be read as the date.
_NOISE = (
    re.compile(r"<ref[^>]*>.*?</ref>", re.DOTALL | re.IGNORECASE),
    re.compile(r"<ref[^>]*/>", re.IGNORECASE),
    re.compile(r"<!--.*?-->", re.DOTALL),
    re.compile(r"\{\{[^{}]*\}\}"),
    re.compile(r"<[^>]+>"),
)

#: ``[[Metro Manila|Manila]]`` -> ``Manila``; ``[[Cuba]]`` -> ``Cuba``. The *display* text is kept,
#: because that is what the article actually says and the pipe target is often a longer formal name.
_WIKILINK = re.compile(r"\[\[(?:[^\]|]*\|)?([^\]|]+)\]\]")

_DECADE = re.compile(r"\b(\d{3,4})0s\b")
_CENTURY = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)[-\s]+century\b", re.IGNORECASE)
#: A bare year, and deliberately NOT matched when followed by ``s`` — "1950s" is a decade and reading it
#: as the year 1950 is the precision error this module exists to avoid.
_YEAR = re.compile(r"\b(1[0-9]{3}|20[0-2][0-9])\b(?!s)")


@dataclass(frozen=True, slots=True)
class CulturalOrigin:
    """One parsed ``cultural_origins`` value.

    ``raw`` is kept so a reader can always see what the parse was made from, and so a disagreement
    between the parse and the source is checkable rather than a matter of trust.
    """

    year: int | None = None
    precision: int | None = None
    countries: tuple[str, ...] = ()
    raw: str = ""

    @property
    def has_date(self) -> bool:
        return self.year is not None


def strip_markup(value: str) -> str:
    """Remove refs, templates and HTML, then flatten wikilinks to their display text."""
    text = value
    for pattern in _NOISE:
        text = pattern.sub(" ", text)
    text = _WIKILINK.sub(r"\1", text)
    return re.sub(r"\s+", " ", text).strip()


def parse_date(text: str) -> tuple[int | None, int | None]:
    """The earliest date the text states, with the precision it was stated at.

    **Order matters and it is not arbitrary.** Decade is tried before bare year because "1950s" contains
    a substring that looks like a year, and century before both because "17th century" contains "17".
    Getting this order wrong produces a confident, wrong, precise-looking number — which is worse than
    no date at all in a corpus that publishes its own coverage gaps.

    A range takes the earliest value: ``cultural_origins`` describes where a genre *began*.
    """
    decades = [int(m.group(1) + "0") for m in _DECADE.finditer(text)]
    centuries = [int(m.group(1)) for m in _CENTURY.finditer(text)]
    # A century mention makes any bare year inside it (rare) redundant, and a decade mention makes the
    # year reading wrong, so each tier is only consulted when the ones above it found nothing.
    if centuries:
        return (min(centuries) - 1) * 100, PRECISION_CENTURY
    if decades:
        return min(decades), PRECISION_DECADE
    years = [int(m.group(1)) for m in _YEAR.finditer(text)]
    if years:
        return min(years), PRECISION_YEAR
    return None, None


#: Abbreviations that appear constantly in this field and denote a country the corpus already names.
#: **A closed, hand-written list of unambiguous forms — not a fuzzy matcher.** "U.S." is not a guess
#: about what a string might mean; anything requiring judgement is left to miss instead.
_ALIASES = {
    "u.s.": "United States",
    "us": "United States",
    "usa": "United States",
    "u.s.a.": "United States",
    "united states of america": "United States",
    "u.k.": "United Kingdom",
    "uk": "United Kingdom",
    "britain": "United Kingdom",
    "great britain": "United Kingdom",
}


def parse_places(text: str, known: frozenset[str]) -> tuple[str, ...]:
    """Country labels the text names, restricted to vocabulary the corpus already uses.

    **Deliberately conservative: a label is accepted only if it already appears as a ``P495`` value in
    the corpus** (or is one of the closed set of abbreviations in :data:`_ALIASES`). ``cultural_origins``
    is prose and contains "Ibero-America", "worldwide", "Metro Manila" and "Captaincy General of Puerto
    Rico" alongside real country names. Inventing a country label from free text would put an unsourced
    geography into the published coverage numbers, and those numbers are what this project points at when
    it says its skew is visible rather than disclaimed. The miss rate is published instead.

    **Whole-word search rather than splitting on punctuation.** Splitting missed "1920s China", where the
    country is not its own comma-delimited token — found by running the parser against live articles. The
    search is anchored on word boundaries so "Chinatown" cannot match "China", and longest-label-first so
    a country whose name contains another's is not shadowed by it.

    **The known limitation, measured rather than glossed: this cannot introduce a country the corpus does
    not already hold, which structurally caps how much it can improve the non-Western skew.** ``C-pop``
    states "1920s China" and gets no country, because no ``P495`` value in the corpus is "China".

    Widening it needs a *sourced* country vocabulary and Wikidata's own labels do not cleanly supply one
    — measured 2026-09-04: ``P31/P279* wd:Q6256`` yields 654 labels that **exclude "China"** (the label
    is "People's Republic of China"), and adding ``skos:altLabel`` brings 2,088 strings of which 252 are
    two- and three-letter ISO codes — ``AN``, ``BR``, ``CA``, ``DE`` — that would false-positive on
    ordinary prose. A loose geography rule is worse than a narrow one here, because a wrong country is
    invisible in an answer while a missing one is merely absent.

    **The principled upgrade, not built here:** resolve each ``[[wikilink]]`` target in the field to its
    Wikidata QID and accept it when that entity is an instance of a country. Exact and fully sourced,
    at the cost of another lookup per link.
    """
    candidates = sorted(known, key=len, reverse=True)
    found: list[str] = []
    for label in candidates:
        if re.search(rf"\b{re.escape(label)}\b", text, re.IGNORECASE) and label not in found:
            found.append(label)
    for alias, label in _ALIASES.items():
        if (
            label in known
            and label not in found
            and re.search(rf"(?<![\w.]){re.escape(alias)}(?![\w])", text, re.IGNORECASE)
        ):
            found.append(label)
    return tuple(found)


def parse(value: str, known_countries: frozenset[str] = frozenset()) -> CulturalOrigin:
    """Parse one raw ``cultural_origins`` wikitext value. Pure."""
    text = strip_markup(value)
    year, precision = parse_date(text)
    return CulturalOrigin(
        year=year,
        precision=precision,
        countries=parse_places(text, known_countries),
        raw=text,
    )


#: The infobox row itself. The value runs to the next field or to the end of the template.
#:
#: **``[ \t]*`` after the ``=``, never ``\s*``, and that is a real bug rather than a nicety.** With
#: ``\s*`` the whitespace class crosses the newline, so a field with an *empty* value consumes the row
#: below it: ``comedy music`` has ``| cultural_origins  =`` followed by ``| instruments = ...`` and
#: parsed as though its cultural origins were a list of instruments. Found by running the parser against
#: live articles rather than by a test — the fixtures all had values.
_FIELD = re.compile(r"\|\s*cultural_origins\s*=[ \t]*(.*?)(?=\n\s*\|\s*\w+\s*=|\n\}\})", re.DOTALL)


def extract_field(wikitext: str) -> str:
    """The raw ``cultural_origins`` value from an article's wikitext, or ``""``.

    Matched up to the next infobox field rather than to the end of the line, because the value wraps
    across lines often enough that a line-based match silently truncates the place half.
    """
    match = _FIELD.search(wikitext)
    return match.group(1).strip() if match else ""


# --- the crawl -------------------------------------------------------------------------------------


WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
USER_AGENT = "musical-mycelium/0.7.1 (https://github.com/sjtroxel; sjtroxel@protonmail.com)"


def fetch_wikitext(title: str, *, pause: float = 1.0) -> str:
    """Lead-section wikitext for one article. One request per second, which is the contract."""
    import json as _json
    import time as _time
    import urllib.parse as _parse
    import urllib.request as _request

    query = _parse.urlencode(
        {"action": "parse", "page": title, "prop": "wikitext", "section": "0", "format": "json"}
    )
    request = _request.Request(f"{WIKIPEDIA_API}?{query}", headers={"User-Agent": USER_AGENT})
    try:
        with _request.urlopen(request, timeout=45) as response:
            payload = _json.load(response)
        return str(payload["parse"]["wikitext"]["*"])
    except Exception:
        # A missing or renamed article is an absence, not a failure. The genre keeps its empty fields
        # and appears in the published miss count, which is the honest outcome for a coverage crawl.
        return ""
    finally:
        _time.sleep(pause)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI, hits the network
    """Fill ``infobox_*`` for genres Wikidata has no date or country for, and write the next artifact."""
    import argparse
    import sys
    from dataclasses import replace

    from musical_mycelium.graph.schema import NODE_KIND_GENRE, Artifact
    from musical_mycelium.ingest import artifact as artifact_io
    from musical_mycelium.ingest import prosecheck
    from musical_mycelium.ingest.wikidata import artifact_dir

    parser = argparse.ArgumentParser(
        description="Parse Wikipedia cultural_origins into the artifact."
    )
    parser.add_argument("--source", default="0.7.0")
    parser.add_argument("--version", default="0.7.1")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    source = Artifact.load(artifact_dir(args.source))
    known_countries = frozenset(c for n in source.nodes for c in n.countries)
    gaps = [
        n
        for n in source.nodes
        if n.kind == NODE_KIND_GENRE and (n.inception_year is None or not n.countries)
    ]
    print(
        f"source v{args.source}: {len(source.nodes)} nodes; {len(gaps)} genres missing a date or a "
        f"country; {len(known_countries)} country labels in the P495 vocabulary",
        file=sys.stderr,
    )

    entities = prosecheck.fetch_entities([n.id for n in gaps])
    titles = {
        n.id: entities[n.id].enwiki_title
        for n in gaps
        if n.id in entities and entities[n.id].enwiki_title
    }
    print(f"  {len(titles)}/{len(gaps)} have an English Wikipedia article", file=sys.stderr)

    parsed: dict[str, CulturalOrigin] = {}
    for index, (qid, title) in enumerate(sorted(titles.items(), key=lambda kv: kv[1]), start=1):
        print(f"  [{index}/{len(titles)}] {title}", file=sys.stderr)
        raw = extract_field(fetch_wikitext(title))
        if raw:
            parsed[qid] = parse(raw, known_countries)

    import urllib.parse as _parse

    nodes = tuple(
        replace(
            node,
            infobox_year=parsed[node.id].year,
            infobox_precision=parsed[node.id].precision,
            infobox_countries=parsed[node.id].countries,
            infobox_source=(
                "https://en.wikipedia.org/wiki/"
                + _parse.quote(titles[node.id].replace(" ", "_"), safe="")
            ),
        )
        if node.id in parsed and (parsed[node.id].year or parsed[node.id].countries)
        else node
        for node in source.nodes
    )
    filled = [n for n in nodes if n.infobox_year or n.infobox_countries]
    dates = sum(1 for n in filled if n.infobox_year)
    places = sum(1 for n in filled if n.infobox_countries)
    print(
        f"  {len(parsed)} articles carried the field; {dates} gained a date, {places} gained a country",
        file=sys.stderr,
    )

    directory = artifact_dir(args.version)
    directory.mkdir(parents=True, exist_ok=True)
    snapshot = {n.id: n.revision_id for n in nodes if n.kind == NODE_KIND_GENRE and n.revision_id}
    manifest = artifact_io.write(
        Artifact(nodes=nodes, edges=source.edges),
        directory,
        artifact_version=args.version,
        generator="musical_mycelium.ingest.culturalorigins",
        predicate="P737 + P136 + dbo:stylisticOrigin (influenced_by)",
        source="dbpedia+wikidata+enwiki",
        source_snapshot=snapshot,
        overwrite=args.overwrite,
        verification_record="docs/phases/phase-6-density-and-coverage-IMPLEMENTATION.md",
    )
    print(
        f"wrote v{args.version}: {manifest.node_count} nodes, {manifest.edge_count} edges",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
