"""The committed price table, and the locks that keep it honest.

**Why this file exists.** `api/telemetry.py` is built on one asymmetry: token counts are measured and
cannot go stale, dollars are an interpretation with an expiry date. It therefore refuses to invent a
price and stays silent when none is configured. That is the right default and it has a cost -- for the
whole of phases 3 through 6, every billable run printed *"cost not shown"*, including the two on
2026-09-06. The fix is configuration, not code, and configuration is exactly what nothing tests.

So these are locks on the configuration. The one that matters most is
:func:`test_every_model_this_project_invokes_has_a_price`: a price table is silently useless the moment
the default model id moves past it, and the failure mode is not an error but a missing line in a report
nobody reads twice.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from musical_mycelium.agent.llm import DEFAULT_JUDGE_MODEL_ID, DEFAULT_MODEL_ID, Usage
from musical_mycelium.api.telemetry import load_prices

PRICES_PATH = Path(__file__).resolve().parents[1] / "infra" / "token-prices.json"

#: The metadata key prefix. `load_prices` skips these, and the file uses one to carry the date the
#: numbers were looked up -- JSON has no comments, and a price separated from its date goes stale with
#: nothing to show for it.
METADATA_PREFIX = "_"


@pytest.fixture(scope="module")
def raw() -> str:
    return PRICES_PATH.read_text()


def test_the_committed_table_is_valid_json_and_parses_to_prices(raw: str) -> None:
    json.loads(raw)
    assert load_prices(raw), "the committed table parsed to no prices at all"


def test_every_model_this_project_invokes_has_a_price(raw: str) -> None:
    """**The lock that earns this file.**

    `load_prices` matches on the EXACT model id and never approximates from a similar model, so a
    default that moves past the table does not fail -- it silently returns to "cost not shown", which
    is the state this whole step existed to leave. Both roles are checked: the traversal/synthesis
    model and the judge, which is a different vendor and priced differently.
    """
    prices = load_prices(raw)
    for model_id in (DEFAULT_MODEL_ID, DEFAULT_JUDGE_MODEL_ID):
        assert model_id in prices, (
            f"{model_id!r} is invoked by this project and is not priced in {PRICES_PATH.name}. "
            "Look the current price up and add it -- do not copy one from a docstring, and do not "
            "let a nearby model's price stand in for it."
        )


def test_metadata_keys_are_not_read_as_prices(raw: str) -> None:
    """The reserved prefix is part of the format, not an accident of the parser.

    This worked before `load_prices` had an explicit branch for it, by falling through the
    `isinstance` check on the entry. It works now because the format says so, and this is what says
    so.
    """
    parsed = json.loads(raw)
    metadata = [key for key in parsed if key.startswith(METADATA_PREFIX)]
    assert metadata, "the table carries no metadata key, so its numbers carry no date"

    prices = load_prices(raw)
    for key in metadata:
        assert key not in prices, f"{key!r} is metadata and was read as a model price"


def test_the_table_reproduces_the_projects_own_measured_per_query_cost(raw: str) -> None:
    """A typo that parses is the failure this catches.

    `1.0` mistyped as `10.0` is valid JSON, valid schema, and silently multiplies every dollar figure
    the project reports by ten. Nothing else here would notice. So the table is checked against a
    number measured independently of it: `.claude/rules/aws-and-cost.md` records a query averaging
    **6,624 input + 421 output tokens (~$0.009)**, measured 2026-08-24.

    **When this fails because a real price changed** -- which will happen -- the fix is not to widen
    the tolerance. It is to update the price AND the measured figure in `.claude/rules/aws-and-cost.md`
    together, because that sentence is quoted in interview material and would otherwise keep asserting
    a cost the table no longer produces.
    """
    prices = load_prices(raw)
    usd = prices[DEFAULT_MODEL_ID].usd_for(Usage(input_tokens=6624, output_tokens=421))
    assert round(usd, 3) == 0.009, (
        f"the committed table prices the measured average query at ${usd:.6f}, and "
        ".claude/rules/aws-and-cost.md records ~$0.009. One of the two is now wrong."
    )
