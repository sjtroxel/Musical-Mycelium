"""The artist axis: P737 between people and bands, bounded by the genres already in the corpus.

**This is the same screening pipeline as the genre axis, pointed at a different axis.** Discovery,
type filter, per-subject article fetch, prose check — all of it is ``ingest.discovery``'s, reused
rather than reimplemented. Only two things differ, and both are stated here rather than buried:

1. **The type test.** The genre axis asks whether both ends reach ``Q188451``. This asks whether both
   ends are a ``Q5`` (human) or a ``Q215380`` (musical group). Both QIDs were resolved by label on
   2026-08-05 rather than recalled.
2. **The bound.** ``§4.6`` scopes this to "artists reachable from genres already in the corpus", which
   is ``P136`` into the 169 genre nodes. Unbounded, the population is **28,150 statements across
   10,737 subjects** — measured 2026-08-05, not estimated.

**The axes are structurally distinct and must stay that way** (``CLAUDE.md`` invariant 3). "Kate Bush
influenced by Peter Gabriel" and "trip hop influenced by hip-hop" are not the same kind of assertion.
``graph.schema.Node.kind`` carries the distinction, and ``agent.claims.gate`` refuses to approve a
claim whose endpoints sit on different axes. This module produces artist rows; it never merges them.

**Direction matters more here than on the genre axis, and this was measured.** Kate Bush — the artist
``SPEC.md`` 2.2 names — has **zero outgoing P737** and **44 incoming**. Nobody is recorded as having
influenced her; 44 artists cite her as an influence on them. The two directions are different
populations, not two views of one:

===============================  =================  ============  ==================
direction                        in-scope artists   statements    measured
===============================  =================  ============  ==================
outgoing (who influenced them)   1,167              10,504        2026-08-05, exact
incoming (who they influenced)   1,955              12,255        2026-08-05, exact
===============================  =================  ============  ==================

``OUTGOING`` ships first because its crawl cost is exactly known — the in-corpus artist *is* the
statement subject, so it is 1,167 article fetches, about 19 minutes at the mandated 1 request/second.
In the incoming direction the subject is the *other* artist, and WDQS timed out twice trying to count
those, so that number is still an estimate and is not being planned against.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from musical_mycelium.ingest.discovery import (
    Candidate,
    DiscoveryError,
    Exclusion,
    Screening,
    parse_discovery,
)

#: Resolved by label 2026-08-05, not recalled. ``reference-never-recall-wikidata-qids`` exists because
#: recalled QIDs have been wrong every single time they were checked.
QID_HUMAN = "Q5"
QID_MUSICAL_GROUP = "Q215380"

#: ``P136`` — the genre an artist works in. This is the bound: an artist is in scope when one of their
#: genres is already a node in the corpus. It is deliberately *not* ``P737``, which is the edge being
#: ingested; using the edge as its own bound would make the population self-selecting.
PROPERTY_GENRE = "P136"
PROPERTY_INFLUENCED_BY = "P737"

#: Reason code for an off-axis object on this axis. Distinct from the genre axis's ``NOT_A_GENRE``
#: because the exclusions file is a published number and a rejection naming the wrong axis is worse
#: than no rejection at all.
NOT_AN_ARTIST = "NOT_AN_ARTIST"

OFF_AXIS_REASON = (
    f"is not a {QID_HUMAN} (human) or {QID_MUSICAL_GROUP} (musical group) via P31/P279*; P737 "
    f"objects on the artist axis include genres, works and record labels"
)


@dataclass(frozen=True, slots=True)
class Bound:
    """The corpus genres an artist must work in to be in scope, as a SPARQL ``VALUES`` clause."""

    genre_ids: tuple[str, ...]

    def values(self) -> str:
        if not self.genre_ids:
            raise DiscoveryError(
                "the artist axis is bounded by the genres already in the corpus, and none were "
                "supplied; an unbounded query is 28,150 statements and is not what §4.6 scopes"
            )
        return " ".join(f"wd:{qid}" for qid in sorted(self.genre_ids))


def outgoing_query(bound: Bound) -> str:
    """Every P737 statement whose subject is an in-scope artist — "who influenced them".

    Shaped exactly like ``discovery.DISCOVERY_QUERY`` and for the same two reasons: ``p:``/``ps:`` so
    each row carries the **statement URI** an edge has to cite, and the object's type test as a
    ``BIND(EXISTS ...)`` rather than a filtering triple, so the rejects come back too and the
    exclusion rate is measured rather than inferred from a missing count.
    """
    return f"""
SELECT ?s ?o ?statement ?objInAxis WHERE {{
  VALUES ?corpusGenre {{ {bound.values()} }}
  ?s wdt:{PROPERTY_GENRE} ?corpusGenre .
  ?s wdt:P31/wdt:P279* ?subjectType .
  VALUES ?subjectType {{ wd:{QID_HUMAN} wd:{QID_MUSICAL_GROUP} }}
  ?s p:{PROPERTY_INFLUENCED_BY} ?statement .
  ?statement ps:{PROPERTY_INFLUENCED_BY} ?o .
  BIND(EXISTS {{
    ?o wdt:P31/wdt:P279* ?objectType .
    VALUES ?objectType {{ wd:{QID_HUMAN} wd:{QID_MUSICAL_GROUP} }}
  }} AS ?objInAxis)
}}
"""


def discover_outgoing(
    genre_ids: Sequence[str],
    sparql: Callable[[str], list[dict[str, Any]]] | None = None,
) -> tuple[Candidate, ...]:
    """Run the outgoing artist query. One WDQS round trip.

    The query is injectable for the same reason ``discovery.discover`` makes it injectable: WDQS is
    materially degraded in 2026 and this project has a standing obligation to be polite to it.
    """
    if sparql is None:
        from musical_mycelium.ingest.wikidata import sparql as _sparql

        sparql = _sparql

    rows = sparql(outgoing_query(Bound(tuple(genre_ids))))
    if not rows:
        raise DiscoveryError(
            "the artist discovery query returned no rows; refusing to screen an empty candidate set"
        )
    return parse_discovery(rows)


def type_exclusions(
    candidates: Sequence[Candidate], labels: dict[str, str] | None = None
) -> tuple[tuple[Candidate, ...], tuple[Exclusion, ...]]:
    """``discovery.type_filter`` with this axis's rejection wording. No filtering logic of its own."""
    from musical_mycelium.ingest.discovery import type_filter

    return type_filter(candidates, labels, reason_code=NOT_AN_ARTIST, off_axis=OFF_AXIS_REASON)


def run_outgoing(
    genre_ids: Sequence[str],
    *,
    limit: int | None = None,
    pause: float = 1.0,
    sparql: Callable[[str], list[dict[str, Any]]] | None = None,
    progress: Callable[[str], None] | None = None,
) -> Screening:
    """Discover, type-filter, fetch, screen — the outgoing artist axis, as one call.

    Deliberately mirrors ``discovery.run`` stage for stage rather than sharing an orchestrator: the
    stages are identical but the *messages* name a different axis, and a run whose progress output
    says "genre" while it crawls artists is how two axes get conflated in someone's head before they
    get conflated in the data.

    ``limit`` truncates after discovery and after the type filter, so a slice run exercises every
    stage of the real pipeline. Finding a bug at article 900 of 1,167 is the expensive way.
    """
    from musical_mycelium.ingest import prosecheck
    from musical_mycelium.ingest.discovery import (
        fetch_articles,
        screen_candidates,
        subject_titles,
    )

    def say(message: str) -> None:
        if progress is not None:
            progress(message)

    say(f"Discovering P737 statements from artists in {len(genre_ids)} corpus genres...")
    discovered = discover_outgoing(genre_ids, sparql)
    say(f"  {len(discovered)} distinct artist-subject P737 statements")

    on_axis, _ = type_exclusions(discovered)
    say(f"  {len(on_axis)} have an artist object; {len(discovered) - len(on_axis)} do not")

    if limit is not None:
        kept = {c.pair for c in on_axis[:limit]}
        discovered = tuple(c for c in discovered if c.pair in kept)
        say(f"  --limit {limit}: screening {len(discovered)} of them")

    qids = sorted({q for candidate in discovered for q in candidate.pair})
    say(f"Reading {len(qids)} entities (label, aliases, enwiki sitelink)...")
    entities = prosecheck.fetch_entities(qids, pause=pause)

    labels = {qid: entity.label for qid, entity in entities.items()}
    on_axis, off_axis = type_exclusions(discovered, labels)

    titles = subject_titles(on_axis, entities)
    say(f"Fetching {len(titles)} subject articles (~{len(titles) * pause / 60:.0f} min)...")

    def report(index: int, total: int, title: str) -> None:
        if index == 1 or index % 25 == 0 or index == total:
            say(f"  [{index}/{total}] {title}")

    articles = fetch_articles(titles, pause=pause, progress=report)
    checks, failed = screen_candidates(on_axis, entities, articles)

    return Screening(
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        query=outgoing_query(Bound(tuple(genre_ids))).strip(),
        candidates=discovered,
        checks=checks,
        excluded=tuple(sorted(off_axis + failed, key=lambda e: (e.subject_id, e.object_id))),
        entities=entities,
    )
