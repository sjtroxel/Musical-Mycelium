"""The guided tour's dataset: what it claims, and the one thing it exists to cover.

**This set is not more path coverage.** ``gold_v0_1`` already holds six ``path`` cases and they score
100%. What gold does not hold is a single **imperative** query -- all 38 of its cases are questions --
while the tour's own stated query in ``SPEC.md`` §1 is *"Take me from Detroit techno back to the blues."*
The phrasing the showcase surface uses had never been evaluated once. That gap is this set, and the tests
below are mostly about protecting that property from being diluted.

**Two cases are controlled pairs with gold**, asserted here rather than merely noted: same endpoints, same
expected path, different grammar. If a live run ever scores a pair differently, phrasing is the cause and
nothing else can be.

**This set must never gate and must never reach the live suite.** Two tests at the bottom hold that,
because the failure is expensive rather than loud: one extra case in a gated set trips
``thresholds.py:_ungateable`` and costs $2.61 and about 2.4 hours to restore the bounds.
"""

from __future__ import annotations

import json
from itertools import pairwise
from typing import Any

import pytest

from musical_mycelium.eval import gold
from musical_mycelium.eval.suite import TOUR_DATASET
from musical_mycelium.graph.memory import GraphStore, default_store
from musical_mycelium.graph.store import Direction

#: Locked. The set is small on purpose; a floor stops it quietly shrinking to the one case someone cares
#: about this week, and an exact count stops it growing without anyone re-reading what it is for.
EXPECTED_CASE_COUNT = 6

#: (tour case, gold case) -- same route, different grammar. The whole design of this set in two rows.
CONTROLLED_PAIRS = (("tour_v1_003", "gold_v0_1_017"), ("tour_v1_004", "gold_v0_1_016"))


@pytest.fixture(scope="module")
def store() -> GraphStore:
    return default_store()


@pytest.fixture(scope="module")
def document() -> dict[str, Any]:
    payload: dict[str, Any] = json.loads(TOUR_DATASET.read_text(encoding="utf-8"))
    return payload


@pytest.fixture(scope="module")
def cases(document: dict[str, Any]) -> list[dict[str, Any]]:
    return list(document["cases"])


def case_ids() -> list[str]:
    return [c["case_id"] for c in json.loads(TOUR_DATASET.read_text(encoding="utf-8"))["cases"]]


def get(cases: list[dict[str, Any]], case_id: str) -> dict[str, Any]:
    return next(c for c in cases if c["case_id"] == case_id)


# --- the set is what it says it is ------------------------------------------------------------------


def test_the_set_pins_the_artifact_the_store_actually_loaded(
    document: dict[str, Any], store: GraphStore
) -> None:
    """A set validated against a different corpus than the one deployed proves nothing. Same equality
    ``test_chips.py`` and ``test_tour_recording.py`` enforce, for the same reason."""
    assert document["artifact_version_pin"] == store.artifact_version


def test_the_case_count_is_locked_and_one_case_is_a_refusal(cases: list[dict[str, Any]]) -> None:
    """A set that refuses nothing gives refusal accuracy no true refusal to measure, and a system that
    answers everything looks flawless."""
    assert len(cases) == EXPECTED_CASE_COUNT
    assert sum(1 for c in cases if c["expected_refusal"]) >= 1


def test_the_loader_accepts_the_file(store: GraphStore) -> None:
    """``gold.load_cases`` is reused wholesale rather than copied. If the schemas ever diverge this is
    where it surfaces, instead of inside a suite run where it reads as a scoring bug."""
    loaded = gold.load_cases(TOUR_DATASET)
    assert len(loaded) == EXPECTED_CASE_COUNT
    assert all(case.shape == "path" for case in loaded)


# --- the property the set exists for ----------------------------------------------------------------


@pytest.mark.parametrize("case_id", case_ids())
def test_every_query_is_an_instruction_not_a_question(
    case_id: str, cases: list[dict[str, Any]]
) -> None:
    """**The reason this dataset exists.** Every gold query is interrogative; if these drift into
    questions the set stops covering anything gold does not already cover, and it would do so silently
    because the routes would still pass."""
    query = get(cases, case_id)["query"]
    assert not query.rstrip().endswith("?"), (
        f"{case_id}: {query!r} is a question, not an instruction"
    )


def test_the_gold_set_really_is_all_questions(store: GraphStore) -> None:
    """The other half of the claim above, asserted rather than assumed. If gold ever gains an imperative
    case, this set's rationale needs re-reading -- and this is what says so."""
    assert all(case.query.rstrip().endswith("?") for case in gold.load_cases())


def test_more_than_one_imperative_verb_is_covered(cases: list[dict[str, Any]]) -> None:
    """One phrasing measured three times is one phrasing. 'Take me', 'walk me' and 'show me' are
    different enough that a planner handling one and not the others is a real finding."""
    openers = {c["query"].split()[0].lower() for c in cases}
    assert len(openers) >= 2, f"only one imperative opener in the set: {openers}"


# --- and the routes are real ------------------------------------------------------------------------


@pytest.mark.parametrize("case_id", case_ids())
def test_every_node_in_the_expected_path_is_in_the_corpus(
    case_id: str, cases: list[dict[str, Any]], store: GraphStore
) -> None:
    case = get(cases, case_id)
    for node_id in case["expected_path"]:
        assert store.get_node(node_id) is not None, f"{case_id}: {node_id} is not in the corpus"


@pytest.mark.parametrize("case_id", case_ids())
def test_an_answerable_case_walks_and_a_refusal_case_does_not(
    case_id: str, cases: list[dict[str, Any]], store: GraphStore
) -> None:
    """The assertion whose absence let a dead demo route ship for six weeks. Both directions on the
    refusal case, because a one-directional check is how a path gets called missing when it is only
    being walked the wrong way."""
    case = get(cases, case_id)
    start = case["expected_resolution"]["node_id"]
    end = case["expected_terminus"]["node_id"]

    if case["expected_refusal"]:
        for a, b in ((start, end), (end, start)):
            for direction in (Direction.INFLUENCED_BY, Direction.INFLUENCED):
                assert not store.path(a, b, direction), f"{case_id}: {a} -> {b} now has a path"
        assert case["expected_path"] == [start]
        return

    chain = store.path(start, end, Direction.INFLUENCED_BY)
    assert chain, f"{case_id}: no sourced chain {start} -> {end}"
    walked = [chain[0].subject_id, *(edge.object_id for edge in chain)]
    assert walked == case["expected_path"]
    for earlier, later in pairwise(chain):
        assert earlier.object_id == later.subject_id
    for edge in chain:
        assert edge.source and edge.source_id


@pytest.mark.parametrize("case_id", case_ids())
def test_no_case_asserts_a_claim(case_id: str, cases: list[dict[str, Any]]) -> None:
    """**Deliberate, and this test is what keeps it deliberate.** Asserting particular edges requires the
    independent non-Wikidata citations the gold set is built on -- real books with page numbers. Those
    cannot be authored without fabricating them, and a project whose pitch is checkable provenance cannot
    carry invented citations in its own eval data. Claim correctness on these routes is covered by the
    gold pairs, which do carry citations."""
    assert get(cases, case_id)["expected_claims"] == []


@pytest.mark.parametrize(("tour_id", "gold_id"), CONTROLLED_PAIRS)
def test_a_controlled_pair_differs_only_in_grammar(
    tour_id: str, gold_id: str, cases: list[dict[str, Any]]
) -> None:
    """Same endpoints, same route, different phrasing. Asserted rather than noted, because a pair that
    silently stops being a pair still passes every other test in this file while measuring nothing."""
    tour = get(cases, tour_id)
    twin = next(c for c in gold.load_cases() if c.case_id == gold_id)

    assert tour["expected_resolution"]["node_id"] == twin.subject_id
    assert tour["expected_terminus"]["node_id"] == twin.terminus_id
    assert tuple(tour["expected_path"]) == twin.expected_path
    assert tour["query"] != twin.query


# --- and it costs nothing -----------------------------------------------------------------------------


def test_the_tour_set_is_not_in_the_live_suite() -> None:
    """**The expensive failure, held by a cheap test.** One extra case in the live set returns from
    ``thresholds.py:_ungateable`` before any per-metric check, un-gating all six properties, and
    restoring the bounds costs $2.61 and about 2.4 hours over five identical runs."""
    from musical_mycelium.eval.live import live_cases

    ids = [case.case_id for case in live_cases()]
    # 56 -> 63 on 2026-09-11, phase 7.6 step 9: the gold set gained five teaching cases and the
    # adversarial set two. **The live suite is therefore ungated until phase 7.7 re-measures the
    # bounds**, which is this test's own warning arriving as a planned cost rather than as an accident
    # -- `thresholds.py:_ungateable` says so in words on every live run, and the pin guard from step 0
    # refuses the run independently because the corpus moved too. What this test still asserts is
    # unchanged: no tour case is ever in the live suite.
    assert len(ids) == 63
    assert not [case_id for case_id in ids if case_id.startswith("tour_")]


def test_the_tour_set_matches_no_threshold_set_and_says_so(store: GraphStore) -> None:
    """Containment, asserted. A set that quietly borrowed gold's baseline would be comparing bounds
    measured on 38 questions against 6 instructions -- different denominators, different questions."""
    from musical_mycelium.eval.suite import run_tour_suite
    from musical_mycelium.eval.thresholds import gate

    outcome = gate(run_tour_suite(store))
    assert outcome.report is None
    assert any("NOT GATED" in line for line in outcome.lines)
    assert outcome.exit_code == 0
