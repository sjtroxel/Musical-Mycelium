"""Gate tests.

The gate is the one component whose failure mode is silent. A broken store throws; a broken gate just
approves something, and the answer still streams, still carries citations, and is wrong. So these tests
lean hard on the rejection paths — the ones that only fire when the model tries something it should not.
"""

from __future__ import annotations

import pytest

from musical_mycelium.agent import claims as claims_module
from musical_mycelium.agent.claims import (
    ALLOWED_PREDICATES,
    UNREACHABLE,
    Claim,
    ClaimProposal,
    GateResult,
    RejectionReason,
    Span,
    gate,
    resolve_sources,
)
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import (
    NODE_KIND_ARTIST,
    NODE_KIND_GENRE,
    VERIFICATION_HAND,
    VERIFICATION_LEVELS,
    VERIFICATION_PROSE_AUTO,
    Artifact,
    Edge,
    Node,
)
from musical_mycelium.graph.store import Direction

BLUES_ROCK, BLUES = "Q193355", "Q9759"
ACID_JAZZ, JAZZ = "Q221772", "Q8341"
HEAVY_METAL = "Q38848"
INFLUENCED_BY = "influenced_by"

#: Test claims state a verification level explicitly, the same rule every construction site obeys.
HAND = VERIFICATION_HAND


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


def proposal(
    subject: str = BLUES_ROCK, obj: str = BLUES, predicate: str = INFLUENCED_BY
) -> ClaimProposal:
    return ClaimProposal(subject_id=subject, predicate=predicate, object_id=obj)


# --- the shape of the contract -----------------------------------------------------------------


def test_a_proposal_cannot_carry_sources() -> None:
    """The structural half of "the model never supplies a citation". If ``ClaimProposal`` ever grows a
    ``source_ids`` field, the fabrication path is open again and no test below would notice."""
    assert not hasattr(ClaimProposal(BLUES_ROCK, INFLUENCED_BY, BLUES), "source_ids")


def test_an_uncited_claim_cannot_be_constructed() -> None:
    with pytest.raises(ValueError, match="no sources"):
        Claim(
            subject_id=BLUES_ROCK,
            predicate=INFLUENCED_BY,
            object_id=BLUES,
            source_ids=(),
            verification=HAND,
        )


def test_a_claim_has_no_span_until_synthesis_attaches_one() -> None:
    """Claims first, prose second. At gate time there is no prose, so there is nothing to point at."""
    claim = Claim(BLUES_ROCK, INFLUENCED_BY, BLUES, ("stmt/1",), HAND)
    assert claim.span is None
    anchored = claim.with_span(0, 12)
    assert anchored.span == Span(0, 12)
    assert claim.span is None, "with_span must not mutate the original"


def test_span_rejects_a_backwards_range() -> None:
    with pytest.raises(ValueError, match="invalid span"):
        Span(10, 4)


def test_only_the_influence_predicate_is_allowed() -> None:
    """P279 is absent from the artifact, so this is a second lock on the same door."""
    assert {INFLUENCED_BY} == ALLOWED_PREDICATES


# --- approval ---------------------------------------------------------------------------------


def test_a_real_edge_is_approved_and_gains_its_sources(store: InMemoryGraphStore) -> None:
    result = gate([proposal()], store)
    assert len(result.approved) == 1
    claim = result.approved[0]
    assert claim.triple == (BLUES_ROCK, INFLUENCED_BY, BLUES)
    assert claim.source_ids
    assert all(s.startswith("http://www.wikidata.org/entity/statement/") for s in claim.source_ids)
    assert not result.rejected


def test_the_gate_supplies_sources_the_proposal_never_had(store: InMemoryGraphStore) -> None:
    """The citation is read off the artifact, not accepted from the caller. This is the test that would
    fail first if someone ever let a model hand in its own ``source_ids``."""
    edge = next(e for e in store.neighbors(BLUES_ROCK) if e.object_id == BLUES)
    assert gate([proposal()], store).approved[0].source_ids == (edge.source_id,)


def test_all_four_acid_jazz_parents_are_approved(store: InMemoryGraphStore) -> None:
    proposals = [proposal(ACID_JAZZ, obj) for obj in (JAZZ, "Q164444", "Q131272", "Q11401")]
    result = gate(proposals, store)
    assert len(result.approved) == 4
    assert not result.rejected


# --- rejection --------------------------------------------------------------------------------


def test_a_fabricated_edge_between_two_real_genres_is_rejected(store: InMemoryGraphStore) -> None:
    """The most likely hallucination by far: two genres that exist, a relationship that does not.
    ``blues <- heavy metal`` is historically backwards and is not in the artifact."""
    result = gate([proposal(BLUES, HEAVY_METAL)], store)
    assert not result.approved
    assert result.rejected[0].reason is RejectionReason.NOT_IN_GRAPH


def test_a_reversed_edge_is_rejected(store: InMemoryGraphStore) -> None:
    """``blues rock <- blues`` is real; ``blues <- blues rock`` is the same row read backwards and is a
    different, false claim. A gate that matched edges without direction would approve both."""
    assert (
        gate([proposal(BLUES, BLUES_ROCK)], store).rejected[0].reason
        is RejectionReason.NOT_IN_GRAPH
    )


def test_an_invented_genre_is_rejected_as_an_unknown_node(store: InMemoryGraphStore) -> None:
    assert (
        gate([proposal("Q99999999", BLUES)], store).rejected[0].reason
        is RejectionReason.UNKNOWN_SUBJECT
    )
    assert gate([proposal(BLUES_ROCK, "Q99999999")], store).rejected[0].reason is (
        RejectionReason.UNKNOWN_OBJECT
    )


def test_griot_is_rejected_because_it_is_not_in_the_artifact(store: InMemoryGraphStore) -> None:
    """Q511054 is a real Wikidata entity and not a music genre. A gate that only checked "is this a
    plausible QID" would let it through."""
    result = gate([proposal("Q511054", BLUES)], store)
    assert result.rejected[0].reason is RejectionReason.UNKNOWN_SUBJECT


def test_a_taxonomic_predicate_is_rejected(store: InMemoryGraphStore) -> None:
    """``subclass_of`` narrated as derivation is the P279 error the whole project rests on avoiding."""
    result = gate([proposal(BLUES_ROCK, BLUES, "subclass_of")], store)
    assert result.rejected[0].reason is RejectionReason.UNSUPPORTED_PREDICATE


def test_a_duplicate_proposal_is_approved_once(store: InMemoryGraphStore) -> None:
    """Otherwise a loop that proposes the same edge twice inflates the claim count and every ratio
    computed from it."""
    result = gate([proposal(), proposal()], store)
    assert len(result.approved) == 1
    assert result.rejected[0].reason is RejectionReason.DUPLICATE


def test_the_first_failure_is_the_reported_reason(store: InMemoryGraphStore) -> None:
    """An invented subject with an invented predicate reports the predicate, because that check runs
    first. Deterministic reason ordering keeps the rejection log stable enough to diff."""
    result = gate([proposal("Q99999999", "Q88888888", "subclass_of")], store)
    assert result.rejected[0].reason is RejectionReason.UNSUPPORTED_PREDICATE


# --- source resolution ------------------------------------------------------------------------


def synthetic_store(
    source_id: str,
    source: str = "wikidata",
    *,
    subject_kind: str = NODE_KIND_GENRE,
    object_kind: str = NODE_KIND_GENRE,
) -> InMemoryGraphStore:
    """One real-looking edge whose citation is under test."""
    when = "2026-01-01T00:00:00+00:00"
    nodes = (
        Node(
            id="Q1",
            label="alpha",
            source="wikidata",
            source_id="Q1",
            retrieved_at=when,
            kind=subject_kind,
        ),
        Node(
            id="Q2",
            label="beta",
            source="wikidata",
            source_id="Q2",
            retrieved_at=when,
            kind=object_kind,
        ),
    )
    edge = Edge(
        subject_id="Q1",
        predicate=INFLUENCED_BY,
        object_id="Q2",
        source=source,
        source_id=source_id,
        retrieved_at=when,
        prose_tier="PROSE",
        verification=VERIFICATION_PROSE_AUTO,
    )
    return InMemoryGraphStore(Artifact(nodes=nodes, edges=(edge,)))


def test_a_real_edge_with_an_unresolvable_source_is_rejected() -> None:
    """Required by the IMPLEMENTATION doc 8. The edge is genuinely present; the citation is not usable,
    so the claim is refused rather than narrated with a broken reference."""
    store = synthetic_store("not-a-url")
    result = gate([proposal("Q1", "Q2")], store)
    assert not result.approved
    assert result.rejected[0].reason is RejectionReason.UNRESOLVABLE_SOURCE


def test_a_citation_pointing_at_the_wrong_entity_is_rejected() -> None:
    """A well-formed statement URI that belongs to some *other* subject. This is what a plausible
    fabricated citation looks like, and a prefix check alone would accept it."""
    store = synthetic_store("http://www.wikidata.org/entity/statement/Q7-DEADBEEF")
    assert (
        gate([proposal("Q1", "Q2")], store).rejected[0].reason
        is RejectionReason.UNRESOLVABLE_SOURCE
    )


def test_a_citation_naming_its_own_subject_resolves() -> None:
    store = synthetic_store("http://www.wikidata.org/entity/statement/Q1-DEADBEEF")
    assert len(gate([proposal("Q1", "Q2")], store).approved) == 1


# --- the axis boundary (invariant 3) ----------------------------------------------------------


GOOD_CITATION = "http://www.wikidata.org/entity/statement/Q1-DEADBEEF"


def test_a_cross_axis_claim_is_refused_even_though_the_edge_is_really_there() -> None:
    """The load-bearing case. This edge exists in the artifact *and* its citation resolves, so every
    other check the gate makes would pass it. It is refused purely because a genre and an artist are
    not the same kind of assertion and must never be narrated as one continuous line of influence.

    The ingest bounds each axis separately, so this artifact should be impossible. That is the point:
    the gate is a second, independent lock, the same belt-and-braces as ALLOWED_PREDICATES against
    P279. A corpus bug must not become a narration bug."""
    store = synthetic_store(GOOD_CITATION, object_kind=NODE_KIND_ARTIST)
    result = gate([proposal("Q1", "Q2")], store)
    assert not result.approved
    assert result.rejected[0].reason is RejectionReason.CROSS_AXIS


def test_cross_axis_is_reported_as_cross_axis_not_as_a_missing_edge() -> None:
    """Reason ordering. The check sits after both nodes resolve and before the edge lookup, so a
    cross-axis proposal names the real problem instead of the misleading "no such edge"."""
    store = synthetic_store("not-a-url", subject_kind=NODE_KIND_ARTIST)
    rejection = gate([proposal("Q1", "Q2")], store).rejected[0]
    assert rejection.reason is RejectionReason.CROSS_AXIS
    # ...and it says which side is which, because "cross axis" alone is not diagnosable.
    assert "artist" in rejection.detail and "genre" in rejection.detail


def test_artist_to_artist_is_the_same_axis_and_passes() -> None:
    """The rule is same-axis, not genre-only. Once the artist axis is ingested, an artist-to-artist
    edge is a perfectly ordinary claim and the gate must not treat 'not a genre' as disqualifying."""
    store = synthetic_store(
        GOOD_CITATION, subject_kind=NODE_KIND_ARTIST, object_kind=NODE_KIND_ARTIST
    )
    assert len(gate([proposal("Q1", "Q2")], store).approved) == 1


def test_a_source_from_an_unknown_provider_does_not_resolve() -> None:
    store = synthetic_store("http://www.wikidata.org/entity/statement/Q1-DEADBEEF", source="vibes")
    assert (
        gate([proposal("Q1", "Q2")], store).rejected[0].reason
        is RejectionReason.UNRESOLVABLE_SOURCE
    )


def test_the_qid_in_a_citation_is_matched_without_regard_to_case() -> None:
    """Wikidata writes the entity in a statement URI in either case; v0.6.0 inherited 21 lowercase ones.

    Both halves are asserted together on purpose. Folding case is only safe because a QID is ``Q``
    followed by digits, so the fold cannot make two *different* entities compare equal — and the second
    assertion is what would fail if someone later widened this into a general fuzzy match.
    """
    store = synthetic_store("http://www.wikidata.org/entity/statement/q1-DEADBEEF")
    assert len(gate([proposal("Q1", "Q2")], store).approved) == 1

    wrong_entity = synthetic_store("http://www.wikidata.org/entity/statement/Q999-DEADBEEF")
    assert (
        gate([proposal("Q1", "Q2")], wrong_entity).rejected[0].reason
        is RejectionReason.UNRESOLVABLE_SOURCE
    )


def test_resolve_sources_on_every_pinned_edge() -> None:
    """Every edge the ingestion wrote must be citable. If this fails the artifact is the problem, not
    the gate — so it reads the artifact directly rather than going through the store."""
    artifact = Artifact.load(artifact_directory())
    for edge in artifact.edges:
        assert resolve_sources(edge) == (edge.source_id,), f"uncitable edge: {edge.subject_id}"


# --- reporting --------------------------------------------------------------------------------


def test_refusing_everything_is_visible_not_silent(store: InMemoryGraphStore) -> None:
    """A gate that refused all of it and a gate that was never asked look identical unless someone
    reports the difference. Refusal is correct behaviour; invisible refusal is not."""
    all_bad = gate([proposal(BLUES, HEAVY_METAL), proposal(BLUES, BLUES_ROCK)], store)
    assert all_bad.refused_everything

    nothing_asked = gate([], store)
    assert not nothing_asked.refused_everything
    assert nothing_asked == GateResult(approved=(), rejected=())


def test_a_mixed_batch_keeps_both_halves(store: InMemoryGraphStore) -> None:
    result = gate([proposal(), proposal(BLUES, HEAVY_METAL), proposal(ACID_JAZZ, JAZZ)], store)
    assert len(result.approved) == 2
    assert len(result.rejected) == 1
    assert not result.refused_everything


# --- step 4: verification, copied not supplied ------------------------------------------------------


def test_the_gate_copies_verification_off_the_edge(store: InMemoryGraphStore) -> None:
    """The same rule ``source_ids`` obeys, and for the same reason: the model may not supply it, so the
    model cannot inflate it. A claim's verification is whatever the artifact edge says and nothing else.
    """
    proposal = ClaimProposal(BLUES_ROCK, INFLUENCED_BY, BLUES)
    approved = gate([proposal], store).approved
    assert len(approved) == 1

    edge = next(
        e
        for e in store.neighbors(BLUES_ROCK, Direction.INFLUENCED_BY)
        if e.object_id == BLUES and e.predicate == INFLUENCED_BY
    )
    assert approved[0].verification == edge.verification


def test_a_proposal_cannot_carry_verification() -> None:
    """The structural half. If ``ClaimProposal`` ever grows this field, a model can assert that its own
    claim was hand-verified, and "grounded" quietly becomes whatever the model says it is."""
    assert not hasattr(ClaimProposal(BLUES_ROCK, INFLUENCED_BY, BLUES), "verification")


def test_a_claim_cannot_invent_a_verification_level() -> None:
    with pytest.raises(ValueError, match="expected one of"):
        Claim(BLUES_ROCK, INFLUENCED_BY, BLUES, ("stmt/1",), "TRIPLE_CHECKED")


def test_every_approved_claim_carries_a_real_level(store: InMemoryGraphStore) -> None:
    """Across a whole fan-out, not one claim. The level must always be one the schema defines, because
    a client rendering an unknown string has no way to tell strong evidence from a typo."""
    proposals = [
        ClaimProposal(BLUES_ROCK, INFLUENCED_BY, edge.object_id)
        for edge in store.neighbors(BLUES_ROCK, Direction.INFLUENCED_BY)
    ]
    approved = gate(proposals, store).approved
    assert approved
    assert all(claim.verification in VERIFICATION_LEVELS for claim in approved)


# --- step 4: the states this corpus cannot express --------------------------------------------------


def test_the_unreachable_states_are_declared_with_their_preconditions() -> None:
    """Declared rather than silently absent. Someone reading ``contested`` in the rules doc and grepping
    for it must find this, not nothing — and must find *why* it is not built."""
    assert set(UNREACHABLE) == {"contested", "checks_disagree"}
    for state, precondition in UNREACHABLE.items():
        assert precondition.strip(), (
            f"{state} is declared with no precondition, which explains nothing"
        )


def test_no_artifact_edge_can_produce_an_unreachable_state() -> None:
    """**This test is the lock**, and without it the declaration above rots.

    ``contested`` needs two sources to disagree; every edge here has exactly one. ``checks_disagree``
    needs an edge whose checks conflict; ``select_edges()`` keeps those out by policy. Both are checked
    against the artifact rather than asserted, so a future corpus that *could* express one of them fails
    here — which is the notification, rather than the state quietly becoming reachable in silence.
    """
    # Loaded straight from the pinned directory rather than walked through the store: the claim is
    # about **every edge in the corpus**, and a walk only ever reaches the edges it happens to visit.
    artifact = Artifact.load(artifact_directory())
    assert artifact.edges

    for edge in artifact.edges:
        assert len(resolve_sources(edge)) <= 1, (
            f"{edge.subject_id} -> {edge.object_id} resolves to more than one source. "
            f"'contested' may now be reachable: {UNREACHABLE['contested']}"
        )
        assert edge.verification in VERIFICATION_LEVELS, (
            f"{edge.subject_id} -> {edge.object_id} carries {edge.verification!r}, which is not a "
            f"declared level. 'checks_disagree' may now be reachable: {UNREACHABLE['checks_disagree']}"
        )


def test_verification_is_not_documented_as_agreement() -> None:
    """The docstring obligation, as an assertion rather than a convention.

    These tiers record **how strongly one source was checked** — not how many sources agree, and not
    whether anything is disputed. That sentence is what stops the slide from *traceable* to *correct*,
    and a docstring is the only place a reader meets the field, so it is where the sentence has to be.
    """
    doc = Claim.__doc__ or ""
    field_doc = claims_module.__doc__ or ""
    combined = f"{doc}\n{field_doc}".lower()
    assert "one source" in combined or "single source" in combined
    for overclaim in ("sources agree", "corroborat", "cross-check"):
        assert overclaim not in doc.lower(), (
            f"Claim's docstring implies {overclaim!r}; verification is not corroboration"
        )
