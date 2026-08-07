"""The four tools added at phase 3 step 2, and the seam that let them be added.

``CLAUDE.md`` invariant 4 is the reason this file exists as much as the tools are: **adding a tool must
never require editing the loop.** The last three tests are that claim stated as executable assertions
rather than as a comment nobody re-checks.

Every tool here reads the pinned artifact, calls no model, and touches no network, so all of it is
Tier 1: deterministic, free, and safe to run on every commit.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

from musical_mycelium.agent import loop as agent_loop
from musical_mycelium.agent.claims import gate
from musical_mycelium.agent.tools import (
    CorpusCoverage,
    DescribeNode,
    GetDescendants,
    ResolveSource,
    default_registry,
)
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.store import Direction

LOOP_SOURCE = Path(agent_loop.__file__)

#: Read off the pinned v0.5.0 artifact on 2026-08-07, never recalled
#: (``reference-never-recall-wikidata-qids``).
BLUES = "Q9759"
BLUES_ROCK = "Q193355"
THE_BEATLES = "Q1299"
OPERA = "Q1344"  # inception 1600, precision 7 (century)
LO_FI = "Q1507298"  # inception 1980, precision 8 (decade)
BROOKLYN_DRILL = "Q104847359"  # no inception at all, and no descendants
FUTURE_RAVE = "Q101109587"  # no descendants


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


# --- get_descendants -------------------------------------------------------------------------------


def test_get_descendants_answers_what_came_out_of_a_genre(store: InMemoryGraphStore) -> None:
    """The gap this tool closes. Before it, this question needed both endpoints named up front."""
    result = GetDescendants(store)(node_id=BLUES)

    assert result.content["count"] == 1
    assert result.content["descendants"][0]["node_id"] == BLUES_ROCK
    assert not result.is_error


def test_get_descendants_proposals_are_oriented_by_the_edge_not_the_argument(
    store: InMemoryGraphStore,
) -> None:
    """The correctness requirement for this whole tool.

    A descendant walk finds edges where the queried node is the **object**, so the proposal's subject
    must be the descendant. Building it from ``node_id`` instead would emit ``blues influenced_by blues
    rock`` — influence narrated backwards in time, out of a query that asked something reasonable.
    """
    result = GetDescendants(store)(node_id=BLUES)

    (proposal,) = result.proposals
    assert proposal.subject_id == BLUES_ROCK, "the descendant must be the subject"
    assert proposal.object_id == BLUES, "the queried node must be the object"


def test_every_descendant_proposal_survives_the_gate(store: InMemoryGraphStore) -> None:
    """A tool that proposed claims the gate rejects would inflate the rejection stream that refusal
    accuracy is measured on. These are real edges, so all of them must pass."""
    result = GetDescendants(store)(node_id=THE_BEATLES)
    assert len(result.proposals) == 19

    decision = gate(list(result.proposals), store)
    assert not decision.rejected
    assert len(decision.approved) == 19


def test_get_descendants_returns_an_empty_list_rather_than_an_error_for_a_leaf(
    store: InMemoryGraphStore,
) -> None:
    """Absence is an answer here, not a failure. ``is_error`` would tell the model something went
    wrong, when in fact the graph simply records nothing descending from this node."""
    result = GetDescendants(store)(node_id=FUTURE_RAVE)

    assert result.content == {"descendants": [], "count": 0}
    assert not result.is_error
    assert not result.proposals


def test_get_descendants_rejects_an_unknown_node(store: InMemoryGraphStore) -> None:
    result = GetDescendants(store)(node_id="Q00000000")
    assert result.is_error
    assert "resolve_node" in result.content["error"]


def test_get_descendants_asserts_no_chain(store: InMemoryGraphStore) -> None:
    """Several descendants of one node are a fan-out, not an ordered descent. Setting ``chain`` here
    would let the loop narrate an arbitrary sibling ordering as a line of influence."""
    assert GetDescendants(store)(node_id=THE_BEATLES).chain == ()


def test_descendants_and_influences_are_exact_inverses(store: InMemoryGraphStore) -> None:
    """The property that makes the two directions trustworthy together."""
    forward = store.neighbors(BLUES_ROCK, Direction.INFLUENCED_BY)
    assert BLUES in {edge.object_id for edge in forward}

    back = GetDescendants(store)(node_id=BLUES)
    assert BLUES_ROCK in {d["node_id"] for d in back.content["descendants"]}


# --- describe_node ---------------------------------------------------------------------------------


def test_describe_node_reports_when_and_where(store: InMemoryGraphStore) -> None:
    content = DescribeNode(store)(node_id=BLUES_ROCK).content

    assert content["kind"] == "genre"
    assert content["inception_year"] == 1960
    assert content["era"] == "1950-1969"
    assert content["countries"] == ["United Kingdom", "United States"]


def test_describe_node_names_the_precision_rather_than_implying_a_year(
    store: InMemoryGraphStore,
) -> None:
    """``graph/schema.py`` warns about this on the field itself: rendering a century-precision 1600 as
    "1600" states something Wikidata does not. The word travels beside the number."""
    opera = DescribeNode(store)(node_id=OPERA).content
    assert opera["inception_year"] == 1600
    assert opera["inception_precision_label"] == "century"

    lo_fi = DescribeNode(store)(node_id=LO_FI).content
    assert lo_fi["inception_year"] == 1980
    assert lo_fi["inception_precision_label"] == "decade"


def test_describe_node_is_honest_about_a_missing_date(store: InMemoryGraphStore) -> None:
    content = DescribeNode(store)(node_id=BROOKLYN_DRILL).content

    assert content["inception_year"] is None
    assert content["inception_precision_label"] is None
    assert content["era"] == "unknown", "an undated node must not be bucketed into a real era"


def test_describe_node_emits_no_proposals(store: InMemoryGraphStore) -> None:
    """No edge is involved, so any proposal would fail ``UNSUPPORTED_PREDICATE`` at the gate and
    pollute the rejection stream refusal accuracy is measured on."""
    result = DescribeNode(store)(node_id=BLUES_ROCK)
    assert result.proposals == ()


def test_describe_node_rejects_an_unknown_node(store: InMemoryGraphStore) -> None:
    assert DescribeNode(store)(node_id="Q00000000").is_error


# --- resolve_source --------------------------------------------------------------------------------


def test_resolve_source_turns_a_statement_uri_into_something_checkable(
    store: InMemoryGraphStore,
) -> None:
    edge = store.neighbors(BLUES_ROCK, Direction.INFLUENCED_BY)[0]
    content = ResolveSource(store)(source_id=edge.source_id).content

    assert content["resolvable"] is True
    assert content["entity_id"] == BLUES_ROCK
    assert content["url"] == f"https://www.wikidata.org/wiki/{BLUES_ROCK}"
    assert content["retrieved_at"]


def test_resolve_source_refuses_a_non_wikidata_id(store: InMemoryGraphStore) -> None:
    content = ResolveSource(store)(source_id="https://example.com/made-up").content
    assert content["resolvable"] is False


def test_resolve_source_refuses_a_well_formed_uri_for_an_entity_we_do_not_hold(
    store: InMemoryGraphStore,
) -> None:
    """The plausible-looking fabrication. The URI is syntactically perfect and names nothing here, and
    reporting it as a citation is exactly what ``claims.resolve_sources`` exists to prevent."""
    forged = "http://www.wikidata.org/entity/statement/Q00000000-DEADBEEF"
    content = ResolveSource(store)(source_id=forged).content

    assert content["resolvable"] is False
    assert content["entity_id"] == "Q00000000"


def test_resolve_source_emits_no_proposals(store: InMemoryGraphStore) -> None:
    edge = store.neighbors(BLUES_ROCK, Direction.INFLUENCED_BY)[0]
    assert ResolveSource(store)(source_id=edge.source_id).proposals == ()


# --- corpus_coverage -------------------------------------------------------------------------------


def test_corpus_coverage_takes_no_arguments_and_reports_measured_numbers(
    store: InMemoryGraphStore,
) -> None:
    content = CorpusCoverage(store)().content

    assert content["artifact_version"] == store.artifact_version
    assert content["genres"] == 169
    assert content["distinct_countries"] == 29
    assert content["genres_without_us_or_uk"] == 43


def test_corpus_coverage_returns_a_shape_no_other_tool_returns(store: InMemoryGraphStore) -> None:
    """This is what makes it the seam test: no proposals, no visited, no chain, no sources. A loop
    that assumed every result contributes to the claim set would have needed an edit to accept it."""
    result = CorpusCoverage(store)()

    assert result.proposals == ()
    assert result.visited == ()
    assert result.chain == ()
    assert result.sources == ()
    assert not result.is_error


def test_corpus_coverage_requires_no_arguments_through_the_registry(
    store: InMemoryGraphStore,
) -> None:
    """The model calls it with ``{}``, so the registry path must accept that without a TypeError."""
    result = default_registry(store).invoke("corpus_coverage", {})
    assert not result.is_error


# --- the seam --------------------------------------------------------------------------------------


def test_seven_tools_are_registered_and_coverage_is_last(store: InMemoryGraphStore) -> None:
    registry = default_registry(store)
    assert len(registry) == 7
    assert registry.names == (
        "resolve_node",
        "get_influences",
        "trace_lineage",
        "get_descendants",
        "describe_node",
        "resolve_source",
        "corpus_coverage",
    )


def test_only_get_descendants_emits_proposals_among_the_new_tools(
    store: InMemoryGraphStore,
) -> None:
    """Three no-proposal tools rather than two, which is what makes the seam test strong: the loop
    must not assume a result contributes to the claim set."""
    assert GetDescendants(store)(node_id=BLUES).proposals
    assert DescribeNode(store)(node_id=BLUES).proposals == ()
    assert CorpusCoverage(store)().proposals == ()

    edge = store.neighbors(BLUES_ROCK, Direction.INFLUENCED_BY)[0]
    assert ResolveSource(store)(source_id=edge.source_id).proposals == ()


def test_the_loop_never_names_a_tool_in_its_executable_source() -> None:
    """Invariant 4, in the durable form.

    The IMPLEMENTATION doc proposed pinning ``loop.py``'s hash across the ``corpus_coverage`` commit.
    That is a good *commit-time* check and a bad permanent test: step 3 adds the plan object and will
    legitimately change this file, at which point a pinned hash fails for a reason that has nothing to
    do with the seam.

    So the durable property is asserted instead: **no tool name appears anywhere the loop executes.**
    Comments are stripped first, deliberately — ``loop.py`` documents the *rejected* v0.1 design, which
    hard-coded "use resolve_node, then get_influences" into the prompt, and a comment recording that
    history cannot break the seam. Code that branches on a tool name can.
    """
    tree = ast.parse(LOOP_SOURCE.read_text(encoding="utf-8"))
    executable = ast.unparse(tree)  # comments are not in the AST; docstrings survive as constants

    offenders = [
        name
        for name in (
            "resolve_node",
            "get_influences",
            "trace_lineage",
            "get_descendants",
            "describe_node",
            "resolve_source",
            "corpus_coverage",
        )
        if name in executable
    ]
    assert not offenders, (
        f"agent/loop.py names {offenders} in executable source. Adding a tool must never require "
        f"editing the loop, and a loop that knows a tool's name has already broken that."
    )


def test_default_registry_still_takes_only_a_store() -> None:
    """Registering four more tools did not change this signature, and that is the point.

    ``corpus_coverage`` needs a ``Coverage``, which is why ``coverage`` was added to the ``GraphStore``
    protocol rather than threaded in as a second argument: a signature change here would have made the
    seventh tool a call-site edit at every caller, undercutting the demonstration it exists to make.
    """
    import inspect

    parameters = list(inspect.signature(default_registry).parameters)
    assert parameters == ["store"]
