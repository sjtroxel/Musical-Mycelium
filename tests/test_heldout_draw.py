"""The held-out draw, checked against the same validator the sealed set is checked with.

This file is safe to read and contains no held-out content. It draws with **published test seeds**, which
is the whole point: a set drawn from a seed written down in the repository is not held out from anybody,
so these seeds must never be the one used for the real set. The real seed is the author's and is never
committed, pasted, or logged.

What these tests are for. ``heldout_draw`` exists so the held-out 10 can be produced without a human
composing ten cases by hand and without a model inventing QIDs — every field is read from the pinned
artifact. That is only worth anything if a drawn set actually satisfies
``heldout.check_against_corpus``, which is the validator the sealed set is judged by. Asserting that here
means the draw cannot silently start producing sets that fail their own check.
"""

from __future__ import annotations

import pytest

from musical_mycelium.eval import heldout, heldout_draw
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import PREDICATE_INFLUENCED_BY, PREDICATE_STUDIED_WITH, Artifact
from musical_mycelium.graph.store import Direction

#: Published on purpose. See the module docstring: a committed seed is the opposite of held out.
TEST_SEEDS = ("published-test-seed-a", "published-test-seed-b", "published-test-seed-c")


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture(scope="module")
def artifact() -> Artifact:
    return Artifact.load(artifact_directory())


@pytest.mark.parametrize("seed", TEST_SEEDS)
def test_a_drawn_set_passes_the_validator_the_sealed_set_is_judged_by(
    seed: str, store: InMemoryGraphStore, artifact: Artifact
) -> None:
    """The load-bearing assertion. Several seeds, because a draw that happens to work once is luck.

    ``check_against_corpus`` reports ids and codes only, so a failure here names the case and the problem
    without disclosing content — the same property that makes the sealed set checkable while sealed.
    """
    data = heldout_draw.draw(seed, store, artifact)
    findings = heldout.check_against_corpus(data, store)
    assert not findings, [str(f) for f in findings]


@pytest.mark.parametrize("seed", TEST_SEEDS)
def test_a_drawn_set_has_the_composition_the_strata_declare(
    seed: str, store: InMemoryGraphStore, artifact: Artifact
) -> None:
    """Ten cases, and the refusal count matches the stratum rather than whatever the draw happened upon.

    Composition is the one thing the public manifest discloses, deliberately, so it has to be a property
    of the draw rather than an accident of it: a held-out set whose shape spread differs from the gold
    set's would make any score gap between them a measure of the composition difference.
    """
    data = heldout_draw.draw(seed, store, artifact)
    cases = data["cases"]

    assert len(cases) == sum(heldout_draw.STRATA.values()) == 10
    assert sum(1 for c in cases if c["expected_refusal"]) == heldout_draw.STRATA["refusal"]
    assert sum(1 for c in cases if c["shape"] == "path") == heldout_draw.STRATA["path"]
    assert (
        sum(1 for c in cases if c["shape"] == "descendants") == heldout_draw.STRATA["descendants"]
    )
    assert sum(1 for c in cases if c["shape"] == "teachers") == heldout_draw.STRATA["teaching"]
    assert {c["case_id"] for c in cases} == {f"heldout_v2_{i:03d}" for i in range(1, 11)}


def test_different_seeds_draw_different_sets(store: InMemoryGraphStore, artifact: Artifact) -> None:
    """Otherwise the seed is decoration and the set is whatever the code happens to pick first.

    This is the property that keeps the author's seed load-bearing: knowing the procedure, the strata and
    the artifact is **not** enough to reproduce the draw. Only the seed is.
    """
    a = heldout_draw.draw(TEST_SEEDS[0], store, artifact)
    b = heldout_draw.draw(TEST_SEEDS[1], store, artifact)

    def subjects(data: dict[str, object]) -> set[str]:
        cases: list[dict[str, object]] = data["cases"]  # type: ignore[assignment]
        return {str(c["expected_resolution"]["node_id"]) for c in cases}  # type: ignore[index]

    assert subjects(a) != subjects(b)


def test_the_same_seed_draws_the_same_set(store: InMemoryGraphStore, artifact: Artifact) -> None:
    """Reproducibility is what makes a lost plaintext recoverable *if* the seed survives — and it is why
    the seed has to be protected as carefully as the key."""
    a = heldout_draw.draw(TEST_SEEDS[2], store, artifact)
    b = heldout_draw.draw(TEST_SEEDS[2], store, artifact)
    assert a == b


@pytest.mark.parametrize("seed", TEST_SEEDS)
def test_no_drawn_case_claims_a_citation_it_does_not_have(
    seed: str, store: InMemoryGraphStore, artifact: Artifact
) -> None:
    """A drawn case has no citation pass, and it must say so rather than leaving the field ambiguous.

    ``not_sought`` is deliberately a different state from the gold set's ``source_uncited``: one means
    nobody looked, the other means somebody looked in four languages and found nothing. Collapsing them
    would let the weaker claim borrow the stronger one's credibility.
    """
    data = heldout_draw.draw(seed, store, artifact)
    for case in data["cases"]:
        for claim in case["expected_claims"]:
            assert not claim["independent_citations"]
            assert claim["citation_status"]["state"] == "not_sought"


@pytest.mark.parametrize("seed", TEST_SEEDS)
def test_every_drawn_refusal_is_the_strong_kind(
    seed: str, store: InMemoryGraphStore, artifact: Artifact
) -> None:
    """Resolved-but-unsourced, never an unknown string.

    The weak refusal — a query naming nothing in the corpus — tests the resolver. The strong one tests
    the gate: the node is present, other cases cite it, and the system still declines to state its
    origins. Only the second is worth a held-out slot.
    """
    data = heldout_draw.draw(seed, store, artifact)
    for case in data["cases"]:
        if not case["expected_refusal"]:
            continue
        node_id = case["expected_resolution"]["node_id"]
        assert store.get_node(node_id) is not None
        assert not store.neighbors(node_id)
        assert store.neighbors(node_id, Direction.INFLUENCED)
        # **And no teaching edge in either direction, since 2026-09-12.** An influence question also
        # asks `get_teachers` (phase 7.6 D5), so a drawn "refusal" with a teacher is answerable and the
        # case would assert a refusal the system is right not to make. The influence check above cannot
        # see that.
        assert not store.neighbors(
            node_id, Direction.INFLUENCED_BY, predicates=heldout_draw.TEACHING_ONLY
        )
        assert not store.neighbors(
            node_id, Direction.INFLUENCED, predicates=heldout_draw.TEACHING_ONLY
        )


@pytest.mark.parametrize("seed", TEST_SEEDS)
def test_every_drawn_claim_cites_the_property_its_predicate_actually_uses(
    seed: str, store: InMemoryGraphStore, artifact: Artifact
) -> None:
    """P737 for influence, P1066 for teaching, and never the wrong one.

    `_claim` hardcoded `P737` for every edge until 2026-09-12. On a `studied_with` edge that is a false
    citation string — and sealed into a set nobody may open, a false citation is permanent. The gold set
    records teaching as `Q254 P1066 Q106641`; this asserts the draw agrees with it.
    """
    data = heldout_draw.draw(seed, store, artifact)
    seen = set()
    for case in data["cases"]:
        for claim in case["expected_claims"]:
            predicate = claim["predicate"]
            expected = {PREDICATE_INFLUENCED_BY: "P737", PREDICATE_STUDIED_WITH: "P1066"}[predicate]
            subject, obj = claim["subject_id"], claim["object_id"]
            assert claim["wikidata_statement"] == f"{subject} {expected} {obj}"
            seen.add(predicate)
    # The teaching stratum guarantees the P1066 branch is exercised rather than merely defined.
    assert PREDICATE_STUDIED_WITH in seen


@pytest.mark.parametrize("seed", TEST_SEEDS)
def test_a_teaching_case_asks_about_study_and_claims_only_teaching(
    seed: str, store: InMemoryGraphStore, artifact: Artifact
) -> None:
    """A claim states what its source asserts, and P1066 asserts study.

    The wording matters as much as the predicate: a teaching case that asked "who influenced X" would
    seal the exact conflation `graph-semantics.md` §8 and the whole of phase 7.6 exist to prevent.
    """
    data = heldout_draw.draw(seed, store, artifact)
    teaching = [c for c in data["cases"] if c["shape"] == "teachers"]
    assert teaching, "the teaching stratum drew nothing"
    for case in teaching:
        assert "study with" in case["query"]
        assert "influence" not in case["query"].lower()
        assert case["expected_claims"]
        assert all(c["predicate"] == PREDICATE_STUDIED_WITH for c in case["expected_claims"])
