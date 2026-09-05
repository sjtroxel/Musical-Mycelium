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
from collections.abc import Callable, Iterable
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
PINNED_ARTIFACT_VERSION = "0.7.1"

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
        """The pairs two different sources disagree about. Two at artifact v0.7.1."""
        return contested_pairs(self._artifact)

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
