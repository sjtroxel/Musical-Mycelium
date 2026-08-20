"""Labelling tests. Half are about the blindness ordering; the rest are about not losing his work.

Two failure modes this module has to make impossible. The first is contamination — a human label sitting
next to a machine's answer, which cannot be detected afterwards and invalidates the agreement figure the
whole judged half of phase 4 rests on. The second is mundane and would hurt more on the night: a label
sitting that ends at item 7 and leaves nothing on disk.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from musical_mycelium.eval import labelling
from musical_mycelium.eval.labelling import (
    QUALITY_LEVELS,
    RUBRIC_NAMES,
    SUPPORT_LEVELS,
    ForbiddenLabelField,
    Pool,
    PoolChanged,
    PoolError,
    RubricChanged,
    build_pool,
    load_labels,
    load_pool,
    next_unlabeled,
    progress_line,
    record_label,
    render_item,
    write_pool,
)
from musical_mycelium.eval.transcripts import CaseTranscript, ClaimRow, RunTranscript


def _claim(subject: str = "blues rock", obj: str = "blues") -> ClaimRow:
    return ClaimRow(
        subject=subject,
        predicate="influenced_by",
        object=obj,
        subject_id="Q193355",
        object_id="Q9759",
        source_ids=("http://www.wikidata.org/entity/statement/Q193355-ABC",),
        verification="HAND",
    )


def _run(stamp: str, case_ids: list[str], *, provider: str = "bedrock") -> RunTranscript:
    return RunTranscript(
        dataset="live",
        provider=provider,
        model_id="us.anthropic.claude-haiku-4-5-20251001-v1:0",
        artifact_version="0.5.0",
        code_revision="abc1234",
        written_at=stamp,
        cases=tuple(
            CaseTranscript(
                case_id=case_id,
                query=f"where did {case_id} come from?",
                refused=False,
                refusal_reason="",
                prose=f"An answer about {case_id}.",
                claims=(_claim(), _claim("heavy metal", "blues rock")),
            )
            for case_id in case_ids
        ),
    )


@pytest.fixture
def pool_on_disk(tmp_path: Path) -> Path:
    pool = build_pool([_run("R1", [f"case_{i:02d}" for i in range(6)])], size=6)
    return write_pool(pool, tmp_path / "pool.json")


# --- the pool ---------------------------------------------------------------------------------------


def test_a_refusing_case_is_not_poolable() -> None:
    """Refusal is correct behaviour and is measured deterministically, as a pair, on every run. Asking a
    judge to re-score it adds noise to a number that has none — and a refused case has no prose to score
    narrative quality on and no claim to score support against."""
    run = RunTranscript(
        dataset="live",
        provider="bedrock",
        model_id="m",
        artifact_version="0.5.0",
        code_revision="r",
        written_at="R1",
        cases=(
            CaseTranscript(
                case_id="answered",
                query="q",
                refused=False,
                refusal_reason="",
                prose="text",
                claims=(_claim(),),
            ),
            CaseTranscript(
                case_id="refused",
                query="q",
                refused=True,
                refusal_reason="no path",
                prose="",
                claims=(),
            ),
            CaseTranscript(
                case_id="answered_without_claims",
                query="q",
                refused=False,
                refusal_reason="",
                prose="text",
                claims=(),
            ),
        ),
    )
    pool = build_pool([run], size=1)
    assert [item.case_id for item in pool.items] == ["answered"]


def test_a_scripted_transcript_is_refused() -> None:
    """`ScriptedLLM`'s synthesis is the fixed string `A grounded answer.` A pool built from one would
    have a human and a model scoring narrative quality on a stub, and the agreement figure would be
    real, reproducible, and about nothing.

    Broken deliberately on 2026-08-19 by dropping the provider check: the scripted gold run built a
    30-item pool of identical stub answers without complaint, and this test failed.
    """
    scripted = _run("R1", ["a", "b"], provider="scripted")
    with pytest.raises(PoolError, match="scripted"):
        build_pool([scripted], size=2)
    assert len(build_pool([scripted], size=2, allow_scripted=True).items) == 2


def test_a_short_pool_is_refused_unless_it_is_asked_for() -> None:
    """One live run answers roughly 25 of its 41 cases, so a 30-item pool needs two runs — and that is
    arithmetic, not a preference. A pool that quietly comes in short would put a smaller n behind every
    judged number without anyone deciding to."""
    one_run = _run("R1", [f"case_{i:02d}" for i in range(4)])
    with pytest.raises(PoolError, match="target"):
        build_pool([one_run], size=30)

    short = build_pool([one_run], size=30, allow_short=True)
    assert short.short
    assert len(short.items) == 4


def test_every_case_is_used_once_before_any_case_is_used_twice() -> None:
    """Two runs of the same 4 cases can fill a 6-item pool, and the two extra items must be second
    answers rather than a random draw that repeats one case three times while never showing another."""
    runs = [_run("R1", ["a", "b", "c", "d"]), _run("R2", ["a", "b", "c", "d"])]
    pool = build_pool(runs, size=6)
    counts = dict.fromkeys("abcd", 0)
    for item in pool.items:
        counts[item.case_id] += 1
    assert sorted(counts.values()) == [1, 1, 2, 2]


def test_the_same_seed_builds_the_same_pool() -> None:
    """Reproducible from the same transcripts, which is what makes "the pool was not reshuffled until it
    looked better" a checkable statement rather than a promise."""
    runs = [_run("R1", [f"case_{i:02d}" for i in range(8)])]
    first = build_pool(runs, size=5, seed=7)
    second = build_pool(runs, size=5, seed=7)
    different = build_pool(runs, size=5, seed=8)
    assert [i.case_id for i in first.items] == [i.case_id for i in second.items]
    assert [i.case_id for i in first.items] != [i.case_id for i in different.items]


def test_an_empty_population_raises_rather_than_producing_an_empty_pool() -> None:
    empty = RunTranscript(
        dataset="live",
        provider="bedrock",
        model_id="m",
        artifact_version="0.5.0",
        code_revision="r",
        written_at="R1",
        cases=(),
    )
    with pytest.raises(PoolError):
        build_pool([empty], size=1)


def test_write_then_load_round_trips(tmp_path: Path) -> None:
    pool = build_pool([_run("R1", ["a", "b"])], size=2)
    path = write_pool(pool, tmp_path / "pool.json")
    assert load_pool(path).to_json() == pool.to_json()


# --- the blindness locks ----------------------------------------------------------------------------


def test_a_label_file_carrying_a_judge_score_is_refused(pool_on_disk: Path, tmp_path: Path) -> None:
    """**The blindness lock.** The label file is defined by what it may hold, not by what it must not.

    A judge score, a model id or a rationale in this file means a human label written next to a
    machine's answer, and no inspection afterwards can tell a contaminated label from a clean one — so
    the contamination has to be impossible to write rather than merely discouraged.

    Broken deliberately on 2026-08-19 by dropping the allowlist check from `load_labels`: a file with a
    `judge_citation_support` field beside every human label loaded silently, and this test failed.
    """
    labels = tmp_path / "labels.json"
    labels.write_text(
        json.dumps(
            {
                "pool": "judge_pool_v1",
                "pool_sha256": hashlib.sha256(pool_on_disk.read_bytes()).hexdigest(),
                "labels": [
                    {
                        "item_id": "judge_pool_v1_001",
                        "citation_support": "SUPPORTED",
                        "narrative_quality": 4,
                        "note": "",
                        "labeled_at": "20260819T000000Z",
                        "judge_citation_support": "SUPPORTED",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(ForbiddenLabelField, match="judge_citation_support"):
        load_labels(labels, pool_path=pool_on_disk)


def test_labels_are_refused_when_the_pool_has_been_rebuilt(
    pool_on_disk: Path, tmp_path: Path
) -> None:
    """Labels are bound to items by id. A rebuilt pool re-pairs every label with whatever item now holds
    that id, and the result looks completely normal — same file, same ids, different answers.

    The same reasoning as the held-out manifest: a set rewritten after the fact must be detectable.
    """
    labels = tmp_path / "labels.json"
    record_label(
        "judge_pool_v1_001",
        citation_support="SUPPORTED",
        narrative_quality=4,
        path=labels,
        pool_path=pool_on_disk,
    )

    rebuilt = build_pool([_run("R2", [f"other_{i:02d}" for i in range(6)])], size=6)
    write_pool(rebuilt, pool_on_disk)

    with pytest.raises(PoolChanged):
        load_labels(labels, pool_path=pool_on_disk)


def test_labels_are_refused_when_a_rubric_has_been_rewritten(
    pool_on_disk: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """`PoolChanged` protects the items; this protects the instructions.

    Agreement is a number about two raters answering the same question. Step 7 budgets two rubric
    rewrites for a poor agreement figure, so the path where a rubric moves under an existing label set
    is planned for, not hypothetical — and re-judging under v2 against labels written under v1 produces
    a kappa that looks entirely normal.
    """
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    for name in RUBRIC_NAMES:
        (rubrics / f"{name}.md").write_text(f"# {name}\noriginal\n", encoding="utf-8")
    monkeypatch.setattr(labelling, "RUBRICS_DIR", rubrics)

    labels = tmp_path / "labels.json"
    record_label(
        "judge_pool_v1_001",
        citation_support="SUPPORTED",
        narrative_quality=4,
        path=labels,
        pool_path=pool_on_disk,
    )
    assert json.loads(labels.read_text(encoding="utf-8"))["rubric_sha256"]

    (rubrics / f"{RUBRIC_NAMES[1]}.md").write_text(
        f"# {RUBRIC_NAMES[1]}\nrewritten\n", encoding="utf-8"
    )

    with pytest.raises(RubricChanged):
        load_labels(labels, pool_path=pool_on_disk)


def test_the_rubric_digest_is_not_ambiguous_about_where_one_rubric_ends(tmp_path: Path) -> None:
    """Two different rubric pairs whose bytes concatenate identically must not share a digest.

    This is the property the name-and-NUL separator actually buys, and it is **not** the same as
    "a swap changes the hash" — plain concatenation already catches a swap, because the order of the
    two byte strings differs. What plain concatenation does not catch is a moved boundary: ("A", "BC")
    and ("AB", "C") both stream as `ABC`. Delimiting each rubric with its own name makes the boundary
    explicit, so instructions that differ cannot hash the same.

    Written after the first version of this test passed with the separator deleted, which is the whole
    reason locks get broken before they are trusted.
    """
    first, second = RUBRIC_NAMES

    def digest_of(one: str, two: str) -> str:
        directory = tmp_path / f"rubrics-{one}-{two}"
        directory.mkdir()
        (directory / f"{first}.md").write_text(one, encoding="utf-8")
        (directory / f"{second}.md").write_text(two, encoding="utf-8")
        return labelling.rubric_digest(directory=directory)

    assert digest_of("A", "BC") != digest_of("AB", "C")


def test_the_rubric_digest_is_stable_and_order_sensitive(tmp_path: Path) -> None:
    """Identical bytes hash identically; exchanging the two rubrics' contents does not."""
    first, second = RUBRIC_NAMES

    def digest_of(name: str, one: str, two: str) -> str:
        directory = tmp_path / name
        directory.mkdir()
        (directory / f"{first}.md").write_text(one, encoding="utf-8")
        (directory / f"{second}.md").write_text(two, encoding="utf-8")
        return labelling.rubric_digest(directory=directory)

    original = digest_of("original", "A\n", "B\n")
    assert digest_of("same", "A\n", "B\n") == original
    assert digest_of("swapped", "B\n", "A\n") != original


def test_a_missing_rubric_is_an_error_not_an_empty_digest(tmp_path: Path) -> None:
    """A deleted rubric must not silently hash to "the other one". That would make a label set look
    bound to instructions that no longer exist."""
    rubrics = tmp_path / "rubrics"
    rubrics.mkdir()
    (rubrics / f"{RUBRIC_NAMES[0]}.md").write_text("A\n", encoding="utf-8")

    with pytest.raises(FileNotFoundError):
        labelling.rubric_digest(directory=rubrics)


# --- not losing his work ----------------------------------------------------------------------------


def test_each_label_is_written_immediately(pool_on_disk: Path, tmp_path: Path) -> None:
    """The property that makes a sitting stoppable. Three labels in, the file has three labels — not an
    in-memory buffer that a closed terminal takes with it."""
    labels = tmp_path / "labels.json"
    for index in range(1, 4):
        record_label(
            f"judge_pool_v1_{index:03d}",
            citation_support="SUPPORTED",
            narrative_quality=3,
            path=labels,
            pool_path=pool_on_disk,
        )
        on_disk = json.loads(labels.read_text(encoding="utf-8"))
        assert len(on_disk["labels"]) == index


def test_progress_says_where_it_is(pool_on_disk: Path, tmp_path: Path) -> None:
    """A session starting cold reads one line instead of reconstructing progress from a diff."""
    labels = tmp_path / "labels.json"
    pool = load_pool(pool_on_disk)
    assert progress_line(pool, load_labels(labels, pool_path=pool_on_disk)).startswith(
        "0 of 6 labeled, next is judge_pool_v1_001"
    )

    record_label(
        "judge_pool_v1_001",
        citation_support="OVERSTATED",
        narrative_quality=2,
        path=labels,
        pool_path=pool_on_disk,
    )
    line = progress_line(pool, load_labels(labels, pool_path=pool_on_disk))
    assert line.startswith("1 of 6 labeled, next is judge_pool_v1_002")


def test_next_unlabeled_skips_what_is_done_and_ends_at_complete(
    pool_on_disk: Path, tmp_path: Path
) -> None:
    labels = tmp_path / "labels.json"
    pool = load_pool(pool_on_disk)
    for item in pool.items:
        record_label(
            item.item_id,
            citation_support="SUPPORTED",
            narrative_quality=5,
            path=labels,
            pool_path=pool_on_disk,
        )
    loaded = load_labels(labels, pool_path=pool_on_disk)
    assert next_unlabeled(pool, loaded) is None
    assert "COMPLETE" in progress_line(pool, loaded)


def test_a_correction_is_a_second_record_not_an_edit(pool_on_disk: Path, tmp_path: Path) -> None:
    """Append-only, last-write-wins. A mislabel and its fix are both visible, because a label set is
    evidence about a human and evidence that can be silently rewritten is not evidence."""
    labels = tmp_path / "labels.json"
    record_label(
        "judge_pool_v1_001",
        citation_support="SUPPORTED",
        narrative_quality=5,
        path=labels,
        pool_path=pool_on_disk,
    )
    with pytest.raises(PoolError, match="already labeled"):
        record_label(
            "judge_pool_v1_001",
            citation_support="OVERSTATED",
            narrative_quality=2,
            path=labels,
            pool_path=pool_on_disk,
        )
    record_label(
        "judge_pool_v1_001",
        citation_support="OVERSTATED",
        narrative_quality=2,
        path=labels,
        pool_path=pool_on_disk,
        replace=True,
    )
    loaded = load_labels(labels, pool_path=pool_on_disk)
    assert len(loaded.records) == 2
    assert loaded.by_item["judge_pool_v1_001"].citation_support == "OVERSTATED"


def test_an_absent_label_file_is_an_ordinary_state(pool_on_disk: Path, tmp_path: Path) -> None:
    """It is where 7b starts. Returning an empty set rather than raising is what lets `status` be the
    first command anyone runs."""
    loaded = load_labels(tmp_path / "nothing.json", pool_path=pool_on_disk)
    assert loaded.records == ()


@pytest.mark.parametrize("support", ["supported", "MAYBE", ""])
def test_an_off_scale_support_level_is_refused(
    support: str, pool_on_disk: Path, tmp_path: Path
) -> None:
    with pytest.raises(ValueError, match="citation_support"):
        record_label(
            "judge_pool_v1_001",
            citation_support=support,
            narrative_quality=3,
            path=tmp_path / "labels.json",
            pool_path=pool_on_disk,
        )


@pytest.mark.parametrize("quality", [0, 6, -1])
def test_an_off_scale_quality_is_refused(quality: int, pool_on_disk: Path, tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="narrative_quality"):
        record_label(
            "judge_pool_v1_001",
            citation_support="SUPPORTED",
            narrative_quality=quality,
            path=tmp_path / "labels.json",
            pool_path=pool_on_disk,
        )


def test_an_unknown_item_is_refused(pool_on_disk: Path, tmp_path: Path) -> None:
    with pytest.raises(PoolError, match="not in"):
        record_label(
            "judge_pool_v1_999",
            citation_support="SUPPORTED",
            narrative_quality=3,
            path=tmp_path / "labels.json",
            pool_path=pool_on_disk,
        )


# --- what he reads ----------------------------------------------------------------------------------


def test_the_rendered_item_carries_everything_needed_to_judge_it(pool_on_disk: Path) -> None:
    """He judges from this text alone. Question, answer, every claim, the focus marker, and the allowed
    answers — with no id to type and no JSON to write."""
    pool: Pool = load_pool(pool_on_disk)
    item = pool.items[0]
    text = render_item(item, index=1, total=len(pool.items))

    assert item.query in text
    assert item.prose in text
    assert text.count(">>") >= 2  # the marked claim, and the line explaining the marker
    for claim in item.claims:
        assert f"{claim.subject} -{claim.predicate}-> {claim.object}" in text
    for support in SUPPORT_LEVELS:
        assert support in text
    for quality in QUALITY_LEVELS:
        assert str(quality) in text


def test_the_focus_claim_is_one_of_the_items_own_claims(pool_on_disk: Path) -> None:
    """An out-of-range focus index would raise at read time — but only once someone reached that item,
    which on a thirty-item pool could be a week later."""
    for item in load_pool(pool_on_disk).items:
        assert 0 <= item.focus_claim < len(item.claims)
        assert item.focus in item.claims
