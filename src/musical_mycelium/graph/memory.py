"""``InMemoryGraphStore`` — the v0.1 backend. A few dicts over a JSON file in the container image.

At 28 nodes this is obviously enough; the reason to write it deliberately anyway is that it is the thing
the ``GraphStore`` protocol is measured against, and the indexes it builds are the ones a bigger backend
will have to reproduce.

**Loading is cached, and meant to happen during the Lambda INIT phase.** ``default_store()`` memoises, so
the JSON is parsed once per container rather than once per request. ``api.app`` calls it at module scope
so the cost lands in INIT, before the first invocation, where it does not show up in response latency.
The cache is a function-level memo rather than an import-time side effect so that importing this module
never does file I/O — an import that can fail on a missing file is a bad cold start and an awful test.

**The artifact is verified on load.** A sha256 over a few KB is free, and a corpus that has drifted from
its manifest should fail loudly at boot rather than quietly serve edges nobody signed off on. That is the
pin actually meaning something.
"""

from __future__ import annotations

import unicodedata
from collections import defaultdict, deque
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass
from functools import cached_property, lru_cache
from pathlib import Path

from musical_mycelium.graph.corroboration import ContestedPair, contested_pairs
from musical_mycelium.graph.corroboration import summary as corroboration_summary
from musical_mycelium.graph.coverage import Coverage
from musical_mycelium.graph.coverage import analyse as analyse_coverage
from musical_mycelium.graph.schema import INFLUENCE_ONLY, Artifact, Edge, Manifest, Node, verify
from musical_mycelium.graph.store import Direction, GraphStore
from musical_mycelium.graph.structure import GraphStructure, analyse

#: The pinned version. A **constant in code**, never "latest" — that is what stops a corpus change from
#: silently invalidating a benchmark (``.claude/rules/evals.md``).
PINNED_ARTIFACT_VERSION = "0.10.0"

#: Leading words to ignore when resolving a typed name. Exactly one, deliberately: "the blues" must
#: resolve to ``blues`` (gold case 5 is phrased that way) and that is the whole of the ambition.
#:
#: ``"a "`` and ``"an "`` were here and were removed on 2026-08-02 — **"a cappella" is a genre**, and
#: stripping the "a" turns it into "cappella", which matches nothing. No plausible query starts with
#: "a" or "an" as an article, so the rule bought nothing and broke a real name. Aggressive normalisation
#: is how a resolver starts guessing, and a confident wrong match is worse here than no match at all.
_LEADING_ARTICLES = ("the ",)


def normalise(text: str) -> str:
    """Fold a human-typed name toward a label for comparison.

    Case, accents, hyphens and surrounding punctuation only. ``hip-hop`` and ``Hip Hop`` are the same
    genre; ``blues`` and ``blues rock`` are not, and nothing here will conflate them.
    """
    folded = unicodedata.normalize("NFKD", text.casefold())
    folded = "".join(ch for ch in folded if not unicodedata.combining(ch))
    folded = "".join(" " if ch in "-_/" else ch for ch in folded)
    folded = "".join(ch for ch in folded if ch.isalnum() or ch.isspace())
    folded = " ".join(folded.split())
    for article in _LEADING_ARTICLES:
        if folded.startswith(article):
            folded = folded[len(article) :]
            break
    return folded


#: Wikidata labels a great many genres ``"<name> music"`` — 32 of the 169 nodes in v0.2.0, including
#: ``heavy metal music``, ``classical music`` and ``electronic music``. Nobody types the suffix, so
#: exact matching alone made **one node in five unreachable by its own name**, and the SPEC's signature
#: query "How is the blues connected to heavy metal?" refused on it. Found 2026-08-05 by running it.
#:
#: This is not a step toward fuzzy matching. It is the same category of rule as stripping a leading
#: "the": a documented, deterministic fold, applied to both sides, and it is checked for ambiguity by
#: the caller — two nodes agreeing under it is a refusal, not a coin flip. It strips **zero** collisions
#: out of the v0.2.0 corpus, verified before it was written; a future corpus that collides must refuse
#: rather than pick.
_OPTIONAL_SUFFIXES = (" music",)


def label_key(text: str) -> str:
    """``normalise``, with a trailing "music" made optional. See ``_OPTIONAL_SUFFIXES``.

    A node labelled exactly "music" keeps its key, because folding it to the empty string would make it
    match everything — the failure mode this whole module is written against.
    """
    folded = normalise(text)
    for suffix in _OPTIONAL_SUFFIXES:
        if folded.endswith(suffix) and folded != suffix.strip():
            return folded[: -len(suffix)]
    return folded


def exact_matches(candidates: Iterable[Node], name: str) -> list[Node]:
    """Those candidates whose label equals ``name`` under ``label_key``.

    The whole of this project's resolution rule, in one place. Callers decide what to do with the
    count, and the counts mean different things: **zero is a near miss, one resolves, and two is
    ambiguity** — which is a refusal too, because if the "music" fold ever makes two nodes equally good
    the honest answer is to ask rather than take the first.

    Extracted from ``ResolveNode`` at phase 3 step 3b, when the loop needed the same rule to turn a
    model-asserted premise into a gateable proposal. A second copy of it is how a tool and the loop
    start disagreeing about what "the blues" means, and a premise resolved by a laxer rule than the one
    the model was answered with would correct a question the user did not ask.
    """
    key = label_key(name)
    return [node for node in candidates if label_key(node.label) == key]


#: D4: 25 candidates shown, **all or nothing**. At or under the cap every candidate is shown; over it,
#: none are, and the count is stated with a request for more of the name. Truncating a longer list by
#: label length is ranking under another name, and the scope doc forbids ranking; an honest count plus
#: an ask is not ranking. Measured effect on this corpus: `bach` shows all 14, `black` 9, `r&b` 6,
#: `mozart` 5; `metal` (34), `john` (42) and `music` (235) show a count and an ask.
OFFER_CAP = 25


@dataclass(frozen=True, slots=True)
class Candidate:
    """One offered choice, carrying why it was offered. D7.

    ``via`` is ``"label"`` or ``"alias"``, and ``alias`` holds the alias text exactly as the source
    wrote it when ``via == "alias"``. Timbaland appearing under "mozart" is then legible — it is there
    because Wikidata lists "Mozart Timadeas" — rather than mysterious, which is the honest way to
    present a noisy source.
    """

    node_id: str
    label: str
    kind: str
    via: str
    alias: str | None = None


@dataclass(frozen=True, slots=True)
class Offer:
    """The candidates for one typed term, plus the arithmetic a person needs to trust the list.

    ``total`` is always the true count of candidates found. ``shown`` is how many are in
    ``candidates`` — equal to ``total`` at or under :data:`OFFER_CAP`, and ``0`` above it. Both are
    stated because a truncated list that does not say it was truncated is a quiet lie about how
    ambiguous the query was.
    """

    term: str
    candidates: tuple[Candidate, ...]
    total: int
    shown: int

    @property
    def over_cap(self) -> bool:
        return self.total > OFFER_CAP


def offer_candidates(store: InMemoryGraphStore, name: str) -> Offer:
    """Every node a typed name could plausibly mean, as choices for a person — never a resolution.

    Three ways in, and all three are whole-word (``_contains_words``, D10 — one whole-word rule in the
    codebase, never a second copy):

    1. **Label**, reusing ``search`` so the offer list and the resolver agree about what a label match
       even is, and so exact matches keep leading the list.
    2. **Alias**, through ``alias_index``. This is the new reach, and it is the reason this function
       returns offers rather than resolutions.
    3. **The ``label_key`` "music" fold** — his decision, 2026-09-12. ``label_key("electro music")`` is
       ``electro`` and a node is labelled ``electro``, but ``search`` finds nothing for it, because
       ``_contains_words`` needs the query's words inside a label and "electro" does not contain
       "electro music". So the fold was installed at the ``exact_matches`` filter and never at the
       index, and a complete, correctly folded name refused. **3,500 of 3,628 nodes are unreachable by
       ``"<label> music"`` for that reason.** Offering the fold's target fixes the dead end without
       widening what resolves: resolution still needs one exact label match, and this path produces a
       choice. The alternative, folding at the index, would have made ``big band music`` ambiguous
       against ``big band`` and was rejected as a one-way door for one node's benefit.

    **D5, and it is the first thing this does:** a query whose every token is a single character
    matches nothing. That kills the ``x`` path — "x" reaches "F. X. Mozart", DMX, NOFX and "X Tina"
    through tokenised initials — and it costs nothing real, because no musician or genre in this corpus
    is found by one letter. ``r&b`` survives it: ``normalise`` makes that ``rb``, two characters.
    """
    tokens = normalise(name).split()
    if not tokens or all(len(token) <= 1 for token in tokens):
        return Offer(term=name, candidates=(), total=0, shown=0)

    found: dict[str, Candidate] = {}
    for node in store.search(name):
        found[node.id] = Candidate(node.id, node.label, node.kind, via="label")

    key = label_key(name)
    if key != normalise(name):
        for node in store.search(key):
            if node.id not in found and label_key(node.label) == key:
                found[node.id] = Candidate(node.id, node.label, node.kind, via="label")

    query = normalise(name)
    aliased: list[Candidate] = [
        Candidate(node.id, node.label, node.kind, via="alias", alias=alias)
        for alias_key, holders in store.alias_index().items()
        if _contains_words(alias_key, query)
        for node, alias in holders
        if node.id not in found
    ]
    # Deterministic and not a ranking: label order only, so two runs never disagree. The label bucket
    # keeps ``search``'s order ahead of it, which is what preserves "exact match first".
    aliased.sort(key=lambda candidate: (len(candidate.label), candidate.label, candidate.node_id))
    for candidate in aliased:
        found.setdefault(candidate.node_id, candidate)

    candidates = tuple(found.values())
    total = len(candidates)
    if total > OFFER_CAP:
        return Offer(term=name, candidates=(), total=total, shown=0)
    return Offer(term=name, candidates=candidates, total=total, shown=total)


def resolve_exact(store: GraphStore, name: str) -> Node | None:
    """The one node ``name`` resolves to, or ``None`` for both no match and an ambiguous one.

    The ``did_you_mean`` reporting stays in ``ResolveNode``, because only a tool answering a model
    needs it; a caller that just needs an id needs the id or nothing.
    """
    matches = exact_matches(store.search(name), name)
    return matches[0] if len(matches) == 1 else None


class InMemoryGraphStore:
    """A ``GraphStore`` over an in-memory artifact. Satisfies the protocol structurally, not by
    inheritance, which is the point of using ``Protocol`` in the first place."""

    def __init__(self, artifact: Artifact, manifest: Manifest | None = None) -> None:
        self._artifact = artifact
        self._manifest = manifest
        self._nodes: dict[str, Node] = {node.id: node for node in artifact.nodes}

        by_subject: dict[str, list[Edge]] = defaultdict(list)
        by_object: dict[str, list[Edge]] = defaultdict(list)
        for edge in artifact.edges:
            by_subject[edge.subject_id].append(edge)
            by_object[edge.object_id].append(edge)
        self._by_subject = dict(by_subject)
        self._by_object = dict(by_object)

        self._by_name: dict[str, list[Node]] = defaultdict(list)
        for node in artifact.nodes:
            self._by_name[normalise(node.label)].append(node)

        # **A SECOND dict, deliberately not merged into ``_by_name``** — phase 7.7 step 2, trap 10.
        # ``_by_name`` feeds ``search``'s exact bucket, and ``exact_matches`` counts zero/one/two off
        # that list to decide resolve-versus-ambiguous. Merging aliases in would change that arithmetic
        # and turn 2,469 alias strings into silent resolutions, which is the opposite of this phase.
        #
        # 37 aliases in this corpus equal a *different* node's label (``heavy metal`` is an alias of
        # ``traditional heavy metal``) and 27 alias keys are claimed by two or more nodes, so an alias
        # may only ever produce an **offer** a person chooses. Keyed on ``normalise`` rather than
        # ``label_key``, matching ``_by_name``: the two answer the same question differently (27 versus
        # 32 collisions), and an index that mixes them is an index nobody can reason about.
        by_alias: dict[str, list[tuple[Node, str]]] = defaultdict(list)
        for node in artifact.nodes:
            for alias in node.aliases:
                by_alias[normalise(alias)].append((node, alias))
        self._by_alias = dict(by_alias)

        # DBpedia resource -> node, for `node_by_resource`. Built here rather than scanned per call:
        # a resolve_source tool call would otherwise walk 1,479 nodes to answer one citation.
        #
        # **A resource claimed by more than one node is EXCLUDED rather than resolved to whichever
        # came first.** Measured at v0.7.1 there are none -- 624 aligned nodes and 624 distinct
        # resources -- but that is a property of one artifact and not a guarantee, and the failure
        # would be silent: a citation resolving to an arbitrary one of two entities looks exactly like
        # a citation that resolved. Absence is checkable; a coin flip is not.
        by_resource: dict[str, Node | None] = {}
        for node in artifact.nodes:
            if not node.dbpedia_resource:
                continue
            # None marks "claimed twice", so a later third claimant cannot revive it.
            by_resource[node.dbpedia_resource] = (
                None if node.dbpedia_resource in by_resource else node
            )
        self._by_resource: dict[str, Node] = {
            resource: node for resource, node in by_resource.items() if node is not None
        }

    # --- construction ---------------------------------------------------------------------------

    @classmethod
    def from_directory(cls, directory: Path, *, check_hash: bool = True) -> InMemoryGraphStore:
        manifest = verify(directory) if check_hash else None
        return cls(Artifact.load(directory), manifest)

    # --- GraphStore -----------------------------------------------------------------------------

    @property
    def artifact_version(self) -> str:
        return self._manifest.artifact_version if self._manifest else "unpinned"

    def get_node(self, node_id: str) -> Node | None:
        return self._nodes.get(node_id)

    def neighbors(
        self,
        node_id: str,
        direction: Direction = Direction.INFLUENCED_BY,
        *,
        predicates: frozenset[str] = INFLUENCE_ONLY,
    ) -> list[Edge]:
        index = self._by_subject if direction is Direction.INFLUENCED_BY else self._by_object
        return [edge for edge in index.get(node_id, ()) if edge.predicate in predicates]

    def search(self, text: str) -> list[Node]:
        """Exact normalised match first, then whole-word substring matches, shortest label first.

        The ordering matters more than it looks. A substring search for ``blues`` also finds
        ``blues rock`` and ``soul blues``; putting the exact match first and sorting the rest by label
        length keeps the resolver from preferring a longer, more specific genre than the one asked for.
        """
        query = normalise(text)
        if not query:
            return []

        exact = list(self._by_name.get(query, ()))
        seen = {node.id for node in exact}

        partial = [
            node
            for name, nodes in self._by_name.items()
            for node in nodes
            if node.id not in seen and _contains_words(name, query)
        ]
        partial.sort(key=lambda node: (len(node.label), node.label))
        return exact + partial

    def path(
        self,
        start_id: str,
        end_id: str,
        direction: Direction = Direction.INFLUENCED_BY,
        *,
        predicates: frozenset[str] = INFLUENCE_ONLY,
    ) -> list[Edge]:
        """Breadth-first, so the chain returned is the **shortest** sourced one.

        Shortest rather than longest or prettiest because every extra hop is another edge the narrative
        has to defend, and a longer chain between the same two genres is strictly more to get wrong.

        Ties are broken by artifact order, which is stable within a pinned version and says nothing
        across versions. That is the honest guarantee: the same query against the same pinned artifact
        returns the same chain, and a re-ingest may legitimately return a different equally-short one.

        The traversal is cycle-safe by construction rather than by assumption. The corpus contains a
        genuine two-edge cycle at v0.2 — ``post-rock`` and ``shoegaze`` each cite the other under P737 —
        and mutual influence is a real thing for a source to claim, so the graph is not a DAG and must
        never be treated as one. The ``seen`` set is what makes that a non-event.
        """
        if start_id not in self._nodes or end_id not in self._nodes or start_id == end_id:
            return []

        if direction is Direction.INFLUENCED_BY:
            index = self._by_subject
            forward, backward = _object_of, _subject_of
        else:
            index = self._by_object
            forward, backward = _subject_of, _object_of

        # The edge each node was first reached by. First is shortest, because BFS.
        arrived_by: dict[str, Edge] = {}
        seen = {start_id}
        queue: deque[str] = deque([start_id])

        while queue:
            current = queue.popleft()
            for edge in index.get(current, ()):
                if edge.predicate not in predicates:
                    continue
                nxt = forward(edge)
                if nxt in seen:
                    continue
                seen.add(nxt)
                arrived_by[nxt] = edge
                if nxt == end_id:
                    return _rebuild(arrived_by, start_id, end_id, backward)
                queue.append(nxt)
        return []

    # --- structure ------------------------------------------------------------------------------

    @cached_property
    def structure(self) -> GraphStructure:
        """Connectivity of the loaded corpus, computed once per store.

        Computed rather than read from the manifest even when the manifest carries it, so the number the
        product displays is a property of the corpus in hand rather than of whatever was true when
        someone last ran a build. ``structure`` is the connectivity half of the displayed coverage
        metric; ``verification_counts`` is the confidence half.
        """
        return analyse(self._artifact)

    @cached_property
    def coverage(self) -> Coverage:
        """Era and region coverage of the loaded corpus, computed once per store.

        Recomputed rather than read from the manifest for the same reason ``structure`` is: the number
        the product displays should be a property of the corpus in hand. This is the third honest half —
        confidence (``verification_counts``), connectivity (``structure``), and **what the corpus can
        speak about at all**. DoD #7 requires it to be a recorded quantity rather than a disclaimer.
        """
        return analyse_coverage(self._artifact)

    @cached_property
    def corroboration(self) -> dict[str, int]:
        """Whether a SECOND source agrees, and where two sources disagree.

        The fourth honest half, and the one that did not exist before artifact v0.7.0. ``structure``
        says what is reachable, ``coverage`` what the corpus can speak about, ``verification_counts``
        how hard **one** source was checked -- and this says whether anything else agrees with it.

        **``verification`` and this are different guarantees and must never be collapsed.** A
        corroborated ``PROSE_AUTO`` edge is not thereby a ``HAND`` edge. Reading a verification tier
        as corroboration is reading the opposite of the truth, and this project has already corrected
        three files once for blurring exactly that.

        Reports ``reciprocal_pairs`` and ``contested_pairs`` together, never one alone: a reciprocal
        pair is two edges pointing both ways, a contested pair is two edges pointing both ways **from
        different sources**, and at v0.7.1 that is 6 against 2. The loose reading overcounts by 3x.
        """
        return corroboration_summary(self._artifact)

    @cached_property
    def contested(self) -> tuple[ContestedPair, ...]:
        """The pairs two different sources disagree about. Two at artifact v0.7.1.

        **Concrete-only, and deliberately not on the ``GraphStore`` protocol.** The API and the
        coverage panel state a corpus-wide count; the agent asks about one pair at a time and reaches
        it through ``contested_between``. See that method for why the whole set is the wrong shape to
        put in front of a model.
        """
        return contested_pairs(self._artifact)

    @cached_property
    def _contested_index(self) -> dict[tuple[str, str], ContestedPair]:
        """Canonical ``(a, b)`` -> pair, computed once. ``ContestedPair`` already orders its two node
        ids, so one key per pair is enough and a lookup needs no second try."""
        return {(pair.a, pair.b): pair for pair in self.contested}

    def contested_between(self, a_id: str, b_id: str) -> ContestedPair | None:
        """See ``GraphStore.contested_between``. Order-independent, and derived, never stamped."""
        return self._contested_index.get((a_id, b_id) if a_id < b_id else (b_id, a_id))

    def alias_index(self) -> Mapping[str, list[tuple[Node, str]]]:
        """Normalised alias -> the nodes holding it, with the alias text as written.

        Read-only by contract and read by ``offer_candidates`` alone. Nothing on the resolution path
        may consult this: ``search`` and ``exact_matches`` see labels only, which is what makes "an
        alias can never resolve anything" a property of the code's shape rather than of a prompt.
        """
        return self._by_alias

    def node_by_resource(self, resource: str) -> Node | None:
        """See ``GraphStore.node_by_resource``. Index built at load; ambiguity resolves to ``None``."""
        return self._by_resource.get(resource)

    # --- convenience ----------------------------------------------------------------------------

    def __len__(self) -> int:
        return len(self._nodes)

    @property
    def edge_count(self) -> int:
        """Public because coverage is a displayed metric, not a debugging aid — the API states the
        corpus size on the screen rather than letting a visitor assume it (``04`` 4.5)."""
        return len(self._artifact.edges)

    @property
    def verification_counts(self) -> dict[str, int]:
        """How many edges a human read, and how many only cleared the automated check.

        Displayed for the same reason ``edge_count`` is, and it is the more honest of the two. A
        corpus that is mostly machine-verified is noisier per edge than one that is not, and stating
        the split is what keeps "grounded" from being read as "correct" (``CLAUDE.md``).

        Read from the artifact rather than the manifest so an unpinned store still answers.
        """
        return self._artifact.verification_counts()

    def __repr__(self) -> str:
        return (
            f"InMemoryGraphStore(version={self.artifact_version!r}, "
            f"nodes={len(self._nodes)}, edges={len(self._artifact.edges)})"
        )


def _object_of(edge: Edge) -> str:
    return edge.object_id


def _subject_of(edge: Edge) -> str:
    return edge.subject_id


def _rebuild(
    arrived_by: dict[str, Edge],
    start_id: str,
    end_id: str,
    backward: Callable[[Edge], str],
) -> list[Edge]:
    """Walk the breadcrumb trail back from ``end_id`` and hand it back pointing forwards.

    ``backward`` is the accessor for whichever end of an edge the traversal came *from*, which is the
    opposite end from the one it walked *to*. Getting those two the same way round is the one place this
    function can silently produce a chain that looks plausible and is wrong, so they are passed in from
    the single branch that already decided the direction rather than re-derived here.
    """
    chain: list[Edge] = []
    node = end_id
    while node != start_id:
        edge = arrived_by[node]
        chain.append(edge)
        node = backward(edge)
    chain.reverse()
    return chain


def _contains_words(haystack: str, needle: str) -> bool:
    """Whole-word containment, so ``jazz`` matches ``acid jazz`` but ``azz`` matches nothing."""
    haystack_words = haystack.split()
    needle_words = needle.split()
    span = len(needle_words)
    return any(
        haystack_words[i : i + span] == needle_words for i in range(len(haystack_words) - span + 1)
    )


def artifact_directory(version: str = PINNED_ARTIFACT_VERSION) -> Path:
    """Where the pinned artifact lives, resolved relative to the installed package.

    Duplicated deliberately from ``ingest.wikidata.artifact_dir``: ``graph`` must not import ``ingest``
    (``tests/test_architecture.py``), and a shared constant is not worth a sixth top-level package. A
    test asserts the two agree.
    """
    return Path(__file__).resolve().parent.parent / "artifacts" / f"v{version}"


@lru_cache(maxsize=1)
def default_store() -> InMemoryGraphStore:
    """The pinned store, parsed once per process.

    Call this at module scope from the Lambda handler so the parse happens during INIT rather than
    inside the first request.
    """
    return InMemoryGraphStore.from_directory(artifact_directory())
