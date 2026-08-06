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

import argparse
import sys
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from musical_mycelium.graph.schema import (
    NODE_KIND_ARTIST,
    PREDICATE_INFLUENCED_BY,
    SOURCE_WIKIDATA,
    VERIFICATION_ASSERTS_AUTO,
    VERIFICATION_EXPOSURE_AUTO,
    Edge,
    Node,
)
from musical_mycelium.ingest.assertion import Assertion, classify_all
from musical_mycelium.ingest.discovery import (
    Candidate,
    DiscoveryError,
    Exclusion,
    Screening,
    parse_discovery,
)

#: Beside the genre axis's ``data/screening.json``, never overwriting it. Two axes, two records: a
#: single file would make "how many edges did the crawl accept" an ambiguous question.
DEFAULT_ARTIST_SCREENING_PATH = Path("data/artist_screening.json")

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


# --- the assertion tier, applied to a screening -------------------------------------------------


def corpus_genre_ids() -> tuple[str, ...]:
    """The bound, read off the pinned artifact rather than passed in.

    Filters on ``kind`` instead of assuming it: once the artist axis is ingested the artifact holds
    both, and bounding an artist crawl by artists would make the population self-selecting in exactly
    the way ``PROPERTY_GENRE`` is chosen to avoid.
    """
    from musical_mycelium.graph.schema import NODE_KIND_GENRE, Artifact
    from musical_mycelium.ingest.wikidata import artifact_dir

    artifact = Artifact.load(artifact_dir())
    return tuple(sorted(node.id for node in artifact.nodes if node.kind == NODE_KIND_GENRE))


def tier_of(check: Any) -> Assertion:
    """The assertion tier for one accepted prose check, from its supporting sentences.

    Derived on demand rather than stored on the ``Screening``, so re-running the filter over an
    existing crawl costs no network. That matters: the filter is the part most likely to be revised,
    and a 19-minute crawl should not have to be repeated to re-measure it.
    """
    return classify_all(check.sentences)


def assertion_tally(screening: Screening) -> dict[str, int]:
    """How the accepted prose checks split across the three assertion outcomes.

    ``NONE`` is reported, not hidden. It is the count of edges the prose check passed and the filter
    then refused, and it is the single number that says what 6a was worth.
    """
    counts = Counter(str(tier_of(check)) for check in screening.accepted)
    return {
        str(tier): counts[str(tier)]
        for tier in (Assertion.ASSERTS, Assertion.EXPOSURE, Assertion.NONE)
    }


#: Which ``verification`` an accepted check earns. ``NONE`` is absent on purpose: it is not a weaker
#: tier, it is a refusal, and mapping it to a level would put un-asserted edges in the corpus at some
#: label. An edge the filter refused does not get ingested at all.
TIER_VERIFICATION = {
    Assertion.ASSERTS: VERIFICATION_ASSERTS_AUTO,
    Assertion.EXPOSURE: VERIFICATION_EXPOSURE_AUTO,
}


#: An endpoint carried no English label. Row 41 of the held-out set at scale (scope doc A6.6): an
#: entity with no label cleared the type filter, and an empty name matches anywhere, so it silently
#: inherited another row's evidence. **Measured on the real crawl: 14 endpoints.**
NO_LABEL = "NO_LABEL"

#: The statement URI does not name this edge's subject, so ``agent.claims.resolve_sources`` can never
#: resolve it. Ingesting it would put a row in the corpus that the gate is structurally unable to
#: approve — present in every count, absent from every answer. **Measured on the real crawl: 3 edges.**
UNCITABLE_STATEMENT = "UNCITABLE_STATEMENT"

_STATEMENT_PREFIX = "http://www.wikidata.org/entity/statement/"


@dataclass(frozen=True, slots=True)
class ArtistRows:
    """What a screening earned, and what it lost on the way. Both halves, always.

    ``excluded`` exists because "the drop *is* the finding" is this phase's rule, and a builder that
    returned only survivors would make the losses invisible at exactly the stage where they are
    cheapest to see.
    """

    nodes: tuple[Node, ...] = ()
    edges: tuple[Edge, ...] = ()
    excluded: tuple[Exclusion, ...] = ()

    def tally(self) -> dict[str, int]:
        counts = Counter(exclusion.reason_code for exclusion in self.excluded)
        return {
            "nodes": len(self.nodes),
            "edges": len(self.edges),
            **{key: counts[key] for key in sorted(counts)},
        }


def artist_rows(
    screening: Screening,
    *,
    retrieved_at: str,
    revisions: dict[str, int] | None = None,
) -> ArtistRows:
    """The artist nodes and edges a screening earns. Pure: no network, no merge, no artifact.

    Only ``ASSERTS`` and ``EXPOSURE`` become edges. ``NONE`` is dropped, which is the entire point of
    6a — on this axis the prose check alone accepts recording trucks, cover versions and support slots
    as evidence of influence.

    **Nodes are derived from the surviving edges, never from the crawl.** An artist who appears only in
    refused candidates is not in the corpus, because a node with no edge is a name the product cannot
    say anything grounded about.

    **Unusable rows are excluded and reported, never raised and never silently dropped.** An early
    version raised on the first unlabelled entity, which would have aborted all 834 edges over 14 bad
    endpoints — brittle in the one direction this pipeline cannot afford, since the crawl that produced
    the input costs 20 minutes.
    """
    statements = screening.statement_uris()
    revisions = revisions or {}

    def label_of(qid: str) -> str:
        entity = screening.entities.get(qid)
        return entity.label.strip() if entity else ""

    def drop(check: Any, code: str, reason: str) -> Exclusion:
        return Exclusion(
            subject_id=check.subject_id,
            object_id=check.object_id,
            subject_label=label_of(check.subject_id),
            object_label=label_of(check.object_id),
            reason_code=code,
            reason=reason,
        )

    edges: list[Edge] = []
    excluded: list[Exclusion] = []
    node_ids: set[str] = set()

    for check in screening.accepted:
        verification = TIER_VERIFICATION.get(tier_of(check))
        if verification is None:
            continue

        pair = (check.subject_id, check.object_id)
        uri = statements.get(pair, "")
        entity = uri.removeprefix(_STATEMENT_PREFIX).split("-", 1)[0]
        if not uri or entity != check.subject_id:
            excluded.append(
                drop(
                    check,
                    UNCITABLE_STATEMENT,
                    f"statement {uri!r} does not name subject {check.subject_id}; the gate resolves a "
                    f"citation by that match, so this edge could never be approved",
                )
            )
            continue

        if not label_of(check.subject_id) or not label_of(check.object_id):
            excluded.append(
                drop(
                    check,
                    NO_LABEL,
                    "an endpoint has no English label; an unnamed node cannot be cited or matched, "
                    "and an empty label is what produced the row-41 evidence-inheritance defect",
                )
            )
            continue

        edges.append(
            Edge(
                subject_id=check.subject_id,
                predicate=PREDICATE_INFLUENCED_BY,
                object_id=check.object_id,
                source=SOURCE_WIKIDATA,
                source_id=uri,
                retrieved_at=retrieved_at,
                prose_tier="PROSE",
                verification=verification,
            )
        )
        node_ids.update(pair)

    nodes = tuple(
        Node(
            id=qid,
            label=label_of(qid),
            source=SOURCE_WIKIDATA,
            source_id=qid,
            retrieved_at=retrieved_at,
            kind=NODE_KIND_ARTIST,
            revision_id=revisions.get(qid),
        )
        for qid in sorted(node_ids)
    )
    return ArtistRows(
        nodes=nodes,
        edges=tuple(sorted(edges, key=lambda e: (e.subject_id, e.object_id))),
        excluded=tuple(sorted(excluded, key=lambda e: (e.subject_id, e.object_id))),
    )


def format_report(screening: Screening) -> str:
    """The artist-axis summary. Deliberately not ``discovery.format_report``: the stages are the same
    but this one has to show the assertion split, which is the whole reason the axis needed 6a."""
    tally = screening.tally()
    lines = [
        f"Artist axis (outgoing P737), screening generated {screening.generated_at}",
        "",
        "  bucket                     count",
        "  " + "-" * 32,
    ]
    for key in ("discovered", "accepted", "excluded"):
        lines.append(f"  {key:<25}{tally[key]:>6}")
    lines.append("  " + "-" * 32)
    for key, value in tally.items():
        if key not in ("discovered", "accepted", "excluded"):
            lines.append(f"  {key:<25}{value:>6}")

    if not screening.reconciles():
        lines.append("\n  WARNING: buckets do not reconcile against the discovered count")

    assertions = assertion_tally(screening)
    lines += [
        "",
        "  of the prose-accepted, the assertion filter says:",
        "  " + "-" * 32,
    ]
    for key, value in assertions.items():
        lines.append(f"  {key:<25}{value:>6}")
    lines.append(
        f"\n  ingestable (ASSERTS + EXPOSURE): "
        f"{assertions[str(Assertion.ASSERTS)] + assertions[str(Assertion.EXPOSURE)]}"
    )
    lines.append(
        "  EXPOSURE recall is 20% (scope doc A6.5) — that tier is a floor on what exists, "
        "never a count of it."
    )

    lines.append(f"\n--- ASSERTS ({assertions[str(Assertion.ASSERTS)]}) ---")
    for check in sorted(screening.accepted, key=lambda c: (c.subject_label, c.object_label)):
        if tier_of(check) is Assertion.ASSERTS:
            lines.append(f"  {check.subject_label} <- {check.object_label}")
    return "\n".join(lines)


def _build(screening_path: Path, version: str) -> int:
    """Merge this axis into the pinned corpus and write a new artifact version. No network.

    Reads the crawl off disk rather than re-running it, so the 20-minute cost is paid once and the
    build is replayable. The genre rows are carried across from the pinned artifact untouched — the
    same no-refetch rule that governed the v0.3.0 migration, and for the same reason: the corpus moves,
    so re-reading it would silently change edges this build is not supposed to touch.
    """
    from datetime import datetime as _dt

    from musical_mycelium.graph.schema import Artifact, read_manifest
    from musical_mycelium.ingest import artifact as artifact_io
    from musical_mycelium.ingest.wikidata import artifact_dir

    screening = Screening.load(screening_path)
    retrieved_at = _dt.now(UTC).isoformat(timespec="seconds")
    rows = artist_rows(screening, retrieved_at=retrieved_at)

    genres = Artifact.load(artifact_dir())
    genre_manifest = read_manifest(artifact_dir())
    merged = artifact_io.merge_axes(genres, Artifact(nodes=rows.nodes, edges=rows.edges))

    tally = screening.tally()
    assertions = assertion_tally(screening)
    manifest = artifact_io.write(
        merged,
        artifact_dir(version),
        artifact_version=version,
        generator="musical_mycelium.ingest.artists --build",
        predicate=genre_manifest.predicate,
        source=genre_manifest.source,
        source_snapshot=genre_manifest.source_snapshot,
        verification_record=genre_manifest.verification_record,
        notes=(
            f"Adds the artist axis (outgoing P737) to the genre corpus carried across from "
            f"v{genre_manifest.artifact_version} untouched. Stage counts, published because the drop "
            f"is the finding: {tally['discovered']} statements discovered, "
            f"{tally['discovered'] - tally.get(NOT_AN_ARTIST, 0)} with an artist at both ends, "
            f"{tally['accepted']} cleared the Wikipedia prose check, and of those the "
            f"influence-assertion filter judged {assertions[str(Assertion.ASSERTS)]} to assert "
            f"influence, {assertions[str(Assertion.EXPOSURE)]} to record formative exposure only, and "
            f"refused {assertions[str(Assertion.NONE)]}. A further {len(rows.excluded)} were dropped "
            f"at build time ({rows.tally().get(NO_LABEL, 0)} with an unlabelled endpoint, "
            f"{rows.tally().get(UNCITABLE_STATEMENT, 0)} whose statement URI does not name the edge's "
            f"subject and which the gate could therefore never approve), leaving {len(rows.edges)} "
            f"artist edges over {len(rows.nodes)} artist nodes. EXPOSURE_AUTO recall is 20% measured "
            f"on a held-out set (scope doc A6.5): that tier is a floor on what exists in the sources, "
            f"never a count of it. Artist nodes carry no revision_id — the genre axis pins an exact "
            f"Wikidata revision per node and the artist axis does not yet. "
            f"Genre corpus notes follow. {genre_manifest.notes}"
        ),
    )

    print(f"Wrote {artifact_dir(version)}")
    print(f"  nodes {manifest.node_count}  edges {manifest.edge_count}")
    print(f"  verification {manifest.verification_counts}")
    print(f"  structure {manifest.structure}")
    print(f"  build-time exclusions {rows.tally()}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="screen only the first N artist-to-artist candidates",
    )
    parser.add_argument("--pause", type=float, default=1.0, help="seconds between requests")
    parser.add_argument(
        "--out",
        type=Path,
        default=DEFAULT_ARTIST_SCREENING_PATH,
        help="where to write the screening",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help="re-read an existing screening and print it; no network",
    )
    parser.add_argument(
        "--build",
        metavar="VERSION",
        default=None,
        help="merge this axis into the pinned corpus and write that artifact version; no network",
    )
    args = parser.parse_args(argv)

    if args.build:
        return _build(args.out, args.build)

    if args.report:
        screening = Screening.load(args.out)
    else:
        genre_ids = corpus_genre_ids()
        print(f"Bounding by {len(genre_ids)} corpus genres", file=sys.stderr)
        screening = run_outgoing(
            genre_ids,
            limit=args.limit,
            pause=args.pause,
            progress=lambda m: print(m, flush=True),
        )
        path = screening.write(args.out)
        print(f"\nWrote {path}", file=sys.stderr)

    print("\n" + format_report(screening))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
