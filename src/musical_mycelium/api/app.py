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
from musical_mycelium.agent.llm import build_llm
from musical_mycelium.agent.loop import (
    ClaimApproved,
    ClaimRejected,
    Done,
    Event,
    PathWalked,
    Refused,
    Token,
    ToolCalled,
)
from musical_mycelium.agent.tools import default_registry
from musical_mycelium.graph.memory import default_store

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
EVENT_NAMES: dict[type, str] = {
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
    llm = build_llm()
    registry = default_registry(STORE)

    for event in agent_loop.run(query, store=STORE, llm=llm, registry=registry):
        if isinstance(event, Done):
            payload = asdict(event)
            payload["elapsed_seconds"] = round(time.monotonic() - started, 3)
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
    """
    return {
        "artifact_version": STORE.artifact_version,
        "nodes": len(STORE),
        "edges": STORE.edge_count,
        "verification": STORE.verification_counts,
        "predicate": "influenced_by",
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
