"""Do the chips actually behave the way `chips.json` declares? Only a real model can answer that.

``tests/test_chips.py`` checks the chip set against the *corpus*: the nodes exist, an ``expect: answer``
step has edges in the direction it names, an ``expect: refusal`` step has none. All true, all free, and
**none of it proves the agent does the corresponding thing.**

That gap was not hypothetical. On 2026-08-26 the paired Kate Bush chip was believed to refuse and then
answer, and every free test agreed. Run against the local stub it refused **twice** — a reachable dead
end, which is exactly what DoD 10 requirement 4 forbids — because ``LocalLLM`` walks one fixed path
(resolve, then ``get_influences``, then stop) and has no route to ``get_descendants`` at all. Against
Bedrock the same chip answers with seven cited claims. The product was fine; the evidence was not.

So this file exists to close the loop the free tests cannot: **the declared expectation, checked against
what the agent really does.**

**How to run it.** Deselected by ``addopts`` in ``pyproject.toml``; a later ``-m`` overrides::

    uv run pytest -m costs_money tests/test_chips_live.py

**Cost.** Six queries, one per chip step, roughly a cent each at Haiku 4.5 prices (6,624 input + 421
output tokens on average, measured 2026-08-24). Under ten cents for the file. It is deliberately one
query per step and it must stay that way -- this account has 10 RPM, so a file that fanned out would hit
request throttling long before it hit token throttling.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from musical_mycelium.agent.llm import ROLE_SYNTHESIS, ROLE_TRAVERSAL, build_llm
from musical_mycelium.agent.loop import ClaimApproved, Refused, run
from musical_mycelium.agent.tools import default_registry
from musical_mycelium.graph.memory import InMemoryGraphStore, default_store

# File-wide, so a new test here cannot be added and quietly run unmarked.
pytestmark = pytest.mark.costs_money

CHIPS_PATH = Path(__file__).resolve().parents[1] / "web" / "src" / "chips.json"


def chip_steps() -> list[tuple[str, str, str]]:
    """``(chip_id, query, expect)`` for every step of every chip, for parametrisation."""
    document = json.loads(CHIPS_PATH.read_text(encoding="utf-8"))
    return [
        (chip["id"], step["query"], step["expect"])
        for chip in document["chips"]
        for step in chip["steps"]
    ]


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return default_store()


@pytest.mark.parametrize(("chip_id", "query", "expect"), chip_steps())
def test_each_chip_step_behaves_as_declared(
    chip_id: str, query: str, expect: str, store: InMemoryGraphStore
) -> None:
    """A chip that says it answers must answer, with at least one gated claim.

    Note what is asserted and what is not. **Claim COUNT is not asserted**, and must not be: the number
    of claims that survive the gate is a property of the run, and pinning it here would turn a normal
    model variation into a red build. What is asserted is the thing the first screen promises -- that a
    chip advertised as answering produces cited claims, and one advertised as refusing produces none.
    """
    events = list(
        run(
            query,
            store=store,
            llm=build_llm(role=ROLE_TRAVERSAL),
            registry=default_registry(store),
            synthesis_llm=build_llm(role=ROLE_SYNTHESIS),
        )
    )
    claims = [event for event in events if isinstance(event, ClaimApproved)]
    refusals = [event for event in events if isinstance(event, Refused)]

    if expect == "answer":
        assert claims, (
            f"chip {chip_id} advertises an answer for {query!r} but the agent produced no approved "
            f"claims (refused: {bool(refusals)})"
        )
        assert not refusals, (
            f"chip {chip_id} advertises an answer for {query!r} but the agent refused"
        )
    else:
        assert refusals, (
            f"chip {chip_id} advertises a refusal for {query!r} but the agent did not refuse"
        )
        assert not claims, (
            f"chip {chip_id} advertises a refusal for {query!r} but {len(claims)} claims were approved"
        )


def test_no_paired_chip_ends_on_a_refusal_in_practice(store: InMemoryGraphStore) -> None:
    """DoD 10 requirement 4 -- *no dead end is reachable* -- verified by running it.

    ``test_chips.py`` asserts the same thing about the chip *file*. This asserts it about the *system*,
    which is the version that was false on 2026-08-26 while the file-level one passed.
    """
    document = json.loads(CHIPS_PATH.read_text(encoding="utf-8"))
    for chip in document["chips"]:
        if not any(step["expect"] == "refusal" for step in chip["steps"]):
            continue
        last = chip["steps"][-1]
        events = list(
            run(
                last["query"],
                store=store,
                llm=build_llm(role=ROLE_TRAVERSAL),
                registry=default_registry(store),
                synthesis_llm=build_llm(role=ROLE_SYNTHESIS),
            )
        )
        assert [event for event in events if isinstance(event, ClaimApproved)], (
            f"chip {chip['id']} ends on {last['query']!r}, which produced no claims -- the pairing "
            f"leaves a refusal as the last thing on screen"
        )
