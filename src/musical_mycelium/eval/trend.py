"""Live runs across time, grouped into cohorts that may honestly share a line. Phase 7.5 step 2.

**The difficulty is not drawing a line; it is that most of the history cannot be on one.** The stored
live runs span three corpus pins, six case counts, smoke tests of one and three cases, and one run that
did not finish (IMPLEMENTATION §4). A line through all of them would join three corpora. The scope doc
names the risk — *"a chart that lies more easily than a sentence"* — and that is what the default
implementation produces.

**The cohort rule is borrowed, never written fresh.** Two runs share a cohort when they agree on every
field ``noise.POOLING_FIELDS`` names except ``code_revision``, ran the identical list of cases, and both
finished. That is the noise floor's pooling rule with one field released on purpose: a trend exists to
show movement *across* code changes, so requiring one revision would make every cohort a single run.
Everything else is kept, **which makes it stricter than the gate.** ``thresholds._ungateable`` checks
completeness and case count but not the corpus pin, so the gate alone would put the 41-case run at
artifact 0.6.0 on the same line as the twelve at 0.5.0. ``tests/test_trend.py`` holds the implication the
plan asks for — nothing joined here is a pair the gate would refuse — over every committed run.

**A cohort is charted only at ``noise.MINIMUM_RUNS`` runs or more**, the project's standing number for a
spread to mean anything. Smaller cohorts, subsets and the unfinished run are listed with the reason and
never drawn, so "shown and not joined" holds by construction rather than by styling.

**This module computes and draws; it writes no sentences.** Every sentence around the charts lives in
``report_page.COPY``, the one place the page's prose is kept.
"""

from __future__ import annotations

import html
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from musical_mycelium.eval import noise

Json = dict[str, Any]

#: The noise floor's pooling fields, less the one a trend exists to cross.
COHORT_FIELDS = tuple(field for field in noise.POOLING_FIELDS if field != "code_revision")

#: What gets a small multiple. Groundedness and citation resolution are left out because they are
#: invariants that read 100% in every stored run -- six flat lines at the ceiling say less than the
#: sentence that says so -- and injection is a count that has never left zero. All three are in the
#: table twin, so nothing is hidden by the choice.
CHARTED = (
    "cases_correct",
    "true_refusal_rate",
    "false_refusal_rate",
    "traversal_recall",
    "traversal_precision",
    "approved_claims",
)

_METRICS = {name: (unit, extract) for name, unit, extract in noise.METRICS}

# Small-multiple geometry, in viewBox units. Scaled by CSS to the column width.
_W, _H = 260, 118
_LEFT, _RIGHT, _TOP, _BOTTOM = 46, 40, 10, 24


def fmt(unit: str, value: float | None) -> str:
    """A metric value as the page prints it, everywhere: charts, tables and the metrics section."""
    if value is None:
        return "undefined"
    return f"{value * 100:.1f}%" if unit == "rate" else f"{round(value):,}"


def when(stamp: str) -> str:
    """``20260907T230821Z`` as ``2026-09-07``. Filename stamps, because three early runs have no
    ``written_at`` field at all (§4); the filename is the only date every run carries."""
    return f"{stamp[0:4]}-{stamp[4:6]}-{stamp[6:8]}"


def cohort_key(stamp: str, run: Json) -> tuple[Any, ...]:
    """Two runs share a cohort exactly when their keys are equal.

    An unfinished run's key carries its own stamp, so it shares with nothing: ``noise.py`` refuses to
    pool one (``IncompleteRun``) for the reason that applies here too -- its cases were chosen by
    exhaustion rather than at random.
    """
    fields = tuple(run.get(field) for field in COHORT_FIELDS)
    cases = frozenset(case["case_id"] for case in run.get("per_case", ()))
    if not run.get("complete", False):
        return (*fields, cases, "incomplete", stamp)
    return (*fields, cases)


def comparable(a: tuple[str, Json], b: tuple[str, Json]) -> bool:
    return cohort_key(*a) == cohort_key(*b)


@dataclass(frozen=True, slots=True)
class Cohort:
    """Runs that may share a line, oldest first."""

    runs: tuple[tuple[str, Json], ...]

    @property
    def first(self) -> Json:
        return self.runs[0][1]

    @property
    def complete(self) -> bool:
        return bool(self.first.get("complete", False))

    @property
    def case_count(self) -> int:
        return len(self.first.get("per_case", ()))

    @property
    def artifact_version(self) -> str:
        return str(self.first.get("artifact_version", "unknown"))

    @property
    def stamps(self) -> tuple[str, ...]:
        return tuple(stamp for stamp, _ in self.runs)

    @property
    def charted(self) -> bool:
        return self.complete and len(self.runs) >= noise.MINIMUM_RUNS


def cohorts(runs: Sequence[tuple[str, Json]]) -> list[Cohort]:
    """Group ``runs`` (oldest first) into cohorts, ordered by each cohort's first run."""
    grouped: dict[tuple[Any, ...], list[tuple[str, Json]]] = {}
    for stamp, run in runs:
        grouped.setdefault(cohort_key(stamp, run), []).append((stamp, run))
    return [Cohort(tuple(members)) for members in grouped.values()]


def unsteady_cases(cohort: Cohort) -> list[tuple[str, list[bool]]]:
    """Cases NOT correct in every run of the cohort, with their verdict per run.

    The per-case view exists because an aggregate hiding a per-case constant has bitten this project
    twice: ``traversal_recall`` read an identical figure across five runs because one case failed
    identically every time. A flat line is a reason to ask what is constant, and this is the answer.
    """
    order = [case["case_id"] for case in cohort.first.get("per_case", ())]
    verdicts: dict[str, list[bool]] = {case_id: [] for case_id in order}
    for _, run in cohort.runs:
        correct = {case["case_id"]: bool(case.get("correct")) for case in run.get("per_case", ())}
        for case_id in order:
            verdicts[case_id].append(correct.get(case_id, False))
    return [(case_id, marks) for case_id, marks in verdicts.items() if not all(marks)]


def _domain(
    values: Sequence[float], band: tuple[float, float] | None, unit: str
) -> tuple[float, float]:
    """A y-range that fits the points and the band with some air, clamped to what the unit allows."""
    pool = list(values) + (list(band) if band else [])
    low, high = min(pool), max(pool)
    minimum_span = 0.02 if unit == "rate" else 2.0
    span = max(high - low, minimum_span)
    low, high = low - span * 0.25, high + span * 0.25
    if unit == "rate":
        low, high = max(low, 0.0), min(high, 1.0)
    else:
        low = max(low, 0.0)
    return low, high


def chart(name: str, cohort: Cohort, band: tuple[float, float] | None) -> str:
    """One small multiple: a metric across a cohort's runs, with the noise band where one was measured.

    A single series in one hue, so no legend: the figure caption names it. Every point carries a native
    ``<title>`` (no script on this page), and every value is also in the cohort's table twin, so the
    hover is an enhancement and never the only way to read a number.
    """
    unit, extract = _METRICS[name]
    values = [extract(run) for _, run in cohort.runs]
    present = [value for value in values if value is not None]
    if not present:
        return ""
    low, high = _domain(present, band, unit)
    plot_w, plot_h = _W - _LEFT - _RIGHT, _H - _TOP - _BOTTOM
    step = plot_w / max(len(values) - 1, 1)

    def x(index: int) -> float:
        return _LEFT + index * step

    def y(value: float) -> float:
        return _TOP + (high - value) / (high - low) * plot_h

    parts = [
        f'<line class="t-grid" x1="{_LEFT}" x2="{_W - _RIGHT}" y1="{_TOP}" y2="{_TOP}"/>',
        f'<line class="t-grid" x1="{_LEFT}" x2="{_W - _RIGHT}" y1="{_TOP + plot_h}" y2="{_TOP + plot_h}"/>',
        f'<text class="t-label" x="{_LEFT - 6}" y="{_TOP + 4}" text-anchor="end">{fmt(unit, high)}</text>',
        f'<text class="t-label" x="{_LEFT - 6}" y="{_TOP + plot_h + 4}" text-anchor="end">'
        f"{fmt(unit, low)}</text>",
    ]
    if band is not None:
        top, bottom = y(max(band)), y(min(band))
        parts.append(
            f'<rect class="t-band" x="{_LEFT}" y="{top:.1f}" width="{plot_w}" '
            f'height="{max(bottom - top, 1.0):.1f}"/>'
        )

    # A run where the metric was undefined BREAKS the line rather than being bridged: joining across a
    # gap draws a value that was never measured.
    segments: list[list[str]] = [[]]
    for index, value in enumerate(values):
        if value is None:
            segments.append([])
        else:
            segments[-1].append(f"{x(index):.1f},{y(value):.1f}")
    for segment in segments:
        if len(segment) > 1:
            parts.append(f'<polyline class="t-line" points="{" ".join(segment)}"/>')

    for index, ((stamp, run), value) in enumerate(zip(cohort.runs, values, strict=True)):
        if value is None:
            continue
        label = html.escape(
            f"{when(stamp)}, revision {run.get('code_revision', 'unknown')}: {fmt(unit, value)}"
        )
        parts.append(
            f'<g><title>{label}</title><circle class="t-hit" cx="{x(index):.1f}" cy="{y(value):.1f}" r="12"/>'
            f'<circle class="t-dot" cx="{x(index):.1f}" cy="{y(value):.1f}" r="4"/></g>'
        )

    last_index = max(index for index, value in enumerate(values) if value is not None)
    last = values[last_index]
    assert last is not None
    parts.append(
        f'<text class="t-end" x="{x(last_index) + 8:.1f}" y="{y(last) + 4:.1f}">{fmt(unit, last)}</text>'
    )
    parts.append(
        f'<text class="t-label" x="{_LEFT}" y="{_H - 6}">{when(cohort.runs[0][0])}</text>'
        f'<text class="t-label" x="{_W - _RIGHT}" y="{_H - 6}" text-anchor="end">'
        f"{when(cohort.runs[-1][0])}</text>"
    )
    summary = html.escape(
        f"{name} across {len(values)} runs, from {fmt(unit, present[0])} to {fmt(unit, present[-1])}"
    )
    return (
        f'<svg class="t-chart" viewBox="0 0 {_W} {_H}" role="img" aria-label="{summary}">'
        + "".join(parts)
        + "</svg>"
    )
