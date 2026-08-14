"""Draw a held-out set by stratified random sample, so nobody has to look at it — including the author.

``.claude/rules/heldout-set.md`` requires a held-out 10 that is never read during development, and
``.claude/rules/evals.md`` explains what it is for: **detecting overfitting to the gold set**, and
nothing else. Those two requirements together are why this module exists rather than a template.

**Why a draw rather than hand-authoring.** The gold set is hand-composed because it is teaching
material — boring middles, planted traps, deliberately sparse slices. The held-out set has the opposite
job. It asks whether performance *generalises past the cases we tuned against*, and a curated held-out
set answers that badly, because it inherits its author's blind spots — which are the same blind spots
already baked into the gold set. An unbiased sample has no such correlation with the tuning target.

**Why this does not contaminate the agent that wrote it.** The draw is seeded, and the seed comes from
the author on the command line. Whoever wrote this module knows the *procedure* and the *strata*; the
manifest publishes the strata anyway, deliberately (:func:`heldout.summarise`), so that is not a
disclosure. Without the seed the output cannot be reproduced. Do not commit the seed, do not paste it
into a chat session, and do not put it in shell history you later share — it is the whole mechanism.

**Why claims are derived rather than written.** Every field is read straight out of the pinned artifact,
so the cases match the corpus by construction. There is no hallucination surface at all: a model
inventing a QID is the single most reliable failure mode this project has seen, and this module never
invents one. The cost, stated plainly: drawn cases carry **no independent citations**. That is
acceptable here and only here — ``heldout.check_against_corpus`` does not read citations, and the Tier 1
metrics it feeds (edge groundedness, traversal recall, refusal accuracy) are dictionary lookups that
never consult them. Citation *support* is a Tier 2 judged metric measured against the gold set.

Usage, and the plaintext never needs to reach a terminal that is being watched::

    make heldout-draw SEED='something only you know' OUT=~/heldout_v1.json
    make heldout-seal PLAINTEXT=~/heldout_v1.json
    shred -u ~/heldout_v1.json     # or just delete it

The draw prints **counts only** — never a case, never a node id.
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import Any

from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import Artifact
from musical_mycelium.graph.store import Direction

#: The strata and how many cases each contributes. Mirrors the gold set's shape spread rather than the
#: corpus's, because the held-out set has to be comparable to the thing it is checking for overfitting:
#: if the gold set is 40% origins and the held-out set is 90% origins, a score gap between them measures
#: the composition difference and not the generalisation gap. Sums to 10.
STRATA: dict[str, int] = {
    "origins": 4,
    "descendants": 2,
    "path": 2,
    "refusal": 2,
}

#: A path case shorter than this is barely a traversal; longer than this and the corpus runs out of
#: candidates (only 6 chains reach 6 hops, all of them artists).
MIN_PATH_HOPS = 2
MAX_PATH_HOPS = 5

#: An origins or descendants case needs enough edges to be worth scoring. One edge is a resolution test
#: wearing a traversal's clothes.
MIN_EDGES = 2


def _drawable(store: InMemoryGraphStore, artifact: Artifact) -> dict[str, list[str]]:
    """Bucket every node by which stratum it could serve, using the artifact only.

    The node list comes from the ``Artifact`` rather than the store because ``GraphStore`` exposes no
    iterator — deliberately, since the agent's tools answer questions *about* nodes and never enumerate
    them. This is a local authoring tool, not Lambda code, so reading the artifact directly is the same
    move ``test_architecture``'s unreachable-state lock makes for the same reason.
    """
    buckets: dict[str, list[str]] = {k: [] for k in STRATA}

    for node in artifact.nodes:
        parents = store.neighbors(node.id, Direction.INFLUENCED_BY)
        children = store.neighbors(node.id, Direction.INFLUENCED)

        if len(parents) >= MIN_EDGES:
            buckets["origins"].append(node.id)
        if len(children) >= MIN_EDGES:
            buckets["descendants"].append(node.id)
        # The strong refusal: the node resolves and is cited by others, but has no sourced origin of
        # its own. The weak kind (an unknown string) is not drawn — it tests the resolver, not the gate.
        if not parents and children:
            buckets["refusal"].append(node.id)
        if parents:
            buckets["path"].append(node.id)

    return buckets


def _path_case(
    store: InMemoryGraphStore, start_id: str, rng: random.Random
) -> dict[str, Any] | None:
    """Walk upward from ``start_id`` to a terminus, then let ``store.path`` define the canonical chain.

    The chain is re-derived through ``store.path`` rather than kept from the walk, because that is the
    function the gold set pins to and the one a traversal is expected to match — the shortest sourced
    route. A random walk may find a longer one.
    """
    current = start_id
    chain = [current]
    for _ in range(MAX_PATH_HOPS):
        parents = store.neighbors(current, Direction.INFLUENCED_BY)
        if not parents:
            break
        current = rng.choice(parents).object_id
        if current in chain:
            break
        chain.append(current)

    if len(chain) - 1 < MIN_PATH_HOPS:
        return None

    edges = store.path(start_id, chain[-1])
    if len(edges) < MIN_PATH_HOPS:
        return None

    subject, terminus = store.get_node(start_id), store.get_node(chain[-1])
    if subject is None or terminus is None:
        return None

    node_ids = [start_id] + [e.object_id for e in edges]
    return {
        "shape": "path",
        "query": f"How does {subject.label} connect back to {terminus.label}?",
        "expected_resolution": {"name": subject.label, "node_id": subject.id},
        "expected_terminus": {"name": terminus.label, "node_id": terminus.id},
        "expected_refusal": False,
        "expected_path": node_ids,
        "expected_claims": [_claim(store, e) for e in edges],
    }


def _claim(store: InMemoryGraphStore, edge: Any) -> dict[str, Any]:
    subject, obj = store.get_node(edge.subject_id), store.get_node(edge.object_id)
    return {
        "subject_id": edge.subject_id,
        "predicate": edge.predicate,
        "object_id": edge.object_id,
        "subject_label": subject.label if subject else "",
        "object_label": obj.label if obj else "",
        "verification": edge.verification,
        "wikidata_statement": f"{edge.subject_id} P737 {edge.object_id}",
        "independent_citations": [],
        "citation_status": {
            "state": "not_sought",
            "searched": [],
            "finding": (
                "Drawn mechanically from the pinned artifact, so no citation pass was run. The held-out "
                "set feeds Tier 1 metrics only, which are dictionary lookups against the artifact and "
                "never read citations. Citation support is judged against the gold set instead."
            ),
        },
    }


def _simple_case(store: InMemoryGraphStore, node_id: str, shape: str) -> dict[str, Any] | None:
    node = store.get_node(node_id)
    if node is None:
        return None

    if shape == "descendants":
        edges = store.neighbors(node_id, Direction.INFLUENCED)
        # The other end of a descendants row is its **subject**, not its object. Reading the wrong end
        # does not raise — it yields a path of the same node repeated, which surfaces downstream as
        # ``path-narrower-than-claims``. Found by tests/test_heldout_draw.py on its first run, which is
        # the second time on 2026-08-14 that assuming the origins direction produced a silent wrong
        # answer rather than an error.
        others = [e.subject_id for e in edges]
        query = f"What came out of {node.label}?"
    else:
        edges = store.neighbors(node_id, Direction.INFLUENCED_BY)
        others = [e.object_id for e in edges]
        query = (
            f"Who influenced {node.label}?"
            if node.kind == "artist"
            else f"Where did {node.label} come from?"
        )

    refusal = shape == "refusal"
    return {
        "shape": "descendants" if shape == "descendants" else "origins",
        "query": query,
        "expected_resolution": {"name": node.label, "node_id": node.id},
        "expected_refusal": refusal,
        "expected_path": [node.id] if refusal else [node.id, *others],
        "expected_claims": [] if refusal else [_claim(store, e) for e in edges],
    }


def draw(seed: str, store: InMemoryGraphStore, artifact: Artifact) -> dict[str, Any]:
    """Draw the full set. Deterministic given ``seed``, and unreproducible without it."""
    rng = random.Random(seed)
    buckets = _drawable(store, artifact)
    cases: list[dict[str, Any]] = []
    used: set[str] = set()

    for shape, wanted in STRATA.items():
        pool = [n for n in buckets[shape] if n not in used]
        rng.shuffle(pool)
        taken = 0
        for node_id in pool:
            if taken >= wanted:
                break
            case = (
                _path_case(store, node_id, rng)
                if shape == "path"
                else _simple_case(store, node_id, shape)
            )
            if case is None:
                continue
            # A drawn case must resolve to itself, exactly as the gold set requires. Labels are not
            # unique and a case that resolves to a different node measures the resolver, not the agent.
            hits = store.search(case["expected_resolution"]["name"])
            if not hits or hits[0].id != case["expected_resolution"]["node_id"]:
                continue
            case["case_id"] = f"heldout_v1_{len(cases) + 1:03d}"
            cases.append(case)
            used.add(node_id)
            taken += 1
        if taken < wanted:
            raise SystemExit(
                f"stratum {shape!r} could only fill {taken} of {wanted}; widen STRATA or the thresholds"
            )

    return {
        "dataset": "heldout_v1",
        "authored_by": "stratified draw",
        "artifact_version_pin": store.artifact_version,
        "method": (
            "Drawn by src/musical_mycelium/eval/heldout_draw.py from a seed known only to the author. "
            "Claims and paths are read from the pinned artifact, so the set matches the corpus by "
            "construction and contains no authored judgement to contaminate. Its job is detecting "
            "overfitting to the gold set; an unbiased sample does that better than a curated one, which "
            "would inherit the same blind spots the gold set already has."
        ),
        "cases": cases,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Draw a held-out set. Prints counts, never content."
    )
    parser.add_argument(
        "--seed", required=True, help="Known only to you. Never commit or paste it."
    )
    parser.add_argument("--out", required=True, type=Path, help="Plaintext path, OUTSIDE the repo.")
    args = parser.parse_args(argv)

    out: Path = args.out.expanduser()
    if out.resolve().is_relative_to(Path(__file__).resolve().parents[3]):
        raise SystemExit(f"refusing to write inside the repository: {out}")

    directory = artifact_directory()
    store = InMemoryGraphStore.from_directory(directory)
    data = draw(args.seed, store, Artifact.load(directory))
    out.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    shapes: dict[str, int] = {}
    for case in data["cases"]:
        shapes[case["shape"]] = shapes.get(case["shape"], 0) + 1
    print(f"wrote {len(data['cases'])} cases to {out}")
    print(f"  artifact pin: {data['artifact_version_pin']}")
    print(f"  shapes: {dict(sorted(shapes.items()))}")
    print(f"  refusals: {sum(1 for c in data['cases'] if c['expected_refusal'])}")
    print("\nNow seal it, then delete the plaintext:")
    print(f"  make heldout-seal PLAINTEXT={out}")
    print(f"  shred -u {out}")
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
