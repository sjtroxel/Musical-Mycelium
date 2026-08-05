"""The SSE surface.

The point of these tests is that the API is a **wire format and nothing else**. Anything asserting
behaviour here — which claims come back, what the prose says — is really asserting the loop, and belongs
in ``test_agent_loop.py``. What belongs here is frame shape, event naming, and the contract ``SPEC.md``
5.3 fixes, because those are what a client depends on and what is annoying to change later.
"""

from __future__ import annotations

import json
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

os.environ.setdefault("MYCELIUM_LLM_PROVIDER", "local")

from musical_mycelium.api.app import EVENT_NAMES, app, sse
from musical_mycelium.graph.memory import PINNED_ARTIFACT_VERSION, artifact_directory
from musical_mycelium.graph.schema import read_manifest


@pytest.fixture(scope="module")
def client() -> TestClient:
    return TestClient(app)


def frames(body: str) -> list[tuple[str, dict[str, Any]]]:
    """Parse an SSE body into (event, payload) pairs."""
    out: list[tuple[str, dict[str, Any]]] = []
    for block in body.split("\n\n"):
        if not block.strip():
            continue
        lines = dict(line.split(": ", 1) for line in block.splitlines() if ": " in line)
        out.append((lines["event"], json.loads(lines["data"])))
    return out


# --- frame format ---------------------------------------------------------------------------------


def test_a_frame_ends_with_a_blank_line() -> None:
    """Not cosmetic. Without the terminator a client buffers forever, and a stream that never delivers
    looks exactly like a hung server."""
    frame = sse("token", {"text": "hi"})
    assert frame.endswith("\n\n")
    assert frame.startswith("event: token\n")


def test_frames_survive_non_ascii() -> None:
    """``tropicália`` and ``bachatón`` are real genre labels; escaping them would be a wire-format bug
    a client only notices as mojibake."""
    payload = frames(sse("token", {"text": "tropicália"}))[0][1]
    assert payload["text"] == "tropicália"


def test_spec_event_names_are_present() -> None:
    """``SPEC.md`` 5.3 fixes these four. The rest are additive and may change; these may not."""
    assert {"claim", "token", "path", "done"} <= set(EVENT_NAMES.values())


# --- the endpoint ---------------------------------------------------------------------------------


def test_lineage_streams_the_spec_events(client: TestClient) -> None:
    response = client.get("/lineage", params={"q": "acid jazz"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = frames(response.text)
    names = [name for name, _ in events]
    assert "claim" in names
    assert "path" in names
    assert "token" in names
    assert names[-1] == "done", "done must be the last frame or a client cannot tell it finished"


def test_claims_arrive_with_their_citations(client: TestClient) -> None:
    """The demo beat: citations resolve as claims are made. If ``source_ids`` is missing from the wire,
    the product's whole pitch is invisible to the client."""
    events = frames(client.get("/lineage", params={"q": "acid jazz"}).text)
    claims = [payload for name, payload in events if name == "claim"]
    assert claims
    for claim in claims:
        assert claim["claim"]["source_ids"]
        assert claim["claim"]["source_ids"][0].startswith(
            "http://www.wikidata.org/entity/statement/"
        )


def test_the_path_is_on_the_wire_in_order(client: TestClient) -> None:
    """``SPEC.md`` 1 commits to the explorable map and the guided tour; both read this field. Cheap now,
    annoying once the schema has consumers."""
    events = frames(client.get("/lineage", params={"q": "acid jazz"}).text)
    path = next(payload for name, payload in events if name == "path")
    assert path["node_ids"][0] == "Q221772"
    assert len(path["labels"]) == len(path["node_ids"])


def test_a_refusal_streams_as_a_refusal(client: TestClient) -> None:
    """Gold case 5 over HTTP. A refusal is a 200 with a ``refused`` frame — it is a correct answer, not
    an error, and returning 4xx would tell a client the request was malformed."""
    response = client.get("/lineage", params={"q": "the blues"})
    assert response.status_code == 200

    events = frames(response.text)
    names = [name for name, _ in events]
    assert "refused" in names
    assert "claim" not in names

    done = next(payload for name, payload in events if name == "done")
    assert done["claim_count"] == 0


def test_an_unknown_genre_refuses_rather_than_erroring(client: TestClient) -> None:
    events = frames(client.get("/lineage", params={"q": "bebop"}).text)
    refused = next(payload for name, payload in events if name == "refused")
    assert "not in this graph" in refused["reason"]


def test_done_carries_usage_cost_inputs_and_the_pin(client: TestClient) -> None:
    """Token cost is measured and logged from the first call, and every result names the artifact
    version it was produced against."""
    events = frames(client.get("/lineage", params={"q": "acid jazz"}).text)
    done = next(payload for name, payload in events if name == "done")

    assert done["usage"]["input_tokens"] > 0
    assert done["artifact_version"] == PINNED_ARTIFACT_VERSION
    assert done["elapsed_seconds"] >= 0
    assert done["model_id"]


def test_done_states_the_corpus_size(client: TestClient) -> None:
    """Coverage on the screen, not in a footnote — and the number has to be the real one."""
    events = frames(client.get("/lineage", params={"q": "acid jazz"}).text)
    corpus = next(payload for name, payload in events if name == "done")["corpus"]

    assert corpus["nodes"] == pinned_manifest_counts()["nodes"]
    assert corpus["edges"] == pinned_manifest_counts()["edges"]


def test_done_states_how_the_corpus_was_verified(client: TestClient) -> None:
    """The honest half of coverage. A corpus that is mostly machine-verified is noisier per edge, and
    the product says so rather than presenting one undifferentiated edge count."""
    events = frames(client.get("/lineage", params={"q": "acid jazz"}).text)
    corpus = next(payload for name, payload in events if name == "done")["corpus"]

    assert corpus["verification"] == pinned_manifest_counts()["verification"]
    assert sum(corpus["verification"].values()) == corpus["edges"]
    assert corpus["verification"]["HAND"] > 0, "the hand-read edges must not vanish from the corpus"


def pinned_manifest_counts() -> dict[str, Any]:
    """The corpus numbers read straight off disk.

    Deliberately an independent read rather than a hardcoded count. The thing worth testing is that
    the API reports the *actual* corpus, and a literal `21` did that only until the corpus changed —
    at which point it tested nothing and had to be edited. Cross-checking against the artifact
    catches a stale or fabricated number at any corpus size.
    """
    manifest = read_manifest(artifact_directory())
    return {
        "nodes": manifest.node_count,
        "edges": manifest.edge_count,
        "verification": manifest.verification_counts,
    }


def test_an_empty_query_is_rejected(client: TestClient) -> None:
    assert client.get("/lineage", params={"q": ""}).status_code == 422
    assert client.get("/lineage").status_code == 422


def test_health_reports_the_corpus(client: TestClient) -> None:
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["corpus"]["edges"] == pinned_manifest_counts()["edges"]
    assert body["corpus"]["artifact_version"] == PINNED_ARTIFACT_VERSION


# --- the api owns no logic -------------------------------------------------------------------------


def test_api_module_does_not_import_ingest_or_reimplement_the_loop() -> None:
    """``api`` is transport. It may call the loop; it may not contain one.

    ``asdict`` and ``json.dumps`` are the whole of its job — if this module ever grows a ``gate`` call, a
    ``neighbors`` call, or prose assembly, the agent has started growing inside an HTTP handler, which
    ``CLAUDE.md`` invariant 6 calls a rewrite rather than a refactor.
    """
    from pathlib import Path

    source = (
        Path(__file__).resolve().parents[1] / "src" / "musical_mycelium" / "api" / "app.py"
    ).read_text(encoding="utf-8")

    for forbidden in ("musical_mycelium.ingest", "gate(", ".neighbors(", "Claim("):
        assert forbidden not in source, f"api/app.py contains logic it should delegate: {forbidden}"
