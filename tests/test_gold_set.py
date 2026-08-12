"""The gold set, validated against the pinned artifact. Tier 1: deterministic, free, every commit.

This is the standing rule adopted in ``docs/SPEC.md`` 2.1 and recommended by
``docs/reviews/2026-08-01-fable-status-review.md`` 4.4: **every canonical query is validated against the
pinned artifact** — either answerable or deliberately labelled a coverage-honesty case. The check is a
dictionary lookup, so a corpus change that silently breaks a demo query fails CI instead of failing in
front of somebody.

Note what this does *not* test: the agent. There is no agent yet, and that is the point — the gold set is
hand-authored **before** the agent exists so it cannot be contaminated by the agent's output
(``.claude/rules/evals.md``). What this asserts is that the gold set and the corpus still agree.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.agent.claims import ClaimProposal, gate
from musical_mycelium.eval.metrics import edge_groundedness, traversal_recall
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory

GOLD_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "musical_mycelium"
    / "eval"
    / "datasets"
    / "gold_v0_1.json"
)


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture(scope="module")
def gold() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(GOLD_PATH.read_text(encoding="utf-8"))
    return data


def case_ids() -> list[str]:
    return [c["case_id"] for c in json.loads(GOLD_PATH.read_text(encoding="utf-8"))["cases"]]


def get_case(gold: dict[str, Any], case_id: str) -> dict[str, Any]:
    case: dict[str, Any] = next(c for c in gold["cases"] if c["case_id"] == case_id)
    return case


# --- the dataset itself ------------------------------------------------------------------------


def test_the_gold_set_is_pinned_to_the_artifact_this_suite_loads(
    gold: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """A gold set measured against a different corpus than the one under test is measuring nothing."""
    assert gold["artifact_version_pin"] == store.artifact_version


def test_there_are_five_cases_and_exactly_one_is_a_refusal(gold: dict[str, Any]) -> None:
    """Both halves matter. Five is the phase scope; **at least one refusal** is what gives refusal
    accuracy a true refusal to measure, and without it a system that answers everything looks flawless."""
    cases = gold["cases"]
    assert len(cases) == 5
    assert sum(1 for c in cases if c["expected_refusal"]) == 1


def test_every_answerable_case_cites_an_independent_source(gold: dict[str, Any]) -> None:
    """``.claude/rules/grounding-and-claims.md``: the gold set cites sources independent of Wikidata, so
    divergence between this graph and the outside world can surface."""
    for case in gold["cases"]:
        if case["expected_refusal"]:
            continue
        for expected in case["expected_claims"]:
            assert expected["independent_citations"], f"{case['case_id']} has an uncited claim"


# --- every case, against the corpus ---------------------------------------------------------------


@pytest.mark.parametrize("case_id", case_ids())
def test_case_resolves_to_the_node_it_names(
    case_id: str, gold: dict[str, Any], store: InMemoryGraphStore
) -> None:
    case = get_case(gold, case_id)
    hits = store.search(case["expected_resolution"]["name"])
    assert hits, f"{case_id}: {case['expected_resolution']['name']!r} no longer resolves"
    assert hits[0].id == case["expected_resolution"]["node_id"]


@pytest.mark.parametrize("case_id", case_ids())
def test_case_claims_match_the_corpus_exactly(
    case_id: str, gold: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """Not a subset — exactly. A corpus that grew an extra edge under a gold case is as much of a problem
    as one that lost an edge, because the case would then under-specify the correct answer."""
    case = get_case(gold, case_id)
    node_id = case["expected_resolution"]["node_id"]

    expected = {(c["subject_id"], c["object_id"]) for c in case["expected_claims"]}
    actual = {(e.subject_id, e.object_id) for e in store.neighbors(node_id)}
    assert actual == expected, f"{case_id}: the corpus and the gold case disagree"


@pytest.mark.parametrize("case_id", case_ids())
def test_case_expectation_of_refusal_still_holds(
    case_id: str, gold: dict[str, Any], store: InMemoryGraphStore
) -> None:
    case = get_case(gold, case_id)
    has_edges = bool(store.neighbors(case["expected_resolution"]["node_id"]))
    assert has_edges is not case["expected_refusal"]


@pytest.mark.parametrize("case_id", case_ids())
def test_case_claims_survive_the_gate_and_measure_as_grounded(
    case_id: str, gold: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """The end-to-end Tier 1 row: propose exactly what the gold case says, gate it, measure it.

    For the four answerable cases this must be 100% — the blocking threshold from
    ``.claude/rules/evals.md``, which is a real threshold rather than an invented one because the ground
    truth is a graph we own. For the refusal case the gate must approve nothing and the score must be
    **undefined**, not perfect.
    """
    case = get_case(gold, case_id)
    proposals = [
        ClaimProposal(c["subject_id"], c["predicate"], c["object_id"])
        for c in case["expected_claims"]
    ]
    result = gate(proposals, store)
    assert not result.rejected, f"{case_id}: the gate rejected a gold claim: {result.rejected}"

    measured = edge_groundedness(list(result.approved), store)
    if case["expected_refusal"]:
        assert not result.approved
        assert measured.score is None
        assert not measured.is_fully_grounded
    else:
        assert measured.is_fully_grounded
        assert measured.score == 1.0
        assert measured.total == len(case["expected_claims"])


# --- expected_path: what traversal_recall reads -----------------------------------------------------


@pytest.mark.parametrize("case_id", case_ids())
def test_case_carries_an_expected_path_of_real_nodes(
    case_id: str, gold: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """``traversal_recall(visited, gold)`` takes node ids and this schema had none until 2026-08-12,
    which is why that metric had never scored a run. Every id in the field must be a node the corpus
    actually holds, or the metric measures a walk toward somewhere that does not exist."""
    case = get_case(gold, case_id)
    path = case["expected_path"]
    assert path, f"{case_id}: expected_path is empty"
    for node_id in path:
        assert store.get_node(node_id) is not None, f"{case_id}: {node_id} is not in the corpus"


@pytest.mark.parametrize("case_id", case_ids())
def test_expected_path_contains_the_subject_and_every_claim_endpoint(
    case_id: str, gold: dict[str, Any]
) -> None:
    """**Broader than the claims is allowed; narrower is not.** The field is authored rather than derived
    because a path case legitimately visits intermediates that produce no claim, and
    ``traversal_precision`` penalises off-path visits — so what counts as on-path is a judgement. This
    locks the one direction that is never a judgement call: a node the case *claims* an edge for must be
    a node the case *expects the traversal to reach*.

    Membership, not position: ``traversal_recall`` is set-valued, because ``PathWalked.node_ids`` is
    visit order rather than descent order.
    """
    case = get_case(gold, case_id)
    path = set(case["expected_path"])

    assert case["expected_resolution"]["node_id"] in path, f"{case_id}: subject missing from path"
    for claim in case["expected_claims"]:
        assert claim["subject_id"] in path, f"{case_id}: claim subject off the expected path"
        assert claim["object_id"] in path, f"{case_id}: claim object off the expected path"


def test_the_refusal_case_expects_the_subject_alone(gold: dict[str, Any]) -> None:
    """The reason the field is authored and not derived. A refusal case has no claims, so a derived node
    set would be empty and ``traversal_recall`` would return ``Rate(0, 0)`` — which ``Rate`` correctly
    reports as *undefined* rather than perfect. That is the quiet failure: the metric would never score a
    refusal case at all, and the behaviour these cases exist to test — reaching the node, then declining
    to narrate it — would go unmeasured while the suite looked healthy.
    """
    refusals = [c for c in gold["cases"] if c["expected_refusal"]]
    assert refusals, "no refusal case to check"
    for case in refusals:
        assert case["expected_path"] == [case["expected_resolution"]["node_id"]]
        assert not case["expected_claims"]


@pytest.mark.parametrize("case_id", case_ids())
def test_a_perfect_walk_scores_perfect_recall_on_every_case(
    case_id: str, gold: dict[str, Any]
) -> None:
    """``traversal_recall``'s first caller outside its own unit tests. A traversal that visited exactly
    the expected path scores 1.0 — including the refusal case, whose denominator is 1 rather than 0."""
    case = get_case(gold, case_id)
    path = case["expected_path"]

    assert traversal_recall(path, path).score == 1.0
    assert traversal_recall([], path).score == 0.0


# --- the rejected edges must not creep back in ------------------------------------------------------


def test_no_gold_case_expects_a_rejected_edge(gold: dict[str, Any]) -> None:
    """The hand-verification threw out seven candidates. If one ever reappears in the corpus, the gold
    set must not be what quietly legitimises it."""
    from musical_mycelium.ingest import wikidata

    rejected = {(subject, obj) for subject, obj, _ in wikidata.REJECTED_EDGES}
    for case in gold["cases"]:
        for expected in case["expected_claims"]:
            assert (expected["subject_id"], expected["object_id"]) not in rejected
