"""What a run actually said, kept so it can be judged later. Phase 4 step 7a.

A `SuiteResult` records how a run **scored**; it does not record what the run **wrote**. That was fine
through step 6, whose every metric is a count. It stops being fine at step 7: citation support and
narrative quality are properties of prose, and `runner.CaseRun.prose` was being dropped by `score_case`
the moment the numbers were read off it. Nine committed result files therefore contain no narrative at
all, which is why the judge's labeling pool has to be produced rather than assembled from what exists.

**A transcript is a separate file from a result, on purpose.** Three reasons, in order of how much they
would cost to get wrong:

1. **The held-out set must never have one.** `write` refuses any dataset whose name looks held out, and
   `.claude/rules/heldout-set.md` is why: a result file carries aggregate metrics and case ids, and case
   ids are not content — prose is. A transcript of a held-out run would put the one dataset nobody may
   read into a plaintext file in the repo. The refusal is structural rather than procedural because the
   procedural version is "remember not to pass that dataset".
2. **Result files are the benchmark history** that phase 7 plots and `noise.py` pools. Growing them by
   the full text of 41 answers makes every one of those readers carry a payload none of them wants.
3. **Prose is the only artifact here a model wrote freely.** Keeping it in its own file makes "this is
   model output, not a measurement" a fact about the filesystem rather than a caveat in a docstring.

**Labels, not ids, in the claim rows.** A human reads this file — that is its entire purpose — and
`Q1041424 -influenced_by-> Q11660` is not something a person can judge. Ids are kept alongside so the
rows stay checkable against the artifact; what changes is which one a reader's eye lands on first.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from musical_mycelium.eval.suite import SuiteResult
from musical_mycelium.graph.store import GraphStore

TRANSCRIPTS_DIR = Path(__file__).parent / "transcripts"

#: Any dataset name containing one of these cannot be transcribed. A substring test rather than an
#: equality test, because the name that arrives will be `heldout_v1` or `held-out` or `live+heldout`
#: long before it is exactly `heldout`, and the failure mode of guessing wrong is unrecoverable.
SEALED_DATASET_MARKERS = ("heldout", "held-out", "held_out", "sealed")


class SealedDatasetRefused(RuntimeError):
    """A transcript was requested for a dataset that must never be written in plaintext.

    Raised, never warned. `.claude/rules/heldout-set.md`: *"no held-out case content may enter a result
    file, a log line, a test failure message, or an agent's context."* A transcript is all four at once,
    and there is no recovery after the fact — an unsealed set cannot be re-sealed into ignorance.
    """


@dataclass(frozen=True, slots=True)
class ClaimRow:
    """One approved claim, in the shape a person can read.

    `verification` travels with every row because it is the field most likely to be misread when it is
    absent: a reader who sees a cited claim and no tier will assume the citation was checked by a human,
    and for most of this corpus it was not.
    """

    subject: str
    predicate: str
    object: str
    subject_id: str
    object_id: str
    source_ids: tuple[str, ...]
    verification: str

    def to_json(self) -> dict[str, Any]:
        return {
            "subject": self.subject,
            "predicate": self.predicate,
            "object": self.object,
            "subject_id": self.subject_id,
            "object_id": self.object_id,
            "source_ids": list(self.source_ids),
            "verification": self.verification,
        }


@dataclass(frozen=True, slots=True)
class CaseTranscript:
    """One case: what was asked, what was approved, and what was written.

    A refused case keeps its row rather than being dropped. Refusal is correct behaviour here, and a
    pool built only from cases that answered would be a pool that cannot contain the project's most
    interesting output — the answer that is grounded, cited, and about the wrong genre.
    """

    case_id: str
    query: str
    refused: bool
    refusal_reason: str
    prose: str
    claims: tuple[ClaimRow, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "query": self.query,
            "refused": self.refused,
            "refusal_reason": self.refusal_reason,
            "prose": self.prose,
            "claims": [claim.to_json() for claim in self.claims],
        }


@dataclass(frozen=True, slots=True)
class RunTranscript:
    """Every case of one run, with just enough provenance to tie it back to its result file."""

    dataset: str
    provider: str
    model_id: str
    artifact_version: str
    code_revision: str
    written_at: str
    cases: tuple[CaseTranscript, ...]

    def to_json(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "provider": self.provider,
            "model_id": self.model_id,
            "artifact_version": self.artifact_version,
            "code_revision": self.code_revision,
            "written_at": self.written_at,
            "cases": [case.to_json() for case in self.cases],
        }

    @property
    def answered(self) -> tuple[CaseTranscript, ...]:
        """Cases that produced prose. The pool builder's population, and not the same as
        `not refused` — a case can end without refusing and still write nothing."""
        return tuple(case for case in self.cases if case.prose.strip())


def guard_dataset(dataset: str) -> None:
    """Raise if this dataset must not be transcribed. Called before anything is built, not before it is
    written, so no held-out prose is ever materialised in memory on the way to a refusal."""
    lowered = dataset.lower()
    for marker in SEALED_DATASET_MARKERS:
        if marker in lowered:
            raise SealedDatasetRefused(
                f"dataset {dataset!r} is sealed; its prose must never be written to disk. "
                "See .claude/rules/heldout-set.md -- a case id is not content, prose is."
            )


def build(result: SuiteResult, store: GraphStore, *, revision: str) -> RunTranscript:
    """Collect one scored run into a transcript. Pure apart from the artifact lookups the labels need."""
    guard_dataset(result.dataset)

    def label(node_id: str) -> str:
        node = store.get_node(node_id)
        # An unresolvable id is shown as the id. It should not happen -- the gate only approves claims
        # whose endpoints exist -- and if it ever does, a reader seeing a bare QID in a labelled column
        # is the correct amount of alarming.
        return node.label if node is not None else node_id

    cases = tuple(
        CaseTranscript(
            case_id=case.case.case_id,
            query=case.case.query,
            refused=case.run.refused,
            refusal_reason=case.run.refusal_reason,
            prose=case.run.prose,
            claims=tuple(
                ClaimRow(
                    subject=label(claim.subject_id),
                    predicate=claim.predicate,
                    object=label(claim.object_id),
                    subject_id=claim.subject_id,
                    object_id=claim.object_id,
                    source_ids=claim.source_ids,
                    verification=claim.verification,
                )
                for claim in case.run.approved
            ),
        )
        for case in result.results
    )
    return RunTranscript(
        dataset=result.dataset,
        provider=result.provider,
        model_id=result.model_id,
        artifact_version=result.artifact_version,
        code_revision=revision,
        written_at=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        cases=cases,
    )


def write(
    transcript: RunTranscript,
    *,
    directory: Path = TRANSCRIPTS_DIR,
    stamp: str | None = None,
) -> Path:
    """Write one transcript to `transcripts/<stamp>-<provider>.json`. Never overwritten, same as results.

    The dataset guard runs again here rather than trusting that `build` ran it. `RunTranscript` can be
    constructed directly -- the tests do it -- so the check belongs at every door into the filesystem,
    not only at the one the intended path uses.
    """
    guard_dataset(transcript.dataset)
    directory.mkdir(parents=True, exist_ok=True)
    written_at = stamp or transcript.written_at
    path = directory / f"{written_at}-{transcript.provider}.json"
    path.write_text(json.dumps(transcript.to_json(), indent=2) + "\n", encoding="utf-8")
    return path


def load(path: Path) -> RunTranscript:
    """Read a transcript back. Used by the pool builder and by nothing else in the runtime path."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    guard_dataset(str(payload.get("dataset", "")))
    return RunTranscript(
        dataset=payload["dataset"],
        provider=payload["provider"],
        model_id=payload["model_id"],
        artifact_version=payload["artifact_version"],
        code_revision=payload["code_revision"],
        written_at=payload["written_at"],
        cases=tuple(
            CaseTranscript(
                case_id=case["case_id"],
                query=case["query"],
                refused=case["refused"],
                refusal_reason=case["refusal_reason"],
                prose=case["prose"],
                claims=tuple(
                    ClaimRow(
                        subject=claim["subject"],
                        predicate=claim["predicate"],
                        object=claim["object"],
                        subject_id=claim["subject_id"],
                        object_id=claim["object_id"],
                        source_ids=tuple(claim["source_ids"]),
                        verification=claim["verification"],
                    )
                    for claim in case["claims"]
                ),
            )
            for case in payload["cases"]
        ),
    )


def newest(directory: Path = TRANSCRIPTS_DIR) -> Path | None:
    """The most recently written transcript, by filename. Filenames are UTC stamps, so lexical order is
    chronological order -- the same assumption `noise.py` makes about result files."""
    if not directory.exists():
        return None
    candidates: Sequence[Path] = sorted(directory.glob("*.json"))
    return candidates[-1] if candidates else None
