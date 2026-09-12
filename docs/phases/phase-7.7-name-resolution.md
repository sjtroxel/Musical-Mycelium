# Phase 7.7 — Name Resolution (v0.9.5)

> **Scope doc.** Written 2026-09-11, at the moment the phase was conceived, which is the rule: *"A phase
> conceived later gets its own scope doc when it is conceived."* Written before anything in it is built.
> Its IMPLEMENTATION doc is written immediately before it is built, after phase 7.6 closes, so it can
> absorb what 7.6 teaches.
>
> **Inserted by his decision on 2026-09-11**, directly after phase 7.6 and before phase 7.5 resumes.
> Product **v0.9.5**, on the v0.6.5 precedent for a phase that sits between two others. **It cuts no
> artifact of its own**: it runs on v0.10.0, which phase 7.6 cuts with the aliases this phase needs
> already stored on the nodes.

## 0. Why this phase exists

**Typing "mozart" into the site refuses, and phase 7.6 alone does not fix that.** 7.6 puts Wolfgang
Amadeus Mozart into the corpus, but the resolver only accepts an **exact** match on a node's full label
(`graph/memory.py:exact_matches`), and the agent is instructed never to substitute a suggestion. So
"mozart" gets a refusal with "Wolfgang Amadeus Mozart" offered as a suggestion the agent may not take.

**It is not a Mozart problem.** He put it this way: "dolly" should work for Dolly Parton. People name
musicians by one name all the time, and every one of those queries refuses today.

**Why it is not simply "match partial names".** Phase 6.5 measured a near-miss resolver and **rejected
it**: 8 real label pairs in the corpus sit one edit apart, including Joy Orbison and Roy Orbison. A
resolver that guesses trades an honest refusal for an answer that is fully grounded, correctly cited,
and about the wrong person, and no metric in this project can see that failure. A partial-name resolver
that picks on its own has the same shape.

**His decision, 2026-09-11: offer, and let the person choose.** A partial or alias match is never
resolved by the system. It is offered: "Did you mean Dolly Parton?" as one click, or every candidate
when there are several ("mozart" offers Wolfgang Amadeus Mozart and Leopold Mozart once 7.6 adds
Leopold). The human makes the choice, so the system never answers about someone the person did not
pick. The Orbison finding stands untouched: nothing here guesses.

## 1. What this phase is for

**To let people find a musician or a genre by the name they actually use, without the system ever
choosing for them.**

## 2. Delivers

- **A NEW HELD-OUT SET, DRAWN ON v0.10.0, AND IT IS THIS PHASE'S FIRST TASK — his decision
  2026-09-11.** The sealed ten were drawn on artifact v0.5.0. At the phase 7.6 re-pin
  `make heldout-check` reported `artifact-pin-moved` **and `claims-diverged` on `heldout_v1_004` and
  `heldout_v1_005`**: two of its cases no longer match the corpus. Nothing was re-sealed or opened, per
  `.claude/rules/heldout-set.md`, and the stale set cannot measure generalization on a corpus three times
  larger than the one it was drawn from.
  **He draws it, not an agent.** `eval/heldout_draw.py` samples the pinned artifact to the gold set's
  shape distribution from a seed only he holds; an agent may not choose subjects, draft cases, or ask
  which he chose. What an agent may do is run `make heldout-verify`, read `make heldout-check`'s ids and
  problem codes, and confirm the key was not overwritten (`make heldout-key` refuses an existing key, and
  that refusal is not to be worked around).
  **The new set's run count starts at 0, and the old set's single run does not carry over.** Until the
  draw exists, every report says generalization is **untested** on this corpus rather than passed. It is
  run once, at a freeze, and only if nothing was tuned in response to it.

- **Alias matching**, from Wikidata's own `en` and `mul` aliases, stored on nodes by phase 7.6.
  Wikidata lists "Mozart", "Beethoven", "Bach", "Chopin" and "Brahms", but not "Liszt" or "Schumann",
  checked 2026-09-11. Sourced, and uneven, and the unevenness is the source's.
- **Whole-word partial matching**: every word of the query appears as a whole word in the candidate's
  label or an alias. "dolly" and "parton" both reach Dolly Parton; "roy orbison" does **not** reach Joy
  Orbison, because "roy" is not a word in that label.
- **A disambiguation offer in the answer stream**: a distinct event carrying the candidates, rendered
  as clickable choices. Choosing one re-asks the question with the chosen node's exact label.
- **The rule, stated so it cannot drift:** exact label match resolves, as today. Anything else is
  offered, never resolved. An offer is not an answer and produces no claims.

## 3. Explicitly not in this phase

- **Any automatic resolution beyond exact labels.** Not for a unique partial match, not for an alias,
  not for a "confident" case. That is the decision this phase exists to hold.
- **Edit-distance or fuzzy matching.** Phase 6.5 rejected it with a measurement. "dolly" is a whole
  word of "Dolly Parton"; "dolyl" is a typo, and typos still refuse.
- **New corpus, new predicates, new tools beyond what resolution needs.** The corpus is v0.10.0.
- **Changes to what an existing exact-label query resolves to.** Every query that resolves today
  resolves to the same node afterwards, and a test proves it over every name in every dataset, chip and
  README example.

## 4. Key decisions this phase makes

- **Where the offer is produced.** In the resolver (deterministic, testable, no model call), or by the
  agent reading `did_you_mean`. The first keeps the no-guess property in code rather than in a prompt.
- **What the offer looks like on the wire.** A new event type in the SSE contract (`SPEC.md` §6), or a
  structured refusal. An offer is not a refusal, and the report's refusal metrics must not count it as
  one without a decision.
- **How offers are scored.** A case that used to refuse and now offers is neither a correct refusal nor
  an answer. `refusal_accuracy` needs a rule for it before the live re-baseline, not after.
- **Whether genres get aliases too.** "R&B" for rhythm and blues is the same problem on the other axis.
  7.6 stores aliases for every node, so this is a scope choice rather than a data one.

## 5. Definition of done

1. Typing "mozart" into the site offers Wolfgang Amadeus Mozart (and Leopold Mozart, if 7.6 ingested
   him), and choosing one returns a gated, cited answer about the person chosen.
2. Typing "dolly" offers Dolly Parton; typing "roy orbison" still refuses.
3. No query that resolves by exact label today resolves differently, proved by a test over every name in
   the gold, adversarial, tour and live sets, the chips and the README.
4. Nothing resolves without either an exact label match or a human choice. A test asserts it.
5. The live re-baseline for **both** 7.6 and 7.7 runs at this phase's close, over five identical runs,
   behind an explicit spend confirmation (his decision 2026-09-11, to pay for it once). The six gates
   hold.
6. v0.10.0 and both phases' code are deployed together, `make check` is green, and the budgets hold.

## 6. The one-way door, named up front

**Resolution is where "grounded" meets "about the right thing".** A grounded answer about the wrong
person is the failure no gate catches. This phase widens what the resolver will *consider* and keeps
exactly one path to *resolving*: an exact label, or a person's click.

## 7. Known risks

- **Offers everywhere.** A common word ("john", "jazz") matches hundreds of labels. The offer list needs
  a cap and a rule for what to show when the list is too long to be useful, and "too long" is a refusal.
- **Aliases are noisy.** Wikidata aliases include codes and transliterations. They only ever produce
  offers, so noise costs a click, not a wrong answer, but a noisy offer list erodes trust in the page.
- **Scoring drift.** Cases that refused before may now offer. That must be decided as a rule before the
  re-baseline, or the baseline measures an unscored behavior.
- **Scope creep into search.** This is resolution, not a search page. No ranking, no autocomplete.

## 8. Left for the IMPLEMENTATION doc

The offer's wire format and UI. The candidate cap. How an offer is scored. Whether genres get aliases.
The test that proves exact-label resolution is unchanged. The re-baseline plan and its cost, measured
against the case count 7.6 leaves behind.
