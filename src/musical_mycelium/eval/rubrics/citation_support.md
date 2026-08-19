# Rubric: citation support

Version `v1`. One judgement per item, three levels, no fourth.

## The question

**Does the narrative assert exactly the claim it was built from, and nothing the claim set does not
carry?**

Read the answer, then read the claim row printed under it. Score the relationship between the two.

## What this does NOT ask

- **It does not ask whether Wikidata is right.** Every claim here already traces to a checkable source;
  that is what "grounded" means in this project and it is a provenance guarantee, not a truth guarantee.
  An answer can be perfectly supported by its claim while the underlying edge is historically disputed.
  Score the support, not the history.
- **It does not ask whether the citation resolves.** That is deterministic, measured on every run, and
  sits at 100%. A judge re-asking a question code already answered measures nothing.
- **It does not ask whether the claim is the most interesting one available.** Traversal recall covers
  what was reached; this covers what was said about it.

## Why the question is shaped this way

The gate guarantees that every claim is a real edge with real sources. Nothing guarantees that the
**prose** stays inside the claim set. Synthesis is a language model writing from an approved list, and
the characteristic failure of that arrangement is not inventing an edge — the gate makes that
impossible — it is *decorating* one: adding a decade, a city, a causal mechanism, or a strength of
influence that no approved claim carries. That decoration is invisible to every deterministic metric in
the catalog, because the claims underneath it are all real.

So this is the judged half of the grounding story, and it is the only place in the suite where the
question "did the prose overstate the evidence" gets asked at all.

## Levels

### SUPPORTED

The sentence asserting the claim says what the claim says. Direction is right, the entities are the
ones in the claim row, and any qualifier in the prose is either in the claim set or is hedging
(`is associated with`, `is cited as an influence on`).

> Claim: `blues rock -influenced_by-> blues`
> Prose: "Blues rock is recorded as drawing on blues."

Also SUPPORTED: prose that adds nothing but connective tissue — "which in turn", "from there" — and
prose that correctly names the source tier or flags the corpus limit.

### OVERSTATED

The claim is there and the prose asserts more than it. This is the level that matters and it is the
easiest to score too generously, so the test is mechanical: **point at the extra fact.** If you can
underline a word carrying a date, a place, a mechanism, a magnitude, or a causal direction that no
claim row supplies, it is OVERSTATED.

> Claim: `heavy metal -influenced_by-> blues rock`
> Prose: "Heavy metal emerged directly out of blues rock in the late 1960s, when British bands
> amplified its riffs." — the decade, the country, and the mechanism are all unsupplied.

Hedging that dissolves ("may have been shaped by" → "was shaped by") is OVERSTATED. So is turning an
influence edge into a claim of origin, descent, or invention.

### UNSUPPORTED

The prose asserts something the claim set does not carry at all: a different pair of entities, a
reversed direction, or an edge that simply is not in the rows printed. A reversal is UNSUPPORTED rather
than OVERSTATED — it is a different claim, not a bigger one.

> Claim: `bebop -influenced_by-> swing`
> Prose: "Swing grew out of bebop." — backwards, and the corpus says the opposite.

Also UNSUPPORTED: an answer that never asserts the claim it was built from, because then the claim is
not supporting the prose at all.

## When two levels both fit

**Take the worse one.** A rubric that resolves ties upward reports a system that is better than it is,
and every reader of the number downstream inherits that.

## Calibration notes

- Judge the sentence that carries the claim, not the whole answer. The answer's overall quality is a
  separate metric with a separate rubric.
- A claim's `verification` tier is context, not a score input. `PROSE_AUTO` does not make prose
  OVERSTATED; it means the edge was machine-checked, which the answer may honestly say.
- An answer that refuses is not scored here. Refused cases carry no claims and are not in this pool.
