"""The agent-to-data tool contract.

``CLAUDE.md`` invariant 4: **adding a tool must never require editing the loop.** That is the whole
design constraint here, and it is what the ``ToolResult.proposals`` field buys. A tool does not just
return data — it returns the claims its data supports. The loop harvests proposals generically and never
learns what any particular tool does, so a third tool is a registration, not a loop edit.

Two other properties matter as much as the seam:

**Tools return provenance, not just answers.** ``ToolResult`` carries ``sources``, because an answer
whose citations were dropped one layer down cannot be grounded one layer up.

**Tools are honest about absence.** ``resolve_genre`` returns ``None`` rather than the closest match. An
unresolvable genre is a **refusal**, not an error and certainly not a guess — refusal accuracy is a
headline metric, and it is only meaningful if the layer underneath declines to invent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from musical_mycelium.agent.claims import ClaimProposal
from musical_mycelium.graph.memory import normalise
from musical_mycelium.graph.schema import PREDICATE_INFLUENCED_BY
from musical_mycelium.graph.store import Direction, GraphStore


@dataclass(frozen=True, slots=True)
class ToolResult:
    """What a tool hands back to the loop.

    ``content`` is the JSON-serialisable payload the model sees. ``sources`` and ``proposals`` are for
    the machinery: the loop harvests proposals and gates them, and the model never gets to invent one.
    """

    content: Any
    sources: tuple[str, ...] = ()
    proposals: tuple[ClaimProposal, ...] = ()
    #: Node ids this call touched, in order. The loop assembles the walked path from these without
    #: knowing what any tool does — ``SPEC.md`` 5.3 makes path-in-payload non-negotiable at v0.1, and
    #: having the loop parse tool ``content`` to reconstruct it would break invariant 4.
    visited: tuple[str, ...] = ()
    is_error: bool = False


@runtime_checkable
class Tool(Protocol):
    """A callable the model may invoke.

    ``spec()`` returns the Bedrock Converse ``toolSpec`` shape so the registry can hand the whole set to
    the model without special-casing anything.
    """

    @property
    def name(self) -> str: ...

    @property
    def description(self) -> str: ...

    def input_schema(self) -> dict[str, Any]: ...

    def __call__(self, **kwargs: Any) -> ToolResult: ...


class ToolRegistry:
    """The set of tools available to one run. The loop talks to this, never to a tool directly."""

    def __init__(self, tools: list[Tool] | None = None) -> None:
        self._tools: dict[str, Tool] = {}
        for tool in tools or []:
            self.register(tool)

    def register(self, tool: Tool) -> None:
        if tool.name in self._tools:
            raise ValueError(f"a tool named {tool.name!r} is already registered")
        self._tools[tool.name] = tool

    def __contains__(self, name: object) -> bool:
        return name in self._tools

    def __len__(self) -> int:
        return len(self._tools)

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def tool_config(self) -> dict[str, Any]:
        """The Bedrock Converse ``toolConfig`` block for every registered tool."""
        return {
            "tools": [
                {
                    "toolSpec": {
                        "name": tool.name,
                        "description": tool.description,
                        "inputSchema": {"json": tool.input_schema()},
                    }
                }
                for tool in self._tools.values()
            ]
        }

    def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        """Run a tool by name. An unknown tool or a bad argument is an error **result**, not an
        exception — the model gets told what went wrong and can correct, which is the whole point of
        returning tool errors rather than crashing the loop.

        Both ``TypeError`` (an unexpected keyword) and ``KeyError`` (a missing one) are caught, because
        tool arguments arrive from a language model and are therefore arbitrary. Catching only
        ``TypeError`` left a missing argument crashing the run — found by test on 2026-08-02.
        """
        tool = self._tools.get(name)
        if tool is None:
            return ToolResult(
                content={"error": f"no such tool: {name}", "available": list(self._tools)},
                is_error=True,
            )
        try:
            return tool(**arguments)
        except (TypeError, KeyError) as exc:
            return ToolResult(
                content={
                    "error": f"bad arguments for {name}: {exc}",
                    "expected": tool.input_schema().get("required", []),
                },
                is_error=True,
            )


@dataclass(frozen=True, slots=True)
class ResolveGenre:
    """Name to node id, or ``None``.

    Returning ``None`` rather than the nearest label is the load-bearing behaviour. ``search`` may
    return several candidates; this tool only resolves when the best one is an **exact** normalised
    match, because a confident wrong resolution answers a question nobody asked, with citations.
    """

    store: GraphStore
    name: str = field(default="resolve_genre", init=False)
    description: str = field(
        default=(
            "Resolve a genre name to its node id in the graph. Returns null when the name is not in "
            "this graph. A null result means the graph does not cover that genre — say so; do not "
            "substitute a similar genre."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "The genre name to resolve."}},
            "required": ["name"],
        }

    def __call__(self, **kwargs: Any) -> ToolResult:
        name = kwargs["name"]
        candidates = self.store.search(name)
        if not candidates:
            return ToolResult(content={"node_id": None, "reason": "not in this graph"})

        best = candidates[0]
        if normalise(best.label) != normalise(name):
            # A near miss is not a resolution. Report the alternatives and let the model ask again.
            return ToolResult(
                content={
                    "node_id": None,
                    "reason": "no exact match",
                    "did_you_mean": [n.label for n in candidates[:5]],
                }
            )

        return ToolResult(
            content={"node_id": best.id, "label": best.label},
            sources=(best.source_id,),
            visited=(best.id,),
        )


@dataclass(frozen=True, slots=True)
class GetInfluences:
    """One hop along ``influenced_by``, with the claim proposals those edges support.

    The proposals are built here rather than in the loop, and that is invariant 4 working: the loop
    harvests ``result.proposals`` without knowing this tool exists.
    """

    store: GraphStore
    name: str = field(default="get_influences", init=False)
    description: str = field(
        default=(
            "List the documented influences on a genre — what it came out of. Returns an empty list "
            "when the graph has no sourced influences for that node. An empty list means this graph "
            "cannot answer the question; it does not mean the genre had no influences."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "A node id from resolve_genre."}
            },
            "required": ["node_id"],
        }

    def __call__(self, **kwargs: Any) -> ToolResult:
        node_id = kwargs["node_id"]
        if self.store.get_node(node_id) is None:
            return ToolResult(
                content={"error": f"unknown node: {node_id}. Use resolve_genre first."},
                is_error=True,
            )

        edges = self.store.neighbors(node_id, Direction.INFLUENCED_BY)
        influences = []
        for edge in edges:
            node = self.store.get_node(edge.object_id)
            influences.append(
                {
                    "node_id": edge.object_id,
                    "label": node.label if node else edge.object_id,
                    "predicate": edge.predicate,
                }
            )

        return ToolResult(
            content={"influences": influences, "count": len(influences)},
            sources=tuple(edge.source_id for edge in edges),
            visited=(node_id, *(edge.object_id for edge in edges)),
            proposals=tuple(
                ClaimProposal(
                    subject_id=edge.subject_id,
                    predicate=PREDICATE_INFLUENCED_BY,
                    object_id=edge.object_id,
                )
                for edge in edges
            ),
        )


def default_registry(store: GraphStore) -> ToolRegistry:
    """The two v0.1 tools. Deliberately two — see the phase-1 scope fence."""
    return ToolRegistry([ResolveGenre(store), GetInfluences(store)])
