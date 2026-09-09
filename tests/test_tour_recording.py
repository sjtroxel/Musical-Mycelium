"""The guided tour's recording must still be true of the pinned artifact.

**Why a recording needs a test at all, and it is the same failure this repo caught three days running.**
The tour replays captured bytes rather than calling the model per visitor -- decided 2026-09-09, phase 7
step 6, on cost: a tour that plays on load would bill a Bedrock run per page view. The price of a
recording is that it is a **file that can drift from the corpus**. If the artifact moves and the
recording does not, the showcase narrates influence claims that are no longer in the graph -- a demo of
something that stopped being true, which is exactly what ``tests/test_canonical_surfaces.py`` was written
for on the same day and what ``tests/test_chips.py`` has enforced since 2026-08-02.

**So this file is the third member of that family and should read like it.** Same standing rule, adopted
2026-08-02: *every demo is validated against the pinned artifact, and the check is a test so a corpus
change fails the build rather than a demo.*

**What it deliberately does not check: the prose.** The recording committed today was captured from
``LocalLLM`` (``make dev``), so its narration is stub text. The claims, the path and the frame sequence
are real -- the stub drives the real ``trace_lineage`` over the real graph and every claim below passed
the real gate. Replacing the narration with a Bedrock capture costs about a cent and is a decision for
sjtroxel, not a side effect of this file; nothing here has to change when it happens, which is the point
of validating claims rather than words.
"""

from __future__ import annotations

import json
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.agent.claims import ClaimProposal, gate
from musical_mycelium.graph.memory import GraphStore, default_store
from musical_mycelium.graph.store import Direction

RECORDING = (
    Path(__file__).resolve().parents[1] / "web" / "src" / "fixtures" / "tour-techno-to-blues.sse"
)

#: The route the recording walks, and the same pair `tests/test_canonical_surfaces.py` pins in the
#: documents. Duplicated as ids rather than imported so that a change to either file is a visible
#: disagreement between two assertions rather than one silently dragging the other along.
TOUR_START = "Q526463"
TOUR_END = "Q9759"
TOUR_CHAIN = ("Detroit techno", "Chicago house", "hip-hop", "rhythm and blues", "blues")


@pytest.fixture(scope="module")
def store() -> GraphStore:
    return default_store()


@pytest.fixture(scope="module")
def frames() -> list[tuple[str, dict[str, Any]]]:
    """The recording as (event name, payload) pairs, parsed the way the SPA's reader parses it."""
    events: list[tuple[str, dict[str, Any]]] = []
    name: str | None = None
    for line in RECORDING.read_text(encoding="utf-8").splitlines():
        if line.startswith("event: "):
            name = line.removeprefix("event: ").strip()
        elif line.startswith("data: ") and name is not None:
            events.append((name, json.loads(line.removeprefix("data: "))))
            name = None
    return events


def of_type(frames: list[tuple[str, dict[str, Any]]], kind: str) -> list[dict[str, Any]]:
    return [payload for name, payload in frames if name == kind]


# --- the recording is a real run ---------------------------------------------------------------------


def test_the_recording_exists_and_parses(frames: list[tuple[str, dict[str, Any]]]) -> None:
    """A zero-length or malformed capture would make every assertion below vacuously true."""
    assert frames, "the tour recording is empty"
    assert {name for name, _ in frames} >= {"plan", "claim", "path", "token", "done"}


def test_the_recording_pins_the_artifact_the_store_loaded(
    frames: list[tuple[str, dict[str, Any]]], store: GraphStore
) -> None:
    """The equality `test_chips.py` restored for the chip set, for the same reason: a demo validated
    against a different corpus than the one deployed proves nothing."""
    done = of_type(frames, "done")
    assert len(done) == 1
    assert done[0]["artifact_version"] == store.artifact_version


# --- and every claim in it is still true ------------------------------------------------------------


def test_every_recorded_claim_still_survives_the_gate(
    frames: list[tuple[str, dict[str, Any]]], store: GraphStore
) -> None:
    """**The staleness check.** Propose exactly what the recording narrates and gate it against the
    pinned artifact. One rejection means the tour is telling a visitor something the graph no longer
    holds, and the build should stop rather than the demo."""
    claims = [payload["claim"] for payload in of_type(frames, "claim")]
    assert claims, "the recording narrates no claims"

    result = gate(
        [
            ClaimProposal(
                subject_id=claim["subject_id"],
                predicate=claim["predicate"],
                object_id=claim["object_id"],
            )
            for claim in claims
        ],
        store,
    )
    assert not result.rejected, f"the recording has gone stale: {result.rejected}"
    assert len(result.approved) == len(claims)


def test_every_recorded_claim_still_cites_a_source_that_resolves(
    frames: list[tuple[str, dict[str, Any]]], store: GraphStore
) -> None:
    """Groundedness is a provenance guarantee, so a recorded claim whose source has left the artifact is
    as broken as one whose edge has."""
    for payload in of_type(frames, "claim"):
        claim = payload["claim"]
        assert claim["source_ids"], f"{claim['subject_id']} -> {claim['object_id']} cites nothing"
        edge = next(
            (
                e
                for e in store.neighbors(claim["subject_id"], Direction.INFLUENCED_BY)
                if e.object_id == claim["object_id"]
            ),
            None,
        )
        assert edge is not None
        assert edge.source_id in claim["source_ids"]


# --- and it walks the route the documents promise ----------------------------------------------------


def test_the_recorded_chain_is_the_canonical_demo_route(
    frames: list[tuple[str, dict[str, Any]]],
) -> None:
    """The recording is a third place the demo route is written down. It has to agree with the other
    two, or a visitor is shown a walk the documents do not describe."""
    paths = of_type(frames, "path")
    assert len(paths) == 1
    assert tuple(paths[0]["chain_labels"]) == TOUR_CHAIN


def test_the_recorded_chain_is_contiguous_and_sourced_in_the_artifact(
    frames: list[tuple[str, dict[str, Any]]], store: GraphStore
) -> None:
    """Not `store.path` -- the recording's own chain, hop by hop, against the graph. `store.path` could
    agree with the artifact while the recording disagreed with both."""
    chain = of_type(frames, "path")[0]["chain"]
    assert chain[0] == TOUR_START
    assert chain[-1] == TOUR_END
    for subject, obj in pairwise(chain):
        edge = next(
            (e for e in store.neighbors(subject, Direction.INFLUENCED_BY) if e.object_id == obj),
            None,
        )
        assert edge is not None, f"no sourced edge {subject} -> {obj}"
        assert edge.source and edge.source_id


def test_the_chain_is_not_the_visit_order(frames: list[tuple[str, dict[str, Any]]]) -> None:
    """`PathFrame` documents the distinction and this recording exercises it: visit order resolves both
    endpoints first, so drawing an arrow down `labels` would narrate false history. If a capture ever
    makes these identical, the recording has stopped covering the case."""
    path = of_type(frames, "path")[0]
    assert path["labels"] != path["chain_labels"]
