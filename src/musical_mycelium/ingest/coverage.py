"""Enrich genre nodes with P571 (inception) and P495 (country of origin).

Scope-doc DoD #7: era and region have to be **recorded quantities**, not a disclaimer. This is the fetch
that supplies them; ``graph.coverage`` is what turns them into numbers.

**One SPARQL query, no article refetch, and that is the whole design.** The corpus moves — a sentence
that supported an edge in the morning can be gone by evening (scope doc A6.6) — so a build that only
needs two new *properties* must not re-read prose it already has. Every existing node and edge, and
every provenance field on them, is carried across untouched.

**Precision is fetched, not inferred.** Wikidata records how precise each date is, and 22 of the 141
dated genres are coarser than a year. Reading a decade-precision value as a year would state something
the source does not — the "grounded slides into correct" failure this project is built against. The
query asks for ``timePrecision`` alongside ``timeValue`` so the artifact can carry both.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, replace
from typing import Any

from musical_mycelium.graph.schema import NODE_KIND_GENRE, Artifact, Node

PROPERTY_INCEPTION = "P571"
PROPERTY_COUNTRY = "P495"


@dataclass(frozen=True, slots=True)
class Facts:
    """What one live read told us about a genre's era and origin."""

    inception_year: int | None = None
    inception_precision: int | None = None
    countries: tuple[str, ...] = ()


def coverage_query(qids: list[str]) -> str:
    """Inception with its precision, and every country of origin, for the given genres.

    ``OPTIONAL`` on both, deliberately: a genre with neither must still come back as a row, because the
    absences are the measurement. A filtering triple would silently drop exactly the nodes DoD #7 is
    asking about.
    """
    values = " ".join(f"wd:{qid}" for qid in sorted(qids))
    return f"""
SELECT ?g ?inception ?precision ?countryLabel WHERE {{
  VALUES ?g {{ {values} }}
  OPTIONAL {{
    ?g p:{PROPERTY_INCEPTION}/psv:{PROPERTY_INCEPTION} ?node .
    ?node wikibase:timeValue ?inception ; wikibase:timePrecision ?precision .
  }}
  OPTIONAL {{ ?g wdt:{PROPERTY_COUNTRY} ?country . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
"""


def parse_coverage(rows: list[dict[str, Any]]) -> dict[str, Facts]:
    """Fold the query's rows into one ``Facts`` per genre.

    A genre appears on several rows when it has several countries — 218 rows for 169 genres on the
    2026-08-06 read. Countries accumulate; inception is the same on every row for a given genre.
    """
    out: dict[str, Facts] = {}
    for row in rows:
        qid = row["g"]["value"].rsplit("/", 1)[1]
        current = out.get(qid, Facts())

        year = current.inception_year
        precision = current.inception_precision
        if "inception" in row and year is None:
            # "1975-01-01T00:00:00Z" and, for very early genres, "0500-01-01T00:00:00Z" — so the year
            # is the leading component up to the first "-", zero-padded, not an int() of the whole.
            year = int(row["inception"]["value"].split("-", 1)[0])
            precision = int(row["precision"]["value"]) if "precision" in row else None

        countries = current.countries
        label = row.get("countryLabel", {}).get("value")
        if label and label not in countries:
            countries = (*countries, label)

        out[qid] = Facts(
            inception_year=year, inception_precision=precision, countries=tuple(sorted(countries))
        )
    return out


def enrich(artifact: Artifact, facts: dict[str, Facts]) -> tuple[Node, ...]:
    """Genre nodes carrying their era and origin. Artist nodes pass through untouched.

    P571 and P495 are genre properties; an artist's equivalents are different properties entirely and
    are out of scope. Stamping an artist node with an empty ``countries`` would be accurate and
    misleading at once — it would read as "no country recorded" rather than "never asked".
    """
    return tuple(
        replace(
            node,
            inception_year=facts[node.id].inception_year,
            inception_precision=facts[node.id].inception_precision,
            countries=facts[node.id].countries,
        )
        if node.kind == NODE_KIND_GENRE and node.id in facts
        else node
        for node in artifact.nodes
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build", metavar="VERSION", required=True, help="artifact version to write"
    )
    # Mirrors wikidata.py's flag and exists for the same narrow case: rebuilding a version that has not
    # been released yet. Artifacts are immutable once published, and the writer refuses by default.
    parser.add_argument(
        "--force", action="store_true", help="rebuild an unreleased version in place"
    )
    args = parser.parse_args(argv)

    from musical_mycelium.graph.coverage import analyse as analyse_coverage
    from musical_mycelium.ingest import artifact as artifact_io
    from musical_mycelium.ingest.wikidata import artifact_dir, sparql

    source_dir = artifact_dir()
    artifact = Artifact.load(source_dir)
    manifest = artifact_io.read_manifest(source_dir)

    genres = [node.id for node in artifact.nodes if node.kind == NODE_KIND_GENRE]
    print(f"Reading P571 and P495 for {len(genres)} genres (one query)...", file=sys.stderr)
    facts = parse_coverage(sparql(coverage_query(genres)))
    print(f"  {len(facts)} genres returned", file=sys.stderr)

    enriched = Artifact(nodes=enrich(artifact, facts), edges=artifact.edges)
    result = analyse_coverage(enriched)

    written = artifact_io.write(
        enriched,
        artifact_dir(args.build),
        overwrite=args.force,
        artifact_version=args.build,
        generator="musical_mycelium.ingest.coverage --build",
        predicate=manifest.predicate,
        source=manifest.source,
        source_snapshot=manifest.source_snapshot,
        verification_record=manifest.verification_record,
        notes=(
            f"Adds P571 (inception) and P495 (country of origin) to the genre axis of "
            f"v{manifest.artifact_version}, from a single SPARQL read. No article refetch: every node, "
            f"edge and provenance field is carried across unchanged, so the counts and verification "
            f"tiers are identical to the source version. Coverage, which DoD #7 requires as a recorded "
            f"quantity rather than a disclaimer: of {result.genres} genres, {result.without_inception} "
            f"have NO inception date and {result.without_country} have NO country of origin. Of the "
            f"dated ones, {result.coarser_than_year} carry a Wikidata precision coarser than a year "
            f"(decade or century), so era assignment is approximate at its edges. The most-credited "
            f"country is {result.top_country} at {result.top_country_share:.0%} of genres that have "
            f"any country recorded. Artist nodes are deliberately unmeasured here: P571 and P495 are "
            f"genre properties, and reporting one figure across both axes would let 804 unmeasured "
            f"artist nodes dilute a genre coverage number. "
            f"Source notes follow. {manifest.notes}"
        ),
    )

    print(f"Wrote {artifact_dir(args.build)}")
    print(f"  nodes {written.node_count}  edges {written.edge_count}")
    print(f"  coverage {written.coverage}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
