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
from collections import defaultdict
from functools import lru_cache
from pathlib import Path

from musical_mycelium.graph.schema import Artifact, Edge, Manifest, Node, verify
from musical_mycelium.graph.store import Direction

#: The pinned version. A **constant in code**, never "latest" — that is what stops a corpus change from
#: silently invalidating a benchmark (``.claude/rules/evals.md``).
PINNED_ARTIFACT_VERSION = "0.2.0"

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

    def neighbors(self, node_id: str, direction: Direction = Direction.INFLUENCED_BY) -> list[Edge]:
        index = self._by_subject if direction is Direction.INFLUENCED_BY else self._by_object
        return list(index.get(node_id, ()))

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

    def path(self, start_id: str, end_id: str) -> list[Edge]:
        raise NotImplementedError(
            "path() lands in phase 2 with the corpus it needs; SPEC.md 2.2 names the query it serves. "
            "v0.1 answers single-hop origins only."
        )

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
