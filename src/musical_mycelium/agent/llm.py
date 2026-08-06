"""The LLM provider seam — ``CLAUDE.md`` invariant 7.

The model and the provider are **configuration, not structure**. Everything above this module talks to
the ``LLM`` protocol; nothing above it imports boto3 or knows what Bedrock is. That is what makes the
Bedrock-quota block survivable: the loop is developed and tested against ``ScriptedLLM`` today and the
deployed product swaps in ``BedrockLLM`` the day the quota clears, with no change above this line.

**This project calls Bedrock through boto3 `bedrock-runtime` Converse, deliberately** — the hand-built
Converse tool loop is the thing the project exists to demonstrate, so a managed agent framework or a
higher-level SDK would hide exactly the engineering that is the point (see ``agent/__init__``).

**Honest status of ``BedrockLLM``: written, never executed.** Every Bedrock daily-token quota on the
account reads 0, so no ``converse`` call has been made. The request and response shapes below follow the
Converse API as documented, but they are **unverified against a live call** — step 1 of the phase-1 plan
(the ``converse`` smoke call) is what confirms them. Treat a shape mismatch here as expected, not as a
surprise, and fix it against the real response rather than by guessing again.
"""

from __future__ import annotations

import json
import os
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

#: The model is genuinely undecided, and the IMPLEMENTATION doc 10 says so: which model, and US vs
#: Global inference profile, cannot be settled until the quota clears and the first ``converse`` call
#: runs. The 8/1 diagnosis sharpened it — if the cross-region row is restored and the on-demand row is
#: not, a cross-region profile becomes mandatory rather than a cost preference.
#:
#: So this is an env var with a documented default, not a hardcoded fact. Set ``MYCELIUM_MODEL_ID`` to
#: whatever the smoke call proves works, and record the answer in the IMPLEMENTATION doc.
DEFAULT_MODEL_ENV = "MYCELIUM_MODEL_ID"
DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

#: Per ``.claude/rules/aws-and-cost.md``: route traversal and tool turns to the cheap model, use a
#: stronger model only for synthesis and judging. Agentic loops are input-heavy — every turn re-sends
#: accumulated context — so the tool loop is where the cheap model earns its keep.
SYNTHESIS_MODEL_ENV = "MYCELIUM_SYNTHESIS_MODEL_ID"

DEFAULT_REGION = "us-east-1"
DEFAULT_MAX_TOKENS = 1024


@dataclass(frozen=True, slots=True)
class Usage:
    """Tokens for one call. Summed across a run and logged — ``.claude/rules/aws-and-cost.md`` requires
    measured token cost from day one so phase 4 has numbers rather than estimates."""

    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens

    def __add__(self, other: Usage) -> Usage:
        return Usage(
            input_tokens=self.input_tokens + other.input_tokens,
            output_tokens=self.output_tokens + other.output_tokens,
        )


@dataclass(frozen=True, slots=True)
class ToolUse:
    """A tool call the model asked for."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(frozen=True, slots=True)
class LLMResponse:
    text: str = ""
    tool_uses: tuple[ToolUse, ...] = ()
    stop_reason: str = "end_turn"
    usage: Usage = field(default_factory=Usage)

    @property
    def wants_tools(self) -> bool:
        return bool(self.tool_uses)


@runtime_checkable
class LLM(Protocol):
    """What the loop needs from a model, and nothing more."""

    @property
    def model_id(self) -> str: ...

    def converse(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tool_config: dict[str, Any] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResponse:
        """One turn. Returns text, tool calls, or both."""
        ...

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Iterator[str]:
        """Text deltas. Used for synthesis, where the API streams tokens to the browser.

        Streaming is invariant 9 and a product decision, not a workaround — it is what keeps a
        multi-step tool loop from exceeding the 29s API Gateway ceiling and what masks cold-start
        latency instead of paying for provisioned concurrency.
        """
        ...


class BedrockLLM:
    """Bedrock Converse via boto3. Written 2026-08-02; **not yet executed against the API.**"""

    def __init__(
        self,
        model_id: str | None = None,
        *,
        region: str = DEFAULT_REGION,
        client: Any = None,
    ) -> None:
        self._model_id = model_id or os.environ.get(DEFAULT_MODEL_ENV, DEFAULT_MODEL_ID)
        self._region = region
        self._client = client

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def client(self) -> Any:
        """Created lazily so importing this module never builds an AWS client or reads credentials."""
        if self._client is None:
            import boto3

            self._client = boto3.client("bedrock-runtime", region_name=self._region)
        return self._client

    def converse(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tool_config: dict[str, Any] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResponse:
        request: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if system:
            request["system"] = [{"text": system}]
        if tool_config:
            request["toolConfig"] = tool_config

        response = self.client.converse(**request)
        return _parse_converse(response)

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Iterator[str]:
        request: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if system:
            request["system"] = [{"text": system}]

        response = self.client.converse_stream(**request)
        for event in response["stream"]:
            delta = event.get("contentBlockDelta", {}).get("delta", {})
            if "text" in delta:
                yield delta["text"]


def _parse_converse(response: dict[str, Any]) -> LLMResponse:
    """Pull text, tool calls and usage out of a Converse response.

    Kept separate from ``BedrockLLM`` so it can be unit-tested against a recorded payload without an
    AWS client — which is the only way to test any of this before the quota clears.
    """
    blocks = response.get("output", {}).get("message", {}).get("content", [])
    text_parts: list[str] = []
    tool_uses: list[ToolUse] = []

    for block in blocks:
        if "text" in block:
            text_parts.append(block["text"])
        elif "toolUse" in block:
            use = block["toolUse"]
            tool_uses.append(
                ToolUse(id=use["toolUseId"], name=use["name"], arguments=use.get("input", {}))
            )

    raw_usage = response.get("usage", {})
    return LLMResponse(
        text="".join(text_parts),
        tool_uses=tuple(tool_uses),
        stop_reason=response.get("stopReason", "end_turn"),
        usage=Usage(
            input_tokens=raw_usage.get("inputTokens", 0),
            output_tokens=raw_usage.get("outputTokens", 0),
        ),
    )


class ScriptedLLM:
    """A model that says exactly what it was told to say, in order.

    Not only a test double. It is what lets the entire loop — tools, gating, synthesis, SSE — be built
    and run locally with no AWS account, no credentials, and no spend, which is why steps 6 and 7 of the
    phase-1 plan are not blocked on the Bedrock quota.

    It records every request it received, so tests can assert on **what the model was shown** — which is
    how the claims-first invariant gets checked rather than assumed.
    """

    def __init__(self, responses: list[LLMResponse], *, model_id: str = "scripted") -> None:
        self._responses = list(responses)
        self._model_id = model_id
        self.requests: list[dict[str, Any]] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    @property
    def exhausted(self) -> bool:
        return not self._responses

    def converse(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tool_config: dict[str, Any] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResponse:
        self.requests.append({"messages": messages, "system": system, "tool_config": tool_config})
        if not self._responses:
            raise AssertionError(
                f"ScriptedLLM ran out of responses after {len(self.requests)} calls; "
                f"the loop asked for more turns than the script provides"
            )
        return self._responses.pop(0)

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Iterator[str]:
        response = self.converse(messages, system=system, max_tokens=max_tokens)
        yield response.text


class LocalLLM:
    """A deterministic stand-in that drives the v0.1 tool sequence without a network call.

    **This is not a model and does not pretend to be one.** It is a development fixture: it walks the
    fixed v0.1 path (resolve, then influences, then stop) and renders prose from a template. It exists
    so ``make dev`` works, so the SSE plumbing can be verified end to end locally, and so none of that
    is blocked on the Bedrock quota.

    It reads the query out of the first user turn and the influence list out of the synthesis prompt.
    Parsing its own prompt format is fine for a fixture and would be indefensible for anything else —
    if this ever starts making decisions a real model should make, delete it rather than extend it.
    """

    def __init__(self, *, model_id: str = "local-stub") -> None:
        self._model_id = model_id
        self.requests: list[dict[str, Any]] = []

    @property
    def model_id(self) -> str:
        return self._model_id

    def converse(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        tool_config: dict[str, Any] | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> LLMResponse:
        self.requests.append({"messages": messages, "system": system, "tool_config": tool_config})
        usage = Usage(input_tokens=_rough_tokens(messages), output_tokens=24)

        pair = _genre_pair(messages)
        if pair is not None:
            return self._lineage_turn(messages, pair, usage)

        resolved = _last_resolved_node(messages)
        if resolved is None and not _has_tool_result(messages):
            return LLMResponse(
                tool_uses=(
                    ToolUse(
                        id="local-1", name="resolve_node", arguments={"name": _query(messages)}
                    ),
                ),
                stop_reason="tool_use",
                usage=usage,
            )
        if resolved is not None and not _has_influences_call(messages):
            return LLMResponse(
                tool_uses=(
                    ToolUse(id="local-2", name="get_influences", arguments={"node_id": resolved}),
                ),
                stop_reason="tool_use",
                usage=usage,
            )
        return LLMResponse(text="Done.", stop_reason="end_turn", usage=usage)

    def _lineage_turn(
        self, messages: list[dict[str, Any]], pair: tuple[str, str], usage: Usage
    ) -> LLMResponse:
        """The second fixed script: resolve both genres, then trace between them.

        Sequenced off the **calls already made**, not off the ids already resolved, so a genre that does
        not resolve falls through to the end turn and the run refuses. Sequencing off resolved ids would
        retry the failed name until ``MAX_TURNS`` and bill for it.
        """
        calls = _tool_call_names(messages)
        resolves = calls.count("resolve_node")
        if resolves < 2:
            return LLMResponse(
                tool_uses=(
                    ToolUse(
                        id=f"local-r{resolves + 1}",
                        name="resolve_node",
                        arguments={"name": pair[resolves]},
                    ),
                ),
                stop_reason="tool_use",
                usage=usage,
            )

        resolved = _resolved_nodes(messages)
        if "trace_lineage" not in calls and len(resolved) == 2:
            return LLMResponse(
                tool_uses=(
                    ToolUse(
                        id="local-t1",
                        name="trace_lineage",
                        arguments={"from_id": resolved[0], "to_id": resolved[1]},
                    ),
                ),
                stop_reason="tool_use",
                usage=usage,
            )
        return LLMResponse(text="Done.", stop_reason="end_turn", usage=usage)

    def stream(
        self,
        messages: list[dict[str, Any]],
        *,
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> Iterator[str]:
        self.requests.append({"messages": messages, "system": system, "tool_config": None})
        prompt = _text_of(messages)

        chain = json.loads(_after(prompt, "Chain: ") or "[]")
        if chain:
            yield f"{str(chain[0]).capitalize()} came out of {chain[1]}"
            for ancestor in chain[2:]:
                yield f", which came out of {ancestor}"
            yield ". Every link above traces to a cited source."
            return

        genre = _after(prompt, "Genre: ")
        influences = json.loads(_after(prompt, "Documented influences: ") or "[]")

        if not influences:
            yield f"The graph records no influences for {genre}."
            return
        listed = (
            influences[0]
            if len(influences) == 1
            else (", ".join(influences[:-1]) + f" and {influences[-1]}")
        )
        # Yielded in pieces so a local run exercises the streaming path rather than sending one blob.
        yield f"{genre.capitalize()} came out of {listed}. "
        yield "Every link above traces to a cited source."


def _text_of(messages: list[dict[str, Any]]) -> str:
    return "\n".join(
        block.get("text", "")
        for message in messages
        for block in message.get("content", [])
        if isinstance(block, dict)
    )


def _query(messages: list[dict[str, Any]]) -> str:
    """The genre the user asked about. Strips the common question wrappers, nothing clever."""
    raw = _text_of(messages).strip().rstrip("?")
    for prefix in ("where did ", "what are the origins of ", "trace the roots of "):
        if raw.lower().startswith(prefix):
            raw = raw[len(prefix) :]
            break
    for suffix in (" come from", " grow out of", " originate"):
        if raw.lower().endswith(suffix):
            raw = raw[: -len(suffix)]
            break
    return raw.strip()


#: Phrasings the fixture treats as "connect these two genres". Both orders appear because the same
#: question is asked from either end, and ``trace_lineage`` searches both directions for that reason.
_LINEAGE_SEPARATORS = (
    " connected to ",
    " connect to ",
    " related to ",
    " come out of ",
    " came out of ",
    " lead to ",
    " to ",
)

_LINEAGE_PREFIXES = (
    "how is ",
    "how are ",
    "how did ",
    "what connects ",
    "trace the lineage from ",
    "trace the line from ",
    "connect ",
)


def _genre_pair(messages: list[dict[str, Any]]) -> tuple[str, str] | None:
    """The two genres a connection question names, or ``None`` if it is not one.

    String matching against a fixed list, which is a fixture's job and would be indefensible in a
    provider that mattered — the point is only that the local stub can drive the multi-hop path so the
    SSE plumbing and the deployed demo are not blocked on Bedrock quota.
    """
    raw = _first_user_text(messages).strip().rstrip("?").strip()
    lowered = raw.lower()
    for prefix in _LINEAGE_PREFIXES:
        if lowered.startswith(prefix):
            raw, lowered = raw[len(prefix) :], lowered[len(prefix) :]
            break
    else:
        return None

    for separator in _LINEAGE_SEPARATORS:
        index = lowered.find(separator)
        if index != -1:
            left, right = raw[:index].strip(), raw[index + len(separator) :].strip()
            if left and right:
                return left, right
    return None


def _tool_call_names(messages: list[dict[str, Any]]) -> list[str]:
    return [
        str(block["toolUse"].get("name", ""))
        for message in messages
        for block in message.get("content", [])
        if isinstance(block, dict) and "toolUse" in block
    ]


def _resolved_nodes(messages: list[dict[str, Any]]) -> list[str]:
    """Every node id resolved so far, in order, deduplicated."""
    found: list[str] = []
    for result in _tool_results(messages):
        for item in result.get("content", []):
            node_id = item.get("json", {}).get("node_id") if isinstance(item, dict) else None
            if node_id and str(node_id) not in found:
                found.append(str(node_id))
    return found


def _first_user_text(messages: list[dict[str, Any]]) -> str:
    for message in messages:
        if message.get("role") == "user":
            return "\n".join(
                block.get("text", "")
                for block in message.get("content", [])
                if isinstance(block, dict)
            )
    return ""


def _after(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].splitlines()[0].strip()


def _tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        block["toolResult"]
        for message in messages
        for block in message.get("content", [])
        if isinstance(block, dict) and "toolResult" in block
    ]


def _has_tool_result(messages: list[dict[str, Any]]) -> bool:
    return bool(_tool_results(messages))


def _last_resolved_node(messages: list[dict[str, Any]]) -> str | None:
    for result in _tool_results(messages):
        for item in result.get("content", []):
            node_id = item.get("json", {}).get("node_id") if isinstance(item, dict) else None
            if node_id:
                return str(node_id)
    return None


def _has_influences_call(messages: list[dict[str, Any]]) -> bool:
    return any(
        isinstance(block, dict) and block.get("toolUse", {}).get("name") == "get_influences"
        for message in messages
        for block in message.get("content", [])
    )


def _rough_tokens(messages: list[dict[str, Any]]) -> int:
    """A stand-in token count for local runs. **Not an estimate of anything** — real numbers arrive
    with the first Bedrock call.

    It measures the whole serialised turn rather than only the text blocks, because an agentic loop's
    input is mostly tool traffic: counting text alone reported 7 tokens for a full run and made local
    output look like the loop was almost free, which is the opposite of the lesson.
    """
    return max(1, len(json.dumps(messages, default=str)) // 4)


def build_llm(provider: str | None = None, **kwargs: Any) -> LLM:
    """The factory invariant 7 asks for. Provider and model are configuration.

    ``MYCELIUM_LLM_PROVIDER=scripted`` runs the whole stack with no AWS at all — the local dev path
    while the Bedrock quota is at zero.
    """
    provider = (provider or os.environ.get("MYCELIUM_LLM_PROVIDER") or "bedrock").lower()

    if provider == "bedrock":
        return BedrockLLM(**kwargs)
    if provider == "local":
        return LocalLLM(**kwargs)
    if provider == "scripted":
        return ScriptedLLM(kwargs.pop("responses", []), **kwargs)
    raise ValueError(f"unknown LLM provider: {provider!r}. Known: bedrock, local, scripted")


def tool_result_message(
    tool_use_id: str, content: Any, *, is_error: bool = False
) -> dict[str, Any]:
    """A Converse ``toolResult`` turn. Here rather than in the loop because it is provider wire format,
    and the loop is not allowed to know about wire formats."""
    return {
        "role": "user",
        "content": [
            {
                "toolResult": {
                    "toolUseId": tool_use_id,
                    "content": [{"json": content}]
                    if not isinstance(content, str)
                    else [{"text": content}],
                    "status": "error" if is_error else "success",
                }
            }
        ],
    }


def assistant_tool_use_message(response: LLMResponse) -> dict[str, Any]:
    """Echo the assistant turn back, tool calls included. Converse requires the full turn in history."""
    content: list[dict[str, Any]] = []
    if response.text:
        content.append({"text": response.text})
    for use in response.tool_uses:
        content.append({"toolUse": {"toolUseId": use.id, "name": use.name, "input": use.arguments}})
    return {"role": "assistant", "content": content}


def user_message(text: str) -> dict[str, Any]:
    return {"role": "user", "content": [{"text": text}]}


def dumps(value: Any) -> str:
    """Deterministic JSON. Sorted keys keep prompts byte-stable, which is what makes prompt caching
    possible later and what keeps eval runs reproducible now."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)
