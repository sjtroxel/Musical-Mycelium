"""Render a ``SuiteResult`` for a human. The rendering is where the caveats become unavoidable.

Three rules, and each one exists because the alternative is a number that gets quoted without its
qualifier six weeks later:

1. **Every number carries its provider.** Not in a header the reader scrolls past — on the line. The
   phase 4 implementation doc says it outright: *"The report must carry which provider produced it, on
   the same line as every number."* ``100.0% [scripted]`` cannot be pasted into a resume bullet by
   accident; ``100.0%`` can.
2. **A script-determined metric is unrenderable without its mark.** ``render`` raises when a scripted
   result declares no ``script_determined`` metrics. That is deliberate over-strictness: the failure it
   prevents is a future edit that adds a provider, forgets the marking, and produces a report where
   ``traversal_recall: 100.0%`` reads as a traversal result. Making it raise means the omission shows up
   as a crash in CI rather than as a good-looking number.
3. **A partial run says so first.** ``complete: false`` is rendered above the metrics rather than below,
   because a reader who has already seen the headline has already formed the belief.

The same guard shape is owed to the judge in step 7 — ``report.py`` raises if asked to render a judged
number with no agreement figure loaded. This module is where that will live, and rule 2 is its precedent.
"""

from __future__ import annotations

from musical_mycelium.eval.metrics import Rate
from musical_mycelium.eval.slices import SliceReport
from musical_mycelium.eval.suite import PROVIDER_SCRIPTED, SuiteResult


class UnmarkedScriptedResult(RuntimeError):
    """A scripted result was rendered without declaring which metrics its script decided.

    Raised rather than defaulted, for the reason ``suite.SCRIPT_DETERMINED`` is a constant rather than a
    comment: a caveat that can be omitted is a caveat that will be.
    """


def render(result: SuiteResult) -> str:
    """The whole report as text. Raises ``UnmarkedScriptedResult`` on an unmarked scripted run."""
    if result.provider == PROVIDER_SCRIPTED and not result.script_determined:
        raise UnmarkedScriptedResult(
            "a scripted run must declare its script-determined metrics before it can be rendered; "
            f"expected a non-empty script_determined on the {result.dataset!r} result"
        )

    lines = [
        f"{result.dataset} v{result.dataset_version} "
        f"-- {result.cases_run} cases, provider={result.provider}, model={result.model_id}",
        f"artifact {result.artifact_version} (dataset pinned to {result.artifact_pin})",
    ]

    if not result.artifact_matches_pin:
        lines.append(
            "  WARNING: the artifact does not match the pin this dataset was authored against. "
            "Every number below is scored against a corpus the cases were not written for."
        )
    if not result.complete:
        lines.append(f"  INCOMPLETE: {result.aborted_reason}")
        lines.append(
            "  Numbers below cover only the cases that ran, chosen by exhaustion, not at random."
        )
    if result.truncated_runs:
        lines.append(f"  truncated traversals: {', '.join(result.truncated_runs)}")

    lines.append("")
    lines.extend(_metric_lines(result))
    lines.append("")
    lines.extend(_slice_lines(result.slices, result.provider))

    if result.script_determined:
        lines.append("")
        lines.extend(_script_determined_note(result))

    return "\n".join(lines)


def _metric_lines(result: SuiteResult) -> list[str]:
    """The catalog. Blocking-eligible metrics first, descriptive ones after, script-determined last.

    Ordered by what a reader should believe, not by what scores best. The three at the bottom are the
    ones a scripted run cannot speak to, and putting them under their own marker keeps a skim-reader from
    treating the whole block as equally load-bearing.
    """
    marked = set(result.script_determined)
    lines = ["metrics:"]

    lines.append(_line("edge_groundedness", _rate(result.groundedness.rate), result, marked))
    lines.append(_line("citation_resolution", _rate(result.citation), result, marked))
    lines.append(
        _line(
            "refusal_accuracy",
            f"true {result.refusal.true_refusal_rate}; false {result.refusal.false_refusal_rate}",
            result,
            marked,
        )
    )
    lines.append(
        _line(
            "injection_resistance",
            f"induced {result.injection.induced} over {result.injection.scored_cases} scored "
            f"({result.injection.unscored_cases} cases planted nothing)",
            result,
            marked,
        )
    )
    lines.append(
        _line(
            "verification_mix",
            ", ".join(f"{tier}={count}" for tier, count in result.verification.items()),
            result,
            marked,
        )
    )
    lines.append(
        _line("cases_correct", f"{result.cases_correct}/{result.cases_run}", result, marked)
    )
    lines.append(_line("traversal_recall", _rate(result.recall), result, marked))
    lines.append(_line("traversal_precision", _rate(result.precision), result, marked))
    lines.append(
        _line(
            "plan_adherence",
            f"{sum(1 for r in result.results if r.adherence.adhered)}/{result.cases_run} exact",
            result,
            marked,
        )
    )
    lines.append(
        _line(
            "tokens",
            f"{result.usage.total_tokens} "
            f"(in {result.usage.input_tokens}, out {result.usage.output_tokens})",
            result,
            marked,
        )
    )
    return lines


def _line(name: str, value: str, result: SuiteResult, marked: set[str]) -> str:
    """One metric line: name, value, provider, and the script marker when it applies.

    The provider is appended to **every** line rather than to the ones that seem to need it, because
    which lines need it is exactly the judgement that goes wrong later.
    """
    suffix = f"  [{result.provider}]"
    if name in marked:
        suffix += "  SCRIPT-DETERMINED: decided by the trace, not the model"
    return f"  {name}: {value}{suffix}"


def _rate(rate: Rate) -> str:
    """``Rate.__str__`` already refuses to print a percentage with no denominator. Routed through here so
    that stays true of every rate in the report rather than of the ones that remembered."""
    return str(rate)


def _slice_lines(slices: tuple[SliceReport, ...], provider: str) -> list[str]:
    if not slices:
        return ["slices: none"]
    lines = [f"slices of cases_correct  [{provider}]"]
    for report in slices:
        lines.extend(f"  {line}" for line in report.render())
    return lines


def _script_determined_note(result: SuiteResult) -> list[str]:
    """Spell the caveat out in prose as well as marking it. The marker survives a skim; the prose is what
    survives being pasted into a doc six weeks later."""
    return [
        "what a scripted run does and does not show:",
        "  DOES  -- the gate and the loop refuse unsupported claims, citations resolve, and the corpus",
        "          still holds what the dataset was authored against. A script cannot make an ungrounded",
        "          claim pass: proposals are built from real artifact edges, never from model text.",
        "  DOES NOT -- that a real model chooses the right tool, reaches the right nodes, or stops at the",
        f"          right time. {', '.join(result.script_determined)} are decided by the trace policy.",
        "          Real-model traversal is phase 4 step 4 and it costs money.",
    ]
