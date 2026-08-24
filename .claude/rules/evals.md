# Rule: Evaluation

Canonical detail: `docs/planning/07-EVAL-SPEC.md`. Evals are a first-class deliverable here, not a test
suite — they are the stated differentiator and the reason "grounded" is a provable property rather than a
marketing word. Hard rules:

- **Tier 1 is deterministic, free, and runs on every commit.** Because the ground truth is a graph we own,
  the headline correctness metrics are dictionary lookups: does edge (subject, predicate, object) exist in
  the pinned artifact. Groundedness, citation resolution, traversal recall/precision, refusal accuracy,
  **`verification_mix`**, coverage honesty, injection resistance, cost and latency. No approval needed, $0.
  *(This list said "contested flagging" until 2026-08-24. Contested is unreachable on a one-source corpus —
  see `.claude/rules/grounding-and-claims.md`, decision A1 — and `verification_mix` is what replaced it.)*
- **Tier 2 is judged, sampled, and gated.** Citation *support* and narrative quality only. 20–30 samples,
  release candidates only, behind an explicit spend confirmation.
- **Block on correctness properties, track quality preferences.** Blocking: edge groundedness 100%,
  citation resolution 100%, injection resistance zero failures, traversal recall within 5pp of baseline,
  refusal accuracy within 5pp of baseline. Everything else is tracked, not gated. A suite that blocks on
  everything gets disabled within two weeks; a suite that blocks on nothing gets ignored.
- **Five gates exist; the free every-commit run blocks on THREE of them.** *(Added 2026-08-24.)*
  Traversal recall is `SCRIPT_DETERMINED` on a scripted run and injection resistance scores zero cases
  there — the planted injections live in the adversarial set and the free run is gold-only. Both come
  back `N/A`, which is **never counted as a pass**: `render` reports gated / failed / inapplicable as
  three separate counts so an all-inapplicable run cannot look green. **The other two need money.** Do
  not write "blocks on five" anywhere; `eval/thresholds.py` is the authority.
- ~~**Do not invent thresholds before a baseline exists.**~~ **The baseline exists — do not re-invent
  them either.** *(Amended 2026-08-24.)* The noise floor was measured over five identical runs and lives
  in `eval/noise_floor.json`; the gates live in `eval/thresholds.json`, each carrying its measured values
  and its reasoning next to the number. A missing thresholds file prints a `NOT GATED` banner and exits
  0 rather than silently passing. **The trap worth naming: `traversal_recall` measured a 0.0pp spread,
  which read as a rock-solid metric and was one case failing identically every run.** A zero-variance
  number is a reason to ask what is constant, not a reason to tighten a bound.
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
- **The three frozen datasets are built before the agent exists** — otherwise they are contaminated by
  model output. Gold lineage set of 20–30 with every edge cited (a gold set that is "what I believe about
  music" is worthless; include boring middles where a step is easy to skip), adversarial set of 15–20
  including a planted prompt injection, and a held-out set of 10 that is **never looked at** during
  development.
- **As built, 2026-08-24 — two corrections to the line above.** The gold set is **25 cases / 67 claims**
  and the adversarial set **18 cases**, both hand-authored. **The held-out 10 was DRAWN, not hand-built**:
  `eval/heldout_draw.py` samples the pinned artifact to the gold set's shape distribution from a seed only
  he holds, because a curated held-out set inherits the same blind spots the gold set already has, and a
  drawn one removes the hallucination surface entirely. **It has now been run once — 2026-08-24, 10/10.**
  Every report of it carries the run count, and re-running it after tuning is forbidden. The hard rules
  are in `.claude/rules/heldout-set.md`; read that file before touching anything near it.
