"""The demo queries named in **prose** must walk in the pinned artifact.

``tests/test_chips.py`` already enforces the standing rule for the first screen's chips, and
``tests/test_gold_set.py`` enforces it for every gold case. Both read **data** — ``chips.json`` and
``gold_v0_1.json`` — and that is why both work.

**This file exists because a demo query written in running text is not data and nothing executed it.**
``SPEC.md`` 1's surface table and ``phase-7-cinematic-surface.md``'s Delivers section each named the guided
tour's example as *"Take me from delta blues to Detroit techno"*. Measured 2026-09-09 at artifact v0.7.1:
there is no path between them in either direction, and no undirected connection either. ``Delta blues``
sits in a two-node influence component with ``Chicago blues``; ``Detroit techno`` sits in the 534-node one.

The sentence had been false since the corpus grew and nothing caught it, because every check this project
owns pointed at data and the sentence was prose. ``SPEC.md`` 2 even recorded *"Delta blues is absent from
the corpus"* on 2026-08-02 while the surface table above it kept offering the route.

**So both halves are asserted here, and neither is sufficient alone.** A test pinned only to node ids goes
green while the prose beside it names something else; a test that only greps prose cannot tell whether the
route walks. The pair below must walk, *and* the documents must name that pair.
"""

from __future__ import annotations

from itertools import pairwise
from pathlib import Path

import pytest

from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.store import Direction

DOCS = Path(__file__).resolve().parents[1] / "docs"

#: The surface-C demo. **No longer provisional: chosen in step 8 from a ranked list of 20,095 candidate
#: walks**, on measured evidence rather than taste. Five hops, three of them ``HAND``-checked and two
#: corroborated. ``graph/routes.py`` is the ranking; ``make routes`` re-runs it.
DEMO_START = ("Q241662", "groove metal")
DEMO_END = ("Q9759", "blues")
DEMO_HOPS = 5

#: The route that was offered for months and never ran. Kept as an assertion rather than a comment so that
#: a future corpus which *does* connect these two fails this file and forces someone to re-read the
#: decision, instead of silently making a retired claim true again.
#:
#: **Both endpoints are named here rather than reusing ``DEMO_START`` for the second one.** They were the
#: same node until step 8 moved the demo to a different route entirely, at which point a shared constant
#: would have quietly re-pointed this assertion at a pair nobody retired -- still green, still passing,
#: and no longer testing the thing it was written for.
RETIRED_START = ("Q1127539", "Delta blues")
RETIRED_END = ("Q526463", "Detroit techno")

#: Where a demo query is named in prose, and the line or block that names it. Extending this dict is the
#: cheap way to protect a new one: any document that offers a route to a reader belongs here.
NAMED_IN_PROSE = {
    "SPEC.md surface table": (DOCS / "SPEC.md", "| **C. Guided tour**"),
    "phase 7 scope doc": (
        DOCS / "phases" / "phase-7-cinematic-surface.md",
        "**The guided tour — surface C.**",
    ),
}


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


def block(path: Path, marker: str) -> str:
    """The marker line plus its continuation lines, which is where a prose route actually sits.

    A markdown table row is one line; a bullet wraps. Reading only the marker line would miss half of
    the scope doc's sentence, and reading the whole file would make the assertion vacuous -- both node
    labels appear somewhere in any of these documents.
    """
    lines = path.read_text(encoding="utf-8").splitlines()
    start = next((i for i, line in enumerate(lines) if marker in line), None)
    assert start is not None, f"{path.name}: no line contains {marker!r}"

    collected = [lines[start]]
    for line in lines[start + 1 :]:
        if not line.strip() or line.lstrip().startswith(("- ", "* ", "|", "#")):
            break
        collected.append(line)
    return "\n".join(collected)


# --- the route has to walk --------------------------------------------------------------------------


def test_the_surface_c_demo_walks_in_the_pinned_artifact(store: InMemoryGraphStore) -> None:
    """The assertion whose absence let a dead demo ship. One call, and it is the whole point of the file."""
    chain = store.path(DEMO_START[0], DEMO_END[0], Direction.INFLUENCED_BY)
    assert chain, f"{DEMO_START[1]} -> {DEMO_END[1]} has no sourced chain in the pinned artifact"
    assert len(chain) == DEMO_HOPS
    assert chain[0].subject_id == DEMO_START[0]
    assert chain[-1].object_id == DEMO_END[0]


def test_every_hop_of_the_demo_carries_a_source(store: InMemoryGraphStore) -> None:
    """A route that walks but cannot be cited is not a demo this project is allowed to show."""
    for edge in store.path(DEMO_START[0], DEMO_END[0], Direction.INFLUENCED_BY):
        assert edge.source and edge.source_id, (
            f"{edge.subject_id} -> {edge.object_id} has no provenance"
        )


def test_the_demo_is_contiguous(store: InMemoryGraphStore) -> None:
    """Each hop starts where the last one ended. A gap would narrate two chains as one."""
    chain = store.path(DEMO_START[0], DEMO_END[0], Direction.INFLUENCED_BY)
    for earlier, later in pairwise(chain):
        assert earlier.object_id == later.subject_id


# --- and the documents have to name the route that walks ---------------------------------------------


@pytest.mark.parametrize("where", sorted(NAMED_IN_PROSE))
def test_the_document_names_the_route_that_walks(where: str) -> None:
    """The half a node-id test cannot cover: the ids are right and the sentence says something else."""
    path, marker = NAMED_IN_PROSE[where]
    text = block(path, marker)
    for _, label in (DEMO_START, DEMO_END):
        assert label.lower() in text.lower(), f"{where}: does not name {label!r}"


@pytest.mark.parametrize("where", sorted(NAMED_IN_PROSE))
def test_the_document_does_not_still_offer_the_retired_route(where: str) -> None:
    """``Delta blues`` may be discussed anywhere in these documents; it may not be *offered* here."""
    path, marker = NAMED_IN_PROSE[where]
    assert RETIRED_START[1].lower() not in block(path, marker).lower(), (
        f"{where}: still offers {RETIRED_START[1]!r} as a demo route"
    )


# --- and the reason it was retired stays measured ----------------------------------------------------


def test_the_retired_route_really_has_no_path(store: InMemoryGraphStore) -> None:
    """Both directions and both argument orders, because a one-directional check is how a path gets
    called missing when it is only being walked the wrong way. If this ever fails, the corpus has
    connected them and the retirement is worth re-reading rather than working around."""
    start, end = RETIRED_START[0], RETIRED_END[0]
    for a, b in ((start, end), (end, start)):
        for direction in (Direction.INFLUENCED_BY, Direction.INFLUENCED):
            assert not store.path(a, b, direction), f"{a} -> {b} ({direction}) now has a path"


def test_the_retired_endpoint_is_in_the_corpus_but_isolated(store: InMemoryGraphStore) -> None:
    """It resolves, which is why the dead route looked plausible. It has no sourced parents at all, so
    no ancestry walk can leave it -- the property that made the demo unanswerable."""
    assert store.get_node(RETIRED_START[0]) is not None
    assert not list(store.neighbors(RETIRED_START[0], Direction.INFLUENCED_BY))
