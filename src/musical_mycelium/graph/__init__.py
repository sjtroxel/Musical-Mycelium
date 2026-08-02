"""The ``GraphStore`` seam — the only way anything reads the graph.

This is the interface that makes the "no managed database" cost decision reversible. v0.1 is an
in-memory dict loaded from a JSON artifact in S3; a 100x corpus later means writing a new implementation
that satisfies the same handful of methods and flipping one wire. The agent, the API, and the eval
harness never learn which backend is behind it.

Contract (``docs/planning/05-EVOLUTION-PLAN.md`` section 3.2): roughly ``get_node``, ``neighbors``,
``search``, ``path``. Storage backend choice (S3 + JSON, SQLite in the image, DuckDB over Parquet,
DynamoDB) is an explicit two-way door — see ``.claude/rules/aws-and-cost.md``.

**Built as of 2026-08-02 (phase 1, steps 3-4).** ``schema.py`` is the artifact contract — node, edge and
manifest shapes, with provenance enforced at construction and the read side of the hash pin. ``store.py``
is the ``GraphStore`` protocol and the ``Direction`` enum. ``memory.py`` is ``InMemoryGraphStore``, the
v0.1 backend, plus the memoised ``default_store()``.

``path`` is declared on the protocol and raises ``NotImplementedError`` in the v0.1 backend. That is
deliberate: phase 5 owns the guided tour, and adding a protocol method later would touch every
implementation.

v0.1 revises one detail above: the artifact ships **inside the container image**, not in S3, because it is
a few KB and that removes an IAM permission and a network call from the cold path. S3 loading is a phase-2
concern and sits behind this same protocol (v0.1 IMPLEMENTATION doc 5.2).
"""
