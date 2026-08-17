"""The spend gate. One chokepoint every billable eval path routes through.

Ported from Patchwork, where it exists because of a real incident on 2026-06-23: a run intended to
*verify that the paid tier skipped gracefully* took the paid path instead, because the skip keyed on
a provider env var that the local `.env` had set to the paid provider. It billed for about a minute
before it was killed. The loss was small; the lesson was not, and it is the reason this module is
three independent layers rather than one prompt:

1. **A hard cap, checked before anything is printed.** No answer at the prompt can approve a run
   larger than the cap. A prompt alone is a single point of failure — it protects against *intent*
   and not at all against a loop that miscounted its own dataset.
2. **Refuse when unattended.** A non-TTY stdin — piped, redirected, backgrounded, CI — is refused
   outright rather than defaulted either way. **This is the exact shape of the original incident**,
   and it is why there is no `--yes` flag and no environment-variable bypass anywhere in this file:
   every escape hatch that would make an unattended run possible is the thing that went wrong.
3. **A typed confirmation**, shown alongside the estimate. `y` is not accepted; the whole word is.

**The prompt happens exactly once, before the first billable call, and never again.** A run that
stops to ask something twenty minutes in is a run he cannot walk away from, and being told he can
walk away and then finding it parked on a prompt is worse than being told to watch it. Per-case or
per-batch confirmation is therefore forbidden here, not merely discouraged. Everything downstream —
`EvalBudget`, the rate limiter, partial results marked `complete: false` — exists so the run can
survive unattended once this gate has been passed.

**Corollary, and it is an operating rule rather than a code property: token-spending commands are
human-run, like `git`.** The assistant provides the command; he runs it in his own terminal. Layer 2
enforces the technical half of that (an agent-launched background run has no TTY and is refused);
the rule covers the half no code can.

**No price is hardcoded here.** Dollars appear only when `MYCELIUM_TOKEN_PRICES` supplies a rate for
the exact model id, reusing `api.telemetry`'s parser rather than a second copy of the rule. With no
price configured the estimate still renders — in requests and tokens, which are facts about a quota
and need no vendor price to be true. A wrong price does not fail loudly; it produces a plausible
number that gets believed, which is why absence is the correct default rather than a fallback rate.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import TextIO

from musical_mycelium.agent.llm import Usage
from musical_mycelium.api.telemetry import Price, load_prices
from musical_mycelium.eval.budget import EVAL_REQUESTS_PER_MINUTE

#: What must be typed. **Not** `y` — a single keystroke is the one most likely to be hit by reflex
#: or left in a terminal's scrollback, and the whole point of this gate is that approving costs a
#: deliberate act.
CONFIRMATION_WORD = "yes"

#: The runaway circuit breaker: the largest case count any single billable run may attempt, whatever
#: the caller passes and whatever is typed at the prompt. Sized as roughly double the largest real
#: dataset (25 gold + 16 adversarial + 10 held-out = 51), so it never obstructs an honest run and
#: still stops a loop that has miscounted. **Not a budget** — `EvalBudget` counts tokens, this counts
#: cases, and the incident this file exists for was a path that spent without either.
MAX_CASES_PER_RUN = 120


class SpendRefused(RuntimeError):
    """He was asked and declined. An ordinary outcome, not an error in the pejorative sense — but it
    is raised rather than returned so a caller cannot spend by forgetting to check a boolean."""


class UnattendedSpend(RuntimeError):
    """A billable run was attempted with no interactive terminal to confirm it.

    Refused rather than defaulted in either direction. Defaulting to *yes* is the original incident;
    defaulting to *no* would be safe but silent, and a silent skip in CI reads as a passing suite
    that measured nothing.
    """


class SpendCapExceeded(RuntimeError):
    """The run asked for more cases than the hard cap allows. Raised **before** the prompt, so no
    answer can approve it."""


@dataclass(frozen=True, slots=True)
class SpendEstimate:
    """What a run expects to cost, in the units a quota is actually denominated in.

    Every field is a **prediction**, and the prompt says so. The measured figures come from `Done`
    afterwards and are what get recorded; nothing here is written to a result file.
    """

    #: What is about to run, in his words rather than a module path — "gold + adversarial, Haiku 4.5".
    description: str
    cases: int
    requests: int
    input_tokens: int
    output_tokens: int
    model_id: str

    @property
    def usage(self) -> Usage:
        return Usage(input_tokens=self.input_tokens, output_tokens=self.output_tokens)

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def estimated_usd(self, prices: dict[str, Price] | None = None) -> float | None:
        """Dollars, or ``None`` when no price is configured for **this exact model id**.

        Never approximated from a similar model and never defaulted, for the reason
        `api/telemetry.py` gives about its own cost record: a figure that is sometimes real and
        sometimes invented is worse than one that is sometimes absent.
        """
        table = load_prices() if prices is None else prices
        price = table.get(self.model_id)
        if price is None:
            return None
        return price.usd_for(self.usage)

    def render(self) -> str:
        lines = [
            "About to spend real money on Bedrock.",
            "",
            f"  what      {self.description}",
            f"  model     {self.model_id}",
            f"  cases     {self.cases}",
            f"  requests  ~{self.requests}",
            f"  tokens    ~{self.total_tokens} (in ~{self.input_tokens}, out ~{self.output_tokens})",
        ]
        usd = self.estimated_usd()
        if usd is None:
            lines.append(
                "  cost      not shown: no price configured for this model in MYCELIUM_TOKEN_PRICES"
            )
        else:
            lines.append(f"  cost      ~${usd:.2f} at the configured price")
        lines += [
            "",
            "These are ESTIMATES. Actual usage is measured from the run and recorded afterwards.",
            f"At {EVAL_REQUESTS_PER_MINUTE} requests/minute this run takes roughly "
            f"{max(1, round(self.requests / EVAL_REQUESTS_PER_MINUTE))}"
            " minutes and cannot be paused.",
        ]
        return "\n".join(lines)


def confirm_spend(
    estimate: SpendEstimate,
    *,
    max_cases: int = MAX_CASES_PER_RUN,
    stdin: TextIO | None = None,
    stdout: TextIO | None = None,
) -> None:
    """Gate one billable run. Returns ``None`` on approval; raises on everything else.

    Returning nothing rather than ``True`` is deliberate: there is no falsy value to ignore, so a
    caller that forgets to handle the outcome cannot proceed to spend anyway.

    ``stdin`` and ``stdout`` are injected so the tests can drive every branch without a terminal —
    and note that injecting a non-TTY stream is exactly what layer 2 refuses, so the tests must fake
    ``isatty`` explicitly rather than getting a pass for being tests.
    """
    out = stdout if stdout is not None else sys.stdout
    source = stdin if stdin is not None else sys.stdin

    # Layer 1, and it runs first on purpose: a cap that can be talked past at a prompt is not a cap.
    if estimate.cases > max_cases:
        raise SpendCapExceeded(
            f"{estimate.cases} cases exceeds the hard cap of {max_cases}; "
            "this is a runaway guard and no confirmation overrides it"
        )
    if estimate.cases <= 0:
        raise SpendCapExceeded("a run of zero cases has nothing to approve")

    # Layer 2. `isatty` may be absent on a substitute stream; absent is treated as not-a-terminal,
    # because the safe reading of "I cannot tell whether anyone is watching" is that nobody is.
    if not getattr(source, "isatty", lambda: False)():
        raise UnattendedSpend(
            "refusing to spend without an interactive terminal to confirm it. "
            "Run this yourself in a real shell; there is deliberately no --yes flag and no "
            "environment variable that bypasses this."
        )

    print(estimate.render(), file=out)
    print(f"\nType {CONFIRMATION_WORD!r} to proceed, anything else to abort: ", end="", file=out)
    out.flush()

    answer = source.readline()
    # An empty string is EOF rather than an empty line — the stream closed underneath us, which is
    # not an answer and must not read as one.
    if not answer:
        raise SpendRefused("stdin closed before an answer was given; nothing was spent")

    if answer.strip().casefold() != CONFIRMATION_WORD:
        raise SpendRefused("not confirmed; nothing was spent")
