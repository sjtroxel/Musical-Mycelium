"""Full P737 discovery: every genre-to-genre influence candidate, screened by the prose check.

**Runs locally, never in Lambda.** This is the phase-2 replacement for the literal edge tuple v0.1
shipped. The pipeline shape ``wikidata`` promised phase 2 would inherit is unchanged (*fetch,
type-filter, stamp provenance, write*); only the origin of the candidate pairs moves.

Note what this module does **not** decide: an accepted candidate is not automatically an ingested edge.
``wikidata.select_edges`` applies the hand-verification lists over this output, and it rejects six
candidates this check accepts. Screening is evidence-gathering; corpus policy lives there.

## The two filters, and why they are separate

A candidate is dropped for one of two independent reasons, and collapsing them would hide which:

1. **It is not a genre-to-genre edge.** P737 is a general ``influenced by`` property, so a music
   genre's P737 objects include bands (``doom metal <- Black Sabbath``), techniques (``drone music
   <- pedal``) and people. The type filter is the bounded membership test ``P31/P279*`` reaching
   ``Q188451`` that ``.claude/rules/graph-semantics.md`` explicitly sanctions — the *only* question
   this project asks of Wikidata's taxonomy, and one neither of the two documented P279 escapes can
   reach.
2. **Wikipedia does not support it.** That is :mod:`musical_mycelium.ingest.prosecheck`, applied to
   the survivors of (1).

Filter (1) is answered inside the discovery query, so a non-genre object never costs an article
fetch. Filter (2) is a crawl and is the expensive half.

## Exclusions are a published number, not a silent drop

Every candidate that does not survive lands in :class:`Exclusion` with a machine-readable
``reason_code`` and a human-readable ``reason``. The exclusion *rate* is a displayed coverage number
(``docs/planning/04-RISK-REGISTER.md`` 4.5), which is only honest if nothing is discarded off the
books. ``REJECTED_EDGES`` in :mod:`~musical_mycelium.ingest.wikidata` was the hand-built ancestor of
this file; :class:`Screening` is its generated successor, and ``wikidata.collect_exclusions`` merges
the two into the ``exclusions.json`` that ships beside the artifact.

## What a screening is worth

A screening run is ~15 minutes of politely rate-limited crawling, so it is written to disk and
reused. It is a **cache, not an artifact**: it lives under gitignored ``data/``, it carries the
query that produced it, and it is regenerable from the network at any time. The artifact — the
pinned, hashed, immutable thing evals run against — is written from a screening by ``wikidata``.

Usage::

    python -m musical_mycelium.ingest.discovery --limit 15   # a slice, to prove the pipeline
    python -m musical_mycelium.ingest.discovery              # the full crawl
    python -m musical_mycelium.ingest.discovery --report     # re-read the cache, no network
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Self

from musical_mycelium.ingest import prosecheck
from musical_mycelium.ingest.prosecheck import Article, Entity, ProseCheck, Tier

#: ``music genre``. Both ends of every candidate must reach this via ``P31/P279*``.
QID_MUSIC_GENRE = "Q188451"

PROPERTY_INFLUENCED_BY = "P737"

#: Where a screening cache lands by default. Untracked: it is regenerable, it is large, and a
#: 350-row crawl log is not something the repo root should carry (``CLAUDE.md`` root discipline).
DEFAULT_SCREENING_PATH = Path("data/screening.json")

#: What the population **measured** on 2026-08-04, probed clause by clause rather than assumed. The
#: 7/31 query used a direct ``wdt:P31 wd:Q188451`` with no object test, so its 351 could not simply be
#: carried over to a query that differs on both ends:
#:
#: * subject ``P31`` direct: **351** statements. Subject ``P31/P279*``: **351** as well. The
#:   transitive climb is a **no-op on the subject side** at this scale — every genre carrying a P737
#:   edge is typed directly as ``Q188451``. It stays because it is the semantically correct
#:   membership test, not because it finds anything.
#: * adding the object-side type test: **331**. So **20 statements (5.7%)** have a non-genre object,
#:   landing almost exactly on the ~6% the phase-2 plan predicted.
#:
#: Held as a number so :func:`run` can warn on drift. A partially degraded WDQS returning a
#: *truncated* result set is the failure this guards: it looks like a successful query and would
#: quietly shrink the corpus, which is precisely the kind of silent invalidation the pinned-artifact
#: discipline exists to prevent.
EXPECTED_POPULATION = 351

#: Tolerance before :func:`run` warns. Wide, because Wikidata legitimately grows — this is a tripwire
#: for a collapsed result set, not a change-detector for ordinary editing.
POPULATION_DRIFT_TOLERANCE = 0.25

#: Every P737 statement whose **subject** is a music genre, with the object's genre-ness decided in
#: the same round trip.
#:
#: Two deliberate choices. First, ``p:``/``ps:`` rather than ``wdt:``, so each row carries its
#: **statement URI** — that is what an edge cites, and it resolves to the specific assertion rather
#: than gesturing at the subject (``graph.schema.Edge``). Second, the object's type test is a
#: ``BIND(EXISTS ...)`` rather than a filtering triple pattern, so the query returns the rejects
#: too and the exclusion rate can be *measured* instead of inferred from a missing count. The BIND
#: was timed at 2.2s against the 1.8s of the same query without it, so that legibility is close to
#: free.
DISCOVERY_QUERY = f"""
SELECT ?s ?o ?statement ?objInAxis WHERE {{
  ?s wdt:P31/wdt:P279* wd:{QID_MUSIC_GENRE} .
  ?s p:{PROPERTY_INFLUENCED_BY} ?statement .
  ?statement ps:{PROPERTY_INFLUENCED_BY} ?o .
  BIND(EXISTS {{ ?o wdt:P31/wdt:P279* wd:{QID_MUSIC_GENRE} }} AS ?objInAxis)
}}
"""

#: Reason code for filter (1). Not a :class:`~musical_mycelium.ingest.prosecheck.Tier`, on purpose:
#: the tiers describe what Wikipedia said about an edge, and this candidate never got that far.
NOT_A_GENRE = "NOT_A_GENRE"


class DiscoveryError(RuntimeError):
    """Discovery could not produce a candidate set worth screening."""


@dataclass(frozen=True, slots=True)
class Candidate:
    """One P737 statement whose subject is in the axis being ingested, before Wikipedia is consulted.

    Axis-neutral on purpose. ``object_in_axis`` was ``object_is_genre`` until phase 2 step 6, when the
    artist axis needed the identical screening pipeline with a different type test on both ends. The
    genre axis asks "is the object a ``Q188451``"; the artist axis asks "is the object a human or a
    musical group". Same question, different axis, and a field named for one of them would have made
    the other read as a lie.

    **The axes stay structurally distinct downstream** — see ``graph.schema.Node.kind``. This type is
    shared because the *screening* is the same work, not because the edges are interchangeable.
    """

    subject_id: str
    object_id: str
    statement_uri: str
    object_in_axis: bool

    @property
    def pair(self) -> tuple[str, str]:
        return (self.subject_id, self.object_id)


@dataclass(frozen=True, slots=True)
class Exclusion:
    """One candidate that did not make it, and why. The unit of ``exclusions.json``."""

    subject_id: str
    object_id: str
    subject_label: str
    object_label: str
    reason_code: str
    reason: str


@dataclass(frozen=True, slots=True)
class Screening:
    """The result of screening a discovered candidate set: what survived, what did not, and why.

    Holds ``checks`` for the survivors of the type filter and ``excluded`` for everything dropped by
    either filter. The two together account for every discovered candidate, and
    :meth:`tally` is what proves it rather than asserting it.
    """

    generated_at: str
    query: str
    candidates: tuple[Candidate, ...] = ()
    checks: tuple[ProseCheck, ...] = ()
    excluded: tuple[Exclusion, ...] = ()
    entities: dict[str, Entity] = field(default_factory=dict)

    @property
    def accepted(self) -> tuple[ProseCheck, ...]:
        """The checks that may be ingested. Only ``PROSE`` — see ``ProseCheck.usable``."""
        return tuple(check for check in self.checks if check.usable)

    @property
    def pairs(self) -> tuple[tuple[str, str], ...]:
        """Accepted ``(subject, object)`` pairs, sorted, ready for ``wikidata.build``."""
        return tuple(sorted((check.subject_id, check.object_id) for check in self.accepted))

    def statement_uris(self) -> dict[tuple[str, str], str]:
        """Pair to statement URI, so the artifact build needs no second round trip to Wikidata."""
        return {c.pair: c.statement_uri for c in self.candidates}

    def tally(self) -> dict[str, int]:
        """Every candidate in exactly one bucket, plus the totals that must reconcile.

        The reconciliation is the point: ``discovered`` has to equal ``accepted`` plus every
        exclusion bucket, or a candidate has gone missing somewhere in the crawl.
        """
        counts = Counter(exclusion.reason_code for exclusion in self.excluded)
        counts[str(Tier.PROSE)] = len(self.accepted)
        out = {key: counts[key] for key in sorted(counts)}
        out["discovered"] = len(self.candidates)
        out["accepted"] = len(self.accepted)
        out["excluded"] = len(self.excluded)
        return out

    def reconciles(self) -> bool:
        return len(self.candidates) == len(self.accepted) + len(self.excluded)

    def to_json(self) -> str:
        payload = {
            "generated_at": self.generated_at,
            "query": self.query,
            "candidates": [asdict(c) for c in self.candidates],
            "checks": [_check_to_dict(c) for c in self.checks],
            "excluded": [asdict(e) for e in self.excluded],
            "entities": {qid: asdict(entity) for qid, entity in sorted(self.entities.items())},
        }
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, raw: str) -> Self:
        data: dict[str, Any] = json.loads(raw)
        return cls(
            generated_at=data["generated_at"],
            query=data["query"],
            candidates=tuple(Candidate(**row) for row in data["candidates"]),
            checks=tuple(_check_from_dict(row) for row in data["checks"]),
            excluded=tuple(Exclusion(**row) for row in data["excluded"]),
            entities={
                qid: Entity(
                    qid=qid,
                    label=row.get("label", ""),
                    enwiki_title=row.get("enwiki_title", ""),
                    # JSON has no tuples. Coercing back matters because these dataclasses are
                    # frozen and compared by value, and a list would make the round trip unequal.
                    aliases=tuple(row.get("aliases", ())),
                )
                for qid, row in data.get("entities", {}).items()
            },
        )

    @classmethod
    def load(cls, path: Path = DEFAULT_SCREENING_PATH) -> Self:
        return cls.from_json(path.read_text(encoding="utf-8"))

    def write(self, path: Path = DEFAULT_SCREENING_PATH) -> Path:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(self.to_json(), encoding="utf-8")
        return path


def _check_to_dict(check: ProseCheck) -> dict[str, Any]:
    row = asdict(check)
    row["tier"] = str(check.tier)
    return row


def _check_from_dict(row: dict[str, Any]) -> ProseCheck:
    row = dict(row)
    row["tier"] = Tier(row["tier"])
    for key in ("matched_names", "sentences"):
        row[key] = tuple(row.get(key, ()))
    return ProseCheck(**row)


# --- pure analysis ---------------------------------------------------------------------------------
# Same discipline as ``prosecheck``: everything above the fetch line is a pure function of its
# arguments, so the parsing, the de-duplication and the partition are all testable with no network.


def parse_discovery(rows: Sequence[dict[str, Any]]) -> tuple[Candidate, ...]:
    """Turn SPARQL bindings into de-duplicated candidates, sorted.

    De-duplication is not optional. One ``(subject, object)`` pair can carry more than one P737
    statement — Wikidata permits duplicate statements and they do occur — and the 7/31 script hit the
    same thing from the label side. Keeping the lexicographically first statement URI makes the
    choice deterministic, which matters because the URI ends up in the artifact and the artifact is
    hashed.
    """
    best: dict[tuple[str, str], Candidate] = {}
    for row in rows:
        try:
            subject = row["s"]["value"].rsplit("/", 1)[1]
            obj = row["o"]["value"].rsplit("/", 1)[1]
            statement = row["statement"]["value"]
        except (KeyError, IndexError) as exc:
            raise DiscoveryError(f"malformed discovery row: {row!r}") from exc

        candidate = Candidate(
            subject_id=subject,
            object_id=obj,
            statement_uri=statement,
            object_in_axis=row.get("objInAxis", {}).get("value") == "true",
        )
        existing = best.get(candidate.pair)
        if existing is None or candidate.statement_uri < existing.statement_uri:
            best[candidate.pair] = candidate

    return tuple(sorted(best.values(), key=lambda c: c.pair))


def population_drift(discovered: int) -> str:
    """A warning string when the discovered count is far from what was measured, else empty.

    Deliberately a warning and not an exception. Wikidata is a live corpus and this project's whole
    posture is that a source can change under it; the response to drift is to look, not to refuse.
    """
    if not discovered:
        return "no candidates discovered"
    ratio = abs(discovered - EXPECTED_POPULATION) / EXPECTED_POPULATION
    if ratio <= POPULATION_DRIFT_TOLERANCE:
        return ""
    direction = "below" if discovered < EXPECTED_POPULATION else "above"
    return (
        f"discovered {discovered} candidates, {ratio:.0%} {direction} the {EXPECTED_POPULATION} "
        f"measured on 2026-08-04. Check WDQS returned a complete result set before trusting this run."
    )


def type_filter(
    candidates: Sequence[Candidate],
    labels: dict[str, str] | None = None,
    *,
    reason_code: str = NOT_A_GENRE,
    off_axis: str = (
        f"does not reach {QID_MUSIC_GENRE} via P31/P279*; P737 is a general influence property "
        f"and its objects include bands, people and techniques"
    ),
) -> tuple[tuple[Candidate, ...], tuple[Exclusion, ...]]:
    """Split candidates on filter (1). Objects outside the axis become exclusions.

    Labels are optional because this runs *before* the entity fetch when it is used to decide what
    to fetch; the exclusion reason is more useful once labels exist, so the caller may pass them.

    ``reason_code`` and ``off_axis`` are parameters so the artist axis can reuse this unchanged
    (step 6). The *filtering* is identical — "is the object in the axis this run is ingesting" — and
    only the sentence explaining the rejection differs. An exclusion whose reason names the wrong
    axis is worse than useless, because the exclusions file is a published number people read.
    """
    labels = labels or {}
    kept: list[Candidate] = []
    dropped: list[Exclusion] = []
    for candidate in candidates:
        if candidate.object_in_axis:
            kept.append(candidate)
            continue
        object_label = labels.get(candidate.object_id, "")
        named = f"{object_label} ({candidate.object_id})" if object_label else candidate.object_id
        dropped.append(
            Exclusion(
                subject_id=candidate.subject_id,
                object_id=candidate.object_id,
                subject_label=labels.get(candidate.subject_id, ""),
                object_label=object_label,
                reason_code=reason_code,
                reason=f"object {named} {off_axis}",
            )
        )
    return tuple(kept), tuple(dropped)


def exclusion_for(check: ProseCheck) -> Exclusion:
    """The exclusions-file row for a candidate that failed filter (2)."""
    return Exclusion(
        subject_id=check.subject_id,
        object_id=check.object_id,
        subject_label=check.subject_label,
        object_label=check.object_label,
        reason_code=str(check.tier),
        reason=check.exclusion_reason,
    )


def subject_titles(candidates: Sequence[Candidate], entities: dict[str, Entity]) -> dict[str, str]:
    """Subject QID to English article title, for subjects that have one.

    Keyed by subject rather than by candidate because **the crawl is per subject, not per edge**.
    ``acid jazz`` carries four P737 edges and its article is one fetch, not four. At the phase-1
    scale that distinction was noise; across the full population it is most of the wall time.
    """
    titles: dict[str, str] = {}
    for candidate in candidates:
        entity = entities.get(candidate.subject_id)
        if entity is not None and entity.enwiki_title:
            titles[candidate.subject_id] = entity.enwiki_title
    return titles


def check_candidate(
    candidate: Candidate, entities: dict[str, Entity], article: Article
) -> ProseCheck:
    """Apply the prose check to one candidate against an already-fetched article. Pure."""
    subject = entities.get(candidate.subject_id, Entity(qid=candidate.subject_id))
    obj = entities.get(candidate.object_id, Entity(qid=candidate.object_id))
    return prosecheck.check_edge(
        subject_id=candidate.subject_id,
        object_id=candidate.object_id,
        subject_label=subject.label,
        object_label=obj.label,
        article=article,
        object_title=obj.enwiki_title,
        object_aliases=obj.aliases,
        subject_aliases=subject.aliases,
    )


#: The article stand-in for a subject Wikidata has no English sitelink for. 35% of the 7/31
#: population, and by far the largest single exclusion bucket — it is a coverage fact about the
#: corpus, not a failure of the check.
NO_SITELINK = Article(tier=Tier.NO_ARTICLE, detail="no enwiki sitelink on the subject entity")


def screen_candidates(
    candidates: Sequence[Candidate],
    entities: dict[str, Entity],
    articles: dict[str, Article],
) -> tuple[tuple[ProseCheck, ...], tuple[Exclusion, ...]]:
    """Run filter (2) over already-fetched articles. Pure, and the whole crawl reduces to this.

    A subject missing from ``articles`` is treated as having no article rather than as an error:
    the caller decides what it could fetch, and this function only reports what that implied.
    """
    checks: list[ProseCheck] = []
    excluded: list[Exclusion] = []
    for candidate in candidates:
        article = articles.get(candidate.subject_id, NO_SITELINK)
        check = check_candidate(candidate, entities, article)
        checks.append(check)
        if not check.usable:
            excluded.append(exclusion_for(check))
    return tuple(checks), tuple(excluded)


# --- fetching --------------------------------------------------------------------------------------


def discover(sparql: Callable[[str], list[dict[str, Any]]] | None = None) -> tuple[Candidate, ...]:
    """Run the discovery query. One WDQS round trip.

    The query is injectable so the CLI can be exercised without touching a service that is
    materially degraded in 2026 and that this project has a standing obligation to be polite to.
    """
    if sparql is None:
        from musical_mycelium.ingest.wikidata import sparql as _sparql

        sparql = _sparql
    rows = sparql(DISCOVERY_QUERY)
    if not rows:
        raise DiscoveryError(
            "the discovery query returned no rows; refusing to screen an empty candidate set"
        )
    return parse_discovery(rows)


def fetch_articles(
    titles: dict[str, str],
    *,
    pause: float = 1.0,
    progress: Callable[[int, int, str], None] | None = None,
) -> dict[str, Article]:
    """Fetch one article per subject, at one request per second.

    The rate limit is the contract with Wikimedia, not a tuning knob. ``resolve_article`` already
    sleeps ``pause`` per call and backs off on 429/503; this loop only orders the work and reports
    progress, because at this scale a silent 15-minute process is indistinguishable from a hung one.
    """
    articles: dict[str, Article] = {}
    total = len(titles)
    for index, (qid, title) in enumerate(sorted(titles.items(), key=lambda kv: kv[1]), start=1):
        if progress is not None:
            progress(index, total, title)
        articles[qid] = prosecheck.resolve_article(title, pause=pause)
    return articles


def run(
    *,
    limit: int | None = None,
    pause: float = 1.0,
    sparql: Callable[[str], list[dict[str, Any]]] | None = None,
    progress: Callable[[str], None] | None = None,
) -> Screening:
    """Discover, type-filter, fetch, screen. The whole of step 2 in one call.

    ``limit`` truncates the candidate set **after** discovery and after the type filter, so a slice
    run exercises every stage of the real pipeline rather than a shortened version of it. That is
    the point of the slice: the full crawl costs 15 minutes and several hundred requests, and
    discovering a bug at request 300 is the expensive way to find it.
    """

    def say(message: str) -> None:
        if progress is not None:
            progress(message)

    say("Discovering P737 candidates whose subject is a music genre...")
    discovered = discover(sparql)
    say(f"  {len(discovered)} distinct genre-subject P737 statements")
    if drift := population_drift(len(discovered)):
        say(f"  WARNING: {drift}")

    genre_pairs, _ = type_filter(discovered)
    say(f"  {len(genre_pairs)} have a genre object; {len(discovered) - len(genre_pairs)} do not")

    if limit is not None:
        # Slicing ``discovered`` rather than ``genre_pairs`` keeps the screening self-consistent:
        # every bucket it reports is then a bucket of the candidates it actually looked at, so a
        # slice run reconciles by the same rule the full run does.
        kept = {c.pair for c in genre_pairs[:limit]}
        discovered = tuple(c for c in discovered if c.pair in kept)
        say(f"  --limit {limit}: screening {len(discovered)} of them")

    qids = sorted({q for candidate in discovered for q in candidate.pair})
    say(f"Reading {len(qids)} entities (label, aliases, enwiki sitelink)...")
    entities = prosecheck.fetch_entities(qids, pause=pause)

    # Re-run the type filter now that labels exist, so exclusion reasons name the thing excluded.
    labels = {qid: entity.label for qid, entity in entities.items()}
    genre_pairs, not_genres = type_filter(discovered, labels)

    titles = subject_titles(genre_pairs, entities)
    say(f"Fetching {len(titles)} subject articles (~{len(titles) * pause / 60:.0f} min)...")

    def report(index: int, total: int, title: str) -> None:
        if index == 1 or index % 25 == 0 or index == total:
            say(f"  [{index}/{total}] {title}")

    articles = fetch_articles(titles, pause=pause, progress=report)

    checks, failed = screen_candidates(genre_pairs, entities, articles)
    return Screening(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        query=DISCOVERY_QUERY.strip(),
        candidates=discovered,
        checks=checks,
        excluded=tuple(sorted(not_genres + failed, key=lambda e: (e.subject_id, e.object_id))),
        entities=entities,
    )


def format_report(screening: Screening) -> str:
    """The human-readable summary. Counts first, then the accepted edges."""
    lines = [
        f"Screening generated {screening.generated_at}",
        "",
        "  bucket                     count",
        "  " + "-" * 32,
    ]
    tally = screening.tally()
    for key in ("discovered", "accepted", "excluded"):
        lines.append(f"  {key:<25}{tally[key]:>6}")
    lines.append("  " + "-" * 32)
    for key, value in tally.items():
        if key not in ("discovered", "accepted", "excluded"):
            lines.append(f"  {key:<25}{value:>6}")

    if not screening.reconciles():
        lines.append("\n  WARNING: buckets do not reconcile against the discovered count")

    accepted = screening.accepted
    lines.append(f"\n--- accepted ({len(accepted)}) ---")
    for check in sorted(accepted, key=lambda c: (c.subject_label, c.object_label)):
        flags = []
        if check.taxonomic_lead:
            flags.append(f"taxonomic-lead {check.taxonomic_hits}")
        suffix = f"  [{', '.join(flags)}]" if flags else ""
        lines.append(
            f"  {check.subject_label} <- {check.object_label}  ({check.prose_hits} hits){suffix}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--limit", type=int, default=None, help="screen only the first N genre-to-genre candidates"
    )
    parser.add_argument("--pause", type=float, default=1.0, help="seconds between requests")
    parser.add_argument(
        "--out", type=Path, default=DEFAULT_SCREENING_PATH, help="where to write the screening"
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="re-read an existing screening and print it; no network",
    )
    args = parser.parse_args(argv)

    if args.report:
        screening = Screening.load(args.out)
    else:
        screening = run(limit=args.limit, pause=args.pause, progress=lambda m: print(m, flush=True))
        path = screening.write(args.out)
        print(f"\nWrote {path}", file=sys.stderr)

    print("\n" + format_report(screening))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
