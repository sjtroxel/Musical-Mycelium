"""Artifact versions are ordered as NUMBERS, never as text, and the pin is the newest cut.

Added 2026-09-11, phase 7.6 step 0, before the pin moves from v0.7.1 to v0.10.0. The jump is deliberate
(``docs/ROADMAP.md`` §2, under the version table: v0.8 and v0.9 collide with product versions, v0.7.2
would understate a new predicate). It creates one trap, and this file exists for it: **as text,
"0.10.0" sorts before "0.7.1"**, so any code that picks "the latest artifact" by sorting strings would
silently load the old corpus.

On 2026-09-11 nothing in the repo sorted versions at all: every reader matches one exact pinned string.
These tests keep the ordering question answered correctly for the day something does.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from musical_mycelium.graph.memory import PINNED_ARTIFACT_VERSION, artifact_directory
from musical_mycelium.ingest import wikidata

ARTIFACTS = artifact_directory().parent
REPO = Path(__file__).resolve().parents[1]

#: Cuts that exist on disk but are deliberately NOT the pin yet. **Empty in the normal state.** Phase 7.6
#: step 5 writes ``artifacts/v0.10.0/`` before step 9 moves the pin (so the new corpus can be checked
#: before anything reads it); step 5 adds "0.10.0" here with that reason and step 9 removes it. A cut
#: that sits here after its phase closes is a pin somebody forgot to move.
UNPINNED_CUTS: dict[str, str] = {
    "0.10.0": (
        "phase 7.6 step 5 wrote it on 2026-09-11; step 9 moves the pin only after every dataset's "
        "re-pin check, so until then it is built and deliberately not read by anything"
    ),
}

_VERSION = re.compile(r"^(\d+)\.(\d+)\.(\d+)$")


def version_key(version: str) -> tuple[int, int, int]:
    """``"0.10.0"`` as ``(0, 10, 0)``. The only correct way to order artifact versions."""
    match = _VERSION.fullmatch(version)
    assert match is not None, f"{version!r} is not MAJOR.MINOR.PATCH"
    major, minor, patch = (int(part) for part in match.groups())
    return (major, minor, patch)


def cut_versions() -> list[str]:
    """Every artifact version on disk, from the directory names under ``artifacts/``."""
    return [
        p.name.removeprefix("v")
        for p in ARTIFACTS.iterdir()
        if p.is_dir() and p.name.startswith("v")
    ]


def test_the_ordering_this_file_relies_on_is_not_string_order() -> None:
    """The control: if string order and numeric order agreed on these, the tests below would prove
    nothing about the trap they exist for."""
    versions = ["0.7.1", "0.10.0", "0.9.0"]
    assert sorted(versions) == ["0.10.0", "0.7.1", "0.9.0"], "string order puts 0.10.0 first"
    assert sorted(versions, key=version_key) == ["0.7.1", "0.9.0", "0.10.0"]


def test_every_cut_is_named_major_minor_patch() -> None:
    for version in cut_versions():
        version_key(version)  # asserts the shape


def test_the_pin_is_the_numerically_newest_cut() -> None:
    """The newest cut is the pinned one, compared as numbers, unless it is recorded as not pinned yet."""
    candidates = [v for v in cut_versions() if v not in UNPINNED_CUTS]
    newest = max(candidates, key=version_key)
    assert newest == PINNED_ARTIFACT_VERSION, (
        f"the newest cut on disk is v{newest} but the pin is v{PINNED_ARTIFACT_VERSION}. Either move "
        f"the pin, or record v{newest} in UNPINNED_CUTS with the reason it is not pinned yet."
    )


def test_unpinned_cuts_exist_and_are_newer_than_the_pin() -> None:
    """An entry here is a cut in flight. One that does not exist, or is older than the pin, is stale."""
    on_disk = set(cut_versions())
    for version, reason in UNPINNED_CUTS.items():
        assert reason.strip(), f"v{version} is listed without a reason"
        assert version in on_disk, f"v{version} is listed as unpinned but is not on disk"
        assert version_key(version) > version_key(PINNED_ARTIFACT_VERSION)


def test_every_copy_of_the_pin_agrees() -> None:
    """The pin lives in more than one place by design (``graph`` may not import ``ingest``, and the
    datasets and the SPA carry their own). Each of these is also asserted by its own test file; this is
    the single list of them, so a copy added later has one obvious place to be registered.
    ``docs/phases/phase-7.6-classical-lineage-IMPLEMENTATION.md`` §3.4 is the map this mirrors."""
    datasets = REPO / "src/musical_mycelium/eval/datasets"
    copies = {
        "graph/memory.py:PINNED_ARTIFACT_VERSION": PINNED_ARTIFACT_VERSION,
        "ingest/wikidata.py:ARTIFACT_VERSION": wikidata.ARTIFACT_VERSION,
        "web/src/chips.json": json.loads((REPO / "web/src/chips.json").read_text())[
            "artifact_version"
        ],
    }
    for name in ("gold_v0_1.json", "adversarial_v1.json", "tour_v1.json"):
        copies[f"eval/datasets/{name}"] = json.loads((datasets / name).read_text())[
            "artifact_version_pin"
        ]
    disagreeing = {
        where: value for where, value in copies.items() if value != PINNED_ARTIFACT_VERSION
    }
    assert not disagreeing, f"these copies disagree with v{PINNED_ARTIFACT_VERSION}: {disagreeing}"
