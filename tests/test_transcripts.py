"""Transcript tests. The interesting ones are the refusals, not the round trip.

A transcript is the only file in this project that holds model prose in plaintext, which makes it the
one file that must never be written for the sealed set. Everything below the first section is ordinary
serialisation and is tested because a pool built from a mis-parsed transcript would be judged anyway.
"""

from __future__ import annotations

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
