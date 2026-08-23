"""Tier 2 tests. No Bedrock call is made anywhere in this file. Phase 4 step 8.

The property under test throughout is **inheritance without loss**: step 7 could make agreement
structural by computing it in the same object as the score, and step 8 cannot, because a release
candidate has no human labels. So every guard that keeps the inherited figure attached to the number it
qualifies is exercised here, and several of them are broken deliberately in the process.
"""

from __future__ import annotations

import json
from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.agent.llm import (
    DEFAULT_JUDGE_MODEL_ID,
    DEFAULT_MODEL_ID,
    LLMResponse,
    Usage,
)
from musical_mycelium.eval.budget import RateLimiter
from musical_mycelium.eval.judge import SelfPreferenceRefused
from musical_mycelium.eval.labelling import POOL_NAME
from musical_mycelium.eval.tier2 import (
    SAMPLE_NAME,
    SINGLE_RUN_CAVEAT,
    JudgeNotValidated,
    MetricValidation,
    NotAReleaseCandidate,
    NoValidationRuns,
    Tier2Run,
    Validation,
    ValidationRunsDisagree,
    guard_validated_judge,
    load_validation,
    render,
    run_tier2,
    sample_from,
    write_run,
)
from musical_mycelium.eval.transcripts import CaseTranscript, ClaimRow, RunTranscript

JUDGEMENT = '{"citation_support": "SUPPORTED", "narrative_quality": 4, "rationale": "fine"}'


class SpyJudgeLLM:
    """Replays a canned reply and counts requests. The count is what proves a guard ran *first*."""

    def __init__(self, *, model_id: str = DEFAULT_JUDGE_MODEL_ID) -> None:
        self._model_id = model_id
        self.calls = 0

    @property
    def model_id(self) -> str:
        return self._model_id

    def converse(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tool_config: dict[str, Any] | None = None,
        max_tokens: int = 1024,
    ) -> LLMResponse:
        self.calls += 1
        return LLMResponse(text=JUDGEMENT, usage=Usage(input_tokens=10, output_tokens=5))

    def stream(
        self, messages: list[dict[str, Any]], *, system: str | None = None, max_tokens: int = 1024
    ) -> Generator[str, None, Usage]:  # pragma: no cover - the judge never streams
        yield ""
        return Usage()


def _claim() -> ClaimRow:
    return ClaimRow(
        subject="blues rock",
        predicate="influenced_by",
        object="blues",
        subject_id="Q193355",
        object_id="Q9759",
        source_ids=("http://www.wikidata.org/entity/statement/Q193355-ABC",),
        verification="HAND",
    )


def _run(
    case_ids: list[str], *, revision: str = "abc1234", written_at: str = "R1"
) -> RunTranscript:
    return RunTranscript(
        dataset="live",
        provider="bedrock",
        model_id=DEFAULT_MODEL_ID,
        artifact_version="0.5.0",
        code_revision=revision,
        written_at=written_at,
        cases=tuple(
            CaseTranscript(
                case_id=case_id,
                query=f"where did {case_id} come from?",
                refused=False,
                refusal_reason="",
                prose=f"An answer about {case_id}.",
                claims=(_claim(),),
            )
            for case_id in case_ids
        ),
    )


def _judge_file(
    directory: Path,
    judged_at: str,
    *,
    kappa: float,
    quality_kappa: float,
    n: int = 30,
    model_id: str = DEFAULT_JUDGE_MODEL_ID,
    pool: str = POOL_NAME,
) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{judged_at}-judge.json"
    path.write_text(
        json.dumps(
            {
                "pool": pool,
                "model_id": model_id,
                "judged_at": judged_at,
                "agreement": {
                    "citation_support": {
                        "metric": "citation_support",
                        "n": n,
                        "exact": 0.7,
                        "kappa": kappa,
                        "kappa_kind": "cohen",
                    },
                    "narrative_quality": {
                        "metric": "narrative_quality",
                        "n": n,
                        "exact": 0.6,
                        "kappa": quality_kappa,
                        "kappa_kind": "quadratic-weighted",
                    },
                },
            }
        ),
        encoding="utf-8",
    )
    return path


@pytest.fixture
def validated(tmp_path: Path) -> Validation:
    """Three validation runs whose kappas span a range, as the real ones do."""
    results = tmp_path / "results"
    _judge_file(results, "R1", kappa=0.44, quality_kappa=0.66)
    _judge_file(results, "R2", kappa=0.48, quality_kappa=0.73)
    _judge_file(results, "R3", kappa=0.46, quality_kappa=0.70)
    return load_validation(directory=results)


def _tier2(validation: Validation, llm: SpyJudgeLLM | None = None) -> Tier2Run:
    return run_tier2(
        sample_from([_run(["a", "b", "c"])], size=3),
        validation,
        llm=llm or SpyJudgeLLM(),
        revision="abc1234",
        rubrics=["support rubric", "quality rubric"],
        limiter=RateLimiter(requests_per_minute=100_000),
    )


# --- the inherited figure is a range, not a point ------------------------------------------------


def test_validation_reports_kappa_as_a_range_across_runs(validated: Validation) -> None:
    """The 2026-08-21 finding, encoded: the judge is not deterministic at temperature 0."""
    assert validated.citation_support.kappa_low == 0.44
    assert validated.citation_support.kappa_high == 0.48
    assert validated.narrative_quality.kappa_low == 0.66
    assert validated.narrative_quality.kappa_high == 0.73
    assert validated.citation_support.runs == 3


def test_a_range_inside_one_band_states_that_band_once(validated: Validation) -> None:
    """0.44-0.48 is moderate at both ends, so the qualitative claim may be stated flatly."""
    assert validated.citation_support.bands == ("moderate",)
    assert validated.narrative_quality.bands == ("substantial",)


def test_a_range_straddling_a_band_boundary_reports_both_labels(tmp_path: Path) -> None:
    """The honest report of 0.58-0.64 is 'moderate, substantial', not the flattering end."""
    results = tmp_path / "results"
    _judge_file(results, "R1", kappa=0.58, quality_kappa=0.58)
    _judge_file(results, "R2", kappa=0.64, quality_kappa=0.64)
    validation = load_validation(directory=results)
    assert validation.citation_support.bands == ("moderate", "substantial")


def test_a_single_validation_run_is_reported_as_a_sample_not_a_bound(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _judge_file(results, "R1", kappa=0.48, quality_kappa=0.70)
    validation = load_validation(directory=results)
    rendered = "\n".join(validation.citation_support.render())
    assert "0.48" in rendered
    assert "0.48-0.48" not in rendered
    assert SINGLE_RUN_CAVEAT in rendered


def test_an_undefined_kappa_everywhere_stays_undefined_rather_than_becoming_zero(
    tmp_path: Path,
) -> None:
    """A kappa that could not be chance-corrected is not an agreement of zero."""
    results = tmp_path / "results"
    path = _judge_file(results, "R1", kappa=0.5, quality_kappa=0.5)
    payload = json.loads(path.read_text(encoding="utf-8"))
    for metric in payload["agreement"].values():
        metric["kappa"] = None
    path.write_text(json.dumps(payload), encoding="utf-8")

    validation = load_validation(directory=results)
    assert validation.citation_support.kappa_low is None
    assert validation.citation_support.bands == ("undefined",)
    assert "undefined" in "\n".join(validation.citation_support.render())


# --- refusals, all of them before any request is made --------------------------------------------


def test_no_committed_judge_run_means_no_tier_2_number(tmp_path: Path) -> None:
    with pytest.raises(NoValidationRuns):
        load_validation(directory=tmp_path / "empty")


def test_validation_runs_that_disagree_on_the_judge_are_refused(tmp_path: Path) -> None:
    """A range pooled across a model change measures the change, not the judge's noise."""
    results = tmp_path / "results"
    _judge_file(results, "R1", kappa=0.44, quality_kappa=0.66)
    _judge_file(results, "R2", kappa=0.48, quality_kappa=0.73, model_id="amazon.nova-lite-v1:0")
    with pytest.raises(ValidationRunsDisagree):
        load_validation(directory=results)


def test_validation_runs_that_disagree_on_the_pool_are_refused(tmp_path: Path) -> None:
    results = tmp_path / "results"
    _judge_file(results, "R1", kappa=0.44, quality_kappa=0.66)
    _judge_file(results, "R2", kappa=0.48, quality_kappa=0.73, pool="some_other_pool")
    with pytest.raises(ValidationRunsDisagree):
        load_validation(directory=results)


def test_a_judge_the_agreement_was_not_measured_on_is_refused_before_spending(
    validated: Validation,
) -> None:
    """The guard that matters most: inheriting a figure across a model swap would attach a
    measurement to a judge that was never measured. Nothing may be requested first."""
    spy = SpyJudgeLLM(model_id="amazon.nova-lite-v1:0")
    with pytest.raises(JudgeNotValidated):
        _tier2(validated, spy)
    assert spy.calls == 0


def test_a_same_family_judge_is_refused_before_spending(validated: Validation) -> None:
    spy = SpyJudgeLLM(model_id=DEFAULT_MODEL_ID)
    with pytest.raises(SelfPreferenceRefused):
        _tier2(validated, spy)
    assert spy.calls == 0


def test_an_unmeasured_validation_is_refused_before_spending(validated: Validation) -> None:
    """n=0 is no measurement, not an agreement of zero."""
    empty = MetricValidation(
        metric="citation_support",
        runs=1,
        n_low=0,
        n_high=0,
        kappa_low=None,
        kappa_high=None,
        kappa_kind="cohen",
        exact_low=None,
        exact_high=None,
    )
    spy = SpyJudgeLLM()
    with pytest.raises(NoValidationRuns):
        run_tier2(
            sample_from([_run(["a", "b"])], size=2),
            Validation(
                judge_model_id=DEFAULT_JUDGE_MODEL_ID,
                pool=POOL_NAME,
                runs=("R1",),
                citation_support=empty,
                narrative_quality=validated.narrative_quality,
            ),
            llm=spy,
            revision="abc1234",
            rubrics=["a", "b"],
            limiter=RateLimiter(requests_per_minute=100_000),
        )
    assert spy.calls == 0


def test_a_source_run_with_an_unpinnable_revision_is_not_a_release_candidate() -> None:
    """`-dirty` names no particular tree, so a score attributed to it names no particular code."""
    with pytest.raises(NotAReleaseCandidate):
        sample_from([_run(["a", "b"], revision="abc1234-dirty")], size=2)
    with pytest.raises(NotAReleaseCandidate):
        sample_from([_run(["a", "b"], revision="unknown")], size=2)


def test_an_unpinnable_source_can_be_judged_only_deliberately() -> None:
    pool = sample_from([_run(["a", "b"], revision="unknown")], size=2, allow_unpinnable=True)
    assert len(pool.items) == 2


# --- the collision lock --------------------------------------------------------------------------


def test_the_sample_pool_cannot_collide_with_the_labeled_validation_pool() -> None:
    """Two pools sharing an id space is how a tier 2 judgement ends up paired against a human label
    written about a different answer -- and nothing downstream would notice."""
    pool = sample_from([_run(["a", "b", "c"])], size=3)
    assert pool.name == SAMPLE_NAME
    assert pool.name != POOL_NAME
    for item in pool.items:
        assert item.item_id.startswith(f"{SAMPLE_NAME}_")
        assert not item.item_id.startswith(f"{POOL_NAME}_")


# --- the number and its agreement cannot be separated --------------------------------------------


def test_a_tier_2_run_cannot_be_constructed_without_its_validation() -> None:
    """The structural half of the rule. `validation` has no default, so there is no code path that
    produces a score and forgets to carry the figure that says what it is worth."""
    with pytest.raises(TypeError):
        Tier2Run(  # type: ignore[call-arg]
            sample=SAMPLE_NAME,
            sample_size=0,
            seed=1,
            sources=(),
            judge_model_id=DEFAULT_JUDGE_MODEL_ID,
            judged_at="R1",
            code_revision="abc1234",
            judgements=(),
            usage=Usage(),
        )


def test_every_judged_number_is_serialised_inside_the_same_object_as_its_agreement(
    validated: Validation,
) -> None:
    """Two parallel blocks -- scores here, validation there -- is the shape that lets a reader quote
    one without the other. Nesting is what makes 'reported next to' survive serialisation."""
    payload = _tier2(validated).to_json()
    assert set(payload["metrics"]) == {"citation_support", "narrative_quality"}
    for metric in payload["metrics"].values():
        assert metric["agreement"]["validation_runs"] == 3
        assert metric["agreement"]["kappa_low"] is not None


def test_a_tier_2_result_declares_itself_non_blocking(validated: Validation) -> None:
    """Tracked, never gated. `.claude/rules/evals.md`: block on correctness, track preferences."""
    payload = _tier2(validated).to_json()
    assert payload["tier"] == 2
    assert payload["blocking"] is False


def test_rendering_refuses_when_the_inherited_agreement_is_unmeasured(
    validated: Validation,
) -> None:
    """`report.render_judged`'s rule, kept in the same shape for the inherited figure."""
    run = _tier2(validated)
    unmeasured = MetricValidation(
        metric="narrative_quality",
        runs=0,
        n_low=0,
        n_high=0,
        kappa_low=None,
        kappa_high=None,
        kappa_kind="quadratic-weighted",
        exact_low=None,
        exact_high=None,
    )
    broken = Tier2Run(
        sample=run.sample,
        sample_size=run.sample_size,
        seed=run.seed,
        sources=run.sources,
        judge_model_id=run.judge_model_id,
        judged_at=run.judged_at,
        code_revision=run.code_revision,
        judgements=run.judgements,
        usage=run.usage,
        validation=Validation(
            judge_model_id=validated.judge_model_id,
            pool=validated.pool,
            runs=validated.runs,
            citation_support=validated.citation_support,
            narrative_quality=unmeasured,
        ),
    )
    with pytest.raises(NoValidationRuns):
        render(broken)


def test_the_rendered_block_carries_both_scores_and_both_agreement_figures(
    validated: Validation,
) -> None:
    text = render(_tier2(validated))
    assert "citation_support: 3/3 SUPPORTED" in text
    assert "narrative_quality: mean 4.00 of 5" in text
    assert "kappa 0.44-0.48" in text
    assert "kappa 0.66-0.73" in text
    assert "TRACKED, never blocking" in text
    assert "inherited from 3 validation run(s)" in text


def test_the_rendered_block_says_the_sample_was_not_re_labeled(validated: Validation) -> None:
    """A reader must not be able to mistake an inherited figure for one measured on this sample."""
    text = render(_tier2(validated))
    assert "not re-measured here" in text
    assert "no human labels" in text


# --- the vacuous-truth guard, applied to tier 2 ---------------------------------------------------


def test_a_sample_with_no_judgements_scores_nothing_rather_than_everything(
    validated: Validation,
) -> None:
    """`.claude/rules/evals.md` requires this shape generally, not only for groundedness: an empty
    output must not read as a perfect one. 0/0 is undefined, and `None` is how that is said here."""
    empty = Tier2Run(
        sample=SAMPLE_NAME,
        sample_size=0,
        seed=1,
        sources=(),
        judge_model_id=DEFAULT_JUDGE_MODEL_ID,
        judged_at="R1",
        code_revision="abc1234",
        judgements=(),
        usage=Usage(),
        validation=validated,
    )
    assert empty.mean_quality is None
    assert empty.supported_rate == (0, 0)
    payload = empty.to_json()
    assert payload["metrics"]["citation_support"]["rate"] is None
    assert payload["metrics"]["narrative_quality"]["mean"] is None


# --- provenance ----------------------------------------------------------------------------------


def test_the_result_records_the_seed_and_the_source_so_the_sample_is_reproducible(
    validated: Validation, tmp_path: Path
) -> None:
    """'The sample was not reshuffled until the score improved' has to be checkable, not promised."""
    path = write_run(_tier2(validated), directory=tmp_path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["seed"] == 20260823
    assert payload["sources"][0]["written_at"] == "R1"
    assert payload["sources"][0]["code_revision"] == "abc1234"
    assert payload["validation_runs"] == ["R1", "R2", "R3"]


def test_the_same_transcript_and_seed_sample_the_same_items() -> None:
    first = sample_from([_run(["a", "b", "c", "d"])], size=3)
    second = sample_from([_run(["a", "b", "c", "d"])], size=3)
    assert [item.case_id for item in first.items] == [item.case_id for item in second.items]


def test_guard_validated_judge_accepts_the_model_it_was_measured_on(validated: Validation) -> None:
    guard_validated_judge(validated, DEFAULT_JUDGE_MODEL_ID)
