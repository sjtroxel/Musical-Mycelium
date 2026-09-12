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

import re

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
from musical_mycelium.eval.report_page import (
    PAGE as REPORT_PAGE,
)
from musical_mycelium.eval.report_page import (
    heldout_runs,
    results,
    sealed_dataset,
)
from musical_mycelium.graph.memory import default_store

#: The two prose surfaces the run-count claim went stale on beside the README. Phase 7.7, 2026-09-12.
EVAL_EXPLAINER = README.parent / "docs" / "eval-suite-explained.md"


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


def test_no_public_surface_claims_a_run_the_sealed_set_has_not_had() -> None:
    """The *claim* again, and the one that actually went wrong. Phase 7.7, 2026-09-12.

    On 2026-09-12 the held-out set was replaced and ``heldout_v1`` retired, its ciphertext kept only in
    git. Its one result file stayed in ``eval/results`` on purpose -- it records a measurement actually
    taken -- and three public surfaces went on presenting that measurement as the *current* set's:
    ``README.md``, ``docs/eval-suite-explained.md``, and the deployed evaluation report, whose generator
    took the newest ``*-heldout.json`` without ever comparing its ``dataset_version`` to the manifest.

    The run count is not a marked figure and cannot be one: it is not a fact about the corpus. So this
    is a claim test. It derives the sealed set's real run count the way the report page now does, and
    fails if prose a stranger reads says the set was run when no run of *that* set exists.
    """
    own, retired = heldout_runs(results("heldout"), sealed_dataset())
    if own:
        pytest.skip(
            f"the sealed set has been run {len(own)} time(s); this guard covers run count 0"
        )

    assert retired, (
        "no retired run to confuse the current set with; this guard has nothing to protect"
    )
    # The retired run may be DISCLOSED, but only as history: every mention of a score has to sit near a
    # word that hands it to the old set. A 300-character window rather than a sentence, because
    # sentence-splitting on "." breaks on "artifact 0.5.0" -- which is how this test first failed.
    attributions = ("earlier", "retired", "no longer", "previous")
    for path in (README, EVAL_EXPLAINER, REPORT_PAGE):
        text = path.read_text(encoding="utf-8")
        for claim in ("was run once", "has now been opened", "10 of 10", "10/10"):
            for match in re.finditer(re.escape(claim), text):
                window = text[max(0, match.start() - 300) : match.start()].lower()
                assert any(word in window for word in attributions), (
                    f"{path.name} says {claim!r} with nothing nearby marking it as the RETIRED set's "
                    f"result, while the sealed set's own run count is 0"
                )


def test_the_sealed_sets_own_runs_never_include_a_retired_sets_run() -> None:
    """``heldout_runs`` is the whole fix, so it gets a test that does not depend on today's files."""
    runs = [
        ("20260824T120956Z", {"dataset_version": "heldout_v1", "cases_correct": 10}),
        ("20260913T000000Z", {"dataset_version": "heldout_v2", "cases_correct": 9}),
        ("20260914T000000Z", {}),
    ]
    own, retired = heldout_runs(runs, "heldout_v2")
    assert [stamp for stamp, _ in own] == ["20260913T000000Z"]
    assert [stamp for stamp, _ in retired] == ["20260824T120956Z", "20260914T000000Z"]
    assert sealed_dataset() == "heldout_v2", (
        "the manifest names a different set than the code expects"
    )
