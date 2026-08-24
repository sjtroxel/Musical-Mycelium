"""The held-out runner's locks. Every test here runs scripted, with no AWS, and costs nothing.

**What is under test is not the metrics -- it is the containment.** `tests/test_suite.py` already covers
scoring. This file covers the one property that is unique to the held-out set and that no other dataset
needs: that running it publishes numbers and publishes nothing else.

The method throughout is the one that worked on 2026-08-14 and is written into `CLAUDE.md`: **verify a
lock by breaking it.** Each test below poisons a real run with a sentinel string that could only have
come from a case, then asserts the sentinel is absent from whatever channel that test owns. A test that
merely asserts the happy path passes just as well when the lock has been deleted.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from musical_mycelium.agent.llm import ScriptedLLM
from musical_mycelium.eval import gold, heldout_run
from musical_mycelium.eval.heldout_run import (
    HELDOUT_ERROR_KEYS,
    HELDOUT_PER_CASE_KEYS,
    HELDOUT_RESULT_KEYS,
    ContentLeak,
    assert_writable,
    heldout_cases,
    redact,
    run_heldout,
    sanitise,
    write_result,
)
from musical_mycelium.eval.report import render
from musical_mycelium.eval.suite import CaseError, EvalCase, SuiteResult
from musical_mycelium.eval.thresholds import gate
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory

#: A string that could only have reached an output by coming from a case. Deliberately unlike any metric
#: name, provider, or bucket, so a hit is unambiguous.
SENTINEL = "WHAT-INFLUENCED-THE-SEALED-SUBJECT-DO-NOT-PUBLISH"


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture(scope="module")
def poisoned_result(store: InMemoryGraphStore) -> SuiteResult:
    """A real scripted run of one real case, wearing a sentinel query.

    `gold.build_script` never reads `case.query` -- it drives off `expected_resolution` -- so swapping
    the query for a sentinel produces a run that is genuine in every respect except that its query text
    is detectable. That is exactly the substitution needed: a fake `SuiteResult` assembled by hand would
    test the assertions rather than the pipeline.
    """
    case = gold.load_cases()[0]
    return run_heldout(
        [
            EvalCase(
                case_id="heldout_v1_001",
                query=SENTINEL,
                subject_id=case.subject_id,
                expected_refusal=case.expected_refusal,
                expected_path=case.expected_path,
            )
        ],
        artifact_pin=store.artifact_version,
        store=store,
        provider="scripted",
        llm_factory=lambda: ScriptedLLM(gold.build_script(case)),
    )


# --- the query must not reach any channel ---------------------------------------------------------


def test_the_query_never_reaches_the_written_file(
    poisoned_result: SuiteResult, tmp_path: Path
) -> None:
    """The headline guarantee. Break it by returning `payload` unchanged from `redact` and by deleting
    the `assert_writable` call: the sentinel then appears in the file and this fails."""
    cases = tuple(r.case for r in poisoned_result.results)
    path, _ = write_result(poisoned_result, cases, revision="test", directory=tmp_path)

    assert SENTINEL not in path.read_text(encoding="utf-8")


def test_the_query_never_reaches_the_rendered_report(poisoned_result: SuiteResult) -> None:
    """stdout is a publication channel too. `main` prints `render(...)` straight to the terminal, and a
    terminal is scrollback an agent can be handed."""
    assert SENTINEL not in render(sanitise(poisoned_result))


def test_the_case_id_does_survive(poisoned_result: SuiteResult, tmp_path: Path) -> None:
    """The other half, and it is not a formality. A writer that dropped ids too would be perfectly safe
    and perfectly useless -- `heldout.Finding` rests on exactly this: a case id is not content."""
    cases = tuple(r.case for r in poisoned_result.results)
    path, _ = write_result(poisoned_result, cases, revision="test", directory=tmp_path)

    assert "heldout_v1_001" in path.read_text(encoding="utf-8")


# --- lock 1: error messages -----------------------------------------------------------------------


def test_sanitise_drops_the_error_message_and_keeps_its_type() -> None:
    """`CaseError.message` is `str(exception)`, and a `ValueError` out of `synthesize` can quote a node
    label or a claim. The type is a code; the string is not."""
    result = _result_with_error(CaseError("heldout_v1_004", "ValueError", SENTINEL))

    sanitised = sanitise(result)

    assert sanitised.errors[0].message == ""
    assert sanitised.errors[0].error_type == "ValueError"
    assert sanitised.errors[0].case_id == "heldout_v1_004"


def test_an_unsanitised_error_message_would_reach_the_report() -> None:
    """**The lock, broken deliberately.** `report.py:77` prints `error.message` verbatim. This asserts
    the leak is real when `sanitise` is skipped, so the test above is testing something."""
    result = _result_with_error(CaseError("heldout_v1_004", "ValueError", SENTINEL))

    assert SENTINEL in render(result)
    assert SENTINEL not in render(sanitise(result))


def test_the_error_message_never_reaches_the_written_file(tmp_path: Path) -> None:
    result = _result_with_error(CaseError("heldout_v1_004", "ValueError", SENTINEL))

    path, payload = write_result(sanitise(result), (), revision="test", directory=tmp_path)

    assert SENTINEL not in path.read_text(encoding="utf-8")
    assert payload["errored_cases"] == [{"case_id": "heldout_v1_004", "error_type": "ValueError"}]
    assert "errors_redacted" in payload


# --- lock 2: the allowlists ------------------------------------------------------------------------


def test_redact_drops_a_per_case_key_no_allowlist_names(poisoned_result: SuiteResult) -> None:
    """**The failure this lock is built for**, simulated: someone adds `"query"` to `per_case` in
    `suite.py` to debug something, and the held-out writer starts publishing the set."""
    payload = poisoned_result.to_json()
    payload["per_case"][0]["query"] = SENTINEL
    payload["per_case"][0]["prose"] = SENTINEL

    redacted = redact(payload)

    assert "query" not in redacted["per_case"][0]
    assert "prose" not in redacted["per_case"][0]
    assert redacted["per_case"][0]["case_id"] == "heldout_v1_001"


def test_redact_drops_a_top_level_key_no_allowlist_names(poisoned_result: SuiteResult) -> None:
    payload = poisoned_result.to_json()
    payload["queries"] = [SENTINEL]

    assert "queries" not in redact(payload)


def test_the_allowlist_covers_exactly_what_the_suite_emits(poisoned_result: SuiteResult) -> None:
    """**The divergence detector, and the reason a fail-closed allowlist is safe to use.**

    Dropping unknown keys silently means a metric added to `suite.py` would vanish from held-out results
    with nobody told. This test is what tells them: it fails the moment `to_json` grows or loses a key,
    forcing the held-out allowlist to be updated as a decision rather than defaulted into.
    """
    payload = poisoned_result.to_json()

    assert set(payload) == HELDOUT_RESULT_KEYS
    assert set(payload["per_case"][0]) == HELDOUT_PER_CASE_KEYS
    assert set(CaseError("x", "y", "z").to_json()) > HELDOUT_ERROR_KEYS


# --- lock 3: the last-resort substring check --------------------------------------------------------


def test_assert_writable_catches_a_leak_the_allowlists_would_pass() -> None:
    """A query smuggled into an **allowlisted** field. Both allowlists pass it; this is what catches it.

    Not hypothetical in shape: `aborted_reason` is built by `suite.py` from an exception, and it is on
    the allowlist because today it only carries case ids and counts.
    """
    payload = {"aborted_reason": f"stopped while running {SENTINEL}"}
    case = EvalCase(
        case_id="heldout_v1_002", query=SENTINEL, subject_id=None, expected_refusal=False
    )

    with pytest.raises(ContentLeak, match="heldout_v1_002"):
        assert_writable(payload, [case])


def test_assert_writable_passes_a_clean_payload() -> None:
    case = EvalCase(
        case_id="heldout_v1_002", query=SENTINEL, subject_id=None, expected_refusal=False
    )

    assert_writable({"cases_run": 10, "edge_groundedness": 1.0}, [case])


def test_nothing_is_written_when_the_leak_check_fires(tmp_path: Path) -> None:
    """The check runs **before** the file is opened. A writer that wrote first and validated after would
    leave the disclosure on disk and report an error about it."""
    result = _result_with_error(CaseError("heldout_v1_004", "ValueError", ""))
    case = EvalCase(
        case_id="heldout_v1_004", query="heldout", subject_id=None, expected_refusal=False
    )

    with pytest.raises(ContentLeak):
        write_result(result, [case], revision="test", directory=tmp_path)

    assert list(tmp_path.iterdir()) == []


# --- lock 4: no transcript -------------------------------------------------------------------------


def test_the_heldout_runner_does_not_import_transcripts() -> None:
    """**A structural lock on an omission**, which is the only kind that survives.

    `live.main` writes a transcript after every run because prose is the judge's raw material. A held-out
    transcript would be the entire set in plaintext, committed. Relying on nobody pasting that line in
    is this repo's named failure mode -- an intent stated in a comment and never enforced.
    """
    source = Path(heldout_run.__file__).read_text(encoding="utf-8")

    assert "transcripts" not in source.replace("No transcript is written", "").replace(
        "no transcript was written", ""
    ).replace("No transcript was written", "")
    assert not hasattr(heldout_run, "transcripts")


# --- the shape of a run ----------------------------------------------------------------------------


def test_heldout_cases_reads_the_sealed_schema() -> None:
    """Built from `heldout_draw.py`'s output schema, which is readable without opening anything: the
    draw tool is committed and its content is generated, not authored."""
    cases = heldout_cases(
        {
            "cases": [
                {
                    "case_id": "heldout_v1_001",
                    "shape": "origins",
                    "query": SENTINEL,
                    "expected_resolution": {"name": "n", "node_id": "Q1"},
                    "expected_refusal": False,
                    "expected_path": ["Q1", "Q2"],
                    "expected_claims": [{"subject_id": "Q1", "object_id": "Q2"}],
                }
            ]
        }
    )

    assert cases[0].case_id == "heldout_v1_001"
    assert cases[0].subject_id == "Q1"
    assert cases[0].expected_path == ("Q1", "Q2")
    assert cases[0].forbidden_triples == ()


def test_a_refusal_case_carries_no_subject_when_the_draw_gave_none() -> None:
    cases = heldout_cases(
        {
            "cases": [
                {
                    "case_id": "heldout_v1_009",
                    "query": SENTINEL,
                    "expected_resolution": {"name": "", "node_id": ""},
                    "expected_refusal": True,
                    "expected_path": [],
                    "expected_claims": [],
                }
            ]
        }
    )

    assert cases[0].subject_id is None
    assert cases[0].expected_refusal is True


def test_progress_reports_the_case_id_and_never_the_query(store: InMemoryGraphStore) -> None:
    """`run_live`'s progress line prints `case.query[:60]`, which is right there and a plaintext
    disclosure here. Break the lock by copying that line across: this fails."""
    case = gold.load_cases()[0]
    lines: list[str] = []

    run_heldout(
        [
            EvalCase(
                case_id="heldout_v1_001",
                query=SENTINEL,
                subject_id=case.subject_id,
                expected_refusal=case.expected_refusal,
                expected_path=case.expected_path,
            )
        ],
        artifact_pin=store.artifact_version,
        store=store,
        provider="scripted",
        llm_factory=lambda: ScriptedLLM(gold.build_script(case)),
        progress=lines.append,
    )

    assert any("heldout_v1_001" in line for line in lines)
    assert not any(SENTINEL in line for line in lines)


def test_held_out_numbers_are_reported_and_never_gated(poisoned_result: SuiteResult) -> None:
    """No threshold set covers `heldout`, and `thresholds.render_unmatched` already says the right
    thing about that. Asserted here so a future threshold set added for this dataset is a deliberate
    act -- gold-set thresholds do not transfer, and a held-out set that gates is a set being tuned on.
    """
    outcome = gate(poisoned_result)

    assert poisoned_result.dataset == "heldout"
    assert not outcome.blocks
    assert any("not a pass" in line for line in outcome.lines)


def _result_with_error(error: CaseError) -> SuiteResult:
    """A minimal result carrying one errored case, for the message-handling tests.

    Assembled by hand rather than driven, because provoking a real `CaseError` needs a case that raises,
    and building one would mean writing the failure this is meant to contain.
    """
    from musical_mycelium.agent.llm import Usage
    from musical_mycelium.eval.metrics import (
        Groundedness,
        InjectionResistance,
        Rate,
        RefusalAccuracy,
    )

    return SuiteResult(
        dataset="heldout",
        dataset_version="heldout_v1",
        provider="bedrock",
        model_id="test",
        artifact_version="0.5.0",
        artifact_pin="0.5.0",
        results=(),
        groundedness=Groundedness(grounded=0, total=0),
        citation=Rate(numerator=0, denominator=0),
        refusal=RefusalAccuracy(0, 0, 0, 0),
        injection=InjectionResistance(induced=0, scored_cases=0, unscored_cases=0),
        verification={},
        recall=Rate(numerator=0, denominator=0),
        precision=Rate(numerator=0, denominator=0),
        usage=Usage(),
        complete=False,
        errors=(error,),
    )
