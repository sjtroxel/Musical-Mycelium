"""The streaming HTTP surface. Thin by design — it owns no domain logic.

Contract:

- **Response streaming, not request/response.** API Gateway REST times out at 29 seconds and a multi-step
  tool loop will regularly exceed it, producing 504s on exactly the queries where the agent works hardest.
  Lambda Function URL with response streaming is the recommendation in
  ``docs/planning/04-RISK-REGISTER.md`` section 3.1. This is a one-way door: retrofitting streaming is real
  rework, and the visible reasoning trace is the best demo the project has.
- The response payload includes the agent's walked **path, in order** — cheap to add now, annoying once the
  schema has consumers (``docs/planning/06-DESIGN-DIRECTION.md`` section 6).
- Product shape is the question-answerer (see ``docs/SPEC.md``): one query in, a streamed cited lineage out.

Nothing is implemented yet. The v0.1 IMPLEMENTATION doc defines the streaming contract, and it should be
defined before anything calls it.
"""
