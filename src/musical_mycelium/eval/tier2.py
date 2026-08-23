"""Tier 2: citation support and narrative quality over a sample of a release candidate. Phase 4 step 8.

Step 7 pointed the judge at a pool a human had already labeled, and the number that came out was about
**the judge**. This module points the same judge at a fresh sample of a release candidate's answers, and
the number that comes out is about **the agent**. Same machinery, opposite subject, and the difference is
worth stating because it is the whole reason this is a separate module rather than a flag on `eval-judge`.

## The problem this module exists to solve

`.claude/rules/evals.md` requires judge-human agreement reported *permanently, next to every judged
metric*. `report.py` enforces that for step 7 by making agreement a required field on `JudgeRun` -- the
number and its validation are one object, so they cannot be separated by a careless caller.

That trick does not survive the move to step 8, because **a fresh sample has no human labels**. Nobody
hand-labeled a release candidate's answers and nobody should: the labels exist to validate the judge, and
re-labeling every candidate would make the judge pointless. So the agreement figure has to be *inherited*
from the validation runs rather than computed here -- and an inherited figure is exactly the kind that
goes missing.

Hence `Validation`: a required field on `Tier2Run`, read from the committed judge runs, carrying the
agreement that was actually measured. A tier 2 number cannot be constructed without it, cannot be
serialised without it -- `to_json` nests each metric *with* its agreement in the same object rather than
in two parallel blocks -- and cannot be rendered without it.

## Inherited agreement is only valid under the conditions it was measured

An agreement figure describes one judge reading one rubric. Three guards, all of them before the spend
prompt, so a misconfigured run never costs anything:

1. **Same judge model.** `JudgeNotValidated`. Agreement measured on Nova Pro says nothing about a
   different judge, and swapping the model is a one-line env change.
2. **Same rubric text.** Reuses `guard_rubrics`, the step 7a lock, against the committed labels. A
   rewritten rubric means the validation measured a judge answering a different question.
3. **The judge is not the generator's family.** `guard_model`, unchanged from step 7.

## Every judged number here is a range, not a point

Measured 2026-08-21: the judge is **not deterministic at temperature 0**. Three runs, two with
byte-identical prompts, produced kappas spanning 0.44-0.48 on citation support and 0.66-0.73 on narrative
quality. So `Validation` reports low-high across the validation runs rather than a single figure, and
`band` is applied to both ends -- the qualitative claim held in all three runs where the digits did not,
and the qualitative claim is the part this project is entitled to state flatly.

A single validation run cannot express that spread at all, so it is reported as one sample with the
caveat attached rather than as a bound.

## Tracked, never blocking

`.claude/rules/evals.md`: *"Block on correctness properties, track quality preferences."* Nothing in this
module reaches `thresholds.py`, and that is deliberate rather than unfinished. A narrative-quality mean
with a kappa of 0.7 is evidence, not a gate, and a suite that blocks on a judged preference is a suite
that gets disabled the first time a rewrite moves it half a point.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from musical_mycelium.agent.llm import LLM, ROLE_JUDGE, Usage, build_llm, model_id_for
from musical_mycelium.eval import transcripts
from musical_mycelium.eval.agreement import band
from musical_mycelium.eval.budget import JUDGE_REQUESTS_PER_MINUTE, RateLimiter
from musical_mycelium.eval.judge import (
    ESTIMATED_INPUT_TOKENS_PER_ITEM,
    ESTIMATED_OUTPUT_TOKENS_PER_ITEM,
    RESULTS_DIR,
    Judgement,
    SelfPreferenceRefused,
    guard_model,
    guard_rubrics,
    judge_item,
    load_rubric,
)
from musical_mycelium.eval.labelling import (
    LABELS_PATH,
    POOL_PATH,
    RUBRIC_NAMES,
    SUPPORT_LEVELS,
    Pool,
    PoolError,
    RubricChanged,
    build_pool,
    load_labels,
    load_pool,
)
from musical_mycelium.eval.provenance import code_revision, is_pinnable
from musical_mycelium.eval.safety import (
    SpendCapExceeded,
    SpendEstimate,
    SpendRefused,
    UnattendedSpend,
    confirm_spend,
)
from musical_mycelium.eval.transcripts import RunTranscript

#: The sample pool's name, and therefore its item-id prefix. Deliberately not `judge_pool_v1`: the two
#: pools must never share an id space, because a `judge_pool_v1_007` from a tier 2 sample sitting next to
#: a human label written about a different answer is a silent, undetectable mis-pairing.
SAMPLE_NAME = "tier2_sample"

#: `07` §2 and the scope doc both say 20-30. Twenty rather than thirty because **one live run answers
#: roughly 25 of its 41 cases** -- the other 16 refuse, correctly -- so 20 is reachable from a single
#: release candidate, and a tier 2 sample that needs two runs to exist is a tier 2 sample that does not
#: get taken. The size travels in the result file next to every number drawn from it.
SAMPLE_SIZE = 20

#: Fixed so a sample is reproducible from the same transcript, which is what makes "the sample was not
#: reshuffled until the score improved" a checkable statement rather than an assurance.
SAMPLE_SEED = 20260823

#: Said once, wherever a single validation run is reported. See the module docstring.
SINGLE_RUN_CAVEAT = (
    "one validation run, so this is a sample rather than a bound -- the judge is not "
    "deterministic at temperature 0 (measured, 2026-08-21)"
)


class NoValidationRuns(RuntimeError):
    """No committed judge run exists, so no agreement figure can be inherited.

    Raised rather than defaulted to an empty figure. A tier 2 score with no validation behind it is the
    decoration `.claude/rules/evals.md` names outright, and the failure mode of a permissive default is
    that it produces a plausible-looking number nobody can later tell was unvalidated.
    """


class ValidationRunsDisagree(RuntimeError):
    """The committed judge runs were not all produced under the same judge or the same pool.

    Pooling them would produce a range that spans a configuration change rather than the judge's own
    noise -- the same error `noise.py` refuses on for agent runs, for the same reason.
    """


class JudgeNotValidated(RuntimeError):
    """The judge about to run is not the judge the inherited agreement was measured on."""


class NotAReleaseCandidate(RuntimeError):
    """The source run was produced by code that cannot be identified. See `is_pinnable`."""


@dataclass(frozen=True, slots=True)
class MetricValidation:
    """One judged metric's inherited agreement, as a range across the validation runs."""

    metric: str
    runs: int
    n_low: int
    n_high: int
    kappa_low: float | None
    kappa_high: float | None
    kappa_kind: str
    exact_low: float | None
    exact_high: float | None

    @property
    def measured(self) -> bool:
        """Whether this is evidence at all. Mirrors `Agreement.measured`, and is the state
        `render` and `report.py` refuse to print a judged number beside."""
        return self.runs > 0 and self.n_low > 0

    @property
    def bands(self) -> tuple[str, ...]:
        """The qualitative label at each end of the range, deduplicated.

        One entry means the band held across every validation run and may be stated flatly. Two means
        the range straddles a boundary, and the honest report is both labels rather than the flattering
        one -- which is the whole reason this returns a tuple instead of a string.
        """
        labels = [band(self.kappa_low), band(self.kappa_high)]
        return tuple(dict.fromkeys(labels))

    def _range(self, low: float | None, high: float | None) -> str:
        if low is None or high is None:
            return "undefined"
        if self.runs == 1 or abs(high - low) < 5e-3:
            return f"{low:.2f}"
        return f"{low:.2f}-{high:.2f}"

    def render(self) -> list[str]:
        n = f"n={self.n_low}" if self.n_low == self.n_high else f"n={self.n_low}-{self.n_high}"
        lines = [
            f"    {self.metric}: kappa {self._range(self.kappa_low, self.kappa_high)} "
            f"({', '.join(self.bands)}, {self.kappa_kind}), "
            f"exact {self._range(self.exact_low, self.exact_high)}, {n}, "
            f"{self.runs} validation run{'' if self.runs == 1 else 's'}"
        ]
        if self.runs == 1:
            lines.append(f"      {SINGLE_RUN_CAVEAT}")
        return lines

    def to_json(self) -> dict[str, Any]:
        return {
            "metric": self.metric,
            "validation_runs": self.runs,
            "n_low": self.n_low,
            "n_high": self.n_high,
            "kappa_low": self.kappa_low,
            "kappa_high": self.kappa_high,
            "kappa_kind": self.kappa_kind,
            "kappa_bands": list(self.bands),
            "exact_low": self.exact_low,
            "exact_high": self.exact_high,
            "single_run_caveat": SINGLE_RUN_CAVEAT if self.runs == 1 else "",
        }


@dataclass(frozen=True, slots=True)
class Validation:
    """The agreement inherited from the committed judge runs. A required field on `Tier2Run`."""

    judge_model_id: str
    pool: str
    runs: tuple[str, ...]
    citation_support: MetricValidation
    narrative_quality: MetricValidation

    @property
    def measured(self) -> bool:
        """Both figures, not one. A block printing a validated number beside an unvalidated one is
        worse than printing neither, because the validated half lends its credibility to the other --
        the same reasoning `report.render_judged` states for step 7."""
        return self.citation_support.measured and self.narrative_quality.measured

    def to_json(self) -> dict[str, Any]:
        return {
            "judge_model_id": self.judge_model_id,
            "pool": self.pool,
            "runs": list(self.runs),
            "citation_support": self.citation_support.to_json(),
            "narrative_quality": self.narrative_quality.to_json(),
        }


def _metric_validation(metric: str, figures: Sequence[dict[str, Any]]) -> MetricValidation:
    """Collapse one metric's figure across the validation runs into a range.

    `None` kappas are dropped rather than treated as zero -- an undefined kappa is a measurement that
    could not be chance-corrected, not a measurement of no agreement -- and if every run is undefined,
    the range is honestly undefined too.
    """
    kappas = [figure["kappa"] for figure in figures if figure.get("kappa") is not None]
    exacts = [figure["exact"] for figure in figures if figure.get("exact") is not None]
    ns = [int(figure.get("n", 0)) for figure in figures]
    kinds = {str(figure.get("kappa_kind", "")) for figure in figures}
    return MetricValidation(
        metric=metric,
        runs=len(figures),
        n_low=min(ns) if ns else 0,
        n_high=max(ns) if ns else 0,
        kappa_low=min(kappas) if kappas else None,
        kappa_high=max(kappas) if kappas else None,
        # Sorted rather than popped: a set's iteration order is not stable across runs, and this string
        # is written into a result file that gets diffed.
        kappa_kind="/".join(sorted(kinds)) if kinds else "",
        exact_low=min(exacts) if exacts else None,
        exact_high=max(exacts) if exacts else None,
    )


def load_validation(*, directory: Path = RESULTS_DIR) -> Validation:
    """Read every committed judge run and collapse their agreement into an inheritable range.

    **Refuses an empty directory and refuses runs that disagree on judge or pool.** Both are the same
    rule: a range is only meaningful across runs that differed in nothing but the judge's own
    non-determinism.
    """
    paths = sorted(directory.glob("*-judge.json"))
    if not paths:
        raise NoValidationRuns(
            f"no judge run in {directory}. Tier 2 inherits its agreement figure from step 7's "
            "validation runs, and a judged number with no measured agreement is not a number this "
            "project reports. Run make eval-judge first."
        )

    loaded = [json.loads(path.read_text(encoding="utf-8")) for path in paths]
    models = {str(run.get("model_id", "")) for run in loaded}
    pools = {str(run.get("pool", "")) for run in loaded}
    if len(models) > 1 or len(pools) > 1:
        raise ValidationRunsDisagree(
            f"the {len(loaded)} judge runs in {directory} disagree: "
            f"model_id={sorted(models)}, pool={sorted(pools)}. An agreement range pooled across a "
            "configuration change measures the change, not the judge."
        )

    def figures(metric: str) -> list[dict[str, Any]]:
        return [run.get("agreement", {}).get(metric, {}) for run in loaded]

    return Validation(
        judge_model_id=next(iter(models)),
        pool=next(iter(pools)),
        runs=tuple(str(run.get("judged_at", "")) for run in loaded),
        citation_support=_metric_validation("citation_support", figures("citation_support")),
        narrative_quality=_metric_validation("narrative_quality", figures("narrative_quality")),
    )


@dataclass(frozen=True, slots=True)
class Tier2Run:
    """One judged sample of a release candidate, with the validation that makes its numbers readable.

    **`validation` has no default.** That is the structural half of the rule: this object cannot be
    constructed without the agreement figure, so no code path exists that produces a tier 2 score and
    forgets to carry its validation along.
    """

    sample: str
    sample_size: int
    seed: int
    sources: tuple[dict[str, Any], ...]
    judge_model_id: str
    judged_at: str
    code_revision: str
    judgements: tuple[Judgement, ...]
    usage: Usage
    validation: Validation

    @property
    def mean_quality(self) -> float | None:
        if not self.judgements:
            return None
        return sum(j.narrative_quality for j in self.judgements) / len(self.judgements)

    @property
    def supported_rate(self) -> tuple[int, int]:
        supported = sum(1 for j in self.judgements if j.citation_support == SUPPORT_LEVELS[0])
        return supported, len(self.judgements)

    def to_json(self) -> dict[str, Any]:
        """Each judged number nested **inside** the same object as its agreement figure.

        Two parallel blocks -- scores here, validation there -- is the shape that lets a reader, a
        script, or a future README quote one without the other. Nesting makes the pairing survive
        serialisation, which is where "reported next to" usually breaks.
        """
        supported, scored = self.supported_rate
        return {
            "tier": 2,
            "blocking": False,
            "sample": self.sample,
            "sample_size": self.sample_size,
            "seed": self.seed,
            "sources": list(self.sources),
            "judge_model_id": self.judge_model_id,
            "judged_at": self.judged_at,
            "code_revision": self.code_revision,
            "metrics": {
                "citation_support": {
                    "supported": supported,
                    "scored": scored,
                    "rate": (supported / scored) if scored else None,
                    "agreement": self.validation.citation_support.to_json(),
                },
                "narrative_quality": {
                    "mean": self.mean_quality,
                    "scored": len(self.judgements),
                    "agreement": self.validation.narrative_quality.to_json(),
                },
            },
            "validation_runs": list(self.validation.runs),
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "total_tokens": self.usage.total_tokens,
            },
            "judgements": [j.to_json() for j in self.judgements],
        }


def sample_from(
    runs: Sequence[RunTranscript],
    *,
    size: int = SAMPLE_SIZE,
    seed: int = SAMPLE_SEED,
    allow_short: bool = False,
    allow_unpinnable: bool = False,
    allow_scripted: bool = False,
) -> Pool:
    """Sample a tier 2 pool from one or more release-candidate transcripts.

    **Refuses a source whose code revision is not pinnable**, because "release candidate" is the whole
    premise of the step: a judged number attributed to a dirty or unknown tree cannot be tied to the
    code it is supposed to describe, and two such runs are indistinguishable afterwards.
    """
    if not allow_unpinnable:
        unpinnable = sorted(
            {run.code_revision for run in runs if not is_pinnable(run.code_revision)}
        )
        if unpinnable:
            raise NotAReleaseCandidate(
                f"source revision(s) {unpinnable} do not identify the code. Tier 2 judges a release "
                "candidate; commit the tree and re-run, or pass allow_unpinnable deliberately and "
                "accept that the resulting score names no particular code."
            )
    return build_pool(
        runs,
        size=size,
        seed=seed,
        allow_short=allow_short,
        allow_scripted=allow_scripted,
        name=SAMPLE_NAME,
    )


def guard_validated_judge(validation: Validation, judge_model_id: str) -> None:
    """Refuse a judge the inherited agreement does not describe. Before the spend prompt."""
    if validation.judge_model_id != judge_model_id:
        raise JudgeNotValidated(
            f"agreement was measured on {validation.judge_model_id} but the judge configured now is "
            f"{judge_model_id}. An agreement figure describes one judge; inheriting it across a model "
            "change would attach a measurement to a judge that was never measured."
        )


def run_tier2(
    pool: Pool,
    validation: Validation,
    *,
    llm: LLM,
    revision: str,
    rubrics: Sequence[str] | None = None,
    progress: Callable[[str], None] | None = None,
    limiter: RateLimiter | None = None,
) -> Tier2Run:
    """Judge every sampled item. **No human labels, and none are asked for.**

    The contrast with `run_judge` is the point: that function refuses an unlabeled pool because its
    output is a statement about the judge. This one requires an unlabeled pool's *validation* instead,
    because its output is a statement about the agent.
    """
    if not validation.measured:
        raise NoValidationRuns(
            "the inherited agreement has no measured items (n=0), so no tier 2 number may be "
            "produced from it. See .claude/rules/evals.md."
        )
    guard_model(llm.model_id)
    guard_validated_judge(validation, llm.model_id)

    say = progress if progress is not None else (lambda line: None)
    pacer = (
        limiter
        if limiter is not None
        else RateLimiter(requests_per_minute=JUDGE_REQUESTS_PER_MINUTE)
    )
    texts = list(rubrics) if rubrics is not None else [load_rubric(n) for n in RUBRIC_NAMES]

    judgements: list[Judgement] = []
    usage = Usage()
    for index, item in enumerate(pool.items, start=1):
        pacer.acquire()
        say(f"[{index}/{len(pool.items)}] {item.item_id}")
        judgement, item_usage = judge_item(item, llm=llm, rubrics=texts)
        judgements.append(judgement)
        usage = usage + item_usage

    return Tier2Run(
        sample=pool.name,
        sample_size=len(pool.items),
        seed=pool.seed,
        sources=tuple(dict(source) for source in pool.sources),
        judge_model_id=llm.model_id,
        judged_at=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        code_revision=revision,
        judgements=tuple(judgements),
        usage=usage,
        validation=validation,
    )


def render(run: Tier2Run) -> str:
    """The tier 2 block. **Raises `NoValidationRuns` when either inherited figure is unmeasured.**

    The rendering half of the rule `report.render_judged` enforces for step 7, kept in the same shape
    on purpose: a judged score is unprintable without the agreement that says what it is worth.
    """
    for figure in (run.validation.citation_support, run.validation.narrative_quality):
        if not figure.measured:
            raise NoValidationRuns(
                f"{figure.metric} has no measured judge-human agreement, so no tier 2 number may be "
                "rendered. A judged score with no agreement is decoration; see "
                ".claude/rules/evals.md."
            )

    supported, scored = run.supported_rate
    quality = f"{run.mean_quality:.2f}" if run.mean_quality is not None else "undefined (0 items)"
    sources = ", ".join(str(source.get("written_at", "?")) for source in run.sources)
    lines = [
        f"tier 2: {run.sample} -- {run.sample_size} items, judge={run.judge_model_id}",
        f"  sampled from {sources} with seed {run.seed}",
        f"  code revision {run.code_revision}, judged at {run.judged_at}",
        "",
        "  judged metrics  [TRACKED, never blocking]",
        f"    citation_support: {supported}/{scored} SUPPORTED",
        *run.validation.citation_support.render(),
        f"    narrative_quality: mean {quality} of 5",
        *run.validation.narrative_quality.render(),
        "",
        f"  agreement inherited from {len(run.validation.runs)} validation run(s) over "
        f"{run.validation.pool}, not re-measured here: this sample has no human labels, and the "
        "labels exist to validate the judge rather than the candidate.",
        "",
        "  Read every judged number above together with the agreement figure under it. A judged "
        "score quoted alone is not a claim this project makes.",
    ]
    return "\n".join(lines)


def write_run(run: Tier2Run, *, directory: Path = RESULTS_DIR) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{run.judged_at}-tier2.json"
    path.write_text(json.dumps(run.to_json(), indent=2) + "\n", encoding="utf-8")
    return path


def estimate_for(pool: Pool, model_id: str) -> SpendEstimate:
    return SpendEstimate(
        description=f"tier 2: judge {len(pool.items)} sampled answers, {model_id}",
        cases=len(pool.items),
        requests=len(pool.items),
        input_tokens=len(pool.items) * ESTIMATED_INPUT_TOKENS_PER_ITEM,
        output_tokens=len(pool.items) * ESTIMATED_OUTPUT_TOKENS_PER_ITEM,
        model_id=model_id,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tier2",
        description="Tier 2: judge a sample of a release candidate. Spends money.",
    )
    parser.add_argument(
        "--transcript",
        action="append",
        default=None,
        help="a transcript to sample from; repeatable. Defaults to the newest.",
    )
    parser.add_argument("--size", type=int, default=SAMPLE_SIZE)
    parser.add_argument("--seed", type=int, default=SAMPLE_SEED)
    parser.add_argument(
        "--allow-short",
        action="store_true",
        help="accept a sample smaller than --size. A smaller n, permanently, next to every number.",
    )
    parser.add_argument(
        "--allow-unpinnable",
        action="store_true",
        help="judge a source whose code revision is dirty or unknown. The score then names no "
        "particular code, and the result file records that it was allowed.",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """`make eval-tier2`. Spends money. Confirms once, then runs unattended.

    Every refusal below happens **before** `confirm_spend`, so a misconfigured tier 2 run costs
    nothing: no validation runs, validation runs that disagree, a rubric the labels were not written
    against, a judge the agreement was not measured on, a same-family judge, an unpinnable source, or
    a transcript too thin to sample.
    """
    args = _parser().parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.transcript:
        paths = [Path(name) for name in args.transcript]
    else:
        newest = transcripts.newest()
        if newest is None:
            print(
                "not started: no transcript to sample. Run make eval-live first.",
                file=sys.stderr,
            )
            return 2
        paths = [newest]

    missing = [path for path in paths if not path.exists()]
    if missing:
        print(f"not started: no transcript at {missing[0]}", file=sys.stderr)
        return 2

    try:
        validation = load_validation()
    except (NoValidationRuns, ValidationRunsDisagree) as refusal:
        print(f"not started: {refusal}", file=sys.stderr)
        return 2

    # The rubric lock, reused rather than reimplemented: the inherited agreement was measured on a
    # judge reading the rubric text the labels were written against, and only that text.
    try:
        pool_for_labels = load_pool(POOL_PATH)
        guard_rubrics(load_labels(LABELS_PATH, pool_path=POOL_PATH, pool=pool_for_labels))
    except (PoolError, RubricChanged) as refusal:
        print(f"not started: {refusal}", file=sys.stderr)
        return 2

    model_id = model_id_for(ROLE_JUDGE)
    try:
        guard_model(model_id)
        guard_validated_judge(validation, model_id)
    except (SelfPreferenceRefused, JudgeNotValidated) as refusal:
        print(f"not started: {refusal}", file=sys.stderr)
        return 2

    try:
        pool = sample_from(
            [transcripts.load(path) for path in paths],
            size=args.size,
            seed=args.seed,
            allow_short=args.allow_short,
            allow_unpinnable=args.allow_unpinnable,
        )
    except (NotAReleaseCandidate, PoolError) as refusal:
        print(f"not started: {refusal}", file=sys.stderr)
        return 2

    revision = code_revision()
    try:
        confirm_spend(estimate_for(pool, model_id))
    except UnattendedSpend as refusal:
        print(f"\nnot started: {refusal}", file=sys.stderr)
        return 2
    except SpendRefused:
        print("\nnot confirmed; nothing was spent.", file=sys.stderr)
        return 2
    except SpendCapExceeded as capped:
        print(f"\nrefused by the hard cap: {capped}", file=sys.stderr)
        return 2

    print("\nconfirmed; judging. This is unattended from here.\n", flush=True)
    run = run_tier2(
        pool,
        validation,
        llm=build_llm("bedrock", role=ROLE_JUDGE),
        revision=revision,
        progress=lambda line: print(line, flush=True),
    )
    path = write_run(run)

    print()
    print(render(run))
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
