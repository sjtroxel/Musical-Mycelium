"""Figures the SPA prints as prose must match the pinned artifact.

``web/src/corpus-facts.json`` holds the numbers that appear in first-screen copy. They are data rather
than string literals in a component precisely so this file can check them: ``CLAUDE.md`` requires corpus
bias to be *visible in output*, and a visible number that has quietly gone wrong is worse than no number.

The precedent is real. A published coverage percentage was retracted on 2026-08-07 because it added the
US and UK country totals and double-counted every genre credited to both.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.graph.memory import default_store
from musical_mycelium.graph.store import Direction, GraphStore

FACTS_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "corpus-facts.json"
ARTIFACTS = Path(__file__).resolve().parents[1] / "src" / "musical_mycelium" / "artifacts"


@pytest.fixture(scope="module")
def facts() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    return document


@pytest.fixture(scope="module")
def store() -> GraphStore:
    return default_store()


@pytest.fixture(scope="module")
def node_ids(store: GraphStore) -> list[str]:
    graph = json.loads(
        (ARTIFACTS / f"v{store.artifact_version}" / "graph.json").read_text(encoding="utf-8")
    )
    return [node["id"] for node in graph["nodes"]]


def test_the_facts_file_pins_the_artifact_the_store_loaded(
    facts: dict[str, Any], store: GraphStore
) -> None:
    assert facts["artifact_version"] == store.artifact_version


def test_the_node_count_is_right(facts: dict[str, Any], node_ids: list[str]) -> None:
    assert facts["nodes"] == len(node_ids)


def test_the_count_of_nodes_with_no_recorded_influences_is_right(
    facts: dict[str, Any], node_ids: list[str], store: GraphStore
) -> None:
    """The number that keeps a refusal from becoming a negative claim.

    IMPLEMENTATION 4.5 requirement 5: "Nobody influenced Kate Bush" is false and this corpus cannot
    support it. The refusal copy says what is *recorded*, and this figure is what makes that honest
    rather than merely careful -- most of the corpus records nothing in this direction.
    """
    observed = sum(
        1 for node_id in node_ids if not store.neighbors(node_id, Direction.INFLUENCED_BY)
    )
    assert facts["nodes_without_recorded_influences"] == observed


def test_most_of_the_corpus_records_no_influences(
    facts: dict[str, Any], node_ids: list[str]
) -> None:
    """The *claim the copy makes*, not just the digits.

    The sentence on screen says a missing edge is overwhelmingly not evidence of a missing influence.
    That argument only holds while the majority of nodes genuinely record nothing. If a future corpus
    flips this, the copy has to be rewritten -- so it fails here rather than going quietly false.
    """
    assert facts["nodes_without_recorded_influences"] > len(node_ids) / 2
