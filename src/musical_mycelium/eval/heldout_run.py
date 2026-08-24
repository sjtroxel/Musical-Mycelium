"""Step 9: the sealed set, run once, scored, and reported without ever being read.

This is the last step of phase 4 and it is last on purpose. `.claude/rules/heldout-set.md` requires a
held-out set that is "never looked at" during development, and `heldout.py` makes that a mechanism rather
than a promise by encrypting it. This module is the only place that decrypts the set in order to *run*
it, which makes it the only place that can leak it.

**The threat is not malice and it is not the author. It is the ordinary operation of a coding agent.**
An agent greps, opens files to check a schema, and reads test failures. So every path out of this module
-- the result file, stdout, an exception message, a test failure -- is treated as a publication channel,
and each one is closed separately rather than by a single guard that has to be right about all of them:

1. **`sanitise` strips the message off every `CaseError` before anything renders or writes the result.**
   `suite.CaseError.message` is `str(exception)`, and an exception raised inside synthesis can quote a
   node label, a query fragment, or a claim. It is the only content-bearing field `SuiteResult.to_json`
   produces today, and `report.render` prints it straight to stdout at `report.py:77`.
2. **`redact` rebuilds the written payload from a positive allowlist**, key by key, at both levels that
   carry per-case rows. Anything not named is dropped. This lock is almost a no-op against today's
   `to_json` and that is fine -- it is forward-looking, and exists so that the day someone adds `"query"`
   to `per_case` for debugging, the held-out writer does not quietly start publishing the set.
3. **No transcript is written.** `live.py` writes one after every run because prose is the judge's raw
   material; a held-out transcript would be the whole set in plaintext, committed. The omission is
   load-bearing, so it is locked by a test rather than left to whoever edits this next -- an omission
   that survives only while nobody adds a line is this repo's named failure mode.
4. **Progress prints case ids, never queries.** `live.py`'s progress callback prints `case.query[:60]`,
   which is right there and is a direct leak here.

**What this module still cannot promise, stated rather than smoothed.** `heldout_cases` returns
`EvalCase` objects holding the real queries, because the model has to be given them. Anything that prints
one is a disclosure. The locks above cover every path this module owns; they do not cover a debugger, a
`print` added mid-investigation, or an agent that decides to inspect the return value. Those are why the
rule is *do not open it*, and the mechanism is a second line rather than a replacement.

**If a metric comes back bad on this set and is not diagnosable from ids and codes alone, the correct
outcome is to report it undiagnosed.** That is written into the phase 4 implementation doc at step 9 and
it is the whole point: a held-out set you open to debug is a development set with extra steps.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from musical_mycelium.agent.llm import LLM, build_llm
from musical_mycelium.eval import heldout
from musical_mycelium.eval.budget import EVAL_REQUESTS_PER_MINUTE, RateLimiter
from musical_mycelium.eval.live import ThrottledLLM, budget_for, estimate_for
from musical_mycelium.eval.provenance import code_revision
from musical_mycelium.eval.report import render
from musical_mycelium.eval.safety import (
    SpendCapExceeded,
    SpendRefused,
    UnattendedSpend,
    confirm_spend,
)
from musical_mycelium.eval.suite import CaseError, EvalCase, SuiteResult, run_suite
from musical_mycelium.eval.thresholds import gate
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.store import GraphStore

RESULTS_DIR = Path(__file__).parent / "results"

#: The dataset name that lands in the result file and that `thresholds.set_for` matches on. It matches
#: **no** threshold set, deliberately: the gold baseline was measured on 41 gold-plus-adversarial cases
#: and `render_unmatched` already says the right thing -- *"thresholds measured on one dataset do not
#: transfer to another. This is not a pass."* Held-out numbers are reported, never gated.
DATASET = "heldout"

#: Top-level keys of `SuiteResult.to_json()` that may be written for the held-out set.
#:
#: Enumerated rather than filtered-by-exclusion because the two fail in opposite directions. An
#: exclusion list lets a newly added field through by default; an allowlist drops it by default. For
#: this one file, dropping a metric is a recoverable annoyance and publishing a query is not.
HELDOUT_RESULT_KEYS = frozenset(
    {
        "dataset",
        "dataset_version",
        "provider",
        "model_id",
        "artifact_version",
        "artifact_pin",
        "artifact_matches_pin",
        "complete",
        "aborted_reason",
        "errored_cases",
        "script_determined",
        "cases_run",
        "cases_correct",
        "truncated_runs",
        "edge_groundedness",
        "citation_resolution",
        "refusal_accuracy",
        "injection_resistance",
        "verification_mix",
        "traversal_recall",
        "traversal_precision",
        "usage",
        "per_case",
        "slices",
    }
)

#: Per-case keys that may be written. **This is the load-bearing allowlist.** `per_case` is the row that
#: a future debugging edit is most likely to grow a `"query"`, a `"prose"`, or an `"approved"` list on,
#: and it is the only place in `to_json` where anything is emitted per case at all.
#:
#: Every key here is a count, a boolean, a score, or the case id. **A case id is not content** -- that is
#: the same judgement `heldout.Finding` already rests on, and it is what makes a sealed set debuggable at
#: all: `heldout_v1_007: claims-diverged` says everything needed to act and discloses nothing.
HELDOUT_PER_CASE_KEYS = frozenset(
    {
        "case_id",
        "refused",
        "expected_refusal",
        "refusal_correct",
        "approved_claims",
        "rejected_claims",
        "groundedness",
        "traversal_recall",
        "traversal_precision",
        "plan_divergence",
        "truncated",
        "correct",
    }
)

#: Errored-case keys that may be written. **`message` is deliberately absent** -- it is `str(exception)`
#: and an exception from synthesis can quote a node label or a claim. `error_type` is a class name, which
#: is a code in the same sense a `Finding.code` is.
HELDOUT_ERROR_KEYS = frozenset({"case_id", "error_type"})

#: Why the errored-case message is dropped rather than left blank. Written into the file so a reader of
#: the result does not conclude the errors were unexplained.
REDACTED_NOTE = (
    "held-out run: error messages are dropped by design, not missing. See eval/heldout_run.py."
)

#: What the four slice dimensions disclose, and why running them anyway is the right call.
#:
#: Slicing publishes the held-out set's coarse *distribution*: which of four era-ish buckets, three
#: density buckets, and `anglophone_core`/`elsewhere`/`unstated` its ten subjects fall into. That is a
#: real disclosure and it is not zero.
#:
#: It is made anyway, for three reasons. The public manifest **already** publishes `shapes` and
#: `refusal_count` on exactly this argument -- aggregates prove composition without naming a subject.
#: `query_kind` is `shapes` under another name, so three quarters of the dimensions disclose nothing new.
#: And phase 4 DoD 6 requires every result sliced four ways, for the reason `.claude/rules/evals.md`
#: gives: *"an aggregate that looks healthy while the sparse and non-Western slices fail is the default
#: outcome without slicing"* -- which is precisely the question a held-out set is run to answer.
#:
#: What it does not disclose is any subject, any query, any edge, or which case sits in which bucket.
#: Knowing that one held-out case is `isolated` tunes nothing.
SLICES_ARE_A_DELIBERATE_DISCLOSURE = True


class ContentLeak(RuntimeError):
    """A held-out payload carried a key no allowlist names.

    Raised rather than filtered when the *shape* is wrong rather than the content -- see
    :func:`assert_writable`. A filter that silently dropped an unknown key would make this module's
    guarantee depend on nobody ever needing the dropped field, which is how locks rot.
    """


@dataclass(frozen=True, slots=True)
class HeldoutRun:
    """One held-out run: the result, and the redacted payload that was written from it.

    Kept together so a caller can render and write from the same object rather than re-deriving one from
    the other, and so a test can assert over exactly what reached disk.
    """

    result: SuiteResult
    payload: dict[str, Any]
    path: Path


# --- adapting the sealed set into cases -----------------------------------------------------------


def heldout_cases(data: dict[str, Any]) -> tuple[EvalCase, ...]:
    """Adapt the decrypted set into the dataset-neutral shape `suite.py` scores.

    The same job `gold.GoldCase.as_eval_case` does, and deliberately not routed through `gold.py`: that
    module builds a *scripted trace* from `expected_resolution`, and a held-out run has no script. The
    model plans it, which is the only reason running this set says anything.

    **No `forbidden_triples`.** `heldout_draw.py` plants no injections, so claiming an
    injection-resistance denominator here would be the inflation `InjectionResistance.scored_cases`
    exists to prevent. Ten unscored cases is the honest report.

    **The return value holds the real queries and must not be printed.** It is the one object in this
    module that is content.
    """
    cases = []
    for case in data.get("cases", []):
        node_id = str(case.get("expected_resolution", {}).get("node_id", "")) or None
        cases.append(
            EvalCase(
                case_id=str(case["case_id"]),
                query=str(case["query"]),
                subject_id=node_id,
                expected_refusal=bool(case.get("expected_refusal")),
                expected_path=tuple(case.get("expected_path", ())),
            )
        )
    if not cases:
        raise heldout.SealError("the sealed set decrypted but holds no cases")
    return tuple(cases)


# --- the locks ------------------------------------------------------------------------------------


def sanitise(result: SuiteResult) -> SuiteResult:
    """Strip the message off every recorded case error. Lock 1.

    Applied to the `SuiteResult` itself rather than to the JSON, so that `report.render` -- which prints
    `error.message` to stdout at `report.py:77` -- is covered by the same act that covers the file.
    Sanitising only on write would leave the terminal leaking.

    `error_type` survives. `ValueError` is a code; the string it carries is not.
    """
    if not result.errors:
        return result
    return replace(
        result,
        errors=tuple(
            CaseError(case_id=error.case_id, error_type=error.error_type, message="")
            for error in result.errors
        ),
    )


def redact(payload: dict[str, Any]) -> dict[str, Any]:
    """Rebuild the payload from the allowlists. Lock 2.

    Positive construction, not deletion: the output starts empty and only named keys are copied in. A
    key added to `SuiteResult.to_json` after today does not appear here until someone adds it to
    `HELDOUT_RESULT_KEYS` on purpose, and `tests/test_heldout_run.py` fails loudly when that happens so
    the decision is made rather than defaulted into.
    """
    out = {key: value for key, value in payload.items() if key in HELDOUT_RESULT_KEYS}

    out["per_case"] = [
        {key: value for key, value in row.items() if key in HELDOUT_PER_CASE_KEYS}
        for row in payload.get("per_case", [])
    ]
    out["errored_cases"] = [
        {key: value for key, value in row.items() if key in HELDOUT_ERROR_KEYS}
        for row in payload.get("errored_cases", [])
    ]
    if out["errored_cases"]:
        out["errors_redacted"] = REDACTED_NOTE
    return out


def assert_writable(payload: dict[str, Any], cases: Sequence[EvalCase]) -> None:
    """Last check before disk: no case's query text appears anywhere in the serialized payload. Lock 3.

    A defence-in-depth check rather than the primary one, and it is worth having precisely because it is
    *not* structural -- it does not care how a query got in, only that it did. The allowlists prevent the
    known route; this catches a route nobody thought of, including one introduced by a future edit to a
    module this one does not import.

    Substring matching over the whole serialized blob, which is crude and correct here: the queries are
    full sentences, so a false positive would need a metric name to contain one.
    """
    blob = json.dumps(payload)
    for case in cases:
        if case.query and case.query in blob:
            raise ContentLeak(
                f"{case.case_id}: the case query reached the result payload. Nothing was written. "
                "This is a defect in the held-out writer, not in the run."
            )


# --- driving --------------------------------------------------------------------------------------


def write_result(
    result: SuiteResult,
    cases: Sequence[EvalCase],
    *,
    revision: str,
    directory: Path = RESULTS_DIR,
) -> tuple[Path, dict[str, Any]]:
    """Write the redacted run to `results/<timestamp>-heldout.json`.

    Deliberately **not** `live.write_result`. That function writes `result.to_json()` straight through,
    which is right for a dataset whose cases are committed in plaintext next to it and wrong here. A
    shared writer with a `redact_if_heldout` flag would put the leak one forgotten argument away.

    `revision` is passed in for the reason `live.write_result` documents: this runs minutes after the
    code it describes was loaded, and reading git at write time answers a different question.
    """
    payload = redact(result.to_json())
    payload["written_at"] = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    payload["code_revision"] = revision
    assert_writable(payload, cases)

    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{payload['written_at']}-heldout.json"
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return path, payload


def run_heldout(
    cases: Sequence[EvalCase],
    *,
    artifact_pin: str,
    store: GraphStore | None = None,
    provider: str = "bedrock",
    requests_per_minute: int = EVAL_REQUESTS_PER_MINUTE,
    llm_factory: Callable[[], LLM] | None = None,
    limiter: RateLimiter | None = None,
    progress: Callable[[str], None] | None = None,
) -> SuiteResult:
    """Drive the held-out cases through the real model. Assumes `confirm_spend` has already passed.

    Structurally the same as `run_live` -- one shared `ThrottledLLM` so the limiter and the request count
    are properties of the run -- with one difference that matters: **the progress line is the case id and
    nothing else.** `run_live` prints `case.query[:60]`, which is the right amount of feedback for a
    committed dataset and a plaintext disclosure for this one.

    The returned result is **not** sanitised. `main` does that, once, before anything reads it, so that a
    caller who forgets cannot get an unsanitised one from a function that claims to be safe -- this one
    does not claim to be.
    """
    graph = store if store is not None else InMemoryGraphStore.from_directory(artifact_directory())
    say = progress if progress is not None else (lambda line: None)

    build = llm_factory if llm_factory is not None else (lambda: build_llm(provider))
    pacer = limiter if limiter is not None else RateLimiter(requests_per_minute=requests_per_minute)
    throttled = ThrottledLLM(inner=build(), limiter=pacer)

    budget = budget_for(estimate_for(cases, throttled.model_id, "held-out run"))
    done = 0

    def llm_for(case: EvalCase) -> LLM:
        nonlocal done
        done += 1
        say(f"[{done}/{len(cases)}] {case.case_id}")
        return throttled

    result = run_suite(
        cases,
        store=graph,
        llm_for=llm_for,
        dataset=DATASET,
        dataset_version="heldout_v1",
        artifact_pin=artifact_pin,
        provider=provider,
        budget=budget,
    )
    say(f"requests issued: {throttled.requests}; tokens: {result.usage.total_tokens}")
    return result


def preflight(key_path: Path) -> tuple[dict[str, Any], InMemoryGraphStore, list[heldout.Finding]]:
    """Everything free that must hold before a cent is spent. Returns the set, the store, and findings.

    Two checks, both of which have already earned their place:

    - **`verify_seal`** compares the ciphertext against its manifest. A set quietly regenerated after
      seeing results is not a benchmark, and this is the only check that catches it.
    - **`check_against_corpus`** validates the cases against the pinned artifact and reports ids and
      codes. Phase 6 moves the corpus; a case whose neighbours shifted stops matching silently, and
      spending the one shot on a drifted corpus wastes it.

    Findings are returned rather than raised so `main` can print them and refuse, which is what
    `.claude/rules/heldout-set.md` requires: *"If the corpus moved under it, say so and let the user
    decide."* Re-sealing to make this pass is forbidden there in as many words.
    """
    heldout.verify_seal()
    data = heldout.load_sealed(key_path)
    store = InMemoryGraphStore.from_directory(artifact_directory())
    return data, store, heldout.check_against_corpus(data, store)


def main(argv: Sequence[str] | None = None) -> int:
    """`make eval-heldout`. One confirmation, then unattended, then a report and one file.

    The order is: verify the seal, open it in memory, check it against the corpus, refuse on any finding,
    confirm the spend, run, sanitise, render, write. Nothing between opening the set and writing the file
    prints anything derived from a case except its id.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    key_path = Path(args[args.index("--key") + 1]) if "--key" in args else heldout.DEFAULT_KEY_PATH

    try:
        data, store, findings = preflight(key_path)
    except heldout.SealError as failure:
        print(f"not started: {failure}", file=sys.stderr)
        return 2

    if findings:
        print(f"not started: {len(findings)} problem(s) against artifact {store.artifact_version}:")
        for finding in findings:
            print(f"  {finding}")
        print(
            "\nIds and codes only, by design. The set no longer agrees with the pinned corpus, so a "
            "run against it would spend the one shot on a benchmark that has already moved. Do not "
            "re-seal to make this pass.",
            file=sys.stderr,
        )
        return 2

    cases = heldout_cases(data)
    pin = str(data.get("artifact_version_pin", ""))
    model_id = build_llm("bedrock").model_id
    revision = code_revision()

    try:
        confirm_spend(
            estimate_for(cases, model_id, f"{len(cases)} cases, HELD-OUT SET, run once, real model")
        )
    except UnattendedSpend as refusal:
        print(f"\nnot started: {refusal}", file=sys.stderr)
        return 2
    except SpendRefused:
        print("\nnot confirmed; nothing was spent.", file=sys.stderr)
        return 2
    except SpendCapExceeded as capped:
        print(f"\nrefused by the hard cap: {capped}", file=sys.stderr)
        return 2

    print("\nconfirmed; running. This is unattended from here.\n", flush=True)
    raw = run_heldout(
        cases,
        artifact_pin=pin,
        store=store,
        progress=lambda line: print(line, flush=True),
    )

    # Sanitised BEFORE anything reads it, and reassigned rather than shadowed, so there is no live
    # reference to the unsanitised result below this line.
    result = sanitise(raw)
    path, _ = write_result(result, cases, revision=revision)
    outcome = gate(result)

    print()
    print(render(result, outcome))
    print(f"\nwritten to {path}")
    print(
        "\nHeld-out numbers are reported, never gated: no threshold set covers this dataset and "
        "thresholds measured on the gold set do not transfer to it. No transcript was written."
    )
    if result.errors:
        print(
            f"\n{len(result.errors)} case(s) failed. Error messages are dropped by design. If the "
            "failure is not diagnosable from ids and types alone, report it undiagnosed -- opening "
            "the set to debug it is what this whole mechanism exists to prevent."
        )
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
