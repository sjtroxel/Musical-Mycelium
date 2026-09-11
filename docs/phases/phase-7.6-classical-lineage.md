# Phase 7.6 — Classical Lineage (v0.9)

> **Scope doc.** Written 2026-09-11, at the moment the phase was conceived, which is the rule: *"A phase
> conceived later gets its own scope doc when it is conceived."* Written before anything in it is built and
> before its IMPLEMENTATION doc exists.
>
> **Inserted mid-arc, by his decision on 2026-09-11**, the way Patchwork gained 4.5 and 4.6. Phase 7.5 is
> paused at step 5 (the launch post) and resumes after this phase, so v1.0 ships on the corpus this phase
> produces. Product **v0.9** is the unused slot between phase 7 (v0.8) and the release (v1.0).
>
> **Approved 2026-09-11 by sjtroxel.** Artifact version decided the same day: **v0.10.0** (§4).

## 0. Why this phase exists

**He typed "mozart" into the live site and it refused.** The refusal was correct for the corpus. The corpus
was wrong, and the diagnosis turned up a second, larger problem underneath the first.

**The first problem is a bug.** `ingest/prosecheck.py:fetch_entities` asks Wikidata for English labels
only. Wikidata now lets an item keep its label in `mul`, a default shared across languages, with no
separate `en` label. Mozart (`Q254`) has only `mul`. His label came back empty, and the label-versus-article
check excluded him as `MISLINKED`. The same fault reached 44 entities that have an English article,
including Taylor Swift, B. B. King, Megadeth and Muse. `docs/KNOWN-GAPS.md` carries the measurement.

**The second problem is a gap, and it is the reason this is a phase rather than a patch.** Measured against
Wikidata on 2026-09-11:

| composers born before 1880, with an English article | count |
|---|---|
| total | **9,212** |
| with any `influenced by` (P737) statement | **56** |
| with a `student of` (P1066) statement naming another composer | **1,766** |

This corpus ingests P737 only, so fixing the label bug alone would add very few pre-1900 composers.
**The classical tradition's lineage is recorded in Wikidata as teacher and student, not as influence.**
Beethoven studied with Haydn, Salieri and Albrechtsberger; Schubert and Liszt with Salieri; Liszt with
Czerny, who studied with Beethoven. None of that can reach an answer today, because the relationship is not
in the corpus and the gate admits one predicate.

About 2,880 such composer-to-composer statements exist for students born before 1880, most of them in the
18th and 19th centuries: 26 in the 1400s, 189 in the 1500s, 316 in the 1600s, 636 in the 1700s and 1,715 in
the 1800s. Those are raw counts from one query and will shrink under screening.

**What the corpus holds today, for contrast.** 23 genres are dated before 1900, including Baroque music,
opera, sonata and symphony, but there is no "Classical period" or "Renaissance music" genre. About 72
artists are attached to a classical-type genre by membership, and the list includes Kate Bush and Freddie
Mercury. **Artists carry no dates at all**, so "how many pre-1900 composers does the corpus hold" cannot be
answered from the artifact. That is a coverage-honesty gap in its own right.

## 1. What this phase is for

**To make the pre-1900 lineage of Western art music answerable, with every step sourced**, through the
relationship the sources actually record for it, and without letting that relationship read as influence.

## 2. Delivers

- **The label fix.** Ask for `en` and `mul`, and prefer `en` when both exist. Recovers the entities the
  bug excluded, on both the artist axis and wherever else labels are fetched.
- **A `studied_with` predicate**, from Wikidata P1066, between two artists: "X studied with Y". It is
  artist-to-artist, like artist `influenced_by`, and it is **not** influence. Bounded, screened with the
  existing prose-check machinery, and hand-validated before a single row is ingested.
- **Artist dates.** A birth year on artist nodes, so era is computable for people as it already is for
  genres, and the coverage panel and the report's era slice can say what the corpus holds before 1900.
- **The gate opened to a second predicate, on purpose.** `agent/claims.py:ALLOWED_PREDICATES` admits
  `studied_with`. Claims carry their predicate through to prose, and the answer says "studied with", never
  "influenced by".
- **A disclosure test**, in the shape of `ContestedDisclosure`: no path by which a `studied_with` edge can
  be narrated as influence.
- **Eval cases for the new predicate.** ~~and a live suite re-gated on the new pin, behind an explicit
  spend confirmation.~~ *(Moved to phase 7.7's close, see the amendment below.)*
- **Wikidata aliases stored on every node** (`en` and `mul`), **as data only**. Nothing in 7.6 resolves
  a name by alias; phase 7.7 decides how they are used. Stored here so 7.7 needs no second re-ingest.
- **A new artifact, v0.10.0**, with the README figures and the report regenerated from it. ~~deployed~~
  *(Deployed at phase 7.7's close, see below.)*

> **Amended 2026-09-11, by his decisions the same day, before the IMPLEMENTATION doc was written.**
> 1. **Name resolution is its own phase, 7.7** (`phase-7.7-name-resolution.md`), directly after this one.
>    **Typing "mozart" into the site will still refuse at the end of 7.6**, because the resolver needs
>    an exact full label. That is expected, not a 7.6 defect, and 7.7 fixes it.
> 2. **The live re-baseline runs once, at 7.7's close, covering both phases** (about $3 and 2.5 hours,
>    paid once instead of twice). Until then the live suite is not gated on v0.10.0, and no live number
>    from between the re-pin and the re-baseline may be reported as gated.
> 3. **Deployment happens at 7.7's close too**, so the site, the report and the live gates all describe
>    the same corpus. The public site stays on v0.7.1 until then.

## 3. Explicitly not in this phase

- **Membership narration.** `plays_genre` stays un-narratable. That is phase 8, and nothing here moves it.
- **Changing `influenced_by`.** Its semantics, tiers and sources are untouched. A teacher is not
  retroactively an influence, and a `studied_with` edge never corroborates an `influenced_by` edge.
- **New sources.** Wikidata for the relationship, Wikipedia for the check. No DBpedia teacher edges, no
  MusicBrainz, no hand-entered lineages. Hand-entering what one person knows is a curated set, and a curated
  set inherits one person's blind spots.
- **Works, performances, instruments, recordings.** People and who taught them.
- **A new tour or demo route.** The tour stays where phase 7 put it. If a classical route is obviously better
  for the post, that is a 7.5 decision.
- **Re-running the held-out set.** It stays sealed at pin 0.5.0, run count 1.
- **P279, `checks_disagree`, anything contested-related.** Untouched.

## 4. Key decisions this phase makes

- **The bound.** Who counts as a student, who counts as a teacher, and the date cut. The measurement above
  used occupation *composer* and birth before 1880. The request was composers *and musicians*, and many
  pre-1900 performers (pianists, singers, violinists) have P1066 too. Too wide and the corpus doubles in a
  day; too narrow and a performer lineage like Czerny to Liszt loses its middle.
- **What P1066 actually asserts, measured by hand.** `student of` ranges from years of formal study to a
  handful of lessons to a claim historians dispute. The rule is the P279 rule: **hand-check a sample before
  ingesting.** The P279 check read 47 edges and found zero historical claims, and it changed the design.
  This one might as well.
- **The verification tier.** The existing tiers were defined for influence. `ASSERTS_AUTO` means "passed an
  influence-assertion filter", which is meaningless for teaching. Reusing a tier across predicates is the
  collapse this repo has corrected three times. Whether `studied_with` gets its own tiers, or the tier
  becomes predicate-scoped, is decided with the code open.
- **How prose names the predicate.** `synthesize` takes exactly one claim-bearing parameter, and that stays
  true. The claims inside it now differ in kind, and the sentence must say which. A pure "studied with"
  chain is simple. A mixed route (Czerny studied with Beethoven, Beethoven influenced by Haydn) is where the
  wording goes wrong, and the disclosure test has to cover it.
- ~~**Whether routes may mix predicates at all.** A lineage that alternates teaching and influence may be one
  path with typed hops, or it may be refused. The phase 8 scope doc asks the same question about
  membership, and this phase answers it first.~~ **DECIDED 2026-09-11 by him: yes, one path with typed
  hops.** "Czerny studied with Beethoven, who was influenced by Haydn" is answerable, each hop keeping
  its own verb, and no summary may call the whole chain influence. Both predicates run the same way in
  time, which is why this is safe here and still an open question for membership in phase 8.
- ~~**The artifact version.** v0.7.2 understates a new predicate. v0.8.x and v0.9.x collide with product
  versions that exist, which is the confusion `ROADMAP.md` §2 names. The recommendation is **artifact
  v0.10.0**, awkward but unambiguous. His call.~~ **DECIDED 2026-09-11 by sjtroxel: artifact v0.10.0,**
  for exactly those reasons, recorded in `ROADMAP.md` §2 under the version table so the odd-looking jump
  is never mistaken for a typo. The trap it creates is named there too: as text, `"0.10.0"` sorts before
  `"0.7.1"`, so versions are compared numerically and a test enforces it.
- **What happens to phase 8.** This phase opens `ALLOWED_PREDICATES` first, so phase 8 becomes the second
  opening. Its scope doc gets an amendment saying so, and whatever this phase builds for typed hops is
  what phase 8 inherits rather than designs.

## 5. Definition of done

1. `Wolfgang Amadeus Mozart` is in the corpus, and so is every entity the `mul` bug excluded that passes
   the rest of screening. A test fixes a `mul`-only entity and asserts it gets its label.
2. P1066 was hand-checked on a sample before ingestion, with the findings recorded the way
   `docs/graph-semantics.md` records P279's.
3. "Who did Beethoven study with?" returns a gated, cited answer that says "studied with".
4. A test asserts that no prose path narrates a `studied_with` claim as influence, including on a route that
   mixes predicates, if mixed routes are allowed at all.
5. `verification` and `corroboration` remain two fields, and no tier means two different things.
6. Artist nodes carry a birth year where Wikidata has one, and the coverage panel and the report's era slice
   show what the corpus holds before 1900, with its skew stated.
7. ~~The live suite is re-gated on the new pin over five identical runs, **behind an explicit spend
   confirmation**, and the six gates hold.~~ **Moved to phase 7.7 DoD 5 (2026-09-11).** What remains
   here: the free scripted gates read the same as before the re-pin (4 passed, 0 failed, 2 not
   applicable, of six), and **no live result produced on v0.10.0 before 7.7's re-baseline is reported as
   gated**. If a gate fails, that is a finding, not a reason to loosen it.
8. ~~The new artifact is deployed,~~ The new artifact is **built and deployable** (the Lambda image builds
   and serves it locally; deployment is at 7.7's close), `make check` is green, the asset budget holds,
   and the repo root is inside its cap.
9. `agent/loop.py` is unmodified, or the edit is a finding recorded in bold in the IMPLEMENTATION doc.

## 6. The one-way doors, named up front

**Invariant 3, validated graph semantics.** A new predicate is exactly what that invariant exists for. P1066
is not ingested until its sample is read.

**`ALLOWED_PREDICATES`.** Phase 8's scope doc describes that line as "a second lock on the same door",
there so a non-influence edge cannot reach prose as influence without someone editing it on purpose. **This
phase is someone editing it on purpose.** The property to preserve is unchanged: after this phase there is
still no path by which a non-influence edge reaches prose as an influence claim.

**Invariant 2, provenance on every edge.** Every `studied_with` row carries `source`, `source_id` and
`retrieved_at` from the first row written, the P1066 statement URI as its `source_id`.

## 7. Known risks

- **The failure is invisible and it flatters.** "Beethoven was influenced by Salieri" is a fluent, cited,
  plausible sentence, and false as stated. Every grounding metric this project owns would score it
  perfectly. This is the same shape as the risk phase 8 names.
- **P1066 is uneven.** Famous lineages carry legendary claims (the Mozart and Beethoven meeting is the
  standard example), and obscure ones carry whatever one editor entered. The hand check is where that gets
  measured instead of assumed.
- **The skew moves, and it must be shown moving.** Pre-1900 Western art music is overwhelmingly European.
  This phase makes the corpus older, and it also makes it more Western. The coverage figures must say both.
  Wikidata's P1066 also covers teaching lineages in Hindustani and Carnatic music, where teacher to student
  is the tradition's own central structure; the bound should not exclude them by accident.
- **The graph asset budget.** `graph` sits at about 2.57 MB of a 3.00 MB cap, and this phase could add over
  a thousand nodes. The map may need to load a subset, or the cap moves with its reasoning updated. Measured
  in the build, not guessed here.
- **Everything downstream moves.** A new pin invalidates the live baseline ($2.61 and about 2.4 hours to
  re-measure), regenerates README and report figures, and can shift chips, gold cases and the tour. Each is
  a check that already exists, which is what makes the move safe rather than cheap.
- **It is not a one-day phase.** Today can carry the plan, the label fix, the hand check and likely the
  ingest. Opening the gate, the eval cases and the re-baseline are more than that. Stopping between steps
  is fine; stopping in the middle of one is not.

## 8. Left for the IMPLEMENTATION doc

The bound, from measurements. The hand-check sample size and who reads it. The verification tier shape. The
prose wording and whether mixed routes are allowed. Whether a new tool is needed for "who studied with X",
noting that a new tool behind the registry is the answer the seam was built for, and that editing the loop
is not. The graph-budget response. The eval cases and where they live. The artifact version.
