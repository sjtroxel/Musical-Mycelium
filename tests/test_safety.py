"""Spend-gate tests. Every one of these is an attempt to spend money without being asked.

The gate exists because of a real incident (see `eval/safety.py`), and the incident's shape was
*a run that took the paid path without a human in the loop*. So the load-bearing test here is not
"does it accept yes" — it is `test_a_non_interactive_stream_is_refused`, which reproduces that
shape directly, plus `test_no_bypass_exists_in_the_source`, which is the only way to assert that
nobody adds the convenience flag back later.
"""

from __future__ import annotations

import ast
import io
from pathlib import Path

import pytest

from musical_mycelium.api.telemetry import Price
from musical_mycelium.eval.safety import (
    CONFIRMATION_WORD,
    MAX_CASES_PER_RUN,
    SpendCapExceeded,
    SpendEstimate,
    SpendRefused,
    UnattendedSpend,
    confirm_spend,
)


class FakeTTY(io.StringIO):
    """A stream that claims to be a terminal.

    Needed because `io.StringIO.isatty()` is `False`, which the gate correctly refuses — the tests
    have to opt *into* looking interactive rather than being waved through for being tests.
    """

    def isatty(self) -> bool:
        return True


def estimate(cases: int = 41, **overrides: object) -> SpendEstimate:
    fields: dict[str, object] = {
        "description": "gold + adversarial",
        "cases": cases,
        "requests": 250,
        "input_tokens": 500_000,
        "output_tokens": 40_000,
        "model_id": "us.anthropic.claude-haiku-4-5-20251001-v1:0",
    }
    fields.update(overrides)
    return SpendEstimate(**fields)  # type: ignore[arg-type]


# --- layer 2: the incident's own shape ---------------------------------------------------------


def test_a_non_interactive_stream_is_refused() -> None:
    """**The original incident, reproduced.** A piped, redirected, backgrounded, or CI stdin is
    refused outright — not defaulted to yes (the incident) and not defaulted to no (which would be
    safe but silent, and a silent skip reads as a suite that passed)."""
    out = io.StringIO()
    with pytest.raises(UnattendedSpend):
        confirm_spend(estimate(), stdin=io.StringIO("yes\n"), stdout=out)


def test_an_unattended_refusal_never_prompts() -> None:
    """Nothing is printed on the unattended path. A prompt written to a stream nobody is reading is
    how a background run appears to hang rather than to have refused."""
    out = io.StringIO()
    with pytest.raises(UnattendedSpend):
        confirm_spend(estimate(), stdin=io.StringIO("yes\n"), stdout=out)
    assert out.getvalue() == ""


def test_a_stream_with_no_isatty_at_all_is_treated_as_unattended() -> None:
    """The safe reading of "I cannot tell whether anyone is watching" is that nobody is."""

    class NoIsatty:
        def readline(self) -> str:
            return "yes\n"

    with pytest.raises(UnattendedSpend):
        confirm_spend(estimate(), stdin=NoIsatty(), stdout=io.StringIO())  # type: ignore[arg-type]


# --- layer 1: the cap cannot be talked past ------------------------------------------------------


def test_the_cap_is_checked_before_the_prompt(capsys: pytest.CaptureFixture[str]) -> None:
    """A cap a confirmation can override is not a cap. Nothing is printed and nothing is read."""
    out = io.StringIO()
    stdin = FakeTTY(f"{CONFIRMATION_WORD}\n")
    with pytest.raises(SpendCapExceeded):
        confirm_spend(estimate(cases=MAX_CASES_PER_RUN + 1), stdin=stdin, stdout=out)
    assert out.getvalue() == ""
    assert stdin.read() == f"{CONFIRMATION_WORD}\n", "the answer was consumed; the cap ran too late"


def test_a_run_of_zero_cases_is_refused() -> None:
    with pytest.raises(SpendCapExceeded):
        confirm_spend(estimate(cases=0), stdin=FakeTTY("yes\n"), stdout=io.StringIO())


def test_the_cap_is_generous_enough_for_every_real_dataset() -> None:
    """25 gold + 16 adversarial + 10 held-out = 51. The cap must never obstruct an honest run, or it
    gets raised in a hurry by someone who has stopped reading it."""
    assert MAX_CASES_PER_RUN > 51 * 2


# --- layer 3: the typed confirmation -------------------------------------------------------------


def test_the_whole_word_confirms() -> None:
    confirm_spend(estimate(), stdin=FakeTTY(f"{CONFIRMATION_WORD}\n"), stdout=io.StringIO())


@pytest.mark.parametrize("answer", ["YES\n", "  yes  \n", "Yes\n"])
def test_confirmation_tolerates_case_and_surrounding_space(answer: str) -> None:
    confirm_spend(estimate(), stdin=FakeTTY(answer), stdout=io.StringIO())


@pytest.mark.parametrize("answer", ["y\n", "Y\n", "yeah\n", "no\n", "\n", "yes please\n"])
def test_anything_short_of_the_whole_word_refuses(answer: str) -> None:
    """`y` is deliberately rejected: a single keystroke is what gets hit by reflex, and approving
    spend is supposed to cost a deliberate act."""
    with pytest.raises(SpendRefused):
        confirm_spend(estimate(), stdin=FakeTTY(answer), stdout=io.StringIO())


def test_eof_is_not_an_answer() -> None:
    """An empty string is a closed stream, not an empty line. Reading it as consent is how a gate
    becomes a formality."""
    with pytest.raises(SpendRefused):
        confirm_spend(estimate(), stdin=FakeTTY(""), stdout=io.StringIO())


# --- the estimate renders honestly ---------------------------------------------------------------


def test_no_dollars_are_shown_without_a_configured_price(monkeypatch: pytest.MonkeyPatch) -> None:
    """Absence is the correct default, not a fallback rate. A wrong price does not fail loudly — it
    produces a plausible number that gets believed."""
    monkeypatch.delenv("MYCELIUM_TOKEN_PRICES", raising=False)
    text = estimate().render()
    assert "no price configured" in text
    assert "$" not in text


def test_dollars_are_shown_when_a_price_is_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    model = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
    monkeypatch.setenv("MYCELIUM_TOKEN_PRICES", f'{{"{model}": {{"input": 1.0, "output": 5.0}}}}')
    # 500k in at $1/M + 40k out at $5/M = $0.50 + $0.20
    assert estimate().estimated_usd() == pytest.approx(0.70)
    assert "$0.70" in estimate().render()


def test_a_price_for_a_different_model_is_not_borrowed() -> None:
    """Never approximated from a similar model, for the reason `api/telemetry.py` gives about its own
    cost record: a figure that is sometimes real and sometimes invented is worse than one absent."""
    prices = {"some.other.model": Price(input_per_mtok=1.0, output_per_mtok=5.0)}
    assert estimate().estimated_usd(prices) is None


def test_the_estimate_says_it_is_an_estimate_and_names_the_wall_clock() -> None:
    text = estimate().render()
    assert "ESTIMATES" in text
    assert "minutes" in text, "10 RPM is the binding constraint; the prompt has to say how long"


def test_the_prompt_shows_the_estimate_before_reading_an_answer() -> None:
    out = io.StringIO()
    confirm_spend(estimate(), stdin=FakeTTY("yes\n"), stdout=out)
    text = out.getvalue()
    assert "About to spend real money" in text
    assert "gold + adversarial" in text
    assert CONFIRMATION_WORD in text


# --- the structural lock -------------------------------------------------------------------------


def test_no_bypass_exists_in_the_source() -> None:
    """**The only test here that guards the future rather than the present.**

    Every escape hatch that would let this run unattended is the thing that went wrong in the
    original incident, so the absence of one is a property worth asserting rather than trusting.
    A future `--yes` flag or `MYCELIUM_ASSUME_YES` env var has to delete this test to land, which
    makes it a decision instead of a convenience.
    """
    source = (
        Path(__file__).resolve().parents[1] / "src/musical_mycelium/eval/safety.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)

    # Identifiers only — docstrings and comments are prose *about* the bypasses and must not trip
    # this. An earlier version scanned raw text and failed on its own explanation of why `--yes`
    # does not exist, which is the difference between checking the code and checking the essay.
    identifiers: set[str] = set()
    for node in ast.walk(tree):
        match node:
            case ast.Name():
                identifiers.add(node.id)
            case ast.Attribute():
                identifiers.add(node.attr)
            case ast.arg():
                identifiers.add(node.arg)
            case ast.keyword() if node.arg is not None:
                identifiers.add(node.arg)
            case ast.FunctionDef() | ast.ClassDef():
                identifiers.add(node.name)

    lowered = {name.casefold() for name in identifiers}
    for bypass in ("assume_yes", "yes", "force", "skip_confirm", "auto_confirm", "non_interactive"):
        assert bypass not in lowered, f"a spend bypass appeared in safety.py: {bypass}"

    # The env-var check is structural: the module must not import `os` at all, so there is no
    # reachable way for a stray variable in his shell to pre-approve a run.
    imported = {
        alias.name.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    } | {
        node.module.split(".")[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert "os" not in imported, "safety.py must not read an environment variable to decide"
