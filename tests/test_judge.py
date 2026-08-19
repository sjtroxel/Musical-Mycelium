"""Judge tests. No Bedrock call is made anywhere in this file.

Everything the judge does before and after the request is tested here: which model it may be, whether it
is allowed to run at all, how it reads a reply, and how its answers are paired with the human's. The
request itself is step 7c and costs money.
"""

from __future__ import annotations

from collections.abc import Generator
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.agent.llm import (
    DEFAULT_JUDGE_MODEL_ID,
    DEFAULT_MODEL_ID,
    JUDGE_TEMPERATURE,
    ROLE_JUDGE,
    BedrockLLM,
    LLMResponse,
    Usage,
    build_llm,
    model_id_for,
)
from musical_mycelium.eval.budget import RateLimiter
from musical_mycelium.eval.judge import (
    Judgement,
    PoolNotFullyLabeled,
    SelfPreferenceRefused,
    UnparseableJudgement,
    build_prompt,
    guard_model,
    load_rubric,
    measure_agreement,
    parse_judgement,
    run_judge,
    vendor_of,
)
from musical_mycelium.eval.labelling import (
    Labels,
    Pool,
    build_pool,
    load_labels,
    load_pool,
    record_label,
    write_pool,
)
from musical_mycelium.eval.transcripts import CaseTranscript, ClaimRow, RunTranscript


class FakeJudgeLLM:
    """Replays canned replies. Records what it was asked, so the prompt can be inspected."""

    def __init__(self, replies: list[str], *, model_id: str = DEFAULT_JUDGE_MODEL_ID) -> None:
        self._replies = list(replies)
        self._model_id = model_id
        self.prompts: list[str] = []

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
        self.prompts.append(messages[0]["content"][0]["text"])
        return LLMResponse(text=self._replies.pop(0), usage=Usage(input_tokens=10, output_tokens=5))

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


def _run(case_ids: list[str]) -> RunTranscript:
    return RunTranscript(
        dataset="live",
        provider="bedrock",
        model_id=DEFAULT_MODEL_ID,
        artifact_version="0.5.0",
        code_revision="abc1234",
        written_at="R1",
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


@pytest.fixture
def labeled(tmp_path: Path) -> tuple[Pool, Labels, Path]:
    """A three-item pool with every item labeled. What 7c starts from."""
    pool_path = write_pool(build_pool([_run(["a", "b", "c"])], size=3), tmp_path / "pool.json")
    labels_path = tmp_path / "labels.json"
    for index, (support, quality) in enumerate(
        [("SUPPORTED", 4), ("OVERSTATED", 2), ("SUPPORTED", 5)], start=1
    ):
        record_label(
            f"judge_pool_v1_{index:03d}",
            citation_support=support,
            narrative_quality=quality,
            path=labels_path,
            pool_path=pool_path,
        )
    return load_pool(pool_path), load_labels(labels_path, pool_path=pool_path), pool_path


def _fast_limiter() -> RateLimiter:
    """A limiter that never actually waits. The pacing itself is tested in `test_budget.py`."""
    return RateLimiter(requests_per_minute=10_000)


# --- the judge may not be the generator's family ------------------------------------------------------


@pytest.mark.parametrize(
    ("model_id", "expected"),
    [
        ("us.anthropic.claude-haiku-4-5-20251001-v1:0", "anthropic"),
        ("global.anthropic.claude-sonnet-4-6:0", "anthropic"),
        ("anthropic.claude-3-5-sonnet", "anthropic"),
        ("amazon.nova-pro-v1:0", "amazon"),
        ("meta.llama3-70b-instruct-v1:0", "meta"),
    ],
)
def test_the_vendor_is_read_past_any_inference_profile_prefix(model_id: str, expected: str) -> None:
    """`us.anthropic.claude-...` is Anthropic, not a vendor called `us`. Getting this wrong makes the
    self-preference guard pass every cross-region Anthropic model."""
    assert vendor_of(model_id) == expected


def test_a_judge_from_the_generators_family_is_refused() -> None:
    """`.claude/rules/evals.md`: the judge "must not be the generator's family". Family, not model — so
    this compares vendors rather than a blocklist of names that next year's models will not be on.

    Broken deliberately on 2026-08-19 by comparing full model ids instead of vendors: Sonnet judging
    Haiku passed the guard, which is precisely the self-preference case the rule exists for.
    """
    with pytest.raises(SelfPreferenceRefused, match="anthropic"):
        guard_model("us.anthropic.claude-sonnet-4-6:0", DEFAULT_MODEL_ID)


def test_the_default_judge_model_is_not_the_generators_family() -> None:
    """The first lock: the judge role has its own default rather than falling back to the traversal
    model, so an unset `MYCELIUM_JUDGE_MODEL_ID` cannot quietly point the judge at Haiku."""
    assert model_id_for(ROLE_JUDGE) == DEFAULT_JUDGE_MODEL_ID
    guard_model(model_id_for(ROLE_JUDGE), DEFAULT_MODEL_ID)


def test_the_judge_role_builds_a_deterministic_client() -> None:
    """Temperature 0 is a property of the role, set once at the seam, so no caller has to remember it.
    A judge that samples reports its own noise as judge-human disagreement."""
    judge = build_llm("bedrock", role=ROLE_JUDGE)
    assert isinstance(judge, BedrockLLM)
    request = judge._request([], system=None, max_tokens=64)
    assert request["inferenceConfig"]["temperature"] == JUDGE_TEMPERATURE

    generator = build_llm("bedrock")
    assert isinstance(generator, BedrockLLM)
    assert (
        "temperature" not in generator._request([], system=None, max_tokens=64)["inferenceConfig"]
    )


# --- blind means ordered ------------------------------------------------------------------------------


def test_the_judge_refuses_to_run_before_the_labels_are_finished(tmp_path: Path) -> None:
    """**The ordering lock.** Labels are collected before the judge runs, not after.

    A partial run "just to see" contaminates twice over: the items already judged, and every item
    labeled afterwards by someone who has now seen a machine's answer to a similar one.

    Broken deliberately on 2026-08-19 by letting `run_judge` skip unlabeled items instead of raising: a
    judge run on an empty label set produced a clean-looking result whose agreement was measured over
    zero items, and this test failed.
    """
    pool_path = write_pool(build_pool([_run(["a", "b"])], size=2), tmp_path / "pool.json")
    pool = load_pool(pool_path)
    labels_path = tmp_path / "labels.json"
    record_label(
        "judge_pool_v1_001",
        citation_support="SUPPORTED",
        narrative_quality=4,
        path=labels_path,
        pool_path=pool_path,
    )
    partial = load_labels(labels_path, pool_path=pool_path)

    with pytest.raises(PoolNotFullyLabeled, match="judge_pool_v1_002"):
        run_judge(
            pool,
            partial,
            llm=FakeJudgeLLM(['{"citation_support": "SUPPORTED", "narrative_quality": 4}'] * 2),
            revision="r",
            limiter=_fast_limiter(),
        )


# --- reading a reply ----------------------------------------------------------------------------------


def test_a_plain_json_reply_parses() -> None:
    judgement = parse_judgement(
        "i1",
        '{"citation_support": "OVERSTATED", "narrative_quality": 3, "rationale": "adds a decade"}',
    )
    assert judgement == Judgement("i1", "OVERSTATED", 3, "adds a decade")


def test_a_fenced_or_chatty_reply_still_parses() -> None:
    """Refusing a working judge over markdown fences would be refusing it over formatting."""
    reply = 'Here is my scoring:\n```json\n{"citation_support": "SUPPORTED", "narrative_quality": 5}\n```'
    assert parse_judgement("i1", reply).narrative_quality == 5


@pytest.mark.parametrize(
    "reply",
    [
        "no json here at all",
        '{"citation_support": "SUPPORTED"}',
        '{"citation_support": "MAYBE", "narrative_quality": 3}',
        '{"citation_support": "SUPPORTED", "narrative_quality": 9}',
        '{"citation_support": "SUPPORTED", "narrative_quality": "high"}',
        '{"citation_support": "SUPPORTED", "narrative_quality": 3',
    ],
)
def test_a_malformed_judgement_raises_rather_than_defaulting(reply: str) -> None:
    """**Never a middle score.** A judge whose parse failures silently become 3s reports a
    rubric-shaped average of its own bugs, and the agreement figure absorbs it without complaint.

    Broken deliberately on 2026-08-19 by returning a neutral judgement on a parse failure: every
    malformed reply became SUPPORTED/3 and the run completed looking healthy.
    """
    with pytest.raises(UnparseableJudgement):
        parse_judgement("i1", reply)


def test_a_lowercase_level_is_accepted_as_the_level_it_names() -> None:
    """Case is formatting, not meaning. The rubric prints the levels in caps and a model will sometimes
    answer in lower case; that is not a malformed judgement."""
    assert parse_judgement("i1", '{"citation_support": "supported", "narrative_quality": 4}')


# --- the prompt ---------------------------------------------------------------------------------------


def test_the_prompt_carries_both_rubrics_verbatim(labeled: tuple[Pool, Labels, Path]) -> None:
    """No summarising. If the wording the human read and the wording the judge read can drift apart, the
    agreement figure stops measuring the rubric and starts measuring the gap between two rubrics."""
    pool, _, _ = labeled
    rubrics = [load_rubric("citation_support"), load_rubric("narrative_quality")]
    prompt = build_prompt(pool.items[0], rubrics=rubrics)
    for rubric in rubrics:
        assert rubric in prompt


def test_the_prompt_shows_the_same_claims_the_human_saw(labeled: tuple[Pool, Labels, Path]) -> None:
    """Same order, same focus marker, same verification tier. Two renderings would mean the human and
    the judge scored two different presentations, and the disagreement would silently include that."""
    pool, _, _ = labeled
    item = pool.items[0]
    prompt = build_prompt(item, rubrics=["R1", "R2"])
    assert item.prose in prompt
    assert item.query in prompt
    assert f">> {item.focus.subject} -{item.focus.predicate}-> {item.focus.object}" in prompt
    assert item.focus.verification in prompt


# --- pairing and agreement ----------------------------------------------------------------------------


def test_agreement_pairs_by_item_id_not_by_position(labeled: tuple[Pool, Labels, Path]) -> None:
    """**The bug this prevents looks like a bad judge, not like a bug.** Two lists that are "obviously"
    in the same order is exactly how a label set ends up compared against the wrong answers.

    Judgements are handed over reversed here; agreement must be identical to the in-order case.
    """
    pool, labels, _ = labeled
    judgements = [
        Judgement("judge_pool_v1_001", "SUPPORTED", 4, ""),
        Judgement("judge_pool_v1_002", "OVERSTATED", 2, ""),
        Judgement("judge_pool_v1_003", "SUPPORTED", 5, ""),
    ]
    in_order = measure_agreement(pool, labels, judgements)
    reversed_order = measure_agreement(pool, labels, list(reversed(judgements)))
    assert in_order[0].exact.score == reversed_order[0].exact.score == 1.0
    assert in_order[1].exact.score == reversed_order[1].exact.score == 1.0


def test_only_items_with_both_a_label_and_a_judgement_are_paired(
    labeled: tuple[Pool, Labels, Path],
) -> None:
    """An item judged but not labeled, or labeled but not judged, is not evidence about agreement and
    must not silently become a disagreement."""
    pool, labels, _ = labeled
    support, quality = measure_agreement(
        pool, labels, [Judgement("judge_pool_v1_001", "SUPPORTED", 4, "")]
    )
    assert support.n == 1
    assert quality.n == 1


def test_a_full_run_scores_every_item_and_measures_agreement(
    labeled: tuple[Pool, Labels, Path],
) -> None:
    """The end-to-end shape, with a fake model. The judge disagrees on one of three items, so neither
    agreement figure may read perfect."""
    pool, labels, _ = labeled
    llm = FakeJudgeLLM(
        [
            '{"citation_support": "SUPPORTED", "narrative_quality": 4}',
            '{"citation_support": "SUPPORTED", "narrative_quality": 3}',
            '{"citation_support": "SUPPORTED", "narrative_quality": 5}',
        ]
    )
    run = run_judge(pool, labels, llm=llm, revision="abc1234", limiter=_fast_limiter())

    assert len(run.judgements) == 3
    assert run.usage.total_tokens == 45
    assert run.support_agreement.n == 3
    assert run.support_agreement.exact.score == pytest.approx(2 / 3)
    assert run.quality_agreement.exact.score == pytest.approx(2 / 3)
    assert run.mean_quality == pytest.approx(4.0)
    assert run.supported_rate == (3, 3)
    assert run.to_json()["agreement"]["citation_support"]["n"] == 3


def test_a_run_with_a_same_family_judge_is_refused_before_any_request(
    labeled: tuple[Pool, Labels, Path],
) -> None:
    """The guard runs inside `run_judge`, not only in `main`, so a caller that builds its own client
    cannot route around it."""
    pool, labels, _ = labeled
    llm = FakeJudgeLLM(["{}"], model_id="us.anthropic.claude-sonnet-4-6:0")
    with pytest.raises(SelfPreferenceRefused):
        run_judge(pool, labels, llm=llm, revision="r", limiter=_fast_limiter())
    assert llm.prompts == []
