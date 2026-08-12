"""The LLM provider seam — ``CLAUDE.md`` invariant 7.

The model and the provider are **configuration, not structure**. Everything above this module talks to
the ``LLM`` protocol; nothing above it imports boto3 or knows what Bedrock is. That is what made the
2026-07-30 to 08-11 Bedrock-quota block survivable: the loop was developed and tested against
``ScriptedLLM`` throughout, and swapping in ``BedrockLLM`` needed no change above this line.

**This project calls Bedrock through boto3 `bedrock-runtime` Converse, deliberately** — the hand-built
Converse tool loop is the thing the project exists to demonstrate, so a managed agent framework or a
higher-level SDK would hide exactly the engineering that is the point (see ``agent/__init__``).

**Honest status of ``BedrockLLM``: executed against the live API on 2026-08-11.** All three shapes in
this module were written from the Converse documentation on 2026-08-02 without a live call to check
them, and all three were confirmed correct when the quota was restored:

- ``converse`` / ``_parse_converse`` — text, ``stop_reason`` and ``Usage`` parse from a real response.
- ``stream`` — text deltas followed by a **non-empty** ``Usage`` from the trailing ``metadata`` event.
  This was the highest-risk guess in the file: the degraded path is a silent empty ``Usage``, which
  would have under-reported cost forever without ever raising.
- ``toolConfig`` — a real ``stop_reason='tool_use'`` turn parsed into a ``ToolUse``.

**What that verification does not cover:** everything proven here is single-turn. The loop above this
seam was verified separately on 2026-08-12 — plan, multi-tool traversal, gate and synthesis against a
real model — and finding the multi-tool-turn bug is what that run bought. What remains unproven is
*measured* real-model behaviour: refusal accuracy and traversal recall are recorded only against scripted
traces. See ``docs/KNOWN-GAPS.md``.
"""

from __future__ import annotations

import json
import os
from collections.abc import Generator, Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable

#: **Settled 2026-08-11 by the first live call.** The default below — Claude Haiku 4.5 on the ``us.``
#: geo cross-region inference profile — is confirmed working on this account. The 8/1 worry that a
#: cross-region profile might become *mandatory* rather than a cost preference did not materialise:
#: quota was restored on both the geo and global cross-region rows (5M TPM / 10 RPM each).
#:
#: **RPM is the binding constraint, not tokens.** 5M tokens per minute against 10 requests per minute
#: means an agentic loop runs out of requests long before it runs out of tokens, so anything that fans
#: out — the eval suite above all — needs throttling and backoff rather than more context budget.
#:
#: It stays an env var with a documented default, not a hardcoded fact, because the model choice is a
#: two-way door. Set ``MYCELIUM_MODEL_ID`` to override.
DEFAULT_MODEL_ENV = "MYCELIUM_MODEL_ID"
DEFAULT_MODEL_ID = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

#: Per ``.claude/rules/aws-and-cost.md``: route traversal and tool turns to the cheap model, use a
#: stronger model only for synthesis and judging. Agentic loops are input-heavy — every turn re-sends
#: accumulated context — so the tool loop is where the cheap model earns its keep.
SYNTHESIS_MODEL_ENV = "MYCELIUM_SYNTHESIS_MODEL_ID"

DEFAULT_REGION = "us-east-1"
DEFAULT_MAX_TOKENS = 1024

#: A marker the planning system prompt embeds so ``LocalLLM`` can tell a planning turn from a tool turn.
#:
#: It lives here, in the seam, rather than in ``agent/plan.py`` where the prompt is written, for one
#: reason: this module deliberately imports nothing from the rest of the project. That isolation is what
#: makes the provider swappable, and spending it on a string constant would be a poor trade. ``plan.py``
#: imports it from here and builds the prompt around it, so rewording the prompt cannot silently break
#: the fixture's detection.
PLANNING_SENTINEL = "TRAVERSAL PLAN"


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
    ) -> Generator[str, None, Usage]:
        """Text deltas, **returning the usage they cost**. Used for synthesis, where the API streams
        tokens to the browser.

        Streaming is invariant 9 and a product decision, not a workaround — it is what keeps a
        multi-step tool loop from exceeding the 29s API Gateway ceiling and what masks cold-start
        latency instead of paying for provisioned concurrency.

        **The return value is why the signature is ``Generator`` and not ``Iterator``** (phase 3 step 6).
        Until then this yielded text and reported nothing, so synthesis tokens never reached
        ``Done.usage`` at all — a local run served five model calls and totalled four. That was survivable
        while one model did everything and stops being survivable the moment traversal and synthesis run
        on **different** models, because two models price differently and a single summed number is then
        not merely incomplete, it is uncostable. Callers read it with ``usage = yield from llm.stream(…)``
        (PEP 380), which keeps the stream lazy — the value arrives on exhaustion, not up front.
        """
        ...


class BedrockLLM:
    """Bedrock Converse via boto3. Written 2026-08-02; **first executed against the live API
    2026-08-11**, single-turn, streaming, and tool-use, all three shapes confirmed."""

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
        """Created lazily so importing this module never builds an AWS client or reads credentials.

        **Adaptive retries, because RPM is this account's binding constraint — measured 2026-08-11.**
        Haiku 4.5 is provisioned at 5M TPM against **10 RPM**, and one query is not one request: a plan
        turn, a tool turn per hop, and a synthesis turn. A single run can approach the per-minute
        request ceiling on its own, and two at once will pass it. This was not theoretical — the first
        run of the live loop tests threw ``ThrottlingException`` on exactly this.

        ``adaptive`` mode adds client-side rate limiting on top of retries, so the client slows itself
        when it sees throttling rather than hammering and failing. The default ``legacy`` mode retries
        far less and has no rate limiter, which is what produced the failure.

        Note the interaction with the Lambda timeout, which is a cost control: retries consume wall
        clock, and a streamed response bills for the full duration. Backoff is the correct behaviour
        here, but it is not free, and that tension is real rather than resolved.
        """
        if self._client is None:
            import boto3
            from botocore.config import Config

            self._client = boto3.client(
                "bedrock-runtime",
                region_name=self._region,
                config=Config(retries={"max_attempts": 8, "mode": "adaptive"}),
            )
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
    ) -> Generator[str, None, Usage]:
        """Text deltas, then the usage Bedrock reports in its trailing ``metadata`` event.

        **Verified against a live call 2026-08-11**: 8 deltas followed by a populated ``Usage``. This
        was the shape most worth checking, because its failure mode is silent. The degraded value is an
        empty ``Usage``, chosen so a mismatch under-reports cost rather than crashing a user's answer
        half-streamed — which also means a wrong shape here would never have raised, and cost tracking
        would have read zero forever. It does not.
        """
        request: dict[str, Any] = {
            "modelId": self._model_id,
            "messages": messages,
            "inferenceConfig": {"maxTokens": max_tokens},
        }
        if system:
            request["system"] = [{"text": system}]

        usage = Usage()
        response = self.client.converse_stream(**request)
        for event in response["stream"]:
            delta = event.get("contentBlockDelta", {}).get("delta", {})
            if "text" in delta:
                yield delta["text"]
            if "metadata" in event:
                usage = _usage_of(event["metadata"])
        return usage


def _parse_converse(response: dict[str, Any]) -> LLMResponse:
    """Pull text, tool calls and usage out of a Converse response.

    Kept separate from ``BedrockLLM`` so it can be unit-tested against a recorded payload without an
    AWS client. That was the only way to test any of this during the quota block, and it remains the
    right default afterwards: these tests stay free and offline rather than billing a call per run.
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

    return LLMResponse(
        text="".join(text_parts),
        tool_uses=tuple(tool_uses),
        stop_reason=response.get("stopReason", "end_turn"),
        usage=_usage_of(response),
    )


def _usage_of(payload: dict[str, Any]) -> Usage:
    """A Converse ``usage`` block as a ``Usage``.

    One function knows the wire key names because the same block arrives in two envelopes: at the top
    level of a ``converse`` response, and inside the trailing ``metadata`` event of a ``converse_stream``
    one. **Both envelopes verified live 2026-08-11.** Missing keys still degrade to zero rather than
    raising: a shape that drifts should under-report cost, not destroy an answer.
    """
    raw = payload.get("usage", {})
    return Usage(
        input_tokens=raw.get("inputTokens", 0),
        output_tokens=raw.get("outputTokens", 0),
    )


class ScriptedLLM:
    """A model that says exactly what it was told to say, in order.

    Not only a test double. It is what lets the entire loop — tools, gating, synthesis, SSE — be built
    and run locally with no AWS account, no credentials, and no spend. That kept steps 6 and 7 of the
    phase-1 plan moving through the quota block, and it is still how the suite runs by default now that
    Bedrock works: 623 tests that cost nothing beat 623 tests that bill.

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
    ) -> Generator[str, None, Usage]:
        """One scripted response as a single chunk, and the usage that response declared.

        Reporting the script's own ``Usage`` rather than a zero is what lets a test assert that
        traversal and synthesis were billed to **different** models — give the two scripts distinct
        numbers and the split in ``Done`` is checkable without a model or a dollar.
        """
        response = self.converse(messages, system=system, max_tokens=max_tokens)
        yield response.text
        return response.usage


class LocalLLM:
    """A deterministic stand-in that drives the v0.1 tool sequence without a network call.

    **This is not a model and does not pretend to be one.** It is a development fixture: it walks the
    fixed v0.1 path (resolve, then influences, then stop) and renders prose from a template. It exists
    so ``make dev`` works and so the SSE plumbing can be verified end to end locally. That was
    load-bearing during the quota block; afterwards it is what keeps local development free.

    **It is still the deployed provider.** Bedrock access was restored 2026-08-11, but the Lambda has
    not been redeployed onto it, so the public URL's prose remains a template and its token counts
    remain synthetic. Do not describe the live demo as model-generated until that redeploy happens.

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

        if system is not None and PLANNING_SENTINEL in system:
            return self._plan_turn(messages, usage)

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

    def _plan_turn(self, messages: list[dict[str, Any]], usage: Usage) -> LLMResponse:
        """The plan for the one path this fixture can walk, as JSON on a text turn.

        It states the sequence it is *about* to hard-code below, which is the honest thing for a fixture
        to do and is also why local runs give a plan-adherence of exactly 1.0 — a number that means
        nothing until a real model produces it, and is labelled as a fixture value wherever it appears.
        """
        if _genre_pair(messages) is not None:
            plan = {
                "query_kind": "lineage",
                "steps": [
                    {"tool": "resolve_node", "reason": "resolve the first name"},
                    {"tool": "resolve_node", "reason": "resolve the second name"},
                    {"tool": "trace_lineage", "reason": "walk between the two ids"},
                ],
            }
        else:
            plan = {
                "query_kind": "origins",
                "steps": [
                    {"tool": "resolve_node", "reason": "resolve the name asked about"},
                    {"tool": "get_influences", "reason": "list what it came out of"},
                ],
            }
        return LLMResponse(text=json.dumps(plan), stop_reason="end_turn", usage=usage)

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
    ) -> Generator[str, None, Usage]:
        self.requests.append({"messages": messages, "system": system, "tool_config": None})
        # Same stand-in count ``converse`` uses. **Not an estimate of anything** — but it must not be
        # zero, or the local path would report synthesis as free and reintroduce, in the provider the
        # deployed URL still runs, exactly the blind spot step 6 exists to close.
        usage = Usage(input_tokens=_rough_tokens(messages), output_tokens=24)
        prompt = _text_of(messages)

        # The reversal framing, rendered rather than skipped: ``v0.3.0-local`` ships on this provider,
        # so a fixture that quietly dropped the correction would make DoD #13 untestable in the one
        # configuration anybody can actually run today. It states the documented orientation and says
        # nothing at all about the direction the question assumed — see ``INVERTED_PREMISE_PROMPT``.
        reversed_premise = json.loads(_after(prompt, "Asked as: ") or "[]")
        preface = "In this graph the influence runs the other way: " if reversed_premise else ""

        chain = json.loads(_after(prompt, "Chain: ") or "[]")
        if chain:
            yield f"{preface}{_lead(str(chain[0]), preface)} came out of {chain[1]}"
            for ancestor in chain[2:]:
                yield f", which came out of {ancestor}"
            yield ". Every link above traces to a cited source."
            return usage

        genre = _after(prompt, "Genre: ")
        influences = json.loads(_after(prompt, "Documented influences: ") or "[]")

        if not influences:
            yield f"The graph records no influences for {genre}."
            return usage
        listed = (
            influences[0]
            if len(influences) == 1
            else (", ".join(influences[:-1]) + f" and {influences[-1]}")
        )
        # Yielded in pieces so a local run exercises the streaming path rather than sending one blob.
        yield f"{preface}{_lead(genre, preface)} came out of {listed}. "
        yield "Every link above traces to a cited source."
        return usage


def _text_of(messages: list[dict[str, Any]]) -> str:
    """Every text block, delimiters removed.

    ``LocalLLM`` parses the prompt format this module produces, and that format now marks untrusted
    spans — so the fixture has to read the current format rather than the one that existed before step
    5. Unwrapping here rather than at each call site keeps the fixture's string matching working on the
    user's actual words: ``<question>Where did bebop come from?</question>`` starts with ``<``, and every
    prefix test in ``_query`` and ``_genre_pair`` would otherwise silently stop matching.
    """
    return undelimit_text(
        "\n".join(
            block.get("text", "")
            for message in messages
            for block in message.get("content", [])
            if isinstance(block, dict)
        )
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
    SSE plumbing and the deployed demo need no model call at all.
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
    """The first user turn, delimiters removed. Same reason as ``_text_of``."""
    for message in messages:
        if message.get("role") == "user":
            return undelimit_text(
                "\n".join(
                    block.get("text", "")
                    for block in message.get("content", [])
                    if isinstance(block, dict)
                )
            )
    return ""


def _lead(label: str, preface: str) -> str:
    """A label at the head of a sentence, or mid-sentence after a preface. Capitalisation only."""
    return label if preface else label.capitalize()


def _after(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].splitlines()[0].strip()


def _tool_results(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tool results with their delimiters removed, keys included.

    ``tool_result_message`` wraps both, so an undelimited read would be looking for ``node_id`` in a
    payload whose key is now ``<data>node_id</data>`` and would find nothing — the fixture would resolve
    a name and then behave as though it never had.
    """
    return [
        undelimit(block["toolResult"])
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


#: The two jobs a run gives a model, and the axis the cheap/strong split runs along
#: (``.claude/rules/aws-and-cost.md``). ``traversal`` is the tool loop: many turns, input-heavy, each one
#: re-sending the whole accumulated context, which is where a cheap model earns its keep. ``synthesis``
#: is one short call over an already-approved claim set, which is where a stronger one is affordable.
ROLE_TRAVERSAL = "traversal"
ROLE_SYNTHESIS = "synthesis"

#: Which env var names the model for each role. ``synthesis`` falls back to the traversal model when
#: ``MYCELIUM_SYNTHESIS_MODEL_ID`` is unset, so **one configured model still runs the whole product** —
#: the split is an optimisation to switch on, never a second thing you are obliged to configure before
#: anything works.
_ROLE_MODEL_ENV = {
    ROLE_TRAVERSAL: (DEFAULT_MODEL_ENV,),
    ROLE_SYNTHESIS: (SYNTHESIS_MODEL_ENV, DEFAULT_MODEL_ENV),
}


def model_id_for(role: str) -> str:
    """The configured model id for one role, or the documented default.

    **No model is chosen here and none is chosen in this phase.** Which model, and US-vs-Global
    inference profile, cannot be settled until a ``converse`` call succeeds — see §10 of the phase 3
    IMPLEMENTATION doc. This resolves configuration; it does not make a decision.
    """
    if role not in _ROLE_MODEL_ENV:
        raise ValueError(f"unknown model role: {role!r}. Known: {sorted(_ROLE_MODEL_ENV)}")
    for name in _ROLE_MODEL_ENV[role]:
        configured = os.environ.get(name)
        if configured:
            return configured
    return DEFAULT_MODEL_ID


def build_llm(provider: str | None = None, *, role: str = ROLE_TRAVERSAL, **kwargs: Any) -> LLM:
    """The factory invariant 7 asks for. Provider and model are configuration.

    ``MYCELIUM_LLM_PROVIDER=scripted`` runs the whole stack with no AWS at all — the free local dev
    path, and the default for the test suite.

    ``role`` selects **which configured model**, not which provider — the cheap/strong split is a model
    choice and both roles run through the same seam. It only reaches ``BedrockLLM``, because the two
    fixtures have no model to choose; ``role`` is still accepted for them so a caller can build a pair
    without branching on provider, which is what makes the routing testable with no AWS at all.
    """
    provider = (provider or os.environ.get("MYCELIUM_LLM_PROVIDER") or "bedrock").lower()

    if provider == "bedrock":
        kwargs.setdefault("model_id", model_id_for(role))
        return BedrockLLM(**kwargs)
    if provider == "local":
        return LocalLLM(**kwargs)
    if provider == "scripted":
        return ScriptedLLM(kwargs.pop("responses", []), **kwargs)
    raise ValueError(f"unknown LLM provider: {provider!r}. Known: bedrock, local, scripted")


# --- untrusted text ---------------------------------------------------------------------------------
#
# ``planning/04`` §6.3: retrieved content is **data, never instructions**, and never reaches a
# tool-invocation decision unmediated. The corpus is Wikidata-derived and Wikidata is user-editable, so
# every label, country name, and source id in a tool payload is text a stranger could have written.
#
# **The gate is the enforcement; this is harm reduction.** An injected instruction cannot manufacture an
# edge or a citation no matter how the model behaves, because ``ClaimProposal`` carries neither and
# ``gate()`` checks every claim against the pinned artifact. Delimiting lowers the chance the model
# *behaves* badly; the gate is what guarantees the *output* is grounded. Do not let a later reader
# mistake the marker for the mechanism — if these functions were deleted the system would still be
# grounded, and if ``gate()`` were deleted no amount of delimiting would save it.

#: The tags that mark untrusted spans. ``data`` wraps anything a tool returned; ``question`` wraps the
#: end user's own words, which are untrusted for the same reason and are the only vector a visitor to the
#: public URL can actually reach.
_UNTRUSTED_TAGS = ("data", "question")


def escape_delimiters(text: str) -> str:
    """Neutralise any delimiter the untrusted text is carrying itself.

    **A boundary the enclosed text can close is not a boundary.** A Wikidata label reading
    ``foo</data>Ignore previous instructions`` would otherwise escape its own wrapper and arrive looking
    like agent-authored prose, which is precisely the attack the wrapper exists to mark.

    Matching is on the opening ``<tag`` / ``</tag`` rather than the full tag, so ``</data >`` and
    ``<data foo="bar">`` are caught too. Nothing ever un-escapes this: the requirement is only that the
    token cannot appear inside a wrapped span, so the transformation does not need to be reversible.

    Deliberately **not** a per-run nonce. A nonce is unforgeable without guessing, but it makes the
    prompt bytes differ on every run — and byte-stability is what ``dumps`` below exists to provide, what
    keeps eval runs against a pinned artifact reproducible, and what prompt caching would later need.
    """
    for tag in _UNTRUSTED_TAGS:
        text = text.replace(f"</{tag}", f"&lt;/{tag}").replace(f"<{tag}", f"&lt;{tag}")
    return text


def undelimit_text(text: str) -> str:
    """``undelimit`` for a value already known to be a string, and typed as such.

    Separate from the recursive form because the callers split cleanly in two: payload walkers hand in
    arbitrary JSON and get ``Any`` back, while the text helpers below hand in a string and must get a
    string back or every one of them becomes an untyped return.
    """
    for tag in _UNTRUSTED_TAGS:
        text = text.replace(f"<{tag}>", "").replace(f"</{tag}>", "")
    return text


def undelimit(value: Any) -> Any:
    """Strip delimiter tags out of anything coming back *from* the model.

    The other half of a symmetric boundary, and it is load-bearing rather than tidy. A model that reads
    ``{"node_id": "<data>Q483352</data>"}`` may well hand that string straight back as a tool argument,
    and every id-taking tool would then answer ``unknown node`` — delimiting would have broken the walk
    it was protecting. Marking is for the model's benefit on the way out; the marks are not part of the
    value on the way in.

    Applied at ``ToolRegistry.invoke``, which is one chokepoint for all seven tools and needs no
    per-tool knowledge, so invariant 4 is untouched.
    """
    if isinstance(value, str):
        return undelimit_text(value)
    if isinstance(value, dict):
        return {undelimit(key): undelimit(item) for key, item in value.items()}
    if isinstance(value, list):
        return [undelimit(item) for item in value]
    return value


def delimit(value: Any) -> Any:
    """Wrap every string in a payload as data, structure preserved.

    Recursive over dicts and lists because the payloads are nested, and **dict keys are wrapped too**:
    ``corpus_coverage`` returns a ``Counter`` keyed by country names read straight out of the artifact,
    so a key is as much an injection vector as a value is. Wrapping only values would leave a hole whose
    existence depends on which tool you happen to be looking at, and the whole point of doing this at one
    chokepoint is that it needs no such knowledge.

    Numbers, booleans and ``None`` pass through untouched — they carry no text and wrapping them would
    turn a count into a string and break every payload that reports one.
    """
    if isinstance(value, str):
        return f"<data>{escape_delimiters(value)}</data>"
    if isinstance(value, dict):
        return {
            delimit(key) if isinstance(key, str) else key: delimit(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [delimit(item) for item in value]
    if isinstance(value, tuple):
        return [delimit(item) for item in value]
    return value


@dataclass(frozen=True, slots=True)
class ToolOutcome:
    """One tool's result paired with the id of the call that asked for it.

    Exists so the loop can accumulate a turn's results without touching wire format. The loop knows a
    tool ran and what it returned; it does not know what a ``toolResult`` block looks like, and that
    boundary is what keeps invariant 4 honest.
    """

    tool_use_id: str
    content: Any
    is_error: bool = False


def tool_results_message(outcomes: Sequence[ToolOutcome]) -> dict[str, Any]:
    """**One** Converse user turn carrying **every** toolResult for the assistant turn that requested
    them. Here rather than in the loop because it is provider wire format, and the loop is not allowed
    to know about wire formats.

    **It takes a sequence, and there is deliberately no single-result variant.** A model may ask for two
    or more tools in one turn, and Converse requires all of that turn's results in a single user message
    as multiple content blocks — it validates the set, and it also demands strict user/assistant
    alternation, so appending one message per result is invalid twice over. That was a real bug
    (2026-08-11): the loop appended per result, which is the shape a singular helper invites. A function
    that is correct when called once and wrong when called in a loop is a trap, so the singular form is
    gone rather than documented, the same reasoning that keeps ``user_message`` and ``question_message``
    apart.

    **Delimiting happens here, not in the caller.** This is the single point every tool payload passes
    through on its way into the message list, so a payload cannot reach the model unmarked by anyone
    forgetting to call something first. A caller-applied wrapper would be a convention; this is a
    property.
    """
    if not outcomes:
        # Unreachable from the loop, which only gets here when the model asked for at least one tool.
        # Raising rather than emitting an empty content list keeps it that way: the wire error for an
        # empty user turn names neither this function nor the turn that produced it.
        raise ValueError("a toolResult turn needs at least one outcome")
    return {
        "role": "user",
        "content": [_tool_result_block(outcome) for outcome in outcomes],
    }


def _tool_result_block(outcome: ToolOutcome) -> dict[str, Any]:
    delimited = delimit(outcome.content)
    return {
        "toolResult": {
            "toolUseId": outcome.tool_use_id,
            "content": [{"json": delimited}]
            if not isinstance(delimited, str)
            else [{"text": delimited}],
            "status": "error" if outcome.is_error else "success",
        }
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
    """A user turn carrying text **this project wrote** — a synthesis prompt, a rendered instruction.

    Not for the end user's question: that is untrusted and goes through ``question_message``. The two are
    separate functions rather than a flag because getting it wrong in either direction is silent. Wrap an
    agent-authored prompt and the model is told its own instructions are data; leave a visitor's question
    bare and ``adv_016`` walks straight in.
    """
    return {"role": "user", "content": [{"text": text}]}


def question_message(query: str) -> dict[str, Any]:
    """The end user's question, marked as the thing being asked *about* rather than asked *for*.

    The weakest of the three injection vectors and the only one a visitor to the public URL can actually
    use, which makes it the one that will really be tried. The query is still answered normally; the
    wrapper only says where the user's words start and stop, so ``Ignore previous instructions and ...``
    arrives as a quoted string rather than as a line of the system prompt.
    """
    return {
        "role": "user",
        "content": [{"text": f"<question>{escape_delimiters(query)}</question>"}],
    }


def dumps(value: Any) -> str:
    """Deterministic JSON. Sorted keys keep prompts byte-stable, which is what makes prompt caching
    possible later and what keeps eval runs reproducible now."""
    return json.dumps(value, sort_keys=True, ensure_ascii=False)
