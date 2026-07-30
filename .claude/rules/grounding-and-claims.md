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
  "correct." The honest follow-up answer is: traceable to a checkable source, contested claims flagged as
  contested, and the gold set cites sources *independent of Wikidata* so divergence surfaces.
- **Contested is a first-class state, not an error.** Musical influence is genuinely disputed. Flag it;
  do not resolve it, and do not silently drop it.
- **Refusal is correct behavior.** An unsourced influence edge must be refused rather than narrated.
  Report refusal accuracy as a **pair** — true refusals and false refusals — always. A system that refuses
  everything scores perfectly on hallucination and is useless.
- **Never claim coverage the graph does not have.** The corpus skews Western, anglophone, and recent. That
  bias is by construction and must be visible in output, not disclaimed in a footnote.
