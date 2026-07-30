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

__version__ = "0.0.1"
