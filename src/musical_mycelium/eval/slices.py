"""Slicing — the thing that stops a healthy aggregate from hiding a failing corner.

``.claude/rules/evals.md``: *"Slice every result by era, region, density, and query type. The corpus skew
is documented; an aggregate that looks healthy while the sparse and non-Western slices fail is the default
outcome without slicing."*

Two rules do the work here, and both exist because the alternative is a number that flatters:

1. **A slice with fewer than five items reports its count, not a percentage.** A 100% on two items is not
   a 100%, and printing it as one teaches the reader something false.
2. **The unknown bucket is a slice, not a dropped row.** ``Node.inception_year`` is optional and 28 of 169
   genres had none at v0.5.0; ``graph.coverage`` already reports ``without_inception`` *before* the era
   histogram for exactly this reason. Dropping the undated makes the dated eras look more complete than
   they are, so every dimension here has an explicit bucket for "we do not know".

Nothing in this module sets a threshold. Phase 3 records baselines; phase 4 sets gates.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass

from musical_mycelium.eval.metrics import Rate
from musical_mycelium.graph.coverage import ANGLOPHONE_CORE, PLACE_TO_COUNTRY, era_of
from musical_mycelium.graph.schema import (
    INFLUENCE_ONLY,
    PREDICATE_PLAYS_GENRE,
    PREDICATES,
    SOURCE_DBPEDIA,
    SOURCE_WIKIDATA,
    Node,
)
from musical_mycelium.graph.store import Direction, GraphStore

#: Below this, a slice reports its raw count instead of a percentage. Five is the figure named in the
#: phase plan; it is a reporting convention, **not a threshold** — nothing passes or fails on it.
SPARSE_SLICE = 5

#: The bucket for items whose dimension cannot be determined. Named once so every dimension spells it the
#: same way, and so a reader can tell "we looked and there were none" from "we could not tell".
UNKNOWN = "unknown"

#: Era bucket for a node Wikidata gives no inception year. **Distinct from ``UNKNOWN``**, which means the
#: node itself was never resolved: an undated node is a real node with a real gap, and collapsing the two
#: would hide which of the two problems the corpus has.
UNDATED = "undated"


@dataclass(frozen=True, slots=True)
class SliceReport:
    """One dimension's worth of results, with the sparse ones marked rather than averaged away."""

    dimension: str
    rates: Mapping[str, Rate]

    def is_sparse(self, name: str) -> bool:
        return self.rates[name].denominator < SPARSE_SLICE

    def render(self) -> list[str]:
        """One line per slice. **Sparse slices render as counts**, so a reader cannot mistake 2/2 for a
        rate. Ordered by descending denominator so the slices carrying real weight come first."""
        lines = []
        for name, rate in sorted(self.rates.items(), key=lambda kv: (-kv[1].denominator, kv[0])):
            if rate.denominator == 0:
                lines.append(f"  {name}: no items")
            elif self.is_sparse(name):
                lines.append(f"  {name}: {rate.numerator} of {rate.denominator} (n<{SPARSE_SLICE})")
            else:
                lines.append(f"  {name}: {rate}")
        return [f"{self.dimension}:", *lines]

    def __str__(self) -> str:
        return "\n".join(self.render())


def slice_rates[T](
    dimension: str,
    items: Iterable[T],
    key_of: Callable[[T], str],
    hit_of: Callable[[T], bool],
) -> SliceReport:
    """Bucket ``items`` by ``key_of`` and score each bucket by ``hit_of``.

    Generic on purpose: the dimensions differ but the reporting rule must not, and a per-dimension
    aggregator is four chances to forget the sparse rule.
    """
    hits: dict[str, int] = {}
    totals: dict[str, int] = {}
    for item in items:
        key = key_of(item)
        totals[key] = totals.get(key, 0) + 1
        hits[key] = hits.get(key, 0) + (1 if hit_of(item) else 0)

    return SliceReport(
        dimension=dimension,
        rates={key: Rate(numerator=hits[key], denominator=total) for key, total in totals.items()},
    )


# --- the four dimensions ---------------------------------------------------------------------------


def era_slice(node: Node | None) -> str:
    """Which era a node belongs to, or why it has none.

    ``inception_precision`` is **carried but not used to move a node between buckets.** The eras are wide,
    so decade precision lands in the right one anyway; the two century-precision genres are named in the
    baseline record rather than silently rebucketed, because inventing a year Wikidata does not state is
    the "grounded slides into correct" failure in miniature.
    """
    if node is None:
        return UNKNOWN
    if node.inception_year is None:
        return UNDATED
    return era_of(node.inception_year)


def region_slice(node: Node | None) -> str:
    """Anglophone core or not, at the coarsest honest resolution.

    **``unstated`` is not ``elsewhere``.** A node with no P495 has an unrecorded country, not a non-US/UK
    one, and folding the two together would let missing data masquerade as coverage breadth — which is
    the exact direction this project must never round in.

    Place labels are normalised through ``PLACE_TO_COUNTRY`` first: that map exists because ``Brixton``
    read as "names no UK" and put the corpus-coverage figure out by one.
    """
    if node is None:
        return UNKNOWN
    if not node.countries:
        return "unstated"
    countries = {PLACE_TO_COUNTRY.get(label, label) for label in node.countries}
    return "anglophone_core" if ANGLOPHONE_CORE & countries else "elsewhere"


def density_slice(node: Node | None, store: GraphStore) -> str:
    """How much sourced history the graph holds about this node, by out-degree.

    ``isolated`` is the interesting bucket and the reason this dimension exists: 542 of 973 nodes have
    zero outgoing edges, so a system that looks accurate overall may simply be answering the dense
    questions and refusing the rest. That is a legitimate outcome and it has to be visible, not averaged
    in with the well-connected nodes.
    """
    if node is None:
        return UNKNOWN
    degree = len(store.neighbors(node.id, Direction.INFLUENCED_BY))
    if degree == 0:
        return "isolated"
    if degree <= 2:
        return "sparse"
    return "connected"


def source_slice(node: Node | None, store: GraphStore) -> str:
    """Which source the graph's account of this node's origins actually comes from.

    **The dimension phase 6 made possible and phase 6 therefore has to be sliced by.** Until v0.7.0 every
    edge was Wikidata, so this question had one answer and was not worth asking. The corpus is now 949
    Wikidata influence edges against 1,336 from DBpedia, and those two halves were screened by the same
    prose check but reached it by different routes -- a Wikidata edge was asserted as a statement and then
    confirmed by an article, a DBpedia edge was extracted from that same article's infobox and confirmed
    by its prose. **An aggregate that looks healthy while the dbpedia_only slice fails is the default
    outcome without this**, and it is the specific risk of adding a second source at 1.4x the size of the
    first.

    Read on the node's INFLUENCED_BY edges, because that is what an origins answer is built from.
    ``none`` is not a gap in the slicing -- it is the isolated nodes, which have no origins at all and are
    already the interesting bucket in :func:`density_slice`.
    """
    if node is None:
        return UNKNOWN
    sources = {edge.source for edge in store.neighbors(node.id, Direction.INFLUENCED_BY)}
    if not sources:
        return "none"
    if sources == {SOURCE_WIKIDATA}:
        return "wikidata_only"
    if sources == {SOURCE_DBPEDIA}:
        return "dbpedia_only"
    return "both"


def predicate_slice(node: Node | None, store: GraphStore) -> str:
    """Whether the graph knows this node through influence, through membership, or both.

    The second dimension phase 6 created. ``plays_genre`` is structural and **can never be narrated** --
    it is absent from ``agent.claims.ALLOWED_PREDICATES`` -- so a genre the corpus knows *only* through
    the artists who play it must always refuse, however many edges touch it. That is correct behaviour
    and it looks identical in an aggregate to a system that refuses because it is broken.

    Slicing by it separates the two. ``membership_only`` is the bucket to watch: those nodes are
    well-connected by every structural measure and narratable by none of them, which is exactly the
    "membership reads as derivation" confusion decision C1 exists to prevent, seen from the metrics side.
    """
    if node is None:
        return UNKNOWN
    influence = bool(store.neighbors(node.id, Direction.INFLUENCED_BY, predicates=INFLUENCE_ONLY))
    membership = any(
        edge.predicate == PREDICATE_PLAYS_GENRE
        for direction in Direction
        for edge in store.neighbors(node.id, direction, predicates=PREDICATES)
    )
    if influence and membership:
        return "both"
    if influence:
        return "influence_only"
    if membership:
        return "membership_only"
    return "neither"


def query_kind_slice(query_kind: str) -> str:
    """Straight through. ``Plan.query_kind`` already degrades to ``unknown`` rather than going absent, so
    every run is sliceable by construction and this needs no fallback of its own."""
    return query_kind or UNKNOWN


def dimensions_of(node: Node | None, store: GraphStore, query_kind: str) -> Mapping[str, str]:
    """All six keys for one item, so a caller cannot slice by five and forget the sixth.

    **Four until v0.7.1.** ``source`` and ``predicate`` were added at phase 6 step 7, because DoD #5 is
    re-judged rather than carried: met at v0.5.0 is not met at v0.7.1, and a corpus that grew a second
    source and a second predicate has two axes the slicer had never seen.
    """
    return {
        "era": era_slice(node),
        "region": region_slice(node),
        "density": density_slice(node, store),
        "source": source_slice(node, store),
        "predicate": predicate_slice(node, store),
        "query_kind": query_kind_slice(query_kind),
    }


def render_all(reports: Sequence[SliceReport]) -> str:
    return "\n".join("\n".join(report.render()) for report in reports)
