"""The ``GraphStore`` seam — the only way anything reads the graph.

This is the interface that makes the "no managed database" cost decision reversible. v0.1 is an
in-memory dict loaded from a JSON artifact in S3; a 100x corpus later means writing a new implementation
that satisfies the same handful of methods and flipping one wire. The agent, the API, and the eval
harness never learn which backend is behind it.

Contract (``docs/planning/05-EVOLUTION-PLAN.md`` section 3.2): roughly ``get_node``, ``neighbors``,
``search``, ``path``. Storage backend choice (S3 + JSON, SQLite in the image, DuckDB over Parquet,
DynamoDB) is an explicit two-way door — see ``.claude/rules/aws-and-cost.md``.

Nothing is implemented yet. The v0.1 IMPLEMENTATION doc defines the protocol and picks the first backend.
"""
