# P1066 `student of` — the hand check, 2026-09-11

Phase 7.6 step 2. `.claude/rules/graph-semantics.md` requires a property to be hand-checked **before** a
single row is ingested. P279 was read at 47 edges and changed the design (zero carried a historical
claim); P136 at 30. This is P1066's. Summary and verdict: `docs/graph-semantics.md` §8.

## Method, fixed before reading

- **Population (bound A):** composer students (P106 `Q36834`) born before 1900, with a P1066 naming a
  composer teacher, both with an English Wikipedia article, deprecated statements excluded. Pulled
  2026-09-11: 3,606 rows, **3,449 distinct statements** (duplicates were people with several recorded
  birth dates; the earliest was kept).
- **Sample:** 40, seed `p1066-handcheck-2026-09-11`, stratified by the student's birth century and by
  whether the statement carries a Wikidata reference: before 1700, 7 referenced + 6 not; 1700s, 7 + 6;
  1800s, 7 + 7. Scripts: `scripts/handcheck/`.
- **The project's own prose check** was run on every row through the real code path
  (`prosecheck.fetch_entities`, with the step 1 `mul` fix, then `resolve_article` and `check_edge`), so
  the "check" column is what the ingest would compute.
- **Each row read** against the student's article and, where that was silent, the teacher's (full plain
  text, searched for the other's surname), and put in one category: *formal study*, *lessons* (real but
  brief), *disputed* (the source itself hedges), *wrong relation*, *inverted*, or *unverifiable* from
  the two articles.
- **Stop rule, written before reading:** *wrong relation* + *inverted* at 3 or fewer of 40 proceeds; 4 to
  8 proceeds only with a tier split or exclusion; more than 8 stops the phase.
- **Reader:** Claude (Opus 5), recording the sentence each verdict rests on. **sjtroxel reviews every row
  not judged *formal study*.** n=40 is a direction, not a rate.

## The 40

| # | stratum | student (born) ← teacher (born) | check | verdict | the evidence |
|---|---|---|---|---|---|
| 1 | 1700s / unref | Antoine Romagnesi (1781) ← Luigi Cherubini (1760) | ORPHAN | **unverifiable** | neither article names the other |
| 2 | 1700s / unref | James Nares (1715) ← Bernard Gates (1686) | PROSE | formal study | "Nares was a pupil of Bernard Gates" |
| 3 | 1700s / unref | Cipriani Potter (1792) ← William Crotch (1775) | PROSE | formal study | "his musical instruction began … with … William Crotch" |
| 4 | 1700s / unref | Carlo Antonio Campioni (1720) ← Giuseppe Tartini (1692) | PROSE | **disputed** | "he *presumably* came into contact with Giuseppe Tartini, who was Campion's teacher" |
| 5 | 1700s / unref | Sigismund von Neukomm (1778) ← Michael Haydn (1737) | PROSE | formal study | "studied theory under Michael Haydn" |
| 6 | 1700s / unref | Jean-Baptiste Bréval (1753) ← François Cupis (1732) | PROSE | formal study | "went on to study with François Cupis" |
| 7 | 1700s / ref | Wolfgang Amadeus Mozart (1756) ← Giovanni Battista Martini (1706) | PROSE | **lessons** | Martini's article: "a mentor to Mozart"; "Among Martini's pupils … the young Wolfgang Amadeus Mozart". **The check passed on a different sentence**: Mozart's article only says he "met" Martini |
| 8 | 1700s / ref | Johann Gottlieb Naumann (1741) ← Giuseppe Tartini (1692) | PROSE | **unverifiable** | only "Tartini encountered Naumann in 1762 and took an interest in his work". **Check passed on contact, not study** |
| 9 | 1700s / ref | Carl Czerny (1791) ← Ludwig van Beethoven (1770) | PROSE | formal study | "one of Ludwig van Beethoven's best-known pupils" |
| 10 | 1700s / ref | August Wilhelm Bach (1796) ← Carl Friedrich Zelter (1758) | PROSE | formal study | "studied with … Carl Friedrich Zelter" |
| 11 | 1700s / ref | Stanislao Mattei (1750) ← Giovanni Battista Martini (1706) | PROSE | formal study | "he became a pupil of the famed musician, Friar Giovanni Battista Martini" |
| 12 | 1700s / ref | Ignazio Fiorillo (1715) ← Leonardo Leo (1694) | PROSE | formal study | "at the Naples Conservatory, as a pupil of Leonardo Leo" |
| 13 | 1700s / ref | Chevalier de Saint-Georges (1745) ← Antonio Lolli (1725) | PROSE | **disputed** | "Lolli *may have* worked with Bologne on his violin technique" |
| 14 | 1800s / unref | Antoine-François Marmontel (1816) ← Victor Dourlen (1780) | PROSE | formal study | "His teachers were … Victor Dourlen in harmony" |
| 15 | 1800s / unref | Herman Bemberg (1859) ← César Franck (1822) | ORPHAN | **unverifiable** | neither article names the other |
| 16 | 1800s / unref | Fredrik Pacius (1809) ← Moritz Hauptmann (1792) | PROSE | formal study | "studied … counterpoint and composition under Moritz Hauptmann" |
| 17 | 1800s / unref | Francisco Tárrega (1852) ← Julián Arcas (1832) | PROSE | formal study | Arcas "advised Tárrega's father to allow Francisco to come to Barcelona to study with him" |
| 18 | 1800s / unref | Joseph-Arthur Bernier (1877) ← Gustave Gagnon (1842) | PROSE | formal study | "Bernier was a pupil of Gustave Gagnon" |
| 19 | 1800s / unref | Felix Otto Dessoff (1835) ← Julius Rietz (1812) | PROSE | formal study | at the Leipzig Conservatory, "Julius Rietz for composition" |
| 20 | 1800s / unref | José Sevenants (1868) ← Joseph Jongen (**1873**) | PROSE | formal study, **flagged** | "harmony with Joseph Jongen". **The teacher is five years younger** — the trap 16 case, not inverted by the article, and worth a reviewer's eye |
| 21 | 1800s / ref | Johannes Haarklou (1847) ← Carl Reinecke (1824) | PROSE | formal study | "he studied with Carl Reinecke at the Leipzig Conservatory" |
| 22 | 1800s / ref | Johanna Senfter (1879) ← Carl Friedberg (1872) | ORPHAN | formal study | "piano under *Karl* Friedberg". **Check missed it: Carl/Karl spelling** |
| 23 | 1800s / ref | Yves Nat (1890) ← Paul Rougnon (1846) | ORPHAN | formal study | Rougnon's article: "His students include … Yves Nat". **Check missed it: only the teacher's article says so** |
| 24 | 1800s / ref | Julius Weismann (1879) ← Josef Rheinberger (1839) | PROSE | formal study | "He studied with Josef Rheinberger" |
| 25 | 1800s / ref | Viking Dahl (1895) ← Andreas Hallén (1846) | ORPHAN | **unverifiable** | neither article names the other |
| 26 | 1800s / ref | Louise Bertin (1805) ← François-Joseph Fétis (1784) | PROSE | **lessons** | "She received lessons from François-Joseph Fétis" |
| 27 | 1800s / ref | Laurent Menager (1835) ← Ferdinand Hiller (1811) | ORPHAN | formal study | "continuing his studies with *Professor Hiller* at the Academy of Music in Cologne". **Check missed it: surname only** |
| 28 | before 1700 / unref | Jacques Hardel (1643) ← Jacques Champion de Chambonnières (1602) | PROSE | formal study | "He was a pupil of Jacques Champion de Chambonnières" |
| 29 | before 1700 / unref | Jerónimo de Carrión (1666) ← Miguel de Irízar (1635) | PROSE | **unverifiable** | only "taking up the position formerly filled by Miguel de Irízar who had died in 1684". **Check passed on succession, not study** |
| 30 | before 1700 / unref | José de Torres (1670) ← Cristóbal Galán (1625) | ORPHAN | **unverifiable** | neither article names the other |
| 31 | before 1700 / unref | Pablo Nassarre (1650) ← Pablo Bruna (1611) | PROSE | formal study | "He moved to Daroca to be taught by Pablo Bruna" |
| 32 | before 1700 / unref | Tommaso Bernardo Gaffi (1667) ← Bernardo Pasquini (1637) | MISLINKED | formal study | "He was a pupil of Bernardo Pasquini". **Excluded by the mislink guard over a missing middle name**: label "Tommaso Bernardo Gaffi", article "Tommaso Gaffi" |
| 33 | before 1700 / unref | Gregorio Allegri (1582) ← Giovanni Bernardino Nanino (1560) | PROSE | formal study | "studied music as a puer … under the maestro di cappella Giovanni Bernardino Nanino" |
| 34 | before 1700 / ref | Francesco Foggia (1604) ← Antonio Cifra (1584) | PROSE | formal study | "was a student of Antonio Cifra" |
| 35 | before 1700 / ref | Nicolas Payen (1512) ← Nicolas Gombert (1495) | ORPHAN | **unverifiable** | neither article names the other |
| 36 | before 1700 / ref | Cornelius Canis (1506) ← Nicolas Gombert (1495) | PROSE | **unverifiable** | only "master of the choirboys of the chapel, succeeding Nicolas Gombert". **Check passed on succession, not study** |
| 37 | before 1700 / ref | Vincenzo Ruffo (1510) ← Jacquet of Mantua (1483) | ORPHAN | **unverifiable** | neither article names the other |
| 38 | before 1700 / ref | Vincenzo Ugolini (1578) ← Giovanni Bernardino Nanino (1560) | PROSE | formal study | "a puer chori … under Giovanni Bernardino Nanino" |
| 39 | before 1700 / ref | Diego Xaraba (1652) ← Pablo Bruna (1611) | PROSE | formal study | "Xaraba studied with him at Daroca" |
| 40 | before 1700 / ref | Pietro Locatelli (1695) ← Arcangelo Corelli (1653) | PROSE | **disputed** | "*perhaps* for a short time under Arcangelo Corelli"; Corelli's article lists him among his pupils |

## Tally

| verdict | count |
|---|---|
| formal study | 26 |
| lessons | 2 |
| disputed | 3 |
| **wrong relation** | **0** |
| **inverted** | **0** |
| unverifiable from the two articles | 9 |

**Stop rule: 0 of 40 wrong or inverted. Proceed.**

**Reviewed by sjtroxel, 2026-09-11:** all fifteen rows not judged formal study (including the flagged
younger-teacher row, #20), read against the evidence column. He agreed with every verdict and changed none.
