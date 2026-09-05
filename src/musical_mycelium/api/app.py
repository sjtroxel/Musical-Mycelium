"""The streaming HTTP surface. Thin, and owns no logic.

Everything here is transport: it maps the loop's events onto SSE frames and returns them. There is no
traversal, no gating, and no prose in this module — ``SPEC.md`` requires ``api`` to own no logic, and an
agent that grows inside an HTTP handler is a rewrite rather than a refactor (invariant 6).

**This is a real ASGI server, not a bare Lambda handler**, and that is forced rather than chosen. The
2026-07-31 spike established that Python on Lambda has no native response streaming; the supported path
is FastAPI under uvicorn behind the **Lambda Web Adapter**, with ``AWS_LWA_INVOKE_MODE=response_stream``
and the Function URL at ``RESPONSE_STREAM``. See ``docs/streaming-verification.md``.

**The store is loaded at module scope on purpose.** Under the Web Adapter this runs during the Lambda
INIT phase, before the first request, so the artifact parse never appears in response latency. It is the
cheap half of the cold-start story — the other half being that streaming makes time-to-first-byte the
number a visitor actually experiences (0.214s vs 10.22s in the spike).
"""

from __future__ import annotations

import json
import time
from collections.abc import Iterator
from dataclasses import asdict
from typing import Any

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse

from musical_mycelium.agent import loop as agent_loop
from musical_mycelium.agent.llm import ROLE_SYNTHESIS, ROLE_TRAVERSAL, build_llm
from musical_mycelium.agent.loop import (
    ClaimApproved,
    ClaimRejected,
    Done,
    Event,
    PathWalked,
    Planned,
    Refused,
    Token,
    ToolCalled,
)
from musical_mycelium.agent.tools import default_registry
from musical_mycelium.api.telemetry import emit_query_cost
from musical_mycelium.graph.memory import default_store
from musical_mycelium.graph.schema import Edge

#: Paid during Lambda INIT, not during the first request. See the module docstring.
STORE = default_store()

app = FastAPI(
    title="Musical Mycelium",
    description="A cited-lineage engine for music history.",
    version=STORE.artifact_version,
)

#: ``SPEC.md`` 5.3 fixes ``claim``, ``token``, ``path`` and ``done``. The rest are additive and exist
#: because the demo is watching the machinery work — a visitor seeing ``tool`` and ``rejected`` frames
#: is seeing the grounding actually happen rather than being told about it afterwards.
#:
#: ``plan`` joined at phase 3 step 3 and cost exactly this line: ``render`` is generic over
#: ``EVENT_NAMES`` and ``asdict``, and ``asdict`` walks the nested ``Plan`` and ``PlanStep`` without
#: help. A frame type that needed a handler here would mean ``api`` had grown logic.
EVENT_NAMES: dict[type, str] = {
    Planned: "plan",
    ToolCalled: "tool",
    ClaimApproved: "claim",
    ClaimRejected: "rejected",
    PathWalked: "path",
    Token: "token",
    Refused: "refused",
    Done: "done",
}


def sse(name: str, payload: dict[str, Any]) -> str:
    """One Server-Sent Event frame.

    The trailing blank line is the frame terminator and is not optional; without it a client buffers
    forever and streaming looks broken in a way that resembles a server hang.
    """
    return f"event: {name}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def render(event: Event) -> str:
    """Event to frame. Pure presentation — the loop decided everything; this only names and encodes."""
    name = EVENT_NAMES[type(event)]
    return sse(name, asdict(event))


def stream_answer(query: str) -> Iterator[str]:
    """Run one query, yielding SSE frames as the loop produces events.

    ``time.monotonic`` rather than ``time.time`` because a measured duration must not move when the
    wall clock resyncs — the spike caught WSL2 under-reporting a run by 30% that way, and latency is a
    planned eval metric.
    """
    started = time.monotonic()
    # Two roles through one seam. With ``MYCELIUM_SYNTHESIS_MODEL_ID`` unset both resolve to the same
    # model, so this is the previous behaviour until the day someone sets that variable — no decision
    # about which models is made here or anywhere else in this phase.
    llm = build_llm(role=ROLE_TRAVERSAL)
    synthesis_llm = build_llm(role=ROLE_SYNTHESIS)
    registry = default_registry(STORE)

    for event in agent_loop.run(
        query, store=STORE, llm=llm, registry=registry, synthesis_llm=synthesis_llm
    ):
        if isinstance(event, Done):
            elapsed = round(time.monotonic() - started, 3)
            # `.claude/rules/aws-and-cost.md`: measured token cost to CloudWatch from day one. Emitted
            # here because this is where a query ends and where both models' usage is finally in one
            # place. Writes a log line and makes no AWS call — see `telemetry` for why EMF rather than
            # `put_metric_data`, and why dollars appear only when prices are configured.
            emit_query_cost(
                traversal_usage=event.usage,
                traversal_model_id=event.model_id,
                synthesis_usage=event.synthesis_usage,
                synthesis_model_id=event.synthesis_model_id or event.model_id,
                elapsed_seconds=elapsed,
            )
            payload = asdict(event)
            payload["elapsed_seconds"] = elapsed
            payload["artifact_version"] = STORE.artifact_version
            payload["corpus"] = corpus_summary()
            yield sse("done", payload)
        else:
            yield render(event)


def corpus_summary() -> dict[str, Any]:
    """How much graph there actually is, and how hard each edge was checked.

    On the screen, not in a footnote. ``04`` 4.5 makes coverage a displayed first-class metric, and
    both numbers here are ones a visitor would otherwise have to assume.

    ``verification`` is the honest half. Most of the corpus cleared an automated prose check that
    confirms an article names the object but cannot tell whether the sentence *asserts* influence;
    a minority was read by a human. Publishing the split is what keeps "grounded" meaning traceable
    rather than correct.

    ``coverage`` is the third honest half and the bluntest one. **Re-measured at artifact v0.7.1,
    2026-09-05:** 198 of 675 genres carry no inception date at all, and the top place accounts for 245
    of them. The corpus skews Western, anglophone and recent **by construction**, and ``CLAUDE.md``
    requires that to be visible in output rather than footnoted. *(These read "28 of 169" and "78 of
    the 121" until step 8; the shape of the skew is unchanged and the corpus under it is four times
    larger.)*

    That figure is stated as a **count, not a percentage, deliberately.** It read "77%" here until
    2026-08-07 — the retracted 2026-08-06 number, which came from adding the US and UK country totals
    and double-counting every genre credited to both. The count is the form that made the error visible,
    so the count is the form that ships. **136 genres name neither the US nor the UK**, across 65
    distinct places, and that counterweight is not optional garnish: a concentration figure published
    without it misdescribes the corpus in the other direction.

    ``structure`` is the other honest half, and it is the one a visitor cannot infer from an edge count.
    Relating two things is a capability *within* a component, and ``max_path_hops`` is the deepest chain
    the corpus can actually return. Stating both is what stops an empty answer from reading as a failure
    when it is a boundary. *(This said "the graph is not one organism yet — it is many disconnected
    islands" through v0.5.0's 169 components. At v0.7.1 there are **7**, with 1,465 of 1,479 nodes in
    the largest, because P136 membership connects the artist and genre axes. The sentence was true and
    is not; what remains true is that reachability is a per-component question.)*

    ``corroboration`` is the fourth, and the newest. ``verification`` says how hard **one** source was
    checked; this says whether a **second** agrees. They are different guarantees and collapsing them
    reads as the opposite of the truth. Both ``reciprocal_pairs`` and ``contested_pairs`` are served,
    never one alone — 6 against 2 at v0.7.1 — and ``contested`` carries each disagreement in full so a
    reader is shown both directions and both sources rather than a winner.
    """
    return {
        "artifact_version": STORE.artifact_version,
        "nodes": len(STORE),
        "edges": STORE.edge_count,
        "verification": STORE.verification_counts,
        "structure": STORE.structure.as_dict(),
        "coverage": STORE.coverage.as_dict(),
        "corroboration": {
            **STORE.corroboration,
            # Each disagreement in full. The honest presentation shows BOTH directions and names
            # BOTH sources and picks no winner -- `.claude/rules/grounding-and-claims.md`: flag it,
            # do not resolve it. `verification` rides along on each edge because it is a different
            # question from corroboration and the interface must be able to show two numbers where
            # there are two, never one.
            "contested": [
                {
                    "a": {"id": pair.a, "label": _label(pair.a)},
                    "b": {"id": pair.b, "label": _label(pair.b)},
                    "a_from_b": _contested_edge(pair.a_from_b),
                    "b_from_a": _contested_edge(pair.b_from_a),
                }
                for pair in STORE.contested
            ],
        },
        "predicate": "influenced_by",
    }


def _label(node_id: str) -> str:
    node = STORE.get_node(node_id)
    return node.label if node else node_id


def _contested_edge(edge: Edge) -> dict[str, Any]:
    """One side of a disagreement, as the interface needs to state it."""
    return {
        "subject_id": edge.subject_id,
        "object_id": edge.object_id,
        "source": edge.source,
        "source_id": edge.source_id,
        "verification": edge.verification,
    }


@app.get("/health")
def health() -> dict[str, Any]:
    """Liveness plus the corpus numbers. Also the target for the Lambda Function URL smoke check."""
    return {"status": "ok", "corpus": corpus_summary()}


@app.get("/lineage")
def lineage(q: str = Query(..., min_length=1, description="A genre name.")) -> StreamingResponse:
    """Stream a grounded, cited lineage for one genre.

    ``X-Accel-Buffering: no`` and ``Cache-Control: no-cache`` are there because a proxy that buffers an
    event stream turns streaming back into request/response without any error to notice.
    """
    return StreamingResponse(
        stream_answer(q),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
