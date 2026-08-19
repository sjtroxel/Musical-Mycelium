# Rubric: narrative quality

Version `v1`. One judgement per item, 1 to 5, whole numbers only.

## The question

**Would a reader who asked this question be well served by this answer?**

Four things go into that, and they are listed in the order they break ties: does it answer the question
that was asked; is it coherent as a piece of writing; does it hedge in proportion to what the corpus
actually supports; is it readable.

## What this does NOT ask

- **It does not ask whether the claims are grounded.** They are, by construction — the gate refuses
  anything else. An answer built from correct claims can still be a bad answer.
- **It does not ask whether the prose overstates its claims.** That is the citation support rubric, and
  scoring it twice would double-count one failure and hide another.
- **It does not reward length.** A two-sentence answer to a two-hop question can score 5.

## Levels

### 5 — answers the question, and nothing in it is wasted

Names the lineage the question asked for, in an order that reads as a chain rather than a list. Hedges
where the corpus is thin and says so plainly rather than in a disclaimer sentence bolted on the end. No
repetition, no throat-clearing, no restating the question back.

### 4 — answers the question, with one soft spot

Everything above, minus one: a clumsy transition, one redundant sentence, a hedge that is slightly
heavier or lighter than the evidence warrants, or an ending that trails instead of landing. A reader
gets what they came for and does not notice the flaw unless looking.

### 3 — answers the question, but the reader has to do work

The information is present and correct and the writing is in the way. Symptoms: the chain is stated as
an unordered list of edges; the same fact is asserted twice in different words; the answer opens by
restating the question; the hedging is boilerplate applied uniformly rather than where it belongs. A
3 is a usable answer that nobody would quote.

### 2 — partially answers, or answers something adjacent

Reaches part of what was asked and stops, or drifts into a related lineage without saying it has. Also
2: an answer so hedged that it declines to state what the corpus does support, which is the failure
mode `.claude/rules/grounding-and-claims.md` names — refusing everything scores perfectly on
hallucination and is useless.

### 1 — does not answer the question

Off-subject, incoherent, self-contradictory, or a restatement of the question with claims attached and
no connective sense. An answer about a genre nobody asked about belongs here **even when every claim in
it is correct and cited** — that case is the project's own worst finding and the rubric has to be able
to score it honestly.

## When two levels both fit

**Take the lower one.** Same reason as the other rubric: a tie resolved upward inflates every number
computed from it, permanently and invisibly.

## Calibration notes

- Coverage honesty is a virtue here, not a hedge. "The corpus records one source for this edge" earns
  its line. "This system may be incomplete" applied to every answer does not.
- Do not reward the answer for citing. Citations are mandatory and deterministic; an answer gets no
  credit for a property it could not have failed.
- Read the answer once at reading speed and score that impression. A rubric scored on the third careful
  re-read measures a reader nobody has.
