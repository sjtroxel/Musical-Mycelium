"""Transcript tests. The interesting ones are the refusals, not the round trip.

A transcript is the only file in this project that holds model prose in plaintext, which makes it the
one file that must never be written for the sealed set. Everything below the first section is ordinary
serialisation and is tested because a pool built from a mis-parsed transcript would be judged anyway.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from musical_mycelium.eval import transcripts
from musical_mycelium.eval.suite import SuiteResult, run_gold_suite
from musical_mycelium.eval.transcripts import (
    CaseTranscript,
    ClaimRow,
    RunTranscript,
    SealedDatasetRefused,
)
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture(scope="module")
def result(store: InMemoryGraphStore) -> SuiteResult:
    return run_gold_suite(store)


@pytest.fixture(scope="module")
def transcript(result: SuiteResult, store: InMemoryGraphStore) -> RunTranscript:
    return transcripts.build(result, store, revision="test")


def _sealed(dataset: str) -> RunTranscript:
    return RunTranscript(
        dataset=dataset,
        provider="bedrock",
        model_id="m",
        artifact_version="0.5.0",
        code_revision="abc",
        written_at="20260819T000000Z",
        cases=(
            CaseTranscript(
                case_id="x", query="q", refused=False, refusal_reason="", prose="p", claims=()
            ),
        ),
    )


# --- the sealed-set refusal -------------------------------------------------------------------------


@pytest.mark.parametrize(
    "dataset", ["heldout", "heldout_v1", "held-out", "held_out", "live+heldout", "SEALED"]
)
def test_a_sealed_dataset_cannot_be_transcribed(dataset: str, tmp_path: Path) -> None:
    """**The lock that matters.** `.claude/rules/heldout-set.md` allows case ids to leave the held-out
    run and nothing else. A transcript is prose, and prose is content.

    Substring matching rather than equality, because the name that actually arrives will be
    `heldout_v1` or `live+heldout` long before it is exactly `heldout`, and guessing wrong here is not
    recoverable — an unsealed set cannot be re-sealed into ignorance.

    Broken deliberately on 2026-08-19 by making `guard_dataset` compare with `==`: `heldout_v1` sailed
    through and wrote a file full of held-out prose into the repo. Restored, and this is the test that
    caught it.
    """
    with pytest.raises(SealedDatasetRefused):
        transcripts.write(_sealed(dataset), directory=tmp_path)


def test_the_refusal_guards_every_door_not_just_the_writer(tmp_path: Path) -> None:
    """`build`, `write` and `load` each check. A `RunTranscript` can be constructed directly, so a guard
    that lived only on the intended path would be a guard with a documented bypass."""
    sealed = _sealed("heldout_v1")
    path = tmp_path / "sealed.json"

    with pytest.raises(SealedDatasetRefused):
        transcripts.write(sealed, directory=tmp_path)

    # Written by hand, bypassing `write` entirely, to prove `load` refuses it too.
    path.write_text(
        '{"dataset": "heldout_v1", "provider": "b", "model_id": "m", "artifact_version": "0.5.0", '
        '"code_revision": "r", "written_at": "t", "cases": []}',
        encoding="utf-8",
    )
    with pytest.raises(SealedDatasetRefused):
        transcripts.load(path)


def test_an_ordinary_dataset_is_not_refused(transcript: RunTranscript, tmp_path: Path) -> None:
    """The guard has to let the live set through, or the pool can never be built."""
    assert transcripts.write(transcript, directory=tmp_path).exists()


# --- what a transcript carries ----------------------------------------------------------------------


def test_prose_survives_scoring(transcript: RunTranscript) -> None:
    """The whole reason this module exists: `score_case` reads numbers off a run and drops its prose,
    so nine committed result files carry no narrative at all and the judge had nothing to judge."""
    assert transcript.cases
    assert any(case.prose for case in transcript.cases)


def test_claims_carry_labels_and_ids_together(transcript: RunTranscript) -> None:
    """A human reads this file. `Q193355 -influenced_by-> Q9759` is not a judgeable sentence, and an id
    alone would make the label pass useless; a label alone would make it uncheckable."""
    rows = [claim for case in transcript.cases for claim in case.claims]
    assert rows
    for row in rows:
        assert row.subject and not row.subject.startswith("Q")
        assert row.subject_id.startswith("Q")
        assert row.source_ids


def test_answered_excludes_cases_that_wrote_nothing() -> None:
    """`answered` is not `not refused`. A case can end without refusing and still produce no prose, and
    a pool item with no answer cannot be scored for narrative quality."""
    run = RunTranscript(
        dataset="live",
        provider="bedrock",
        model_id="m",
        artifact_version="0.5.0",
        code_revision="r",
        written_at="t",
        cases=(
            CaseTranscript(
                case_id="a", query="q", refused=False, refusal_reason="", prose="text", claims=()
            ),
            CaseTranscript(
                case_id="b", query="q", refused=False, refusal_reason="", prose="   ", claims=()
            ),
            CaseTranscript(
                case_id="c", query="q", refused=True, refusal_reason="no path", prose="", claims=()
            ),
        ),
    )
    assert [case.case_id for case in run.answered] == ["a"]


def test_write_then_load_round_trips(transcript: RunTranscript, tmp_path: Path) -> None:
    path = transcripts.write(transcript, directory=tmp_path)
    reloaded = transcripts.load(path)
    assert reloaded.to_json() == transcript.to_json()


def test_newest_is_the_last_stamp(tmp_path: Path) -> None:
    """Filenames are UTC stamps, so lexical order is chronological order — the same assumption
    `noise.py` already makes about result files."""
    for stamp in ("20260819T010000Z", "20260819T030000Z", "20260819T020000Z"):
        (tmp_path / f"{stamp}-bedrock.json").write_text("{}", encoding="utf-8")
    newest = transcripts.newest(tmp_path)
    assert newest is not None
    assert newest.name.startswith("20260819T030000Z")


def test_newest_is_none_when_there_are_none(tmp_path: Path) -> None:
    assert transcripts.newest(tmp_path / "missing") is None


def test_an_unresolvable_node_id_is_shown_as_the_id(store: InMemoryGraphStore) -> None:
    """It should not happen — the gate only approves claims whose endpoints exist — and if it does, a
    bare QID in a labelled column is the correct amount of alarming."""
    row = ClaimRow(
        subject="Q999999",
        predicate="influenced_by",
        object="blues",
        subject_id="Q999999",
        object_id="Q9759",
        source_ids=("s",),
        verification="HAND",
    )
    assert row.to_json()["subject"] == "Q999999"
    assert store.get_node("Q999999") is None


# --- the trace -------------------------------------------------------------------------------------
#
# Added 2026-09-07, phase 6.5 step 3. A transcript recorded what a run WROTE and not what it DID, so a
# refusing case's whole record was its refusal reason. `gold_v0_1_020` was diagnosed across a full day
# on `SuiteResult` metrics alone -- 11 refusals in 12 recorded runs, one perfect answer, and no way to
# see what the model reached for -- while `CaseRun` had carried `plan`, `tool_calls`, `unregistered`,
# `visited` and `rejections` since phase 3. The runner recorded them; this file dropped them.


def test_the_trace_records_what_the_model_actually_called(transcript: RunTranscript) -> None:
    answered = next(c for c in transcript.cases if c.claims)
    assert answered.trace.tool_calls, "a case that produced claims called no tools"
    assert all(call.name for call in answered.trace.tool_calls)


def test_the_trace_records_arguments_and_not_only_names(transcript: RunTranscript) -> None:
    """**The arguments are the diagnostic half.** A name says the model reached for `trace_lineage`;
    the arguments say whether it passed two ids or one, and in which order.

    Asserted on the SERIALISED form, not the in-memory object. The first draft checked the dataclass
    and a mutation that dropped arguments from `to_json` sailed straight past it -- the field a reader
    of a committed file actually sees is the one in the JSON (2026-09-07).
    """
    calls = [c for case in transcript.cases for c in case.trace.tool_calls]
    assert any(call.arguments for call in calls), "every recorded call had empty arguments"

    serialised = [
        call for case in transcript.to_json()["cases"] for call in case["trace"]["tool_calls"]
    ]
    assert any(call["arguments"] for call in serialised), (
        "arguments were dropped on the way to JSON"
    )


def test_a_refusing_case_still_carries_its_trace(transcript: RunTranscript) -> None:
    """The case this step exists for. A refusal used to record a reason and nothing else, which is the
    one shape where knowing what was attempted matters most."""
    refusals = [c for c in transcript.cases if c.refused]
    assert refusals, "the scripted gold run produced no refusal to check"
    assert any(c.trace.tool_calls or c.trace.planned_tools for c in refusals)


def test_the_plan_is_recorded_and_still_does_not_drive_execution(
    transcript: RunTranscript,
) -> None:
    """`loop.run` is explicit that no branch reads `plan`. Recording it changes nothing about that --
    the value is that `planned_tools` can be compared against `tool_calls`, which is how a premature
    stop becomes visible at all."""
    case = transcript.cases[0]
    assert case.trace.query_kind
    assert isinstance(case.trace.planned_tools, tuple)


def test_build_copies_every_trace_field_from_the_run_it_scored(
    result: SuiteResult, transcript: RunTranscript
) -> None:
    """**The lock that matters, and the first draft did not have it.**

    Four mutations were tried against these tests; the one that emptied `visited` and `rejections`
    inside `build` failed nothing, because the tests asserted `isinstance(..., tuple)` and `()` is a
    tuple. Asserting a type is not asserting a behaviour -- the same defect found one layer down in
    step 1. This compares the transcript against the `CaseRun` it was built from, field by field, so a
    dropped field cannot pass as an empty one.

    `rejections` matters for its own reason: `approved_claims: 0` collapses two different failures --
    the model proposed nothing, and the model proposed claims the gate threw out. Only this field
    separates them, and `gold_v0_1_020` is the first case where the difference decided a diagnosis.
    """
    assert len(transcript.cases) == len(result.results)
    for scored, case in zip(result.results, transcript.cases, strict=True):
        run = scored.run
        assert case.trace.query_kind == run.plan.query_kind
        assert case.trace.planned_tools == tuple(step.tool for step in run.plan.steps)
        assert case.trace.unregistered == run.unregistered
        assert case.trace.visited == run.visited
        assert case.trace.rejections == run.rejection_reasons
        assert [c.name for c in case.trace.tool_calls] == [c.name for c in run.tool_calls]
        assert [c.arguments for c in case.trace.tool_calls] == [
            dict(c.arguments) for c in run.tool_calls
        ]


def test_a_transcript_written_before_traces_existed_still_loads(tmp_path: Path) -> None:
    """**Eleven committed transcripts predate this field**, and `eval-tier2` and the judge pool builder
    both load them. An absent trace must read as "not recorded" rather than as an empty run -- the
    difference between a fact and a fabrication, in the file whose entire purpose is being read later.
    """
    legacy = {
        "dataset": "live",
        "provider": "bedrock",
        "model_id": "m",
        "artifact_version": "0.5.0",
        "code_revision": "abc",
        "written_at": "20260819T000000Z",
        "cases": [
            {
                "case_id": "x",
                "query": "q",
                "refused": True,
                "refusal_reason": "it is not in this graph",
                "prose": "p",
                "claims": [],
            }
        ],
    }
    path = tmp_path / "20260819T000000Z-bedrock.json"
    path.write_text(json.dumps(legacy), encoding="utf-8")

    loaded = transcripts.load(path)
    assert loaded.cases[0].trace is transcripts.NO_TRACE_RECORDED
    assert loaded.cases[0].trace.query_kind == "not-recorded"
    assert loaded.cases[0].trace.tool_calls == ()


def test_every_committed_transcript_still_loads() -> None:
    """The real files, not a synthetic one. A schema change that breaks the committed history breaks
    the judge pool, and the pool is the only thing tier 2 can be built from."""
    for path in sorted(transcripts.TRANSCRIPTS_DIR.glob("*.json")):
        assert transcripts.load(path).cases, f"{path.name} loaded with no cases"


def test_the_trace_round_trips(transcript: RunTranscript, tmp_path: Path) -> None:
    path = transcripts.write(transcript, directory=tmp_path)
    reloaded = transcripts.load(path)
    assert [c.trace for c in reloaded.cases] == [c.trace for c in transcript.cases]
