"""Suite tests — mostly attempts to make the suite report something false.

The gold set scored 25/25 on every metric the first time it was ever executed (2026-08-16). That is the
result this file exists to distrust. A suite that reports perfection on its first run is indistinguishable
from a suite that reports perfection on any input, and the repo's named failure mode is *assertions
written from a mental model and never executed*. So the tests below are structured as perturbations: feed
the suite something known to be wrong and assert the number moves.

Three of them are the load-bearing ones:

- ``test_the_trace_policy_cannot_see_the_answer`` — the non-circularity lock. If ``build_script`` could
  read ``expected_path``, ``traversal_recall`` would be measuring ``gold.py``.
- ``test_a_direction_inversion_is_caught_by_recall_and_missed_by_groundedness`` — the finding that
  justifies keeping recall in the report at all.
- ``test_a_run_of_zero_cases_reports_no_percentage`` — the vacuous-truth guard, at suite level rather
  than metric level.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable
from pathlib import Path

import pytest

from musical_mycelium.agent.llm import LLM, LLMResponse, ScriptedLLM
from musical_mycelium.eval import gold
from musical_mycelium.eval import suite as suite_module
from musical_mycelium.eval.budget import EvalBudget
from musical_mycelium.eval.suite import (
    PROVIDER_SCRIPTED,
    SCRIPT_DETERMINED,
    EvalCase,
    SuiteResult,
    run_gold_suite,
    run_suite,
)
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture(scope="module")
def cases() -> tuple[gold.GoldCase, ...]:
    return gold.load_cases()


@pytest.fixture(scope="module")
def result(store: InMemoryGraphStore) -> SuiteResult:
    return run_gold_suite(store)


def _run_with_policy(
    store: InMemoryGraphStore,
    cases: tuple[gold.GoldCase, ...],
    policy: Callable[[gold.GoldCase], list[LLMResponse]],
) -> SuiteResult:
    """Drive the gold set with a perturbed script builder. The perturbation is the test."""
    scripts = {case.case_id: policy(case) for case in cases}

    def llm_for(case: EvalCase) -> LLM:
        return ScriptedLLM(list(scripts[case.case_id]))

    return run_suite(
        gold.eval_cases(cases),
        store=store,
        llm_for=llm_for,
        dataset="gold",
        dataset_version="perturbed",
        artifact_pin=store.artifact_version,
    )


# --- the run happens at all --------------------------------------------------------------------------


def test_the_gold_set_runs_end_to_end_against_the_pinned_artifact(result: SuiteResult) -> None:
    """The first execution of the 25 cases, and the thing step 3 exists to find out."""
    assert result.cases_run == 25
    assert result.complete
    assert result.aborted_reason == ""
    assert result.artifact_matches_pin, (
        f"the gold set is pinned to {result.artifact_pin} but the loaded artifact is "
        f"{result.artifact_version}; every number is scored against the wrong corpus"
    )


def test_no_gold_case_truncates(result: SuiteResult) -> None:
    """A truncated traversal may have stopped one tool call short of the edge that mattered, and would
    then score as a confident short answer. The naive policy is well inside the ceilings; if this ever
    fails, the ceilings moved rather than the policy."""
    assert result.truncated_runs == ()


def test_every_gold_case_reaches_its_whole_expected_path(result: SuiteResult) -> None:
    """The 2026-08-16 finding, recorded as a test rather than as a sentence in a doc.

    Every case's ``expected_path`` is exactly reachable by one resolve turn and one shape-appropriate
    tool call, with no off-path visits. **This is a fact about the gold set, not a score**: it means
    ``expected_path`` was authored as the one-hop neighbourhood, which is why recall and precision are
    marked script-determined. A case that stops satisfying this has had its corpus move underneath it.
    """
    for case in result.results:
        assert case.recall.score == 1.0, f"{case.case.case_id}: recall {case.recall}"
        assert case.precision.score == 1.0, f"{case.case.case_id}: precision {case.precision}"


def test_refusal_cases_refuse_and_answerable_cases_answer(result: SuiteResult) -> None:
    """Both halves of the pair, per ``.claude/rules/grounding-and-claims.md``. A system that refuses
    everything scores perfectly on hallucination and is useless, so the false-refusal count is asserted
    alongside the true-refusal one rather than left to the aggregate."""
    assert result.refusal.true_refusals == result.refusal.expected_refusals
    assert result.refusal.false_refusals == 0
    assert result.refusal.expected_refusals == 3
    assert result.refusal.expected_answers == 22


def test_the_gold_set_plants_no_injections_and_says_so(result: SuiteResult) -> None:
    """``holds`` is **False** here and that is correct. The gold set carries no forbidden triples, so
    every case is unscored, and ``InjectionResistance.holds`` requires ``scored_cases > 0`` precisely so
    that a suite which tested nothing cannot report resistance. Injection resistance is the adversarial
    set's job."""
    assert result.injection.scored_cases == 0
    assert result.injection.unscored_cases == 25
    assert result.injection.induced == 0
    assert not result.injection.holds


# --- the non-circularity lock ------------------------------------------------------------------------


def test_the_trace_policy_cannot_see_the_answer(cases: tuple[gold.GoldCase, ...]) -> None:
    """**The lock that makes a scripted gold run mean anything.**

    ``build_script`` may read what the query already names out loud — the subject, and for a path case the
    terminus. It must not read ``expected_path`` or ``expected_claims``. If it could, the trace would be
    written from the answer and ``traversal_recall`` would be scoring ``gold.py`` rather than the corpus.

    Verified by mutation rather than by inspection: replace the answer fields with nonsense and assert
    the script does not move. Broken deliberately on 2026-08-16 by making ``trace_of`` walk
    ``expected_path`` — this test failed on all 25 cases, as it should.
    """
    for case in cases:
        poisoned = dataclasses.replace(
            case,
            expected_path=("Q_NOT_A_NODE", "Q_ALSO_NOT"),
            expected_claims=(("Q_NOT_A_NODE", "influenced_by", "Q_ALSO_NOT"),),
        )
        assert gold.trace_of(poisoned) == gold.trace_of(case), (
            f"{case.case_id}: trace saw the answer"
        )
        assert gold.build_script(poisoned) == gold.build_script(case), (
            f"{case.case_id}: script saw the answer"
        )


def test_the_trace_names_only_endpoints_the_query_already_names(
    cases: tuple[gold.GoldCase, ...],
) -> None:
    """The same rule stated positively: every node id a trace passes to a tool is either the subject or
    the terminus. An intermediate id appearing here would be the answer leaking in through arguments."""
    for case in cases:
        allowed = {case.subject_id, case.terminus_id} - {None}
        for _name, arguments in gold.trace_of(case):
            for key, value in arguments.items():
                if key.endswith("_id"):
                    assert value in allowed, f"{case.case_id}: trace names {value}, not an endpoint"


# --- perturbations: the numbers must move ------------------------------------------------------------


def test_a_direction_inversion_is_caught_by_recall_and_missed_by_groundedness(
    store: InMemoryGraphStore, cases: tuple[gold.GoldCase, ...]
) -> None:
    """**The finding that justifies keeping recall in the report.**

    Ask every ``origins`` case for descendants and every ``descendants`` case for influences. The walk is
    now backwards — and ``edge_groundedness`` still reads **100%**, because ``GetDescendants`` builds its
    proposals from real edges oriented off the edge rather than off the argument, so a backwards walk
    produces claims that are individually true about the wrong nodes.

    Groundedness structurally cannot catch this. Recall can, and does. That matters because "assuming the
    origins direction" is a named recurring failure in this repo — three independent instances on
    2026-08-14, none of which raised — and this is the first metric that would have caught any of them.
    """
    flip = {"origins": "descendants", "descendants": "origins", "path": "path"}

    def inverted(case: gold.GoldCase) -> list[LLMResponse]:
        return gold.build_script(dataclasses.replace(case, shape=flip[case.shape]))

    result = _run_with_policy(store, cases, inverted)

    assert result.groundedness.score == 1.0, (
        "the premise of this test is that groundedness is blind to direction; if it now catches it, "
        "the claim model changed and this test's reasoning needs rewriting rather than its number"
    )
    assert result.recall.score is not None and result.recall.score < 0.6
    assert result.refusal.false_refusals > 0


def test_dropping_the_shape_tool_collapses_recall_and_empties_the_claim_set(
    store: InMemoryGraphStore, cases: tuple[gold.GoldCase, ...]
) -> None:
    """A trace that resolves and then gives up. Recall falls to the subjects alone, and groundedness goes
    **undefined rather than perfect** — the vacuous-truth guard doing its job on a real run instead of on
    a synthetic input."""

    def resolve_only(case: gold.GoldCase) -> list[LLMResponse]:
        script = gold.build_script(case)
        return [script[0], script[1], script[-2], script[-1]]

    result = _run_with_policy(store, cases, resolve_only)

    assert result.recall.score is not None and result.recall.score < 0.5
    assert result.groundedness.score is None, "an empty claim set must not score 100% groundedness"
    assert result.refusal.false_refusals == 22


def test_a_run_of_zero_cases_reports_no_percentage(store: InMemoryGraphStore) -> None:
    """The suite-level vacuous-truth guard. Every rate is ``None``, not ``1.0`` and not ``0.0``.

    ``.claude/rules/evals.md`` names this for groundedness; the failure it prevents is broader — a suite
    whose dataset failed to load reporting a clean sweep.
    """
    result = run_suite(
        [],
        store=store,
        llm_for=lambda case: pytest.fail("no case should have been driven"),
        dataset="empty",
        dataset_version="0",
        artifact_pin=store.artifact_version,
    )

    assert result.cases_run == 0
    assert result.groundedness.score is None
    assert result.citation.score is None
    assert result.recall.score is None
    assert result.precision.score is None
    assert not result.groundedness.is_fully_grounded


# --- the budget aborts rather than skipping ----------------------------------------------------------


def test_the_budget_aborts_and_the_partial_run_says_it_is_partial(
    store: InMemoryGraphStore,
) -> None:
    """A truncated run that reports itself as truncated is usable; one that looks complete is poison.

    Broken deliberately on 2026-08-16 by catching ``BudgetExceeded`` and ``continue``-ing instead of
    breaking: the run then reported ``complete=True`` over the cases it happened to afford, and this test
    failed on ``complete``.
    """
    budget = EvalBudget(max_tokens=2_000, max_requests=100)
    result = run_gold_suite(store, budget=budget)

    assert not result.complete
    assert "token budget exhausted" in result.aborted_reason
    assert 0 < result.cases_run < 25


def test_a_provider_failure_keeps_the_cases_that_already_ran(store: InMemoryGraphStore) -> None:
    """**The lock on what cost a real run on 2026-08-17.** A `ThrottlingException` on case 41 of 41
    propagated past the writer and destroyed forty completed cases — no file, no recorded usage,
    seventeen minutes and a real bill for nothing.

    Only `BudgetExceeded` was caught. Every exception now aborts the same way the budget does: stop,
    record why, return what exists. Billable cases are expensive and non-reproducible, and the one
    thing `run_suite` must never do is throw them away.

    Broken deliberately by narrowing the handler back to `BudgetExceeded`: the exception escaped
    `run_suite` and this test failed with `ThrottlingLikeError` instead of an assertion.
    """

    class ThrottlingLikeError(RuntimeError):
        """Stands in for `botocore.errorfactory.ThrottlingException`, which `eval/` must not import."""

    gold_cases = gold.load_cases()
    cases = gold.eval_cases(gold_cases)
    by_id = {case.case_id: case for case in gold_cases}
    fail_on = cases[2].case_id

    def llm_for(case: EvalCase) -> LLM:
        if case.case_id == fail_on:
            raise ThrottlingLikeError("Too many requests, please wait before trying again")
        return ScriptedLLM(gold.build_script(by_id[case.case_id]))

    result = run_suite(
        cases,
        store=store,
        llm_for=llm_for,
        dataset="live",
        dataset_version="gold",
        artifact_pin=gold.dataset_version()[1],
        provider="bedrock",
    )

    assert not result.complete
    assert result.cases_run == 2, "the two cases that finished must survive the third one failing"
    assert "ThrottlingLikeError" in result.aborted_reason
    assert fail_on in result.aborted_reason, (
        "which case died is the difference between case 3 and 41"
    )
    assert "case 3 of 25" in result.aborted_reason


def test_an_exhausted_budget_stops_before_spending_more(store: InMemoryGraphStore) -> None:
    """``check`` runs before the call, so the recorded spend is what was billed rather than what was
    attempted. A budget with no room drives nothing at all."""
    budget = EvalBudget(max_tokens=1, max_requests=1)
    budget.spent_tokens = 1
    result = run_gold_suite(store, budget=budget)

    assert result.cases_run == 0
    assert not result.complete


# --- the marking ------------------------------------------------------------------------------------


def test_a_scripted_result_marks_the_metrics_its_script_decided(result: SuiteResult) -> None:
    assert result.provider == PROVIDER_SCRIPTED
    assert result.script_determined == SCRIPT_DETERMINED
    assert "traversal_recall" in result.script_determined
    assert "edge_groundedness" not in result.script_determined, (
        "groundedness is decided by the gate and the corpus, not by the trace; marking it would tell "
        "the reader to discount the one number a scripted run can actually stand behind"
    )


def test_a_non_scripted_result_carries_no_script_marking(
    store: InMemoryGraphStore, cases: tuple[gold.GoldCase, ...]
) -> None:
    """The marking is a property of the provider, not a decoration applied to every run. A real-model run
    marks nothing, because nothing in it was decided by a trace."""
    scripts = {case.case_id: gold.build_script(case) for case in cases}
    result = run_suite(
        gold.eval_cases(cases),
        store=store,
        llm_for=lambda case: ScriptedLLM(list(scripts[case.case_id])),
        dataset="gold",
        dataset_version="0.1.0",
        artifact_pin=store.artifact_version,
        provider="bedrock",
    )
    assert result.script_determined == ()


# --- loading refuses to guess -------------------------------------------------------------------------


def test_an_unknown_shape_raises_rather_than_defaulting(tmp_path: Path) -> None:
    """Two shape branches read the same edge rows in opposite directions, so a shape that falls through
    to a default does not raise — it answers the wrong question and passes."""
    import json

    payload = {
        "version": "0",
        "artifact_version_pin": "0.5.0",
        "cases": [
            {
                "case_id": "x",
                "query": "q",
                "shape": "origns",
                "difficulty": "trivial",
                "expected_resolution": {"name": "n", "node_id": "Q1"},
                "expected_refusal": False,
                "expected_path": ["Q1"],
                "expected_claims": [],
            }
        ],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="unknown shape"):
        gold.load_cases(path)


def test_a_path_case_without_a_terminus_raises(tmp_path: Path) -> None:
    import json

    payload = {
        "version": "0",
        "artifact_version_pin": "0.5.0",
        "cases": [
            {
                "case_id": "x",
                "query": "q",
                "shape": "path",
                "difficulty": "trivial",
                "expected_resolution": {"name": "n", "node_id": "Q1"},
                "expected_refusal": False,
                "expected_path": ["Q1"],
                "expected_claims": [],
            }
        ],
    }
    path = tmp_path / "bad.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="expected_terminus"):
        gold.load_cases(path)


# --- slicing -----------------------------------------------------------------------------------------


def test_every_result_is_sliced_four_ways(result: SuiteResult) -> None:
    """DoD 6. The dimensions are fixed by ``.claude/rules/evals.md`` and a suite that reports three of
    them has dropped the one that was going to fail."""
    assert tuple(report.dimension for report in result.slices) == (
        "era",
        "region",
        "density",
        "query_kind",
    )


def test_the_slices_account_for_every_case(result: SuiteResult) -> None:
    """A dimension whose denominators do not sum to the case count has dropped rows — which is exactly
    what the ``unknown`` and ``undated`` buckets exist to prevent."""
    for report in result.slices:
        total = sum(rate.denominator for rate in report.rates.values())
        assert total == result.cases_run, f"{report.dimension}: {total} of {result.cases_run} cases"


# --- the serialised shape ----------------------------------------------------------------------------


def test_the_json_carries_the_provider_and_the_marking(result: SuiteResult) -> None:
    """Phase 7 reads these files. A result file that does not say who produced it is a number with no
    provenance, in a project whose whole claim is provenance."""
    payload = result.to_json()
    assert payload["provider"] == PROVIDER_SCRIPTED
    assert payload["script_determined"] == list(SCRIPT_DETERMINED)
    assert payload["artifact_version"] == result.artifact_version
    assert payload["artifact_matches_pin"] is True
    assert payload["complete"] is True
    assert len(payload["per_case"]) == 25


def test_the_json_is_serialisable(result: SuiteResult) -> None:
    import json

    assert json.loads(json.dumps(result.to_json()))["cases_run"] == 25


def test_the_module_exposes_the_catalog_the_phase_doc_names() -> None:
    """Eight scorers plus two telemetry figures, and deliberately not eleven. The scope doc says eleven;
    the implementation doc recorded the correction and its reason. Rounding down is the rule."""
    payload_keys = {
        "edge_groundedness",
        "citation_resolution",
        "refusal_accuracy",
        "traversal_recall",
        "traversal_precision",
        "injection_resistance",
        "verification_mix",
        "usage",
    }
    assert payload_keys <= set(
        run_suite(
            [],
            store=InMemoryGraphStore.from_directory(artifact_directory()),
            llm_for=lambda case: pytest.fail("no case should have been driven"),
            dataset="empty",
            dataset_version="0",
            artifact_pin="0",
        ).to_json()
    )
    assert suite_module.SCRIPT_DETERMINED
