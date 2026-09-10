"""The trend view's cohorts. Phase 7.5 step 2.

Step 2's done-when: the view reads ``eval/results/``, **refuses to join what the gate would refuse to
compare, and a test asserts that refusal.** This file is that test, in two halves. Synthetic runs pin
each refusal by construction -- a different corpus, a subset, an unfinished run -- and the committed
history is checked for the implication itself: every pair the trend puts on one line is a pair the gate
would judge against the same bounds.
"""

from __future__ import annotations

from itertools import combinations
from typing import Any

from musical_mycelium.eval import noise, trend
from musical_mycelium.eval.report_page import NOISE_FLOOR, _load, results

Json = dict[str, Any]


def _run(
    *,
    artifact: str = "0.7.1",
    cases: tuple[str, ...] = ("a", "b", "c"),
    correct: tuple[bool, ...] | None = None,
    revision: str = "r1",
    complete: bool = True,
    **extra: Any,
) -> Json:
    marks = correct if correct is not None else tuple(True for _ in cases)
    return {
        "dataset": "live",
        "dataset_version": "gold+adversarial",
        "provider": "bedrock",
        "model_id": "haiku",
        "artifact_version": artifact,
        "artifact_pin": artifact,
        "complete": complete,
        "code_revision": revision,
        "cases_run": len(cases),
        "per_case": [
            {"case_id": case, "correct": ok} for case, ok in zip(cases, marks, strict=True)
        ],
        **extra,
    }


# --- each refusal, by construction -------------------------------------------------------------------


def test_code_revision_is_the_one_field_a_cohort_crosses() -> None:
    """The released field. Without it every cohort is one run and there is no trend to show."""
    assert trend.comparable(("1", _run(revision="aaa")), ("2", _run(revision="bbb")))


def test_a_different_corpus_is_never_joined_even_where_the_gate_would() -> None:
    """The gate checks completeness and case count, not the pin. The trend is stricter on purpose."""
    before, after = ("1", _run(artifact="0.5.0")), ("2", _run(artifact="0.6.0"))
    assert before[1]["cases_run"] == after[1]["cases_run"], "the gate would compare these"
    assert not trend.comparable(before, after)


def test_a_subset_is_never_joined_with_the_full_set() -> None:
    assert not trend.comparable(("1", _run(cases=("a", "b", "c"))), ("2", _run(cases=("a",))))


def test_same_size_different_cases_is_not_the_same_measurement() -> None:
    """Two one-case smoke tests of different cases share a case count and nothing else."""
    assert not trend.comparable(("1", _run(cases=("a",))), ("2", _run(cases=("b",))))


def test_an_unfinished_run_joins_nothing_not_even_another_unfinished_run() -> None:
    first, second = ("1", _run(complete=False)), ("2", _run(complete=False))
    assert not trend.comparable(first, second)
    assert not trend.comparable(first, ("3", _run()))


def test_a_cohort_is_charted_only_at_the_noise_floor_minimum() -> None:
    few = trend.cohorts([(str(i), _run()) for i in range(noise.MINIMUM_RUNS - 1)])
    enough = trend.cohorts([(str(i), _run()) for i in range(noise.MINIMUM_RUNS)])
    assert len(few) == 1 and not few[0].charted
    assert len(enough) == 1 and enough[0].charted


# --- the implication, over every committed run --------------------------------------------------------


def test_nothing_joined_is_a_pair_the_gate_would_refuse() -> None:
    """The plan's own wording: the view "does not join points that the gate logic itself would refuse
    to compare". The gate's conditions are ``ThresholdSet.matches`` (dataset and provider) and
    ``thresholds._ungateable`` (the run finished, and its case count is the baseline's). Every pair that
    shares a cohort must satisfy all of them."""
    runs = results("bedrock")
    assert len(runs) > 20, "the committed history is missing -- eval/results/ is not being read"
    for cohort in trend.cohorts(runs):
        for (_, a), (_, b) in combinations(cohort.runs, 2):
            assert (a["dataset"], a["provider"]) == (b["dataset"], b["provider"])
            assert a["complete"] and b["complete"]
            assert a["cases_run"] == b["cases_run"]


def test_the_measured_floor_sits_inside_one_charted_cohort() -> None:
    """The band is drawn on the cohort that contains the floor's runs, so that cohort must exist."""
    floor = _load(NOISE_FLOOR)
    stamps = {name.split("-", 1)[0] for name in floor["runs"]}
    homes = [c for c in trend.cohorts(results("bedrock")) if stamps <= set(c.stamps)]
    assert len(homes) == 1 and homes[0].charted


# --- the per-case view and the chart ------------------------------------------------------------------


def test_unsteady_cases_are_exactly_the_ones_not_always_correct() -> None:
    cohort = trend.cohorts(
        [
            ("1", _run(correct=(True, False, True))),
            ("2", _run(correct=(True, False, False))),
        ]
    )[0]
    assert trend.unsteady_cases(cohort) == [("b", [False, False]), ("c", [True, False])]


def test_an_undefined_value_breaks_the_line_rather_than_bridging_it() -> None:
    values = (0.9, 0.95, None, 0.9, 0.92)
    runs = []
    for index, value in enumerate(values):
        extra: dict[str, Any] = {} if value is None else {"traversal_recall": value}
        runs.append((f"2026090{index}T000000Z", _run(**extra)))
    cohort = trend.cohorts(runs)[0]
    svg = trend.chart("traversal_recall", cohort, band=None)
    assert svg.count("<polyline") == 2, "the gap must split the line into two segments"
    assert svg.count("<title>") == 4, "every measured point, and only those, carries a value"
    assert "nan" not in svg.lower()
