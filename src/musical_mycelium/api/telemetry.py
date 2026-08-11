"""Token cost to CloudWatch, which ``.claude/rules/aws-and-cost.md`` has asked for since day one.

**Why this did not exist until 2026-08-11.** The rule says *"track real token cost to CloudWatch from
day one so measured numbers replace the estimates,"* and nothing did. It is worth being straight about
the reason: this was never blocked by the Bedrock quota. It could have been written against
``ScriptedLLM`` at any point. It is ordinary debt, not a casualty of the outage.

## Two decisions worth stating

**1. Embedded Metric Format on stdout, not ``put_metric_data``.** EMF is a JSON line written to the log
stream; CloudWatch extracts metrics from it automatically. That means **no boto3 client, no extra IAM
permission, no added request latency on a streaming response, and no per-call charge** — against
``put_metric_data``, which costs all four. For a project whose fixed infrastructure is designed to cost
approximately nothing, on a Lambda where the timeout is itself a cost control, that is not a close call.
It also keeps this module free of an AWS import, so nothing above the provider seam grows one.

**2. Prices are configuration and are never hardcoded.** Token counts are always emitted, because they
are *measured* and cannot go stale. Dollars are emitted **only** when ``MYCELIUM_TOKEN_PRICES`` is set.

That asymmetry is deliberate. A per-token price baked into source is wrong the moment a vendor changes
it, and a wrong price does not fail — it silently produces a plausible cost number that every downstream
decision then trusts. Tokens are ground truth; dollars are an interpretation with an expiry date. If the
variable is unset, this module reports usage and stays quiet about money, which is the honest degraded
state rather than a guess.

``MYCELIUM_TOKEN_PRICES`` is JSON mapping model id to USD **per million tokens**::

    {"us.anthropic.claude-haiku-4-5-20251001-v1:0": {"input": 1.0, "output": 5.0}}

Look the numbers up when setting it. Do not copy them from a docstring, including this one — the shape
above is an illustration of the format and nothing else.

## Why the split survives all the way out here

``Done`` carries traversal and synthesis usage **separately**, and its docstring explains why: two roles
may run on two models, two models price differently, and one summed token count cannot be turned into
dollars by anyone downstream. This module is the "anyone downstream" that finally knows both prices, so
it is where summing legitimately happens — one EMF record per role, dimensioned by model, so a
cheap/strong split stays visible in CloudWatch rather than being averaged into a single misleading rate.
"""

from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, TextIO

from musical_mycelium.agent.llm import Usage

#: The CloudWatch namespace every metric here lands in.
NAMESPACE = "MusicalMycelium"

#: JSON mapping model id -> {"input": usd_per_million, "output": usd_per_million}. Unset means token
#: counts are still emitted and dollar figures are not. See the module docstring for why that is the
#: correct default rather than a fallback price.
PRICES_ENV = "MYCELIUM_TOKEN_PRICES"

ROLE_TRAVERSAL = "traversal"
ROLE_SYNTHESIS = "synthesis"


@dataclass(frozen=True, slots=True)
class Price:
    """USD per million tokens, in and out."""

    input_per_mtok: float
    output_per_mtok: float

    def usd_for(self, usage: Usage) -> float:
        return (
            usage.input_tokens * self.input_per_mtok + usage.output_tokens * self.output_per_mtok
        ) / 1_000_000


def load_prices(raw: str | None = None) -> dict[str, Price]:
    """Parse ``MYCELIUM_TOKEN_PRICES``, degrading to "no prices" rather than raising.

    **A malformed price table must never take down a user's answer.** This runs inside a request that is
    already streaming; raising here would turn a cost-reporting problem into a failed query. The
    degraded state is the same one an unset variable produces — tokens without dollars — which is
    exactly the state this module is designed to be honest about, so the failure is survivable by
    construction rather than by a rescue.
    """
    source = os.environ.get(PRICES_ENV) if raw is None else raw
    if not source:
        return {}

    try:
        parsed = json.loads(source)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}

    prices: dict[str, Price] = {}
    for model_id, entry in parsed.items():
        if not isinstance(entry, dict):
            continue
        try:
            prices[str(model_id)] = Price(
                input_per_mtok=float(entry["input"]),
                output_per_mtok=float(entry["output"]),
            )
        except (KeyError, TypeError, ValueError):
            continue
    return prices


def cost_record(
    *,
    role: str,
    model_id: str,
    usage: Usage,
    prices: dict[str, Price],
    elapsed_seconds: float | None = None,
    timestamp_ms: int | None = None,
) -> dict[str, Any]:
    """One EMF record. Pure — builds the dict, writes nothing, so it is testable without capturing IO.

    ``EstimatedCostUsd`` is present only when a price is configured for this exact model id. It is not
    approximated from a similar model, and there is no default price: a metric that is sometimes real
    and sometimes a guess is worse than one that is sometimes absent, because absence is visible in a
    dashboard and a wrong number is not.
    """
    metrics: list[dict[str, str]] = [
        {"Name": "InputTokens", "Unit": "Count"},
        {"Name": "OutputTokens", "Unit": "Count"},
        {"Name": "TotalTokens", "Unit": "Count"},
    ]
    record: dict[str, Any] = {
        "Role": role,
        "ModelId": model_id,
        "InputTokens": usage.input_tokens,
        "OutputTokens": usage.output_tokens,
        "TotalTokens": usage.total_tokens,
    }

    price = prices.get(model_id)
    if price is not None:
        record["EstimatedCostUsd"] = round(price.usd_for(usage), 8)
        metrics.append({"Name": "EstimatedCostUsd", "Unit": "None"})

    if elapsed_seconds is not None:
        record["ElapsedSeconds"] = round(elapsed_seconds, 3)
        metrics.append({"Name": "ElapsedSeconds", "Unit": "Seconds"})

    record["_aws"] = {
        "Timestamp": timestamp_ms if timestamp_ms is not None else int(time.time() * 1000),
        "CloudWatchMetrics": [
            {
                "Namespace": NAMESPACE,
                # Dimensioned by both, so the cheap/strong split stays legible: a single aggregate rate
                # across two differently-priced models is a number that describes neither.
                "Dimensions": [["Role", "ModelId"]],
                "Metrics": metrics,
            }
        ],
    }
    return record


def emit_query_cost(
    *,
    traversal_usage: Usage,
    traversal_model_id: str,
    synthesis_usage: Usage,
    synthesis_model_id: str,
    elapsed_seconds: float | None = None,
    prices: dict[str, Price] | None = None,
    stream: TextIO | None = None,
) -> list[dict[str, Any]]:
    """Write one EMF line per role that actually spent tokens. Returns what it wrote, for tests.

    **A role that reported zero tokens is skipped rather than emitted as a zero.** The local provider
    reports synthetic counts and a run that refused never synthesises at all; publishing those as real
    zeroes would drag any average down and make a stub deployment look like a cheap model. Absent is
    honest; zero is a claim.
    """
    resolved = load_prices() if prices is None else prices
    out = stream if stream is not None else sys.stdout

    records: list[dict[str, Any]] = []
    for role, model_id, usage in (
        (ROLE_TRAVERSAL, traversal_model_id, traversal_usage),
        (ROLE_SYNTHESIS, synthesis_model_id, synthesis_usage),
    ):
        if usage.total_tokens <= 0 or not model_id:
            continue
        record = cost_record(
            role=role,
            model_id=model_id,
            usage=usage,
            prices=resolved,
            # Elapsed is a property of the whole query, not of one role, so it rides on the traversal
            # record only. Emitting it twice would double-count it in any CloudWatch statistic.
            elapsed_seconds=elapsed_seconds if role == ROLE_TRAVERSAL else None,
        )
        records.append(record)
        print(json.dumps(record), file=out)

    return records
