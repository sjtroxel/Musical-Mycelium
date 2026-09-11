"""The v0.10.0 layer: `mul` recovery, teaching lineage, artist dates, aliases, and membership.

Phase 7.6 step 5. ``docs/phases/phase-7.6-classical-lineage-IMPLEMENTATION.md`` is the plan; this module
is its D2: **v0.10.0 is v0.7.1 plus exactly five classes of change**, and a diff report classifies every
row that moved. A change it cannot classify stops the build.

- **(a) `mul` recovery.** Entities whose label came back empty in the 2026-08-05 artist crawl (Wikidata's
  `mul` default label, which every fetch then asked for in `en` only; `ingest.labels`) are re-fetched,
  and every candidate row touching one is re-screened through the artist axis's own pipeline
  (``discovery.screen_candidates``, then ``artists.artist_rows``, which applies the influence-assertion
  tiers). Mozart is the case that found it.
- **(b) Teaching.** P1066 "student of" between composers, the student born before 1900, both with an
  English article (bound A, phase 7.6 step 3), screened by the same prose check on the student's article.
  Hand-checked before a row was ingested: ``docs/p1066-handcheck.md``.
- **(c) Dates.** P569 for people into ``birth_year``; P571 for groups into ``inception_year``, which for
  a group already means formation. Every artist, old and new.
- **(d) Aliases.** Wikidata ``en`` and ``mul`` aliases on every node. Stored, not used, until phase 7.7.
- **(e) Membership.** P136 for every artist new in (a) or (b), and the reviewed repertoire allowlist
  (``membership.REPERTOIRE_ALLOWLIST``) for every artist, with a collision rule enforced here: a new genre
  whose label folds to an existing node's label is never admitted.

**Two phases, the ``artists.py`` pattern.** ``--crawl`` does every network read and saves each part under
``data/lineage/``, resumable part by part, because the teaching crawl is about 2,000 Wikipedia articles at
one per second and a later timeout must not waste it. ``--build`` is offline and repeatable: it reads the
saved parts and v0.7.1 and writes v0.10.0. Nothing about v0.7.1 is re-read from Wikidata except what the
five classes name, so a month of unrelated Wikidata edits cannot leak into the diff.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import asdict, dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from musical_mycelium.graph.memory import label_key
from musical_mycelium.graph.schema import (
    NODE_KIND_ARTIST,
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    PREDICATE_PLAYS_GENRE,
    PREDICATE_STUDIED_WITH,
    SOURCE_WIKIDATA,
    VERIFICATION_TEACHING_PROSE_AUTO,
    Artifact,
    Edge,
    Node,
)
from musical_mycelium.ingest.discovery import Candidate, Exclusion, Screening, parse_discovery
from musical_mycelium.ingest.membership import REPERTOIRE_ALLOWLIST, Membership, admitted

#: Where ``--crawl`` saves each part. Root ``data/`` is gitignored by a phase 0 decision, like the other
#: screenings; the artifact is the committed record, and these are what make it rebuildable.
CRAWL_DIR = Path("data/lineage")
RECOVERY_FILE = "recovery.json"
TEACHING_FILE = "teaching.json"
FACTS_FILE = "facts.json"

SOURCE_VERSION = "0.7.1"
TARGET_VERSION = "0.10.0"

#: P1066, and the bound decided at phase 7.6 step 3 (bound A).
PROPERTY_STUDENT_OF = "P1066"
QID_COMPOSER = "Q36834"
BORN_BEFORE = 1900

#: Birth-year windows the teaching discovery is split into. **Eight, not four, after measuring.** On the
#: morning of 2026-09-11 four windows (to 1700, 1700s, 1800-1850, 1850-1900) returned 534, 636, 841 and
#: 1,595 rows. That afternoon the first of them came back as a **truncated response**: the service hit its
#: own timeout mid-stream and sent partial JSON with no error status. Smaller windows are smaller queries.
TEACHING_WINDOWS: tuple[tuple[int, int], ...] = (
    (-3000, 1600),
    (1600, 1700),
    (1700, 1750),
    (1750, 1800),
    (1800, 1825),
    (1825, 1850),
    (1850, 1875),
    (1875, BORN_BEFORE),
)

#: Teaching edges excluded by a person, with the reason. The ``wikidata.REJECTED_EDGES`` pattern, kept
#: separate so an influence rejection can never be read as a teaching one.
#:
#: **Filled from ``docs/p1066-build-review.md``, reviewed and approved by sjtroxel on 2026-09-11.** Two
#: rules produced it, both stated before the rows were judged: (1) a teacher recorded as younger than the
#: student is kept only when an article sentence states the study, and (2) an edge whose only supporting
#: sentences describe succeeding someone in a post is excluded. 18 distinct edges; Ercole Pasquini is
#: excluded by both rules and listed once.
TEACHING_REJECTED: tuple[tuple[str, str, str], ...] = (
    # Rule 1: a younger teacher, and no sentence stating study.
    ("Q4334843", "Q360863", "inverted: Ondříček's article names Jan Kubelík as his pupil"),
    ("Q1450915", "Q189544", "inverted: Benoist's article lists Adolphe Adam among his students"),
    (
        "Q125065",
        "Q360410",
        "younger teacher; only sentence is family (son of); 1501 birth is wrong",
    ),
    ("Q3731206", "Q445581", "younger teacher; only sentence is succession as organist"),
    ("Q218633", "Q377409", "younger teacher; only sentence is a co-written work: collaborators"),
    ("Q7512883", "Q2288473", "younger teacher; only sentence names him as her brother, a painter"),
    ("Q16190541", "Q1908638", "younger teacher; only sentence is a premiere under his baton"),
    ("Q354947", "Q320534", "younger teacher; only sentence names them as peer opera composers"),
    ("Q668969", "Q156910", "younger teacher; only sentence is patronage ('helped and promoted')"),
    ("Q3371608", "Q56158", "younger teacher; only sentence is admiration of his music"),
    # Rule 2: the only supporting sentences describe succession to a post.
    ("Q11686949", "Q1797599", "succession only: assistant, then successor as organist"),
    ("Q1451270", "Q1355872", "succession only: organist of Rouen Cathedral after him"),
    ("Q18534903", "Q4888428", "succession only: succeeded his father as organist"),
    ("Q2004683", "Q277029", "succession only: court posts in de Monte's line"),
    ("Q2605900", "Q205898", "succession only: maitre de chapelle after him"),
    ("Q2997483", "Q549689", "succession only: master of the choirboys after him"),
    ("Q466841", "Q780211", "succession only: Kapellmeister after him"),
    ("Q715368", "Q313860", "succession only: music master at Toulouse after him"),
)

#: Build-time exclusion codes, published beside the counts because the drop is the finding.
NO_LABEL = "NO_LABEL"
UNCITABLE_STATEMENT = "UNCITABLE_STATEMENT"
HAND_REJECTED = "HAND_REJECTED"
DEPRECATED = "DEPRECATED"
LABEL_COLLISION = "LABEL_COLLISION"

_STATEMENT_PREFIX = "http://www.wikidata.org/entity/statement/"

#: The step 2 "succession shape": a passing check whose only sentences speak of succeeding someone and
#: never of study. Both cases the hand check found were before 1700; this measures it everywhere.
_SUCCESSION = re.compile(r"\b(succeed\w*|success(?:ion|or)|predecessor)\b", re.IGNORECASE)
# Widened on 2026-09-11 after the first real build: it missed "professor" (Vaughan Williams, whose
# "new professor of composition was Stanford"), "his master" (Leoni, who "succeeded Giammateo Asola, his
# master") and "learn" (Fauré), so it called three real teaching lines succession-only.
_STUDY = re.compile(
    r"\b(stud(?:y|ied|ies|ying|ent)|pupil|taught|teach\w*|lesson\w*|instruct\w*|train\w*|"
    r"apprentic\w*|tutor\w*|disciple|mentor\w*|learn\w*|professor\w*|(?:his|her) master|"
    r"under the (?:direction|guidance|tutelage))\b",
    re.IGNORECASE,
)


# --- pure: the queries -------------------------------------------------------------------------------


def teaching_query(lo: int, hi: int) -> str:
    """Every non-deprecated P1066 statement in bound A for students born in ``[lo, hi)``.

    Shaped like the other axes' discovery queries so ``discovery.parse_discovery`` reads it unchanged:
    ``p:``/``ps:`` so each row carries the **statement URI** an edge cites, and ``objInAxis`` bound true
    because both ends are already typed by the bound.
    """
    # The sitelink tests are plain joins, not ``FILTER EXISTS``. Measured 2026-09-11: this exact shape
    # returned every window in under 90 s that morning, and the ``FILTER EXISTS`` form timed out on the
    # first window that afternoon. DISTINCT because a person with several birth dates repeats rows;
    # ``parse_discovery`` would de-duplicate them anyway, but there is no reason to ship them.
    return f"""
SELECT DISTINCT ?s ?o ?statement ?objInAxis WHERE {{
  ?s wdt:P106 wd:{QID_COMPOSER}; wdt:P569 ?born; p:{PROPERTY_STUDENT_OF} ?statement .
  ?statement ps:{PROPERTY_STUDENT_OF} ?o .
  FILTER NOT EXISTS {{ ?statement wikibase:rank wikibase:DeprecatedRank }}
  ?o wdt:P106 wd:{QID_COMPOSER} .
  FILTER(YEAR(?born) >= {lo} && YEAR(?born) < {hi})
  ?a schema:about ?s; schema:isPartOf <https://en.wikipedia.org/> .
  ?a2 schema:about ?o; schema:isPartOf <https://en.wikipedia.org/> .
  BIND(true AS ?objInAxis)
}}
"""


def patient_sparql(
    query: str, *, attempts: int = 4, wait: float = 30.0
) -> list[dict[str, Any]]:  # pragma: no cover
    """``wikidata.sparql`` by POST, with a timeout treated as a reason to wait and retry.

    The shared helper retries HTTP 429/5xx but not a read timeout, and not a response the service
    truncated mid-stream (a 200 carrying half a JSON document); and it sends short queries by GET
    with a 60 s limit. The teaching discovery died on exactly that on 2026-09-11, before a single
    article was fetched. POST carries the project's 180 s limit; a timeout then waits ``wait`` seconds
    and tries again, because a degraded service that timed out once is usually answering a minute
    later, and giving up would waste the whole crawl.
    """
    import time

    from musical_mycelium.ingest.wikidata import WDQS, _post

    for attempt in range(1, attempts + 1):
        try:
            body = _post(WDQS, {"query": query, "format": "json"})
            rows: list[dict[str, Any]] = body["results"]["bindings"]
            return rows
        except (TimeoutError, OSError, ValueError) as exc:
            # ValueError covers json.JSONDecodeError: a response the service cut off mid-stream, which
            # arrives with a 200 and half a document. Measured on the first teaching window, 2026-09-11.
            if attempt == attempts:
                raise
            print(
                f"  query timed out ({exc}); waiting {wait:.0f}s, attempt {attempt + 1}",
                file=sys.stderr,
            )
            time.sleep(wait)
    raise RuntimeError("unreachable")


def dates_query(qids: Sequence[str]) -> str:
    """P569 and P571 with precision and rank, for the given entities. Rejects come back as rows."""
    values = " ".join(f"wd:{q}" for q in sorted(qids))
    return f"""
SELECT ?q ?prop ?time ?precision ?rank WHERE {{
  VALUES ?q {{ {values} }}
  {{ ?q p:P569 ?st . ?st psv:P569 ?v . BIND("P569" AS ?prop) }}
  UNION
  {{ ?q p:P571 ?st . ?st psv:P571 ?v . BIND("P571" AS ?prop) }}
  ?v wikibase:timeValue ?time ; wikibase:timePrecision ?precision .
  ?st wikibase:rank ?rank .
  FILTER(?rank != wikibase:DeprecatedRank)
}}
"""


# --- pure: dates ---------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Dated:
    """One entity's best birth (P569) and inception (P571), each with its precision."""

    birth_year: int | None = None
    birth_precision: int | None = None
    inception_year: int | None = None
    inception_precision: int | None = None


_YEAR = re.compile(r"^([+-]?)(\d+)-")


def year_of(time_value: str) -> int:
    """The year of a Wikidata time value, sign included. ``-0500-01-01T00:00:00Z`` is 500 BCE.

    ``coverage.parse_coverage`` splits on the first ``-``, which is right for its genres and wrong for a
    negative year: the sign is the first character. People born BCE are in scope here.
    """
    match = _YEAR.match(time_value)
    if match is None:
        raise ValueError(f"not a Wikidata time value: {time_value!r}")
    sign, digits = match.groups()
    return -int(digits) if sign == "-" else int(digits)


_RANK_ORDER = {"PreferredRank": 0, "NormalRank": 1}


def parse_dates(rows: Iterable[Mapping[str, Any]]) -> dict[str, Dated]:
    """The best value per entity and property: the best rank first, then the earliest year.

    Deterministic on purpose. People carry several recorded birth dates surprisingly often (the step 2
    pull had 3,606 rows for 3,449 statements for that reason), and letting row order pick one would make
    the artifact's bytes depend on the query service's mood. Preferred rank is Wikidata's own verdict
    when it gives one; the earliest year is the tie-break the step 2 draw already used.
    """
    best: dict[tuple[str, str], tuple[int, int, int]] = {}
    for row in rows:
        qid = row["q"]["value"].rsplit("/", 1)[1]
        prop = row["prop"]["value"]
        rank = _RANK_ORDER.get(row["rank"]["value"].rsplit("#", 1)[-1], 2)
        candidate = (rank, year_of(row["time"]["value"]), int(row["precision"]["value"]))
        key = (qid, prop)
        if key not in best or candidate[:2] < best[key][:2]:
            best[key] = candidate

    out: dict[str, Dated] = {}
    for (qid, prop), (_, year, precision) in best.items():
        current = out.get(qid, Dated())
        if prop == "P569":
            current = replace(current, birth_year=year, birth_precision=precision)
        else:
            current = replace(current, inception_year=year, inception_precision=precision)
        out[qid] = current
    return out


_RANK_URI = {
    "preferred": "http://wikiba.se/ontology#PreferredRank",
    "normal": "http://wikiba.se/ontology#NormalRank",
}


def date_rows_from_entities(entities: Mapping[str, Any]) -> list[dict[str, Any]]:
    """P569 and P571 claims from a ``wbgetentities`` payload, as the rows ``parse_dates`` reads.

    The same row shape the SPARQL date query produced, so the ranking and precision rules stay in one
    tested place. Deprecated claims are dropped (Wikidata's own verdict that a statement is wrong), and so
    are ``somevalue`` and ``novalue`` snaks, which carry no date to read.
    """
    rows: list[dict[str, Any]] = []
    for qid, entity in sorted(entities.items()):
        for prop in ("P569", "P571"):
            for claim in entity.get("claims", {}).get(prop, []):
                rank = claim.get("rank")
                snak = claim.get("mainsnak", {})
                if rank not in _RANK_URI or snak.get("snaktype") != "value":
                    continue
                value = snak.get("datavalue", {}).get("value", {})
                time, precision = value.get("time"), value.get("precision")
                if not time or precision is None:
                    continue
                rows.append(
                    {
                        "q": {"value": f"http://www.wikidata.org/entity/{qid}"},
                        "prop": {"value": prop},
                        "time": {"value": time},
                        "precision": {"value": str(precision)},
                        "rank": {"value": _RANK_URI[rank]},
                    }
                )
    return rows


def fetch_date_rows(
    qids: Sequence[str], say: Callable[[str], None], pause: float = 1.0
) -> list[dict[str, Any]]:  # pragma: no cover - network
    """Birth and inception claims for ``qids``, 40 entities per ``wbgetentities`` request."""
    import time
    import urllib.parse

    from musical_mycelium.ingest.wikidata import WD_API, _get

    rows: list[dict[str, Any]] = []
    for start in range(0, len(qids), 40):
        chunk = list(qids[start : start + 40])
        url = (
            WD_API
            + "?"
            + urllib.parse.urlencode(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "props": "claims",
                    "format": "json",
                }
            )
        )
        rows.extend(date_rows_from_entities(_get(url)["entities"]))
        if (start // 40) % 10 == 0 or start + 40 >= len(qids):
            say(f"  dates: {min(start + 40, len(qids))}/{len(qids)}")
        time.sleep(pause)
    return rows


def apply_dates(node: Node, dated: Dated | None) -> Node:
    """Class (c). People get ``birth_year``; groups get ``inception_year``; genres are untouched.

    A person is an artist with a P569. An artist with no P569 and a P571 is a group, and P571 is the
    field's existing meaning. An artist with both keeps the birth and leaves inception alone, because
    ``inception_year`` means P571 and a person's P571 is not a formation date.
    """
    if node.kind != NODE_KIND_ARTIST or dated is None:
        return node
    if dated.birth_year is not None:
        return replace(node, birth_year=dated.birth_year, birth_precision=dated.birth_precision)
    if dated.inception_year is not None and node.inception_year is None:
        return replace(
            node, inception_year=dated.inception_year, inception_precision=dated.inception_precision
        )
    return node


# --- pure: (a) the `mul` recovery ------------------------------------------------------------------


def unlabelled(screening: Screening) -> tuple[str, ...]:
    """Every entity the 2026-08-05 crawl recorded with an empty label: the `mul` bug's reach."""
    return tuple(sorted(q for q, e in screening.entities.items() if not e.label.strip()))


def recovery_candidates(screening: Screening, affected: Iterable[str]) -> tuple[Candidate, ...]:
    """Every discovered candidate that touches an affected entity, at either end."""
    hit = set(affected)
    return tuple(c for c in screening.candidates if c.subject_id in hit or c.object_id in hit)


# --- pure: (b) teaching rows ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Rows:
    """What one screening earned, and what it lost. Both halves, as ``artists.ArtistRows``."""

    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    excluded: tuple[Exclusion, ...] = ()


def _label(screening: Screening, qid: str) -> str:
    entity = screening.entities.get(qid)
    return entity.label.strip() if entity else ""


def teaching_rows(
    screening: Screening,
    *,
    retrieved_at: str,
    deprecated: frozenset[str] = frozenset(),
    rejected: Sequence[tuple[str, str, str]] = TEACHING_REJECTED,
) -> Rows:
    """Class (b). Every teaching check the prose check passed becomes a ``studied_with`` edge.

    No assertion filter, unlike the artist influence axis: the hand check found the prose check passing
    on a study sentence in 27 of 30 cases, and the tier says exactly what was checked
    (``VERIFICATION_TEACHING_PROSE_AUTO``). Nodes come from surviving edges only, never from the crawl.
    """
    statements = screening.statement_uris()
    rejected_pairs = {(s, o): why for s, o, why in rejected}
    edges: list[Edge] = []
    excluded: list[Exclusion] = []
    ids: set[str] = set()

    def drop(check: Any, code: str, reason: str) -> None:
        excluded.append(
            Exclusion(
                subject_id=check.subject_id,
                object_id=check.object_id,
                subject_label=_label(screening, check.subject_id),
                object_label=_label(screening, check.object_id),
                reason_code=code,
                reason=reason,
            )
        )

    for check in screening.accepted:
        pair = (check.subject_id, check.object_id)
        uri = statements.get(pair, "")
        if pair in rejected_pairs:
            drop(check, HAND_REJECTED, rejected_pairs[pair])
            continue
        if uri in deprecated:
            drop(check, DEPRECATED, f"statement {uri} is now deprecated on Wikidata")
            continue
        if not uri or uri.removeprefix(_STATEMENT_PREFIX).split("-", 1)[0] != check.subject_id:
            drop(check, UNCITABLE_STATEMENT, f"statement {uri!r} does not name {check.subject_id}")
            continue
        if not _label(screening, check.subject_id) or not _label(screening, check.object_id):
            drop(check, NO_LABEL, "an endpoint has no label in either en or mul")
            continue
        edges.append(
            Edge(
                subject_id=check.subject_id,
                predicate=PREDICATE_STUDIED_WITH,
                object_id=check.object_id,
                source=SOURCE_WIKIDATA,
                source_id=uri,
                retrieved_at=retrieved_at,
                prose_tier="PROSE",
                verification=VERIFICATION_TEACHING_PROSE_AUTO,
            )
        )
        ids.update(pair)

    nodes = tuple(
        Node(
            id=qid,
            label=_label(screening, qid),
            source=SOURCE_WIKIDATA,
            source_id=qid,
            retrieved_at=retrieved_at,
            kind=NODE_KIND_ARTIST,
        )
        for qid in sorted(ids)
    )
    return Rows(nodes=nodes, edges=tuple(edges), excluded=tuple(excluded))


def succession_only(sentences: Sequence[str]) -> bool:
    """Every supporting sentence speaks of succession and none of study. The step 2 shape."""
    return bool(sentences) and all(
        _SUCCESSION.search(s) and not _STUDY.search(s) for s in sentences
    )


def younger_teachers(
    edges: Iterable[Edge], nodes: Mapping[str, Node]
) -> list[tuple[Edge, int, int]]:
    """Teaching edges whose teacher is recorded as born after the student (trap 16). For a human to read.

    Suspicious, not disqualifying: the step 2 sample held one (Sevenants, b. 1868, studied harmony with
    Jongen, b. 1873) and his article supports it. So this lists, and ``TEACHING_REJECTED`` decides.
    """
    out = []
    for edge in edges:
        if edge.predicate != PREDICATE_STUDIED_WITH:
            continue
        student, teacher = nodes.get(edge.subject_id), nodes.get(edge.object_id)
        if (
            student
            and teacher
            and student.birth_year is not None
            and teacher.birth_year is not None
            and teacher.birth_year > student.birth_year
        ):
            out.append((edge, student.birth_year, teacher.birth_year))
    return out


# --- pure: (e) membership ------------------------------------------------------------------------------


def select_memberships(
    memberships: Iterable[Membership],
    *,
    new_artists: frozenset[str],
    existing_artists: frozenset[str],
    existing_edges: frozenset[tuple[str, str, str]],
    allowlist: Mapping[str, str] = REPERTOIRE_ALLOWLIST,
) -> tuple[Membership, ...]:
    """Class (e): which P136 statements this layer adds.

    - An artist **new** in this layer gets its whole admitted P136 list: typed a genre, or allowlisted.
    - An artist **already in v0.7.1** gets only allowlisted repertoire. Re-reading its other P136 values
      would pull in whatever Wikidata editors changed since 2026-09-02, which is drift, not this layer.
    - **An artist in neither gets nothing.** The crawl reads P136 for everyone a teaching or recovery row
      *might* admit, and some of those rows are then refused at build time (deprecated, unlabelled,
      hand-rejected); a membership edge to a refused artist would dangle, and ``merge_axes`` rightly
      refuses an edge to a node the corpus does not hold.
    - Nothing already in the corpus is added twice.
    """
    out = []
    for m in memberships:
        triple = (m.artist_id, PREDICATE_PLAYS_GENRE, m.genre_id)
        if triple in existing_edges or not admitted(m, allowlist):
            continue
        if m.artist_id in new_artists or (
            m.artist_id in existing_artists and m.genre_id in allowlist
        ):
            out.append(m)
    return tuple(out)


def label_collisions(candidates: Mapping[str, str], existing: Iterable[Node]) -> dict[str, str]:
    """New genre QIDs whose label folds (``graph.memory.label_key``) onto another node's, with the reason.

    The collision rule from the step 3 review: two nodes with one label make that name ambiguous and
    break its resolution, so the newcomer is never admitted and never re-pointed at the existing node.
    Collisions among the newcomers themselves drop all but none: neither can be told apart by name.
    """
    taken: dict[str, str] = {}
    for node in existing:
        taken.setdefault(label_key(node.label), node.id)
    by_key: dict[str, list[str]] = {}
    for qid, label in candidates.items():
        by_key.setdefault(label_key(label), []).append(qid)
    out: dict[str, str] = {}
    for key, qids in by_key.items():
        if key in taken:
            for qid in qids:
                out[qid] = f"label {candidates[qid]!r} folds onto existing node {taken[key]}"
        elif len(qids) > 1:
            for qid in qids:
                out[qid] = f"label {candidates[qid]!r} is shared by new genres {sorted(qids)}"
    return out


# --- pure: the diff, and the classes it allows ---------------------------------------------------------

#: The fields each class may change on a node that already existed. Anything else changing is a bug.
_CHANGEABLE = {
    "birth_year": "c",
    "birth_precision": "c",
    "inception_year": "c",
    "inception_precision": "c",
    "aliases": "d",
}


@dataclass(frozen=True, slots=True)
class Diff:
    """Every row that differs between two artifacts, sorted into D2's classes, plus what could not be."""

    counts: dict[str, int] = field(default_factory=dict)
    unclassified: tuple[str, ...] = ()

    @property
    def clean(self) -> bool:
        return not self.unclassified


def classify(
    source: Artifact,
    result: Artifact,
    *,
    recovered: frozenset[str],
    teaching: frozenset[str],
    new_genres: frozenset[str],
) -> Diff:
    """Sort every difference into (a) to (e), and list anything that fits none.

    ``recovered``, ``teaching`` and ``new_genres`` are the node ids each class is entitled to add; an
    added node outside them, a removed row of any kind, a changed edge, or a changed node field outside
    ``_CHANGEABLE`` is unclassified. Rules by predicate for added edges: ``influenced_by`` is (a),
    ``studied_with`` is (b), ``plays_genre`` is (e).
    """
    counts: dict[str, int] = {}
    bad: list[str] = []

    def count(key: str) -> None:
        counts[key] = counts.get(key, 0) + 1

    before = {n.id: n for n in source.nodes}
    after = {n.id: n for n in result.nodes}
    for qid in sorted(before.keys() - after.keys()):
        bad.append(f"node {qid} removed")
    for qid in sorted(after.keys() - before.keys()):
        node = after[qid]
        if node.kind == NODE_KIND_ARTIST and qid in recovered:
            count("a: artist node")
        elif node.kind == NODE_KIND_ARTIST and qid in teaching:
            count("b: artist node")
        elif node.kind == NODE_KIND_GENRE and qid in new_genres:
            count("e: genre node")
        else:
            bad.append(f"node {qid} ({node.kind}) added outside every class")
    for qid in sorted(before.keys() & after.keys()):
        old, new = asdict(before[qid]), asdict(after[qid])
        for name in sorted(k for k in old if old[k] != new[k]):
            if name not in _CHANGEABLE:
                bad.append(f"node {qid} field {name} changed: {old[name]!r} -> {new[name]!r}")
            else:
                count(f"{_CHANGEABLE[name]}: {name} set")

    key = lambda e: (e.subject_id, e.predicate, e.object_id)  # noqa: E731
    edges_before = {key(e): e for e in source.edges}
    edges_after = {key(e): e for e in result.edges}
    for triple in sorted(edges_before.keys() - edges_after.keys()):
        bad.append(f"edge {triple} removed")
    for triple in sorted(edges_before.keys() & edges_after.keys()):
        if edges_before[triple] != edges_after[triple]:
            bad.append(f"edge {triple} changed")
    classes = {
        PREDICATE_INFLUENCED_BY: "a",
        PREDICATE_STUDIED_WITH: "b",
        PREDICATE_PLAYS_GENRE: "e",
    }
    for triple in sorted(edges_after.keys() - edges_before.keys()):
        count(f"{classes[triple[1]]}: {triple[1]} edge")
    return Diff(counts=dict(sorted(counts.items())), unclassified=tuple(bad))


# --- the build: pure given the crawl -------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Crawl:
    """Everything ``--build`` needs, as read back from ``data/lineage/``."""

    recovery: Screening
    teaching: Screening
    dates: dict[str, Dated]
    aliases: dict[str, tuple[str, ...]]
    memberships: tuple[Membership, ...]
    genre_labels: dict[str, str]
    genre_revisions: dict[str, int]
    coverage_rows: list[dict[str, Any]]
    deprecated: frozenset[str]


@dataclass(frozen=True, slots=True)
class Built:
    artifact: Artifact
    diff: Diff
    excluded: tuple[Exclusion, ...]
    collisions: dict[str, str]
    younger: list[tuple[Edge, int, int]]
    succession: tuple[tuple[str, str, tuple[str, ...]], ...]
    no_genre: tuple[str, ...]


def rows_a(crawl: Crawl, source: Artifact, retrieved_at: str) -> Rows:
    """Class (a), with ``artists.artist_rows`` applying the influence-assertion tiers as v0.4.0 did."""
    from musical_mycelium.ingest.artists import artist_rows

    earned = artist_rows(crawl.recovery, retrieved_at=retrieved_at)
    present = {(e.subject_id, e.predicate, e.object_id) for e in source.edges}
    known = {n.id for n in source.nodes}
    edges = tuple(
        e
        for e in earned.edges
        if (e.subject_id, e.predicate, e.object_id) not in present
        and e.source_id not in crawl.deprecated
    )
    ids = {q for e in edges for q in (e.subject_id, e.object_id)}
    nodes = tuple(n for n in earned.nodes if n.id in ids and n.id not in known)
    return Rows(nodes=nodes, edges=edges, excluded=earned.excluded)


def build(crawl: Crawl, source: Artifact, *, retrieved_at: str) -> Built:
    """v0.7.1 plus (a) to (e). Offline, deterministic given the crawl, and classified before it returns."""
    from musical_mycelium.ingest import artifact as artifact_io
    from musical_mycelium.ingest import coverage as coverage_io
    from musical_mycelium.ingest import membership as membership_io

    known_ids = {n.id for n in source.nodes}
    a = rows_a(crawl, source, retrieved_at)
    b = teaching_rows(crawl.teaching, retrieved_at=retrieved_at, deprecated=crawl.deprecated)
    new_b_nodes = tuple(
        n for n in b.nodes if n.id not in known_ids and n.id not in {x.id for x in a.nodes}
    )
    new_artists = frozenset(n.id for n in a.nodes) | frozenset(n.id for n in new_b_nodes)

    existing_edges = frozenset((e.subject_id, e.predicate, e.object_id) for e in source.edges)
    chosen = select_memberships(
        crawl.memberships,
        new_artists=new_artists,
        existing_artists=frozenset(n.id for n in source.nodes if n.kind == NODE_KIND_ARTIST),
        existing_edges=existing_edges,
    )
    known_genres = frozenset(n.id for n in source.nodes if n.kind == NODE_KIND_GENRE)
    candidate_genres = {
        m.genre_id: crawl.genre_labels.get(m.genre_id, "")
        for m in chosen
        if m.genre_id not in known_genres and crawl.genre_labels.get(m.genre_id)
    }
    collisions = label_collisions(candidate_genres, (*source.nodes, *a.nodes, *new_b_nodes))
    chosen = tuple(m for m in chosen if m.genre_id not in collisions)
    layer = membership_io.build(
        chosen,
        {q: label for q, label in crawl.genre_labels.items() if q not in collisions},
        crawl.genre_revisions,
        known_genres,
        retrieved_at=retrieved_at,
        allowlist=REPERTOIRE_ALLOWLIST,
    )
    new_genres = frozenset(n.id for n in layer.nodes)

    merged = artifact_io.merge_axes(
        source,
        Artifact(nodes=a.nodes, edges=a.edges),
        Artifact(nodes=new_b_nodes, edges=b.edges),
        layer,
    )
    facts = {
        q: f for q, f in coverage_io.parse_coverage(crawl.coverage_rows).items() if q in new_genres
    }
    merged = Artifact(nodes=coverage_io.enrich(merged, facts), edges=merged.edges)
    nodes = tuple(
        replace(apply_dates(n, crawl.dates.get(n.id)), aliases=crawl.aliases.get(n.id, n.aliases))
        for n in merged.nodes
    )
    result = Artifact(nodes=nodes, edges=merged.edges)

    diff = classify(
        source,
        result,
        recovered=frozenset(n.id for n in a.nodes),
        teaching=frozenset(n.id for n in new_b_nodes),
        new_genres=new_genres,
    )
    by_id = {n.id: n for n in result.nodes}
    playing = {e.subject_id for e in result.edges if e.predicate == PREDICATE_PLAYS_GENRE}
    teachers_and_students = {
        q
        for e in result.edges
        if e.predicate == PREDICATE_STUDIED_WITH
        for q in (e.subject_id, e.object_id)
    }
    checks = {(c.subject_id, c.object_id): c for c in crawl.teaching.accepted}
    succession = tuple(
        (e.subject_id, e.object_id, tuple(checks[(e.subject_id, e.object_id)].sentences))
        for e in b.edges
        if (e.subject_id, e.object_id) in checks
        and succession_only(checks[(e.subject_id, e.object_id)].sentences)
    )
    return Built(
        artifact=result,
        diff=diff,
        excluded=(*a.excluded, *b.excluded),
        collisions=collisions,
        younger=younger_teachers(result.edges, by_id),
        succession=succession,
        no_genre=tuple(sorted(teachers_and_students - playing)),
    )


# --- the crawl: every network read, saved part by part -------------------------------------------------


def _save(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, indent=1, sort_keys=True, ensure_ascii=False) + "\n", "utf-8"
    )


def crawl_recovery(say: Callable[[str], None], pause: float = 1.0) -> Screening:  # pragma: no cover
    """(a), network half: re-fetch the unlabelled entities, re-screen every candidate touching one."""
    from musical_mycelium.ingest import prosecheck
    from musical_mycelium.ingest.artists import DEFAULT_ARTIST_SCREENING_PATH, type_exclusions
    from musical_mycelium.ingest.discovery import fetch_articles, screen_candidates, subject_titles

    old = Screening.load(DEFAULT_ARTIST_SCREENING_PATH)
    affected = unlabelled(old)
    candidates = recovery_candidates(old, affected)
    qids = sorted({q for c in candidates for q in c.pair})
    say(
        f"(a) {len(affected)} unlabelled entities; {len(candidates)} candidates touch one; {len(qids)} to re-read"
    )
    entities = {**old.entities, **prosecheck.fetch_entities(qids, pause=pause)}
    labels = {q: e.label for q, e in entities.items()}
    on_axis, off_axis = type_exclusions(candidates, labels)
    titles = subject_titles(on_axis, entities)
    say(f"(a) fetching {len(titles)} subject articles")
    articles = fetch_articles(titles, pause=pause)
    checks, failed = screen_candidates(on_axis, entities, articles)
    return Screening(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        query=f"re-screen of {len(candidates)} artist-axis candidates touching {len(affected)} "
        f"entities unlabelled in the 2026-08-05 crawl (the `mul` bug)",
        candidates=candidates,
        checks=checks,
        excluded=tuple(sorted(off_axis + failed, key=lambda e: (e.subject_id, e.object_id))),
        entities={q: entities[q] for q in qids if q in entities},
    )


def crawl_teaching(say: Callable[[str], None], pause: float = 1.0) -> Screening:  # pragma: no cover
    """(b), network half: discover bound A in birth windows, read entities and student articles, screen."""
    from musical_mycelium.ingest import prosecheck
    from musical_mycelium.ingest.discovery import fetch_articles, screen_candidates, subject_titles

    rows: list[dict[str, Any]] = []
    for lo, hi in TEACHING_WINDOWS:
        got = patient_sparql(teaching_query(lo, hi))
        say(f"(b) students born [{lo}, {hi}): {len(got)} rows")
        rows.extend(got)
    candidates = parse_discovery(rows)
    qids = sorted({q for c in candidates for q in c.pair})
    say(f"(b) {len(candidates)} distinct statements over {len(qids)} people; reading entities")
    entities = prosecheck.fetch_entities(qids, pause=pause)
    titles = subject_titles(candidates, entities)
    say(f"(b) fetching {len(titles)} student articles (~{len(titles) * pause / 60:.0f} min)")

    def report(index: int, total: int, title: str) -> None:
        if index == 1 or index % 50 == 0 or index == total:
            say(f"  [{index}/{total}] {title}")

    articles = fetch_articles(titles, pause=pause, progress=report)
    checks, failed = screen_candidates(candidates, entities, articles)
    return Screening(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        query="\n".join(teaching_query(lo, hi).strip() for lo, hi in TEACHING_WINDOWS),
        candidates=candidates,
        checks=checks,
        excluded=tuple(sorted(failed, key=lambda e: (e.subject_id, e.object_id))),
        entities=entities,
    )


def crawl_facts(
    source: Artifact, recovery: Screening, teaching: Screening, say: Callable[[str], None]
) -> dict[str, Any]:  # pragma: no cover
    """(c), (d), (e) network half, for every artist the build will hold and every node it will carry."""
    from musical_mycelium.ingest import coverage as coverage_io
    from musical_mycelium.ingest import prosecheck
    from musical_mycelium.ingest.membership import discover
    from musical_mycelium.ingest.wikidata import deprecated_statements, fetch_entities

    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    probe = Crawl(recovery, teaching, {}, {}, (), {}, {}, [], frozenset())
    a = rows_a(probe, source, stamp)
    b = teaching_rows(teaching, retrieved_at=stamp)
    artists = sorted(
        {n.id for n in source.nodes if n.kind == NODE_KIND_ARTIST}
        | {n.id for n in a.nodes}
        | {n.id for n in b.nodes}
    )
    say(f"(c) dates for {len(artists)} artists")
    date_rows: list[dict[str, Any]] = []
    # From the entity API, not the query service. On 2026-09-11 the SPARQL date query drew repeated 504s at
    # 200 artists and again at 50: the shape (a UNION over value nodes) was the problem, not the batch.
    # ``wbgetentities`` serves 40 entities a request without the query service's timeouts, and this
    # project already reads labels through it.
    date_rows.extend(fetch_date_rows(artists, say))
    say(f"(e) P136 for {len(artists)} artists")
    memberships = discover(artists, patient_sparql, chunk=75)
    known = {n.id for n in source.nodes if n.kind == NODE_KIND_GENRE}
    genre_ids = sorted({m.genre_id for m in memberships if admitted(m) and m.genre_id not in known})
    say(f"(e) labels, revisions and coverage for {len(genre_ids)} candidate genres")
    genre_facts = fetch_entities(genre_ids) if genre_ids else {}
    coverage_rows = patient_sparql(coverage_io.coverage_query(genre_ids)) if genre_ids else []
    everything = sorted({n.id for n in source.nodes} | set(artists) | set(genre_ids))
    say(f"(d) aliases for {len(everything)} nodes")
    entities = prosecheck.fetch_entities(everything)
    uris = [e.source_id for e in (*a.edges, *b.edges)]
    say(f"re-checking {len(uris)} statement URIs against Wikidata's deprecated rank")
    deprecated = sorted(deprecated_statements(uris)) if uris else []
    return {
        "date_rows": date_rows,
        "memberships": [asdict(m) for m in memberships],
        "genre_labels": {q: f.label for q, f in genre_facts.items()},
        "genre_revisions": {q: f.revision_id for q, f in genre_facts.items()},
        "coverage_rows": coverage_rows,
        "aliases": {q: list(e.aliases) for q, e in entities.items()},
        "deprecated": deprecated,
    }


def load_crawl(directory: Path = CRAWL_DIR) -> Crawl:
    """Read the three saved parts back. Fails loudly on a missing part rather than building without it."""
    facts = json.loads((directory / FACTS_FILE).read_text(encoding="utf-8"))
    return Crawl(
        recovery=Screening.load(directory / RECOVERY_FILE),
        teaching=Screening.load(directory / TEACHING_FILE),
        dates=parse_dates(facts["date_rows"]),
        aliases={q: tuple(v) for q, v in facts["aliases"].items()},
        memberships=tuple(Membership(**m) for m in facts["memberships"]),
        genre_labels=facts["genre_labels"],
        genre_revisions={q: int(v) for q, v in facts["genre_revisions"].items()},
        coverage_rows=facts["coverage_rows"],
        deprecated=frozenset(facts["deprecated"]),
    )


def main(
    argv: list[str] | None = None,
) -> int:  # pragma: no cover - CLI, hits the network on --crawl
    from musical_mycelium.ingest import artifact as artifact_io
    from musical_mycelium.ingest.wikidata import artifact_dir

    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--crawl", choices=("recovery", "teaching", "facts", "all"))
    parser.add_argument(
        "--build", action="store_true", help="offline: write v0.10.0 from the crawl"
    )
    parser.add_argument(
        "--refresh", action="store_true", help="re-crawl a part that already exists"
    )
    parser.add_argument("--overwrite", action="store_true", help="rebuild an unreleased v0.10.0")
    parser.add_argument("--pause", type=float, default=1.0)
    args = parser.parse_args(argv)

    def say(message: str) -> None:
        print(message, file=sys.stderr, flush=True)

    source = Artifact.load(artifact_dir(SOURCE_VERSION))
    parts = (
        ("recovery", "teaching", "facts")
        if args.crawl == "all"
        else (args.crawl,)
        if args.crawl
        else ()
    )
    for part in parts:
        path = CRAWL_DIR / f"{part}.json"
        if path.exists() and not args.refresh:
            say(f"{path} exists; skipping (pass --refresh to re-crawl it)")
            continue
        if part == "recovery":
            crawl_recovery(say, args.pause).write(path)
        elif part == "teaching":
            crawl_teaching(say, args.pause).write(path)
        else:
            recovery = Screening.load(CRAWL_DIR / RECOVERY_FILE)
            teaching = Screening.load(CRAWL_DIR / TEACHING_FILE)
            _save(path, crawl_facts(source, recovery, teaching, say))
        say(f"wrote {path}")

    if not args.build:
        return 0

    stamp = datetime.now(UTC).isoformat(timespec="seconds")
    built = build(load_crawl(), source, retrieved_at=stamp)
    if not built.diff.clean:
        say(f"REFUSING TO WRITE: {len(built.diff.unclassified)} unclassified change(s):")
        for line in built.diff.unclassified[:40]:
            say(f"  {line}")
        return 1

    source_manifest = artifact_io.read_manifest(artifact_dir(SOURCE_VERSION))
    snapshot = {
        n.id: n.revision_id
        for n in built.artifact.nodes
        if n.kind == NODE_KIND_GENRE and n.revision_id
    }
    manifest = artifact_io.write(
        built.artifact,
        artifact_dir(TARGET_VERSION),
        artifact_version=TARGET_VERSION,
        generator="musical_mycelium.ingest.lineage",
        predicate="P737 (influenced_by) + P136 (plays_genre) + P1066 (studied_with)",
        source=source_manifest.source,
        source_snapshot=snapshot,
        overwrite=args.overwrite,
        verification_record="docs/p1066-handcheck.md; docs/p136-allowlist-review.md",
        notes=(
            f"v{SOURCE_VERSION} plus five classified changes (phase 7.6 D2): {built.diff.counts}. "
            f"Build-time exclusions: {len(built.excluded)}. Genre label collisions refused: "
            f"{len(built.collisions)}. Teaching endpoints with no P136 genre on Wikidata: "
            f"{len(built.no_genre)}, shown as a gap and never inferred. v0.10.0 follows v0.7.1 on "
            f"purpose; see docs/ROADMAP.md section 2."
        ),
    )
    say(f"wrote v{TARGET_VERSION}: {manifest.node_count} nodes, {manifest.edge_count} edges")
    say(f"  diff {built.diff.counts}")
    say(f"  verification {manifest.verification_counts}")
    say(
        f"  younger teachers to hand-read: {len(built.younger)}; succession-only: {len(built.succession)}"
    )
    say(f"  collisions {built.collisions}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
