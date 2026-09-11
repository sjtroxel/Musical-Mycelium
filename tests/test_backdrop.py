"""The committed backdrop data must still be the pinned corpus.

`web/src/graph/backdropData.ts` is generated and committed, the way `web/src/corpus-facts.json` is.
A generated file that nobody re-derives is a file that silently stops matching its source -- and this
one would fail quietly rather than loudly, because a backdrop drawn from a stale corpus still looks
like a backdrop. Nothing on screen would say the picture is of a graph the project no longer ships.

This is the same guard `tests/test_chips.py` puts on the chip set and for the same reason.
"""

from __future__ import annotations

import re
from pathlib import Path

from musical_mycelium.graph.backdrop import OUT, build
from musical_mycelium.graph.memory import PINNED_ARTIFACT_VERSION


def committed() -> dict[str, str]:
    """The fields of the generated module, read back out of the TypeScript."""
    text = Path(OUT).read_text(encoding="utf-8")
    # `\s*` because the emitted lines are long: whatever wraps them, the field is still the field.
    found = dict(re.findall(r'(\w+):\s*"([^"]*)"', text))
    found.update(dict(re.findall(r"(\w+):\s*(\d+),", text)))
    return found


def test_the_committed_backdrop_matches_a_fresh_solve_of_the_pinned_artifact() -> None:
    """Re-solve and compare. The layout is deterministic from a seed, so this is exact, not fuzzy."""
    fresh = build()
    have = committed()
    assert have["artifactVersion"] == PINNED_ARTIFACT_VERSION
    assert have["xy"] == fresh["xy"], "positions have drifted from the pinned artifact"
    assert have["kinds"] == fresh["kinds"]
    assert have["edges"] == fresh["edges"]
    assert int(have["nodeCount"]) == fresh["node_count"]
    assert int(have["edgeCount"]) == fresh["edge_count"]


def test_the_solve_is_deterministic() -> None:
    """Two solves of the same artifact and seed agree.

    Without this the test above would pass by construction on a machine where the layout happened to
    be stable and fail on another. The one place randomness enters -- coincident nodes -- is nudged
    by index rather than by `random`, and this is what holds that.
    """
    assert build()["xy"] == build()["xy"]


def test_the_backdrop_is_a_connected_picture_not_a_scattering() -> None:
    """Every edge index addresses a node that exists.

    The packing stores edges as uint16 indices into the node list, which silently truncates above
    65,535 nodes. The corpus is nowhere near that today; this fails the day it is, rather than drawing
    a picture of the wrong graph.
    """
    fresh = build()
    assert fresh["node_count"] <= 65_535, "uint16 indices cannot address this corpus any more"
    assert fresh["edge_count"] > 0


def test_the_backdrop_holds_the_largest_component_and_says_so() -> None:
    """It is the largest component, not the whole graph, and the numbers are the recorded ones."""
    fresh = build()
    # v0.7.1: 7 components, 1,465 of 1,479 nodes in the largest. Asserted as a floor rather than an
    # equality so a corpus change fails the test above -- which explains itself -- rather than this one.
    assert fresh["node_count"] >= 1_000
    assert fresh["edge_count"] > 0


def test_the_backdrop_draws_every_lineage_line_and_no_membership_line() -> None:
    """Phase 7.6 step 6, his decision: every node of the component, but only lineage lines drawn.

    Replaced ``edge_count >= node_count``, which held while every component edge was drawn and means
    nothing now that membership lines are not. The property worth holding is exact: the drawn count is
    the component's influence and teaching edges, all of them, and nothing else.
    """
    import json

    from musical_mycelium.graph.backdrop import ARTIFACT, DRAWN_PREDICATES, largest_component

    graph = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    keep = set(largest_component(graph["nodes"], graph["edges"]))
    inside = [e for e in graph["edges"] if e["subject_id"] in keep and e["object_id"] in keep]
    lineage = [e for e in inside if e["predicate"] in DRAWN_PREDICATES]
    assert "plays_genre" not in DRAWN_PREDICATES
    assert build()["edge_count"] == len(lineage)
