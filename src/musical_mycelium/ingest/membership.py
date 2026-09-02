"""The membership layer: ``P136``, the genre an artist works in. Added at v0.6.0, phase 6 step 2.

**This is the layer that joins the two axes, and it is structural rather than narratable.** Through
v0.5.0 the corpus was 169 disconnected components in which artists and genres never touched — 128
purely artists, 41 purely genres, none mixed — because only ``P737`` was ingested and P737 does not
link the two. ``P136`` does.

## Why P136 where P279 was refused

``docs/graph-semantics.md`` §2 refused ``P279`` after reading 47 edges by hand: P279 says "bebop is a
kind of jazz", which is one preposition away from "bebop came out of jazz", and **zero** of the 47
carried a historical claim. P136 says "Miles Davis works in jazz". It makes no claim about derivation
in either direction and there is no reading of it that becomes one. That is the whole argument, and it
is why the two properties get opposite answers. Decision C1, ``graph-semantics.md`` §5.2.

The gate never has to know any of this. ``PREDICATE_PLAYS_GENRE`` is absent from
``agent.claims.ALLOWED_PREDICATES``, so a proposal carrying it is rejected ``UNSUPPORTED_PREDICATE``,
and its endpoints are a genre and an artist, so it is rejected again as ``CROSS_AXIS``. Two independent
pre-existing locks, no edit to ``agent/`` (phase 6 DoD #6).

## The object side is NOT bounded to the corpus, and that was measured rather than assumed

The plan said to keep only P136 objects already among the 169 genres. **A measurement on 2026-09-02
killed that**, and the finding is worth keeping because it is counter-intuitive: the bound does not
*coarsen* the data, it filters it **arbitrarily**. It keeps whichever of an artist's genres happen to
fall inside the 169, which has no relationship to which one is representative.

The case that settled it — every P136 Wikidata records for Red Hot Chili Peppers:

    jazz fusion, alternative rock, rock music, alternative metal, classic rock,
    funk metal, hard rock, funk rock, rap rock          -> all outside the 169
    heavy metal music                                   -> the only one inside

Nine dropped, and the survivor is arguably the least representative of the ten. Bounded ingestion would
have published "Red Hot Chili Peppers, heavy metal" and nothing else. Across the layer the bound
discarded **half of all genre precision** — 2,605 Wikidata tags reduced to 1,313 — and left **200
artists on a single arbitrarily-chosen genre**.

``rock music`` is not among the 169. Neither is alternative rock, pop rock, hard rock, indie rock or
rock and roll, because the 169 are exactly the genres carrying a ``P737`` influence edge and those
carry none.

**So the objects come in as nodes.** They are not dead ends: 305 of the 392 (78%) align to a DBpedia
``MusicGenre`` and 185 of those carry ``dbo:stylisticOrigin``, so phase 6 step 4 gives many of them
sourced influence edges. None is isolated — each has at least one membership edge — so ``isolated_nodes``
stays 0. A genre known only as an artist tag answers "where did this come from?" with a refusal that
names the gap, which is strictly more useful than an unknown node.

## Two verification tiers, because the hand-check found they differ

``.claude/rules/graph-semantics.md`` requires hand validation before ingesting a property and has no
exemption for easy cases. 30 pairs were read on 2026-09-02, stratified 15/15 between artists carrying
one-to-two genres and artists carrying three or more, seed ``p136-handcheck-2026-09-02``.

The property itself passed cleanly: **zero of 30 were category errors about the relation**, against
P279's 47 of 47. What the check found instead was per-row noise, and that it is **predicted by whether
the Wikidata statement carries a reference** — 17 of 18 referenced pairs read as clean against 5 of 12
unreferenced. n=30, judged by an agent rather than from hand-read sources, so it is a **direction and
not a rate**. It is enough to justify carrying the distinction on the row rather than averaging two
different populations behind one label.

## Deprecated statements are excluded

Added here and to both ``P737`` discovery queries on 2026-09-02. A deprecated rank is Wikidata
recording that editors judged a statement wrong; ingesting one puts a known-bad edge into a corpus
whose whole pitch is provenance. One P136 statement into the corpus is deprecated (``Izza -> hip-hop``),
as is one edge already shipped in v0.5.0 (``Nine Inch Nails influenced_by Pink Floyd``).
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from musical_mycelium.graph.schema import (
    NODE_KIND_GENRE,
    PREDICATE_PLAYS_GENRE,
    PROSE_TIER_NOT_APPLICABLE,
    SOURCE_WIKIDATA,
    VERIFICATION_MEMBERSHIP_BARE,
    VERIFICATION_MEMBERSHIP_CITED,
    Artifact,
    Edge,
    Node,
)

#: ``P136`` — the genre an artist works in.
PROPERTY_GENRE = "P136"

#: The type test for the object side. Same QID the genre axis uses, and it is a real filter rather than
#: a formality: P136 objects include things that are not music genres at all.
QID_MUSIC_GENRE = "Q188451"

#: Reason code for an object that is not a music genre. Distinct from the other axes' codes because the
#: exclusions are a published number and a rejection naming the wrong axis is worse than none.
NOT_A_GENRE = "NOT_A_GENRE"


@dataclass(frozen=True, slots=True)
class Membership:
    """One ``P136`` statement, before the type filter and before nodes exist for either end."""

    artist_id: str
    genre_id: str
    statement: str
    referenced: bool
    object_in_axis: bool

    @property
    def verification(self) -> str:
        return VERIFICATION_MEMBERSHIP_CITED if self.referenced else VERIFICATION_MEMBERSHIP_BARE


def membership_query(artist_ids: Sequence[str]) -> str:
    """Every non-deprecated ``P136`` statement for the given artists, with its evidence state.

    Three deliberate choices, each matching the existing axes rather than inventing a convention:

    1. ``p:``/``ps:`` rather than ``wdt:``, so each row carries the **statement URI** an edge cites.
       ``wdt:`` also returns only truthy statements, which silently hides rank — and rank is exactly
       what this query has to see.
    2. The object type test as ``BIND(EXISTS ...)`` rather than a filtering triple, so rejects come
       back too and the exclusion rate is **measured** instead of inferred from a missing count.
    3. ``OPTIONAL`` on the reference rather than a filter, for the same reason: an unreferenced
       statement is ingested at a weaker tier, not dropped, so it must come back as a row.

    Bounded by a large ``VALUES`` clause, so it must be sent by POST — see
    :func:`musical_mycelium.ingest.wikidata.sparql`, which chooses by URL length.
    """
    if not artist_ids:
        raise ValueError(
            "membership_query needs the artists already in the corpus; an unbounded P136 query is "
            "every tagged musician on Wikidata and is not what phase 6 step 2 scopes"
        )
    values = " ".join(f"wd:{qid}" for qid in sorted(artist_ids))
    return f"""
SELECT ?a ?g ?statement (BOUND(?ref) AS ?referenced) ?objInAxis WHERE {{
  VALUES ?a {{ {values} }}
  ?a p:{PROPERTY_GENRE} ?statement .
  ?statement ps:{PROPERTY_GENRE} ?g .
  FILTER NOT EXISTS {{ ?statement wikibase:rank wikibase:DeprecatedRank }}
  OPTIONAL {{ ?statement prov:wasDerivedFrom ?ref . }}
  BIND(EXISTS {{ ?g wdt:P31/wdt:P279* wd:{QID_MUSIC_GENRE} }} AS ?objInAxis)
}}
"""


def parse(rows: list[dict[str, Any]]) -> tuple[Membership, ...]:
    """One :class:`Membership` per ``(artist, genre)`` pair, keeping the strongest evidence seen.

    De-duplication is not optional and the direction of the merge matters. One pair can carry more
    than one statement — a preferred and a normal rank, say — and if any of them is referenced the
    pair has a reference. Taking whichever row arrived last would make the verification tier depend
    on result ordering, which is the same class of bug as letting ``Node.kind`` depend on it.
    """
    merged: dict[tuple[str, str], Membership] = {}
    for row in rows:
        artist = row["a"]["value"].rsplit("/", 1)[1]
        genre = row["g"]["value"].rsplit("/", 1)[1]
        referenced = row["referenced"]["value"] == "true"
        in_axis = row["objInAxis"]["value"] == "true"
        key = (artist, genre)
        seen = merged.get(key)
        merged[key] = Membership(
            artist_id=artist,
            genre_id=genre,
            statement=row["statement"]["value"] if seen is None else seen.statement,
            referenced=referenced or (seen is not None and seen.referenced),
            object_in_axis=in_axis,
        )
    return tuple(sorted(merged.values(), key=lambda m: (m.artist_id, m.genre_id)))


def build(
    memberships: Sequence[Membership],
    labels: dict[str, str],
    revisions: dict[str, int],
    known_genres: frozenset[str],
    retrieved_at: str | None = None,
) -> Artifact:
    """Membership edges, plus a genre node for every object the corpus does not already hold.

    ``retrieved_at`` is this layer's own, not the P737 crawl's, and they will differ by weeks. That is
    correct: provenance is per row, and a corpus assembled from reads taken at different times should
    say so rather than pretend to one moment. It also matters — a Wikidata edit between the two reads
    is exactly how ``Villano Antillano`` ended up in the artifact with no surviving corpus-genre P136.
    """
    stamp = retrieved_at or datetime.now(UTC).isoformat(timespec="seconds")
    in_axis = [m for m in memberships if m.object_in_axis]

    nodes = tuple(
        Node(
            id=qid,
            label=labels[qid],
            kind=NODE_KIND_GENRE,
            source=SOURCE_WIKIDATA,
            source_id=qid,
            retrieved_at=stamp,
            revision_id=revisions.get(qid),
        )
        for qid in sorted({m.genre_id for m in in_axis} - known_genres)
        if qid in labels
    )
    known_labels = {n.id for n in nodes} | known_genres
    edges = tuple(
        Edge(
            subject_id=m.artist_id,
            predicate=PREDICATE_PLAYS_GENRE,
            object_id=m.genre_id,
            source=SOURCE_WIKIDATA,
            source_id=m.statement,
            retrieved_at=stamp,
            prose_tier=PROSE_TIER_NOT_APPLICABLE,
            verification=m.verification,
        )
        for m in in_axis
        if m.genre_id in known_labels
    )
    return Artifact(nodes=nodes, edges=edges)


def discover(
    artist_ids: Sequence[str],
    sparql: Callable[[str], list[dict[str, Any]]] | None = None,
    chunk: int = 150,
) -> tuple[Membership, ...]:
    """Run the query in chunks and merge. Chunked because WDQS rate-limits on requests, not tokens."""
    if sparql is None:
        from musical_mycelium.ingest.wikidata import sparql as _sparql

        sparql = _sparql
    rows: list[dict[str, Any]] = []
    ids = sorted(artist_ids)
    for start in range(0, len(ids), chunk):
        batch = ids[start : start + chunk]
        rows.extend(sparql(membership_query(batch)))
        print(
            f"  {min(start + chunk, len(ids))}/{len(ids)} artists, {len(rows)} statements",
            file=sys.stderr,
        )
    return parse(rows)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI, hits the network
    """Extend a pinned artifact with the membership layer and write the next version.

    The steps are ordered so that nothing is written until every live read has succeeded: a partial
    artifact is worse than no artifact, because it looks finished.
    """
    from musical_mycelium.ingest import artifact as artifact_io
    from musical_mycelium.ingest import coverage as coverage_io
    from musical_mycelium.ingest.wikidata import (
        artifact_dir,
        deprecated_statements,
        fetch_entities,
        sparql,
    )

    parser = argparse.ArgumentParser(description="Build the P136 membership layer.")
    parser.add_argument("--source", default="0.5.0", help="artifact version to extend")
    parser.add_argument("--version", default="0.6.0", help="artifact version to write")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)

    source = Artifact.load(artifact_dir(args.source))
    # Repair before extend. A derived artifact carries its predecessor's edges across untouched, so
    # the rank filter on the discovery queries does not reach them -- see
    # ``wikidata.deprecated_statements``. Re-checking here is the only place the inherited rows are
    # ever looked at again.
    stale = deprecated_statements([e.source_id for e in source.edges])
    if stale:
        kept = tuple(e for e in source.edges if e.source_id not in stale)
        for edge in source.edges:
            if edge.source_id in stale:
                print(
                    f"  DROPPING inherited edge on a now-deprecated statement: "
                    f"{edge.subject_id} -{edge.predicate}-> {edge.object_id}",
                    file=sys.stderr,
                )
        source = Artifact(nodes=source.nodes, edges=kept)

    artists = [n.id for n in source.nodes if n.kind != NODE_KIND_GENRE]
    known = frozenset(n.id for n in source.nodes if n.kind == NODE_KIND_GENRE)
    print(
        f"source v{args.source}: {len(source.nodes)} nodes, {len(source.edges)} edges",
        file=sys.stderr,
    )

    memberships = discover(artists, sparql)
    in_axis = [m for m in memberships if m.object_in_axis]
    rejected = len(memberships) - len(in_axis)
    new_ids = sorted({m.genre_id for m in in_axis} - known)
    print(
        f"  {len(memberships)} pairs, {rejected} rejected {NOT_A_GENRE}, "
        f"{len(new_ids)} genres not already in the corpus",
        file=sys.stderr,
    )

    facts = fetch_entities(new_ids) if new_ids else {}
    labels = {q: f.label for q, f in facts.items()}
    revisions = {q: f.revision_id for q, f in facts.items()}
    layer = build(in_axis, labels, revisions, known)

    merged = artifact_io.merge_axes(source, layer)
    if new_ids:
        rows = sparql(coverage_io.coverage_query(new_ids))
        merged = Artifact(
            nodes=coverage_io.enrich(merged, coverage_io.parse_coverage(rows)),
            edges=merged.edges,
        )

    directory = artifact_dir(args.version)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = artifact_io.write(
        merged,
        directory,
        artifact_version=args.version,
        generator="musical_mycelium.ingest.membership",
        predicate=f"P737 (influenced_by) + {PROPERTY_GENRE} (plays_genre)",
        source=SOURCE_WIKIDATA,
        overwrite=args.overwrite,
        verification_record="docs/phases/phase-6-density-and-coverage-IMPLEMENTATION.md",
    )
    print(
        f"wrote v{args.version}: {manifest.node_count} nodes, {manifest.edge_count} edges\n"
        f"  {manifest.verification_counts}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
