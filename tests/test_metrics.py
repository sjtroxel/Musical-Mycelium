"""Metric tests — the metrics measuring themselves.

``.claude/rules/evals.md`` requires this and says why: *"A metric you have not tried to break is not a
metric."* That section exists because of a real difflib coverage bug in a previous project, where the
number looked healthy and meant nothing.

So every case here is **synthetic, with the answer known by construction**: a claim set assembled to make
the score obviously 1.0, 0.5, 0.0 or undefined, checked against a graph small enough to hold in your head.
The pinned artifact appears only where the point is that the metric agrees with real data.
"""

from __future__ import annotations

import pytest

from musical_mycelium.agent.claims import Claim, ClaimProposal, gate
from musical_mycelium.agent.llm import Usage
from musical_mycelium.agent.loop import Done
from musical_mycelium.eval.metrics import (
    Groundedness,
    Rate,
    citation_resolution,
    edge_groundedness,
    injection_resistance,
    plan_adherence,
    refusal_accuracy,
    traversal_precision,
    traversal_recall,
    verification_mix,
)
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import (
    NODE_KIND_GENRE,
    VERIFICATION_HAND,
    VERIFICATION_LEVELS,
    VERIFICATION_PROSE_AUTO,
    Artifact,
    Edge,
    Node,
)

INFLUENCED_BY = "influenced_by"
WHEN = "2026-01-01T00:00:00+00:00"

# A three-edge graph where every answer is countable by eye:
#   Q2 <- Q1,  Q3 <- Q1,  Q3 <- Q2
STATEMENTS = {
    ("Q2", "Q1"): "http://www.wikidata.org/entity/statement/Q2-AAA",
    ("Q3", "Q1"): "http://www.wikidata.org/entity/statement/Q3-BBB",
    ("Q3", "Q2"): "http://www.wikidata.org/entity/statement/Q3-CCC",
}


@pytest.fixture(scope="module")
def toy() -> InMemoryGraphStore:
    nodes = tuple(
        Node(
            id=q,
            label=f"genre {q}",
            source="wikidata",
            source_id=q,
            retrieved_at=WHEN,
            kind=NODE_KIND_GENRE,
        )
        for q in ("Q1", "Q2", "Q3", "Q4")
    )
    edges = tuple(
        Edge(
            subject_id=subject,
            predicate=INFLUENCED_BY,
            object_id=obj,
            source="wikidata",
            source_id=statement,
            retrieved_at=WHEN,
            prose_tier="PROSE",
            verification=VERIFICATION_PROSE_AUTO,
        )
        for (subject, obj), statement in STATEMENTS.items()
    )
    return InMemoryGraphStore(Artifact(nodes=nodes, edges=edges))


def claim(subject: str, obj: str, source: str | None = None) -> Claim:
    return Claim(
        subject_id=subject,
        predicate=INFLUENCED_BY,
        object_id=obj,
        source_ids=(source or STATEMENTS.get((subject, obj), "http://example.invalid/made-up"),),
        verification=VERIFICATION_PROSE_AUTO,
    )


# --- the vacuous-truth guard --------------------------------------------------------------------


def test_an_empty_output_does_not_score_one_hundred_percent(toy: InMemoryGraphStore) -> None:
    """The guard ``.claude/rules/evals.md`` names by name. A system that asserts nothing is not perfectly
    grounded; its groundedness is undefined. Scoring it 1.0 would make "refuse everything" the winning
    strategy on the headline metric."""
    result = edge_groundedness([], toy)
    assert result.total == 0
    assert result.score is None
    assert result.score != 1.0


def test_an_empty_output_does_not_pass_the_blocking_check(toy: InMemoryGraphStore) -> None:
    """The other half of the guard, and the one that actually protects CI. ``score is None`` is only
    useful if the pass/fail branch treats it as a failure rather than tripping over it."""
    assert not edge_groundedness([], toy).is_fully_grounded


def test_undefined_renders_as_undefined_not_as_a_number(toy: InMemoryGraphStore) -> None:
    """A report that prints "0.0%" or "100.0%" for an empty run teaches the reader the wrong thing."""
    assert str(edge_groundedness([], toy)) == "groundedness: undefined (0 claims)"


# --- scores known by construction ---------------------------------------------------------------


def test_all_grounded_scores_one(toy: InMemoryGraphStore) -> None:
    result = edge_groundedness([claim("Q2", "Q1"), claim("Q3", "Q1"), claim("Q3", "Q2")], toy)
    assert result.score == 1.0
    assert result.is_fully_grounded
    assert result.ungrounded == ()


def test_none_grounded_scores_zero(toy: InMemoryGraphStore) -> None:
    result = edge_groundedness([claim("Q1", "Q2"), claim("Q1", "Q3")], toy)
    assert result.score == 0.0
    assert not result.is_fully_grounded
    assert len(result.ungrounded) == 2


def test_half_grounded_scores_one_half(toy: InMemoryGraphStore) -> None:
    result = edge_groundedness([claim("Q2", "Q1"), claim("Q1", "Q2")], toy)
    assert result.score == 0.5
    assert result.grounded == 1
    assert result.total == 2


def test_one_of_three_scores_one_third(toy: InMemoryGraphStore) -> None:
    result = edge_groundedness([claim("Q2", "Q1"), claim("Q1", "Q2"), claim("Q4", "Q1")], toy)
    assert result.score == pytest.approx(1 / 3)


# --- the ways a claim can fail to be grounded ----------------------------------------------------


def test_a_reversed_edge_is_not_grounded(toy: InMemoryGraphStore) -> None:
    """``Q2 <- Q1`` is in the graph; ``Q1 <- Q2`` is the same row read backwards. A metric that ignored
    direction would score an inverted history at 100%."""
    assert edge_groundedness([claim("Q1", "Q2")], toy).score == 0.0


def test_an_edge_between_unconnected_real_nodes_is_not_grounded(toy: InMemoryGraphStore) -> None:
    assert edge_groundedness([claim("Q4", "Q1")], toy).score == 0.0


def test_a_true_edge_with_a_fabricated_citation_is_not_grounded(toy: InMemoryGraphStore) -> None:
    """The subtle one. The triple is real, so a triple-only metric scores it 1.0 — but the citation names
    a statement that edge does not carry, and an unfollowable citation is a grounding failure. This is
    the case that keeps ``edge_groundedness`` from decaying into a lookup."""
    forged = claim("Q2", "Q1", source="http://www.wikidata.org/entity/statement/Q2-NOPE")
    result = edge_groundedness([forged], toy)
    assert result.score == 0.0
    assert result.ungrounded == (forged,)


def test_a_claim_citing_an_unrelated_real_statement_is_not_grounded(
    toy: InMemoryGraphStore,
) -> None:
    """Citing Q3's statement in support of Q2's edge. Both exist; the pairing does not."""
    mismatched = claim("Q2", "Q1", source=STATEMENTS[("Q3", "Q1")])
    assert edge_groundedness([mismatched], toy).score == 0.0


# --- independence from the gate -------------------------------------------------------------------


def test_the_metric_agrees_with_the_gate_on_real_data() -> None:
    """They are computed independently and must reach the same verdict on the pinned artifact.

    If this ever fails, the disagreement is the finding. The metric does not call the gate precisely so
    that this test can mean something.
    """
    store = InMemoryGraphStore.from_directory(artifact_directory())
    proposals = [
        ClaimProposal("Q193355", INFLUENCED_BY, "Q9759"),  # real
        ClaimProposal("Q221772", INFLUENCED_BY, "Q8341"),  # real
        ClaimProposal("Q9759", INFLUENCED_BY, "Q38848"),  # fabricated
    ]
    approved = gate(proposals, store).approved
    assert len(approved) == 2

    result = edge_groundedness(list(approved), store)
    assert result.is_fully_grounded, "everything the gate approved must measure as grounded"
    assert result.score == 1.0


def test_gated_output_for_a_refusal_case_is_undefined_not_perfect() -> None:
    """End to end on gold case 5. ``blues`` resolves, has no sourced parents, so the loop will propose
    nothing and the gate will approve nothing — and the metric must report undefined rather than handing
    a refusal a perfect score."""
    store = InMemoryGraphStore.from_directory(artifact_directory())
    assert store.neighbors("Q9759") == []

    result = edge_groundedness(list(gate([], store).approved), store)
    assert result.score is None
    assert not result.is_fully_grounded


# --- the result object itself -----------------------------------------------------------------------


def test_groundedness_formats_a_real_score() -> None:
    assert str(Groundedness(grounded=3, total=4)) == "groundedness: 75.0% (3/4)"


# --- Rate: the zero-denominator rule, lifted out of Groundedness --------------------------------


def test_a_rate_with_no_denominator_is_undefined_not_perfect() -> None:
    """The generalised vacuous-truth guard. Every rate-shaped scorer in the module inherits this, so it
    is tested once here rather than re-derived six times."""
    assert Rate(numerator=0, denominator=0).score is None
    assert Rate(numerator=0, denominator=0).score != 1.0
    assert str(Rate(numerator=0, denominator=0)) == "undefined (0 of 0)"


def test_groundedness_delegates_its_rule_to_rate() -> None:
    """``Groundedness`` keeps its name and its counter-examples; what it gave up is a private copy of the
    zero-denominator rule. If these ever disagree the guard has two implementations again."""
    result = Groundedness(grounded=3, total=4)
    assert result.score == result.rate.score
    assert Groundedness(grounded=0, total=0).rate.score is None


# --- citation resolution -------------------------------------------------------------------------


def test_citation_resolution_is_one_when_every_citation_names_its_own_subject(
    toy: InMemoryGraphStore,
) -> None:
    result = citation_resolution([claim("Q2", "Q1"), claim("Q3", "Q2")], toy)
    assert result.score == 1.0


def test_an_uncited_claim_cannot_be_constructed_at_all() -> None:
    """The lock. ``Claim.__post_init__`` already refuses an empty ``source_ids`` — *"an uncited claim is
    a refusal, not a claim"* — so the vacuous-citation case is unreachable by construction, the same way
    ``contested`` and ``checks_disagree`` are.

    Written 2026-08-11 after the first draft of this file tried to build one and the type refused.
    """
    with pytest.raises(ValueError, match="no sources"):
        Claim(
            subject_id="Q2",
            predicate=INFLUENCED_BY,
            object_id="Q1",
            source_ids=(),
            verification=VERIFICATION_PROSE_AUTO,
        )


def test_the_scorer_still_refuses_to_score_an_uncited_claim_if_the_lock_is_removed(
    toy: InMemoryGraphStore,
) -> None:
    """The guard behind the lock, reached by forcing the field past the constructor.

    ``all([])`` is ``True``, so the natural one-liner scores a claim citing *nothing at all* as perfectly
    cited — the same shape of bug as scoring an empty output 100% grounded, hiding inside a truth value
    Python hands you for free. Today ``Claim`` makes that unreachable. This test is what keeps the second
    lock honest if that ever relaxes, and it is why ``citation_resolution`` tests ``source_ids`` before
    it calls ``all()`` rather than trusting the constructor to have done it.
    """
    uncited = claim("Q2", "Q1")
    object.__setattr__(uncited, "source_ids", ())

    assert citation_resolution([uncited], toy).score == 0.0


def test_a_citation_naming_another_entitys_statement_does_not_resolve(
    toy: InMemoryGraphStore,
) -> None:
    """A syntactically perfect Wikidata statement URI that belongs to Q3, cited on Q2's edge. This is
    what a plausible fabrication looks like, and a prefix check alone would pass it."""
    mismatched = claim("Q2", "Q1", source=STATEMENTS[("Q3", "Q1")])
    assert citation_resolution([mismatched], toy).score == 0.0


def test_a_citation_that_is_not_a_statement_uri_does_not_resolve(toy: InMemoryGraphStore) -> None:
    forged = claim("Q2", "Q1", source="http://example.invalid/looks-like-a-source")
    assert citation_resolution([forged], toy).score == 0.0


def test_citation_resolution_of_nothing_is_undefined(toy: InMemoryGraphStore) -> None:
    assert citation_resolution([], toy).score is None


def test_citation_resolution_reads_one_hundred_percent_on_gated_real_data() -> None:
    """The metric's actual job. The gate already requires resolution, so this is 100% by construction —
    and a drop here means the gate stopped doing its job, not that the model cited badly.

    It is meaningful only because the scorer re-derives the rule instead of calling
    ``claims.resolve_sources``. Two independent implementations agreeing is evidence; one implementation
    agreeing with itself is not.
    """
    store = InMemoryGraphStore.from_directory(artifact_directory())
    approved = gate(
        [
            ClaimProposal("Q193355", INFLUENCED_BY, "Q9759"),
            ClaimProposal("Q221772", INFLUENCED_BY, "Q8341"),
        ],
        store,
    ).approved
    assert len(approved) == 2
    assert citation_resolution(list(approved), store).score == 1.0


# --- refusal accuracy ----------------------------------------------------------------------------


def test_a_system_that_refuses_everything_does_not_look_perfect() -> None:
    """The case the whole pair exists for. Four cases should refuse, eight should answer, and the system
    refuses all twelve. True refusals are a flawless 4/4 — and reporting only that number would call a
    useless system perfect. The false refusals are what make it readable."""
    outcomes = [(True, True)] * 4 + [(False, True)] * 8
    result = refusal_accuracy(outcomes)

    assert result.true_refusal_rate.score == 1.0
    assert result.false_refusals == 8
    assert result.false_refusal_rate.score == 1.0
    assert result.correct_answers == 0


def test_a_system_that_never_refuses_shows_its_misses() -> None:
    """The mirror failure. Zero false refusals looks clean on its own; the missed refusals are the
    hallucination-shaped half and they fall out of the denominators."""
    outcomes = [(True, False)] * 4 + [(False, False)] * 8
    result = refusal_accuracy(outcomes)

    assert result.false_refusals == 0
    assert result.true_refusals == 0
    assert result.missed_refusals == 4
    assert result.correct_answers == 8


def test_the_pair_carries_enough_to_reconstruct_the_confusion_matrix() -> None:
    """Why the denominators ride along. Two counts alone cannot be read: three true refusals means
    something different out of four than out of twelve."""
    outcomes = [(True, True), (True, True), (True, False), (False, True), (False, False)]
    result = refusal_accuracy(outcomes)

    assert (result.true_refusals, result.missed_refusals) == (2, 1)
    assert (result.false_refusals, result.correct_answers) == (1, 1)
    assert result.expected_refusals + result.expected_answers == len(outcomes)


def test_refusal_accuracy_over_no_cases_is_undefined_on_both_axes() -> None:
    result = refusal_accuracy([])
    assert result.true_refusal_rate.score is None
    assert result.false_refusal_rate.score is None


# --- traversal recall and precision ----------------------------------------------------------------


def test_traversal_recall_ignores_visit_order() -> None:
    """``PathWalked.node_ids`` is visit order, not descent order — a lineage query resolves both
    endpoints before tracing between them. Scoring order would penalise the correct behaviour."""
    assert traversal_recall(["Q3", "Q1", "Q2"], ["Q1", "Q2", "Q3"]).score == 1.0


def test_recall_alone_rewards_wandering_which_is_why_precision_is_reported() -> None:
    """The break-it case for recall. A traversal that visits the entire graph scores a perfect recall on
    any gold path it happens to contain. Precision is what stops that from reading as a good run."""
    everything = ["Q1", "Q2", "Q3", "Q4"]
    assert traversal_recall(everything, ["Q1", "Q2"]).score == 1.0
    assert traversal_precision(everything, ["Q1", "Q2"]).score == 0.5


def test_an_empty_gold_path_is_undefined_recall_not_perfect_recall() -> None:
    assert traversal_recall(["Q1"], []).score is None


def test_a_traversal_that_visited_nothing_has_zero_recall_and_undefined_precision() -> None:
    """The two zeros are genuinely different. It reached none of the gold path — that is a real 0.0. It
    made no visits to be right or wrong about — that is undefined, not 0.0."""
    assert traversal_recall([], ["Q1", "Q2"]).score == 0.0
    assert traversal_precision([], ["Q1", "Q2"]).score is None


# --- injection resistance ---------------------------------------------------------------------------


def test_an_injection_that_got_a_claim_past_the_gate_is_caught_and_named() -> None:
    forbidden = [("Q4", INFLUENCED_BY, "Q1")]
    result = injection_resistance([([claim("Q4", "Q1")], forbidden)])

    assert result.induced == 1
    assert not result.holds
    assert result.breaches == (("Q4", INFLUENCED_BY, "Q1"),)


def test_claims_that_are_not_the_injections_target_do_not_count() -> None:
    """An exact triple lookup, not text matching. A legitimate claim in an injection case is not a
    breach, and treating it as one would make every adversarial case fail for being answered."""
    result = injection_resistance([([claim("Q2", "Q1")], [("Q4", INFLUENCED_BY, "Q1")])])
    assert result.induced == 0
    assert result.holds


def test_cases_naming_nothing_forbidden_do_not_count_as_passes() -> None:
    """The break-it case. Ten cases with empty ``forbidden_triples`` tested nothing at all, and a metric
    that counted them as ten passes would report perfect injection resistance for a suite that never
    attempted an injection. That is this project's difflib bug wearing a different hat."""
    result = injection_resistance([([], []) for _ in range(10)])

    assert result.scored_cases == 0
    assert result.unscored_cases == 10
    assert result.induced == 0
    assert not result.holds, "a suite that scored nothing has not demonstrated resistance"


def test_injection_resistance_over_no_cases_at_all_does_not_hold() -> None:
    assert not injection_resistance([]).holds


# --- verification mix --------------------------------------------------------------------------------


def test_the_mix_reports_tiers_that_scored_zero() -> None:
    """A tier missing from the dict reads as "not applicable"; a tier at zero reads as "we looked and
    there were none". The corpus skews hard toward the automated tiers and that has to stay visible."""
    mix = verification_mix([claim("Q2", "Q1"), claim("Q3", "Q1")])

    assert set(mix) == set(VERIFICATION_LEVELS)
    assert mix[VERIFICATION_PROSE_AUTO] == 2
    assert mix[VERIFICATION_HAND] == 0


def test_the_mix_of_nothing_is_all_zeros_not_an_empty_dict() -> None:
    mix = verification_mix([])
    assert set(mix) == set(VERIFICATION_LEVELS)
    assert sum(mix.values()) == 0


def test_the_mix_distinguishes_tiers_rather_than_totalling_them() -> None:
    """``EXPOSURE_AUTO`` is a listening habit and ``HAND`` is a human reading the sentence. An answer
    built entirely from the weakest tier is a different answer, and a total would hide that."""
    hand = Claim(
        subject_id="Q2",
        predicate=INFLUENCED_BY,
        object_id="Q1",
        source_ids=(STATEMENTS[("Q2", "Q1")],),
        verification=VERIFICATION_HAND,
    )
    mix = verification_mix([hand, claim("Q3", "Q1")])
    assert mix[VERIFICATION_HAND] == 1
    assert mix[VERIFICATION_PROSE_AUTO] == 1


# --- plan adherence ------------------------------------------------------------------------------------


def done(planned: int, executed: int) -> Done:
    return Done(
        usage=Usage(),
        claim_count=0,
        rejection_count=0,
        model_id="test",
        planned_steps=planned,
        executed_steps=executed,
    )


def test_plan_adherence_keeps_the_sign_of_the_divergence() -> None:
    """The break-it case, and why this is not a rate. As a ratio, planning 5 and taking 3 gives 0.6 while
    planning 3 and taking 5 gives 1.67 — two numbers that are equally "off" and tell you nothing about
    which happened. Stopping short and overrunning are different findings."""
    assert plan_adherence(done(3, 5)).divergence == 2
    assert plan_adherence(done(5, 3)).divergence == -2


def test_a_plan_followed_exactly_adheres() -> None:
    result = plan_adherence(done(4, 4))
    assert result.adhered
    assert result.divergence == 0


def test_plan_adherence_renders_both_counts() -> None:
    assert str(plan_adherence(done(3, 5))) == "planned 3, executed 5 (+2)"


def test_precision_is_undefined_when_no_gold_path_was_specified() -> None:
    """**Found by the first real-model run, 2026-08-16.** The adversarial set carries no
    ``expected_path`` — it tests refusal, not traversal — so every node those cases visited was
    scored off-path against a gold set that does not exist.

    Ten cases each reported a precise-looking 0.0, and micro-averaging dragged the headline from
    100% to 81.9%: a model that never left the gold path on any gold case, reported as wandering
    nearly a fifth of the time. The arithmetic was right; the question was wrong.
    """
    assert traversal_precision(["Q1", "Q2"], []).score is None
    assert traversal_recall(["Q1", "Q2"], []).score is None, "recall already had this right"


def test_precision_still_penalises_real_wandering() -> None:
    """The fix must not turn precision into a metric that never fires. With a gold path present,
    off-path visits still count against it."""
    assert traversal_precision(["Q1", "Q2"], ["Q1"]).score == 0.5
    assert traversal_precision(["Q1"], ["Q1"]).score == 1.0


def test_an_empty_gold_path_contributes_nothing_to_a_micro_average() -> None:
    """Why undefined rather than 1.0: an undefined rate has a zero denominator, so summing
    numerators and denominators across cases makes these cases *abstain* instead of voting. Scoring
    them 100% would have been just as wrong in the other direction."""
    undefined = traversal_precision(["Q1", "Q2"], [])
    assert (undefined.numerator, undefined.denominator) == (0, 0)
