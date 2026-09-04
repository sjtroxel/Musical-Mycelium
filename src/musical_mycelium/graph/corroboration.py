"""Agreement and disagreement between the corpus's two sources. Added at v0.7.0, phase 6 step 5.

This module is what decision **A1** was waiting for. From v0.1 to v0.6.0 every edge carried exactly one
source, always Wikidata, so ``contested`` was **arithmetically** unreachable rather than merely unbuilt —
nothing could disagree with anything because there was only ever one voice. Phase 6 step 4 added the
second voice. This is where the two are compared.

## Two different facts, and collapsing them is the failure this module exists to avoid

- **Corroboration** — both sources assert the *same* edge in the *same* direction. Recorded per row, as
  ``Edge.corroboration``, because it is a fact about that edge.
- **Contested** — the two sources assert *opposite* directions for the same pair. **A property of a
  PAIR, not of an edge**, which is why it is derived here rather than stamped on a row. Neither edge is
  individually wrong; the disagreement exists only in the relationship between them.

Neither is ``verification``, which says how strongly one source was checked. ``.claude/rules/
grounding-and-claims.md`` had to be corrected once for letting verification read as corroboration; do not
re-introduce the blur from the other direction by letting corroboration read as verification strength.

## The definition that matters: contested needs DIFFERENT sources

*Measured on v0.7.0, and this is why the distinction is load-bearing rather than pedantic.* The corpus
holds **6 reciprocal pairs** — pairs where both ``(A, B)`` and ``(B, A)`` exist. Only **2** are contested:

    western music  <-> New Mexico music    wikidata / dbpedia   <- CONTESTED
    electropop     <-> electroclash        wikidata / dbpedia   <- CONTESTED
    jangle pop     <-> college rock        dbpedia  / dbpedia
    noise rock     <-> post-hardcore       dbpedia  / dbpedia
    tejano music   <-> country music       dbpedia  / dbpedia
    post-rock      <-> shoegaze            wikidata / wikidata

**Defining contested as "a reciprocal pair exists" would overcount by 3x.** A single source asserting
both directions is not two sources disagreeing — it is one source describing mutual influence, which for
genres is often a real claim rather than an error. Reporting that as a dispute between sources would
state something false about where the corpus's information came from.

**``post-rock <-> shoegaze`` predates DBpedia entirely** — it is in v0.5.0, from Wikidata alone, and had
gone unnoticed. So the corpus has always contained a cycle in its influence graph, which also makes
``web/src/graph/layout.ts``'s *"there are no cycles in artifact v0.5.0 — measured, not assumed"* false as
written. Corrected at this step; the layout was already defensive about cycles, so nothing rendered
wrongly.
"""

from __future__ import annotations

from dataclasses import dataclass

from musical_mycelium.graph.schema import PREDICATE_INFLUENCED_BY, Artifact, Edge


@dataclass(frozen=True, slots=True)
class ContestedPair:
    """Two sources asserting opposite directions of influence for the same pair of nodes.

    ``a`` and ``b`` are ordered by node id so the pair has one canonical form and cannot be reported
    twice, once from each end. ``a_from_b`` is the edge saying *a came out of b*.
    """

    a: str
    b: str
    a_from_b: Edge
    b_from_a: Edge

    @property
    def sources(self) -> tuple[str, str]:
        return (self.a_from_b.source, self.b_from_a.source)


def reciprocal_pairs(artifact: Artifact) -> tuple[tuple[Edge, Edge], ...]:
    """Every pair of influence edges pointing both ways between the same two nodes.

    The superset of :func:`contested_pairs`, returned separately because the difference between the two
    is the whole finding: 6 of these exist at v0.7.0 and only 2 are contested. A caller that wants
    "reciprocal" must not get it by asking for "contested", and vice versa.
    """
    edges = {
        (e.subject_id, e.object_id): e
        for e in artifact.edges
        if e.predicate == PREDICATE_INFLUENCED_BY
    }
    out: list[tuple[Edge, Edge]] = []
    for (subject, obj), edge in sorted(edges.items()):
        # `subject < obj` keeps one representative per pair rather than reporting each twice.
        if subject < obj and (obj, subject) in edges:
            out.append((edge, edges[(obj, subject)]))
    return tuple(out)


def contested_pairs(artifact: Artifact) -> tuple[ContestedPair, ...]:
    """Reciprocal pairs whose two edges come from **different** sources.

    The source comparison is the entire definition. Without it this returns 6 pairs at v0.7.0 where 2
    are contested, and the other 4 are one source describing mutual influence — a different fact, stated
    by the same shape of data.
    """
    return tuple(
        ContestedPair(
            a=forward.subject_id, b=reverse.subject_id, a_from_b=forward, b_from_a=reverse
        )
        for forward, reverse in reciprocal_pairs(artifact)
        if forward.source != reverse.source
    )


def corroborated_edges(artifact: Artifact) -> tuple[Edge, ...]:
    """Edges a second source also asserts, in the same direction."""
    return tuple(e for e in artifact.edges if e.corroboration)


def summary(artifact: Artifact) -> dict[str, int]:
    """Counts for the manifest and the coverage panel.

    ``reciprocal`` and ``contested`` are both reported, never one alone. A reader given only the
    contested count cannot tell whether the corpus has no mutual-influence pairs or three of them, and
    the gap between the two numbers is exactly the thing this module exists to keep visible.
    """
    influence = [e for e in artifact.edges if e.predicate == PREDICATE_INFLUENCED_BY]
    return {
        "influence_edges": len(influence),
        "corroborated": len(corroborated_edges(artifact)),
        "single_source": sum(1 for e in influence if not e.corroboration),
        "reciprocal_pairs": len(reciprocal_pairs(artifact)),
        "contested_pairs": len(contested_pairs(artifact)),
    }
