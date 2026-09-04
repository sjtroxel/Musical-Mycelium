"""Build the pinned artifact from Wikidata P737 (``influenced by``) genre-to-genre edges.

**Runs locally, never in Lambda.** Nothing here is imported by the runtime packages, and the agent never
queries Wikidata live — every agent tool call hits the pre-built artifact
(``.claude/rules/graph-semantics.md``).

The pipeline shape is the one v0.1 promised phase 2 would inherit — **fetch, type-filter, stamp
provenance, write**. What changed at v0.2 is only where the candidate pairs come from: a
:mod:`~musical_mycelium.ingest.discovery` screening rather than a literal tuple.

## Two tiers of verification, and the hand lists still govern

Every edge carries ``verification``:

* ``HAND`` — a human read the subject's article and judged that its prose asserts influence.
  :data:`HAND_VERIFIED_EDGES`, recorded per-edge in ``docs/phases/phase-1-edge-verification.md``.
* ``PROSE_AUTO`` — the automated prose check passed and nothing more. Strictly weaker: the check
  cannot tell whether a sentence *asserts* influence, and over-accepts at roughly 1 in 5.

:func:`select_edges` applies the hand lists as an **override in both directions**, which matters more
than it sounds: the automated check accepts six of the seven edges the 2026-08-02 pass rejected, so
building straight from the screening would quietly re-admit every one of them.

Usage::

    python -m musical_mycelium.ingest.discovery         # crawl, writing data/screening.json
    python -m musical_mycelium.ingest.wikidata          # build the pinned version from it
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
from collections.abc import Iterable, Sequence
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from musical_mycelium.graph.schema import (
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    SOURCE_WIKIDATA,
    VERIFICATION_HAND,
    VERIFICATION_PROSE_AUTO,
    Artifact,
    Edge,
    Node,
)
from musical_mycelium.ingest import artifact as artifact_io
from musical_mycelium.ingest.discovery import Exclusion, Screening

ARTIFACT_VERSION = "0.7.1"
VERIFICATION_RECORD = "docs/phases/phase-1-edge-verification.md"

#: Written beside the artifact: every discovered candidate that did not make the corpus, with a
#: machine-readable reason. The exclusion rate is a displayed coverage number, never a silent filter
#: (``docs/planning/04-RISK-REGISTER.md`` 4.5).
EXCLUSIONS_FILENAME = "exclusions.json"

#: Reason code for a candidate the automated check accepted and a human had already rejected.
OVERRULED = "HAND_REJECTED"

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

#: The edges a **human read and accepted**: 21 from the 2026-08-02 verification pass, plus one added
#: 2026-08-04 (see below). Only Q-ids appear here on purpose — labels are fetched live, because a label
#: can drift and because a hand-typed identifier is a hallucination with a plausible shape. Two rounds
#: of recalled Q-ids during this phase resolved to a spider, a Polish municipality and gravity; the type
#: filter is what caught them.
#:
#: **At v0.2 this is no longer the corpus — it is the ``HAND`` slice of it.** The rest of the corpus
#: comes from the discovery screening and carries ``PROSE_AUTO``. This list still overrides the
#: automated check, because a human reading the sentence is the stronger signal in both directions:
#: these go in even if the check were to miss them, and :data:`REJECTED_EDGES` stays out even though
#: the check now accepts six of the seven.
HAND_VERIFIED_EDGES: tuple[tuple[str, str], ...] = (
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
    # Added 2026-08-04, and it is HAND rather than PROSE_AUTO because a human read the sentence. The
    # 08-02 pass rejected it on a recorded belief — "zero genuine prose" — that live measurement
    # disproved: the lead reads "The genre is primarily derived from thrash metal, but played in
    # slower tempos", which is the exact claim shape this product promises. Record: the 4.6 correction
    # in ``docs/graph-semantics.md``.
    ("Q241662", "Q483352"),  # groove metal <- thrash metal
)

#: Edges a **human read and rejected**, recorded so they are not quietly re-added.
#:
#: **This list is load-bearing at v0.2 in a way it was not at v0.1.** The automated prose check accepts
#: **six of these seven** — it cannot tell synonymy, contradiction, taxonomy or a wrong-way-in-time
#: mention from a genuine influence claim (``ingest.prosecheck``). Building the corpus straight from the
#: screening would therefore re-admit every one of them. :func:`select_edges` applies this list as an
#: override, and ``tests/test_artifact.py::test_rejected_edges_are_absent`` fails if it ever stops.
#:
#: Six entries, not seven: ``groove metal <- thrash metal`` was a **false rejection** — recorded as
#: having "zero genuine prose" when it has seven sentences led by "primarily derived from thrash metal"
#: — and moved to :data:`HAND_VERIFIED_EDGES` on 2026-08-04. The remaining reasons were re-measured
#: against the live articles at the same time. See ``docs/graph-semantics.md`` 4.6.
REJECTED_EDGES: tuple[tuple[str, str, str], ...] = (
    (
        "Q241662",
        "Q38848",
        "groove metal <- heavy metal: taxonomic. 6 genuine prose mentions, but the lead reads "
        "'is a subgenre of heavy metal music'. (Was recorded as 'zero genuine prose'; that was wrong.)",
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


#: Status codes worth a second attempt. 429 and 503 are the documented rate-limit signals; 500, 502
#: and 504 are WDQS being WDQS. **Measured 2026-08-04:** the phase-2 discovery query returned a 502 on
#: its first run and the *identical* query returned 351 rows in 2.2 seconds minutes later, so a bare
#: 502 says nothing about the query. Retrying is not optional politeness here — one transient gateway
#: error would otherwise abort a 15-minute crawl at request 300.
#:
#: A genuine timeout also arrives as a 500 and will simply exhaust the attempts; a malformed query
#: arrives as a 400 and is never retried, so this cannot silently paper over a broken query.
_RETRYABLE = frozenset({429, 500, 502, 503, 504})


#: Comfortably under the cache layer's limit, which is not published. Measured only in the negative:
#: a ~13,000-character URL was rejected on 2026-09-02 and shorter ones have always been served.
_MAX_GET_URL = 3000


def _get(url: str, timeout: int = 60, attempts: int = 4) -> Any:
    """One polite GET with backoff.

    WDQS budgets 60 seconds of query time per minute per IP and returns 429 when that is exceeded.
    Back off rather than hammering it; this client exists to be a good citizen of a service that is
    materially degraded in 2026.
    """
    return _request(url, None, timeout=timeout, attempts=attempts)


def _post(url: str, form: dict[str, str], timeout: int = 180, attempts: int = 5) -> Any:
    """The same politeness, over POST, for queries whose URL would be too long to GET.

    **Added 2026-09-02, after :func:`sparql` failed on a 973-QID ``VALUES`` clause with
    ``HTTP 503 VCL failed``.** That is Wikidata's cache layer rejecting an over-long URL, and it is not
    a retryable condition — the backoff in :func:`_get` retried it three times and then raised, which
    cost a measurement run. Any query bounded by a large ``VALUES`` set must come through here.
    """
    body = urllib.parse.urlencode(form).encode()
    return _request(url, body, timeout=timeout, attempts=attempts)


def _request(url: str, body: bytes | None, *, timeout: int, attempts: int) -> Any:
    headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if body is not None:
        headers["Content-Type"] = "application/x-www-form-urlencoded"
    request = urllib.request.Request(url, data=body, headers=headers)
    delay = 5.0
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRYABLE or attempt == attempts:
                raise
            print(
                f"  HTTP {exc.code}; backing off {delay:.0f}s (attempt {attempt}/{attempts})",
                file=sys.stderr,
            )
            time.sleep(delay)
            delay *= 2
    raise IngestError("unreachable")


def sparql(query: str) -> list[dict[str, Any]]:
    """Run a SPARQL query, choosing GET or POST by how long the URL would be.

    The switch is not a style preference. WDQS sits behind a cache that rejects over-long URLs with
    ``HTTP 503 VCL failed``, which is indistinguishable from a transient 503 at the HTTP layer and so
    gets retried and then raised. Queries carrying a large ``VALUES`` clause exceed it easily; the
    2026-09-02 P136 measurement did so at 973 QIDs.
    """
    form = {"query": query, "format": "json"}
    url = WDQS + "?" + urllib.parse.urlencode(form)
    body = _post(WDQS, form) if len(url) > _MAX_GET_URL else _get(url)
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


def deprecated_statements(uris: Sequence[str], chunk: int = 250) -> frozenset[str]:
    """Which of these statement URIs Wikidata currently ranks **deprecated**.

    **Prevention is not repair, and this function is the repair half.** The rank filter added to both
    discovery queries on 2026-09-02 stops a deprecated statement entering a *new* crawl. It does
    nothing about one already sitting in a pinned artifact, because a derived artifact carries its
    predecessor's edges across untouched — which is the whole point of carrying them across. So a cut
    that inherits edges must re-check them, or the fix silently applies only to rows nobody was worried
    about.

    Found by building v0.6.0 and reading the verification counts: the P737 tiers still summed to 950
    after the filter landed, because every one of those edges came from v0.5.0 rather than from a
    query the filter had touched.

    Chunked, and it goes through :func:`sparql`, which sends a large ``VALUES`` clause by POST.
    """
    deprecated: set[str] = set()
    ordered = sorted(set(uris))
    for start in range(0, len(ordered), chunk):
        values = " ".join(f"<{u}>" for u in ordered[start : start + chunk])
        rows = sparql(
            f"SELECT ?st WHERE {{ VALUES ?st {{ {values} }} "
            f"?st wikibase:rank wikibase:DeprecatedRank . }}"
        )
        deprecated.update(row["st"]["value"] for row in rows)
    return frozenset(deprecated)


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


@dataclass(frozen=True, slots=True)
class SelectedEdge:
    """One edge chosen for the corpus, carrying how strongly it was verified."""

    subject_id: str
    object_id: str
    verification: str

    @property
    def pair(self) -> tuple[str, str]:
        return (self.subject_id, self.object_id)


def select_edges(
    auto_accepted: Iterable[tuple[str, str]],
) -> tuple[tuple[SelectedEdge, ...], tuple[tuple[tuple[str, str], str], ...]]:
    """Apply the hand judgments over the automated screening. Pure — this is the corpus policy.

    Two rules, and the second is the one that matters:

    1. Everything in :data:`HAND_VERIFIED_EDGES` is in, marked ``HAND``.
    2. Everything in :data:`REJECTED_EDGES` is **out**, even though the automated check accepts six of
       the seven. A human read those sentences and judged that they do not assert influence; the check
       structurally cannot make that judgement, so it does not get to overrule one.

    Returns the selection and the **overruled** list: hand-rejected pairs the automated check accepted,
    which is a number worth publishing rather than a silent subtraction. It is the over-accept rate
    caught in the act.
    """
    rejected = {(subject, obj): reason for subject, obj, reason in REJECTED_EDGES}
    hand = set(HAND_VERIFIED_EDGES)

    conflict = hand & set(rejected)
    if conflict:
        raise IngestError(
            f"{sorted(conflict)} is in both HAND_VERIFIED_EDGES and REJECTED_EDGES. "
            f"A pair cannot be both hand-accepted and hand-rejected; fix the lists."
        )

    selected = {pair: SelectedEdge(*pair, VERIFICATION_HAND) for pair in sorted(hand)}
    overruled: list[tuple[tuple[str, str], str]] = []

    for pair in sorted(set(auto_accepted)):
        if pair in rejected:
            overruled.append((pair, rejected[pair]))
            continue
        selected.setdefault(pair, SelectedEdge(*pair, VERIFICATION_PROSE_AUTO))

    return tuple(selected[pair] for pair in sorted(selected)), tuple(overruled)


def build(
    selected: tuple[SelectedEdge, ...],
    statement_uris: dict[tuple[str, str], str],
) -> tuple[Artifact, dict[str, int]]:
    """Fetch, type-filter, stamp provenance, and return the artifact plus its revision snapshot.

    ``statement_uris`` comes from the discovery screening rather than a second WDQS round trip: the
    statement URI an edge cites should be the one discovery actually saw, and re-fetching it would
    introduce a window in which the two could disagree.
    """
    retrieved_at = datetime.now(UTC).isoformat(timespec="seconds")
    pairs = tuple(edge.pair for edge in selected)

    missing_uri = [pair for pair in pairs if pair not in statement_uris]
    if missing_uri:
        print(f"Confirming {len(missing_uri)} statement(s) not present in the screening...")
        statement_uris = {**statement_uris, **fetch_statements(tuple(missing_uri))}
        time.sleep(3.0)

    statements = statement_uris
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
            # Unconditional, and safe to be: the type filter above has already refused every qid that
            # does not reach QID_MUSIC_GENRE, so by the time we get here every node is a genre by
            # construction. The artist axis builds its nodes in ingest/artists.py, not here.
            kind=NODE_KIND_GENRE,
            revision_id=facts[qid].revision_id,
        )
        for qid in qids
    )

    edges = tuple(
        Edge(
            subject_id=edge.subject_id,
            predicate=PREDICATE_INFLUENCED_BY,
            object_id=edge.object_id,
            source=SOURCE_WIKIDATA,
            source_id=statements[edge.pair],
            retrieved_at=retrieved_at,
            prose_tier="PROSE",
            verification=edge.verification,
        )
        for edge in selected
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


def collect_exclusions(
    screening: Screening, overruled: tuple[tuple[tuple[str, str], str], ...]
) -> tuple[Exclusion, ...]:
    """Every discovered candidate that did not reach the corpus, from both filters plus the override.

    The screening's own exclusions cover the type filter and the prose check. This adds the third
    reason, which only exists once the hand lists are applied: the check accepted it and a human had
    already said no.
    """
    labels = {qid: entity.label for qid, entity in screening.entities.items()}
    overrides = tuple(
        Exclusion(
            subject_id=subject,
            object_id=obj,
            subject_label=labels.get(subject, ""),
            object_label=labels.get(obj, ""),
            reason_code=OVERRULED,
            reason=(
                f"the automated prose check accepted this edge and the 2026-08-02 hand-verification "
                f"pass rejected it; the hand judgement governs. {reason}"
            ),
        )
        for (subject, obj), reason in overruled
    )
    return tuple(sorted(screening.excluded + overrides, key=lambda e: (e.subject_id, e.object_id)))


def write_exclusions(exclusions: tuple[Exclusion, ...], directory: Path) -> Path:
    """Write ``exclusions.json`` beside the artifact."""
    path = directory / EXCLUSIONS_FILENAME
    payload = {
        "count": len(exclusions),
        "by_reason": {
            code: sum(1 for e in exclusions if e.reason_code == code)
            for code in sorted({e.reason_code for e in exclusions})
        },
        "excluded": [asdict(e) for e in exclusions],
    }
    directory.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--force", action="store_true", help="rebuild the pinned version in place")
    parser.add_argument("--version", default=ARTIFACT_VERSION, help="artifact version to write")
    parser.add_argument(
        "--screening",
        type=Path,
        default=None,
        help="screening cache to build from (default: ingest.discovery's)",
    )
    args = parser.parse_args(argv)

    screening = Screening.load(args.screening) if args.screening is not None else Screening.load()
    selected, overruled = select_edges(screening.pairs)
    hand = sum(1 for edge in selected if edge.verification == VERIFICATION_HAND)

    print(
        f"Screening {screening.generated_at}: {len(screening.candidates)} candidates, "
        f"{len(screening.accepted)} passed the prose check."
    )
    print(f"Selected {len(selected)} edges: {hand} HAND, {len(selected) - hand} PROSE_AUTO.")
    if overruled:
        print(f"Overruled {len(overruled)} auto-accepted edge(s) on the hand rejections:")
        for pair, reason in overruled:
            print(f"  {pair[0]} <- {pair[1]}: {reason}")

    artifact, snapshot = build(selected, screening.statement_uris())
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
            f"{manifest_counts(artifact)}. HAND edges were read by a human who judged the prose to "
            f"assert influence; PROSE_AUTO edges cleared the automated prose check only, which "
            f"confirms the subject's article names the object in body prose but cannot judge whether "
            f"that sentence asserts influence. Measured against the 28 edges hand-read on 2026-08-02, "
            f"the automated check over-accepts at roughly 1 in 5. Every edge in both tiers cites a "
            f"Wikidata statement URI and types as a music genre at both ends."
        ),
        overwrite=args.force,
    )

    exclusions = collect_exclusions(screening, overruled)
    exclusions_path = write_exclusions(exclusions, directory)

    artifact_io.verify(directory)
    print(
        f"\nWrote {directory}\n"
        f"  {manifest.node_count} nodes, {manifest.edge_count} edges "
        f"({manifest.verification_counts})\n"
        f"  sha256 {manifest.sha256}\n"
        f"  {exclusions_path.name}: {len(exclusions)} excluded candidates\n"
        f"  verified: graph.json hashes to its manifest"
    )
    return 0


def manifest_counts(artifact: Artifact) -> str:
    counts = artifact.verification_counts()
    return (
        f"{counts[VERIFICATION_HAND]} hand-verified edges and "
        f"{counts[VERIFICATION_PROSE_AUTO]} machine-verified edges"
    )


if __name__ == "__main__":
    raise SystemExit(main())
