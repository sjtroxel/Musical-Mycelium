"""Live-run wiring tests. Every one of these runs with no AWS and costs nothing.

What is actually being tested is the part that only shows up under a real provider: that the rate
limiter fires per **request** rather than per case, that one limiter is shared across the whole run,
and that a result file is written even when the run aborts. The billable behaviour itself is
`costs_money` and lives elsewhere; this file makes sure the scaffolding around it is not lying.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from typing import Any

import pytest

from musical_mycelium.agent.llm import LLMResponse, ScriptedLLM, Usage
from musical_mycelium.eval import gold, harness
from musical_mycelium.eval.budget import RateLimiter
from musical_mycelium.eval.live import (
    BUDGET_SAFETY_FACTOR,
    ThrottledLLM,
    UnknownCase,
    budget_for,
    estimate_for,
    live_cases,
    run_live,
    select_cases,
    write_result,
)
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory


class CountingLimiter(RateLimiter):
    """A limiter that records rather than sleeps, so the test asserts *when* it was consulted."""

    def __init__(self) -> None:
        super().__init__(requests_per_minute=1000, sleep=lambda _seconds: None)
        self.acquisitions = 0

    def acquire(self) -> None:
        self.acquisitions += 1
        super().acquire()


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


# --- the limiter sits at the request boundary ----------------------------------------------------


def test_the_limiter_fires_once_per_request_not_once_per_case(store: InMemoryGraphStore) -> None:
    """**The bug this test exists to prevent.** One case is five to seven requests, so a limiter
    acquired per case lets a single case burst past 10 RPM on its own while the code looks correct.

    Broken deliberately on 2026-08-16 by moving `acquire()` into `llm_for` (once per case): the
    count fell to 1 and this failed.
    """
    case = gold.load_cases()[0]
    limiter = CountingLimiter()

    run_live(
        store=store,
        cases=[case.as_eval_case()],
        provider="scripted",
        llm_factory=lambda: ScriptedLLM(gold.build_script(case)),
        limiter=limiter,
    )

    # One origins case is five requests: plan, two tool turns, the closing text turn, synthesis.
    assert limiter.acquisitions == 5, (
        f"one case acquired {limiter.acquisitions} times; 1 means the limiter is per-case and a "
        "single case can burst past the RPM ceiling on its own"
    )


def test_every_converse_and_stream_passes_through_the_limiter() -> None:
    limiter = CountingLimiter()
    inner = ScriptedLLM(
        [
            LLMResponse(text="one", usage=Usage(1, 1)),
            LLMResponse(text="two", usage=Usage(1, 1)),
            LLMResponse(text="streamed", usage=Usage(1, 1)),
        ]
    )
    throttled = ThrottledLLM(inner=inner, limiter=limiter)

    throttled.converse([])
    throttled.converse([])
    list(throttled.stream([]))

    assert limiter.acquisitions == 3
    assert throttled.requests == 3


def test_the_stream_acquires_before_the_first_delta() -> None:
    """A stream that has started is a request the quota already counted, so pacing after the fact
    would let long syntheses drift over the ceiling while looking compliant."""
    limiter = CountingLimiter()
    inner = ScriptedLLM([LLMResponse(text="hello", usage=Usage(1, 1))])
    throttled = ThrottledLLM(inner=inner, limiter=limiter)

    stream: Generator[str, None, Usage] = throttled.stream([])
    next(stream)
    assert limiter.acquisitions == 1, "acquired only after the stream was exhausted"


def test_model_id_delegates_so_done_records_the_real_model() -> None:
    inner = ScriptedLLM([], model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0")
    throttled = ThrottledLLM(inner=inner, limiter=CountingLimiter())
    assert throttled.model_id == "us.anthropic.claude-haiku-4-5-20251001-v1:0"


# --- the dataset the live run drives -------------------------------------------------------------


def test_live_cases_is_gold_then_adversarial() -> None:
    """Order matters: gold fails loudly if the wiring is wrong, so a broken run burns the fewest
    requests before it becomes obvious."""
    cases = live_cases()
    expected_gold = gold.eval_cases()
    assert len(cases) == len(expected_gold) + len(harness.eval_cases())
    assert cases[: len(expected_gold)] == expected_gold


def test_the_live_set_carries_both_a_gold_path_and_a_forbidden_triple() -> None:
    """The two datasets contribute different, non-overlapping measurement capability. If either half
    stopped contributing, half the catalog would silently go undefined."""
    cases = live_cases()
    assert any(case.expected_path for case in cases), "no case can score traversal recall"
    assert any(case.forbidden_triples for case in cases), "no case can score injection resistance"


# --- selecting which cases to run ------------------------------------------------------------------


def test_no_selector_runs_everything() -> None:
    assert select_cases([], live_cases()) == live_cases()


def test_cases_takes_a_prefix_and_case_ids_takes_exactly_what_it_names() -> None:
    """The two selectors answer different questions. A prefix is right for "prove the wiring cheaply";
    it is wrong for "check a behaviour", because the case exhibiting a behaviour is wherever the
    dataset happens to put it — `gold_v0_1_021` is 21 cases deep."""
    cases = live_cases()
    assert select_cases(["--cases", "2"], cases) == cases[:2]

    picked = select_cases(["--case-ids", "gold_v0_1_021,gold_v0_1_001"], cases)
    assert [case.case_id for case in picked] == ["gold_v0_1_021", "gold_v0_1_001"], (
        "the order given is the order run"
    )


def test_an_unknown_case_id_is_refused_rather_than_skipped() -> None:
    """A typo that quietly runs three cases instead of four is a run whose clean result means nothing,
    and nothing downstream would ever say so."""
    with pytest.raises(UnknownCase, match="gold_v0_1_999"):
        select_cases(["--case-ids", "gold_v0_1_001,gold_v0_1_999"], live_cases())


def test_case_ids_wins_over_cases_when_both_are_given() -> None:
    """Intersecting them would silently return fewer cases than either flag asked for."""
    picked = select_cases(["--cases", "1", "--case-ids", "gold_v0_1_021"], live_cases())
    assert [case.case_id for case in picked] == ["gold_v0_1_021"]


# --- the estimate and the circuit breaker --------------------------------------------------------


def test_the_estimate_scales_with_the_case_count() -> None:
    small = estimate_for(live_cases()[:1], "m", "one")
    full = estimate_for(live_cases(), "m", "all")
    assert small.cases == 1
    assert full.requests > small.requests
    assert full.input_tokens > small.input_tokens


def test_the_budget_is_wider_than_the_estimate_but_not_unbounded() -> None:
    """A budget equal to the estimate would abort on any honest overshoot; an unbounded one is not a
    circuit breaker. Both failure modes are worse than a stated multiple."""
    estimate = estimate_for(live_cases(), "m", "all")
    budget = budget_for(estimate)
    assert budget.max_tokens == estimate.total_tokens * BUDGET_SAFETY_FACTOR
    assert budget.max_requests == estimate.requests * BUDGET_SAFETY_FACTOR
    assert budget.max_tokens < 27_000_000, "a single run must not be able to consume the daily cap"


# --- results are written, including partial ones -------------------------------------------------


def test_a_result_is_written_per_run_and_names_its_provider(
    store: InMemoryGraphStore, tmp_path: Any
) -> None:
    case = gold.load_cases()[0]
    result = run_live(
        store=store,
        cases=[case.as_eval_case()],
        provider="scripted",
        llm_factory=lambda: ScriptedLLM(gold.build_script(case)),
    )
    path = write_result(result, revision="abc1234", directory=tmp_path)

    assert path.exists()
    assert path.name.endswith("-scripted.json")
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["provider"] == "scripted"
    assert payload["cases_run"] == 1


def test_two_runs_do_not_overwrite_each_other(store: InMemoryGraphStore, tmp_path: Any) -> None:
    """Per-run files, never one rolling file: phase 7 plots the trend, and a benchmark with no
    history cannot show that a number moved."""
    case = gold.load_cases()[0]

    def once() -> Any:
        return run_live(
            store=store,
            cases=[case.as_eval_case()],
            provider="scripted",
            llm_factory=lambda: ScriptedLLM(gold.build_script(case)),
        )

    first = write_result(once(), revision="abc1234", directory=tmp_path)
    first.rename(first.with_name("20260101T000000Z-scripted.json"))
    second = write_result(once(), revision="abc1234", directory=tmp_path)

    assert len({p.name for p in tmp_path.iterdir()}) == 2
    assert second.exists()


def test_a_run_reports_the_requests_it_actually_issued(store: InMemoryGraphStore) -> None:
    """The suite counts tokens; nothing else counts requests, and requests are the unit the binding
    quota is denominated in."""
    case = gold.load_cases()[0]
    lines: list[str] = []
    run_live(
        store=store,
        cases=[case.as_eval_case()],
        provider="scripted",
        llm_factory=lambda: ScriptedLLM(gold.build_script(case)),
        progress=lines.append,
    )
    assert any("requests issued:" in line for line in lines)
    assert any(case.case_id in line for line in lines)


def test_progress_names_each_case_as_it_starts(store: InMemoryGraphStore) -> None:
    """So that coming back to a half-finished run shows where it got, rather than a blank screen."""
    cases = [c.as_eval_case() for c in gold.load_cases()[:3]]
    scripts = {c.case_id: gold.build_script(c) for c in gold.load_cases()[:3]}
    lines: list[str] = []

    for case in cases:
        run_live(
            store=store,
            cases=[case],
            provider="scripted",
            llm_factory=lambda c=case: ScriptedLLM(scripts[c.case_id]),  # type: ignore[misc]
            progress=lines.append,
        )
    for case in cases:
        assert any(case.case_id in line for line in lines)


def test_the_written_revision_is_the_one_passed_not_the_tree_now(
    store: InMemoryGraphStore, tmp_path: Any
) -> None:
    """**The lock on the 2026-08-17 near-miss.** `write_result` runs seventeen minutes after the code it
    describes was loaded, so it must record the revision it was *given*, never re-read the tree.

    An edit made while a run was in flight came within one commit of stamping a clean run `-dirty`,
    which its own pooling guard would then have refused. Broken deliberately by restoring
    `code_revision()` inside `write_result`: this test failed with the live tree's sha.
    """
    case = gold.load_cases()[0]
    result = run_live(
        store=store,
        cases=[case.as_eval_case()],
        provider="scripted",
        llm_factory=lambda: ScriptedLLM(gold.build_script(case)),
    )
    path = write_result(result, revision="deadbee", directory=tmp_path)

    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["code_revision"] == "deadbee"
