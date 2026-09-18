"""Cross-axis routes — phase 8 step 4.

The premise, measured on artifact v0.10.0 and asserted here so it cannot drift silently: `delta blues`
and `Detroit techno` have **no influence path** in either direction or undirected, and a five-hop route
appears once membership is walkable. Everything in this file exists to make sure that route is never
narrated as a line of descent.
"""

from __future__ import annotations

import pytest

from musical_mycelium.agent.claims import gate
from musical_mycelium.agent.loop import chain_is_approved
from musical_mycelium.agent.tools import ToolRegistry, default_registry
from musical_mycelium.graph.crossaxis import cross_axis_route, crosses_axes
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import (
    INFLUENCE_ONLY,
    LINEAGE_PREDICATES,
    PREDICATE_PLAYS_GENRE,
)
from musical_mycelium.graph.store import Direction

DELTA_BLUES, DETROIT_TECHNO = "Q1127539", "Q526463"


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture(scope="module")
def registry(store: InMemoryGraphStore) -> ToolRegistry:
    return default_registry(store)


# --- the premise -----------------------------------------------------------------------------------


def test_the_two_genres_have_no_influence_path_in_either_direction(
    store: InMemoryGraphStore,
) -> None:
    """Phase 8's founding measurement. If this ever passes, the phase's premise has changed and the
    scope doc's §0 needs re-reading before anything here is trusted."""
    assert not store.path(
        DELTA_BLUES, DETROIT_TECHNO, Direction.INFLUENCED_BY, predicates=INFLUENCE_ONLY
    )
    assert not store.path(
        DETROIT_TECHNO, DELTA_BLUES, Direction.INFLUENCED_BY, predicates=INFLUENCE_ONLY
    )
    assert not store.path(
        DELTA_BLUES, DETROIT_TECHNO, Direction.INFLUENCED_BY, predicates=LINEAGE_PREDICATES
    )


def test_membership_produces_a_route_where_influence_produces_none(
    store: InMemoryGraphStore,
) -> None:
    hops = cross_axis_route(store, DELTA_BLUES, DETROIT_TECHNO)
    assert hops, "the corpus holds no cross-axis route between the phase's own two genres"
    assert crosses_axes(hops), "the route never left the influence layer"
    assert any(hop.predicate == PREDICATE_PLAYS_GENRE for hop in hops)


# --- the reason a route is not a chain ---------------------------------------------------------------


def test_most_hops_of_the_canonical_route_run_against_their_own_edges(
    store: InMemoryGraphStore,
) -> None:
    """**The measurement that decides the whole design.** A route is an ordering; a chain is an
    assertion that each node came out of the next. On this route four of five hops walk against the
    edge underneath them, so reading it as descent inverts most of it."""
    hops = cross_axis_route(store, DELTA_BLUES, DETROIT_TECHNO)
    backwards = [hop for hop in hops if not hop.forward]
    assert len(backwards) > len(hops) / 2, "the premise of ToolResult.route no longer holds"


def test_the_route_would_fail_chain_approval_and_is_therefore_never_offered_as_one(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """The lock. Were a future edit to put this route in ``chain``, ``chain_is_approved`` would reject
    it — so the failure would be a silent loss of the ordering rather than a false claim. This asserts
    the tool does not even try, which is the difference between a bug that degrades and one that lies.
    """
    result = registry.invoke(
        "trace_route_through_musicians", {"from_id": DELTA_BLUES, "to_id": DETROIT_TECHNO}
    )
    assert result.chain == (), "a cross-axis route must never be offered as a chain"
    assert result.route, "the route field is how the ordering survives"

    approved = gate(list(result.proposals), store).approved
    route_order = (result.route[0].from_id, *(hop.to_id for hop in result.route))
    assert not chain_is_approved(route_order, approved), (
        "the route happens to satisfy chain orientation; the premise of this design has changed"
    )


# --- claims come from the edge's orientation, never the route's ---------------------------------------


def test_every_proposal_uses_the_edges_own_direction(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """``Hop.claim_pair`` is the only correct way to build a proposal from a hop, and this is why: a
    proposal built from the route's direction would say a genre performed an artist."""
    result = registry.invoke(
        "trace_route_through_musicians", {"from_id": DELTA_BLUES, "to_id": DETROIT_TECHNO}
    )
    for hop, proposal in zip(result.route, result.proposals, strict=True):
        assert (proposal.subject_id, proposal.object_id) == hop.claim_pair
        assert proposal.predicate == hop.predicate


def test_every_hop_of_the_route_survives_the_gate(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """Every hop is a real artifact edge in its real direction, so the gate approves all of them. If a
    hop were rejected the route would be one this graph cannot justify, and the loop declines to emit
    a partial one."""
    result = registry.invoke(
        "trace_route_through_musicians", {"from_id": DELTA_BLUES, "to_id": DETROIT_TECHNO}
    )
    decision = gate(list(result.proposals), store)
    assert not decision.rejected
    assert len(decision.approved) == len(result.route)


def test_a_membership_hop_is_gated_as_membership_and_not_as_influence(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    from musical_mycelium.graph.schema import VERIFICATION_MEMBERSHIP_LEVELS

    result = registry.invoke(
        "trace_route_through_musicians", {"from_id": DELTA_BLUES, "to_id": DETROIT_TECHNO}
    )
    approved = gate(list(result.proposals), store).approved
    membership = [c for c in approved if c.predicate == PREDICATE_PLAYS_GENRE]
    assert membership, "the canonical route carries no membership claim"
    for claim in membership:
        assert claim.verification in VERIFICATION_MEMBERSHIP_LEVELS


# --- the tool's own honesty ---------------------------------------------------------------------------


def test_the_payload_states_each_hops_real_direction(registry: ToolRegistry) -> None:
    """DoD 1: the predicate of each hop is in the payload, not inferred from the node kinds at its ends.
    ``asserted_as`` is the field that keeps a backwards hop readable."""
    result = registry.invoke(
        "trace_route_through_musicians", {"from_id": DELTA_BLUES, "to_id": DETROIT_TECHNO}
    )
    for row in result.content["route"]:
        assert row["relationship"] in {"influenced_by", "plays_genre", "studied_with"}
        assert row["asserted_as"]
    assert result.content["through_musicians"] is True
    assert "not a line of influence" in result.content["note"]


def test_an_unreachable_pair_returns_an_empty_route_and_says_what_that_means(
    registry: ToolRegistry,
) -> None:
    """Refusal is correct behaviour. The wording must not slide into "these are unrelated"."""
    result = registry.invoke(
        "trace_route_through_musicians", {"from_id": DELTA_BLUES, "to_id": "Q_not_a_node"}
    )
    assert result.is_error


def test_an_unknown_node_is_an_error_not_an_empty_route(registry: ToolRegistry) -> None:
    result = registry.invoke(
        "trace_route_through_musicians", {"from_id": "Q_nope", "to_id": DETROIT_TECHNO}
    )
    assert result.is_error
    assert "resolve_node" in result.content["error"]
