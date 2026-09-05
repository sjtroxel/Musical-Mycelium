# Phase 6 — Density and Coverage (v0.6) — IMPLEMENTATION

> **As-built plan.** Written 2026-09-02, immediately after the phase 5 close and before any phase 6 code,
> per `CLAUDE.md`. The scope doc is `phase-6-density-and-coverage.md`; read its §0 first, which records
> what phases 2-5 already answered. This doc is what gets built and in what order.
>
> **It was written against measurements taken the same day, not against estimates.** The scope doc's own
> instruction is *measure before committing*, and two counts it depends on had been owed since
> 2026-08-01. Both were run before a line of this plan was drafted. §2 is those numbers.

---

## 1. What this phase delivers, in one sentence

**A corpus deep enough to disagree with itself:** a second, independent source of origin claims, a
structural layer connecting artists to the genres they work in, and coverage figures that keep telling
the truth after the corpus triples.

The one-sentence version of *why*: at v0.5.0 the project's central honesty caveat is that `contested`
is arithmetically unreachable, because every edge has exactly one source. This phase is where that
stops being true, or is declared permanently true. It was never a question of effort. It was a question
of whether a second source existed at all, and as of today that is measured rather than assumed.

---

## 2. The measurements this plan was written against

All taken 2026-09-02. Reproduce with the scripts described in §11.

### 2.1 The genre corpus is already at its ceiling on Wikidata

This was the finding that reframed the phase, and it contradicts an assumption made earlier the same day.

| measure | value | source |
|---|---|---|
| music genres on Wikidata (`P31 Q188451`) | 6,328 | `docs/graph-semantics.md` §1, 2026-07-31 |
| `P737` edges genre → genre, all of Wikidata | **331** | same |
| genres touched by those edges | 198 | same |
| genres in artifact v0.5.0 | 169 | manifest |
| genre-genre edges in artifact v0.5.0 | 133 | measured today |

`ingest/discovery.py:1` is explicit that discovery is *"Full P737 discovery: every genre-to-genre
influence candidate"* — no seed list, no `LIMIT`. **So the corpus already holds roughly 95% of every
genre on Wikidata that has an influence edge at all.** The remaining ~6,130 genres carry zero P737.

**The consequence, stated plainly because it is easy to get backwards:** "expand to more genres" is not
a scheduling question and never was. Ingesting the other 6,130 would raise `isolated_nodes` from 0,
raise the refusal rate, and make the coverage panel worse while making the node count look better. On
Wikidata P737 alone, this corpus is finished. **More genres exists only through a second source.** That
is the whole argument for step 4, and it is a measurement rather than a preference.

### 2.2 P136 — the artist-to-genre membership layer

Bounded to the 804 artist nodes already in the artifact.

| measure | value |
|---|---|
| P136 pairs, corpus artist → **corpus** genre | **1,313** |
| distinct artists covered | 672 / 804 |
| distinct genres covered | 91 / 169 |
| P136 pairs, corpus artist → any genre object | 2,826 across 483 distinct genres |

1,313 membership edges against a current total of 950 edges of all kinds. This is the layer that makes
"one connected organism" drawable, because it is the only thing in reach that connects the two axes —
phase 5 §0.4 measured 128 purely-artist components and 41 purely-genre components with **none mixed**.

**Two cautions carried into step 2 rather than resolved here.** First, 672 of 804 is not 804, and the
most likely explanation is that artist nodes include P737 *objects* — influencers pulled in from
outside the P136 bound — which is plausible and **unverified**; step 2 verifies it before the number is
published. Second, only 91 of 169 genres gain an artist, so 78 genres stay artist-less and the
connectivity win is partial. Neither figure should be rounded up in copy.

### 2.3 DBpedia `dbo:stylisticOrigin` — the second source

The count owed since the 2026-08-01 review §5.1 and flagged again on 08-07. It is not close.

| measure | Wikidata P737 | DBpedia `stylisticOrigin` |
|---|---|---|
| genre → genre origin edges | **331** | **5,124** |
| distinct subjects | — | 1,215 |
| distinct genres touched | 198 | 1,628 |
| `MusicGenre` resources in total | 6,328 (Wikidata genres) | 3,551 |
| subjects carrying an `owl:sameAs` to Wikidata | — | 983 / 1,215 |

**15.5x denser than Wikidata on the one relation this project exists to trace.** Two adjacent properties
were also counted and are not planned against: `dbo:derivative` (1,253) and `dbo:musicFusionGenre` (680).

> **A counting trap, recorded because every future query against this endpoint has it.** The first run of
> the both-ends-typed count returned **35,947**, which is larger than the unfiltered count of the same
> relation and therefore impossible. DBpedia's public endpoint holds type assertions across several named
> graphs, so `COUNT(*)` over a `?a a dbo:MusicGenre` join multiplies rows per graph. **5,124 is the
> `COUNT(DISTINCT ?a ?b)` figure and the raw `COUNT(*)` is meaningless here.** Any DBpedia count in this
> phase must be a distinct-pair count or it is wrong in the direction that flatters the plan.

### 2.4 The overlap, which is the actual finding

**Re-measured against v0.6.0 on 2026-09-04, and the growth rows moved by more than 4x.** The figures
below are the current ones. The originals were measured against the 169-genre v0.5.0 corpus **before
step 2 raised the genre count to 509**, and step 4 was scoped on them; the superseded table is kept
underneath because the difference between the two is itself the finding.

459 of the 509 corpus genres carry a DBpedia `MusicGenre` resource via `owl:sameAs` — **90% alignment**,
so the two sources can be compared in a shared identifier space without name matching. Their
`stylisticOrigin` edges against the corpus's 133 genre-genre edges:

| relation | count | was (v0.5.0) | what it means for the product |
|---|---|---|---|
| **corroborates** an existing corpus edge | **80** | 80 | a genuine second source on 60% of the genre axis |
| **new** — DBpedia has it, the corpus does not | **1,100** | 237 | **8.2x the corpus's own genre edge count**, and 1.2x its entire influence layer |
| corpus has it, DBpedia does not | 53 | 53 | stays single-source and must stay labelled as such |
| **DBpedia asserts the opposite direction** | **2** | 2 | **`contested` is reachable** |

**Three of the four rows did not move, and that is a consistency check rather than a coincidence.**
Corroboration, corpus-only and contested are all measured against the corpus's 133 genre-to-genre
influence edges, and step 2 added membership without adding a single P737 edge. They *could* not have
moved. Only the rows scoped by how many genres exist to be a target did — which is exactly the
signature a real corpus expansion should leave, and its absence would have meant the probe was wrong.

1,523 `stylisticOrigin` edges leave the corpus genres in total; 1,180 land on another corpus genre and
343 point at a genre outside the corpus, which is the growth path in §2.1's terms.

**The alignment rate held across the expansion — 92% to 90% — which was not guaranteed.** The 340
genres step 2 brought in arrived from P136 artist tags rather than from P737, so there was no prior
reason to expect DBpedia to cover them as well as it covers the original 169. It does.

**`contested` is reachable, with two concrete instances rather than a theoretical capability:**

```
New Mexico music  <-> western music
electropop        <-> electroclash
```

**The second one converges with a finding phase 5 already had, by a completely different method.** Phase
5 §0.5 flagged `electroclash (1995) -> electropop (1978)` as the worst of six backwards-in-time edges, 17
years wrong. DBpedia independently records that pair the other way round, and DBpedia's direction is the
chronologically coherent one. Two independent signals, arrived at from inception dates and from a second
corpus respectively, agreeing that one specific Wikidata edge is inverted. That is the strongest possible
validation that the contested machinery is worth building, and it is the single best story this phase can
produce.

**Direction was verified, not assumed.** `graph/store.py:32` defines subject `influenced_by` object as
*the subject came out of the object*. The corpus row is `electropop influenced_by electroclash` — the
1978 genre out of the 1995 one. DBpedia has `electroclash stylisticOrigin electropop`. The reversal is
real. `MEMORY.md` records assuming the origins direction as a recurring failure mode with three instances
in one night, none of which raised; this check exists because of that.

---

## 3. The connectivity decision — DoD #1

The scope doc poses three candidate resolutions and preselects none. **This is the recorded answer, with
its reasoning, and DoD #1 asks for exactly that.**

**Resolution 3 is adopted for lineage. Resolution 2 is adopted in a modified form for structure. P279 is
still not ingested and this phase does not change that.**

The reasoning, in the order it actually ran:

1. **Resolution 1 (narrow to component-local lineage) is what the product already does, and it stays
   true.** It is not a resolution so much as the honest description of current behaviour. It was the
   strongest option in July when the largest component held 44 genres. It is the weakest now: the largest
   component holds 458 nodes and refusing across components refuses far less than it used to. Adopting it
   as *the* answer would mean declaring the corpus finished, which §2.1 shows is true of Wikidata P737 and
   false of the world.

2. **Resolution 2 was "P279 supplies connectivity". P279 is still the wrong property and this phase does
   not touch it.** `.claude/rules/graph-semantics.md` is unambiguous: zero of 47 hand-read P279 edges
   carried a historical claim, and P279 chains climb out of the genre domain both vertically and
   laterally. **But the shape of resolution 2 — one property for structure, a different one for lineage,
   held apart so neither can read as the other — is correct, and P136 is the property that fits it.**
   P136 is `genre` on an artist: a membership fact, not a historical one, and true. Ingested as a
   distinct predicate that the gate cannot narrate, it connects the graph without adding a single
   influence claim. That is resolution 2's architecture with a property that survives the semantics test
   P279 failed.

3. **Resolution 3 (a second source) is adopted, and the reason changed since the scope doc was written.**
   The scope doc says connectivity was largely solved by the artist axis, so what a second source buys is
   `contested`. That is still true and §2.4 now shows it is buildable. What the scope doc could not know
   is §2.1: a second source is also **the only available route to more genres at all**. It buys both, and
   MusicBrainz cannot be it — MusicBrainz has no influence relationship in its schema, so it can add
   releases and identifiers and not one lineage edge. DBpedia can, 15.5x over.

**The product claim that follows, and it must match — DoD #1 requires this.** `CLAUDE.md` states the
thesis as *"Genres look like separate things; underneath they are one connected organism."* After this
phase that sentence is defensible for the first time, but only in a specific form: **the organism is
connected through the people who play across it**, via membership, not through a single unbroken chain of
sourced influence. That is both true and more interesting than the vague version. Copy that implies one
continuous influence chain remains false and stays forbidden. Step 10 audits every surface for it.

---

## 4. Step plan

Eleven steps, three artifact cuts, two eval re-runs. **The cuts are deliberately separate.** P136 changes
the predicate count; DBpedia changes the source count. Landing them in one artifact means that when an
eval number moves, nothing can say which change moved it. Separating them costs two extra re-runs at
roughly $0.36 each and buys attributable numbers, which is the whole point of having an eval suite.

| step | what | artifact | DoD | spends |
|---|---|---|---|---|
| 0 | Guard the Makefile terraform targets | — | operational | $0 |
| 1 | Record the connectivity decision (§3) into the repo | — | 1 | $0 |
| 2 | P136 membership predicate; `Coverage` absorbs the density figures | **v0.6.0** | 3, 7 | $0 |
| 3 | Re-pin, re-run tier 1, republish against v0.6.0 | — | — | ~$0.36 |
| 4 | DBpedia alignment and ingestion | **v0.7.0** | 4 | $0 |
| 5 | Corroboration and `contested` | v0.7.0 | 4 | $0 |
| 6 | Geography and time on the widened corpus | **v0.7.1** | 4 | $0 |
| 7 | Slicing audit across every metric | — | 5 | $0 |
| 8 | Frontend: coverage, map, and the CC BY-SA attribution | — | 2, 8 | ~$0.02 |
| 9 | Full suite: tier 1 + judged tier 2; the held-out decision | — | 5 | ~$0.40 |
| 10 | Docs, copy audit, release, `v0.6` tag | — | 1, 8 | ~$0.02 |

### Step 0 — Guard the Makefile terraform targets — **DONE 2026-09-02**

Both halves closed the day the plan was written.

**The settings half.** The audit found `.claude/settings.json` denied `Bash(terraform apply*)` and
`Bash(terraform destroy*)` while allowing `Bash(make *)`, and those patterns do not match `make tf-apply`
or `make tf-destroy`, which run the bare commands. `Bash(make tf-apply*)`, `Bash(make tf-destroy*)` and
`Bash(make heldout-seal*)` are now denied.

**The Makefile half.** `tf-plan`, `tf-apply` and `tf-destroy` now **refuse rather than default**. All
three of the variables at issue have a Terraform default that disagrees with the deployed stack, and the
third one was worse than the audit realised:

| variable | Terraform default | live stack | what the default does |
|---|---|---|---|
| `image_tag` | `"latest"` | the git sha | trades a commit-traceable pin for an ambiguous one |
| `llm_provider` | `"local"` | `bedrock` | **reverts the public URL to the stub LLM** |
| `reserved_concurrency` | `5` | `-1` | **fails outright** — this account's whole ceiling is ~10 |

A shared `TF_REQUIRE` macro demands all three and prints the correct invocation when any is missing.
Verified by running it: bare refuses, partially-specified refuses, and fully-specified expands to
`terraform -chdir=infra/terraform/main plan -var image_tag=... -var llm_provider=... -var reserved_concurrency=...`.
`make check` unaffected at 1189 — `tf-validate` uses none of these.

**`tf-destroy` carries a second, separate guard**, and it is the more important of the two:
`CONFIRM=destroy-the-live-site`. Destroying `aws_cloudfront_distribution.spa` means AWS assigns a **new
hostname on re-apply**, so `d2vtdkpgmecreg.cloudfront.net` stops existing and every link to it dies. That
is unrecoverable and it is the one thing in this repo a typo should not be able to reach.

**What is still not fully closed, stated rather than glossed.** A deny pattern is matched against the
command string, so `Bash(make tf-destroy*)` covers `make tf-destroy` and not `make -C . tf-destroy` or a
`cd` that precedes it. **The settings deny is defence in depth; the guard inside the Makefile is the half
that cannot be routed around by invoking make differently.** That is the argument for putting the real
check in the thing being run rather than only in the pattern that describes it, and it generalises to
every future target this phase adds.

### Step 1 — Record the connectivity decision — **DONE 2026-09-02**

§3 of this doc is the reasoning. Step 1 landed the *decision* in the five places the rest of the repo
reads it from, as **decision C1**:

| file | what landed |
|---|---|
| `docs/graph-semantics.md` §5.2 | **the canonical record.** §5 posed the question in July and said it was open and belonged to sjtroxel; §5.2 closes it, with the Wikidata-ceiling finding, the DBpedia counts, the P136-over-P279 argument, and what the decision does *not* settle |
| `docs/graph-semantics.md` §6 | the phase 6 consequence bullet now names the two properties and points at §5.2 |
| `docs/ROADMAP.md` §4 | two dated decision-history entries — C1, and the step 0 deny-pattern generalisation |
| `CLAUDE.md` | the thesis paragraph, amended |
| `README.md`, `docs/spa-explained.md` | status, and a dated forward-note on the section that goes stale at step 2 |

**The trap this step exists to avoid, and it nearly landed.** The decision is made now; the corpus does
not move until step 2. So every sentence written here had to be true of **v0.5.0**, not of the corpus this
phase is going to cut. A first draft of §5.2 read *"the first now becomes demonstrable"*, which is
ambiguous between "as of this decision" and "as of this corpus" — and the second reading is false. Both
`CLAUDE.md` and §5.2 now carry the explicit line: **until phase 6 step 2 lands, present-tense copy must
still say 169 disjoint components.**

That is DoD #8 being enforced against this phase's own optimism rather than against a legacy sentence,
which is the harder direction and the one it will keep being needed in.

**What was decided about P136 that was not in the plan.** §3 argued P136 passes the semantics test P279
failed. Writing it up surfaced that `.claude/rules/graph-semantics.md` requires hand validation before
ingesting a property **with no exemption for easy cases**, so a hand-check is owed and step 2 owes it.
§5.2 records that it will be smaller than the 47-edge P279 pass and *why the reason is not "because this
one is obvious"*: P279's risk was a systematic misreading of the property's meaning, which needs a large
sample to rule out. P136's meaning is not in question; its risk is per-row noise — an artist tagged with
a genre they barely played — which a small sample bounds and no sample size eliminates. Different failure
mode, different sample size, stated rather than assumed.

### Step 2 — P136 membership -> artifact v0.6.0 — **DONE 2026-09-02**

**Artifact v0.6.0 is cut. The pin has NOT moved** — `graph/memory.py:34` and `ingest/wikidata.py:59`
still read `0.5.0`, which is step 3's job. `make check` is green at **1209**.

| | v0.5.0 | **v0.6.0** |
|---|---|---|
| nodes | 973 | **1,313** |
| edges | 950 | **3,731** |
| genres | 169 | **509** |
| **components** | **169** | **12** |
| largest component | 458 | **1,286** of 1,313 |
| isolated nodes | 0 | **0** |
| max path hops | 6 | 7 |

**169 disjoint islands became 12, and 98% of the corpus is now one component.** That is the phase's
central claim becoming demonstrable, and §3's wording holds exactly: the organism is connected through
the people who play across it.

Verification counts: `MEMBERSHIP_CITED` **1,419**, `MEMBERSHIP_BARE` **1,363**, against 949 influence
edges. **63 P136 objects were rejected `NOT_A_GENRE`** — the type test was a real filter, not a
formality.

#### The plan said bounded. The measurement said the bound was arbitrary.

The written plan kept only P136 objects already among the 169 genres. A measurement killed it, and the
finding is counter-intuitive enough to be worth keeping: **the bound does not coarsen the data, it
filters it arbitrarily.** It keeps whichever of an artist's genres happen to fall inside the 169, which
has no relationship to which is representative. Every P136 Wikidata records for Red Hot Chili Peppers:

```
jazz fusion, alternative rock, rock music, alternative metal, classic rock,
funk metal, hard rock, funk rock, rap rock              -> all outside the 169
heavy metal music                                       -> the only one inside
```

Nine dropped and the survivor is arguably the least representative. Bounded ingestion would have
published "Red Hot Chili Peppers, heavy metal" and nothing else, on the map, publicly. Across the layer
the bound discarded **half of all genre precision** (2,605 tags to 1,313) and left **200 artists on a
single arbitrarily-chosen genre**. `rock music` is not among the 169, nor are alternative rock, pop
rock, hard rock, indie rock or rock and roll — the 169 are exactly the genres carrying a P737 edge, and
those carry none.

Decision, sjtroxel 2026-09-02: **unbounded**. The 340 surviving objects arrive as genre nodes. They are
not dead ends — 305 of 392 candidates align to a DBpedia `MusicGenre` and 185 carry `stylisticOrigin`,
so step 4 gives many of them sourced origins — and none is isolated.

#### The hand-check, which the rules require and which changed the schema

30 pairs, stratified 15/15 by whether the artist carries one-to-two genres or three or more, seed
`p136-handcheck-2026-09-02`. **The property passed cleanly: zero of 30 were category errors about the
relation**, against P279's 47 of 47. What it found instead was per-row noise **predicted by whether the
Wikidata statement carries a reference** — 17 of 18 referenced pairs read as clean against 5 of 12
unreferenced.

n=30, judged by an agent rather than from hand-read sources: **a direction, not a rate**, and it ships
labelled that way. It is enough to justify **two tiers rather than one**, so the row carries the
difference instead of averaging a 94%-clean population together with a 42%-clean one.

**One call in that sample was wrong and sjtroxel caught it.** `McFly -> punk rock` was scored a data
error; Wikidata actually records four genres for McFly including `pop-punk`, and it is *our* corpus
bound that drops the precise tag and keeps the coarse one. Wikidata was right. That correction is what
surfaced the arbitrary-filter finding above, so the entire unbounded decision traces to it.

#### Prevention is not repair, and the build said so out loud

The rank filter added to both discovery queries excludes deprecated statements from **new** crawls. The
first v0.6.0 build then reported P737 tiers still summing to **950** — because every one of those edges
came from v0.5.0 and was carried across untouched, which is the entire point of carrying them across.
The fix reached only rows nobody was worried about.

`wikidata.deprecated_statements` is the repair half: a cut that inherits edges re-checks them. The
rebuild dropped `Nine Inch Nails influenced_by Pink Floyd` and `ASSERTS_AUTO` moved 760 to **759**.
**Generalises: a guard added to the producer does not reach data the consumer inherited.**

#### A frozen record versus a widened schema

Adding two verification tiers failed three tests at once — the manifest counts, the `/health` payload,
and the committed eval baseline — all comparing a v0.5.0-era frozen record against a v0.6.0-era schema
by strict equality, and **none of them wrong about the corpus**. `schema.py` already promised this
("a widening, so every earlier artifact stays valid") and nothing encoded it.

`schema.counts_agree` encodes it once, narrowly: a level the record omits must be **zero**; every level
it names must match exactly. A record that misreports still fails. The alternative — regenerating the
baseline — would have rewritten a historical number for a non-event, and that file's own docstring says
to find out why before regenerating.

#### The density figures moved into `Coverage`, and they exclude membership on purpose

Phase 5's owed item. `genres_without_recorded_origins`, `genres_with_one_connection`,
`busiest_genre_connections` and the `connections` histogram are now computed in `graph/coverage.py`.

**They count `influenced_by` edges only.** Membership outnumbers influence roughly three to one at
v0.6.0, so including it would report a corpus three times denser in the one dimension this project
claims to measure. Verified rather than asserted: the backend reproduces phase 5's independently
computed frontend figures for v0.5.0 **exactly** — 85 / 108 / 6 and an identical histogram.

At v0.6.0 they read **425 / 108 / 6**, with a new `'0': 340` bucket. Nothing that already existed
moved; what moved is the honest part — 340 genres now have no sourced origin at all.
`web/src/corpus-facts.json` still exists and is still asserted against the pinned artifact, so it
cannot rot silently; **step 8 deletes it** when the frontend moves to the new pin.

#### Coverage got worse in the way that matters, and it is published

| | v0.5.0 | v0.6.0 |
|---|---|---|
| genres without inception | 28 | 131 |
| genres without country | 48 | 164 |
| distinct places | 29 | **50** |
| genres naming neither US nor UK | 43 | **92** |
| **top country share** | **0.421** | **0.562** |

More places and more non-anglophone genres in absolute terms, and **a corpus measurably more
US-concentrated in relative terms**. Both are true and the last one is the uncomfortable one, so it goes
in the panel at step 8 rather than the two that flatter.

#### An inconsistency found on the way through, and it is benign

The shipped v0.5.0 manifest records `genres_without_us_or_uk: 44`; the code computes **43**. The
manifest was written 2026-08-06 and the guard that fixed the count landed 08-07, and artifacts are
immutable so it was never rewritten. **It never reaches a user** — `graph/memory.py:251` recomputes
coverage at load rather than reading the manifest, which is the 2026-08-05 recompute-at-load decision
paying off a second time, now for coverage as well as structure. v0.6.0's manifest and the code agree.

#### DoD #6 held, and it was checked rather than assumed

No file in `agent/` was edited. `tests/test_membership.py` asserts `plays_genre` is absent from
`ALLOWED_PREDICATES`, so the gate refuses it `UNSUPPORTED_PREDICATE` with no change, and the pre-existing
cross-axis check refuses it again. **The artifact-level lock `tests/test_claims.py:253` only described in
a comment is now asserted** — no `influenced_by` edge crosses the axes, in either artifact — and its
companion asserts every membership edge does, so neither can pass vacuously.

### Step 3 — Re-pin and re-run tier 1 — **DONE 2026-09-03**

Bump `graph/memory.py:34` and `ingest/wikidata.py:59` together — `tests/test_graph_store.py:251` already
asserts they agree, which is a lock worth knowing exists. Re-run tier 1, republish the numbers.

**What is expected to move and what is not.** Groundedness and citation resolution should be unchanged at
100% — membership edges add no claims. `verification_mix` gains a new tier and will move by construction,
which is a tracked metric and not a gate. Traversal recall is measured against gold cases whose claims are
all `influenced_by` and should not move; if it does, that is a finding about the traversal, not about the
corpus, and it gets chased before step 4.

#### As built, 2026-09-03

`make check` **1215 passed**, 0 failed, 14 `costs_money` deselected. Frontend **146 passed**. Eval gates
**3 passed / 0 failed / 2 not applicable**, unchanged. Full record in `docs/KNOWN-GAPS.md`; what belongs
here is how the plan above held up.

**The three predictions, scored honestly.**

| the plan said | outcome |
|---|---|
| groundedness and citation resolution unchanged at 100% | **held** — 67/67 both, before and after |
| `verification_mix` gains a tier by construction, tracked not gated | **held** — two tiers, `MEMBERSHIP_CITED` and `MEMBERSHIP_BARE`, both at zero |
| traversal recall should not move; if it does, chase it before step 4 | **it moved, and it was chased** |

The third is the one that mattered. The pin bump failed 52 tests and **17 of them were one defect**:
`neighbors()` and `path()` had no predicate filter, so a corpus with two predicates returned membership
edges wherever influence was asked for. "Who influenced Michael Jackson" came back with three genres he
plays; "what came out of rock music" came back 113 artists and no genres; a gold refusal case stopped
refusing. The clause in the plan — *"that is a finding about the traversal, not about the corpus"* — was
right, and writing it down in advance is why it was chased rather than absorbed into a number update.

Fixed with a keyword-only `predicates` argument on both methods defaulting to `schema.INFLUENCE_ONLY`.
No tool and no loop was edited, so invariant 4 held under a seam change. Verified by comparing all 973
shared nodes in both directions across the two artifacts: influence traversal is now identical, save the
one edge step 2 deliberately dropped.

**Two v0.6.0 defects found and closed on the way:** 21 uncitable `plays_genre` edges whose statement URIs
differ from their subject QID only by case, and an empty `source_snapshot` — 0 entries against 509 genre
nodes — from `membership.py` omitting the argument. Builder fixed, artifact repaired in place from the
node revisions already inside `graph.json`, `graph.json` itself untouched.

**Three adversarial cases re-authored** (`rock` → `black`, `raga` → `dastgah`, `afrobeat` → `juju`) and
the gold set re-pinned after the pair-by-pair neighbour check its own file requires. Behind them was a
quieter bug: the attack scripts in `eval/harness.py` still named the retired subjects, and the only
symptom was `gate_rejections_consistent` slipping 16 → 15 while every headline metric held.

**Deliberately not done: the frontend.** `web/src/chips.json` stays at `0.5.0` until step 8, because the
SPA fetches the artifact as a static asset and v0.6.0 is 1.77MB against 640KB — payable three times if
paid now, with v0.7.0 and v0.7.1 still to come. **The condition attached is DO NOT DEPLOY until step 8**:
a deployed site would answer from v0.6.0 and draw its map from v0.5.0, omitting nodes the answer cites.

**The live run closed it, 2026-09-03**: 41 cases, **5 of 5 gates passed**, groundedness and citation
resolution 100% over 69 claims, and **`MEMBERSHIP_CITED` and `MEMBERSHIP_BARE` both zero on a real
model** — the step's central prediction, confirmed by execution rather than by construction.

`cases_correct` read 39/41 against the previous run's 41/41 and **that is not a regression**: measured
against `eval/noise_floor.json`, every figure sits at its modal value and the 8/24 run was the outlier
above the floor. Both failing cases predate v0.6.0 — `gold_v0_1_020` failed all five noise-floor runs on
v0.5.0, and `adv_008` failed three of five. Detail and the adv_008 transcript are in `KNOWN-GAPS`.

**What the run leaves open:** the noise floor is stale (artifact 0.5.0, revision `f84453a`) and v0.6.0 is
n=1, so no threshold near these numbers moves until five runs are measured on this corpus.

### Step 4 — DBpedia alignment and ingestion → artifact v0.7.0 — **DONE 2026-09-04**

The source half, and the largest step in the phase.

- `ingest/dbpedia.py`. Alignment through `owl:sameAs` into Wikidata QIDs, so the two sources share an
  identifier space and comparison is exact rather than fuzzy. **459 of 509 align; the 50 that do not
  are a published number, not a silent drop.** *(Was 155 of 169, measured pre-step-2. Re-measured
  2026-09-04 — see §2.4.)*
- `SOURCE_DBPEDIA` in `graph/schema.py`. **`Edge.source` stops being "always Wikidata"**, which is a
  sentence currently written into `CLAUDE.md`, both rules files, `README.md` and `agent/claims.py`'s
  docstring. Step 10 audits all of them; step 4 lists them as it breaks them.
- Its own verification tier. DBpedia's `stylisticOrigin` is extracted from the Wikipedia infobox, not from
  body prose, so it is neither `HAND` nor `PROSE_AUTO` nor `ASSERTS_AUTO`. It is an editor-curated
  structured field, closest in kind to a Wikidata statement. `INFOBOX_AUTO` names what it is. **Do not
  reuse a Wikidata tier for it** — the tiers are how this project avoids overstating its own rigour, and
  the moment two different checks share a label the tier stops meaning anything.
- ~~**`Node.source` stops being "always Wikidata" too.**~~ **Withdrawn while building, same day.** It
  looked true from the probe and is false in the build: every genre this axis discovers is resolved to a
  Wikidata QID and has its label, revision and coverage read *from Wikidata*, so the node's provenance
  genuinely is Wikidata and marking it `dbpedia` would overstate what DBpedia supplied. **Only
  `Edge.source` changes**, which is what the original plan said. The 13 resources with no `owl:sameAs`
  are excluded rather than admitted as DBpedia-native nodes — admitting them needs a node whose
  `revision_id` cannot exist, and that is a decision this step does not make.
- The **1,100** new edges are ingested; the **343** pointing outside the corpus bring their target genres
  in, which is where corpus growth comes from. Growth is bounded by what `stylisticOrigin` reaches,
  deliberately — not by a target node count.

#### How far growth follows — measured, and the ambiguity is now closed

*"Bounded by what `stylisticOrigin` reaches"* was ambiguous between following the out-of-corpus edges
**one hop** and following them **to closure**. At the old figure of 213 that ambiguity was cheap. At 343
it is not, so it was measured rather than argued (2026-09-04, against the full 5,124-pair DBpedia origin
graph — which reproduced the §2.3 count exactly):

| | new genres | cumulative genres | origin edges |
|---|---|---|---|
| hop 1 | +167 | 621 | 1,804 |
| hop 2 | +49 | 670 | 1,942 |
| hop 3 | +8 | 678 | 1,956 |
| hop 4 | — terminates | | |

**Decision: take the closure.** It terminates on its own after three hops, and the entire difference
between stopping at one hop and going to closure is **57 genres and 152 edges**. Paying 57 nodes to
delete an arbitrary cutoff is the same trade step 2 made when it went unbounded, except an order of
magnitude cheaper. A one-hop bound would have to be defended as meaning something, and it does not mean
anything — it is just where we happened to stop looking. The ceiling is knowable and gets published
alongside the number: the whole DBpedia genre-origin graph is 1,601 genres, and the closure reaches 678
of them, so growth is bounded by the source's own extent and not by a rule of ours.

**211 of the 224 arriving genres carry a Wikidata QID; 13 do not.** Those 13 are hand-checked before
ingestion rather than admitted or dropped in bulk, because the sample immediately produced
`List_of_break-in_records` — a Wikipedia *list article* typed as `dbo:MusicGenre`. **DBpedia's typing is
noisier than Wikidata's, and this is the first hard evidence of it in the phase.** It is also an argument
*for* `INFOBOX_AUTO` being its own tier rather than a nicety: a source that types a list article as a
genre has visibly different rigour from one that does not, and the tier is where that difference is
recorded. A DBpedia-only node also cannot be given a Wikidata `revision_id`, so provenance for those 13
would have a different shape from every other node in the corpus — a second reason not to bulk-admit them.

**Licensing, which is a hard rule and not a footnote.** DBpedia is Wikipedia-derived and **CC BY-SA**.
`04-RISK-REGISTER.md` §4.3 names DBpedia explicitly: *"attribution required, share-alike applies... display
the attribution and link back."* `.claude/rules/graph-semantics.md` says the attribution is displayed, "not
in a buried credits page." So:

- Every DBpedia-sourced edge carries a resolvable DBpedia resource URI in `source_id`, same as Wikidata
  edges carry a statement URI. Attribution is structural, which is the same move the project already makes
  for provenance.
- The SPA displays the attribution and links back. Step 8.
- **A `DATA-LICENSES.md` is added**, because the repo `LICENSE` is MIT and that covers the code. The
  artifact is now a mixture: Wikidata is CC0, DBpedia is CC BY-SA 3.0. Stating which parts are under which
  licence is cheap now and awkward later, which is exactly what §4.3 predicts.
- **Named as uncertain in §9:** whether incorporating CC BY-SA data into a committed artifact in an
  MIT-licensed repo creates a share-alike obligation on the artifact is a real question and I am not
  qualified to answer it. The plan takes the conservative position — attribute, link back, and state the
  per-source licence — which is defensible regardless of how the question resolves.

### Step 5 — Corroboration and `contested` — **DONE 2026-09-04**

The payload, and the part most worth designing carefully rather than fast.

**The schema move, chosen to be additive because DoD #7 requires it.** `Edge.source` does *not* become a
list — that would repurpose a field every pinned eval number reads. Instead:

- `Edge.corroboration: str | None`, defaulting to `None`. `None` means single-source and every v0.5.0 edge
  keeps its exact current meaning. A populated value is the second source's resolvable URI. 80 edges get
  one on day one.
- **`contested` is a property of a pair, not of an edge**, and getting this wrong is the easy mistake. It
  holds when both `(A, B)` and `(B, A)` exist from different sources. It is *derived* over the edge set,
  not stamped on a row, and it is computed in `graph/`, never proposed by the model.
- `agent/claims.py:UNREACHABLE` loses `contested` and keeps `checks_disagree` unless step 5 also makes
  that one real. **The test that locks both as unreachable will fail at this step, and that failure is the
  system working exactly as designed** — the rules file says a future corpus that could express one should
  fail the test rather than quietly making it reachable. It is a green-to-red transition to be celebrated
  and then resolved deliberately, not routed around.

**What must not happen, stated because the temptation is real.** `verification` is *how strongly one source
was checked*. `corroboration` is *whether a second source agrees*. They are different guarantees and the
project has already corrected `CLAUDE.md` and two rules files once for blurring exactly this. A
corroborated `PROSE_AUTO` edge is not thereby a `HAND` edge. Do not collapse the two fields, do not let a
corroboration promote a verification tier, and do not let the UI show one number where there are two.

### Step 6 — Geography and time → artifact v0.7.1 — **DONE 2026-09-04**

DoD #4 asks that a traversal name specific people, places and dates rather than only genre labels. After
step 4 the genre population has grown, so `P571` and `P495` must be re-read for the new genres — the same
single SPARQL read that produced v0.5.0 from v0.4.0, which is why this is a separate small cut rather than
folded into step 4.

**Start from phase 5 §0.5's finding, which is that the dates are not measurements.** Six of 102 datable
edges run backwards in time. Phase 5 declined to build geometry on those numbers and that was correct. What
this step adds is that **DBpedia now provides an independent check on two of the six**, and the two it
checks it disagrees with Wikidata about. So the backwards edges stop being an embarrassing artifact and
become the corpus's most interesting output: a place where two sources disagree and the disagreement is
visible. Whether the remaining four have a DBpedia opinion is unmeasured and is the first thing this step
should ask.

**The undated three are the non-Western three** — Na mele paleoleo, Pinoy hip hop, sampledelia — every
time. Whether DBpedia dates them is the sharpest single test of whether a second source improves the skew
or reproduces it, and the answer goes in the coverage panel either way.

### Step 7 — Slicing audit — **DONE 2026-09-04**

DoD #5 is recorded as already met by `eval/slices.py` from phase 3 step 7b. **Met at v0.5.0 is not met at
v0.7.1**, which is the whole reason DoD items are re-judged rather than carried. Two new dimensions exist
that the slicer has never seen: source (Wikidata / DBpedia / both) and predicate (`influenced_by` /
`plays_genre`). An aggregate that looks healthy while the DBpedia-only slice fails is the default outcome
without slicing, and it is now possible for the first time.

### Step 8 — Frontend — **DONE 2026-09-05**

**Written 2026-09-05, immediately before building, against measurements taken the same morning.** The
four bullets this section held until now were the up-front sketch; they are kept as 8.11 at the end and
every one of them survived. What the sketch did not know is that **one item on this list is a
correctness issue rather than a presentation one** — the map draws membership as derivation — and it is
now 8.2 rather than a sub-clause of "show artists and genres together".

**Baseline, measured this morning, not recalled:** `make check` **1329 passed**, 14 deselected, mypy
clean over 97 source files, root 17 of 18, eval gates **3 passed / 0 failed / 2 N/A**. Frontend
**146 passed** across 13 files. Everything below is a delta from that.

#### 8.0 As built — what the plan did not know

**Verified on completion:** `make check` **1330 passed** (was 1329), 14 deselected, mypy clean over 98
source files, root 17 of 18, eval gates **3 passed / 0 failed / 2 N/A**. Frontend **159 passed** across
15 files (was 146 across 13). **DO NOT DEPLOY is lifted** — both pins read `0.7.1`.

Six things the plan got wrong or could not see, recorded because the corrections are the useful part:

1. **The inspector had the same defect as the map, in plain English, and 8.2 did not name it.** `split()`
   classified every incident edge by subject/object position, so with `artist plays_genre genre` the
   panel would have read *"Miles Davis — Came out of — jazz"* and *"jazz — Led to — Fred Astaire"*.
   Membership is now a third list with its own heading. Locked in `components/inspector.test.ts`, and the
   lock was verified by breaking it: `expected [ 'Q_jazz' ] to deeply equal []`.
2. **`NEIGHBOURS_PER_OPEN` was worse than 8.3 estimated.** The plan said max degree 204 and 37 nodes over
   30 — correct — but the docstring's promise ("cannot truncate") was load-bearing for
   `RenderNode.hidden`'s meaning. Resolution: the number stays at 30 and the promise changes, because
   truncation here is already *visible* by design.
3. **`Verification` in `types.ts` had gone stale against the backend, and a real claim carried the
   missing tier.** The union listed the original four; v0.6.0 added two `MEMBERSHIP_*` and v0.7.0
   `INFOBOX_AUTO`. `ClaimList`'s wording map was short the same three, so an `INFOBOX_AUTO` claim printed
   the **raw constant** at a reader. `contract.test.ts` caught it on the re-pin — exactly its job.
4. **The three SSE fixtures were NOT captured the same way, and re-recording all three would have
   destroyed one.** `acid-jazz-answer` and `kate-bush-refusal` are `local-stub` captures and re-recorded
   faithfully. **`kate-bush-descendants` was captured on real Haiku 4.5 with 7 claims**; the stub returns
   a refusal, because it passes the whole question to `resolve_node` as the name. It is left at v0.5.0
   and **owed a decision** — see 8.9.
5. **`corpus-facts.json`'s `coverage`/`density` split is not stale** and the plan said it was.
   `Coverage.as_dict()` deliberately serialises 10 of 14 fields; it is the wire contract. Corrected in
   8.5 rather than silently.
6. **The first draft of the generator got the influence DIRECTION backwards** — counting nodes untouched
   in either direction (120) instead of nodes that are never a subject (723). That is the project's named
   second failure mode, and `tests/test_corpus_facts.py` caught it immediately. The generator now reads
   through `Direction.INFLUENCED_BY` so it cannot drift from the test's definition.

**What the screenshot pass found, which no test could.** The panel measured **1,961px against a 900px
viewport** — twice the 988px phase 5 treated as the defect. Three causes, all fixed, nothing removed:
`How densely` rendered one bar per distinct connection count, 35 bars in 974px with 26 of them counting
five genres or fewer (now 14 bucketed bars, 457px, and the buckets still sum to every genre); the
places tail wrapped 57 tick marks onto a second line of four, **reading as a broken bar** — the exact
2026-09-01 defect (now `nowrap`, one line, all 57); and the new contested section left **639px of empty
column 2** beside it, the dead-quarter-panel defect (now a full-width band, 296px). **Final: 1,203px,
down 39%, no horizontal overflow at 1280px or 420px.**

**Not done in this step and not owed by it:** the §9.3 projection, deferred by decision (8.1), and the
`ResolveSource` DBpedia lookup, routed out under DoD #6 (§7).

#### 8.1 The re-pin, and what it actually costs

`web/src/chips.json:artifact_version` goes `0.5.0` -> `0.7.1`. It is the only place the frontend pin is
written: `staticGraph.ts:65` reads it into `GRAPH_PIN` and `web/scripts/stage-graph.mjs` reads the same
field to decide what to copy. Then `tests/test_chips.py:56`'s `FRONTEND_PIN_LAG_UNTIL_STEP_8` constant is
deleted and the plain equality restored, which is what lifts **DO NOT DEPLOY**.

**The size question the lag was deferring, answered with numbers rather than adjectives.** v0.5.0's
`graph.json` is 655,641 bytes raw / **56,778 gzipped**. v0.7.1 is 2,694,624 raw / **187,294 gzipped**.
So it is 4.1x on disk and **3.3x over the wire — 183 KB, not 2.6 MB** — because `frontend.tf` already
sets `compress = true`.

**Corrected while building, 2026-09-05: there is NO git cost, and the sentence here claimed one.** This
read *"the 2.6 MB is a git cost, paid once"*. It is not: `.gitignore:98` excludes `web/public/graph/`,
and `web/package.json`'s `prebuild` runs `stage-graph.mjs` on every build, so the staged copy is
generated from the artifact already committed under `src/musical_mycelium/artifacts/v0.7.1/`. The
re-pin adds **zero** bytes to the repository. The lag was still the right call — it deferred a
*decision* and three rounds of test churn, not a download — but the reason recorded for it in
`tests/test_chips.py` ("committing a second copy of the corpus to the repo") was also wrong, and is
corrected there too.

**But §9.3 already decided the SPA gets a projection, and left its FORM as a step 8 question. That
question is live and it is not answered by the gzip number above.** §9.3 reasoned from raw megabytes;
gzip absorbs a lot of what it was worried about, so the decision deserves the measured figures rather
than the projected ones it was made on. Measured this morning against v0.7.1, keeping only what the map
actually draws — `id`, `label`, `kind`, `inception_year` on nodes; `subject_id`, `object_id`,
`predicate`, `verification` on edges:

| | raw | gzipped |
|---|---|---|
| v0.7.1 full (what ships today, byte-for-byte) | 2,694,624 | **187,294** |
| v0.7.1 projected | 650,503 | **52,411** |
| v0.5.0 full, for reference | 655,641 | 56,778 |

**A projected v0.7.1 costs the browser almost exactly what the full v0.5.0 costs it today** — 52 KB
against 56 KB — and the projection removes 72% of the transfer. The fields it drops are `source_id`,
`retrieved_at`, `revision_id`, `source`, `prose_tier`, `corroboration` and the infobox columns; nearly
all of that is provenance the map never draws.

**The catch, and it is why this is a decision and not a cleanup.** `source_id` is the citation itself.
`NodeInspector` renders edges read from the static graph, so dropping `source_id` means an inspected
edge either loses its link back or needs a second fetch to recover it — and 8.7 has this step adding a
*visible CC BY-SA attribution and link-back*, which is the same bytes. §9.3's two options were "a second
generated file" or "fetch a neighbourhood on demand"; there is a third that did not exist when §9.3 was
written, which is **ship the projection and keep provenance on the claim stream only**, since a
gate-approved claim already carries its `source_ids` through the SSE frames.

**DECIDED 2026-09-05 by sjtroxel: take the 183 KB and defer the projection.** The numbers above are
the reason, recorded so the deferral is a measurement rather than a silence. 183 KB gzipped is not a
user-visible problem on a page that already streams a model response, and the projection interacts
directly with 8.7's attribution requirement — building both in the same step is how one quietly breaks
the other. **This closes the open half of §9.3.** The projection remains available and its measured
saving is on the table above; what is settled is that it is not this step's work.

**Blast radius, checked before writing this rather than discovered during it.** Step 3's re-pin broke 52
tests and the v0.7.1 re-pin broke 78; he said explicitly that checking first is what made those
manageable, and that a re-pin is never scheduled as a one-liner. Twelve files under `web/src` name
`0.5.0`:

| file | occurrences | what it is |
|---|---|---|
| `graph/subgraph.test.ts` | 4 | fixture pins |
| `graph/map.test.tsx` | 4 | includes an asserted fetch URL `/graph/v0.5.0/graph.json` |
| `useLineageRun.test.ts` | 2 | `done` frame version |
| `contract.test.ts` | 2 | fixture provenance + `done` assertion |
| `graph/layout.test.ts` | 2 | comments |
| `graph/layout.ts` | 2 | **a measured claim, see 8.3** |
| `graph/subgraph.ts` | 1 | **a measured claim, see 8.3** |
| `components/mark.ts` | 1 | **a measured claim, see 8.3** |
| `fixtures/*.sse` (3 files) | 3 | recorded bytes, see 8.9 |
| `chips.json` | 1 | the pin itself |

The three source files are the ones that matter. The test files are mechanical.

#### 8.2 THE CENTRAL ISSUE: the map is predicate-blind, so membership renders as derivation

This is the item to build first and the one most likely to be got wrong quietly.

**Measured at v0.7.1: 5,066 edges are 2,782 `plays_genre` and 2,284 `influenced_by`.** Membership is
**55% of the edge set**. And:

- `subgraph.ts` builds `incident` from **every** edge regardless of predicate, and `RenderEdge` carries
  `from`, `to`, `kind: "claimed" | "context"`, `order`, `verification` — **no predicate field at all**.
  `kind` is an approval distinction, not a semantic one.
- `RenderEdge`'s own docstring reads *"The arrow of history. `subject influenced_by object`"*. It is
  written on the assumption that every edge in the map is an influence edge. At v0.5.0 that was true.
  At v0.7.1 it is false for the majority of them.
- `layout.ts` layers by longest path, and `GraphView` was told by step 5 that **x is influence depth**.
  Feed it membership edges and it will place an artist one column "downstream" of a genre and draw the
  arrow of history through it.

**So the re-pin alone, with no other change, makes the map state that Miles Davis was derived from
jazz.** `CLAUDE.md` forbids exactly this — *"never let membership read as derivation"* — and
`.claude/rules/grounding-and-claims.md` puts the same rule on the gate. The gate is safe:
`ALLOWED_PREDICATES` is `frozenset({PREDICATE_INFLUENCED_BY})`, so no `plays_genre` proposal can ever
become a claim, and `ClaimList.tsx:39` (which hardcodes the words " influenced by ") never sees one.
**The map is the hole, because the map reads the static artifact directly and never passes through the
gate.**

**What must happen, and the order is not arbitrary:**

1. `RenderEdge` gains `predicate`, carried from the artifact rather than inferred. This is the
   enabling change and nothing else in 8.2 is safe without it.
2. `layerOf` layers on **influence edges only**. Membership must not create depth, because depth means
   "came after" and membership means no such thing.
3. Membership renders **visibly differently** from influence — a different stroke, and no arrowhead.
   The arrowhead is the assertion of direction; a membership edge has a direction in the data
   (`artist plays_genre genre`) that is not a direction in *time*, and drawing it with the same
   arrowhead is the whole failure restated in ink.
4. The legend and the node inspector say which is which in words, not only in ink. `NodeInspector.tsx:31`
   already carries the direction comment for influence; it needs the membership case beside it.

**The trap, stated so it is not walked into:** it is tempting to solve this by filtering `plays_genre`
out of the map entirely. That would be correct and it would also **delete the phase's headline result**
— artists and genres in one component is the amended thesis, and the thesis is that the organism is
connected *through the people who play across it*. Filtering membership out returns the map to 169
islands while the corpus has 7 components. Draw both, distinguish them.

#### 8.3 Three measured constants that go false at the re-pin

Each of these is a comment or a constant justified by a measurement of v0.5.0. All three were verified
against v0.7.1 this morning.

**`subgraph.ts:112` — `NEIGHBOURS_PER_OPEN = 30`. This is a live defect, not a stale comment.** Its
docstring promises: *"the highest degree in artifact v0.5.0 is 25 and no node at all exceeds 30, so this
budget cannot truncate any single node's neighbourhood: opening a node shows all of its connections or
the corpus does not hold them."* Measured at v0.7.1, undirected degree over all predicates:

```
   204  pop music        157  jazz            152  rock music       127  hip-hop
    97  soul              93  alternative rock 86  punk rock         83  rhythm and blues
```

**Max degree is 204 and 37 nodes exceed 30.** The budget now silently truncates 37 nodes while the code
promises it cannot. Either the number moves or the promise does — and the promise is the valuable half,
because `RenderNode.hidden` exists precisely so a reader can tell a thin region from an unexplored one.
Note that max *influence-only* degree is **55**, so if 8.2 splits the budgets by predicate the influence
side is far cheaper to keep honest than the combined one.

**`subgraph.ts:104` — `MAX_CONTEXT_NODES = 40`.** Justified by "the largest component is 458 nodes and
the median degree is 1, so the neighbourhood of a hub such as The Beatles (degree 25) would swamp a
three-node answer". Largest component is now **1,465 of 1,479 nodes**. 40 remains a legibility number
and probably remains right; the reasoning under it is stale and must be re-derived rather than left.

**`components/mark.ts:9` — the mark's claim.** It draws `blues -> blues rock -> heavy metal music` and
says that is *"the whole connected component in artifact v0.5.0 - step 3 measured it at exactly 3
nodes."* At v0.7.1 there are 7 components and the largest holds 1,465 nodes, so those three are
certainly not a component any more. **The drawing is still real** — verify the two edges still exist and
are still `HAND` — but the sentence justifying it is false and `mark.ts` is the one file in the repo
whose entire premise is "nothing here is invented".

#### 8.4 The coverage panel: the layout risk is LIVE NOW, not introduced by this step

The sketch said the panel's figures are computed so the risk is layout, not staleness. That is right,
and it is more urgent than it reads: **`corpus-facts.json` already carries `artifact_version: 0.7.1`** —
step 6 moved it — and `tests/test_corpus_facts.py` already asserts it against the pinned artifact. So
the panel is **already rendering v0.7.1 numbers today**, unscreenshotted. Only the map's `graph.json` is
still on v0.5.0.

Measured growth, v0.5.0 -> v0.7.1:

| | v0.5.0 | v0.7.1 |
|---|---|---|
| genres | 169 | **675** |
| distinct places | 29 | **65** |
| place bars after `NAMED_PLACES = 8` | 21 marks | **57 marks**, plus a **642-character** comma-joined name string |
| `How densely` histogram bars | **6** | **35** (23 of them counting 5 or fewer) |
| busiest genre connections | 6 | **55** |
| genres with no recorded origin | 85 | **266** |

`HowDensely` renders one `Bar` per distinct connection count with no cap, so that section alone goes
from 6 bars to 35, and two thirds of the new ones are a long tail of near-empty buckets. The places
tail renders both as marks and as `tail.map(([place]) => place).join(", ")` — a single 642-character
run of text.

**This is precisely the failure class `reference-headless-browser-is-available` records**: on work where
139 frontend tests passed, headless Chromium caught a panel 988px tall on a 900px viewport, a grid
silently resolving to two columns, and a tick row reading as another bar. jsdom cannot see any of it,
and `npx vitest` currently logs `HTMLCanvasElement's getContext() is not implemented` four times, which
is the same blindness stated out loud.

**So: screenshot and measure before deciding anything.** Launch
`~/.cache/ms-playwright/chromium_headless_shell-1234/chrome-headless-shell-linux64/chrome-headless-shell`
with `playwright-core` installed **into the scratchpad, never the repo**, at
`deviceScaleFactor: 2`, screenshot the `.cov` element rather than the page, and read
`getBoundingClientRect().height` rather than eyeballing it. A histogram needing a bucketing decision is
a finding to bring back, not a thing to fix silently — the panel's standing rule is **counts, never
percentages**, and any bucketing must not become a rate through the back door.

#### 8.5 Deleting `corpus-facts.json` without breaking first paint

§7 says the file is deleted and its figures move into `Coverage`. **The backend half is already done** —
`graph/coverage.py`'s `Coverage` dataclass now carries `genres_without_recorded_origins`,
`genres_with_one_connection`, `busiest_genre_connections` and `connections` alongside the original
fields, so the split into `coverage` / `density` inside `corpus-facts.json` is already stale against its
own source of truth.

**The constraint that makes the deletion non-trivial, and it is a real one.** `App.tsx:106` records the
decision that the panel reads `corpus-facts.json` *"so it renders at first paint and never waits on the
`done` frame's `corpus.coverage` — DoD 5 keeps the artifact fetch off first paint and this must not
smuggle one in."* Deleting the file and reading the `done` frame instead would violate that on purpose,
which is a regression dressed as a cleanup.

**DECIDED 2026-09-05 by sjtroxel: the file is GENERATED, not deleted.** §7's "deleted" is superseded —
deleting it and reading the `done` frame instead would trade a hand-maintained duplicate for a first-paint
regression, which is a worse repo for a tidier file list. Instead it stops being hand-maintained and
becomes **generated from `graph/coverage.py`**, the same way `stage-graph.mjs` stages `graph.json` and
`mark.test.ts` regenerates `favicon.svg`. One generator, wired into `make check` so a corpus cut fails
the build rather than a demo. That keeps first paint synchronous, removes the hand-maintained duplicate,
and preserves the existing property that `tests/test_corpus_facts.py` asserts it whole against the
pinned artifact. What it does **not** do is reduce the root entry count or the file count — it is the
same file, with nobody typing into it.

~~**The generator is the source of truth for the SHAPE too.** `Coverage` already absorbed the three
density figures, so the generated file should carry `analyse()`'s fields as one object rather than
reproducing `corpus-facts.json`'s stale `coverage` / `density` split.~~

**Corrected 2026-09-05 while building it: the split is NOT stale and must be kept.** `Coverage`
carries 14 fields but `Coverage.as_dict()` deliberately serialises only 10 — the density three plus
`connections` are excluded. `as_dict()` is the **wire contract**: it is what `corpus_summary()` puts
on `/health` and on the `done` frame. So `corpus-facts.json`'s `coverage` block is "what the API
serves" and its `density` block is "what the panel computes beyond that", which is a real boundary
rather than a leftover. Merging them would silently widen the API payload. The generator reproduces
the split; the paragraph above is kept as the record of a wrong assumption caught by reading the
code instead of the field list.

#### 8.6 Contested display — the enabling piece for the two deferred gold cases

`graph/corroboration.py` computes this and **nothing exposes it**: no tool, no API field, no SPA
surface. Verified at v0.7.1:

```
summary: influence_edges 2284, corroborated 82, single_source 2202,
         reciprocal_pairs 6, contested_pairs 2
```

The two, with their sources and verification tiers, since the honest display names both:

| pair | edge | source | verification |
|---|---|---|---|
| western music / New Mexico music | western music `influenced_by` New Mexico music | dbpedia | `INFOBOX_AUTO` |
| | New Mexico music `influenced_by` western music | wikidata | `PROSE_AUTO` |
| electropop / electroclash | electropop `influenced_by` electroclash | wikidata | `PROSE_AUTO` |
| | electroclash `influenced_by` electropop | dbpedia | `INFOBOX_AUTO` |

**Show both directions, name both sources, pick no winner.** And the standing trap applies with full
force here: `verification` and `corroboration` are different guarantees and **must never be collapsed**.
A contested display that shows `PROSE_AUTO` next to `INFOBOX_AUTO` is showing *how hard each single
source was checked*, which is not *whether they agree*. The UI must never show one number where there
are two.

**Where the derivation runs is a decision.** Both edges of every contested pair are present in the
static `graph.json`, so the SPA *can* compute it client-side. It should not. `contested` is a property
of the corpus derived in `graph/`, and duplicating the derivation in TypeScript creates a second
implementation of a definition this project has already corrected once for being loose — the reciprocal
/ contested distinction overcounts by 3x if the source comparison is dropped, and a second copy is a
second chance to drop it. **Carry it from the backend** (`corpus_summary()` is the existing seam) and
let the SPA render what it is given.

**What this unblocks and what it does not.** It unblocks the two deferred gold cases as a *display*.
It does **not** on its own let the agent say "the sources disagree" in prose, because that would need a
tool, and a tool is an `agent/` edit — see 8.10. Do not let the gold cases quietly pull the agent change
in behind them.

#### 8.7 The CC BY-SA attribution

`DATA-LICENSES.md:27` names this step by name: *"the SPA's visible attribution and link back is phase 6
step 8."* Grepping `web/src` for `CC BY-SA`, `creativecommons`, `Wikipedia`, `DBpedia` or `attribution`
returns **nothing** — it is genuinely absent, not merely thin.

The obligations, from `DATA-LICENSES.md` §conclusion, are that per-source licences are stated, every
CC BY-SA row carries a resolvable link back, and **the attribution is displayed in the product rather
than buried**. `.claude/rules/graph-semantics.md` adds: *"not in a buried credits page."* Two sources
now carry it — `dbo:stylisticOrigin` edges under **CC BY-SA 3.0**, and `infobox_year` /
`infobox_countries` under **CC BY-SA 4.0** with `infobox_source` as the link. Both versions get named;
they are different licences.

#### 8.8 The copy audit that belongs to this step

Step 10 owns the full DoD #8 sweep. These are the ones step 8 itself falsifies or touches, so they are
fixed here rather than left for a sweep to find:

- **`StepPanel.tsx:223`** renders `nodes_without_recorded_influences` of `nodes` — **723 of 1,479**, which
  is 48.9%. The surrounding argument ("a missing edge is not evidence of a missing influence") is still
  sound and still load-bearing for requirement 5; the word "most" is not available any more.
- **`CoveragePanel.tsx:16`** says *"43 genres that name neither the US nor the UK"*. Measured now:
  **136**.
- **`api/app.py:140`**, `corpus_summary()`'s docstring: *"28 of 169 genres carry no inception date"*.
  Measured now: **198 of 675**. A backend docstring, but it is copy and DoD #8 does not exempt
  docstrings.
- **`App.tsx:42`**, the masthead tagline — *"Music history is a network, not a timeline"* — stays true
  and stays. The amended thesis wording from step 1 is what has to *appear*, and it has a specific
  shape: the organism is connected **through the people who play across it**, artist-to-genre
  membership, **not** an unbroken chain of genre-to-genre influence. Wording that lets membership read
  as derivation is the same defect as 8.2, in prose.
- **`App.tsx:120`**'s footer sentence — *"across N disconnected components. Relating two things is only
  possible within a component"* — is computed from the `done` frame, so the number self-corrects from
  169 to 7. Re-read the sentence anyway: at 7 components with 1,465 of 1,479 nodes in the largest, the
  clause is still true but no longer says what it was written to say.

**A discrepancy found while measuring, which belongs to step 10 but is recorded here because this is
where it was found.** `CLAUDE.md`, `.claude/rules/grounding-and-claims.md` and `.claude/rules/evals.md`
all state **"2,203 of 2,285 influence edges are single-source"**. The store reports **2,284 influence
edges and 2,202 single-source** at both v0.7.0 and v0.7.1. Commit `c697712` ("honour hand-rejected
edges") rewrote v0.7.0's `graph.json` after those sentences were written and dropped one edge. The
figures to carry forward are **2,284 and 2,202**; corroborated stays **82**. Round down, as always.

#### 8.9 The three recorded SSE fixtures

`contract.test.ts`, `useLineageRun.test.ts` and `map.test.tsx` replay `fixtures/*.sse` — **real bytes
captured from `/lineage` against a local `api/app.py` on artifact v0.5.0**, not hand-written strings.
That is the point of them: they test the parser against the protocol rather than against an idea of it.

After the re-pin they describe a corpus the backend no longer holds. Regenerating is **free and
offline** — `make dev` runs `MYCELIUM_LLM_PROVIDER=local`, the stub, with no AWS — so there is no cost
argument for leaving them stale. Re-record all three, and **re-read the resulting frames rather than
assuming they replay**: a fixture that parses is not a fixture that still exercises the branch it was
captured for, and `kate-bush-refusal.sse` in particular was captured to exercise a refusal that the
widened corpus may no longer produce. If it no longer refuses, that is a finding about the corpus, not a
fixture to force.

#### 8.10 What must not happen in this step

- **No `agent/` edits.** DoD #6, and §7 of this doc already fixes the rule: the only permitted change in
  the whole phase is removing `contested` from `UNREACHABLE`, and that is spent. **`ResolveSource`
  cannot verify a DBpedia URI** (`agent/tools.py:590`) and fixing it needs a reverse lookup
  `GraphStore` does not expose — a `graph/` seam widening *plus* an `agent/` edit. §7 says: if any other
  line in `agent/` needs to change, stop and write down why. **So it is written down and routed out of
  this step.** It is also less severe than the gap list implies: the tool returns `resolvable: false`
  with a stated reason, and **the gate does verify DBpedia citations against `Node.dbpedia_resource`
  before approving a claim**, so this is a reader-facing capability gap, not a hole under the
  citation-resolution gate. It is sjtroxel's call whether it becomes a phase 7 item.
- **No deploy inside this step.** Lifting `FRONTEND_PIN_LAG_UNTIL_STEP_8` removes the *reason* not to
  deploy; step 9 and step 10 are still ahead, and the deploy is step 10's.
- **No new one-way doors, no agent loop edits, no SPA rebuild.** The scope doc's fence: this phase feeds
  the visualization data, it does not redesign it. 8.2 is a correction to a rendering that became wrong,
  not a redesign.
- **No percentages on the coverage panel.** A published percentage was retracted on 2026-08-07 for
  double-counting; counts are what replaced it, and a bucketing decision in 8.4 must not reintroduce a
  rate.

#### 8.11 Done means

1. `chips.json` pins `0.7.1`, `web/public/graph/v0.7.1/graph.json` is staged, and
   `FRONTEND_PIN_LAG_UNTIL_STEP_8` is gone with the plain equality restored.
2. **The map distinguishes influence from membership** in layout, in ink, and in words, and an artist
   and a genre appear in one component without membership reading as derivation.
3. The three measured constants in 8.3 are re-derived against v0.7.1 or their promises are rewritten to
   match what they now do — `NEIGHBOURS_PER_OPEN` explicitly resolved, not left silently truncating.
4. The coverage panel has been **screenshotted and measured in headless Chromium** at v0.7.1, and the
   places tail and the 35-bucket histogram have a recorded decision behind them.
5. `corpus-facts.json` is generated rather than hand-maintained, and first paint still does not wait on
   the `done` frame.
6. Contested is carried from the backend and displayed showing both directions and both sources, with
   `verification` and `corroboration` visibly distinct.
7. CC BY-SA 3.0 and 4.0 attribution and link-back are visible in the product, not in a credits page.
8. The copy in 8.8 is corrected.
9. The three SSE fixtures are re-recorded against v0.7.1 and their branches re-read.
10. The §9.3 projection is **deferred by decision, not by omission**, with 8.1's measured table as the
    recorded reason.
11. `make check` and `npx vitest` both green, with the new counts recorded here rather than in memory.

**The original four-bullet sketch, kept as written on 2026-09-04:** the coverage panel keeps telling the
truth on a corpus roughly 3x larger and the risk is layout, not staleness, so screenshot it in headless
Chromium; the map can finally show artists and genres in one component and it is the single most visible
change in the phase; contested pairs get a display that shows both directions and names both sources
without picking a winner; and the CC BY-SA attribution and link-back per step 4.

### Step 9 — The full suite, and the held-out decision

Tier 1 plus a judged tier 2, as agreed. Roughly $0.40 measured.

**The held-out set is a decision for sjtroxel and this plan does not make it.** `heldout_v1.manifest.json`
carries `artifact_version_pin: "0.5.0"`, as does `gold_v0_1.json`. After step 6 the sealed set describes a
corpus that no longer exists. The relevant facts, stated so the decision is made on them:

- It has been **run once**, 2026-08-24, 10/10. Every report of it carries the run count.
- `.claude/rules/heldout-set.md` forbids re-sealing outright, and forbids re-running after anything was
  tuned in response to what it said.
- Nothing in this phase is tuned in response to a held-out number, so a re-run would not be disqualified
  on that ground.
- But a re-run against a *different corpus* measures something the first run did not, and its 2 refusal
  cases mean one flip moves refusal accuracy 50 points against a measured noise floor of 12.5.

**The plan's default is to not run it**, and to state in the release that held-out generalisation was
measured at v0.5.0 and is untested at v0.7.1. That is honest and it costs nothing. Overriding the default
is his call, made deliberately at the freeze, not incidentally mid-phase.

### Step 10 — Docs, copy audit, release

DoD #8 — *no project copy anywhere claims coverage the graph does not have* — is the one that cannot be
tested and is the one this phase is most likely to fail, because the corpus genuinely improves and every
improvement is one adjective from an overstatement.

The specific sentences that become false in this phase and must be found and rewritten:

- *"every edge has exactly one source, always Wikidata"* — `CLAUDE.md`, `.claude/rules/grounding-and-claims.md`,
  `.claude/rules/evals.md`, `README.md`, `agent/claims.py` docstring, `docs/SPEC.md` §7.
- *"`contested` is arithmetically unreachable"* / *"decision A1, do not re-litigate"* — same files. **A1
  was correct when written and this phase is its stated precondition arriving, not a re-litigation.** Say
  so explicitly in the amendment rather than silently reversing it.
- *"the corpus is 169 disjoint islands and artists and genres never touch"* — `docs/spa-explained.md`,
  phase 5 docs, `MEMORY.md`.
- The four aspirational chips in `SPEC.md` §2.2 blocked on this phase's second source, and the open sixth
  chip slot at `SPEC.md:163`.

---

## 5. Explicitly not in this phase

The scope fence, which does more work than the feature list.

- **P279 is not ingested.** Unchanged from the scope doc, and §3 explains why P136 replaces the role P279
  was proposed for. If a later phase wants P279, it owes the genre-domain boundary predicate that
  `.claude/rules/graph-semantics.md` still holds against it — the one inherited assignment from
  `planning/09` §6 that is still open.
- **No MusicBrainz.** It has no influence relationship in its schema. It can add releases and identifiers
  and not one lineage edge. Adding it would be scope with no bearing on any DoD item here.
- **No agent loop edits.** DoD #6. §4 step 2 shows why none are needed; if one becomes necessary, that is
  the finding and it gets written down rather than made quietly.
- **No new model, provider or prompt changes.** The eval numbers in this phase must move because the
  corpus moved and for no other reason. Changing two things at once is how a suite stops being evidence.
- **No SPA rebuild.** Step 8 feeds the existing surface new data and adds a contested display. The layout,
  palette and motion decided in phase 5 stand.
- **No re-authoring of any frozen dataset.** The gold set, the adversarial set and the held-out set are
  not edited to accommodate a bigger corpus. If a gold case becomes wrong because the corpus grew, that is
  a finding to record, not a case to rewrite.
- **No `dbo:derivative` or `dbo:musicFusionGenre`.** Counted in §2.3 so the numbers exist; both are
  deliberately out of scope. One new source is the scope.
- **No vanity domain.** Phase 7.

---

## 6. One-way doors touched, and how each is satisfied

| # | door | touched? | how it is satisfied |
|---|---|---|---|
| 1 | Claims first, prose second | yes | `plays_genre` never becomes a claim (`ALLOWED_PREDICATES`); `contested` is derived in `graph/`, never proposed by the model |
| 2 | Provenance on every edge from the first row | yes | DBpedia edges carry `source`, `source_id` (resolvable URI), `retrieved_at` from the first row written; `corroboration` is additive |
| 3 | Validated graph semantics | yes | P136 is a membership fact and is ingested as a distinct predicate that cannot be narrated as influence; this is the whole of §3 |
| 4 | Explicit agent-to-data tool contract | no | no tool is added; if density required a loop edit, the seam broke — see DoD #6 |
| 5 | Everything in Terraform | yes, weakly | step 0 hardens the Makefile; no new AWS resource |
| 6 | Package boundaries | yes | `ingest/membership.py` and `ingest/dbpedia.py` are new modules in `ingest/`; nothing crosses into `agent/` |
| 7 | LLM provider seam | no | untouched |
| 8 | Lambda container image | no | untouched, though the artifact grows — see §9 |
| 9 | Response streaming | no | untouched |

---

## 7. Files by path

**New:**

```
src/musical_mycelium/ingest/membership.py     P136 artist -> genre, bounded to corpus QIDs
src/musical_mycelium/ingest/dbpedia.py        stylisticOrigin, aligned through owl:sameAs
tests/test_membership.py
tests/test_dbpedia.py
tests/test_contested.py                       the pair-level derivation, and its guards
docs/DATA-LICENSES.md                         CC0 / CC BY-SA per source
src/musical_mycelium/artifacts/v0.6.0/        P136 cut
src/musical_mycelium/artifacts/v0.7.0/        DBpedia cut
src/musical_mycelium/artifacts/v0.7.1/        geography and time on the widened corpus
```

**Changed:**

```
.claude/settings.json                 DONE 2026-09-02 (step 0, first half)
Makefile                              tf-* targets demand image_tag / llm_provider / reserved_concurrency
src/musical_mycelium/graph/schema.py  PREDICATE_PLAYS_GENRE, SOURCE_DBPEDIA, two verification tiers,
                                      Edge.corroboration
src/musical_mycelium/graph/coverage.py   absorbs the three density figures; source and predicate mixes
src/musical_mycelium/graph/structure.py  component counts across two predicates
src/musical_mycelium/graph/memory.py     PINNED_ARTIFACT_VERSION
src/musical_mycelium/ingest/wikidata.py  ARTIFACT_VERSION; a POST path for large VALUES clauses
src/musical_mycelium/agent/claims.py     UNREACHABLE only — contested stops being unreachable
src/musical_mycelium/eval/slices.py      source and predicate dimensions
web/src/chips.json                       artifact_version 0.5.0 -> 0.7.1 (the only frontend pin)
web/src/corpus-facts.json                GENERATED from graph/coverage.py (supersedes "deleted")
web/src/graph/subgraph.ts                RenderEdge gains `predicate`; NEIGHBOURS_PER_OPEN re-derived
web/src/graph/layout.ts                  layers on influence edges only
web/src/graph/GraphView.tsx              membership drawn distinctly, and without an arrowhead
web/src/components/mark.ts               the "whole component" claim, false at v0.7.1
web/src/components/CoveragePanel.tsx     places tail and the 35-bucket histogram; the 43 -> 136 figure
web/src/components/StepPanel.tsx         the "most of the corpus" figure, now 723 of 1,479
web/src/components/NodeInspector.tsx     membership stated in words beside the influence direction
web/src/fixtures/*.sse                   re-recorded against v0.7.1 (free, MYCELIUM_LLM_PROVIDER=local)
web/src/  (attribution, contested display)
tests/test_chips.py                      FRONTEND_PIN_LAG_UNTIL_STEP_8 deleted, equality restored
src/musical_mycelium/api/app.py          corpus_summary() carries contested; its docstring figures
docs/  (ROADMAP, KNOWN-GAPS, SPEC, graph-semantics, spa-explained, phase-6 scope)
CLAUDE.md, README.md, .claude/rules/*.md   the A1 amendment
```

`agent/claims.py` appears in the changed list and DoD #6 says the agent package was not edited. **That is a
real tension and it is resolved by scope, not by argument:** the only permitted change is removing
`contested` from the `UNREACHABLE` dictionary, which is a declaration of what the corpus can express, not
logic. No gate rule, no loop, no tool, no prompt. If any other line in `agent/` needs to change, stop and
write down why — that is the seam breaking and it is a phase finding.

**It was needed once, and it is written down here rather than done.** `ResolveSource` cannot verify a
DBpedia resource URI (`agent/tools.py:590`): a resource names an article rather than a QID, so unlike a
Wikidata statement URI it cannot be parsed for its entity, and resolving one needs a reverse lookup
`GraphStore` does not expose. Fixing it is a `graph/` seam widening **plus** an `agent/` edit, so under
the rule above it stops here. **It is milder than it sounds and that is why deferring it is safe:** the
tool already returns `resolvable: false` with a stated reason rather than resolving on faith, and the
gate does verify DBpedia citations against `Node.dbpedia_resource` before approving a claim. The gap is
a reader's ability to re-check, not a hole under the citation-resolution gate. Phase 7 or later, at
sjtroxel's call.

---

## 8. Testing and evals

- **Every new number is asserted against the pinned artifact**, following `tests/test_chips.py` and
  `tests/test_corpus_facts.py`, which is the pattern phase 5 established for exactly this.
- **The metrics get broken on purpose before they are trusted.** `.claude/rules/evals.md` requires the
  vacuous-truth guard; the new one this phase needs is a **vacuous-corroboration guard**: an edge whose
  "second source" is the same source under a different URI must not count as corroborated, and a corpus
  where every edge is corroborated by construction must not score as though disagreement were possible.
- **The contested derivation is unit-tested on synthetic pairs where the answer is known by
  construction**, including the direction-inversion case, because `MEMORY.md` records three separate
  origins-direction bugs that all passed silently.
- **Gates:** the free every-commit run gates three of five. That is unchanged and no number in this phase
  changes it. `eval/thresholds.py` is the authority; do not write "blocks on five" anywhere.
- **Thresholds are not re-tuned to accommodate the new corpus.** If a gate fails after a cut, the corpus
  change caused it and that is information. Moving the bound to make it pass is how a suite stops
  measuring. The noise floor in `eval/noise_floor.json` was measured at v0.5.0 and **is not valid for a
  different corpus** — re-measuring it is a step 9 decision, and until it is re-measured, movement inside
  the old floor cannot be called noise.

---

## 9. Named uncertainties

Stated as uncertain rather than smoothed over, per the skill.

1. **Whether CC BY-SA data in a committed artifact creates a share-alike obligation on an MIT repo.** Real
   question, outside my competence. The plan attributes, links back, and states per-source licences, which
   is conservative and defensible either way. Worth a real answer before v1.0.
2. **Whether 672 of 804 artists is explained by P737 objects sitting outside the P136 bound.** Plausible,
   unverified, and it must be verified before the number is published.
3. ~~**The artifact size against invariant 8.**~~ **MEASURED 2026-09-04 — this is no longer an
   uncertainty, and the estimate was right.** v0.5.0's `graph.json` is 640KB; **v0.6.0 is already
   1.7MB**, and v0.7.0 at closure projects to **~2.0MB** (1,537 nodes at 250 B, 5,607 edges at 313 B,
   both rates measured off v0.6.0 rather than assumed). The original guess of 2-3MB was accurate.
   - **Invariant 8 is not threatened and was never the real question.** 2MB against a 250MB image limit
     is noise. In-memory is fine.
   - **The browser is the real question, and the answer is that the SPA currently ships the artifact
     byte-for-byte.** Verified, not assumed: `web/public/graph/v0.5.0/graph.json` has the *identical*
     key and field set as the artifact — `retrieved_at`, `revision_id`, `source_id` and all. There is no
     projection step today. At v0.7.0 that is a ~2MB client-side download.
   - **Where the bytes are, measured:** edges are 1,140KB of v0.6.0's 1,768KB, and provenance dominates
     them — `source_id` alone is **372KB (32% of the edge payload)** and `retrieved_at` another 164KB.
     Close to half the edge bytes are fields the *map* never draws.
   - **Decision: the SPA gets a projection, and the decision is recorded now while the build stays in
     step 8.** The map needs ids, labels, kinds, predicates and endpoints to draw and to be clickable;
     it does not need every source URI and timestamp on first paint, because those are needed only for
     the one edge a visitor actually inspects. Dropping `source_id` and `retrieved_at` from the map
     payload alone cuts roughly 45% of the edge bytes.
   - **What step 4 owes this decision is only to not foreclose it, and it does not.** The artifact
     writer already emits a flat shape a projection can be derived from mechanically, so no step 4 code
     changes on account of this. **Deciding it now costs nothing and rules out discovering it at the
     layout stage**, which is what this entry was flagged early to prevent.
   - **Not yet decided and deliberately left open:** whether the projection is a second generated file
     or the map fetches a neighbourhood on demand. That is a genuine step 8 design question, it does not
     block step 4, and picking it now would be guessing at frontend needs a month early.
   - **Re-measured 2026-09-05, at step 8, and the reasoning above needs one correction: it argued from
     RAW megabytes and the wire cost is gzipped.** v0.7.1 full is 2,694,624 raw but **187,294 gzipped**;
     projected it is 650,503 / **52,411**. So the projection saves 72% of the transfer and lands the
     browser cost at roughly what full v0.5.0 costs today — a real saving, and a smaller problem than
     "~2MB client-side download" implied. **The decision and its recommendation are in step 8.1**, along
     with a third option §9.3 could not have known about: provenance already travels on the claim
     stream, so the projection need not lose the citation at all.
4. **Whether DBpedia's 5,124 edges survive screening at anything like the Wikidata rate.** The Wikidata
   genre axis went 351 candidates to 133 edges — a 62% drop through the prose check. `stylisticOrigin` is
   an infobox field rather than a prose mention so the failure modes differ, and the retained fraction is
   genuinely unknown. **If it screens down to a few hundred, the headline "15.5x" is wrong** and the phase
   is smaller than this plan assumes. Step 4 measures it before any copy quotes a number.
5. **Whether the two contested pairs are two, or the visible two.** **Sharpened 2026-09-04 and still
   open, but the odds moved.** The widened corpus was the obvious place for more reversals to appear and
   they did not: **1,180** DBpedia edges now land inside the corpus, up from 317, and the reversal count
   is **still exactly 2**. That is a 3.7x larger comparison surface returning the same two pairs.
   - It is genuine evidence that 2 is close to the real number rather than a sampling floor, and it is
     **not** evidence that the machinery is unnecessary — a reversal is detectable at all only because
     both sources are present, which is the entire point of the second source.
   - The reason the rate cannot rise the way the edge count did: a reversal requires the corpus to
     *already hold* the edge, so the denominator is the corpus's 133 genre edges, not DBpedia's 1,180.
     The comparison surface that matters never grew. Quote 2 as a floor still, but the floor is now
     measured against a much wider net.
6. **Whether a bigger corpus makes refusal accuracy better or worse.** More edges means fewer true
   refusals available, and the adversarial set's false-premise cases were authored against a 169-genre
   corpus. Some of them may stop being false premises. That is a finding to record, not a reason to edit
   the set.

---

## 10. Cost

| item | cost |
|---|---|
| SPARQL and DBpedia queries | $0, read-only public endpoints |
| Ingestion crawls | $0 — the assertion filter is regex, not a model call (`ingest/assertion.py`) |
| Two intermediate tier 1 re-runs | ~$0.36 each, measured |
| Step 9 tier 1 + judged tier 2 | ~$0.40, measured |
| Deploys | ~$0.02 each |
| **Phase total** | **under $2** |

Quote the measured numbers, never the ~$5-25/run planning estimate. Fixed infrastructure is unchanged: no
new AWS resource, no always-on anything. **The one real cost is time** — the crawls run at the mandated 1
request/second and the DBpedia pass is the largest ingestion this project has done.

**The guardrail:** `make eval-live`, `make tf-apply`, `make tf-destroy` and `make heldout-seal` are all in
the `deny` list as of step 0. Any new target added in this phase that spends money, mutates infrastructure
or touches the sealed set gets its own deny line **on the day it is written**, per the generalisation
recorded in `KNOWN-GAPS.md`: a deny pattern naming a command does not cover a wrapper that runs it.

---

## 11. Reproducing the measurements

The three measurement scripts were written to the session scratchpad rather than the repo, deliberately —
they are one-shot planning instruments, not project code, and `CLAUDE.md` caps the root at 18 entries for
this kind of reason. What matters is reproducible from this doc:

- **P136:** `SELECT ?a ?g WHERE { VALUES ?a { <804 artist QIDs> } ?a wdt:P136 ?g }` against WDQS, **by
  POST**, chunked at 200 QIDs, then filtered locally to the 169 corpus genres.
- **DBpedia population:** `SELECT (COUNT(*) AS ?n) WHERE { SELECT DISTINCT ?a ?b WHERE { ?a dbo:stylisticOrigin ?b . ?a a dbo:MusicGenre . ?b a dbo:MusicGenre } }`
  against `https://dbpedia.org/sparql`. **The nested `DISTINCT` is required** — see §2.3.
- **The overlap:** map the 169 corpus QIDs to DBpedia resources through `owl:sameAs`, pull their
  `stylisticOrigin`, map back, and compare against the artifact's genre-genre edges as sets. Corroboration
  is set intersection; contested is intersection with the reversed set.

Both endpoints were flaky on the day — WDQS returned 502 and 429 across the chunked run and DBpedia was
slow. Retry with exponential backoff and expect to. `.claude/rules/graph-semantics.md` records WDQS as
materially degraded in 2026, which is also why the agent never queries it live.

---

## 12. Definition of done — how each item is met

| # | scope doc DoD | met by |
|---|---|---|
| 1 | Connectivity answered with reasoning, product claim matches | §3, landed in step 1, audited in step 10 |
| 2 | Coverage and density displayed in numbers, no footnote needed | met at phase 5 step 9; step 8 keeps it honest at 3x corpus |
| 3 | Component structure queryable | met at phase 2 step 4; step 2 extends it across two predicates |
| 4 | Traversals name specific people, places, dates | steps 2, 4 and 6 — people via P136, places and dates via the re-read |
| 5 | Every metric sliced by era, region, density, query type | step 7, plus two new dimensions the slicer has never seen |
| 6 | The agent package was not edited | step 2 §"why this needs zero edits"; the one permitted change is `UNREACHABLE` |
| 7 | Schema changes additive | `Edge.corroboration` defaults to `None`; no field removed or repurposed |
| 8 | No copy claims coverage the graph does not have | step 10, and it is the item most likely to be failed |

---

## 13. Plain-English explanation, written as we go

Per the skill, and because it is the cold-articulation rep that is much harder to reconstruct later. The
version as of the plan:

> The app traces where music styles came from, and it only says things it can point to a source for. Until
> now it had exactly one source — Wikidata — which meant it could tell you *how carefully* a fact had been
> checked but never whether anyone disagreed with it, because there was nobody else in the room. This phase
> brings in a second source and finds that on the styles both of them know about, they mostly agree, they
> each know things the other doesn't, and in two cases they flatly contradict each other about which style
> came first. The app now shows all three of those situations differently instead of pretending they're the
> same. It also, for the first time, connects the musicians to the styles they play, which is what makes the
> whole thing look like one connected web rather than a few hundred unrelated fragments — and that turns out
> to be the honest picture, because what actually connects musical genres is the people who move between them.

Rewrite this at each step close rather than at the end.
