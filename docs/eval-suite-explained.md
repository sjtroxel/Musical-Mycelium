# What the eval suite is, in plain English

Phase 4's write-up. No jargon, or jargon explained the first time it appears. This exists because being
able to say all of this out loud, cold, without the page, is a different skill from having built it, and
the second one does not automatically produce the first.

## The problem

The agent answers questions about how music influenced other music. "Where did blues rock come from."
"What came out of dub." It answers by walking a graph of influence that we built and own, and then
writing a short piece of prose about what it found.

So: how do you know it is any good?

The tempting answer is to read some answers and decide they look right. That is not an answer. It does
not scale past ten examples, it changes every time your mood does, and it cannot tell you whether last
week's change made things better or worse. What you need instead is a fixed set of questions, a fixed
definition of a right answer, and a number that comes out the same way every time.

That is all an eval suite is: a test suite for a system whose output is not deterministic.

## The one trick that makes this project's version unusually solid

Most people evaluating a language model end up asking another language model to grade the first one,
because there is no other way to check a free-text answer. That works, sort of, and it is expensive and
soft.

This project mostly does not have to. **We own the graph.** Every influence edge in it came from
Wikidata or MusicBrainz, and it is sitting in a file we control. So when the agent claims "bebop was
influenced by swing", checking it is not a judgement call. It is a dictionary lookup: is that edge in the
file, yes or no.

That one property turns the headline correctness measures into free, instant, deterministic checks:

- **Groundedness** - of the claims the agent made, how many correspond to a real edge. Must be 100%.
- **Citation resolution** - of the sources those edges cite, how many actually resolve. Must be 100%.
- **Refusal accuracy** - when we ask something the graph cannot support, does it decline instead of
  making something up. Reported as a **pair**, always: how often it correctly refuses, and how often it
  wrongly refuses something it could have answered. A system that refuses everything scores perfectly on
  the first half and is useless.
- **Traversal recall** - did it actually visit the nodes the answer needed.
- **Injection resistance** - if a question contains a planted instruction trying to make the agent assert
  something false, does it hold.

These run on every commit, cost nothing, and five of them can block a merge.

## Why the agent cannot lie in the prose

The order matters and it is the single most important design decision in the project. The agent emits
**structured claims first**. A separate piece of ordinary code - not a model, just code - approves or
rejects each one against the graph. Only then is the prose written, and it is written **from the approved
claims only**. It never sees the rejected ones.

The original design had the model write claims and prose at the same time. That leaks: the prose can
assert an edge that never became a claim, so the groundedness score reads 100% while the text is making
things up. Separating them is what makes the number mean anything.

## What "grounded" does and does not mean

Grounded means every edge traces to a checkable source. It does **not** mean the edge is true. Wikidata
can be wrong, and musical influence is genuinely disputed - reasonable people disagree about who
influenced whom. The honest claim is "traceable", never "correct", and that distinction has to survive
into how the project is described out loud.

## Three datasets, and why one of them is encrypted

- **The gold set** - 25 questions, hand-built, every expected edge cited. Includes deliberately boring
  middles, because a set of only dramatic examples flatters a system that skips steps.
- **The adversarial set** - 18 questions designed to break things, including a planted prompt injection.
- **The held-out set** - 10 questions that are **never looked at** during development.

All three were built before the agent could run, so none of them are contaminated by its output.

The held-out set is encrypted, and the reason is worth stating plainly: **the threat is the coding agent,
not the person.** An AI assistant working in this repo greps, opens files to check a schema, and reads
test failures. The moment held-out content lands in its context, every threshold and prompt it touches
afterwards is quietly tuned toward that set, with no way to detect it later. A file named "do not read"
does not stop that. Encryption does.

It is still checkable while sealed. A tool decrypts it in memory and reports problems as case numbers and
problem codes - `heldout_v1_007: claims-diverged` - which says everything you need in order to act and
discloses nothing. A case number is not content.

## Why a score with no noise floor is not a score

Run the same suite twice against the same model with the same inputs and you do not get the same number.
Models are not deterministic. So before any threshold could be set, the identical suite was run **five
times** and the spread recorded.

What came back:

| measure | spread across 5 identical runs |
|---|---|
| groundedness | 0 |
| citation resolution | 0 |
| correct refusals | 12.5 points |
| wrong refusals | 4 points |
| cases fully correct | 38 to 40 of 41 |
| claims approved | 67 to 72 |
| injections that worked | 0, every run |

The point of that table: **a 5-point movement in refusal accuracy is noise, not progress.** Without having
measured it, you would celebrate it. Four cases were identified as genuinely unstable and are named in
the record rather than averaged away.

A trap worth keeping: one measure showed *zero* spread, which read as "this metric is rock solid." It was
not. It was one case failing identically every single time, and the stability was the failure. A
zero-variance number is a reason to ask what is constant, not a reason to relax.

## The judged part, and why it is small

Two things genuinely cannot be checked by lookup: whether a citation actually *supports* the sentence it
is attached to, and whether the prose is any good. Those are judged by a second model - deliberately a
non-Anthropic one, so it is not grading its own family's work.

And a judge with no measured agreement is decoration. So 30 items were hand-labelled by the project's
author, and the judge was run against those same 30 to see how often it agreed. That agreement figure is
**printed next to every judged number, permanently**, and the code refuses to render a judged score
without it.

Measured, over three runs: moderate agreement on citation support, substantial agreement on narrative
quality. Two things learned the hard way there. First, the judge is **not deterministic even at
temperature zero** - two runs with byte-identical prompts disagreed - so every judged number is a sample
and gets quoted as a range, never as a single figure. Second, the temptation to rewrite the rubric until
agreement improves was deliberately not taken: rewriting a rubric using the same labels you are being
scored against is fitting to the answer sheet.

## What it costs

Everything deterministic is free and runs on every commit. The real-model runs cost roughly 36 cents for
all 41 cases, measured rather than estimated. The judged runs are a few cents. Every operation that spends
money sits behind a confirmation prompt that names the estimate first, and the estimate deliberately
rounds *up*, because an estimate that understates spend is the one that causes harm.

The binding constraint is not money, it is requests per minute - the account allows ten - so the suite
paces itself and backs off rather than running everything at once.

## What this phase does not claim

- The deployed public URL still runs a stub, not the real model. "Deployed on Bedrock" is not yet a claim
  this project makes.
- Per-run cost is measured and recorded in committed result files, but has not yet reached CloudWatch,
  because that needs a redeploy that is deferred to phase 5.
- The graph skews Western, anglophone and recent. That is by construction and it is visible in every
  sliced result rather than disclaimed in a footnote. Every number is cut four ways - era, region, how
  densely connected the subject is, and what kind of question was asked - because an aggregate that looks
  healthy while the sparse and non-Western slices fail is the default outcome, not the exception.

## The one-sentence version

Because the ground truth is a graph we own, correctness is a lookup rather than an opinion; everything
that genuinely needs an opinion is judged by a separate model whose agreement with a human has been
measured and is printed beside every number it produces; and no movement is called progress until it is
larger than the noise floor that was measured before any threshold existed.
