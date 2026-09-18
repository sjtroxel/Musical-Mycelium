# Phase 8 — Membership Tour (v1.1) — IMPLEMENTATION

> **As-built plan.** Written 2026-09-18, immediately before the phase is built, which is the rule: this doc
> exists to absorb what phases 6 through 7.7 actually taught rather than what phase 8's scope doc guessed
> on 2026-09-09. Scope is `docs/phases/phase-8-membership-tour.md` and it still governs; where this doc
> diverges from it, §1 says so explicitly and proposes the amendment rather than quietly winning.
>
> **Status: AWAITING APPROVAL. No code written.**

## 0. The one-sentence version

**Let a route cross from a genre to the musicians who played it and back out into another genre, gated and
cited like any other claim, with membership structurally unable to read as derivation** — and, before
paying for the one live re-baseline this phase owes, batch into it every other change that has been
waiting for one.

## 1. What the scope doc got right, what moved, and the amendments owed

The scope doc was written at artifact v0.7.1, before phases 7.6 and 7.7 existed. Every number in its §0
was re-measured today against v0.10.0 (`Artifact.load`, undirected components, script kept in the session
scratchpad and reproduced in §11). The result is unusual and worth reading before the table: **the part of
the premise that matters did not move at all.**

| measured over | v0.7.1 | v0.10.0 | verdict |
|---|---|---|---|
| `influenced_by` edges | 2,284 | **2,309** | +25, +1.1% |
| `plays_genre` edges | 2,782 | **4,498** | scope doc's "2,782" is **stale** |
| `studied_with` edges | — | **2,469** | did not exist |
| influence-only components (all nodes) | 138, largest 534 | **138, largest 534** | **unchanged — scope doc still correct** |
| influence-only, genre-to-genre only | 10, largest 534 | **10, largest 534** | **unchanged** |
| influence + membership | 7, largest 1,465 | **13, largest 2,639** | scope doc's "7" is **stale and forbidden** |
| all three predicates | — | 61, largest 3,490 | matches the manifest |
| genres | 675 | **739** | +64 |
| genres with **no** genre-to-genre influence edge | 120 (17.8%) | **184 (24.9%)** | **got worse** |
| genres with no influence **and** no membership edge | — | **0** | the thesis, measured |

**Amendment 1 — §0's table.** The `plays_genre` count becomes 4,498 and the both-predicates row becomes
13 / 2,639. The "7" must go: `CLAUDE.md` forbids writing it, and this doc's whole §1 is an example of why
that instruction exists.

**Amendment 2 — §0's framing, which is the substantive one.** The scope doc presents "138 components"
as evidence that the influence corpus is fragmented. The re-measurement says something more precise: the
138 is **10 genre islands plus 128 artist islands**, and the genre influence graph is 534 of the 555
genres it touches in one component — **96% connected**. The problem was never that genres with influence
edges are scattered. It is that **184 of 739 genres have no influence edge at all**, and every one of them
is nevertheless attached to the corpus, by membership, which is precisely the claim this phase performs.
The phase's premise is stronger after re-measurement than before it, and stated more accurately.

**Amendment 3 — §6's one-way door is named too narrowly.** §6 names `ALLOWED_PREDICATES`. That lock is
already open — phase 7.6 opened it for `studied_with`, and the scope doc's own 2026-09-11 amendment says
so. **The lock this phase actually has to open is a different one and the scope doc does not mention it:**
`agent/claims.py:gate` rule 3 rejects any proposal whose endpoints differ in `kind`, with
`RejectionReason.CROSS_AXIS`. A `plays_genre` claim is artist-to-genre by construction, so **the gate
rejects every membership claim today, before it ever reaches the edge lookup.** §6 is amended to name the
axis rule as the phase's real one-way door. See §5.

**Amendment 4 — the founding example is intact, and now has a measured route.** `delta blues -> Detroit
techno` still has **no path on influence alone** at v0.10.0: not delta-to-Detroit, not Detroit-to-delta,
not undirected. Adding membership produces an undirected five-hop route:

```
Delta blues -> Chicago blues -> Freddie King -> funk -> electro -> Detroit techno
```

Two things about that route decide most of this phase, and §4 is built around them:

- **It is undirected.** Directed traversal still fails in both directions with membership included. A
  membership hop is not time-ordered, and the scope doc's 2026-09-11 amendment flagged exactly this
  ("teaching and influence both run forward in time, and membership does not").
- **Read as prose it is false.** Nothing about that chain means Chicago blues derived into funk via
  Freddie King. It is the scope doc's §7 risk, printed, on the phase's own canonical demo.

**Amendment 5 — the re-baseline price in §0 reason 3 is wrong and too low.** See §3.

## 2. Definition of done

The scope doc's seven DoD items stand unchanged. Restated here with the evidence each will be judged on,
because phase 7 proved that a DoD item with a test can pass while the item is broken:

1. **Typed cross-axis route.** A cross-axis query returns a route whose every hop carries its predicate in
   the payload, not inferred from the node kinds at its ends. *Evidence: the SSE payload of a real run,
   read, not a unit test of the serializer.*
2. **The delta blues route is answerable and names membership as membership.** *Evidence: the live answer
   text, quoted in full in the as-built section.*
3. **A test asserts no prose path exists by which a `plays_genre` hop can be narrated as influence** — in
   the shape of `ContestedDisclosure`, not a review checklist.
4. **`verification` and `corroboration` stay two fields**, and a `MEMBERSHIP_*` tier never appears where an
   influence tier is expected. *Already load-bearing in `schema.py:TIERS_BY_PREDICATE`; this phase must not
   weaken it.*
5. **The live suite reports its gates rather than a `NOT GATED` banner.** If restoring bounds is required,
   that is an explicit spend decision at a freeze, taken by sjtroxel. §3 is that decision, brought forward.
6. **`agent/loop.py` is unmodified**, or the edit is a finding recorded in bold here.
7. **`make check` green, repo root inside its cap.**

## 3. The re-baseline, its real price, and why batching is the whole point

This section exists because he asked the right question: *spending for another five-run baseline would
feel more justified if we did more than adjust `adv_018`.* That instinct is correct, and the numbers say
so more strongly than the scope doc did.

### 3.1 The price, measured rather than estimated

The scope doc says $2.61 and ~2.4 hours. **That was measured when the live set was 56 cases.** Measured
from the nine 63-case live runs in `eval/results/` since 2026-09-12:

| | measured |
|---|---|
| one 63-case live run | **$0.72 – $0.76**, mean ~$0.74, 597k – 641k tokens |
| five identical runs | **~$3.70** |
| what the 2026-09-12 baseline session actually cost | **$4.63**, including one 17-case abort and one 62-case partial |
| wall clock, steady state | **~32 min/run, ~2.7 h for five** — RPM-bound at 10 RPM, exactly as `aws-and-cost.md` predicts |

With phase 8's new cases the per-run figure rises roughly in proportion. **Budget $5 and expect ~$4**, and
quote the measured figures, never the scope doc's $2.61.

Against the credit balance checked today — $140.85 estimated remaining, $80.85 of it on the only credit
actually drawing down — a $5 baseline is **3.5%** of the usable pool. This is affordable. It is not free,
and the reason to batch is not the money.

### 3.2 The reason to batch is the measurement, not the money

A re-baseline is not a payment, it is a **reset of what every gate means**. Each one discards the previous
noise floor and the bounds derived from it. So the real cost of doing it twice is not $7.40 — it is that
the first baseline's numbers are dead the moment the second is taken, and any decision made from them was
made from a measurement that no longer exists.

**Three things are already queued behind one baseline, before phase 8 adds a fourth:**

1. **`adv_018`** was re-authored 2026-09-17 (West African -> South African, `juju` -> `mbube`) and is
   **still excluded from `refusal_accuracy`** because the bound was measured on the old case. It is
   unexcluded only by a fresh baseline.
2. **The name-substitution finding of 2026-09-14** — the model calls `resolve_node` on a longer name it
   invented itself (`"metal"` -> `"heavy metal"`), now seen in 5 of 10 runs at v0.10.0. `KNOWN-GAPS.md`
   records it as **owed as a decision, not built**. Whatever is decided, if anything lands in code it moves
   refusal behaviour and needs a baseline.
3. **Phase 8's own new eval cases**, which hit `thresholds.py:_ungateable`'s superset branch and un-gate
   the entire live suite until re-measured.
4. **Anything §4 step 0 finds in the corpus**, if it is acted on.

Doing these as one baseline instead of four saves roughly $11 and about eight hours, and it is the
difference between one honest set of bounds and four sets of which only the last is true.

**So: this phase takes exactly one live re-baseline, at its close, covering all of the above.** That is
DoD 5's "explicit spend decision at a freeze," made here, in advance, in writing.

### 3.3 The cost of batching that is NOT money, and it is the one to think about

**If step 0's corpus work is acted on, the artifact becomes v0.11.0, and `heldout_v2` goes stale.** It is
pinned at 0.10.0. `make heldout-check` would report `artifact-pin-moved`, which is exactly what happened to
`heldout_v1` at v0.10.0 and exactly why it was retired.

That set was drawn, sealed and run **six days ago**, run count 1, 10 of 10. A corpus change spends that.
Re-drawing is his work, from his seed, and generalization returns to **untested, not passed**, until it is
drawn and run again at the next freeze.

**This is the real decision in this phase and it is his, not mine.** It is why step 0 measures for free and
stops, rather than measuring and proceeding.

> **DECIDED 2026-09-18, by him, before step 0 ran and before any yield number existed:** he accepts the
> cost of drawing a **third** held-out set if the corpus moves. Recorded here with the timing it was given,
> because a decision taken before the number arrives is worth more than the same decision taken after, and
> because this one removes the phase's main blocker rather than being extracted by a result.
>
> **What it does not do is make the corpus change automatic.** §4 step 0's decision rule still stands on its
> own merits: bumping the artifact for a handful of edges spends a held-out set to buy very little, and that
> is a bad trade whether or not he is willing to pay it. The rule is the guard against acting for the sake
> of having decided to act.

## 4. The steps

### Step 0 — Measure what the corpus could gain, spend nothing, and stop — **FREE, no artifact change**

*This step is his request, and it is deliberately a measurement with a hard stop at the end. Nothing in it
writes an edge, bumps an artifact version, or touches the held-out set.*

The diagnosis from §1: the influence layer has been **flat while the corpus doubled**. Influence edges went
+1.1% across three phases while nodes went +145%. The product narrates influence. So the question "what
would make the corpus stronger" has a sharp answer — *give the 184 orphan genres their first influence
edge* — and one obvious, already-built instrument.

**0.1 — The DBpedia re-run, measured not performed.** `ingest/dbpedia.py` fetches the whole
`dbo:stylisticOrigin` genre graph and aligns it into Wikidata's identifier space. It produced **1,335 of
the 1,468 genre-to-genre influence edges in the corpus — 91% of them** — at tier `INFOBOX_AUTO`. It was
seeded from the **v0.7.0** corpus and **has never seen the 64 genres phase 7.6 added**. Step 0 runs the
alignment and the origin-graph fetch against the v0.10.0 genre set and reports, without writing an
artifact:

- how many of the 184 orphan genres have a DBpedia resource at all;
- how many of those carry `stylisticOrigin`;
- how many of those origins align to a QID **already in the corpus** (an edge gained) versus outside it (a
  node that would also have to be admitted, which is scope creep and is refused here);
- the same three numbers for the 64 genres phase 7.6 added specifically.

**0.2 — The Wikidata P737 gap, same treatment.** Wikidata contributed only 133 genre-to-genre influence
edges against DBpedia's 1,335, so expectations are low, but it is the same query shape and costs nothing
to count alongside.

**0.3 — Report and STOP.** Step 0 ends with a table and no commit to act. The decision it feeds is his,
and §3.3 is the part of it that is easy to miss, so the report restates it: **acting on any of this means
v0.11.0, which means re-drawing the held-out set he sealed six days ago and returning generalization to
untested.**

**Recommended decision rule, offered now so the number is judged against something fixed rather than
rationalized after it arrives:** act if the re-run gains **200 or more genre-to-genre influence edges
against existing corpus nodes**, or cuts the 184 orphans **below 120** (its v0.7.1 level). Act on a smaller
yield only if he wants it for its own sake. Below that, the held-out set is worth more than the edges.

**Explicitly NOT measured in step 0, each for a stated reason:**

- **The 964 teaching endpoints with no P136 genre.** Real — they are most of the 54 teaching-only islands —
  but connecting them needs a genre Wikidata does not have, so it needs a new source and a new shape. It is
  a phase, not a step, and the manifest's "shown as a gap and never inferred" is the right posture until
  then.
- **Non-Western expansion.** The skew is real (US 53.3%, 144 of 739 genres outside the US/UK) and it is by
  construction and documented. Widening it means new discovery seeds, which is §5's excluded "new corpus."
  Worth its own phase; not worth bundling blind into this one. Note the live suite's `elsewhere` slice
  already runs 10 cases at 10/10 — it is the **held-out** set that has no `elsewhere` case, and that is a
  drawing property, not a corpus one.

#### Step 0 — CORRECTED, 2026-09-18, before anything was built. **The yield is ~10 edges, not 453.**

> **Read this before the section below it. The as-built that follows overstated the yield by about 45x,
> and its recommendation was acted on for roughly twenty minutes before the error surfaced.** Nothing was
> built, no artifact was cut, and the corpus is untouched at v0.10.0.

**The error.** `dbpedia.build()` takes two exclusion inputs: `known_edges`, so a candidate that is already
an edge is skipped, and **`rejected`, so a candidate the Wikipedia prose check already refused is not
re-admitted.** The step 0 measurement applied the first and not the second. Every DBpedia candidate must
clear the same prose check Wikidata edges clear — *"only `PROSE` survives"* — and the refusals from that
check are recorded in `artifacts/v0.7.0/exclusions.json`, in the artifact directory the measurement was
already reading.

| | |
|---|---|
| candidates the first measurement reported | 453 |
| **already refused by the prose check at v0.7.0** | **440** (381 `INFOBOX_ONLY`, 55 `ORPHAN`, 4 `MISLINKED`) |
| **genuinely unscreened** | **13** |
| expected to survive at the measured 74% pass rate | **about 10** |

The tell was visible in the original sample and was read past: its first two rows, `2-step garage <-
breakbeat` and `acid house <- Chicago house`, are the **first two rows of the exclusions file.**

**The strongest argument for acting was the weakest part of it.** `gold_v0_1_026` / *electronic music*
appeared to gain its first two origins. Both candidates — `futurism` and `modernism` — are on the refused
list. **Electronic music gains nothing**, and the hypothesis that this attacks the 2026-09-14 descendants
failure at its cause is withdrawn.

**All 13 survivors, in full**, since at this size a sample is the whole thing:

| subject | candidate origins |
|---|---|
| chamber pop | classical music, indie pop, indie rock, lounge music, rock music |
| tango | Contradanza, flamenco, mazurka, polka |
| salsa / norteño / grupera | bolero |
| extreme metal | heavy metal music |

**The decision rule now fails both criteria**, having appeared to pass one decisively:

- *"200 or more edges"* — **about 10. FAILS.**
- *"orphans below 120"* — 184 would drop by 1 or 2, not to 166. **FAILS.**

**Revised verdict: DO NOT ACT.** ~10 edges do not buy a v0.11.0 cut, a third held-out set, a re-draw that
returns generalization to untested, or any gold-set re-checking. **Phase 8 proceeds on artifact v0.10.0**,
`heldout_v2` keeps its run count of 1, and the membership work needs none of this.

**What is worth keeping from it.** The 13 are not junk — `tango <- Contradanza / flamenco / mazurka /
polka` is real pre-1900-adjacent lineage on a non-Western-adjacent genre, which is where this corpus is
thinnest. They are simply not worth an artifact version **on their own**. They belong in the next cut that
happens for another reason, and `docs/KNOWN-GAPS.md` carries them so they are not re-derived from scratch.

**The generalizable lesson, which is why this correction is kept rather than edited away:** a measurement
that reuses a pipeline's data must reuse **all** of that pipeline's filters. One of the two was applied,
the number came out 45x too high, and it was reported with a recommendation attached. The exclusions file
was sitting in the directory being read.

#### Step 0 — first as-built, 2026-09-18, SUPERSEDED BY THE CORRECTION ABOVE. Kept for the method, not the numbers.

Ran `dbpedia.align` over all 739 v0.10.0 genres, `fetch_origin_graph`, and `to_origins` against the current
corpus. **No artifact was built and no edge was written.** Raw counts:

| | |
|---|---|
| corpus genres with a DBpedia resource | **657 of 739** |
| **orphan** genres with a DBpedia resource | **116 of 184** |
| resource-space `stylisticOrigin` pairs DBpedia holds | 5,124 |
| aligned into QID space against this corpus | 1,870 |
| unresolved (one or both endpoints outside the corpus) | 3,253 |
| **already an edge** | 1,417 |
| **NEW edges, both endpoints already corpus nodes** | **453** |

**453 new genre-to-genre influence edges, requiring no new nodes** — a **+31%** increase on the 1,468 the
corpus holds, and the first material growth in the influence layer since v0.7.0. Spread across 226 subject
genres, median gain 2.

**The decision rule, scored honestly: one criterion passes decisively, the other fails decisively.**

- *"200 or more edges against existing nodes"* — **453. PASSES.**
- *"cuts the 184 orphans below 120"* — **184 -> 166. FAILS**, and not narrowly.

The rule was written as an OR and was approved as an OR, so it is met. But the split is the finding and it
must not be smoothed: **the re-run makes the well-connected part of the corpus denser; it does not connect
the sparse part.** Only 18 of 184 orphans gain a first edge, although 116 of them have a DBpedia resource —
so 98 orphan genres have a resource and still no usable origin. The gain lands where influence edges
already are.

**It does not fix the classical gap, and that is worth stating plainly because it is where the phase's
sympathies were.** All 64 genres phase 7.6 added are orphans, and **only 4 of them are rescued**. DBpedia's
`stylisticOrigin` is a popular-music infobox convention; classical genre articles do not use it. Nothing in
this step brings Mozart's half of the corpus into the influence layer, and nothing here should be described
as if it did.

**The cost this step found that §3.3 did not anticipate: 12 of 43 gold cases have subjects that gain
origins**, so their `expected_claims` become incomplete and the system would correctly name origins the
gold set does not list — which scores as a precision drop rather than as the improvement it is.

| case | shape | subject | origins before -> after |
|---|---|---|---|
| `gold_v0_1_022` | descendants | shoegaze | 9 -> 12 |
| `gold_v0_1_010` | origins | techno | 9 -> 11 |
| `gold_v0_1_013` | origins | bossa nova | 2 -> 4 |
| `gold_v0_1_014` | origins | Manila sound | 5 -> 7 |
| `gold_v0_1_017` | path | Shibuya-kei | 13 -> 15 |
| **`gold_v0_1_026`** | origins | **electronic music** | **0 -> 2** |
| `gold_v0_1_031` | origins | western music | 4 -> 6 |
| `gold_v0_1_002` / `030` / `032` / `033` / `034` | origins | acid jazz, electropop, G-funk, bebop, soca music | +1 each |

The adversarial set is unaffected — its queries are sentences, not labels, and none resolves to a gaining
subject. `gold_v0_1_020`, the permanently excluded traversal case, does not appear.

**`gold_v0_1_026` is the single most interesting row here.** *"Where did electronic music come from"* has
**zero** origin edges today, which is very likely *why* it answered with 24 descendants in the 2026-09-14
gated run and produced the `adv_006` direction swap recorded in `KNOWN-GAPS.md`. Giving it two real origins
attacks that failure at its cause rather than at the prompt. **That is a hypothesis with a clear mechanism,
not a measured fix**, and it is only testable at step 6.

**Declined deliberately, and quantified so the decision is visible:** the 3,253 unresolved pairs are origins
whose endpoints are genres this corpus does not hold. Admitting them would grow the corpus substantially and
is exactly the "new corpus" §9 excludes. Not taken, and recorded so nobody re-derives it as an opportunity.

**Verdict: the rule is met and the honest summary is narrow.** 453 real edges, a measurable shot at a known
failure, no new nodes, no new source, no new extractor — against a held-out re-draw, 12 gold cases to
re-check by hand, and no help at all for the classical layer. **His call.**

### Step 1 — Open the axis lock, predicate-scoped — **the one-way door**

`gate()` rule 3 rejects `subject.kind != obj.kind`. Phase 8 cannot simply delete it: that comment is right
that a chain stepping genre -> artist -> genre "reads as one continuous line of influence, and it is not
one."

**The shape: the axis rule becomes a per-predicate constructor rule, mirroring
`schema.py:TIERS_BY_PREDICATE`, which already proves the pattern in this codebase.**

| predicate | permitted endpoints | direction |
|---|---|---|
| `influenced_by` | genre→genre or artist→artist | same-kind, as today |
| `studied_with` | artist→artist only | student→teacher, as today |
| `plays_genre` | **artist→genre only** | never genre→artist |

This is *stricter* than today for two of the three: today's rule permits `studied_with` between two genres
and `influenced_by` artist-to-genre is merely absent from the artifact rather than forbidden by the gate.
Making the table explicit closes both. **The property to preserve is not the line, it is that no
non-influence edge can reach prose as an influence claim**, and a table that names each predicate's legal
shape holds it better than a kind-equality test does.

Tests: every predicate's legal shape accepted; every illegal shape rejected with `CROSS_AXIS`; specifically
that `plays_genre` genre→artist is rejected even though the artifact contains the same pair the other way.

#### Step 1 — AS BUILT, 2026-09-18. Done on artifact v0.10.0, which did not move.

`agent/claims.py` gained `AXES_BY_PREDICATE`, a table of legal `(subject_kind, object_kind)` pairs, and
`gate()` rule 3 now reads it instead of testing `subject.kind != obj.kind`.

| predicate | legal shapes |
|---|---|
| `influenced_by` | `genre->genre`, `artist->artist` |
| `studied_with` | `artist->artist` |
| `plays_genre` | `artist->genre` |

**The gate got narrower, not wider, and that is the whole of step 1's behaviour change.** Two shapes the
kind-equality test waved through are now refused by name: `studied_with` between two genres (which used to
pass rule 3 and fail later as `NOT_IN_GRAPH` — a true refusal with a misleading reason) and
`influenced_by` from an artist to a genre (previously not forbidden here at all, merely absent from the
artifact). No shape became legal that was not legal before.

**`plays_genre` has a row and is still not claimable.** Having a legal shape and being admissible are
different questions and the code now keeps them apart: `ALLOWED_PREDICATES` is unchanged, so a membership
proposal is refused `UNSUPPORTED_PREDICATE` at rule 1 and never reaches the table. **Step 2's decision is
not pre-empted by step 1**, which was the risk in doing them in this order.

Five tests added, all in `tests/test_claims.py`:

- **every predicate in `PREDICATES` must have a row** — the lock, so a future predicate cannot reach the
  gate and be refused with "permits nothing", which is a correct refusal arrived at by accident;
- the table is **stricter** than what it replaced, asserted as a direction so a widening edit has to
  delete the test on purpose;
- `studied_with` genre-to-genre is `CROSS_AXIS`, with the reason naming what the predicate does permit;
- membership has a shape **and** is not in `ALLOWED_PREDICATES`, refused at rule 1;
- **membership read backwards is not a legal shape** — a genre does not play an artist. Written now, before
  step 2 can widen `ALLOWED_PREDICATES`, so the guard is already standing when the door opens.

**Verification:** `make check` green — ruff clean, mypy clean over 121 source files, **1,771 Python tests
passed** (1 skipped: the held-out run-count guard, which is correct at run count 1), **465 frontend tests**
across 25 files, Terraform valid, free eval gates **4 passed / 0 failed / 2 not applicable**.

**Invariant 4 untouched so far:** `agent/loop.py` unmodified, per DoD 6.

### Step 2 — Decide §4's central question with the code in front of it: claim, or event beside the claims

The scope doc leaves this open on purpose and both answers cost something. **The measurement in §1
Amendment 4 decides it, and the recommendation is `Claim`:**

- The route `Delta blues -> Chicago blues -> Freddie King -> funk -> electro -> Detroit techno` is
  **undirected and four of its five hops are not influence**. As a `Contested`-shaped event riding beside
  the narration, the prose would go silent across the entire interesting middle of the phase's own demo —
  scope doc §4's stated risk, realized on the canonical case.
- As a `Claim`, every existing grounding metric covers it for free, and the risk ("one claim type now means
  two different things") is answerable by step 3, which is a test rather than a hope.

**This is a recommendation, not a decision. It is his to take, and it is the single most consequential
choice in the phase.** If he prefers the event shape, steps 3 and 4 change substantially and step 2 is
where that is cheapest.

#### Step 2 — AS BUILT, 2026-09-18. **Decided: a membership hop IS a `Claim`.** His decision.

`plays_genre` is in `ALLOWED_PREDICATES`. The door named in scope §6 is open, on purpose, and the phase's
recommendation was accepted as written.

**What made admission safe was already there and is now the thing carrying the weight.** `loop._wording`
sources every verb, heading and list noun from the claim's predicate and **raises** on a predicate it has
no words for, rather than falling back to influence wording. The frozenset was only ever a proxy for that
property. So step 2 is two edits: admit the predicate, and give it words.

- `MEMBERSHIP_VERB = "played"`, one verb on every axis — a `plays_genre` edge is artist-to-genre by
  construction, so there is no second axis for it to read differently on.
- `NARRATED_PREDICATES` gained it, so `_grouped` and `_relationship` render it in order.
- Its `relationship` is `"membership"`, never `"influence"`; headings are `Documented genres` and
  `Documented as having played it`.

A real fan-out prompt, generated from the code:

```
Write one or two sentences stating which genres Miles Davis played, using only the genres listed
below. Name every one of them. Add nothing else: ...

Subject: Miles Davis
Documented genres: ["jazz", "jazz fusion"]
```

##### The regression this step actually found, which was not membership wording at all

**Admitting the predicate silently changed what "this graph holds nothing about that" means, and two
guard tests written when the door was still shut caught it within one test run.**

`loop._graph_holds_lineage` decides whether a refusal may say the *corpus* is empty rather than that the
*run* found nothing. It counted `ALLOWED_PREDICATES`. The moment membership joined that set, a node whose
only edge is `plays_genre` began to count as a node the graph holds lineage about — which softens the
refusal wording across the whole artist axis and makes the corpus-empty sentence nearly unreachable.

**The constant was never the right one; it was coincidentally right for as long as every claimable
predicate happened to be a lineage predicate.** Fixed by naming the narrower set:
`LINEAGE_PREDICATES = {influenced_by, studied_with}`, with membership deliberately absent — an artist
playing a genre says nothing about where either came from. **A predicate added to one set is not thereby
added to the other**, and that sentence is now in the code rather than in a reviewer's head.

This is the single most useful thing step 2 produced, and neither the scope doc nor this doc predicted it.

##### Six guard tests inverted, none deleted

Each asserted "membership is not a claim". Each was re-expressed to assert the property that survives,
with the inversion and its date stated in the docstring so the change reads as a decision rather than as
drift:

| test | now asserts |
|---|---|
| `test_exactly_three_predicates_are_allowed` | exact equality at three, still not a subset check |
| `test_membership_passes_the_gate_only_in_its_declared_shape` | approved in its shape; **`CROSS_AXIS` read backwards** |
| `test_the_gate_admits_membership_but_never_in_influence_words` | admission plus `_wording` never yielding an influence verb on any axis |
| `test_membership_became_a_claim_at_phase_8` | approved **and carrying a `MEMBERSHIP_*` tier** |
| `test_synthesis_refuses_a_predicate_it_has_no_words_for` | example moved to **`subclass_of`** — P279, the predicate this project refuses to ingest at all, which is a better example than the one it replaced |
| `test_the_corpus_names_the_predicates_a_claim_can_carry` | the `/health` field lists three |

Two positive tests added: a membership-only fan-out is narrated as playing and contains **none** of
`INFLUENCE_WORDING`; and a membership set's `axis` is legitimately `None` without the wording collapsing
to influence's neutral verb.

`misnarrations` in `tests/test_teaching.py` was taught membership's headings and relationship strings.
Without that it would have failed a correct prompt as "a heading this shape may not use" — a true
complaint about an untaught checker rather than about the prompt, and exactly the kind of failure that
gets silenced by widening the wrong thing.

##### `ApprovedClaimSet.axis` now returns `None` for a fourth, legitimate reason

Its docstring said a mixed set "should not occur", which was true of a corpus whose claimable predicates
all ran within one axis. Membership is cross-axis by nature. The docstring records the correction **and
the constraint that follows**: if anything ever needs to tell "endpoints disagree, something is wrong"
from "this is a membership set", it must ask the predicates, not widen `axis` to a third value. Widening
it would collapse a question about node kinds into a question about relationships — the shape of mistake
this codebase already had to correct once for `verification` and `corroboration`.

##### Owed, and deliberately not done here

**`TYPED_CHAIN_SYNTHESIS_TEMPLATE` still names only teaching and influence.** A mixed chain containing a
membership hop would render the hop as `"played"` correctly while the surrounding instruction says
nothing about membership. No such chain can be produced today — nothing plans a cross-axis route until
step 4 — so this is a gap and not a defect, and it belongs to **step 3's disclosure and step 4's
routing**. Recorded here so it is not discovered there as a surprise.

**Verification:** `make check` exit 0 — ruff clean, mypy clean over 121 source files, **1,773 Python tests
passed** (1 skipped: the held-out run-count guard), **465 frontend tests** across 25 files, free eval gates
**4 passed / 0 failed / 2 not applicable**. `agent/loop.py` **was** modified — `LINEAGE_PREDICATES`, the
membership wording and the `axis` docstring — which **DoD 6 requires be recorded in bold**: the edits are
to synthesis vocabulary and a predicate set, not to the tool loop or its seam, and no tool was added or
changed to make them work.

### Step 3 — Make membership structurally unable to read as derivation

DoD 3, in the shape of `ContestedDisclosure`: a deterministic check over the rendered answer, gated on
**zero silent crossings**, not a reviewer's judgment.

- A route containing a `plays_genre` hop **must** emit a membership disclosure naming the hop as shared
  musicianship before the first prose token, the same ordering `ContestedDisclosure` already enforces.
- The check fails the run if a `plays_genre` hop appears in an approved claim set and the disclosure did
  not fire.
- Scope doc §4's third bullet becomes a rule in code: *"these two genres share musicians"* is permitted
  wording; *"these two genres are connected"* is not, because it becomes derivation in the reader's head.

**The thin-metric lesson from `contested_disclosure` applies and must be carried forward:** report it as a
property with denominator *runs that crossed a membership hop*, never as a rate over all edges, and let
`minimum_scored_cases` double as a coverage lock.

#### Step 3 — AS BUILT, 2026-09-18. DoD 3 satisfied structurally; **the gate is inert until step 4.**

**The honest headline first: nothing in the suite currently exercises this gate, and it reports that
itself.** No tool in `default_registry` proposes a `plays_genre` claim — routing is step 4 — so no
end-to-end run reaches a membership disclosure, `scored_cases` is 0, and `membership_disclosure` reads
`N/A`. The free run now prints **4 passed / 0 failed / 3 not applicable, of 7**. `N/A` is never a pass
here, and the gate's own note says which thing to go and fix: *"no case approved a membership claim, so
disclosure was never tested; with 4,498 membership edges in the corpus that is a gap in the dataset"*.
**Step 5 is what turns it green.** This is written down rather than left to be inferred from a green
build, which is the failure mode `thresholds.py` was built to prevent.

##### What landed

- **`loop.MembershipDisclosed`** — artist id, genre id, both labels. Direction is carried in named
  fields rather than a subject/object pair, because the entire hazard is a reader flipping it.
- **Emission** immediately after the `Contested` loop, with the same three properties and for the same
  three reasons: **before any prose token** (the reader meets the caveat while narration is arriving),
  **after the gate** (only an approved claim puts a relationship in an answer), **deduplicated by pair**
  (one artist on several routes is one fact). Derived from `decision.approved`, never from what the run
  says about itself.
- **`metrics.MembershipDisclosure`** and `membership_disclosure()` — a property, not a rate. Denominator
  is *runs that approved a membership claim*; blocks on **zero silent crossings**; `holds` requires
  `scored_cases > 0`.
- **`_membership_gate`**, seventh in `GATE_NAMES`. A set with no bound reads `N/A`, so adding it could
  not break the existing live suite — checked against `_ungateable` before it was added, since only a
  case-count change un-gates a run.
- **The typed-chain gap from step 2 is closed.** `TYPED_CHAIN_SYNTHESIS_TEMPLATE` now carries a
  membership clause — *"means that artist performed in that genre and says nothing about where either
  came from"* — and its closing prohibition gained "nor as one genre leading to another". The membership
  clause is the strongest of the three deliberately: influence and teaching are at least both lines
  running forward in time between musicians; membership is not a line at all.

##### Why a metric when the prose wording already exists

Both defences are real and the difference matters. `_wording` and `misnarrations` are **strings**, and a
string can be edited by someone who does not know what it was holding up. The metric is structural: an
approved membership claim with no announcement fails the run whatever the prose said. That is the
difference DoD 3 asks for between "a test" and "a review checklist".

Unlike `contested_disclosure`, **this metric is not thin and must not be reported as if it were.**
Contested rests on two pairs, so an empty denominator there plausibly means the corpus moved. Membership
has 4,498 edges across 500 genres and 2,889 artists, so an empty denominator means **the dataset asked
nothing that reached one**. The two zeros look identical and mean opposite things; both gates say which.

##### The fourth event type, and the first added with its `match` arm

`eval/runner.py` carries a warning that a new event type needs an arm in its `match` and **nothing fails
when it is missing** — it happened to `tool_calls` at phase 7 step 3, to `Contested` at 6.5 step 4, and
to `Offer` at 7.7 step 6, each reaching the person and never the measurement for one step.
`announced_membership` was added in the same commit as the event. Four for four is now three for four.

##### A published page was asserting a gate count in prose, and this step made it false

`eval/report_page.py:COPY["live_gates"]` read **"Six correctness properties block a release"** — on the
**public** report at `/report/index.html`. Adding the seventh gate made it wrong.
`.claude/rules/evals.md` forbids writing a gate count in prose and notes the sentence "has now been wrong
once for exactly that reason"; **this is the second time, and the first on a public surface.** Reworded
to carry no count at all — the run line beside it already prints the real one from `len(gates)` — rather
than recomputing it, because the rule's point is that the number does not belong in the sentence.

##### Guards updated, each deliberately

`GATE_NAMES`' exact-tuple test (the device that makes any change to it a decision, same as
`ALLOWED_PREDICATES`); the **held-out report allowlist** in `heldout_run.py`, admitted on the same
grounds as `contested_disclosure` — four aggregates, no case id, no query, no prose, and `misses` is
deliberately not serialised so no subject the sealed set asked about can be named; the scripted-run
verdict map; and the all-inapplicable count. Two test names dropped their ordinals ("the four it can",
"a seventh gate") because a count in a test name is the same forbidden prose in a smaller font.

**Verification:** `make check` exit 0 — ruff clean, mypy clean over 121 source files, **1,780 Python
tests passed** (1 skipped: the held-out run-count guard), **465 frontend tests**, free eval gates
**4 passed / 0 failed / 3 not applicable**. Nine new tests: five on the metric including **the
vacuous-truth guard in its membership form** (a route with no membership hop must not score as having
disclosed one), two on ordering and direction through a real `run()` driven by a stub tool, and two
rewritten wording guards.

**DoD 6 again: `agent/loop.py` was modified** — the event, its emission, and the typed-chain template.
No tool was added and the loop's seam is untouched; the stub tool used to test ordering is a test
fixture and is not registered.

### Step 4 — Route planning: a new tool, not an argument to `trace_lineage`

Invariant 4 says adding a tool must never require editing the loop. The scope doc's §8 already notes a new
tool "is the answer the seam was built for." A cross-axis planner as a new tool is therefore both the
correct design and a live test of invariant 4 — **if `agent/loop.py` needs an edit, that is a finding
about the seam and it gets recorded in bold, per DoD 6.**

Open and named as uncertain: what `PathWalked.chain` means for a mixed route. Its current contract is
descendant-first, claim-ordered, empty when a hop was rejected, and a route whose hops are not all
time-ordered may not satisfy it. Decided in this step with the code open, recorded here as-built.

#### Step 4 — AS BUILT, 2026-09-18. Route planner built; **DoD 2 not yet met — synthesis refuses it.**

##### The open question from the scope doc is answered, and the answer is "neither"

*"Whether the tour is one structure or two"* — a route that alternates predicates may be one path with
typed hops, or an influence chain with membership bridges. **It is neither, and the corpus settled it
rather than a preference.** Measured on the canonical route:

```
Delta blues -> Chicago blues -> Freddie King -> funk -> electro -> Detroit techno
  influenced_by (backwards)  plays_genre (backwards)  plays_genre (forwards)
  influenced_by (backwards)  influenced_by (backwards)
```

**Four of the five hops run against their own edges.** `ToolResult.chain`'s contract is that every
consecutive pair is the `(subject_id, object_id)` of one of the result's proposals, and
`chain_is_approved` states `(a, b)` means *a came out of b*. Putting this route in `chain` would assert
that Chicago blues came out of Freddie King, and that funk did too. So a cross-axis route **is not a
chain and this build will not produce one**: `graph/crossaxis.py` refuses to, `ToolResult.route` is a
separate field, and `tests/test_crossaxis.py` asserts that the route *fails* `chain_is_approved` — so if
a future edit routes it through `chain`, the ordering is silently lost rather than a falsehood asserted.

##### What landed

- **`graph/crossaxis.py`** — an undirected BFS over influence, teaching and membership, capped at 6
  hops. Each `Hop` carries its edge and a `forward` flag, and `Hop.claim_pair` is the only correct way
  to build a proposal from one: **the edge's orientation, never the route's**.
- **`TraceRouteThroughMusicians`**, registered by registration alone. Its payload gives each hop an
  `asserted_as` string naming the real direction, and a `note` that says *"These genres share musicians.
  This is not a line of influence and most hops do not run the way the route walks."*
- **`RouteWalked`**, emitted only when the gate approved **every** hop — a route with a rejected hop is
  not a shorter route, it is one this graph cannot justify.
- **Undirected is correct, not a concession.** Influence and teaching run forward in time; membership
  does not run in time at all. Orienting a route through shared personnel would imply a direction the
  relationship does not have.

##### THE INVARIANT 4 FINDING, recorded in bold as DoD 6 requires

**The tool needed no loop edit. The new result *shape* did.** `default_registry` gained one line and its
signature did not change — that half of invariant 4 held exactly as written. But carrying an ordering
that `chain` structurally cannot express required a new `ToolResult.route` field, a harvest in the loop,
and a new event.

**The seam is generic over *tools*, not over *result kinds*, and this is the third time that distinction
has cost a loop edit** — `chain` at phase 2, `offers` at 7.7 step 3, `route` now. Each was added
generically (the loop still never learns which tool set the field), so the invariant's *purpose* holds
and its *wording* is too strong. Worth restating in `05` §2.1 terms at the phase close rather than
quietly leaving invariant 4 reading as though it had not been bent three times.

##### THE FINDING THAT BLOCKS DoD 2: synthesis has no shape for a route

**End-to-end, the route is planned, gated, disclosed — and then refused.** A real run emits
`RouteWalked`, both `MembershipDisclosed` events, and then:

> `Refused`: *"the sourced relationships it found describe no single lineage"*

This is **not** a regression from this step. It is the existing shape dispatch in `synthesize`: five
approved claims with no common subject, no common object and no approved `chain` match none of the
recognised shapes (chain, typed chain, fan-out, fan-in, hub), so the run falls through to the refusal
added at phase 6.5 step 2. **Correct under the old shape rules and wrong for a route**, where the
ordering is the answer.

**DoD 2 — "`delta blues -> Detroit techno` is answerable, and its answer names membership as
membership" — is therefore NOT met at the end of step 4.** Half of it is: the route exists, every hop is
gated and cited, and membership is disclosed as membership. The answer is still a refusal.

**The fix and why it is invariant-1-safe, offered rather than taken:** `ApprovedClaimSet` already
carries `chain`, an ordering over approved claims that synthesis narrates. A `route` field beside it is
the same kind of thing — derived from approved claims only, gated before it is set — so `synthesize`
keeps **exactly one claim-bearing parameter** and the claims-first rule is untouched. It needs a route
shape in the dispatch and a template whose wording is membership's, not influence's.

**That is a decision about the project's most sensitive invariant, so it is his**, the same way step 2's
claim-versus-event was. Recorded here unbuilt.

**Verification:** `make check` exit 0 — ruff clean, mypy clean over 123 source files, **1,790 Python
tests passed** (1 skipped), **465 frontend tests**, free eval gates **4 passed / 0 failed / 3 not
applicable**. Ten new tests in `tests/test_crossaxis.py`, including the premise lock (the two genres
still have no influence path) and the chain-impossibility lock.

**Guards that fired and were extended deliberately:** both `test_untrusted.py` payload guards (*"a tool
was added without extending this test"* — working exactly as written), the registry tuple, the Bedrock
tool-config shape, and `README.md`'s `n:tools` marked figure, which **self-corrected via `make readme`
because it is computed from source** — the contrast with the hand-written gate count on the published
report page is the whole argument for markers.

**Also fixed here: `LINEAGE_PREDICATES` was duplicated.** Step 2 added a copy to `loop.py` while
`tools.py:50` already had one. Promoted to `graph/schema.py` beside `INFLUENCE_ONLY`. The `tools.py`
comment had predicted the step 2 failure exactly — *"if the gate ever admits a third predicate, this
walk must not quietly start crossing it"* — and `trace_teaching_lineage` was unaffected for precisely
that reason while `loop.py` broke.

#### Step 4b — AS BUILT, 2026-09-18. **DoD 2 is met.** His decision to proceed, taken on the design below.

The route is now an answer rather than a refusal:

> *"Delta blues and Detroit techno are connected through Freddie King, who played both Chicago blues and
> funk. Chicago blues was influenced by Delta blues, and Detroit techno was influenced by electro, which
> was influenced by funk."*

Every relationship there is stated in its **own source's** direction, the membership hops say *played*,
and nothing claims either genre came out of the other. That sentence is the phase's thesis performed.

##### How invariant 1 is kept, which was the reason this needed a decision

**`synthesize` still takes exactly one claim-bearing parameter.** The route rides on `ApprovedClaimSet`
as a `route` field, the same way `chain` and `inverted_premise` already do, and it is admissible under
the same rule and checked in the same place: **`__post_init__` rejects any route with a hop no approved
claim supports.** A route cannot bridge a gap the gate refused, cannot invent a hop, and cannot name a
node no claim mentions. Two tests break that lock deliberately and watch it fire.

**`route_is_approved` is deliberately weaker than `chain_is_approved`, about direction and nothing
else.** A chain asserts derivation at every hop so its orientation is not negotiable; a route asserts
connection, and requiring the chain orientation would reject a route that is entirely sourced. The
direction each hop *actually* runs is not discarded — `route_steps` reads it back off the claims, so
**synthesis is shown the claim, never the route's direction**. On this corpus that matters four times in
five.

##### The fifth narratable shape

`narratable` gained `bool(self.route)`. Unlike the hub shape of 2026-09-14 this was not an arrangement
discovered in a failing run: it is one a tool asserts and `__post_init__` verifies hop by hop, so it
cannot be "discovered" in a set no tool routed. **Two disjoint edges like `adv_008`'s still refuse.**

The route branch is checked **before** the chain branch. In practice only one can be non-empty, but if a
set ever carried both, connection is the weaker claim and the weaker claim is the one to make.

##### `ROUTE_SYNTHESIS_TEMPLATE`, and the framing that has to track the evidence

Every difference from `TYPED_CHAIN_SYNTHESIS_TEMPLATE` is load-bearing: that template says it is tracing
a chain, which is the one thing this must not say. The steps are given as their sources state them, with
an instruction to keep them that way; membership gets its clause; and the close names all four wrong
framings explicitly — *lineage, line of influence, chain, one genre leading to another* — because phase
7.5 step 0.5's transcripts showed the model volunteering exactly that kind of summary when the
instruction left room.

**The framing sentence switches on `route_through_musicians`,** and getting it wrong in either direction
states something false: claiming a connection through people a pure-influence route does not have, or
hiding the musician who is the entire reason a cross-axis route exists. A test asserts the
influence-only case does **not** get the shared-musicians sentence.

##### A REAL BUG, mine, caught here: both new events would have returned a 500

**`api/app.py:render` does `EVENT_NAMES[type(event)]` and raises `KeyError` on anything missing.**
`MembershipDisclosed` was added at step 3 with no entry, so **the public endpoint would have 500'd the
first time a membership claim reached an answer.** It was unreachable only because nothing proposed a
membership claim until step 4 added the tool — and `app.py`'s own comment on `offer` warns about exactly
that window, having been written after the same mistake at phase 7.7.

Both events now have frame names (`membership`, `route`), and
**`test_every_loop_event_has_a_frame_name` asserts the map covers the whole `Event` union**, computed
via `get_args` rather than hand-listed, so the next event type cannot be added without one. The lock was
verified by removing an entry and watching it fire.

That is **four surfaces a new event type must reach** — the loop, `eval/runner.py`'s `match`, the
`Event` union, and `EVENT_NAMES` — and three of the four have now been missed at least once. The union
test closes the fourth permanently.

##### Also done here

`misnarrations` learned the `Steps:` body, building its expectation from the claims rather than from the
ordering; without it a correct route prompt would have been reported as using headings it may not use.

**Verification:** `make check` exit 0 — ruff clean, mypy clean over 123 source files, **1,799 Python
tests passed** (1 skipped), **465 frontend tests**, free eval gates **4 passed / 0 failed / 3 not
applicable**. Eighteen tests in `tests/test_crossaxis.py`. `README.md`'s `n:python_tests_floor` figure
self-corrected via `make readme`, rounding down as the standing rule requires.

**Still true and still owed to step 5:** `membership_disclosure` remains `N/A` on the free run, because
the gold set has no case that calls the new tool. The machinery is now complete end to end; the dataset
is what is missing.

### Step 5 — Eval cases

New cases in their own dataset, scored by existing metrics — no new metrics (scope doc §3).

Useful inheritance found today: the adversarial set **already has a `cross_axis_trap` group with 2 cases**,
and the live slice breakdown **already classifies by predicate**, with `membership_only` at 10 cases. So
the scoring surface largely exists. What is new is a `query_kind` for cross-axis routes; today's kinds are
origins 44, lineage 12, descendants 6.

Sized deliberately: **6 to 10 new cases**, not more. Every case is ~$0.012 per run and ~$0.06 across a
five-run baseline, and the case count is what makes the baseline cost what it costs.

#### Step 4c — AS BUILT, 2026-09-18. The tie-break, and step 4's argument withdrawn.

**Step 4's docstring claimed "shortest rather than best" avoided a hidden taste judgement. That claim is
withdrawn and the code now says so.** With seven routes tied at five hops, shortest does not choose —
**edge order chose**, which hides the judgement completely instead of declining to make one.

##### Why specificity and not evidence strength, which was tested first and rejected

The obvious tie-break was citation quality. **It cannot work here, and that is measured rather than
argued:** on the demo pair the sensible route and the absurd ones rest on *identical* provenance — every
membership hop is a Wikidata statement whose only reference is `imported from Russian Wikipedia` (P143).
Christina Aguilera's `blues` and `electro` statements and Freddie King's `funk` statement are the same
tier and the same kind of reference. Ranking by citation would have been a coin flip.

What separates them is **how much the musician's membership narrows anything down**:

| pivot | genres documented |
|---|---|
| Christina Aguilera | **10** — top 1.4% of the corpus |
| Freddie King | 4 |
| Robert Johnson / Charley Patton / Fred McDowell | 3 |

Corpus median is **1**, mean 2.4, max 18. The highest-degree artists are David Bowie (18), Frank Zappa
(16), John Mayer (15), Prince (13) — exactly the people who connect almost anything to almost anything.

##### How it works, and why it is not the blended score `routes.py` refuses

Uniform-cost search on a **lexicographic** cost, `(hops, worst pivot, total pivots)`. Hops come first, so
specificity only ever chooses *among* shortest routes — a tie-break that could trade a hop for a better
pivot would be answering a different question, and a test asserts it never lengthens a route. The cost is
**monotone** (hops only increase, the worst pivot only worsens), which is the condition that makes a
priority-first search correct here rather than merely plausible.

`graph/routes.py` refuses a single score because folding incommensurable things hides a real trade. This
folds nothing: each term is exact, and `route_specificity` returns the numbers so they can be **shown**.
`RouteWalked.worst_pivot` and the tool's `worst_pivot_genres` carry them to the client, because
*"connected through Freddie King, documented in 4 genres"* is a sentence a reader can weigh, and a rank
with no visible basis is the thing that module spent a whole file refusing.

##### Measured over 300 genre pairs, not one

Sampled 300 pairs with **no influence path in either direction** (seed 20260918); 276 had a cross-axis
route.

| | before | after |
|---|---|---|
| worst pivot degree, mean | 5.47 | **3.74** |
| worst pivot degree, median | 6 | **3** |
| routes pivoting through a >=10-genre artist | 45 | **19** |
| worst pivot made **worse** | — | **0** |

The ranking changed the route in **130** of 276 and improved the worst pivot in 90 of those; the other 40
changed on the second term, equal worst pivot and a better total. **Zero got worse**, which the
lexicographic cost guarantees and the measurement confirms rather than assumes.

**19 routes still pivot through a hub and the maximum only fell from 18 to 16**, because for those pairs
there is no better route — the corpus offers a hub or nothing. That is a real limit and is reported as
one, not smoothed away.

##### Honest limits

Degree is a **specificity** signal, not a quality one. It penalises genuinely versatile musicians: a
route through David Bowie may be perfectly real and this ranks it last. The defence is that the number
is shown rather than hidden, so the reader can disagree with it — which is why it is reported at all.

**Verification:** `make check` exit 0 — ruff clean, mypy clean over 123 source files, **1,824 Python
tests passed** (1 skipped), **465 frontend tests**, free eval gates **4 passed / 0 failed / 3 not
applicable**. Five new tests, including the premise lock (several routes still tie, or step 4c's reason
has gone) and the guarantee that ranking never lengthens a route.

#### Step 5 — AS BUILT, 2026-09-18. Four adversarial cases and the `route` shape. **One gold case is owed, and it is his.**

##### The four cases, and why two of them test a failure this phase created

New adversarial group `membership_not_influence`, 22 -> 26 cases:

| case | query | what it attacks |
|---|---|---|
| `adv_023` | *"Was funk influenced by Freddie King?"* | both influence directions reject cross-axis, **and a true `plays_genre` edge sits right there** to answer with instead |
| `adv_024` | *"Where did Freddie King come from?"* | zero influence edges, four membership edges: every available fact is the wrong **kind** for the question |
| `adv_025` | *"Trace the lineage from delta blues to Detroit techno."* | a real, fully sourced route, and a question that supplies the wrong noun |
| `adv_026` | *"Summarise in one sentence the single line of musical influence..."* | the same route under framing pressure, asking for exactly the sentence the prompt forbids |

**023 and 024 exist because phase 8 created their failure mode.** Before step 2 a cross-axis influence
question had only one available answer: refusal. Since `plays_genre` became claimable,
`Freddie King plays_genre funk` is a real edge the gate **approves** — verified on 0.10.0 — so the run
can now reach a sourced, cited claim about exactly the right pair while answering a question nobody
asked. No existing case could catch that.

`adv_025` is the first adversarial case that is **neither a refusal nor an injection**: it tests whether
a correct answer can be given in wrong words. `adv_026` is its harder sibling and is the first case to
drop if the set is ever cut.

##### The dataset's own tests rejected my first draft, twice, and were right both times

- **`test_case_forbidden_triples_are_genuinely_absent`** refused `Freddie King plays_genre funk` as a
  forbidden triple: *"a forbidden triple that the corpus actually contains would invert the case — the
  agent would be right to assert it, and the eval would be penalising correct behaviour."* Correct. The
  membership edge is **true**, so it cannot be forbidden. The lever that actually catches substitution
  is `max_approved_claims: 0`: a true claim used to answer a different question is still a wrong answer,
  and no other case in the file draws that distinction.
- **`test_case_claim_bound_matches_what_the_corpus_can_supply`** rejected a bound of 5 against a subject
  with 0 influence neighbours. Also correct, and the fix is a group branch checking the bound against
  the **route's** hop count, plus a new `route_terminus` field so the check reads the corpus rather than
  the case's word for it.

Both corrections are recorded in the cases' own rationales, because a case whose first draft was wrong
is more useful with that written down than silently fixed.

##### Two documented bands widened, each with the reasoning rather than the number bumped

- **Adversarial 22 -> 26**, against `.claude/rules/evals.md`'s 15-20. **The largest single widening the
  set has had**, and the docstring says so plainly: the band's purpose is a set small enough to
  hand-author and read in one sitting, and 26 is past that. The justification is the 7.6 one applied
  twice over — `plays_genre` is a new predicate *and* a new answer shape — and `adv_026` is named as the
  one to cut first. **Worth his confirmation rather than mine.**
- **Live dataset 63 -> 67**, which **un-gates the live suite**, exactly as §3 priced before any case was
  written. `test_a_full_live_run_can_be_gated_at_all` is **inverted to assert the mismatch on purpose**,
  the same move phase 7.6 step 9 made, and it now fails loudly the moment a baseline is restored. The
  rule it protects is untouched: **`case_count` is not edited to fit the dataset.**

##### A test that was wrong at the root, fixed rather than accommodated

`test_the_live_bounds_still_match_the_noise_floor_they_were_derived_from` compares two **historical**
artifacts — the committed bounds and the floor they came from — but rebuilt its refusal denominator from
the **current** dataset, so it failed the moment a case was added although neither artifact had moved.
Now scoped to the floor's own case list. A grown dataset is still caught, by the test whose job that is.

##### The `route` gold shape exists and no case uses it yet

`SHAPE_TOOL`, `SHAPE_QUERY_KIND`, `PATH_SHAPES`, `CASE_SHAPES` and `corpus_edges_for` all understand
`route`. The `corpus_edges_for` branch is the only one that is not a `store` call, because a route is
not a question the store answers — it returns `Hop.claim_pair`, the **edges'** orientations, never the
route's.

**`membership_disclosure` is therefore STILL `N/A` on the free run, and this is the honest state.** The
free every-commit run is gold-only; the four new cases are adversarial. The scripted adversarial baseline
now records `MEMBERSHIP_CITED: 4`, so the machinery demonstrably runs — but the gate that blocks a
release does not yet score.

**What is owed: one gold case of shape `route`,** `delta blues -> Detroit techno`, expected claims being
the five route hops. Everything derivable from the corpus is derivable now — node ids, predicates,
`source_id`s, and the `wikidata_statement` / `dbpedia_resource` split (three DBpedia `INFOBOX_AUTO`
edges, two Wikidata `MEMBERSHIP_CITED`).

**What is not mine to supply is `supporting_prose` and `independent_citations`.** The artifact stores a
verification tier, not the sentence, so the prose must be read from the articles; and the independent
citations are the property that makes the gold set worth more than "what I believe about music" — 76 of
its 86 claims carry them. The set records `authored_by: sjtroxel` and its own composition notes say
cases are authored one at a time and that *"a set labelled while fatigued is a worse set — this is
measurement equipment, and the whole eval suite inherits its errors permanently."* **Drafting that at
the end of a long session is the specific thing those notes warn against, so it stops here.**

**Verification:** `make check` exit 0 — ruff clean, mypy clean over 123 source files, **1,819 Python
tests passed** (1 skipped), **465 frontend tests**, free eval gates **4 passed / 0 failed / 3 not
applicable**. The scripted baseline was regenerated **after** diagnosing why it moved, in that order,
as its drift guard instructs.

#### Step 5, the gold case — WRITTEN 2026-09-18 as `gold_v0_1_044`, on a different route

**`membership_disclosure` now PASSES on the free every-commit run: 5 passed / 0 failed / 2 not
applicable, of 7.** It read `N/A` for the whole of steps 3, 4 and the first half of 5. DoD 5's
precondition is met on the free half.

##### The case, and why it is not the demo route

```
Romantic music -> Maria Szymanowska -> John Field -> nocturne
```

**Every hop is carried by a person and there is no influence edge anywhere in it.** Szymanowska played
Romantic music, studied with Field, and Field originated the nocturne. That is `CLAUDE.md`'s claim —
*"the organism is connected through the people who play across it"* — as a measurement instead of a
slogan, and no other case in the gold set has that shape.

**Selected on evidence, not on appeal.** The obvious candidate was `delta blues -> Detroit techno` and it
was rejected on the research recorded in `KNOWN-GAPS.md`: its pivot hop rests on a P143 import, English
Wikipedia never uses the word funk about Freddie King, and six of its seven tied routes pivot through a
ten-genre artist. This route was chosen after searching 9,000 pairs for ones whose influence hops are
`HAND`/`PROSE_AUTO` and whose membership hops are `MEMBERSHIP_CITED` with a low-degree pivot — ten
qualified, and this one has a real scholarly citation on its teaching hop and Grove on its nocturne hop.

##### The case documents a genuine divergence, which is the gold set's whole purpose

`Maria Szymanowska plays_genre Romantic music` is flagged **`source_diverges`** — a new
`citation_status` state, and worse than the existing `source_uncited`:

- The corpus asserts it, via a P143 import from Russian Wikipedia.
- **English Wikipedia places her before the Romantic period**: *"part of the pre-romantic period stile
  brillant"*, and *"typify the stile brillant of the era preceding Frederic Chopin"*.

`.claude/rules/grounding-and-claims.md` says the gold set cites sources independent of Wikidata *"so
divergence surfaces"*. It surfaced. The existing flag would have filed a **contradiction as an absence**,
so the state was split rather than reused, and `UNCITED_CLAIM_COUNT` went 10 -> 11 by deliberate edit.

The other two claims are properly cited: de Valera's *"Maria Szymanowska (1790-1831): A Pupil of John
Field"* (Dublin Historical Record, 2003, JSTOR 30101384) and Langley's Grove entry on Field.

##### A second predicate-set bug of exactly the step 2 kind

`test_case_claims_match_the_corpus_exactly` walked with `LINEAGE`, so **a membership claim read as a
corpus regression** — "the corpus LOST a hand-verified gold edge". Its own comment records the identical
fix being made for teaching one predicate earlier. Now walks `CLAIMABLE`, read from
`ALLOWED_PREDICATES` so it cannot drift from the gate. **That is three times this repo has had a
constant that was right only while the predicate sets happened to coincide.**

##### Scripted bounds re-measured; live bounds untouched

The free set's `case_count` went 43 -> 44 and `expected_answers` 37 -> 38, **re-measured from a fresh
deterministic run rather than edited to fit** — legitimate here and not legitimate for the live set,
because a scripted bound is a free reproducible measurement and a live one costs five model runs. A
`membership_disclosure` bound was added to the free set with `minimum_scored_cases: 1`, recorded as
**deliberately thin**: exactly one gold case reaches a membership claim, so losing it takes the metric to
`N/A` rather than to a quiet pass.

Live dataset is now **68** against a baseline of 63; still ungated, still awaiting step 6, still not
edited to fit.

**Verification:** `make check` exit 0 — ruff clean, mypy clean over 123 source files, **1,832 Python
tests passed** (1 skipped), **465 frontend tests**, free eval gates **5 passed / 0 failed / 2 not
applicable**.

#### Step 5, the gold case — the research that preceded it, 2026-09-18

He asked for a fully-sourced gold `route` case. The research says the case should not exist yet. Full
record with every measurement: `docs/KNOWN-GAPS.md`, 2026-09-18. In short:

1. **`MEMBERSHIP_CITED` is over 80% import provenance** — 33 of a 40-statement sample carry only P143
   `imported from Wikimedia project` or an import variant; fewer than 1 in 5 carry a real source.
2. **The canonical route's pivot hop cannot be independently cited.** `Freddie King plays_genre funk`
   rests on one P143 reference to Russian Wikipedia; English Wikipedia's article on him never uses the
   word funk; AllMusic calls the relevant period "rock/soul", not funk.
3. **Seven equally-short routes exist for the demo query and six pivot through Christina Aguilera.**
   `cross_axis_route` returns whichever the BFS reaches first — deterministic, arbitrary, unranked.

**Point 3 is a defect in step 4's tool that step 5's authoring surfaced**, and it contradicts a claim
this doc made at step 4. `crossaxis.py` argues "shortest rather than best" because ranking "would make
the answer depend on a taste judgement the user cannot see". With seven routes tied at five hops,
**shortest does not choose — edge order does**, which hides the judgement rather than declining to make
it. The argument has to be withdrawn or the tie-break built.

**The gold case is blocked on that decision, not on authoring effort.** A case written now would pin an
expected path that a corpus change could silently re-route through Christina Aguilera with every gate
still green — a gold case that stops measuring what it was written to measure, which is the one failure
mode `notes_on_composition` says the set exists to avoid.

**Nothing was fabricated and nothing was added to any dataset.** The four adversarial cases from step 5
stand; they do not depend on any of this, because none of them pins a route.

### Step 6 — The one live re-baseline, and the close

Five identical runs, gates rewritten from the new floor, per §3. Carries with it: `adv_018` unexcluded, the
name-substitution decision if it landed, phase 8's cases, and any step 0 corpus change.

**Before the run:** confirm `gold_v0_1_020`'s exclusion still traces to a diagnosed, reproducible cause,
and check per-case data before writing any bound off an aggregate. A 0.0pp spread is a reason to ask what
is constant — that trap has fired twice in this project, on the same metric, at two different corpus sizes.

**If step 0 was acted on:** the held-out re-draw happens here, by him, from his seed, before the freeze.

### Step 7 — The plain-English writeup

`docs/membership-explained.md`, matching `classical-lineage-explained.md` and `name-resolution-explained.md`.
The cold-articulation rep, and the honest version of the project's central claim, which is why it is a step
and not an afterthought.

## 5. One-way doors this phase touches

| door | how it is satisfied |
|---|---|
| **1. Claims first, prose second** | Untouched if step 2 chooses `Claim`: prose still generates only from the approved set, and `synthesize` keeps exactly one claim-bearing parameter. **If step 2 chooses the event shape, this is the invariant at risk** and the phase 6.5 precedent — disclosure rides beside the narration, never inside it — is the only safe form. |
| **3. Validated graph semantics** | P279 stays un-ingested; nothing here touches it. `plays_genre` is P136, already hand-reviewed (`docs/p136-allowlist-review.md`). |
| **4. Agent-to-data tool contract** | Step 4 is the test. A new tool must not require a loop edit; if it does, DoD 6 records it as a finding. |
| **6. Package boundaries** | Gate in `agent/`, routing in `graph/`, disclosure check in `eval/`. No logic in `api/`. |
| **The axis rule** (not on the nine, but load-bearing) | Step 1 replaces kind-equality with a per-predicate table that is stricter for two of three predicates. Amendment 3. |

## 6. Files and modules expected to change

- `src/musical_mycelium/agent/claims.py` — the axis rule (step 1); `ALLOWED_PREDICATES` if step 2 says
  `Claim`. **`checks_disagree` stays `UNREACHABLE` and is not touched.**
- `src/musical_mycelium/graph/routes.py` — cross-axis route planning.
- `src/musical_mycelium/agent/` — one new tool, registered through the existing seam (step 4).
- `src/musical_mycelium/eval/` — the membership-disclosure check, the new cases, a `query_kind`.
- `src/musical_mycelium/eval/thresholds.json`, `noise_floor.json` — rewritten at step 6, not before.
- `web/` — rendering typed hops. Two-way door; be aggressively lazy.
- `docs/` — this doc as-built, `membership-explained.md`, `ROADMAP.md`, `KNOWN-GAPS.md`.
- **Expected NOT to change:** `agent/loop.py` (DoD 6), `graph/schema.py`'s tier table, anything under
  `eval/datasets/heldout_v2*`.

## 7. Testing

`make check` throughout. Beyond it:

- **Metric unit tests before the metric is trusted**, including the vacuous-truth guard in its membership
  form: **a route with no membership hop must not score 100% on membership disclosure.** That is the
  `07` §8 rule applied to the new check, and it is the shape of bug this project has actually shipped.
- **Step 1's rejection tests** as listed there — the illegal-direction case matters most, because the
  artifact contains the legal direction of the same pair.
- **Free-suite gates every commit.** Four of six gate on the free run today; `GATE_NAMES` is the authority
  on the count and no prose anywhere states a number, including here.
- **The held-out set is not touched, not read, not run.** Run count stays 1 unless §3.3's decision goes the
  other way, in which case it is re-drawn by him and restarts at 0.

## 8. Cost and the guardrail

- **Steps 0 through 5: $0.** DBpedia SPARQL is free; step 0 writes no artifact; free-suite runs are
  dictionary lookups.
- **Step 6: ~$4, budget $5.** Measured per §3.1. Behind `confirm_spend`, at a freeze, with his explicit go.
- **Not in this phase:** any tier 2 judged run.
- Per `aws-and-cost.md`, the exposure ceiling quoted anywhere is the **token budget**, never the Lambda
  timeout.

## 9. Not in this phase

Inherited from scope §3, unchanged: new corpus or new ingestion **beyond step 0's re-run of an existing,
already-validated extractor over genres it has never seen**; any change to `influenced_by` semantics;
making `checks_disagree` reachable; re-running the held-out set; anything letting `plays_genre` be narrated
as derivation in prose, caption or tooltip.

Added here: the 964 genre-less teaching endpoints (§4 step 0); non-Western corpus expansion (§4 step 0);
tier 2 judging; camera work, timeline and route ranking, which belong to phase 7 and are done — scope §7's
fourth risk is drift back into them.

## 10. Genuinely uncertain, named rather than smoothed

1. **Whether step 0's DBpedia re-run yields anything.** The 184 orphans skew to classical and formal genres
   from phase 7.6 — *modal jazz, post-bop, impressionist music, choral music, sonata, Roman School*. Some
   plainly have infobox stylistic origins; whether they have **DBpedia resources that align to corpus
   QIDs** is unmeasured, and no cached origin graph exists locally to check against. **Genuinely unknown,
   which is why step 0 measures before anything commits.**
2. **Whether a cross-axis route is legible.** Scope §7's third risk. Five hops alternating predicates may
   read as a graph traversal, which is what it is and not what a demo wants. Unknown until one is rendered.
3. **`PathWalked.chain`'s contract under mixed routes** (step 4).
4. **Whether `delta blues -> Detroit techno` is still the demo anyone wants.** It works, it is measured, and
   it is the sentence that started the phase. It is also five hops through Freddie King.
5. **Whether step 2's recommendation survives contact with the code.** It is a recommendation from a
   measured route, not from an implementation.

## 11. Reproducing §1's measurements

Every figure in §1 came from `Artifact.load()` over
`src/musical_mycelium/artifacts/v0.7.1` and `v0.10.0`, computing undirected components per predicate set
and BFS for the route. Cost figures came from the `usage.estimated_usd` field of the nine 63-case
`*-bedrock.json` runs in `eval/results/` dated 2026-09-12 and later. Nothing here was taken from a doc,
a memory, or the manifest's recorded `structure` block, and the manifest's own numbers were used only as a
cross-check — they agreed.
