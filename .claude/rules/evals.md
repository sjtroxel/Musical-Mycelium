# Rule: Evaluation

Canonical detail: `docs/planning/07-EVAL-SPEC.md`. Evals are a first-class deliverable here, not a test
suite — they are the stated differentiator and the reason "grounded" is a provable property rather than a
marketing word. Hard rules:

- **Tier 1 is deterministic, free, and runs on every commit.** Because the ground truth is a graph we own,
  the headline correctness metrics are dictionary lookups: does edge (subject, predicate, object) exist in
  the pinned artifact. Groundedness, citation resolution, traversal recall/precision, refusal accuracy,
  **`verification_mix`**, coverage honesty, injection resistance, cost and latency. No approval needed, $0.
  *(This list said "contested flagging" until 2026-08-24, when contested was unreachable on a one-source
  corpus and `verification_mix` replaced it. **Amended 2026-09-04: contested is REACHABLE at artifact
  v0.7.0** — 2 pairs — so a contested metric is now buildable. **Amended again 2026-09-07, phase 6.5
  step 6: `contested_disclosure` IS in this catalog and IS gated**, on both the free run and the live
  one, by an explicit decision with its threshold recorded.
  **The denominator warning was right and is why the metric is a PROPERTY rather than a rate.** A
  contested *rate* over all edges would measure DBpedia's coverage far more than disagreement — 2,202
  of 2,284 influence edges are single-source. `ContestedDisclosure` computes no rate: its denominator is
  *runs that crossed a contested pair*, and it blocks on **zero silent crossings**, the same shape as
  injection resistance. **It is thin and must be reported as thin** — exactly two contested pairs exist,
  so `minimum_scored_cases` doubles as a coverage lock and losing one FAILS rather than narrowing
  quietly. See `.claude/rules/grounding-and-claims.md`.)*
- **Tier 2 is judged, sampled, and gated.** Citation *support* and narrative quality only. 20–30 samples,
  release candidates only, behind an explicit spend confirmation.
- **Block on correctness properties, track quality preferences.** Blocking: edge groundedness 100%,
  citation resolution 100%, injection resistance zero failures, **contested disclosure zero silent
  crossings**, traversal recall ~~within 5pp of baseline~~ **per case**, refusal accuracy ~~within 5pp
  of baseline~~ **in cases**. Everything else is tracked, not gated. A suite that blocks on everything
  gets disabled within two weeks; a suite that blocks on nothing gets ignored.
  *(The two "within 5pp" phrasings were abandoned as arithmetically unsatisfiable and the strikethroughs
  are kept because the reason generalises. With 20 refusal cases one case IS 5pp, so a 5pp band cannot
  fire on less than one case and one case already reaches it. Traversal is per case for a different
  reason — see the zero-variance trap below. **`traversal_precision` is measured and NOT gated**: its
  floor is 11.4pp, so a 5pp band there would fire on chance alone.)*
- **SIX gates exist; the free every-commit run blocks on FOUR of them.** *(Added 2026-08-24 as
  "five ... THREE"; amended 2026-09-07 when `contested_disclosure` joined and gated on the free run
  too — the scripted trace crosses both contested pairs, so it costs nothing.)*
  Traversal recall is `SCRIPT_DETERMINED` on a scripted run and injection resistance scores zero cases
  there — the planted injections live in the adversarial set and the free run is gold-only. Both come
  back `N/A`, which is **never counted as a pass**: `render` reports gated / failed / inapplicable as
  three separate counts so an all-inapplicable run cannot look green. **The other two need money.** Do
  not write a gate count in prose anywhere, including this line: `eval/thresholds.py:GATE_NAMES` is the
  authority, and this sentence has now been wrong once for exactly that reason.

  **The paid live suite gates all six as of 2026-09-07**, against bounds measured over five identical
  runs of the 56-case set ($2.61, ~2.4 hours). `refusal_accuracy` and `traversal_recall` both exclude
  `gold_v0_1_020` — a diagnosed, reproducible failure — and **nothing else**. Excluding a case for
  being *noisy* is a different act from excluding one that is *understood*, and it is how a gate stops
  measuring what is broken.
- ~~**Do not invent thresholds before a baseline exists.**~~ **The baseline exists — do not re-invent
  them either.** *(Amended 2026-08-24.)* The noise floor was measured over five identical runs and lives
  in `eval/noise_floor.json` — **re-measured 2026-09-07 at artifact v0.7.1 over the 56-case set; the
  v0.5.0 floor it replaced is gone** — and the gates live in `eval/thresholds.json`, each carrying its measured values
  and its reasoning next to the number. A missing thresholds file prints a `NOT GATED` banner and exits
  0 rather than silently passing. **The trap worth naming: `traversal_recall` measured a 0.0pp spread,
  which read as a rock-solid metric and was one case failing identically every run.** A zero-variance
  number is a reason to ask what is constant, not a reason to tighten a bound.

  **IT HAPPENED AGAIN AT THE NEXT BASELINE, 2026-09-07, and this time it was proved rather than
  suspected.** `traversal_recall` read an identical 203/209 in all five runs; per case, **37 cases
  scored 1.0 every run and `gold_v0_1_020` scored 0.143 every run**. Same metric, same cause, a corpus
  three times larger and a different case count. Treat this as the default hypothesis for any 0.0pp
  spread in this project rather than as a historical curiosity, and **check the per-case data before
  writing a bound off an aggregate**.

  **A second lesson from the same baseline: five runs is the floor for a reason.** `adv_018` failed runs
  1-3 and passed runs 4-5. Three runs would have recorded a coin as a reproducible failure — which is
  exactly what the 2026-08-17 floor did to `gold_v0_1_020`'s neighbours and had to be corrected.
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
