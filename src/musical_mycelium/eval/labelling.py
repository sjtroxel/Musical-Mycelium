"""The labeling pool, the labels, and the one-item-at-a-time terminal flow. Phase 4 step 7a.

`.claude/rules/evals.md`: *"Hand-label 30 items, report judge-human agreement permanently next to every
judged metric. An LLM-judge score with no measured agreement is decoration."* This module owns the human
half of that — the pool the labels are drawn over, the label file, and the commands that present one
item at a time.

## Blind means before, and this module is what enforces the ordering

Labels are collected **before the judge is ever run on the pool**. Not because a person would peek, but
because a label file that can hold a judge score is a label file that eventually does, and no agreement
figure computed afterwards can be shown to be uncontaminated. So:

- the label record has a fixed field allowlist and `load_labels` raises on anything outside it,
- `judge.py` refuses to run until every pool item is labeled,
- and the labels are bound to the pool by a digest, so a pool rebuilt under a finished label set is a
  loud failure rather than a quiet re-pairing of answers to the wrong items.

## The cadence is a requirement, not a preference

Thirty items is the largest piece of his time this phase asks for, and the shape that worked for all 25
gold cases on 2026-08-14 is the shape reused here: **one item at a time, one judgement each, from a
pre-filled draft, never typing JSON.** Consequences that are visible in this module's design:

- `record` writes immediately. A sitting that ends at item 7 has seven labels on disk, not zero.
- `status` says where it is, in the terminal, in one line, so a session that starts cold does not have
  to reconstruct progress from a diff.
- the label file is **append-only** and last-write-wins. A correction is a second record, not an edit,
  which keeps a mislabel visible instead of erasing it.
- ten is a sitting, not a target. Nothing here counts sittings or complains about a short one.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from musical_mycelium.eval import transcripts
from musical_mycelium.eval.suite import PROVIDER_SCRIPTED
from musical_mycelium.eval.transcripts import ClaimRow, RunTranscript

DATASETS_DIR = Path(__file__).parent / "datasets"
POOL_PATH = DATASETS_DIR / "judge_pool_v1.json"
LABELS_PATH = DATASETS_DIR / "judge_labels_v1.json"

#: Where the rubrics live. Declared here rather than in `judge.py` because the *labels* are the thing
#: bound to a rubric version, and `judge.py` already imports this module -- the other direction would
#: be a cycle.
RUBRICS_DIR = Path(__file__).parent / "rubrics"

#: Both rubrics, in the order they are hashed and the order they are handed to the judge. The order is
#: load-bearing for the digest: a different order is a different hash for identical instructions.
RUBRIC_NAMES = ("citation_support", "narrative_quality")

POOL_NAME = "judge_pool_v1"

#: 30, from `07` §6 and `.claude/rules/evals.md`. Not a round number chosen for feel: it is the n that
#: gets quoted next to the agreement figure forever, and a smaller one makes kappa a rumour.
TARGET_POOL_SIZE = 30

#: The citation-support levels, worst last. Ordinal, so the order is load-bearing for weighted
#: agreement. Three levels and no fourth -- an "unclear" option costs nothing to choose and would
#: become the modal answer, which is the same escape-hatch failure the gold set's `citation_status`
#: was written to avoid.
SUPPORT_LEVELS = ("SUPPORTED", "OVERSTATED", "UNSUPPORTED")

#: Narrative quality, 1-5, whole numbers. Half points are not offered for the same reason.
QUALITY_LEVELS = (1, 2, 3, 4, 5)

#: Exactly what a label record may contain. Anything else is refused on read and on write.
#:
#: **This is the blindness lock.** A judge score, a model id, or a rationale appearing in this file
#: would mean a human label written next to a machine's answer, and there is no way to detect that after
#: the fact -- so the file is defined by what it may hold rather than by what it must not.
LABEL_FIELDS = frozenset({"item_id", "citation_support", "narrative_quality", "note", "labeled_at"})


class PoolError(RuntimeError):
    """The pool cannot be built or read as a pool."""


class PoolChanged(RuntimeError):
    """The labels on disk were written against a different pool than the one now present.

    Raised rather than reconciled. Labels are bound to items by position in a sampled set; a rebuilt
    pool re-pairs every label with whatever item now holds that id, and the result looks completely
    normal. The same reasoning as the held-out manifest: a set rewritten after the fact must be
    detectable.
    """


class ForbiddenLabelField(RuntimeError):
    """A label record carried a field outside the allowlist. See `LABEL_FIELDS`."""


class RubricChanged(RuntimeError):
    """The labels were written against different rubric text than the one now on disk.

    Raised rather than reconciled, for the same reason as `PoolChanged` and one more. Agreement is a
    number about **two raters given the same instructions**. If a rubric is rewritten and only the
    judge re-reads it, the human labels were made under the old wording and the machine's under the
    new one, and the resulting kappa silently measures raters who were asked different questions.

    This is not hypothetical: `docs/phases/phase-4-eval-suite-IMPLEMENTATION.md` step 7 budgets **two**
    rubric rewrites for the case where agreement comes back poor. Nothing recorded which rubric a label
    was written under until 2026-08-20, so that budgeted path had no way to notice.
    """


@dataclass(frozen=True, slots=True)
class PoolItem:
    """One thing to be judged: an answer, its claims, and the one claim citation support is scored on.

    `focus_claim` names a single claim rather than asking for a verdict over all of them, because a
    per-answer aggregate of per-claim support is not a judgement a human can give reliably and is not
    the unit `07` §4.4 samples. Every claim is still printed -- the focus claim cannot be judged without
    the others as context, since "overstated" often means "asserts a link the other rows do not carry".
    """

    item_id: str
    case_id: str
    #: Which transcript this answer came from. Two runs of the same case are two different answers and
    #: both are legitimate items; this is what tells them apart.
    source: str
    query: str
    prose: str
    claims: tuple[ClaimRow, ...]
    focus_claim: int

    @property
    def focus(self) -> ClaimRow:
        return self.claims[self.focus_claim]

    def to_json(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "case_id": self.case_id,
            "source": self.source,
            "query": self.query,
            "prose": self.prose,
            "claims": [claim.to_json() for claim in self.claims],
            "focus_claim": self.focus_claim,
        }


@dataclass(frozen=True, slots=True)
class Pool:
    """The sampled set, plus everything needed to rebuild it identically."""

    name: str
    built_at: str
    seed: int
    target: int
    sources: tuple[dict[str, str], ...]
    items: tuple[PoolItem, ...]

    @property
    def short(self) -> bool:
        """Whether the pool came in under its target. Recorded rather than hidden: an agreement figure
        at n=22 is a different claim from one at n=30 and must not be quoted as the same."""
        return len(self.items) < self.target

    def item(self, item_id: str) -> PoolItem | None:
        for candidate in self.items:
            if candidate.item_id == item_id:
                return candidate
        return None

    def to_json(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "built_at": self.built_at,
            "seed": self.seed,
            "target": self.target,
            "size": len(self.items),
            "short": self.short,
            "sources": [dict(source) for source in self.sources],
            "items": [item.to_json() for item in self.items],
        }


@dataclass(frozen=True, slots=True)
class Label:
    """One human judgement. Two scores, an optional note, and when it was made."""

    item_id: str
    citation_support: str
    narrative_quality: int
    note: str
    labeled_at: str

    def to_json(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "citation_support": self.citation_support,
            "narrative_quality": self.narrative_quality,
            "note": self.note,
            "labeled_at": self.labeled_at,
        }


@dataclass(frozen=True, slots=True)
class Labels:
    """Every label record written so far, in the order they were written.

    **Append-only, last-write-wins.** `by_item` collapses the history; `records` keeps it. A correction
    is a new record rather than an edit so that a mislabel and its fix are both visible -- which matters
    because a label set is evidence about a human, and evidence that can be silently rewritten is not.
    """

    pool: str
    pool_sha256: str
    records: tuple[Label, ...]
    #: SHA-256 over both rubric files. What binds a label set to the *instructions* it was written
    #: under, as `pool_sha256` binds it to the items. Empty only for a label file written before
    #: 2026-08-20, which is a state that exists exactly once and is backfilled on the next write.
    rubric_sha256: str = ""

    @property
    def by_item(self) -> dict[str, Label]:
        collapsed: dict[str, Label] = {}
        for record in self.records:
            collapsed[record.item_id] = record
        return collapsed

    def to_json(self) -> dict[str, Any]:
        return {
            "pool": self.pool,
            "pool_sha256": self.pool_sha256,
            "rubric_sha256": self.rubric_sha256,
            "labels": [record.to_json() for record in self.records],
        }


def digest(path: Path) -> str:
    """SHA-256 of the pool file's bytes. What binds a label set to the exact items it was written for."""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rubric_digest(*, directory: Path | None = None, names: Sequence[str] = RUBRIC_NAMES) -> str:
    """SHA-256 over every rubric's bytes, in `RUBRIC_NAMES` order.

    One digest for both files rather than one each: a judgement is made against the pair, and a label
    set written under one pair cannot be partially valid under another. The name is hashed alongside
    the bytes so that swapping two rubrics' contents is a different digest, not the same one.

    `directory` defaults to `None` and resolves to the module global at **call** time rather than
    binding it in the signature, so a test can redirect it. A default argument would capture the path
    once at import and quietly ignore every override.
    """
    root = directory if directory is not None else RUBRICS_DIR
    running = hashlib.sha256()
    for name in names:
        path = root / f"{name}.md"
        if not path.exists():
            raise FileNotFoundError(f"no rubric at {path}")
        running.update(name.encode("utf-8"))
        running.update(b"\0")
        running.update(path.read_bytes())
    return running.hexdigest()


def eligible_items(transcript: RunTranscript) -> list[tuple[str, transcripts.CaseTranscript]]:
    """Cases that can be judged at all: prose to read, and at least one claim to score support against.

    A refused case has neither and is excluded -- not because refusal is uninteresting (it is the most
    interesting behaviour this project measures) but because it is measured deterministically, as a
    pair, on every run. Asking a judge to re-score it would add noise to a number that already has none.
    """
    return [(transcript.written_at, case) for case in transcript.answered if case.claims]


def build_pool(
    runs: Sequence[RunTranscript],
    *,
    size: int = TARGET_POOL_SIZE,
    seed: int = 20260819,
    allow_short: bool = False,
    allow_scripted: bool = False,
) -> Pool:
    """Sample `size` items across one or more transcripts, deterministically.

    **Distinct cases first, then second answers to cases already used.** One live run answers about 25
    of its 41 cases -- the other 16 are refusal cases and refuse correctly -- so a single run cannot
    fill a 30-item pool at all, and a naive sample across two runs would happily take the same case
    twice while leaving another unseen. The greedy rounds below take every case once before taking any
    case twice, which maximises how much of the corpus the agreement figure is measured over.

    `seed` is recorded in the file. The sample is reproducible from the same transcripts, which is what
    makes "the pool was not reshuffled until it looked better" a checkable statement rather than a
    promise.

    **A scripted transcript is refused.** `ScriptedLLM`'s synthesis is the fixed string `A grounded
    answer.`, so a pool built from one would have a human and a model scoring narrative quality on a
    stub -- and the agreement figure would be real, reproducible, and about nothing. `allow_scripted`
    exists for the tests, which need a pool with no AWS and know what they are looking at.
    """
    scripted = sorted({run.written_at for run in runs if run.provider == PROVIDER_SCRIPTED})
    if scripted and not allow_scripted:
        raise PoolError(
            f"transcript(s) {scripted} were produced by the scripted provider. Scripted prose is a "
            "fixed stub, so judging it measures the fixture rather than the agent. Judge a live run."
        )

    pooled: list[tuple[str, transcripts.CaseTranscript]] = []
    for run in runs:
        pooled.extend(eligible_items(run))
    if not pooled:
        raise PoolError(
            "no eligible items: every case either refused or produced no claims. "
            "A pool needs answers with claims, and this run has none."
        )

    rng = random.Random(seed)
    # Sorted before shuffling so the shuffle is a function of the seed alone, not of dict or filesystem
    # ordering. Two machines building the same pool from the same transcripts must agree.
    pooled.sort(key=lambda pair: (pair[1].case_id, pair[0]))
    rng.shuffle(pooled)

    chosen: list[tuple[str, transcripts.CaseTranscript]] = []
    used: dict[str, int] = {}
    round_number = 0
    while len(chosen) < size and round_number <= len(runs):
        for source, case in pooled:
            if len(chosen) >= size:
                break
            if used.get(case.case_id, 0) != round_number:
                continue
            if any(source == s and case.case_id == c.case_id for s, c in chosen):
                continue
            chosen.append((source, case))
            used[case.case_id] = round_number + 1
        round_number += 1

    if len(chosen) < size and not allow_short:
        raise PoolError(
            f"only {len(chosen)} eligible items across {len(runs)} run(s); the target is {size}. "
            "One live run answers roughly 25 of its 41 cases, so a 30-item pool needs two runs. "
            "Pass allow_short to build a smaller pool deliberately -- it is a smaller n, permanently, "
            "next to every judged number."
        )

    items = tuple(
        PoolItem(
            item_id=f"{POOL_NAME}_{index:03d}",
            case_id=case.case_id,
            source=source,
            query=case.query,
            prose=case.prose,
            claims=case.claims,
            focus_claim=rng.randrange(len(case.claims)),
        )
        for index, (source, case) in enumerate(chosen, start=1)
    )
    return Pool(
        name=POOL_NAME,
        built_at=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
        seed=seed,
        target=size,
        sources=tuple(
            {
                "written_at": run.written_at,
                "dataset": run.dataset,
                "provider": run.provider,
                "model_id": run.model_id,
                "code_revision": run.code_revision,
            }
            for run in runs
        ),
        items=items,
    )


def write_pool(pool: Pool, path: Path = POOL_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(pool.to_json(), indent=2) + "\n", encoding="utf-8")
    return path


def load_pool(path: Path = POOL_PATH) -> Pool:
    if not path.exists():
        raise PoolError(f"{path} does not exist; build it from a transcript first")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return Pool(
        name=payload["name"],
        built_at=payload["built_at"],
        seed=int(payload["seed"]),
        target=int(payload["target"]),
        sources=tuple(payload.get("sources", ())),
        items=tuple(
            PoolItem(
                item_id=item["item_id"],
                case_id=item["case_id"],
                source=item["source"],
                query=item["query"],
                prose=item["prose"],
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
                    for claim in item["claims"]
                ),
                focus_claim=int(item["focus_claim"]),
            )
            for item in payload["items"]
        ),
    )


def load_labels(
    path: Path = LABELS_PATH, *, pool_path: Path = POOL_PATH, pool: Pool | None = None
) -> Labels:
    """Read the labels, checking the pool digest and the field allowlist. Empty when the file is absent.

    An absent label file is an ordinary state -- it is where 7b starts -- so it returns an empty set
    bound to the current pool rather than raising.
    """
    resolved = pool if pool is not None else load_pool(pool_path)
    current = digest(pool_path)
    current_rubric = rubric_digest()
    if not path.exists():
        return Labels(
            pool=resolved.name, pool_sha256=current, records=(), rubric_sha256=current_rubric
        )

    payload = json.loads(path.read_text(encoding="utf-8"))
    recorded_rubric = str(payload.get("rubric_sha256", ""))
    if recorded_rubric and recorded_rubric != current_rubric:
        raise RubricChanged(
            f"{path} was written against rubric digest {recorded_rubric[:12]} and the rubrics on disk "
            f"hash to {current_rubric[:12]}. Agreement compares two raters given the same "
            "instructions; re-judging under rewritten rubrics against labels made under the old ones "
            "produces a number that looks normal and means nothing. Restore the rubrics or re-label."
        )
    recorded = str(payload.get("pool_sha256", ""))
    if recorded != current:
        raise PoolChanged(
            f"{path} was written against pool digest {recorded[:12] or '(none)'} and the pool on disk "
            f"is {current[:12]}. Labels are bound to items by id; re-pairing them against a rebuilt "
            "pool would look completely normal and mean nothing. Restore the pool or re-label."
        )

    records: list[Label] = []
    for raw in payload.get("labels", ()):
        extra = set(raw) - LABEL_FIELDS
        if extra:
            raise ForbiddenLabelField(
                f"{path} label {raw.get('item_id', '?')} carries {sorted(extra)}, which is outside the "
                f"allowlist {sorted(LABEL_FIELDS)}. A human label sitting next to a machine's answer is "
                "not an independent label and cannot be shown to be one afterwards."
            )
        records.append(
            Label(
                item_id=raw["item_id"],
                citation_support=raw["citation_support"],
                narrative_quality=int(raw["narrative_quality"]),
                note=raw.get("note", ""),
                labeled_at=raw["labeled_at"],
            )
        )
    return Labels(
        pool=payload.get("pool", resolved.name),
        pool_sha256=current,
        records=tuple(records),
        #: A legacy file with no recorded digest adopts the current one. That is honest only because
        #: the mismatch branch above has already run: an absent digest cannot disagree with anything,
        #: and the very next write pins it.
        rubric_sha256=recorded_rubric or current_rubric,
    )


def record_label(
    item_id: str,
    *,
    citation_support: str,
    narrative_quality: int,
    note: str = "",
    path: Path = LABELS_PATH,
    pool_path: Path = POOL_PATH,
    replace: bool = False,
) -> Label:
    """Append one label and write the file immediately.

    Written on every call rather than at the end of a sitting: this is the thing that makes stopping at
    item 7 cost nothing, and it is the whole reason 7b can be spread over three evenings.
    """
    pool = load_pool(pool_path)
    if pool.item(item_id) is None:
        raise PoolError(f"{item_id!r} is not in {pool.name}")
    if citation_support not in SUPPORT_LEVELS:
        raise ValueError(
            f"citation_support {citation_support!r} is not one of {list(SUPPORT_LEVELS)}"
        )
    if narrative_quality not in QUALITY_LEVELS:
        raise ValueError(
            f"narrative_quality {narrative_quality!r} is not one of {list(QUALITY_LEVELS)}"
        )

    labels = load_labels(path, pool_path=pool_path, pool=pool)
    if item_id in labels.by_item and not replace:
        existing = labels.by_item[item_id]
        raise PoolError(
            f"{item_id} is already labeled {existing.citation_support}/{existing.narrative_quality}. "
            "Pass replace to record a correction; the original stays in the file."
        )

    label = Label(
        item_id=item_id,
        citation_support=citation_support,
        narrative_quality=narrative_quality,
        note=note,
        labeled_at=datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ"),
    )
    updated = Labels(
        pool=labels.pool,
        pool_sha256=labels.pool_sha256,
        records=(*labels.records, label),
        rubric_sha256=labels.rubric_sha256,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(updated.to_json(), indent=2) + "\n", encoding="utf-8")
    return label


def next_unlabeled(pool: Pool, labels: Labels) -> PoolItem | None:
    """The first item with no label, in pool order. `None` when the set is finished."""
    done = labels.by_item
    for item in pool.items:
        if item.item_id not in done:
            return item
    return None


def progress_line(pool: Pool, labels: Labels) -> str:
    """One line saying where this is. Printed by `status`, and by `record` after every write, so a
    sitting always ends with its own position on screen rather than in someone's memory."""
    done = len(labels.by_item)
    remaining = next_unlabeled(pool, labels)
    where = f"next is {remaining.item_id}" if remaining is not None else "COMPLETE"
    short = "  (POOL IS SHORT OF ITS TARGET)" if pool.short else ""
    return f"{done} of {len(pool.items)} labeled, {where}{short}"


#: Every source id in this corpus is a Wikidata statement URI and every one of them starts with this.
#: Stripped for display only -- the full id stays in the pool file, which is what a checker reads.
_STATEMENT_PREFIX = "http://www.wikidata.org/entity/statement/"


def claim_lines(item: PoolItem) -> list[str]:
    """The claim rows, marked. **Shared by the terminal view and the judge prompt**, so the human and
    the model are looking at the same rendering of the same claims rather than at two that happen to
    agree today. A difference between them would show up as judge-human disagreement and be
    indistinguishable from one."""
    return [
        f"{'>>' if position == item.focus_claim else '  '} "
        f"{claim.subject} -{claim.predicate}-> {claim.object}"
        f"   [{claim.verification}]  "
        f"{', '.join(source.replace(_STATEMENT_PREFIX, '') for source in claim.source_ids)}"
        for position, claim in enumerate(item.claims)
    ]


def render_item(item: PoolItem, *, index: int, total: int) -> str:
    """One item, formatted for reading in a terminal. Everything needed to judge it and nothing else.

    The focus claim is marked rather than isolated: citation support is a question about one claim, and
    the commonest way to get it wrong is to score a sentence as overstated when a *different* claim row
    supports the extra fact.
    """
    lines = [
        f"{item.item_id}  ({index} of {total})",
        f"  case      {item.case_id}   from run {item.source}",
        f"  question  {item.query}",
        "",
        "  ANSWER",
    ]
    lines.extend(f"    {line}" for line in _wrap(item.prose))
    lines.append("")
    lines.append("  APPROVED CLAIMS")
    lines.extend(f"  {line}" for line in claim_lines(item))
    lines.append("")
    lines.append(
        f"  >> marks the claim citation_support is scored on ({item.focus.subject} "
        f"-> {item.focus.object})."
    )
    lines.append("")
    lines.append(f"  citation_support:  {' | '.join(SUPPORT_LEVELS)}")
    lines.append("  narrative_quality: 1 | 2 | 3 | 4 | 5")
    return "\n".join(lines)


def _wrap(text: str, width: int = 92) -> list[str]:
    """Wrap prose for a terminal without importing textwrap's whole configuration surface. Paragraph
    breaks are preserved because they are part of how the answer reads, and readability is scored."""
    out: list[str] = []
    for paragraph in text.split("\n"):
        if not paragraph.strip():
            out.append("")
            continue
        line = ""
        for word in paragraph.split():
            if line and len(line) + 1 + len(word) > width:
                out.append(line)
                line = word
            else:
                line = f"{line} {word}".strip()
        if line:
            out.append(line)
    return out


def _transcript_runs(paths: Iterable[Path]) -> list[RunTranscript]:
    return [transcripts.load(path) for path in paths]


def main(argv: Sequence[str] | None = None) -> int:
    """`make eval-label`. Four commands, all free, none of them touching a model.

    make eval-label ARGS='status'
    make eval-label ARGS='next'
    make eval-label ARGS='record judge_pool_v1_007 SUPPORTED 4 --note "..."'
    make eval-label ARGS='build --transcript A.json --transcript B.json'
    """
    parser = argparse.ArgumentParser(prog="eval-label", description="Hand-label the judge pool")
    sub = parser.add_subparsers(dest="command", required=True)

    build = sub.add_parser("build", help="sample a pool from one or more transcripts")
    build.add_argument("--transcript", action="append", type=Path, default=None)
    build.add_argument("--size", type=int, default=TARGET_POOL_SIZE)
    build.add_argument("--seed", type=int, default=20260819)
    build.add_argument("--allow-short", action="store_true")
    build.add_argument("--allow-scripted", action="store_true")
    build.add_argument("--out", type=Path, default=POOL_PATH)

    sub.add_parser("status", help="how many are labeled and which is next")
    sub.add_parser("next", help="show the next unlabeled item")

    show = sub.add_parser("show", help="show one item by id")
    show.add_argument("item_id")

    record = sub.add_parser("record", help="record one judgement")
    record.add_argument("item_id")
    record.add_argument("citation_support", choices=SUPPORT_LEVELS)
    record.add_argument("narrative_quality", type=int, choices=QUALITY_LEVELS)
    record.add_argument("--note", default="")
    record.add_argument("--replace", action="store_true")

    args = parser.parse_args(list(sys.argv[1:] if argv is None else argv))

    if args.command == "build":
        paths = args.transcript or ([transcripts.newest()] if transcripts.newest() else [])
        if not paths:
            print("no transcripts found; run make eval-live first", file=sys.stderr)
            return 2
        pool = build_pool(
            _transcript_runs(paths),
            size=args.size,
            seed=args.seed,
            allow_short=args.allow_short,
            allow_scripted=args.allow_scripted,
        )
        written = write_pool(pool, args.out)
        print(f"{len(pool.items)} items written to {written} (seed {pool.seed})")
        if pool.short:
            print("POOL IS SHORT OF ITS TARGET -- n travels with every judged number from here.")
        return 0

    pool = load_pool()
    labels = load_labels(pool=pool)

    if args.command == "status":
        print(progress_line(pool, labels))
        return 0

    if args.command == "next":
        item = next_unlabeled(pool, labels)
        if item is None:
            print(progress_line(pool, labels))
            return 0
        print(render_item(item, index=len(labels.by_item) + 1, total=len(pool.items)))
        print()
        print(progress_line(pool, labels))
        return 0

    if args.command == "show":
        item = pool.item(args.item_id)
        if item is None:
            print(f"{args.item_id} is not in {pool.name}", file=sys.stderr)
            return 2
        position = pool.items.index(item) + 1
        print(render_item(item, index=position, total=len(pool.items)))
        return 0

    label = record_label(
        args.item_id,
        citation_support=args.citation_support,
        narrative_quality=args.narrative_quality,
        note=args.note,
        replace=args.replace,
    )
    print(f"recorded {label.item_id}: {label.citation_support}, quality {label.narrative_quality}")
    print(progress_line(pool, load_labels(pool=pool)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
