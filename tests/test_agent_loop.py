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

from collections.abc import Iterator
from typing import Any

import pytest

from musical_mycelium.agent import loop as agent_loop
from musical_mycelium.agent.claims import Claim, ClaimProposal, RejectionReason
from musical_mycelium.agent.llm import (
    LLM,
    LLMResponse,
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
    Refused,
    Token,
    ToolCalled,
    refusal_text,
    run,
    synthesize,
)
from musical_mycelium.agent.tools import (
    GetInfluences,
    ResolveGenre,
    Tool,
    ToolRegistry,
    ToolResult,
    TraceLineage,
    default_registry,
)
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory

BLUES_ROCK, BLUES = "Q193355", "Q9759"
ACID_JAZZ, JAZZ = "Q221772", "Q8341"
HEAVY_METAL = "Q38848"
INFLUENCED_BY = "influenced_by"


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture
def registry(store: InMemoryGraphStore) -> ToolRegistry:
    return default_registry(store)


def resolve_then_influences(name: str, node_id: str) -> list[LLMResponse]:
    """The two tool turns v0.1 expects, then a final text turn."""
    return [
        LLMResponse(
            tool_uses=(ToolUse(id="t1", name="resolve_genre", arguments={"name": name}),),
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
    assert isinstance(ResolveGenre(store), Tool)
    assert isinstance(GetInfluences(store), Tool)
    assert isinstance(TraceLineage(store), Tool)


def test_tool_config_is_the_bedrock_shape(registry: ToolRegistry) -> None:
    specs = registry.tool_config()["tools"]
    assert {s["toolSpec"]["name"] for s in specs} == {
        "resolve_genre",
        "get_influences",
        "trace_lineage",
    }
    for spec in specs:
        assert spec["toolSpec"]["description"]
        assert spec["toolSpec"]["inputSchema"]["json"]["type"] == "object"


def test_the_system_prompt_names_no_tool(store: InMemoryGraphStore) -> None:
    """Invariant 4 has a prose door as well as a code one.

    v0.1's system prompt hard-coded "use resolve_genre, then get_influences", so a third tool could be
    registered without a loop edit and still never be called. A tool describes itself in its own spec;
    the system prompt states the rules.
    """
    for name in default_registry(store).names:
        assert name not in agent_loop.SYSTEM_PROMPT, f"the system prompt hard-codes {name}"


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
    registry.register(CountGenres())
    assert len(registry) == 4

    llm = ScriptedLLM(
        [
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
        registry.register(ResolveGenre(store))


def test_an_unknown_tool_is_an_error_result_not_an_exception(registry: ToolRegistry) -> None:
    """The model gets told what went wrong and can correct. A raise would kill the run instead."""
    result = registry.invoke("teleport", {})
    assert result.is_error
    assert "no such tool" in result.content["error"]


def test_bad_arguments_are_an_error_result(registry: ToolRegistry) -> None:
    assert registry.invoke("resolve_genre", {"wrong": "arg"}).is_error


# --- tools: honest absence ----------------------------------------------------------------------


def test_resolve_genre_returns_null_for_an_unknown_genre(registry: ToolRegistry) -> None:
    assert registry.invoke("resolve_genre", {"name": "bebop"}).content["node_id"] is None


def test_resolve_genre_refuses_a_near_miss_rather_than_guessing(registry: ToolRegistry) -> None:
    """``blues r`` must not silently resolve to ``blues rock``. It offers alternatives instead — a
    confident wrong resolution answers a question nobody asked, with citations attached."""
    result = registry.invoke("resolve_genre", {"name": "metal"})
    assert result.content["node_id"] is None
    assert "did_you_mean" in result.content


def test_resolve_genre_resolves_an_exact_match(registry: ToolRegistry) -> None:
    result = registry.invoke("resolve_genre", {"name": "the blues"})
    assert result.content["node_id"] == BLUES
    assert result.visited == (BLUES,)


def test_resolve_genre_tolerates_wikidatas_trailing_music(registry: ToolRegistry) -> None:
    """32 of the 169 nodes are labelled "<name> music" and nobody types the suffix. Both spellings must
    reach the same node, and neither is a guess — the fold is documented and applied to both sides."""
    assert (
        registry.invoke("resolve_genre", {"name": "heavy metal"}).content["node_id"] == HEAVY_METAL
    )
    assert (
        registry.invoke("resolve_genre", {"name": "heavy metal music"}).content["node_id"]
        == HEAVY_METAL
    )


def test_the_music_fold_still_refuses_a_genuine_near_miss(registry: ToolRegistry) -> None:
    """The fold must not become fuzzy matching by increments. "metal" is still not a genre in here."""
    assert registry.invoke("resolve_genre", {"name": "metal"}).content["node_id"] is None
    assert registry.invoke("resolve_genre", {"name": "blues r"}).content["node_id"] is None


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
                                "name": "resolve_genre",
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
    assert parsed.tool_uses[0].name == "resolve_genre"
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
    assert called == ["resolve_genre", "resolve_genre", "trace_lineage"]

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
            LLMResponse(
                tool_uses=(
                    ToolUse(id="t1", name="resolve_genre", arguments={"name": "the blues"}),
                ),
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
            LLMResponse(
                tool_uses=(ToolUse(id="t1", name="resolve_genre", arguments={"name": "bebop"}),),
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
                tool_uses=(ToolUse(id="t", name="resolve_genre", arguments={"name": "jazz"}),),
                stop_reason="tool_use",
            )

    generator = endless()
    llm = ScriptedLLM([next(generator) for _ in range(20)])
    events = list(
        run(
            "loop forever",
            store=store,
            llm=llm,
            registry=default_registry(store),
            max_turns=3,
        )
    )
    assert len([e for e in events if isinstance(e, ToolCalled)]) == 3
    assert any(isinstance(e, Done) for e in events)


def test_max_turns_default_is_small(store: InMemoryGraphStore) -> None:
    assert agent_loop.MAX_TURNS <= 5, "an agentic loop's turn ceiling is a cost control"
