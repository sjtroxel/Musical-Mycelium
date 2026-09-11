# P1066 build review — younger teachers and succession sentences, 2026-09-11

Phase 7.6 step 5. The first real build of v0.10.0 flagged two kinds of teaching edge for a person to
read before the artifact is final (trap 16 of the IMPLEMENTATION doc, and the step 2 succession shape).
Every row below passed the prose check: the student's English Wikipedia article names the teacher. The
question here is whether the sentence that names them states **study**.

**Proposed rules, for his review:**

1. **A teacher recorded as younger than the student shifts the burden.** Such an edge is kept only when
   an article sentence states the study. A younger teacher is not disqualifying on its own: Bruckner
   studied with Otto Kitzler, "nine years younger than he", and his article says so. But when the only
   sentence describes something else, the age gap is the second piece of evidence that the statement
   is wrong, reversed, or a different relation.
2. **An edge whose only supporting sentences describe succeeding someone in a post is excluded.** The
   step 2 hand check saw this shape twice in 40; the full build finds 9 in 2,487 (0.4%). Succeeding a
   choirmaster is a different relation from studying with him, even where the two often went together.
   Missing an edge never narrates a false one.

Excluded edges go into `ingest/lineage.py:TEACHING_REJECTED` with the reason, the
`wikidata.REJECTED_EDGES` pattern, and are reported as `HAND_REJECTED` by the build.

## Younger teachers — 53 edges; proposed: keep 43, exclude 10

Ordered by the size of the age gap. Birth years are Wikidata's; some are plainly wrong (a 1501 birth
for a musician who worked in the 1590s), which is noted where the sentence shows it.

| # | student (born) ← teacher (born) | gap | proposed | the sentence |
|---|---|---|---|---|
| 1 | Francesco Rognoni Taeggio (1501) ← Riccardo Rognoni (1550) | 49 | **exclude** | only "He was the son of Riccardo Rognoni"; family, not study. The 1501 birth is wrong too |
| 2 | Ercole Pasquini (1501) ← Luzzasco Luzzaschi (1545) | 44 | **exclude** | only "he succeeded Luzzasco Luzzaschi as organist"; succession. The 1501 birth is wrong too |
| 3 | Walther von der Vogelweide (1170) ← Reinmar of Hagenau (1200) | 30 | keep | "learned his craft under the renowned master Reinmar von Hagenau" |
| 4 | Reine Colaço Osorio-Swaab (1881) ← Henk Badings (1907) | 26 | keep | "studied with … Henk Badings for melody", after her children were grown |
| 5 | Ruth Almén (1870) ← Knud Jeppesen (1892) | 22 | keep | "composition with Franz Neruda and Knud Jeppesen in Copenhagen" |
| 6 | Karel Ondříček (1863) ← Jan Kubelík (1880) | 17 | **exclude: inverted** | "Among his pupils was Jan Kubelík." Kubelík was the pupil |
| 7 | Florence Maude Ewart (1864) ← Ottorino Respighi (1879) | 15 | keep | "studied composition intensively … with composer Ottorino Respighi" |
| 8 | Francisco Leontaritis (1518) ← Orlande de Lassus (1532) | 14 | keep | "a student of … Orlande de Lassus and Giovanni Pierluigi da Palestrina" |
| 9 | Kateřina Emingerová (1856) ← Vítězslav Novák (1870) | 14 | keep | "studied composition privately with Zdeněk Fibich and Vítězslav Novák" |
| 10 | Giovanni Pierluigi da Palestrina (1525) ← Robin Mallapert (1538) | 13 | keep | "He also studied with Robin Mallapert and Firmin Lebel" |
| 11 | Roberta Geddes-Harvey (1849) ← Humfrey Anger (1862) | 13 | keep | "studied music with … Humfrey Anger" |
| 12 | Vasily Pashkevich (1742) ← Vicente Martín y Soler (1754) | 12 | **exclude** | only a work written "together with Vicente Martín y Soler"; collaborators |
| 13 | Eda Rapoport (1890) ← Aaron Copland (1900) | 10 | keep | "studied composition with Walter Piston, Aaron Copland and Arnold Schoenberg" |
| 14 | Mary Lucas (1882) ← Herbert Howells (1892) | 10 | keep | returned in the 1920s to study composition at the Royal College |
| 15 | Anton Bruckner (1824) ← Otto Kitzler (1834) | 10 | keep | "studied further with Otto Kitzler, who was nine years younger than he" |
| 16 | François Benoist (1794) ← Adolphe Adam (1803) | 9 | **exclude: inverted** | "His students included … Adolphe Adam." Adam was the pupil |
| 17 | Pierre-Louis Hus-Desforges (1773) ← Benoît Tranquille Berbiguier (1782) | 9 | keep | "his studies at the Conservatoire de Paris with Benoit Tranquille Berbiguier" |
| 18 | Ika Peyron (1845) ← Emil Sjögren (1853) | 8 | keep | "a student of … Emil Sjögren" |
| 19 | Jerónimo Giménez (1854) ← Salvador Viniegra (1862) | 8 | keep | "continued his education with Salvador Viniegra" |
| 20 | Guy d'Hardelot (1858) ← Clarence Lucas (1866) | 8 | keep | "she became a pupil of Clarence Lucas" |
| 21 | Clémence de Grandval (1828) ← Camille Saint-Saëns (1835) | 7 | keep | "studied for two years with Camille Saint-Saëns" |
| 22 | Francisco Leontaritis (1518) ← Palestrina (1525) | 7 | keep | same sentence as #8 |
| 23 | Florence Price (1887) ← Wesley LaViolette (1894) | 7 | keep | "studied composition, orchestration, and organ with … Wesley La Violette" |
| 24 | Signe Lund (1868) ← Henrik Lund (1875) | 7 | **exclude** | only "the sister of the artist Henrik Lund"; a sibling, and a painter |
| 25 | Harry T. Burleigh (1866) ← Rubin Goldmark (1872) | 6 | keep | "studied composition with … Rubin Goldmark" |
| 26 | Pere-Enric de Ferran (1865) ← Mathieu Crickboom (1871) | 6 | **exclude** | only a premiere by an orchestra Crickboom directed; a performer, not a teacher |
| 27 | Liza Lehmann (1862) ← Hamish MacCunn (1868) | 6 | keep | "composition studies with teachers including Hamish MacCunn" |
| 28 | Johanna Müller-Hermann (1868) ← Franz Schmidt (1874) | 6 | keep | "She studied under … Franz Schmidt" |
| 29 | Ida Moberg (1859) ← Émile Jaques-Dalcroze (1865) | 6 | keep | finished her education "at the Dalcroze Institute" |
| 30 | José Sevenants (1868) ← Joseph Jongen (1873) | 5 | keep | "harmony with Joseph Jongen"; reviewed at step 2 |
| 31 | Robert Nathaniel Dett (1882) ← Nadia Boulanger (1887) | 5 | keep | "to study … with composer Nadia Boulanger" |
| 32 | Marion Bauer (1882) ← Nadia Boulanger (1887) | 5 | keep | "the first American to study with Nadia Boulanger" |
| 33 | Mary Howe (1882) ← Nadia Boulanger (1887) | 5 | keep | "traveled to Paris to study with Nadia Boulanger" |
| 34 | Mary Knight Wood (1857) ← Henry Holden Huss (1862) | 5 | keep | "further studies in New York under … Henry Holden Huss" |
| 35 | Johanna Bordewijk-Roepman (1892) ← Eduard Flipse (1896) | 4 | keep | "studied orchestration with Eduard Flipse" |
| 36 | José Rolón (1883) ← Nadia Boulanger (1887) | 4 | keep | "a student of Nadia Boulanger" (his article gives 1876 for his birth) |
| 37 | Giovanni Legrenzi (1626) ← Carlo Pallavicino (1630) | 4 | **exclude** | only "along with Carlo Pallavicino, the leading opera composer of his day"; peers |
| 38 | Luigi de Baillou (1736) ← Nicolas Capron (1740) | 4 | keep | "probably studied violin under the guidance of Nicolas Capron"; hedged, as step 2 kept |
| 39 | Eda Rapoport (1890) ← Walter Piston (1894) | 4 | keep | same sentence as #13 |
| 40 | Johan Wikmanson (1753) ← Joseph Martin Kraus (1756) | 3 | keep | "His teachers included … Joseph Martin Kraus" |
| 41 | Giuseppe Torelli (1658) ← Giacomo Antonio Perti (1661) | 3 | keep | "it is certain that he studied composition with Giacomo Antonio Perti" |
| 42 | Johanna Müller-Hermann (1868) ← Alexander von Zemlinsky (1871) | 3 | keep | same sentence as #28 |
| 43 | Aladar Rado (1882) ← Leó Weiner (1885) | 3 | keep | "continued his compositional studies under Leo Weiner" |
| 44 | Sláva Vorlová (1894) ← Jaroslav Řídký (1897) | 3 | keep | "continued her composition studies … with Jaroslav Řídký" |
| 45 | Mykola Lysenko (1842) ← Nikolai Rimsky-Korsakov (1844) | 2 | keep | "to study orchestration with Nikolai Rimsky-Korsakov" |
| 46 | William Arms Fisher (1861) ← Horatio Parker (1863) | 2 | keep | "studied under Antonín Dvořák and Horatio Parker" |
| 47 | Giulia Recli (1890) ← Victor de Sabata (1892) | 2 | keep | "a student under Ildebrando Pizzetti and Victor de Sabata" |
| 48 | Julius Bittner (1874) ← Bruno Walter (1876) | 2 | **exclude** | only "helped and promoted by Mahler and Bruno Walter"; a patron, not a teacher |
| 49 | Gaston Carraud (1864) ← Albéric Magnard (1865) | 1 | keep | "receiving instruction from Albéric Magnard" |
| 50 | Whitney Eugene Thayer (1838) ← John Knowles Paine (1839) | 1 | keep | "An early student of John Knowles Paine" |
| 51 | Paul Lacombe (1837) ← Georges Bizet (1838) | 1 | **exclude** | only "an admirer of the music of Georges Bizet". The rule excludes it; if you know of real lessons, it can be kept |
| 52 | William Hayman Cummings (1831) ← Alberto Randegger (1832) | 1 | keep | "becoming a pupil of … Alberto Randegger" |
| 53 | Ruth Almén (1870) ← Wilhelm Stenhammar (1871) | 1 | keep | "She studied counterpoint with Wilhelm Stenhammar" |

**Two of the ten are reversed outright** (#6, #16): the student's own article names the "teacher" as
*his* pupil. That is exactly the error trap 16 was written to catch. The other eight rest on a sentence
describing family, succession, collaboration, performance, patronage or admiration.

## Succession sentences — 9 edges; proposed: exclude all 9

After the detector fix (it had missed "professor", "his master" and "learn", and so miscalled Vaughan
Williams, Leoni and Fauré), 9 edges rest only on succeeding someone. **Six are before 1700**, as the
step 2 sample predicted.

| student ← teacher | the sentence |
|---|---|
| José Ximénez ← Sebastian Aguilera de Heredia | became his assistant in 1620 and succeeded him as principal organist |
| François d'Agincourt ← Jacques Boyvin | became organist of Rouen Cathedral, succeeding Jacques Boyvin |
| Robert Cooke ← Benjamin Cooke | son of Benjamin Cooke; succeeded his father as organist |
| Carolus Luython ← Philippe de Monte | court organist and court composer, in de Monte's line |
| Guillaume Minoret ← Étienne Moulinié | maître de chapelle at Toulouse, succeeding Moulinié |
| Cornelius Canis ← Nicolas Gombert | master of the choirboys, succeeding Gombert (also step 2 row #36) |
| Ercole Pasquini ← Luzzasco Luzzaschi | succeeded Luzzaschi as organist (also younger-teacher #2) |
| Antonio Scandello ← Mattheus Le Maistre | Kapellmeister, succeeding Le Maistre |
| Jean Gilles ← André Campra | music master at Toulouse, as the successor of Campra |

Some of these may well be true teaching lines (an assistant, a son), and excluding them costs real
edges. The rule excludes them because none of the sentences states study.

**Pasquini is in both lists**, so the two rules exclude **18 distinct edges** in total, not 19.

**Reviewed by sjtroxel, 2026-09-11: approved as proposed**, both rules and all 18 exclusions. They are
`ingest/lineage.py:TEACHING_REJECTED`, and v0.10.0 was rebuilt with them the same afternoon: 2,469
teaching edges (2,487 less the 18), and none of the 18 present in the artifact, checked by loading it.
