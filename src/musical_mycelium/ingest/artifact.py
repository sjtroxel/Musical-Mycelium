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
    "build_manifest",
    "read_manifest",
    "sha256_of",
    "verify",
    "write",
]


class ArtifactExistsError(FileExistsError):
    """The target version already exists. Artifacts are immutable; build a new version."""


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
