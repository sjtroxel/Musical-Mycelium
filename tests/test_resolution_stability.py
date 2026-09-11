"""Every name the project depends on resolves the same way after a corpus change.

Added 2026-09-11, phase 7.6 step 0, **before** the pin moves from v0.7.1 to v0.10.0 (phase 7.6
IMPLEMENTATION trap 14). Resolution needs exactly one exact label match: zero is "not in this graph"
and two is ambiguity, which also refuses (``graph/memory.py:exact_matches``). So a corpus that GROWS can
break a name without touching it. A newly ingested 19th-century "John Williams" would make the film
composer ambiguous, and every case that resolves him would start refusing, for a reason no other test
names. The reverse matters as much: several adversarial cases are correct only because a name does NOT
resolve, and a recovered entity could quietly turn one of those refusals into an answer.

``resolution_snapshot_v0_7_1.json`` is the record of what every such name resolved to on v0.7.1,
written once from that corpus and **never regenerated afterwards**: it is the "before" half of a
comparison, and regenerating it on the new corpus would compare the new corpus with itself.

A name that legitimately resolves differently on a later corpus is listed in ``RESOLUTION_CHANGES`` with
the reason, and the dataset case that depends on it is re-authored or re-pinned by its own rule. Nothing
is allowed to change silently.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from musical_mycelium.graph.memory import InMemoryGraphStore, default_store, exact_matches

REPO = Path(__file__).resolve().parents[1]
SNAPSHOT = Path(__file__).with_name("resolution_snapshot_v0_7_1.json")
SNAPSHOT_ARTIFACT = "0.7.1"
DATASETS = REPO / "src/musical_mycelium/eval/datasets"

#: The three outcomes, named once. A node id means exactly one exact match.
UNRESOLVED = "UNRESOLVED"
AMBIGUOUS = "AMBIGUOUS"

#: Names whose resolution is ALLOWED to differ from the v0.7.1 snapshot, each with its reason and the
#: dataset consequence. **Empty until phase 7.6 step 9**, which fills it from the comparison rather than
#: from expectation.
RESOLUTION_CHANGES: dict[str, str] = {}

#: The README's refusal example (``eval/published.py:REFUSAL_EXAMPLE``). Named here because the README is
#: prose, not a dataset, and "a demo query written in prose is not protected by anything" (phase 7).
README_IDS = ("Q636",)


def resolve(store: InMemoryGraphStore, name: str) -> str:
    """What ``resolve_node`` would do with ``name``, reduced to an outcome."""
    matches = exact_matches(store.search(name), name)
    if not matches:
        return UNRESOLVED
    if len(matches) > 1:
        return AMBIGUOUS
    return matches[0].id


def referenced_names(store: InMemoryGraphStore) -> dict[str, str]:
    """Every name the project depends on, mapped to its resolution on ``store``.

    Two kinds of name. **Query terms** as the datasets record them (a gold case's
    ``expected_resolution.name``, an adversarial case's ``query_term``), which is what a model types.
    **Labels of every node the datasets, chips and README reference**, because a model that walked to a
    node will resolve it by its label, and a label collision breaks that silently.
    """
    names: set[str] = set()
    ids: set[str] = set(README_IDS)

    gold = json.loads((DATASETS / "gold_v0_1.json").read_text(encoding="utf-8"))
    tour = json.loads((DATASETS / "tour_v1.json").read_text(encoding="utf-8"))
    for case in [*gold["cases"], *tour["cases"]]:
        for key in ("expected_resolution", "expected_terminus"):
            if isinstance(case.get(key), dict):
                names.add(case[key]["name"])
                if case[key].get("node_id"):
                    ids.add(case[key]["node_id"])
        ids.update(case.get("expected_path", []))
        for claim in case.get("expected_claims", []):
            ids.update((claim["subject_id"], claim["object_id"]))

    adversarial = json.loads((DATASETS / "adversarial_v1.json").read_text(encoding="utf-8"))
    for case in adversarial["cases"]:
        resolution = case["expected"].get("resolution") or {}
        if resolution.get("query_term"):
            names.add(resolution["query_term"])
        if resolution.get("node_id"):
            ids.add(resolution["node_id"])
        for triple in case["expected"].get("forbidden_triples", []):
            ids.update((triple[0], triple[2]))

    chips = json.loads((REPO / "web/src/chips.json").read_text(encoding="utf-8"))
    for chip in chips["chips"]:
        for step in chip["steps"]:
            for key in ("subject_id", "start_id", "end_id"):
                if step.get(key):
                    ids.add(step[key])

    for node_id in ids:
        node = store.get_node(node_id)
        if node is not None:
            names.add(node.label)

    return {name: resolve(store, name) for name in sorted(names)}


def test_the_snapshot_was_taken_on_the_corpus_it_names() -> None:
    recorded: dict[str, Any] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))
    assert recorded["artifact_version"] == SNAPSHOT_ARTIFACT
    assert recorded["resolutions"], "an empty snapshot would compare nothing"


def test_every_recorded_name_resolves_as_it_did_on_v0_7_1() -> None:
    """The comparison. On v0.7.1 it is the snapshot agreeing with itself; from the re-pin on it is the
    check that nothing the project depends on moved without a recorded reason."""
    recorded: dict[str, str] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["resolutions"]
    store = default_store()
    moved = {
        name: f"{before} -> {resolve(store, name)}"
        for name, before in recorded.items()
        if name not in RESOLUTION_CHANGES and resolve(store, name) != before
    }
    assert not moved, (
        f"{len(moved)} name(s) resolve differently on v{store.artifact_version} than on "
        f"v{SNAPSHOT_ARTIFACT}: {moved}. Record each in RESOLUTION_CHANGES with its reason, and handle "
        f"the dataset case that depends on it by that dataset's own re-pin rule."
    )


def test_listed_changes_are_real_and_explained() -> None:
    recorded: dict[str, str] = json.loads(SNAPSHOT.read_text(encoding="utf-8"))["resolutions"]
    for name, reason in RESOLUTION_CHANGES.items():
        assert name in recorded, f"{name!r} is listed as changed but was never in the snapshot"
        assert reason.strip(), f"{name!r} is listed without a reason"


def _write_snapshot() -> None:  # pragma: no cover - run once, by hand, on v0.7.1 only
    store = default_store()
    if store.artifact_version != SNAPSHOT_ARTIFACT:
        sys.exit(
            f"refusing: the pinned corpus is v{store.artifact_version}. This snapshot is the v"
            f"{SNAPSHOT_ARTIFACT} half of a before/after comparison and must never be regenerated "
            f"on a later corpus."
        )
    payload = {
        "$comment": [
            "Written 2026-09-11 by tests/test_resolution_stability.py on artifact v0.7.1, before",
            "phase 7.6 moved the pin. The BEFORE half of a comparison: never regenerate it.",
        ],
        "artifact_version": store.artifact_version,
        "resolutions": referenced_names(store),
    }
    SNAPSHOT.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {SNAPSHOT.name}: {len(payload['resolutions'])} names")


if __name__ == "__main__":  # pragma: no cover
    _write_snapshot()
