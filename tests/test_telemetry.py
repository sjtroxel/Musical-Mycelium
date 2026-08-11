"""Tests for cost emission.

**These cost nothing and touch no AWS.** That is the point of choosing EMF over ``put_metric_data``:
the emitter writes a JSON line to a stream, so its entire contract is testable offline. A metric path
that could only be verified in production is a metric path nobody verifies.

``.claude/rules/evals.md`` requires the metrics themselves be unit-tested against synthetic inputs where
the answer is known by construction, *including a guard against vacuous success*. The same reasoning
applies here: cost reporting that silently reads zero is worse than cost reporting that is absent, so
several of these exist specifically to prove zero is never emitted as if it were a measurement.
"""

from __future__ import annotations

import io
import json
from typing import Any

from musical_mycelium.agent.llm import Usage
from musical_mycelium.api.telemetry import (
    NAMESPACE,
    Price,
    cost_record,
    emit_query_cost,
    load_prices,
)

HAIKU = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
SONNET = "us.anthropic.claude-sonnet-4-6-v1:0"

# 1.0 in / 5.0 out per million makes the arithmetic checkable by hand: 1M input tokens is exactly $1.
PRICES = {HAIKU: Price(input_per_mtok=1.0, output_per_mtok=5.0)}


def emitted(**kwargs: Any) -> list[dict[str, Any]]:
    """Run the emitter against a buffer and return what it actually wrote to the stream.

    Deliberately parses the stream rather than trusting the return value — the return value is a
    convenience for tests, and a test that only checked it would pass even if nothing was ever written.
    """
    buffer = io.StringIO()
    emit_query_cost(stream=buffer, **kwargs)
    return [json.loads(line) for line in buffer.getvalue().splitlines() if line.strip()]


# --- the EMF envelope -------------------------------------------------------------------------------


def test_the_record_is_valid_emf_with_the_declared_metrics_present() -> None:
    """Every name in ``CloudWatchMetrics`` must exist as a root key, or CloudWatch drops it silently."""
    record = cost_record(
        role="traversal",
        model_id=HAIKU,
        usage=Usage(input_tokens=1000, output_tokens=200),
        prices=PRICES,
        elapsed_seconds=1.5,
        timestamp_ms=1_700_000_000_000,
    )

    directive = record["_aws"]["CloudWatchMetrics"][0]
    assert directive["Namespace"] == NAMESPACE
    assert directive["Dimensions"] == [["Role", "ModelId"]]

    for metric in directive["Metrics"]:
        assert metric["Name"] in record, f"{metric['Name']} is declared but not present at root"

    for dimension in directive["Dimensions"][0]:
        assert dimension in record, f"dimension {dimension} is not present at root"


def test_token_counts_are_emitted_without_any_price_configured() -> None:
    """Tokens are measured and always reported; dollars are an interpretation and may be absent."""
    record = cost_record(
        role="traversal", model_id=HAIKU, usage=Usage(1000, 200), prices={}, timestamp_ms=0
    )

    assert record["InputTokens"] == 1000
    assert record["OutputTokens"] == 200
    assert record["TotalTokens"] == 1200
    assert "EstimatedCostUsd" not in record

    declared = {metric["Name"] for metric in record["_aws"]["CloudWatchMetrics"][0]["Metrics"]}
    assert "EstimatedCostUsd" not in declared


def test_an_unpriced_model_gets_no_invented_cost() -> None:
    """**The guard against a plausible wrong number.** A price for one model must never be borrowed
    for another — a cost metric that is sometimes real and sometimes approximated is unusable, and the
    approximation is invisible once it is in a dashboard."""
    record = cost_record(
        role="synthesis", model_id=SONNET, usage=Usage(1000, 200), prices=PRICES, timestamp_ms=0
    )

    assert "EstimatedCostUsd" not in record


def test_cost_arithmetic_is_per_million_tokens() -> None:
    record = cost_record(
        role="traversal",
        model_id=HAIKU,
        usage=Usage(input_tokens=1_000_000, output_tokens=1_000_000),
        prices=PRICES,
        timestamp_ms=0,
    )

    assert record["EstimatedCostUsd"] == 6.0  # 1M in at $1 + 1M out at $5


# --- the price table --------------------------------------------------------------------------------


def test_prices_parse_from_json() -> None:
    prices = load_prices(json.dumps({HAIKU: {"input": 1.0, "output": 5.0}}))

    assert prices[HAIKU].usd_for(Usage(1_000_000, 0)) == 1.0


def test_a_malformed_price_table_degrades_instead_of_raising() -> None:
    """This parses inside a request that is already streaming. A bad env var must cost the user their
    cost metric, never their answer."""
    for broken in ("", "not json", "[]", '{"m": "cheap"}', '{"m": {"input": "free"}}'):
        assert load_prices(broken) == {}


def test_one_bad_entry_does_not_discard_the_good_ones() -> None:
    prices = load_prices(
        json.dumps({HAIKU: {"input": 1.0, "output": 5.0}, SONNET: {"input": None}})
    )

    assert HAIKU in prices
    assert SONNET not in prices


# --- what gets written, and what deliberately does not ----------------------------------------------


def test_both_roles_are_emitted_separately_when_two_models_ran() -> None:
    """The cheap/strong split must stay legible. One blended rate describes neither model."""
    records = emitted(
        traversal_usage=Usage(5000, 100),
        traversal_model_id=HAIKU,
        synthesis_usage=Usage(800, 300),
        synthesis_model_id=SONNET,
        prices=PRICES,
    )

    by_role = {record["Role"]: record for record in records}
    assert by_role["traversal"]["ModelId"] == HAIKU
    assert by_role["synthesis"]["ModelId"] == SONNET
    assert "EstimatedCostUsd" in by_role["traversal"]
    assert "EstimatedCostUsd" not in by_role["synthesis"], "SONNET has no configured price"


def test_a_role_that_spent_nothing_is_absent_rather_than_zero() -> None:
    """**The vacuous-truth guard.** A refused run never synthesises. Emitting a zero would report a
    real measurement of zero cost and drag every average toward it; absence is the honest state."""
    records = emitted(
        traversal_usage=Usage(5000, 100),
        traversal_model_id=HAIKU,
        synthesis_usage=Usage(0, 0),
        synthesis_model_id=HAIKU,
        prices=PRICES,
    )

    assert [record["Role"] for record in records] == ["traversal"]


def test_nothing_is_emitted_when_a_run_spent_nothing_at_all() -> None:
    assert (
        emitted(
            traversal_usage=Usage(0, 0),
            traversal_model_id=HAIKU,
            synthesis_usage=Usage(0, 0),
            synthesis_model_id=HAIKU,
            prices=PRICES,
        )
        == []
    )


def test_elapsed_is_attributed_to_one_record_only() -> None:
    """Elapsed time belongs to the query, not to a role. On both records CloudWatch would double-count
    it in every statistic."""
    records = emitted(
        traversal_usage=Usage(5000, 100),
        traversal_model_id=HAIKU,
        synthesis_usage=Usage(800, 300),
        synthesis_model_id=SONNET,
        elapsed_seconds=2.25,
        prices=PRICES,
    )

    carrying = [record for record in records if "ElapsedSeconds" in record]
    assert len(carrying) == 1
    assert carrying[0]["Role"] == "traversal"


def test_each_record_is_one_line_of_json() -> None:
    """EMF is parsed per log line. A pretty-printed record spanning lines is silently ignored."""
    buffer = io.StringIO()
    emit_query_cost(
        traversal_usage=Usage(5000, 100),
        traversal_model_id=HAIKU,
        synthesis_usage=Usage(800, 300),
        synthesis_model_id=SONNET,
        prices=PRICES,
        stream=buffer,
    )

    lines = buffer.getvalue().strip().splitlines()
    assert len(lines) == 2
    for line in lines:
        json.loads(line)
