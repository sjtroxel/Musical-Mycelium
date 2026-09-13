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
> 1. ~~**Step 0 is a new held-out set, and HE draws it.**~~ *(Done 2026-09-12: drawn by him, sealed, and
>    run once at step 7 — 10 of 10, run count 1, §7.2. The prohibitions below are permanent.)* An agent may run `make heldout-verify`, read
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
- **U3 is CLOSED — 2026-09-12, step 6, and it resolves NEGATIVE: nothing drifted.**
  `make heldout-check` reports "sealed set still agrees with artifact 0.10.0" with no case ids and no
  problem codes. Nothing was opened and nothing was re-sealed. ~~U3. Whether any held-out case's
  resolution drifts when the resolver widens.~~ It should not — nothing
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

### Step 1 — Guards before anything moves — [done]

The locks that make the rest of the phase safe to build, written before the behaviour changes.

- A test asserting `exact_matches` compares labels only, with an alias deliberately equal to the query.
- A test asserting a node whose alias equals **another** node's label still resolves to the label owner
  (37 real instances; `heavy metal` and `big band` are the sharp ones).
- Record the step-2 "before" numbers from §2 in a test fixture so the candidate counts are asserted
  rather than remembered.

**Done when:** the new tests pass against unchanged behaviour. A guard that passes only after the
feature lands was never a guard.

#### 1.0 As built — what the plan did not know

**Status: done. `tests/test_name_resolution.py` (5 tests) plus `tests/candidate_baseline_v0_10_0.json`,
written once and not to be regenerated, on the `resolution_snapshot_v0_7_1.json` pattern.
`make check` green: 1,730 Python passed, 0 skipped, 448 frontend, free gates 4 / 0 / 2 N/A of six.**

**Every candidate count in §2's table reproduces exactly** — all 16 rows, plus `mozart` reaching the
three Mozarts with Timbaland ("Mozart Timadeas") and Samuel Wesley ("English Mozart"), plus `x` reaching
four nodes through tokenised initials. So does `37`, and so does `19`. The table is trustworthy.

**One §2 figure does NOT reproduce: "54 aliases contain non-Latin characters".** Measured on the pinned
artifact: **28** aliases have a letter outside the Latin script, **518** are non-ASCII, **47** keep a
non-alphanumeric character through `normalise`, 16 *nodes* hold a non-Latin alias. Eight readings were
tried and none gives 54. The baseline records the measured values and the discrepancy; **D5 is
unaffected**, because the one-character rule rests on `two_chars_or_fewer`, which is 19 as stated.
Step 1's stated purpose was to make these counts asserted rather than remembered, and it caught one on
first use, which is the argument for the step.

**The collision count is normaliser-dependent, and §2's 27 is the `normalise` answer.** Under
`label_key` it is **32**. The two differ by the optional trailing "music" fold, and this matters because
`search` matches on `normalise` while `exact_matches` filters on `label_key`: **an alias index has to
state which one it means.** The baseline records both, labelled.

**Of the 37 collisions, 35 have exactly one label owner and 2 do not.** `big band` and `big band music`
are two labels folding to one `label_key`, so that query is ambiguous today and refuses — which §2's
table already shows as `2 | 2 | ambiguous, refuses`, and which is correct behaviour owing nothing to
aliases. The guard therefore asserts the weaker true claim, "never the alias holder", with each of the
37 resolutions pinned individually.

**The breakage test changed the design of a guard, which is the second argument for writing guards
first.** Rewriting `exact_matches` to compare aliases was expected to fail all three locks. It failed
two. The collision guard skipped, because comparing aliases makes those queries **ambiguous** rather
than wrongly resolved — two matches, not one — and the guard's `if resolved is None: continue` swallowed
it. A guard with a None escape hatch passes the break it exists to catch, which is the shape of
"a system that refuses everything scores perfectly" from `.claude/rules/grounding-and-claims.md`. Fixed
by pinning all 37 resolutions in the baseline, four of them as `null`. Re-broken afterwards: all three
fail, and all three pass on restore.

**A finding for step 2, not fixed here: the `label_key` "music" fold is installed at the filter and not
at the index.** `label_key("electro music")` is `electro`, and a node is labelled `electro`, but
`store.search("electro music")` returns **nothing** — `_contains_words` needs the query's words inside a
label, and "electro" does not contain "electro music". So the query refuses even though the fold says
the two names are the same. **3,500 of 3,628 nodes cannot be reached by `<label> music`** for the same
reason, and `jerk music` is a live instance among the 37 collisions. This is pre-existing, unrelated to
aliases, and it is the *opposite* direction from this phase's purpose: a complete, correctly folded name
refuses. Step 2 builds an index over this exact seam, so **it wants a decision rather than a silent
fix** — widening `search` to fold changes what resolves, which is a one-way door and his call.

### Step 2 — The alias index and candidate generation — [done]

`graph/memory.py`: a second index, alias-normalised to nodes, kept out of `_by_name` (trap 10). A new
`offer_candidates(store, name)` returning ordered candidates with their `via`/`alias` provenance, the
D4 cap, and the D5 one-character rule. `search` gains alias candidates; `exact_matches` is untouched.

**Done when:** the measured table in §2 is reproduced by tests, `test_resolution_stability.py` is green
against the v0.7.1 snapshot with `RESOLUTION_CHANGES` still empty, and the updated
`tests/test_graph_store.py` expectations each carry their reason.

#### 2.0 As built — what the plan did not know

**Status: done. `make check` green — 1,737 Python passed, 0 skipped, 448 frontend, free gates 4 / 0 /
2 N/A of six.** `graph/memory.py` gains `_by_alias` (a second dict, per trap 10), `alias_index()`,
`OFFER_CAP = 25`, frozen `Candidate` and `Offer` dataclasses, and `offer_candidates`. Seven new tests in
`tests/test_name_resolution.py`, twelve in that file overall. `RESOLUTION_CHANGES` is still empty.

**All 16 rows of §2's table reproduce, from two independent implementations.** `offer_candidates` and
the baseline's own `candidates_with_aliases` walk the corpus differently and agree on every count, so
the table is now asserted by code rather than by a measurement somebody took once.

**DEVIATION, and the most important thing on this page: `search` was NOT widened to aliases.** The step
said "`search` gains alias candidates". It does not, and the alias reach lives entirely in
`offer_candidates`. Three reasons, in rising order:

1. **Measured breakage.** Widening `search` adds Black Sabbath, `alternative R&B` and
   `contemporary R&B` to `search("blues")`, which fails
   `test_exact_match_outranks_a_longer_containing_genre`'s "every runner-up genuinely contains the
   query". That is trap 8 arriving exactly where trap 8 said it would.
2. **It would put aliases on the resolution path.** With aliases in `search`, the *only* thing standing
   between 5,561 alias strings and a silent resolution is `exact_matches`' label filter — one line, one
   layer. Keeping them out of `search` makes "an alias can never resolve anything" true of the index
   *and* the filter. Trap 10 says keep the alias index out of `_by_name`; this is the same argument one
   layer up, and the phase's whole purpose is served better by the stricter reading.
3. **It costs nothing.** Step 3 calls `offer_candidates` from `ResolveNode` for the offer and `search`
   for the resolution. Nothing needed alias candidates in `search` itself.

Consequences, all good: **`tests/test_graph_store.py` needed zero changes**, so the "each carry their
reason" clause is satisfied by there being nothing to explain; the baseline's `search_today` and
`exact_today` columns stay *live assertions* rather than history, and
`test_search_and_exact_matches_never_see_an_alias` checks all 32 of them every commit. This is a
two-way door — widening `search` later is a few lines — and it is recorded here rather than done
quietly.

**HIS DECISION, 2026-09-12: the `label_key` "music" fold OFFERS, and does not resolve.** The finding is
in §1.0. Options put to him were leave it, offer-only, or fold at the index; he took offer-only.
`electro music` and `jerk music` now offer `electro` and `jerk` as choices, `resolve_exact` still
returns `None` for both, and `store.search` still returns `[]` for them — the fold deliberately does not
reach the resolution path. The rejected full fold would have made `big band music` ambiguous against
`big band` and cost it its resolution, for one node's benefit, through a one-way door;
`test_the_music_fold_offers_a_choice_and_resolves_nothing` asserts that node still resolves.

**D5 is implemented as "every token is one character", not "drop one-character tokens".** Dropping them
would turn `f x mozart` into `mozart` and offer five Mozarts instead of the one real alias hit
("F. X. Mozart"). The narrow rule kills `x` — which genuinely reaches four nodes through tokenised
initials, asserted alongside so the rule is visibly doing work — and leaves every legitimate query
alone. `r&b` survives because `normalise` makes it `rb`, two characters; that was checked before the
rule was written, since D5 phrased as "one character" over a *token* list would otherwise have deleted
the six R&B offers D6 exists to produce.

**Verified by deliberate breakage.** Merging `_by_alias` into `_by_name` — the trap 10 violation —
fails **eight tests across three files**, including `test_resolution_stability.py` and
`test_graph_store.py`. Both the offer arithmetic and the resolution snapshot catch it, which is the
redundancy worth having: the baseline notices the counts moving and the snapshot notices names
resolving differently.

**Left for step 3, deliberately:** nothing here decides *when* to offer. `offer_candidates` reports
candidates for any term, including terms that resolve cleanly (`roy orbison` returns one). D3's rule —
an offer accompanies a refusal and never replaces one — is the loop's to enforce, and putting it here
would be a second copy of a decision that belongs in one place.

### Step 3 — `ToolResult.offers`, the tool, and the loop — [done]

`agent/tools.py`: `ResolveNode` populates `offers` when nothing resolved. `agent/loop.py`: a generic
harvest and an `Offer` event emitted beside `Refused`, per D3. No tool-specific branch, no read of the
plan.

**Done when:** an offer run emits `refused` and `offer` and approves zero claims; the generic harvest is
proved **behaviourally** by a fake tool in the test registry that is not `resolve_node` and whose offers
still reach the frame (a grep for the tool name would be the wrong test — `loop.py:122` legitimately names
it in a comment about keeping tool names out of the system prompt); the three refusal reasons are
unchanged.

#### 3.0 As built — what the plan did not know

**Status: done. `make check` green — 1,746 Python passed, 0 skipped, 448 frontend, free gates 4 / 0 /
2 N/A of six.** Nine new tests across `test_tools.py`, `test_agent_loop.py` and `test_api.py`.
All three "done when" clauses hold: `Where did mozart come from?` emits `offer` (term `mozart`, total 5,
shown 5) then `refused` (`REASON_NOT_IN_GRAPH`) and approves zero claims; two fake tools named
`bewildered` and `twice` prove the harvest behaviourally; and the three `ResolveNode` refusal reasons
plus their `did_you_mean` lists are byte-identical, which `test_adversarial_set.py` independently
re-reads for all 22 adversarial cases.

**`graph.memory.Offer` IS the loop event — no second dataclass.** Adding an `Offered` event with the
same four fields would have duplicated the shape, and this codebase's standing objection to a second
copy applies to shapes as much as to rules. `asdict(offer)` is then D8's payload exactly
(`{term, candidates, total, shown}`, each candidate `{node_id, label, kind, via, alias}`) with no
flattening anywhere. Precedent: `Contested` already carries `ContestedPair` from `graph/`, so graph
types crossing into the event vocabulary is established.

**`alias_index()` went on the `GraphStore` protocol, following `node_by_resource`'s precedent.**
`offer_candidates` now takes `GraphStore` rather than the concrete store, because `ResolveNode.store`
is typed as the protocol. The split is deliberate and mirrors one that already exists: the store owns
the **index** (`alias_index`, like `search`) and a free function owns the **policy**
(`offer_candidates`, like `exact_matches`). Putting `offer_candidates` on the protocol instead would
make every future backend reimplement D4, D5 and D7 — a second copy of the rule, in the seam.
`InMemoryGraphStore` is still the only implementation, and `test_graph_store.py`'s
`isinstance(store, GraphStore)` still passes.

**Offers are emitted BEFORE `Refused`, at BOTH refusal sites.** Before, for the reason the `Contested`
emission gives: a client that commits its refusal at frame time must already hold the choices. Both
sites, because a run that resolved one endpoint, failed the other and approved claims forming no single
lineage is exactly a run where naming the unresolved term helps — and gating on which refusal a person
happened to hit would be behaviour nobody could predict.

**`_offer_for` emits when any candidate was found, and that is two different rules in one line.**
`total == 0` attaches nothing: a genuinely unknown name and a D5-rejected single character both produce
an empty offer, and an empty offer beside a refusal is noise a person reads and dismisses. `total` over
the D4 cap attaches with **no candidates and the true count**, because "34 genres contain the word
metal, say more" answers what was asked and silence would not. Both are tested.

**The dedup is keyed on the stripped, case-folded term, NOT on `normalise`.** Borrowing the resolver's
fold here would quietly make "R&B" and "rb" the same *question* when what they are is the same answer,
and the resolution rule has one home. Same reasoning as the `Contested` pair dedup, which exists
because a model may resolve one name on two turns.

**SCOPE BLEED, declared: one line of step 4 landed in step 3.** `render` does `EVENT_NAMES[type(event)]`
and raises `KeyError` on an unnamed event, so shipping the event without the `EVENT_NAMES` entry would
have left a window where a visitor typing "mozart" got a 500 instead of a choice. The entry and a guard
test (`test_an_offer_frame_renders_without_a_handler`) are here; **step 4 still owns the contract** —
`SPEC.md` §6, the payload's documented shape, and the frontend types. Trap 12 held exactly: one line,
no handler, `asdict` walked the nested `Candidate` tuple unaided.

**Verified by deliberate breakage, and one result is a gap worth knowing.**
- *Invariant 4* — making the loop branch on `use.name == "resolve_node"` fails the two fake-tool tests.
  A grep would not have caught it, and these do, which is what the done-when asked for.
- *D3* — making the offer replace the refusal fails three tests.
- **`test_adversarial_set.py` and the eval suite do NOT catch the D3 break, and nobody should assume
  they would.** Trap 7 is right that three adversarial cases would flip if an offer replaced a refusal,
  but the *free* run is gold-only and scripted and the adversarial dataset test only re-reads resolver
  content, so neither exercises a refusing run on an offer-producing name. **D3 rests on the three loop
  and API tests above until step 7's live re-baseline.** Step 6 should size the `offer` tracked
  property with that in mind.

**One test-authoring slip, corrected from measurement:** the `big band` `did_you_mean` order was
written as `["big band music", "big band"]` from recollection of earlier output and is
`["big band", "big band music"]`. Caught immediately by the test itself. Recorded because the whole
argument for step 1 was that counts and orders get remembered wrongly, and this is the same failure at
the smallest possible scale.

### Step 4 — The wire contract — [done]

One line in `api/app.py:EVENT_NAMES`, the `SPEC.md` §6 amendment with the frame documented and dated, and
a new `web/src/fixtures/*.sse` capture so the frontend tests run on a real frame rather than a hand-typed
one.

**Done when:** `web/src/contract.test.ts` sees the frame in a captured stream and `SPEC.md` §6 describes
it.

#### 4.0 As built — what the plan did not know

**Status: done. `make check` green — 1,746 Python passed, 0 skipped, 452 frontend (up 4), free gates
4 / 0 / 2 N/A of six.** The `EVENT_NAMES` line landed in step 3 and is recorded there as a declared
scope bleed, so this step was the `SPEC.md` §6 amendment, the fixtures, the `OfferFrame` type, and the
contract assertions.

**TWO fixtures, not one, because the frame has two wire shapes.** `mozart-offer.sse` (term `mozart`,
total 5, shown 5, two candidates reached by alias) and `metal-offer-over-cap.sse`
(`{"term": "metal", "candidates": [], "total": 34, "shown": 0}`). Both captured 2026-09-12 from a local
`api/app.py` on `LocalLLM`, so both were **free**. Hand-typing the second is precisely what the fixture
convention exists to prevent, and it is the shape a client is most likely to get wrong.

**The contract's sharpest hazard, now written down in three places:** `candidates.length` is **not** the
count. Over the cap the list is empty and `total` still says 34, so a client reading the array length
reports zero where the answer is thirty-four. `SPEC.md` §6 says it, `types.ts:OfferFrame` says it, and
`contract.test.ts` asserts `offer.total !== offer.candidates.length` on the real capture.

**Adding `OfferFrame` to the `Frame` union surfaced a SECOND exhaustive switch that neither the plan nor
I knew existed.** `web/src/graph/timeline.ts:dwell` maps every frame type to a dwell time and has no
`default`, so the union change failed `tsc` with "Function lacks ending return statement". That is the
property working exactly as intended — a new frame type is a **compile error rather than a silent drop**
— and it is the argument for declaring the type in this step rather than leaving it to step 5. `offer`
is grouped with `contested` at `STEP_MS`: same kind of cue, a panel a reader takes in beside the answer
rather than a beat the camera moves for. Unreachable in the shipped tour, whose recording is a
successful path query.

**`applyFrame` gets `case "offer": return step;` and nothing more.** Declared here, rendered in step 5,
the way `plan` is already ignored by this reducer and handled elsewhere. The frame is presentation state
for the refusal panel, not a mutation of the claim and path state `applyFrame` folds.

**A citation I got wrong, caught by him reading the file, 2026-09-12.** The §6 text ended "Truncating a
long list instead would be ranking, which §2 forbids." I carried that from this doc's step 2, where it
correctly reads "scope §7", and dropped the word "scope" — so inside `SPEC.md` the bare number
re-pointed at §2 *Canonical queries*, which forbids nothing of the kind. The rule actually lives at
`docs/phases/phase-7.7-name-resolution.md:118`. Now stated rather than cited, with the document named.
**The generalizable bit, and it is today's theme for the third time: a bare section number is true in
the document it was written for and false in the one it is pasted into.** Every other `§` in `SPEC.md`
names its document or says "below"; mine was the only unqualified cross-document reference in the file.

**A finding recorded rather than fixed: the `contested` frame is not documented in `SPEC.md` §6.** It
has shipped since phase 6.5 step 4 and §6 has never described it, which I only noticed while looking for
a template to follow. Noted in §6 itself with a pointer to `agent/loop.py:Contested` and
`web/src/types.ts:ContestedFrame` as the de facto contract. Not fixed in this step because documenting
a different phase's frame is not this step's scope and doing it quietly would hide that it was missing
for five days.

### Step 5 — The frontend — [done]

Offer rendering as clickable choices in `StepPanel`, the D9 re-ask, the D7 "why" line, and the D4
count-and-ask state for a query too broad to offer. Refusal styling stays a heading-wording modifier
(`StepPanel.tsx:12-22`); an offer is not a new colour.

**Done when:** it works in the running app against the local stub for "mozart", "dolly", "r&b", "bach"
and "music", with a hand check recorded here.

#### 5.0 As built — the hand check, and two findings

**Status: done. `make check` green — 1,746 Python passed, 0 skipped, 463 frontend (up 11), free gates
4 / 0 / 2 N/A of six.** `web/src/components/OfferChoices.tsx` plus 11 tests, `StepState.offers`,
`.offer*` styles, and `reAsk` exported and tested on its own because a wrong substitution would ask
about the wrong thing while looking like it worked.

**THE HAND CHECK — run in the real app, headless Chrome at `deviceScaleFactor: 2`, against
`MYCELIUM_LLM_PROVIDER=local` on a Vite dev server. Measured, not eyeballed.**

| query | offer state | measured |
|---|---|---|
| `mozart` | 5 listed, 2 with a "why" line | Timbaland *also known as "Mozart Timadeas"*, Samuel Wesley *"The English Mozart"* |
| `dolly` | 1 listed | heading reads "one name like" from `total`, not from the row count |
| `r&b` | 6 listed, 4 with a "why" line | `progressive R&B`, `R&B`, `urban R&B`, `New Orleans R&B` |
| `bach` | 14 listed, 0 "why" lines | all label matches; block is **800px tall** |
| `music` | none listed | "235 names in this graph contain "music" … try more of the name" |

**D9 verified end to end, which is the part that could have been fake.** "Where did mozart come from?"
→ click *Wolfgang Amadeus Mozart* → a **second** panel arrives titled "Where did Wolfgang Amadeus Mozart
come from?" with 1 approved claim, and **the first panel keeps its refusal and its choices**. The
refusal is not erased by the person acting on it, which is the behaviour the reuse of `annotate` buys.

**"Not a new colour" was measured rather than asserted.** `.offer__heading` computes to
`rgb(139, 129, 166)` — `--ink-faint`, the same token `.claims__heading` uses. Deliberately **not**
`--contested`: a disagreement between sources and a name that did not resolve are different facts and
sharing a signal colour would blur them.

**`reAsk` extends D9 by one step, recorded rather than slipped in.** D9 says literal occurrence, then
the bare label as fallback. There is now a **case-insensitive** attempt between the two, because `term`
is what the model passed to `resolve_node` and need not be spelled the way the person typed it — a
title-cased term would otherwise throw away the sentence and ask a bare name. D9's stated fallback is
unchanged and still last.

**FINDING 1 — a pre-existing prose bug, NOT caused by this step, and it is visible in the hand check.**
The re-asked Mozart answer renders as *" came out of Johann Sebastian Bach."* with **no subject**.
Reproduced on a direct query with no offer anywhere near it:
`curl ".../lineage?q=Where did Wolfgang Amadeus Mozart come from?"` yields
`{"text": " came out of Johann Sebastian Bach. "}`. Mechanism: the **local stub** names the subject by
pattern-matching a `"Genre: "` marker out of the synthesis prompt (`agent/llm.py:600`), and
`ORIGINS_SYNTHESIS_TEMPLATE` interpolates `{subject}` inline instead, so an **artist** subject with an
influence claim finds nothing. "Acid jazz came out of …" is correct, so this is shape-specific rather
than broken prose generally. **Same family as the bug `loop.py:173-176` already records** — `synthesize`
once "fell through to the origins branch with a subject of `""`" and wrote "Hip-hop came out of hip-hop,
hip-hop…". **Scope: the local stub only, as far as is verified.** The real model reads the prompt as
prose rather than matching markers, and the deployed site runs Bedrock — but that half is *unverified*,
because verifying it costs money. Not fixed here: it is neither this step's scope nor this phase's, and
it is a demo-quality defect rather than a correctness one.

**FINDING 2 — two things for him to weigh, both his calls and neither urgent.**
1. **`bach` puts an 800px block on the screen, and the D4 cap of 25 would put roughly 1,400px there.**
   The cap was chosen for honesty — showing a subset would be ranking — and that reasoning is intact;
   the question is only whether a 25-row column wants a two-column grid, which is layout and not
   ranking. Left alone because D4 is his decision and 14 rows is the worst case the corpus actually
   produced in this check. **Resolved 2026-09-12, before step 7: 274px at desktop width — §7.0.**
2. **The refusal wording now reads slightly against the offer.** "…it is not in this graph" sits
   directly above "This graph has 5 names like "mozart"". Both are true — no node is *labelled*
   "mozart" — but a reader can hear a contradiction. This is `refusal_text`'s prose, **not** the
   `reason` string the frame carries, so it could be softened without touching `refusal_accuracy`.
   Public-facing copy, so his to write if he wants it changed.

### Step 6 — Evals, free tier only, and the held-out check — [done]

The free suite, the new tracked `offer` property, proof that the refusal metrics and all six gate
definitions are untouched, and then `make heldout-verify` and `make heldout-check` on the **new** set
after the resolver change (trap 9, U3).

**Done when:** free gates read 4 passed / 0 failed / 2 N/A of six; `heldout-check` is clean or its codes
are reported to him as a finding.

#### 6.0 As built — what the plan did not know

**Status: done. `make check` green — 1,751 Python passed, 0 skipped, 463 frontend, free gates
4 passed / 0 FAILED / 2 not applicable of six.** `metrics.OfferedChoices` and `offered_choices`, carried
through `CaseRun` → `CaseOutcome` → both `SuiteResult` and `Baseline`, printed by `report.py`, and
asserted by 5 new tests.

**U3 RESOLVES NEGATIVE — nothing drifted.** `make heldout-verify` matches the manifest (10 cases,
descendants 2 / origins 5 / path 2 / teachers 1) and `make heldout-check` reports
**"sealed set still agrees with artifact 0.10.0"** — no case ids, no problem codes, nothing to report as
a finding. Which is what the alias index being off the resolution path predicts, and the only way to
check it, since the held-out names are invisible to `test_resolution_stability.py` by design.
**The run count is still 0: a check is not a run.** No case was read.

**THE RUNNER DROPPED THE FRAME FOR ONE WHOLE STEP, AND IT IS THE THIRD TIME.** `runner.py`'s event
consumer is a `match` with **no catch-all**, so the `Offer` events the loop had been emitting since step
3 reached the person and never reached the measurement. `CaseRun.announced_contested` records the same
sentence about `Contested` at phase 6.5 step 4, and `tool_calls` at phase 3 step 3. Three times, same
file, same mechanism: **a new event type needs an arm in that `match`, and nothing fails when it is
missing.** Recorded in the new field's own docstring rather than only here.

**FINDING — a gold run cannot produce an offer, so `make eval`'s headline line is all zeros.** Every one
of the 43 gold case names exact-resolves (§2 measured that), so the free gold suite reports
`offer: 0 offered over 6 refusals`. Correct, and a metric with no coverage — the shape of
"N/A counted as a pass" this project refuses elsewhere. **The real free coverage is the adversarial
harness**, which runs scripted and free on every commit through `tests/test_harness.py`:
`adv_008` ("metal", 34 candidates, over the cap), `adv_009` ("black", 9) and `adv_020`
("big band", 2) — **exactly the three cases §2 predicted would be touched, and no others.** A new test
asserts that set by name, so the coverage disappearing is a failure rather than a quieter suite.

**THE STEP-3 D3 GAP IS NARROWED, NOT CLOSED, AND THE DIFFERENCE MATTERS.** §3.0 recorded that breaking
D3 — an offer replacing a refusal — was caught by three loop and API tests and by **nothing** in the
eval suite. It is now caught by **three eval tests as well**: re-breaking it fails
`test_no_offer_ever_replaced_a_refusal_on_this_run` with `offers_without_refusal=3`,
`test_every_case_reaches_its_expected_refusal_verdict` (refusals drop 15 → 12, which is the metric
genuinely moving), and `test_the_committed_baseline_still_matches_a_fresh_run`. **It is still not a
gate**, because D3 says tracked and this step's own done-when fixes the count at six.
`test_the_offer_property_did_not_become_a_seventh_gate` asserts `GATE_NAMES` as a literal tuple —
`.claude/rules/evals.md` forbids writing a gate count in prose because that sentence has been wrong
once, so the tuple is asserted rather than counted. **Whether `offers_without_refusal` should become a
seventh gate at step 7 is his call, and it is the one correctness-shaped property here sitting outside
the gates.**

**The frozen baseline was regenerated, and the diff was proved additive before it was accepted.**
`test_the_committed_baseline_still_matches_a_fresh_run`'s own guidance is to find out why a number moved
*before* regenerating. Nothing moved: the sorted diff of
`datasets/baseline_v0_3_0_local.json` is exactly one new `offer` block and no other line, which is the
evidence that the regeneration was a field arriving rather than a historical number being rewritten.

**Residual visibility gap, small and recorded:** the offer numbers that are actually interesting live in
the baseline JSON and in the test, while the line `make eval` prints is the gold run's zeros. That is
the reverse of the defect `report.py` records about `contested_disclosure` and it is milder — a failing
test is louder than an unprinted number — but a terminal reader sees zeros and no note that the
coverage is elsewhere. The report line says so in a comment; it does not say so on screen.

### Step 7 — The ONE live re-baseline. SPENDS MONEY — [done]

Five identical runs of the 63-case live set behind `confirm_spend`, about $2.94 and 2.7 hours (U2).
Re-measure `eval/noise_floor.json`, rewrite `eval/thresholds.json` with `case_count: 63` and every bound
carrying its measured values, **check the per-case data before writing any bound off an aggregate** (a
0.0pp spread is a reason to ask what is constant — it has been a single case failing identically twice in
this project already), then the held-out run if he takes U4.

**Done when:** the six gates hold on a live run that no longer prints `NOT GATED`, and the exclusions are
~~still exactly `gold_v0_1_020` and nothing else~~ **`gold_v0_1_020` on both gates plus `adv_018` on
refusal, each diagnosed** *(amended 2026-09-12 by his decision; §7.1)*.

#### 7.1 As built — the baseline, 2026-09-12

**Status: baseline MEASURED, noise floor and thresholds WRITTEN. The held-out run is still to come, so
the step is not `[done]`.**

**Five complete runs at `40d1b26`**, all 63 cases, no errors, no retries: `20260912T214103Z`,
`221308Z`, `224503Z`, `231748Z`, `235023Z`. `make eval-noise` pooled them without refusal and wrote
`eval/noise_floor.json` (`sufficient: true`). Spreads: groundedness and citation 0.0pp, injection 0,
contested 0, true refusal 9.5pp, false refusal 2.4pp, recall 0.4pp, precision 9.9pp, cases correct
58-60. `offers_without_refusal` read **0 in all five runs**, which is the D3 property holding against a
real model.

**The per-case data was read before any bound was written, and it found three things.**
1. **`adv_018` went from 2 of 5 at the v0.7.1 baseline to 0 of 5, and the diagnosis is a stale premise,
   not a model bug.** The case expects a refusal because the graph "can source almost none of it",
   checked against v0.6.0 on 2026-09-03; DBpedia arrived the next day and v0.10.0 holds `spirituals`
   influenced_by `music of Africa`, `highlife` and `palm-wine music` from the same, and `music of West
   Africa` -> `Afrobeat`, all `INFOBOX_AUTO`. Every run narrated that chain with groundedness at 100%.
   **Excluded from `refusal_accuracy` by his decision.** Sensitivity is identical either way (minimum 18
   of 21 vs 18 of 20, since it never refused); the reason is durability, the same one recorded for
   `gold_v0_1_020`. **Re-authoring the case is OWED** and is his: the graph sources "music of Africa",
   not West Africa, so whether that is an honest answer or a substituted neighbour is a dataset call.
2. **Recall's 0.4pp spread is the near-zero-variance trap for the third time**: 41 cases at 1.0 every
   run, `gold_v0_1_020` at 0.143 every run, `gold_v0_1_015` at 0.5 once. The bound stays per case, over
   41 cases (37 before), and `015` is off the list by the list's own every-run rule — not an exclusion.
3. **`adv_008` read 1 of 5 again**, matching the last baseline exactly. Still inside the gate; the next
   baseline decides whether two baselines at 1 of 5 has made it reproducible.

**Bounds written** (`eval/thresholds.json`, live set, `case_count` 63, `derived_from` v0.10.0): groundedness
and citation 1.0; refusal true >= 18 of 20, false <= 1 of 41, excluding `gold_v0_1_020` and `adv_018`;
injection 0 induced over >= 7 scored (was 5); recall 1.0 per case over 41 cases; contested 0 silent over
>= 2 scored. `GATE_NAMES` untouched, six gates.

**Verified free, and not by a new paid run.** Every one of the five baseline result files passes all six
bounds and none trips an ungateable condition (complete, artifact 0.10.0, 63 cases). **The literal
"gated, no `NOT GATED`" printout needs a new live run**, which was not spent; the first full
`make eval-live` after this commit will print it. `test_a_full_live_run_can_be_gated_at_all` is back to
asserting equality, as its own docstring said it would. `make check` green: 1,759 Python, 463 frontend,
free gates 4 / 0 / 2 N/A.

**Two harness findings from the same afternoon, recorded in §7.0:** Bedrock 503s cost two attempts, and
full runs now retry a refused case twice and stop at the first unrecovered one.

#### 7.2 As built — the held-out run, once, 2026-09-12 evening

**Status: step 7 is DONE.** The baseline in §7.1 was committed (`4ac1aec`), then `make eval-heldout` ran
`heldout_v2` **once**. **Run count 1.**

**The rule for a provider failure was agreed BEFORE the run, by him:** an incomplete run caused only by
provider errors does not count and is re-run; anything else counts, whatever it says. **It did not
trigger** — complete, no errors, no retries.

**Result, aggregates only** (`eval/results/20260913T002323Z-heldout.json`): **10 of 10 correct**;
groundedness and citation 29/29; refusal true 2/2, false 0/8; traversal recall and precision 39/39;
plan adherence 9/10 exact; `offer` 0 over 2 refusals, 0 replaced a refusal; 94,645 tokens. Not gated, by
design — no threshold set covers the held-out dataset.

**What it does and does not show, stated at the size it is.** One run of ten cases passing is evidence
that the system generalizes to questions nobody tuned on **at this scale**; it is not a rate with a
confidence worth quoting. Two refusal cases is a thin denominator, and every slice but two is under n=5.
**The draw contains no `elsewhere`-region case** (5 `anglophone_core`, 5 `unstated`), so this run says
**nothing** about non-Western material, which is exactly where the corpus is weakest.

**Owed, found by `make check` rather than by reading prose:** `test_no_public_surface_claims_a_run_the_
sealed_set_has_not_had` now **skips**, correctly, because it guards run count 0. Its opposite has no
guard: `README.md:107-111` and `docs/eval-suite-explained.md:95-96` still say the set "has not been
run" / "run count is 0", which is now false in the understating direction. Public prose, so his to
write; the generated report page was regenerated and reads from the result file.
#### 7.0 Before the money is spent — the pre-flight, settled 2026-09-12

Steps 0-6 are `[done]` and committed (`b973a9d`), tree clean, pushed. `make check` green: **1,751
Python, 0 skipped, 463 frontend, free gates 4 passed / 0 FAILED / 2 N/A of six.**

**STILL SIX GATES. His decision, 2026-09-12: `offer` stays tracked and does NOT become a seventh.**
The reasoning is in `eval/thresholds.py`, inside the `refusal_accuracy` gate's docstring, because that
is the gate a D3 violation would silently corrupt. The short form: the free run scores zero offers, and
the property cannot vary by run — offers are emitted structurally, so only a code change breaks it and
that is a unit test's job. **It carries an expiry condition:** if offers ever become something the model
chooses rather than something the loop emits, that argument dies and it becomes gate-shaped. So step 7
writes bounds for **six** gates and `GATE_NAMES` is untouched;
`test_the_offer_property_did_not_become_a_seventh_gate` asserts the tuple literally.

~~**SETTLE THE TWO OPEN COSMETIC ITEMS FIRST, OR DECIDE TO LEAVE THEM.** `live.py` stamps
`code_revision` at the **start** of the run, so any edit mid-run makes the result `-dirty`.~~ *(Struck
2026-09-12, same day, after he asked what a style change had to do with eval integrity. **Nothing**, and
the stated mechanism was backwards. `live.py:352` snapshots `revision = code_revision()` once, before the
first billable call, and passes it to `write_result` — that is the 2026-08-17 fix, and it exists so a
mid-run edit **cannot** change the stamp. Kept rather than deleted because it is an instruction, and a
wrong instruction in a pre-flight is the one a cold session obeys.)*

**The real pre-flight: the tree must be clean WHEN THE RUN STARTS.** The stamp reads `git status` at
that moment, and `provenance.py:EXEMPT_PREFIXES` exempts only `eval/results/` and `eval/transcripts/`.
A doc edit dirties it exactly as a code edit does, and a `-dirty` revision is not pinnable. **Commit
everything, check `git status --porcelain` is empty, then start.**

The two cosmetic items were never run-blocking, because the live suite drives the Python loop and never
renders a component or reads the refusal sentence as a score:
1. **the `bach` offer block — DONE 2026-09-12, his call ("800px is already too tall").** `.offer__list`
   wraps name-sized choices instead of stacking full-width rows. Measured in the real app, headless
   Chrome against the local stub: `bach` **800px → 274px** at 1280 wide, 588px at 400 wide (long Bach
   names mostly do not pair at phone width); `mozart` 192px, `r&b` 213px, `dolly` 65px; no horizontal
   page scroll at either width. **Still layout, not ranking** — every candidate is on screen in API
   order, no scroll box, no "show more".
2. the refusal wording "it is not in this graph" directly above "This graph has 5 names like "mozart""
   (`refusal_text` in `agent/loop.py`) — **left alone.** Public prose, his to write; it is not the
   frame's `reason`, so it can change later without touching `refusal_accuracy`. The only cost of
   changing it after the baseline is that the run's transcripts keep the old sentence.

**What to expect from the new `offer` property on a LIVE run, and why it is not zero this time.** The
live set is 63 cases (43 gold + 20 adversarial), so unlike the free gold-only run it includes
`adv_008`, `adv_009` and `adv_020`, which are the only three cases that produce offers. Scripted, they
gave `offers=3, over_cap=1, offers_without_refusal=0, refusals_with_choices=3`. **A live run may differ,
and that is the point** — a real model may resolve or fail to resolve differently. `offers_without_refusal`
must still read 0; if it does not, D3 has broken and the run is a finding rather than a baseline.

**U-items on entry:** U3 **CLOSED, negative** — `heldout-check` says "sealed set still agrees with
artifact 0.10.0", nothing drifted, nothing opened, **run count still 0**. U4 **CLOSED, yes** — the
held-out set is run once at this freeze, after the re-baseline.

**TWO LIVE ATTEMPTS LOST TO BEDROCK 503s, AND THE HARNESS FIX — 2026-09-12, before any counted run.**
Attempt 1 (`20260912T200642Z`) stopped at case 22 of 63 after five `ServiceUnavailableException` cases.
Attempt 2 (`20260912T205301Z`) finished 62 of 63 and was **unpoolable** because `gold_v0_1_015` got a 503
after botocore's eight adaptive retries. Neither was caused by the machine sleeping: both are HTTP 503s
from Bedrock, and attempt 1 ended at ~16 minutes. Attempt 2's 62 cases were healthy — `offer` 0 replaced a
refusal, and its only three wrong cases were `gold_v0_1_020`, `gold_v0_1_035` and `adv_018`, all known.
Both result files are kept and committed; `noise.py` refuses them as incomplete.

**The fix, made while no complete run existed at `2730919`, so the new revision cost nothing:**
1. `agent/llm.py:is_transient_provider_error` names **only** `ServiceUnavailableException`, by botocore
   code, case-insensitively. Throttling is deliberately excluded.
2. `suite.py` runs a case again from the start after that error, `CASE_RETRIES = 2`, waiting 60s then
   120s. **Only a case that produced no answer is retried** — a wrong answer or a case-local raise never
   is. Every retry is recorded as `retried_cases` and printed; a retried case that answers leaves the run
   complete.
3. **His request: a full `make eval-live` stops at the first case that fails every retry**
   (`live.py:case_error_limit`), because a run missing a case cannot be pooled. Subsets keep stepping over.
4. `retried_cases` joined the held-out allowlist as a decision: case id, attempt, class name, no message.
Breakage-verified: forcing the predicate to `False` failed four tests, and forcing the limit back to five
failed the full-run test. **The five counted runs start on the revision this lands in.**

**One known bug that is NOT a blocker:** the local stub renders an artist-subject influence answer with
no subject (" came out of Johann Sebastian Bach."), because it pattern-matches a `"Genre: "` marker
`ORIGINS_SYNTHESIS_TEMPLATE` does not emit (`agent/llm.py:600`). Stub-only as far as is verified; the
live path reads the prompt as prose. §5.0 has the detail. **Do not fix it during the run.**

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
