# Name resolution, explained

Phase 7.7, built 2026-09-12. This is the plain-English walk-through: what changed, why, and which
sentences about it are true. The as-built detail is
`docs/phases/phase-7.7-name-resolution-IMPLEMENTATION.md`; this file is the version you can read aloud.

## The problem, the same one that started phase 7.6

Phase 7.6 fixed the bug that had kept Mozart out of the corpus. After it, typing **"mozart"** still
refused, and this time the corpus was right. Mozart is in it, as **Wolfgang Amadeus Mozart**. So are
Leopold Mozart and Franz Xaver Wolfgang Mozart.

The system resolves a name only when it matches a label exactly. "mozart" matches no label, so it
refused, and a person who typed the name everyone uses got told the graph did not have him. The same was
true of "dolly", "beethoven", "chopin", "bach" and "r&b".

The obvious fix is to guess. Phase 6.5 measured why that is the one fix this project cannot make.

## Why the system still never guesses

The corpus holds 8 pairs of real names one character apart. The sharpest is **Joy Orbison and Roy
Orbison**: a contemporary electronic producer and a 1960s rock singer, both in the graph. A system that
quietly turned one into the other would produce an answer with every claim grounded and every citation
resolving, about the wrong person, and no check in the suite would notice. Groundedness guarantees an
answer traces to a source. It says nothing about whether it is the answer to the question asked.

So the rule did not change, and this phase exists to hold it:

- **An exact label match resolves**, as it always has.
- **Anything else is a choice a person makes.** Not a unique partial match, not a unique alias, not a
  case that looks obvious. The system never picks.

What changed is that a refusal no longer ends the conversation.

## What happens now

Ask "Where did mozart come from?" and the answer is still a refusal. Underneath it, the page lists every
name in the graph that "mozart" could mean, as buttons. Choose **Wolfgang Amadeus Mozart** and the
question is asked again with his full name in place of the word you typed. That second question resolves
exactly, like any other, and comes back as a normal gated, cited answer. The first answer stays on the
page with its refusal and its choices, so the record of what happened is not rewritten by what you did
next.

For "mozart" the list has five names:

- Wolfgang Amadeus Mozart, Leopold Mozart and Franz Xaver Wolfgang Mozart, because "mozart" is a word in
  their names;
- **Timbaland**, *also known as "Mozart Timadeas"*;
- **Samuel Wesley**, *also known as "The English Mozart"*.

The last two look strange, and the page says why each one is there rather than hiding them. They come
from Wikidata's own list of alternate names, which is a real source and an uneven one. Showing a
candidate with its reason is honest about a noisy source; quietly dropping the ones that look odd would
be ranking by taste.

## How a name gets onto the list

Three ways, and all three use the same whole-word rule the rest of the system already used:

1. **Its name contains every word you typed**, as whole words. "dolly" and "parton" both reach Dolly
   Parton. "roy orbison" cannot reach Joy Orbison, because "roy" is not a word in that name, and a test
   now asserts that in both directions.
2. **One of its recorded alternate names does.** Wikidata lists "R&B" for rhythm and blues, which is part of
   how "r&b" now reaches six genres. It lists "Mozart", "Beethoven", "Bach", "Chopin" and "Brahms" for those
   composers, and does not list "Liszt" or "Schumann" (checked 2026-09-11). Of the 3,628 nodes, 2,423
   carry at least one alternate name, so this helps unevenly, and the unevenness is Wikidata's.
3. **A trailing "music" is folded.** "electro music" now offers **electro**, where it used to refuse.

**Alternate names can only ever produce a choice, never a resolution, and the data is the reason.**
37 alternate names are the exact label of a *different* node: "heavy metal" is listed as another name
for "traditional heavy metal" and is also a node of its own. 27 are claimed by more than one node at
once. A resolver that trusted alternate names would be wrong in exactly those places, silently.

## The limits on the list

- **25 names or fewer: every one is shown. More than 25: none are, and the total is.** "bach" shows all
  14. "metal" reaches 34 and "music" reaches 235, so the page states the count and asks for more of the
  name. Showing the first 25 of a longer list would mean choosing which 25, and that is ranking under
  another name.
- **A single letter matches nothing.** Without that rule, "x" reached four names through initials, among
  them F. X. Mozart and DMX. No musician or genre in this corpus is found by one letter, so the rule
  costs nothing real.
- **No ranking, no autocomplete, no spelling correction.** This is resolution, not search.

## What it did not change, and how that was checked

**A choice rides beside a refusal; it never replaces one.** The answer still refuses, still approves no
claims, and the list arrives as a separate event next to it. That is why the evaluation suite measures
exactly what it measured before: a case that expects a refusal still gets one. It is also checked
against a real model rather than assumed. Across the five live baseline runs on 2026-09-12, **an offer
appeared without a refusal zero times**.

**No name that resolved before resolves differently now.** A test runs every name in the gold set, the
adversarial set, the guided tour, the suggested questions and the README through the resolver and
compares each to a snapshot taken on artifact 0.7.1, before either phase. None moved.

**Offers are tracked, not gated.** They are produced by code, not chosen by the model, so only a code
change could break them, and that is what unit tests are for. If offers ever become something the model
decides, that argument stops holding and they become a gate.

## What it cannot do

**It does not stop a model from typing the wrong name.** The femtanyl case is still the example: asked
about the artist femtanyl, the model looks up fentanyl. That lookup finds nothing and refuses, which is
visible and honest. If the model had typed "Joy Orbison" when asked about Roy, both names resolve, and
nothing in this phase or any metric here would catch it. Offers protect the person typing. They do not
audit the model.

## Where it is

Built and measured on 2026-09-12 and deployed with phase 7.6 on 2026-09-13, then checked by hand on
the public site. The offers, the "also known as" reasons and the re-ask all behaved as described here.
One thing did not: choosing Wolfgang Amadeus Mozart for "Where did mozart come from?" returned real,
cited claims, several about his students rather than his teachers, under a refusal sentence saying none
traced. The choice worked; the answer to the re-asked question did not, and that problem most likely
predates this phase. It is recorded in `docs/KNOWN-GAPS.md` and is the next thing to fix.

## The one-sentence version

When a name is not an exact match, the system still refuses, but now it shows you every name in the
graph you might have meant and why, and lets you pick, because a system that picks for you is the one
that answers confidently about the wrong person.
