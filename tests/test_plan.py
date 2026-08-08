"""The traversal plan object, its prompt, and its parser.

Two properties here are load-bearing beyond ordinary correctness.

``test_the_planning_prompt_names_every_registered_tool`` together with the widened
``test_no_prompt_names_a_tool`` in ``test_agent_loop.py`` is **invariant 4 through the prose door**: the
prompt template must name no tool, and the rendered prompt must name all of them, because the list comes
from the registry. An eighth tool then appears in the plan prompt the day it is registered, with no edit
here or in ``loop.py``.

``test_unknown_keys_are_ignored`` is what keeps this object cheap to extend. Step 3's premise correction
adds a field; a parser that rejected unrecognised keys would make that a breaking change to every
scripted plan in the suite.

All of it is deterministic, free, and network-free — Tier 1, safe on every commit.
"""

from __future__ import annotations

import json
from typing import Any

import pytest

from musical_mycelium.agent.llm import PLANNING_SENTINEL
from musical_mycelium.agent.plan import (
    MAX_REASON_CHARS,
    PLANNING_PROMPT_TEMPLATE,
    QUERY_KINDS,
    UNKNOWN_QUERY_KIND,
    Plan,
    PlanStep,
    PremiseAssertion,
    parse_plan,
    planning_prompt,
)
from musical_mycelium.agent.tools import ToolRegistry, ToolResult, default_registry
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture
def registry(store: InMemoryGraphStore) -> ToolRegistry:
    return default_registry(store)


WELL_FORMED = json.dumps(
    {
        "query_kind": "lineage",
        "steps": [
            {"tool": "resolve_node", "reason": "resolve the first name", "arguments": {}},
            {
                "tool": "trace_lineage",
                "reason": "walk between them",
                "arguments": {"from_id": "Q9759"},
            },
        ],
    }
)


# --- the prompt -----------------------------------------------------------------------------------


def test_the_planning_prompt_names_every_registered_tool(registry: ToolRegistry) -> None:
    """Invariant 4's prose door, from the other side. The template names nothing; the rendered prompt
    names everything, because the list is read off the registry rather than written down."""
    prompt = planning_prompt(registry)
    for name in registry.names:
        assert name in prompt, f"{name} is registered but absent from the plan prompt"
        assert name not in PLANNING_PROMPT_TEMPLATE, f"the template hard-codes {name}"


def test_a_tool_registered_later_appears_in_the_prompt_without_an_edit(
    registry: ToolRegistry,
) -> None:
    class Invented:
        name = "invented_tool"
        description = "Something no version of this prompt was written to know about."

        def input_schema(self) -> dict[str, Any]:
            return {"type": "object", "properties": {}}

        def __call__(self, **kwargs: Any) -> ToolResult:  # pragma: no cover - never invoked
            raise AssertionError("this tool is registered for the prompt, not to be called")

    assert "invented_tool" not in planning_prompt(registry)
    registry.register(Invented())
    prompt = planning_prompt(registry)
    assert "invented_tool" in prompt
    assert "Something no version of this prompt" in prompt, (
        "the description travels, not just the name"
    )


def test_the_prompt_carries_the_sentinel_the_local_fixture_keys_off() -> None:
    """``LocalLLM`` distinguishes a planning turn from a tool turn by this string. If the prompt is
    reworded past it, ``make dev`` and the deployed local-provider demo stop planning and nothing else
    fails — which is the kind of silent break a test is for."""
    assert PLANNING_SENTINEL in PLANNING_PROMPT_TEMPLATE


def test_the_shape_the_prompt_asks_for_is_a_shape_the_parser_accepts(
    registry: ToolRegistry,
) -> None:
    """Prompt and parser, locked together rather than maintained in parallel.

    The rendered prompt's only braces are its JSON example, so feeding the whole prompt to ``parse_plan``
    reads exactly that example back. It catches the two failures that matter and would otherwise be
    invisible: the doubled braces that survive ``str.format`` getting written wrong, and the example
    drifting to a ``query_kind`` the validator does not accept — either of which makes every real model
    copy a shape that degrades to the empty plan.
    """
    plan = parse_plan(planning_prompt(registry))
    assert plan.query_kind in QUERY_KINDS
    assert plan.query_kind != UNKNOWN_QUERY_KIND, "the example demonstrates the degraded value"
    assert len(plan.steps) == 1
    assert plan.steps[0].arguments == {}
    # Step 3b's field is in the example, so the same lock covers it: a premise example that stopped
    # parsing would make every real model copy a shape the loop silently drops.
    assert plan.asserted_premise is not None
    assert plan.asserted_premise.subject and plan.asserted_premise.object


# --- parsing: the good case -----------------------------------------------------------------------


def test_a_well_formed_plan_parses() -> None:
    plan = parse_plan(WELL_FORMED)
    assert plan.query_kind == "lineage"
    assert [step.tool for step in plan.steps] == ["resolve_node", "trace_lineage"]
    assert plan.steps[0].reason == "resolve the first name"
    assert plan.steps[1].arguments == {"from_id": "Q9759"}


def test_a_fenced_plan_parses() -> None:
    """Models wrap JSON in markdown fences whatever the prompt says. One brace-slicing rule absorbs
    fences, a preamble and a sign-off together, rather than a special case per wrapper."""
    assert parse_plan(f"```json\n{WELL_FORMED}\n```").query_kind == "lineage"


def test_a_plan_with_a_preamble_and_a_signoff_parses() -> None:
    text = f"Sure, here is the plan.\n\n{WELL_FORMED}\n\nLet me know if you want changes."
    plan = parse_plan(text)
    assert plan.query_kind == "lineage"
    assert len(plan.steps) == 2


def test_every_query_kind_the_prompt_offers_is_accepted() -> None:
    """The prompt and the validator have to agree. If they drift, every run of one kind silently
    reports ``unknown`` and DoD #7's query-type slice loses a whole category without erroring."""
    for kind in QUERY_KINDS:
        assert parse_plan(json.dumps({"query_kind": kind, "steps": []})).query_kind == kind


# --- parsing: degradation -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "text",
    ["", "   ", "I cannot plan this.", "{", "}{", "not json {at all}", "[1, 2, 3]", '"a string"'],
)
def test_an_unusable_answer_degrades_to_the_empty_plan(text: str) -> None:
    """Never raises. The plan is a proposal and was never load-bearing, so a model that answers with
    prose costs the run its plan and nothing else."""
    plan = parse_plan(text)
    assert plan == Plan()
    assert plan.query_kind == UNKNOWN_QUERY_KIND


def test_query_kind_is_never_absent_even_when_the_plan_is_empty() -> None:
    """Property 2. A run with no ``query_kind`` cannot be sliced by query type, so the degraded value
    is ``unknown`` rather than ``None`` or a missing key."""
    assert parse_plan("garbage").query_kind == UNKNOWN_QUERY_KIND
    assert parse_plan(json.dumps({"steps": []})).query_kind == UNKNOWN_QUERY_KIND


def test_a_bogus_query_kind_does_not_discard_the_steps() -> None:
    """Fields are validated independently. One bad value dropping the whole plan is the failure mode
    that makes a plan object useless in practice."""
    plan = parse_plan(json.dumps({"query_kind": "vibes", "steps": [{"tool": "resolve_node"}]}))
    assert plan.query_kind == UNKNOWN_QUERY_KIND
    assert [step.tool for step in plan.steps] == ["resolve_node"]


def test_one_malformed_step_does_not_discard_the_others() -> None:
    plan = parse_plan(
        json.dumps(
            {
                "query_kind": "origins",
                "steps": [
                    {"tool": "resolve_node"},
                    "not a step",
                    {"reason": "a step with no tool is not a step"},
                    {"tool": "   "},
                    {"tool": "get_influences"},
                ],
            }
        )
    )
    assert [step.tool for step in plan.steps] == ["resolve_node", "get_influences"]


def test_steps_that_are_not_a_list_are_dropped_rather_than_crashing() -> None:
    assert parse_plan(json.dumps({"query_kind": "origins", "steps": "resolve_node"})).steps == ()


def test_non_dict_arguments_become_empty_rather_than_travelling() -> None:
    """``arguments`` reaches the SSE frame. A string where a mapping belongs would be rendered to a
    client as an argument map it cannot read."""
    plan = parse_plan(json.dumps({"steps": [{"tool": "resolve_node", "arguments": "blues"}]}))
    assert plan.steps[0].arguments == {}


def test_a_runaway_reason_is_collapsed_to_one_line_and_capped() -> None:
    """``reason`` is model-authored free text on the wire and is never read for control flow, so the
    cap is about frame size rather than meaning."""
    plan = parse_plan(
        json.dumps({"steps": [{"tool": "resolve_node", "reason": "why\nnot\n  " + "x" * 500}]})
    )
    reason = plan.steps[0].reason
    assert "\n" not in reason
    assert len(reason) == MAX_REASON_CHARS
    assert reason.startswith("why not ")


def test_unknown_keys_are_ignored() -> None:
    """Forward compatibility, deliberately, and it paid at step 3b.

    This test used ``asserted_premise`` as its unknown key until that field landed for real, which is
    the property working rather than the test going stale: adding it cost a paragraph and broke no
    scripted plan. The placeholders are now fields nothing emits, so the check keeps meaning something.
    """
    plan = parse_plan(
        json.dumps(
            {
                "query_kind": "origins",
                "steps": [{"tool": "resolve_node", "confidence": 0.9}],
                "estimated_cost": {"tokens": 400},
                "notes": "something a later version emits",
            }
        )
    )
    assert plan.query_kind == "origins"
    assert plan.steps == (PlanStep(tool="resolve_node"),)
    assert plan.asserted_premise is None


# --- parsing: the asserted premise ------------------------------------------------------------------


def test_an_asserted_premise_parses() -> None:
    plan = parse_plan(
        json.dumps(
            {
                "query_kind": "lineage",
                "asserted_premise": {"subject": "the blues", "object": "heavy metal"},
                "steps": [],
            }
        )
    )
    assert plan.asserted_premise == PremiseAssertion(subject="the blues", object="heavy metal")


def test_a_question_asserting_nothing_carries_no_premise() -> None:
    """The common case by a wide margin — "what did X come out of" assumes nothing to correct."""
    assert parse_plan(WELL_FORMED).asserted_premise is None


@pytest.mark.parametrize(
    ("payload", "why"),
    [
        ({"subject": "the blues"}, "object missing"),
        ({"object": "heavy metal"}, "subject missing"),
        ({"subject": "the blues", "object": ""}, "object blank"),
        ({"subject": "  ", "object": "heavy metal"}, "subject blank"),
        ({"subject": "the blues", "object": ["heavy metal"]}, "object not a string"),
        ("the blues came out of heavy metal", "not an object at all"),
        (None, "explicit null"),
    ],
)
def test_a_half_stated_premise_is_no_premise(payload: object, why: str) -> None:
    """Both names or neither. A premise missing one side is not a weaker premise, it is an unusable
    one, and filling the gap from the query would be exactly the inference this field exists to avoid:
    the whole point is that the model asserts the premise rather than anything guessing it."""
    plan = parse_plan(json.dumps({"query_kind": "lineage", "asserted_premise": payload}))
    assert plan.asserted_premise is None, why
    assert plan.query_kind == "lineage", "a bad premise must not discard the rest of the plan"


def test_premise_names_are_stripped() -> None:
    plan = parse_plan(
        json.dumps({"asserted_premise": {"subject": " the blues\n", "object": "\theavy metal "}})
    )
    assert plan.asserted_premise == PremiseAssertion(subject="the blues", object="heavy metal")


# --- unregistered tools ---------------------------------------------------------------------------


def test_a_plan_naming_a_tool_that_does_not_exist_is_reported_not_raised(
    registry: ToolRegistry,
) -> None:
    """The same posture ``ToolRegistry.invoke`` already takes. The plan never drives execution, so the
    model being wrong about its own toolbox is a measurement rather than a failure."""
    plan = parse_plan(
        json.dumps(
            {
                "query_kind": "origins",
                "steps": [
                    {"tool": "resolve_node"},
                    {"tool": "consult_the_oracle"},
                    {"tool": "consult_the_oracle"},
                    {"tool": "ask_a_friend"},
                ],
            }
        )
    )
    assert plan.unregistered(registry) == ("consult_the_oracle", "ask_a_friend")


def test_a_plan_using_only_real_tools_reports_nothing_unregistered(registry: ToolRegistry) -> None:
    assert parse_plan(WELL_FORMED).unregistered(registry) == ()
