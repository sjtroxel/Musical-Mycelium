"""The ``Claim`` model and the deterministic gate. The spine of the project.

**Claims first, prose second — never side by side.** The agent proposes claims, this gate approves or
rejects each one against the pinned artifact, and prose is generated from the approved set *only*. The
original design had the model emit claims alongside prose, and that leaked: prose could assert an edge
that never became a claim, so groundedness would read 100% while the text hallucinated
(``.claude/rules/grounding-and-claims.md``).

**The model never supplies a citation.** That is why there are two types here rather than one. A
``ClaimProposal`` is what the model may emit and it carries *no sources* — just subject, predicate and
object. A ``Claim`` carries ``source_ids``, and the only thing that can produce one is ``gate()``, which
reads the sources off the artifact edge. A model that cannot name a source cannot fabricate one, and the
type system rather than a code review is what enforces it.

**The gate is deterministic code, not a model call.** The model proposes; the gate decides. Every check
below is a dictionary lookup or a string comparison, so it is free, reproducible, and unit-testable —
which is also what makes the Tier 1 eval metrics possible at all.

Not here, and deliberately: **contested** claims. ``.claude/rules/grounding-and-claims.md`` makes
contested a first-class state rather than an error, and it will need a third outcome alongside approved
and rejected. Nothing in the v0.1 corpus can mark an edge as disputed, so adding a state nothing can
produce would be speculative structure. It arrives with the data that justifies it, in phase 2 or 6.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import StrEnum

from musical_mycelium.graph.schema import PREDICATE_INFLUENCED_BY, SOURCE_WIKIDATA, Edge
from musical_mycelium.graph.store import Direction, GraphStore

#: Predicates a claim is allowed to assert at v0.1. P279 is absent from the artifact entirely, so this is
#: a second lock on the same door: even a corpus that later carries ``subclass_of`` cannot have it
#: narrated as derivation without someone editing this line on purpose.
ALLOWED_PREDICATES = frozenset({PREDICATE_INFLUENCED_BY})

_WIKIDATA_STATEMENT_PREFIX = "http://www.wikidata.org/entity/statement/"


class RejectionReason(StrEnum):
    """Why the gate refused. Reported, never swallowed — the rejections are the evidence the gate ran."""

    UNKNOWN_SUBJECT = "unknown_subject"
    UNKNOWN_OBJECT = "unknown_object"
    UNSUPPORTED_PREDICATE = "unsupported_predicate"
    CROSS_AXIS = "cross_axis"
    NOT_IN_GRAPH = "not_in_graph"
    UNRESOLVABLE_SOURCE = "unresolvable_source"
    DUPLICATE = "duplicate"


@dataclass(frozen=True, slots=True)
class Span:
    """A half-open character range in the emitted prose that a claim underwrites."""

    start: int
    end: int

    def __post_init__(self) -> None:
        if self.start < 0 or self.end < self.start:
            raise ValueError(f"invalid span [{self.start}, {self.end})")


@dataclass(frozen=True, slots=True)
class ClaimProposal:
    """What the model is allowed to emit. Note what is missing: sources, and any prose."""

    subject_id: str
    predicate: str
    object_id: str


@dataclass(frozen=True, slots=True)
class Claim:
    """An approved claim. ``SPEC.md`` 7 fixes this shape.

    ``source_ids`` are copied off the artifact edge by the gate, never accepted from a caller that got
    them from a model. ``span`` is empty until synthesis attaches it, because at gate time there is no
    prose yet — that ordering *is* the claims-first rule.
    """

    subject_id: str
    predicate: str
    object_id: str
    source_ids: tuple[str, ...]
    span: Span | None = None

    def __post_init__(self) -> None:
        if not self.source_ids:
            raise ValueError(
                f"claim {self.subject_id} -{self.predicate}-> {self.object_id} has no sources; "
                f"an uncited claim is a refusal, not a claim"
            )

    def with_span(self, start: int, end: int) -> Claim:
        """Return a copy anchored to the prose that asserts it. Used by synthesis, not by the gate."""
        return replace(self, span=Span(start, end))

    @property
    def triple(self) -> tuple[str, str, str]:
        return (self.subject_id, self.predicate, self.object_id)


@dataclass(frozen=True, slots=True)
class Rejection:
    proposal: ClaimProposal
    reason: RejectionReason
    detail: str = ""


@dataclass(frozen=True, slots=True)
class GateResult:
    """Both halves, always. A gate that reported only approvals would hide the refusals, and refusal
    accuracy is a headline metric reported as a pair (``.claude/rules/grounding-and-claims.md``)."""

    approved: tuple[Claim, ...]
    rejected: tuple[Rejection, ...]

    @property
    def refused_everything(self) -> bool:
        """True when proposals were made and none survived. Not an error — often the correct answer —
        but the thing a caller must be able to notice in order to say so honestly."""
        return bool(self.rejected) and not self.approved


def resolve_sources(edge: Edge) -> tuple[str, ...]:
    """The citations for an edge, if they resolve. Empty tuple when they do not.

    "Resolves" is deliberately checkable rather than aspirational. A Wikidata statement URI encodes the
    QID of the entity the statement belongs to, so a citation on an ``influenced_by`` edge must name that
    edge's **subject**. A source id that points at some other entity is not a citation for this claim
    even if it is a perfectly valid URI, and that is exactly the failure a plausible-looking fabrication
    produces. Verified against all 21 v0.1 edges on 2026-08-02.
    """
    if edge.source != SOURCE_WIKIDATA:
        return ()
    if not edge.source_id.startswith(_WIKIDATA_STATEMENT_PREFIX):
        return ()
    entity = edge.source_id.removeprefix(_WIKIDATA_STATEMENT_PREFIX).split("-", 1)[0]
    if entity != edge.subject_id:
        return ()
    return (edge.source_id,)


def gate(proposals: list[ClaimProposal], store: GraphStore) -> GateResult:
    """Approve each proposal that the pinned artifact actually supports. Reject everything else.

    A proposal passes only if all five hold:

    1. the predicate is one v0.1 permits,
    2. both endpoints are nodes in the artifact,
    3. both endpoints sit on the **same axis** — genre-to-genre or artist-to-artist, never across,
    4. the edge exists in the artifact in the stated direction, and
    5. that edge's sources resolve.

    Order matters for the reported reason — the first failure wins, so "I made up a genre" is reported as
    an unknown node rather than as a missing edge, and a cross-axis proposal is reported as cross-axis
    rather than as a merely absent edge.
    """
    approved: list[Claim] = []
    rejected: list[Rejection] = []
    seen: set[tuple[str, str, str]] = set()

    for proposal in proposals:
        triple = (proposal.subject_id, proposal.predicate, proposal.object_id)

        if triple in seen:
            rejected.append(Rejection(proposal, RejectionReason.DUPLICATE))
            continue
        seen.add(triple)

        if proposal.predicate not in ALLOWED_PREDICATES:
            rejected.append(
                Rejection(
                    proposal,
                    RejectionReason.UNSUPPORTED_PREDICATE,
                    f"{proposal.predicate!r} is not one of {sorted(ALLOWED_PREDICATES)}",
                )
            )
            continue

        subject = store.get_node(proposal.subject_id)
        if subject is None:
            rejected.append(
                Rejection(proposal, RejectionReason.UNKNOWN_SUBJECT, proposal.subject_id)
            )
            continue

        obj = store.get_node(proposal.object_id)
        if obj is None:
            rejected.append(Rejection(proposal, RejectionReason.UNKNOWN_OBJECT, proposal.object_id))
            continue

        # Invariant 3, enforced rather than assumed. The ingest bounds each axis separately so a
        # cross-axis edge should never reach the artifact at all; this is the second lock on that door,
        # the same belt-and-braces as ALLOWED_PREDICATES against P279. A chain that steps from a genre
        # to an artist and back reads as one continuous line of influence, and it is not one.
        if subject.kind != obj.kind:
            rejected.append(
                Rejection(
                    proposal,
                    RejectionReason.CROSS_AXIS,
                    f"{proposal.subject_id} is a {subject.kind}, "
                    f"{proposal.object_id} is a {obj.kind}",
                )
            )
            continue

        edge = _find_edge(store, proposal)
        if edge is None:
            rejected.append(
                Rejection(
                    proposal,
                    RejectionReason.NOT_IN_GRAPH,
                    f"no {proposal.predicate} edge from {proposal.subject_id} to {proposal.object_id}",
                )
            )
            continue

        sources = resolve_sources(edge)
        if not sources:
            rejected.append(
                Rejection(
                    proposal, RejectionReason.UNRESOLVABLE_SOURCE, f"source_id={edge.source_id!r}"
                )
            )
            continue

        approved.append(
            Claim(
                subject_id=proposal.subject_id,
                predicate=proposal.predicate,
                object_id=proposal.object_id,
                source_ids=sources,
            )
        )

    return GateResult(approved=tuple(approved), rejected=tuple(rejected))


def _find_edge(store: GraphStore, proposal: ClaimProposal) -> Edge | None:
    for edge in store.neighbors(proposal.subject_id, Direction.INFLUENCED_BY):
        if edge.object_id == proposal.object_id and edge.predicate == proposal.predicate:
            return edge
    return None
