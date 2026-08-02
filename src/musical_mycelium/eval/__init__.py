"""The evaluation harness — a first-class deliverable, not a test suite.

The project-specific advantage: the ground truth is a graph we own, so the headline correctness metrics
are **deterministic dictionary lookups** rather than judged text comparison. They are exact, free, and can
run on every commit. That is what turns "grounded" from a soft claim into a provable property.

Contract (``docs/planning/07-EVAL-SPEC.md``, and ``.claude/rules/evals.md`` for the hard rules):

- Tier 1 deterministic, $0, every commit. Tier 2 judged, sampled, behind an explicit spend confirmation.
- Block on correctness properties; track quality preferences.
- The judge is validated against 30 hand-labeled items and is not from the generator's model family.
- The metrics themselves are unit-tested, including the vacuous-truth guard: an empty output must not
  score 100% groundedness.
- Every result is sliced by era, region, density, and query type. The corpus skew is documented and an
  aggregate that hides a failing slice is the default outcome without slicing.
- All runs are against a pinned artifact version.

May import from any other subpackage. Nothing imports from here.

**Partly built as of 2026-08-02 (phase 1, step 5).** ``metrics.py`` holds ``edge_groundedness``, the one
Tier 1 metric in v0.1 scope, and ``datasets/gold_v0_1.json`` holds the five gold cases — hand-authored on
2026-08-02, **before the agent exists**, or they would be contaminated by model output.

``edge_groundedness`` deliberately does **not** call the gate. It re-derives its verdict from the
artifact, because a measurement that asks the gate whether the gate was right measures nothing.

Still to come: the full gold set (20-30), the adversarial set with a planted injection, the sealed
held-out ten, the judge and its human-agreement measurement, and the slicing. Phase 4 owns those.
"""
