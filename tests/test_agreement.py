"""Agreement tests. Every kappa here is checked against a value computed by hand.

`.claude/rules/evals.md`: *"Unit-test the metrics themselves. Synthetic outputs where the answer is known
by construction... A metric you have not tried to break is not a metric."* Agreement is the metric that
decides whether every judged number in this project is worth reporting, so it gets the same treatment as
groundedness — including its own vacuous-truth case, which is the degenerate label set.
"""

from __future__ import annotations

import pytest

from musical_mycelium.eval.agreement import KAPPA_QUADRATIC, categorical, ordinal
from musical_mycelium.eval.labelling import QUALITY_LEVELS, SUPPORT_LEVELS

SUPPORT = list(SUPPORT_LEVELS)
QUALITY = list(QUALITY_LEVELS)


# --- the arithmetic ---------------------------------------------------------------------------------


def test_perfect_agreement_over_two_categories_is_one() -> None:
    """po = 1, pe = 0.5, kappa = 1. The only case where kappa and raw agreement may both read perfect."""
    human = ["SUPPORTED"] * 5 + ["OVERSTATED"] * 5
    figure = categorical("citation_support", human, human, levels=SUPPORT)
    assert figure.exact.score == 1.0
    assert figure.kappa == pytest.approx(1.0)
    assert figure.strength == "almost perfect"


def test_kappa_is_zero_when_agreement_is_exactly_chance() -> None:
    """Hand-computed. Human 5/5 split, judge 5/5 split, and they agree on exactly half:
    po = 0.5, pe = 0.5*0.5 + 0.5*0.5 = 0.5, kappa = 0.

    **This is the case raw agreement cannot see.** 50% agreement looks like a weak judge; kappa says it
    is a judge indistinguishable from a coin.
    """
    human = ["SUPPORTED", "SUPPORTED", "SUPPORTED", "SUPPORTED", "SUPPORTED"] + ["OVERSTATED"] * 5
    judge = ["SUPPORTED"] * 3 + ["OVERSTATED"] * 2 + ["SUPPORTED"] * 2 + ["OVERSTATED"] * 3
    figure = categorical("citation_support", human, judge, levels=SUPPORT)
    assert figure.exact.score == pytest.approx(0.6)
    assert figure.kappa == pytest.approx(0.2)


def test_a_judge_that_answers_one_category_scores_high_raw_and_zero_kappa() -> None:
    """**The reason kappa is reported at all, in one case.** 9 of 10 items are genuinely SUPPORTED and
    the judge says SUPPORTED unconditionally: 90% raw agreement, and it has measured nothing.

    kappa is exactly 0.0 here — chance agreement is also 0.9 — which is the number that says so. Quoting
    the 90% alone would describe this judge as excellent.
    """
    human = ["SUPPORTED"] * 9 + ["UNSUPPORTED"]
    judge = ["SUPPORTED"] * 10
    figure = categorical("citation_support", human, judge, levels=SUPPORT)
    assert figure.exact.score == pytest.approx(0.9)
    assert figure.kappa == pytest.approx(0.0)
    assert figure.strength == "slight"


def test_both_raters_using_one_category_is_undefined_not_perfect() -> None:
    """The vacuous-truth guard, in its agreement form. Every item labeled the same by both raters is
    100% raw agreement over a measurement that could not have failed. `Rate` refuses to turn 0/0 into a
    number and so does this.

    Broken deliberately on 2026-08-19 by returning 1.0 when `1 - pe` underflows: the degenerate set
    reported kappa 1.00, "almost perfect", and this test failed.
    """
    human = ["SUPPORTED"] * 8
    figure = categorical("citation_support", human, list(human), levels=SUPPORT)
    assert figure.exact.score == 1.0
    assert figure.kappa is None
    assert figure.strength == "undefined"


def test_worse_than_chance_is_reported_as_such() -> None:
    human = ["SUPPORTED", "OVERSTATED", "SUPPORTED", "OVERSTATED"]
    judge = ["OVERSTATED", "SUPPORTED", "OVERSTATED", "SUPPORTED"]
    figure = categorical("citation_support", human, judge, levels=SUPPORT)
    assert figure.kappa is not None
    assert figure.kappa < 0
    assert figure.strength == "none (worse than chance)"


# --- the ordinal scale ------------------------------------------------------------------------------


def test_quadratic_weights_forgive_a_near_miss_more_than_a_far_one() -> None:
    """Two label sets with the same raw agreement and different weighted kappa. If they came out equal,
    the weights are not being applied."""
    human = [1, 2, 3, 4, 5, 3, 2, 4]
    near = [2, 2, 3, 4, 4, 3, 3, 4]
    far = [5, 2, 3, 4, 1, 3, 5, 4]
    close = ordinal("narrative_quality", human, near, levels=QUALITY)
    distant = ordinal("narrative_quality", human, far, levels=QUALITY)
    assert close.exact.score == distant.exact.score == pytest.approx(0.625)
    assert close.kappa is not None and distant.kappa is not None
    assert close.kappa > 0.8
    assert distant.kappa < 0
    assert close.kappa_kind == KAPPA_QUADRATIC


def test_the_weighted_scale_is_the_declared_one_not_the_observed_one() -> None:
    """**The trap this class of metric sets.** A run where only 1s and 4s appear has an observed scale
    of two categories; positions taken from it put 1 and 4 one step apart and the quadratic weight
    forgives a three-point miss as if it were adjacent.

    Same labels, two scales, two different answers. The declared 1-5 scale is the correct one, and it is
    the one that must be harder to agree on.

    Broken deliberately on 2026-08-19 by deriving the scale from the observed values inside `_kappa`:
    the three-point miss scored as generously as a one-point miss, and this test failed.
    """
    human = [2, 1, 2, 2]
    judge = [5, 1, 5, 2]
    declared = ordinal("narrative_quality", human, judge, levels=QUALITY)
    observed_only = ordinal("narrative_quality", human, judge, levels=[1, 2, 5])
    assert declared.kappa is not None and observed_only.kappa is not None
    assert declared.kappa == pytest.approx(0.2)
    assert observed_only.kappa == pytest.approx(0.5556, abs=1e-4)


def test_within_one_is_reported_for_the_ordinal_scale_only() -> None:
    """A judge that is never more than a point out is useful even when its exact rate is poor, and that
    fact is invisible in exact agreement alone."""
    human = [2, 3, 4, 5]
    judge = [3, 4, 5, 4]
    figure = ordinal("narrative_quality", human, judge, levels=QUALITY)
    assert figure.exact.score == 0.0
    assert figure.within_one is not None
    assert figure.within_one.score == 1.0

    categoricals = categorical("citation_support", ["SUPPORTED"], ["OVERSTATED"], levels=SUPPORT)
    assert categoricals.within_one is None


# --- nothing measured -------------------------------------------------------------------------------


def test_no_items_is_not_an_agreement_of_zero() -> None:
    """`measured` is what `report.py` checks before printing a judged number. An empty label set is not
    a disagreement — it is the absence of evidence, and the two must not render the same."""
    figure = categorical("citation_support", [], [], levels=SUPPORT)
    assert figure.n == 0
    assert not figure.measured
    assert figure.kappa is None
    assert figure.exact.score is None


def test_mismatched_lengths_raise_rather_than_truncate() -> None:
    """`zip(strict=True)`. Silently truncating to the shorter list would compute a real-looking kappa
    over a subset chosen by an off-by-one."""
    with pytest.raises(ValueError):
        categorical("citation_support", ["SUPPORTED", "OVERSTATED"], ["SUPPORTED"], levels=SUPPORT)


def test_the_confusion_matrix_keeps_the_direction() -> None:
    """(human, judge), not the reverse. A judge that is systematically one level harsher and one that is
    systematically softer need completely different fixes, and the matrix is the only thing that says
    which one is happening."""
    figure = categorical(
        "citation_support", ["SUPPORTED", "SUPPORTED"], ["OVERSTATED", "OVERSTATED"], levels=SUPPORT
    )
    assert figure.confusion == {("SUPPORTED", "OVERSTATED"): 2}
