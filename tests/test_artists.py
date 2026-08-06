"""``ingest.artists`` — the artist axis's bound, its query, and the assertion tier applied to a crawl.

The module had no tests before 2026-08-06. These cover the pure parts: what bounds the population, what
the query asks for, and how an existing screening is tiered. The networked path (``run_outgoing``) is
exercised by the real crawl rather than by a mock of four services, on the same reasoning
``test_prosecheck`` uses — a fixture that lies about what the live fetch returns is worse than no
fixture, and this axis has already been bitten by exactly that (scope doc A6.6).
"""

from __future__ import annotations

import pytest

from musical_mycelium.graph.schema import (
    NODE_KIND_ARTIST,
    NODE_KIND_GENRE,
    VERIFICATION_ASSERTS_AUTO,
    VERIFICATION_EXPOSURE_AUTO,
    Artifact,
)
from musical_mycelium.ingest import artists
from musical_mycelium.ingest.assertion import Assertion
from musical_mycelium.ingest.discovery import Candidate, DiscoveryError, Screening
from musical_mycelium.ingest.prosecheck import Entity, ProseCheck, Tier
from musical_mycelium.ingest.wikidata import artifact_dir

# --- the bound --------------------------------------------------------------------------------


def test_an_unbounded_crawl_is_refused() -> None:
    """The bound is the whole scope control. Unbounded this is 28,150 statements, which is not what
    the phase scopes, and the failure has to be loud rather than a slow crawl nobody cancelled."""
    with pytest.raises(DiscoveryError, match="28,150"):
        artists.Bound(()).values()


def test_the_bound_is_the_corpus_genres_and_only_the_genres() -> None:
    """Filters on ``kind`` rather than assuming it. Once artists are in the artifact, bounding an
    artist crawl by artists would make the population self-selecting."""
    artifact = Artifact.load(artifact_dir())
    genre_ids = artists.corpus_genre_ids()

    assert len(genre_ids) == sum(1 for n in artifact.nodes if n.kind == NODE_KIND_GENRE)
    assert genre_ids == tuple(sorted(genre_ids)), "sorted, so the query text is reproducible"
    assert all(qid.startswith("Q") for qid in genre_ids)


def test_the_query_carries_the_bound_and_both_axis_types() -> None:
    query = artists.outgoing_query(artists.Bound(("Q9759", "Q8341")))

    assert "wd:Q9759" in query and "wd:Q8341" in query
    assert f"wd:{artists.QID_HUMAN}" in query
    assert f"wd:{artists.QID_MUSICAL_GROUP} " in query
    # p:/ps: rather than wdt:, because an edge has to cite a statement URI and wdt: does not carry one.
    assert f"p:{artists.PROPERTY_INFLUENCED_BY} ?statement" in query
    # The bound is P136, never P737 — using the ingested edge as its own bound is self-selection.
    assert f"wdt:{artists.PROPERTY_GENRE} ?corpusGenre" in query


# --- the assertion tier over a screening ------------------------------------------------------


def a_check(sentence: str, tier: Tier = Tier.PROSE) -> ProseCheck:
    return ProseCheck(
        subject_id="Q1",
        object_id="Q2",
        tier=tier,
        subject_label="alpha",
        object_label="beta",
        sentences=(sentence,),
    )


def a_screening(*checks: ProseCheck) -> Screening:
    return Screening(generated_at="2026-08-06T00:00:00+00:00", query="", checks=checks)


ASSERTS_SENTENCE = "He has cited Beta as a major influence on his songwriting."
EXPOSURE_SENTENCE = "As a teenager he listened to Beta constantly."
NONE_SENTENCE = "Beta played the same festival that summer."


def test_tier_of_reads_the_supporting_sentences() -> None:
    assert artists.tier_of(a_check(ASSERTS_SENTENCE)) is Assertion.ASSERTS
    assert artists.tier_of(a_check(EXPOSURE_SENTENCE)) is Assertion.EXPOSURE
    assert artists.tier_of(a_check(NONE_SENTENCE)) is Assertion.NONE


def test_the_tally_reports_all_three_outcomes_including_the_zeroes() -> None:
    """``NONE`` is the count of edges the prose check passed and the filter then refused — the single
    number that says what 6a was worth. A tally that omitted it would hide the answer."""
    tally = artists.assertion_tally(a_screening(a_check(ASSERTS_SENTENCE)))

    assert set(tally) == {str(Assertion.ASSERTS), str(Assertion.EXPOSURE), str(Assertion.NONE)}
    assert tally[str(Assertion.ASSERTS)] == 1
    assert tally[str(Assertion.EXPOSURE)] == 0
    assert tally[str(Assertion.NONE)] == 0


def test_only_prose_accepted_checks_are_tiered() -> None:
    """The filter runs on what the prose check accepted, not on everything crawled. An INFOBOX_ONLY
    row has no body prose to classify, so counting it would inflate every tier."""
    screening = a_screening(
        a_check(ASSERTS_SENTENCE),
        a_check(ASSERTS_SENTENCE, tier=Tier.INFOBOX_ONLY),
        a_check(ASSERTS_SENTENCE, tier=Tier.ORPHAN),
    )
    assert artists.assertion_tally(screening)[str(Assertion.ASSERTS)] == 1


def test_an_empty_screening_does_not_tier_anything() -> None:
    """The vacuous-truth guard ``.claude/rules/evals.md`` requires: nothing in, zeroes out, and no
    key silently missing."""
    tally = artists.assertion_tally(a_screening())
    assert set(tally) == {str(Assertion.ASSERTS), str(Assertion.EXPOSURE), str(Assertion.NONE)}
    assert sum(tally.values()) == 0


# --- the report -------------------------------------------------------------------------------


def test_the_report_shows_the_assertion_split_and_the_exposure_caveat() -> None:
    """The split is the reason this axis needed 6a at all, and the 20% recall caveat travels with the
    number rather than living only in a doc — quoting EXPOSURE without it overstates the corpus."""
    report = artists.format_report(
        a_screening(a_check(ASSERTS_SENTENCE), a_check(EXPOSURE_SENTENCE), a_check(NONE_SENTENCE))
    )

    assert "assertion filter" in report
    assert "ingestable (ASSERTS + EXPOSURE): 2" in report
    assert "20%" in report, "the exposure recall caveat must ship with the count"
    assert "alpha <- beta" in report


def test_the_report_names_the_artist_axis() -> None:
    """``run_outgoing``'s docstring makes the case: progress output that says "genre" while crawling
    artists is how two axes get conflated in someone's head before they get conflated in the data."""
    assert "Artist axis" in artists.format_report(a_screening(a_check(ASSERTS_SENTENCE)))


# --- artist_rows: what a screening actually earns ---------------------------------------------


WHEN = "2026-08-06T00:00:00+00:00"


def pair_check(subject: str, obj: str, sentence: str) -> ProseCheck:
    return ProseCheck(
        subject_id=subject,
        object_id=obj,
        tier=Tier.PROSE,
        subject_label=f"artist {subject}",
        object_label=f"artist {obj}",
        sentences=(sentence,),
    )


def rowable(*checks: ProseCheck, labels: dict[str, str] | None = None) -> Screening:
    """A screening complete enough to build rows from: candidates carry the statement URIs."""
    ids = sorted({q for check in checks for q in (check.subject_id, check.object_id)})
    entities = {qid: Entity(qid=qid, label=(labels or {}).get(qid, f"artist {qid}")) for qid in ids}
    candidates = tuple(
        Candidate(
            subject_id=check.subject_id,
            object_id=check.object_id,
            statement_uri=(
                f"http://www.wikidata.org/entity/statement/{check.subject_id}-{check.object_id}"
            ),
            object_in_axis=True,
        )
        for check in checks
    )
    return Screening(
        generated_at=WHEN, query="", candidates=candidates, checks=checks, entities=entities
    )


def test_only_asserts_and_exposure_become_edges() -> None:
    """The entire point of 6a. On this axis the prose check alone accepts recording trucks, cover
    versions and support slots, so a ``NONE`` is a refusal and not a weaker tier."""
    screening = rowable(
        pair_check("Q1", "Q2", ASSERTS_SENTENCE),
        pair_check("Q3", "Q4", EXPOSURE_SENTENCE),
        pair_check("Q5", "Q6", NONE_SENTENCE),
    )
    rows = artists.artist_rows(screening, retrieved_at=WHEN)

    assert {(e.subject_id, e.object_id) for e in rows.edges} == {("Q1", "Q2"), ("Q3", "Q4")}
    by_pair = {(e.subject_id, e.object_id): e.verification for e in rows.edges}
    assert by_pair[("Q1", "Q2")] == VERIFICATION_ASSERTS_AUTO
    assert by_pair[("Q3", "Q4")] == VERIFICATION_EXPOSURE_AUTO


def test_nodes_come_from_surviving_edges_not_from_the_crawl() -> None:
    """An artist who appears only in refused candidates is not in the corpus. A node with no edge is
    a name the product cannot say anything grounded about."""
    screening = rowable(
        pair_check("Q1", "Q2", ASSERTS_SENTENCE),
        pair_check("Q5", "Q6", NONE_SENTENCE),
    )
    rows = artists.artist_rows(screening, retrieved_at=WHEN)

    assert {n.id for n in rows.nodes} == {"Q1", "Q2"}
    assert "Q5" not in {n.id for n in rows.nodes}, (
        "a refused candidate must not leave a node behind"
    )


def test_every_artist_node_is_typed_as_an_artist() -> None:
    rows = artists.artist_rows(rowable(pair_check("Q1", "Q2", ASSERTS_SENTENCE)), retrieved_at=WHEN)
    assert rows.nodes and all(node.kind == NODE_KIND_ARTIST for node in rows.nodes)


def test_revision_ids_are_carried_when_supplied() -> None:
    """Provenance parity with the genre axis: those nodes pin the exact revision read."""
    rows = artists.artist_rows(
        rowable(pair_check("Q1", "Q2", ASSERTS_SENTENCE)),
        retrieved_at=WHEN,
        revisions={"Q1": 999, "Q2": 1000},
    )
    assert {n.id: n.revision_id for n in rows.nodes} == {"Q1": 999, "Q2": 1000}


def test_an_edge_whose_citation_does_not_name_its_subject_is_excluded() -> None:
    """``agent.claims.resolve_sources`` resolves a citation by matching the statement URI's entity to
    the edge's subject. An edge that fails that match could never be approved, so ingesting it would
    put a row in the corpus that is present in every count and absent from every answer.
    **3 real edges hit this on the 2026-08-06 crawl.**"""
    screening = rowable(pair_check("Q1", "Q2", ASSERTS_SENTENCE))
    stripped = Screening(
        generated_at=WHEN,
        query="",
        candidates=(),
        checks=screening.checks,
        entities=screening.entities,
    )
    rows = artists.artist_rows(stripped, retrieved_at=WHEN)

    assert rows.edges == () and rows.nodes == ()
    assert [e.reason_code for e in rows.excluded] == [artists.UNCITABLE_STATEMENT]


def test_an_unlabelled_entity_is_excluded_and_reported() -> None:
    """Row 41 of the held-out set, encoded (scope doc A6.6). An entity with no English label cleared
    the type filter, and an empty name matches anywhere, so it silently inherited another row's
    evidence. **14 real endpoints hit this on the crawl.**"""
    screening = rowable(pair_check("Q1", "Q2", ASSERTS_SENTENCE), labels={"Q2": ""})
    rows = artists.artist_rows(screening, retrieved_at=WHEN)

    assert rows.edges == ()
    assert [e.reason_code for e in rows.excluded] == [artists.NO_LABEL]


def test_one_bad_row_does_not_abort_the_build() -> None:
    """The brittleness that matters here. An early version raised on the first unlabelled entity,
    which would have thrown away 834 good edges over 14 bad endpoints — and the input costs a
    20-minute crawl to regenerate. Exclusions are reported, never raised and never silently dropped."""
    screening = rowable(
        pair_check("Q1", "Q2", ASSERTS_SENTENCE),
        pair_check("Q3", "Q4", ASSERTS_SENTENCE),
        labels={"Q4": ""},
    )
    rows = artists.artist_rows(screening, retrieved_at=WHEN)

    assert [(e.subject_id, e.object_id) for e in rows.edges] == [("Q1", "Q2")]
    assert len(rows.excluded) == 1
    assert rows.tally() == {"nodes": 2, "edges": 1, artists.NO_LABEL: 1}


def test_an_empty_screening_earns_no_rows() -> None:
    """The vacuous-truth guard again: nothing in, nothing out, and no crash on the way."""
    rows = artists.artist_rows(a_screening(), retrieved_at=WHEN)
    assert rows.nodes == () and rows.edges == () and rows.excluded == ()
