"""The first screen's chips must resolve against the pinned artifact.

Standing rule, adopted 2026-08-02 and restated in ``docs/phases/phase-5-spa-and-visualization-
IMPLEMENTATION.md`` 4.3: **every chip is validated against the pinned artifact before it ships, and the
check is a test so a corpus change fails the build rather than a demo.** A demo that 404s in front of a
recruiter is the failure this file exists to prevent.

``web/src/chips.json`` is the single source of truth. The SPA renders it; this validates it. Nothing
here imports from ``web/`` — it reads the JSON, which is the whole point of keeping the chip definitions
in data rather than in TypeScript.

**The direction assertions are the load-bearing half.** A chip that says ``expect: answer`` while the
graph only has edges the other way would render a refusal on the first screen, and the reverse would
render a confident answer where the corpus has nothing. Three separate bugs in this project's history
came from assuming the origins direction (``Direction``'s own docstring warns about it), so each step
names its direction explicitly and it is checked rather than defaulted.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.graph.memory import default_store
from musical_mycelium.graph.store import Direction, GraphStore

CHIPS_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "chips.json"


@pytest.fixture(scope="module")
def store() -> GraphStore:
    return default_store()


@pytest.fixture(scope="module")
def chips_document() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(CHIPS_PATH.read_text(encoding="utf-8"))
    return document


@pytest.fixture(scope="module")
def chips(chips_document: dict[str, Any]) -> list[dict[str, Any]]:
    return list(chips_document["chips"])


def _steps(chips: list[dict[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
    return [(chip["id"], step) for chip in chips for step in chip["steps"]]


def test_the_chip_file_pins_the_artifact_version_the_store_actually_loaded(
    chips_document: dict[str, Any], store: GraphStore
) -> None:
    """A chip set validated against a different corpus than the one deployed proves nothing."""
    assert chips_document["artifact_version"] == store.artifact_version


def test_there_are_five_chips(chips: list[dict[str, Any]]) -> None:
    """Five is a decision, not an accident -- IMPLEMENTATION 4.3, decided 2026-08-24.

    Asserted so that adding a sixth is a deliberate act that updates this test and re-reads 4.3,
    rather than something that drifts in while nobody is counting.
    """
    assert len(chips) == 5


def test_chip_ids_are_unique(chips: list[dict[str, Any]]) -> None:
    ids = [chip["id"] for chip in chips]
    assert len(ids) == len(set(ids))


def test_every_chip_has_a_label_and_at_least_one_step(chips: list[dict[str, Any]]) -> None:
    for chip in chips:
        assert chip["label"].strip(), f"{chip['id']} has no label"
        assert chip["steps"], f"{chip['id']} has no steps"


def test_every_named_node_exists_in_the_pinned_artifact(
    chips: list[dict[str, Any]], store: GraphStore
) -> None:
    """The bluntest check and the one most likely to fire after a re-ingest."""
    for chip_id, step in _steps(chips):
        for field in ("subject_id", "start_id", "end_id"):
            node_id = step.get(field)
            if node_id is None:
                continue
            assert store.get_node(node_id) is not None, (
                f"chip {chip_id} names {field}={node_id}, which is not in artifact "
                f"{store.artifact_version}"
            )


def test_every_step_declares_a_direction_the_store_understands(
    chips: list[dict[str, Any]],
) -> None:
    valid = {d.value for d in Direction}
    for chip_id, step in _steps(chips):
        assert step["direction"] in valid, f"chip {chip_id} names direction {step['direction']!r}"


def test_answer_steps_have_edges_in_the_direction_they_name(
    chips: list[dict[str, Any]], store: GraphStore
) -> None:
    """``expect: answer`` must be backed by real edges, walked the way the step says to walk them."""
    for chip_id, step in _steps(chips):
        if step["expect"] != "answer" or step["kind"] == "path":
            continue
        direction = Direction(step["direction"])
        edges = store.neighbors(step["subject_id"], direction)
        assert edges, (
            f"chip {chip_id} expects an answer for {step['subject_id']} walking {direction.value}, "
            f"but the artifact has no edges that way"
        )


def test_refusal_steps_have_no_edges_in_the_direction_they_name(
    chips: list[dict[str, Any]], store: GraphStore
) -> None:
    """The other half, and the one that quietly rots.

    A refusal chip whose subject gains an edge stops demonstrating a refusal and starts demonstrating
    an answer -- with copy on screen still saying the sources record nothing. That is the corpus
    telling the visitor something false, so it fails here.
    """
    for chip_id, step in _steps(chips):
        if step["expect"] != "refusal":
            continue
        direction = Direction(step["direction"])
        edges = store.neighbors(step["subject_id"], direction)
        assert not edges, (
            f"chip {chip_id} expects a refusal for {step['subject_id']} walking {direction.value}, "
            f"but the artifact now has {len(edges)} edge(s) that way -- the chip is stale"
        )


def test_path_steps_resolve_to_a_real_path_in_the_direction_they_name(
    chips: list[dict[str, Any]], store: GraphStore
) -> None:
    """``path`` is directional and the reverse is empty.

    ``path("Q9759", "Q38848")`` returns ``[]`` while ``path("Q38848", "Q9759")`` returns two hops, so
    a chip that named the endpoints the intuitive way round -- oldest first, the way the *label* reads
    -- would render nothing at all.
    """
    for chip_id, step in _steps(chips):
        if step["kind"] != "path":
            continue
        direction = Direction(step["direction"])
        edges = store.path(step["start_id"], step["end_id"], direction)
        assert edges, (
            f"chip {chip_id} expects a path {step['start_id']} -> {step['end_id']} walking "
            f"{direction.value}, but the artifact has none"
        )


def test_the_paired_chip_refuses_before_it_answers(chips: list[dict[str, Any]]) -> None:
    """DoD 10's fourth requirement, asserted rather than trusted to copy review.

    IMPLEMENTATION 4.5: *no dead end is reachable*, and the pairing is what makes that structural
    instead of a matter of good intentions. A refusal must never be the last thing on screen, so any
    chip containing a refusal step must continue to an answer step after it.
    """
    for chip in chips:
        expectations = [step["expect"] for step in chip["steps"]]
        if "refusal" not in expectations:
            continue
        assert expectations[-1] == "answer", (
            f"chip {chip['id']} ends on a refusal; DoD 10 requires the pairing to end on an answer"
        )
