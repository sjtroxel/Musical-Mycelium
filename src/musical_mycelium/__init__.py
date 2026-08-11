"""Musical Mycelium — a cited-lineage engine for music history.

A goal-directed research agent that traverses a provenance-backed graph of musical influence and
cites every link it draws.

The five subpackages below are the package boundaries fixed in ``docs/planning/05-EVOLUTION-PLAN.md``
section 2.1. They are a one-way door: an agent that grows inside an HTTP handler is a rewrite, not a
refactor. Keep the dependency direction pointing one way::

    ingest  ->  (artifact in S3)  ->  graph  ->  agent  ->  api
                                       |          |
                                       +----------+---->  eval

``eval`` may import anything. Nothing imports ``eval``.
"""

#: Tracks the ROADMAP product spine (decided 2026-08-11), and must equal ``pyproject.toml``'s
#: ``version``. Two literals in two files is a drift waiting to happen, so
#: ``tests/test_architecture.py`` asserts they match rather than trusting whoever edits one to
#: remember the other. Deliberately a literal and not ``importlib.metadata.version`` — that reads
#: installed distribution metadata, which is stale until reinstall and absent if the package is ever
#: run from a path rather than installed.
__version__ = "0.3.0"
