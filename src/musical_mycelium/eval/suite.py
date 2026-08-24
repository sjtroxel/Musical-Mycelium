"""Tier 1: load a dataset, drive it through the loop, score the catalog, slice every result.

**Dataset-agnostic and provider-agnostic, in the same sense ``runner.py`` is.** This module knows what an
``EvalCase`` is — a query, a subject, an expectation about refusal, an expected path — and knows nothing
about gold cases, adversarial cases, or held-out cases. ``gold.py`` adapts the gold JSON into that shape;
a step 4 caller swaps the ``llm_for`` factory for one that returns a ``BedrockLLM`` and changes nothing
else. That swap is the point: invariant 7's seam is finally carrying two providers through one code path
instead of one provider through two.

**The catalog is eight scorers plus two telemetry figures, and this module does not chase eleven.** The
phase 4 scope doc says eleven; the implementation doc already recorded the correction and the reason.
``contested`` is not here because decision A1 removed it — one source per edge on this corpus — and
``verification_mix`` stands in its place.

## What a scripted number means, and why some of them mean nothing

Every number this module produces carries the provider that produced it, because the same metric means
two different things depending on who drove:

- ``edge_groundedness``, ``citation_resolution``, ``refusal_accuracy``, ``verification_mix`` and
  ``injection_resistance`` are decided by the **gate and the corpus**, not by the trace. A script cannot
  make an ungrounded claim pass, because ``ToolResult.proposals`` is built from real artifact edges and
  the model never gets to invent one. These are real measurements under a scripted provider.
- ``traversal_recall``, ``traversal_precision`` and ``plan_adherence`` are decided by the **trace**. A
  script that names the right tool reaches the right nodes and executes the steps it planned, so on a
  scripted run these are a statement about the trace policy. They are computed anyway — a drop below the
  recorded value means the artifact moved under the dataset, which is worth catching — but they are
  marked ``SCRIPT_DETERMINED`` and ``report.py`` refuses to render them unmarked.

That distinction is the honest half of "tier 1 runs on every commit at $0". The every-commit gate
measures the machinery. The model's traversal is step 4 and it costs money.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from musical_mycelium.agent.claims import Claim
from musical_mycelium.agent.llm import LLM, Usage
from musical_mycelium.eval import runner
from musical_mycelium.eval.budget import BudgetExceeded, EvalBudget
from musical_mycelium.eval.metrics import (
    Groundedness,
    InjectionResistance,
    PlanAdherence,
    Rate,
    RefusalAccuracy,
    citation_resolution,
    edge_groundedness,
    injection_resistance,
    plan_adherence,
    refusal_accuracy,
    traversal_precision,
    traversal_recall,
    verification_mix,
)
from musical_mycelium.eval.slices import (
    SliceReport,
    density_slice,
    era_slice,
    query_kind_slice,
    region_slice,
    slice_rates,
)
from musical_mycelium.graph.schema import Node
from musical_mycelium.graph.store import GraphStore

#: The provider name a ``ScriptedLLM`` run reports. Matches ``build_llm``'s vocabulary so a result file
#: and a config string spell the same thing.
PROVIDER_SCRIPTED = "scripted"

#: Metrics whose value is decided by the trace rather than by the model or the corpus. **On a scripted
#: run these are not measurements of behaviour**, and anything that renders them has to say so.
#:
#: Named as a constant rather than a comment because ``report.py`` reads it and refuses to print an
#: unmarked scripted number. A caveat in a docstring is a caveat that gets quoted without.
SCRIPT_DETERMINED = ("traversal_recall", "traversal_precision", "plan_adherence")


@dataclass(frozen=True, slots=True)
class EvalCase:
    """One case, in the shape the suite scores and no dataset's shape in particular.

    ``subject_id`` may be ``None``: the adversarial absent-genre cases have no node, and that is the
    structural guarantee showing up as data rather than a gap. The node-shaped slices bucket it as
    ``unknown`` rather than dropping the row.
    """

    case_id: str
    query: str
    subject_id: str | None
    expected_refusal: bool
    expected_path: tuple[str, ...] = ()
    #: Triples an injection was trying to induce. Empty on any dataset that plants none, which makes the
    #: case **unscored** for injection resistance rather than a free pass.
    forbidden_triples: tuple[tuple[str, str, str], ...] = ()


@dataclass(frozen=True, slots=True)
class CaseResult:
    """One case's run and the per-case scores read off it.

    Per-case scores are kept alongside the aggregate because slicing needs a per-case verdict, and a
    suite that only stores aggregates has to re-drive the run to answer "which cases failed".
    """

    case: EvalCase
    run: runner.CaseRun
    #: The subject node when it resolved. ``None`` is a real answer, not a missing value.
    subject: Node | None
    groundedness: Groundedness
    recall: Rate
    precision: Rate
    adherence: PlanAdherence

    @property
    def refusal_correct(self) -> bool:
        return self.run.refused == self.case.expected_refusal

    @property
    def fully_grounded(self) -> bool:
        """A refusing case asserts nothing, so it is vacuously grounded — and ``Groundedness`` correctly
        calls that *undefined* rather than perfect. Treating undefined as grounded here is right only
        because ``refusal_correct`` is checked beside it: a case that should have answered and instead
        said nothing fails on that half, not this one."""
        return self.groundedness.score is None or self.groundedness.is_fully_grounded

    @property
    def correct(self) -> bool:
        """The single per-case verdict the slices are cut on.

        One metric across four dimensions rather than four across four, for the reason
        ``harness.slice_by_dimensions`` gives: sixteen numbers and no comparison. Refusal correctness and
        groundedness together, because either alone has a degenerate way to score well — a system that
        refuses everything is perfectly grounded, and a system that answers everything gets every refusal
        expectation wrong.
        """
        return self.refusal_correct and self.fully_grounded


#: How many cases may fail before the run stops anyway. A case-local bug costs one case; a systemic
#: failure — expired credentials, a provider outage — would otherwise burn every remaining case to
#: record the same error N times. Five is generous enough that a couple of flaky cases do not end a
#: run and tight enough that a broken configuration is not paid for forty times.
MAX_CASE_ERRORS = 5


@dataclass(frozen=True, slots=True)
class CaseError:
    """One case that raised. Recorded and stepped over, rather than ending the run.

    **Added 2026-08-23, after a run died at case 33 of 41.** ``adv_008`` approved two claims forming a
    shape ``synthesize`` could not narrate, raised ``ValueError``, and took the eight cases after it
    down with it — cases that were affordable, unaffected, and already paid for by the time the
    exception was raised.

    The distinction this draws is the one the previous design missed. On ``BudgetExceeded`` stopping is
    right: everything after is unaffordable, so the missing subset is *the tail*, and a number computed
    over it is a number computed over a non-random sample. A case-local bug is not that. The cases after
    it are unaffected, and dropping them buys nothing.

    Nothing is swallowed. The error and its type ride in the result file, ``complete`` is ``False``, and
    the gates refuse to run — the same treatment a budget abort gets. What changes is only how much
    survives.
    """

    case_id: str
    error_type: str
    message: str

    def to_json(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "error_type": self.error_type,
            "message": self.message,
        }


@dataclass(frozen=True, slots=True)
class SuiteResult:
    """One run of one dataset through one provider, with everything needed to read it later.

    ``complete`` is the field to check before quoting anything. A budget-aborted run still writes its
    results — a truncated run that reports itself as truncated is usable, one that looks complete is
    poison (``budget.py``) — so a consumer that ignores this field will average a partial set.
    """

    dataset: str
    dataset_version: str
    provider: str
    model_id: str
    artifact_version: str
    #: The pin the dataset was authored against. **Compared, not assumed**: a dataset pinned to 0.5.0
    #: scored against 0.6.0 is a silently invalidated benchmark, which is the failure `.claude/rules/
    #: evals.md` names when it says evals run against a pinned artifact version.
    artifact_pin: str
    results: tuple[CaseResult, ...]
    groundedness: Groundedness
    citation: Rate
    refusal: RefusalAccuracy
    injection: InjectionResistance
    verification: Mapping[str, int]
    recall: Rate
    precision: Rate
    usage: Usage
    slices: tuple[SliceReport, ...] = ()
    complete: bool = True
    #: Why it stopped early. Empty on a complete run.
    aborted_reason: str = ""
    script_determined: tuple[str, ...] = ()
    #: Cases that raised and were stepped over. Non-empty means ``complete`` is ``False``.
    errors: tuple[CaseError, ...] = ()

    @property
    def artifact_matches_pin(self) -> bool:
        return self.artifact_version == self.artifact_pin

    @property
    def cases_run(self) -> int:
        return len(self.results)

    @property
    def cases_correct(self) -> int:
        return sum(1 for result in self.results if result.correct)

    @property
    def truncated_runs(self) -> tuple[str, ...]:
        """Cases whose traversal hit a turn or token ceiling. Reported rather than averaged in: a
        truncated answer may have stopped one tool call short of the edge that mattered."""
        return tuple(r.case.case_id for r in self.results if r.run.truncated)

    def to_json(self) -> dict[str, Any]:
        return {
            "dataset": self.dataset,
            "dataset_version": self.dataset_version,
            "provider": self.provider,
            "model_id": self.model_id,
            "artifact_version": self.artifact_version,
            "artifact_pin": self.artifact_pin,
            "artifact_matches_pin": self.artifact_matches_pin,
            "complete": self.complete,
            "aborted_reason": self.aborted_reason,
            "errored_cases": [error.to_json() for error in self.errors],
            "script_determined": list(self.script_determined),
            "cases_run": self.cases_run,
            "cases_correct": self.cases_correct,
            "truncated_runs": list(self.truncated_runs),
            "edge_groundedness": self.groundedness.score,
            "citation_resolution": self.citation.score,
            "refusal_accuracy": {
                "true_refusals": self.refusal.true_refusals,
                "false_refusals": self.refusal.false_refusals,
                "missed_refusals": self.refusal.missed_refusals,
                "correct_answers": self.refusal.correct_answers,
                "expected_refusals": self.refusal.expected_refusals,
                "expected_answers": self.refusal.expected_answers,
            },
            "injection_resistance": {
                "induced": self.injection.induced,
                "scored_cases": self.injection.scored_cases,
                "unscored_cases": self.injection.unscored_cases,
                "holds": self.injection.holds,
            },
            "verification_mix": dict(self.verification),
            "traversal_recall": self.recall.score,
            "traversal_precision": self.precision.score,
            "usage": {
                "input_tokens": self.usage.input_tokens,
                "output_tokens": self.usage.output_tokens,
                "total_tokens": self.usage.total_tokens,
            },
            "per_case": [
                {
                    "case_id": r.case.case_id,
                    "refused": r.run.refused,
                    "expected_refusal": r.case.expected_refusal,
                    "refusal_correct": r.refusal_correct,
                    "approved_claims": len(r.run.approved),
                    "rejected_claims": len(r.run.rejections),
                    "groundedness": r.groundedness.score,
                    "traversal_recall": r.recall.score,
                    "traversal_precision": r.precision.score,
                    "plan_divergence": r.adherence.divergence,
                    "truncated": r.run.truncated,
                    "correct": r.correct,
                }
                for r in self.results
            ],
            "slices": {
                report.dimension: {
                    name: {"numerator": rate.numerator, "denominator": rate.denominator}
                    for name, rate in report.rates.items()
                }
                for report in self.slices
            },
        }


def score_case(case: EvalCase, run: runner.CaseRun, store: GraphStore) -> CaseResult:
    """Score one run. Pure — no driving, no I/O — so the scoring is testable on a synthetic ``CaseRun``.

    ``traversal_recall`` reads ``run.visited`` against ``case.expected_path``, and both are **sets**.
    ``PathWalked.node_ids`` is visit order rather than descent order, and scoring order would penalise a
    traversal that resolved both endpoints before tracing between them — which is the correct behaviour
    for a lineage query, not a mistake to punish.
    """
    return CaseResult(
        case=case,
        run=run,
        subject=store.get_node(case.subject_id) if case.subject_id else None,
        groundedness=edge_groundedness(list(run.approved), store),
        recall=traversal_recall(run.visited, case.expected_path),
        precision=traversal_precision(run.visited, case.expected_path),
        adherence=plan_adherence(run.done),
    )


def run_suite(
    cases: Sequence[EvalCase],
    *,
    store: GraphStore,
    llm_for: Callable[[EvalCase], LLM],
    dataset: str,
    dataset_version: str,
    artifact_pin: str,
    provider: str = PROVIDER_SCRIPTED,
    budget: EvalBudget | None = None,
    synthesis_llm_for: Callable[[EvalCase], LLM] | None = None,
) -> SuiteResult:
    """Drive every case, score it, and aggregate. Returns a result even when it aborts.

    ``llm_for`` is the provider seam and the reason this function needs no ``if provider ==`` anywhere.
    A scripted caller returns a fresh ``ScriptedLLM`` per case (a script is consumed as it runs, so one
    instance cannot serve two cases); a Bedrock caller returns the same client every time. Neither shape
    is privileged here.

    **On ``BudgetExceeded`` the run stops and returns what it has, marked ``complete=False``.** It does
    not skip the case and continue: a run that drops the cases it could not afford reports a number
    computed over a subset chosen by exhaustion, and that subset is not random — it is the tail.

    **The same is true of any provider failure, and that was a real loss before 2026-08-17.** Only
    ``BudgetExceeded`` was caught here, so a ``ThrottlingException`` on case 41 of 41 propagated past
    the writer and **destroyed forty completed cases** — no file, no recorded usage, seventeen minutes
    and a real bill for nothing. A billable run's cases are expensive and non-reproducible; the one
    thing this function must never do is throw them away.

    **Amended 2026-08-23: a failing case is now stepped over rather than ending the run.** The 8/17 fix
    caught the exception but kept the budget's *response* to it — stop and return what exists — and on
    2026-08-23 that cost eight cases. ``adv_008`` raised a ``ValueError`` from ``synthesize`` at case 33
    of 41 and the remaining eight died with it, though they were affordable, unaffected, and about to
    run.

    The two situations are not alike and this is the line between them:

    - **``BudgetExceeded`` stops the run.** Everything after is unaffordable, so the cases that go
      missing are *the tail* — a subset chosen by exhaustion, which is not a random sample.
    - **A case that raises is recorded and skipped.** The cases after it are unaffected. Dropping them
      buys no honesty and loses real, already-paid-for evidence.

    **Nothing is swallowed either way.** An errored case rides in the result file with its type and
    message, ``complete`` is ``False``, and ``render`` refuses to gate — exactly the treatment a budget
    abort gets. ``noise.py`` already refuses to pool an incomplete run, so a partial result still cannot
    become a sample in a noise floor.

    **``MAX_CASE_ERRORS`` is the guard against the other failure.** A systemic fault — expired
    credentials, a provider outage — would otherwise record the same error once per remaining case.
    After five, the run stops and says so.
    """
    results: list[CaseResult] = []
    errors: list[CaseError] = []
    usage = Usage()
    complete = True
    aborted_reason = ""

    for position, case in enumerate(cases, start=1):
        try:
            if budget is not None:
                budget.check()
            run = runner.run_case(
                case.query,
                store=store,
                llm=llm_for(case),
                synthesis_llm=synthesis_llm_for(case) if synthesis_llm_for else None,
            )
        except BudgetExceeded as exceeded:
            complete = False
            aborted_reason = str(exceeded)
            break
        except Exception as failure:
            # The case id matters more than the traceback here. A throttle at case 41 and a throttle
            # at case 3 are different situations, and the recorded error is the only place a reader of
            # the result file can tell them apart.
            complete = False
            errors.append(
                CaseError(
                    case_id=case.case_id,
                    error_type=type(failure).__name__,
                    message=str(failure),
                )
            )
            if len(errors) >= MAX_CASE_ERRORS:
                aborted_reason = (
                    f"stopped after {len(errors)} failing cases (last: {type(failure).__name__} on "
                    f"{case.case_id}, case {position} of {len(cases)}). That many failures is a "
                    "systemic fault rather than a case-local bug, and the rest of the run would only "
                    "record it again."
                )
                break
            continue

        case_usage = run.traversal_usage + run.synthesis_usage
        usage = usage + case_usage
        if budget is not None:
            budget.charge(case_usage)
        results.append(score_case(case, run, store))

    return _aggregate(
        results,
        store=store,
        dataset=dataset,
        dataset_version=dataset_version,
        artifact_pin=artifact_pin,
        provider=provider,
        usage=usage,
        complete=complete,
        aborted_reason=aborted_reason,
        errors=tuple(errors),
    )


def _aggregate(
    results: Sequence[CaseResult],
    *,
    store: GraphStore,
    dataset: str,
    dataset_version: str,
    artifact_pin: str,
    provider: str,
    usage: Usage,
    complete: bool,
    aborted_reason: str,
    errors: tuple[CaseError, ...] = (),
) -> SuiteResult:
    """Roll per-case results into the catalog.

    Recall and precision are **micro-averaged** — numerators and denominators summed across cases, not
    per-case rates averaged. A macro average weights a two-node case the same as a seven-node one and
    lets ``Rate``'s undefined cases turn into an arbitrary skip; summing keeps the denominator readable
    as "nodes the dataset expected" and keeps the zero-denominator rule in one place.
    """
    all_claims: list[Claim] = [claim for result in results for claim in result.run.approved]

    recall_hits = sum(r.recall.numerator for r in results)
    recall_total = sum(r.recall.denominator for r in results)
    precision_hits = sum(r.precision.numerator for r in results)
    precision_total = sum(r.precision.denominator for r in results)

    return SuiteResult(
        dataset=dataset,
        dataset_version=dataset_version,
        provider=provider,
        model_id=results[0].run.done.model_id if results else "none",
        artifact_version=store.artifact_version,
        artifact_pin=artifact_pin,
        results=tuple(results),
        groundedness=edge_groundedness(all_claims, store),
        citation=citation_resolution(all_claims, store),
        refusal=refusal_accuracy((r.case.expected_refusal, r.run.refused) for r in results),
        injection=injection_resistance((r.run.approved, r.case.forbidden_triples) for r in results),
        verification=verification_mix(all_claims),
        recall=Rate(numerator=recall_hits, denominator=recall_total),
        precision=Rate(numerator=precision_hits, denominator=precision_total),
        usage=usage,
        slices=slice_by_dimensions(results, store),
        complete=complete,
        aborted_reason=aborted_reason,
        script_determined=SCRIPT_DETERMINED if provider == PROVIDER_SCRIPTED else (),
        errors=errors,
    )


def slice_by_dimensions(
    results: Sequence[CaseResult], store: GraphStore
) -> tuple[SliceReport, ...]:
    """``CaseResult.correct``, cut four ways. The metric being sliced is deliberately the same one."""

    def correct(result: CaseResult) -> bool:
        return result.correct

    return (
        slice_rates("era", results, lambda r: era_slice(r.subject), correct),
        slice_rates("region", results, lambda r: region_slice(r.subject), correct),
        slice_rates("density", results, lambda r: density_slice(r.subject, store), correct),
        slice_rates(
            "query_kind", results, lambda r: query_kind_slice(r.run.plan.query_kind), correct
        ),
    )


# --- the gold suite, wired ---------------------------------------------------------------------------


def run_gold_suite(
    store: GraphStore,
    *,
    llm_for: Callable[[EvalCase], LLM] | None = None,
    provider: str = PROVIDER_SCRIPTED,
    budget: EvalBudget | None = None,
) -> SuiteResult:
    """The gold set through the suite. Scripted by default and therefore free.

    Imported locally rather than at module scope because ``gold`` imports ``EvalCase`` from here; the
    cycle is real and the local import is the smaller of the two fixes. The alternative — moving
    ``EvalCase`` into its own module — buys nothing but a third file.
    """
    from musical_mycelium.eval import gold

    cases = gold.load_cases()
    version, pin = gold.dataset_version()
    scripts = {case.case_id: gold.build_script(case) for case in cases}

    def scripted(case: EvalCase) -> LLM:
        from musical_mycelium.agent.llm import ScriptedLLM

        return ScriptedLLM(list(scripts[case.case_id]))

    return run_suite(
        gold.eval_cases(cases),
        store=store,
        llm_for=llm_for if llm_for is not None else scripted,
        dataset="gold",
        dataset_version=version,
        artifact_pin=pin,
        provider=provider,
        budget=budget,
    )


def main() -> int:
    """``make eval`` — the scripted tier 1 run, printed. $0, no AWS, no credentials.

    **This blocks as of phase 4 step 5.** It did not before, and the reason it did not is worth keeping:
    thresholds are not invented before a baseline exists, so until `eval/thresholds.json` was written
    from a measured noise floor there was nothing to block *on* and a non-zero exit would either have
    been arbitrary or would have quietly become the threshold nobody chose.

    What it can block on for free is narrower than the five correctness properties, and the report says
    so rather than rounding it off: traversal recall is ``SCRIPT_DETERMINED`` here and the gold-only run
    plants no injections, so both render ``N/A``. Three gates are real — groundedness, citation
    resolution and refusal accuracy are decided by the deterministic gate against the pinned artifact,
    not by the script. A missing threshold file still exits 0 behind a ``NOT GATED`` banner.

    The two conditions that *are* structural rather than numeric — an artifact that does not match the
    dataset's pin, and an incomplete run — are surfaced by ``render`` at the top of the report.
    """
    from musical_mycelium.eval.report import render
    from musical_mycelium.eval.thresholds import gate
    from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory

    store = InMemoryGraphStore.from_directory(artifact_directory())
    result = run_gold_suite(store)
    outcome = gate(result)
    print(render(result, outcome))
    return outcome.exit_code


if __name__ == "__main__":
    raise SystemExit(main())
