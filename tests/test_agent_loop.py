"""Tools, the provider seam, and the loop.

Two of these tests are load-bearing beyond ordinary correctness:

``test_a_new_tool_does_not_touch_the_loop`` is **invariant 4**. If it ever needs editing to
accommodate a new tool, the seam is broken. ``trace_lineage`` was added under it in phase 2 step 5 and
this test did not change shape — only the registry count it asserts.

``test_synthesis_prompt_contains_only_approved_claims`` is **invariant 1**. It inspects what the model
was actually shown at synthesis time, which is the only way to check the claims-first rule rather than
assume it — a rejected edge appearing in that prompt is the leak the 7/27 review caught.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

import musical_mycelium
from musical_mycelium.agent import loop as agent_loop
from musical_mycelium.agent.claims import Claim, ClaimProposal, RejectionReason, gate
from musical_mycelium.agent.llm import (
    LLM,
    PLANNING_SENTINEL,
    LLMResponse,
    LocalLLM,
    ScriptedLLM,
    ToolUse,
    Usage,
    _parse_converse,
    build_llm,
)
from musical_mycelium.agent.loop import (
    ApprovedClaimSet,
    ClaimApproved,
    ClaimRejected,
    Done,
    PathWalked,
    Planned,
    Refused,
    Token,
    ToolCalled,
    refusal_text,
    run,
    synthesize,
)
from musical_mycelium.agent.plan import (
    PLANNING_PROMPT_TEMPLATE,
    UNKNOWN_QUERY_KIND,
    Plan,
    PremiseAssertion,
)
from musical_mycelium.agent.tools import (
    GetInfluences,
    ResolveNode,
    Tool,
    ToolRegistry,
    ToolResult,
    TraceLineage,
    default_registry,
)
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import NODE_KIND_ARTIST, NODE_KIND_GENRE

BLUES_ROCK, BLUES = "Q193355", "Q9759"
ACID_JAZZ, JAZZ = "Q221772", "Q8341"
HEAVY_METAL = "Q38848"
INFLUENCED_BY = "influenced_by"

#: The ``adv_013`` pair, read off the frozen adversarial set and confirmed against the artifact rather
#: than recalled — see ``reference-never-recall-wikidata-qids``. Thrash metal came out of punk rock, and
#: the reverse is not in the graph, which is what makes the pair a one-hop inversion fixture.
PUNK_ROCK, THRASH_METAL = "Q3071", "Q483352"

#: An artist in the v0.4.0 corpus, resolved from the artifact rather than recalled — see
#: ``reference-never-recall-wikidata-qids``. U2 has six sourced influences and is a stable fixture.
ARTIST, ARTIST_LABEL = "Q396", "U2"


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture
def registry(store: InMemoryGraphStore) -> ToolRegistry:
    return default_registry(store)


def plan_turn(query_kind: str, *tools: str, premise: tuple[str, str] | None = None) -> LLMResponse:
    """The planning turn every run now opens with.

    **Prepended to every script rather than made skippable**, and that is not pedantry. A script without
    it does not fail: its first tool turn is silently consumed by the planner, the run shifts by one, and
    the test goes green having exercised the wrong sequence. Two tests were passing that way in the hour
    this helper was written.
    """
    payload: dict[str, Any] = {
        "query_kind": query_kind,
        "steps": [{"tool": t} for t in tools],
    }
    if premise is not None:
        payload["asserted_premise"] = {"subject": premise[0], "object": premise[1]}
    return LLMResponse(text=json.dumps(payload), usage=Usage(80, 15))


def resolve_then_influences(name: str, node_id: str) -> list[LLMResponse]:
    """The plan turn, the two tool turns v0.1 expects, then a final text turn."""
    return [
        plan_turn("origins", "resolve_node", "get_influences"),
        LLMResponse(
            tool_uses=(ToolUse(id="t1", name="resolve_node", arguments={"name": name}),),
            stop_reason="tool_use",
            usage=Usage(100, 20),
        ),
        LLMResponse(
            tool_uses=(ToolUse(id="t2", name="get_influences", arguments={"node_id": node_id}),),
            stop_reason="tool_use",
            usage=Usage(150, 25),
        ),
        LLMResponse(text="Found them.", stop_reason="end_turn", usage=Usage(200, 30)),
        LLMResponse(text="A grounded two-sentence answer."),  # the synthesis stream
    ]


# --- tools: the contract ------------------------------------------------------------------------


def test_the_tools_satisfy_the_protocol(store: InMemoryGraphStore) -> None:
    assert isinstance(ResolveNode(store), Tool)
    assert isinstance(GetInfluences(store), Tool)
    assert isinstance(TraceLineage(store), Tool)


def test_tool_config_is_the_bedrock_shape(registry: ToolRegistry) -> None:
    specs = registry.tool_config()["tools"]
    assert {s["toolSpec"]["name"] for s in specs} == {
        "resolve_node",
        "get_influences",
        "trace_lineage",
        "get_descendants",
        "describe_node",
        "resolve_source",
        "corpus_coverage",
    }
    for spec in specs:
        assert spec["toolSpec"]["description"]
        assert spec["toolSpec"]["inputSchema"]["json"]["type"] == "object"


def test_no_prompt_names_a_tool(store: InMemoryGraphStore) -> None:
    """Invariant 4 has a prose door as well as a code one.

    v0.1's system prompt hard-coded "use resolve_node, then get_influences", so a third tool could be
    registered without a loop edit and still never be called. A tool describes itself in its own spec;
    the system prompt states the rules.

    Checked against ``registry.names`` rather than a literal list, so a tool added later is covered by
    this test the day it is registered. Widened 2026-08-07 from the system prompt alone to **all three
    prompts**: the synthesis prompts must not name tools either, and going from three tools to seven is
    exactly when that property is most likely to be quietly broken.

    Widened again 2026-08-08 to the planning **template**. The planning prompt is the one place a tool
    name legitimately appears, and it gets there by being rendered from the registry — so the template
    is held to the same rule and ``test_plan.py`` asserts the rendered result names them all.
    """
    prompts = {
        "SYSTEM_PROMPT": agent_loop.SYSTEM_PROMPT,
        "SYNTHESIS_PROMPT": agent_loop.SYNTHESIS_PROMPT,
        "CHAIN_SYNTHESIS_PROMPT": agent_loop.CHAIN_SYNTHESIS_PROMPT,
        "PLANNING_PROMPT_TEMPLATE": PLANNING_PROMPT_TEMPLATE,
    }
    for name in default_registry(store).names:
        for prompt_name, prompt in prompts.items():
            assert name not in prompt, f"{prompt_name} hard-codes {name}"


def test_a_new_tool_does_not_touch_the_loop(store: InMemoryGraphStore) -> None:
    """Invariant 4, as a test. A new tool is a registration; the loop never learns it exists.

    The tool below contributes a claim proposal and a visited node, and the loop harvests both without
    a single branch naming it.
    """

    class CountGenres:
        name = "count_genres"
        description = "How many genres are in the graph."

        def input_schema(self) -> dict[str, Any]:
            return {"type": "object", "properties": {}}

        def __call__(self, **kwargs: Any) -> ToolResult:
            return ToolResult(
                content={"count": 28},
                proposals=(ClaimProposal(BLUES_ROCK, INFLUENCED_BY, BLUES),),
                visited=("Q1",),
            )

    registry = default_registry(store)
    before = len(registry)
    registry.register(CountGenres())
    # Relative, not a magic number: what this test is about is that registration adds exactly one tool
    # and the loop is unchanged. Pinning an absolute count made it fail every time a tool was added,
    # for a reason unrelated to the property under test — which happened at phase 3 step 2.
    assert len(registry) == before + 1

    llm = ScriptedLLM(
        [
            plan_turn("unknown", "count_genres"),
            LLMResponse(
                tool_uses=(ToolUse(id="t1", name="count_genres", arguments={}),),
                stop_reason="tool_use",
            ),
            LLMResponse(text="done"),
            LLMResponse(text="prose"),
        ]
    )
    events = list(run("anything", store=store, llm=llm, registry=registry))

    assert any(isinstance(e, ToolCalled) and e.name == "count_genres" for e in events)
    approved = [e for e in events if isinstance(e, ClaimApproved)]
    assert len(approved) == 1, "the loop gated a proposal from a tool it has never heard of"


def test_registry_refuses_a_duplicate_name(store: InMemoryGraphStore) -> None:
    registry = default_registry(store)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(ResolveNode(store))


def test_an_unknown_tool_is_an_error_result_not_an_exception(registry: ToolRegistry) -> None:
    """The model gets told what went wrong and can correct. A raise would kill the run instead."""
    result = registry.invoke("teleport", {})
    assert result.is_error
    assert "no such tool" in result.content["error"]


def test_bad_arguments_are_an_error_result(registry: ToolRegistry) -> None:
    assert registry.invoke("resolve_node", {"wrong": "arg"}).is_error


# --- tools: honest absence ----------------------------------------------------------------------


def test_resolve_node_returns_null_for_an_unknown_genre(registry: ToolRegistry) -> None:
    assert registry.invoke("resolve_node", {"name": "bebop"}).content["node_id"] is None


def test_resolve_node_refuses_a_near_miss_rather_than_guessing(registry: ToolRegistry) -> None:
    """``blues r`` must not silently resolve to ``blues rock``. It offers alternatives instead — a
    confident wrong resolution answers a question nobody asked, with citations attached."""
    result = registry.invoke("resolve_node", {"name": "metal"})
    assert result.content["node_id"] is None
    assert "did_you_mean" in result.content


def test_resolve_node_resolves_an_exact_match(registry: ToolRegistry) -> None:
    result = registry.invoke("resolve_node", {"name": "the blues"})
    assert result.content["node_id"] == BLUES
    assert result.visited == (BLUES,)


# --- tools: the axis is visible to the model ----------------------------------------------------


def test_resolve_node_reports_which_axis_it_landed_on(registry: ToolRegistry) -> None:
    """The payload carries ``kind``, and it is not decoration.

    Without it the model resolves a name, gets an id and a label, and has no way to know whether it
    is holding a genre or an artist — so it can propose a genre-to-artist claim, have ``gate()``
    refuse it ``CROSS_AXIS``, and burn a turn on a rejection it had no information to avoid. The gate
    is the enforcement; this is what lets the model cooperate with it instead of discovering it by
    failing.
    """
    genre = registry.invoke("resolve_node", {"name": "the blues"})
    assert genre.content["kind"] == NODE_KIND_GENRE


def test_resolve_node_resolves_artists_not_only_genres(registry: ToolRegistry) -> None:
    """The whole reason the tool stopped being called ``resolve_genre`` at v0.4.0."""
    artist = registry.invoke("resolve_node", {"name": ARTIST_LABEL})
    assert artist.content["node_id"] == ARTIST
    assert artist.content["kind"] == NODE_KIND_ARTIST


def test_the_tool_contract_tells_the_model_both_axes_exist_and_must_not_be_mixed(
    store: InMemoryGraphStore,
) -> None:
    """A contract test, because this text is the only thing a real model ever reads about the tool.

    It said "Resolve a genre name" through v0.3.0. A model told the tool resolves *genres* will not
    offer it an artist name, so the artist axis would have been invisible in production while being
    fully present in the corpus — a failure that no unit test of the graph could surface.
    """
    description = ResolveNode(store).description
    assert "artist" in description and "genre" in description
    assert "kind" in description
    assert "same" in description.lower(), "the cross-axis rule must be stated, not implied"


def test_resolve_node_tolerates_wikidatas_trailing_music(registry: ToolRegistry) -> None:
    """32 of the 169 nodes are labelled "<name> music" and nobody types the suffix. Both spellings must
    reach the same node, and neither is a guess — the fold is documented and applied to both sides."""
    assert (
        registry.invoke("resolve_node", {"name": "heavy metal"}).content["node_id"] == HEAVY_METAL
    )
    assert (
        registry.invoke("resolve_node", {"name": "heavy metal music"}).content["node_id"]
        == HEAVY_METAL
    )


def test_the_music_fold_still_refuses_a_genuine_near_miss(registry: ToolRegistry) -> None:
    """The fold must not become fuzzy matching by increments. "metal" is still not a genre in here."""
    assert registry.invoke("resolve_node", {"name": "metal"}).content["node_id"] is None
    assert registry.invoke("resolve_node", {"name": "blues r"}).content["node_id"] is None


def test_get_influences_returns_edges_and_proposals(registry: ToolRegistry) -> None:
    result = registry.invoke("get_influences", {"node_id": ACID_JAZZ})
    assert result.content["count"] == 4
    assert len(result.proposals) == 4
    assert len(result.sources) == 4
    assert result.visited[0] == ACID_JAZZ


def test_get_influences_on_an_unsourced_node_is_empty_not_an_error(registry: ToolRegistry) -> None:
    """Gold case 5. Empty means the graph cannot answer, and the tool says so without erroring."""
    result = registry.invoke("get_influences", {"node_id": BLUES})
    assert result.content["influences"] == []
    assert result.proposals == ()
    assert not result.is_error


def test_get_influences_rejects_a_node_that_is_not_in_the_graph(registry: ToolRegistry) -> None:
    assert registry.invoke("get_influences", {"node_id": "Q99999999"}).is_error


def test_get_influences_asserts_no_chain(registry: ToolRegistry) -> None:
    """A fan-out is a set, not a sequence. Setting ``chain`` here would narrate four sibling influences
    as a line of descent, which is the exact false ordering the chain field exists to prevent."""
    assert registry.invoke("get_influences", {"node_id": ACID_JAZZ}).chain == ()


# --- trace_lineage: the phase 2 tool --------------------------------------------------------------


def test_trace_lineage_returns_a_hop_per_edge(registry: ToolRegistry) -> None:
    """The signature chain, walked as ancestry. Two hops is the deepest this corpus holds
    (``phase-2-corpus-and-traversal.md`` A5) and that is measured, not assumed."""
    result = registry.invoke("trace_lineage", {"from_id": HEAVY_METAL, "to_id": BLUES})

    assert result.content["hops"] == 2
    assert len(result.proposals) == 2
    assert len(result.sources) == 2
    assert result.chain == (HEAVY_METAL, BLUES_ROCK, BLUES)
    assert [p.subject_id for p in result.proposals] == [HEAVY_METAL, BLUES_ROCK]
    assert [p.object_id for p in result.proposals] == [BLUES_ROCK, BLUES]


def test_the_reversed_question_finds_the_same_chain_without_inverting_it(
    registry: ToolRegistry,
) -> None:
    """The load-bearing one. "How is blues connected to heavy metal?" puts the arguments in the other
    order, and the answer must be the same chain — **not** a chain claiming blues came out of metal.

    This holds because a proposal is built from the edge rather than from argument order, so a
    descent walk cannot manufacture a reversed influence claim.
    """
    forward = registry.invoke("trace_lineage", {"from_id": HEAVY_METAL, "to_id": BLUES})
    reverse = registry.invoke("trace_lineage", {"from_id": BLUES, "to_id": HEAVY_METAL})

    assert reverse.chain == forward.chain == (HEAVY_METAL, BLUES_ROCK, BLUES)
    assert {(p.subject_id, p.object_id) for p in reverse.proposals} == {
        (p.subject_id, p.object_id) for p in forward.proposals
    }
    assert all(p.subject_id != BLUES for p in reverse.proposals), (
        "blues was narrated as a descendant"
    )


def test_trace_lineage_chain_pairs_are_all_claims_it_proposes(registry: ToolRegistry) -> None:
    """``ToolResult.chain``'s stated contract, checked in both walk directions rather than trusted."""
    for args in (
        {"from_id": HEAVY_METAL, "to_id": BLUES},
        {"from_id": BLUES, "to_id": HEAVY_METAL},
    ):
        result = registry.invoke("trace_lineage", args)
        proposed = {(p.subject_id, p.object_id) for p in result.proposals}
        pairs = list(zip(result.chain, result.chain[1:], strict=False))
        assert pairs and all(pair in proposed for pair in pairs)


def test_trace_lineage_with_no_chain_is_a_refusal_not_an_error(registry: ToolRegistry) -> None:
    """Different components. The graph cannot connect them, and saying so is correct behaviour —
    an empty path proposes nothing, so the gate approves nothing and the run refuses."""
    result = registry.invoke("trace_lineage", {"from_id": ACID_JAZZ, "to_id": BLUES})

    assert result.content["path"] == []
    assert result.content["hops"] == 0
    assert result.proposals == ()
    assert result.chain == ()
    assert not result.is_error


def test_trace_lineage_rejects_a_node_that_is_not_in_the_graph(registry: ToolRegistry) -> None:
    assert registry.invoke("trace_lineage", {"from_id": "Q99999999", "to_id": BLUES}).is_error
    assert registry.invoke("trace_lineage", {"from_id": BLUES, "to_id": "Q99999999"}).is_error


# --- the provider seam --------------------------------------------------------------------------


def test_build_llm_selects_a_provider() -> None:
    assert isinstance(build_llm("scripted", responses=[]), ScriptedLLM)
    with pytest.raises(ValueError, match="unknown LLM provider"):
        build_llm("telepathy")


def test_scripted_llm_satisfies_the_protocol() -> None:
    assert isinstance(ScriptedLLM([]), LLM)


def test_bedrock_llm_satisfies_the_protocol_without_touching_aws() -> None:
    """Constructing it must not build a client or read credentials — the client is lazy. If this ever
    starts requiring AWS, local development and CI both break."""
    from musical_mycelium.agent.llm import BedrockLLM

    llm = BedrockLLM(model_id="test-model")
    assert isinstance(llm, LLM)
    assert llm.model_id == "test-model"


def test_converse_response_parsing_against_a_recorded_payload() -> None:
    """The only way to test the Bedrock shape before the quota clears.

    This is a payload shaped the way the Converse API documents, **not** one captured from a real call
    — no ``converse`` call has ever succeeded on this account. When the smoke call lands, replace this
    fixture with the real response and fix whatever disagrees.
    """
    parsed = _parse_converse(
        {
            "output": {
                "message": {
                    "content": [
                        {"text": "Looking that up."},
                        {
                            "toolUse": {
                                "toolUseId": "tooluse_abc",
                                "name": "resolve_node",
                                "input": {"name": "acid jazz"},
                            }
                        },
                    ]
                }
            },
            "stopReason": "tool_use",
            "usage": {"inputTokens": 412, "outputTokens": 58, "totalTokens": 470},
        }
    )
    assert parsed.text == "Looking that up."
    assert parsed.wants_tools
    assert parsed.tool_uses[0].name == "resolve_node"
    assert parsed.tool_uses[0].arguments == {"name": "acid jazz"}
    assert parsed.usage.input_tokens == 412
    assert parsed.usage.total_tokens == 470


def test_usage_accumulates() -> None:
    assert (Usage(10, 5) + Usage(3, 2)) == Usage(13, 7)


# --- invariant 1: prose sees only approved claims -------------------------------------------------


def test_claim_set_rejects_a_label_no_claim_mentions() -> None:
    """The structural half of the leak-proofing. A caller cannot smuggle extra context into synthesis
    by attaching it to the labels map."""
    claim = Claim(BLUES_ROCK, INFLUENCED_BY, BLUES, ("stmt/1",))
    with pytest.raises(ValueError, match="no approved claim mentions"):
        ApprovedClaimSet(
            claims=(claim,), labels={BLUES_ROCK: "blues rock", HEAVY_METAL: "heavy metal"}
        )


def test_synthesize_refuses_to_run_on_an_empty_claim_set() -> None:
    with pytest.raises(ValueError, match="no approved claims"):
        list(synthesize(ApprovedClaimSet(claims=()), ScriptedLLM([])))


def test_claim_set_rejects_a_chain_hop_no_claim_supports() -> None:
    """The ordering half of the same leak-proofing. A chain is an assertion about descent, so a hop the
    gate never approved cannot ride into synthesis just because it was listed between two that were."""
    claims = (Claim(HEAVY_METAL, INFLUENCED_BY, BLUES_ROCK, ("stmt/1",)),)
    with pytest.raises(ValueError, match="no approved claim supports"):
        ApprovedClaimSet(claims=claims, chain=(HEAVY_METAL, BLUES_ROCK, BLUES))


def test_claim_set_rejects_a_chain_running_the_wrong_way() -> None:
    """Orientation is not a formatting detail. The same two approved claims read backwards narrate the
    blues as coming out of heavy metal, which is false and is exactly the confident wrong answer this
    project exists not to produce."""
    claims = (
        Claim(HEAVY_METAL, INFLUENCED_BY, BLUES_ROCK, ("stmt/1",)),
        Claim(BLUES_ROCK, INFLUENCED_BY, BLUES, ("stmt/2",)),
    )
    ApprovedClaimSet(
        claims=claims, chain=(HEAVY_METAL, BLUES_ROCK, BLUES)
    )  # descendant-first: fine
    with pytest.raises(ValueError, match="no approved claim supports"):
        ApprovedClaimSet(claims=claims, chain=(BLUES, BLUES_ROCK, HEAVY_METAL))


def test_the_chain_prompt_keeps_the_chain_in_order() -> None:
    """A reordered chain is a different history. The prompt states the order and the labels carry it."""
    claims = (
        Claim(HEAVY_METAL, INFLUENCED_BY, BLUES_ROCK, ("stmt/1",)),
        Claim(BLUES_ROCK, INFLUENCED_BY, BLUES, ("stmt/2",)),
    )
    claim_set = ApprovedClaimSet(
        claims=claims,
        labels={HEAVY_METAL: "heavy metal music", BLUES_ROCK: "blues rock", BLUES: "blues"},
        chain=(HEAVY_METAL, BLUES_ROCK, BLUES),
    )
    llm = ScriptedLLM([LLMResponse(text="prose")])
    list(synthesize(claim_set, llm))

    prompt = str(llm.requests[-1]["messages"])
    assert "Chain: " in prompt
    assert prompt.index("heavy metal music") < prompt.index("blues rock") < prompt.index('"blues"')


def test_synthesis_prompt_contains_only_approved_claims(store: InMemoryGraphStore) -> None:
    """Invariant 1, checked rather than assumed.

    The model proposes an edge that does not exist (``blues <- heavy metal``) alongside real ones. The
    gate rejects it. This asserts the rejected genre never reaches the synthesis prompt — if it did,
    prose could assert an edge that never became a claim, and groundedness would read 100% while the
    text hallucinated.
    """

    class Fabricating:
        name = "fabricate"
        description = "Proposes one real edge and one invented one."

        def input_schema(self) -> dict[str, Any]:
            return {"type": "object", "properties": {}}

        def __call__(self, **kwargs: Any) -> ToolResult:
            return ToolResult(
                content={},
                proposals=(
                    ClaimProposal(BLUES_ROCK, INFLUENCED_BY, BLUES),  # real
                    ClaimProposal(BLUES, INFLUENCED_BY, HEAVY_METAL),  # fabricated
                ),
                visited=(BLUES_ROCK, BLUES, HEAVY_METAL),
            )

    registry = ToolRegistry([Fabricating()])
    llm = ScriptedLLM(
        [
            plan_turn("origins", "fabricate"),
            LLMResponse(
                tool_uses=(ToolUse(id="t1", name="fabricate", arguments={}),),
                stop_reason="tool_use",
            ),
            LLMResponse(text="done"),
            LLMResponse(text="Blues rock came out of blues."),
        ]
    )

    events = list(run("Where did blues rock come from?", store=store, llm=llm, registry=registry))
    assert len([e for e in events if isinstance(e, ClaimApproved)]) == 1
    rejected = [e for e in events if isinstance(e, ClaimRejected)]
    assert rejected[0].rejection.reason is RejectionReason.NOT_IN_GRAPH

    synthesis_request = llm.requests[-1]
    prompt = str(synthesis_request["messages"])
    assert "blues rock" in prompt
    assert "heavy metal" not in prompt, (
        "a rejected edge reached the synthesis prompt — the leak is back"
    )
    assert "Where did blues rock come from?" not in prompt, "synthesis can see the raw query"


def test_synthesis_prompt_names_every_approved_influence(store: InMemoryGraphStore) -> None:
    llm = ScriptedLLM(resolve_then_influences("acid jazz", ACID_JAZZ))
    list(
        run(
            "Where did acid jazz come from?", store=store, llm=llm, registry=default_registry(store)
        )
    )

    prompt = str(llm.requests[-1]["messages"])
    for label in ("jazz", "funk", "soul", "hip-hop"):
        assert label in prompt


# --- the loop end to end ------------------------------------------------------------------------


def test_a_full_answer_run(store: InMemoryGraphStore) -> None:
    llm = ScriptedLLM(resolve_then_influences("acid jazz", ACID_JAZZ))
    events = list(
        run(
            "Where did acid jazz come from?", store=store, llm=llm, registry=default_registry(store)
        )
    )

    assert len([e for e in events if isinstance(e, ToolCalled)]) == 2
    assert len([e for e in events if isinstance(e, ClaimApproved)]) == 4
    assert not [e for e in events if isinstance(e, Refused)]
    assert [e for e in events if isinstance(e, Token)]

    done = next(e for e in events if isinstance(e, Done))
    assert done.claim_count == 4
    assert done.usage.total_tokens > 0, "token usage must be measured, not estimated"


def test_a_lineage_run_narrates_the_chain(store: InMemoryGraphStore) -> None:
    """``SPEC.md`` 2.2's signature query, **worded exactly as the SPEC words it**, end to end on the
    local provider — which is what the deployed URL runs while the Bedrock quota is at zero. Three tool
    turns, two approved hops, chain prose. Wording it verbatim is the point: the first run of this
    query refused, because "heavy metal" did not resolve to "heavy metal music"."""
    llm = build_llm("local")
    events = list(
        run(
            "How is the blues connected to heavy metal?",
            store=store,
            llm=llm,
            registry=default_registry(store),
        )
    )

    called = [e.name for e in events if isinstance(e, ToolCalled)]
    assert called == ["resolve_node", "resolve_node", "trace_lineage"]

    approved = [e.claim for e in events if isinstance(e, ClaimApproved)]
    assert [(c.subject_id, c.object_id) for c in approved] == [
        (HEAVY_METAL, BLUES_ROCK),
        (BLUES_ROCK, BLUES),
    ]
    assert all(c.source_ids for c in approved)
    assert not [e for e in events if isinstance(e, Refused)]

    prose = "".join(e.text for e in events if isinstance(e, Token))
    assert prose.index("blues rock") < prose.index("blues.")
    assert prose.lower().startswith("heavy metal music came out of blues rock")


def test_the_path_frame_separates_visit_order_from_descent_order(
    store: InMemoryGraphStore,
) -> None:
    """Found by running it: a lineage query resolves both endpoints before tracing, so visit order
    opens *blues, heavy metal* and a client drawing arrows down that list would state the descent
    backwards. The chain rides as its own field rather than being inferred from the walk."""
    events = list(
        run(
            "How is the blues connected to heavy metal?",
            store=store,
            llm=build_llm("local"),
            registry=default_registry(store),
        )
    )

    path = next(e for e in events if isinstance(e, PathWalked))
    assert path.node_ids[:2] == (BLUES, HEAVY_METAL), "visit order is the walk, not the descent"
    assert path.chain == (HEAVY_METAL, BLUES_ROCK, BLUES)
    assert path.chain_labels == ("heavy metal music", "blues rock", "blues")


def test_an_origins_run_has_no_chain(store: InMemoryGraphStore) -> None:
    """Four sibling influences are a set. Reporting them as a chain would invent an ordering."""
    llm = ScriptedLLM(resolve_then_influences("acid jazz", ACID_JAZZ))
    events = list(
        run(
            "Where did acid jazz come from?", store=store, llm=llm, registry=default_registry(store)
        )
    )

    assert next(e for e in events if isinstance(e, PathWalked)).chain == ()


def test_a_lineage_run_across_components_refuses(store: InMemoryGraphStore) -> None:
    """Two genres in different components have no sourced chain, and the honest answer is that the
    graph cannot connect them — not a bridge invented to satisfy the question."""
    events = list(
        run(
            "How is acid jazz connected to blues?",
            store=store,
            llm=build_llm("local"),
            registry=default_registry(store),
        )
    )

    assert [e for e in events if isinstance(e, Refused)]
    assert not [e for e in events if isinstance(e, ClaimApproved)]


def test_a_rejected_hop_drops_the_chain_rather_than_narrating_it(
    store: InMemoryGraphStore,
) -> None:
    """A tool may assert a chain; only the gate decides whether it is told as one. Here the middle hop
    is fabricated, so the surviving claim is listed rather than sequenced."""

    class BrokenChain:
        name = "broken_chain"
        description = "Asserts a chain whose middle hop is not in the graph."

        def input_schema(self) -> dict[str, Any]:
            return {"type": "object", "properties": {}}

        def __call__(self, **kwargs: Any) -> ToolResult:
            return ToolResult(
                content={},
                proposals=(
                    ClaimProposal(HEAVY_METAL, INFLUENCED_BY, BLUES_ROCK),  # real
                    ClaimProposal(BLUES_ROCK, INFLUENCED_BY, ACID_JAZZ),  # fabricated
                ),
                visited=(HEAVY_METAL, BLUES_ROCK, ACID_JAZZ),
                chain=(HEAVY_METAL, BLUES_ROCK, ACID_JAZZ),
            )

    llm = ScriptedLLM(
        [
            plan_turn("lineage", "broken_chain"),
            LLMResponse(
                tool_uses=(ToolUse(id="t1", name="broken_chain", arguments={}),),
                stop_reason="tool_use",
            ),
            LLMResponse(text="done"),
            LLMResponse(text="prose"),
        ]
    )
    events = list(run("anything", store=store, llm=llm, registry=ToolRegistry([BrokenChain()])))

    assert len([e for e in events if isinstance(e, ClaimApproved)]) == 1
    prompt = str(llm.requests[-1]["messages"])
    assert "Chain: " not in prompt, "a chain with a rejected hop was narrated as a chain"
    assert "acid jazz" not in prompt


def test_the_path_is_emitted_in_order(store: InMemoryGraphStore) -> None:
    """``SPEC.md`` 5.3 commits to the walked path in payload — phase 5's guided tour is built on it."""
    llm = ScriptedLLM(resolve_then_influences("acid jazz", ACID_JAZZ))
    events = list(
        run(
            "Where did acid jazz come from?", store=store, llm=llm, registry=default_registry(store)
        )
    )

    path = next(e for e in events if isinstance(e, PathWalked))
    assert path.node_ids[0] == ACID_JAZZ
    assert set(path.node_ids[1:]) == {JAZZ, "Q164444", "Q131272", "Q11401"}
    assert path.labels[0] == "acid jazz"
    assert len(path.labels) == len(path.node_ids)


def test_a_refusal_run_never_calls_the_model_for_prose(store: InMemoryGraphStore) -> None:
    """Gold case 5, end to end. ``blues`` resolves and has no sourced parents, so the gate approves
    nothing and the refusal is a template — reliable rather than probabilistic, and free."""
    llm = ScriptedLLM(
        [
            plan_turn("origins", "resolve_node", "get_influences"),
            LLMResponse(
                tool_uses=(ToolUse(id="t1", name="resolve_node", arguments={"name": "the blues"}),),
                stop_reason="tool_use",
            ),
            LLMResponse(
                tool_uses=(ToolUse(id="t2", name="get_influences", arguments={"node_id": BLUES}),),
                stop_reason="tool_use",
            ),
            LLMResponse(text="Nothing found."),
        ]
    )
    events = list(
        run(
            "Where did the blues come from?", store=store, llm=llm, registry=default_registry(store)
        )
    )

    assert not [e for e in events if isinstance(e, ClaimApproved)]
    refusal = next(e for e in events if isinstance(e, Refused))
    assert "no sourced influences" in refusal.reason
    assert llm.exhausted, "the loop asked the model for prose it had no claims to ground"
    assert next(e for e in events if isinstance(e, Done)).claim_count == 0


def test_an_unresolvable_genre_refuses_with_a_different_reason(store: InMemoryGraphStore) -> None:
    llm = ScriptedLLM(
        [
            plan_turn("origins", "resolve_node", "get_influences"),
            LLMResponse(
                tool_uses=(ToolUse(id="t1", name="resolve_node", arguments={"name": "bebop"}),),
                stop_reason="tool_use",
            ),
            LLMResponse(text="Not in the graph."),
        ]
    )
    events = list(
        run("Where did bebop come from?", store=store, llm=llm, registry=default_registry(store))
    )
    refusal = next(e for e in events if isinstance(e, Refused))
    assert "not in this graph" in refusal.reason


def test_refusal_text_states_the_absence_plainly() -> None:
    text = refusal_text(
        "Where did the blues come from?", "the genre resolved but carries no sourced influences"
    )
    assert "no sourced answer" in text
    assert "checkable source" in text


def test_the_loop_is_bounded(store: InMemoryGraphStore) -> None:
    """A model that never stops calling tools must not run forever. The ceiling is a cost control:
    every turn re-sends accumulated context, so an unbounded loop is an unbounded bill."""

    def endless() -> Iterator[LLMResponse]:
        while True:
            yield LLMResponse(
                tool_uses=(ToolUse(id="t", name="resolve_node", arguments={"name": "jazz"}),),
                stop_reason="tool_use",
            )

    generator = endless()
    llm = ScriptedLLM([plan_turn("unknown"), *(next(generator) for _ in range(20))])
    events = list(
        run(
            "loop forever",
            store=store,
            llm=llm,
            registry=default_registry(store),
            max_turns=3,
        )
    )
    # Two, not three: ``max_turns`` counts **total model turns** and the plan turn is one of them. That
    # is the property under test as much as the ceiling itself — a plan turn taken outside the budget
    # would loosen a cost control while looking like it had left it alone.
    assert len([e for e in events if isinstance(e, ToolCalled)]) == 2
    assert any(isinstance(e, Done) for e in events)


def test_every_run_opens_with_a_plan(store: InMemoryGraphStore) -> None:
    """First event, always. A client rendering the traversal needs it before anything is walked, and
    DoD #7's query-type slice reads ``query_kind`` off it."""
    llm = ScriptedLLM(resolve_then_influences("acid jazz", ACID_JAZZ))
    events = list(
        run(
            "Where did acid jazz come from?", store=store, llm=llm, registry=default_registry(store)
        )
    )

    assert isinstance(events[0], Planned)
    assert events[0].plan.query_kind == "origins"
    assert [step.tool for step in events[0].plan.steps] == ["resolve_node", "get_influences"]


def test_a_plan_that_will_not_parse_still_produces_an_answer(store: InMemoryGraphStore) -> None:
    """The plan is a proposal, so losing it costs the run its plan and nothing else. A model that
    answers the planning turn with prose must not take the answer down with it."""
    script = resolve_then_influences("acid jazz", ACID_JAZZ)
    script[0] = LLMResponse(text="I would rather just answer the question.", usage=Usage(80, 15))
    events = list(
        run(
            "Where did acid jazz come from?",
            store=store,
            llm=ScriptedLLM(script),
            registry=default_registry(store),
        )
    )

    planned = next(e for e in events if isinstance(e, Planned))
    assert planned.plan == Plan(), "an unparseable plan must degrade, not raise"
    assert planned.plan.query_kind == UNKNOWN_QUERY_KIND
    assert [e.claim for e in events if isinstance(e, ClaimApproved)], "the run lost its answer too"
    assert not [e for e in events if isinstance(e, Refused)]


def test_a_plan_naming_an_unregistered_tool_is_reported_and_the_run_continues(
    store: InMemoryGraphStore,
) -> None:
    """Reported, not crashed on — the same posture ``ToolRegistry.invoke`` takes for a tool the model
    actually calls. Here it never calls it; it only said it would."""
    script = resolve_then_influences("acid jazz", ACID_JAZZ)
    script[0] = plan_turn("origins", "resolve_node", "consult_the_oracle")
    events = list(
        run(
            "Where did acid jazz come from?",
            store=store,
            llm=ScriptedLLM(script),
            registry=default_registry(store),
        )
    )

    assert next(e for e in events if isinstance(e, Planned)).unregistered == ("consult_the_oracle",)
    assert [e.claim for e in events if isinstance(e, ClaimApproved)]


def test_the_loop_executes_what_the_model_calls_not_what_the_plan_said(
    store: InMemoryGraphStore,
) -> None:
    """**The plan is not a control-flow mechanism**, and this is that claim as an assertion.

    The plan names one tool; the model then calls two entirely different ones. The loop follows the
    model. If a later change makes execution follow the plan instead, the plan has become a second
    ungated way for the model to steer the answer and this test is what catches it.
    """
    script = resolve_then_influences("acid jazz", ACID_JAZZ)
    script[0] = plan_turn("coverage", "corpus_coverage")
    events = list(
        run(
            "Where did acid jazz come from?",
            store=store,
            llm=ScriptedLLM(script),
            registry=default_registry(store),
        )
    )

    called = [e.name for e in events if isinstance(e, ToolCalled)]
    assert called == ["resolve_node", "get_influences"]
    assert "corpus_coverage" not in called


def test_done_carries_planned_and_executed_counts(store: InMemoryGraphStore) -> None:
    """**Divergence is data, not an error.** The plan says one step; the model takes two; the run
    reports both rather than the loop deciding one of them is wrong. Phase 4 computes plan adherence
    from exactly this pair."""
    script = resolve_then_influences("acid jazz", ACID_JAZZ)
    script[0] = plan_turn("origins", "resolve_node")
    events = list(
        run(
            "Where did acid jazz come from?",
            store=store,
            llm=ScriptedLLM(script),
            registry=default_registry(store),
        )
    )

    done = next(e for e in events if isinstance(e, Done))
    assert done.planned_steps == 1
    assert done.executed_steps == 2


def test_the_planning_turn_is_not_shown_the_toolbox(store: InMemoryGraphStore) -> None:
    """It is asked for JSON, not for tool use. Handing it the tool config invites a model to start
    walking mid-plan, which spends a turn and produces a tool call nothing has planned for."""
    llm = ScriptedLLM(resolve_then_influences("acid jazz", ACID_JAZZ))
    list(
        run(
            "Where did acid jazz come from?", store=store, llm=llm, registry=default_registry(store)
        )
    )

    planning_request = llm.requests[0]
    assert planning_request["tool_config"] is None
    assert PLANNING_SENTINEL in planning_request["system"]


def test_the_plan_turn_is_billed(store: InMemoryGraphStore) -> None:
    """An extra model turn on every query is a real cost, and whether it earns it is an open question
    the phase names. It cannot be answered if the turn's tokens are missing from the total."""
    llm = ScriptedLLM(resolve_then_influences("acid jazz", ACID_JAZZ))
    events = list(
        run(
            "Where did acid jazz come from?", store=store, llm=llm, registry=default_registry(store)
        )
    )

    done = next(e for e in events if isinstance(e, Done))
    assert done.usage.input_tokens >= 80 + 100 + 150 + 200
    assert done.usage.output_tokens >= 15 + 20 + 25 + 30


def test_max_turns_default_is_small(store: InMemoryGraphStore) -> None:
    """Raised 5 -> 6 at phase 3 step 3 for the plan turn, so the execution budget is unchanged at 5.
    Step 4 takes it to 8 and pairs it with a token budget; until then the turn count is the only cost
    control here, so the ceiling stays where the work actually needs it."""
    assert agent_loop.MAX_TURNS <= 6, "an agentic loop's turn ceiling is a cost control"


# --- DoD #13: a backwards premise ------------------------------------------------------------------
#
# The property under test is stated positively and so is the prose. "Heavy metal did not influence the
# blues" is a NEGATIVE claim, and 542 of the corpus's 973 nodes have no outgoing edges at all, so a
# missing edge is overwhelmingly not evidence of a missing influence. The correction may only select a
# framing for a chain the gate already approved; it may never assert the direction the graph lacks.


def premise_names(dataset_case: dict[str, Any]) -> tuple[str, str]:
    """A case's asserted premise as the two labels the question used."""
    subject_id, _, object_id = dataset_case["expected"]["premise_correction"]["asserted"]
    return subject_id, object_id


@pytest.fixture(scope="module")
def inversion_cases() -> dict[str, dict[str, Any]]:
    """``adv_012`` and ``adv_013``, read from the frozen set rather than restated here.

    Restating the forbidden phrasings in this file would let the dataset and the check drift apart,
    and the dataset is the artefact the eval suite scores against — so it is the one that governs.
    """
    path = Path(musical_mycelium.__file__).parent / "eval" / "datasets" / "adversarial_v1.json"
    cases = json.loads(path.read_text(encoding="utf-8"))["cases"]
    return {
        case["case_id"]: case for case in cases if "premise_correction" in case.get("expected", {})
    }


def synthesis_prompt(llm: ScriptedLLM) -> str:
    """The synthesis prompt as text. ``str(messages)`` is fine for a short substring and useless for a
    multi-line constant, because the repr escapes the newlines."""
    messages = llm.requests[-1]["messages"]
    return str(messages[0]["content"][0]["text"])


def test_descent_is_approved_follows_claim_orientation() -> None:
    """One hop, two hops, and never backwards. A claim ``(s, o)`` means *s came out of o*."""
    claims = (
        Claim(HEAVY_METAL, INFLUENCED_BY, BLUES_ROCK, ("stmt/1",)),
        Claim(BLUES_ROCK, INFLUENCED_BY, BLUES, ("stmt/2",)),
    )
    assert agent_loop.descent_is_approved(HEAVY_METAL, BLUES_ROCK, claims), "one hop"
    assert agent_loop.descent_is_approved(HEAVY_METAL, BLUES, claims), "two hops"
    assert not agent_loop.descent_is_approved(BLUES, HEAVY_METAL, claims), "backwards"
    assert not agent_loop.descent_is_approved(BLUES, BLUES, claims), (
        "a node is not its own ancestor"
    )
    assert not agent_loop.descent_is_approved(HEAVY_METAL, ACID_JAZZ, claims), "unrelated"


def test_descent_is_approved_terminates_on_a_cycle() -> None:
    """Musical influence is not acyclic and the corpus does not promise it is. A pair of claims
    pointing at each other must return an answer rather than walk forever."""
    claims = (
        Claim(BLUES_ROCK, INFLUENCED_BY, BLUES, ("stmt/1",)),
        Claim(BLUES, INFLUENCED_BY, BLUES_ROCK, ("stmt/2",)),
    )
    assert agent_loop.descent_is_approved(BLUES_ROCK, BLUES, claims)
    assert not agent_loop.descent_is_approved(BLUES_ROCK, HEAVY_METAL, claims)


def test_claim_set_rejects_an_inverted_premise_the_claims_do_not_reverse() -> None:
    """The same leak-proofing ``chain`` gets, for the same reason. A correction the gate did not
    produce cannot be constructed, so the framing can never outrun the claim set."""
    claims = (Claim(BLUES_ROCK, INFLUENCED_BY, BLUES, ("stmt/1",)),)
    with pytest.raises(ValueError, match="not established in reverse"):
        ApprovedClaimSet(claims=claims, inverted_premise=(BLUES, HEAVY_METAL))


def test_claim_set_rejects_an_inverted_premise_the_claims_state_forwards() -> None:
    """The nastier direction error. If the approved claims say the question was RIGHT, framing the
    answer as a reversal tells a user they had it backwards when they did not."""
    claims = (Claim(BLUES_ROCK, INFLUENCED_BY, BLUES, ("stmt/1",)),)
    with pytest.raises(ValueError, match="not established in reverse"):
        ApprovedClaimSet(claims=claims, inverted_premise=(BLUES_ROCK, BLUES))


def test_claim_set_accepts_an_inverted_premise_the_claims_reverse() -> None:
    claims = (
        Claim(HEAVY_METAL, INFLUENCED_BY, BLUES_ROCK, ("stmt/1",)),
        Claim(BLUES_ROCK, INFLUENCED_BY, BLUES, ("stmt/2",)),
    )
    claim_set = ApprovedClaimSet(claims=claims, inverted_premise=(BLUES, HEAVY_METAL))
    assert claim_set.inverted_premise == (BLUES, HEAVY_METAL)


def test_claim_set_rejects_a_malformed_inverted_premise() -> None:
    claims = (Claim(HEAVY_METAL, INFLUENCED_BY, BLUES, ("stmt/1",)),)
    with pytest.raises(ValueError, match="not established in reverse"):
        ApprovedClaimSet(claims=claims, inverted_premise=(BLUES,))


def test_premise_proposal_resolves_the_names_the_question_used(
    store: InMemoryGraphStore,
) -> None:
    """ "the blues" and "heavy metal" are not labels in this corpus — the labels are "blues" and "heavy
    metal music". The premise resolves through the same rule the traversal did, or not at all."""
    plan = Plan(asserted_premise=PremiseAssertion(subject="the blues", object="heavy metal"))
    proposal = agent_loop.premise_proposal(plan, store)
    assert proposal == ClaimProposal(BLUES, INFLUENCED_BY, HEAVY_METAL)


@pytest.mark.parametrize(
    "premise",
    [
        PremiseAssertion(subject="the blues", object="skiffle-adjacent nonsense"),
        PremiseAssertion(subject="not a genre at all", object="heavy metal"),
    ],
)
def test_an_unresolvable_premise_is_no_premise(
    store: InMemoryGraphStore, premise: PremiseAssertion
) -> None:
    """The degraded outcome is silence. Missing a backwards question costs a slightly worse answer;
    inventing one tells a user they asked something they did not."""
    assert agent_loop.premise_proposal(Plan(asserted_premise=premise), store) is None


def test_no_premise_asserted_means_no_proposal(store: InMemoryGraphStore) -> None:
    assert agent_loop.premise_proposal(Plan(), store) is None


def inversion_script(
    names: tuple[str, str], ids: tuple[str, str], premise: tuple[str, str] | None
) -> list[LLMResponse]:
    """Resolve both names, trace between them, having asserted the question's premise in the plan.

    ``trace_lineage`` is handed the two ids **in the order the question put them**, which is the
    inverted order — and it self-corrects, returning the chain descendant-first regardless. That is
    precisely why the premise cannot be inferred here and has to be asserted in the plan.
    """
    return [
        plan_turn("lineage", "resolve_node", "resolve_node", "trace_lineage", premise=premise),
        LLMResponse(
            tool_uses=(ToolUse(id="r1", name="resolve_node", arguments={"name": names[0]}),),
            stop_reason="tool_use",
        ),
        LLMResponse(
            tool_uses=(ToolUse(id="r2", name="resolve_node", arguments={"name": names[1]}),),
            stop_reason="tool_use",
        ),
        LLMResponse(
            tool_uses=(
                ToolUse(
                    id="t1",
                    name="trace_lineage",
                    arguments={"from_id": ids[0], "to_id": ids[1]},
                ),
            ),
            stop_reason="tool_use",
        ),
        LLMResponse(text="done"),
        LLMResponse(text="prose"),
    ]


def test_a_backwards_premise_is_gated_like_any_other_proposal(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """No special path. The premise comes back as an ordinary ``ClaimRejected`` with an ordinary
    reason, which is what makes it measurable next to every other rejection the gate reports."""
    llm = ScriptedLLM(
        inversion_script(
            ("the blues", "heavy metal"), (BLUES, HEAVY_METAL), ("the blues", "heavy metal")
        )
    )
    events = list(
        run("Did heavy metal influence the blues?", store=store, llm=llm, registry=registry)
    )

    rejected = [e.rejection for e in events if isinstance(e, ClaimRejected)]
    assert ClaimProposal(BLUES, INFLUENCED_BY, HEAVY_METAL) in [r.proposal for r in rejected]
    assert RejectionReason.NOT_IN_GRAPH in [r.reason for r in rejected]


def test_a_backwards_premise_is_answered_with_the_documented_orientation(
    store: InMemoryGraphStore, registry: ToolRegistry, inversion_cases: dict[str, Any]
) -> None:
    """DoD #13 end to end, on ``adv_012``.

    The answer must state the direction this graph documents and must not deny the one it lacks. The
    forbidden phrasings come from the frozen set, so the dataset governs the check.
    """
    llm = ScriptedLLM(
        inversion_script(
            ("the blues", "heavy metal"), (BLUES, HEAVY_METAL), ("the blues", "heavy metal")
        )
    )
    events = list(
        run("Did heavy metal influence the blues?", store=store, llm=llm, registry=registry)
    )

    prompt = synthesis_prompt(llm)
    assert agent_loop.INVERTED_PREMISE_PROMPT in prompt, "the reversal framing was not requested"
    assert "Asked as: " in prompt
    # The instruction quotes the forbidden phrasing in order to forbid it, so scanning the PROMPT for
    # the dataset's ``forbidden_negation`` strings would fail on the sentence doing the forbidding.
    # The property is about what the user reads, so it is asserted on the prose below instead.
    assert '"did not influence"' in prompt, "the prompt must rule the negation out explicitly"

    documented = inversion_cases["adv_012"]["expected"]["premise_correction"][
        "documented_orientation"
    ]
    walked = next(e for e in events if isinstance(e, PathWalked))
    assert walked.chain == tuple(documented), "the answer must trace the direction the graph holds"


@pytest.mark.parametrize("case_id", ["adv_012", "adv_013"])
def test_the_prose_states_the_orientation_and_denies_nothing(
    store: InMemoryGraphStore, inversion_cases: dict[str, Any], case_id: str
) -> None:
    """DoD #13's actual promise, on the prose the user reads, at both inversion depths.

    ``v0.3.0-local`` ships on the local provider, so this is the one configuration anybody can run
    today and the framing has to survive it. The forbidden phrasings come from the frozen set: every
    one of them is a NEGATIVE claim, and a corpus where 542 of 973 nodes have no outgoing edges cannot
    support one. The answer may state the direction the graph documents and must say nothing at all
    about the direction it lacks.
    """
    correction = inversion_cases[case_id]["expected"]["premise_correction"]
    documented = correction["documented_orientation"]
    subject_id, _, object_id = correction["asserted"]

    claims = tuple(
        Claim(descendant, INFLUENCED_BY, ancestor, (f"stmt/{i}",))
        for i, (descendant, ancestor) in enumerate(pairwise(documented))
    )
    labels = {node_id: _label_of(store, node_id) for node_id in documented}
    claim_set = ApprovedClaimSet(
        claims=claims,
        labels=labels,
        chain=tuple(documented),
        inverted_premise=(subject_id, object_id),
    )
    prose = "".join(synthesize(claim_set, LocalLLM()))

    assert "the influence runs the other way" in prose.lower()
    # Walked with a moving cursor rather than compared by ``index``: "blues" is a prefix of "blues
    # rock", so a plain lookup finds the wrong occurrence and the check passes or fails by accident.
    cursor = 0
    for node_id in documented:
        found = prose.find(labels[node_id], cursor)
        assert found != -1, (
            f"{labels[node_id]!r} is missing or out of order; "
            f"the documented orientation must be stated descendant-first: {prose!r}"
        )
        cursor = found + len(labels[node_id])
    for phrase in correction["forbidden_negation"]:
        assert phrase.lower() not in prose.lower(), f"the prose denies: {phrase!r}"


def _label_of(store: InMemoryGraphStore, node_id: str) -> str:
    node = store.get_node(node_id)
    assert node is not None, f"{node_id} is not in the pinned artifact"
    return node.label


def test_a_one_hop_inversion_corrects_the_same_way(
    store: InMemoryGraphStore, registry: ToolRegistry, inversion_cases: dict[str, Any]
) -> None:
    """``adv_013``, paired with ``adv_012`` at a different depth on purpose: a one-hop and a two-hop
    inversion fail differently if the bug is in the reachability walk."""
    case = inversion_cases["adv_013"]
    subject_id, _, object_id = case["expected"]["premise_correction"]["asserted"]
    llm = ScriptedLLM(
        inversion_script(
            ("punk rock", "thrash metal"), (PUNK_ROCK, THRASH_METAL), ("punk rock", "thrash metal")
        )
    )
    events = list(
        run("Did punk rock come out of thrash metal?", store=store, llm=llm, registry=registry)
    )

    rejected = [e.rejection.proposal for e in events if isinstance(e, ClaimRejected)]
    assert ClaimProposal(subject_id, INFLUENCED_BY, object_id) in rejected

    assert agent_loop.INVERTED_PREMISE_PROMPT in synthesis_prompt(llm)
    walked = next(e for e in events if isinstance(e, PathWalked))
    assert walked.chain == tuple(case["expected"]["premise_correction"]["documented_orientation"])


def test_a_neutral_question_gets_no_reversal_framing(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """The failure mode the model-asserted design exists to prevent.

    "How is the blues connected to heavy metal?" asserts nothing, and ``trace_lineage`` self-corrects
    inverted arguments — so a system that inferred the premise from argument order would tell this user
    they had it backwards when they never put it any way at all.
    """
    llm = ScriptedLLM(inversion_script(("the blues", "heavy metal"), (BLUES, HEAVY_METAL), None))
    list(run("How is the blues connected to heavy metal?", store=store, llm=llm, registry=registry))

    prompt = synthesis_prompt(llm)
    assert agent_loop.INVERTED_PREMISE_PROMPT not in prompt
    assert "Asked as: " not in prompt


def test_a_premise_the_gate_approves_gets_no_reversal_framing(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """A user who had it right is told they had it right, by not being told anything."""
    llm = ScriptedLLM(
        inversion_script(
            ("thrash metal", "punk rock"), (THRASH_METAL, PUNK_ROCK), ("thrash metal", "punk rock")
        )
    )
    events = list(
        run("Did thrash metal come out of punk rock?", store=store, llm=llm, registry=registry)
    )

    approved = [e.claim.triple for e in events if isinstance(e, ClaimApproved)]
    assert ("Q483352", INFLUENCED_BY, "Q3071") in approved, "the premise itself was approved"
    assert agent_loop.INVERTED_PREMISE_PROMPT not in synthesis_prompt(llm)


def test_a_rejected_premise_with_no_reverse_is_an_ordinary_refusal(
    store: InMemoryGraphStore,
) -> None:
    """Both conditions, not one. "Did polka influence hip hop?" has nothing to correct, and dressing
    the refusal up as a reversal would assert a direction nobody sourced."""
    premise = ClaimProposal(BLUES, INFLUENCED_BY, HEAVY_METAL)
    decision = gate([premise], store)
    assert agent_loop._inverted_premise(premise, decision) == ()
