"""Architecture tests.

The package boundaries and the dependency direction are one-way doors (``CLAUDE.md`` invariant 6), so
they get a test rather than a convention nobody checks. These are the only tests that exist before there
is anything to test, and that is deliberate: they make CI real from the first commit.
"""

from __future__ import annotations

import importlib
import re
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


def test_package_version_matches_pyproject() -> None:
    """The version is written in two files and they must agree.

    Added 2026-08-11, when the decision that ``pyproject.toml`` follows the ROADMAP product spine made
    the version a thing that gets edited every phase. It had sat at ``0.0.1`` since scaffolding, which
    is exactly why the drift went unnoticed: a number nobody changes cannot disagree with itself.

    This is the cheap enforcement of a convention that would otherwise be remembered or not.
    """
    import tomllib

    import musical_mycelium

    pyproject = SRC.parents[1] / "pyproject.toml"
    declared = tomllib.loads(pyproject.read_text(encoding="utf-8"))["project"]["version"]

    assert musical_mycelium.__version__ == declared, (
        f"__init__.py says {musical_mycelium.__version__!r}, pyproject.toml says {declared!r}"
    )


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


# --- the Makefile is the interface, so its index has to be complete ------------------------------


def test_every_documented_make_target_is_listed_by_make_help() -> None:
    """`make help` filters targets with a regex, and a regex is a place a target can silently vanish.

    Found 2026-08-23: the pattern was ``^[a-zA-Z_-]+:``, which has no digits in its character class,
    so `eval-tier2` was a real, working, documented target that `make help` did not list. Nothing
    failed -- the target simply could not be discovered by the command whose whole job is discovery.

    This compares the two directly: every target line carrying a ``## `` comment must be matched by
    the pattern `help` actually greps with, read out of the Makefile rather than restated here.
    """
    makefile = (Path(__file__).resolve().parents[1] / "Makefile").read_text(encoding="utf-8")

    pattern = re.search(r"grep -hE '([^']+)'", makefile)
    assert pattern is not None, "make help no longer greps for its target list"
    help_filter = re.compile(pattern.group(1))

    documented = re.findall(r"(?m)^([A-Za-z0-9_-]+):.*?## ", makefile)
    assert len(documented) > 10, "the Makefile suddenly documents almost nothing; check the parse"

    invisible = [name for name in documented if not help_filter.search(f"{name}: ## x")]
    assert not invisible, f"documented but absent from make help: {invisible}"
