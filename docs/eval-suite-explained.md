# What the eval suite is, in plain English

Phase 4's write-up. No jargon, or jargon explained the first time it appears. This exists because being
able to say all of this out loud, cold, without the page, is a different skill from having built it, and
the second one does not automatically produce the first.

*Counts in the phase 4 part are phase 4's, and they are kept because the reasoning around them still
holds. The sections added at the end bring them forward; the newest is dated 2026-09-13.*

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
Wikidata, and it is sitting in a file we control. So when the agent claims "bebop was influenced by
swing", checking it is not a judgment call. It is a dictionary lookup: is that edge in the file, yes or
no.

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

These run on every commit and cost nothing. Five of them are wired as gates — but on the free run, only
**three** can actually block a merge. Traversal recall on a scripted run is determined by the script
rather than the model, and the planted injections live in the adversarial set, which the free run does not
include. Both come back as `N/A`, and `N/A` is never counted as a pass: the report prints gated, failed,
and inapplicable as three separate counts, so a run where nothing was gated cannot come out looking green.
The other two gates need money.

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

- **The gold set** - 25 questions at phase 4, 43 today, hand-built, every expected edge cited. Includes deliberately boring
  middles, because a set of only dramatic examples flatters a system that skips steps.
- **The adversarial set** - 18 questions at phase 4, 22 today, designed to break things, including a planted prompt injection.
- **The held-out set** - 10 questions that are **never looked at** during development. This one was not
  hand-written: it was **drawn** from the graph by a seeded random sample matched to the gold set's mix of
  question shapes. That was deliberate. A held-out set someone curates inherits the same blind spots as
  the gold set they curated first, and a drawn one cannot contain a hallucinated edge at all, because
  every case is generated from edges that are already in the file.

All three were fixed before the agent could run, so none of them are contaminated by its output.

The held-out set is encrypted, and the reason is worth stating plainly: **the threat is the coding agent,
not the person.** An AI assistant working in this repo greps, opens files to check a schema, and reads
test failures. The moment held-out content lands in its context, every threshold and prompt it touches
afterwards is quietly tuned toward that set, with no way to detect it later. A file named "do not read"
does not stop that. Encryption does.

It is still checkable while sealed. A tool decrypts it in memory and reports problems as case numbers and
problem codes, in the form `<case id>: claims-diverged`, which says everything you need in order to act
and discloses nothing. A case number is not content.

**The set in the repository today has been run exactly once, and came back 10 of 10.** It was drawn on
the morning of 2026-09-12 against artifact 0.10.0, sealed, and checked without being read: ten cases, two
of them refusals, matching their manifest, with nothing diverging from the corpus they were drawn
against. That evening, after the live suite had been re-measured and its thresholds rewritten, it was run
once. The rule for a provider outage was agreed before the run: a run cut short only by provider errors
would not count, and anything else would, whatever it said. It finished with no errors and no retries.

That result is one run of ten cases, and it is reported at that size. It is evidence that the system
holds up on questions nobody tuned against, not a rate worth a confidence interval. Two refusal cases is
a thin denominator, and the draw happened to contain no case placed outside the US and UK - five are
placed there and five record no region - so it says nothing about non-Western material, which is where
the corpus is weakest. It is not run again until the next freeze, because a set re-run after a change
made because of its own result has stopped measuring generalization and started measuring how many
attempts it took.

An earlier set was opened once, on 2026-08-24, and came back 10 of 10 at artifact 0.5.0 with every metric
matching the development set. That was a real negative on the overfitting question, and one observation
rather than a rate: with two refusal cases and no error bar, one flip moves that metric fifty points. It
was retired on 2026-09-12 rather than re-run, because the corpus had roughly tripled beneath it and two
of its cases no longer matched the graph they had been drawn against. That measurement is kept and stays
auditable, but it is not evidence about the set that replaced it.

One thing no drawn set here can tell us: nothing is planted in it, so injection resistance has no
held-out evidence at all. That question is open, not passed.

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

And a judge with no measured agreement is decoration. So 30 items were hand-labeled by the project's
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
all 41 cases at phase 4, measured rather than estimated; the 63-case set of 2026-09-12 costs about 75
cents a run. The judged runs are a few cents. Every operation that spends
money sits behind a confirmation prompt that names the estimate first, and the estimate deliberately
rounds *up*, because an estimate that understates spend is the one that causes harm.

The binding constraint is not money, it is requests per minute - the account allows ten - so the suite
paces itself and backs off rather than running everything at once.

## What this phase does not claim

- ~~The deployed public URL still runs a stub~~ and ~~per-run cost has not yet reached CloudWatch~~.
  **Both closed on 2026-08-24, at phase 5 step 0.** The public URL runs Claude Haiku 4.5 on Bedrock, and
  per-query token counts land in CloudWatch from real traffic. Struck rather than deleted because the
  honest version of this section is what it looked like while those were true.
- The graph skews Western, anglophone and recent. That is by construction and it is visible in every
  sliced result rather than disclaimed in a footnote. Every number is cut four ways - era, region, how
  densely connected the subject is, and what kind of question was asked - because an aggregate that looks
  healthy while the sparse and non-Western slices fail is the default outcome, not the exception.

## The one-sentence version

Because the ground truth is a graph we own, correctness is a lookup rather than an opinion; everything
that genuinely needs an opinion is judged by a separate model whose agreement with a human has been
measured and is printed beside every number it produces; and no movement is called progress until it is
larger than the noise floor that was measured before any threshold existed.

---

## What phase 6.5 added, in the same plain English

*Written 2026-09-07, the day the phase closed. Phase 4 built this suite; phase 6.5 is the first time it
was pointed at a corpus with two sources in it, and several things that had been true stopped being true.*

### The system can now say its sources disagree

The graph is built from two places now — Wikidata and DBpedia. Mostly they agree, or only one of them
has anything to say. But for two pairs of genres they flatly contradict each other: one says electropop
came out of electroclash, the other says the opposite. Both are cited. Neither is obviously wrong.

Until this phase the system knew that and could not say it. The disagreement was computed, displayed as a
statistic on the coverage panel — "2 contested pairs" — and completely absent from any actual answer. Ask
where electropop came from and you got a confident answer that looked exactly like every other answer.

Now the answer carries a note: *these two sources disagree about this, here is what each one says, and
this graph is not going to tell you which is right.* Both directions get identical weight, on purpose.
Picking a winner would be inventing a fact.

**What it deliberately does not do is put that in the prose.** The prose is written by the AI model, and
the model is only ever shown claims that survived the checking step. If we handed it a disagreement, it
could write sentences about it that nothing had checked. So the disagreement sits *beside* the written
answer rather than inside it — the page shows it, the model never sees it.

### Refusals stopped lying about the graph

When the system can't answer, it says so. That was already true. What was wrong was *what* it said: every
refusal was phrased as "this graph has no sourced answer", even when the graph had plenty and that
particular attempt had simply come up empty.

There is a real difference between "we looked and there is nothing here" and "this run didn't find it",
and the second was being reported as the first. Two measured examples: the system told users acid jazz
had no documented influences when the graph holds five, and said the same of an artist with four. Both
were false statements about the corpus, produced by a run that had a bad afternoon.

There are three messages now, and only one of them claims the graph is empty — the one where it actually is.

### The most interesting bug of the phase

One test case had been failing for weeks: *"How does femtanyl connect back to Woody Guthrie?"* — femtanyl
being a musician. It failed 16 times out of 17. Everyone assumed the chain was too long, or the corpus
too thin.

It was neither. We started recording what the model actually *did* rather than just what it produced, ran
the case once, and the answer was immediate: the model typed **fentanyl** — the drug — because that is the
far more common word. That name isn't in the graph, so it got nothing back, and gave up.

Nothing was broken. The graph, the search, and the path-finding all answer that question perfectly in a
single step. The model just mistyped the name of the thing it was asked about.

**The obvious fix turned out to be a trap.** If someone types a name we don't have, why not suggest the
close ones? Because we measured what "close" means in this corpus, and found eight pairs of *real*
entities one character apart — including `funk rock`/`punk rock`, and `Joy Orbison`/`Roy Orbison`, who are
a contemporary electronic producer and a 1960s rock legend. Suggesting near-matches would trade an honest
"I don't know" for a confident, perfectly-cited answer about the wrong person. **That is the worst trade
this project can make**, because every check we have would pass it.

### Why five identical runs, and what they cost

The suite has thresholds — numbers that decide whether a change made things worse. Setting them requires
knowing how much the results move when *nothing* changes, because a threshold tighter than the natural
wobble fires at random and teaches everyone to ignore it.

So: five identical runs, $2.61, about two and a half hours. What they showed:

- **Four of 56 questions changed answer between identical runs.** Same code, same data, same question.
- **The amount of evidence behind an answer swung 17%** — some runs gathered 182 supporting facts, others
  218 — while the accuracy of that evidence stayed at 100% every time.
- **One case failed three runs in a row and then passed twice.** Had we stopped at three runs, we would
  have written it down as permanently broken. It is a coin.

And the finding worth the whole exercise: one score came back *identical* in all five runs, which looks
like the most reliable number in the set. It isn't. Thirty-seven questions score perfectly every time and
one fails identically every time, and the average of those two things never moves. **A number that never
changes is a reason to ask what is stuck, not a reason to trust it** — and this is the second time that
exact trap has been caught in this project.

### The one-sentence version

The system can now tell you when its sources disagree, it stopped claiming the graph is empty when it
isn't, and its pass/fail thresholds are set from measured noise rather than from hope — which cost $2.61
and revealed that a fifth of what the suite reports moves on its own.

---

## What the phase 7.7 re-baseline added

*Written 2026-09-13. Between phase 6.5 and phase 7.7 the corpus gained a teaching layer (artifact
0.10.0) and the live set grew from 56 cases to 63, so the thresholds set on 2026-09-07 no longer
described the thing they were gating. They were measured again from scratch rather than carried over.*

### Five more identical runs, and two that did not count

Five full runs of all 63 cases, on 2026-09-12, about 75 cents each. Two earlier attempts that afternoon
were lost to Amazon's model service returning "unavailable" errors, and they are kept on file but never
pooled, because a run missing a case measures a different set. The harness now retries a case that got
no answer because the service was unavailable, up to twice, and a full run stops at the first case that still fails rather than
producing a result nobody can use. A case that answered *wrongly* is never retried: that is the result.

What the five runs showed:

- **Five of 63 questions changed answer between identical runs.** The same kind of wobble as four of 56
  at the previous baseline, on a set seven cases larger.
- **Groundedness and citation resolution stayed at 100% in every run, and no planted injection worked.**
- **The traversal trap turned up a third time.** The aggregate moved by less than half a point, which
  looks like stability. Per case, 41 questions reached their full path every run, the femtanyl case
  reached a seventh of it every run, and one other case dropped once. The bound is written per case for
  that reason, and it now covers 41 questions rather than 37.

### Two exclusions, each with a diagnosis

A case can lose its vote on whether a release is blocked only when the reason it fails is understood,
never because it is noisy. Two qualify.

- **The femtanyl case**, excluded since 2026-09-07 and still failing the same way every run: the model
  looks up the drug.
- **A West African influence question**, excluded on 2026-09-12. It was written to expect a refusal,
  because the graph could source almost none of that history when it was authored. The next day DBpedia
  arrived with sourced edges from "music of Africa", and in all five runs the model found that chain and
  narrated it with every claim grounded. The case's premise failed, not the model. Whether an answer at
  the level of a continent is honest for a question about West Africa is a dataset decision, so the case
  is owed a rewrite, not a pass.

Both still run and still count in every total and every slice. The five cases that flip between runs
are deliberately left in the gates.

Excluding a case that fails every run has a reason beyond tidiness: the day it is fixed, a bound that
still counts it quietly gains a spare case of slack that nobody decided to grant.

### The first gated run failed, and what happened next

The five baseline runs could not store a pass or fail, because the thresholds were written after them.
So on 2026-09-13 one more full run was made, the first to be judged against the new thresholds, and it
**failed**. Two questions the system can answer were refused in the same run. Both were already on the
list of cases that flip between identical runs, each had refused before, just never together, and no
code had changed since the baseline. The threshold allowed one wrong refusal; the run had two.

Running again until the gate goes green would turn the gate into a coin you keep flipping. So before a
second run started, the rule was set: if it passes, deploy and publish the failure next to the pass; if
it fails, stop, and work out why those two questions refuse. It passed all six, and the report shows both
runs.

The failed run also turned up something more interesting than either verdict. Asked **"Where did house
music come from?"**, which the graph cannot source, the model answered a different question: what came
*out of* house music, with 27 claims that were all real and all correctly cited. Every grounding check
passed, because every sentence was true. It is the Orbison problem again, with the direction of the
question swapped instead of the name, and it was caught only because that test expects no claims at all.

### The held-out set, run once

With the thresholds committed, the sealed set was run for the first and only time at this freeze: 10 of
10, every claim grounded, both refusals correct. The section on the three datasets above states what that
does and does not show, and the size it was measured at.

### The one-sentence version

The corpus and the question set both grew, so the noise was measured again instead of assumed, the two
cases allowed out of the gates each have a written diagnosis, and the held-out set was spent exactly once
at the end, reported at the size of ten questions rather than as a rate.
