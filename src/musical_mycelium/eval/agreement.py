"""Judge-human agreement: raw agreement and Cohen's kappa. Phase 4 step 7a.

`.claude/rules/evals.md`: *"Hand-label 30 items, report judge-human agreement permanently next to every
judged metric. An LLM-judge score with no measured agreement is decoration."* This module computes the
figure; `report.py` is what refuses to print a judged number without it.

## Why kappa and not just the agreement rate

Raw agreement is the number people quote and it is inflatable to the point of meaninglessness. If 27 of
30 answers are genuinely SUPPORTED, a judge that answers SUPPORTED unconditionally agrees with the
human 90% of the time while measuring nothing at all. Chance-corrected agreement is what separates that
judge from one that is actually reading, and it is the difference between a portfolio project that says
"the judge agrees 90%" and one that can say what the 90% is worth.

Both are reported. Kappa without the raw rate is hard to read; the raw rate without kappa is the number
that flatters.

## Two scales, two kappas

- **Citation support is three unordered-for-scoring categories.** Unweighted Cohen's kappa: a
  disagreement is a disagreement.
- **Narrative quality is 1-5 and ordinal.** Quadratic weights, because scoring a 4 as a 5 is not the
  same error as scoring a 4 as a 1, and unweighted kappa on a five-point scale calls them identical.
  Exact and within-one agreement are both reported alongside, since a judge that is never more than one
  point out is useful even if its exact rate is poor.

## Undefined is not zero and not one

When both raters use a single category for everything, expected agreement is 1.0 and kappa is `0/0`.
That is **undefined**, and this module says so rather than returning a number. Same rule as `Rate`, for
the same reason: a denominator of zero is not perfection, and the vacuous-truth guard
`.claude/rules/evals.md` requires for groundedness is a general rule, not a groundedness quirk.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field

from musical_mycelium.eval.metrics import Rate

KAPPA_COHEN = "cohen"
KAPPA_QUADRATIC = "quadratic-weighted"

#: Landis & Koch's bands, kept because a bare kappa means nothing to most readers, and labelled as a
#: convention because that is what it is -- a widely used rule of thumb, not a property of the data.
_BANDS = (
    (0.81, "almost perfect"),
    (0.61, "substantial"),
    (0.41, "moderate"),
    (0.21, "fair"),
    (0.0, "slight"),
)


class NoAgreementMeasured(RuntimeError):
    """Agreement was asked for where none exists. Raised by `report.py` rather than rendered as blank."""


@dataclass(frozen=True, slots=True)
class Agreement:
    """One metric's judge-human agreement, with everything a reader needs to weigh it.

    `n` travels with the figure everywhere, deliberately. "Judge-human agreement 0.71" is a claim about
    a measurement whose whole credibility rests on how many items it was measured over, and the two get
    separated the moment they are allowed to.
    """

    metric: str
    n: int
    exact: Rate
    kappa: float | None
    kappa_kind: str
    #: Why kappa is `None`, when it is. Empty otherwise.
    undefined_reason: str = ""
    #: Only meaningful on an ordinal scale. `None` on the categorical one rather than 0, because
    #: "within one" has no meaning when the categories have no distance.
    within_one: Rate | None = None
    #: (human, judge) -> count. Kept because the shape of the disagreement is more actionable than its
    #: size: a judge one point low on everything needs a rubric anchor, a judge scattered needs a rewrite.
    confusion: Mapping[tuple[str, str], int] = field(default_factory=dict)

    @property
    def measured(self) -> bool:
        """Whether this is evidence at all. `n == 0` is not an agreement of zero -- it is no measurement,
        and it is the state `report.py` refuses to print a judged number beside."""
        return self.n > 0

    @property
    def strength(self) -> str:
        if self.kappa is None:
            return "undefined"
        for floor, label in _BANDS:
            if self.kappa >= floor:
                return label
        return "none (worse than chance)"

    def render(self) -> list[str]:
        kappa = (
            f"{self.kappa:.2f} ({self.strength}, {self.kappa_kind})"
            if self.kappa is not None
            else f"undefined -- {self.undefined_reason}"
        )
        lines = [
            f"  {self.metric}: exact {self.exact}, kappa {kappa}, n={self.n}",
        ]
        if self.within_one is not None:
            lines.append(f"    within one point: {self.within_one}")
        return lines


def _confusion(human: Sequence[object], judge: Sequence[object]) -> dict[tuple[str, str], int]:
    counts: dict[tuple[str, str], int] = {}
    for left, right in zip(human, judge, strict=True):
        key = (str(left), str(right))
        counts[key] = counts.get(key, 0) + 1
    return counts


def _kappa(
    human: Sequence[object],
    judge: Sequence[object],
    *,
    scale: Sequence[str],
    weights: bool = False,
) -> tuple[float | None, str]:
    """Cohen's kappa, quadratically weighted when asked. Returns `(kappa, undefined_reason)`.

    Written out rather than imported because the alternative is scipy or scikit-learn for one formula --
    a large dependency in a project whose deployed image is bounded by a 250MB limit (invariant 8).
    Thirty lines of arithmetic with tests against hand-computed values is the cheaper side of that trade.

    **`scale` is the declared scale, not the observed one, and on a weighted kappa that distinction is
    the difference between a right answer and a wrong one.** If a run happens to use only scores 1 and
    4, positions taken from the observed set put them one step apart and the quadratic weight forgives a
    three-point miss as if it were adjacent. The full scale has to be stated by the caller.
    """
    n = len(human)
    if n == 0:
        return None, "nothing was labeled"

    categories = list(dict.fromkeys([*scale, *(str(value) for value in (*human, *judge))]))
    index = {name: position for position, name in enumerate(categories)}
    size = len(categories)

    def weight(left: int, right: int) -> float:
        """1.0 for agreement, 0.0 for total disagreement. Quadratic in between when weighted, so a
        one-point miss on a five-point scale costs a sixteenth of a four-point miss."""
        if not weights:
            return 1.0 if left == right else 0.0
        if size == 1:
            return 1.0
        return 1.0 - ((left - right) ** 2) / ((size - 1) ** 2)

    human_counts = [0] * size
    judge_counts = [0] * size
    observed = 0.0
    for left, right in zip(human, judge, strict=True):
        i, j = index[str(left)], index[str(right)]
        human_counts[i] += 1
        judge_counts[j] += 1
        observed += weight(i, j)
    observed /= n

    expected = 0.0
    for i in range(size):
        for j in range(size):
            expected += weight(i, j) * (human_counts[i] / n) * (judge_counts[j] / n)

    if abs(1.0 - expected) < 1e-12:
        return None, (
            "expected agreement is 1.0 -- both raters used a single category, so chance correction "
            "divides by zero. Undefined, not perfect."
        )
    return (observed - expected) / (1.0 - expected), ""


def categorical(
    metric: str, human: Sequence[str], judge: Sequence[str], *, levels: Sequence[str] = ()
) -> Agreement:
    """Agreement on an unordered categorical scale. Citation support uses this.

    `levels` declares the scale. It cannot change an unweighted kappa -- a category nobody used
    contributes zero to both observed and expected agreement -- and it is still passed, because the
    alternative is a function whose correctness depends on which categories a run happened to produce.
    """
    exact_hits = sum(1 for left, right in zip(human, judge, strict=True) if left == right)
    kappa, reason = _kappa(human, judge, scale=[str(level) for level in levels])
    return Agreement(
        metric=metric,
        n=len(human),
        exact=Rate(numerator=exact_hits, denominator=len(human)),
        kappa=kappa,
        kappa_kind=KAPPA_COHEN,
        undefined_reason=reason,
        confusion=_confusion(human, judge),
    )


def ordinal(
    metric: str, human: Sequence[int], judge: Sequence[int], *, levels: Sequence[int]
) -> Agreement:
    """Agreement on an ordered numeric scale. Narrative quality uses this.

    `levels` is **required** here, unlike the categorical case, because the quadratic weights are
    positions on it: a scale declared as 1-5 forgives a one-point miss by fifteen sixteenths, and the
    same two labels scored against an observed-only scale of {1, 4} would be forgiven the same way
    despite being three points apart.
    """
    exact_hits = sum(1 for left, right in zip(human, judge, strict=True) if left == right)
    close = sum(1 for left, right in zip(human, judge, strict=True) if abs(left - right) <= 1)
    kappa, reason = _kappa(human, judge, scale=[str(level) for level in levels], weights=True)
    return Agreement(
        metric=metric,
        n=len(human),
        exact=Rate(numerator=exact_hits, denominator=len(human)),
        kappa=kappa,
        kappa_kind=KAPPA_QUADRATIC,
        undefined_reason=reason,
        within_one=Rate(numerator=close, denominator=len(human)),
        confusion=_confusion(human, judge),
    )
