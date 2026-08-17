"""The noise floor: how much a metric moves when nothing changes.

`.claude/rules/evals.md` asks for it in one line — *"Run the identical suite 5 times, record the
spread, and never celebrate a movement that falls inside it"* — and phase 4 originally scheduled it
**after** thresholds were set. Two live runs on 2026-08-16 forced the swap. Identical inputs,
identical artifact, identical code: `traversal_recall` moved 6.5pp and the true-refusal rate moved
6.3pp, both wider than the 5pp gate step 5 was about to adopt. A threshold inside the noise fires on
chance, which makes the suite worse than having none — it teaches its reader to ignore it.

So this module runs first, and step 5 reads it.

## What it measures, and the part that is easy to miss

Two things, and the second is the one those two runs actually taught:

1. **Spread per metric.** Min, max, range, mean and standard deviation across N identical runs. This
   is the number a threshold has to clear.
2. **Membership churn.** Which *cases* flipped. Runs 1 and 2 both scored 39/41 and failed
   **different cases** — `gold_v0_1_020` went 0 approved claims to 6, `adv_018` went 0 to 4, in
   opposite directions. A stable aggregate concealed a complete change of membership, and a floor
   that reported only the aggregate would have said the suite was steady. `cases_correct` had a
   spread of exactly zero across the pair while nearly 5% of the set changed answer.

A case that fails in every run is a finding. A case that fails in some runs is a coin, and the two
are indistinguishable from one run.

## What it refuses to do

- **Pool runs that differ in any recorded dimension**, including the code that produced them. See
  `provenance.py`: the metric fix between runs 1 and 2 was invisible in every field a reader would
  think to check, and averaging across it would have produced an unfalsifiable number.
- **Report a spread over fewer than two runs.** A single run has a spread of 0.0, which is arithmetic
  rather than a measurement, and a confident zero is precisely the failure `traversal_precision` shipped
  with on 2026-08-16: right arithmetic, wrong question. It raises instead.
- **Hand out a tolerance from a provisional floor.** Under five runs, or any run whose code revision
  does not identify a working tree, and `tolerance_for` raises rather than returning a number that
  would go straight into `thresholds.json` and stay there.

A provisional floor still *renders*, loudly and with its reasons at the top. The same rule step 5
applies to a missing `thresholds.json`: report loudly, never silently pass.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from musical_mycelium.eval.provenance import UNKNOWN, is_pinnable

RESULTS_DIR = Path(__file__).parent / "results"
NOISE_FLOOR_PATH = Path(__file__).parent / "noise_floor.json"

#: `.claude/rules/evals.md`: *"Run the identical suite 5 times."* Five is the standing rule, and a
#: floor built on fewer is marked provisional rather than quietly accepted at four.
MINIMUM_RUNS = 5

#: Below this nothing can be computed at all. Two is not a noise floor either, but it is the point at
#: which the word "spread" starts to mean something; one is arithmetic.
ABSOLUTE_MINIMUM_RUNS = 2

#: Fields every pooled run must agree on. Order matters only for the error message, which names the
#: first disagreement rather than all of them: one mismatch is already disqualifying.
POOLING_FIELDS = (
    "dataset",
    "dataset_version",
    "provider",
    "model_id",
    "artifact_version",
    "artifact_pin",
    "code_revision",
)


class NotEnoughRuns(RuntimeError):
    """Fewer than two comparable runs. Raised rather than returning a zero spread."""


class IncomparableRuns(RuntimeError):
    """Two runs disagree on something that makes their numbers different measurements."""


class IncompleteRun(RuntimeError):
    """A budget-aborted run was offered to the pool.

    A partial run's metrics are computed over the cases that happened to fit, chosen by exhaustion
    rather than at random, so its distance from a complete run is not noise.
    """


class ProvisionalNoiseFloor(RuntimeError):
    """A tolerance was asked of a floor that is not yet entitled to give one."""


@dataclass(frozen=True, slots=True)
class RunRecord:
    """One result file, loaded. Keeps its path because every error message needs to name a file."""

    path: Path
    payload: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> RunRecord:
        return cls(path=path, payload=json.loads(path.read_text(encoding="utf-8")))

    @property
    def code_revision(self) -> str:
        """``unknown`` for any result file written before `provenance.py` existed.

        Absent and unknown are the same state and are treated identically: a run whose code cannot be
        identified makes the floor provisional. It does not make it unpoolable — an unknown pooled
        with an unknown is at least self-consistent about what it does not know.
        """
        value = self.payload.get("code_revision", UNKNOWN)
        return value if isinstance(value, str) and value else UNKNOWN

    @property
    def case_ids(self) -> tuple[str, ...]:
        return tuple(case["case_id"] for case in self.payload.get("per_case", ()))

    @property
    def complete(self) -> bool:
        return bool(self.payload.get("complete", False))

    def pooling_key(self) -> tuple[tuple[str, Any], ...]:
        return tuple((field, self.payload.get(field, UNKNOWN)) for field in POOLING_FIELDS)


@dataclass(frozen=True, slots=True)
class Spread:
    """One metric's behaviour across the pool.

    ``undefined_runs`` counts runs where the metric had no value — a rate with a zero denominator,
    which `Rate` correctly calls undefined rather than perfect. Those runs are excluded from the
    statistics and counted in the open, because dropping them silently would let a metric that was
    undefined four times out of five report a tight spread over its one real value.
    """

    metric: str
    #: ``rate`` renders as percentages and percentage points; ``count`` renders as integers.
    unit: str
    values: tuple[float, ...]
    undefined_runs: int = 0

    @property
    def low(self) -> float | None:
        return min(self.values) if self.values else None

    @property
    def high(self) -> float | None:
        return max(self.values) if self.values else None

    @property
    def spread(self) -> float | None:
        """``high - low``. ``None`` when the metric never had a value.

        Zero is a legitimate answer here and means the metric did not move across the pool. It is
        only meaningless when there was one run to move between, which `compute` refuses upstream.
        """
        if not self.values:
            return None
        return max(self.values) - min(self.values)

    @property
    def mean(self) -> float | None:
        return statistics.fmean(self.values) if self.values else None

    @property
    def stdev(self) -> float | None:
        """Sample standard deviation, or ``None`` under two defined values."""
        if len(self.values) < 2:
            return None
        return statistics.stdev(self.values)

    def render(self) -> str:
        if not self.values:
            return f"  {self.metric}: undefined in all {self.undefined_runs} runs"
        note = f"  [{self.undefined_runs} undefined]" if self.undefined_runs else ""
        if self.unit == "rate":
            body = (
                f"{self._pct(self.low)}-{self._pct(self.high)}  "
                f"spread {self._pp(self.spread)}  mean {self._pct(self.mean)}  "
                f"sd {self._pp(self.stdev)}"
            )
        else:
            body = (
                f"{self._num(self.low)}-{self._num(self.high)}  "
                f"spread {self._num(self.spread)}  mean {self.mean:.1f}  sd {self._num(self.stdev)}"
            )
        return f"  {self.metric}: {body}  over {len(self.values)} runs{note}"

    @staticmethod
    def _pct(value: float | None) -> str:
        return "n/a" if value is None else f"{value:.1%}"

    @staticmethod
    def _pp(value: float | None) -> str:
        return "n/a" if value is None else f"{value * 100:.1f}pp"

    @staticmethod
    def _num(value: float | None) -> str:
        return "n/a" if value is None else f"{value:g}"

    def to_json(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "unit": self.unit,
            "values": list(self.values),
            "undefined_runs": self.undefined_runs,
            "low": self.low,
            "high": self.high,
            "spread": self.spread,
            "mean": self.mean,
            "stdev": self.stdev,
        }


@dataclass(frozen=True, slots=True)
class CaseStability:
    """One case's answer across the pool. The unit membership churn is measured in."""

    case_id: str
    correct: tuple[bool, ...]
    refused: tuple[bool, ...]
    approved_claims: tuple[int, ...]

    @property
    def stable(self) -> bool:
        """Same verdict every time. Says nothing about whether the verdict was right."""
        return len(set(self.correct)) <= 1

    @property
    def always_correct(self) -> bool:
        return all(self.correct)

    @property
    def always_wrong(self) -> bool:
        """A reproducible failure. `adv_008` is the project's example: wrong in both runs, and
        therefore the one result a single run was entitled to establish."""
        return not any(self.correct)

    @property
    def claim_swing(self) -> int:
        return max(self.approved_claims) - min(self.approved_claims)

    def render(self) -> str:
        verdict = "correct" if self.always_correct else "wrong"
        if not self.stable:
            verdict = f"UNSTABLE {sum(self.correct)}/{len(self.correct)} correct"
        claims = "/".join(str(count) for count in self.approved_claims)
        refusals = sum(self.refused)
        return f"  {self.case_id}: {verdict}  claims {claims}  refused in {refusals} runs"

    def to_json(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "correct": list(self.correct),
            "refused": list(self.refused),
            "approved_claims": list(self.approved_claims),
            "stable": self.stable,
            "claim_swing": self.claim_swing,
        }


#: The catalog, as extractors off a result payload. A metric returns ``None`` for a run where it was
#: undefined, and ``Spread`` counts those separately rather than treating absence as zero.
def _rate_field(name: str) -> Callable[[dict[str, Any]], float | None]:
    def extract(payload: dict[str, Any]) -> float | None:
        value = payload.get(name)
        return None if value is None else float(value)

    return extract


def _refusal_rate(numerator: str, denominator: str) -> Callable[[dict[str, Any]], float | None]:
    """Refusal is reported as a **pair** — true refusals and false refusals — per
    `.claude/rules/grounding-and-claims.md`, so each half gets its own spread. A system that refuses
    everything has a perfect true-refusal rate, and a floor that tracked only that would say so."""

    def extract(payload: dict[str, Any]) -> float | None:
        refusal = payload.get("refusal_accuracy", {})
        total = refusal.get(denominator, 0)
        if not total:
            return None
        return float(refusal[numerator]) / float(total)

    return extract


def _count_field(name: str) -> Callable[[dict[str, Any]], float | None]:
    def extract(payload: dict[str, Any]) -> float | None:
        value = payload.get(name)
        return None if value is None else float(value)

    return extract


def _approved_claims(payload: dict[str, Any]) -> float | None:
    cases = payload.get("per_case", ())
    if not cases:
        return None
    return float(sum(case["approved_claims"] for case in cases))


def _injection_induced(payload: dict[str, Any]) -> float | None:
    return float(payload.get("injection_resistance", {}).get("induced", 0))


def _total_tokens(payload: dict[str, Any]) -> float | None:
    return float(payload.get("usage", {}).get("total_tokens", 0))


METRICS: tuple[tuple[str, str, Callable[[dict[str, Any]], float | None]], ...] = (
    ("edge_groundedness", "rate", _rate_field("edge_groundedness")),
    ("citation_resolution", "rate", _rate_field("citation_resolution")),
    ("true_refusal_rate", "rate", _refusal_rate("true_refusals", "expected_refusals")),
    ("false_refusal_rate", "rate", _refusal_rate("false_refusals", "expected_answers")),
    ("traversal_recall", "rate", _rate_field("traversal_recall")),
    ("traversal_precision", "rate", _rate_field("traversal_precision")),
    ("cases_correct", "count", _count_field("cases_correct")),
    ("approved_claims", "count", _approved_claims),
    ("injection_induced", "count", _injection_induced),
    ("total_tokens", "count", _total_tokens),
)

#: Metrics a threshold could plausibly be written against. `thresholds.json` gates five things and
#: two of them — traversal recall and refusal accuracy — are "within Npp of baseline", which is the
#: pair this floor exists to size.
RATE_METRICS = tuple(name for name, unit, _ in METRICS if unit == "rate")


@dataclass(frozen=True, slots=True)
class NoiseFloor:
    """The measured spread of a suite against itself, plus what it is and is not entitled to say."""

    runs: tuple[Path, ...]
    code_revision: str
    dataset_version: str
    model_id: str
    artifact_version: str
    spreads: tuple[Spread, ...]
    cases: tuple[CaseStability, ...]
    provisional_reasons: tuple[str, ...]

    @property
    def sufficient(self) -> bool:
        return not self.provisional_reasons

    @property
    def unstable_cases(self) -> tuple[CaseStability, ...]:
        """Cases that did not give the same verdict every time. **The headline of this whole module.**"""
        return tuple(case for case in self.cases if not case.stable)

    @property
    def reproducible_failures(self) -> tuple[CaseStability, ...]:
        return tuple(case for case in self.cases if case.always_wrong)

    def spread_for(self, metric: str) -> Spread:
        for spread in self.spreads:
            if spread.metric == metric:
                return spread
        raise KeyError(f"no metric named {metric!r} in this floor")

    def tolerance_for(self, metric: str) -> float:
        """The observed spread, for step 5 to build a threshold on. Raises on a provisional floor.

        It returns the **measured** number and nothing more — no padding, no rounding up to a
        friendlier figure. Choosing how much headroom a gate needs above the floor is a threshold
        decision and belongs in step 5, where it is written down with its reasoning. A function that
        quietly returned ``spread * 1.5`` would be inventing a threshold here and hiding it in a
        helper.
        """
        if not self.sufficient:
            raise ProvisionalNoiseFloor(
                "this floor is provisional and cannot supply a tolerance: "
                + "; ".join(self.provisional_reasons)
            )
        spread = self.spread_for(metric).spread
        if spread is None:
            raise ProvisionalNoiseFloor(
                f"{metric} was undefined in every run; it has no measured spread to gate on"
            )
        return spread

    def metrics_wider_than(self, candidate: float) -> tuple[str, ...]:
        """Rate metrics whose observed spread exceeds a candidate gate.

        The question step 5 actually asks: *is 5pp defensible?* Anything this returns is a metric
        where a gate at ``candidate`` would fire on noise alone.
        """
        wider = []
        for metric in RATE_METRICS:
            spread = self.spread_for(metric).spread
            if spread is not None and spread > candidate:
                wider.append(metric)
        return tuple(wider)

    def to_json(self) -> dict[str, Any]:
        return {
            "runs": [path.name for path in self.runs],
            "run_count": len(self.runs),
            "code_revision": self.code_revision,
            "dataset_version": self.dataset_version,
            "model_id": self.model_id,
            "artifact_version": self.artifact_version,
            "sufficient": self.sufficient,
            "provisional_reasons": list(self.provisional_reasons),
            "spreads": [spread.to_json() for spread in self.spreads],
            "unstable_case_ids": [case.case_id for case in self.unstable_cases],
            "reproducible_failure_ids": [case.case_id for case in self.reproducible_failures],
            "cases": [case.to_json() for case in self.cases],
        }


def compute(records: Sequence[RunRecord], *, minimum_runs: int = MINIMUM_RUNS) -> NoiseFloor:
    """Pool N result files into a floor, or refuse and say why.

    Every refusal here is a case where the alternative is a number that looks fine and is not
    checkable afterwards. That is the whole reason they are exceptions rather than warnings.
    """
    if len(records) < ABSOLUTE_MINIMUM_RUNS:
        raise NotEnoughRuns(
            f"a noise floor needs at least {ABSOLUTE_MINIMUM_RUNS} runs; got {len(records)}. "
            "One run has a spread of zero by construction, which is arithmetic and not a measurement."
        )

    first = records[0]
    for record in records[1:]:
        for (field, mine), (_, theirs) in zip(
            first.pooling_key(), record.pooling_key(), strict=True
        ):
            if mine != theirs:
                raise IncomparableRuns(
                    f"{record.path.name} and {first.path.name} disagree on {field}: "
                    f"{theirs!r} vs {mine!r}. These are two different measurements, not two "
                    "samples of one."
                )
        if record.case_ids != first.case_ids:
            raise IncomparableRuns(
                f"{record.path.name} ran {len(record.case_ids)} cases and {first.path.name} ran "
                f"{len(first.case_ids)}; a spread across different case sets is not a spread."
            )
    for record in records:
        if not record.complete:
            raise IncompleteRun(
                f"{record.path.name} is incomplete "
                f"({record.payload.get('aborted_reason', 'no reason recorded')}). "
                "Its cases were chosen by exhaustion, so its distance from a complete run is not noise."
            )

    spreads = []
    for name, unit, extract in METRICS:
        values = [extract(record.payload) for record in records]
        defined = tuple(value for value in values if value is not None)
        spreads.append(
            Spread(
                metric=name,
                unit=unit,
                values=defined,
                undefined_runs=len(values) - len(defined),
            )
        )

    cases = []
    for index, case_id in enumerate(first.case_ids):
        rows = [record.payload["per_case"][index] for record in records]
        cases.append(
            CaseStability(
                case_id=case_id,
                correct=tuple(bool(row["correct"]) for row in rows),
                refused=tuple(bool(row["refused"]) for row in rows),
                approved_claims=tuple(int(row["approved_claims"]) for row in rows),
            )
        )

    reasons = []
    if len(records) < minimum_runs:
        reasons.append(
            f"{len(records)} runs; the standing rule in .claude/rules/evals.md is {minimum_runs}"
        )
    if not is_pinnable(first.code_revision):
        reasons.append(
            f"code_revision {first.code_revision!r} does not identify a working tree, so these runs "
            "cannot be shown to have come from the same code"
        )

    return NoiseFloor(
        runs=tuple(record.path for record in records),
        code_revision=first.code_revision,
        dataset_version=str(first.payload.get("dataset_version", UNKNOWN)),
        model_id=str(first.payload.get("model_id", UNKNOWN)),
        artifact_version=str(first.payload.get("artifact_version", UNKNOWN)),
        spreads=tuple(spreads),
        cases=tuple(cases),
        provisional_reasons=tuple(reasons),
    )


def render(floor: NoiseFloor) -> str:
    """The floor as text. Provisional reasons go **first**, for `report.py`'s reason: a reader who
    has already seen the headline has already formed the belief."""
    lines = [
        f"noise floor -- {len(floor.runs)} runs, "
        f"{floor.dataset_version}, model={floor.model_id}, artifact {floor.artifact_version}",
        f"code {floor.code_revision}",
    ]
    if not floor.sufficient:
        lines.append("  PROVISIONAL. This floor cannot be used to set a threshold:")
        lines.extend(f"    - {reason}" for reason in floor.provisional_reasons)
    lines.append("")
    lines.append("runs pooled:")
    lines.extend(f"  {path.name}" for path in floor.runs)

    lines.append("")
    lines.append("spread per metric (identical inputs; any movement here is noise, not a result):")
    lines.extend(spread.render() for spread in floor.spreads)

    lines.append("")
    lines.append(
        f"membership churn: {len(floor.unstable_cases)} of {len(floor.cases)} cases "
        "did not give the same verdict every run"
    )
    if floor.unstable_cases:
        lines.extend(case.render() for case in floor.unstable_cases)
    else:
        lines.append("  none -- every case was stable across the pool")

    lines.append("")
    lines.append(
        f"reproducible failures: {len(floor.reproducible_failures)} "
        "(wrong in every run, so not chance)"
    )
    lines.extend(case.render() for case in floor.reproducible_failures)

    lines.append("")
    lines.append("against a candidate 5pp gate:")
    wider = floor.metrics_wider_than(0.05)
    if wider:
        lines.append(
            "  WIDER THAN THE GATE -- a 5pp threshold on these would fire on chance alone: "
            + ", ".join(wider)
        )
    else:
        lines.append("  no rate metric moved more than 5pp across the pool")

    return "\n".join(lines)


def recent_runs(
    *, directory: Path = RESULTS_DIR, count: int = MINIMUM_RUNS, pattern: str = "*-bedrock.json"
) -> tuple[Path, ...]:
    """The newest ``count`` result files, by filename.

    Filenames are UTC timestamps, so lexical order is chronological. **No filtering for
    comparability happens here on purpose** — silently selecting the subset that happens to agree
    would hide exactly the situation the pooling guard exists to surface, and the operator would
    never learn that the run they thought was included was dropped.
    """
    return tuple(sorted(directory.glob(pattern))[-count:])


def main(argv: Sequence[str] | None = None) -> int:
    """``make eval-noise``. Free: it reads files that a billable run already wrote.

    Exit 2 on a refusal, 0 on a rendered floor including a provisional one. A provisional floor is a
    real measurement that is not yet entitled to set a threshold, not a failure.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    count = MINIMUM_RUNS
    write = False
    paths: list[Path] = []

    index = 0
    while index < len(args):
        argument = args[index]
        if argument == "--runs":
            count = int(args[index + 1])
            index += 2
        elif argument == "--write":
            write = True
            index += 1
        else:
            paths.append(Path(argument))
            index += 1

    selected = tuple(paths) if paths else recent_runs(count=count)
    if not selected:
        print("no result files found; run `make eval-live` first.", file=sys.stderr)
        return 2

    try:
        floor = compute([RunRecord.load(path) for path in selected])
    except (NotEnoughRuns, IncomparableRuns, IncompleteRun) as refusal:
        print(f"\ncannot pool these runs: {refusal}", file=sys.stderr)
        return 2

    print(render(floor))
    if write:
        NOISE_FLOOR_PATH.write_text(json.dumps(floor.to_json(), indent=2) + "\n", encoding="utf-8")
        print(f"\nwritten to {NOISE_FLOOR_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
