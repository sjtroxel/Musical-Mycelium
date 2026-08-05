"""Corpus policy: what the hand lists do to the automated screening.

This is the seam where phase 2's two halves meet. ``discovery`` gathers evidence and knows nothing
about who read what; ``wikidata.select_edges`` decides the corpus. Getting it wrong is not a crash —
it is an artifact that quietly contains edges a human threw out, which is the failure
``REJECTED_EDGES`` was written to prevent and the one nobody would notice.

Pure and offline: ``select_edges`` takes the accepted pairs and returns the selection.
"""

from __future__ import annotations

import pytest

from musical_mycelium.graph.schema import VERIFICATION_HAND, VERIFICATION_PROSE_AUTO
from musical_mycelium.ingest.wikidata import (
    HAND_VERIFIED_EDGES,
    REJECTED_EDGES,
    IngestError,
    select_edges,
)

REJECTED_PAIRS = tuple((subject, obj) for subject, obj, _ in REJECTED_EDGES)


def test_hand_verified_edges_are_selected_even_when_the_screening_missed_them() -> None:
    """A human reading the sentence is the stronger signal. The check missing one does not lose it."""
    selected, _ = select_edges([])

    assert {edge.pair for edge in selected} == set(HAND_VERIFIED_EDGES)
    assert {edge.verification for edge in selected} == {VERIFICATION_HAND}


def test_a_hand_rejected_edge_is_not_admitted_by_the_automated_check() -> None:
    """The headline guarantee. The check accepts six of the seven hand rejections, so building
    straight from the screening would re-admit every one of them."""
    selected, overruled = select_edges(REJECTED_PAIRS)

    assert not ({edge.pair for edge in selected} & set(REJECTED_PAIRS))
    assert {pair for pair, _ in overruled} == set(REJECTED_PAIRS)


def test_an_overruled_edge_carries_the_human_s_reason() -> None:
    """The reason is what makes the exclusion auditable rather than an unexplained subtraction."""
    _, overruled = select_edges([("Q38848", "Q9730")])

    assert len(overruled) == 1
    assert "contradicts" in overruled[0][1]


def test_a_new_edge_is_prose_auto() -> None:
    selected, overruled = select_edges([("Q999901", "Q999902")])

    new = next(edge for edge in selected if edge.subject_id == "Q999901")
    assert new.verification == VERIFICATION_PROSE_AUTO
    assert overruled == ()


def test_an_edge_in_both_lists_is_not_silently_resolved() -> None:
    """A pair cannot be both hand-accepted and hand-rejected, and guessing which wins would encode a
    coin flip as corpus policy. The two lists are hand-maintained, so this is reachable by a typo."""
    pair = HAND_VERIFIED_EDGES[0]
    patched = ((*pair, "invented conflict"),)

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("musical_mycelium.ingest.wikidata.REJECTED_EDGES", patched)
        with pytest.raises(IngestError, match="both"):
            select_edges([])


def test_selection_is_deterministic_and_sorted() -> None:
    """The statement URI of each selected edge reaches the artifact, and the artifact is hashed. An
    ordering that depended on input order would make the sha256 vary over identical source data."""
    pairs = [("Q999903", "Q999904"), ("Q999901", "Q999902")]

    forward, _ = select_edges(pairs)
    backward, _ = select_edges(list(reversed(pairs)))

    assert forward == backward
    assert list(forward) == sorted(forward, key=lambda edge: edge.pair)


def test_a_duplicate_accepted_pair_does_not_duplicate_the_edge() -> None:
    selected, _ = select_edges([("Q999901", "Q999902"), ("Q999901", "Q999902")])

    assert len([edge for edge in selected if edge.subject_id == "Q999901"]) == 1


def test_the_hand_lists_do_not_overlap_as_shipped() -> None:
    """The guard above proves the check works; this proves the real lists are clean right now."""
    assert not (set(HAND_VERIFIED_EDGES) & set(REJECTED_PAIRS))
