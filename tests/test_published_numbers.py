"""Every current-state number in ``README.md`` must match its source. Phase 7.5 step 0.

The README said *"1465 Python tests and 210 frontend tests"* while the suites held 1522 and 428, and
*"43 of its genres name no US or UK origin"* two artifact versions after that stopped being true. Both
were correct when typed. ``eval/published.py`` now writes those figures and this file fails when the
committed README disagrees with a source -- the arrangement ``tests/test_corpus_facts.py`` already has
with the SPA's figures, extended to the page a stranger reads first.

If it fails, run ``make readme``. If the diff surprises you, that is the point.

The frontend test floor is the one marked figure this file does not check: the backend CI job has no
Node. ``web/scripts/readme-count.mjs`` checks it inside ``npm run check``.
"""

from __future__ import annotations

import pytest

from musical_mycelium.eval.published import (
    MARKER,
    README,
    REFUSAL_EXAMPLE,
    WEB_KEYS,
    figures,
    floor,
    render,
    stale,
)
from musical_mycelium.graph.memory import default_store


@pytest.fixture(scope="module")
def values() -> dict[str, str]:
    return figures(include_web=False)


@pytest.fixture(scope="module")
def readme() -> str:
    return README.read_text(encoding="utf-8")


def test_every_marked_figure_matches_its_source(values: dict[str, str], readme: str) -> None:
    problems = stale(readme, values)
    assert not problems, "README.md has stale figures -- run `make readme`:\n" + "\n".join(problems)


def test_every_marker_names_a_figure_the_generator_computes(
    values: dict[str, str], readme: str
) -> None:
    """A typo in a key would leave a number unprotected while looking protected."""
    unknown = {key for key, _ in MARKER.findall(readme)} - values.keys() - WEB_KEYS
    assert not unknown, f"README.md markers with no source: {sorted(unknown)}"


def test_every_figure_the_generator_computes_is_still_marked(
    values: dict[str, str], readme: str
) -> None:
    """The other direction. Deleting a marker and retyping the number by hand must fail somewhere, and
    this is where: a figure that stops being published has to be removed from the generator on purpose.
    """
    marked = {key for key, _ in MARKER.findall(readme)}
    missing = (values.keys() | WEB_KEYS) - marked
    assert not missing, f"figures computed but no longer marked in README.md: {sorted(missing)}"


def test_the_refusal_example_still_refuses(values: dict[str, str]) -> None:
    """The *claim*, not the digits. The README says "Who influenced Kate Bush?" refuses. That sentence is
    true only while she is the subject of no influence edge; the markers keep the counts right, and this
    keeps the sentence built on them from going quietly false."""
    node = default_store().get_node(REFUSAL_EXAMPLE)
    assert node is not None and node.label == "Kate Bush"
    assert values["refusal_example_influenced_by"] == "0", (
        "Kate Bush now records an influence -- the README's refusal example no longer refuses"
    )


def test_a_floor_is_never_more_than_the_count() -> None:
    assert floor(1522) == 1500
    assert floor(1500) == 1500
    assert floor(1499) == 1400
    assert floor(99) == 0
    for count in range(0, 2000, 37):
        assert floor(count) <= count


def test_a_stale_figure_is_caught_and_rewritten() -> None:
    """Deliberate breakage, kept as a test: a wrong number is reported, and render repairs it."""
    text = "The corpus has <!-- n:nodes -->1,000<!-- /n --> nodes."
    source = {"nodes": "1,479"}
    assert stale(text, source) == ["n:nodes -- README says 1,000, the source says 1,479"]
    assert render(text, source) == "The corpus has <!-- n:nodes -->1,479<!-- /n --> nodes."
    assert stale(render(text, source), source) == []


def test_an_unknown_marker_is_an_error_not_a_pass_through() -> None:
    with pytest.raises(KeyError):
        render("<!-- n:nodez -->1<!-- /n -->", {"nodes": "1"})


def test_a_web_marker_survives_a_render_that_cannot_compute_it() -> None:
    text = "<!-- n:web_tests_floor -->400<!-- /n -->"
    assert render(text, {}) == text
