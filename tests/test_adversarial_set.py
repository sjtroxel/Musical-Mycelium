"""The adversarial set, validated against the pinned artifact. Tier 1: deterministic, free, every commit.

Same standing rule as ``test_gold_set.py``: every case is checked against the corpus it is pinned to, so
a corpus change that silently invalidates a case fails CI rather than failing quietly inside an eval run
months later.

What this file does **not** test is the agent -- there is no agent yet, and that is the point. The
adversarial set is hand-authored *before* the agent exists so it cannot be shaped by watching the agent
fail (``.claude/rules/evals.md``). What is asserted here is that the dataset and the corpus still agree:
that absent genres are still absent, that forbidden edges are still forbidden, and that the resolver
still emits the exact strings the cases were written against.

The strongest assertions in this file are the negative ones. A ``forbidden_triple`` that turns out to
*exist* in the corpus would silently convert an adversarial case into a case the agent is supposed to
pass by answering -- so every forbidden triple is re-checked through the real gate on every run.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from itertools import pairwise
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.agent.claims import ClaimProposal, RejectionReason, gate
from musical_mycelium.agent.tools import ResolveNode
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory, label_key
from musical_mycelium.graph.schema import PREDICATE_INFLUENCED_BY, Artifact
from musical_mycelium.graph.store import Direction

ADVERSARIAL_PATH = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "musical_mycelium"
    / "eval"
    / "datasets"
    / "adversarial_v1.json"
)

#: The amended composition. The ``ambiguous`` group from the IMPLEMENTATION doc 4.1 became
#: ``near_miss_substitution`` on 2026-08-07 because the ``ambiguous`` branch has population zero --
#: see ``test_the_ambiguous_branch_is_still_unreachable`` below, which locks that finding.
EXPECTED_GROUPS = {
    "false_premise_not_in_graph": 4,
    "false_premise_resolves_but_unsourced": 3,
    "near_miss_substitution": 2,
    "cross_axis_trap": 2,
    "direction_inversion": 2,
    "prompt_injection": 3,
    "coverage_honesty": 2,
}


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture(scope="module")
def dataset() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(ADVERSARIAL_PATH.read_text(encoding="utf-8"))
    return data


def case_ids() -> list[str]:
    return [c["case_id"] for c in json.loads(ADVERSARIAL_PATH.read_text(encoding="utf-8"))["cases"]]


def get_case(dataset: dict[str, Any], case_id: str) -> dict[str, Any]:
    case: dict[str, Any] = next(c for c in dataset["cases"] if c["case_id"] == case_id)
    return case


# --- the dataset itself ---------------------------------------------------------------------------


def test_the_set_is_pinned_to_the_artifact_this_suite_loads(
    dataset: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """A dataset measured against a different corpus than the one under test is measuring nothing."""
    assert dataset["artifact_version_pin"] == store.artifact_version


def test_there_are_eighteen_cases_with_unique_ids(dataset: dict[str, Any]) -> None:
    ids = [c["case_id"] for c in dataset["cases"]]
    assert len(ids) == 18
    assert len(set(ids)) == 18, "duplicate case_id"


def test_the_group_composition_matches_the_amended_plan(dataset: dict[str, Any]) -> None:
    """``.claude/rules/evals.md`` wants 15-20 adversarial cases; the plan fixes the mix. If a group
    is silently rebalanced, the set stops testing what its composition table claims it tests."""
    assert Counter(c["group"] for c in dataset["cases"]) == Counter(EXPECTED_GROUPS)


def test_every_case_has_a_rationale_and_an_attack(dataset: dict[str, Any]) -> None:
    """The plan requires a hand-written rationale per case. An adversarial case whose reason for
    existing was never written down cannot be maintained, only deleted."""
    for case in dataset["cases"]:
        assert case["rationale"].strip(), f"{case['case_id']} has no rationale"
        assert case["attack"].strip(), f"{case['case_id']} has no attack description"
        assert case["query"].strip(), f"{case['case_id']} has no query"


def test_refusal_cases_permit_no_approved_claims(dataset: dict[str, Any]) -> None:
    """A case that expects a refusal but tolerates an approved claim is self-contradictory."""
    for case in dataset["cases"]:
        if case["expected"]["refusal"]:
            assert case["expected"]["max_approved_claims"] == 0, case["case_id"]


def test_the_set_is_not_all_refusals(dataset: dict[str, Any]) -> None:
    """``.claude/rules/grounding-and-claims.md``: a system that refuses everything scores perfectly on
    hallucination and is useless. The set must contain cases where answering is correct, or it cannot
    tell those two systems apart."""
    answerable = [c for c in dataset["cases"] if not c["expected"]["refusal"]]
    assert len(answerable) >= 4, "too few answerable cases to detect over-refusal"


# --- every case, against the corpus ----------------------------------------------------------------


@pytest.mark.parametrize("case_id", case_ids())
def test_case_resolution_still_matches_the_resolver(
    case_id: str, dataset: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """The exact strings each case was authored against, re-read from the live tool.

    This is the check that catches corpus drift fastest: if a genre this set calls absent is later
    ingested, or a ``did_you_mean`` list reorders, the case's premise is gone and the case must be
    re-authored rather than quietly re-pinned.
    """
    case = get_case(dataset, case_id)
    expected = case["expected"]["resolution"]
    actual = ResolveNode(store)(name=expected["query_term"]).content

    assert actual["node_id"] == expected["node_id"], f"{case_id}: resolution changed"

    if expected["node_id"] is None:
        assert actual["reason"] == expected["reason"], f"{case_id}: refusal reason changed"
        if "did_you_mean" in expected:
            assert actual.get("did_you_mean") == expected["did_you_mean"], (
                f"{case_id}: the suggestion list changed; the substitution trap is no longer the "
                f"one the case describes"
            )
    else:
        assert actual["kind"] == expected["kind"], f"{case_id}: node kind changed"


@pytest.mark.parametrize("case_id", case_ids())
def test_case_forbidden_triples_are_genuinely_absent(
    case_id: str, dataset: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """Re-checked through the real gate, not by assertion.

    A forbidden triple that the corpus actually contains would invert the case: the agent would be
    *right* to assert it, and the eval would be penalising correct behaviour. This is the single most
    important test in the file.
    """
    case = get_case(dataset, case_id)
    for subject, predicate, obj in case["expected"]["forbidden_triples"]:
        result = gate([ClaimProposal(subject, predicate, obj)], store)
        assert not result.approved, (
            f"{case_id}: forbidden triple ({subject}, {predicate}, {obj}) EXISTS in the corpus; "
            f"the case is no longer adversarial and must be re-authored"
        )
        assert result.rejected


@pytest.mark.parametrize("case_id", case_ids())
def test_case_expected_rejection_reasons_are_real_reasons(
    case_id: str, dataset: dict[str, Any]
) -> None:
    """Guards against a typo'd reason string quietly never matching anything at scoring time."""
    case = get_case(dataset, case_id)
    valid = {r.value for r in RejectionReason}
    for reason in case["expected"]["expected_gate_rejections"]:
        assert reason in valid, f"{case_id}: {reason!r} is not a RejectionReason"


@pytest.mark.parametrize("case_id", case_ids())
def test_case_claim_bound_matches_what_the_corpus_can_supply(
    case_id: str, dataset: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """``max_approved_claims`` must be reachable but not generous.

    For an answerable case the bound is the number of sourced edges actually available from the
    resolved subject; a bound larger than that would let a fabricated extra claim slip under it.
    """
    case = get_case(dataset, case_id)
    if case["expected"]["refusal"]:
        return
    node_id = case["expected"]["resolution"]["node_id"]
    if node_id is None:
        return

    available = len(store.neighbors(node_id, Direction.INFLUENCED_BY))
    bound = case["expected"]["max_approved_claims"]

    if case["group"] == "direction_inversion":
        # The subject is the DESCENDANT and the bound covers a multi-hop chain, so the one-hop
        # neighbour count is a floor rather than the answer.
        assert bound >= available, f"{case_id}: bound {bound} below the {available} direct edges"
        assert bound <= 6, f"{case_id}: bound {bound} exceeds the corpus's deepest chain"
    else:
        assert bound == available, (
            f"{case_id}: bound is {bound} but {node_id} has {available} sourced influences"
        )


# --- the injection fixtures ------------------------------------------------------------------------


def test_every_injection_case_commits_its_literal_string(dataset: dict[str, Any]) -> None:
    """The plan: the injection strings are committed as fixtures, **not generated**. A generated
    payload drifts from the assertion written against it, and then the test passes for the wrong
    reason."""
    injections = [c for c in dataset["cases"] if c["group"] == "prompt_injection"]
    assert len(injections) == 3

    for case in injections:
        injection = case["injection"]
        assert injection["literal_string"].strip(), f"{case['case_id']} has no payload"
        assert injection["vector"] in {"node_label", "tool_result_payload", "user_query"}
        assert case["expected"]["forbidden_prose_assertions"], (
            f"{case['case_id']}: an injection case with nothing forbidden in prose asserts nothing"
        )


def test_the_three_injection_vectors_are_distinct(dataset: dict[str, Any]) -> None:
    """Three payloads down one pipe is one test run three times."""
    vectors = [
        c["injection"]["vector"] for c in dataset["cases"] if c["group"] == "prompt_injection"
    ]
    assert len(set(vectors)) == 3


def test_no_injection_fixture_targets_the_pinned_artifact(dataset: dict[str, Any]) -> None:
    """A poisoned label must live in a synthetic fixture. Writing one into the real artifact would
    corrupt every other measurement in the project."""
    for case in dataset["cases"]:
        if case["group"] != "prompt_injection":
            continue
        assert (
            "v0.5.0" not in case["injection"]["fixture"] or "NEVER" in case["injection"]["fixture"]
        )


# --- premise correction ----------------------------------------------------------------------------


def test_only_inversion_cases_carry_a_premise_correction(dataset: dict[str, Any]) -> None:
    """The correction fires on a narrow trigger: the premise is rejected AND the reverse is approved.

    A case outside ``direction_inversion`` carrying one would mean the trigger had widened past what
    ``IMPLEMENTATION`` 4.3 approved, which is how a gratuitous framing starts appearing on neutral
    questions.
    """
    for case in dataset["cases"]:
        has_block = "premise_correction" in case["expected"]
        assert has_block is (case["group"] == "direction_inversion"), case["case_id"]


@pytest.mark.parametrize("case_id", case_ids())
def test_asserted_premise_is_rejected_and_its_reverse_is_supported(
    case_id: str, dataset: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """Both halves of the trigger, re-checked against the corpus on every run.

    ``IMPLEMENTATION`` 4.3: ``inverted_premise`` is admissible only when the approved claims establish
    the reverse. If the asserted premise ever became a real edge, or the documented orientation ever
    lost a hop, the case would be asking for a correction the gate cannot produce.
    """
    case = get_case(dataset, case_id)
    correction = case["expected"].get("premise_correction")
    if correction is None:
        return

    subject, predicate, obj = correction["asserted"]
    rejected = gate([ClaimProposal(subject, predicate, obj)], store)
    assert not rejected.approved, (
        f"{case_id}: the asserted premise is a real edge; nothing to correct"
    )

    orientation = correction["documented_orientation"]
    assert len(orientation) >= 2, f"{case_id}: a chain needs at least two nodes"
    for head, tail in pairwise(orientation):
        hop = gate([ClaimProposal(head, PREDICATE_INFLUENCED_BY, tail)], store)
        assert hop.approved, (
            f"{case_id}: documented orientation hop {head} -> {tail} is NOT an approved claim; "
            f"the correction would assert a chain the gate never passed"
        )

    # The premise and the documented orientation must be the same relation, opposite ways round.
    assert orientation[0] == obj, f"{case_id}: chain does not start where the premise's object is"
    assert orientation[-1] == subject, (
        f"{case_id}: chain does not end where the premise's subject is"
    )


def test_premise_correction_forbids_asserting_the_negative(dataset: dict[str, Any]) -> None:
    """The decision of 2026-08-07: state the orientation positively, never assert the negative.

    "Heavy metal did not influence the blues" is a negative claim, and with 542 of 973 nodes carrying
    zero outgoing edges this corpus cannot support one. Absence of an edge is not evidence of absence.
    Every inversion case must therefore name the phrasings that would cross that line.
    """
    for case in dataset["cases"]:
        correction = case["expected"].get("premise_correction")
        if correction is None:
            continue
        assert correction["framing_required"] is True, case["case_id"]
        assert correction["forbidden_negation"], (
            f"{case['case_id']}: no forbidden negations listed, so nothing stops the answer sliding "
            f"from 'this graph documents X' to 'not-X is true'"
        )


# --- the locks -------------------------------------------------------------------------------------


def test_the_ambiguous_branch_is_still_unreachable(store: InMemoryGraphStore) -> None:
    """``resolve_node`` emits ``"ambiguous"`` only when two or more nodes exact-match one normalised
    query. In v0.5.0 no two node labels share a ``label_key``, so that branch has **population zero** --
    the same status as ``contested`` and ``checks_disagree``.

    This test is the lock. It is not asserting that ambiguity is impossible in principle; it is
    asserting that the corpus has not quietly grown a collision while two adversarial cases are written
    against the reachable ``no exact match`` branch instead.

    **IT FIRED AT v0.7.1 AND `ambiguous` IS NOW REACHABLE.** The DBpedia growth brought in
    ``big band music`` (Q105756581) alongside the existing ``big band`` (Q207378) -- two genuinely
    distinct Wikidata items whose labels normalise to the same ``label_key``. The docstring above
    promised this would be a signal rather than a bug, so:

    - the lock is **kept, not deleted**, and now names the one collision the corpus actually has, so a
      *second* one fails here instead of hiding behind the first -- the same shape as the named Nine
      Inch Nails edge in ``test_graph_store``;
    - **authoring real ambiguity cases is now possible and is owed.** The two ``near_miss_substitution``
      cases are still written against the reachable "no exact match" branch and remain valid; what is
      missing is a case that exercises the ``ambiguous`` branch with a query a real user would type.
      That is dataset authoring and it belongs to sjtroxel.
    """
    by_key: dict[str, list[str]] = defaultdict(list)
    for node in Artifact.load(artifact_directory()).nodes:
        by_key[label_key(node.label)].append(node.label)

    collisions = {key: sorted(labels) for key, labels in by_key.items() if len(labels) > 1}
    assert collisions == {"big band": ["big band", "big band music"]}, (
        f"the label_key collisions moved: {collisions}. `ambiguous` reachability is a dataset "
        f"decision -- re-read this docstring rather than widening the expected set by reflex."
    )


def test_absent_genres_are_still_absent(dataset: dict[str, Any], store: InMemoryGraphStore) -> None:
    """Every case whose premise is 'this graph does not contain it' re-checked against search().

    Phase 6 is explicitly about density and coverage. When it lands, some of these names may be
    ingested -- and this test failing is exactly how that should be discovered.
    """
    for case in dataset["cases"]:
        resolution = case["expected"]["resolution"]
        if resolution["node_id"] is None and resolution["reason"] == "not in this graph":
            assert not store.search(resolution["query_term"]), (
                f"{case['case_id']}: {resolution['query_term']!r} is now in the corpus; the case's "
                f"premise is gone and it must be re-authored, not re-pinned"
            )


def test_unsourced_subjects_still_have_no_outgoing_edges(
    dataset: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """The 'resolves but unsourced' group depends on an absence that phase 6 may well fill."""
    for case in dataset["cases"]:
        if case["group"] != "false_premise_resolves_but_unsourced":
            continue
        node_id = case["expected"]["resolution"]["node_id"]
        edges = store.neighbors(node_id, Direction.INFLUENCED_BY)
        assert not edges, (
            f"{case['case_id']}: {node_id} now has {len(edges)} sourced influence(s); refusing is no "
            f"longer the correct behaviour and the case must be re-authored"
        )
