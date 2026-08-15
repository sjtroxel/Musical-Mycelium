"""Throttling and spend limits for eval runs. Three axes bind, and they need three mechanisms.

Measured against this account on 2026-08-11 and 2026-08-12, recorded in `.claude/rules/aws-and-cost.md`:

1. **10 requests/minute is the binding constraint**, not the 5M tokens/minute. One case is a plan turn,
   one turn per hop, then synthesis — call it six requests — so 25 gold cases is roughly 150 requests and
   roughly fifteen minutes at the cap. That is the floor of a run, not a problem to engineer around, and
   more context budget does not help. `RateLimiter` is the answer.
2. **Concurrency 2**, per `planning/07` §315. It hides latency and cannot buy throughput, because the
   limiter is global. Above 2 it only makes backoff noisier.
3. **27,000,000 tokens per day** on Haiku 4.5, and this is the one that actually hurts. TPM recovers in
   sixty seconds; a blown daily cap locks the model out for the rest of the calendar day, which on a
   Saturday afternoon means the run is over. Per-request backoff cannot see this coming, because no
   single request is too large — the run as a whole is. `EvalBudget` is the answer.

**The budget aborts; it does not skip.** A run that quietly drops the cases it could not afford reports
a number computed over a subset it chose by exhaustion, which is the worst kind of wrong: it looks like a
complete result. Raising `BudgetExceeded` forces the caller to write partial results marked as partial.

**No dollar figure appears here.** Prices live in `MYCELIUM_TOKEN_PRICES` at runtime and cost is measured
from recorded usage, never estimated in code. This module counts tokens and requests, which are facts
about a quota, and says nothing about money.
"""

from __future__ import annotations

import random
import time
from collections import deque
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field

from musical_mycelium.agent.llm import Usage

#: The measured limits for Haiku 4.5 on this account. Defaults, not truths — a different model has
#: different numbers, and a caller running the judge on Nova Pro (2M TPM / 25 RPM) must pass its own.
HAIKU_REQUESTS_PER_MINUTE = 10
HAIKU_TOKENS_PER_DAY = 27_000_000

#: Concurrency for a fan-out run. `planning/07` §315, now a measured requirement rather than a precaution.
MAX_CONCURRENCY = 2


class BudgetExceeded(RuntimeError):
    """The run asked for more than it was allotted. Carries what was spent, so the caller can record it.

    Raised **before** the offending call is made, not after, so the recorded spend is what was actually
    billed rather than what was attempted.
    """

    def __init__(self, message: str, *, spent_tokens: int, spent_requests: int) -> None:
        super().__init__(message)
        self.spent_tokens = spent_tokens
        self.spent_requests = spent_requests


@dataclass(slots=True)
class EvalBudget:
    """A cumulative allowance for one run. Mutable on purpose — it is a running total, not a value.

    Both limits are **required**. There is no default, and that is deliberate: `.claude/rules/evals.md`
    says not to invent thresholds before a baseline exists, and a default budget is an invented threshold
    wearing a helpful hat. The first real run measures a per-run figure; until then every caller states
    what it is willing to spend.
    """

    max_tokens: int
    max_requests: int
    spent_tokens: int = 0
    spent_requests: int = 0

    def __post_init__(self) -> None:
        if self.max_tokens <= 0 or self.max_requests <= 0:
            raise ValueError("a budget of zero cannot run anything; pass a positive allowance")

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self.spent_tokens)

    @property
    def remaining_requests(self) -> int:
        return max(0, self.max_requests - self.spent_requests)

    @property
    def exhausted(self) -> bool:
        return self.remaining_tokens == 0 or self.remaining_requests == 0

    def check(self, *, estimated_tokens: int = 0) -> None:
        """Assert there is room for one more call. Raises rather than returning a verdict.

        ``estimated_tokens`` lets a caller that knows roughly how large the next case is refuse to start
        it. Zero — the default — checks only that the budget is not already spent, which is the honest
        position when the size is unknown.
        """
        if self.remaining_requests <= 0:
            raise BudgetExceeded(
                f"request budget exhausted after {self.spent_requests} requests",
                spent_tokens=self.spent_tokens,
                spent_requests=self.spent_requests,
            )
        if self.remaining_tokens <= 0 or estimated_tokens > self.remaining_tokens:
            raise BudgetExceeded(
                f"token budget exhausted after {self.spent_tokens} tokens"
                f" (needed {estimated_tokens}, {self.remaining_tokens} left)",
                spent_tokens=self.spent_tokens,
                spent_requests=self.spent_requests,
            )

    def charge(self, usage: Usage, *, requests: int = 1) -> None:
        """Record what a call actually cost. Always called, including when the call then fails a check.

        Spend is recorded from **real** usage rather than an estimate, because that is the whole reason
        `Done` carries `Usage` at all. Charging past the limit is allowed and is not an error — the limit
        is enforced at ``check`` time, before the next call, and pretending a billed token was not billed
        would make the recorded spend a lie.
        """
        self.spent_tokens += usage.total_tokens
        self.spent_requests += requests


@dataclass(slots=True)
class RateLimiter:
    """A global token bucket over a sliding window. Not per-worker — the quota is per account.

    A per-worker limiter is the obvious mistake here and it is invisible in testing: two workers each
    politely limited to 10 RPM issue 20 RPM together and the quota does not care which one asked. So one
    instance is shared by every worker, and ``acquire`` is the only way through.

    ``clock`` and ``sleep`` are injected so the tests do not have to wait a real minute to prove a real
    minute is waited.
    """

    requests_per_minute: int = HAIKU_REQUESTS_PER_MINUTE
    window_seconds: float = 60.0
    clock: Callable[[], float] = time.monotonic
    sleep: Callable[[float], None] = time.sleep
    _recent: deque[float] = field(default_factory=deque, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.requests_per_minute <= 0:
            raise ValueError("a rate limit of zero permits nothing; pass a positive rate")

    def acquire(self) -> None:
        """Block until one more request is permitted, then record it."""
        while True:
            now = self.clock()
            cutoff = now - self.window_seconds
            while self._recent and self._recent[0] <= cutoff:
                self._recent.popleft()
            if len(self._recent) < self.requests_per_minute:
                self._recent.append(now)
                return
            self.sleep(max(0.0, self._recent[0] + self.window_seconds - now))


def backoff_delays(
    attempts: int,
    *,
    base_seconds: float = 1.0,
    cap_seconds: float = 60.0,
    jitter: Callable[[], float] = random.random,
) -> Iterator[float]:
    """Exponential backoff with full jitter, capped. Yields one delay per retry.

    Full jitter rather than a fixed multiple: several workers that back off by exactly the same amount
    retry in lockstep and rebuild the burst that caused the throttle. Yields ``attempts - 1`` delays,
    because the first try is not a retry.
    """
    for attempt in range(max(0, attempts - 1)):
        yield min(cap_seconds, base_seconds * (2**attempt)) * jitter()


def call_with_retries[T](
    call: Callable[[], T],
    *,
    is_retryable: Callable[[Exception], bool],
    attempts: int = 5,
    sleep: Callable[[float], None] = time.sleep,
    jitter: Callable[[], float] = random.random,
) -> T:
    """Run ``call``, retrying retryable failures with backoff. Re-raises anything else immediately.

    ``is_retryable`` is a parameter rather than a hardcoded exception list because this module must not
    import boto3 — `api/telemetry.py` set that precedent for the same reason, and the eval package has no
    business knowing what a Bedrock throttling exception is called. The caller that builds the client
    knows; this does not.

    **A `BudgetExceeded` is never retried**, whatever ``is_retryable`` says. Retrying an exhausted budget
    is how a guard becomes a formality.
    """
    delays = list(backoff_delays(attempts, jitter=jitter))
    last: Exception | None = None
    for index in range(max(1, attempts)):
        try:
            return call()
        except BudgetExceeded:
            raise
        except Exception as error:
            if not is_retryable(error):
                raise
            last = error
            if index < len(delays):
                sleep(delays[index])
    assert last is not None
    raise last
