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
    """A genre. ``source_id`` is the Wikidata QID; ``revision_id`` pins the exact revision read."""

    id: str
    label: str
    source: str
    source_id: str
    retrieved_at: str
    revision_id: int | None = None

    def __post_init__(self) -> None:
        _require(self.id, "id", "node")
        _require(self.label, "label", f"node {self.id}")
        _require(self.source, "source", f"node {self.id}")
        _require(self.source_id, "source_id", f"node {self.id}")
        _require(self.retrieved_at, "retrieved_at", f"node {self.id}")


@dataclass(frozen=True, slots=True)
class Edge:
    """One influence claim.

    ``source_id`` is the Wikidata **statement** URI, not the subject QID. That distinction is the whole
    point: a statement identifier resolves to the specific assertion being cited, so a claim's citation
    can be checked rather than merely gestured at.
    """

    subject_id: str
    predicate: str
    object_id: str
    source: str
    source_id: str
    retrieved_at: str
    prose_tier: str

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
    verification_record: str = ""
    notes: str = ""


@dataclass(frozen=True, slots=True)
class Artifact:
    """Nodes plus edges. Deliberately dumb: at v0.1 the format is chosen for legibility, not speed."""

    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]

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
