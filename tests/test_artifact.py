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
    NODE_KIND_ARTIST,
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    PREDICATE_PLAYS_GENRE,
    SOURCE_WIKIDATA,
    VERIFICATION_HAND,
    VERIFICATION_PROSE_AUTO,
    Artifact,
    Edge,
    Node,
    ProvenanceError,
    counts_agree,
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
        "kind": NODE_KIND_GENRE,
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


def test_node_rejects_an_unknown_kind() -> None:
    with pytest.raises(ValueError, match="kind"):
        a_node(kind="album")


def test_node_kind_has_no_default() -> None:
    """The whole point of the field. A default would have to be ``genre``, which is right for the 169
    nodes that predate it and silently wrong for every artist node after it — and a node that quietly
    reads as the wrong axis is the conflation ``kind`` exists to prevent. Constructing without one is
    a TypeError at the call site, not a shrug at read time."""
    fields = {
        "id": "Q193355",
        "label": "blues rock",
        "source": SOURCE_WIKIDATA,
        "source_id": "Q193355",
        "retrieved_at": RETRIEVED,
    }
    with pytest.raises(TypeError, match="kind"):
        Node(**fields)  # type: ignore[arg-type]


def test_an_empty_kind_is_not_a_kind() -> None:
    """Same erosion path as the whitespace-provenance case above."""
    with pytest.raises(ValueError, match="kind"):
        a_node(kind="")


# --- merging the axes -------------------------------------------------------------------------


def genre_node(qid: str) -> Node:
    return a_node(id=qid, source_id=qid, label=f"genre {qid}", kind=NODE_KIND_GENRE)


def artist_node(qid: str) -> Node:
    return a_node(id=qid, source_id=qid, label=f"artist {qid}", kind=NODE_KIND_ARTIST)


def edge_between(subject: str, obj: str) -> Edge:
    return an_edge(
        subject_id=subject,
        object_id=obj,
        source_id=f"http://www.wikidata.org/entity/statement/{subject}-AAA",
    )


def test_merging_two_axes_keeps_every_row() -> None:
    genres = Artifact(nodes=(genre_node("Q1"), genre_node("Q2")), edges=(edge_between("Q1", "Q2"),))
    artists = Artifact(
        nodes=(artist_node("Q10"), artist_node("Q11")), edges=(edge_between("Q10", "Q11"),)
    )
    merged = artifact_io.merge_axes(genres, artists)

    assert len(merged.nodes) == 4
    assert len(merged.edges) == 2
    assert {n.kind for n in merged.nodes} == {NODE_KIND_GENRE, NODE_KIND_ARTIST}


def test_the_same_entity_on_two_axes_is_refused() -> None:
    """Invariant 3, at the one place two axes become one corpus. If a QID arrives as a genre from one
    crawl and an artist from another, the two type filters disagree — and silently keeping whichever
    row sorted last would make ``kind`` depend on iteration order, which is invariant 3 failing
    quietly. That is the only way it ever fails."""
    genres = Artifact(nodes=(genre_node("Q1"),), edges=())
    artists = Artifact(nodes=(artist_node("Q1"),), edges=())

    with pytest.raises(artifact_io.AxisCollisionError, match="both"):
        artifact_io.merge_axes(genres, artists)


def test_the_same_entity_at_the_same_kind_is_merely_a_duplicate() -> None:
    """Not every repeat is a collision. Two crawls legitimately overlap; the same node at the same
    kind is one node, and refusing it would make re-running an axis impossible."""
    merged = artifact_io.merge_axes(
        Artifact(nodes=(genre_node("Q1"),), edges=()),
        Artifact(nodes=(genre_node("Q1"),), edges=()),
    )
    assert len(merged.nodes) == 1


def test_an_edge_with_no_node_is_refused() -> None:
    """The gate resolves both endpoints before it looks for the edge, so an edge to a node the corpus
    does not contain could never be approved. Better to fail the build than ship an unreachable row."""
    with pytest.raises(artifact_io.AxisCollisionError, match="no node"):
        artifact_io.merge_axes(
            Artifact(nodes=(genre_node("Q1"),), edges=(edge_between("Q1", "Q404"),))
        )


def test_merging_is_ordered_and_reproducible() -> None:
    """The artifact hash is the pin. Row order deciding the sha256 would make an identical corpus
    hash differently depending on which axis was crawled first."""
    genres = Artifact(nodes=(genre_node("Q2"), genre_node("Q1")), edges=())
    artists = Artifact(nodes=(artist_node("Q11"), artist_node("Q10")), edges=())

    forward = artifact_io.merge_axes(genres, artists)
    backward = artifact_io.merge_axes(artists, genres)

    assert [n.id for n in forward.nodes] == ["Q1", "Q10", "Q11", "Q2"]
    assert forward.to_json() == backward.to_json(), "axis order must not change the bytes"


def test_merging_nothing_is_an_empty_artifact_not_a_crash() -> None:
    merged = artifact_io.merge_axes()
    assert merged.nodes == () and merged.edges == ()


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
    kinds = {node.id: node.kind for node in pinned.nodes}
    genre_levels = {VERIFICATION_HAND, VERIFICATION_PROSE_AUTO}

    for edge in pinned.edges:
        on_genre_axis = kinds[edge.subject_id] == NODE_KIND_GENRE
        if not on_genre_axis:
            # The artist axis earns its own two levels from the assertion filter, and HAND_VERIFIED_EDGES
            # is a genre-pair list that says nothing about it. Asserting PROSE_AUTO here would be
            # asserting the wrong axis's standard.
            assert edge.verification not in genre_levels, f"{edge.subject_id} <- {edge.object_id}"
            continue
        expected = (
            VERIFICATION_HAND
            if (edge.subject_id, edge.object_id) in hand
            else VERIFICATION_PROSE_AUTO
        )
        assert edge.verification == expected, f"{edge.subject_id} <- {edge.object_id}"


def test_the_manifest_verification_counts_match_the_edges(pinned: Artifact) -> None:
    """The manifest is what the API quotes, so it must be derived from the edges, not asserted."""
    manifest = artifact_io.read_manifest(wikidata.artifact_dir())

    # Widening-tolerant, narrowly: a level the manifest predates must be zero, and every level it
    # does name must match exactly. See ``schema.counts_agree``.
    assert counts_agree(manifest.verification_counts, pinned.verification_counts())
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


def test_p279_is_not_ingested_and_the_predicate_set_is_closed(pinned: Artifact) -> None:
    """P279 is taxonomic. It is not ingested, so it cannot be narrated as derivation by construction
    rather than by the gate remembering to refuse (``docs/graph-semantics.md`` 2).

    **Renamed at v0.6.0, because the old name became a false description of what this asserts.** The
    artifact carries two predicates now: P737 influence and P136 membership. The property being locked
    was never "exactly one predicate" -- it is that the set is *closed and known*, so a third arriving
    unannounced fails here. P279 is called out by name because it is the one that would read as
    derivation if it ever slipped in, and ``agent.claims.ALLOWED_PREDICATES`` is the second lock.
    """
    assert {e.predicate for e in pinned.edges} == {PREDICATE_INFLUENCED_BY, PREDICATE_PLAYS_GENRE}
    assert not any(e.predicate == "subclass_of" for e in pinned.edges)


def test_manifest_records_a_revision_for_every_node(pinned: Artifact) -> None:
    """The snapshot is what makes ``retrieved_at`` checkable rather than decorative.

    **Scoped to the genre axis, and that scope is a known gap rather than a convenience.** Genre nodes
    pin the exact Wikidata revision they were read from; artist nodes at v0.4.0 do not, because the
    artist build reads labels from the crawl rather than re-reading entities for their revision ids.
    The assertion below is written to fail the day that is fixed, so the gap cannot be forgotten.
    """
    manifest = artifact_io.read_manifest(wikidata.artifact_dir())
    genres = {n.id for n in pinned.nodes if n.kind == NODE_KIND_GENRE}
    artists = {n.id for n in pinned.nodes if n.kind == NODE_KIND_ARTIST}

    assert genres <= set(manifest.source_snapshot)
    assert all(revision > 0 for revision in manifest.source_snapshot.values())
    assert not (artists & set(manifest.source_snapshot)), (
        "artist nodes gained revision ids; delete this assertion and fold them into the check above"
    )


def test_the_snapshot_is_exactly_the_revisions_the_genre_nodes_carry(pinned: Artifact) -> None:
    """Equality, not containment -- and this is the assertion the v0.6.0 cut needed and did not have.

    ``membership.py`` omitted ``source_snapshot`` from its ``artifact_io.write`` call, so the first
    v0.6.0 manifest recorded **zero** revisions against 509 genre nodes while the test above still
    passed on ``genres <= set(...)`` for the empty set... which it does not, and that is the only reason
    the omission was caught at all. Containment is the wrong shape for a check like this: it cannot see
    a snapshot that has drifted from the nodes, only one missing an id outright.

    The manifest duplicates what each node already carries. That is worth locking rather than
    de-duplicating, because the manifest is what a reader checks ``retrieved_at`` against without
    parsing the graph. Two copies are fine; two copies that can disagree are not.
    """
    manifest = artifact_io.read_manifest(wikidata.artifact_dir())
    expected = {
        node.id: node.revision_id
        for node in pinned.nodes
        if node.kind == NODE_KIND_GENRE and node.revision_id
    }
    assert manifest.source_snapshot == expected


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
