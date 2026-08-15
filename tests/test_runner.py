"""Runner tests — written after the extraction's intended lock turned out not to be a lock.

The plan for phase 4 step 1 said the baseline drift test would catch any behaviour change in the
extraction. It does not. A deliberately perturbed runner that dropped the last node from every walked
path passed all 852 tests, because ``CaseOutcome.visited`` is recorded in the baseline's inputs and read
by nothing — which is the same root cause as ``traversal_recall`` never having been scored on any run
until 2026-08-12. Data that no assertion consumes is data that can silently rot.

So the lock is here instead, and it is the specific one: **what the loop emitted is what the runner
reports, field by field.** Each test below was confirmed to fail against a perturbed runner before
being kept.
"""

from __future__ import annotations

import json

import pytest

from musical_mycelium.agent.llm import LLMResponse, ScriptedLLM, ToolUse, Usage
from musical_mycelium.agent.loop import PathWalked, run
from musical_mycelium.agent.tools import default_registry
from musical_mycelium.eval import runner
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.store import GraphStore


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


#: ``blues rock -> blues``, the simplest chain in the corpus and gold case 001. The two-tool shape is
#: not decoration: ``visited`` is built from **tool results**, not from the query text, so a script that
#: skips ``resolve_node`` and jumps to a node id walks nothing and the run refuses. That cost three
#: failing tests to learn and is why it is written down here.
BLUES_ROCK: tuple[tuple[str, dict[str, object]], ...] = (
    ("resolve_node", {"name": "blues rock"}),
    ("get_influences", {"node_id": "Q193355"}),
)


def _script(
    query_kind: str = "origins",
    *,
    tools: tuple[tuple[str, dict[str, object]], ...] = (),
) -> list[LLMResponse]:
    """A plan turn, the tool turns, a closing text turn, then the synthesis stream.

    The plan turn is always first. A script without one does not fail — its first tool turn is eaten by
    the planner and the run exercises the wrong sequence, which is how two tests once went green on the
    wrong thing.
    """
    script = [
        LLMResponse(
            text=json.dumps({"query_kind": query_kind, "steps": [{"tool": n} for n, _ in tools]}),
            usage=Usage(80, 15),
        )
    ]
    for index, (name, arguments) in enumerate(tools):
        script.append(
            LLMResponse(
                tool_uses=(ToolUse(id=f"t{index}", name=name, arguments=arguments),),
                stop_reason="tool_use",
                usage=Usage(120, 20),
            )
        )
    script.append(LLMResponse(text="Done looking.", stop_reason="end_turn", usage=Usage(150, 25)))
    script.append(LLMResponse(text="Some prose."))
    return script


# --- the transcript is faithful ----------------------------------------------------------------------


def test_the_runner_reports_exactly_the_nodes_the_loop_walked(store: GraphStore) -> None:
    """The test the drift lock was assumed to be. It compares against the ``PathWalked`` event itself
    rather than a hardcoded list, so it stays true if the corpus or the traversal changes and stays
    false the moment the runner edits what it was handed."""
    query = "Where did blues rock come from?"
    script = _script(tools=BLUES_ROCK)

    walked = tuple(
        event.node_ids
        for event in run(
            query,
            llm=ScriptedLLM(_script(tools=BLUES_ROCK)),
            store=store,
            registry=default_registry(store),
        )
        if isinstance(event, PathWalked)
    )

    case_run = runner.run_case(query, store=store, llm=ScriptedLLM(script))
    assert walked, (
        "the fixture stopped emitting PathWalked; this test is no longer measuring anything"
    )
    assert case_run.visited == walked[-1]


def test_the_runner_keeps_the_whole_path_not_a_truncation(store: GraphStore) -> None:
    """A path that loses an endpoint scores a plausible-looking partial recall rather than an error.
    ``blues rock -> blues`` is the simplest chain in the corpus and both ends must survive."""
    case_run = runner.run_case(
        "Where did blues rock come from?",
        store=store,
        llm=ScriptedLLM(_script(tools=BLUES_ROCK)),
    )
    assert "Q193355" in case_run.visited


def test_prose_is_only_the_token_stream(store: GraphStore) -> None:
    """Prose comes from ``Token`` events and nothing else.

    **Stated honestly, because it was checked: this test cannot currently fail from the change it
    guards.** The old harness collected any event carrying a ``.text`` attribute, and ``Token`` is the
    only event that has one, so the two are equivalent today — restoring the catch-all leaves this test
    green. What it does catch is prose collection breaking outright, and what it documents is that the
    explicit match is deliberate: a future event type with a ``text`` field would leak into the
    narrative under a catch-all, and prose is the one place in this project where what may reach it is
    a structural rule rather than a preference. If such an event is ever added, this test needs a case
    that uses it."""
    case_run = runner.run_case(
        "Where did blues rock come from?",
        store=store,
        llm=ScriptedLLM(_script(tools=BLUES_ROCK)),
    )
    assert case_run.prose == "Some prose."
    assert "Done looking." not in case_run.prose


def test_the_plan_and_its_unregistered_tools_both_survive(store: GraphStore) -> None:
    """A plan naming a tool that does not exist is a measurement, not a failure — but only if it is
    carried out of the run. It was dropped entirely before this extraction."""
    script = [
        LLMResponse(
            text=json.dumps({"query_kind": "origins", "steps": [{"tool": "teleport"}]}),
            usage=Usage(80, 15),
        ),
        LLMResponse(text="Done looking.", stop_reason="end_turn", usage=Usage(150, 25)),
        LLMResponse(text="Some prose."),
    ]
    case_run = runner.run_case(
        "Where did blues rock come from?", store=store, llm=ScriptedLLM(script)
    )
    assert case_run.unregistered == ("teleport",)


def test_a_refusal_carries_its_reason(store: GraphStore) -> None:
    """Refusal is correct behaviour, and reporting refusal accuracy needs the reason as well as the
    fact. ``techno`` has zero edges in the pinned corpus, so it refuses by construction."""
    case_run = runner.run_case(
        "Where did Detroit techno come from?",
        store=store,
        llm=ScriptedLLM(_script()),
    )
    assert case_run.refused
    assert case_run.refusal_reason.strip()


# --- the failure modes fail loudly -------------------------------------------------------------------


def test_a_run_with_no_done_event_raises_rather_than_reporting_zero(store: GraphStore) -> None:
    """The vacuous-truth guard's shape, one layer up. A loop that ends without a ``Done`` has no usage
    and no claim count, and every metric computed from it would still return a number — a confident
    zero indistinguishable from a model that found nothing."""

    def _no_done(*_args: object, **_kwargs: object) -> object:
        return iter(())

    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(runner, "run", _no_done)
        with pytest.raises(runner.RunIncomplete):
            runner.run_case(
                "Where did blues rock come from?", store=store, llm=ScriptedLLM(_script())
            )


# --- the accounting -----------------------------------------------------------------------------------


def test_total_tokens_sums_traversal_and_synthesis(store: GraphStore) -> None:
    """Summed here and nowhere else. ``Done`` keeps the two halves apart because two models price
    differently; this property exists for the token budget, which counts tokens against a per-model
    daily cap and asks no question about dollars."""
    case_run = runner.run_case(
        "Where did blues rock come from?",
        store=store,
        llm=ScriptedLLM(_script(tools=BLUES_ROCK)),
    )
    assert case_run.total_tokens == (
        case_run.traversal_usage.total_tokens + case_run.synthesis_usage.total_tokens
    )
    assert case_run.total_tokens > 0


def test_a_complete_run_is_not_reported_as_truncated(store: GraphStore) -> None:
    case_run = runner.run_case(
        "Where did blues rock come from?",
        store=store,
        llm=ScriptedLLM(_script(tools=BLUES_ROCK)),
    )
    assert not case_run.truncated
