"""Artifact schema and writer tests.

Two things are being defended here, and only one of them is ordinary correctness.

The first is **invariant 2**: provenance on every row from the first row written. Retrofitting
source-tracking means re-ingesting everything and invalidating every eval, so the tests assert that a row
*cannot be constructed* without it — not merely that the current writer happens to supply it.

The second is the **pin**. Evals run against a pinned artifact version, and that guarantee is only worth
something if a pinned artifact cannot change under it. Hence the immutability and hash tests.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from musical_mycelium.graph import structure
from musical_mycelium.graph.schema import (
    ARTIFACT_FILENAME,
    MANIFEST_FILENAME,
    PREDICATE_INFLUENCED_BY,
    SOURCE_WIKIDATA,
    VERIFICATION_HAND,
    VERIFICATION_PROSE_AUTO,
    Artifact,
    Edge,
    Node,
    ProvenanceError,
)
from musical_mycelium.ingest import artifact as artifact_io
from musical_mycelium.ingest import wikidata

RETRIEVED = "2026-08-02T21:52:49+00:00"


def a_node(**overrides: object) -> Node:
    fields: dict[str, object] = {
        "id": "Q193355",
        "label": "blues rock",
        "source": SOURCE_WIKIDATA,
        "source_id": "Q193355",
        "retrieved_at": RETRIEVED,
        "revision_id": 1,
    }
    fields.update(overrides)
    return Node(**fields)  # type: ignore[arg-type]


def an_edge(**overrides: object) -> Edge:
    fields: dict[str, object] = {
        "subject_id": "Q193355",
        "predicate": PREDICATE_INFLUENCED_BY,
        "object_id": "Q9759",
        "source": SOURCE_WIKIDATA,
        "source_id": "http://www.wikidata.org/entity/statement/Q193355-032451F3",
        "retrieved_at": RETRIEVED,
        "prose_tier": "PROSE",
        "verification": VERIFICATION_PROSE_AUTO,
    }
    fields.update(overrides)
    return Edge(**fields)  # type: ignore[arg-type]


# --- invariant 2: provenance is structural ------------------------------------------------------


@pytest.mark.parametrize("missing", ["source", "source_id", "retrieved_at"])
def test_node_without_provenance_cannot_be_constructed(missing: str) -> None:
    with pytest.raises(ProvenanceError, match=missing):
        a_node(**{missing: ""})


@pytest.mark.parametrize("missing", ["source", "source_id", "retrieved_at"])
def test_edge_without_provenance_cannot_be_constructed(missing: str) -> None:
    with pytest.raises(ProvenanceError, match=missing):
        an_edge(**{missing: ""})


def test_whitespace_does_not_count_as_provenance() -> None:
    """A space is not a source. Blank-ish values are the way this invariant actually erodes."""
    with pytest.raises(ProvenanceError):
        an_edge(source_id="   ")


def test_edge_rejects_an_unknown_prose_tier() -> None:
    with pytest.raises(ValueError, match="prose_tier"):
        an_edge(prose_tier="probably fine")


# --- the pin --------------------------------------------------------------------------------------


def test_written_artifact_verifies(tmp_path: Path) -> None:
    manifest = artifact_io.write(
        Artifact(nodes=(a_node(),), edges=(an_edge(),)),
        tmp_path,
        artifact_version="0.0.0-test",
        generator="test",
        predicate="P737",
        source=SOURCE_WIKIDATA,
    )
    assert artifact_io.verify(tmp_path) == manifest
    assert manifest.node_count == 1
    assert manifest.edge_count == 1


def test_editing_the_artifact_in_place_is_detected(tmp_path: Path) -> None:
    artifact_io.write(
        Artifact(nodes=(a_node(),), edges=(an_edge(),)),
        tmp_path,
        artifact_version="0.0.0-test",
        generator="test",
        predicate="P737",
        source=SOURCE_WIKIDATA,
    )
    payload = json.loads((tmp_path / ARTIFACT_FILENAME).read_text(encoding="utf-8"))
    payload["edges"][0]["object_id"] = "Q1"  # a fabricated edge, smuggled in after the fact
    (tmp_path / ARTIFACT_FILENAME).write_text(json.dumps(payload, indent=2), encoding="utf-8")

    with pytest.raises(artifact_io.ArtifactCorruptError):
        artifact_io.verify(tmp_path)


def test_a_version_cannot_be_silently_overwritten(tmp_path: Path) -> None:
    artifact = Artifact(nodes=(a_node(),), edges=(an_edge(),))
    kwargs = {
        "artifact_version": "0.0.0-test",
        "generator": "test",
        "predicate": "P737",
        "source": SOURCE_WIKIDATA,
    }
    artifact_io.write(artifact, tmp_path, **kwargs)  # type: ignore[arg-type]
    with pytest.raises(artifact_io.ArtifactExistsError):
        artifact_io.write(artifact, tmp_path, **kwargs)  # type: ignore[arg-type]


def test_serialisation_is_byte_stable() -> None:
    """The same content must produce the same bytes, or the hash pin means nothing."""
    artifact = Artifact(nodes=(a_node(),), edges=(an_edge(),))
    assert artifact.to_json() == Artifact.from_json(artifact.to_json()).to_json()


# --- the shipped v0.1 artifact ---------------------------------------------------------------------


@pytest.fixture(scope="module")
def pinned() -> Artifact:
    return Artifact.load(wikidata.artifact_dir())


def test_pinned_artifact_hash_matches_its_manifest() -> None:
    """Runs on every commit. If the corpus file drifts from its manifest, CI says so."""
    artifact_io.verify(wikidata.artifact_dir())


def test_every_hand_verified_edge_is_in_the_artifact(pinned: Artifact) -> None:
    """The hand-read edges are the corpus's strongest evidence and must never be dropped.

    At v0.1 this was an equality: the artifact *was* the hand list. At v0.2 it is containment, because
    the rest of the corpus comes from the automated screening. The complementary guarantee — that
    nothing sneaks in past the hand rejections — is `test_rejected_edges_are_absent` below.
    """
    in_artifact = {(e.subject_id, e.object_id) for e in pinned.edges}
    assert set(wikidata.HAND_VERIFIED_EDGES) <= in_artifact


def test_hand_verified_edges_are_labelled_hand_and_the_rest_are_not(pinned: Artifact) -> None:
    """Verification strength has to match the record, in both directions.

    A `PROSE_AUTO` edge mislabelled `HAND` claims a human read it when none did, which is the
    "grounded slides into correct" failure `CLAUDE.md` forbids. The reverse understates the corpus.
    """
    hand = set(wikidata.HAND_VERIFIED_EDGES)
    for edge in pinned.edges:
        expected = (
            VERIFICATION_HAND
            if (edge.subject_id, edge.object_id) in hand
            else VERIFICATION_PROSE_AUTO
        )
        assert edge.verification == expected, f"{edge.subject_id} <- {edge.object_id}"


def test_the_manifest_verification_counts_match_the_edges(pinned: Artifact) -> None:
    """The manifest is what the API quotes, so it must be derived from the edges, not asserted."""
    manifest = artifact_io.read_manifest(wikidata.artifact_dir())

    assert manifest.verification_counts == pinned.verification_counts()
    assert sum(manifest.verification_counts.values()) == manifest.edge_count


def test_build_manifest_derives_structure_from_the_edges(pinned: Artifact) -> None:
    """Same anti-drift rule as ``verification_counts``: ``structure`` is computed by ``build_manifest``
    and is not a parameter, so a build cannot record connectivity that disagrees with its own corpus.

    Note what this does **not** assert. The pinned v0.2.0 manifest on disk carries no ``structure`` at
    all — it was written before the field existed and artifacts are immutable, so it stays that way and
    the runtime recomputes instead (``test_structure.py``). This asserts the *next* build fills it.
    """
    manifest = artifact_io.build_manifest(
        pinned,
        artifact_version="0.0.0-test",
        generator="test",
        predicate="influenced_by",
        source="wikidata",
        graph_json=pinned.to_json(),
    )

    assert manifest.structure == structure.analyse(pinned).as_dict()
    assert manifest.structure["component_count"] > 0
    assert manifest.structure["largest_component"] <= manifest.node_count


def test_rejected_edges_are_absent(pinned: Artifact) -> None:
    """The rejections are the point. An edge thrown out for contradicting its own source must not
    reappear because someone re-ran a discovery query."""
    in_artifact = {(e.subject_id, e.object_id) for e in pinned.edges}
    for subject, obj, reason in wikidata.REJECTED_EDGES:
        assert (subject, obj) not in in_artifact, f"rejected edge is back: {reason}"


def test_every_pinned_row_carries_provenance(pinned: Artifact) -> None:
    for node in pinned.nodes:
        assert node.source and node.source_id and node.retrieved_at
    for edge in pinned.edges:
        assert edge.source and edge.source_id and edge.retrieved_at


def test_every_edge_cites_a_distinct_wikidata_statement(pinned: Artifact) -> None:
    """``source_id`` is a statement URI, not a QID. Two edges sharing one is a stamping bug that would
    make citations unresolvable while still looking populated."""
    statement_ids = [e.source_id for e in pinned.edges]
    assert all(s.startswith("http://www.wikidata.org/entity/statement/") for s in statement_ids)
    assert len(set(statement_ids)) == len(statement_ids)


def test_every_edge_endpoint_is_a_declared_node(pinned: Artifact) -> None:
    """A dangling edge would let the agent traverse to a node with no label and no provenance."""
    node_ids = {n.id for n in pinned.nodes}
    for edge in pinned.edges:
        assert edge.subject_id in node_ids
        assert edge.object_id in node_ids


def test_only_the_influence_predicate_is_ingested(pinned: Artifact) -> None:
    """P279 is taxonomic. v0.1 does not ingest it, so it cannot be narrated as derivation by
    construction rather than by the gate remembering to refuse (``docs/graph-semantics.md`` 2)."""
    assert {e.predicate for e in pinned.edges} == {PREDICATE_INFLUENCED_BY}


def test_manifest_records_a_revision_for_every_node(pinned: Artifact) -> None:
    """The snapshot is what makes ``retrieved_at`` checkable rather than decorative."""
    manifest = artifact_io.read_manifest(wikidata.artifact_dir())
    assert set(manifest.source_snapshot) == {n.id for n in pinned.nodes}
    assert all(revision > 0 for revision in manifest.source_snapshot.values())


def test_the_refusal_case_node_resolves_but_has_no_parents(pinned: Artifact) -> None:
    """Gold case 5 depends on this exact shape: ``blues`` is in the graph and is cited as the source of
    ``blues rock``, yet has no sourced origins of its own. If ingestion ever gave it a parent, the gold
    set would silently start expecting an answer where refusal is correct."""
    blues = "Q9759"
    assert blues in {n.id for n in pinned.nodes}
    assert any(e.object_id == blues for e in pinned.edges)
    assert not [e for e in pinned.edges if e.subject_id == blues]


def test_manifest_points_at_the_verification_record() -> None:
    manifest = artifact_io.read_manifest(wikidata.artifact_dir())
    assert (Path(__file__).resolve().parents[1] / manifest.verification_record).exists()


def test_manifest_filename_constant_is_what_was_written() -> None:
    assert (wikidata.artifact_dir() / MANIFEST_FILENAME).exists()
