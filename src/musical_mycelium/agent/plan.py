"""The traversal plan: what the agent says it is going to do, before it does it.

**Explicit, not emergent.** The scope doc leaned this way and phase 3 commits to it. Planning that is
implicit in the tool-call sequence is less code, but it is not inspectable, not evaluable, and not
streamable — and v1.0's guided tour has to narrate *something*. An explicit plan object is what a client
can render, what ``plan_adherence`` is measured against, and what DoD #7's query-type slicing keys off.

Three properties hold and are tested:

1. **The plan is a proposal, not an authority.** The loop still executes tools through the registry; the
   plan is never consulted for control flow. A plan naming an unregistered tool is *reported* — on the
   ``Planned`` event — not crashed on, the same posture ``ToolRegistry.invoke`` already takes.
2. **``query_kind`` is always emitted**, including when parsing fails completely. A run with no
   ``query_kind`` is a run that cannot be sliced, so the degraded value is ``unknown`` rather than absent.
3. **The prompt names no tool of its own.** ``planning_prompt`` renders the tool list *from the registry*,
   so an eighth tool appears in the plan prompt the day it is registered. Hard-coding names here would be
   invariant 4 leaking through the prose door — the same failure v0.1's ``SYSTEM_PROMPT`` had.

**Parsing is deliberately forgiving.** A malformed plan degrades to ``Plan()`` — kind ``unknown``, no
steps — and the run proceeds normally, because the plan was never load-bearing. Unknown JSON keys are
ignored rather than rejected, which is what keeps adding a field to this object a one-paragraph change.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from musical_mycelium.agent.llm import PLANNING_SENTINEL
from musical_mycelium.agent.tools import ToolRegistry

#: The query shapes results are sliced by (DoD #7). Deliberately coarse: these are the shapes the seven
#: registered tools can actually serve, not a taxonomy of questions.
QUERY_KINDS = frozenset({"origins", "lineage", "descendants", "coverage", "unknown"})

#: What an unclassifiable — or unparseable — query reports. Never absent, see property 2 above.
UNKNOWN_QUERY_KIND = "unknown"

#: A model-authored ``reason`` is free text on the wire, so it is collapsed to one line and capped. It is
#: never read for control flow; the cap is about frame size, not meaning.
MAX_REASON_CHARS = 200

#: ``{tools}`` is filled from the registry, never from a literal list — see property 3. The doubled
#: braces are the JSON example surviving ``str.format``.
PLANNING_PROMPT_TEMPLATE = f"""\
Before answering, produce a {PLANNING_SENTINEL} over a graph of documented musical influences: classify \
the question, then list the calls you expect to make, in order.

query_kind is exactly one of:
- origins      what something came out of
- lineage      how two named things connect
- descendants  what came out of something
- coverage     what this graph does and does not hold
- unknown      none of the above, or the question is not about this graph

The calls available to you:
{{tools}}

Reply with JSON and nothing else, in this shape:

{{{{"query_kind": "origins",
  "steps": [{{{{"tool": "<a name from the list above>", "reason": "<one short line>", \
"arguments": {{{{}}}}}}}}]}}}}

Rules:
- Plan only with the names listed above. Do not invent one.
- Leave out an argument you cannot know yet, such as an id you have not resolved.
- This is a proposal. You carry it out yourself afterwards and may depart from it; nothing here binds \
you, and none of it is shown to the user as an answer.
- Do not answer the question here. No prose, no explanation, no markdown fences.
"""


@dataclass(frozen=True, slots=True)
class PlanStep:
    """One intended call. ``reason`` is model-authored prose and is **never used for control flow** —
    it exists so a client can narrate the traversal, which is what v1.0's guided tour needs."""

    tool: str
    reason: str = ""
    arguments: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class Plan:
    """The traversal the agent proposes. Defaults are the degraded plan, and they are legal."""

    query_kind: str = UNKNOWN_QUERY_KIND
    steps: tuple[PlanStep, ...] = ()

    def unregistered(self, registry: ToolRegistry) -> tuple[str, ...]:
        """Names the plan uses that no tool answers to, deduplicated in first-seen order.

        Reported rather than raised. A plan is a proposal, so naming a tool that does not exist is the
        model being wrong about its own toolbox — worth measuring, and not worth failing a run over,
        since the plan never drives execution in the first place.
        """
        return tuple(dict.fromkeys(step.tool for step in self.steps if step.tool not in registry))


def planning_prompt(registry: ToolRegistry) -> str:
    """The planning system prompt for the tools that are actually registered.

    Rendered from ``registry.tool_config()`` — the same block the model already receives — so this
    function has no per-tool knowledge and an eighth tool needs no edit here.

    The full descriptions travel rather than a truncation of them. It is the more expensive choice, and
    a measured one: whether the planning turn earns its token cost is an open question the phase names
    (§7), and answering it against summaries the model never sees during execution would answer a
    different question.
    """
    lines = [
        f"- {spec['toolSpec']['name']}: {spec['toolSpec']['description']}"
        for spec in registry.tool_config()["tools"]
    ]
    return PLANNING_PROMPT_TEMPLATE.format(tools="\n".join(lines))


def parse_plan(text: str) -> Plan:
    """A model turn to a ``Plan``. Never raises; an unusable answer is ``Plan()``.

    Every field is validated independently, so one bad step does not discard the good ones and a bogus
    ``query_kind`` does not discard the steps. That is the difference between a plan object that
    degrades and one that vanishes the moment a model adds a stray sentence.
    """
    payload = _json_object(text)
    if payload is None:
        return Plan()

    kind = payload.get("query_kind")
    query_kind = kind if isinstance(kind, str) and kind in QUERY_KINDS else UNKNOWN_QUERY_KIND

    raw_steps = payload.get("steps")
    steps = [
        step
        for item in (raw_steps if isinstance(raw_steps, list) else [])
        if (step := _step(item)) is not None
    ]
    return Plan(query_kind=query_kind, steps=tuple(steps))


def _step(item: object) -> PlanStep | None:
    """One step, or ``None`` if it is not one. A step with no tool name is not a step."""
    if not isinstance(item, dict):
        return None
    tool = item.get("tool")
    if not isinstance(tool, str) or not tool.strip():
        return None

    reason = item.get("reason")
    arguments = item.get("arguments")
    return PlanStep(
        tool=tool.strip(),
        reason=_one_line(reason) if isinstance(reason, str) else "",
        arguments=dict(arguments) if isinstance(arguments, dict) else {},
    )


def _one_line(reason: str) -> str:
    return " ".join(reason.split())[:MAX_REASON_CHARS]


def _json_object(text: str) -> dict[str, Any] | None:
    """The outermost JSON object in a model turn, or ``None``.

    Slicing from the first ``{`` to the last ``}`` is what absorbs markdown fences, a preamble sentence
    and a trailing sign-off in one rule, without a fence-stripping special case for each. A model that
    wrote prose containing a stray brace produces ``None`` here, which is the degraded plan — the right
    outcome, since the plan was not load-bearing.
    """
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end <= start:
        return None
    try:
        payload = json.loads(text[start : end + 1])
    except ValueError:
        return None
    return payload if isinstance(payload, dict) else None
