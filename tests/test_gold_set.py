"""The gold set, validated against the pinned artifact. Tier 1: deterministic, free, every commit.

This is the standing rule adopted in ``docs/SPEC.md`` 2.1 and recommended by
``docs/reviews/2026-08-01-fable-status-review.md`` 4.4: **every canonical query is validated against the
pinned artifact** — either answerable or deliberately labelled a coverage-honesty case. The check is a
dictionary lookup, so a corpus change that silently breaks a demo query fails CI instead of failing in
front of somebody.

Note what this does *not* test: the agent. What it asserts is that the gold set and the corpus still
agree. The set is hand-authored so it cannot be contaminated by the agent's output
(``.claude/rules/evals.md``) — but read that claim precisely as of 2026-08-14. The agent now exists and
has run against a real model once, so the set is no longer clean *by construction*; it is clean *by
procedure*, which is weaker. The procedure and its one narrow exposure are recorded in the dataset's own
``provenance.honest_limits``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.agent.claims import ClaimProposal, gate
from musical_mycelium.eval.metrics import edge_groundedness, traversal_recall
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.store import Direction

#: The query shapes a gold case may declare. Every case has carried a ``shape`` since v0.1 and until
#: 2026-08-14 **nothing read it** — every test assumed origins, which was true of all fifteen cases then
#: in the set and false for both remaining slots. Locked as a frozenset so a typo fails loudly rather
#: than falling through a default branch into the wrong direction, which is the specific error
#: ``Direction``'s own docstring warns about: "getting them backwards silently inverts music history".
#:
#: Refusal is deliberately **not** a shape. It is a ``difficulty``, because a refusal is a property of
#: what the corpus can answer, not of what was asked — case 005 asks an origins question and case 010
#: asks the same question of a node with no parents.
CASE_SHAPES = frozenset({"origins", "descendants", "path"})

GOLD_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "musical_mycelium"
    / "eval"
    / "datasets"
    / "gold_v0_1.json"
)

#: The number of cases the gold set is *known* to hold. The set is authored incrementally across
#: sittings — ``notes_on_composition.authoring_is_incremental`` — so this is bumped to the real count at
#: the end of each one. That is the point of it: adding a case is a deliberate act that touches this
#: line, and a case can never appear in the dataset without someone saying so here. The target is 25,
#: distributed across the slots in ``notes_on_composition.composition_plan``. The requirement is
#: 20 to 30 (``.claude/rules/evals.md``, ``planning/07`` 3.1); 25 is a choice inside it, not the rule.
EXPECTED_CASE_COUNT = 25

#: How many gold claims carry no independent citation and say so via ``citation_status``. Locked for the
#: same reason as the case count, and it matters more: this one is an escape hatch from the project's
#: central honesty rule. Eight of 67 claims as of 2026-08-14. Seven are non-Western; the eighth is
#: Lady Gaga → the
#: Beatles, where Wikipedia footnotes a fifteen-artist sentence one artist at a time and skips that one.
#: That one is the useful one: uncited claims track Wikipedia's sourcing habits rather than a region, and
#: they concentrate where coverage is thin without being confined there.
UNCITED_CLAIM_COUNT = 8


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


def corpus_edges_for(case: dict[str, Any], store: InMemoryGraphStore) -> set[tuple[str, str]]:
    """The edge set the corpus must hold for this case, read according to its declared shape.

    Each branch preserves the same invariant the origins-only version enforced — **exactly**, not a
    subset — but asks the corpus a different question:

    * ``origins`` — the subject's parents. What it came out of.
    * ``descendants`` — the subject's children, which is the *same rows read the other way*, not a
      different table. Passing the wrong ``Direction`` here does not error; it silently answers the
      opposite question, which is why the shape is declared rather than inferred.
    * ``path`` — the **shortest** sourced chain between two named endpoints. ``store.path`` is BFS, so
      shortest is what a traversal should find, and pinning to it means a corpus that later grows a
      shortcut fails this test instead of quietly leaving the gold case pointing down a longer route
      that is no longer the right answer.
    """
    shape = case["shape"]
    node_id = case["expected_resolution"]["node_id"]

    if shape == "origins":
        return {
            (e.subject_id, e.object_id) for e in store.neighbors(node_id, Direction.INFLUENCED_BY)
        }
    if shape == "descendants":
        return {(e.subject_id, e.object_id) for e in store.neighbors(node_id, Direction.INFLUENCED)}
    if shape == "path":
        end_id = case["expected_terminus"]["node_id"]
        return {(e.subject_id, e.object_id) for e in store.path(node_id, end_id)}
    raise AssertionError(f"{case['case_id']}: unknown shape {shape!r}")


def corpus_can_answer(case: dict[str, Any], store: InMemoryGraphStore) -> bool:
    """Whether the corpus holds an answer to the question this case actually asks.

    Split out from the refusal test because "has edges" is shape-relative. A descendants case about a
    node with many parents and no children is a **correct refusal**, and the origins-only version of
    this check would have called it answerable.
    """
    return bool(corpus_edges_for(case, store))


# --- the dataset itself ------------------------------------------------------------------------


def test_the_gold_set_is_pinned_to_the_artifact_this_suite_loads(
    gold: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """A gold set measured against a different corpus than the one under test is measuring nothing."""
    assert gold["artifact_version_pin"] == store.artifact_version


def test_the_case_count_is_locked_and_at_least_one_case_is_a_refusal(gold: dict[str, Any]) -> None:
    """Both halves matter. The count is locked so a case cannot enter the set silently; **at least one
    refusal** is what gives refusal accuracy a true refusal to measure, and without it a system that
    answers everything looks flawless. The plan targets three refusal cases, so this floor rises as the
    set fills rather than being pinned at the one case v0.1 shipped with."""
    cases = gold["cases"]
    assert len(cases) == EXPECTED_CASE_COUNT
    assert sum(1 for c in cases if c["expected_refusal"]) >= 1


def test_every_answerable_case_cites_an_independent_source_or_says_why_not(
    gold: dict[str, Any],
) -> None:
    """``.claude/rules/grounding-and-claims.md``: the gold set cites sources independent of Wikidata, so
    divergence between this graph and the outside world can surface.

    A claim may fail to carry one **only** by saying so out loud. Silence is still forbidden — what is
    now permitted is an explicit ``citation_status`` naming the sources that were searched and came up
    empty. See ``provenance.schema_history`` for why that third option exists: the two obvious responses
    were to attach an article's general reference list (passes this test, hides the weakness) or to drop
    the cases (buys a perfect citation rate by excluding the global south, then reports the rate as a
    property of the system).
    """
    for case in gold["cases"]:
        if case["expected_refusal"]:
            continue
        for expected in case["expected_claims"]:
            if expected["independent_citations"]:
                continue
            status = expected.get("citation_status")
            assert status, f"{case['case_id']} has a silently uncited claim"
            assert status["state"] == "source_uncited"
            assert status["searched"], (
                f"{case['case_id']} flagged a claim without recording the search"
            )
            assert status["finding"]


def test_the_number_of_uncited_claims_is_locked(gold: dict[str, Any]) -> None:
    """The flag is an escape hatch, and an escape hatch that costs nothing to widen becomes the standard.

    Locking the count means a future case cannot quietly join the flagged set: the number only moves when
    someone edits this line on purpose, exactly as with ``EXPECTED_CASE_COUNT``. Every flag was applied
    only after searching for a source in every language the subject plausibly has one in — a pass which
    rescued kuduro's and cachaca's claims rather than flagging them, so the count reflects what is
    genuinely unsourced rather than what was inconvenient to chase.
    """
    flagged = [
        (case["case_id"], claim["object_label"])
        for case in gold["cases"]
        for claim in case["expected_claims"]
        if not claim["independent_citations"]
    ]
    assert len(flagged) == UNCITED_CLAIM_COUNT, f"the flagged set moved: {flagged}"


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
    as one that lost an edge, because the case would then under-specify the correct answer.

    Shape-aware since 2026-08-14; see :func:`corpus_edges_for`. Before that this read
    ``store.neighbors(node_id)`` unconditionally, which is correct for origins and wrong for the other
    two shapes — a path case's claims mostly do not originate at its subject at all.
    """
    case = get_case(gold, case_id)

    expected = {(c["subject_id"], c["object_id"]) for c in case["expected_claims"]}
    actual = corpus_edges_for(case, store)
    assert actual == expected, f"{case_id}: the corpus and the gold case disagree"


@pytest.mark.parametrize("case_id", case_ids())
def test_case_expectation_of_refusal_still_holds(
    case_id: str, gold: dict[str, Any], store: InMemoryGraphStore
) -> None:
    case = get_case(gold, case_id)
    assert corpus_can_answer(case, store) is not case["expected_refusal"]


@pytest.mark.parametrize("case_id", case_ids())
def test_case_declares_a_shape_the_harness_understands(case_id: str, gold: dict[str, Any]) -> None:
    """A shape field nothing validates is a shape field that silently accepts ``"origns"``.

    This matters more than a typo check. ``corpus_edges_for`` dispatches on this string, and two of its
    branches read the same edge rows in opposite directions — so an unrecognised shape falling through
    to a default would not raise, it would answer the wrong question and pass.
    """
    case = get_case(gold, case_id)
    assert case["shape"] in CASE_SHAPES, f"{case_id}: unknown shape {case['shape']!r}"
    if case["shape"] == "path":
        assert case.get("expected_terminus"), f"{case_id}: a path case needs an expected_terminus"


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
