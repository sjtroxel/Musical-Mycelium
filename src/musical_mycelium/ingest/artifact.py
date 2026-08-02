"""Write and verify the versioned artifact.

The artifact is **immutable and versioned**: a build writes ``graph.json`` plus a ``manifest.json``
carrying the sha256 of those exact bytes, and downstream code reads a pinned version rather than
"latest". That is what stops a corpus change from silently invalidating every previous benchmark
(``.claude/rules/evals.md``).

Writing refuses to overwrite an existing version by default, because an artifact version that quietly
changes contents is the failure the pin exists to prevent. Rebuild under a new version instead.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from musical_mycelium.graph.schema import (
    ARTIFACT_FILENAME,
    MANIFEST_FILENAME,
    Artifact,
    Manifest,
)


class ArtifactExistsError(FileExistsError):
    """The target version already exists. Artifacts are immutable; build a new version."""


class ArtifactCorruptError(ValueError):
    """``graph.json`` does not hash to the value its manifest records."""


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


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


def read_manifest(directory: Path) -> Manifest:
    data = json.loads((directory / MANIFEST_FILENAME).read_text(encoding="utf-8"))
    return Manifest(**data)


def verify(directory: Path) -> Manifest:
    """Recompute the hash of ``graph.json`` and check it against the manifest.

    This is the cheap integrity check that makes "pinned artifact version" a real guarantee. It is a
    Tier 1 eval candidate: deterministic, free, and it fails loudly if a corpus file drifts.
    """
    manifest = read_manifest(directory)
    actual = sha256_of((directory / ARTIFACT_FILENAME).read_text(encoding="utf-8"))
    if actual != manifest.sha256:
        raise ArtifactCorruptError(
            f"{directory / ARTIFACT_FILENAME} hashes to {actual} but its manifest records "
            f"{manifest.sha256}. The artifact has been edited in place."
        )
    return manifest
