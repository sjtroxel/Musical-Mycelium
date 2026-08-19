"""Report tests — the caveats are the feature, so the caveats are what get tested.

A report is the last place a number is honest before it becomes a sentence someone repeats. Every test
here is about something that must be impossible to omit, not about formatting.
"""

from __future__ import annotations

import dataclasses

import pytest

from musical_mycelium.agent.llm import Usage
from musical_mycelium.agent.loop import STOP_MAX_TURNS
from musical_mycelium.eval.agreement import Agreement, NoAgreementMeasured, categorical, ordinal
from musical_mycelium.eval.judge import Judgement, JudgeRun
from musical_mycelium.eval.labelling import QUALITY_LEVELS, SUPPORT_LEVELS
from musical_mycelium.eval.report import UnmarkedScriptedResult, render, render_judged
from musical_mycelium.eval.suite import PROVIDER_SCRIPTED, SuiteResult, run_gold_suite
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture(scope="module")
def result(store: InMemoryGraphStore) -> SuiteResult:
    return run_gold_suite(store)


@pytest.fixture(scope="module")
def text(result: SuiteResult) -> str:
    return render(result)


def _metric_lines(text: str) -> list[str]:
    """The lines between ``metrics:`` and the blank line that ends the block."""
    lines = text.splitlines()
    start = lines.index("metrics:") + 1
    end = next(i for i in range(start, len(lines)) if not lines[i].strip())
    return lines[start:end]


# --- the guard --------------------------------------------------------------------------------------


def test_render_refuses_an_unmarked_scripted_result(result: SuiteResult) -> None:
    """**The structural lock.** A scripted run whose script-determined metrics were not declared cannot
    be rendered at all.

    Deliberately over-strict. The failure it prevents is a future edit that adds a provider, forgets the
    marking, and produces a report where ``traversal_recall: 100.0%`` reads as a traversal result. A
    crash in CI is a much cheaper way to find that than a resume bullet.

    Broken deliberately on 2026-08-16 by defaulting the marking inside ``render`` instead of raising —
    the report came out clean and wrong, and this test failed.
    """
    unmarked = dataclasses.replace(result, script_determined=())
    with pytest.raises(UnmarkedScriptedResult):
        render(unmarked)


def test_a_real_model_result_renders_without_any_marking(result: SuiteResult) -> None:
    """The guard is about scripted runs specifically. A Bedrock result declares nothing script-determined
    and must render — otherwise step 4 cannot report at all."""
    live = dataclasses.replace(result, provider="bedrock", script_determined=())
    text = render(live)
    assert "SCRIPT-DETERMINED" not in text
    assert "[bedrock]" in text


# --- the provider travels with every number ----------------------------------------------------------


def test_every_metric_line_names_its_provider(text: str, result: SuiteResult) -> None:
    """On the line, not in a header the reader scrolls past. Appended to *every* line rather than to the
    ones that seem to need it, because which lines need it is exactly the judgement that goes wrong."""
    lines = _metric_lines(text)
    assert lines
    for line in lines:
        assert f"[{result.provider}]" in line, f"no provider on: {line}"


def test_the_slice_block_names_its_provider(text: str) -> None:
    assert f"slices of cases_correct  [{PROVIDER_SCRIPTED}]" in text


def test_script_determined_metrics_are_marked_and_the_others_are_not(
    text: str, result: SuiteResult
) -> None:
    marked = {
        line.split(":")[0].strip() for line in _metric_lines(text) if "SCRIPT-DETERMINED" in line
    }
    assert marked == set(result.script_determined)
    assert "edge_groundedness" not in marked
    assert "refusal_accuracy" not in marked


def test_the_prose_caveat_names_the_same_metrics_as_the_markers(
    text: str, result: SuiteResult
) -> None:
    """Two statements of the same fact drift. The prose block is generated from
    ``script_determined`` rather than typed out, and this is what stops someone editing one and not the
    other."""
    assert "what a scripted run does and does not show:" in text
    for metric in result.script_determined:
        assert metric in text.split("DOES NOT")[1]


# --- a partial or mispinned run says so, first --------------------------------------------------------


def test_an_incomplete_run_warns_above_the_metrics(result: SuiteResult) -> None:
    """Above, not below. A reader who has seen the headline has already formed the belief."""
    partial = dataclasses.replace(
        result, complete=False, aborted_reason="token budget exhausted after 2200 tokens"
    )
    text = render(partial)
    assert text.index("INCOMPLETE") < text.index("metrics:")
    assert "chosen by exhaustion" in text


def test_a_pin_mismatch_warns_that_every_number_is_against_the_wrong_corpus(
    result: SuiteResult,
) -> None:
    """Evals run against a pinned artifact version; a moved corpus silently invalidates every previous
    benchmark. Silently is the word this warning exists to falsify."""
    moved = dataclasses.replace(result, artifact_pin="0.4.0")
    text = render(moved)
    assert "WARNING" in text
    assert text.index("WARNING") < text.index("metrics:")


def test_a_clean_run_carries_no_warning(text: str) -> None:
    assert "WARNING" not in text
    assert "INCOMPLETE" not in text


def test_truncated_traversals_are_named_not_counted(text: str, result: SuiteResult) -> None:
    """Named, because "1 truncated" is not actionable and "gold_v0_1_001" is.

    Faked at the one place the property reads from — ``Done.stop_reason`` — rather than by stubbing the
    property, so the test exercises the real derivation. The naive policy truncates nothing, hence the
    negative assertion on the real run.
    """
    assert result.truncated_runs == ()
    assert "truncated traversals" not in text

    first = result.results[0]
    stalled = dataclasses.replace(
        first,
        run=dataclasses.replace(
            first.run, done=dataclasses.replace(first.run.done, stop_reason=STOP_MAX_TURNS)
        ),
    )
    faked = dataclasses.replace(result, results=(stalled, *result.results[1:]))
    faked_text = render(faked)

    assert faked.truncated_runs == (first.case.case_id,)
    assert f"truncated traversals: {first.case.case_id}" in faked_text


# --- rates render honestly ---------------------------------------------------------------------------


def test_an_undefined_rate_renders_as_undefined_rather_than_zero(store: InMemoryGraphStore) -> None:
    """``Rate.__str__`` refuses to print a percentage with no denominator, and the report routes every
    rate through it so that stays true of all of them rather than of the ones that remembered."""
    from musical_mycelium.eval.suite import run_suite

    empty = run_suite(
        [],
        store=store,
        llm_for=lambda case: pytest.fail("no case should be driven"),
        dataset="empty",
        dataset_version="0",
        artifact_pin=store.artifact_version,
    )
    text = render(empty)
    assert "undefined (0 of 0)" in text
    assert "100.0%" not in text
    assert "0.0%" not in text


def test_the_header_names_the_dataset_the_model_and_both_artifact_versions(
    text: str, result: SuiteResult
) -> None:
    assert result.dataset in text
    assert result.model_id in text
    assert result.artifact_version in text
    assert f"pinned to {result.artifact_pin}" in text


def test_a_numeric_dataset_version_keeps_its_v_prefix(text: str) -> None:
    assert "gold v0.1.0" in text


def test_a_composite_dataset_label_is_not_given_a_fake_v_prefix(result: SuiteResult) -> None:
    """The live run spans two datasets and says so. Prefixing that with ``v`` rendered as
    ``live vgold+adversarial``, which reads as a typo — and a header that looks broken makes a
    reader distrust the numbers under it."""
    composite = dataclasses.replace(result, dataset="live", dataset_version="gold+adversarial")
    header = render(composite).splitlines()[0]
    assert "live gold+adversarial" in header
    assert "vgold" not in header


# --- the judged block, and its agreement figure -------------------------------------------------------


def _judge_run(
    support: Agreement, quality: Agreement, judgements: tuple[Judgement, ...] = ()
) -> JudgeRun:
    return JudgeRun(
        pool="judge_pool_v1",
        model_id="amazon.nova-pro-v1:0",
        judged_at="20260819T000000Z",
        code_revision="abc1234",
        judgements=judgements,
        usage=Usage(input_tokens=1, output_tokens=1),
        support_agreement=support,
        quality_agreement=quality,
    )


def test_render_judged_refuses_a_judged_number_with_no_agreement() -> None:
    """**The step 7 guard, and rule 2's shape applied to the judge.** `.claude/rules/evals.md`: *"An
    LLM-judge score with no measured agreement is decoration."*

    Raising rather than printing a blank is the whole point — decoration is quotable and a crash is not.

    Broken deliberately on 2026-08-19 by rendering the block whenever agreement was merely *present*
    rather than measured: an `Agreement` with n=0 printed `exact undefined (0 of 0)` under a clean-looking
    mean quality score, and this test failed.
    """
    nothing = categorical("citation_support", [], [], levels=SUPPORT_LEVELS)
    real = ordinal("narrative_quality", [4], [4], levels=QUALITY_LEVELS)
    with pytest.raises(NoAgreementMeasured, match="citation_support"):
        render_judged(_judge_run(nothing, real))


def test_both_agreement_figures_are_checked_not_one() -> None:
    """A block printing one validated number beside one unvalidated one is worse than printing neither:
    the validated half lends its credibility to the other."""
    real = categorical("citation_support", ["SUPPORTED"], ["SUPPORTED"], levels=SUPPORT_LEVELS)
    nothing = ordinal("narrative_quality", [], [], levels=QUALITY_LEVELS)
    with pytest.raises(NoAgreementMeasured, match="narrative_quality"):
        render_judged(_judge_run(real, nothing))


def test_an_undefined_kappa_still_renders() -> None:
    """A degenerate label set has a real raw agreement and an honestly undefined chance correction.
    Refusing to render that would be refusing to report a measurement that was actually taken — which is
    a different thing from having taken none."""
    degenerate = categorical(
        "citation_support", ["SUPPORTED"] * 4, ["SUPPORTED"] * 4, levels=SUPPORT_LEVELS
    )
    quality = ordinal("narrative_quality", [4, 5], [4, 4], levels=QUALITY_LEVELS)
    text = render_judged(_judge_run(degenerate, quality))
    assert "undefined" in text
    assert "single category" in text


def test_the_judged_block_puts_agreement_next_to_every_number() -> None:
    """ "Next to" is structural here rather than a habit: the numbers and their agreement figures come
    out of the same object, so a caller cannot render one without the other."""
    support = categorical(
        "citation_support",
        ["SUPPORTED", "OVERSTATED"],
        ["SUPPORTED", "SUPPORTED"],
        levels=SUPPORT_LEVELS,
    )
    quality = ordinal("narrative_quality", [4, 2], [4, 3], levels=QUALITY_LEVELS)
    text = render_judged(
        _judge_run(
            support,
            quality,
            judgements=(
                Judgement("judge_pool_v1_001", "SUPPORTED", 4, ""),
                Judgement("judge_pool_v1_002", "SUPPORTED", 3, ""),
            ),
        )
    )
    assert "citation_support: 2/2 SUPPORTED" in text
    assert "narrative_quality: mean 3.50 of 5" in text
    assert "judge-human agreement" in text
    assert "n=2" in text
    assert "TRACKED, never blocking" in text
    assert "amazon.nova-pro-v1:0" in text
