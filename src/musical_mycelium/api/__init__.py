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

**Built as of 2026-08-02 (phase 1, step 7).** ``app.py`` is the whole surface: ``GET /lineage`` streams
SSE frames, ``GET /health`` reports liveness and the corpus size.

It is a **real ASGI server rather than a bare Lambda handler**, and that is forced rather than chosen —
Python on Lambda has no native response streaming, so invariant 9 requires FastAPI under uvicorn behind
the Lambda Web Adapter (``docs/streaming-verification.md``).

The module maps loop events onto frames and does nothing else. A test asserts it contains no ``gate(``,
no ``.neighbors(``, no ``Claim(`` and no ``ingest`` import, because "owns no logic" is an invariant and
invariants get tests rather than good intentions.

``make dev`` runs it locally on :8000 against the ``local`` LLM stub — no AWS, no credentials, no spend.
"""
