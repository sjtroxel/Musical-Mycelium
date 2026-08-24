# Rule: Grounding, claims, and the gate

Canonical detail: `docs/planning/07-EVAL-SPEC.md` §2 (as amended) and `08-REVIEW-VERDICT-AND-CATCHES.md`
§2. This is the spine of the project. Hard rules:

- **Claims first, prose second — never side by side.** The agent emits structured claims; a deterministic
  gate approves or rejects each one; the narrative is then generated **from the approved claim set only**.
  The original design had the model emit claims *alongside* prose, and that leaked: prose could assert an
  edge that never became a claim, so groundedness would read 100% while the text hallucinated. If you find
  yourself writing a pipeline where prose generation can see anything other than approved claims, stop —
  the leak is back.
- **The gate is deterministic code, not a model call.** Same pattern as Patchwork: the model proposes, the
  gate decides. A claim passes only if the edge exists in the pinned artifact and resolves to real sources.
- **A `Claim` carries `subject_id`, `predicate`, `object_id`, `source_ids`, `span`.** Without machine-readable
  claims every correctness metric degrades to fuzzy text matching — the exact failure that produced the
  difflib coverage bug in Patchwork.
- **"Grounded" is a provenance guarantee, not a truth guarantee.** Every edge traces to a checkable source.
  Wikidata can still be wrong. Never let project copy, docs, or interview answers slide from "traceable" to
  "correct." The honest follow-up answer is: traceable to a checkable source, the strength of that check
  published per claim, and the gold set cites sources *independent of Wikidata* so divergence surfaces.
- **`contested` is UNREACHABLE on this corpus, and saying otherwise is the error.** *(Amended 2026-08-24.
  This bullet read "Contested is a first-class state, not an error. Musical influence is genuinely
  disputed. Flag it; do not resolve it, and do not silently drop it." — an instruction to build something
  the corpus cannot support.)* Musical influence **is** genuinely disputed; what this corpus cannot do is
  detect the dispute. Every v0.5.0 edge has exactly one source, always Wikidata, so nothing can disagree
  with anything. That is arithmetic, not effort — **decision A1, do not re-litigate.**
  - `contested` and `checks_disagree` are **declared and test-locked-unreachable** in
    `agent/claims.py:UNREACHABLE`. Named rather than silently absent, so a future corpus that could
    express one fails the test instead of quietly making it reachable. Do not delete them and do not
    make them reachable to satisfy a metric.
  - What ships instead is **`verification`** — `HAND`, `PROSE_AUTO`, `ASSERTS_AUTO`, `EXPOSURE_AUTO` —
    on every edge and copied onto every approved claim by the gate, never supplied by the model. It says
    **how strongly one source was checked. It is not a count of agreeing sources and not a disputed
    flag.** In the eval catalog, `verification_mix` replaces the "contested flagging" metric.
  - Phase 6's second source is the precondition. Until it lands, a doc, a metric, or an interview answer
    that implies this system detects disagreement is overstating it.
- **Refusal is correct behavior.** An unsourced influence edge must be refused rather than narrated.
  Report refusal accuracy as a **pair** — true refusals and false refusals — always. A system that refuses
  everything scores perfectly on hallucination and is useless.
- **Never claim coverage the graph does not have.** The corpus skews Western, anglophone, and recent. That
  bias is by construction and must be visible in output, not disclaimed in a footnote.
