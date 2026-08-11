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

**Extended 2026-08-07 (phase 3, step 1).** ``datasets/adversarial_v1.json`` holds the 18 adversarial
cases, hand-authored before any loop code exists and while Bedrock has still never completed a call, so
nothing in it can have been shaped by model output. ``tests/test_adversarial_set.py`` re-checks every
case against the pinned corpus on every commit -- absent genres still absent, forbidden edges still
forbidden, resolver strings unchanged.

Two of its cases departed from the phase plan for cause: the planned "ambiguous name" group tests a
``resolve_node`` branch with **population zero** (no two labels in v0.5.0 share a ``label_key``), so it
was redirected to the reachable ``no exact match`` branch and the dead one is locked by test, exactly as
``contested`` and ``checks_disagree`` are.

**Extended 2026-08-11 (phase 3, step 7).** ``metrics.py`` gained the six scorers of the phase plan's
§4.7 (7a), and ``slices.py`` plus ``harness.py`` landed with the baseline run (7b).
``datasets/baseline_v0_3_0_local.json`` is that run's recorded output, regenerable with
``harness.write_baseline`` and drift-tested against a fresh run on every commit.

**Read the ``measures`` field at the top of that record before quoting any number from it.** Every run
is driven by ``ScriptedLLM``, so the baseline demonstrates that the gate and the loop refuse unsupported
claims — **not** that a real model resists. Real-model behaviour is DoD #10 and #11 and needs Bedrock.

Still to come: the full gold set (20-30) extending the five in ``gold_v0_1.json``, and the sealed
held-out ten. Per the 2026-08-07 threshold review both are a **hard precondition on phase 3 step 8**
rather than phase 4 work -- step 8 is the first billable Bedrock call this project will ever make, and a
dataset authored after it is authored by someone who has seen the real agent behave. The judge, its
human-agreement measurement, and the slicing remain phase 4.
"""
