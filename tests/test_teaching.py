"""Teaching: the gate, the three teaching tools, and the prose. Phase 7.6 step 7.

``studied_with`` (P1066) became a claim a user can be told in this step, and the whole risk of that is
one sentence: **"Beethoven was influenced by Haydn" is fluent, cited, and false as stated when the
source says "student of"**, and every grounding metric would score it perfectly. The tests below are
named after the trap each one closes (``phase-7.6-classical-lineage-IMPLEMENTATION.md`` §3), so a
future reader can find why each exists.

**The disclosure test (DoD 4) is the centre of this file.** ``test_no_teaching_claim_is_ever_narrated_
as_influence`` renders the synthesis prompt for every teaching claim set the corpus can produce, and
parses it with its own literal strings rather than the loop's constants, so a change to a heading in
``loop.py`` cannot make the check agree with itself. **What it cannot test is the model ignoring the
instruction**; that residual risk is watched by the live capture and phase 7.7's judged pass, and is
recorded here rather than claimed away.

These tests read **artifact v0.10.0 directly, before the pin moves** at step 9, because v0.7.1 holds no
teaching edge and a test of teaching on it would pass vacuously. ``TEACHING_ARTIFACT`` becomes the pin
at step 9 and this constant goes away with ``UNPINNED_CUTS``.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from collections.abc import Iterator
from itertools import pairwise
from typing import Any

import pytest

from musical_mycelium.agent import loop as agent_loop
from musical_mycelium.agent.claims import (
    ALLOWED_PREDICATES,
    Claim,
    ClaimProposal,
    RejectionReason,
    gate,
)
from musical_mycelium.agent.llm import (
    LLMResponse,
    ScriptedLLM,
    ToolOutcome,
    ToolUse,
    Usage,
    dumps,
    tool_results_message,
)
from musical_mycelium.agent.loop import (
    REASON_RUN_FOUND_NONE,
    SYSTEM_PROMPT,
    ApprovedClaimSet,
    ClaimApproved,
    ClaimRejected,
    Done,
    Refused,
    Token,
    ToolCalled,
    _graph_holds_lineage,
    descent_is_approved,
    run,
    synthesize,
)
from musical_mycelium.agent.tools import ToolRegistry, default_registry
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import (
    NODE_KIND_ARTIST,
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    PREDICATE_PLAYS_GENRE,
    PREDICATE_STUDIED_WITH,
    VERIFICATION_HAND,
    VERIFICATION_MEMBERSHIP_BARE,
    VERIFICATION_TEACHING_PROSE_AUTO,
)
from musical_mycelium.graph.store import Direction

#: The unpinned cut these tests read. See the module docstring.
TEACHING_ARTIFACT = "0.10.0"

#: Read off artifact v0.10.0 on 2026-09-11, never recalled (``reference-never-recall-wikidata-qids``).
BEETHOVEN, HAYDN, CZERNY, LISZT = "Q255", "Q7349", "Q215333", "Q41309"
SALIERI, CLEMENTI, NEEFE, HUMMEL = "Q51088", "Q193673", "Q213556", "Q151953"
FUX = "Q311378"  # Haydn was influenced by Fux; nobody here studied with him
ELSNER = "Q471647"  # three students, no recorded teacher
BLUES = "Q9759"
STUDIED, INFLUENCED = PREDICATE_STUDIED_WITH, PREDICATE_INFLUENCED_BY

BEETHOVENS_TEACHERS = {CLEMENTI, NEEFE, SALIERI, HAYDN}


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory(TEACHING_ARTIFACT))


@pytest.fixture(scope="module")
def registry(store: InMemoryGraphStore) -> ToolRegistry:
    return default_registry(store)


def test_the_teaching_artifact_is_the_one_these_tests_mean(store: InMemoryGraphStore) -> None:
    assert store.artifact_version == TEACHING_ARTIFACT
    assert store.neighbors(BEETHOVEN, Direction.INFLUENCED_BY, predicates=frozenset({STUDIED}))


# --- trap 1: the gate can see a teaching edge, and the two predicates never approve each other ----


def test_the_gate_approves_a_real_teaching_claim_with_the_teaching_tier(
    store: InMemoryGraphStore,
) -> None:
    """Trap 1. Widening ``ALLOWED_PREDICATES`` alone would have rejected this ``NOT_IN_GRAPH``,
    because the store walks ``INFLUENCE_ONLY`` unless told otherwise."""
    decision = gate([ClaimProposal(BEETHOVEN, STUDIED, HAYDN)], store)

    assert not decision.rejected
    (claim,) = decision.approved
    assert claim.verification == VERIFICATION_TEACHING_PROSE_AUTO
    (source,) = claim.source_ids
    assert source.startswith(f"http://www.wikidata.org/entity/statement/{BEETHOVEN}-")


@pytest.mark.parametrize(
    ("proposal", "why"),
    [
        (ClaimProposal(CZERNY, INFLUENCED, BEETHOVEN), "teaching only: no influence edge"),
        (ClaimProposal(BEETHOVEN, INFLUENCED, SALIERI), "teaching only: no influence edge"),
        (ClaimProposal(HAYDN, INFLUENCED, CZERNY), "no edge of any kind"),
        (ClaimProposal(HAYDN, STUDIED, BEETHOVEN), "teaching reversed"),
        (ClaimProposal(HAYDN, STUDIED, FUX), "influence only: no teaching edge"),
    ],
)
def test_one_predicate_never_approves_the_other(
    store: InMemoryGraphStore, proposal: ClaimProposal, why: str
) -> None:
    """The exact predicate match in ``_find_edge``. Czerny studied with Beethoven, and the gate must not
    let that approve "Czerny was influenced by Beethoven"; Haydn was influenced by Fux, and that must
    not approve "Haydn studied with Fux"."""
    decision = gate([proposal], store)
    assert not decision.approved, why
    assert decision.rejected[0].reason == RejectionReason.NOT_IN_GRAPH


def test_membership_is_still_not_a_claim(store: InMemoryGraphStore) -> None:
    """``plays_genre`` stays out of ``ALLOWED_PREDICATES``: phase 8's to open, not this phase's."""
    assert PREDICATE_PLAYS_GENRE not in ALLOWED_PREDICATES
    edge = store.neighbors(
        BEETHOVEN, Direction.INFLUENCED_BY, predicates=frozenset({PREDICATE_PLAYS_GENRE})
    )[0]
    decision = gate([ClaimProposal(BEETHOVEN, PREDICATE_PLAYS_GENRE, edge.object_id)], store)
    assert decision.rejected[0].reason == RejectionReason.UNSUPPORTED_PREDICATE


# --- trap 17: the teaching tools, and that teachers and students are not swapped ------------------


def test_get_teachers_answers_who_beethoven_studied_with(registry: ToolRegistry) -> None:
    result = registry.invoke("get_teachers", {"node_id": BEETHOVEN})

    assert not result.is_error
    assert {t["node_id"] for t in result.content["teachers"]} == BEETHOVENS_TEACHERS
    assert result.content["count"] == 4
    assert {(p.subject_id, p.predicate) for p in result.proposals} == {(BEETHOVEN, STUDIED)}
    assert {p.object_id for p in result.proposals} == BEETHOVENS_TEACHERS
    assert result.chain == (), "several teachers are a fan-out, not an ordered descent"


def test_get_students_is_oriented_by_the_edge_not_the_argument(registry: ToolRegistry) -> None:
    """Trap 17's other half. Built from ``node_id``, "who studied with Haydn" would propose that Haydn
    studied with each of his students."""
    result = registry.invoke("get_students", {"node_id": HAYDN})

    assert BEETHOVEN in {s["node_id"] for s in result.content["students"]}
    assert all(p.object_id == HAYDN and p.predicate == STUDIED for p in result.proposals)
    assert BEETHOVEN in {p.subject_id for p in result.proposals}


def test_teachers_and_students_are_exact_inverses(registry: ToolRegistry) -> None:
    for teacher in BEETHOVENS_TEACHERS:
        students = registry.invoke("get_students", {"node_id": teacher}).content["students"]
        assert BEETHOVEN in {s["node_id"] for s in students}, teacher


def test_every_teaching_proposal_survives_the_gate(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """A tool that proposed claims the gate rejects would inflate the rejection stream refusal accuracy
    is measured on. Liszt has 41 recorded students and five teachers."""
    proposals = [
        *registry.invoke("get_teachers", {"node_id": LISZT}).proposals,
        *registry.invoke("get_students", {"node_id": LISZT}).proposals,
    ]
    decision = gate(proposals, store)
    assert len(proposals) == 46
    assert not decision.rejected
    assert all(c.verification == VERIFICATION_TEACHING_PROSE_AUTO for c in decision.approved)


def test_the_influence_tools_still_return_influence_only(registry: ToolRegistry) -> None:
    """Beethoven has four teachers and one influence. The influence tools must not start returning
    teachers because the store now holds them; D5 changes what the model is TOLD, not what they return."""
    influences = registry.invoke("get_influences", {"node_id": BEETHOVEN})
    assert [i["node_id"] for i in influences.content["influences"]] == [HAYDN]
    assert {p.predicate for p in influences.proposals} == {INFLUENCED}

    descendants = registry.invoke("get_descendants", {"node_id": BEETHOVEN})
    assert {p.predicate for p in descendants.proposals} <= {INFLUENCED}
    assert CZERNY not in {d["node_id"] for d in descendants.content["descendants"]}


def test_an_artist_with_no_teachers_gets_an_empty_list_not_an_error(
    registry: ToolRegistry,
) -> None:
    result = registry.invoke("get_teachers", {"node_id": ELSNER})
    assert result.content == {"teachers": [], "count": 0}
    assert not result.is_error
    assert not result.proposals


@pytest.mark.parametrize("tool", ["get_teachers", "get_students"])
def test_the_fan_out_teaching_tools_reject_an_unknown_node(
    registry: ToolRegistry, tool: str
) -> None:
    result = registry.invoke(tool, {"node_id": "Q00000000"})
    assert result.is_error
    assert "resolve_node" in result.content["error"]


def test_get_influences_tells_the_model_to_ask_for_teachers_and_report_them_as_teachers(
    registry: ToolRegistry,
) -> None:
    """His decision D5. A description change, not a loop change."""
    specs = {s["toolSpec"]["name"]: s["toolSpec"] for s in registry.tool_config()["tools"]}
    description = specs["get_influences"]["description"]
    assert "get_teachers" in description
    assert "as teachers, never as influences" in description


def test_every_teaching_tool_says_teaching_is_not_influence(registry: ToolRegistry) -> None:
    specs = {s["toolSpec"]["name"]: s["toolSpec"] for s in registry.tool_config()["tools"]}
    for name in ("get_teachers", "get_students"):
        assert "This is teaching, not influence" in specs[name]["description"], name
    assert (
        "never describe a teaching hop as influence"
        in (specs["trace_teaching_lineage"]["description"])
    )


# --- trace_teaching_lineage: typed hops, D4 --------------------------------------------------------


@pytest.mark.parametrize("arguments", [(LISZT, HAYDN), (HAYDN, LISZT)])
def test_a_pure_teaching_chain_is_found_in_either_argument_order(
    store: InMemoryGraphStore, registry: ToolRegistry, arguments: tuple[str, str]
) -> None:
    """Liszt studied with Czerny, who studied with Hummel, who studied with Haydn. Descendant-first
    whichever way the question put the names, exactly as ``trace_lineage`` behaves."""
    result = registry.invoke(
        "trace_teaching_lineage", {"from_id": arguments[0], "to_id": arguments[1]}
    )

    assert result.chain == (LISZT, CZERNY, HUMMEL, HAYDN)
    assert result.visited == result.chain
    assert {p.predicate for p in result.proposals} == {STUDIED}
    assert not gate(list(result.proposals), store).rejected


def test_a_hop_the_corpus_holds_under_both_predicates_is_proposed_under_both(
    registry: ToolRegistry,
) -> None:
    """Beethoven studied with Haydn and was influenced by him, as two separately sourced edges.
    Proposing whichever edge the walk crossed first would narrate half of that by accident of
    artifact order."""
    result = registry.invoke("trace_teaching_lineage", {"from_id": BEETHOVEN, "to_id": HAYDN})

    assert result.chain == (BEETHOVEN, HAYDN)
    assert {p.predicate for p in result.proposals} == {INFLUENCED, STUDIED}
    assert result.content["path"][0]["predicates"] == [INFLUENCED, STUDIED]


def test_a_mixed_chain_carries_every_hops_own_predicates(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """Czerny to Fux: teaching, teaching, then Haydn's influence by Fux. Each hop's reported predicates
    must be exactly the lineage edges the artifact holds for that pair, no more and no fewer."""
    result = registry.invoke("trace_teaching_lineage", {"from_id": CZERNY, "to_id": FUX})
    lineage = frozenset({STUDIED, INFLUENCED})

    hop_predicates = []
    for (subject, obj), hop in zip(pairwise(result.chain), result.content["path"], strict=True):
        held = sorted(
            edge.predicate
            for edge in store.neighbors(subject, Direction.INFLUENCED_BY, predicates=lineage)
            if edge.object_id == obj
        )
        assert hop["predicates"] == held, (subject, obj)
        hop_predicates.append(tuple(held))

    assert len(set(hop_predicates)) > 1, "the fixture must actually be a mixed chain"
    assert result.chain[0] == CZERNY and result.chain[-1] == FUX
    assert not gate(list(result.proposals), store).rejected


def test_trace_lineage_is_still_influence_only(registry: ToolRegistry) -> None:
    """D4: ``trace_lineage`` is not touched, so no gold path case can acquire a route through a
    teaching hop. Liszt and Haydn connect only through teachers."""
    result = registry.invoke("trace_lineage", {"from_id": LISZT, "to_id": HAYDN})
    assert result.content["path"] == []


def test_trace_teaching_lineage_refuses_genres(registry: ToolRegistry) -> None:
    result = registry.invoke("trace_teaching_lineage", {"from_id": BLUES, "to_id": HAYDN})
    assert result.is_error
    assert "trace_lineage" in result.content["error"]


# --- trap 4: a teaching claim cannot establish an influence premise in reverse ---------------------


def _claim(subject: str, predicate: str, obj: str) -> Claim:
    verification = VERIFICATION_TEACHING_PROSE_AUTO if predicate == STUDIED else VERIFICATION_HAND
    return Claim(subject, predicate, obj, (f"stmt/{subject}-{obj}",), verification)


def test_descent_reads_influence_claims_only() -> None:
    teaching = (_claim(CZERNY, STUDIED, BEETHOVEN),)
    assert not descent_is_approved(CZERNY, BEETHOVEN, teaching)
    assert descent_is_approved(CZERNY, BEETHOVEN, (_claim(CZERNY, INFLUENCED, BEETHOVEN),))


def test_a_teaching_claim_cannot_be_used_to_correct_an_influence_question() -> None:
    with pytest.raises(ValueError, match="not established in reverse"):
        ApprovedClaimSet(
            claims=(_claim(CZERNY, STUDIED, BEETHOVEN),), inverted_premise=(BEETHOVEN, CZERNY)
        )


def plan_turn(query_kind: str, *tools: str, premise: tuple[str, str] | None = None) -> LLMResponse:
    """The planning turn every run opens with (see ``test_agent_loop.plan_turn`` for why it is never
    skipped)."""
    payload: dict[str, Any] = {"query_kind": query_kind, "steps": [{"tool": t} for t in tools]}
    if premise is not None:
        payload["asserted_premise"] = {"subject": premise[0], "object": premise[1]}
    return LLMResponse(text=json.dumps(payload), usage=Usage(80, 15))


def tool_turn(*uses: tuple[str, dict[str, Any]]) -> LLMResponse:
    return LLMResponse(
        tool_uses=tuple(
            ToolUse(id=f"t{i}", name=name, arguments=args) for i, (name, args) in enumerate(uses)
        ),
        stop_reason="tool_use",
        usage=Usage(100, 20),
    )


END = LLMResponse(text="Found them.", stop_reason="end_turn", usage=Usage(200, 30))


def test_an_influence_question_is_not_corrected_on_the_strength_of_a_teaching_claim(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """Trap 4, end to end. "Did Czerny influence Beethoven?" asserts that Beethoven came out of Czerny.
    The corpus holds only that Czerny STUDIED WITH Beethoven. Before the fix, that teaching claim
    established the reverse and the answer opened "in this graph the influence runs the other way":
    telling the user Beethoven influenced Czerny, which no source says."""
    traversal = ScriptedLLM(
        [
            plan_turn(
                "lineage",
                "resolve_node",
                "get_students",
                premise=("Ludwig van Beethoven", "Carl Czerny"),
            ),
            tool_turn(("resolve_node", {"name": "Ludwig van Beethoven"})),
            tool_turn(("get_students", {"node_id": BEETHOVEN})),
            END,
        ]
    )
    synthesis = ScriptedLLM([LLMResponse(text="prose")])
    events = list(
        run(
            "Did Czerny influence Beethoven?",
            store=store,
            llm=traversal,
            registry=registry,
            synthesis_llm=synthesis,
        )
    )

    premise = ClaimProposal(BEETHOVEN, INFLUENCED, CZERNY)
    assert any(isinstance(e, ClaimRejected) and e.rejection.proposal == premise for e in events)
    assert any(
        isinstance(e, ClaimApproved) and e.claim.triple == (CZERNY, STUDIED, BEETHOVEN)
        for e in events
    )
    prompt = _sent(synthesis)
    assert "Asked as" not in prompt
    assert "runs the other way" not in prompt


# --- trap 8: refusals stop asserting influence -----------------------------------------------------


def test_a_refused_teaching_question_does_not_call_the_graph_empty(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """Elsner has three recorded students and no teacher. Refusing "who did Elsner study with" is
    correct; telling the user the graph holds nothing about him is not."""
    assert _graph_holds_lineage(store, [ELSNER])
    traversal = ScriptedLLM(
        [
            plan_turn("origins", "resolve_node", "get_teachers"),
            tool_turn(("resolve_node", {"name": "Józef Elsner"})),
            tool_turn(("get_teachers", {"node_id": ELSNER})),
            END,
        ]
    )
    events = list(
        run("Who did Józef Elsner study with?", store=store, llm=traversal, registry=registry)
    )

    refusal = next(e for e in events if isinstance(e, Refused))
    assert refusal.reason == REASON_RUN_FOUND_NONE
    assert "teaching" in refusal.reason
    prose = "".join(e.text for e in events if isinstance(e, Token))
    assert prose.startswith("This run found no sourced answer")


def test_the_refusal_reasons_name_both_relationships() -> None:
    for reason in (agent_loop.REASON_NO_LINEAGE, agent_loop.REASON_RUN_FOUND_NONE):
        assert "influence or teaching" in reason, reason


# --- the system prompt and the plan -----------------------------------------------------------------


def test_the_system_prompt_says_teaching_is_never_influence() -> None:
    assert "studied with another, report it as study, never as an influence" in SYSTEM_PROMPT


# --- trap 3 and DoD 4: the prose ------------------------------------------------------------------
#
# Every literal below is written out here rather than imported from ``loop.py``, deliberately. The
# checker must be able to disagree with the code; one that read the loop's own constants would agree
# with any edit to them.

ORIGINS_HEADINGS = {"Documented influences": INFLUENCED, "Documented teachers": STUDIED}
FAN_IN_HEADINGS = {
    "Documented as coming out of it": INFLUENCED,
    "Documented as influenced by them": INFLUENCED,
    "Documented as influenced by it": INFLUENCED,
    "Documented as having studied with them": STUDIED,
}
#: Artist-axis renderings: teaching only ever runs between artists.
RELATIONSHIP = {
    (INFLUENCED,): "was influenced by",
    (STUDIED,): "studied with",
    (INFLUENCED, STUDIED): "was influenced by and studied with",
}
#: Wording that may appear in a prompt only if the claim set holds an influence claim.
INFLUENCE_WORDING = (
    "was influenced by",
    "came out of",
    "coming out of",
    "chain of influence",
    "Documented influences",
    "Documented as influenced",
)
TEACHING_CLAUSE = "Studying with someone is teaching, not influence."
CHAIN_SUMMARY_BAN = "Do not describe the chain as a whole as a line, lineage or chain of influence"


def _sent(llm: ScriptedLLM) -> str:
    text: str = llm.requests[-1]["messages"][0]["content"][0]["text"]
    return text


def _prompt(claim_set: ApprovedClaimSet) -> str:
    llm = ScriptedLLM([LLMResponse(text="prose")])
    list(synthesize(claim_set, llm))
    return _sent(llm)


def _claim_set(
    store: InMemoryGraphStore, claims: tuple[Claim, ...], chain: tuple[str, ...] = ()
) -> ApprovedClaimSet:
    """Built the way ``run`` builds one: labels and kinds for the approved endpoints and nothing else."""
    ends = {node for claim in claims for node in (claim.subject_id, claim.object_id)}
    return ApprovedClaimSet(
        claims=claims,
        labels={node: _label(store, node) for node in ends},
        kinds={node: _kind(store, node) for node in ends},
        chain=chain,
    )


def _label(store: InMemoryGraphStore, node_id: str) -> str:
    node = store.get_node(node_id)
    assert node is not None
    return node.label


def _kind(store: InMemoryGraphStore, node_id: str) -> str:
    node = store.get_node(node_id)
    assert node is not None
    return node.kind


def misnarrations(prompt: str, claim_set: ApprovedClaimSet) -> list[str]:
    """Every way ``prompt`` could lead a model to say a claim in another claim's words. Empty is a pass.

    Parsed from the prompt the model actually receives, and checked against the approved claims:
    each listed name sits under a heading of its own claim's predicate, each typed hop carries exactly
    the predicates approved for that pair, a single-verb chain is used only when every hop agrees,
    and a teaching-only prompt contains no influence wording at all.
    """
    problems: list[str] = []
    label = claim_set.label_of
    head, _, body = prompt.rpartition("\n\n")
    predicates = {claim.predicate for claim in claim_set.claims}
    by_pair: dict[tuple[str, str], set[str]] = defaultdict(set)
    for claim in claim_set.claims:
        by_pair[(claim.subject_id, claim.object_id)].add(claim.predicate)

    if STUDIED in predicates and TEACHING_CLAUSE not in head:
        problems.append("a claim set holding teaching was not told teaching is not influence")
    if INFLUENCED not in predicates:
        problems.extend(
            f"influence wording {word!r} in a prompt with no influence claim"
            for word in INFLUENCE_WORDING
            if word in prompt
        )

    if body.startswith("Hops: "):
        hops = json.loads(body.removeprefix("Hops: "))
        expected = [
            [label(a), RELATIONSHIP[tuple(sorted(by_pair[(a, b)]))], label(b)]
            for a, b in pairwise(claim_set.chain)
        ]
        if hops != expected:
            problems.append(f"typed hops {hops} are not the approved {expected}")
        if CHAIN_SUMMARY_BAN not in head:
            problems.append("a mixed chain was not forbidden from being summed up as influence")
    elif body.startswith("Chain: "):
        kinds = {tuple(sorted(by_pair[pair])) for pair in pairwise(claim_set.chain)}
        if len(kinds) != 1 or len(only := next(iter(kinds))) != 1:
            problems.append(f"a chain whose hops are {kinds} was given one verb for every hop")
        elif only == (STUDIED,) and "Each name listed studied with the one after it" not in head:
            problems.append("a teaching chain was not narrated as study")
        elif only == (INFLUENCED,) and "chain of influence" not in head:
            problems.append("an influence chain lost its wording")
    else:
        origins = claim_set.subject_id is not None
        headings = ORIGINS_HEADINGS if origins else FAN_IN_HEADINGS
        listed: dict[str, list[str]] = defaultdict(list)
        for line in body.split("\n")[1:]:
            heading, _, names = line.partition(": ")
            if heading not in headings:
                problems.append(f"heading {heading!r} is not one this shape may use")
                continue
            listed[headings[heading]].extend(json.loads(names))
        for predicate in predicates | set(listed):
            expected_names = sorted(
                label(claim.object_id if origins else claim.subject_id)
                for claim in claim_set.claims
                if claim.predicate == predicate
            )
            if sorted(listed[predicate]) != expected_names:
                problems.append(
                    f"{predicate} lists {sorted(listed[predicate])}, approved {expected_names}"
                )
    return problems


def _teaching_claim_sets(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> Iterator[tuple[str, ApprovedClaimSet]]:
    """Every teaching claim set the tools can hand synthesis on this corpus, labelled by shape.

    For every artist touching a teaching edge: teachers alone, teachers with influences (the D5
    fan-out), students alone, students with descendants, and every chain from them to a node two
    lineage hops away through ``trace_teaching_lineage``. Proposals are gated exactly as ``run`` gates
    them, so nothing here is hand-built.
    """
    lineage = frozenset({STUDIED, INFLUENCED})
    teaching_artists = sorted(
        {
            node
            for edge in store._artifact.edges
            if edge.predicate == STUDIED
            for node in (edge.subject_id, edge.object_id)
        }
    )
    for artist in teaching_artists:
        teachers = registry.invoke("get_teachers", {"node_id": artist}).proposals
        influences = registry.invoke("get_influences", {"node_id": artist}).proposals
        students = registry.invoke("get_students", {"node_id": artist}).proposals
        descendants = registry.invoke("get_descendants", {"node_id": artist}).proposals
        for shape, proposals in (
            ("teachers", teachers),
            ("teachers+influences", (*teachers, *influences)),
            ("students", students),
            ("students+descendants", (*students, *descendants)),
        ):
            claims = gate(list(proposals), store).approved
            if claims:
                yield shape, _claim_set(store, claims)

        targets = {
            far.object_id
            for near in store.neighbors(artist, Direction.INFLUENCED_BY, predicates=lineage)
            for far in store.neighbors(near.object_id, Direction.INFLUENCED_BY, predicates=lineage)
        } - {artist}
        for target in sorted(targets):
            result = registry.invoke("trace_teaching_lineage", {"from_id": artist, "to_id": target})
            if not result.chain:
                continue
            claims = gate(list(result.proposals), store).approved
            if any(claim.predicate == STUDIED for claim in claims):
                yield "chain", _claim_set(store, claims, chain=result.chain)


def test_no_teaching_claim_is_ever_narrated_as_influence(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """**DoD 4, the disclosure test.** Shaped like ``ContestedDisclosure``: a property over a
    population rather than a rate, blocking on **zero** misnarrations, with the population reported so
    an empty one cannot pass.

    Minimums are floors, rounded down from what v0.10.0 produced on 2026-09-11, so that losing most of
    a shape (a mixed chain that stops being mixed, a fan-in that stops being built) fails rather than
    narrowing the test quietly.
    """
    silent: list[tuple[str, list[str]]] = []
    shapes: Counter[str] = Counter()
    for shape, claim_set in _teaching_claim_sets(store, registry):
        predicates = {claim.predicate for claim in claim_set.claims}
        if STUDIED not in predicates:
            continue
        kind = shape
        if shape == "chain":
            mixed = len({p for _, _, preds in claim_set.hops for p in preds}) > 1
            kind = "mixed chain" if mixed else "teaching chain"
        elif len(predicates) > 1:
            kind = f"mixed {shape}"
        shapes[kind] += 1
        if problems := misnarrations(_prompt(claim_set), claim_set):
            silent.append((kind, problems))

    assert not silent, f"{len(silent)} misnarrated claim sets, first: {silent[:3]}"
    minimums = {
        "teachers": 1500,
        "students": 800,
        "mixed teachers+influences": 10,
        "mixed students+descendants": 10,
        "teaching chain": 1000,
        "mixed chain": 50,
    }
    short = {kind: shapes[kind] for kind, floor in minimums.items() if shapes[kind] < floor}
    assert not short, f"shapes below their floor: {short}; population was {dict(shapes)}"


def test_the_checker_catches_a_teaching_claim_under_an_influence_heading(
    store: InMemoryGraphStore,
) -> None:
    """A metric you have not tried to break is not a metric (``.claude/rules/evals.md``). The checker
    is handed the exact prompt the pre-fix code would have built for Beethoven's teachers, and must
    object to it."""
    claim_set = _claim_set(store, gate([ClaimProposal(BEETHOVEN, STUDIED, HAYDN)], store).approved)
    old_prompt = (
        "Write one sentence stating what Ludwig van Beethoven was influenced by, using only the "
        "influences listed below. Name every one of them. Add nothing else.\n\n"
        'Artist: Ludwig van Beethoven\nDocumented influences: ["Joseph Haydn"]'
    )
    problems = misnarrations(old_prompt, claim_set)
    assert any("was influenced by" in p for p in problems)
    assert any("not told teaching is not influence" in p for p in problems)
    # The heading itself is a legal origins heading. What is wrong is who is under it: Haydn listed
    # as an influence, where the only approved claim is that Beethoven studied with him.
    assert "influenced_by lists ['Joseph Haydn'], approved []" in problems
    assert "studied_with lists [], approved ['Joseph Haydn']" in problems


def test_the_checker_catches_a_mixed_chain_told_with_one_verb(store: InMemoryGraphStore) -> None:
    claims = gate(
        [ClaimProposal(CZERNY, STUDIED, BEETHOVEN), ClaimProposal(BEETHOVEN, INFLUENCED, HAYDN)],
        store,
    ).approved
    claim_set = _claim_set(store, claims, chain=(CZERNY, BEETHOVEN, HAYDN))
    one_verb = (
        f"Write one or two sentences tracing the chain of influence below. {TEACHING_CLAUSE}\n\n"
        f"Chain: {dumps(['Carl Czerny', 'Ludwig van Beethoven', 'Joseph Haydn'])}"
    )
    assert any("given one verb for every hop" in p for p in misnarrations(one_verb, claim_set))


def test_who_did_beethoven_study_with_is_answered_as_study(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """**Step 7's done-when**: a scripted run of "who did Beethoven study with" passes locally.

    Scripted, so the model's choices are authored: this shows the gate, the tool and the prose wiring,
    not that a real model picks ``get_teachers``. That is the live capture's job at step 10.
    """
    traversal = ScriptedLLM(
        [
            plan_turn("origins", "resolve_node", "get_teachers"),
            tool_turn(("resolve_node", {"name": "Ludwig van Beethoven"})),
            tool_turn(("get_teachers", {"node_id": BEETHOVEN})),
            END,
        ]
    )
    synthesis = ScriptedLLM([LLMResponse(text="Beethoven studied with four teachers.")])
    events = list(
        run(
            "Who did Beethoven study with?",
            store=store,
            llm=traversal,
            registry=registry,
            synthesis_llm=synthesis,
        )
    )

    assert [e.name for e in events if isinstance(e, ToolCalled)] == [
        "resolve_node",
        "get_teachers",
    ]
    approved = [e.claim for e in events if isinstance(e, ClaimApproved)]
    assert {c.triple for c in approved} == {(BEETHOVEN, STUDIED, t) for t in BEETHOVENS_TEACHERS}
    assert all(c.verification == VERIFICATION_TEACHING_PROSE_AUTO for c in approved)
    assert not [e for e in events if isinstance(e, (ClaimRejected, Refused))]

    prompt = _sent(synthesis)
    assert "stating who Ludwig van Beethoven studied with" in prompt
    assert "Documented teachers: " in prompt
    claim_set = _claim_set(store, tuple(approved))
    assert misnarrations(prompt, claim_set) == []
    assert "".join(e.text for e in events if isinstance(e, Token)) == (
        "Beethoven studied with four teachers."
    )
    done = next(e for e in events if isinstance(e, Done))
    assert done.claim_count == 4 and done.rejection_count == 0


def test_who_influenced_beethoven_answers_with_influences_and_teachers_kept_apart(
    store: InMemoryGraphStore, registry: ToolRegistry
) -> None:
    """D5 end to end: an influence question that also asked for teachers. Haydn is on both lists,
    because the corpus holds both edges, and the prompt says a name on both is both."""
    traversal = ScriptedLLM(
        [
            plan_turn("origins", "resolve_node", "get_influences", "get_teachers"),
            tool_turn(("resolve_node", {"name": "Ludwig van Beethoven"})),
            tool_turn(
                ("get_influences", {"node_id": BEETHOVEN}),
                ("get_teachers", {"node_id": BEETHOVEN}),
            ),
            END,
        ]
    )
    synthesis = ScriptedLLM([LLMResponse(text="prose")])
    events = list(
        run(
            "Who influenced Beethoven?",
            store=store,
            llm=traversal,
            registry=registry,
            synthesis_llm=synthesis,
        )
    )

    approved = tuple(e.claim for e in events if isinstance(e, ClaimApproved))
    assert Counter(c.predicate for c in approved) == {STUDIED: 4, INFLUENCED: 1}
    prompt = _sent(synthesis)
    assert 'Documented influences: ["Joseph Haydn"]' in prompt
    assert "A name listed under both is both." in prompt
    assert misnarrations(prompt, _claim_set(store, approved)) == []


def test_a_mixed_chain_reaches_the_prompt_with_typed_hops(store: InMemoryGraphStore) -> None:
    """D4. Czerny studied with Beethoven; Beethoven studied with Haydn AND was influenced by him. The
    second hop is narrated with both, never one picked."""
    claims = gate(
        [
            ClaimProposal(CZERNY, STUDIED, BEETHOVEN),
            ClaimProposal(BEETHOVEN, STUDIED, HAYDN),
            ClaimProposal(BEETHOVEN, INFLUENCED, HAYDN),
        ],
        store,
    ).approved
    claim_set = _claim_set(store, claims, chain=(CZERNY, BEETHOVEN, HAYDN))

    assert claim_set.predicate is None
    assert claim_set.hops == (
        (CZERNY, BEETHOVEN, (STUDIED,)),
        (BEETHOVEN, HAYDN, (INFLUENCED, STUDIED)),
    )
    prompt = _prompt(claim_set)
    assert prompt.endswith(
        "Hops: "
        + dumps(
            [
                ["Carl Czerny", "studied with", "Ludwig van Beethoven"],
                ["Ludwig van Beethoven", "was influenced by and studied with", "Joseph Haydn"],
            ]
        )
    )
    assert CHAIN_SUMMARY_BAN in prompt
    assert misnarrations(prompt, claim_set) == []


def test_synthesis_refuses_a_predicate_it_has_no_words_for() -> None:
    """A fallback to influence wording is exactly how a new predicate would be narrated as influence
    without anyone deciding to. It raises instead."""
    genre = "Q1"
    claim = Claim(
        BEETHOVEN, PREDICATE_PLAYS_GENRE, genre, ("stmt/1",), VERIFICATION_MEMBERSHIP_BARE
    )
    with pytest.raises(ValueError, match="no words for predicate"):
        _prompt(ApprovedClaimSet(claims=(claim,)))


# --- untrusted text: the teaching payloads are marked like every other --------------------------------


def _strings(value: object) -> Iterator[str]:
    """Every string in a payload, dictionary keys included."""
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from _strings(key)
            yield from _strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from _strings(item)


def test_teaching_payloads_reach_the_model_marked(registry: ToolRegistry) -> None:
    """``tests/test_untrusted.py`` covers every tool on the pinned corpus, where the teaching tools
    return empty lists. This is the same property on full payloads, labels included, which are the
    Wikidata-derived text the delimiting exists for."""
    for name, arguments in (
        ("get_teachers", {"node_id": BEETHOVEN}),
        ("get_students", {"node_id": HAYDN}),
        ("trace_teaching_lineage", {"from_id": CZERNY, "to_id": FUX}),
    ):
        result = registry.invoke(name, arguments)
        assert not result.is_error and result.proposals, name
        message = tool_results_message([ToolOutcome("t1", result.content)])
        payload = message["content"][0]["toolResult"]["content"][0]
        texts = list(_strings(payload["json"] if "json" in payload else payload["text"]))
        assert texts, name
        for text in texts:
            assert text.startswith("<data>") and text.endswith("</data>"), (name, text)


# --- the influence prompts did not move ------------------------------------------------------------
#
# The three templates as they stood at HEAD before this step, written out verbatim. An influence-only
# set must render exactly these, so step 7 changes nothing about how an influence answer is prompted.
# Also checked across 4,750 prompts rendered from the v0.7.1 corpus against the previous loop.py, once,
# at the time of the change (phase 7.6 step 7 as-built).

OLD_ORIGINS = (
    "Write {sentences} stating what {subject} {verb}, using only the influences listed below. "
    "Name every one of them. {ban}"
)
OLD_DESCENDANTS = (
    "Every name listed below {verb} {subject}. Write {sentences} saying so, naming every one of them "
    "and keeping that direction. Do not state it the other way round: {subject} did not come out of "
    "them. {ban}"
)
OLD_CHAIN = (
    "Write {sentences} tracing the chain of influence below, in the order given. Each name listed "
    "{verb} the one after it. Name every one of them and keep them in that order. {ban}"
)
A, B, C = "Q9001", "Q9002", "Q9003"


@pytest.mark.parametrize(
    ("axis", "verb"), [(NODE_KIND_GENRE, "came out of"), (NODE_KIND_ARTIST, "was influenced by")]
)
def test_influence_prompts_render_exactly_as_before(axis: str, verb: str) -> None:
    labels = {A: "alpha", B: "beta", C: "gamma"}
    kinds = dict.fromkeys(labels, axis)
    ban = agent_loop._embellishment_ban(axis)
    noun = "Genre" if axis == NODE_KIND_GENRE else "Artist"

    origins = ApprovedClaimSet(
        claims=(_claim(A, INFLUENCED, B), _claim(A, INFLUENCED, C)), labels=labels, kinds=kinds
    )
    assert _prompt(origins) == (
        OLD_ORIGINS.format(sentences="one or two sentences", subject="alpha", verb=verb, ban=ban)
        + f"\n\n{noun}: alpha\nDocumented influences: {dumps(['beta', 'gamma'])}"
    )

    fan_in = ApprovedClaimSet(
        claims=(_claim(B, INFLUENCED, A), _claim(C, INFLUENCED, A)), labels=labels, kinds=kinds
    )
    heading = (
        "Documented as coming out of it"
        if axis == NODE_KIND_GENRE
        else "Documented as influenced by them"
    )
    assert _prompt(fan_in) == (
        OLD_DESCENDANTS.format(
            sentences="one or two sentences", subject="alpha", verb=verb, ban=ban
        )
        + f"\n\n{noun}: alpha\n{heading}: {dumps(['beta', 'gamma'])}"
    )

    chain = ApprovedClaimSet(
        claims=(_claim(A, INFLUENCED, B), _claim(B, INFLUENCED, C)),
        labels=labels,
        kinds=kinds,
        chain=(A, B, C),
    )
    assert _prompt(chain) == (
        OLD_CHAIN.format(sentences="one or two sentences", verb=verb, ban=ban)
        + f"\n\nChain: {dumps(['alpha', 'beta', 'gamma'])}"
    )
