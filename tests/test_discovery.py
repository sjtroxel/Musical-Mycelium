"""Discovery tests: the pure layer, with no network.

The crawl itself cannot be unit-tested — it is 15 minutes of politely rate-limited requests against
Wikimedia. What *can* be tested is everything on either side of it, and that is why
:mod:`~musical_mycelium.ingest.discovery` splits along the same line
:mod:`~musical_mycelium.ingest.prosecheck` does: SPARQL parsing, de-duplication, the type filter, the
per-subject fetch plan, the screening partition and the round trip are all pure functions of their
arguments, so a fake ``sparql`` and a dict of fixture ``Article`` objects exercise the whole pipeline.

The bindings below are shaped exactly like WDQS output, including the two things that bite: a
``(subject, object)`` pair carrying more than one statement, and ``objInAxis`` arriving as the
*string* ``"true"`` rather than a boolean.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.ingest.discovery import (
    EXPECTED_POPULATION,
    NOT_A_GENRE,
    Candidate,
    DiscoveryError,
    Screening,
    check_candidate,
    discover,
    exclusion_for,
    format_report,
    parse_discovery,
    population_drift,
    run,
    screen_candidates,
    subject_titles,
    type_filter,
)
from musical_mycelium.ingest.prosecheck import Article, Entity, Tier

WD = "http://www.wikidata.org/entity/"
ST = "http://www.wikidata.org/entity/statement/"


def binding(subject: str, obj: str, statement: str, is_genre: bool = True) -> dict[str, Any]:
    return {
        "s": {"value": WD + subject},
        "o": {"value": WD + obj},
        "statement": {"value": ST + statement},
        "objInAxis": {"value": "true" if is_genre else "false"},
    }


#: blues rock <- blues, heavy metal <- blues rock, and doom metal <- Black Sabbath. The third is the
#: real shape of filter (1): P737 is a general influence property and a band is a legitimate object
#: of it, just not one this project's graph can carry.
BINDINGS = [
    binding("Q193355", "Q9759", "s1"),
    binding("Q38848", "Q193355", "s2"),
    binding("Q131755", "Q131144", "s3", is_genre=False),
]

ENTITIES = {
    "Q193355": Entity("Q193355", label="blues rock", enwiki_title="Blues rock"),
    "Q9759": Entity("Q9759", label="blues", enwiki_title="Blues"),
    "Q38848": Entity("Q38848", label="heavy metal music", enwiki_title="Heavy metal music"),
    "Q131755": Entity("Q131755", label="doom metal", enwiki_title="Doom metal"),
    "Q131144": Entity("Q131144", label="Black Sabbath", enwiki_title="Black Sabbath"),
}

BLUES_ROCK_ARTICLE = Article(
    requested_title="Blues rock",
    resolved_title="Blues rock",
    wikitext=(
        "Blues rock is a fusion genre that developed when musicians took the blues and played it "
        "with rock instrumentation.\n"
        "[[Category:Blues music genres]]\n"
    ),
)

HEAVY_METAL_ARTICLE = Article(
    requested_title="Heavy metal music",
    resolved_title="Heavy metal music",
    wikitext="Heavy metal developed out of blues rock and psychedelic rock in the late 1960s.\n",
)


# --- parsing ---------------------------------------------------------------------------------------


def test_parse_extracts_qids_statement_uri_and_genreness() -> None:
    candidates = parse_discovery(BINDINGS)

    assert [c.pair for c in candidates] == [
        ("Q131755", "Q131144"),
        ("Q193355", "Q9759"),
        ("Q38848", "Q193355"),
    ]
    by_pair = {c.pair: c for c in candidates}
    assert by_pair[("Q193355", "Q9759")].statement_uri == ST + "s1"
    assert by_pair[("Q193355", "Q9759")].object_in_axis is True
    assert by_pair[("Q131755", "Q131144")].object_in_axis is False


def test_parse_deduplicates_pairs_deterministically() -> None:
    """A pair with two statements collapses to one candidate, and always to the same one.

    The statement URI reaches the artifact, and the artifact is hashed, so a non-deterministic pick
    would make ``manifest.sha256`` vary between runs over identical source data.
    """
    rows = [
        binding("Q193355", "Q9759", "zzz"),
        binding("Q193355", "Q9759", "aaa"),
    ]

    assert parse_discovery(rows) == parse_discovery(list(reversed(rows)))
    assert parse_discovery(rows)[0].statement_uri == ST + "aaa"


def test_parse_rejects_a_malformed_row_rather_than_skipping_it() -> None:
    with pytest.raises(DiscoveryError, match="malformed"):
        parse_discovery([{"s": {"value": WD + "Q1"}}])


def test_population_drift_warns_on_a_collapsed_result_set_but_not_on_growth() -> None:
    """A partially degraded WDQS returning fewer rows looks exactly like a successful query.

    Warning rather than raising is the deliberate choice: Wikidata is a live corpus and ordinary
    editing moves this number, so the response to drift is to look at it, not to refuse to run.
    """
    assert population_drift(EXPECTED_POPULATION) == ""
    assert population_drift(int(EXPECTED_POPULATION * 1.2)) == ""
    assert "below" in population_drift(12)
    assert "above" in population_drift(EXPECTED_POPULATION * 3)
    assert population_drift(0) == "no candidates discovered"


def test_discover_refuses_an_empty_result() -> None:
    """An empty candidate set is a broken query, not a corpus of zero genres.

    Screening it would write a perfectly reconciled, perfectly empty screening file — which is the
    kind of confidently wrong output the whole prose-check exercise exists to prevent.
    """
    with pytest.raises(DiscoveryError, match="no rows"):
        discover(lambda _query: [])


# --- filter (1): type ------------------------------------------------------------------------------


def test_type_filter_splits_on_object_genreness() -> None:
    kept, dropped = type_filter(parse_discovery(BINDINGS))

    assert [c.pair for c in kept] == [("Q193355", "Q9759"), ("Q38848", "Q193355")]
    assert [e.object_id for e in dropped] == ["Q131144"]
    assert dropped[0].reason_code == NOT_A_GENRE


def test_type_filter_names_the_excluded_entity_when_labels_are_available() -> None:
    labels = {qid: entity.label for qid, entity in ENTITIES.items()}
    _, dropped = type_filter(parse_discovery(BINDINGS), labels)

    assert dropped[0].object_label == "Black Sabbath"
    assert "Black Sabbath (Q131144)" in dropped[0].reason


# --- filter (2): the crawl plan and the screening --------------------------------------------------


def test_subject_titles_are_keyed_per_subject_not_per_edge() -> None:
    """Four edges out of one genre are one article fetch. Most of the crawl's wall time is this."""
    candidates = tuple(
        Candidate("Q221772", obj, ST + str(i), True)
        for i, obj in enumerate(("Q8341", "Q164444", "Q131272", "Q11401"))
    )
    entities = {"Q221772": Entity("Q221772", label="acid jazz", enwiki_title="Acid jazz")}

    assert subject_titles(candidates, entities) == {"Q221772": "Acid jazz"}


def test_a_subject_with_no_sitelink_is_no_article_not_an_error() -> None:
    """35% of the 7/31 population had no English article. That is a coverage fact, not a failure."""
    candidates = (Candidate("Q404", "Q9759", ST + "s", True),)
    checks, excluded = screen_candidates(candidates, ENTITIES, articles={})

    assert checks[0].tier is Tier.NO_ARTICLE
    assert excluded[0].reason_code == "NO_ARTICLE"


def test_screening_partitions_accepted_from_excluded() -> None:
    candidates, _ = type_filter(parse_discovery(BINDINGS))
    articles = {"Q193355": BLUES_ROCK_ARTICLE, "Q38848": HEAVY_METAL_ARTICLE}

    checks, excluded = screen_candidates(candidates, ENTITIES, articles)

    assert all(check.tier is Tier.PROSE for check in checks)
    assert excluded == ()


def test_check_candidate_passes_aliases_through_to_the_prose_check() -> None:
    """The alias path is the fix for the under-accept defect, so it has to actually be wired."""
    entities = {
        "Q20474": Entity("Q20474", label="dubstep", enwiki_title="Dubstep"),
        "Q212688": Entity("Q212688", label="dub music", enwiki_title="Dub", aliases=("dub",)),
    }
    article = Article(
        requested_title="Dubstep",
        resolved_title="Dubstep",
        wikitext="Dubstep is characterised by sparse dub production and heavy bass.\n",
    )

    check = check_candidate(Candidate("Q20474", "Q212688", ST + "s", True), entities, article)

    assert check.tier is Tier.PROSE
    assert {name.casefold() for name in check.matched_names} == {"dub"}


def test_exclusion_carries_the_tier_as_its_machine_readable_code() -> None:
    candidates = (Candidate("Q1", "Q9759", ST + "s", True),)
    entities = {"Q1": Entity("Q1", label="nowhere", enwiki_title="Nowhere")}
    orphan = Article(requested_title="Nowhere", resolved_title="Nowhere", wikitext="Unrelated.\n")

    checks, _ = screen_candidates(candidates, entities, {"Q1": orphan})
    exclusion = exclusion_for(checks[0])

    assert exclusion.reason_code == "ORPHAN"
    assert "never mentions" in exclusion.reason


# --- the whole pipeline, and the bookkeeping -------------------------------------------------------


@pytest.fixture
def screening(monkeypatch: pytest.MonkeyPatch) -> Screening:
    """A full ``run()`` with the two network calls replaced. Exercises every stage."""
    monkeypatch.setattr(
        "musical_mycelium.ingest.prosecheck.fetch_entities",
        lambda qids, pause=1.0: {q: ENTITIES[q] for q in qids if q in ENTITIES},
    )
    articles = {"Blues rock": BLUES_ROCK_ARTICLE, "Heavy metal music": HEAVY_METAL_ARTICLE}
    monkeypatch.setattr(
        "musical_mycelium.ingest.prosecheck.resolve_article",
        lambda title, pause=1.0: articles[title],
    )
    return run(sparql=lambda _query: BINDINGS, pause=0.0)


def test_run_reconciles_every_discovered_candidate(screening: Screening) -> None:
    """Nothing may be dropped off the books. The exclusion rate is a published coverage number."""
    tally = screening.tally()

    assert screening.reconciles()
    assert tally["discovered"] == 3
    assert tally["accepted"] == 2
    assert tally[NOT_A_GENRE] == 1
    assert tally["discovered"] == tally["accepted"] + tally["excluded"]


def test_run_yields_pairs_and_statement_uris_for_the_artifact_build(screening: Screening) -> None:
    """``wikidata.build`` needs both, and getting them here saves a second WDQS round trip."""
    assert screening.pairs == (("Q193355", "Q9759"), ("Q38848", "Q193355"))
    assert screening.statement_uris()[("Q193355", "Q9759")] == ST + "s1"


def test_limit_slices_after_discovery_so_a_slice_run_exercises_the_real_pipeline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "musical_mycelium.ingest.prosecheck.fetch_entities",
        lambda qids, pause=1.0: {q: ENTITIES[q] for q in qids if q in ENTITIES},
    )
    monkeypatch.setattr(
        "musical_mycelium.ingest.prosecheck.resolve_article",
        lambda title, pause=1.0: BLUES_ROCK_ARTICLE,
    )

    sliced = run(sparql=lambda _query: BINDINGS, pause=0.0, limit=1)

    assert len(sliced.accepted) == 1
    assert sliced.pairs == (("Q193355", "Q9759"),)


def test_screening_round_trips_through_json(screening: Screening, tmp_path: Path) -> None:
    """The cache is what stops a bug costing another 15 minutes of crawling."""
    path = screening.write(tmp_path / "screening.json")
    reloaded = Screening.load(path)

    assert reloaded == screening
    assert reloaded.checks[0].tier is Tier.PROSE


def test_report_states_the_counts_and_the_accepted_edges(screening: Screening) -> None:
    report = format_report(screening)

    assert "discovered" in report and "accepted" in report
    assert NOT_A_GENRE in report
    assert "blues rock <- blues" in report
    assert "WARNING" not in report
