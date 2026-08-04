"""The ``GraphStore`` protocol — the only way anything reads the graph.

This is the seam that makes the "no managed database" cost decision reversible. Today it is a dict over a
JSON file baked into the container image; a 100x corpus later is a new implementation of these four
methods and one wire flipped. The agent, the API and the eval harness never learn what is behind it.

**Every method here exists at v0.1 even though v0.1 does not need all of them.** Adding a method to a
protocol later means touching every implementation, and the shapes are already known: phase 5's guided
tour needs ``path``, and ``SPEC.md`` 2.2 commits to descendant queries. So ``path`` is declared and
raises ``NotImplementedError`` in the v0.1 backend rather than being absent, and ``neighbors`` takes a
direction rather than hard-coding the one direction v0.1 walks.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Protocol, runtime_checkable

from musical_mycelium.graph.schema import Edge, Node


class Direction(StrEnum):
    """Which way to walk an ``influenced_by`` edge.

    Named after the claim rather than the graph. An edge reads *subject* ``influenced_by`` *object*, so
    "the influences on X" and "what X influenced" are opposite traversals of the same row, and getting
    them backwards silently inverts music history. ``INCOMING``/``OUTGOING`` invites exactly that
    mistake; these names do not.
    """

    #: Edges where the node is the **subject** — what this genre came out of. The v0.1 direction.
    INFLUENCED_BY = "influenced_by"

    #: Edges where the node is the **object** — what came out of this genre. Arrives with phase 2's
    #: corpus; the store supports it now so the tool layer does not have to grow a new method later.
    INFLUENCED = "influenced"


@runtime_checkable
class GraphStore(Protocol):
    """Read access to a pinned graph artifact.

    Implementations must be **honest about absence**: an unknown node is ``None`` and an unsourced node
    is an empty list, never a guess. Refusal is correct behaviour
    (``.claude/rules/grounding-and-claims.md``), and it can only be correct if the layer underneath the
    agent declines to invent rather than returning a near-miss.
    """

    @property
    def artifact_version(self) -> str:
        """The pinned version this store was loaded from. Evals report against it."""
        ...

    def get_node(self, node_id: str) -> Node | None:
        """The node with this id, or ``None``. Never a fuzzy match — that is ``search``'s job."""
        ...

    def neighbors(self, node_id: str, direction: Direction = Direction.INFLUENCED_BY) -> list[Edge]:
        """One hop from ``node_id``, as **edges** rather than nodes.

        Edges, because an edge carries the provenance a ``Claim`` has to cite. Returning nodes here
        would strand ``source_id`` on the floor and make grounding unverifiable one layer up.

        An empty list means the graph has no sourced edges in that direction. It does not mean the
        genre has no influences in reality, and nothing downstream may narrate it that way.
        """
        ...

    def search(self, text: str) -> list[Node]:
        """Candidate nodes for a human-typed name, best match first. Empty when nothing matches."""
        ...

    def path(self, start_id: str, end_id: str) -> list[Edge]:
        """The shortest sourced chain from ``start_id`` to ``end_id``, or an empty list if none exists.

        Declared at v0.1, **implemented in phase 2** alongside the corpus it needs. The v0.1 backend
        raises ``NotImplementedError``: the method is on the protocol because retrofitting it would touch
        every implementation, and because ``SPEC.md`` 2.2 already names the query it serves.

        *(Corrected 2026-08-04: this said "phase 5". It was written while ``path()`` was a phase-1
        deferral, but the ROADMAP assigns "real multi-hop traversal" to phase 2 and that phase's DoD #2
        requires a three-hop path. Phase 5 **consumes** this for the guided tour; it does not introduce
        it.)*
        """
        ...
