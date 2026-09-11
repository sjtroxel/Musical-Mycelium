"""The v0.10.0 layer, phase 7.6 step 5, over synthetic inputs. No network.

Everything here runs the same pure functions ``--build`` runs, on inputs small enough to know the answer
by construction. The real crawl is 40 minutes of Wikipedia; a logic bug should cost seconds instead.
"""

from __future__ import annotations

import dataclasses
from typing import Any

import pytest

from musical_mycelium.graph.schema import (
    NODE_KIND_ARTIST,
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    PREDICATE_PLAYS_GENRE,
    PREDICATE_STUDIED_WITH,
    PROSE_TIER_NOT_APPLICABLE,
    SOURCE_WIKIDATA,
    VERIFICATION_ASSERTS_AUTO,
    VERIFICATION_MEMBERSHIP_CITED,
    VERIFICATION_TEACHING_PROSE_AUTO,
    Artifact,
    Edge,
    Node,
)
from musical_mycelium.ingest.discovery import Candidate, Screening
from musical_mycelium.ingest.lineage import (
    DEPRECATED,
    HAND_REJECTED,
    NO_LABEL,
    UNCITABLE_STATEMENT,
    Crawl,
    Dated,
    apply_dates,
    build,
    classify,
    label_collisions,
    parse_dates,
    recovery_candidates,
    select_memberships,
    succession_only,
    teaching_rows,
    unlabelled,
    year_of,
    younger_teachers,
)
from musical_mycelium.ingest.membership import Membership
from musical_mycelium.ingest.prosecheck import Entity, ProseCheck, Tier

STAMP = "2026-09-11T00:00:00+00:00"
ST = "http://www.wikidata.org/entity/statement/"


def _node(qid: str, label: str, kind: str = NODE_KIND_ARTIST, **extra: Any) -> Node:
    return Node(
        id=qid,
        label=label,
        kind=kind,
        source=SOURCE_WIKIDATA,
        source_id=qid,
        retrieved_at=STAMP,
        **extra,
    )


def _edge(s: str, p: str, o: str, verification: str, tier: str = "PROSE") -> Edge:
    return Edge(
        subject_id=s,
        predicate=p,
        object_id=o,
        source=SOURCE_WIKIDATA,
        source_id=f"{ST}{s}-{o}",
        retrieved_at=STAMP,
        prose_tier=tier,
        verification=verification,
    )


def _check(s: str, o: str, *sentences: str, tier: Tier = Tier.PROSE) -> ProseCheck:
    return ProseCheck(subject_id=s, object_id=o, tier=tier, sentences=tuple(sentences))


def _screening(
    checks: tuple[ProseCheck, ...],
    labels: dict[str, str],
    uris: dict[tuple[str, str], str] | None = None,
) -> Screening:
    uris = uris or {}
    return Screening(
        generated_at=STAMP,
        query="",
        candidates=tuple(
            Candidate(
                c.subject_id,
                c.object_id,
                uris.get((c.subject_id, c.object_id), f"{ST}{c.subject_id}-{c.object_id}"),
                True,
            )
            for c in checks
        ),
        checks=checks,
        entities={q: Entity(qid=q, label=label) for q, label in labels.items()},
    )


def _date_row(
    q: str, prop: str, time: str, precision: int, rank: str = "NormalRank"
) -> dict[str, Any]:
    return {
        "q": {"value": f"http://www.wikidata.org/entity/{q}"},
        "prop": {"value": prop},
        "time": {"value": time},
        "precision": {"value": str(precision)},
        "rank": {"value": f"http://wikiba.se/ontology#{rank}"},
    }


# --- dates ------------------------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("value", "year"),
    [
        ("1756-01-27T00:00:00Z", 1756),
        ("+1756-01-27T00:00:00Z", 1756),
        ("0500-01-01T00:00:00Z", 500),
        # The case coverage.parse_coverage's split-on-"-" would read as a crash or a wrong year.
        ("-0500-01-01T00:00:00Z", -500),
    ],
)
def test_year_of_keeps_the_sign(value: str, year: int) -> None:
    assert year_of(value) == year


def test_year_of_refuses_what_is_not_a_time_value() -> None:
    with pytest.raises(ValueError):
        year_of("sometime in the 1750s")


def test_best_rank_wins_then_the_earliest_year() -> None:
    rows = [
        _date_row("Q1", "P569", "1750-01-01T00:00:00Z", 9),
        _date_row("Q1", "P569", "1756-01-27T00:00:00Z", 11, "PreferredRank"),
        _date_row("Q2", "P569", "1612-01-01T00:00:00Z", 9),
        _date_row("Q2", "P569", "1601-01-01T00:00:00Z", 7),
        _date_row("Q3", "P571", "1962-01-01T00:00:00Z", 9),
    ]
    dated = parse_dates(rows)
    assert (dated["Q1"].birth_year, dated["Q1"].birth_precision) == (1756, 11), (
        "preferred beats earlier"
    )
    assert (dated["Q2"].birth_year, dated["Q2"].birth_precision) == (1601, 7), "same rank: earliest"
    assert dated["Q3"].inception_year == 1962 and dated["Q3"].birth_year is None


def test_people_get_birth_groups_get_inception_genres_nothing() -> None:
    person = apply_dates(_node("Q1", "a composer"), Dated(birth_year=1756, birth_precision=11))
    assert (person.birth_year, person.inception_year) == (1756, None)
    group = apply_dates(_node("Q2", "a band"), Dated(inception_year=1962, inception_precision=9))
    assert (group.birth_year, group.inception_year) == (None, 1962)
    both = apply_dates(
        _node("Q3", "a person with a P571"), Dated(birth_year=1800, inception_year=1850)
    )
    assert (both.birth_year, both.inception_year) == (1800, None), (
        "a person's P571 is not formation"
    )
    genre = _node("Q4", "a genre", kind=NODE_KIND_GENRE)
    assert apply_dates(genre, Dated(birth_year=1800)) == genre


# --- (a) recovery ---------------------------------------------------------------------------------------


def test_unlabelled_entities_and_the_candidates_they_touch() -> None:
    screening = Screening(
        generated_at=STAMP,
        query="",
        candidates=(
            Candidate("Q254", "Q7349", f"{ST}Q254-a", True),
            Candidate("Q255", "Q254", f"{ST}Q255-b", True),
            Candidate("Q255", "Q7349", f"{ST}Q255-c", True),
        ),
        entities={
            "Q254": Entity(qid="Q254", label=""),
            "Q255": Entity(qid="Q255", label="Ludwig van Beethoven"),
        },
    )
    assert unlabelled(screening) == ("Q254",)
    touched = recovery_candidates(screening, ("Q254",))
    assert {c.pair for c in touched} == {("Q254", "Q7349"), ("Q255", "Q254")}


# --- (b) teaching rows -----------------------------------------------------------------------------------


def test_teaching_rows_keep_prose_and_refuse_what_cannot_be_cited_or_named() -> None:
    checks = (
        _check("Q9", "Q255", "Czerny was one of Beethoven's best-known pupils."),
        _check("Q8", "Q7", "pupil of someone"),
        _check("Q6", "Q5", "studied with a teacher"),
        _check("Q4", "Q3", "studied with X"),
        _check("Q2", "Q1", "studied with Y"),
        _check("Q20", "Q21", "never mentioned", tier=Tier.ORPHAN),
    )
    labels = {q: f"person {q}" for q in ("Q9", "Q255", "Q7", "Q6", "Q5", "Q4", "Q3", "Q2", "Q1")}
    labels["Q7"] = ""  # unlabelled endpoint
    uris = {("Q6", "Q5"): f"{ST}Q999-x", ("Q4", "Q3"): f"{ST}Q4-dep"}
    rows = teaching_rows(
        _screening(checks, labels, uris),
        retrieved_at=STAMP,
        deprecated=frozenset({f"{ST}Q4-dep"}),
        rejected=(("Q2", "Q1", "a colleague, not a teacher"),),
    )
    assert [(e.subject_id, e.object_id) for e in rows.edges] == [("Q9", "Q255")]
    edge = rows.edges[0]
    assert (edge.predicate, edge.verification) == (
        PREDICATE_STUDIED_WITH,
        VERIFICATION_TEACHING_PROSE_AUTO,
    )
    assert {e.reason_code for e in rows.excluded} == {
        NO_LABEL,
        UNCITABLE_STATEMENT,
        DEPRECATED,
        HAND_REJECTED,
    }
    assert {n.id for n in rows.nodes} == {"Q9", "Q255"}, "nodes come from surviving edges only"


def test_the_succession_shape_is_found_and_study_overrides_it() -> None:
    assert succession_only(("Canis became master of the choirboys, succeeding Nicolas Gombert.",))
    assert not succession_only(("He was a pupil of Pasquini, whom he succeeded in 1704.",))
    assert not succession_only(("He studied with Pablo Bruna.",))
    assert not succession_only(())
    # The three the first real build miscalled, 2026-09-11: each names study in words the detector
    # did not yet know.
    assert not succession_only(
        (
            "Parry had by then succeeded Sir George Grove as director of the college, and Vaughan "
            "Williams's new professor of composition was Charles Villiers Stanford.",
        )
    )
    assert not succession_only(
        ("Leoni succeeded Giammateo Asola, his master, as maestro di capella.",)
    )
    assert not succession_only(("He learnt counterpoint from the man he later succeeded.",))


def test_a_younger_teacher_is_listed_not_removed() -> None:
    nodes = {
        "Q1": _node("Q1", "Sevenants", birth_year=1868),
        "Q2": _node("Q2", "Jongen", birth_year=1873),
        "Q3": _node("Q3", "Czerny", birth_year=1791),
        "Q4": _node("Q4", "Beethoven", birth_year=1770),
    }
    edges = [
        _edge("Q1", PREDICATE_STUDIED_WITH, "Q2", VERIFICATION_TEACHING_PROSE_AUTO),
        _edge("Q3", PREDICATE_STUDIED_WITH, "Q4", VERIFICATION_TEACHING_PROSE_AUTO),
    ]
    found = younger_teachers(edges, nodes)
    assert [(e.subject_id, s, t) for e, s, t in found] == [("Q1", 1868, 1873)]


# --- (e) membership --------------------------------------------------------------------------------------


def _m(artist: str, genre: str, in_axis: bool = True) -> Membership:
    return Membership(artist, genre, f"{ST}{artist}-{genre}", True, in_axis)


def test_membership_selection_new_full_existing_allowlist_only() -> None:
    allow = {"Q7366": "song"}
    chosen = select_memberships(
        [
            _m("NEW", "Q1344"),  # new artist, typed genre: in
            _m("NEW", "Q7366", in_axis=False),  # new artist, allowlisted form: in
            _m("NEW", "Q41425", in_axis=False),  # new artist, not admitted (ballet the dance): out
            _m("OLD", "Q9730"),  # existing artist, typed genre: drift, out
            _m("OLD", "Q7366", in_axis=False),  # existing artist, allowlisted: in
            _m("GONE", "Q7366", in_axis=False),  # artist refused at build time: out
            _m("NEW", "Q9734"),  # already an edge: out
        ],
        new_artists=frozenset({"NEW"}),
        existing_artists=frozenset({"OLD"}),
        existing_edges=frozenset({("NEW", PREDICATE_PLAYS_GENRE, "Q9734")}),
        allowlist=allow,
    )
    assert {(m.artist_id, m.genre_id) for m in chosen} == {
        ("NEW", "Q1344"),
        ("NEW", "Q7366"),
        ("OLD", "Q7366"),
    }


def test_a_colliding_label_is_never_admitted() -> None:
    existing = [
        _node("Q4851628", "ballet", kind=NODE_KIND_GENRE),
        _node("Q8361", "Baroque music", kind=NODE_KIND_GENRE),
    ]
    collisions = label_collisions(
        {"Q41425": "ballet", "Q37853": "Baroque", "Q1": "a", "Q2": "A", "Q3": "new genre"},
        existing,
    )
    assert set(collisions) == {"Q41425", "Q37853", "Q1", "Q2"}, (
        "the music fold makes Baroque collide"
    )


# --- the diff ---------------------------------------------------------------------------------------------


def _source() -> Artifact:
    return Artifact(
        nodes=(
            _node("Q255", "Ludwig van Beethoven"),
            _node("Q7349", "Joseph Haydn"),
            _node("Q9730", "classical music", kind=NODE_KIND_GENRE),
        ),
        edges=(
            _edge("Q255", PREDICATE_INFLUENCED_BY, "Q7349", VERIFICATION_ASSERTS_AUTO),
            _edge(
                "Q255",
                PREDICATE_PLAYS_GENRE,
                "Q9730",
                VERIFICATION_MEMBERSHIP_CITED,
                PROSE_TIER_NOT_APPLICABLE,
            ),
        ),
    )


def test_a_clean_diff_is_classified() -> None:
    source = _source()
    result = Artifact(
        nodes=(
            *(
                n if n.id != "Q255" else _node("Q255", "Ludwig van Beethoven", birth_year=1770)
                for n in source.nodes
            ),
            _node("Q254", "Wolfgang Amadeus Mozart"),
        ),
        edges=(
            *source.edges,
            _edge("Q255", PREDICATE_STUDIED_WITH, "Q7349", VERIFICATION_TEACHING_PROSE_AUTO),
        ),
    )
    diff = classify(
        source, result, recovered=frozenset({"Q254"}), teaching=frozenset(), new_genres=frozenset()
    )
    assert diff.clean, diff.unclassified
    assert diff.counts == {"a: artist node": 1, "b: studied_with edge": 1, "c: birth_year set": 1}


@pytest.mark.parametrize(
    "tamper",
    ["remove an edge", "relabel a node", "add an unexplained node", "change an edge"],
)
def test_an_unclassifiable_change_is_caught(tamper: str) -> None:
    source = _source()
    nodes, edges = list(source.nodes), list(source.edges)
    if tamper == "remove an edge":
        edges.pop()
    elif tamper == "relabel a node":
        nodes[0] = _node("Q255", "Beethoven")
    elif tamper == "add an unexplained node":
        nodes.append(_node("Q1", "a stranger"))
    else:
        # Same triple, upgraded tier: the silent kind of change the diff exists to refuse.
        edges[0] = dataclasses.replace(edges[0], verification="HAND")
    diff = classify(
        source,
        Artifact(nodes=tuple(nodes), edges=tuple(edges)),
        recovered=frozenset(),
        teaching=frozenset(),
        new_genres=frozenset(),
    )
    assert not diff.clean


# --- the whole build, end to end ---------------------------------------------------------------------------


def test_build_adds_the_five_classes_and_nothing_else() -> None:
    source = _source()
    recovery = _screening(
        (_check("Q254", "Q7349", "Mozart was influenced by Haydn."),),
        {"Q254": "Wolfgang Amadeus Mozart", "Q7349": "Joseph Haydn"},
    )
    teaching = _screening(
        (
            _check("Q1", "Q255", "Czerny was one of Beethoven's best-known pupils."),
            _check("Q2", "Q3", "He took up the post, succeeding his predecessor Gombert."),
        ),
        {
            "Q1": "Carl Czerny",
            "Q255": "Ludwig van Beethoven",
            "Q2": "Cornelius Canis",
            "Q3": "Nicolas Gombert",
        },
    )
    crawl = Crawl(
        recovery=recovery,
        teaching=teaching,
        dates={
            "Q1": Dated(birth_year=1791, birth_precision=11),
            "Q255": Dated(birth_year=1770, birth_precision=11),
        },
        aliases={"Q254": ("Mozart",), "Q9730": ("art music",)},
        memberships=(
            Membership("Q1", "Q9730", f"{ST}Q1-g", True, True),
            Membership("Q254", "Q1344", f"{ST}Q254-g", True, True),
            Membership("Q255", "Q7366", f"{ST}Q255-g", False, False),
            Membership("Q2", "Q41425", f"{ST}Q2-g", False, False),
        ),
        genre_labels={"Q1344": "opera", "Q7366": "song"},
        genre_revisions={"Q1344": 1, "Q7366": 2},
        coverage_rows=[],
        deprecated=frozenset(),
    )
    built = build(crawl, source, retrieved_at=STAMP)
    assert built.diff.clean, built.diff.unclassified
    triples = {(e.subject_id, e.predicate, e.object_id) for e in built.artifact.edges}
    assert ("Q254", PREDICATE_INFLUENCED_BY, "Q7349") in triples, "(a) Mozart recovered"
    assert ("Q1", PREDICATE_STUDIED_WITH, "Q255") in triples, "(b) Czerny studied with Beethoven"
    assert ("Q1", PREDICATE_PLAYS_GENRE, "Q9730") in triples, "(e) new artist, typed genre"
    assert ("Q254", PREDICATE_PLAYS_GENRE, "Q1344") in triples, (
        "(e) recovered artist, new genre node"
    )
    assert ("Q255", PREDICATE_PLAYS_GENRE, "Q7366") in triples, (
        "(e) existing artist, allowlisted form"
    )
    assert all(o != "Q41425" for _, _, o in triples), "ballet the dance is never admitted"
    nodes = {n.id: n for n in built.artifact.nodes}
    assert nodes["Q1"].birth_year == 1791, "(c)"
    assert nodes["Q254"].aliases == ("Mozart",), "(d)"
    assert nodes["Q9730"].aliases == ("art music",), "(d) genres too"
    assert [s for s, _, _ in built.succession] == ["Q2"], (
        "Canis's succession-only sentence is measured"
    )
    assert "Q2" in built.no_genre and "Q3" in built.no_genre, "no P136: counted, never inferred"


# --- dates from the entity API ----------------------------------------------------------------------


def _claim(
    time: str, precision: int, rank: str = "normal", snaktype: str = "value"
) -> dict[str, Any]:
    snak: dict[str, Any] = {"snaktype": snaktype}
    if snaktype == "value":
        snak["datavalue"] = {"value": {"time": time, "precision": precision}}
    return {"rank": rank, "mainsnak": snak}


def test_entity_api_claims_become_the_rows_parse_dates_reads() -> None:
    """The 2026-09-11 switch from SPARQL to ``wbgetentities`` must not move a single date."""
    from musical_mycelium.ingest.lineage import date_rows_from_entities

    entities = {
        "Q254": {
            "claims": {
                "P569": [
                    _claim("+1756-01-27T00:00:00Z", 11, "preferred"),
                    _claim("+1750-01-01T00:00:00Z", 9),
                    _claim("+1700-01-01T00:00:00Z", 9, "deprecated"),
                    _claim("", 0, "normal", snaktype="somevalue"),
                ]
            }
        },
        "Q2": {"claims": {"P571": [_claim("+1962-01-01T00:00:00Z", 9)]}},
        "Q3": {"claims": {}},
    }
    rows = date_rows_from_entities(entities)
    assert len(rows) == 3, "deprecated and somevalue claims carry no usable date"
    dated = parse_dates(rows)
    assert (dated["Q254"].birth_year, dated["Q254"].birth_precision) == (1756, 11)
    assert dated["Q2"].inception_year == 1962
    assert "Q3" not in dated


# --- the reviewed exclusions ------------------------------------------------------------------------


def test_teaching_rejections_are_unique_explained_and_well_formed() -> None:
    """``TEACHING_REJECTED`` is the 2026-09-11 build review (``docs/p1066-build-review.md``): 18 distinct
    edges, each with its reason. A duplicate would hide a miscount; a blank reason would be an exclusion
    nobody can audit."""
    import re as _re

    from musical_mycelium.ingest.lineage import TEACHING_REJECTED

    pairs = [(s, o) for s, o, _ in TEACHING_REJECTED]
    assert len(pairs) == len(set(pairs)) == 18
    for subject, obj, reason in TEACHING_REJECTED:
        assert _re.fullmatch(r"Q\d+", subject) and _re.fullmatch(r"Q\d+", obj)
        assert subject != obj
        assert reason.strip()
