"""Budget and throttle tests.

Every lock in this file was broken deliberately once, watched to fail, and restored — the practice from
2026-08-14, and the counter to this repo's named failure mode of assertions written from a mental model
and never executed. A rate limiter that does not limit and a budget that does not stop are both green by
default, because the thing they guard against costs money to observe in production.
"""

from __future__ import annotations

import pytest

from musical_mycelium.agent.llm import Usage
from musical_mycelium.eval.budget import (
    EVAL_REQUESTS_PER_MINUTE,
    HAIKU_REQUESTS_PER_MINUTE,
    BudgetExceeded,
    EvalBudget,
    RateLimiter,
    backoff_delays,
    call_with_retries,
)


class FakeClock:
    """A monotonic clock that only moves when something sleeps. Makes 'a minute passed' a fact rather
    than a wait, and makes 'nothing slept' observable."""

    def __init__(self) -> None:
        self.now = 0.0
        self.slept: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.slept.append(seconds)
        self.now += seconds


# --- the cumulative budget ----------------------------------------------------------------------------


def test_a_budget_must_be_stated_and_cannot_be_zero() -> None:
    """No default allowance exists anywhere in this module. A default budget is an invented threshold,
    and `.claude/rules/evals.md` forbids inventing thresholds before a baseline exists."""
    with pytest.raises(ValueError):
        EvalBudget(max_tokens=0, max_requests=10)
    with pytest.raises(ValueError):
        EvalBudget(max_tokens=1000, max_requests=0)


def test_the_token_budget_stops_the_run_rather_than_skipping_cases() -> None:
    """The failure this exists to prevent: a run that quietly drops what it cannot afford and reports a
    number over a subset it chose by exhaustion. It must raise."""
    budget = EvalBudget(max_tokens=1000, max_requests=100)
    budget.charge(Usage(600, 400))
    assert budget.exhausted
    with pytest.raises(BudgetExceeded) as caught:
        budget.check()
    assert caught.value.spent_tokens == 1000


def test_the_request_budget_stops_the_run_independently_of_tokens() -> None:
    """10 RPM binds before 5M TPM does, so a run can exhaust requests with tokens to spare. Checking
    only tokens would sail straight past the axis that actually binds."""
    budget = EvalBudget(max_tokens=10_000_000, max_requests=2)
    budget.charge(Usage(1, 1))
    budget.charge(Usage(1, 1))
    assert budget.remaining_tokens > 0
    with pytest.raises(BudgetExceeded):
        budget.check()


def test_an_oversized_next_case_is_refused_before_it_starts() -> None:
    budget = EvalBudget(max_tokens=1000, max_requests=100)
    budget.check(estimated_tokens=999)
    with pytest.raises(BudgetExceeded):
        budget.check(estimated_tokens=1001)


def test_spend_is_recorded_even_past_the_limit() -> None:
    """Charging past the limit is not an error. The limit is enforced at ``check`` time, before the next
    call; a billed token that the record denies is a lie about what the run cost."""
    budget = EvalBudget(max_tokens=100, max_requests=10)
    budget.charge(Usage(90, 90))
    assert budget.spent_tokens == 180
    assert budget.remaining_tokens == 0


# --- the rate limiter ---------------------------------------------------------------------------------


def test_the_limiter_lets_the_first_window_through_without_sleeping() -> None:
    clock = FakeClock()
    limiter = RateLimiter(requests_per_minute=10, clock=clock.time, sleep=clock.sleep)
    for _ in range(10):
        limiter.acquire()
    assert clock.slept == []


def test_the_eleventh_request_in_a_minute_waits_for_the_window_to_slide() -> None:
    """The lock that matters. A limiter that records requests but never blocks is green on every test
    that does not measure the sleeping, and issues 60 RPM against a 10 RPM quota in production."""
    clock = FakeClock()
    limiter = RateLimiter(requests_per_minute=10, clock=clock.time, sleep=clock.sleep)
    for _ in range(10):
        limiter.acquire()
    limiter.acquire()
    assert clock.slept, "the eleventh request did not wait; the limiter does not limit"
    assert clock.now == pytest.approx(60.0)


def test_the_window_slides_rather_than_resetting() -> None:
    """A fixed window permits a double burst across the boundary — ten at 0:59 and ten at 1:01 is twenty
    requests inside one minute of wall clock, which the quota counts and a fixed window does not."""
    clock = FakeClock()
    limiter = RateLimiter(requests_per_minute=2, clock=clock.time, sleep=clock.sleep)
    limiter.acquire()
    clock.now = 59.0
    limiter.acquire()
    limiter.acquire()
    assert clock.now == pytest.approx(60.0)


def test_a_rate_of_zero_is_rejected_rather_than_deadlocking() -> None:
    with pytest.raises(ValueError):
        RateLimiter(requests_per_minute=0)


# --- backoff ------------------------------------------------------------------------------------------


def test_backoff_grows_and_is_capped() -> None:
    delays = list(backoff_delays(8, base_seconds=1.0, cap_seconds=10.0, jitter=lambda: 1.0))
    assert delays == [1.0, 2.0, 4.0, 8.0, 10.0, 10.0, 10.0]


def test_backoff_yields_one_fewer_delay_than_attempts() -> None:
    """The first try is not a retry. Off by one here means one extra billed call per failure."""
    assert len(list(backoff_delays(5, jitter=lambda: 1.0))) == 4
    assert list(backoff_delays(1)) == []
    assert list(backoff_delays(0)) == []


def test_jitter_is_applied_so_workers_do_not_retry_in_lockstep() -> None:
    """Several workers backing off by an identical amount rebuild the burst that caused the throttle."""
    assert list(backoff_delays(3, base_seconds=8.0, jitter=lambda: 0.5)) == [4.0, 8.0]


# --- retries ------------------------------------------------------------------------------------------


def test_a_retryable_failure_is_retried_and_can_succeed() -> None:
    clock = FakeClock()
    attempts: list[int] = []

    def call() -> str:
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError("throttled")
        return "ok"

    result = call_with_retries(
        call, is_retryable=lambda _: True, attempts=5, sleep=clock.sleep, jitter=lambda: 1.0
    )
    assert result == "ok"
    assert len(attempts) == 3
    assert len(clock.slept) == 2


def test_a_non_retryable_failure_is_raised_immediately() -> None:
    clock = FakeClock()
    with pytest.raises(ValueError):
        call_with_retries(
            _raise(ValueError("bad request")),
            is_retryable=lambda error: isinstance(error, RuntimeError),
            sleep=clock.sleep,
        )
    assert clock.slept == []


def test_an_exhausted_budget_is_never_retried() -> None:
    """Whatever ``is_retryable`` says. Retrying an exhausted budget is how a guard becomes a formality,
    and ``is_retryable=lambda _: True`` is exactly what a caller writes when it is being lazy."""
    clock = FakeClock()
    with pytest.raises(BudgetExceeded):
        call_with_retries(
            _raise(BudgetExceeded("spent", spent_tokens=1, spent_requests=1)),
            is_retryable=lambda _: True,
            sleep=clock.sleep,
        )
    assert clock.slept == []


def test_retries_give_up_and_reraise_the_last_failure() -> None:
    clock = FakeClock()
    with pytest.raises(RuntimeError, match="throttled"):
        call_with_retries(
            _raise(RuntimeError("throttled")),
            is_retryable=lambda _: True,
            attempts=3,
            sleep=clock.sleep,
            jitter=lambda: 1.0,
        )
    assert len(clock.slept) == 2


def _raise(error: Exception):  # type: ignore[no-untyped-def]
    def call() -> object:
        raise error

    return call


# --- pacing leaves room for retries the limiter cannot see -----------------------------------------


def test_eval_pacing_stays_below_the_account_quota() -> None:
    """**The lock the 2026-08-17 fix did not have until this test existed.**

    Setting `EVAL_REQUESTS_PER_MINUTE` back to 10 broke nothing, which is how a fix gets quietly
    reverted as a "simplification" — two constants with the same value look redundant. They are not:
    one is *what the account allows* and the other is *what a long run should ask for*, and the gap
    between them is deliberate.

    The gap exists because botocore retries a throttled request up to eight times inside the client,
    each retry is another request against the quota, and `ThrottledLLM.requests` counts one. The
    limiter cannot see those retries, so it has to leave room for them. A run at exactly 10 died of
    `ThrottlingException` on case 41 of 41 after three runs had got away with it.
    """
    assert EVAL_REQUESTS_PER_MINUTE < HAIKU_REQUESTS_PER_MINUTE, (
        "eval runs must pace below the account quota, not at it: the limiter cannot see botocore's "
        "retries, and a throttle costs the entire run"
    )


def test_the_live_runner_defaults_to_the_eval_pace() -> None:
    """The constant is only worth having if the billable path actually uses it."""
    import inspect

    from musical_mycelium.eval.live import run_live

    default = inspect.signature(run_live).parameters["requests_per_minute"].default
    assert default == EVAL_REQUESTS_PER_MINUTE
