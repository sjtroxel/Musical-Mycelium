"""The artifact schema — the on-disk contract between ``ingest`` and ``graph``.

It lives here rather than in ``ingest`` because of the dependency direction in
``musical_mycelium.__init__``: ``ingest -> (artifact) -> graph``. ``ingest`` may import this;
``graph`` must never import ``ingest``, or the Lambda container ends up carrying the network-fetching
ingestion code it has no business running. ``tests/test_architecture.py`` enforces that.

**Provenance is structural here, not validated later.** ``CLAUDE.md`` invariant 2 requires ``source``,
``source_id`` and ``retrieved_at`` on every node and edge from the first row written, and retrofitting
source-tracking means re-ingesting everything and invalidating every eval. So the fields are required
positional state on frozen dataclasses and ``__post_init__`` rejects blanks: a row without provenance
cannot be constructed, let alone written. A test that checks provenance can be deleted; a constructor
that refuses to build the row cannot be.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Self

#: The only predicate v0.1 ingests. P279 (``subclass of``) is deliberately absent: it is taxonomic, and
#: a graph that cannot represent it cannot narrate it as derivation. See ``docs/graph-semantics.md`` 2.
PREDICATE_INFLUENCED_BY = "influenced_by"

SOURCE_WIKIDATA = "wikidata"

#: Tiers from the Wikipedia disconfirmation check (``docs/graph-semantics.md`` 4.2). Only PROSE is
#: ingested. The others are recorded in the exclusions file so the exclusion rate stays a displayed
#: number rather than a silent filter.
PROSE_TIERS = frozenset({"PROSE", "INFOBOX_ONLY", "ORPHAN"})

#: A human read the subject's article and judged that its prose **asserts influence**. 22 edges at
#: v0.2, recorded per-edge with supporting quotations in ``docs/phases/phase-1-edge-verification.md``
#: and listed as ``ingest.wikidata.HAND_VERIFIED_EDGES``.
VERIFICATION_HAND = "HAND"

#: The automated prose check passed, and nothing else. Strictly weaker than ``HAND``: the check confirms
#: the subject's article names the object in genuine body prose, but it **structurally cannot tell
#: whether that sentence asserts influence** rather than synonymy, taxonomy, contradiction, or a mention
#: running the wrong way in time (``ingest.prosecheck`` module docstring). Measured against the 28 edges
#: phase 1 hand-read, it over-accepts at roughly 1 in 5.
VERIFICATION_PROSE_AUTO = "PROSE_AUTO"

#: The prose check passed **and** the influence-assertion filter judged the sentence to *assert*
#: influence. Stronger than ``PROSE_AUTO`` and only meaningful on the artist axis, where a mention is
#: cheap: artists are named constantly for tours, covers, session work and chart comparisons, so
#: "the article names the object in body prose" is close to no evidence at all (``ingest.assertion``).
#: Measured on a held-out set the filter never saw: **97% precision, 95% recall** (scope doc A6.5).
VERIFICATION_ASSERTS_AUTO = "ASSERTS_AUTO"

#: The prose check passed and the filter found **formative exposure rather than an assertion** — *"as a
#: teenager he listened to Alice Cooper"*, *"his sister took him to the Apollo to see James Brown"*.
#: Deliberately ingested rather than dropped (scope doc A6.1, and dropping was ruled out 2026-08-05),
#: and deliberately *not* labelled the same as an assertion, because "grounded" must never quietly come
#: to rest on a listening habit. **This tier's recall is 20%** — proximity is a semantic category, not a
#: linguistic one, and no pattern list closes that gap. The miss rate is published, not engineered away
#: (A6.4). Read it as a floor on what exists, never as a count of what there is.
VERIFICATION_EXPOSURE_AUTO = "EXPOSURE_AUTO"

#: How strongly an edge was verified. **A required field with no default, deliberately.** A default
#: would have to be wrong for one half of the corpus or the other — ``HAND`` overstates the machine-
#: verified majority, ``PROSE_AUTO`` understates the edges a human actually read — and silently
#: mislabelling verification strength is precisely the "grounded slides into correct" failure
#: ``CLAUDE.md`` forbids. Every construction site states which it is.
#:
#: The two ``*_AUTO`` artist tiers were added at v0.4.0. This is a **widening**, so every earlier
#: artifact stays valid; ``verification_counts`` reports the new levels at zero for a genre-only corpus,
#: which is the honest reading rather than an omission.
VERIFICATION_LEVELS = frozenset(
    {
        VERIFICATION_HAND,
        VERIFICATION_PROSE_AUTO,
        VERIFICATION_ASSERTS_AUTO,
        VERIFICATION_EXPOSURE_AUTO,
    }
)

#: A genre: bebop, trip hop, blues rock. Every node through v0.2 was one, which is why this field did not
#: need to exist until the artist axis arrived.
NODE_KIND_GENRE = "genre"

#: A person or a musical group. Person-versus-group is deliberately **not** a third value: the distinction
#: the gate needs is the *axis*, and member-versus-band is a detail inside the artist axis rather than a
#: separate one. Widening a frozenset later is trivial; narrowing one that edges already depend on is not.
NODE_KIND_ARTIST = "artist"

#: What kind of thing a node is. **A required field with no default, for the same reason ``verification``
#: is one.** Genre and artist are structurally distinct axes of the same predicate: "Kate Bush influenced
#: by Peter Gabriel" and "trip hop influenced by hip-hop" are not the same kind of assertion and must
#: never be narrated as interchangeable (invariant 3). A default of ``genre`` would be right for the 169
#: nodes that predate the field and silently wrong for every artist node added after it — and a node that
#: quietly reads as the wrong axis is exactly the conflation this field exists to prevent. See
#: ``docs/phases/phase-2-corpus-and-traversal.md`` A6.7.
NODE_KINDS = frozenset({NODE_KIND_GENRE, NODE_KIND_ARTIST})

ARTIFACT_FILENAME = "graph.json"
MANIFEST_FILENAME = "manifest.json"


class ProvenanceError(ValueError):
    """A row was constructed without the provenance every row is required to carry."""


def _require(value: str, field_name: str, row: str) -> None:
    if not value or not value.strip():
        raise ProvenanceError(
            f"{row} is missing {field_name}; every row carries provenance (invariant 2)"
        )


@dataclass(frozen=True, slots=True)
class Node:
    """A genre or an artist, told apart by ``kind``.

    ``source_id`` is the Wikidata QID; ``revision_id`` pins the exact revision read. ``kind`` is required
    and carries no default, because the two axes must never be silently interchangeable — see
    ``NODE_KINDS``.
    """

    id: str
    label: str
    source: str
    source_id: str
    retrieved_at: str
    kind: str
    revision_id: int | None = None

    def __post_init__(self) -> None:
        _require(self.id, "id", "node")
        _require(self.label, "label", f"node {self.id}")
        _require(self.source, "source", f"node {self.id}")
        _require(self.source_id, "source_id", f"node {self.id}")
        _require(self.retrieved_at, "retrieved_at", f"node {self.id}")
        if self.kind not in NODE_KINDS:
            raise ValueError(
                f"node {self.id} has kind {self.kind!r}, expected one of {sorted(NODE_KINDS)}"
            )


@dataclass(frozen=True, slots=True)
class Edge:
    """One influence claim.

    ``source_id`` is the Wikidata **statement** URI, not the subject QID. That distinction is the whole
    point: a statement identifier resolves to the specific assertion being cited, so a claim's citation
    can be checked rather than merely gestured at.

    ``verification`` says **how strongly** the claim was checked, and it is required for the same reason
    the provenance fields are. The 111 machine-verified edges at v0.2 are noisier per edge than the 22
    a human read; carrying that difference on the row keeps it visible in the manifest and the API
    instead of averaging it away. Provenance is not truth, and verification strength is not either —
    but an unmarked mixture of the two is worse than either alone.
    """

    subject_id: str
    predicate: str
    object_id: str
    source: str
    source_id: str
    retrieved_at: str
    prose_tier: str
    verification: str

    def __post_init__(self) -> None:
        row = f"edge {self.subject_id} -{self.predicate}-> {self.object_id}"
        _require(self.subject_id, "subject_id", row)
        _require(self.predicate, "predicate", row)
        _require(self.object_id, "object_id", row)
        _require(self.source, "source", row)
        _require(self.source_id, "source_id", row)
        _require(self.retrieved_at, "retrieved_at", row)
        if self.prose_tier not in PROSE_TIERS:
            raise ValueError(
                f"{row} has prose_tier {self.prose_tier!r}, expected one of {sorted(PROSE_TIERS)}"
            )
        if self.verification not in VERIFICATION_LEVELS:
            raise ValueError(
                f"{row} has verification {self.verification!r}, expected one of "
                f"{sorted(VERIFICATION_LEVELS)}"
            )


@dataclass(frozen=True, slots=True)
class Manifest:
    """What was built, from what, when, and whether it still hashes to the same bytes.

    ``sha256`` is over ``graph.json`` exactly as written. Evals run against a pinned
    ``artifact_version``; the hash is what makes "pinned" mean something stronger than a directory name.
    """

    artifact_version: str
    generated_at: str
    generator: str
    predicate: str
    node_count: int
    edge_count: int
    sha256: str
    source: str
    source_snapshot: dict[str, int] = field(default_factory=dict)
    #: Edge count per ``VERIFICATION_LEVELS`` entry. **Derived from the edges by ``build_manifest``,
    #: never passed in**, so it cannot drift from what the artifact actually contains. Defaulted only
    #: so a pre-0.2.0 manifest still parses; a live build always fills it.
    verification_counts: dict[str, int] = field(default_factory=dict)
    #: Connectivity of the artifact — component count, largest component, diameter, isolated nodes and
    #: the deepest chain ``path()`` can return. **Derived by ``build_manifest`` from
    #: ``graph.structure.analyse``, never passed in**, for the same anti-drift reason as
    #: ``verification_counts``.
    #:
    #: A **record of the build, not an input to the runtime**: the store recomputes these at load rather
    #: than trusting them, so a manifest that predates this field costs nothing and a manifest that
    #: disagrees with its own corpus loses. Defaulted for exactly that reason — v0.2.0 was written
    #: before this field existed and is immutable, so it carries an empty structure and the numbers come
    #: from the corpus itself.
    structure: dict[str, int] = field(default_factory=dict)
    verification_record: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Artifact:
    """Nodes plus edges. Deliberately dumb: at v0.1 the format is chosen for legibility, not speed."""

    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]

    def verification_counts(self) -> dict[str, int]:
        """How many edges carry each verification level, including the levels that scored zero.

        Zeroes are included on purpose: a corpus with no hand-verified edges should say ``"HAND": 0``
        rather than omit the key, because a missing key reads as "not measured" and this is measured.
        """
        counts = dict.fromkeys(sorted(VERIFICATION_LEVELS), 0)
        for edge in self.edges:
            counts[edge.verification] += 1
        return counts

    def to_json(self) -> str:
        payload = {
            "nodes": [asdict(n) for n in self.nodes],
            "edges": [asdict(e) for e in self.edges],
        }
        # sort_keys and a trailing newline so the bytes are stable across runs; an artifact whose hash
        # changes without its content changing makes the pin meaningless.
        return json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"

    @classmethod
    def from_json(cls, raw: str) -> Self:
        data: dict[str, Any] = json.loads(raw)
        return cls(
            nodes=tuple(Node(**row) for row in data["nodes"]),
            edges=tuple(Edge(**row) for row in data["edges"]),
        )

    @classmethod
    def load(cls, directory: Path) -> Self:
        return cls.from_json((directory / ARTIFACT_FILENAME).read_text(encoding="utf-8"))


class ArtifactCorruptError(ValueError):
    """``graph.json`` does not hash to the value its manifest records."""


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def read_manifest(directory: Path) -> Manifest:
    return Manifest(**json.loads((directory / MANIFEST_FILENAME).read_text(encoding="utf-8")))


def verify(directory: Path) -> Manifest:
    """Recompute the hash of ``graph.json`` and check it against the manifest.

    The read side of the pin lives here, not in ``ingest``, so the runtime can check its own corpus
    without importing the ingestion package. ``ingest.artifact`` owns the *write* side and imports this.
    Cheap enough to run on every cold start: a sha256 over a few KB.
    """
    manifest = read_manifest(directory)
    actual = sha256_of((directory / ARTIFACT_FILENAME).read_text(encoding="utf-8"))
    if actual != manifest.sha256:
        raise ArtifactCorruptError(
            f"{directory / ARTIFACT_FILENAME} hashes to {actual} but its manifest records "
            f"{manifest.sha256}. The artifact has been edited in place."
        )
    return manifest
