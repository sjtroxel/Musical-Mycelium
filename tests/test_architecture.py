"""Architecture tests.

The package boundaries and the dependency direction are one-way doors (``CLAUDE.md`` invariant 6), so
they get a test rather than a convention nobody checks. These are the only tests that exist before there
is anything to test, and that is deliberate: they make CI real from the first commit.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

SUBPACKAGES = ["ingest", "graph", "agent", "api", "eval"]
SRC = Path(__file__).resolve().parents[1] / "src" / "musical_mycelium"


@pytest.mark.parametrize("name", SUBPACKAGES)
def test_subpackage_exists_and_documents_its_contract(name: str) -> None:
    module = importlib.import_module(f"musical_mycelium.{name}")
    assert module.__doc__, f"{name} must document its contract in its module docstring"


def test_version_is_exposed() -> None:
    import musical_mycelium

    assert musical_mycelium.__version__


def test_graph_does_not_import_ingest() -> None:
    """``ingest`` may depend on ``graph``; never the reverse.

    The direction is not stylistic. ``ingest`` runs locally and does network I/O against Wikidata; if
    ``graph`` imported it, the Lambda container image would carry the ingestion code and its
    dependencies, and the runtime would be one import away from being able to query the internet — the
    exact thing ``.claude/rules/graph-semantics.md`` forbids. The artifact is the seam between them.
    """
    offenders: list[str] = []
    for path in (SRC / "graph").rglob("*.py"):
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            if "musical_mycelium.ingest" in stripped or stripped.startswith("from ..ingest"):
                offenders.append(f"{path.relative_to(SRC)}:{lineno}")

    assert not offenders, f"graph must not import ingest: {offenders}"


def test_nothing_outside_eval_imports_eval() -> None:
    """``eval`` may import anything; nothing may import ``eval``.

    An eval harness that production code depends on stops being an independent measurement.
    """
    offenders: list[str] = []
    for path in SRC.rglob("*.py"):
        if "eval" in path.parts:
            continue
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if not stripped.startswith(("import ", "from ")):
                continue
            if "musical_mycelium.eval" in stripped or stripped.startswith("from .eval"):
                offenders.append(f"{path.relative_to(SRC)}:{lineno}")

    assert not offenders, f"production code must not import eval: {offenders}"
