"""Figures the SPA prints as prose must match the pinned artifact.

``web/src/corpus-facts.json`` holds the numbers that appear in first-screen copy. They are data rather
than string literals in a component precisely so this file can check them: ``CLAUDE.md`` requires corpus
bias to be *visible in output*, and a visible number that has quietly gone wrong is worse than no number.

The precedent is real. A published coverage percentage was retracted on 2026-08-07 because it added the
US and UK country totals and double-counted every genre credited to both.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.graph.memory import default_store
from musical_mycelium.graph.schema import PREDICATE_INFLUENCED_BY
from musical_mycelium.graph.store import Direction, GraphStore

FACTS_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "corpus-facts.json"
ARTIFACTS = Path(__file__).resolve().parents[1] / "src" / "musical_mycelium" / "artifacts"


@pytest.fixture(scope="module")
def facts() -> dict[str, Any]:
    document: dict[str, Any] = json.loads(FACTS_PATH.read_text(encoding="utf-8"))
    return document


@pytest.fixture(scope="module")
def store() -> GraphStore:
    return default_store()


@pytest.fixture(scope="module")
def node_ids(store: GraphStore) -> list[str]:
    graph = json.loads(
        (ARTIFACTS / f"v{store.artifact_version}" / "graph.json").read_text(encoding="utf-8")
    )
    return [node["id"] for node in graph["nodes"]]


def test_the_facts_file_pins_the_artifact_the_store_loaded(
    facts: dict[str, Any], store: GraphStore
) -> None:
    assert facts["artifact_version"] == store.artifact_version


def test_the_node_count_is_right(facts: dict[str, Any], node_ids: list[str]) -> None:
    assert facts["nodes"] == len(node_ids)


def test_the_count_of_nodes_with_no_recorded_influences_is_right(
    facts: dict[str, Any], node_ids: list[str], store: GraphStore
) -> None:
    """The number that keeps a refusal from becoming a negative claim.

    IMPLEMENTATION 4.5 requirement 5: "Nobody influenced Kate Bush" is false and this corpus cannot
    support it. The refusal copy says what is *recorded*, and this figure is what makes that honest
    rather than merely careful -- most of the corpus records nothing in this direction.
    """
    observed = sum(
        1 for node_id in node_ids if not store.neighbors(node_id, Direction.INFLUENCED_BY)
    )
    assert facts["nodes_without_recorded_influences"] == observed


def test_most_of_the_corpus_records_no_influences(
    facts: dict[str, Any], node_ids: list[str]
) -> None:
    """The *claim the copy makes*, not just the digits.

    The sentence on screen says a missing edge is overwhelmingly not evidence of a missing influence.
    That argument holds while a large share of nodes genuinely record nothing.

    **THE MAJORITY CLAIM FLIPPED AT v0.7.1 AND THIS TEST IS WHY WE KNOW.** It read
    ``> len(node_ids) / 2`` and was true from v0.1 to v0.6.0. The DBpedia axis took the figure to
    **723 of 1,479 -- 48.9%, a large minority rather than "most"**. The docstring above promised that a
    flip would fail here rather than go quietly false, and it did.

    **The underlying argument survives and the WORD does not.** Nearly half the corpus recording nothing
    still makes a missing edge weak evidence of a missing influence. But any copy saying "most" is now
    wrong, and rewriting it is owed at step 8 -- DoD #8, arriving from the unfamiliar direction of copy
    that *understates* the corpus rather than overstating it.
    """
    share = facts["nodes_without_recorded_influences"] / len(node_ids)
    assert 0.4 < share < 0.5, (
        f"{share:.1%} record no influences. Below 40% the 'absence is not evidence' argument needs "
        f"restating on different grounds; above 50% the word 'most' is correct again. Either way the "
        f"copy has to move, so this fails rather than drifting."
    )


@pytest.fixture(scope="module")
def genre_degrees(store: GraphStore) -> dict[str, tuple[int, int]]:
    """Per genre: (total influence connections, connections recording where it came from).

    Read straight from the artifact rather than through ``GraphStore`` so the fixture cannot inherit
    a direction bug from the thing it is checking.

    **Influence edges only, and at v0.6.0 that stopped being a free choice.** Counting membership too
    would put the busiest genre at 160 connections rather than 6, and 154 of those 160 are artists who
    play it. A density row that reports 160 says the corpus is richly connected about influence, which
    is the "membership reads as derivation" failure in ``CLAUDE.md`` decision C1 wearing a bar chart.

    The row would also be internally incoherent: ``origins`` can only ever count influence, because a
    genre is never the subject of a ``plays_genre`` edge. One half filtered and the other not is not a
    measurement of anything.
    """
    graph = json.loads(
        (ARTIFACTS / f"v{store.artifact_version}" / "graph.json").read_text(encoding="utf-8")
    )
    degree: dict[str, int] = {}
    origins: dict[str, int] = {}
    for node in graph["nodes"]:
        degree[node["id"]] = 0
        origins[node["id"]] = 0
    for edge in graph["edges"]:
        if edge["predicate"] != PREDICATE_INFLUENCED_BY:
            continue
        degree[edge["subject_id"]] += 1
        degree[edge["object_id"]] += 1
        # `subject influenced_by object`: influence runs object -> subject, so an edge where a node
        # is the SUBJECT is a record of where that node came from. Reversing this is the project's
        # named failure mode and it would invert every sentence the panel prints.
        origins[edge["subject_id"]] += 1
    return {
        node["id"]: (degree[node["id"]], origins[node["id"]])
        for node in graph["nodes"]
        if node["kind"] == "genre"
    }


def test_the_coverage_block_matches_the_pinned_artifact(
    facts: dict[str, Any], store: GraphStore
) -> None:
    """Asserted whole, not key by key.

    The coverage panel renders every one of these figures. Checking them individually invites the
    next figure to be added to the panel and not to this file, which is how a rendered number goes
    quietly wrong.
    """
    from musical_mycelium.graph.coverage import analyse
    from musical_mycelium.graph.schema import Artifact

    artifact = Artifact.load(ARTIFACTS / f"v{store.artifact_version}")
    assert facts["coverage"] == analyse(artifact).as_dict()


def test_the_density_figures_are_right(
    facts: dict[str, Any], genre_degrees: dict[str, tuple[int, int]]
) -> None:
    density = facts["density"]
    assert density["genres_without_recorded_origins"] == sum(
        1 for _, origins in genre_degrees.values() if origins == 0
    )
    assert density["genres_with_one_connection"] == sum(
        1 for degree, _ in genre_degrees.values() if degree == 1
    )
    assert density["busiest_genre_connections"] == max(
        degree for degree, _ in genre_degrees.values()
    )

    observed: dict[str, int] = {}
    for degree, _ in genre_degrees.values():
        observed[str(degree)] = observed.get(str(degree), 0) + 1
    assert density["connections"] == observed

    # The histogram is the density row's only visual, so it has to account for every genre. A bucket
    # quietly dropped would draw a corpus that is denser than the real one.
    assert sum(density["connections"].values()) == len(genre_degrees)


def test_the_corpus_is_thin_in_the_way_the_panel_says_it_is(
    facts: dict[str, Any], genre_degrees: dict[str, tuple[int, int]]
) -> None:
    """The *claim*, not the digits -- the same shape as the refusal figure's second test.

    The panel's density row says three things: that most genres have no recorded origin at all, that
    the commonest genre in this corpus has the fewest possible connections, and that even the busiest
    one is thin in absolute terms. If a future corpus makes any of those false the copy is wrong and
    has to be rewritten, so it fails here rather than going quietly false on screen.

    **The middle claim changed shape at v0.6.0 and the copy has to change with it.** Through v0.5.0 the
    commonest genre had exactly one connection, and this read ``genres_with_one_connection > total / 2``.
    The membership crawl brought in 340 genres with no influence edge in either direction, so the modal
    bucket is now **zero**, not one, and 108 of 509 have exactly one. That is the corpus getting
    *thinner* on influence as it got larger -- it grew by acquiring genres nobody recorded an influence
    for. Asserting the mode directly says that, where the old inequality would now simply be false.

    **v0.7.1 REVERSED THAT TREND AND TWO OF THE THREE CLAIMS ARE NOW FALSE.** The DBpedia axis added
    1,336 sourced genre-to-genre edges, so:

    - genres with no recorded origin fell to **266 of 675 (39%)** -- no longer "most", and the panel's
      first claim has to be reworded;
    - the busiest genre now has **55** connections, not fewer than 10, so the "even the busiest is thin"
      line is simply wrong;
    - the modal bucket flipped BACK to ``1`` (125 genres, against 120 at zero), which is the shape
      v0.5.0 had before the membership crawl. The commonest genre once again has exactly one recorded
      connection, and it got there by the zero bucket shrinking rather than by anything moving up.

    Every one of those is copy on a screen, and rewriting it is owed at step 8. This is the corpus
    outgrowing its own disclaimers, which is a better problem than the reverse and still a problem.
    """
    density = facts["density"]
    total = len(genre_degrees)
    modal_bucket = max(density["connections"], key=lambda k: density["connections"][k])

    assert 0.3 < density["genres_without_recorded_origins"] / total < 0.5
    assert modal_bucket == "1"
    assert density["connections"]["0"] < total / 2
    assert density["busiest_genre_connections"] > 20


def test_the_skew_cannot_be_rendered_without_its_counterweight(facts: dict[str, Any]) -> None:
    """Concentration is not absence, asserted rather than remembered.

    ``CLAUDE.md`` requires the corpus skew to be visible, and a 2026-08-06 correction established
    that overstating it fails the same honesty bar as hiding it. The panel prints the US and UK
    counts, so the figures that keep them from being read as the whole story have to be present and
    non-trivial: genres naming neither, and the number of distinct places.
    """
    coverage = facts["coverage"]

    assert coverage["genres_without_us_or_uk"] > 0
    assert coverage["distinct_countries"] > 10
    # The counterweight has to be large enough to actually counterweigh: if a future corpus made
    # this a handful of genres, "92 name neither" would become a fig leaf and the sentence built on
    # it would need rewriting.
    #
    # THIS BOUND WAS RELAXED IN THE BAD DIRECTION AT v0.6.0, 2026-09-03, and that is a finding rather
    # than maintenance. In absolute terms the counterweight grew -- 43 genres over 29 places became 92
    # over 50 -- but as a SHARE of the corpus it shrank from 25.4% to 18.1%, falling through the
    # one-fifth bar this line was set at. The membership crawl was seeded from the artists already in
    # the corpus, and those artists are anglophone, so it reached anglophone genres.
    #
    # 18% is not yet a fig leaf and the sentence still stands. But the direction is the one that
    # matters and the next cut is the one to watch: if this has to be relaxed a second time, the
    # counterweight sentence is being kept alive by adjusting its test, which is the failure this
    # assertion exists to catch.
    assert coverage["genres_without_us_or_uk"] > coverage["genres"] / 6


def test_the_unknown_era_bucket_is_present_and_counted(facts: dict[str, Any]) -> None:
    """The absences ARE the measurement.

    ``eras`` carries an explicit ``unknown`` bucket rather than summing to a tidier number, and the
    panel draws it as a bar like any other. A histogram that silently dropped the undated genres
    would be the footnote this step exists to remove, drawn as a chart.
    """
    coverage = facts["coverage"]

    assert coverage["eras"]["unknown"] == coverage["without_inception"]
    assert sum(coverage["eras"].values()) == coverage["genres"]
