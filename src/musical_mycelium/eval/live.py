"""The billable run: real model, both datasets, one suite, one confirmation.

Everything here exists because a *real* provider has properties a `ScriptedLLM` does not — a quota,
a latency, a bill — and none of them belong in `suite.py`, which must stay provider-agnostic. The
suite takes an `llm_for` callable; this module is what that callable returns and what wraps it.

**Why there is no `call_with_retries` in this file, despite `budget.py` providing one.**
`BedrockLLM` already builds its boto3 client with `Config(retries={"max_attempts": 8, "mode":
"adaptive"})`, and adaptive mode is not just retries — it adds a client-side rate limiter that slows
down when it sees throttling. Wrapping that in a second retry layer would give 8 x N worst-case
attempts and two independent backoffs fighting each other, and the failure would show up as a run
that takes an unexplained hour. So the division is: **botocore handles throttling reactively, and
`RateLimiter` here paces proactively so throttling is rare in the first place.** `call_with_retries`
stays available for the judge in step 7, which talks to a different model on a different quota.

**The rate limiter has to sit at the request boundary, not the case boundary.** One case is five to
seven requests, so a limiter acquired once per case would let a single case burst past 10 RPM on its
own. `ThrottledLLM` therefore wraps the `LLM` seam itself — every `converse` and every `stream`
passes through `acquire()`, and neither the loop nor the suite learns that throttling exists.
"""

from __future__ import annotations

import json
import sys
from collections.abc import Callable, Generator, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from musical_mycelium.agent.llm import DEFAULT_MAX_TOKENS, LLM, Usage, build_llm
from musical_mycelium.eval import gold, harness
from musical_mycelium.eval.budget import HAIKU_REQUESTS_PER_MINUTE, EvalBudget, RateLimiter
from musical_mycelium.eval.report import render
from musical_mycelium.eval.safety import (
    SpendCapExceeded,
    SpendEstimate,
    SpendRefused,
    UnattendedSpend,
    confirm_spend,
)
from musical_mycelium.eval.suite import EvalCase, SuiteResult, run_suite
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.store import GraphStore

RESULTS_DIR = Path(__file__).parent / "results"

#: Measured from the scripted run on 2026-08-16, then scaled for a real model taking five to six
#: tool turns rather than the scripted two. **Estimates for the confirmation prompt only** — nothing
#: here is ever written to a result file, where only measured usage belongs.
#:
#: The scripted floor was 179 requests and ~225k input tokens across 41 cases. These round that up
#: rather than down, because an estimate that under-states spend is the one that matters.
ESTIMATED_REQUESTS_PER_CASE = 7
ESTIMATED_INPUT_TOKENS_PER_CASE = 14_000
ESTIMATED_OUTPUT_TOKENS_PER_CASE = 1_100

#: Headroom over the estimate before `EvalBudget` aborts. Not a prediction — a circuit breaker for
#: the case where a real model loops far longer than the scripted trace suggests. 3x is wide enough
#: that an honest run never trips it and narrow enough that a runaway stops well inside the 27M/day
#: cap. **Deliberately not a default inside `budget.py`**, which requires callers to state a number.
BUDGET_SAFETY_FACTOR = 3


@dataclass(slots=True)
class ThrottledLLM:
    """An `LLM` that pauses before every request so a run stays under the account's RPM ceiling.

    Wraps the seam rather than living inside `BedrockLLM`, for two reasons: the limiter is a property
    of *a run* (shared across every case, and across both models when the judge lands) rather than of
    a client, and `agent/` must not grow eval concerns. `model_id` delegates so `Done` still records
    the real model rather than "throttled".
    """

    inner: LLM
    limiter: RateLimiter
    #: Bumped on every request that goes out. The suite counts tokens; nothing else counts requests,
    #: and requests are what the binding quota is denominated in.
    requests: int = 0

    @property
    def model_id(self) -> str:
        return self.inner.model_id

    def converse(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tool_config: dict[str, Any] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Any:
        self.limiter.acquire()
        self.requests += 1
        return self.inner.converse(
            messages, system=system, tool_config=tool_config, max_tokens=max_tokens
        )

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Generator[str, None, Usage]:
        """Acquired **before** the first delta, not after the stream is exhausted.

        A stream that has started is a request the quota has already counted, so pacing after the
        fact would let a run of long syntheses drift over the ceiling while looking compliant.
        """
        self.limiter.acquire()
        self.requests += 1
        return (yield from self.inner.stream(messages, system=system, max_tokens=max_tokens))


def live_cases() -> tuple[EvalCase, ...]:
    """Gold then adversarial, in that order.

    Order is not cosmetic: the gold set is what fails loudly if the wiring is wrong, so putting it
    first means a broken run burns the fewest requests before it becomes obvious.
    """
    return (*gold.eval_cases(), *harness.eval_cases())


def estimate_for(cases: Sequence[EvalCase], model_id: str, description: str) -> SpendEstimate:
    return SpendEstimate(
        description=description,
        cases=len(cases),
        requests=len(cases) * ESTIMATED_REQUESTS_PER_CASE,
        input_tokens=len(cases) * ESTIMATED_INPUT_TOKENS_PER_CASE,
        output_tokens=len(cases) * ESTIMATED_OUTPUT_TOKENS_PER_CASE,
        model_id=model_id,
    )


def budget_for(estimate: SpendEstimate) -> EvalBudget:
    """A circuit breaker sized from the estimate, since no measured per-run figure exists yet.

    `budget.py` refuses to carry a default on purpose — *"a default budget is an invented threshold
    wearing a helpful hat"* — so the number is stated here, at the call site, where the reasoning
    for it is visible and where step 4's measured figures will replace it.
    """
    return EvalBudget(
        max_tokens=estimate.total_tokens * BUDGET_SAFETY_FACTOR,
        max_requests=estimate.requests * BUDGET_SAFETY_FACTOR,
    )


def write_result(result: SuiteResult, *, directory: Path = RESULTS_DIR) -> Path:
    """Write one run to `results/<timestamp>-<provider>.json`. Per-run files, never overwritten.

    Phase 7 reads these to plot the trend, which is the whole reason they are not one rolling file:
    a single overwritten result has no history, and a benchmark with no history cannot show that a
    number moved.
    """
    directory.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    path = directory / f"{stamp}-{result.provider}.json"
    path.write_text(json.dumps(result.to_json(), indent=2) + "\n", encoding="utf-8")
    return path


def run_live(
    *,
    store: GraphStore | None = None,
    cases: Sequence[EvalCase] | None = None,
    provider: str = "bedrock",
    requests_per_minute: int = HAIKU_REQUESTS_PER_MINUTE,
    llm_factory: Callable[[], LLM] | None = None,
    limiter: RateLimiter | None = None,
    progress: Callable[[str], None] | None = None,
) -> SuiteResult:
    """Drive the real model. **Assumes `confirm_spend` has already passed** — see `main`.

    One `ThrottledLLM` instance is shared by every case, because the limiter and the request count
    are properties of the run. That is also why `llm_for` closes over it rather than building a new
    client per case: a per-case client would be a per-case limiter, which is no limiter at all.
    """
    graph = store if store is not None else InMemoryGraphStore.from_directory(artifact_directory())
    selected = tuple(cases) if cases is not None else live_cases()
    say = progress if progress is not None else (lambda line: None)

    build = llm_factory if llm_factory is not None else (lambda: build_llm(provider))
    pacer = limiter if limiter is not None else RateLimiter(requests_per_minute=requests_per_minute)
    throttled = ThrottledLLM(inner=build(), limiter=pacer)

    _, pin = gold.dataset_version()
    estimate = estimate_for(selected, throttled.model_id, "live run")
    budget = budget_for(estimate)

    done = 0

    def llm_for(case: EvalCase) -> LLM:
        nonlocal done
        done += 1
        say(f"[{done}/{len(selected)}] {case.case_id}: {case.query[:60]}")
        return throttled

    result = run_suite(
        selected,
        store=graph,
        llm_for=llm_for,
        dataset="live",
        dataset_version="gold+adversarial",
        artifact_pin=pin,
        provider=provider,
        budget=budget,
    )
    say(f"requests issued: {throttled.requests}; tokens: {result.usage.total_tokens}")
    return result


def main(argv: Sequence[str] | None = None) -> int:
    """`make eval-live`. Confirms once, then runs unattended.

    **The only interactive moment is `confirm_spend`.** After it returns, nothing reads stdin again —
    a run that stops to ask something twenty minutes in is a run he cannot walk away from, and the
    whole design downstream (budget abort writing partial results, progress to stdout, the limiter)
    exists so that leaving it alone is safe.

    `--cases N` runs a prefix of the set, for proving the wiring cheaply before committing to the
    full run. One case is a few cents and catches the failures that matter — a bad credential, a
    tool-turn shape the loop mishandles, a model that ignores the plan format.
    """
    args = list(sys.argv[1:] if argv is None else argv)
    limit: int | None = None
    if "--cases" in args:
        limit = int(args[args.index("--cases") + 1])

    selected = live_cases()
    if limit is not None:
        selected = selected[:limit]

    model_id = build_llm("bedrock").model_id
    label = f"{len(selected)} cases, tier 1, real model"

    # Declining is an ordinary outcome and must not look like a crash. A traceback here would read
    # as "the tool is broken" when what actually happened is "the guard did its job" — and the
    # unattended branch is the one an agent or a CI job hits, where a stack trace is pure noise.
    try:
        confirm_spend(estimate_for(selected, model_id, label))
    except UnattendedSpend as refusal:
        print(f"\nnot started: {refusal}", file=sys.stderr)
        return 2
    except SpendRefused:
        print("\nnot confirmed; nothing was spent.", file=sys.stderr)
        return 2
    except SpendCapExceeded as capped:
        print(f"\nrefused by the hard cap: {capped}", file=sys.stderr)
        return 2

    print("\nconfirmed; running. This is unattended from here.\n", flush=True)
    result = run_live(cases=selected, progress=lambda line: print(line, flush=True))

    path = write_result(result)
    print()
    print(render(result))
    print(f"\nwritten to {path}")
    if not result.complete:
        print(
            "\nRUN WAS INCOMPLETE — see aborted_reason above. Partial results were still written."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
