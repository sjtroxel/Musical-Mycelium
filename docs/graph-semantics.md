# Graph semantics — what the Wikidata predicates actually assert

**Status: validated 2026-07-31.** This doc discharges the requirement in `planning/04-RISK-REGISTER.md`
§4.4 — *"pull 20 edges, read them by hand, and decide what each property actually means in the model"* —
and the invariant in `CLAUDE.md` #3. It is a record of measurements, not a design decision. Where a
decision is still open it says so.

It lives outside `planning/` because that series is closed, and outside `phases/` because it is not
scoped to one phase: phases 1, 2 and 6 all read from it.

---

## 1. What was measured

47 edges read by hand, plus two automated passes over the full corpus. All figures verified live against
the Wikidata Query Service on 2026-07-31 and reproducible from the scripts described in §7.

| measure | value |
|---|---|
| music genres (`P31 Q188451`) | 6,328 |
| `P279` edges, genre → genre | 7,948 |
| `P737` edges, genre → genre (object typed as a genre) | 331 |
| `P737` edges out of a genre (object of any type) | 351 |
| `P737` edges of any kind, all of Wikidata | 31,691 |

`01-DATA-SOURCES.md`'s 2026-07-24 figures (6,324 genres / ~7,936 edges) are confirmed; the drift is a few
weeks of edits.

---

## 2. P279 is category membership. It is not lineage.

**This is the finding the whole project rests on, and it falsifies the original plan.**

Across 17 famous-genre edges and 30 long-tail edges, **zero** were historical-derivation claims. Every
one is a statement of kind:

```
bebop          --subclass of-->  jazz
rock and roll  --subclass of-->  rock music
grunge         --subclass of-->  alternative rock
space rock     --subclass of-->  psychedelic rock
```

Read `bebop --> jazz` carefully: bebop **is** jazz. Historically bebop emerged from **swing**, and swing
does not appear anywhere in bebop's P279 edges. Likewise rock and roll, which came out of blues, country,
R&B and gospel — none of which appear. The edges are true. They are not the claim the product makes.

**Consequence:** P279 may be ingested and may be narrated as *"X is a kind of Y."* It must never be
narrated as *"X came from Y."* The gate in `.claude/rules/grounding-and-claims.md` is the mechanism that
enforces this, and this is its primary job on the genre axis.

### 2.1 P279 leaves the genre domain two ways, not one

`04` §4.4 and `08` §4 predicted a vertical climb into abstraction. That is real and fast:

```
bebop -> jazz -> popular music -> music -> sound -> longitudinal wave -> progressive wave -> wave -> oscillation
```

Four hops from bebop to physics. A second branch runs `music -> work -> artificial object -> object -> entity`.

**The unpredicted escape is lateral, and it happens at depth 1** — P279 targets that are not genres at all:

| target | kind |
|---|---|
| music of North America, music of Jamaica, music of Spain | geography |
| popular music | market category |
| club/dance music, theatre music | function |
| Christian music | religion |
| polyphony | musical form |
| musical drama | format |

**The boundary predicate required by `phase-2-corpus-and-traversal.md` must catch both escapes.** A rule
that only stops the upward climb will still admit geography and market categories as if they were genres.

---

## 3. P737 is the lineage predicate, and it works genre-to-genre

`01-DATA-SOURCES.md` documented P737 as artist-to-artist. It also runs between genres, and those edges
are exactly the claim shape the product promises:

```
thrash metal  <-influenced by-  punk rock
bossa nova    <-influenced by-  jazz
stoner rock   <-influenced by-  acid rock, doom metal, psychedelic rock
country rock  <-influenced by-  country music
```

### 3.1 Type hygiene

351 edges leave a genre; only 331 land on something typed as a genre. **~6% point at a non-genre** —
`doom metal <- Black Sabbath` (a band), `drone music <- pedal` (a technique). **Ingestion must type-filter
both ends of both predicates.**

### 3.2 The corpus skews away from the product's own pitch

A seeded random sample (seed `20260731`) of the 351 is dominated by recent electronic and hip-hop
micro-genres: post-dubstep, skweee, UK jackin', trapetón, RnBass, downtempo deathcore, jazz guachaca.
**The canonical `bebop <- swing` edge is not in the corpus at all.** The lineage data is not merely
sparse; it is concentrated in exactly the eras the pitch does not lead with.

---

## 4. The Wikipedia prose check

**Method contributed by sjtroxel, 2026-07-31**, after a cold spot-check of one row found that Wikipedia's
acid jazz article never discusses disco.

### 4.1 The asymmetry

Wikipedia **cannot confirm** a P737 edge — it shares an editorial ecosystem with Wikidata, so agreement
approaches the graph agreeing with itself. Wikipedia **can disconfirm** one, and strongly, *for that same
reason*: if Wikidata asserts `A <- B` and A's own article never mentions B, the edge is an **orphan**,
unsupported even by its sibling source.

### 4.2 Three tiers, because infobox agreement is weak

`acid jazz` mentions "disco" exactly once in 14,495 characters, and that instance is inside the infobox.
Genre infoboxes are casually edited and rarely cited, so they are scored separately from prose.

- **PROSE** — object appears in the article body outside the infobox (strongest available signal)
- **INFOBOX_ONLY** — present in `stylistic_origins`, absent from prose
- **ORPHAN** — absent from the article entirely

### 4.3 Circularity hypothesis: tested, rejected

If Wikidata's genre properties were simply harvested from Wikipedia infoboxes, this check would be
circular. **Only 11 of 227 checkable edges (5%) are INFOBOX_ONLY**, so it is not. This was tested rather
than assumed, and the test should be re-run if the corpus is ever re-ingested.

### 4.4 Full-corpus result, all 351 edges

| tier | count | share |
|---|---|---|
| **PROSE (usable)** | **158** | 45% |
| ORPHAN | 58 | 17% |
| INFOBOX_ONLY | 11 | 3% |
| subject has no English Wikipedia article | 124 | 35% |

123 of the 158 have three or more prose mentions. **The usable corpus is ~123–158 edges, not 351.**
55% of P737 fails the weakest test that can be constructed against it.

*Amended 2026-08-02: treat 158 as an **upper bound**. Hand-reading 28 of these edges rejected 7 (§4.7),
and the mention counter has three inflating defects (§4.6). The true usable count is lower and is not yet
measured.*

### 4.5 Why this belongs in the pipeline, not in a curation pass

The check is deterministic, free, requires no model call, and is reproducible. It therefore belongs in
**ingestion**: ingest P737, run the check, keep the PROSE tier, and write the remainder to an exclusions
file with a per-edge reason. That yields a defensible corpus without hand-curation, an exclusion rate
that is a **displayed** coverage metric per `04` §4.5, and a **Tier 1 eval** that costs $0 and runs on
every commit per `.claude/rules/evals.md`.

### 4.6 Known defects. All three inflate the tier, so 158 is an upper bound

The first was found on 2026-07-31; the second and third on 2026-08-02 during the phase-1 hand-verification
(`docs/phases/phase-1-edge-verification.md` §3). None of them can deflate the PROSE tier, only inflate it.

1. **Markup counted as prose.** `[[Category:...]]` tags and navbox templates are counted as body text.
   Skweee reports 6 mentions of which 1 is genuine. Strip categories, navboxes, external-link sections
   and references before counting.

   **AMENDED 2026-08-04 — the `groove metal` example attached to this defect was wrong, and the error
   mattered.** This item originally read *"Confirmed live on 2026-08-02: both `groove metal` edges hold
   a PROSE tier with zero genuine prose sentences."* Re-measured against the live articles while
   building `ingest/prosecheck.py`, that is false: after stripping, `groove metal <- heavy metal music`
   has **6** genuine prose mentions and `groove metal <- thrash metal` has **7**.

   - **The defect itself is real and the fix is necessary.** Stripping retains 29% of the groove metal
     article's raw wikitext and halves the hit count, 12 to 6. Markup was inflating the tier; it was
     just not the *whole* signal on this article.
   - **Groove metal is a 4.7 case, not a 4.6 one** — prose that mentions the object without asserting
     influence. `groove metal <- heavy metal music` leads with *"is a subgenre of heavy metal music"*,
     which is taxonomy.
   - **`groove metal <- thrash metal` is a FALSE REJECTION.** Its lead sentence reads *"The genre is
     primarily derived from thrash metal, but played in slower tempos"*, and a second says the same.
     That is the exact claim shape the product promises. It was excluded on a reason that does not hold,
     and it is a candidate to re-admit when phase 2 step 2 rebuilds the corpus.

   The general lesson is the one that produced this whole check: **a tier is not evidence, the sentences
   are.** `ProseCheck.sentences` now carries them for exactly this reason.
2. **Self-match when the object label is a substring of the subject label.** `Western swing <- swing`
   reports 28 sentences because `\bswing\b` matches the "swing" in "Western swing" — the article matching
   against its own title. 8 survive masking; 1 supports the edge. Mask the subject label first.
3. **Redirect collapse, and it is the worst of the three.** `disco house` (Q360596) sitelinks to a title
   that redirects to **`French house`**. The check read the French house article, found "disco" discussed
   throughout, and scored the edge PROSE. This produces **confident false support** rather than a missing
   signal. Resolve redirects and reject or flag any subject article that resolves to a different title.

**A counter-defect, working the other way:** exact-label matching *under*-accepts. `country rock <- country
music` scores zero because the lead says "fuses rock and country", and `dubstep <- dub music` scores zero
because the article says "sparse dub production". Both edges are genuinely supported. The check must try
label variants and will still err in both directions — which is an argument for reporting the exclusion
rate as a measured number with a known error bar, not for claiming the check is exact.

### 4.7 The tier over-accepts by roughly a fifth on hand-reading

Of 28 candidates drawn from the PROSE tier and hand-read on 2026-08-02, **21 were accepted and 7 rejected**
— and 4 of the 7 failed on a gate the automated check cannot apply at all: whether the sentence *asserts
influence* rather than merely mentioning the object. Synonymy ("the terms were used interchangeably"),
contradiction ("rooted in different cultural traditions"), taxonomy ("is a subgenre of"), and a mention
that runs the wrong way in time ("the fall of dubstep" as a motive for returning to grime) all read as
PROSE.

**The usable corpus is therefore smaller than 158.** Do not quote 158 as the sourced-edge count without
this caveat.

### 4.8 P737 is not uniformly historical — an open input to phase 2

§2 concluded that P279 is taxonomy and P737 is lineage. The boundary is not that clean. `extreme metal
<- heavy metal music` is a P737 edge whose only prose support is:

> "Extreme metal is a loosely defined umbrella term for a number of related heavy metal music subgenres."

That is a taxonomic statement riding on the influence predicate, and the prose check cannot detect it —
"is a subgenre of Y" contains a real, findable mention of Y. **Some P737 edges encode category membership.**
Phase 2's ingestion design has to confront this rather than inherit the assumption that P737 is
uniformly historical. Recorded, not resolved.

---

## 5. The open question: 46 components

The 158 PROSE edges connect **198 genres in 46 disconnected components.**

| | |
|---|---|
| largest component | 44 genres |
| next largest | 13, 13, 9 |
| components that are a single pair | 24 of 46 |
| diameter of the largest component | 14 hops |

`CLAUDE.md` states the thesis as: *"Genres look like separate things; underneath they are one connected
organism, and most of the connections are not written down in one place."*

**The second clause is confirmed emphatically. The first is not currently demonstrable from sourced
influence data.** Two mitigations are real: the 7,948 P279 edges connect the graph taxonomically, and the
largest component contains genuine 14-hop traversals (`motswako` … `folk punk`) of exactly the kind the
product is built to narrate.

**This decision is open and belongs to sjtroxel.** It determines whether "trace the lineage between two
genres" is a general capability or a capability within one component. It is the substance of phase 6
(density and coverage) and it constrains phase 2. It is recorded here, not resolved here.

---

## 6. Consequences by phase

- **Phase 1** — *amended 2026-08-01, decided by sjtroxel; originally "genre axis only, P279."* That
  assignment contradicted the scope doc's promised **origins** answer: P279 is category membership (§2),
  and a gate that correctly refuses to narrate it as derivation makes an origins answer impossible from
  P279 data. v0.1 therefore uses **P737 genre-to-genre edges from the PROSE tier** (~15, hand-verified),
  which preserves the real claim shape (`influenced_by`) so the gate, the `Claim` model, and the prose
  templates survive into phase 2 unchanged. P279 is not ingested at v0.1 at all, so it cannot be narrated
  as derivation by construction. Reasoning in `docs/phases/phase-1-walking-skeleton-IMPLEMENTATION.md` §2.
- **Phase 2** — the boundary predicate must catch the vertical *and* lateral escapes (§2.1). Type
  filtering on both ends of both predicates (§3.1). The prose check moves into ingestion (§4.5).
- **Phase 6** — unblocked as of 2026-07-31. §4.4 and §5 are its raw material; density and coverage are
  now measured quantities rather than assumptions.
- **Evals** — §4.4's exclusion rate and §5's component structure are both sliceable metrics. The corpus
  skew in §3.2 is the coverage-honesty case `.claude/rules/grounding-and-claims.md` requires be visible
  in output.

---

## 7. Reproducing this

Scripts were written to a session scratchpad and are **not yet in the repo**. They are stdlib-only, have
no dependencies, and hit only `query.wikidata.org`, `www.wikidata.org` and `en.wikipedia.org` with a
contactable User-Agent.

| script | purpose |
|---|---|
| `wd.py` | minimal WDQS client |
| `q_a_p279.py` | P279 out-edges for 14 seed genres (§2) |
| `q_b_climb.py` | upward P279 chain walk (§2.1) |
| `q_c_tail.py` | long-tail genre→genre P279 sample (§2) |
| `q_d_p737.py` | P737 existence and counts (§3) |
| `sample30.py` | full population pull + seeded random sample (§3.2) |
| `wikicheck.py` / `prosecheck.py` | the three-tier Wikipedia check (§4) |

WDQS was fully responsive on 2026-07-31 despite the degradation documented in
`.claude/rules/graph-semantics.md`; small sequential queries were sufficient. AllMusic, Britannica,
RateYourMusic, MasterClass, Presto Music and Fandom all return 403/402 to automated fetch, so independent
citation retrieval is substantially a manual task. Search results for micro-genres are dominated by
AI-generated content farms, which any automated sourcing attempt will have to exclude.
