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
from itertools import pairwise
from typing import Any, Protocol, runtime_checkable

from musical_mycelium.agent.claims import ClaimProposal
from musical_mycelium.agent.llm import undelimit
from musical_mycelium.graph.coverage import (
    PRECISION_CENTURY,
    PRECISION_DECADE,
    PRECISION_YEAR,
    era_of,
)
from musical_mycelium.graph.memory import Offer, exact_matches, offer_candidates
from musical_mycelium.graph.schema import (
    DBPEDIA_RESOURCE_PREFIX,
    NODE_KIND_ARTIST,
    PREDICATE_INFLUENCED_BY,
    PREDICATE_STUDIED_WITH,
    Edge,
)
from musical_mycelium.graph.store import Direction, GraphStore

#: What ``get_teachers`` and ``get_students`` walk, and nothing else. Added at phase 7.6 step 7.
TEACHING_ONLY = frozenset({PREDICATE_STUDIED_WITH})

#: What ``trace_teaching_lineage`` walks: teaching **and** influence, his decision D4 (2026-09-11). Sound
#: because both run the same way in time (the later person learned from, or was shaped by, the earlier
#: one), which membership does not. Deliberately its own constant rather than
#: ``claims.ALLOWED_PREDICATES``: if the gate ever admits a third predicate, this walk must not quietly
#: start crossing it.
LINEAGE_PREDICATES = frozenset({PREDICATE_INFLUENCED_BY, PREDICATE_STUDIED_WITH})

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
    #: Choices to put in front of a **person** when this call resolved nothing. *(Phase 7.7 step 3,
    #: D2.)* Generic exactly as ``visited`` and ``chain`` are generic: the loop harvests this field
    #: without learning which tool sets it, which is what keeps invariant 4 intact while a refusal
    #: gains a way forward. A loop that special-cased ``resolve_node`` would have broken the seam this
    #: project is built on.
    #:
    #: **An offer is never a resolution and never a claim.** It carries no ``ClaimProposal``, it goes
    #: nowhere near the gate, and nothing in it can be narrated: ``offer_candidates`` reaches nodes by
    #: alias, and 37 aliases in this corpus equal a *different* node's label. The person chooses, and
    #: the choice is re-asked as an ordinary query that resolves by exact label like any other.
    offers: tuple[Offer, ...] = ()
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
        ``<data>Q483352</data>`` to a tool that only knows ``Q483352``. One call here covers every
        registered tool and knows nothing about any of them, so the seam is intact.
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


def _offer_for(store: GraphStore, name: str) -> tuple[Offer, ...]:
    """The offer for an unresolved name, or nothing when there is nothing honest to offer.

    One place rather than two, because both refusal paths in ``ResolveNode`` need the same rule and a
    second copy is how they start disagreeing. The rule: emit when **any** candidate was found.

    ``total == 0`` covers a genuinely unknown name and a query D5 rejected as a single character, and
    an empty offer beside a refusal is noise a person has to read and dismiss. ``total`` over the D4
    cap is the opposite — it emits, with no candidates and the true count, because "34 genres contain
    the word metal, say more" is a real answer to what the person asked, and silence there would be a
    worse one.
    """
    offer = offer_candidates(store, name)
    return (offer,) if offer.total else ()


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
            "'artist': influence and teaching only ever run between two nodes of the SAME kind, so "
            "never relate a genre to an artist."
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
        # Offers are computed on both refusal paths and on neither success path, and the ``content``
        # the model sees is **byte-identical** to what it saw before this existed. The model must not
        # be able to spend a turn "choosing" a candidate — that is the guess this phase exists to
        # prevent — so the offer rides on the machinery field, addressed to the person, and the three
        # refusal reasons below are untouched.
        if not candidates:
            return ToolResult(
                content={"node_id": None, "reason": "not in this graph"},
                offers=_offer_for(self.store, name),
            )

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
                },
                offers=_offer_for(self.store, name),
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

    **It still returns influence only, and proposes ``influenced_by`` only.** The last sentence of the
    description is his decision D5 (2026-09-11): teaching is often a strong influence, so an influence
    question about an artist should also ask for teachers, and report them **as teachers**. That is a
    change to what the model is told, not to what this tool returns: the two answers stay two lists,
    and ``synthesize`` narrates them under separate headings.
    """

    store: GraphStore
    name: str = field(default="get_influences", init=False)
    description: str = field(
        default=(
            "List the documented influences on a genre — what it came out of. Returns an empty list "
            "when the graph has no sourced influences for that node. An empty list means this graph "
            "cannot answer the question; it does not mean the genre had no influences. For an "
            "artist, teachers are often a strong influence too: also call get_teachers, and report "
            "what it returns as teachers, never as influences."
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
class GetTeachers:
    """Who an artist studied with: one hop along ``studied_with``, from the student's side.

    *(Added 2026-09-11, phase 7.6 step 7, by registration alone. The mirror of ``GetInfluences``.)*

    **Trap 17, and why this class owns the call.** ``Direction`` is named for influence:
    ``INFLUENCED_BY`` means "walk from the subject to the object". A teaching edge is stored *student*
    ``studied_with`` *teacher*, so a student's teachers are ``neighbors(student, INFLUENCED_BY,
    predicates=TEACHING_ONLY)``, which reads wrong and would be written wrong at a call site. This class
    and ``GetStudents`` are the only places that make it, and a test pins that they are not swapped.

    Proposals carry ``studied_with`` and nothing else, built from the edge as every tool here does.
    """

    store: GraphStore
    name: str = field(default="get_teachers", init=False)
    description: str = field(
        default=(
            "List who an artist studied with: their documented teachers. This is teaching, not "
            "influence: report each one as someone the artist studied with, never as an influence. "
            "Returns an empty list when the graph records no teachers for that artist. An empty list "
            "means this graph cannot answer the question; it does not mean the artist had no teachers."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "An artist node id from resolve_node."}
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

        edges = self.store.neighbors(node_id, Direction.INFLUENCED_BY, predicates=TEACHING_ONLY)
        return ToolResult(
            content={
                "teachers": [_listed(self.store, edge.object_id, edge) for edge in edges],
                "count": len(edges),
            },
            sources=tuple(edge.source_id for edge in edges),
            visited=(node_id, *(edge.object_id for edge in edges)),
            # A fan-out, not a sequence, so no ``chain``: several teachers are not an ordered descent.
            proposals=_teaching_proposals(edges),
        )


@dataclass(frozen=True, slots=True)
class GetStudents:
    """Who studied with an artist: one hop along ``studied_with``, from the teacher's side.

    The mirror of ``GetDescendants``, with the same orientation rule: the walk finds edges where the
    queried artist is the **object**, so each proposal's subject is the student, read off the edge and
    never off ``node_id``. Built the other way, "who studied with Haydn" would propose that Haydn
    studied with each of his students.
    """

    store: GraphStore
    name: str = field(default="get_students", init=False)
    description: str = field(
        default=(
            "List who studied with an artist: their documented students. This is teaching, not "
            "influence: report each one as someone who studied with the artist, never as someone "
            "the artist influenced. Returns an empty list when the graph records no students for "
            "that artist. An empty list means this graph cannot answer the question; it does not "
            "mean the artist had no students."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "node_id": {"type": "string", "description": "An artist node id from resolve_node."}
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

        edges = self.store.neighbors(node_id, Direction.INFLUENCED, predicates=TEACHING_ONLY)
        return ToolResult(
            content={
                "students": [_listed(self.store, edge.subject_id, edge) for edge in edges],
                "count": len(edges),
            },
            sources=tuple(edge.source_id for edge in edges),
            visited=(node_id, *(edge.subject_id for edge in edges)),
            proposals=_teaching_proposals(edges),
        )


@dataclass(frozen=True, slots=True)
class TraceTeachingLineage:
    """The sourced chain between two artists through teachers **and** influences, with typed hops.

    *(Added 2026-09-11, phase 7.6 step 7. D4 and D5 of the IMPLEMENTATION doc.)*

    **``trace_lineage`` is not touched, deliberately.** It stays influence-only so that no gold path
    case can silently acquire a shorter route through a teaching hop. This is the tool that walks both.

    **Every hop is typed, and a hop is never given one predicate where the corpus holds two.** The walk
    finds a shortest route; each consecutive pair on it is then read back off the artifact under both
    predicates, and **every** edge between that pair is proposed. Beethoven studied with Haydn *and* was
    influenced by him; proposing whichever edge the walk happened to cross first would narrate half of
    that and drop the other half by accident of artifact order. Synthesis reads each hop's predicates
    off the claims the gate approved, never off this tool.

    Artists only. Teaching never touches a genre, so a genre-to-genre walk here would be
    ``trace_lineage`` under another name with a looser description; it is refused with a pointer
    instead. Orientation follows ``TraceLineage`` exactly: both walk directions are tried, and the chain
    is read off the edges, descendant-first, whichever way the arguments were given.
    """

    store: GraphStore
    name: str = field(default="trace_teaching_lineage", init=False)
    description: str = field(
        default=(
            "Trace the documented chain between two artists through teachers and influences, hop by "
            "hop. Each hop is 'studied with', 'influenced by', or both, and the result says which. Give "
            "it two artist node ids from resolve_node, in either order. Report every hop with its own "
            "relationship: never describe a teaching hop as influence, and never call the whole chain "
            "a line of influence. Returns an empty path when the graph holds no sourced chain between "
            "them: that means this graph cannot connect the two, not that they are unrelated. Do not "
            "bridge the gap yourself. For two genres, use trace_lineage."
        ),
        init=False,
    )

    def input_schema(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "from_id": {
                    "type": "string",
                    "description": "An artist node id from resolve_node.",
                },
                "to_id": {"type": "string", "description": "The other artist node id."},
            },
            "required": ["from_id", "to_id"],
        }

    def __call__(self, **kwargs: Any) -> ToolResult:
        from_id, to_id = kwargs["from_id"], kwargs["to_id"]
        for node_id in (from_id, to_id):
            node = self.store.get_node(node_id)
            if node is None:
                return ToolResult(
                    content={"error": f"unknown node: {node_id}. Use resolve_node first."},
                    is_error=True,
                )
            if node.kind != NODE_KIND_ARTIST:
                return ToolResult(
                    content={
                        "error": (
                            f"{node.label} is a {node.kind}. Teaching runs only between artists; "
                            f"for two genres, use trace_lineage."
                        )
                    },
                    is_error=True,
                )

        walked = self.store.path(
            from_id, to_id, Direction.INFLUENCED_BY, predicates=LINEAGE_PREDICATES
        )
        if not walked:
            walked = list(
                reversed(
                    self.store.path(
                        from_id, to_id, Direction.INFLUENCED, predicates=LINEAGE_PREDICATES
                    )
                )
            )

        if not walked:
            return ToolResult(
                content={
                    "path": [],
                    "hops": 0,
                    "reason": "no sourced chain between these artists in either direction",
                },
                visited=(from_id, to_id),
            )

        chain = (walked[0].subject_id, *(edge.object_id for edge in walked))
        hops = [self._hop_edges(subject, obj) for subject, obj in pairwise(chain)]
        edges = [edge for hop in hops for edge in hop]

        return ToolResult(
            content={
                "path": [
                    {
                        "subject": _label(self.store, hop[0].subject_id),
                        "predicates": [edge.predicate for edge in hop],
                        "object": _label(self.store, hop[0].object_id),
                    }
                    for hop in hops
                ],
                "hops": len(hops),
            },
            sources=tuple(edge.source_id for edge in edges),
            visited=chain,
            chain=chain,
            proposals=tuple(
                ClaimProposal(
                    subject_id=edge.subject_id, predicate=edge.predicate, object_id=edge.object_id
                )
                for edge in edges
            ),
        )

    def _hop_edges(self, subject_id: str, object_id: str) -> list[Edge]:
        """Every lineage edge from ``subject_id`` to ``object_id``, sorted by predicate so the order
        does not depend on the artifact's. Never empty: the walk crossed at least one of them."""
        return sorted(
            (
                edge
                for edge in self.store.neighbors(
                    subject_id, Direction.INFLUENCED_BY, predicates=LINEAGE_PREDICATES
                )
                if edge.object_id == object_id
            ),
            key=lambda edge: edge.predicate,
        )


def _listed(store: GraphStore, node_id: str, edge: Edge) -> dict[str, str]:
    """One entry of a fan-out, in the shape ``GetInfluences`` and ``GetDescendants`` already return."""
    return {"node_id": node_id, "label": _label(store, node_id), "predicate": edge.predicate}


def _label(store: GraphStore, node_id: str) -> str:
    node = store.get_node(node_id)
    return node.label if node else node_id


def _teaching_proposals(edges: list[Edge]) -> tuple[ClaimProposal, ...]:
    """``studied_with`` proposals, oriented by the edge. The predicate is stated rather than copied so
    a teaching tool cannot propose anything else even if a caller widened its walk by mistake."""
    return tuple(
        ClaimProposal(
            subject_id=edge.subject_id, predicate=PREDICATE_STUDIED_WITH, object_id=edge.object_id
        )
        for edge in edges
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
        # reverse lookup from resource to node.
        #
        # **RESOLVED 2026-09-07, phase 6.5 step 4.** From v0.7.0 until today this branch returned
        # `resolvable: False` with the reason "this tool cannot verify the alignment", which was honest
        # and was a weaker guarantee for half the corpus than for the other half -- 624 of 1,479 nodes
        # carry a DBpedia resource. `GraphStore.node_by_resource` (step 1) is the lookup that was
        # missing; the check now performed here is the same one `claims.resolve_sources` runs before
        # approving, against `Node.dbpedia_resource`, so "resolvable" finally means one thing across
        # both sources rather than two things depending on which source a claim happened to cite.
        if source_id.startswith(DBPEDIA_RESOURCE_PREFIX):
            # CC BY-SA 3.0 requires attribution and a link back; DATA-LICENSES.md is the full
            # statement. Carried on both outcomes -- a URI that resolves to nothing here is still a
            # DBpedia URI, and the attribution is not conditional on the lookup succeeding.
            node = self.store.node_by_resource(source_id)
            if node is None:
                return ToolResult(
                    content={
                        "source_id": source_id,
                        "resolvable": False,
                        "url": source_id,
                        "license": "CC BY-SA 3.0 (DBpedia)",
                        "reason": (
                            "no node in this graph is aligned to that DBpedia resource, so it is not "
                            "a citation for anything here"
                        ),
                    }
                )
            return ToolResult(
                content={
                    "source_id": source_id,
                    "resolvable": True,
                    "entity_id": node.id,
                    "label": node.label,
                    "kind": node.kind,
                    "url": source_id,
                    "license": "CC BY-SA 3.0 (DBpedia)",
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
    """The ten tools as of phase 7.6 (product v0.9).

    ``trace_lineage`` joined at phase 2 step 5, the next four at phase 3 step 2, and the three teaching
    tools at phase 7.6 step 7, all by registration alone. The signature has not changed since the
    three-tool version, which is invariant 4 stated as a fact about this line rather than as an
    aspiration. ``corpus_coverage`` stays last on purpose; see its docstring.
    """
    return ToolRegistry(
        [
            ResolveNode(store),
            GetInfluences(store),
            TraceLineage(store),
            GetDescendants(store),
            GetTeachers(store),
            GetStudents(store),
            TraceTeachingLineage(store),
            DescribeNode(store),
            ResolveSource(store),
            CorpusCoverage(store),
        ]
    )
