"""The figures a stranger reads in ``README.md``, derived rather than typed. Phase 7.5 step 0.

**This closes a pattern that has bitten the repo three times** (``phase-7.5-portfolio-and-writeup-
IMPLEMENTATION.md`` §3.4): the asset budget's ``observed`` fields, a demo route in ``SPEC.md`` with no
path, and the README's own test counts, which said 1465 and 210 while the suites held 1522 and 428. Each
number was true when it was written and nothing re-checked it.

**How it works.** Every current-state figure in the README sits between two markers::

    <!-- n:influence_edges -->2,284<!-- /n -->

which Markdown renders as the bare number. ``make readme`` rewrites every marked value from its source,
and ``tests/test_published_numbers.py`` fails when the committed README disagrees with one. A stale
number fails the build instead of reaching a reader, the same arrangement ``graph/facts.py`` has with
``web/src/corpus-facts.json``.

**What is deliberately NOT marked.** A dated measurement -- a latency taken on 2026-09-06, the $2.61
baseline, the single held-out run -- is history, and history does not rot as long as its date is
beside it. So is anything about the *deployed* site, which changes on a deploy rather than a commit.
Only figures describing the corpus or the code *as it is in this tree* are marked.

**Test counts are floors, not counts** -- decided by sjtroxel 2026-09-10. An exact count would fail
the build on every commit that adds a test, which is how a check gets resented and then removed. A
floor rounded down to the hundred is true the moment it is written, stays true as the suite grows, and
fails only when the suite crosses the next hundred and the claim starts understating it.

**Why this lives in ``eval``.** It reads the graph, the tool registry and the eval datasets, and
``eval`` is the one package allowed to import all three (``tests/test_architecture.py``).
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from collections import Counter
from collections.abc import Mapping
from pathlib import Path

from musical_mycelium.agent.tools import default_registry
from musical_mycelium.eval.live import live_cases
from musical_mycelium.graph.backdrop import largest_component
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import PREDICATE_INFLUENCED_BY, PREDICATE_PLAYS_GENRE, Artifact
from musical_mycelium.graph.store import Direction

ROOT = Path(__file__).resolve().parents[3]
README = ROOT / "README.md"

#: One marked figure. The key is lowercase so a marker cannot be mistaken for prose.
MARKER = re.compile(r"<!-- n:([a-z0-9_]+) -->(.*?)<!-- /n -->")

#: Test counts are published rounded DOWN to this. ``web/scripts/readme-count.mjs`` carries the same
#: number and the two must move together.
FLOOR_STEP = 100

#: Figures only the frontend toolchain can compute. The backend CI job has no Node, so these are written
#: by ``make readme`` and checked by ``web/scripts/readme-count.mjs``, never by the Python test.
WEB_KEYS = frozenset({"web_tests_floor"})

#: The artist the README uses to show a refusal. Held by id rather than label so a relabel cannot
#: quietly re-point the sentence at somebody else; the test asserts the label separately.
REFUSAL_EXAMPLE = "Q636"


def floor(count: int) -> int:
    """Round down to ``FLOOR_STEP``, so "at least N" is true by construction."""
    return count // FLOOR_STEP * FLOOR_STEP


def corpus_figures(store: InMemoryGraphStore, artifact: Artifact) -> dict[str, int | str]:
    """Every marked figure that is a fact about the pinned artifact."""
    corroboration = store.corroboration
    coverage = store.coverage.as_dict()
    tiers = artifact.verification_counts()
    by_predicate = Counter(edge.predicate for edge in artifact.edges)
    reciprocal = int(corroboration["reciprocal_pairs"])
    contested = int(corroboration["contested_pairs"])

    # The backdrop's component, computed the way `graph/backdrop.py:build` computes it but without the
    # layout solve, which is the expensive half and says nothing about the counts.
    graph = json.loads((artifact_directory() / "graph.json").read_text(encoding="utf-8"))
    keep = set(largest_component(graph["nodes"], graph["edges"]))
    backdrop_edges = sum(
        1 for e in graph["edges"] if e["subject_id"] in keep and e["object_id"] in keep
    )

    return {
        "artifact": store.artifact_version,
        "nodes": len(artifact.nodes),
        "edges": len(artifact.edges),
        "influence_edges": by_predicate[PREDICATE_INFLUENCED_BY],
        "membership_edges": by_predicate[PREDICATE_PLAYS_GENRE],
        # How strongly ONE source was checked. Never read as corroboration, which is the next block.
        "verified_hand": tiers["HAND"],
        "verified_prose": tiers["PROSE_AUTO"],
        "verified_asserts": tiers["ASSERTS_AUTO"],
        "verified_infobox": tiers["INFOBOX_AUTO"],
        "verified_exposure": tiers["EXPOSURE_AUTO"],
        "verified_membership": tiers["MEMBERSHIP_BARE"] + tiers["MEMBERSHIP_CITED"],
        # Whether a SECOND source agrees. Reciprocal and contested ride together, never one alone.
        "corroborated": int(corroboration["corroborated"]),
        "single_source": int(corroboration["single_source"]),
        "reciprocal_pairs": reciprocal,
        "contested_pairs": contested,
        "contested_overcount": f"{reciprocal / contested:g}x" if contested else "n/a",
        "backdrop_nodes": len(keep),
        "backdrop_edges": backdrop_edges,
        "earliest_genre_year": min(
            node.inception_year
            for node in artifact.nodes
            if node.kind == "genre" and node.inception_year is not None
        ),
        # P495 values, which include Brixton and Europe: the README says PLACES, not countries.
        "places": int(coverage["distinct_countries"]),
        "genres_without_us_or_uk": int(coverage["genres_without_us_or_uk"]),
        "tools": len(default_registry(store)),
        # `subject influenced_by object`. The refusal rests on the FIRST of these being zero.
        "refusal_example_influenced_by": len(
            store.neighbors(REFUSAL_EXAMPLE, Direction.INFLUENCED_BY)
        ),
        "refusal_example_influenced": len(store.neighbors(REFUSAL_EXAMPLE, Direction.INFLUENCED)),
    }


def _collected(*args: str) -> int:
    """How many tests pytest collects, honouring the spend guard in ``pyproject.toml``'s addopts."""
    output = subprocess.run(
        [sys.executable, "-m", "pytest", "--collect-only", "-q", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return sum(int(match) for match in re.findall(r"^tests/\S+: (\d+)$", output, re.MULTILINE))


def python_test_counts() -> tuple[int, int]:
    """(tests ``make check`` runs, tests that spend real money and are deselected by default)."""
    return _collected(), _collected("-m", "costs_money")


def web_test_count() -> int:
    """The frontend suite's size. Needs Node, so only ``make readme`` calls it."""
    output = subprocess.run(
        ["npx", "vitest", "list", "--json"],
        cwd=ROOT / "web",
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    return len(json.loads(output))


def _format(value: int | str) -> str:
    return f"{value:,}" if isinstance(value, int) else value


def figures(*, include_web: bool = True) -> dict[str, str]:
    """Every marked figure, formatted exactly as the README prints it."""
    store = InMemoryGraphStore.from_directory(artifact_directory())
    values = corpus_figures(store, Artifact.load(artifact_directory()))
    python_tests, spends_money = python_test_counts()
    values["python_tests_floor"] = floor(python_tests)
    values["costs_money_tests"] = spends_money
    values["live_cases"] = len(live_cases())
    if include_web:
        values["web_tests_floor"] = floor(web_test_count())
    return {key: _format(value) for key, value in values.items()}


def render(text: str, values: Mapping[str, str]) -> str:
    """``text`` with every marked figure rewritten from ``values``.

    A marker naming a figure this module does not compute is an error rather than a pass-through: a
    typo in a key would otherwise leave that number unprotected and look protected. Web keys absent
    from ``values`` are left as they are, because the Python side cannot compute them.
    """

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key in values:
            return f"<!-- n:{key} -->{values[key]}<!-- /n -->"
        if key in WEB_KEYS:
            return match.group(0)
        raise KeyError(f"README marker n:{key} names no figure in eval/published.py")

    return MARKER.sub(replace, text)


def stale(text: str, values: Mapping[str, str]) -> list[str]:
    """One line per marked figure that disagrees with its source, for a failure message a person can
    act on without diffing the file."""
    return [
        f"n:{key} -- README says {shown}, the source says {values[key]}"
        for key, shown in MARKER.findall(text)
        if key in values and shown != values[key]
    ]


def main() -> None:
    values = figures()
    text = README.read_text(encoding="utf-8")
    changed = stale(text, values)
    README.write_text(render(text, values), encoding="utf-8")
    for line in changed:
        print(line)
    print(f"README.md: {len(changed)} figure(s) rewritten, {len(MARKER.findall(text))} marked")


if __name__ == "__main__":
    main()
