# Phase 7.7 — Name Resolution (v0.9.5) — IMPLEMENTATION

> **As-built plan.** Written 2026-09-12, immediately after phase 7.6 closed, against code read and
> measurements taken in the same session rather than recalled. Every number below was measured against
> artifact v0.10.0 on 2026-09-12; none of it is carried over from a previous phase.
>
> **APPROVED 2026-09-12 by sjtroxel** ("I'm fine with the new doc"). **Three
> decisions of his are already folded in below, taken 2026-09-12 before approval:** the teaching stratum
> (U1, yes), the retirement of the old sealed set rather than keeping two (D1, his call and his
> reasoning), and running the new set once at this freeze (U4, yes).
>
> Steps are marked `[done]` as they land, and each gets an as-built subsection recording where reality
> disagreed with this plan. The doc is allowed to be wrong. It is not allowed to be silently wrong.
>
> **Four things a cold session must not get wrong, before anything else:**
> 1. **Step 0 is a new held-out set, and HE draws it.** An agent may run `make heldout-verify`, read
>    `make heldout-check`'s case ids and problem codes, and nothing else. Never decrypt, never read a
>    decrypted copy, never ask for the key, never suggest subjects. `.claude/rules/heldout-set.md`
>    governs and outranks this doc.
> 2. **An offer is not a resolution.** Exactly two things resolve a name: one exact label match, or a
>    person's click. Nothing else, ever, including a unique partial match and a "confident" alias.
> 3. **An offer ACCOMPANIES a refusal; it never replaces one.** That is what keeps `refusal_accuracy`
>    measuring the same thing it measured before this phase, and it is why no adversarial case has to
>    be re-authored. See D3.
> 4. **This phase carries the ONE live re-baseline and the ONE deploy for phases 7.6 and 7.7 together**
>    (his decision, 2026-09-11). The public site is on v0.7.1 until step 8 of this doc lands.

## 1. What this phase delivers, in one sentence

**A resolver that will consider partial names and Wikidata aliases, and a wire format, UI and eval
treatment that turn every one of those matches into a choice a person makes rather than a guess the
system makes — plus a fresh sealed held-out set drawn on v0.10.0, one live re-baseline, and one deploy.**

### 1.1 Definition of done

Restated from the scope doc so it cannot be skipped, with the two corrections §1.2 records folded in:

1. Typing "mozart" into the site offers Wolfgang Amadeus Mozart, Leopold Mozart and Franz Xaver
   Wolfgang Mozart, and choosing one returns a gated, cited answer about the person chosen.
2. Typing "dolly" offers Dolly Parton. Typing "roy orbison" resolves to Roy Orbison exactly as it does
   today, and **nothing this phase adds makes "roy orbison" reach Joy Orbison** — proved by a test.
3. No query that resolves by exact label today resolves differently, proved by a test over every name
   in the gold, adversarial, tour and live sets, the chips and the README.
4. Nothing resolves without either an exact label match or a human choice. A test asserts it, and a
   second test asserts that an offer carries no claims.
5. A new held-out set is drawn from his own seed on the v0.10.0 pin, sealed, committed, and reported
   with a run count; the old set is retired from the working tree in the same commit, and exactly one
   sealed set exists on disk. `make heldout-verify` matches its manifest, `make heldout-check` is clean,
   and the set is run once after the re-baseline (run count 1).
6. The live re-baseline for **both** 7.6 and 7.7 runs at this phase's close, over five identical runs,
   behind an explicit spend confirmation. The six gates hold and `thresholds.json` names the new case
   count.
7. v0.10.0 and both phases' code are deployed together, `make check` is green, and the budgets hold.

### 1.2 Where the scope doc has already diverged from the corpus, and the amendment it needs

The skill requires this check rather than letting an IMPLEMENTATION doc quietly contradict its scope doc.
Two divergences, both measured 2026-09-12, both doc-only:

- **Scope §5 DoD 2 says "typing 'roy orbison' still refuses". It does not — it resolves.** Measured:
  `label_key("roy orbison")` has exactly one exact label match, `Q188426` Roy Orbison, so it resolved
  before this phase and will resolve after it. The *intent* is intact and is the thing worth protecting:
  "roy orbison" must not reach **Joy Orbison** (`Q14159313`), and under whole-word matching it cannot,
  because "roy" is not a word of "Joy Orbison" and `Peter O'Grady` is that node's only alias. DoD 2
  above is reworded to say what was meant. **Proposed scope-doc amendment: strike "typing 'roy orbison'
  still refuses" and replace with "nothing offered for 'roy orbison' is Joy Orbison."**
- **Scope §2 says 7.6 stores aliases "on nodes"; it reads as every node.** Measured: **2,423 of 3,628
  nodes carry at least one alias** (1,855 of 2,889 artists, 568 of 739 genres), 5,561 aliases in total.
  Two nodes in three, not all of them. The consequence is real and belongs in the copy: alias matching
  helps unevenly, and the unevenness is Wikidata's.

## 2. Baseline, measured 2026-09-12, not recalled

**The pin.** `graph/memory.py:36` and `ingest/wikidata.py:60` both read `0.10.0`. Nothing in this phase
moves it. This phase cuts no artifact.

**Most of the candidate generator already exists, and this is the single most important fact in this
plan.** `InMemoryGraphStore.search` (`graph/memory.py:196-207`) already returns exact normalised matches
first and then **whole-word substring matches, shortest label first**, using `_contains_words`
(`graph/memory.py:390`). Whole-word partial matching over labels is not new work. What is missing is
(a) aliases in the index, and (b) any way for a candidate to reach a person as a choice.

**The no-guess property is already structural, in one line.** `exact_matches`
(`graph/memory.py:92-106`) filters candidates by `label_key(node.label)` — the **label**, never an
alias, never the candidate's provenance. So candidates can be widened without widening what resolves,
and that is a property of where the comparison is written rather than of a prompt.

**Candidate counts under label + alias whole-word matching, measured:**

| query | candidates | exact label matches | today |
|---|---|---|---|
| `mozart` | 5 | 0 | refuses |
| `dolly` | 1 | 0 | refuses |
| `beethoven` | 1 | 0 | refuses |
| `chopin` | 1 | 0 | refuses |
| `brahms` | 1 | 0 | refuses |
| `schumann` | 2 | 0 | refuses |
| `liszt` | 3 | 0 | refuses |
| `bach` | 14 | 0 | refuses |
| `r&b` | 6 | 0 | refuses |
| `black` | 9 | 0 | refuses (adv_009) |
| `metal` | 34 | 0 | refuses (adv_008) |
| `john` | 42 | 0 | refuses |
| `music` | 235 | 0 | refuses |
| `big band` | 2 | 2 | ambiguous, refuses (adv_020) |
| `roy orbison` | 1 | 1 | **resolves** |
| `james brown` | 1 | 1 | **resolves** |

**The offer list is noisy, and the noise is measurable rather than hypothetical.** `mozart` reaches five
nodes: the three real Mozarts by label, plus **Timbaland** (alias "Mozart Timadeas") and **Samuel
Wesley** (alias "English Mozart"). A single-character query reaches four nodes through tokenised
initials — `x` matches "F. X. Mozart", "X" (DMX), "No F X" and "X Tina". Across the corpus: 54 aliases
contain non-Latin characters, 19 normalise to two characters or fewer.

**Alias collisions, measured:** 37 aliases equal a *different* node's label under `label_key`
(`jazz rock` is both a label and an alias of `jazz fusion`; `heavy metal` is an alias of
`traditional heavy metal`), and 27 aliases are claimed by two or more nodes (`fusion` by two, `rap` by
three, `electro funk` by four). Every one of those is a reason an alias may only ever produce an offer.

**Exposure on the eval sets.** Gold: **all 43 case names exact-resolve on v0.10.0** — zero drift risk.
Adversarial: three of 22 cases are touched, and all three expect `refusal: true` today — `adv_008`
(`metal`, 34 candidates), `adv_009` (`black`, 9), `adv_020` (`big band`, ambiguous, 2). D3 is what keeps
all three scored exactly as they are scored now.

**The live suite.** `live_cases()` returns **63** cases (43 gold + 20 adversarial).
`eval/thresholds.json` records `case_count: 56`, so a live run today prints `NOT GATED` and exits 0.
That single number is what step 7 exists to replace.

**The old held-out set.** Manifest: `heldout_v1`, sealed 2026-08-14, pinned artifact **0.5.0**, 10 cases,
2 refusals, shapes `origins 6 / descendants 2 / path 2`. Run count **1** (2026-08-24, 10/10).
`make heldout-check` reports `artifact-pin-moved` plus `claims-diverged` on `heldout_v1_004` and
`heldout_v1_005`. Nothing has been opened or re-sealed.

**Gold set shape distribution, for sizing the new draw:** origins 28, path 6, descendants 4, teachers 2,
teaching_path 2, students 1, of 43; 6 refusals. Teaching is **5 of 43** cases, about 12%.

## 3. What the code reading found — every trap, with its location

### 3.1 Traps that would silently pass the wrong thing

1. **`exact_matches` must keep comparing labels only** (`graph/memory.py:105`). If a later edit compares
   aliases there, every alias becomes a silent resolution and this phase has delivered the opposite of
   its purpose. A test locks it.
2. **`heldout_draw.py:220` accepts a drawn case by `store.search(name)[0].id`.** Changing what `search`
   returns, or in what order, changes which cases a draw accepts. **This is an independent reason the
   draw goes first**, beyond his decision that it goes first: draw on today's resolver, then change the
   resolver, then check.
3. **`heldout_draw` draws influence only.** Every `store.neighbors` call in it uses the default
   `predicates=INFLUENCE_ONLY`, so a draw on v0.10.0 contains **zero teaching cases** and cannot test
   generalisation on the capability phase 7.6 just shipped. Worse, `_claim`
   (`heldout_draw.py:139-165`) hardcodes `"wikidata_statement": f"{subject} P737 {object}"`, so
   admitting teaching without fixing that line writes a **false citation string** into a sealed set —
   the gold set records teaching as `Q254 P1066 Q106641`. See U1; nothing is drawn until he rules.
4. **`seal()` writes a fixed path** (`eval/heldout.py:49-50`, `207-208`). Re-sealing **overwrites**
   `heldout_v1.json.enc`. `.claude/rules/heldout-set.md` forbids re-sealing to make a check pass; this
   is a deliberate replacement rather than a re-seal, and D1 keeps that distinction visible in the
   filenames instead of destroying the evidence.
5. **The offer cannot be computed from the plan.** `PlanStep.arguments` is model-authored and explicitly
   optional ("Leave out an argument you cannot know yet", `agent/plan.py:81`), and `loop.py`'s own
   docstring says that if a change makes the loop branch on `plan.steps`, "the plan has stopped being a
   proposal and that change is wrong". So no offer logic reads the plan.
6. **Invariant 4 forbids the loop knowing what a tool does.** The offer therefore rides a *generic*
   `ToolResult` field, harvested the way `proposals` already is. A loop that special-cases
   `resolve_node` has broken the seam this project is built on.
7. **`refusal_accuracy` is computed from `(expected_refusal, refused)` pairs** (`eval/metrics.py:263`),
   and `refused` is set by the runner on the `Refused` event (`eval/runner.py:178`). If an offer
   replaced a refusal, three adversarial cases would flip and the gate would silently start measuring a
   different quantity. D3 forecloses that.
8. **`tests/test_graph_store.py` asserts on `search` results** (lines 83-86, 189-217, 327), including the
   label set for `search("jazz")`. Alias indexing changes those sets. They are updated deliberately,
   from measurement, with the reason in the test.
9. **`test_resolution_stability.py` does not cover held-out names, and must not.** Its inputs are the
   gold, tour and adversarial datasets plus the chips and README. So after the resolver change the
   **only** safe detector of held-out drift is `make heldout-check`, read as codes. That check is a step,
   not an afterthought (step 6).
10. **Keep the alias index separate from `_by_name`.** `_by_name` feeds `search`'s *exact* bucket, and
    `exact_matches` counts zero/one/two off the candidate list to decide resolve-versus-ambiguous. Merging
    aliases into that dict risks changing the arithmetic that produces "ambiguous". A second dict costs
    nothing and keeps the exact path untouched.
11. **Single-character and non-Latin aliases produce nonsense offers** (the `x` case). D5 rules on it.
12. **A new event costs one line in `api/app.py`** (`EVENT_NAMES`, line 63) because `render` is generic
    over `asdict`. Keep the `Offer` payload plain dataclasses so it stays one line. A frame needing a
    handler there means `api` has grown logic.

### 3.2 The count map — what moves this phase and what must not

| thing | today | after |
|---|---|---|
| artifact pin | 0.10.0 | **unchanged** — this phase cuts no artifact |
| `thresholds.json` `case_count` | 56 | **63**, at step 7, from the new noise floor |
| `eval/noise_floor.json` | measured 2026-09-07, 56 cases | re-measured at step 7, 63 cases |
| held-out set | `heldout_v1`, pin 0.5.0, run count 1 | `heldout_v2`, pin 0.10.0, run count 0 then 1 |
| deployed site | v0.7.1 corpus, pre-7.6 code | v0.10.0 corpus, 7.6 + 7.7 code, at step 8 |

## 4. Decisions

### 4.1 Taken by him, 2026-09-11

- A partial or alias match is **offered**, never resolved. The human chooses.
- A new held-out set is this phase's **first** task, drawn by him from his own seed.
- **One** live re-baseline and **one** deploy, covering 7.6 and 7.7 together, at this phase's close.
- Phase 7.5 resumes at step 5 (the launch post) after this phase, not before.

### 4.2 Taken by this plan, open to his veto at approval

- **D1. HIS DECISION, 2026-09-12: the old sealed set is RETIRED, not kept beside the new one.** The
  code is routed to `heldout_v2` by name (two constants in `eval/heldout.py`, two strings in
  `heldout_draw.py`, one in `heldout_run.py`, the filename list in `tests/test_heldout_seal.py`, and ids
  `heldout_v2_001..010`), and `heldout_v1.json.enc` plus `heldout_v1.manifest.json` are **deleted from
  the working tree**. His reasoning, and it is right: two sealed sets in one directory is a standing
  confusion surface — an agent checks the wrong one, a report cites the wrong run count — and the old set
  has no job left once a set drawn on the live pin exists.
  **The preservation argument I had made for keeping it is weak, and here is why.** Deleting the file
  does not destroy the ciphertext: **git keeps it permanently**, at `b9072ee` and every earlier commit.
  So the historical 10/10 result of 2026-08-24 stays auditable — the ciphertext and its manifest sha256
  are recoverable from history by anyone who ever needs them — while the working tree holds exactly one
  set. Nothing reads the v1 files programmatically; only `docs/KNOWN-GAPS.md` and two phase docs mention
  the *result*, and `test_the_committed_sealed_set_matches_its_manifest` skips when the manifest is
  absent.
  **Three things this decision does not do.** It does not rewrite history and must not — the retired
  ciphertext staying in git is the point, not a loophole. It does not delete
  `eval/results/20260824T120956Z-heldout.json`, which is a record of a measurement actually taken and is
  referenced in three docs. And **the old run count does not carry over**: `heldout_v2` starts at 0.
  `KNOWN-GAPS.md` records, in one line, that the retired set's ciphertext lives in git at `b9072ee` and
  what its manifest said (pin 0.5.0, 10 cases, 2 refusals, run count 1).
  **Sequencing matters and step 0 enforces it:** the delete, the rename and the freshly sealed `v2` land
  in **one commit**, so `main` never holds a state where the manifest is missing and the CI test quietly
  skips. A skipped seal test is "the set does not exist", which the rules call a real outstanding item
  rather than a passing state.
- **D2. Offers are produced in `graph/memory.py` and carried on a new generic `ToolResult.offers`
  field**, populated by `ResolveNode`, harvested by the loop the way `proposals` already is. Rejected
  alternative: a deterministic pre-flight over the raw query before the loop runs. It would make a bare
  "mozart" free instead of about two-tenths of a cent, and it would put a second copy of the resolution
  rule in a second place — which is the exact failure `exact_matches` was extracted to prevent
  ("a second copy of it is how a tool and the loop start disagreeing about what 'the blues' means").
  One rule, one place, one-fifth of a cent.
- **D3. An offer accompanies a refusal; it never replaces one.** The run still emits `Refused`, still
  narrates the refusal, still approves no claims. The `offer` frame rides beside it, the way
  `contested` rides beside the narration rather than inside it. Consequences, all good: `refusal_accuracy`
  and every gate keep measuring what they measured; `adv_008`, `adv_009` and `adv_020` need no
  re-authoring; the scope doc's "how are offers scored" question is answered without inventing a
  threshold. `offer` becomes a **tracked, non-gated** property with its own free-suite check.
- **D4. The candidate cap is 25 shown, all or nothing, with the total always stated.** 25 or fewer
  candidates: show every one. More than 25: show none, state the count, and ask for more of the name.
  Measured effect: `bach` shows all 14, `black` all 9, `mozart` all 5, `r&b` all 6; `metal` (34),
  `john` (42) and `music` (235) show a count and an ask. Rejected alternative: show the first N of a
  longer list. Truncating a list by label length is ranking under another name, and scope §7 forbids
  ranking; an honest count plus an ask is not ranking.
- **D5. A query token of one character matches no alias and no label.** This is what kills the `x` path,
  and it costs nothing real: no musician or genre in this corpus is found by one letter.
- **D6. Genres get aliases too.** Same code path, no extra data, and it fixes "R&B" (6 offers) on the
  axis the site's own chips live on.
- **D7. Every offered candidate says why it was offered** — `via: "label"` or `via: "alias"` with the
  alias text. Timbaland appearing under "mozart" is then legible rather than mysterious, and it is the
  honest presentation of a noisy source.
- **D8. The frame is `offer`**, payload `{ term, candidates: [{node_id, label, kind, via, alias}],
  total, shown }`. Plain dataclasses, one line in `EVENT_NAMES`, documented in `SPEC.md` §6.
- **D9. Choosing a candidate re-asks the original question with the matched term replaced by the chosen
  exact label.** "mozart" becomes "Wolfgang Amadeus Mozart"; "who did mozart study with" becomes "who
  did Wolfgang Amadeus Mozart study with". The frame carries `term` so the substitution is deterministic
  client-side. If `term` does not occur literally in the query, the fallback is to ask the bare exact
  label. Nothing about this path resolves anything: the re-asked query resolves by exact label like any
  other.
- **D10. `_contains_words` is reused, not reimplemented.** One whole-word rule in the codebase.

### 4.3 Genuinely uncertain, named rather than smoothed

- **U1 is CLOSED — his decision, 2026-09-12: YES, the draw includes teaching.** *(Kept here with its
  reasoning rather than moved, because the argument is what a later reader needs.)*
  For: phase 7.6 shipped a whole predicate, the gold
  set gives teaching 5 of 43 cases, and a held-out set with no teaching case leaves the newest
  capability's generalisation untested. Against: it means editing `heldout_draw.py` (the `INFLUENCE_ONLY`
  defaults and the hardcoded `P737` of trap 3) immediately before drawing, and a draw is a thing you
  want boringly unchanged. **As decided**, sized to mirror gold: `STRATA` becomes
  origins 3, descendants 2, path 2, refusal 2, **teaching 1**, still summing to 10. The pool supports it
  comfortably: 545 nodes have two or more teachers, 430 have two or more students. The `P737` fix is
  required either way, because it is a latent false-citation bug whether or not it fires this week.
- **U2. The re-baseline's cost is derived, not measured.** The 2026-09-07 baseline was $2.61 and about
  2.4 hours for five runs of 56 cases. At the same per-case rate, five runs of 63 cases is about
  **$2.94 and 2.7 hours**. That is arithmetic on a measured number, not a measurement, and 7.6 changed
  the corpus under it — a larger corpus means longer traversals, so the real figure may come in above
  it. The circuit breaker, not the estimate, is what bounds it.
- **U3. Whether any held-out case's resolution drifts when the resolver widens.** It should not — nothing
  that resolves today resolves differently — but the held-out names are invisible to the stability test
  by design, so the claim is only checkable through `make heldout-check`'s codes at step 6. If it fires,
  that is a finding to report and his decision to rule on, not something to fix by re-drawing.
- **U4 is CLOSED — his decision, 2026-09-12: YES, run it once at this freeze.** The rules permit one run
  at a freeze, the set will be brand new and untuned-against, so a run is legitimate and cheap (about
  nine cents, measured 2026-08-24).
  It runs **once, after step 7's re-baseline**, and is reported as run count 1 with the count beside it
  every time it is quoted. Until it runs, every report says generalisation is **untested** on this corpus
  rather than passed. If anything is tuned in response to what it says, the set is dead and that has to
  be said out loud rather than worked around.

## 5. Explicitly not in this phase

- **Any automatic resolution beyond an exact label.** Not for a unique partial match, not for a unique
  alias, not for a "confident" case. This is the decision the phase exists to hold.
- **Edit-distance or fuzzy matching.** Phase 6.5 rejected it with a measurement.
- **Ranking, scoring, autocomplete, or a search page.** This is resolution, not search.
- **A new corpus, a new predicate, a new artifact, or a new tool beyond what resolution needs.**
- **Re-authoring any adversarial or gold case.** D3 is what makes that unnecessary; if it turns out to be
  necessary, that is a finding and a decision, not a step.
- **Reading, decrypting, regenerating or re-sealing the sealed held-out set, old or new.**
- **The launch post.** It is phase 7.5 step 5 and resumes after this phase.

## 6. The one-way doors this phase touches

- **Invariant 1, claims first.** An offer carries no claims and cannot become one: it is emitted beside a
  refusal, on a run where the gate approved nothing. A test asserts an offer run has zero approved claims.
- **Invariant 4, the agent-to-data tool contract.** Satisfied by a generic `ToolResult.offers` field. The
  loop harvests it without knowing which tool produced it, exactly as it harvests `proposals`. No
  tool-specific branch enters the loop.
- **Invariant 9, streaming.** One additive frame, one line in `EVENT_NAMES`, documented in `SPEC.md` §6.
- **The resolution door named in scope §6.** "Grounded" meeting "about the right thing". This phase
  widens what is *considered* and leaves exactly two paths to *resolving*.

## 7. Steps

### Step 0 — The new held-out set, drawn by him — [done]

**He runs every command in this step.** An agent may run `make heldout-verify`, read
`make heldout-check` output, and read this doc. Nothing else.

0a. Decisions taken: U1 yes, D1 retire-and-rename, U4 run once. Nothing left to rule on here.
0b. Fix `heldout_draw.py`'s predicate defaults and the hardcoded `P737` in `_claim`, add
    the `teaching` stratum, and prove it in `tests/test_heldout_draw.py`, which draws from the **real
    pinned artifact using three published test seeds** — so the modified draw is provable end to end
    without his seed and without producing his set. A committed seed is the opposite of held out, and
    those seeds must never be the one he uses.
0c. Apply D1: route every path and id to `heldout_v2` (two constants, three strings, the id prefix, the
    `tests/test_heldout_seal.py` filename list) and stage the deletion of `heldout_v1.json.enc` and
    `heldout_v1.manifest.json`. Add the one-line retirement note to `KNOWN-GAPS.md`.
0d. `make check` green before a single real case exists.
0e. He draws, seals, shreds, verifies, checks, and commits. The exact sequence is in §7.0.1.
0f. Record in this doc: the manifest's published counts and strata, the pin, and **run count 0**.

**Done when:** `heldout_v2.json.enc` and its manifest are committed **in the same commit that deletes the
v1 pair**, `make heldout-verify` matches, `make heldout-check` reports no problems on the v0.10.0 pin,
`test_the_committed_sealed_set_matches_its_manifest` runs rather than skips, and no agent has read a case.

#### 0.1 As built, 2026-09-12 — steps 0b through 0f, complete

**The code half, then his draw, then the seal. Step 0 is closed.** `make check` green after it:
**1,721 Python passed, 1 skipped, 448 frontend**, free gates **4 passed / 0 failed / 2 N/A of six**,
unchanged. The one skip is `test_the_committed_sealed_set_matches_its_manifest`, which now points at a
`heldout_v2` manifest that does not exist yet — the rules call that skip a real outstanding item rather
than a passing state, and it is exactly the state step 0e closes.

**A trap the plan did not have, found while building it, and it is the important one.** §3.1 trap 3 said
`heldout_draw` draws influence only. **So does the validator.** `heldout.check_against_corpus` reaches
`_corpus_edges`, which read every direction with the default `INFLUENCE_ONLY`, so a teaching case would
have been compared against the node's *influences*, reported `claims-diverged` and `refusal-flipped`
while being entirely correct — and a false alarm on a sealed set is undebuggable without opening it and
destroying it. This is the **same defect** that module's own docstring records from 2026-08-14, one layer
deeper: there the *direction* was assumed, here the *predicate* was. Fixed with the shape `teachers`,
which is the gold set's vocabulary (`gold.SHAPE_TOOL`) so the two sets stay comparable.

**A second trap, and it would have sealed a false expectation.** **The refusal stratum was unsafe at
v0.10.0.** It selected a node with no influence parents, but since phase 7.6 an influence question also
asks `get_teachers` (D5), so a drawn "refusal" whose subject has a teacher is answerable and its
`expected_refusal` would assert a refusal the system is right not to make. The refusal pool now excludes
any node carrying a teaching edge in **either** direction. Measured: the pool goes 614 → 600 excluding
teachers, → **597** excluding students as well; the conservative rule was taken because 17 candidates out
of 614 is not a cost worth reasoning about.

**As built, against the plan:**
- `STRATA` is origins 3, descendants 2, path 2, refusal 2, **teaching 1**, summing to 10 as before.
  Teaching drew from a pool of **545** nodes with two or more teachers.
- `_claim` derives the Wikidata property from the predicate (`STATEMENT_PROPERTY`), so teaching cases
  cite **P1066**. It wrote `P737` for every edge before today.
- Every path and id is routed to `heldout_v2`; `heldout_v1.json.enc` and `heldout_v1.manifest.json`
  are staged for deletion and land with the sealed v2 in one commit, per D1.
- **`TEACHING_ONLY` is defined locally in both `heldout.py` and `heldout_draw.py`** rather than promoted
  into `graph/schema.py`. That is this repo's existing convention for this constant —
  `agent/tools.py:43` and `eval/slices.py:210` each define their own — and the validator must not import
  the authoring tool. Promoting it would have meant editing two modules this phase does not touch.
- Four new tests: the teaching stratum's count, that a teaching case asks about **study** and never
  influence and claims only `studied_with`, that every claim cites the property its predicate actually
  uses (with `P1066` asserted as exercised rather than merely defined), and the refusal stratum's
  teaching exclusion in both directions. `tests/test_heldout_draw.py` draws from the real pinned artifact
  with three **published** seeds, so all of it is proved without his seed and without producing his set.

**Steps 0e and 0f, 2026-09-12 — he drew, sealed, shredded, verified and checked it. Published counts, the
only thing the manifest discloses and deliberately so:**

- `heldout_v2`, sealed **2026-09-12**, artifact pin **0.10.0**, cipher `aes-256-cbc pbkdf2 sha256 600000`.
- **10 cases, 2 refusals.** Shapes `descendants 2, origins 5, path 2, teachers 1`.
  **`origins` reads 5 rather than 3 and that is correct**: `_simple_case` labels every non-descendants
  case `origins`, so the two refusal-stratum cases are origins questions the graph declines. 3 origins +
  2 refusals = 5, and the separate `refusal_count` is the cross-check. **The `teachers` slot drew**, which
  was the one thing that could have come back silently empty.
- `sha256_ciphertext e30c6977bc9b7da2de9eb227241ce49f77de46af80443dd29f2ecb01b693ae2c`,
  `sha256_plaintext db4266a54ab56371699aca036aa2f6aba2320e25a3f4f140ca670d1ea715f2cc`.
- **`make heldout-verify`: matches its manifest** (no key, hash comparison only).
  **`make heldout-check`: "sealed set still agrees with artifact 0.10.0" — zero findings.**
- **The plaintext was shredded and confirmed gone.** The set is fully usable — both `heldout-check` and
  `eval-heldout` decrypt in memory and write no plaintext — and recoverable two ways, from the key plus
  the ciphertext, or from his seed plus the pinned artifact, since the draw is deterministic.
- **Run count 0.** `make check` after sealing: **1,722 Python passed, 0 skipped**, 448 frontend, free gates
  4 passed / 0 failed / 2 N/A of six. `test_the_committed_sealed_set_matches_its_manifest` **runs rather
  than skips**, which closes the outstanding item that skip represented.
- **No agent read a case, drafted one, suggested a subject, or asked about the seed.** The only agent-side
  inputs to this step were the two safe commands' output.

#### 7.0.1 The exact command sequence, one line at a time

Given to him at approval, and repeated here because it is the part that is easy to get wrong once a year.

1. `ls ~/.config/musical-mycelium/heldout.key`
   — the key must already exist. **Do not run `make heldout-key`**; it refuses to overwrite, and that
   refusal is not to be worked around. If the key is gone, the old set can never be opened again and
   that is a decision to stop and think about, not to route around.
2. `make heldout-draw SEED='<something only you know>' OUT=~/heldout_v2.json`
   — the seed is the whole mechanism. Do not commit it, do not paste it into a chat session, and be
   aware it lands in shell history. The draw prints counts only, never a case.
3. `make heldout-seal PLAINTEXT=~/heldout_v2.json`
4. `shred -u ~/heldout_v2.json`
5. `make heldout-verify`
6. `make heldout-check`
7. `git add -A && git status` then the commit he runs himself.

### Step 1 — Guards before anything moves

The locks that make the rest of the phase safe to build, written before the behaviour changes.

- A test asserting `exact_matches` compares labels only, with an alias deliberately equal to the query.
- A test asserting a node whose alias equals **another** node's label still resolves to the label owner
  (37 real instances; `heavy metal` and `big band` are the sharp ones).
- Record the step-2 "before" numbers from §2 in a test fixture so the candidate counts are asserted
  rather than remembered.

**Done when:** the new tests pass against unchanged behaviour. A guard that passes only after the
feature lands was never a guard.

### Step 2 — The alias index and candidate generation

`graph/memory.py`: a second index, alias-normalised to nodes, kept out of `_by_name` (trap 10). A new
`offer_candidates(store, name)` returning ordered candidates with their `via`/`alias` provenance, the
D4 cap, and the D5 one-character rule. `search` gains alias candidates; `exact_matches` is untouched.

**Done when:** the measured table in §2 is reproduced by tests, `test_resolution_stability.py` is green
against the v0.7.1 snapshot with `RESOLUTION_CHANGES` still empty, and the updated
`tests/test_graph_store.py` expectations each carry their reason.

### Step 3 — `ToolResult.offers`, the tool, and the loop

`agent/tools.py`: `ResolveNode` populates `offers` when nothing resolved. `agent/loop.py`: a generic
harvest and an `Offer` event emitted beside `Refused`, per D3. No tool-specific branch, no read of the
plan.

**Done when:** an offer run emits `refused` and `offer` and approves zero claims; the generic harvest is
proved **behaviourally** by a fake tool in the test registry that is not `resolve_node` and whose offers
still reach the frame (a grep for the tool name would be the wrong test — `loop.py:122` legitimately names
it in a comment about keeping tool names out of the system prompt); the three refusal reasons are
unchanged.

### Step 4 — The wire contract

One line in `api/app.py:EVENT_NAMES`, the `SPEC.md` §6 amendment with the frame documented and dated, and
a new `web/src/fixtures/*.sse` capture so the frontend tests run on a real frame rather than a hand-typed
one.

**Done when:** `web/src/contract.test.ts` sees the frame in a captured stream and `SPEC.md` §6 describes
it.

### Step 5 — The frontend

Offer rendering as clickable choices in `StepPanel`, the D9 re-ask, the D7 "why" line, and the D4
count-and-ask state for a query too broad to offer. Refusal styling stays a heading-wording modifier
(`StepPanel.tsx:12-22`); an offer is not a new colour.

**Done when:** it works in the running app against the local stub for "mozart", "dolly", "r&b", "bach"
and "music", with a hand check recorded here.

### Step 6 — Evals, free tier only, and the held-out check

The free suite, the new tracked `offer` property, proof that the refusal metrics and all six gate
definitions are untouched, and then `make heldout-verify` and `make heldout-check` on the **new** set
after the resolver change (trap 9, U3).

**Done when:** free gates read 4 passed / 0 failed / 2 N/A of six; `heldout-check` is clean or its codes
are reported to him as a finding.

### Step 7 — The ONE live re-baseline. SPENDS MONEY

Five identical runs of the 63-case live set behind `confirm_spend`, about $2.94 and 2.7 hours (U2).
Re-measure `eval/noise_floor.json`, rewrite `eval/thresholds.json` with `case_count: 63` and every bound
carrying its measured values, **check the per-case data before writing any bound off an aggregate** (a
0.0pp spread is a reason to ask what is constant — it has been a single case failing identically twice in
this project already), then the held-out run if he takes U4.

**Done when:** the six gates hold on a live run that no longer prints `NOT GATED`, and the exclusions are
still exactly `gold_v0_1_020` and nothing else.

### Step 8 — The ONE deploy, the writeup, and the close

Deploy 7.6 + 7.7 together, verify by hand on the public URL, write
`docs/name-resolution-explained.md` in plain English, update `KNOWN-GAPS.md`, `ROADMAP.md`, the memory
router and this doc's DoD verdicts.

**Done when:** the site answers "mozart" with offers, `make check` is green, the budgets hold, and every
DoD item in §1.1 has a verdict written next to it.

## 8. Testing, and which eval metrics apply

- **Unit:** the alias index, `offer_candidates`, the cap, the one-character rule, `exact_matches`
  label-only, the alias-equals-another-label cases, `_contains_words` reuse.
- **Integration:** an offer run end to end through the loop, the SSE frame, the frontend re-ask.
- **Regression:** `test_resolution_stability.py` over gold, tour, adversarial, chips and README, with
  `RESOLUTION_CHANGES` expected to stay empty. If it does not stay empty, that is a finding and a
  decision, not a line to add.
- **Metrics that apply:** `refusal_accuracy` (must be unchanged — that is the point of D3),
  `traversal_recall`, edge groundedness, citation resolution, injection resistance,
  `contested_disclosure`, `verification_mix`. **New:** `offer` as a tracked, non-gated property.
- **Metrics that do not apply:** nothing here touches synthesis, so Tier 2 is unchanged.

## 9. Cost, and the guardrails

- **Steps 0 through 6 cost $0.** No Bedrock call, no infrastructure change, no artifact build.
- **Step 7 is the spend:** about $2.94 for five runs of 63 cases, derived from the measured $2.61 over
  56, behind `confirm_spend` with a circuit breaker sized from the estimate. RPM 10 is the binding
  constraint, not TPM; concurrency stays at 2-4 with exponential backoff.
- **The optional held-out run is about nine cents** (measured 2026-08-24).
- **Step 8 changes no always-on resource.** No VPC, no NAT, no provisioned concurrency, no managed
  database. Log retention stays explicit.
- **Per-visitor exposure is unchanged**, and the honest ceiling is still the token budget
  (`MAX_ACCUMULATED_TOKENS = 60_000`), not the Lambda timeout.

## 10. What happens after

Phase 7.5 resumes at step 5: the launch post, the kit in `docs/launch/`, draft, audit, step 6, then post.
Phase 8 `membership-tour` (v1.1) is scoped and sits after v1.0.
