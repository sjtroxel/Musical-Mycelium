"""Write the versioned artifact.

The artifact is **immutable and versioned**: a build writes ``graph.json`` plus a ``manifest.json``
carrying the sha256 of those exact bytes, and downstream code reads a pinned version rather than
"latest". That is what stops a corpus change from silently invalidating every previous benchmark
(``.claude/rules/evals.md``).

Writing refuses to overwrite an existing version by default, because an artifact version that quietly
changes contents is the failure the pin exists to prevent. Rebuild under a new version instead.

Only the **write** side lives here. Reading, hashing and verification live in ``graph.schema``, so the
runtime can check its own corpus without importing this package and dragging the ingestion code into the
Lambda image. ``verify`` and ``read_manifest`` are re-exported below for callers that already have this
module in hand.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from musical_mycelium.graph.schema import (
    ARTIFACT_FILENAME,
    MANIFEST_FILENAME,
    ArtifactCorruptError,
    Manifest,
    read_manifest,
    sha256_of,
    verify,
)
from musical_mycelium.graph.schema import Artifact as Artifact
from musical_mycelium.graph.structure import analyse

__all__ = [
    "Artifact",
    "ArtifactCorruptError",
    "ArtifactExistsError",
    "AxisCollisionError",
    "build_manifest",
    "merge_axes",
    "read_manifest",
    "sha256_of",
    "verify",
    "write",
]


class ArtifactExistsError(FileExistsError):
    """The target version already exists. Artifacts are immutable; build a new version."""


class AxisCollisionError(ValueError):
    """One entity was ingested on two axes. Its ``kind`` would then depend on which row won."""


def merge_axes(*artifacts: Artifact) -> Artifact:
    """Combine per-axis artifacts into one graph, refusing anything that blurs the axes.

    The merge lives here rather than in ``ingest.artists`` on purpose: each axis module produces its
    own rows and never reaches across, so there is exactly one place where the two become one corpus
    and exactly one place to enforce what that is allowed to mean.

    **A node id may appear in more than one input, but only at the same ``kind``.** The same QID
    arriving as a genre from one crawl and an artist from another is not a duplicate to be
    de-duplicated — it means the two type filters disagree, and silently keeping whichever row sorted
    last would make ``Node.kind`` depend on iteration order. That is invariant 3 failing quietly,
    which is the only way it ever fails.
    """
    by_id: dict[str, Any] = {}
    for artifact in artifacts:
        for node in artifact.nodes:
            existing = by_id.get(node.id)
            if existing is not None and existing.kind != node.kind:
                raise AxisCollisionError(
                    f"{node.id} ({node.label!r}) was ingested as both {existing.kind!r} and "
                    f"{node.kind!r}; the two axis type filters disagree and Node.kind cannot be "
                    f"decided by whichever row sorted last"
                )
            by_id.setdefault(node.id, node)

    edges = {(e.subject_id, e.predicate, e.object_id): e for a in artifacts for e in a.edges}
    dangling = sorted(
        {q for triple in edges for q in (triple[0], triple[2])} - set(by_id),
    )
    if dangling:
        raise AxisCollisionError(
            f"{len(dangling)} edge endpoint(s) have no node: {dangling[:5]}. An edge to a node the "
            f"corpus does not contain cannot be gated, because the gate resolves both endpoints first"
        )

    return Artifact(
        nodes=tuple(sorted(by_id.values(), key=lambda n: n.id)),
        edges=tuple(sorted(edges.values(), key=lambda e: (e.subject_id, e.object_id))),
    )


def build_manifest(
    artifact: Artifact,
    *,
    artifact_version: str,
    generator: str,
    predicate: str,
    source: str,
    graph_json: str,
    source_snapshot: dict[str, int] | None = None,
    verification_record: str = "",
    notes: str = "",
) -> Manifest:
    return Manifest(
        artifact_version=artifact_version,
        generated_at=datetime.now(UTC).isoformat(timespec="seconds"),
        generator=generator,
        predicate=predicate,
        node_count=len(artifact.nodes),
        edge_count=len(artifact.edges),
        sha256=sha256_of(graph_json),
        source=source,
        source_snapshot=source_snapshot or {},
        # Derived, never a parameter: a caller-supplied count could disagree with the edges it claims
        # to describe, and a manifest that misreports verification strength is worse than none.
        verification_counts=artifact.verification_counts(),
        # Same rule, same reason. Recorded here so a build is self-describing and an eval can read the
        # connectivity it ran against without loading the corpus; the runtime still recomputes it.
        structure=analyse(artifact).as_dict(),
        verification_record=verification_record,
        notes=notes,
    )


def write(
    artifact: Artifact,
    directory: Path,
    *,
    artifact_version: str,
    generator: str,
    predicate: str,
    source: str,
    source_snapshot: dict[str, int] | None = None,
    verification_record: str = "",
    notes: str = "",
    overwrite: bool = False,
) -> Manifest:
    """Write ``graph.json`` and ``manifest.json`` into ``directory``. Returns the manifest."""
    graph_path = directory / ARTIFACT_FILENAME
    if graph_path.exists() and not overwrite:
        raise ArtifactExistsError(
            f"{graph_path} already exists. Artifacts are immutable — bump the version, "
            f"or pass overwrite=True if you are deliberately rebuilding the same version."
        )

    graph_json = artifact.to_json()
    manifest = build_manifest(
        artifact,
        artifact_version=artifact_version,
        generator=generator,
        predicate=predicate,
        source=source,
        graph_json=graph_json,
        source_snapshot=source_snapshot,
        verification_record=verification_record,
        notes=notes,
    )

    directory.mkdir(parents=True, exist_ok=True)
    graph_path.write_text(graph_json, encoding="utf-8")
    (directory / MANIFEST_FILENAME).write_text(
        json.dumps(asdict(manifest), indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return manifest
