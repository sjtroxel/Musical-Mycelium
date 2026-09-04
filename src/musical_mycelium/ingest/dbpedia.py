"""The second source: DBpedia's ``dbo:stylisticOrigin``. Added at v0.7.0, phase 6 step 4.

This is the step that makes ``Edge.source`` mean something. Through v0.6.0 every edge in the corpus was
sourced to Wikidata, which is why ``contested`` was *arithmetically* unreachable rather than merely
unbuilt (decision A1): nothing could disagree with anything, because there was only ever one voice.
This module adds the second voice. Step 5 is what listens for disagreement between them.

## The tension this module exists to resolve, and how

DBpedia's ``stylisticOrigin`` is extracted from the **Wikipedia infobox**. This project already has an
opinion about Wikipedia genre infoboxes, and the opinion is not favourable: ``ingest.prosecheck`` scores
an edge ``INFOBOX_ONLY`` when the object appears in the infobox but not in body prose, calls genre
infoboxes *"casually edited and rarely cited"*, and **excludes those edges from ingestion** — 14 of them
at v0.2.0, and ``prosecheck`` line 408 says infobox agreement is *"only weak — never grounds for
ingestion."*

Ingesting DBpedia's infobox-derived edges without screening would therefore mean the corpus applied
**two different standards to the same evidence**, deciding by which service happened to serve it. That
is not defensible, and it was measured rather than argued: of the 218 candidates the prose check
excluded at v0.2.0, DBpedia independently asserts 9 — including **7 of the 14 ``INFOBOX_ONLY`` ones**,
and **zero** of the 35 ``ORPHAN`` or 116 ``NO_ARTICLE`` ones. The overlap sits exactly where the shared
infobox predicts and nowhere else.

**So DBpedia candidates are put to the same prose check, and only ``PROSE`` is ingested.** One standard
for one corpus. The rejects go to ``exclusions.json`` with the rate published, which is also what named
uncertainty §9.4 asks step 4 to measure before any copy quotes a density number.

## Why the surviving edges still get their own tier

An edge that clears the prose check here has been checked *identically* to a ``PROSE_AUTO`` edge, so a
separate tier could look like padding. It is not, and the difference is structural:

- ``PROSE_AUTO``: Wikidata editors asserted the statement, and the subject's Wikipedia article
  independently confirmed it. ``docs/graph-semantics.md`` §4.3 **tested** that independence — only 5% of
  checkable edges were infobox-only, so Wikidata's genre statements are not harvested from infoboxes.
- ``INFOBOX_AUTO``: DBpedia extracted the candidate from the subject article's infobox, and the *same
  article's* body prose confirmed it. One page agreeing with itself.

The confirmation is real and it is the strongest check this project has. What it is not is *independent*
of the candidate, and a corpus that recorded both at one tier would be claiming corroboration it does not
have. See ``graph.schema.VERIFICATION_INFOBOX_AUTO``.

## Growth follows the closure, and the closure terminates

``stylisticOrigin`` edges that point outside the corpus bring their targets in. How far that follows was
ambiguous in the plan — one hop, or to closure — and was measured on 2026-09-04 rather than argued: hop 1
adds 167 genres, hop 2 adds 49, hop 3 adds 8, and hop 4 adds none. **The entire cost of closure over a
one-hop bound is 57 genres**, so the bound buys nothing and would have to be defended as meaning
something it does not mean. Same reasoning as step 2's unbounded membership decision, an order of
magnitude cheaper. The ceiling is the source's own extent: the whole DBpedia genre-origin graph is 1,601
genres and the closure reaches 678 of them.

Growth is still gated on Wikidata alignment. A discovered resource with no ``owl:sameAs`` to a Wikidata
entity is excluded (:data:`NO_WIKIDATA_MATCH`), because every node in this corpus carries a
``revision_id`` pinning the exact revision read and a DBpedia-native node cannot have one. 13 of 224 at
the step 4 cut, and one of those 13 is ``List_of_break-in_records`` — a Wikipedia *list article* typed
``dbo:MusicGenre``, which is a fair warning about how much lighter DBpedia's typing is than Wikidata's.

## Licensing, which is a hard rule here and not a footnote

DBpedia is Wikipedia-derived and **CC BY-SA 3.0**, where Wikidata is CC0. ``04-RISK-REGISTER.md`` §4.3
names it explicitly and ``.claude/rules/graph-semantics.md`` requires the attribution be displayed
rather than buried. Two consequences land in this module:

1. Every DBpedia-sourced edge carries a **resolvable DBpedia resource URI** in ``source_id``, exactly as
   Wikidata edges carry a statement URI. Attribution is structural, like provenance.
2. ``DATA-LICENSES.md`` states which parts of the artifact are under which licence, because the repo
   ``LICENSE`` is MIT and covers the code, not a mixed-licence corpus.

The SPA's visible attribution is step 8's.

## The counting trap, which every query against this endpoint has

DBpedia's public endpoint holds type assertions across several named graphs, so a ``COUNT(*)`` over a
``?a a dbo:MusicGenre`` join multiplies rows per graph. The first run of the both-ends-typed count
returned 35,947 — larger than the unfiltered count of the same relation, and therefore impossible. Every
count here is ``COUNT(DISTINCT ...)`` or a de-duplicated set, and the error inflates, which is the
direction that flatters a plan.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from typing import Any

from musical_mycelium.graph.schema import (
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    SOURCE_DBPEDIA,
    SOURCE_WIKIDATA,
    VERIFICATION_INFOBOX_AUTO,
    Artifact,
    Edge,
    Node,
)

#: The public endpoint. Read-only, no key, and materially healthier than WDQS in 2026 — measured at
#: 0.43s for a full-graph count on 2026-09-04, where the equivalent WDQS query times out.
DBPEDIA_SPARQL = "https://dbpedia.org/sparql"

#: Contactable User-Agent, same obligation as the MusicBrainz and Wikimedia crawls.
USER_AGENT = "musical-mycelium/0.7.0 (https://github.com/sjtroxel; sjtroxel@protonmail.com)"

DBO_STYLISTIC_ORIGIN = "http://dbpedia.org/ontology/stylisticOrigin"
DBO_MUSIC_GENRE = "http://dbpedia.org/ontology/MusicGenre"
OWL_SAME_AS = "http://www.w3.org/2002/07/owl#sameAs"
DBPEDIA_RESOURCE_PREFIX = "http://dbpedia.org/resource/"
WIKIDATA_ENTITY_PREFIX = "http://www.wikidata.org/entity/"

#: Reason code for a discovered DBpedia resource carrying no ``owl:sameAs`` to Wikidata. Distinct from
#: the prose check's codes because it is a *different kind* of rejection — the edge was never checked,
#: the endpoint could not be given a node to hang it on. 13 of 224 at the step 4 cut.
NO_WIKIDATA_MATCH = "NO_WIKIDATA_MATCH"

#: Retryable status codes. Identical to ``ingest.wikidata._RETRYABLE`` and ``prosecheck._RETRYABLE``,
#: and identical on purpose: a transient 5xx must not abort a crawl of several hundred.
_RETRYABLE = frozenset({429, 500, 502, 503, 504})

#: Rows per page. The endpoint caps a single result set well below the full origin graph, so every
#: unbounded read here pages rather than trusting one response to be complete. A silently truncated
#: result is the failure mode that would make every downstream count quietly too small.
PAGE = 10_000


class DBpediaError(RuntimeError):
    """The endpoint could not be read, or answered with something this module refuses to trust."""


def _post(query: str, *, timeout: int = 180, attempts: int = 5) -> dict[str, Any]:
    """One polite POST with backoff. POST rather than GET because ``VALUES`` clauses get long."""
    body = urllib.parse.urlencode({"query": query}).encode()
    request = urllib.request.Request(
        DBPEDIA_SPARQL,
        data=body,
        headers={
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
            "User-Agent": USER_AGENT,
        },
    )
    delay = 5.0
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                result: dict[str, Any] = json.load(response)
                return result
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRYABLE or attempt == attempts:
                raise DBpediaError(
                    f"DBpedia returned {exc.code} for a query of {len(query)} chars"
                ) from exc
            time.sleep(delay)
            delay *= 2
        except urllib.error.URLError as exc:
            if attempt == attempts:
                raise DBpediaError(f"could not reach {DBPEDIA_SPARQL}: {exc.reason}") from exc
            time.sleep(delay)
            delay *= 2
    raise DBpediaError("unreachable")


def sparql(query: str) -> list[dict[str, Any]]:
    """Run one query and return its bindings. The seam the CLI injects around in tests."""
    payload = _post(query)
    bindings: list[dict[str, Any]] = payload.get("results", {}).get("bindings", [])
    return bindings


def _qid(uri: str) -> str:
    return uri.rsplit("/", 1)[-1]


def alignment_query(qids: Sequence[str]) -> str:
    """DBpedia ``MusicGenre`` resources for the given Wikidata QIDs, via ``owl:sameAs``.

    The type test is a filtering triple here rather than the ``BIND(EXISTS ...)`` the Wikidata queries
    use, and the difference is deliberate: on that axis the rejects had to come back so the exclusion
    rate could be measured, whereas a Wikidata genre with no DBpedia *resource* is not a rejection at
    all. It is simply absent from the second source, which is what the alignment count reports.

    ``FILTER(STRSTARTS(...))`` because ``owl:sameAs`` on a DBpedia resource fans out to Freebase, YAGO
    and every language chapter. Without it the same genre returns a dozen times and the alignment count
    becomes a count of interwiki links.
    """
    if not qids:
        raise ValueError(
            "alignment_query needs QIDs; an unbounded owl:sameAs read is the whole web"
        )
    values = " ".join(f"<{WIKIDATA_ENTITY_PREFIX}{qid}>" for qid in sorted(qids))
    return f"""
SELECT DISTINCT ?res ?wd WHERE {{
  VALUES ?wd {{ {values} }}
  ?res <{OWL_SAME_AS}> ?wd .
  ?res a <{DBO_MUSIC_GENRE}> .
  FILTER(STRSTARTS(STR(?res), "{DBPEDIA_RESOURCE_PREFIX}"))
}}
"""


def origin_graph_query(offset: int = 0, limit: int = PAGE) -> str:
    """The whole genre-to-genre ``stylisticOrigin`` graph, one page at a time.

    Both ends typed ``MusicGenre``, ``DISTINCT`` per the counting trap in the module docstring, and
    ``ORDER BY`` because paging an unordered result set is how rows go missing between pages.

    Reading the entire graph in one paged pass rather than querying per-subject is the polite choice as
    well as the fast one: the closure needs edges out of genres that are not yet in the corpus, and
    discovering those one round trip at a time would mean hundreds of requests to compute a set that
    fits comfortably in memory.
    """
    return f"""
SELECT DISTINCT ?s ?o WHERE {{
  ?s <{DBO_STYLISTIC_ORIGIN}> ?o .
  ?s a <{DBO_MUSIC_GENRE}> .
  ?o a <{DBO_MUSIC_GENRE}> .
}} ORDER BY ?s ?o LIMIT {limit} OFFSET {offset}
"""


def _fold(text: str) -> str:
    """Normalise a DBpedia resource name or a Wikidata label for comparison."""
    return text.replace("_", " ").strip().casefold()


def resource_to_qid(
    pairs: Iterable[tuple[str, str]], labels: dict[str, str]
) -> tuple[dict[str, str], tuple[tuple[str, tuple[str, ...]], ...]]:
    """Group ``(qid, resource)`` pairs into one QID per resource, resolving the genuine collisions.

    **This function exists because of a real defect in the first v0.7.0 cut, found by checking a
    six-edge discrepancy rather than by a failing test.** ``owl:sameAs`` is many-to-many and the first
    implementation assumed it was one-to-one *in both directions*, using a dict in each. Both silently
    kept whichever row iterated last:

    - **One resource, several QIDs.** DBpedia's ``Rock_and_roll`` is ``sameAs`` both ``rock music``
      (Q11399) and ``rock and roll`` (Q7749) — different genres, not duplicate Wikidata items.
    - **One QID, several resources.** The same QIDs are also ``sameAs`` ``Rock_music``. Keying by QID
      therefore *dropped* one of the two resources, which pushed a genre the corpus already held into
      the "newly discovered" path where there are no labels to disambiguate with.

    In the first cut, **46 edges landed on `rock and roll` that belong to `rock music`** — iteration
    order deciding what the corpus says about one of its most central nodes, in a project about
    influence. Two of the five collisions happened to land correctly, which is why nothing failed. It
    is the same class of failure the schema's ``Node.kind`` docstring and ``membership.parse`` both
    warn about, and ``MEMORY.md`` records three instances of in one night, none of which raised.

    **The rule: an exact label match wins, and nothing else does.** A DBpedia resource name comes from
    the Wikipedia article title, so ``Rock_and_roll`` folding to exactly the Wikidata label ``rock and
    roll`` is strong evidence, and ``rock music`` is not a near miss — it is a different string. Where
    no single QID matches exactly the resource is **dropped and reported**, because a fuzzy tie-break
    would be a guess about a node's identity and every edge on that node would inherit it.

    Taking pairs rather than a dict is the structural half of the fix: there is no longer a dict for a
    collision to be silently absorbed into before this function ever sees it.
    """
    grouped: dict[str, set[str]] = {}
    for qid, resource in pairs:
        grouped.setdefault(resource, set()).add(qid)

    resolved: dict[str, str] = {}
    ambiguous: list[tuple[str, tuple[str, ...]]] = []
    for resource, qids in grouped.items():
        if len(qids) == 1:
            resolved[resource] = next(iter(qids))
            continue
        name = _fold(resource.rsplit("/", 1)[-1])
        exact = sorted(q for q in qids if _fold(labels.get(q) or "") == name)
        if len(exact) == 1:
            resolved[resource] = exact[0]
        else:
            ambiguous.append((resource, tuple(sorted(qids))))
    return resolved, tuple(sorted(ambiguous))


def align(
    qids: Sequence[str],
    runner: Callable[[str], list[dict[str, Any]]] | None = None,
    chunk: int = 120,
    pause: float = 1.0,
) -> tuple[tuple[str, str], ...]:
    """Map corpus QIDs to DBpedia resource URIs. Chunked, because ``VALUES`` clauses have limits.

    **Returns ``(qid, resource)`` pairs, not a dict, and that is the fix rather than a style choice.**
    ``owl:sameAs`` is many-to-many: one QID can carry several DBpedia resources just as one resource
    can carry several QIDs. Accumulating into ``dict[qid] = resource`` silently discarded a resource
    per collision, and the discarded one then looked like a genre the corpus had never seen. Pairs
    cannot absorb a collision, so :func:`resource_to_qid` gets to decide about it with labels in hand.
    """
    run = runner or sparql
    out: set[tuple[str, str]] = set()
    ids = sorted(set(qids))
    for start in range(0, len(ids), chunk):
        batch = ids[start : start + chunk]
        for row in run(alignment_query(batch)):
            out.add((_qid(row["wd"]["value"]), row["res"]["value"]))
        if start + chunk < len(ids):
            time.sleep(pause)
    return tuple(sorted(out))


def fetch_origin_graph(
    runner: Callable[[str], list[dict[str, Any]]] | None = None,
    pause: float = 1.0,
    max_pages: int = 20,
) -> frozenset[tuple[str, str]]:
    """Every ``(subject, object)`` origin pair DBpedia holds between two music genres.

    ``max_pages`` is a guard, not a tuning knob: an endpoint that ignored ``OFFSET`` would otherwise
    page forever returning the same rows. Measured at 5,124 pairs on 2026-09-04, so one page of 10,000
    is enough today and the loop exists for the day it is not.
    """
    run = runner or sparql
    pairs: set[tuple[str, str]] = set()
    for page in range(max_pages):
        rows = run(origin_graph_query(offset=page * PAGE))
        if not rows:
            break
        pairs.update((row["s"]["value"], row["o"]["value"]) for row in rows)
        if len(rows) < PAGE:
            break
        time.sleep(pause)
    else:
        raise DBpediaError(
            f"origin graph did not terminate within {max_pages} pages of {PAGE}; refusing a "
            f"result set that may be looping rather than paging"
        )
    if not pairs:
        raise DBpediaError(
            "the origin query returned no rows; refusing to screen an empty candidate set"
        )
    return frozenset(pairs)


def closure(
    seed: Iterable[str], pairs: frozenset[tuple[str, str]], max_hops: int = 12
) -> tuple[frozenset[str], tuple[int, ...]]:
    """Follow ``stylisticOrigin`` out of the seed until it stops adding genres.

    Returns the reached set and the per-hop growth, because *"it terminates"* is a claim that should
    come with the evidence attached rather than be asserted. Measured from the 459 aligned v0.6.0
    genres: 167, 49, 8, then nothing.

    Direction matters and is easy to get backwards — ``MEMORY.md`` records assuming the origins
    direction as a recurring failure mode with three instances in one night, none of which raised. This
    walks **subject to object**, i.e. from a genre to what it came out of, which is the direction that
    reaches a genre's ancestry. Walking the other way would collect its descendants instead, and both
    are plausible-looking sets of music genres, which is precisely why nothing here would have failed.
    """
    out: dict[str, set[str]] = {}
    for subject, obj in pairs:
        out.setdefault(subject, set()).add(obj)
    reached = set(seed)
    frontier = set(reached)
    growth: list[int] = []
    for _ in range(max_hops):
        nxt = {o for s in frontier for o in out.get(s, ()) if o not in reached}
        if not nxt:
            break
        growth.append(len(nxt))
        reached |= nxt
        frontier = nxt
    else:
        raise DBpediaError(
            f"closure did not terminate within {max_hops} hops; the origin graph should be shallow "
            f"and one that is not needs looking at before it is ingested"
        )
    return frozenset(reached), tuple(growth)


@dataclass(frozen=True, slots=True)
class Origin:
    """One ``stylisticOrigin`` edge, aligned into Wikidata's identifier space.

    ``resource`` is the *subject's* DBpedia URI and becomes the edge's ``source_id``: it is what a
    reader follows to check the claim, and it is the CC BY-SA attribution link the licence requires.
    """

    subject_id: str
    object_id: str
    resource: str

    @property
    def pair(self) -> tuple[str, str]:
        return (self.subject_id, self.object_id)


def to_origins(
    pairs: Iterable[tuple[str, str]], resource_to_qid: dict[str, str]
) -> tuple[tuple[Origin, ...], tuple[tuple[str, str], ...]]:
    """Translate resource-space pairs into QID-space origins, keeping what could not be translated.

    The unresolved list is returned rather than dropped because it becomes ``exclusions.json`` rows.
    A silent drop here would make the alignment rate look better than it is, and the alignment rate is
    a published number.
    """
    origins: list[Origin] = []
    unresolved: list[tuple[str, str]] = []
    for subject, obj in sorted(pairs):
        s_qid, o_qid = resource_to_qid.get(subject), resource_to_qid.get(obj)
        if s_qid is None or o_qid is None:
            unresolved.append((subject, obj))
            continue
        if s_qid == o_qid:
            # A genre that lists itself as its own origin. Rare, and it would become a self-loop that
            # every traversal has to special-case forever.
            continue
        origins.append(Origin(subject_id=s_qid, object_id=o_qid, resource=subject))
    return tuple(origins), tuple(unresolved)


def build(
    accepted: Sequence[Origin],
    labels: dict[str, str],
    revisions: dict[str, int],
    known_genres: frozenset[str],
    retrieved_at: str | None = None,
    known_edges: frozenset[tuple[str, str, str]] = frozenset(),
) -> Artifact:
    """Influence edges from the accepted origins, plus a genre node for every object not already held.

    ``retrieved_at`` is this layer's own and will differ from the P737 crawl's by weeks. That is
    correct and deliberate — provenance is per row, and a corpus assembled from reads taken at
    different times should say so rather than pretend to one moment (``membership.build`` says the
    same, for the same reason).

    **Nodes carry ``SOURCE_WIKIDATA``, not ``SOURCE_DBPEDIA``, and the asymmetry is the honest
    reading.** DBpedia is where the *edge* was asserted, so the edge is sourced to it. But a node's
    label, revision and coverage are read from Wikidata, so that is where the node's provenance points.
    Marking these nodes ``dbpedia`` would credit DBpedia with data it did not supply.

    **``known_edges`` exists because of a real defect, caught before it shipped.**
    ``artifact.merge_axes`` keys edges on ``(subject_id, predicate, object_id)`` and later inputs win,
    so a DBpedia edge duplicating an existing Wikidata edge would **overwrite** it — silently replacing
    a statement URI with a resource URI and downgrading a ``HAND`` or ``PROSE_AUTO`` row to
    ``INFOBOX_AUTO``. That is the corroborating 80 being destroyed by the very thing that corroborates
    them, and it would have looked like a successful build.

    So an origin whose triple is already in the corpus is **skipped, not emitted**. The corroboration
    is not lost — it is exactly what step 5 is for — but an artifact whose schema holds **one source
    per edge** cannot express "two sources agree", and quietly letting the second overwrite the first
    is the worst of the available ways to not express it.
    """
    stamp = retrieved_at or datetime.now(UTC).isoformat(timespec="seconds")
    wanted = {origin.object_id for origin in accepted} | {o.subject_id for o in accepted}
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
        for qid in sorted(wanted - known_genres)
        if qid in labels
    )
    holdable = {node.id for node in nodes} | known_genres
    edges = tuple(
        Edge(
            subject_id=origin.subject_id,
            predicate=PREDICATE_INFLUENCED_BY,
            object_id=origin.object_id,
            source=SOURCE_DBPEDIA,
            source_id=origin.resource,
            retrieved_at=stamp,
            prose_tier="PROSE",
            verification=VERIFICATION_INFOBOX_AUTO,
        )
        for origin in accepted
        if origin.subject_id in holdable
        and origin.object_id in holdable
        and (origin.subject_id, PREDICATE_INFLUENCED_BY, origin.object_id) not in known_edges
    )
    return Artifact(nodes=nodes, edges=edges)


def node_by_id(artifact: Artifact, node_id: str) -> Node | None:
    """One node by id. A linear scan, which is fine for a build-time integrity check over ~1,500 rows."""
    return next((n for n in artifact.nodes if n.id == node_id), None)


def main(argv: list[str] | None = None) -> int:  # pragma: no cover - CLI, hits the network
    """Align, discover, screen, and write the next artifact version.

    Ordered so nothing is written until every live read has succeeded: a partial artifact is worse than
    no artifact, because it looks finished.
    """
    from musical_mycelium.agent.claims import resolve_sources
    from musical_mycelium.ingest import artifact as artifact_io
    from musical_mycelium.ingest import coverage as coverage_io
    from musical_mycelium.ingest import discovery
    from musical_mycelium.ingest.wikidata import artifact_dir
    from musical_mycelium.ingest.wikidata import fetch_entities as wd_entities
    from musical_mycelium.ingest.wikidata import sparql as wd_sparql

    parser = argparse.ArgumentParser(description="Build the DBpedia stylisticOrigin layer.")
    parser.add_argument("--source", default="0.6.0", help="artifact version to extend")
    parser.add_argument("--version", default="0.7.0", help="artifact version to write")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--limit", type=int, default=None, help="screen only the first N candidates (a smoke run)"
    )
    args = parser.parse_args(argv)

    source = Artifact.load(artifact_dir(args.source))
    known = frozenset(n.id for n in source.nodes if n.kind == NODE_KIND_GENRE)
    print(
        f"source v{args.source}: {len(source.nodes)} nodes, {len(source.edges)} edges",
        file=sys.stderr,
    )

    aligned = align(sorted(known))
    seed_resources = {resource for _, resource in aligned}
    print(
        f"  aligned {len({q for q, _ in aligned})}/{len(known)} genres to "
        f"{len(seed_resources)} DBpedia resources",
        file=sys.stderr,
    )

    pairs = fetch_origin_graph()
    reached, growth = closure(seed_resources, pairs)
    print(
        f"  origin graph {len(pairs)} pairs; closure {list(growth)} -> {len(reached)} genres",
        file=sys.stderr,
    )

    # Everything reached that the seed alignment did not already name needs a QID to become a node.
    unknown = sorted(reached - seed_resources)
    back, back_ambiguous = _reverse_align(unknown) if unknown else ({}, ())

    # Resolved from PAIRS with corpus labels in hand, never by inverting a dict. `owl:sameAs` is
    # many-to-many in both directions and each dict silently dropped a row per collision -- which put
    # 46 edges on `rock and roll` that belong to `rock music`. See `resource_to_qid`.
    corpus_labels = {n.id: n.label for n in source.nodes}
    seeded, seeded_ambiguous = resource_to_qid(aligned, corpus_labels)
    r2q = seeded | back
    ambiguous = seeded_ambiguous + back_ambiguous
    print(
        f"  {len(back)}/{len(unknown)} discovered resources carry a Wikidata QID "
        f"({len(unknown) - len(back)} {NO_WIKIDATA_MATCH})",
        file=sys.stderr,
    )
    for resource, qids in ambiguous:
        print(
            f"  AMBIGUOUS, dropped: {resource.rsplit('/', 1)[-1]} owl:sameAs {list(qids)} "
            f"-- no single exact label match, so which node its edges belong to is a guess",
            file=sys.stderr,
        )

    # Every pair *reachable from the corpus*, not every pair that already resolves. Pre-filtering to
    # pairs whose ends both carry a QID would make `to_origins` structurally unable to report an
    # unresolved endpoint, and the unresolved count is the published half of the alignment rate.
    relevant = [(s, o) for s, o in pairs if s in reached]
    origins, unresolved = to_origins(relevant, r2q)
    print(
        f"  {len(origins)} candidate edges in QID space, {len(unresolved)} unresolved",
        file=sys.stderr,
    )

    if args.limit:
        origins = origins[: args.limit]
        print(f"  --limit: screening only {len(origins)}", file=sys.stderr)

    accepted, excluded = screen(origins)
    print(
        f"  prose check: {len(accepted)}/{len(origins)} accepted "
        f"({100 * len(accepted) // max(len(origins), 1)}%), {len(excluded)} excluded",
        file=sys.stderr,
    )

    # The unresolved endpoints are exclusions too, and they must reach the file. They are a different
    # kind of rejection from the prose check's -- the edge was never checked, because there was no node
    # to hang it on -- so they carry their own reason code rather than being folded in.
    excluded = tuple(excluded) + tuple(
        discovery.Exclusion(
            subject_id=subject,
            object_id=obj,
            subject_label=subject.rsplit("/", 1)[-1].replace("_", " "),
            object_label=obj.rsplit("/", 1)[-1].replace("_", " "),
            reason_code=NO_WIKIDATA_MATCH,
            reason="DBpedia resource carries no owl:sameAs to a Wikidata entity, so no node can "
            "carry the revision_id every node in this corpus is required to pin",
        )
        for subject, obj in unresolved
    )

    # Parenthesised deliberately: `-` binds tighter than `|`, so the unbracketed form is
    # `subjects | (objects - known)` and quietly re-adds every already-known subject.
    new_ids = sorted(({o.subject_id for o in accepted} | {o.object_id for o in accepted}) - known)
    facts = wd_entities([q for q in new_ids if q not in known]) if new_ids else {}
    known_edges = frozenset((e.subject_id, e.predicate, e.object_id) for e in source.edges)
    layer = build(
        accepted,
        {q: f.label for q, f in facts.items()},
        {q: f.revision_id for q, f in facts.items()},
        known,
        known_edges=known_edges,
    )
    # Phase 6 step 5. An accepted origin whose triple the corpus ALREADY holds is not a new edge --
    # emitting it would let `merge_axes` overwrite the Wikidata row (step 4's defect). It is a second
    # source agreeing, which is a fact about the existing edge, so it is recorded ON that edge as
    # `corroboration` rather than added beside it or dropped.
    #
    # Note what this is not: corroboration does NOT promote `verification`. A corroborated PROSE_AUTO
    # edge stays PROSE_AUTO. "How strongly one source was checked" and "whether a second source agrees"
    # are different guarantees, and this project has already corrected three files once for blurring
    # them -- see `graph.schema.Edge.corroboration`.
    agreeing = {
        (o.subject_id, PREDICATE_INFLUENCED_BY, o.object_id): o.resource
        for o in accepted
        if (o.subject_id, PREDICATE_INFLUENCED_BY, o.object_id) in known_edges
    }
    source = Artifact(
        nodes=source.nodes,
        edges=tuple(
            replace(edge, corroboration=agreeing[triple])
            if (triple := (edge.subject_id, edge.predicate, edge.object_id)) in agreeing
            else edge
            for edge in source.edges
        ),
    )
    print(
        f"  {len(layer.edges)} new edges, {len(agreeing)} corroborate an existing Wikidata edge "
        f"and are recorded as Edge.corroboration on it",
        file=sys.stderr,
    )

    merged = artifact_io.merge_axes(source, layer)
    added = [n.id for n in layer.nodes]
    if added:
        rows = wd_sparql(coverage_io.coverage_query(added))
        merged = Artifact(
            nodes=coverage_io.enrich(merged, coverage_io.parse_coverage(rows)), edges=merged.edges
        )

    # Stamp the resolved owl:sameAs alignment onto every node it covers, INCLUDING genres the corpus
    # already held. `merge_axes` keeps the first node it sees for an id, so a layer node cannot update
    # an existing one -- and the subjects of DBpedia edges are mostly pre-existing corpus genres. This
    # is what makes `agent.claims.resolve_sources` able to check a DBpedia citation exactly rather
    # than by folding an article title against a label, which was measured and fails on 9% of correct
    # edges. Same enrich-after-merge shape `coverage_io.enrich` already uses.
    qid_to_resource = {qid: resource for resource, qid in r2q.items()}
    merged = Artifact(
        nodes=tuple(
            replace(node, dbpedia_resource=qid_to_resource[node.id])
            if node.id in qid_to_resource
            else node
            for node in merged.nodes
        ),
        edges=merged.edges,
    )
    aligned_nodes = sum(1 for n in merged.nodes if n.dbpedia_resource)
    uncitable = [
        e
        for e in merged.edges
        if e.source == SOURCE_DBPEDIA and not resolve_sources(e, node_by_id(merged, e.subject_id))
    ]
    print(f"  {aligned_nodes} nodes carry a DBpedia alignment", file=sys.stderr)
    if uncitable:
        raise DBpediaError(
            f"{len(uncitable)} DBpedia edges would be uncitable -- the gate would reject every one of "
            f"them UNRESOLVABLE_SOURCE. Refusing to write an artifact whose edges cannot be claimed. "
            f"First: {uncitable[0].subject_id} -> {uncitable[0].object_id}"
        )

    snapshot = {
        node.id: node.revision_id
        for node in merged.nodes
        if node.kind == NODE_KIND_GENRE and node.revision_id
    }

    directory = artifact_dir(args.version)
    directory.mkdir(parents=True, exist_ok=True)
    manifest = artifact_io.write(
        merged,
        directory,
        artifact_version=args.version,
        generator="musical_mycelium.ingest.dbpedia",
        predicate=f"P737 + P136 + dbo:stylisticOrigin ({PREDICATE_INFLUENCED_BY})",
        source=f"{SOURCE_DBPEDIA}+wikidata",
        source_snapshot=snapshot,
        overwrite=args.overwrite,
        verification_record="docs/phases/phase-6-density-and-coverage-IMPLEMENTATION.md",
    )
    from musical_mycelium.ingest.wikidata import write_exclusions

    write_exclusions(tuple(excluded), directory)
    print(
        f"wrote v{args.version}: {manifest.node_count} nodes, {manifest.edge_count} edges\n"
        f"  {manifest.verification_counts}",
        file=sys.stderr,
    )
    return 0


def _reverse_align(
    resources: Sequence[str], runner: Callable[[str], list[dict[str, Any]]] | None = None
) -> tuple[dict[str, str], tuple[tuple[str, tuple[str, ...]], ...]]:
    """DBpedia resource to Wikidata QID, for resources the corpus discovered rather than seeded.

    The mirror of :func:`align`, and it needs its own query because the ``VALUES`` clause binds the
    other variable. The ``STRSTARTS`` filter is on the *Wikidata* side here, which matters: without it
    ``owl:sameAs`` returns YAGO and Freebase identifiers that look nothing like QIDs and would be
    written into the corpus as node ids.

    **Multi-valued in exactly the way :func:`resource_to_qid` documents**, so it returns the ambiguous
    resources rather than letting the last row win. There are no corpus labels to disambiguate against
    here — these resources are being discovered, not matched to something already held — so an
    ambiguous one is simply dropped and reported. Guessing which QID a new node *is* would put the
    guess under every edge that node carries.
    """
    run = runner or sparql
    seen: dict[str, set[str]] = {}
    for start in range(0, len(resources), 100):
        values = " ".join(f"<{uri}>" for uri in resources[start : start + 100])
        rows = run(
            f"""
SELECT DISTINCT ?res ?wd WHERE {{
  VALUES ?res {{ {values} }}
  ?res <{OWL_SAME_AS}> ?wd .
  FILTER(STRSTARTS(STR(?wd), "{WIKIDATA_ENTITY_PREFIX}Q"))
}}
"""
        )
        for row in rows:
            seen.setdefault(row["res"]["value"], set()).add(_qid(row["wd"]["value"]))
        if start + 100 < len(resources):
            time.sleep(1.0)
    resolved = {res: next(iter(qids)) for res, qids in seen.items() if len(qids) == 1}
    ambiguous = tuple(
        sorted((res, tuple(sorted(qids))) for res, qids in seen.items() if len(qids) > 1)
    )
    return resolved, ambiguous


def screen(
    origins: Sequence[Origin],
) -> tuple[tuple[Origin, ...], tuple[Any, ...]]:  # pragma: no cover - network-bound
    """Put DBpedia candidates through the *existing* Wikipedia prose check. Only ``PROSE`` survives.

    This reuses ``ingest.discovery`` and ``ingest.prosecheck`` wholesale rather than reimplementing the
    check, which is the point: two implementations of "does this article assert this" would drift, and
    the whole justification for admitting DBpedia edges at all is that they clear *the same bar*.

    The pure half is :func:`classify`, which is what the tests exercise; this function is the network
    around it.
    """
    from musical_mycelium.ingest import discovery, prosecheck

    subjects = sorted({o.subject_id for o in origins})
    objects = sorted({o.object_id for o in origins})
    entities = prosecheck.fetch_entities(sorted(set(subjects) | set(objects)))
    titles = {
        qid: entities[qid].enwiki_title
        for qid in subjects
        if qid in entities and entities[qid].enwiki_title
    }
    articles = discovery.fetch_articles(
        titles,
        progress=lambda i, n, t: print(f"  [{i}/{n}] {t}", file=sys.stderr),
    )

    return classify(origins, entities, articles)


def classify(
    origins: Sequence[Origin],
    entities: dict[str, Any],
    articles: dict[str, Any],
) -> tuple[tuple[Origin, ...], tuple[Any, ...]]:
    """Apply the prose check to already-fetched articles. Pure, and the whole crawl reduces to this.

    A subject missing from ``articles`` is treated as having no article rather than as an error, the
    same contract ``discovery.screen_candidates`` uses: the caller decides what it could fetch, and
    this only reports what that implied.
    """
    from musical_mycelium.ingest import discovery, prosecheck

    accepted: list[Origin] = []
    excluded: list[Any] = []
    for origin in origins:
        article = articles.get(origin.subject_id, discovery.NO_SITELINK)
        subject = entities.get(origin.subject_id, prosecheck.Entity(qid=origin.subject_id))
        obj = entities.get(origin.object_id, prosecheck.Entity(qid=origin.object_id))
        check = prosecheck.check_edge(
            subject_id=origin.subject_id,
            object_id=origin.object_id,
            subject_label=subject.label,
            object_label=obj.label,
            article=article,
            object_title=obj.enwiki_title,
            object_aliases=obj.aliases,
            subject_aliases=subject.aliases,
        )
        if check.usable:
            accepted.append(origin)
        else:
            excluded.append(discovery.exclusion_for(check))
    return tuple(accepted), tuple(excluded)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
