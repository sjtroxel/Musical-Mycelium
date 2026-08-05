"""``GraphStore`` protocol and ``InMemoryGraphStore`` tests.

The interesting tests here are not the lookups. They are the ones that pin down **honest absence**: an
unknown node is ``None``, an unsourced node is an empty list, and neither is ever a near-miss. The whole
grounding story rests on the layer under the agent declining to guess, because a resolver that returns
"close enough" makes every refusal metric above it meaningless.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from musical_mycelium.graph.memory import (
    PINNED_ARTIFACT_VERSION,
    InMemoryGraphStore,
    artifact_directory,
    default_store,
    normalise,
)
from musical_mycelium.graph.schema import (
    VERIFICATION_PROSE_AUTO,
    Artifact,
    ArtifactCorruptError,
    Edge,
    Node,
)
from musical_mycelium.graph.store import Direction, GraphStore
from musical_mycelium.ingest import wikidata

BLUES = "Q9759"
BLUES_ROCK = "Q193355"
HEAVY_METAL = "Q38848"
ACID_JAZZ = "Q221772"
JAZZ = "Q8341"


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


# --- the protocol ----------------------------------------------------------------------------------


def test_the_v01_backend_satisfies_the_protocol(store: InMemoryGraphStore) -> None:
    assert isinstance(store, GraphStore)


def test_path_is_declared_but_not_implemented(store: InMemoryGraphStore) -> None:
    """Deliberate, not an oversight. It is on the protocol because retrofitting a protocol method
    touches every implementation; it raises because v0.1's corpus is one hop deep.

    **This test caught the phase-5-to-phase-2 correction on 2026-08-04** — the message said phase 5 in
    three places and the assertion pinned one of them. That is the test working, so it keeps asserting on
    the phase, not merely on the exception type. It is expected to fail and be deleted in phase 2 when
    `path()` is implemented.
    """
    with pytest.raises(NotImplementedError, match="phase 2"):
        store.path(BLUES, HEAVY_METAL)


def test_direction_names_the_claim_not_the_arrow() -> None:
    """If these ever get renamed to incoming/outgoing, the next person will invert music history."""
    assert Direction.INFLUENCED_BY.value == "influenced_by"
    assert Direction.INFLUENCED.value == "influenced"


# --- honest absence --------------------------------------------------------------------------------


def test_an_unknown_id_is_none_not_a_guess(store: InMemoryGraphStore) -> None:
    assert store.get_node("Q511054") is None  # griot: a real Wikidata entity, not in this artifact
    assert store.get_node("") is None
    assert store.get_node("not-a-qid") is None


def test_an_unknown_name_finds_nothing(store: InMemoryGraphStore) -> None:
    assert store.search("griot") == []
    assert store.search("bebop") == []
    assert store.search("") == []
    assert store.search("   ") == []


def test_a_resolvable_node_with_no_sourced_origins_returns_empty(store: InMemoryGraphStore) -> None:
    """Gold case 5. ``blues`` resolves, is cited as the source of ``blues rock``, and still has nothing
    upstream. Empty means "the graph has no sourced answer", never "this genre had no influences"."""
    assert store.get_node(BLUES) is not None
    assert store.neighbors(BLUES, Direction.INFLUENCED_BY) == []
    assert store.neighbors(BLUES, Direction.INFLUENCED) != []


# --- traversal -------------------------------------------------------------------------------------


def test_influenced_by_walks_to_parents(store: InMemoryGraphStore) -> None:
    parents = {e.object_id for e in store.neighbors(ACID_JAZZ, Direction.INFLUENCED_BY)}
    assert parents == {JAZZ, "Q164444", "Q131272", "Q11401"}  # jazz, funk, soul, hip-hop


def test_influenced_walks_to_children(store: InMemoryGraphStore) -> None:
    children = {e.subject_id for e in store.neighbors(JAZZ, Direction.INFLUENCED)}
    assert children == {ACID_JAZZ, "Q486263", "Q255406"}  # acid jazz, bossa nova, jazz rap


def test_the_two_directions_are_not_the_same_walk(store: InMemoryGraphStore) -> None:
    """The failure this guards is a one-character index mix-up that inverts every claim in the product
    while leaving every count identical."""
    up = store.neighbors(BLUES_ROCK, Direction.INFLUENCED_BY)
    down = store.neighbors(BLUES_ROCK, Direction.INFLUENCED)
    assert [e.object_id for e in up] == [BLUES]
    assert [e.subject_id for e in down] == [HEAVY_METAL]


def test_influenced_by_is_the_default_direction(store: InMemoryGraphStore) -> None:
    assert store.neighbors(ACID_JAZZ) == store.neighbors(ACID_JAZZ, Direction.INFLUENCED_BY)


def test_neighbors_returns_edges_so_provenance_survives(store: InMemoryGraphStore) -> None:
    """Returning nodes would strand ``source_id`` and make the claim unciteable one layer up."""
    for edge in store.neighbors(ACID_JAZZ):
        assert edge.source_id.startswith("http://www.wikidata.org/entity/statement/")
        assert edge.retrieved_at


def test_the_returned_list_cannot_mutate_the_index(store: InMemoryGraphStore) -> None:
    before = len(store.neighbors(ACID_JAZZ))
    store.neighbors(ACID_JAZZ).clear()
    assert len(store.neighbors(ACID_JAZZ)) == before


# --- search ----------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("blues", "blues"),
        ("Blues", "blues"),
        ("  BLUES  ", "blues"),
        ("the blues", "blues"),  # the gold case 5 query says "the blues"
        ("The Blues", "blues"),
        ("hip hop", "hip-hop"),  # label is hyphenated
        ("Hip-Hop", "hip-hop"),
        ("western swing", "Western swing"),
        ("acid jazz", "acid jazz"),
    ],
)
def test_search_resolves_human_typed_names(
    store: InMemoryGraphStore, typed: str, expected: str
) -> None:
    results = store.search(typed)
    assert results, f"{typed!r} resolved to nothing"
    assert results[0].label == expected


def test_exact_match_outranks_a_longer_containing_genre(store: InMemoryGraphStore) -> None:
    """``blues`` must not resolve to ``blues rock`` or ``soul blues``. A resolver that prefers a more
    specific genre than the one asked for answers a question nobody asked, with citations.

    Asserts the ranking rule, not the membership of the corpus. An earlier version enumerated the runner
    -up set exhaustively, which was only ever true at the 28-node v0.1 scale — v0.2 added ``rhythm and
    blues`` and broke it without anything being wrong. A test that fails whenever the corpus grows
    teaches people to edit tests instead of reading them.
    """
    results = store.search("blues")

    assert results[0].id == BLUES, "the exact match ranks first"
    labels = {n.label for n in results[1:]}
    assert {"blues rock", "soul blues"} <= labels
    assert all("blues" in label for label in labels), "every runner-up genuinely contains the query"


def test_search_does_not_match_word_fragments(store: InMemoryGraphStore) -> None:
    assert store.search("azz") == []
    assert store.search("ues") == []


def test_search_finds_a_genre_by_its_distinctive_word(store: InMemoryGraphStore) -> None:
    labels = {n.label for n in store.search("jazz")}
    assert {"jazz", "acid jazz", "jazz rap"} <= labels


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Hip-Hop", "hip hop"),
        ("the blues", "blues"),
        ("The Blues", "blues"),
        ("tropicália", "tropicalia"),
        ("R&B!", "rb"),
        ("   ", ""),
    ],
)
def test_normalise(raw: str, expected: str) -> None:
    assert normalise(raw) == expected


def test_normalise_does_not_eat_the_a_in_a_cappella() -> None:
    """Regression, 2026-08-02. ``normalise`` originally stripped a leading "a "/"an " as well as "the ",
    which silently turned the genre **a cappella** into "cappella" — a name that matches nothing. The
    first version of this test asserted the broken behaviour because it was written to describe the
    implementation instead of the requirement.
    """
    assert normalise("A cappella") == "a cappella"
    assert normalise("an ambient piece") == "an ambient piece"


def test_normalise_strips_only_one_leading_article() -> None:
    """ "the the" is not a genre in this corpus, but eating articles greedily is how a resolver starts
    matching things the user did not type."""
    assert normalise("the the blues") == "the blues"


# --- loading and the pin ----------------------------------------------------------------------------


def test_store_reports_the_pinned_version(store: InMemoryGraphStore) -> None:
    assert store.artifact_version == PINNED_ARTIFACT_VERSION


def test_loading_verifies_the_hash(tmp_path: Path) -> None:
    """A corpus that has drifted from its manifest fails at boot rather than serving edges quietly."""
    source = artifact_directory()
    (tmp_path / "graph.json").write_text(
        (source / "graph.json").read_text(encoding="utf-8").replace("Q9759", "Q1"), encoding="utf-8"
    )
    (tmp_path / "manifest.json").write_text(
        (source / "manifest.json").read_text(encoding="utf-8"), encoding="utf-8"
    )

    with pytest.raises(ArtifactCorruptError):
        InMemoryGraphStore.from_directory(tmp_path)

    # ...and the escape hatch is explicit, never the default.
    assert (
        InMemoryGraphStore.from_directory(tmp_path, check_hash=False).artifact_version == "unpinned"
    )


def test_default_store_is_parsed_once_per_process() -> None:
    """The cheap half of the cold-start story: the JSON is parsed once per container, not per request."""
    assert default_store() is default_store()


def test_graph_and_ingest_agree_on_where_the_artifact_lives() -> None:
    """``graph`` may not import ``ingest``, so the path constant is duplicated. This is the test that
    makes the duplication safe."""
    assert artifact_directory() == wikidata.artifact_dir()
    assert PINNED_ARTIFACT_VERSION == wikidata.ARTIFACT_VERSION


# --- the store over a synthetic artifact -------------------------------------------------------------


def test_store_works_without_a_manifest() -> None:
    """Constructed directly from an ``Artifact``, as fixtures and the step-6 loop tests will do."""
    node = Node(
        id="Q1",
        label="test genre",
        source="test",
        source_id="Q1",
        retrieved_at="2026-01-01T00:00:00+00:00",
    )
    other = Node(
        id="Q2",
        label="other genre",
        source="test",
        source_id="Q2",
        retrieved_at="2026-01-01T00:00:00+00:00",
    )
    edge = Edge(
        subject_id="Q1",
        predicate="influenced_by",
        object_id="Q2",
        source="test",
        source_id="stmt/1",
        retrieved_at="2026-01-01T00:00:00+00:00",
        prose_tier="PROSE",
        verification=VERIFICATION_PROSE_AUTO,
    )
    store = InMemoryGraphStore(Artifact(nodes=(node, other), edges=(edge,)))

    assert store.artifact_version == "unpinned"
    assert len(store) == 2
    assert store.neighbors("Q1")[0].object_id == "Q2"
    assert store.neighbors("Q2") == []
    assert store.search("test genre")[0].id == "Q1"
