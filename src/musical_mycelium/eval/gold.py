"""The gold set's half of the suite: loading the 25 frozen cases, and the trace that drives them.

``suite.py`` is dataset-agnostic by contract, so the two things that are irreducibly *about the gold set*
live here — the same split ``harness.py`` already makes for the adversarial 18. That is a divergence from
the phase 4 implementation doc's file list, which named only ``suite.py`` and ``report.py`` for step 3;
recorded here rather than made silently, because a dataset-agnostic module that grows a ``shape`` branch
has stopped being dataset-agnostic.

**The non-circularity rule, which is the whole reason this module is small.** A scripted run measures the
machinery, not the model — but only if the script is not written from the answer. ``build_script`` reads
``expected_resolution`` and ``expected_terminus`` and **nothing else**. Those two fields are what the
query already names out loud: "where did blues rock come from" names blues rock, and "how does heavy metal
connect to the blues" names both ends. Handing the trace the endpoints is handing it what the reader can
see. Handing it ``expected_path`` would be handing it the answer, and ``traversal_recall`` would then be
measuring this file.

``tests/test_suite.py::test_the_trace_policy_cannot_see_the_answer`` locks that by mutating
``expected_path`` and ``expected_claims`` on a case and asserting the script does not move.

**The policy is uniform and naive on purpose.** One resolve turn, one shape-appropriate tool turn, stop.
It is not tuned per case, so a case that scores badly is a fact about the corpus or the tools rather than
a fact about how hard this file tried. Measured against v0.5.0 on 2026-08-16: every one of the 25 cases
reaches its whole ``expected_path`` under this policy with no off-path visits, which is a real finding
about the gold set and a **warning about the metric** — see ``suite.SCRIPT_DETERMINED``.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from musical_mycelium.agent.llm import LLMResponse, ToolUse, Usage
from musical_mycelium.eval.suite import EvalCase

GOLD_DATASET = Path(__file__).parent / "datasets" / "gold_v0_1.json"

#: Gold ``shape`` to the one-hop tool that answers it. ``path`` maps to ``trace_lineage`` and to the
#: ``lineage`` query kind — the dataset and the planner named the same idea differently, and mapping it
#: here is better than teaching either one the other's vocabulary.
SHAPE_TOOL = {
    "origins": "get_influences",
    "descendants": "get_descendants",
    "path": "trace_lineage",
}

#: Gold ``shape`` to ``Plan.query_kind``. Both vocabularies are closed sets and neither is a superset of
#: the other, so the mapping is explicit and ``load_cases`` refuses a shape missing from it.
SHAPE_QUERY_KIND = {
    "origins": "origins",
    "descendants": "descendants",
    "path": "lineage",
}


@dataclass(frozen=True, slots=True)
class GoldCase:
    """One frozen gold case, flattened out of the JSON.

    ``expected_path`` and ``expected_claims`` are carried because the *suite* scores against them. They
    are deliberately not reachable from ``build_script`` — see the module docstring.
    """

    case_id: str
    query: str
    shape: str
    difficulty: str
    subject_name: str
    subject_id: str
    expected_refusal: bool
    expected_path: tuple[str, ...]
    expected_claims: tuple[tuple[str, str, str], ...]
    #: Present on the five ``path`` cases and nowhere else. ``None`` is the ordinary state.
    terminus_name: str | None = None
    terminus_id: str | None = None
    #: Carried on 20 of 25 and 5 of 25 respectively. Optional in the schema, so optional here: a case
    #: without them is not malformed, and defaulting them to a value would invent a fact.
    axis: str | None = None
    region: str | None = None

    @property
    def query_kind(self) -> str:
        return SHAPE_QUERY_KIND[self.shape]

    def as_eval_case(self) -> EvalCase:
        """The dataset-neutral view the suite scores. **No ``forbidden_triples``** — the gold set plants
        no injections, and claiming an injection-resistance denominator it never earned is exactly the
        inflation ``InjectionResistance.scored_cases`` exists to prevent."""
        return EvalCase(
            case_id=self.case_id,
            query=self.query,
            subject_id=self.subject_id,
            expected_refusal=self.expected_refusal,
            expected_path=self.expected_path,
        )


def load_cases(path: Path = GOLD_DATASET) -> tuple[GoldCase, ...]:
    """Read the frozen set. Raises on an unknown ``shape`` rather than defaulting.

    ``tests/test_gold_set.py`` already makes the same check, and it is repeated here for the reason that
    file gives: two of the shape branches read the same edge rows in opposite directions, so a shape that
    falls through to a default does not raise — it answers the wrong question and passes.
    """
    payload = json.loads(path.read_text(encoding="utf-8"))
    cases = []
    for case in payload["cases"]:
        shape = case["shape"]
        if shape not in SHAPE_TOOL:
            raise ValueError(f"{case['case_id']}: unknown shape {shape!r}")
        terminus = case.get("expected_terminus") or {}
        if shape == "path" and not terminus:
            raise ValueError(f"{case['case_id']}: a path case needs an expected_terminus")
        cases.append(
            GoldCase(
                case_id=case["case_id"],
                query=case["query"],
                shape=shape,
                difficulty=case["difficulty"],
                subject_name=case["expected_resolution"]["name"],
                subject_id=case["expected_resolution"]["node_id"],
                expected_refusal=case["expected_refusal"],
                expected_path=tuple(case["expected_path"]),
                expected_claims=tuple(
                    (claim["subject_id"], claim["predicate"], claim["object_id"])
                    for claim in case["expected_claims"]
                ),
                terminus_name=terminus.get("name"),
                terminus_id=terminus.get("node_id"),
                axis=case.get("axis"),
                region=case.get("region"),
            )
        )
    return tuple(cases)


def dataset_version(path: Path = GOLD_DATASET) -> tuple[str, str]:
    """``(version, artifact_version_pin)``. Read rather than hardcoded so a moved pin cannot go unnoticed
    in a result file that claims to have been produced against the old one."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload["version"], payload["artifact_version_pin"]


def trace_of(case: GoldCase) -> tuple[tuple[str, dict[str, Any]], ...]:
    """The tool calls one case's trace makes, as ``(name, arguments)`` pairs.

    Split out from ``build_script`` so a test can read the policy without parsing an ``LLMResponse``
    stream, and so the one thing worth asserting about it — that it names only the endpoints — is
    assertable directly.

    A ``path`` case resolves **both** endpoints in a single turn. That is the honest shape of the trace
    (a model asked to connect two things looks up two things) and it exercises the multi-tool turn that
    broke against the first real model on 2026-08-11, which a single-tool-per-turn script never touches.
    """
    tool = SHAPE_TOOL[case.shape]
    if case.shape == "path":
        assert case.terminus_id is not None  # load_cases refuses a path case without one
        return (
            ("resolve_node", {"name": case.subject_name}),
            ("resolve_node", {"name": case.terminus_name}),
            (tool, {"from_id": case.subject_id, "to_id": case.terminus_id}),
        )
    return (
        ("resolve_node", {"name": case.subject_name}),
        (tool, {"node_id": case.subject_id}),
    )


def build_script(case: GoldCase, *, prose: str = "A grounded answer.") -> list[LLMResponse]:
    """A plan turn, the trace's tool turns, a closing text turn, then the synthesis stream.

    Same shape as ``harness.build_script`` and for the same reason: **the plan turn is always first.** A
    script without it does not fail — its first tool turn is silently eaten by the planner and the run
    exercises the wrong sequence, which is how two tests went green on the wrong thing in phase 3.

    **No ``asserted_premise``.** The adversarial scripts assert one because that is the single channel by
    which a model states a triple of its own, and attacking it is the point there. A gold case asks a
    question rather than asserting an answer, so a premise here would put a claim in front of the gate
    that the case never made — and ``edge_groundedness`` would then be scoring this function.

    The turns are grouped so that the ``path`` cases issue their two ``resolve_node`` calls in one turn.
    """
    trace = trace_of(case)
    turns: tuple[tuple[tuple[str, dict[str, Any]], ...], ...] = (
        (trace[:2], trace[2:]) if case.shape == "path" else tuple((call,) for call in trace)
    )

    payload = {
        "query_kind": case.query_kind,
        "steps": [{"tool": name} for name, _ in trace],
    }
    script = [LLMResponse(text=json.dumps(payload), usage=Usage(80, 15))]
    for index, turn in enumerate(turns):
        script.append(
            LLMResponse(
                tool_uses=tuple(
                    ToolUse(id=f"t{index}_{offset}", name=name, arguments=arguments)
                    for offset, (name, arguments) in enumerate(turn)
                ),
                stop_reason="tool_use",
                usage=Usage(120, 20),
            )
        )
    script.append(LLMResponse(text="Done looking.", stop_reason="end_turn", usage=Usage(150, 25)))
    script.append(LLMResponse(text=prose))
    return script


def eval_cases(cases: Sequence[GoldCase] | None = None) -> tuple[EvalCase, ...]:
    """The whole set in the suite's neutral shape."""
    return tuple(case.as_eval_case() for case in (cases if cases is not None else load_cases()))
