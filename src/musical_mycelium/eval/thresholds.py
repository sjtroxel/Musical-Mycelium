"""The gates: what makes a suite run fail the build, and what is only reported.

Phase 4 step 5, written **after** step 6 because a threshold chosen before its noise floor is a guess
wearing a number. `eval/noise_floor.json` is the input; `eval/thresholds.json` is the output; this
module is what reads one against a `SuiteResult`.

`.claude/rules/evals.md` sets the shape: *"Block on correctness properties, track quality preferences.
A suite that blocks on everything gets disabled within two weeks; a suite that blocks on nothing gets
ignored."* Five things block and nothing else does.

## Three states, not two

A gate is `PASS`, `FAIL`, or **`N/A`**, and the third one is load-bearing. Two of the five gates cannot
be evaluated at all on a free scripted run:

- **traversal recall is `SCRIPT_DETERMINED` there** — the trace policy walks the path, not a model, so
  a live-derived traversal number gating a scripted run would read as a real gate in CI while measuring
  the script. That is precisely the confusion `report.py`'s rule 2 exists to prevent.
- **injection resistance scores zero cases there** — the planted injections live in the adversarial set
  and the free run is gold-only. `InjectionResistance.holds` already refuses to call an untested
  property proven, and a gate has to inherit that refusal rather than quietly reading `induced == 0` as
  a pass.

So `N/A` is never counted as a pass, `render` reports gated / failed / inapplicable as three separate
counts, and a run where every gate is inapplicable cannot come out looking green. The honest
consequence, stated here because it is the kind of limit that gets rounded away: **the free
every-commit gate blocks on three of the five correctness properties. The other two need money.**

## What a missing file means

Loudly nothing, and deliberately not "pass". `load` returns `None`, `make eval` prints a `NOT GATED`
banner and exits 0. Absent thresholds are not a build failure — but a suite that silently passes when
its thresholds are missing is worse than no suite, so the banner says which state it is in.

## Why the bounds are where they are

Not in this module. Every gate carries its measured values and its reasoning in `thresholds.json`
itself, next to the number, because a bare bound invites being tightened later by someone who does not
know what it cost to measure. The two that are not percentages — refusal accuracy in cases, traversal
recall per case — are explained at length in the phase 4 implementation doc under "Step 5, as-built".
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from musical_mycelium.eval.metrics import Rate
from musical_mycelium.eval.suite import SuiteResult

THRESHOLDS_PATH = Path(__file__).parent / "thresholds.json"

PASS = "PASS"
FAIL = "FAIL"
NOT_APPLICABLE = "N/A"

#: The five and only five. Ordered as they render. `.claude/rules/evals.md` names exactly these as
#: blocking and everything else as tracked; adding a sixth is a decision, not a tweak.
GATE_NAMES = (
    "edge_groundedness",
    "citation_resolution",
    "refusal_accuracy",
    "injection_resistance",
    "traversal_recall",
)


class MalformedThresholds(RuntimeError):
    """`thresholds.json` exists but cannot be read as thresholds.

    Raised rather than skipped. A malformed gate file degrading to "no gates" is the same silent pass
    the missing-file rule exists to prevent, except harder to notice because the file is right there.
    """


@dataclass(frozen=True, slots=True)
class GateResult:
    """One gate's verdict, carrying enough to be read without opening the threshold file."""

    name: str
    verdict: str
    observed: str
    expected: str
    note: str = ""

    @property
    def blocks(self) -> bool:
        return self.verdict == FAIL

    def render(self) -> str:
        line = (
            f"  [{self.verdict:4}] {self.name}: observed {self.observed}; required {self.expected}"
        )
        return f"{line}\n         {self.note}" if self.note else line


@dataclass(frozen=True, slots=True)
class ThresholdReport:
    """The gate results for one run, plus which threshold set produced them."""

    set_name: str
    applies_to: Mapping[str, str]
    derived_from: Mapping[str, Any]
    gates: tuple[GateResult, ...]

    @property
    def failures(self) -> tuple[GateResult, ...]:
        return tuple(gate for gate in self.gates if gate.verdict == FAIL)

    @property
    def inapplicable(self) -> tuple[GateResult, ...]:
        return tuple(gate for gate in self.gates if gate.verdict == NOT_APPLICABLE)

    @property
    def passed(self) -> tuple[GateResult, ...]:
        return tuple(gate for gate in self.gates if gate.verdict == PASS)

    @property
    def blocks(self) -> bool:
        """True when the build should fail. Inapplicable gates never make this true, and never make it
        false either — they are simply not evidence in either direction."""
        return bool(self.failures)

    def render(self) -> list[str]:
        lines = [
            f"gates: {self.set_name}  "
            f"(from {self.derived_from.get('source', 'an unrecorded source')}, "
            f"{self.derived_from.get('decided', 'undated')})",
        ]
        lines.extend(gate.render() for gate in self.gates)
        lines.append(
            f"  {len(self.passed)} passed, {len(self.failures)} FAILED, "
            f"{len(self.inapplicable)} not applicable, of {len(self.gates)} correctness properties"
        )
        if self.inapplicable:
            lines.append(
                "  NOT APPLICABLE IS NOT A PASS. "
                + "; ".join(f"{gate.name} -- {gate.note}" for gate in self.inapplicable)
            )
        if self.blocks:
            lines.append("  BLOCKING: " + ", ".join(gate.name for gate in self.failures))
        return lines


@dataclass(frozen=True, slots=True)
class ThresholdSet:
    """One set of bounds and the kind of run they were measured on."""

    name: str
    applies_to: Mapping[str, str]
    derived_from: Mapping[str, Any]
    bounds: Mapping[str, Any]
    case_count: int

    def matches(self, result: SuiteResult) -> bool:
        """Dataset **and** provider must both match.

        Provider alone is not enough and that is the whole reason this class exists. The live floor was
        measured over 41 gold+adversarial cases with 16 refusal cases; the free run is 25 gold cases
        with 3. Same provider family, entirely different denominators, and a count gate crossing that
        boundary compares two different questions.
        """
        return (
            self.applies_to.get("dataset") == result.dataset
            and self.applies_to.get("provider") == result.provider
        )


@dataclass(frozen=True, slots=True)
class Thresholds:
    """Every threshold set in the file."""

    path: Path
    sets: tuple[ThresholdSet, ...]

    def set_for(self, result: SuiteResult) -> ThresholdSet | None:
        for candidate in self.sets:
            if candidate.matches(result):
                return candidate
        return None


def load(path: Path = THRESHOLDS_PATH) -> Thresholds | None:
    """The thresholds, or ``None`` when the file does not exist.

    ``None`` is the documented "report loudly, do not block" state. A file that exists and is broken is
    a different thing entirely and raises.
    """
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MalformedThresholds(f"{path} is not valid JSON: {exc}") from exc

    raw_sets = payload.get("sets")
    if not isinstance(raw_sets, list) or not raw_sets:
        raise MalformedThresholds(f"{path} declares no threshold sets")

    sets: list[ThresholdSet] = []
    for index, raw in enumerate(raw_sets):
        try:
            sets.append(
                ThresholdSet(
                    name=raw["name"],
                    applies_to=raw["applies_to"],
                    derived_from=raw.get("derived_from", {}),
                    bounds=raw["bounds"],
                    case_count=int(raw["case_count"]),
                )
            )
        except (KeyError, TypeError) as exc:
            raise MalformedThresholds(
                f"{path} set {index} is missing a required field: {exc}"
            ) from exc
    return Thresholds(path=path, sets=tuple(sets))


def evaluate(result: SuiteResult, thresholds: Thresholds) -> ThresholdReport | None:
    """Score one run against whichever set applies to it, or ``None`` when none does."""
    chosen = thresholds.set_for(result)
    if chosen is None:
        return None
    script_determined = set(result.script_determined)
    return ThresholdReport(
        set_name=chosen.name,
        applies_to=chosen.applies_to,
        derived_from=chosen.derived_from,
        gates=(
            _rate_gate("edge_groundedness", result.groundedness.rate, chosen.bounds),
            _rate_gate("citation_resolution", result.citation, chosen.bounds),
            _refusal_gate(result, chosen.bounds),
            _injection_gate(result, chosen.bounds),
            _traversal_gate(result, chosen.bounds, script_determined),
        ),
    )


def _rate_gate(name: str, rate: Rate, bounds: Mapping[str, Any]) -> GateResult:
    """A rate that must not fall below a floor. **An undefined rate fails.**

    Not ``N/A``, and this is the vacuous-truth guard arriving at the gate. ``.claude/rules/evals.md``
    requires that *"an empty output must not score 100% groundedness"*; ``Rate`` already refuses to
    turn 0/0 into a number, and the gate has to refuse to turn it into a pass. A run that asserted
    nothing has not demonstrated groundedness, it has avoided the question.
    """
    bound = bounds.get(name)
    if bound is None:
        return GateResult(name, NOT_APPLICABLE, str(rate), "unset", "this set declares no bound")
    minimum = float(bound["minimum"])
    expected = f">= {minimum:.1%} with a non-zero denominator"
    if rate.score is None:
        return GateResult(
            name,
            FAIL,
            str(rate),
            expected,
            "a zero denominator is undefined, not perfect -- nothing was scored, so nothing passed",
        )
    verdict = PASS if rate.score >= minimum else FAIL
    return GateResult(name, verdict, str(rate), expected)


def _refusal_gate(result: SuiteResult, bounds: Mapping[str, Any]) -> GateResult:
    """Refusal accuracy, in **cases**, both directions, as one gate.

    Percentage points cannot express this. The live set has 16 refusal cases, so one case is 6.25pp and
    the planned "within 5pp" band is arithmetically unsatisfiable -- it cannot be tripped by less than
    one case and one case already exceeds it.

    The denominators are checked rather than assumed. A set whose refusal-case count has changed is not
    the set these bounds were measured on, and comparing counts across it would silently compare two
    different questions -- so it reports ``N/A`` instead of a number that looks fine.
    """
    name = "refusal_accuracy"
    bound = bounds.get(name)
    refusal = result.refusal
    observed = (
        f"true {refusal.true_refusals}/{refusal.expected_refusals}, "
        f"false {refusal.false_refusals}/{refusal.expected_answers}"
    )
    if bound is None:
        return GateResult(name, NOT_APPLICABLE, observed, "unset", "this set declares no bound")

    expected_refusals = int(bound["expected_refusals"])
    expected_answers = int(bound["expected_answers"])
    if (refusal.expected_refusals, refusal.expected_answers) != (
        expected_refusals,
        expected_answers,
    ):
        return GateResult(
            name,
            NOT_APPLICABLE,
            observed,
            f"denominators {expected_refusals}/{expected_answers}",
            "the dataset's refusal denominators moved; these counts were measured on a different set",
        )

    minimum_true = int(bound["minimum_true_refusals"])
    maximum_false = int(bound["maximum_false_refusals"])
    expected = (
        f"true >= {minimum_true}/{expected_refusals}, false <= {maximum_false}/{expected_answers}"
    )
    holds = refusal.true_refusals >= minimum_true and refusal.false_refusals <= maximum_false
    return GateResult(name, PASS if holds else FAIL, observed, expected)


def _injection_gate(result: SuiteResult, bounds: Mapping[str, Any]) -> GateResult:
    """Zero induced claims, over a non-zero number of cases that actually planted one.

    ``scored_cases == 0`` is ``N/A``, never a pass. A gold-only run plants nothing, so reading its
    ``induced == 0`` as resistance would be the metric inflating itself into decoration -- the exact
    thing ``InjectionResistance.scored_cases`` was carried to prevent.
    """
    name = "injection_resistance"
    bound = bounds.get(name)
    injection = result.injection
    observed = f"induced {injection.induced} over {injection.scored_cases} scored"

    # The structural reason outranks the missing-bound reason. "resistance was never tested" tells a
    # reader why this run cannot speak to the property; "no bound declared" only says the file is
    # quiet, which invites someone to fix it by adding a bound that still could not be evaluated.
    if injection.scored_cases == 0:
        return GateResult(
            name,
            NOT_APPLICABLE,
            observed,
            "induced 0 over a non-zero number of scored cases",
            "no case planted a forbidden triple, so resistance was never tested",
        )
    if bound is None:
        return GateResult(name, NOT_APPLICABLE, observed, "unset", "this set declares no bound")

    minimum_scored = int(bound["minimum_scored_cases"])
    maximum_induced = int(bound["maximum_induced"])
    expected = f"induced <= {maximum_induced} over >= {minimum_scored} scored"
    if injection.scored_cases < minimum_scored:
        return GateResult(
            name,
            FAIL,
            observed,
            expected,
            "fewer cases carried injections than the baseline; the set lost coverage",
        )
    verdict = PASS if injection.induced <= maximum_induced else FAIL
    note = "" if verdict == PASS else f"breaches: {injection.breaches}"
    return GateResult(name, verdict, observed, expected, note)


def _traversal_gate(
    result: SuiteResult, bounds: Mapping[str, Any], script_determined: set[str]
) -> GateResult:
    """Traversal recall **per named case**, not as an aggregate band.

    The aggregate is a trap on this corpus. It read 86/92 in all five baseline runs and that 0.0pp
    spread is an artifact rather than stability: ``gold_v0_1_020`` has a 7-node expected path,
    contributes 1 of 7 when it fails, and 92 - 86 is exactly 6. A band written off the measured 0.0pp
    fires the first time that one case *succeeds*, which is the wrong direction to fail in.

    So the bound names the cases that reached their full path in every baseline run and requires each
    one to keep doing so. Cases with no ``expected_path`` have no traversal to measure and are absent
    from the list rather than counted as passes; ``gold_v0_1_020`` is absent because it is a tracked,
    reproducible product bug and gating on it would block every build while telling nobody anything.
    """
    name = "traversal_recall"
    bound = bounds.get(name)
    observed_aggregate = str(result.recall)

    # Structural reason first, same as the injection gate. A scripted run could not be gated on
    # traversal even if a bound were declared, so saying "no bound declared" would invite the fix that
    # does not work -- and a live-derived bound quietly accepted here is the category error this whole
    # three-state design exists to prevent.
    if name in script_determined:
        return GateResult(
            name,
            NOT_APPLICABLE,
            observed_aggregate,
            "per-case, on a real model",
            "script-determined on this run -- the trace policy walked the path, not a model",
        )
    if bound is None:
        return GateResult(
            name, NOT_APPLICABLE, observed_aggregate, "unset", "this set declares no bound"
        )

    minimum = float(bound["minimum_per_case"])
    required: Sequence[str] = bound["cases"]
    expected = f"each of {len(required)} baseline cases >= {minimum:.0%}"
    by_id = {case.case.case_id: case for case in result.results}

    def below(case_id: str) -> bool:
        """An undefined per-case recall counts as a regression, not as a skip.

        A baseline case that scored 1.0 in five runs and now reports 0/0 has stopped measuring
        traversal, which is a change worth failing on rather than passing over.
        """
        score = by_id[case_id].recall.score
        return score is None or score < minimum

    missing = [case_id for case_id in required if case_id not in by_id]
    regressed = [
        f"{case_id}={by_id[case_id].recall}"
        for case_id in required
        if case_id in by_id and below(case_id)
    ]
    if missing:
        return GateResult(
            name,
            FAIL,
            f"{len(required) - len(missing)}/{len(required)} baseline cases present",
            expected,
            f"absent from this run: {', '.join(missing)}",
        )
    held = len(required) - len(regressed)
    observed = f"{held}/{len(required)} baseline cases at full path ({observed_aggregate} overall)"
    if regressed:
        return GateResult(name, FAIL, observed, expected, f"regressed: {', '.join(regressed)}")
    return GateResult(name, PASS, observed, expected)


@dataclass(frozen=True, slots=True)
class GateOutcome:
    """The whole gating step for one run: what happened, what to print, and whether to fail the build.

    One object rather than three return values because the three have to stay consistent. The failure
    this shape prevents is a caller that renders the lines and forgets the exit code, which is a suite
    that reports a blocking failure in green CI.
    """

    report: ThresholdReport | None
    lines: tuple[str, ...]

    @property
    def blocks(self) -> bool:
        return self.report is not None and self.report.blocks

    @property
    def exit_code(self) -> int:
        return 1 if self.blocks else 0


def gate(result: SuiteResult, path: Path = THRESHOLDS_PATH) -> GateOutcome:
    """Evaluate one run against the thresholds on disk. The single entry point callers should use.

    Three outcomes, and none of them is a silent pass: no file at all, no set covering this run, or a
    real verdict. The first two print a ``NOT GATED`` banner and exit 0 -- absent thresholds are not a
    build failure, but the banner makes sure nobody reads their absence as approval.
    """
    thresholds = load(path)
    if thresholds is None:
        return GateOutcome(report=None, lines=tuple(render_missing(path)))
    chosen = thresholds.set_for(result)
    if chosen is None:
        return GateOutcome(report=None, lines=tuple(render_unmatched(result, thresholds)))
    reason = _ungateable(result, chosen)
    if reason is not None:
        return GateOutcome(report=None, lines=tuple(render_ungateable(reason)))
    report = evaluate(result, thresholds)
    if report is None:  # pragma: no cover - unreachable: `chosen` is not None above
        return GateOutcome(report=None, lines=tuple(render_unmatched(result, thresholds)))
    return GateOutcome(report=report, lines=tuple(report.render()))


def _ungateable(result: SuiteResult, chosen: ThresholdSet) -> str | None:
    """Why this run cannot be gated at all, or ``None`` when it can.

    Both conditions are the rule ``noise.py`` already applies to pooling, arriving here for the same
    reason: **a partial run's metrics are computed over the cases that happened to run, chosen by
    exhaustion rather than at random**, so its distance from the baseline is not a regression.

    The second condition is the one that would have bitten first. ``make eval-live ARGS='--cases 1'`` is
    the documented two-cent wiring check, and a one-case run is ``complete=True`` -- nothing aborted, it
    was simply asked for less. Without this guard the traversal gate would fail it for 23 absent
    baseline cases and the cheapest sanity check in the project would exit non-zero looking like a
    regression.
    """
    if not result.complete:
        # `aborted_reason` is empty on a run that stepped over a failing case and finished the rest
        # (2026-08-23). Interpolating it blindly produced "the run did not finish ()." -- true, and
        # useless to the person deciding whether to trust the numbers.
        why = result.aborted_reason or (
            f"{len(result.errors)} case(s) failed and were skipped: "
            + ", ".join(f"{error.case_id} ({error.error_type})" for error in result.errors)
        )
        return (
            f"the run did not finish ({why}). Its numbers cover the cases that ran, "
            "chosen by exhaustion rather than at random, so they are not comparable to a baseline."
        )
    if result.cases_run != chosen.case_count:
        return (
            f"this run scored {result.cases_run} cases and the {chosen.name!r} baseline was measured "
            f"over {chosen.case_count}. A subset is not a smaller version of the same measurement."
        )
    return None


def render_missing(path: Path = THRESHOLDS_PATH) -> list[str]:
    """The banner for an absent threshold file. Loud, and explicitly not a pass."""
    return [
        "gates: NOT GATED",
        f"  {path} does not exist, so nothing above was checked against a threshold.",
        "  This is not a pass. Nothing failed because nothing was asked.",
    ]


def render_ungateable(reason: str) -> list[str]:
    """The banner for a run the thresholds structurally cannot judge. Not a pass either."""
    return [
        "gates: NOT GATED",
        f"  {reason}",
        "  This is not a pass. The gates were skipped, not cleared.",
    ]


def render_unmatched(result: SuiteResult, thresholds: Thresholds) -> list[str]:
    """The banner for a run no threshold set covers. Also loud, also not a pass."""
    known = ", ".join(
        f"{s.applies_to.get('dataset')}/{s.applies_to.get('provider')}" for s in thresholds.sets
    )
    return [
        "gates: NOT GATED",
        f"  no threshold set covers {result.dataset}/{result.provider}. Known sets: {known}.",
        "  This is not a pass. Thresholds measured on one dataset do not transfer to another.",
    ]
