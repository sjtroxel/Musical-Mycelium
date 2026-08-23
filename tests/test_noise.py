"""Noise floor tests. Every refusal in `noise.py` is here, because the refusals are the module.

A spread is trivially easy to compute and trivially easy to compute over the wrong pool, and the wrong
pool produces a number that looks right forever. So the tests weighted here are the ones about what the
module declines to do: pool across a code change, average a partial run, report a spread over one run,
or hand a threshold to step 5 off four runs and a dirty tree.

The synthetic payloads are built to a known answer, per `.claude/rules/evals.md` — *"synthetic outputs
where the answer is known by construction"* — rather than read off the real result files, so a change to
a real run cannot quietly change what these assert.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.eval.noise import (
    ABSOLUTE_MINIMUM_RUNS,
    MINIMUM_RUNS,
    IncomparableRuns,
    IncompleteRun,
    NotEnoughRuns,
    ProvisionalNoiseFloor,
    RunRecord,
    compute,
    recent_runs,
    render,
)
from musical_mycelium.eval.provenance import UNKNOWN, code_revision, is_pinnable

CLEAN_REVISION = "abc1234"


def payload(
    *,
    cases: dict[str, tuple[bool, int]],
    groundedness: float | None = 1.0,
    recall: float | None = 1.0,
    precision: float | None = 1.0,
    true_refusals: int = 2,
    expected_refusals: int = 2,
    false_refusals: int = 0,
    expected_answers: int = 2,
    induced: int = 0,
    tokens: int = 100_000,
    complete: bool = True,
    revision: str = CLEAN_REVISION,
    overrides: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """One synthetic result file. ``cases`` maps case id to ``(correct, approved_claims)``.

    ``overrides`` is an explicit dict rather than ``**kwargs`` so that a test can set a field this
    helper already names — ``provider`` is both a keyword here and a pooling field under test.
    """
    body = {
        "dataset": "live",
        "dataset_version": "gold+adversarial",
        "provider": "bedrock",
        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
        "artifact_version": "0.5.0",
        "artifact_pin": "0.5.0",
        "code_revision": revision,
        "complete": complete,
        "aborted_reason": "" if complete else "token budget exhausted",
        "cases_run": len(cases),
        "cases_correct": sum(1 for correct, _ in cases.values() if correct),
        "edge_groundedness": groundedness,
        "citation_resolution": 1.0,
        "traversal_recall": recall,
        "traversal_precision": precision,
        "refusal_accuracy": {
            "true_refusals": true_refusals,
            "false_refusals": false_refusals,
            "missed_refusals": expected_refusals - true_refusals,
            "correct_answers": expected_answers - false_refusals,
            "expected_refusals": expected_refusals,
            "expected_answers": expected_answers,
        },
        "injection_resistance": {
            "induced": induced,
            "scored_cases": 5,
            "unscored_cases": len(cases) - 5,
            "holds": induced == 0,
        },
        "usage": {"input_tokens": tokens, "output_tokens": 0, "total_tokens": tokens},
        "per_case": [
            {
                "case_id": case_id,
                "refused": not correct,
                "expected_refusal": False,
                "refusal_correct": correct,
                "approved_claims": claims,
                "rejected_claims": 0,
                "groundedness": 1.0,
                "traversal_recall": 1.0,
                "traversal_precision": 1.0,
                "plan_divergence": (),
                "truncated": False,
                "correct": correct,
            }
            for case_id, (correct, claims) in cases.items()
        ],
    }
    body.update(overrides or {})
    return body


def record(tmp_path: Path, name: str, body: dict[str, Any]) -> RunRecord:
    path = tmp_path / f"{name}-bedrock.json"
    path.write_text(json.dumps(body), encoding="utf-8")
    return RunRecord.load(path)


def five(tmp_path: Path, bodies: list[dict[str, Any]]) -> list[RunRecord]:
    return [record(tmp_path, f"2026081{i}T000000Z", body) for i, body in enumerate(bodies)]


# --- the refusals -------------------------------------------------------------------------------


def test_one_run_is_refused_rather_than_reported_as_zero_spread(tmp_path: Path) -> None:
    """**The vacuous guard, and the reason this module exists in the shape it does.**

    A single run has a spread of 0.0 by arithmetic. Reporting that would be the same failure
    `traversal_precision` shipped with on 2026-08-16 — correct arithmetic answering a question that
    was not asked — except that here it would read as *"the suite is perfectly stable"*, which is the
    most expensive wrong answer this module could give.
    """
    only = five(tmp_path, [payload(cases={"a": (True, 3)})])
    with pytest.raises(NotEnoughRuns) as refusal:
        compute(only)
    assert str(ABSOLUTE_MINIMUM_RUNS) in str(refusal.value)


def test_runs_from_different_code_are_refused(tmp_path: Path) -> None:
    """The 2026-08-16 case, encoded. Two runs that agree on dataset, model and artifact and disagree
    on nothing else a reader would check, produced by different code.

    Broken deliberately by dropping ``code_revision`` from ``POOLING_FIELDS``: the floor computed
    happily and reported an 18pp precision spread as model variance.
    """
    runs = five(
        tmp_path,
        [
            payload(cases={"a": (True, 3)}, precision=0.819, revision="24517e1"),
            payload(cases={"a": (True, 3)}, precision=1.0, revision="700bad3"),
        ],
    )
    with pytest.raises(IncomparableRuns) as refusal:
        compute(runs)
    assert "code_revision" in str(refusal.value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("dataset_version", "gold"),
        ("model_id", "amazon.nova-pro-v1:0"),
        ("artifact_version", "0.6.0"),
        ("artifact_pin", "0.4.0"),
        ("provider", "scripted"),
    ],
)
def test_every_pooling_field_is_actually_checked(tmp_path: Path, field: str, value: str) -> None:
    """Parametrised because a list of fields is exactly the kind of thing that grows a member which
    nothing verifies. An artifact that moved under the dataset is the one that matters most: it
    silently invalidates the benchmark, which is what `.claude/rules/evals.md` means by pinning."""
    runs = five(
        tmp_path,
        [
            payload(cases={"a": (True, 3)}),
            payload(cases={"a": (True, 3)}, overrides={field: value}),
        ],
    )
    with pytest.raises(IncomparableRuns) as refusal:
        compute(runs)
    assert field in str(refusal.value)


def test_a_different_case_set_is_refused(tmp_path: Path) -> None:
    """`--cases 1` writes a result file that looks like every other one. It is the file most likely
    to be sitting in the results directory when the newest-five default picks a pool."""
    runs = five(
        tmp_path,
        [
            payload(cases={"a": (True, 3), "b": (True, 2)}),
            payload(cases={"a": (True, 3)}),
        ],
    )
    with pytest.raises(IncomparableRuns):
        compute(runs)


def test_an_incomplete_run_is_refused(tmp_path: Path) -> None:
    """A budget-aborted run's cases were chosen by exhaustion, so its distance from a complete run
    is not noise. `budget.py` writes partial results on purpose; this is the consumer honouring the
    ``complete`` flag it wrote them with."""
    runs = five(
        tmp_path,
        [
            payload(cases={"a": (True, 3)}),
            payload(cases={"a": (True, 3)}, complete=False),
        ],
    )
    with pytest.raises(IncompleteRun) as refusal:
        compute(runs)
    assert "token budget exhausted" in str(refusal.value)


# --- provisional --------------------------------------------------------------------------------


def test_four_runs_compute_but_cannot_set_a_threshold(tmp_path: Path) -> None:
    """Under five, the floor renders and refuses to be used. Report loudly, never silently pass."""
    runs = five(tmp_path, [payload(cases={"a": (True, 3)})] * 4)
    floor = compute(runs)

    assert not floor.sufficient
    assert "PROVISIONAL" in render(floor)
    with pytest.raises(ProvisionalNoiseFloor):
        floor.tolerance_for("traversal_recall")


def test_a_dirty_tree_makes_the_floor_provisional(tmp_path: Path) -> None:
    """Two runs both labelled ``abc1234-dirty`` can have come from different working trees, so the
    label matches without being an identity. Pooling is allowed; setting a threshold is not."""
    runs = five(
        tmp_path, [payload(cases={"a": (True, 3)}, revision="abc1234-dirty")] * MINIMUM_RUNS
    )
    floor = compute(runs)

    assert not floor.sufficient
    assert "does not identify a working tree" in " ".join(floor.provisional_reasons)
    with pytest.raises(ProvisionalNoiseFloor):
        floor.tolerance_for("traversal_recall")


def test_an_unrecorded_revision_is_provisional_not_fatal(tmp_path: Path) -> None:
    """Result files written before `provenance.py` existed carry no revision at all. They are still
    worth pooling — an unknown pooled with an unknown is self-consistent — and they still cannot set
    a threshold."""
    bodies = [payload(cases={"a": (True, 3)}) for _ in range(MINIMUM_RUNS)]
    for body in bodies:
        del body["code_revision"]
    floor = compute(five(tmp_path, bodies))

    assert floor.code_revision == UNKNOWN
    assert not floor.sufficient


def test_five_clean_runs_yield_a_usable_tolerance(tmp_path: Path) -> None:
    """The happy path, and the only state that may feed `thresholds.json`."""
    runs = five(
        tmp_path,
        [
            payload(cases={"a": (True, 3)}, recall=0.90),
            payload(cases={"a": (True, 3)}, recall=0.94),
            payload(cases={"a": (True, 3)}, recall=1.00),
            payload(cases={"a": (True, 3)}, recall=0.96),
            payload(cases={"a": (True, 3)}, recall=0.92),
        ],
    )
    floor = compute(runs)

    assert floor.sufficient
    assert floor.tolerance_for("traversal_recall") == pytest.approx(0.10)
    assert "traversal_recall" in floor.metrics_wider_than(0.05)


# --- what the spread says -----------------------------------------------------------------------


def test_the_tolerance_is_the_measured_spread_and_nothing_more(tmp_path: Path) -> None:
    """No padding, no rounding to a friendlier figure. Deciding how much headroom a gate needs above
    the floor is a step 5 decision written down with its reasoning, not a multiplier hidden here."""
    runs = five(
        tmp_path,
        [payload(cases={"a": (True, 3)}, recall=value) for value in (0.80, 0.85, 0.90, 0.95, 1.00)],
    )
    assert compute(runs).tolerance_for("traversal_recall") == pytest.approx(0.20)


def test_an_undefined_metric_is_counted_not_treated_as_zero(tmp_path: Path) -> None:
    """A rate with a zero denominator is undefined, and `Rate` already refuses to call it perfect.
    Folding those runs in as 0.0 would invent a spread; dropping them silently would let a metric
    that was undefined four times in five report a tight spread over its single real value."""
    runs = five(
        tmp_path,
        [
            payload(cases={"a": (True, 3)}, groundedness=None),
            payload(cases={"a": (True, 3)}, groundedness=None),
            payload(cases={"a": (True, 3)}, groundedness=None),
            payload(cases={"a": (True, 3)}, groundedness=None),
            payload(cases={"a": (True, 3)}, groundedness=1.0),
        ],
    )
    spread = compute(runs).spread_for("edge_groundedness")

    assert spread.undefined_runs == 4
    assert spread.values == (1.0,)
    assert spread.spread == 0.0
    assert "[4 undefined]" in spread.render()


def test_refusal_is_spread_as_a_pair(tmp_path: Path) -> None:
    """`.claude/rules/grounding-and-claims.md`: refusal accuracy is reported as a pair, always. A
    floor that tracked only true refusals would give a system that refuses everything a perfect and
    perfectly stable score."""
    floor = compute(five(tmp_path, [payload(cases={"a": (True, 3)})] * MINIMUM_RUNS))
    metrics = {spread.metric for spread in floor.spreads}
    assert {"true_refusal_rate", "false_refusal_rate"} <= metrics


# --- membership churn ---------------------------------------------------------------------------


def test_a_stable_aggregate_hiding_a_changed_membership_is_surfaced(tmp_path: Path) -> None:
    """**The finding runs 1 and 2 actually produced**, reduced to its shape.

    Both runs scored the same total and failed *different* cases. ``cases_correct`` has a spread of
    exactly zero, which is true and reads as stability. The floor has to say the other thing.
    """
    runs = five(
        tmp_path,
        [
            payload(cases={"gold_020": (False, 0), "adv_018": (True, 4), "adv_008": (False, 1)}),
            payload(cases={"gold_020": (True, 6), "adv_018": (False, 0), "adv_008": (False, 1)}),
        ],
    )
    floor = compute(runs)

    assert floor.spread_for("cases_correct").spread == 0.0
    assert {case.case_id for case in floor.unstable_cases} == {"gold_020", "adv_018"}
    assert [case.case_id for case in floor.reproducible_failures] == ["adv_008"]

    text = render(floor)
    assert "2 of 3 cases did not give the same verdict every run" in text
    assert "UNSTABLE" in text


def test_a_reproducible_failure_is_distinguished_from_a_coin(tmp_path: Path) -> None:
    """The distinction this module exists to draw, and the live runs have not yet produced an example
    of the first kind: after three runs `adv_008` is 2 of 3, `gold_v0_1_020` is 2 of 3, `adv_018` is 1
    of 3, and **no case has been wrong in all three.** Two runs made `adv_008` look reproducible and it
    was not. Nothing but repetition can tell a finding from a coin."""
    runs = five(
        tmp_path,
        [
            payload(cases={"coin": (True, 2), "always": (False, 0)}),
            payload(cases={"coin": (False, 0), "always": (False, 0)}),
        ],
    )
    floor = compute(runs)

    coin, always = floor.cases
    assert not coin.stable and coin.claim_swing == 2
    assert always.stable and always.always_wrong


def test_claim_counts_move_even_when_the_verdict_does_not(tmp_path: Path) -> None:
    """Approved claims moved 69 to 79 between the two live runs while `cases_correct` sat still. A
    case can be scored correct on very different amounts of work."""
    runs = five(
        tmp_path,
        [payload(cases={"a": (True, 3)}), payload(cases={"a": (True, 9)})],
    )
    floor = compute(runs)

    assert floor.spread_for("cases_correct").spread == 0.0
    assert floor.spread_for("approved_claims").spread == 6.0
    assert floor.cases[0].claim_swing == 6


# --- selection ----------------------------------------------------------------------------------


def test_recent_runs_does_not_filter_for_comparability(tmp_path: Path) -> None:
    """It returns the newest N and lets `compute` refuse. Silently selecting the subset that happens
    to agree would hide the situation the pooling guard exists to surface, and the operator would
    never learn that the run they thought was in the pool was dropped."""
    for name in ("20260816T010000Z", "20260816T020000Z", "20260816T030000Z"):
        (tmp_path / f"{name}-bedrock.json").write_text("{}", encoding="utf-8")
    (tmp_path / "20260816T025959Z-scripted.json").write_text("{}", encoding="utf-8")

    selected = recent_runs(directory=tmp_path, count=2)
    assert [path.name for path in selected] == [
        "20260816T020000Z-bedrock.json",
        "20260816T030000Z-bedrock.json",
    ]


# --- provenance ---------------------------------------------------------------------------------


def test_code_revision_reports_dirty_when_the_tree_is_dirty() -> None:
    def fake(command: object, cwd: object) -> str | None:
        return "abc1234\n" if "rev-parse" in command else " M src/thing.py\n"  # type: ignore[operator]

    assert code_revision(run=fake) == "abc1234-dirty"


def test_code_revision_assumes_dirty_when_cleanliness_cannot_be_determined() -> None:
    """HEAD resolved and ``git status`` failed. Unknown-clean is the dangerous answer."""

    def fake(command: object, cwd: object) -> str | None:
        return "abc1234\n" if "rev-parse" in command else None  # type: ignore[operator]

    assert code_revision(run=fake) == "abc1234-dirty"


def test_code_revision_never_raises_when_git_is_unavailable() -> None:
    """Gathered on the way out of a billable run. There is no failure here worth losing that run for."""
    assert code_revision(run=lambda command, cwd: None) == UNKNOWN
    assert not is_pinnable(UNKNOWN)


def test_a_real_revision_is_pinnable() -> None:
    assert is_pinnable("24517e1")
    assert not is_pinnable("24517e1-dirty")


# --- the results-directory exemption, added 2026-08-23 -------------------------------------------
#
# The defect this closes: a judge run writes its result file into `eval/results/`, `.gitignore`
# re-includes judge results, and so run N's own output made the tree untracked-dirty for run N+1.
# Run 3 was stamped `fd79865-dirty` over code byte-identical to run 2's, which `is_pinnable` then
# refused and `noise.py` then refused to pool. Both directions are locked below, because an exemption
# that is too wide is a false *clean* and there is no recovering from one of those after the fact.


def _status(*lines: str) -> Callable[..., str | None]:
    def fake(command: object, cwd: object) -> str | None:
        if "rev-parse" in command:  # type: ignore[operator]
            return "abc1234\n"
        return "".join(line + "\n" for line in lines)

    return fake


def test_a_stray_result_file_does_not_dirty_the_stamp() -> None:
    assert (
        code_revision(
            run=_status("?? src/musical_mycelium/eval/results/20260823T000000Z-judge.json")
        )
        == "abc1234"
    )


def test_a_stray_source_file_still_dirties_the_stamp() -> None:
    """The other half. An exemption nobody tried to break is not an exemption, it is a hole."""
    assert code_revision(run=_status("?? src/musical_mycelium/eval/tier2.py")) == "abc1234-dirty"


def test_a_modified_source_file_dirties_even_beside_an_exempt_one() -> None:
    """One exempt line must not launder the tree for the lines around it."""
    fake = _status(
        "?? src/musical_mycelium/eval/results/20260823T000000Z-judge.json",
        " M src/musical_mycelium/eval/judge.py",
    )
    assert code_revision(run=fake) == "abc1234-dirty"


def test_a_path_merely_resembling_the_results_directory_is_not_exempt() -> None:
    """`results_backup/` is not `results/`, and prefix matching is exactly where that slips."""
    assert (
        code_revision(run=_status("?? src/musical_mycelium/eval/results_backup/x.json"))
        == "abc1234-dirty"
    )


def test_a_rename_out_of_the_results_directory_dirties() -> None:
    """A rename dirties on either side; only a line with every path exempt is clean."""
    fake = _status("R  src/musical_mycelium/eval/results/a.json -> src/musical_mycelium/eval/a.py")
    assert code_revision(run=fake) == "abc1234-dirty"


def test_an_unreadable_status_line_counts_as_dirty() -> None:
    """Guessing on a line this cannot parse would be a false clean, so it does not guess."""
    assert code_revision(run=_status("garbage")) == "abc1234-dirty"


def test_a_stray_transcript_does_not_dirty_the_stamp() -> None:
    """The same defect one directory over, and the one that would have bitten run N+2: `eval/results/`
    is gitignored but `eval/transcripts/` is tracked, so a live run's own transcript is an untracked
    file the moment it is written."""
    assert (
        code_revision(
            run=_status("?? src/musical_mycelium/eval/transcripts/20260823T231500Z-bedrock.json")
        )
        == "abc1234"
    )


def test_the_exemption_covers_run_output_only_and_not_the_eval_package() -> None:
    """Named directories, not a wildcard over `eval/`. The package is almost entirely code."""
    for path in (
        "src/musical_mycelium/eval/tier2.py",
        "src/musical_mycelium/eval/datasets/gold_v0_1.json",
        "src/musical_mycelium/eval/rubrics/citation_support.md",
        "src/musical_mycelium/eval/noise_floor.json",
        "src/musical_mycelium/eval/thresholds.json",
    ):
        assert code_revision(run=_status(f" M {path}")) == "abc1234-dirty", path
