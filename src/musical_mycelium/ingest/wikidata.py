"""Build the v0.1 artifact from Wikidata P737 (``influenced by``) genre-to-genre edges.

**Runs locally, never in Lambda.** Nothing here is imported by the runtime packages, and the agent never
queries Wikidata live — every agent tool call hits the pre-built artifact
(``.claude/rules/graph-semantics.md``).

At v0.1 the edge set is a **hand-verified list**, not a discovery query. The 2026-08-02 verification pass
read 26 candidates from the PROSE tier and rejected 5; the survivors are ``VERIFIED_EDGES`` below and the
full record with per-edge supporting prose is ``docs/phases/phase-1-edge-verification.md``.

The pipeline shape is nonetheless the real one — **fetch, type-filter, stamp provenance, write** — so
phase 2 replaces only where the candidate pairs come from (a full P737 query plus the automated prose
check) without touching ``artifact.py`` or the schema.

Usage::

    python -m musical_mycelium.ingest.wikidata          # build the pinned version
    python -m musical_mycelium.ingest.wikidata --force  # rebuild it in place
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from musical_mycelium.graph.schema import (
    PREDICATE_INFLUENCED_BY,
    SOURCE_WIKIDATA,
    Artifact,
    Edge,
    Node,
)
from musical_mycelium.ingest import artifact as artifact_io

ARTIFACT_VERSION = "0.1.0"
VERIFICATION_RECORD = "docs/phases/phase-1-edge-verification.md"

WDQS = "https://query.wikidata.org/sparql"
WD_API = "https://www.wikidata.org/w/api.php"

# MusicBrainz requires a contactable User-Agent and Wikimedia expects one too. Identify honestly.
USER_AGENT = "MusicalMycelium/0.1 (https://github.com/sjtroxel; sjtroxel@protonmail.com)"

#: ``influenced by``. P279 (``subclass of``) is deliberately not ingested at v0.1 — see the module
#: docstring of ``graph.schema``.
PROPERTY_INFLUENCED_BY = "P737"

#: ``music genre``. Both ends of every edge must reach this via ``P31/P279*`` or the edge is dropped:
#: roughly 6% of P737 objects are bands, techniques or instruments (``docs/graph-semantics.md`` 3.1).
QID_MUSIC_GENRE = "Q188451"

#: The 21 edges that survived hand-verification on 2026-08-02. Only Q-ids appear here on purpose —
#: labels are fetched live, because a label can drift and because a hand-typed identifier is a
#: hallucination with a plausible shape. Two rounds of recalled Q-ids during this phase resolved to a
#: spider, a Polish municipality and gravity; the type filter is what caught them.
VERIFIED_EDGES: tuple[tuple[str, str], ...] = (
    ("Q193355", "Q9759"),  # blues rock <- blues
    ("Q38848", "Q193355"),  # heavy metal music <- blues rock
    ("Q483352", "Q3071"),  # thrash metal <- punk rock
    ("Q1425661", "Q3071"),  # folk punk <- punk rock
    ("Q186472", "Q43343"),  # folk rock <- folk music
    ("Q205560", "Q11401"),  # trip hop <- hip-hop
    ("Q205560", "Q817138"),  # trip hop <- electronica
    ("Q1730388", "Q203775"),  # Western swing <- swing
    ("Q1730388", "Q83440"),  # Western swing <- country music
    ("Q613408", "Q83440"),  # country rock <- country music
    ("Q2706919", "Q83440"),  # country rap <- country music
    ("Q486263", "Q8341"),  # bossa nova <- jazz
    ("Q255406", "Q8341"),  # jazz rap <- jazz
    ("Q221772", "Q8341"),  # acid jazz <- jazz
    ("Q221772", "Q164444"),  # acid jazz <- funk
    ("Q221772", "Q131272"),  # acid jazz <- soul
    ("Q221772", "Q11401"),  # acid jazz <- hip-hop
    ("Q2521569", "Q131272"),  # soul blues <- soul
    ("Q1166726", "Q1165777"),  # grime <- UK garage
    ("Q20474", "Q1751409"),  # dubstep <- 2-step garage
    ("Q20474", "Q212688"),  # dubstep <- dub music
)

#: Rejected during the same pass, recorded so they are not quietly re-added. The exclusion rate is a
#: displayed coverage number, not a silent filter (``docs/planning/04-RISK-REGISTER.md`` 4.5).
#:
#: **Two reasons corrected 2026-08-04** while building ``prosecheck.py``, which re-measured every case
#: against the live articles. The count is unchanged at 7 — the v0.1 artifact is pinned and is not being
#: rewritten — but the *record* was wrong and one of these is a false rejection worth re-admitting when
#: phase 2 rebuilds the corpus. See ``docs/graph-semantics.md`` 4.6.
REJECTED_EDGES: tuple[tuple[str, str, str], ...] = (
    (
        "Q241662",
        "Q38848",
        "groove metal <- heavy metal: taxonomic. 6 genuine prose mentions, but the lead reads "
        "'is a subgenre of heavy metal music'. (Was recorded as 'zero genuine prose'; that was wrong.)",
    ),
    (
        "Q241662",
        "Q483352",
        "groove metal <- thrash metal: FALSE REJECTION. Recorded as 'zero genuine prose'; it has 7, "
        "led by 'primarily derived from thrash metal'. Re-admit in phase 2.",
    ),
    ("Q38848", "Q83270", "heavy metal <- hard rock: prose asserts synonymy, not derivation"),
    ("Q38848", "Q9730", "heavy metal <- classical music: prose contradicts it"),
    ("Q465978", "Q38848", "extreme metal <- heavy metal: taxonomic, not historical"),
    ("Q1166726", "Q20474", "grime <- dubstep: cites the *fall* of dubstep; grime predates it"),
    ("Q360596", "Q58339", "disco house <- disco: subject article redirects to French house"),
)


class IngestError(RuntimeError):
    """Ingestion refused to write an artifact it could not stand behind."""


@dataclass(frozen=True, slots=True)
class EntityFacts:
    """What a live read of one Wikidata entity told us."""

    qid: str
    label: str
    revision_id: int
    is_genre: bool


def _get(url: str, timeout: int = 60, attempts: int = 4) -> Any:
    """One polite GET with backoff.

    WDQS budgets 60 seconds of query time per minute per IP and returns 429 when that is exceeded.
    Back off rather than hammering it; this client exists to be a good citizen of a service that is
    materially degraded in 2026.
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    delay = 5.0
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in (429, 503) or attempt == attempts:
                raise
            print(
                f"  HTTP {exc.code}; backing off {delay:.0f}s (attempt {attempt}/{attempts})",
                file=sys.stderr,
            )
            time.sleep(delay)
            delay *= 2
    raise IngestError("unreachable")


def sparql(query: str) -> list[dict[str, Any]]:
    url = WDQS + "?" + urllib.parse.urlencode({"query": query, "format": "json"})
    body = _get(url)
    bindings: list[dict[str, Any]] = body["results"]["bindings"]
    return bindings


def fetch_statements(pairs: tuple[tuple[str, str], ...]) -> dict[tuple[str, str], str]:
    """Map each ``(subject, object)`` pair to its Wikidata **statement** URI.

    The statement URI, not the subject QID, is what an edge cites. It resolves to the specific assertion,
    which is the difference between a citation that can be checked and one that merely gestures.
    """
    values = " ".join(f"(wd:{s} wd:{o})" for s, o in pairs)
    rows = sparql(
        f"""
        SELECT ?s ?o ?statement WHERE {{
          VALUES (?s ?o) {{ {values} }}
          ?s p:{PROPERTY_INFLUENCED_BY} ?statement .
          ?statement ps:{PROPERTY_INFLUENCED_BY} ?o .
        }}
        """
    )
    out: dict[tuple[str, str], str] = {}
    for row in rows:
        subject = row["s"]["value"].rsplit("/", 1)[1]
        obj = row["o"]["value"].rsplit("/", 1)[1]
        out[(subject, obj)] = row["statement"]["value"]
    return out


def fetch_entities(qids: list[str]) -> dict[str, EntityFacts]:
    """Label, revision id and genre-ness for each entity, from two live reads.

    ``revision_id`` is the snapshot this row was read from. Without it "retrieved_at" is a timestamp with
    nothing behind it; with it, any claim in the artifact can be replayed against the exact revision.
    """
    genre_rows = sparql(
        f"""
        SELECT ?q ?isGenre WHERE {{
          VALUES ?q {{ {" ".join(f"wd:{q}" for q in qids)} }}
          BIND(EXISTS {{ ?q wdt:P31/wdt:P279* wd:{QID_MUSIC_GENRE} }} AS ?isGenre)
        }}
        """
    )
    is_genre = {
        row["q"]["value"].rsplit("/", 1)[1]: row["isGenre"]["value"] == "true" for row in genre_rows
    }

    facts: dict[str, EntityFacts] = {}
    for start in range(0, len(qids), 40):
        chunk = qids[start : start + 40]
        url = (
            WD_API
            + "?"
            + urllib.parse.urlencode(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "props": "labels|info",
                    "languages": "en",
                    "format": "json",
                }
            )
        )
        entities: dict[str, Any] = _get(url)["entities"]
        for qid, entity in entities.items():
            label = entity.get("labels", {}).get("en", {}).get("value", "")
            facts[qid] = EntityFacts(
                qid=qid,
                label=label,
                revision_id=int(entity.get("lastrevid", 0)),
                is_genre=is_genre.get(qid, False),
            )
        time.sleep(1.0)
    return facts


def build(pairs: tuple[tuple[str, str], ...] = VERIFIED_EDGES) -> tuple[Artifact, dict[str, int]]:
    """Fetch, type-filter, stamp provenance, and return the artifact plus its revision snapshot."""
    retrieved_at = datetime.now(UTC).isoformat(timespec="seconds")

    print(f"Confirming {len(pairs)} P737 statements against Wikidata...")
    statements = fetch_statements(pairs)
    time.sleep(3.0)

    qids = sorted({q for pair in pairs for q in pair})
    print(f"Reading {len(qids)} entities (label, revision, type)...")
    facts = fetch_entities(qids)

    missing = [pair for pair in pairs if pair not in statements]
    if missing:
        raise IngestError(
            f"{len(missing)} verified edge(s) no longer exist in Wikidata: {missing}. "
            f"Re-run the verification pass rather than writing an artifact that claims them."
        )

    not_genres = sorted(q for q in qids if not facts.get(q, EntityFacts(q, "", 0, False)).is_genre)
    if not_genres:
        labels = ", ".join(f"{q} ({facts[q].label or '?'})" for q in not_genres)
        raise IngestError(
            f"type filter rejected {len(not_genres)} node(s) that are not music genres: {labels}. "
            f"Both ends of every edge must reach {QID_MUSIC_GENRE} via P31/P279*."
        )

    unlabelled = sorted(q for q in qids if not facts[q].label)
    if unlabelled:
        raise IngestError(f"no English label for: {unlabelled}")

    nodes = tuple(
        Node(
            id=qid,
            label=facts[qid].label,
            source=SOURCE_WIKIDATA,
            source_id=qid,
            retrieved_at=retrieved_at,
            revision_id=facts[qid].revision_id,
        )
        for qid in qids
    )

    edges = tuple(
        Edge(
            subject_id=subject,
            predicate=PREDICATE_INFLUENCED_BY,
            object_id=obj,
            source=SOURCE_WIKIDATA,
            source_id=statements[(subject, obj)],
            retrieved_at=retrieved_at,
            prose_tier="PROSE",
        )
        for subject, obj in pairs
    )

    snapshot = {qid: facts[qid].revision_id for qid in qids}
    return Artifact(nodes=nodes, edges=edges), snapshot


def artifact_dir(version: str = ARTIFACT_VERSION) -> Path:
    """Where the pinned artifact lives.

    Inside the package, so ``pip install`` carries it into the Lambda container image without a separate
    COPY and without an S3 fetch on the cold path (v0.1 IMPLEMENTATION doc 5.2). Root-level ``data/`` is
    gitignored by a phase-0 decision and cannot hold a tracked artifact.
    """
    return Path(__file__).resolve().parent.parent / "artifacts" / f"v{version}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--force", action="store_true", help="rebuild the pinned version in place")
    parser.add_argument("--version", default=ARTIFACT_VERSION, help="artifact version to write")
    args = parser.parse_args(argv)

    artifact, snapshot = build()
    directory = artifact_dir(args.version)

    manifest = artifact_io.write(
        artifact,
        directory,
        artifact_version=args.version,
        generator="musical_mycelium.ingest.wikidata",
        predicate=f"{PROPERTY_INFLUENCED_BY} ({PREDICATE_INFLUENCED_BY})",
        source=SOURCE_WIKIDATA,
        source_snapshot=snapshot,
        verification_record=VERIFICATION_RECORD,
        notes=(
            f"{len(VERIFIED_EDGES)} hand-verified edges; {len(REJECTED_EDGES)} candidates rejected. "
            f"Every edge cleared four gates: the statement exists, both ends type as a music genre, the "
            f"subject's Wikipedia article contains genuine prose naming the object, and that prose "
            f"asserts influence rather than co-occurrence, synonymy or taxonomy."
        ),
        overwrite=args.force,
    )

    artifact_io.verify(directory)
    print(
        f"\nWrote {directory}\n"
        f"  {manifest.node_count} nodes, {manifest.edge_count} edges\n"
        f"  sha256 {manifest.sha256}\n"
        f"  verified: graph.json hashes to its manifest"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
