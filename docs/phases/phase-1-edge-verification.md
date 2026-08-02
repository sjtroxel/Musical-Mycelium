# Phase 1, step 2 — edge hand-verification record

> The record of the hand-verification pass required by `phase-1-walking-skeleton-IMPLEMENTATION.md` §12
> step 2. It exists so the v0.1 artifact is reproducible and so the rejections are inspectable: an edge
> that was thrown out is more informative than one that was kept.
>
> Performed 2026-08-02. All Wikidata figures confirmed live that day; Wikipedia prose read from the
> then-current revisions.

## 1. Method

Candidates were drawn only from the **158 PROSE-tier edges** of the 2026-07-31 validation
(`docs/graph-semantics.md` §4). Each candidate then had to clear four gates, in order:

| Gate | Test | Why |
|---|---|---|
| 1. Existence | The P737 statement still exists in Wikidata today | The 7/31 pull is a month-old snapshot; edges get deleted |
| 2. Type | Both ends resolve as a music genre via `P31/P279* Q188451` | `graph-semantics.md` §3.1 — ~6% of P737 objects are bands, techniques, instruments |
| 3. Prose | The subject's English Wikipedia article contains a genuine body sentence naming the object | The PROSE tier, recomputed with the defects in §3 corrected |
| 4. **Assertion** | That sentence asserts **influence or derivation** — not co-occurrence, not synonymy, and not taxonomy | This is the gate the automated tier cannot apply, and it is the one that rejected the most |

Gate 4 is the whole point of doing this by hand. Gate 3 asks whether the label is present; gate 4 asks
whether the article says what the edge claims.

## 2. Result

**21 of 26 candidates accepted. 5 rejected.** Two batches were run because the first lost 5 of 16 and the
plan calls for ~15 edges.

The survival rate matters beyond this phase: these candidates had **already passed** the automated PROSE
tier. Roughly **one in five surviving edges does not withstand hand-reading**, which means the usable
corpus is smaller than the 158 that `graph-semantics.md` §4.4 records. See §4.

## 3. Three defects in the automated prose check

`graph-semantics.md` §4.5 records one known defect. This pass found two more. All three inflate the PROSE
tier, none deflate it, so **the 158 figure is an upper bound.**

### 3.1 Markup counted as prose (already known, §4.5)

`[[Category:...]]` tags, navboxes, and reference blocks are counted as body text. Confirmed live: both
`groove metal` edges reported a PROSE tier with **zero** genuine prose sentences once markup was stripped.

### 3.2 Self-match when the object label is a substring of the subject label (new)

`Western swing <- swing` reported 28 prose sentences. The pattern `\bswing\b` matches the "swing" inside
"Western swing", so the article was matching against its own title. After masking the subject's name, 8
sentences survived and only 1 actually supports the edge. **Fix: mask the subject label before searching
for the object.**

### 3.3 Redirect collapse — the check can verify against the wrong article (new, and the worst of the three)

`disco house <- disco` appeared well-supported. It is not. The Wikidata item for `disco house` (Q360596)
sitelinks to an English Wikipedia title that **redirects to `French house`**:

```
Disco house -> French house#Terms, origins and variations
```

The checker fetched the French house article, found "disco" discussed at length, and scored the edge as
PROSE. The evidence was real; it was evidence about a different genre.

This is the most dangerous of the three because it produces **confident false support** rather than a
missing signal. **Fix: resolve the redirect and reject or flag any edge whose subject article resolves to
a different title than the subject's own label.**

### 3.4 A counter-defect: exact-label matching under-accepts

Working the other way, matching on the full Wikidata label misses articles that use the short form.
`country rock <- country music` scored no supporting sentence because the article's lead says *"fuses rock
and country"*, and `dubstep <- dub music` scored zero because the article says *"sparse dub production"*.
Both edges are genuinely supported and were accepted on hand-reading.

**Consequence for phase 2:** the pipeline check must try label variants, and it will still be wrong in both
directions. That is an argument for reporting the exclusion rate as a **measured, displayed** number with a
known error bar, not for pretending the check is exact.

## 4. The accepted set — 21 edges, 28 nodes

All `influenced_by`, all genre-to-genre, all with a quoted supporting sentence recorded during the pass.

| Subject | Influenced by | Supporting prose (abbreviated) |
|---|---|---|
| acid jazz | jazz | "has its origins in the 1950s, 1960s, when psychedelic styles were being incorporated into other musical genres, jazz being one of these" |
| acid jazz | funk | "combines elements of funk, soul, and hip hop" |
| acid jazz | soul | "combines elements of funk, soul, and hip hop" |
| acid jazz | hip-hop | "combines elements of funk, soul, and hip hop" |
| blues rock | blues | "a fusion genre and form of rock and blues music that relies on the chords/scales and instrumental improvisation of blues" |
| heavy metal music | blues rock | "With roots in blues rock, psychedelic rock and acid rock, heavy metal bands developed a thick, monumental sound" |
| thrash metal | punk rock | "The thrash metal genre is also strongly influenced by punk rock" |
| folk punk | punk rock | "a fusion of folk music and punk rock" |
| folk rock | folk music | "a fusion genre of rock music with heavy influences from English and American folk music" |
| trip hop | hip-hop | "a psychedelic fusion of hip-hop and electronica" |
| trip hop | electronica | "a psychedelic fusion of hip-hop and electronica" |
| Western swing | swing | "an amalgamation of rural, cowboy, polka, early Honky Tonk, old-time, Dixieland jazz, and blues blended with swing" |
| Western swing | country music | "The movement was an outgrowth of country music and jazz" |
| country rock | country music | "Country rock is a music genre that fuses rock and country" |
| country rap | country music | "a fusion genre that mixes country music elements with hip-hop beats and rapping" |
| bossa nova | jazz | "bossa nova was influenced by jazz, both in the harmonies used and also by the instrumentation of songs" |
| jazz rap | jazz | "a fusion of jazz and hip hop music" |
| soul blues | soul | "combines elements of soul music and urban contemporary music" |
| grime | UK garage | "It developed out of the earlier UK dance style UK garage" |
| dubstep | 2-step garage | "emerged as a UK garage offshoot that blended 2-step rhythms"; "musical precursors such as 2-step garage" |
| dubstep | dub music | "emerged as a UK garage offshoot that blended 2-step rhythms and sparse dub production" |

### 4.1 Structure

7 connected components across 28 nodes:

| size | component |
|---|---|
| 10 | acid jazz, bossa nova, electronica, funk, hip-hop, jazz, jazz rap, soul, soul blues, trip hop |
| 5 | Western swing, country music, country rap, country rock, swing |
| 3 | blues, blues rock, heavy metal music |
| 3 | folk punk, punk rock, thrash metal |
| 3 | 2-step garage, dub music, dubstep |
| 2 | folk music, folk rock |
| 2 | UK garage, grime |

This fragmentation is **not** an artifact of hand-picking. It is the same shape as the full corpus, which
`graph-semantics.md` §5 measures at 46 components over 198 nodes. A v0.1 artifact that was a single
connected blob would have misrepresented the data the product actually has.

**13 nodes have zero parent edges** — blues, jazz, funk, soul, hip-hop, punk rock, country music, swing,
electronica, folk music, dub music, 2-step garage, UK garage. These are not gaps in the verification; they
are the corpus. They make the refusal case testable against a node the graph can resolve but cannot source.

## 5. The rejected set — and why each was rejected

The more useful half of the record.

| Rejected edge | Gate | Reason |
|---|---|---|
| `groove metal <- heavy metal music` | 3 | Zero genuine prose sentences. Its PROSE tier was entirely markup (§3.1) |
| `groove metal <- thrash metal` | 3 | Same |
| `heavy metal music <- hard rock` | **4** | Every mention is **synonymy**, not derivation: "the terms have often been used interchangeably", "largely synonymous", "the distinction can never be more than tenuous". The article's lead names the roots as blues rock, psychedelic rock and acid rock. Hard rock is not among them |
| `heavy metal music <- classical music` | **4** | The article **contradicts** the edge: "classical and metal are rooted in different cultural traditions and practices — classical in the art music tradition, metal in the popular music tradition." Individual metal musicians citing classical composers is not a genre-level derivation claim |
| `grime <- dubstep` | **4** | The single supporting sentence says an artist "credited **the fall of dubstep** as inspiration for going back to grime" — a later revival motive, not a formative influence. Grime predates dubstep's rise |
| `disco house <- disco` | 3 | Redirect collapse (§3.3). Verified against the French house article |

### 5.1 One rejection deserves its own note

`extreme metal <- heavy metal music` was rejected at gate 4, and it is the most instructive failure in the
set. Its only prose sentence is:

> "Extreme metal is a loosely defined umbrella term for a number of related heavy metal music subgenres
> that have developed since the early 1980s."

That is a **taxonomic** statement — *is a kind of* — carried on a **P737 `influenced by`** edge. It is
exactly the P279/P737 conflation that `graph-semantics.md` §2 establishes as the error the whole project
rests on avoiding, appearing here **inside the predicate that was supposed to be safe from it.**

The consequence is not small. `graph-semantics.md` §2 concluded that P279 is taxonomy and P737 is lineage.
This pass shows the boundary is not clean: **some P737 edges also encode taxonomy**, and the prose check as
specified cannot tell the difference, because "X is a subgenre of Y" contains a real, findable mention of Y.

**This is an unresolved input to phase 2**, not something to fix here. It is recorded so the phase-2
ingestion design confronts it rather than inheriting the assumption that P737 is uniformly historical.

## 6. Reproducing this

Scripts were written to a session scratchpad, as in the 7/31 pass. They build on the backed-up validation
scripts and add: live existence re-checking, type filtering via `P31/P279*`, subject-name masking, redirect
resolution, and sentence-level extraction with an influence-verb and taxonomy-hedge classifier.

Per `docs/reviews/2026-08-01-fable-status-review.md` §4.3, where the validation scripts land in the repo is
a phase-2 decision. This pass is recorded here in full so the result does not depend on the scripts
surviving.

## 7. What this changes

- **The artifact is 21 edges over 28 nodes**, not the "~15" the scope doc estimated. Close enough that the
  scope doc's point stands (a tiny hand-verified set, not the corpus); recorded here rather than silently.
- **`graph-semantics.md` §4.5 needs amending** with the two new defects and the hand-verification survival
  rate. The 158 figure is an upper bound.
- **The five gold cases** are authored from this set, before the agent exists, per `.claude/rules/evals.md`.
- **Phase 2 inherits an open question** (§5.1): P737 is not uniformly historical.
