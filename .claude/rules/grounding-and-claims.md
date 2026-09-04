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
- **`contested` is REACHABLE as of artifact v0.7.0, and 2 pairs are contested.** *(Amended 2026-09-04,
  phase 6 step 5. This bullet read "`contested` is UNREACHABLE on this corpus, and saying otherwise is
  the error" from 2026-08-24 until then, and before that it read the opposite again — see the history
  below, because the direction of travel is the point.)*
  - **Decision A1 is CLOSED by its own stated precondition arriving, not re-litigated.** A1 said
    disagreement needs two sources and every edge had exactly one; that was **arithmetic and it was
    correct**. Phase 6 step 4 ingested DBpedia. Two sources can now disagree, and two do. Do not read
    this as A1 having been wrong, and do not re-open the question.
  - **`contested` means TWO DIFFERENT SOURCES assert opposite directions for one pair. It does not mean
    a reciprocal pair exists.** Measured on v0.7.0: **6 reciprocal pairs, 2 contested.** The other four
    are one source describing mutual influence, which between genres is frequently a real claim. The
    loose definition overcounts by 3x and would state something false about where the corpus's
    information came from. `graph/corroboration.py` reports both counts and never one alone.
  - **It is a property of a PAIR, derived in `graph/`** — never stamped on an edge, never proposed by
    the model. `checks_disagree` remains declared in `agent/claims.py:UNREACHABLE`; do not delete it and
    do not make it reachable to satisfy a metric.
  - **`verification` and `corroboration` are different fields and must never be collapsed.**
    `verification` — `HAND`, `PROSE_AUTO`, `ASSERTS_AUTO`, `EXPOSURE_AUTO`, `INFOBOX_AUTO`, the two
    `MEMBERSHIP_*` — says **how strongly ONE source was checked**. `Edge.corroboration` says **whether a
    second source agrees**. A corroborated `PROSE_AUTO` edge is **not** thereby a `HAND` edge; a
    corroboration must never promote a tier; a UI must never show one number where there are two. This
    project has already corrected three files once for blurring these, from the other direction.
  - **Still true and still the constraint:** 2,203 of 2,285 influence edges are single-source, so the
    corpus detects disagreement only where DBpedia has an opinion at all. "This system surfaces
    disagreement between two sources on the 82 edges where both speak" is honest; "this system knows
    which influence claims are disputed" is not.
- **Refusal is correct behavior.** An unsourced influence edge must be refused rather than narrated.
  Report refusal accuracy as a **pair** — true refusals and false refusals — always. A system that refuses
  everything scores perfectly on hallucination and is useless.
- **Never claim coverage the graph does not have.** The corpus skews Western, anglophone, and recent. That
  bias is by construction and must be visible in output, not disclaimed in a footnote.
