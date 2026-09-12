# Classical lineage, explained

Phase 7.6, built 2026-09-11. This is the plain-English walk-through: what changed, why, and which
sentences about it are true. The as-built detail is
`docs/phases/phase-7.6-classical-lineage-IMPLEMENTATION.md`; this file is the version you can read
aloud.

## The problem, found by typing a name into the live site

He typed **"mozart"** and the site refused. The refusal was correct given the corpus, and the corpus was
wrong: Mozart was not in it.

The cause was one query parameter. The ingestion asked Wikidata for labels in English (`languages=en`),
and Wikidata now lets an item hold its label in **`mul`** — a default shared across languages — with no
separate English one. Mozart (`Q254`) is such an item. The label came back empty, and an empty label
failed the check that compares a label against its article title, so he was excluded as `MISLINKED`.
44 entities were in that state, Taylor Swift, B. B. King, Dua Lipa and Radiohead among them.

**The bug excluded; it did not corrupt.** No node in any earlier artifact carries an empty label, and the
genre axis was untouched: 0 of 395 genre entities were affected.

## What the phase added

**One new relationship: `studied_with`.** Wikidata's P1066, "student of", stored as *student*
`studied_with` *teacher*.

The reason to add it is arithmetic. Of 9,212 composers born before 1880 with an English article, **56**
carry an influence statement and **1,766** carry a teacher. Before this phase the corpus could say almost
nothing about music before 1900, not because the history is undocumented but because it is documented as
**teaching** rather than as influence. Classical lineage is a chain of teachers.

Also added: **birth years** for artists (2,652 of 2,889 have one, 2,111 born before 1900), **aliases**
stored but not yet used, and the 19 artists the `mul` bug had excluded, Mozart among them.

## The one distinction the whole phase rests on

**Teaching is not influence, and the corpus must never say it is.**

This is not pedantry, and it is not a claim that a teacher had no effect on a student. It is about what a
source says. P1066 says "student of". If the system stored that as "influenced by", it would be asserting
something no source asserted — the project's central failure mode, where *traceable* quietly becomes
*correct*. So:

- The two relationships are **separate predicates** with separate verification tiers.
- Every surface that shows a claim takes its verb from the claim's predicate: the synthesis prompt, the
  claim list, the map, the node inspector. None has a fixed verb, and none falls back to influence
  wording for a relationship it does not recognise.
- The map draws teaching as a **dashed green line**, distinct from solid influence and dotted membership.
  When a pair is both — Beethoven studied with Haydn *and* was influenced by him, two separately sourced
  edges — both lines are drawn, offset so neither hides the other.
- Asked "who influenced Beethoven?", the agent may also fetch his teachers, and reports them **as
  teachers**, under their own heading. That was his decision: teaching is often a strong influence, and
  the honest way to say so is to name it as teaching.

## How strongly a teaching claim is checked

Its tier is `TEACHING_PROSE_AUTO`, and it means exactly one thing: **the student's Wikipedia article
names the teacher in body prose**. It does not mean the sentence is about study.

That limit was measured before ingesting anything, by hand-reading 40 rows. Of the 30 the check passed,
**27 rested on a sentence stating study and 3 did not** — roughly one in ten. The same check over-accepts
*influence* at about one in five, because "studied with X" is exactly the sort of thing a biography says
while an influence is something a writer chooses to assert.

The hand check's headline result is the opposite of P279's, the taxonomic property this project refuses to
ingest: **zero of 40 teaching rows were a wrong relation and zero were inverted**, against 47 of 47
category errors for P279. That is why one is in the corpus and the other is not.

**The weakness showed up immediately, on the most famous case in the set.** All three of Mozart's teaching
edges passed the prose check on *his* article, and for two of them the matched sentence never mentions
study: Johann Christian Bach appears as "a particularly significant influence", and Padre Martini as
someone Mozart "met" in Bologna. Study-stating prose exists for both, but in the teachers' articles. The
gold case quotes it from there and says so.

## What was thrown away, and why that matters

2,487 rows passed the automated checks. **18 were then removed by hand**, after review:

- **Two were backwards.** Ondříček's article names Kubelík as *his* pupil; Benoist's names Adolphe Adam as
  *his* student. Direction is the one error that turns a correct claim into false history, so every edge
  whose teacher was recorded as *younger* than the student — 53 of them — was read by a person. 43 were
  kept, because a younger teacher is suspicious rather than impossible.
- **Nine were successions, not lessons.** A *maestro di cappella* who succeeded another, recorded as that
  person's pupil. The hand check saw the shape twice in 40 rows and asked the build to measure it across
  the whole population rather than guess.

## What it cannot do

- **It cannot resolve "mozart".** Resolution still needs an exact full label, so the site answers
  "Wolfgang Amadeus Mozart" and refuses "mozart". That is phase 7.7's job, and it will **offer** choices
  rather than guess.
- **It does not know who taught whom outside its bound.** Only composer-to-composer teaching where both
  people have an English article, students born before 1900. A performer who taught but is not recorded as
  a composer is absent.
- **It has no second opinion on teaching.** All 2,469 teaching edges come from Wikidata. The corpus can
  still only surface disagreement where DBpedia has an opinion, which is 82 of its 2,309 influence edges.
- **Its pre-1900 artists are overwhelmingly Western European**, because that is where these records are
  dense. The corpus does not record where a person came from, so it cannot count that skew — the coverage
  panel states it instead.

## How you can tell it works

Ask the running app **"Who did Ludwig van Beethoven study with?"** It returns four cited claims —
Clementi, Neefe, Salieri, Haydn — each linking to the Wikidata statement it came from, and prose that says
*studied with* and never *influenced by*.

Underneath, a test renders the synthesis prompt for **every teaching answer the corpus can produce**
— 8,373 of them — and checks that no teaching claim ever reaches the model under an influence verb or
heading. Zero do. What that test cannot prove is that a model obeys the instruction it is given; that is
watched by live captures and by the judged pass at phase 7.7's close.
