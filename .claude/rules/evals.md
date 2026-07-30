# Rule: Evaluation

Canonical detail: `docs/planning/07-EVAL-SPEC.md`. Evals are a first-class deliverable here, not a test
suite — they are the stated differentiator and the reason "grounded" is a provable property rather than a
marketing word. Hard rules:

- **Tier 1 is deterministic, free, and runs on every commit.** Because the ground truth is a graph we own,
  the headline correctness metrics are dictionary lookups: does edge (subject, predicate, object) exist in
  the pinned artifact. Groundedness, citation resolution, traversal recall/precision, refusal accuracy,
  contested flagging, coverage honesty, injection resistance, cost and latency. No approval needed, $0.
- **Tier 2 is judged, sampled, and gated.** Citation *support* and narrative quality only. 20–30 samples,
  release candidates only, behind an explicit spend confirmation.
- **Block on correctness properties, track quality preferences.** Blocking: edge groundedness 100%,
  citation resolution 100%, injection resistance zero failures, traversal recall within 5pp of baseline,
  refusal accuracy within 5pp of baseline. Everything else is tracked, not gated. A suite that blocks on
  everything gets disabled within two weeks; a suite that blocks on nothing gets ignored.
- **Do not invent thresholds before a baseline exists.**
- **The judge must be validated and must not be the generator's family.** Hand-label 30 items, report
  judge-human agreement permanently next to every judged metric. An LLM-judge score with no measured
  agreement is decoration. Use a non-Anthropic model on Bedrock (Nova, Llama, Mistral, DeepSeek) to avoid
  self-preference.
- **Measure the noise floor.** Run the identical suite 5 times, record the spread, and never celebrate a
  movement that falls inside it.
- **Unit-test the metrics themselves.** Synthetic outputs where the answer is known by construction,
  including the **vacuous-truth guard: an empty output must not score 100% groundedness.** A metric you have
  not tried to break is not a metric. This section exists because of a real difflib coverage bug.
- **Slice every result by era, region, density, and query type.** The corpus skew is documented; an
  aggregate that looks healthy while the sparse and non-Western slices fail is the default outcome without
  slicing.
- **The three frozen datasets are hand-built before the agent exists** — otherwise they are contaminated by
  model output. Gold lineage set of 20–30 with every edge cited (a gold set that is "what I believe about
  music" is worthless; include boring middles where a step is easy to skip), adversarial set of 15–20
  including a planted prompt injection, and a held-out set of 10 that is **never looked at** during
  development.
