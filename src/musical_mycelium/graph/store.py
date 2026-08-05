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

    def path(
        self,
        start_id: str,
        end_id: str,
        direction: Direction = Direction.INFLUENCED_BY,
    ) -> list[Edge]:
        """The shortest sourced chain from ``start_id`` to ``end_id``, or an empty list if none exists.

        Edges in traversal order, starting at ``start_id``. Edges, not nodes, for the same reason
        ``neighbors`` returns them: every hop has to carry the provenance its ``Claim`` will cite, and a
        chain of node ids would strand it.

        ``direction`` says which way to walk **from** ``start_id``, exactly as in ``neighbors``, and it
        defaults the same way. ``INFLUENCED_BY`` walks toward ancestors, so
        ``path(heavy_metal, blues)`` traces heavy metal back to the blues. ``INFLUENCED`` walks toward
        descendants, so ``SPEC.md`` 2.2's "how is the blues connected to heavy metal?" is
        ``path(blues, heavy_metal, Direction.INFLUENCED)``. The two are the same chain in opposite
        orders, and the parameter exists so that answering the second phrasing never requires inverting
        an influence claim to do it.

        **Direction is respected, and that is a correctness requirement rather than a nicety.**
        Influence runs one way in time. A traversal that ignored direction would happily return a chain
        narrating heavy metal as an influence on the blues, which is both false and exactly the kind of
        confident wrong answer this project exists to not produce.

        An empty list means **no sourced chain in that direction**. It does not mean the two genres are
        unrelated, and nothing downstream may narrate it that way. Three distinguishable situations all
        collapse to ``[]`` — an unknown id, ``start_id == end_id``, and a genuine absence — so a caller
        that needs to tell them apart checks ``get_node`` and equality itself. That is deliberate: a
        traversal method that raised on an unknown id would make refusal an exception path, and refusal
        is correct behaviour here, not an error.

        *(Corrected 2026-08-04: this said "phase 5". It was written while ``path()`` was a phase-1
        deferral, but the ROADMAP assigns "real multi-hop traversal" to phase 2. Phase 5 **consumes**
        this for the guided tour; it does not introduce it. Implemented 2026-08-05, phase 2 step 4.)*
        """
        ...
