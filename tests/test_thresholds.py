"""Threshold and gate tests — phase 4 step 5.

Every lock in this file was broken deliberately once, watched to fail, and restored. That is the
2026-08-14 practice and it matters more here than almost anywhere else in the repo, because **a gate
that does not gate is green by default**. Every failure mode below looks exactly like success from the
outside: a threshold file that silently does not load, a metric that passes because nothing was scored,
a live bound quietly applied to a scripted run. None of them produce a red build on their own, which is
precisely why each one needs a test that produces one.

The base fixture is the *real* scripted run rather than a hand-built ``SuiteResult``. It is
deterministic, so it is reproducible, and it means the committed ``thresholds.json`` is exercised
against the thing it actually gates instead of against a mock that agrees with it by construction.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.eval.metrics import Groundedness, InjectionResistance, Rate, RefusalAccuracy
from musical_mycelium.eval.suite import SuiteResult, run_gold_suite
from musical_mycelium.eval.thresholds import (
    FAIL,
    GATE_NAMES,
    NOT_APPLICABLE,
    PASS,
    THRESHOLDS_PATH,
    GateResult,
    MalformedThresholds,
    evaluate,
    gate,
    load,
)
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory


@pytest.fixture(scope="module")
def scripted() -> SuiteResult:
    """The free every-commit run, as it actually runs."""
    return run_gold_suite(InMemoryGraphStore.from_directory(artifact_directory()))


@pytest.fixture(scope="module")
def committed() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    return payload


def verdicts(result: SuiteResult) -> dict[str, str]:
    thresholds = load()
    assert thresholds is not None
    report = evaluate(result, thresholds)
    assert report is not None
    return {g.name: g.verdict for g in report.gates}


def as_live(result: SuiteResult, **changes: object) -> SuiteResult:
    """Relabel a scripted result as a completed live run, so the live bounds apply to it.

    A typed helper rather than a ``**dict`` splat: mypy cannot see through the splat into
    ``dataclasses.replace``, and spelling the three relabelled fields out here keeps the
    ``script_determined=()`` in one place. Dropping that marker is the point — a live run has no
    script-determined metrics, which is what lets the traversal gate engage at all.
    """
    return dataclasses.replace(
        result,
        dataset="live",
        provider="bedrock",
        script_determined=(),
        **changes,  # type: ignore[arg-type]
    )


# --- the committed file ------------------------------------------------------


def test_the_committed_thresholds_load(committed: dict[str, Any]) -> None:
    thresholds = load()
    assert thresholds is not None
    assert len(thresholds.sets) == len(committed["sets"])


def test_the_live_bounds_still_match_the_noise_floor_they_were_derived_from(
    committed: dict[str, Any],
) -> None:
    """The gate file and the floor it came from must not drift apart.

    A bound hand-edited in isolation is the way a measured threshold quietly becomes an invented one —
    the exact thing `.claude/rules/evals.md` forbids. This compares the recorded observations against
    `noise_floor.json` rather than the bounds themselves, because the *bounds* are a judgement call and
    the *observations* are a measurement. A judgement may be revisited; a measurement may not be edited.
    """
    floor = json.loads((THRESHOLDS_PATH.parent / "noise_floor.json").read_text(encoding="utf-8"))
    live = next(s for s in committed["sets"] if s["applies_to"]["provider"] == "bedrock")

    assert live["derived_from"]["code_revision"] == floor["code_revision"]
    assert live["derived_from"]["run_count"] == floor["run_count"]
    assert live["case_count"] == len(floor["cases"])

    by_metric = {s["metric"]: s for s in floor["spreads"]}
    bounds = live["bounds"]
    assert bounds["edge_groundedness"]["observed"] == by_metric["edge_groundedness"]["values"]
    assert bounds["citation_resolution"]["observed"] == by_metric["citation_resolution"]["values"]

    #: 16 refusal cases and 25 answer cases, recovered from the rates rather than trusted.
    true_rates = by_metric["true_refusal_rate"]["values"]
    observed_true = bounds["refusal_accuracy"]["observed_true_refusals"]
    denominator = bounds["refusal_accuracy"]["expected_refusals"]
    assert [round(r * denominator) for r in true_rates] == observed_true


def test_every_live_bound_records_why_it_is_where_it_is(committed: dict[str, Any]) -> None:
    """A bare number invites being tightened by someone who does not know what measuring it cost."""
    for threshold_set in committed["sets"]:
        for metric, bound in threshold_set["bounds"].items():
            assert bound.get("why"), f"{threshold_set['name']}/{metric} has no recorded reasoning"
            assert "slack" in bound, f"{threshold_set['name']}/{metric} does not state its slack"


def test_the_traversal_gate_excludes_the_known_reproducible_failure(
    committed: dict[str, Any],
) -> None:
    """`gold_v0_1_020` fails 5 of 5 and must be tracked, not gated.

    Gating on it would block every build until a product bug is fixed while telling nobody anything
    new, which is how a suite gets disabled.
    """
    live = next(s for s in committed["sets"] if s["applies_to"]["provider"] == "bedrock")
    traversal = live["bounds"]["traversal_recall"]
    assert "gold_v0_1_020" not in traversal["cases"]
    assert "gold_v0_1_020" in traversal["excluded"]
    assert len(traversal["cases"]) == 24


# --- the five gates, and only five -------------------------------------------


def test_exactly_the_five_correctness_properties_are_gated(scripted: SuiteResult) -> None:
    assert tuple(verdicts(scripted)) == GATE_NAMES


def test_the_scripted_run_passes_the_three_it_can_and_skips_the_two_it_cannot(
    scripted: SuiteResult,
) -> None:
    """The honest shape of the free gate, asserted so it cannot be quietly widened.

    If a future edit makes traversal or injection read `PASS` here, it has started gating a scripted
    trace as though a model produced it.
    """
    assert verdicts(scripted) == {
        "edge_groundedness": PASS,
        "citation_resolution": PASS,
        "refusal_accuracy": PASS,
        "injection_resistance": NOT_APPLICABLE,
        "traversal_recall": NOT_APPLICABLE,
    }


def test_make_eval_exits_zero_on_a_clean_scripted_run(scripted: SuiteResult) -> None:
    assert gate(scripted).exit_code == 0


# --- not applicable is not a pass --------------------------------------------


def test_an_all_inapplicable_report_does_not_read_as_green(scripted: SuiteResult) -> None:
    """The failure this prevents: a run where nothing could be checked, reported as though it passed."""
    outcome = gate(scripted)
    assert outcome.report is not None
    rendered = "\n".join(outcome.lines)
    assert "NOT APPLICABLE IS NOT A PASS" in rendered
    assert "2 not applicable" in rendered
    assert len(outcome.report.passed) + len(outcome.report.inapplicable) == len(GATE_NAMES)


def test_injection_with_nothing_scored_is_not_a_pass(scripted: SuiteResult) -> None:
    """`induced == 0` over zero scored cases is a metric inflating itself into decoration.

    **This test asserts against the *live* set, and the first draft did not — it asserted against the
    scripted one and passed for the wrong reason.** The scripted set declares no injection bound at
    all, so deleting the zero-scored guard entirely left the suite green: the gate still returned `N/A`,
    just via "this set declares no bound" instead. Caught on 2026-08-18 by breaking the guard and
    watching the test *not* fail, which is the whole argument for breaking them.

    So the run below carries a bound it could satisfy and still must not, because it scored nothing.
    """
    untested = as_live(
        scripted,
        injection=InjectionResistance(induced=0, scored_cases=0, unscored_cases=41),
    )
    thresholds = load()
    assert thresholds is not None
    report = evaluate(untested, thresholds)
    assert report is not None
    injection = next(g for g in report.gates if g.name == "injection_resistance")
    assert injection.verdict == NOT_APPLICABLE
    assert "never tested" in injection.note

    # And the same set, with cases that actually planted something, does engage and pass.
    engaged = dataclasses.replace(
        untested, injection=InjectionResistance(induced=0, scored_cases=5, unscored_cases=36)
    )
    engaged_report = evaluate(engaged, thresholds)
    assert engaged_report is not None
    assert {g.name: g.verdict for g in engaged_report.gates}["injection_resistance"] == PASS


def test_a_real_injection_breach_blocks(scripted: SuiteResult) -> None:
    breached = as_live(
        scripted,
        injection=InjectionResistance(
            induced=1, scored_cases=5, unscored_cases=20, breaches=(("Q1", "P737", "Q2"),)
        ),
    )
    thresholds = load()
    assert thresholds is not None
    report = evaluate(breached, thresholds)
    assert report is not None
    injection = next(g for g in report.gates if g.name == "injection_resistance")
    assert injection.verdict == FAIL
    assert "Q737" in injection.note or "P737" in injection.note


def test_an_adversarial_set_that_lost_its_injections_fails_rather_than_passing(
    scripted: SuiteResult,
) -> None:
    """The other direction. Zero induced over *fewer cases than the baseline* is lost coverage."""
    thinned = as_live(
        scripted,
        injection=InjectionResistance(induced=0, scored_cases=2, unscored_cases=23),
    )
    thresholds = load()
    assert thresholds is not None
    report = evaluate(thinned, thresholds)
    assert report is not None
    assert next(g for g in report.gates if g.name == "injection_resistance").verdict == FAIL


# --- the vacuous-truth guard, at the gate ------------------------------------


def test_an_empty_run_does_not_score_a_passing_groundedness(scripted: SuiteResult) -> None:
    """`.claude/rules/evals.md`: *an empty output must not score 100% groundedness.*

    `Rate` already refuses to turn 0/0 into a number. This asserts the gate refuses to turn it into a
    pass — the same guard one layer up, where a `None` would otherwise be easy to skip over.
    """
    empty = dataclasses.replace(
        scripted,
        groundedness=Groundedness(grounded=0, total=0),
        citation=Rate(numerator=0, denominator=0),
    )
    result = verdicts(empty)
    assert result["edge_groundedness"] == FAIL
    assert result["citation_resolution"] == FAIL
    assert gate(empty).exit_code == 1


def test_a_single_ungrounded_claim_blocks(scripted: SuiteResult) -> None:
    leaked = dataclasses.replace(scripted, groundedness=Groundedness(grounded=66, total=67))
    assert verdicts(leaked)["edge_groundedness"] == FAIL
    assert gate(leaked).exit_code == 1


# --- refusal accuracy, in cases ----------------------------------------------


def test_refusal_is_gated_in_cases_not_percentage_points(committed: dict[str, Any]) -> None:
    """16 refusal cases makes one case 6.25pp, so a 5pp band cannot be tripped by less than one case.

    Asserting the *shape* of the bound, not just its value: a future edit that reintroduces a
    percentage here has reintroduced an arithmetically unsatisfiable gate.
    """
    live = next(s for s in committed["sets"] if s["applies_to"]["provider"] == "bedrock")
    bound = live["bounds"]["refusal_accuracy"]
    assert isinstance(bound["minimum_true_refusals"], int)
    assert isinstance(bound["maximum_false_refusals"], int)
    assert bound["expected_refusals"] == 16
    assert 100 / bound["expected_refusals"] > 5, "one case must exceed the abandoned 5pp band"


def test_a_two_case_refusal_regression_blocks(scripted: SuiteResult) -> None:
    """13 of 16 passes; 12 does not. The gate sits one case below the worst observed value of 14."""
    at_the_bound = as_live(
        scripted,
        refusal=RefusalAccuracy(
            true_refusals=13, false_refusals=3, expected_refusals=16, expected_answers=25
        ),
    )
    below = as_live(
        scripted,
        refusal=RefusalAccuracy(
            true_refusals=12, false_refusals=3, expected_refusals=16, expected_answers=25
        ),
    )
    thresholds = load()
    assert thresholds is not None
    for result, expected in ((at_the_bound, PASS), (below, FAIL)):
        report = evaluate(result, thresholds)
        assert report is not None
        assert next(g for g in report.gates if g.name == "refusal_accuracy").verdict == expected


def test_too_many_false_refusals_blocks_even_when_true_refusals_are_perfect(
    scripted: SuiteResult,
) -> None:
    """*"A system that refuses everything scores perfectly on hallucination and is useless."*

    The gate is a pair, so the useless-but-safe direction has to fail too.
    """
    cautious = as_live(
        scripted,
        refusal=RefusalAccuracy(
            true_refusals=16, false_refusals=4, expected_refusals=16, expected_answers=25
        ),
    )
    thresholds = load()
    assert thresholds is not None
    report = evaluate(cautious, thresholds)
    assert report is not None
    assert next(g for g in report.gates if g.name == "refusal_accuracy").verdict == FAIL


def test_moved_refusal_denominators_are_not_applicable_rather_than_compared(
    scripted: SuiteResult,
) -> None:
    """Counts measured on 16 refusal cases say nothing about a set with 20 of them."""
    regrown = as_live(
        scripted,
        refusal=RefusalAccuracy(
            true_refusals=20, false_refusals=0, expected_refusals=20, expected_answers=25
        ),
    )
    thresholds = load()
    assert thresholds is not None
    report = evaluate(regrown, thresholds)
    assert report is not None
    refusal = next(g for g in report.gates if g.name == "refusal_accuracy")
    assert refusal.verdict == NOT_APPLICABLE
    assert "denominators moved" in refusal.note


# --- traversal, per case ------------------------------------------------------


def test_traversal_is_never_gated_on_a_script_determined_run(scripted: SuiteResult) -> None:
    """The category error this whole three-state design exists to prevent."""
    traversal = next(g for g in _gates(scripted) if g.name == "traversal_recall")
    assert traversal.verdict == NOT_APPLICABLE
    assert "script-determined" in traversal.note


def test_one_baseline_case_losing_its_path_blocks(scripted: SuiteResult) -> None:
    """A per-case gate, so a single regression is visible where an aggregate would absorb it.

    92 nodes across the set means one case dropping from 4/4 to 3/4 moves the aggregate by ~1pp —
    inside anything a percentage band would tolerate, and exactly the regression worth catching.
    """
    unmarked = as_live(scripted)
    thresholds = load()
    assert thresholds is not None
    baseline = evaluate(unmarked, thresholds)
    assert baseline is not None
    assert next(g for g in baseline.gates if g.name == "traversal_recall").verdict == PASS

    target = next(r for r in unmarked.results if r.case.case_id == "gold_v0_1_001")
    regressed = dataclasses.replace(
        unmarked,
        results=tuple(
            dataclasses.replace(r, recall=Rate(numerator=1, denominator=2)) if r is target else r
            for r in unmarked.results
        ),
    )
    report = evaluate(regressed, thresholds)
    assert report is not None
    traversal = next(g for g in report.gates if g.name == "traversal_recall")
    assert traversal.verdict == FAIL
    assert "gold_v0_1_001" in traversal.note


def test_a_baseline_case_vanishing_from_the_set_blocks(scripted: SuiteResult) -> None:
    """A case quietly dropped from the dataset must not read as a pass by absence."""
    unmarked = as_live(scripted)
    dropped = dataclasses.replace(
        unmarked,
        results=tuple(r for r in unmarked.results if r.case.case_id != "gold_v0_1_001"),
    )
    thresholds = load()
    assert thresholds is not None
    report = evaluate(dropped, thresholds)
    assert report is not None
    traversal = next(g for g in report.gates if g.name == "traversal_recall")
    assert traversal.verdict == FAIL
    assert "absent from this run" in traversal.note


def _gates(result: SuiteResult) -> tuple[GateResult, ...]:
    thresholds = load()
    assert thresholds is not None
    report = evaluate(result, thresholds)
    assert report is not None
    return report.gates


# --- runs that cannot be gated at all ----------------------------------------


def test_a_one_case_wiring_run_is_not_gated(scripted: SuiteResult) -> None:
    """`make eval-live ARGS='--cases 1'` is the documented two-cent wiring check.

    It is `complete=True` — nothing aborted, it was simply asked for less — so without this guard the
    traversal gate would fail it for 23 absent baseline cases and the cheapest sanity check in the
    project would exit non-zero looking like a regression.
    """
    one = dataclasses.replace(scripted, results=scripted.results[:1])
    outcome = gate(one)
    assert outcome.report is None
    assert outcome.exit_code == 0
    rendered = "\n".join(outcome.lines)
    assert "NOT GATED" in rendered
    assert "not a pass" in rendered
    assert "A subset is not a smaller version of the same measurement" in rendered


def test_an_aborted_run_is_not_gated(scripted: SuiteResult) -> None:
    """Its cases were chosen by exhaustion, so its distance from the baseline is not a regression.

    The same rule `noise.py` applies to pooling, arriving here for the same reason.
    """
    aborted = dataclasses.replace(
        scripted, complete=False, aborted_reason="budget exceeded at 12/25"
    )
    outcome = gate(aborted)
    assert outcome.report is None
    assert outcome.exit_code == 0
    assert "did not finish" in "\n".join(outcome.lines)


def test_an_unknown_dataset_is_not_gated_by_another_datasets_thresholds(
    scripted: SuiteResult,
) -> None:
    stranger = dataclasses.replace(scripted, dataset="heldout")
    outcome = gate(stranger)
    assert outcome.report is None
    assert outcome.exit_code == 0
    rendered = "\n".join(outcome.lines)
    assert "no threshold set covers heldout/scripted" in rendered
    assert "do not transfer" in rendered


def test_live_thresholds_do_not_gate_a_scripted_run_of_the_same_dataset(
    scripted: SuiteResult,
) -> None:
    """Provider is half the key. 41 live cases and 25 scripted ones are different measurements."""
    mislabelled = dataclasses.replace(scripted, dataset="live")
    outcome = gate(mislabelled)
    assert outcome.report is None
    assert "no threshold set covers live/scripted" in "\n".join(outcome.lines)


# --- the missing and broken file ---------------------------------------------


def test_a_missing_thresholds_file_reports_loudly_and_does_not_block(
    scripted: SuiteResult, tmp_path: Path
) -> None:
    """*A suite that silently passes when its thresholds are absent is worse than no suite.*"""
    outcome = gate(scripted, tmp_path / "nothing.json")
    assert outcome.report is None
    assert outcome.exit_code == 0
    rendered = "\n".join(outcome.lines)
    assert "NOT GATED" in rendered
    assert "This is not a pass" in rendered


def test_a_malformed_thresholds_file_raises_rather_than_degrading_to_no_gates(
    tmp_path: Path,
) -> None:
    """A broken gate file quietly meaning "no gates" is the missing-file failure, harder to notice."""
    broken = tmp_path / "thresholds.json"
    broken.write_text("{not json", encoding="utf-8")
    with pytest.raises(MalformedThresholds):
        load(broken)

    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"sets": []}), encoding="utf-8")
    with pytest.raises(MalformedThresholds):
        load(empty)

    incomplete = tmp_path / "incomplete.json"
    incomplete.write_text(json.dumps({"sets": [{"name": "x"}]}), encoding="utf-8")
    with pytest.raises(MalformedThresholds):
        load(incomplete)
