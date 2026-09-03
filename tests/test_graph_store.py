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
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    PREDICATE_PLAYS_GENRE,
    PREDICATES,
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


def test_path_is_implemented(store: InMemoryGraphStore) -> None:
    """Replaces ``test_path_is_declared_but_not_implemented``, deleted 2026-08-05 in phase 2 step 4
    exactly as that test's own docstring said it would be.

    It earned its keep first: it caught the phase-5-to-phase-2 correction on 2026-08-04 by asserting on
    the *phase* named in the ``NotImplementedError`` rather than just the exception type. What survives
    it is the assertion that the protocol method no longer raises at all. Traversal behaviour is tested
    in ``test_path.py``.
    """
    assert store.path(HEAVY_METAL, BLUES) != []


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
    assert store.search("gamelan") == []  # bebop until v0.6.0, which ingested it
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
        kind=NODE_KIND_GENRE,
    )
    other = Node(
        id="Q2",
        label="other genre",
        source="test",
        source_id="Q2",
        retrieved_at="2026-01-01T00:00:00+00:00",
        kind=NODE_KIND_GENRE,
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


# --- the predicate filter --------------------------------------------------------------------------
#
# Added 2026-09-03, phase 6 step 3, when bumping the pin to v0.6.0 made these fail. Until the membership
# axis arrived every edge was ``influenced_by``, so a traversal that returned whatever touched a node was
# right by accident. Unfiltered against v0.6.0, "who influenced Michael Jackson" answered with three
# genres he plays and "what came out of rock music" answered with 113 artists and no genres at all.
#
# The gate would have rejected any claim built from those edges, so groundedness never moved -- which is
# precisely why this needs its own lock down here. The contamination was invisible to every metric that
# blocks, and showed up as traversal and refusal instead.

MICHAEL_JACKSON = "Q2831"
ROCK_MUSIC = "Q11399"


def test_neighbors_walks_influence_only_unless_asked_otherwise(store: InMemoryGraphStore) -> None:
    """The default is restrictive, and an artist is where that bites: Michael Jackson carries both kinds
    of edge, so an unfiltered walk mixes the genres he plays into the list of people who influenced him."""
    assert {e.predicate for e in store.neighbors(MICHAEL_JACKSON)} == {PREDICATE_INFLUENCED_BY}
    assert {e.predicate for e in store.neighbors(MICHAEL_JACKSON, predicates=PREDICATES)} == {
        PREDICATE_INFLUENCED_BY,
        PREDICATE_PLAYS_GENRE,
    }


def test_membership_is_reachable_when_a_caller_names_it(store: InMemoryGraphStore) -> None:
    """Opt-in, not unavailable. Connectivity and the map need this axis; the default merely refuses to
    hand it to a caller that did not ask."""
    members = store.neighbors(ROCK_MUSIC, Direction.INFLUENCED, predicates=PREDICATES)
    assert members != []
    assert {e.predicate for e in members} == {PREDICATE_PLAYS_GENRE}
    assert store.neighbors(ROCK_MUSIC, Direction.INFLUENCED) == []


def test_a_path_never_crosses_a_membership_edge_by_default(store: InMemoryGraphStore) -> None:
    """This matters more than the ``neighbors`` case because a chain is narrated hop by hop. Michael
    Jackson reaches rock music in one membership hop, and that hop must not be available to a lineage:
    "works in" is not "descends from", and a path is read as derivation.
    """
    crossing = store.path(
        MICHAEL_JACKSON, ROCK_MUSIC, Direction.INFLUENCED_BY, predicates=PREDICATES
    )
    assert [e.predicate for e in crossing] == [PREDICATE_PLAYS_GENRE]
    assert store.path(MICHAEL_JACKSON, ROCK_MUSIC, Direction.INFLUENCED_BY) == []


def test_influence_traversal_is_unchanged_by_the_membership_axis() -> None:
    """The point of the default: every node the two artifacts share answers influence questions
    identically at v0.6.0 and v0.5.0.

    One edge legitimately differs -- Nine Inch Nails ``influenced_by`` Pink Floyd, dropped by step 2's
    deprecated-statement repair -- and it is named here rather than tolerated by a fuzzy bound, so a
    second divergence fails this test instead of hiding behind the first.
    """
    previous = InMemoryGraphStore.from_directory(artifact_directory().parent / "v0.5.0")
    current = InMemoryGraphStore.from_directory(artifact_directory())

    differing = {
        (node_id, direction)
        for node_id in previous._nodes
        if node_id in current._nodes
        for direction in Direction
        if {(e.subject_id, e.object_id) for e in previous.neighbors(node_id, direction)}
        != {(e.subject_id, e.object_id) for e in current.neighbors(node_id, direction)}
    }
    assert differing == {
        ("Q11647", Direction.INFLUENCED_BY),
        ("Q2306", Direction.INFLUENCED),
    }
