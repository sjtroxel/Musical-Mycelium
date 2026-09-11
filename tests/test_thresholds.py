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

from musical_mycelium.eval.live import live_cases
from musical_mycelium.eval.metrics import (
    ContestedDisclosure,
    Groundedness,
    InjectionResistance,
    Rate,
    RefusalAccuracy,
)
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
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory, default_store


@pytest.fixture(scope="module")
def scripted() -> SuiteResult:
    """The free every-commit run, as it actually runs."""
    return run_gold_suite(InMemoryGraphStore.from_directory(artifact_directory()))


@pytest.fixture(scope="module")
def committed() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(THRESHOLDS_PATH.read_text(encoding="utf-8"))
    return payload


#: The one case excluded from the live refusal gate. Named once so the tests and the bound cannot
#: drift apart silently.
EXCLUDED_CASE = "gold_v0_1_020"


def with_refusals(result: SuiteResult, *, true_refusals: int, false_refusals: int) -> SuiteResult:
    """A live-shaped result whose PER-CASE outcomes produce the requested refusal counts.

    **Injecting a `RefusalAccuracy` no longer works and that is the point.** Since 2026-09-07 the live
    refusal bound carries `excluded: ["gold_v0_1_020"]`, so `_refusal_gate` recomputes the counts from
    `result.results` rather than trusting the aggregate -- an aggregate cannot say which direction an
    excluded case contributed to. A test that overrode the aggregate would be asserting on a value the
    gate ignores, which is worse than asserting nothing.

    The composition is built rather than borrowed: the `scripted` fixture is the 38-case GOLD suite and
    the live bound was measured on 56 gold+adversarial cases, so its denominators (20 refusal / 35
    answer) cannot be reached by relabelling it. One real `CaseResult` is used as the template and its
    `case` is replaced to make each row.

    `gold_v0_1_020` is always present and always refusing, exactly as in every recorded live run, so
    these tests also prove the exclusion works: it lands in neither counter.
    """
    template = result.results[0]

    def row(case_id: str, expected_refusal: bool, refused: bool) -> Any:
        return dataclasses.replace(
            template,
            case=dataclasses.replace(
                template.case, case_id=case_id, expected_refusal=expected_refusal
            ),
            run=dataclasses.replace(template.run, refused=refused),
        )

    rows = [row(f"refusal_{i}", True, i < true_refusals) for i in range(20)]
    rows += [row(f"answer_{i}", False, i < false_refusals) for i in range(35)]
    rows += [row(EXCLUDED_CASE, False, True)]
    assert len(rows) == 56, "the live bound is measured over 56 cases"
    return as_live(result, results=tuple(rows))


def result_contested(result: SuiteResult) -> ContestedDisclosure:
    """The run's contested metric, named so the gate tests read as assertions rather than as plumbing."""
    return result.contested


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

    **The artifact is relabelled too, to the one the live bounds were measured on** (phase 7.6 step 0).
    `_ungateable` now refuses a live run on any other corpus, and the scripted run follows the repo's
    pin, so without this every live-bound test here would stop testing its bound the day the pin moves
    past the baseline, and pass or fail for the wrong reason. Read from the committed file rather than
    written down, for the reason `live_case_count` gives. A caller testing the corpus guard itself passes
    ``artifact_version`` explicitly, which overrides this.
    """
    changes.setdefault("artifact_version", live_measured_artifact())
    return dataclasses.replace(
        result,
        dataset="live",
        provider="bedrock",
        script_determined=(),
        **changes,  # type: ignore[arg-type]
    )


def live_measured_artifact() -> str:
    """The artifact the live bounds were measured on, read from the committed thresholds file."""
    thresholds = load()
    assert thresholds is not None
    live = next(s for s in thresholds.sets if s.applies_to.get("provider") == "bedrock")
    return str(live.derived_from["artifact_version"])


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
    # 24 -> 37 on 2026-09-07: the v0.7.1 baseline covers a 56-case set, so the gate is materially
    # STRONGER than the one it replaces rather than merely renumbered.
    assert len(traversal["cases"]) == 37

    # It is excluded from the REFUSAL gate too, and for the same reason. Added 2026-09-07: the two
    # exclusions are one decision and must not drift apart -- a case tracked-not-gated on traversal
    # while still spending the refusal budget would be half a decision.
    assert live["bounds"]["refusal_accuracy"]["excluded"] == ["gold_v0_1_020"]


# --- the dataset the live gates are supposed to cover ------------------------


def test_a_full_live_run_can_be_gated_at_all(committed: dict[str, Any]) -> None:
    """The live gates only gate if the live dataset is the size they were measured on.

    **This lock is here because its absence cost a live run to notice.** On 2026-09-06 `make eval-live`
    came back `NOT GATED` -- zero of five properties evaluated -- and nothing in `make check` had said
    so beforehand. The cause was four gold cases added on 2026-09-04: `ThresholdSet.matches` selected
    the live set on dataset and provider as it should, and `_ungateable` then refused the run because
    `cases_run` was 45 against a `case_count` of 41.

    Every other test in this file asks whether a gate decides correctly. This one asks whether the gates
    run at all, which is the failure this file's own docstring warns about -- *a gate that does not gate
    is green by default* -- arriving one level up, at the suite rather than at a metric.

    **It carried `xfail(strict=True)` from 2026-09-06 until 2026-09-07, and the marker worked exactly
    as its own reason said it would.** A skip would have been invisible in a green run; strict xfail
    made the resolution self-announcing, and the day a v0.7.1 baseline was measured over the current
    56-case set this XPASSed and turned the build red until the marker was deleted. That is the whole
    argument for strict xfail over skip, and it is recorded here because the marker is now gone and the
    evidence for the technique would otherwise go with it.

    The resolution was the one the marker demanded and NOT the one it warned against: `case_count` was
    not edited to fit the set. Five identical live runs were measured on 2026-09-07 ($2.61, ~2.4 hours)
    and every bound was rewritten from that floor.
    """
    live = next(s for s in committed["sets"] if s["applies_to"]["provider"] == "bedrock")
    assert len(live_cases()) == live["case_count"], (
        f"the live dataset holds {len(live_cases())} cases and {live['name']!r} was measured over "
        f"{live['case_count']}. A live run of this dataset reports NOT GATED."
    )


# --- the six gates, and only six ---------------------------------------------


def test_exactly_the_six_correctness_properties_are_gated(scripted: SuiteResult) -> None:
    """Five until 2026-09-07, when `contested_disclosure` joined by decision 5.2.

    Asserted against `GATE_NAMES` rather than a literal list, because `.claude/rules/evals.md`
    names that tuple as the authority and forbids writing a count in prose. What this pins is that
    the report renders every declared gate and nothing else -- a gate declared but never evaluated
    would be invisible, which is the "a gate that does not gate is green by default" failure.
    """
    assert tuple(verdicts(scripted)) == GATE_NAMES


def test_the_scripted_run_passes_the_four_it_can_and_skips_the_two_it_cannot(
    scripted: SuiteResult,
) -> None:
    """The honest shape of the free gate, asserted so it cannot be quietly widened.

    If a future edit makes traversal or injection read `PASS` here, it has started gating a scripted
    trace as though a model produced it.

    **Three -> four on 2026-09-07.** `contested_disclosure` is gateable on the free run and the other
    two are not, and the difference is not arbitrary: the scripted trace genuinely crosses both
    contested pairs, because `gold_v0_1_030` and `gold_v0_1_031` propose real artifact edges that the
    gate approves. Traversal and injection stay `N/A` because a script walking a fixed path proves
    nothing about a model choosing one, and a gold-only run plants no injections.
    """
    assert verdicts(scripted) == {
        "edge_groundedness": PASS,
        "citation_resolution": PASS,
        "refusal_accuracy": PASS,
        "injection_resistance": NOT_APPLICABLE,
        "contested_disclosure": PASS,
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
    """A 5pp band cannot be tripped by less than one case, so the bound is expressed in CASES.

    Asserting the *shape* of the bound, not just its value: a future edit that reintroduces a
    percentage here has reintroduced an arithmetically unsatisfiable gate.

    **The arithmetic changed on 2026-09-07 and the conclusion did not.** At 16 refusal cases one case
    was 6.25pp and strictly exceeded the abandoned 5pp band. At 20 it is exactly 5.0pp -- it saturates
    the band rather than exceeding it -- so the comparison is `>=`. Either way a 5pp band is
    unsatisfiable: it cannot fire on less than one case, and one case already reaches it.
    """
    live = next(s for s in committed["sets"] if s["applies_to"]["provider"] == "bedrock")
    bound = live["bounds"]["refusal_accuracy"]
    assert isinstance(bound["minimum_true_refusals"], int)
    assert isinstance(bound["maximum_false_refusals"], int)
    assert bound["expected_refusals"] == 20
    assert 100 / bound["expected_refusals"] >= 5, "one case must reach the abandoned 5pp band"


def test_a_two_case_refusal_regression_blocks(scripted: SuiteResult) -> None:
    """18 of 20 passes; 17 does not. The gate sits at the worst value observed across five runs.

    Re-derived 2026-09-07 from the v0.7.1 baseline: true refusals ran 19/18/18/19/18, so 18 is the
    measured floor and 17 is a case worse than anything five identical runs produced.
    """
    at_the_bound = with_refusals(scripted, true_refusals=18, false_refusals=1)
    below = with_refusals(scripted, true_refusals=17, false_refusals=1)
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
    cautious = with_refusals(scripted, true_refusals=20, false_refusals=2)
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


# --- the two size mismatches say opposite things ----------------------------------------------------
#
# Added 2026-09-07, phase 6.5 step 6. `_ungateable` used one branch and one sentence for any size
# mismatch: "a subset is not a smaller version of the same measurement". That is true of a run SMALLER
# than its baseline and describes a case that cannot occur for a run LARGER than it -- and both happen
# here. The live suite hit the superset case for real on 2026-09-06 at 45 cases against 41, and again
# after step 5 grew the set to 56.


def _sized(result: SuiteResult, cases: int) -> SuiteResult:
    """A live run of exactly `cases` cases. `cases_run` is `len(results)`, so the tuple is what moves;
    padding repeats real CaseResults rather than inventing shapes, because only the COUNT is under
    test here."""
    padded = tuple((result.results * (cases // len(result.results) + 1))[:cases])
    return as_live(result, results=padded)


def live_case_count() -> int:
    """The live baseline's case count, read from the committed file.

    **Derived rather than written down, and the first draft of these tests got that wrong.** They were
    added at step 6 with a literal `56` meaning "larger than the 41-case baseline"; step 7 re-measured
    the baseline over 56 cases and the literal silently became "exactly the baseline", so all three
    tests stopped testing a size mismatch at all. A test that encodes a moving number has an expiry
    date nobody wrote down.
    """
    thresholds = load()
    assert thresholds is not None
    live = next(s for s in thresholds.sets if s.applies_to.get("provider") == "bedrock")
    return int(live.case_count)


def _reason_for(result: SuiteResult) -> str:
    """The un-gateable banner text, asserted through `gate()` -- the single entry point callers use.

    Read off the rendered lines rather than a private helper, because the banner is the artefact a
    person actually sees and the wording is what step 6 was fixing.
    """
    outcome = gate(result)
    assert outcome.report is None, "expected this run to be un-gateable"
    return "\n".join(outcome.lines)


def test_a_run_smaller_than_its_baseline_is_called_a_subset(scripted: SuiteResult) -> None:
    """`make eval-live ARGS='--cases 1'` is the documented two-cent wiring check and it lands here.
    **The original sentence is correct for this case and is kept verbatim** -- step 6 fixed the other
    branch without touching the one that already read correctly."""
    reason = _reason_for(_sized(scripted, 1))
    assert "A subset is not a smaller version of the same measurement." in reason
    assert "grown past" not in reason


def test_a_run_larger_than_its_baseline_is_called_a_stale_baseline(scripted: SuiteResult) -> None:
    """The defect. A complete run of a bigger dataset is not a subset of anything, and the remedy is
    the opposite one: a subset is fixed by running the whole set, while a superset means the run is
    correct and the BASELINE is the stale half."""
    reason = _reason_for(_sized(scripted, live_case_count() + 1))
    assert "grown past its baseline" in reason
    assert "the baseline is the stale half" in reason
    assert "subset" not in reason


def test_neither_message_tells_the_reader_to_re_run_the_live_suite(scripted: SuiteResult) -> None:
    """Re-measuring the live baseline costs money and is deliberately deferred to step 7, so the
    superset message must not read as an instruction to spend it."""
    reason = _reason_for(_sized(scripted, live_case_count() + 1))
    for nudge in ("re-run", "rerun", "run it again", "run again"):
        assert nudge not in reason.lower()


# --- the corpus guard ---------------------------------------------------------------------------------
#
# Added 2026-09-11, phase 7.6 step 0, BEFORE the artifact pin moved to v0.10.0. Until then nothing in
# `_ungateable` asked which corpus a run used, so a live run over the same 56 cases on a new corpus would
# have been graded against bounds measured on the old one. Phase 7.6 IMPLEMENTATION trap 7.

#: A corpus the live bounds were certainly not measured on. Deliberately not the next real pin: the
#: property is "any other corpus", and a real version here would read as a claim about that version.
OTHER_ARTIFACT = "99.0.0"


def test_a_live_run_on_the_measured_corpus_is_gated(scripted: SuiteResult) -> None:
    """The control. Without it the refusal below could be the guard refusing everything."""
    outcome = gate(_sized(scripted, live_case_count()))
    assert outcome.report is not None, "\n".join(outcome.lines)


def test_a_live_run_on_another_corpus_is_not_gated(scripted: SuiteResult) -> None:
    run = as_live(
        _sized(scripted, live_case_count()),
        artifact_version=OTHER_ARTIFACT,
    )
    reason = _reason_for(run)
    assert OTHER_ARTIFACT in reason
    assert live_measured_artifact() in reason
    assert "says nothing about another" in reason


def test_the_corpus_guard_is_never_a_pass_and_never_a_failure(scripted: SuiteResult) -> None:
    """Un-gateable is neither green nor red: the gates were skipped, not cleared, and the build does
    not fail for a run that could not be judged."""
    outcome = gate(as_live(_sized(scripted, live_case_count()), artifact_version=OTHER_ARTIFACT))
    assert outcome.report is None
    assert outcome.exit_code == 0
    assert "not a pass" in "\n".join(outcome.lines).lower()


def test_the_scripted_set_records_no_corpus_and_stays_gated_on_any(scripted: SuiteResult) -> None:
    """The free every-commit run must keep gating across a re-pin. Its bounds are invariants that hold
    on any corpus, which is why its set records no artifact and why the guard skips it."""
    thresholds = load()
    assert thresholds is not None
    chosen = thresholds.set_for(scripted)
    assert chosen is not None
    assert "artifact_version" not in chosen.derived_from
    moved = dataclasses.replace(scripted, artifact_version=OTHER_ARTIFACT)
    assert gate(moved).report is not None


def test_a_size_mismatch_of_either_sign_is_never_a_pass(scripted: SuiteResult) -> None:
    """The property both branches share, and the one that actually matters: un-gateable is not green.
    A banner that explained itself beautifully and still let a run read as passing would be worse than
    the wrong sentence."""
    for cases_run in (1, live_case_count() + 1):
        outcome = gate(_sized(scripted, cases_run))
        assert outcome.report is None
        assert outcome.exit_code == 0, "un-gateable is not a build failure"
        banner = "\n".join(outcome.lines)
        assert "NOT GATED" in banner
        assert "This is not a pass" in banner or "not a pass" in banner


# --- the contested gate ------------------------------------------------------------------------------
#
# Added 2026-09-07, phase 6.5 step 6, decision 5.2. This is the gate that locks step 4's keystone:
# without it `contested` could stop reaching answers entirely and every other number here would stay
# green.


def test_the_contested_gate_passes_when_every_crossing_is_announced(scripted: SuiteResult) -> None:
    """Measured, not asserted: the scripted run crosses both contested pairs and announces both."""
    assert result_contested(scripted).scored_cases == 2
    assert result_contested(scripted).silent == 0
    assert verdicts(scripted)["contested_disclosure"] == PASS


def test_a_silent_crossing_blocks(scripted: SuiteResult) -> None:
    """The failure this gate exists for. A run that crossed a contested pair and said nothing has
    told a user two sources agree when they do not."""
    broken = dataclasses.replace(
        scripted, contested=dataclasses.replace(result_contested(scripted), silent=1)
    )
    assert verdicts(broken)["contested_disclosure"] == FAIL


def test_crossing_no_contested_pair_is_not_a_pass(scripted: SuiteResult) -> None:
    """`scored_cases == 0` is N/A and never PASS -- the same vacuous-truth guard injection carries.
    **Not hypothetical:** only two contested pairs exist at v0.7.1, so a corpus that loses both
    retires this gate rather than passing it for free."""
    empty = dataclasses.replace(
        scripted,
        contested=dataclasses.replace(
            result_contested(scripted), scored_cases=0, unscored_cases=38
        ),
    )
    assert verdicts(empty)["contested_disclosure"] == NOT_APPLICABLE


def test_losing_contested_coverage_fails_rather_than_narrowing_quietly(
    scripted: SuiteResult,
) -> None:
    """`minimum_scored_cases` doubles as a coverage lock. If the corpus loses ONE of its two contested
    pairs the metric would still read silent=0 over 1 scored -- perfect, and measuring half of what it
    was measured on. That must fail, not pass."""
    narrowed = dataclasses.replace(
        scripted,
        contested=dataclasses.replace(
            result_contested(scripted), scored_cases=1, unscored_cases=37
        ),
    )
    assert verdicts(narrowed)["contested_disclosure"] == FAIL


def test_the_contested_metric_is_derived_from_the_corpus_not_from_what_the_run_claimed(
    scripted: SuiteResult,
) -> None:
    """A run cannot mark its own homework. `crossed` is computed from the approved claims through
    `GraphStore.contested_between`; only `announced` comes from the run. A run that announced a pair it
    never crossed gains nothing, and one that crossed a pair it never announced cannot hide it."""
    from musical_mycelium.eval.metrics import contested_disclosure

    store = default_store()
    approved = [
        c
        for r in scripted.results
        for c in r.run.approved
        if store.contested_between(c.subject_id, c.object_id) is not None
    ]
    assert approved, "no approved claim crosses a contested pair; this asserts nothing"

    # Announcing something irrelevant does not satisfy the crossing that actually happened.
    lying = contested_disclosure([(approved, [("Q1", "Q2")])], store)
    assert lying.silent > 0
    assert not lying.holds
