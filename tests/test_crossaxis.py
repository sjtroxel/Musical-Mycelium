"""Cross-axis routes — phase 8 step 4.

The premise, measured on artifact v0.10.0 and asserted here so it cannot drift silently: `delta blues`
and `Detroit techno` have **no influence path** in either direction or undirected, and a five-hop route
appears once membership is walkable. Everything in this file exists to make sure that route is never
narrated as a line of descent.
"""

from __future__ import annotations

from typing import Any

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
    Node,
)
from musical_mycelium.graph.store import Direction

DELTA_BLUES, DETROIT_TECHNO = "Q1127539", "Q526463"


def _node(store: InMemoryGraphStore, node_id: str) -> Node:
    """A node that is definitely there. Every id here comes off an approved claim, so ``None`` means the
    gate approved a claim about a node the store does not hold, which is worth an assertion rather than
    a silent ``getattr``."""
    node = store.get_node(node_id)
    assert node is not None, f"approved claim references unknown node {node_id}"
    return node


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


# --- step 4b: the route becomes an answer ------------------------------------------------------------


def _route_claim_set(store: InMemoryGraphStore, registry: ToolRegistry) -> Any:
    """The claim set `run` would build for the canonical route, assembled the way `run` assembles it."""
    from musical_mycelium.agent.loop import ApprovedClaimSet

    result = registry.invoke(
        "trace_route_through_musicians", {"from_id": DELTA_BLUES, "to_id": DETROIT_TECHNO}
    )
    approved = gate(list(result.proposals), store).approved
    ends = {n for c in approved for n in (c.subject_id, c.object_id)}
    return ApprovedClaimSet(
        claims=approved,
        labels={i: _node(store, i).label for i in ends},
        kinds={i: _node(store, i).kind for i in ends},
        route=(result.route[0].from_id, *(h.to_id for h in result.route)),
    )


def test_a_route_is_narratable_where_the_same_claims_alone_are_not(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """**The defect step 4b fixes.** The identical five claims with no route match no shape -- no common
    subject, no common object, no chain, no hub -- and refuse with "describe no single lineage". The
    ordering is what makes them an answer."""
    from musical_mycelium.agent.loop import ApprovedClaimSet

    routed = _route_claim_set(store, registry)
    assert routed.narratable

    unrouted = ApprovedClaimSet(
        claims=routed.claims, labels=dict(routed.labels), kinds=dict(routed.kinds)
    )
    assert not unrouted.narratable


def test_every_step_is_stated_in_its_own_sources_direction_not_the_routes(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """**The single most important assertion in this file.** The route walks Delta blues -> Chicago
    blues; the claim says Chicago blues came out of Delta blues. Synthesis must be shown the claim. A
    `route_steps` that returned the route's direction would state the reverse of the truth on four of
    these five hops."""
    claim_set = _route_claim_set(store, registry)
    approved = {(c.subject_id, c.object_id) for c in claim_set.claims}
    for subject, predicates, obj in claim_set.route_steps:
        assert (subject, obj) in approved, f"{subject}->{obj} is not an approved claim's direction"
        assert predicates


def test_the_prompt_says_connected_and_never_says_lineage(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    from musical_mycelium.agent.llm import LLMResponse, ScriptedLLM
    from musical_mycelium.agent.loop import synthesize

    llm = ScriptedLLM([LLMResponse(text="prose")])
    list(synthesize(_route_claim_set(store, registry), llm))
    prompt = llm.requests[-1]["messages"][0]["content"][0]["text"]

    assert "connected through musicians who played in both" in prompt
    assert "played" in prompt
    for forbidden in ("chain of influence", "Documented influences", "came out of it"):
        assert forbidden not in prompt
    assert "Do not call this a lineage" in prompt


# --- breaking the lock on purpose, which is this repo's practice --------------------------------------


def test_a_route_with_an_unapproved_hop_cannot_be_constructed(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """`__post_init__` must reject a route that bridges a gap the gate did not approve, exactly as it
    rejects an unapproved chain. Without this the route field is a hole straight through the gate."""
    from musical_mycelium.agent.loop import ApprovedClaimSet

    routed = _route_claim_set(store, registry)
    with pytest.raises(ValueError, match="no approved claim supports"):
        ApprovedClaimSet(
            claims=routed.claims,
            labels=dict(routed.labels),
            kinds=dict(routed.kinds),
            route=(*routed.route, DELTA_BLUES),  # a hop back to the start that no claim supports
        )


def test_a_route_naming_a_node_no_claim_mentions_is_refused(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    from musical_mycelium.agent.loop import ApprovedClaimSet

    routed = _route_claim_set(store, registry)
    with pytest.raises(ValueError):
        ApprovedClaimSet(
            claims=routed.claims,
            labels=dict(routed.labels),
            kinds=dict(routed.kinds),
            route=(routed.route[0], "Q_invented"),
        )


def test_route_approval_accepts_either_direction_but_still_demands_a_claim(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """The looseness is about direction and nothing else. A reversed route of the same nodes is still
    fully approved; a route over a pair with no claim at all is not."""
    from musical_mycelium.agent.loop import route_is_approved

    routed = _route_claim_set(store, registry)
    assert route_is_approved(routed.route, routed.claims)
    assert route_is_approved(tuple(reversed(routed.route)), routed.claims)
    assert not route_is_approved((DELTA_BLUES, DETROIT_TECHNO), routed.claims)
    assert not route_is_approved((DELTA_BLUES,), routed.claims)


def test_a_route_that_never_leaves_influence_is_not_framed_as_shared_musicians(
    store: InMemoryGraphStore,
) -> None:
    """The framing must track what the route actually rests on. Claiming a connection through people
    that a pure-influence route does not have is the same class of error as the reverse."""
    from musical_mycelium.agent.claims import ClaimProposal
    from musical_mycelium.agent.llm import LLMResponse, ScriptedLLM
    from musical_mycelium.agent.loop import ApprovedClaimSet, synthesize

    chain = store.path("Q483352", "Q3071", Direction.INFLUENCED_BY, predicates=INFLUENCE_ONLY)
    assert chain, "the influence-only fixture path is gone; pick another pair"
    approved = gate(
        [ClaimProposal(e.subject_id, e.predicate, e.object_id) for e in chain], store
    ).approved
    ends = {n for c in approved for n in (c.subject_id, c.object_id)}
    claim_set = ApprovedClaimSet(
        claims=approved,
        labels={i: _node(store, i).label for i in ends},
        kinds={i: _node(store, i).kind for i in ends},
        route=(approved[0].subject_id, *(c.object_id for c in approved)),
    )
    assert not claim_set.route_through_musicians

    llm = ScriptedLLM([LLMResponse(text="prose")])
    list(synthesize(claim_set, llm))
    prompt = llm.requests[-1]["messages"][0]["content"][0]["text"]
    assert "connected through musicians" not in prompt
    assert "the graph records these steps between them" in prompt


def test_the_whole_run_answers_instead_of_refusing(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """**DoD 2, end to end.** Before step 4b this run emitted `Refused` beside five approved claims."""
    import json as _json

    from musical_mycelium.agent.llm import LLMResponse, ScriptedLLM, ToolUse
    from musical_mycelium.agent.loop import MembershipDisclosed, Refused, RouteWalked, Token, run

    llm = ScriptedLLM(
        [
            LLMResponse(
                text=_json.dumps(
                    {
                        "query_kind": "lineage",
                        "steps": [{"tool": "trace_route_through_musicians"}],
                    }
                )
            ),
            LLMResponse(
                tool_uses=(
                    ToolUse(
                        id="t1",
                        name="trace_route_through_musicians",
                        arguments={"from_id": DELTA_BLUES, "to_id": DETROIT_TECHNO},
                    ),
                )
            ),
            LLMResponse(text="done"),
            LLMResponse(text="They share musicians."),
        ]
    )
    events = list(
        run(
            "how is delta blues connected to detroit techno?",
            store=store,
            llm=llm,
            registry=registry,
        )
    )
    names = [type(e).__name__ for e in events]

    assert not [e for e in events if isinstance(e, Refused)], "a fully sourced route still refuses"
    assert [e for e in events if isinstance(e, RouteWalked)]
    assert [e for e in events if isinstance(e, MembershipDisclosed)]
    assert [e for e in events if isinstance(e, Token)]
    assert names.index("RouteWalked") < names.index("Token")
    assert names.index("MembershipDisclosed") < names.index("Token")
