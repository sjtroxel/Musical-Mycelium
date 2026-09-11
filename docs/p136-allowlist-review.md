# P136 repertoire allowlist — review sheet, 2026-09-11

Phase 7.6 step 3. **His decision, 2026-09-11:** new composers get their genre-membership (P136) edges,
and "each composer's full repertoire is adequately included". The membership layer
(`ingest/membership.py`) already takes an artist's **whole** P136 list, every non-deprecated statement,
unfiltered by the corpus, the phase 6 decision after a filtered version reduced Red Hot Chili Peppers
to "heavy metal". **One filter remains:** the object must be a music genre by Wikidata's own typing
(`P31/P279*` of `Q188451`). That filter drops real repertoire, so a **reviewed allowlist** of object
QIDs is admitted past it, applied to **every** artist, old and new (also his decision).

## What was measured

Over all 4,838 P136 statements of the 804 artists in v0.7.1 plus the 2,584 people in the P1066 bound
(non-deprecated, pulled live, parsed by the membership layer's own `parse`): **132 statements dropped by
the type filter, across 90 distinct values.** The famous cases:

| composer | Wikidata P136, as it stands | after this review |
|---|---|---|
| Mozart | opera, Classical period, chamber music, symphony | unchanged (all four already pass) |
| Beethoven | sonata, opera, art music, classical music, symphony | unchanged |
| Tchaikovsky | classical music, opera, symphony, Romantic music, **ballet (the dance item)** | ballet cannot be admitted: see the collision rule |
| Liszt | classical music, symphony, Hungarian folk music, symphonic poem | unchanged |
| Chopin, Brahms, Schumann | **nothing at all** | nothing; shown as a gap, never inferred (his decision) |

## The rules the verdicts follow

1. **Keep** a value Wikidata itself classifies as musical: a type of musical work or composition, a
   musical form, a musical repertoire, a music-specific movement, or a music scene. The statement is
   Wikidata's; the allowlist only admits its object past a type test that was too narrow.
2. **Drop** a value that is not music: a general art or cultural movement (the music is already covered
   by genres such as "Baroque music" and "Romantic music"), an ensemble, an instrument, a technique or
   activity, a tempo, a single composition, a disambiguation page, or a non-music genre (comedy,
   fiction, painting, poetry).
3. **The collision rule, found by measurement:** a value whose label folds to an **existing** node's
   label is dropped, however musical, because two nodes with one label make that name ambiguous and
   break its resolution. Its objects are never re-pointed at the existing node: that would make the
   corpus state something the Wikidata statement does not.

## Proposed KEEP — 20 values, 32 statements

| value | QID | statements | Wikidata says it is |
|---|---|---|---|
| Atlanta hip-hop | Q4816198 | 6 | a music genre or scene |
| song | Q7366 | 4 | a type of musical work |
| impressionism in music | Q837182 | 3 | a musical movement |
| piano sonata | Q1546995 | 2 | a type of musical work |
| organ repertoire | Q2003283 | 2 | a musical repertoire |
| concertino | Q779024 | 1 | a musical form |
| viola sonata | Q715028 | 1 | a type of musical work |
| sinfonia | Q377141 | 1 | a musical form |
| suite | Q203005 | 1 | a musical form |
| piano piece | Q1746015 | 1 | a type of musical work |
| piano concerto | Q1746028 | 1 | a type of musical work |
| patriotic song | Q7148059 | 1 | a song type |
| canon | Q53831 | 1 | a musical form |
| chaconne | Q841238 | 1 | a musical form |
| rhapsody | Q464769 | 1 | a musical form |
| canzone | Q873000 | 1 | a song form |
| song form | Q1824109 | 1 | a musical form |
| neoclassicism (music) | Q535611 | 1 | a musical movement (distinct from general Neoclassicism) |
| Roman School | Q1294582 | 1 | a composition school / musical movement |
| polka | Q153071 | 1 | **already a genre node in v0.7.1**; today's Wikidata no longer types it as one. Keeping it restores an existing artist's edge; no new node, no collision |

## BORDERLINE — his call, one line each

| value | QID | statements | the case for | the case against | proposed |
|---|---|---|---|---|---|
| **ballet** | Q41425 | 17 (16 new) | a central repertoire category; Tchaikovsky | the item is the **dance**, and "ballet" is already a corpus genre (Q4851628, the music) — **collision** | **drop**; the fix is upstream, pointing these statements at Q4851628 on Wikidata |
| spoken word | Q1428637 | 3 | a recognized recording genre | Wikidata types it as poetry / performing arts, not music | drop |
| ode | Q178985 | 2 | a choral genre for composers (Purcell's odes) | the item is a poetic form | drop |
| ballad | Q182659 | 2 | a song form in music | the item is the literary ballad | drop |
| string quartet | Q207338 | 1 | central chamber repertoire (Haydn) | the item is the **ensemble**, not the composition | drop |
| Catholic Mass | Q132612 | 1 | composers write Masses | the item is the **rite**, not the musical setting | drop |

## Proposed DROP — 64 values (74 statements), clearly not music or colliding

13 + 9 + 5 + 3 + 34 = 64.

- **General art and cultural movements (13):** Romanticism, Baroque, Impressionism, Renaissance,
  Expressionism, Neoclassicism, modernism, romantic nationalism, avant-garde, Fluxus, conceptual art,
  hip hop culture, underground culture.
- **Ensembles, instruments, techniques, tempos, activities (9):** orchestra, wind orchestra, girl group,
  piano, lyric singing, solo singing, choir singing (Q113360774, no label), cantus firmus, slow.
- **Collides with an existing corpus genre (5):** soundtrack, mambo, cha-cha-cha, Lo-fi, vocal. (Ballet
  collides too; it is in the borderline table because it is real repertoire.)
- **Not a genre at all (3):** "Choral" (a single 1950 Stockhausen composition), "Concert music" (a
  disambiguation page), Q139971303 (no label).
- **Non-music genres (34):** comedy and its kinds (ribaldry, observational, sketch, surreal, deadpan,
  black, clean, anti-humor, parody, satire), fiction and its kinds (historical, dystopian, feminist
  science fiction, science fiction, utopian and dystopian, speculative), tragedy, theatre, happening,
  performance art, estrada, art, religious art, history painting, portrait, portrait painting, still
  life, roman à clef, confessional poetry, essay, poetry, fable, vanguard (a military unit).

## After review

The kept QIDs become a constant in `ingest/membership.py` (an allowlist, each with this sheet as its
record), tested so that a kept value is admitted, a dropped one is not, and a colliding one can never be
admitted. Artists with no P136 are counted and shown, never filled.

**Reviewed by sjtroxel, 2026-09-11: approved as proposed** — 20 keep, all 6 borderline values dropped
(ballet, spoken word, ode, ballad, string quartet, Catholic Mass), 64 drop. No verdict changed.
