"""The agent-to-data tool contract.

``CLAUDE.md`` invariant 4: **adding a tool must never require editing the loop.** That is the whole
design constraint here, and it is what the ``ToolResult.proposals`` field buys. A tool does not just
return data — it returns the claims its data supports. The loop harvests proposals generically and never
learns what any particular tool does, so a third tool is a registration, not a loop edit.

Two other properties matter as much as the seam:

**Tools return provenance, not just answers.** ``ToolResult`` carries ``sources``, because an answer
whose citations were dropped one layer down cannot be grounded one layer up.

**Tools are honest about absence.** ``resolve_node`` returns ``None`` rather than the closest match. An
unresolvable name is a **refusal**, not an error and certainly not a guess — refusal accuracy is a
headline metric, and it is only meaningful if the layer underneath declines to invent.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

from musical_mycelium.agent.claims import ClaimProposal
from musical_mycelium.agent.llm import undelimit
from musical_mycelium.graph.coverage import (
    PRECISION_CENTURY,
    PRECISION_DECADE,
    PRECISION_YEAR,
    era_of,
)
from musical_mycelium.graph.memory import exact_matches
from musical_mycelium.graph.schema import DBPEDIA_RESOURCE_PREFIX, PREDICATE_INFLUENCED_BY
from musical_mycelium.graph.store import Direction, GraphStore

#: Wikidata statement URIs encode the QID of the entity the statement belongs to. Same prefix
#: ``claims.resolve_sources`` parses; kept as its own constant here rather than imported so the tool
#: layer does not reach into the gate's internals for a string.
_WIKIDATA_STATEMENT_PREFIX = "http://www.wikidata.org/entity/statement/"

#: Wikidata's time-precision codes rendered as words. A decade-precision 1970 shown as "1970" asserts a
#: year the source never claimed, so the word travels beside the number rather than the number alone.
_PRECISION_LABELS: dict[int | None, str] = {
    PRECISION_CENTURY: "century",
    PRECISION_DECADE: "decade",
    PRECISION_YEAR: "year",
}


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
    #: An ordered chain this result asserts, when it asserts one. **Contract: every consecutive pair
    #: ``(chain[i], chain[i + 1])`` must be the ``(subject_id, object_id)`` of one of this result's own
    #: proposals** — so a chain is always oriented descendant-first, whichever way the tool walked to
    #: find it. Generic on purpose: the loop reads this field the way it already reads ``visited``, and
    #: never learns which tool produced it (invariant 4). Empty when a result is a set rather than a
    #: sequence — ``get_influences`` returns a fan-out, not a chain, and must leave this alone.
    chain: tuple[str, ...] = ()
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

        Arguments are stripped of data delimiters first. Tool results reach the model wrapped in
        ``<data>`` tags, and a model handing an id back verbatim would otherwise pass
        ``<data>Q483352</data>`` to a tool that only knows ``Q483352``. One call here covers all seven
        tools and knows nothing about any of them, so the seam is intact.
        """
        arguments = undelimit(arguments)
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
class ResolveNode:
    """Name to node id, or ``None``.

    Returning ``None`` rather than the nearest label is the load-bearing behaviour. ``search`` may
    return several candidates; this tool only resolves when the best one is an **exact** normalised
    match, because a confident wrong resolution answers a question nobody asked, with citations.
    """

    store: GraphStore
    name: str = field(default="resolve_node", init=False)
    description: str = field(
        default=(
            "Resolve a genre name OR an artist name to its node id in the graph. Returns null when "
            "the name is not in this graph. A null result means the graph does not cover it — say "
            "so; do not substitute something similar. The result carries a 'kind' of 'genre' or "
            "'artist': influence only ever runs between two nodes of the SAME kind, so never relate "
            "a genre to an artist."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "The genre or artist name to resolve."}
            },
            "required": ["name"],
        }

    def __call__(self, **kwargs: Any) -> ToolResult:
        name = kwargs["name"]
        candidates = self.store.search(name)
        if not candidates:
            return ToolResult(content={"node_id": None, "reason": "not in this graph"})

        # Exactly one match resolves. Zero is a near miss and **two is ambiguity**, which is also a
        # refusal: "heavy metal" may skip Wikidata's trailing "music" (``label_key``), but if that fold
        # ever makes two nodes equally good the honest answer is to ask, not to take the first.
        # The rule itself lives in ``graph.memory`` because the loop resolves an asserted premise with
        # it too; what stays here is the reporting, which is the part only a tool needs.
        matches = exact_matches(candidates, name)
        if len(matches) != 1:
            return ToolResult(
                content={
                    "node_id": None,
                    "reason": "no exact match" if not matches else "ambiguous",
                    "did_you_mean": [n.label for n in (matches or candidates)[:5]],
                }
            )

        best = matches[0]
        # ``kind`` is returned, not merely stored. Without it the model resolves "U2", gets an id and a
        # label, and has no way to know which axis it landed on — so it can propose a genre-to-artist
        # claim, have ``gate()`` refuse it CROSS_AXIS, and burn a turn on a rejection it had no
        # information to avoid. The gate is the enforcement; this is what lets the model cooperate with
        # it rather than discover it by failing.
        return ToolResult(
            content={"node_id": best.id, "label": best.label, "kind": best.kind},
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
                "node_id": {"type": "string", "description": "A node id from resolve_node."}
            },
            "required": ["node_id"],
        }

    def __call__(self, **kwargs: Any) -> ToolResult:
        node_id = kwargs["node_id"]
        if self.store.get_node(node_id) is None:
            return ToolResult(
                content={"error": f"unknown node: {node_id}. Use resolve_node first."},
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


@dataclass(frozen=True, slots=True)
class TraceLineage:
    """The sourced chain between two genres, one ``ClaimProposal`` per hop.

    **This tool is the seam test.** It is the third tool, it returns a shape the first two do not, and
    adding it changed no branch of the loop — the loop harvests ``proposals``, ``visited`` and ``chain``
    generically and still does not know this class exists (``CLAUDE.md`` invariant 4).

    **It searches both directions and says which one it found**, because the two natural phrasings of
    the same question put the arguments in opposite orders: "how did heavy metal come out of the blues"
    is an ancestry walk from heavy metal, "how is the blues connected to heavy metal" is a descent walk
    from the blues, and the model should not have to get that right to get an answer. Trying both is
    safe precisely because a proposal is built from the **edge**, never from the argument order: an edge
    is asserted in the direction the artifact stores it whichever way the traversal reached it, so a
    reversed query cannot produce a reversed influence claim.

    The chain it reports is therefore always descendant-first, matching claim orientation, regardless of
    which walk found it. ``phase-2-corpus-and-traversal.md`` A5: two hops is the deepest chain this
    corpus contains, and that is a published number rather than a hidden ceiling.
    """

    store: GraphStore
    name: str = field(default="trace_lineage", init=False)
    description: str = field(
        default=(
            "Trace the documented chain of influence between two genres, hop by hop. Give it two node "
            "ids from resolve_node, in either order. Returns an empty path when the graph holds no "
            "sourced chain between them: that means this graph cannot connect the two genres, not that "
            "they are unrelated. Do not bridge the gap yourself."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "from_id": {"type": "string", "description": "A node id from resolve_node."},
                "to_id": {"type": "string", "description": "The other node id from resolve_node."},
            },
            "required": ["from_id", "to_id"],
        }

    def __call__(self, **kwargs: Any) -> ToolResult:
        from_id, to_id = kwargs["from_id"], kwargs["to_id"]
        for node_id in (from_id, to_id):
            if self.store.get_node(node_id) is None:
                return ToolResult(
                    content={"error": f"unknown node: {node_id}. Use resolve_node first."},
                    is_error=True,
                )

        edges = self.store.path(from_id, to_id, Direction.INFLUENCED_BY)
        if not edges:
            # A descent walk starts at the ancestor, so its traversal order is claim order backwards.
            # Reversing here rather than at the end means the hops, the citations, the proposals and the
            # chain all read descendant-first, and the rest of this method needs no direction branch.
            edges = list(reversed(self.store.path(from_id, to_id, Direction.INFLUENCED)))

        if not edges:
            # A refusal, not an error. The model is told the graph cannot answer, and the deterministic
            # gate will approve nothing, so the refusal template runs rather than prose.
            return ToolResult(
                content={
                    "path": [],
                    "hops": 0,
                    "reason": "no sourced chain between these genres in either direction",
                },
                visited=(from_id, to_id),
            )

        # Read off the edges rather than off the arguments, so the chain states what the artifact says
        # rather than the order the question happened to be asked in.
        chain = (edges[0].subject_id, *(edge.object_id for edge in edges))

        return ToolResult(
            content={
                "path": [
                    {
                        "subject": self._label(edge.subject_id),
                        "predicate": edge.predicate,
                        "object": self._label(edge.object_id),
                    }
                    for edge in edges
                ],
                "hops": len(edges),
            },
            sources=tuple(edge.source_id for edge in edges),
            visited=chain,
            chain=chain,
            proposals=tuple(
                ClaimProposal(
                    subject_id=edge.subject_id,
                    predicate=edge.predicate,
                    object_id=edge.object_id,
                )
                for edge in edges
            ),
        )

    def _label(self, node_id: str) -> str:
        node = self.store.get_node(node_id)
        return node.label if node else node_id


@dataclass(frozen=True, slots=True)
class GetDescendants:
    """One hop along ``influenced_by`` in the **other** direction — what came out of this node.

    This closes a real gap rather than adding a convenience. ``Direction.INFLUENCED`` has been supported
    by the store since phase 2 and no registered tool exposed it, so "what came out of the blues?" was
    unanswerable except as a side effect of tracing between two *named* nodes — which requires already
    knowing the answer.

    **Orientation is read off the edge, never off the argument**, exactly as ``TraceLineage`` does. A
    descendant walk finds edges where this node is the *object*, so the proposal's subject is the
    descendant and its object is the node asked about. Building the proposal from ``edge`` rather than
    from ``node_id`` is what makes a descendant query incapable of emitting a backwards influence claim.
    """

    store: GraphStore
    name: str = field(default="get_descendants", init=False)
    description: str = field(
        default=(
            "List what came out of a genre or artist — the things this graph records as having been "
            "influenced BY it. This is the opposite direction from get_influences. Returns an empty "
            "list when the graph records nothing descending from that node. An empty list means this "
            "graph cannot answer the question; it does not mean nothing came out of it."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "A node id from resolve_node."}
            },
            "required": ["node_id"],
        }

    def __call__(self, **kwargs: Any) -> ToolResult:
        node_id = kwargs["node_id"]
        if self.store.get_node(node_id) is None:
            return ToolResult(
                content={"error": f"unknown node: {node_id}. Use resolve_node first."},
                is_error=True,
            )

        edges = self.store.neighbors(node_id, Direction.INFLUENCED)
        descendants = []
        for edge in edges:
            node = self.store.get_node(edge.subject_id)
            descendants.append(
                {
                    "node_id": edge.subject_id,
                    "label": node.label if node else edge.subject_id,
                    "predicate": edge.predicate,
                }
            )

        return ToolResult(
            content={"descendants": descendants, "count": len(descendants)},
            sources=tuple(edge.source_id for edge in edges),
            visited=(node_id, *(edge.subject_id for edge in edges)),
            # A fan-out, not a sequence. ``chain`` stays empty for the same reason it does in
            # ``GetInfluences``: several descendants of one node are not an ordered descent.
            proposals=tuple(
                ClaimProposal(
                    subject_id=edge.subject_id,
                    predicate=PREDICATE_INFLUENCED_BY,
                    object_id=edge.object_id,
                )
                for edge in edges
            ),
        )


@dataclass(frozen=True, slots=True)
class DescribeNode:
    """When and where, rather than out of what. **Emits no proposals.**

    No proposal, because no edge is involved. A proposal from here would carry no valid predicate, fail
    ``UNSUPPORTED_PREDICATE`` at the gate, and pollute the rejection stream that refusal accuracy is
    measured on.

    **What this tool returns can never reach prose**, and that is invariant 1 rather than an oversight.
    ``synthesize()`` sees only the approved claim set, and both synthesis prompts forbid dates, places
    and artists outright. These values inform the agent's *traversal reasoning* and feed the era/region
    slicing; putting dates into answers is a claim-model extension — new predicates, gated the same way
    — and is phase 6 at the earliest.

    ``inception_precision`` is rendered as a word beside the raw code because a decade-precision 1970
    printed as "1970" asserts a year Wikidata never claimed. That is the traceable-slides-into-correct
    failure in miniature, and ``graph/schema.py`` already warns about it on the field itself.
    """

    store: GraphStore
    name: str = field(default="describe_node", init=False)
    description: str = field(
        default=(
            "Get what the graph records ABOUT a node: whether it is a genre or an artist, when it "
            "began, how precise that date is, and which countries it is credited to. Use it to orient "
            "yourself before or during a traversal. It returns no influence relationships and supports "
            "no claims about influence — use get_influences or get_descendants for those. Any field "
            "may be null, and null means the graph does not record it."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "A node id from resolve_node."}
            },
            "required": ["node_id"],
        }

    def __call__(self, **kwargs: Any) -> ToolResult:
        node_id = kwargs["node_id"]
        node = self.store.get_node(node_id)
        if node is None:
            return ToolResult(
                content={"error": f"unknown node: {node_id}. Use resolve_node first."},
                is_error=True,
            )

        return ToolResult(
            content={
                "node_id": node.id,
                "label": node.label,
                "kind": node.kind,
                "inception_year": node.inception_year,
                "inception_precision": node.inception_precision,
                "inception_precision_label": _PRECISION_LABELS.get(node.inception_precision),
                "era": era_of(node.inception_year)
                if node.inception_year is not None
                else "unknown",
                "countries": list(node.countries),
            },
            sources=(node.source_id,),
            visited=(node.id,),
        )


@dataclass(frozen=True, slots=True)
class ResolveSource:
    """A source id turned into something a reader can actually go and check. **Emits no proposals.**

    This is what makes "grounded means provenance" visible in the product rather than only true in the
    code. A claim carries ``source_ids``; without this the reader sees an opaque statement URI.

    ``resolvable`` uses the same rule as ``claims.resolve_sources``: a Wikidata statement URI encodes
    the QID of the entity the statement belongs to, so the citation must name an entity this graph
    holds. A syntactically perfect URI pointing at an entity that is not here is **not** a citation for
    anything, and reporting it as one is exactly the plausible-looking fabrication the gate exists to
    catch.
    """

    store: GraphStore
    name: str = field(default="resolve_source", init=False)
    description: str = field(
        default=(
            "Turn a source id from a claim into a checkable citation: which entity the statement "
            "belongs to and the URL a reader can open to verify it. Use it when asked where something "
            "comes from or how a statement can be checked. Returns resolvable=false when the id does "
            "not name an entity in this graph, and an unresolvable source supports nothing."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "source_id": {
                    "type": "string",
                    "description": "A source id taken from a claim or a tool result.",
                }
            },
            "required": ["source_id"],
        }

    def __call__(self, **kwargs: Any) -> ToolResult:
        source_id = kwargs["source_id"]

        # DBpedia arrived at v0.7.0. A resource URI names an article rather than a QID, so unlike a
        # statement URI it cannot be *parsed* for the entity it belongs to -- resolving one needs a
        # reverse lookup from resource to node, and `GraphStore` exposes no way to scan nodes.
        #
        # **Reported as unresolved-by-this-tool rather than resolved-on-faith.** The gate DOES verify
        # these exactly, against `Node.dbpedia_resource`, so a DBpedia citation on an approved claim is
        # checked; what is missing is only this tool's ability to re-check it for a reader. Saying
        # `resolvable: True` here without performing the check would make the word mean something
        # weaker for DBpedia than for Wikidata, which is the failure this tool exists to prevent.
        # Widening `GraphStore` for it is a real design change and belongs in a step that owns the
        # seam -- recorded in KNOWN-GAPS, step 4.
        if source_id.startswith(DBPEDIA_RESOURCE_PREFIX):
            return ToolResult(
                content={
                    "source_id": source_id,
                    "resolvable": False,
                    "url": source_id,
                    # CC BY-SA 3.0 requires attribution and a link back; DATA-LICENSES.md is the
                    # full statement. The link is given even though the check could not be run.
                    "license": "CC BY-SA 3.0 (DBpedia)",
                    "reason": (
                        "a DBpedia resource URI names an article, not an entity id; this tool cannot "
                        "verify the alignment, though the gate did before approving the claim"
                    ),
                }
            )

        if not source_id.startswith(_WIKIDATA_STATEMENT_PREFIX):
            return ToolResult(
                content={
                    "source_id": source_id,
                    "resolvable": False,
                    "reason": "not a Wikidata statement URI or a DBpedia resource URI",
                }
            )

        entity_id = source_id.removeprefix(_WIKIDATA_STATEMENT_PREFIX).split("-", 1)[0]
        node = self.store.get_node(entity_id)
        if node is None:
            return ToolResult(
                content={
                    "source_id": source_id,
                    "entity_id": entity_id,
                    "resolvable": False,
                    "reason": "the statement names an entity this graph does not hold",
                }
            )

        return ToolResult(
            content={
                "source_id": source_id,
                "entity_id": entity_id,
                "label": node.label,
                "resolvable": True,
                "url": f"https://www.wikidata.org/wiki/{entity_id}",
                "retrieved_at": node.retrieved_at,
            },
            sources=(source_id,),
        )


@dataclass(frozen=True, slots=True)
class CorpusCoverage:
    """What this graph can speak about at all, in measured numbers. **Emits no proposals.**

    Directly serves the never-claim-coverage-you-do-not-have rule: the corpus skew is documented, and it
    has to be visible in the output rather than disclaimed in a footnote. An agent that can be *asked*
    what the corpus holds can say so in the answer.

    **This tool is the invariant-4 seam test, and it is registered last on purpose.** It takes no node
    id, returns no edges, emits no proposals, records nothing visited, and asserts no chain — a shape
    unlike every tool before it. Adding it changed zero lines of ``agent/loop.py``: the loop harvests
    ``proposals``, ``chain`` and ``visited`` generically and simply gets empty ones here. A loop that had
    assumed every result contributes to the claim set would have needed an edit, and that edit is the
    thing invariant 4 forbids.
    """

    store: GraphStore
    name: str = field(default="corpus_coverage", init=False)
    description: str = field(
        default=(
            "Report what this graph covers and what it does not: how many genres it holds, how many "
            "lack a date or a country, the spread across eras and countries, and how concentrated it "
            "is. Takes no arguments. Use it when asked what the graph knows, or when answering about a "
            "region or period the graph may cover thinly, so the gap can be stated rather than hidden."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {"type": "object", "properties": {}}

    def __call__(self, **kwargs: Any) -> ToolResult:
        return ToolResult(
            content={
                "artifact_version": self.store.artifact_version,
                **self.store.coverage.as_dict(),
            }
        )


def default_registry(store: GraphStore) -> ToolRegistry:
    """The seven tools as of v0.3.

    ``trace_lineage`` joined at phase 2 step 5 and the last four at phase 3 step 2, all by registration
    alone. The signature has not changed since the three-tool version, which is invariant 4 stated as a
    fact about this line rather than as an aspiration.
    """
    return ToolRegistry(
        [
            ResolveNode(store),
            GetInfluences(store),
            TraceLineage(store),
            GetDescendants(store),
            DescribeNode(store),
            ResolveSource(store),
            CorpusCoverage(store),
        ]
    )
