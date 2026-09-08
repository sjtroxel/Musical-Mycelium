# Phase 7 — Cinematic Surface (v0.8) — IMPLEMENTATION

> **As-built plan.** Written 2026-09-08, immediately before building, against measurements taken the same
> afternoon rather than recalled. The scope doc `phase-7-cinematic-surface.md` was written 2026-07-30 as
> `phase-7-polish-and-portfolio.md` and amended 2026-08-24; nothing in it is withdrawn, but §3 below records
> four places where fourteen months of building have moved out from under it.
>
> **THE SPLIT IS APPROVED — sjtroxel, 2026-09-08.** §7 proposed it and this doc now assumes it. Phase 7 is
> the cinematic surface at **product v0.8**; phase 7.5 is portfolio and writeup at **v1.0**, scoped in
> `phase-7.5-portfolio-and-writeup.md`. Both scope docs were amended or written the same day.
>
> **The brief this plan adds, and it came from him on 2026-09-08:** the design half is not a coat of paint
> at the end. It is a named deliverable with full-page video and motion graphics in it, and it is sized
> like one here.
>
> Steps are marked `[done]` as they land, and each carries an as-built subsection recording where reality
> disagreed with this plan. The doc is allowed to be wrong. It is not allowed to be silently wrong.

## 1. What this phase delivers, in one sentence

**The cinematic surface:** a guided tour that walks two nodes and narrates the walk, a backdrop and motion
system that makes the page land in the first three seconds, and one timeline underneath both so the
narration and the camera cannot drift apart.

**This is half of the scope doc's definition of done, and the split is approved — see §7.** Items 1, 2
and 8 are closed here, plus three new checkable items the design half added. Items 3 through 7 — the
published eval report, the trend view, the writeup, the Terraform round-trip and the verified bill — are the
portfolio half and are now **phase 7.5**, `phase-7.5-portfolio-and-writeup.md`. The scope doc anticipated
exactly this: *"If this phase starts to feel like two phases, it is — split it."* It does.

## 2. Baseline, measured 2026-09-08, not recalled

Everything below was run this afternoon on a clean tree at `2b04185`.

| measurement | value | how |
|---|---|---|
| Python suite | **1461 passed, 14 deselected, 0 xfailed** | `make check` |
| mypy | clean over **99 source files** | `make check` |
| Frontend suite | **168 passed** across 16 files | `npm test` in `web/` |
| `make check` | green end to end, exit 0 | `make check` |
| Scripted eval gates | **4 passed, 0 failed, 2 N/A** of 6 | the `eval` target inside `make check` |
| Repo root | **17 entries, cap 18** | `make root-check` |
| Artifact pin | **0.7.1** | `graph/memory.py:34` |
| Gold set | **38 cases** | `eval/datasets/gold_v0_1.json` |
| Adversarial set | **20 cases** | `eval/datasets/adversarial_v1.json` |
| Live set | **56 cases**, live baseline measured over 56 | `eval/thresholds.json` |
| Held-out set | sealed, pinned 0.5.0, **run count 1** | not opened, and not opened by this plan |

**The SPA as it ships today, measured with `npm run build`** — this is the row the whole design half has to
argue with, and nothing in the repo was tracking it before now:

| asset | bytes | note |
|---|---|---|
| `dist/assets/index-*.js` | **236,210** | React 19 + the whole app |
| `dist/assets/index-*.css` | **10,303** | `styles.css`, 982 lines |
| `dist/index.html` | **1,087** | |
| `dist/graph/v0.7.1/graph.json` | **2,600,000** approx | staged by `scripts/stage-graph.mjs` |
| **`dist/` total** | **3.5 MB** | |

The page already ships roughly **2.9 MB of real payload**, and **2.6 MB of it is the graph**. Any video
budget is negotiated against that number, not against zero.

**What already exists that this phase builds on, rather than inventing:**

- `web/src/graph/motion.ts` — 160 lines, a real motion system. `MotionMode`, `EDGE_MS = 850`,
  `POSITION_MS = 526`, hand-written easing, every value chosen by him in the running app on 2026-08-31.
  Its design note is the important part: the arithmetic was split out of the canvas **so that timing is
  testable in jsdom even though pixels are not**. That constraint governs step 4.
- `web/src/styles.css:22-60` — the palette, chosen by him 2026-08-30 from three candidates rendered in the
  real app, against his own brief: *"a music venue, lights, camera, showtime and neons... performing
  arts... cinematic."* Dark-only, committed to on purpose. Every value validated for contrast rather than
  eyeballed.
- `web/previews/` — 20 files. The throwaway-preview pattern phase 5 used to decide palette, layout, type
  and motion in the real app before committing to any of them. Step 1 reuses it.
- `@media (prefers-reduced-motion: reduce)` at `styles.css:959`, already honored.

## 3. The scope doc, re-read: four places reality moved

Required by the `start-a-phase` skill, and all four are real.

1. **"The deployed URL still runs a template stub" is stale.** That amendment was written 2026-08-24 and
   phase 6 closed it: `v0.6.0` is tagged at `51f2c21` and deployed, `/health` serves artifact 0.7.1, and a
   real Bedrock query streamed a claim and its narration. **This phase inherits a working deployed
   product**, which is the state the scope doc hoped for and could not assume.
2. **"Polish, no architecture change" undersells it, and the scope doc already said so.** It is right. The
   guided tour is a new agent behavior and the backdrop is a new asset class with a new build step.
   Neither touches a seam, so "no architecture change" survives as literally true and useless as a size
   estimate.
3. **The design brief is not new and this plan is not starting one.** The scope doc treats visual work as
   README-adjacent. In fact he chose a cinematic neon palette on 2026-08-30 and a motion mode on
   2026-08-31, both from rendered candidates. The 2026-09-08 brief — full-page video, motion graphics —
   **continues that decision rather than opening a new question.** That is why step 1 is previews and not
   a moodboard: the aesthetic is settled, only the treatment is open.
4. **"Contested claims are flagged rather than resolved"** in the scope doc's risk list was written when
   `contested` was unreachable. It is reachable now, 2 pairs at v0.7.1, and phase 6.5 step 4 shipped the
   disclosure surface. The risk it names is unchanged; the tense is wrong. Amend on contact.

**Inherited assignments, `docs/planning/09` §6:** checked, all eight. Every one was discharged in phases 0
through 6.5 — the claims-first pipeline, the P279 hand-validation, the graph-store pick, the judge model,
the streaming shape, the test layout, the eval build order, the v1 not-list. **Nothing from that list is
outstanding for this phase.** The list is doing its job by being empty here.

## 4. The finding this plan adds: adding one live case costs $2.61 and 2.4 hours

Read out of the code today, not recalled. `thresholds.py:597` — the superset branch, split from the subset
branch on 2026-09-07:

> *"this run scored N cases and the baseline was measured over M. The dataset has grown past its baseline,
> so this run is the complete one and the baseline is the stale half."*

`_ungateable` returns before any per-metric check, so **the entire live suite reports `NOT GATED` the
moment the live case count changes by one.** It has already bitten twice — at 45 against 41 on 2026-09-06,
and again at 56 after phase 6.5 step 5. Restoring the gates means re-measuring the floor over five
identical runs: **$2.61 and about 2.4 hours**, the figure phase 6.5 step 7 actually paid.

The guided tour is a new query shape. The obvious move — add tour cases to `gold_v0_1` — therefore carries
a price tag that has nothing to do with the tour and would not be visible until the next `make eval-live`.

**Decision: the tour gets its own dataset, `tour_v1.json`, and gold stays at 38.** `ThresholdSet.matches`
keys on dataset **and** provider (`thresholds.py:177`), so a new dataset name matches no set and prints the
loud `render_unmatched` banner — *"NOT GATED. This is not a pass."* — rather than silently borrowing a
baseline measured over different questions. The containment is already built; this plan just has to not
defeat it.

## 5. A second finding: there is no asset-weight guard, and this is the phase that needs one

I looked for one. `make root-check` caps repo root entries. `eval/thresholds.py` gates correctness. The
"split size guard" in the phase 6.5 step 6 commit message is about **threshold set sizes**, not bytes —
`git show 2957832 --stat` touches ten files and not one of them is in `web/`. `stage-graph.mjs:46` prints
a KB figure and asserts nothing about it.

So: **the project gates six correctness properties and zero bytes**, and the next thing it does is add
video. That is the exact shape of the failure this repo's culture is built to catch — a number nobody is
watching, moving in one direction only.

**Step 0 adds the budget before step 2 adds the first frame**, for the same reason the noise floor was
measured before the gates were written. A budget authored after the asset exists is a description of the
asset, not a constraint on it.

## 6. A third finding: the backdrop and the signature moment compete for the same eye

This is a design finding and it is the one most likely to be got wrong quietly.

The scope doc's headline deliverable is: *"As the agent streams its reasoning, the graph animates the
traversal it is describing... One shared timeline driving both the text and the view. This is the single
most demo-able thing in the project."* That is already motion, on the most important surface, carrying
real information.

A video loop playing behind it is **ambient motion competing with semantic motion**, and ambient motion
wins, because it is smoother and larger and never stops. The visitor's eye goes to the thing that is
moving for no reason instead of the thing that is moving because a claim just passed the gate.

**The rule, and it is testable rather than tasteful: the backdrop yields.** It plays in the hero, above the
fold, before a query exists. The moment a run starts streaming it pauses and does not resume for the life
of that run. Step 3 tests exactly this, because "we'll be tasteful about it" is not a property and does not
survive a late-night tweak.

## 7. The split: what stays in 7 and what became 7.5 — **APPROVED 2026-09-08**

The scope doc's own key decision — *"Whether the tour is its own phase. Decide this at phase start by
looking at what phases 5 and 6 actually produced, not now."* Looking at them: phase 5 produced a real
canvas renderer with a tested motion module, and phase 6 produced a corpus dense enough to walk. Both make
the tour cheaper than it looked. Neither makes it small.

Adding a full design and video track on top of the tour, the eval report, the trend view and the writeup
is four deliverables in a phase whose scope doc names *"polish is unbounded"* as risk number one.

**Approved by sjtroxel on 2026-09-08.** The docs were split the same day: this file was renamed from
`phase-7-polish-and-portfolio-IMPLEMENTATION.md`, the scope doc gained a §0 recording the carve, and
`phase-7.5-portfolio-and-writeup.md` was written to carry the half that left.

| | phase 7 — cinematic surface (**v0.8**) | phase 7.5 — portfolio and writeup (**v1.0**) |
|---|---|---|
| scope DoD items | 1, 2, 8 | 3, 4, 5, 6, 7 |
| content | backdrop, motion system, guided tour, one timeline, demo route | eval report page, trend view, README, writeup, coverage position, `terraform destroy`/`apply` round-trip, verified bill |
| shape | build | build plus prose |
| his hands | picks treatments, picks the route | **writes the writeup himself** |

The last cell is not a scheduling note. DoD item 5 is *"the writeup exists and he can walk through it
cold"* — the articulation rep. Prose he hands a recruiter has to be his words, and that is a rule that
predates this repo.

## 8. Step plan

### Step 0 — The asset budget, before a single frame exists — **DONE 2026-09-08**

Add `web/scripts/asset-budget.mjs` and wire it into `npm run check` and therefore `make check`. It walks
`dist/` after a build, classifies every file, and fails on any class over budget.

Four classes, because one total hides the interesting movement:

| class | today | proposed cap | reasoning |
|---|---|---|---|
| script | 236 KB | **320 KB** | room for the tour and timeline; not room for an animation library — see step 4 |
| style | 10 KB | **40 KB** | the design half will grow this legitimately |
| graph data | 2.6 MB | **3.0 MB** | pinned artifact, moves only when the pin does |
| **media** | 0 | **decide at step 1** | the number this phase is actually arguing about |

The media cap is deliberately blank. Picking it before the treatments are rendered is picking it from
taste, which is what §5 says not to do. It gets a number at step 1, from what the candidates actually
weigh, and that number goes in the table with its reasoning beside it the way `thresholds.json` does.

**Done when:** `make check` fails on a deliberately oversized fixture and passes on `dist/` as it stands,
and the baseline row above is committed as the starting measurement.

#### 0.0 As built — what the plan did not know

**Verified on completion, 2026-09-08:** `make check` green end to end, exit 0. Python **1461 passed, 14
deselected, 0 xfailed**, mypy clean over **99** source files. Frontend **177 passed across 17 files**, up
from 168 across 16 — the nine new tests are `web/scripts/asset-budget.test.mjs`. Scripted eval gates
unchanged at **4 passed / 0 failed / 2 N/A of six**. Root **17 of 18**.

The budget as it actually runs:

```
  ok   script   230.7 KB of  320.0 KB (72% of cap)  1 file(s)
  ok   style     10.1 KB of   40.0 KB (25% of cap)  1 file(s)
  ok   graph     2.57 MB of   3.00 MB (86% of cap)  1 file(s)
  ok   media      0.0 KB of    0.0 KB              0 file(s)
  ok   shell     10.0 KB of   32.0 KB (31% of cap)  4 file(s)
asset budget: 5 classes, all inside cap
```

Six things the plan got wrong or could not see.

1. **Five classes, not four. `shell` was missing and it is the important one.** The plan listed script,
   style, graph data and media, which leaves `index.html` and three favicons — 10 KB — unclassified. The
   fix is not the 10 KB; it is that **an unrecognised file must land somewhere loud rather than be
   skipped**. `classify` sends anything it does not recognize to `shell`, which carries the smallest cap,
   so a new asset type arriving unannounced fails a build instead of being silently exempt. A budget that
   ignores what it does not recognize stops covering the thing it was written for, which is the failure
   mode the whole step exists to prevent, reproduced inside the guard itself.

2. **THE BUDGET FOUND A REAL DEFECT ON THE FIRST RUN IT EVER DID, before it had a number in it.**
   `web/public/graph/v0.5.0/graph.json` — **655 KB** — was still staged alongside `v0.7.1` and was being
   copied into `dist/` by Vite and would have been synced to CloudFront by the deploy job.
   `stage-graph.mjs` only ever *wrote* the current pin and never removed the last one.

   **Why nothing caught it, and this is the part worth keeping.** Three independent reasons, each of which
   is individually reasonable: nothing fetches it, because `staticGraph.ts` builds its URL from
   `GRAPH_PIN` alone, so no test could fail; `.gitignore` excludes `web/public/graph/`, so it never
   appeared in a diff; and the one thing that did print its size — `stage-graph.mjs:46` — printed only the
   file it had just written. **It was invisible to tests, invisible to review, and invisible to the one
   number being reported.** Fixed at source rather than in the budget: `PRUNES_STALE_PINS` in
   `stage-graph.mjs` now deletes any staged pin that is not the current one, and says so when it does.

3. **The graph cap this plan proposed would have FAILED on its first run, and for an instructive reason.**
   §8's table proposed 3.0 MB against a stated "today: 2.6 MB". That 2.6 MB was measured from the pinned
   artifact in `public/`. The number that matters is what lands in `dist/`, and that was **3.21 MB** —
   the pinned artifact plus the ghost from finding 2. **I wrote a cap from the wrong denominator**, and
   the only reason it did not become a wrong committed threshold is that the ghost had to be explained
   before the number could be set. Measure the thing the gate measures, not its neighbor.

4. **The script cap turned out to enforce step 4's recommendation rather than merely coexist with it.**
   320 KB against 230.7 KB used leaves roughly 89 KB. framer-motion is roughly 120 KB before tree-shaking.
   So **importing an animation library now fails this gate**, which converts step 4's "recommended
   against, and here is the cost of overruling it" into "costs a budget amendment with reasoning
   attached." That is a better outcome than the plan intended and it was not designed — it fell out of
   picking the number from what the app actually weighs. **If he overrules step 4, the cap moves and the
   `why` string moves with it**; that is the whole mechanism, and it is deliberately not silent.

5. **A stale measured claim, found while measuring.** `useStaticGraph.ts:8` said the artifact is *"640 KB
   (55 KB over the wire)"*. Both figures were measured honestly at artifact v0.5.0 and went stale the
   moment phase 6 re-pinned to v0.7.1 — the corpus grew roughly 4x and **a comment stating a measurement
   does not re-measure itself**. Corrected to **2.6 MB, 201 KB gzipped**, both measured today. Worth
   noting that the argument that paragraph makes — do not fetch the corpus before first paint — is
   *stronger* at the true number, so this was a stale fact propping up a correct conclusion, which is the
   kind that survives longest.

6. **The test is `.mjs`, not `.ts`, and that was forced rather than chosen.** `web/tsconfig.json` includes
   only `src` and `vite.config.ts`, so `scripts/` is not typechecked, while vitest's default include
   *does* reach it. A `.test.ts` there would run in the suite while being invisible to `tsc` — a test file
   that looks typechecked and is not. `.mjs` makes the absence of typechecking honest instead of hidden.

**The media cap is 0 and that is load-bearing, not a placeholder.** Proven by pointing the CLI at a
fixture holding one 879 KB `media/backdrop.webm`: it fails, names the class, prints the recorded reason,
and exits 1. Phase 7 step 1 sets the real number from what the rendered candidates weigh. **Until then no
media can ship**, which is exactly the ordering §5 argued for.

#### 0.1 In plain English

Websites get slow one file at a time, and nobody notices because no single addition looks like the
problem. This project already had automatic checks for whether its *answers* are honest, but none at all
for how *heavy* the page is — and the next thing planned was full-screen video, which is the heaviest
thing a web page can carry.

So before adding any video, I added a scale. It weighs the finished site in five separate categories —
program code, styling, the music-graph data, video and images, and everything else — and refuses to
finish the build if any category is heavier than an agreed limit. Each limit has its reasoning written
next to it, so raising one later means arguing with the reason rather than quietly changing a number.

The scale found something the first time it was used: an old copy of the music graph, 655 KB, left behind
from an earlier version and still being uploaded to the website every time it was published. Nothing used
it. No test could have caught it, because nothing was looking. That is the entire argument for weighing
things before you add weight.

### Step 1 — Treatments, behind throwaway previews — **DECIDED 2026-09-08: CANDIDATE A**

The phase 5 pattern, unchanged: render candidates in the real app, let him decide, keep the decision and
throw away the code. `web/previews/backdrop.html` and friends.

Four candidates, and they are genuinely different bets rather than one idea at four opacities:

- **A — live canvas drift.** The real 1,465-node component, rendered by the real `layout.ts`, drifting
  slowly behind the page at low alpha. **Zero additional bytes** — `graph.json` is already loaded. Scales
  to any viewport. Costs a persistent `requestAnimationFrame` loop and therefore battery.
- **B — pre-rendered corpus video.** The same drift, rendered offline at a quality no real-time loop can
  reach, encoded to a file. Costs bytes; **saves** power, because hardware video decode is cheaper than a
  rAF loop over 1,465 nodes. This is the literal full-page video background, and it is the one I would
  build first.
- **C — a neon field.** Gradient and noise in the palette's own hues, tied to nothing. Cheapest to build,
  cheapest to ship, and the only candidate that is decoration. Included because it is the honest control:
  if it reads better than A and B, that is worth knowing before spending a week on a renderer.
- **D — hybrid.** B in the hero, nothing behind the working surface. The §6 rule taken to its conclusion.

**On the "full page video is mandatory in 2026" framing, once, then I build what he picks.** It is not
mandatory, and a recruiter has never rejected an engineer for a missing video loop. What *is* true is that
a portfolio piece gets about three seconds to establish that a person with taste built it, and motion is
the fastest way to spend those three seconds well. So the instinct is right even though the rule is not,
and the work is worth doing on those grounds.

**One thing I would push on, and it changes the interview answer rather than the visual.** A stock clip of
abstract particles is the same clip on ten thousand landing pages, and on *this* project it is also a
small dishonesty: the entire pitch is that what you see traces to something checkable. **Candidates A, B
and D render the actual corpus** — the real 1,465-node component, the real layout code, the real pin.
Identical on screen to good stock footage, and the sentence underneath it becomes *"the background is the
graph"* instead of *"I bought a video."* That sentence is worth more in a live round than any amount of
polish. If he prefers a licensed clip anyway, candidate C is the slot for it and nothing else in this plan
changes.

**Done when:** he has picked a treatment in the real running app, and the media budget has a number.

#### 1.0 As built — what the plan did not know

**Status: the previews are built, verified headlessly, and measured. The step is NOT done**, because
its deliverable is a decision and the decision is his. Nothing here is committed — `web/previews/` is
gitignored by the phase 5 decision that previews are throwaway, so `git status` is clean and
`make check` is untouched at **1461 / 177 / 4 gates passed / budget green**.

Built: `build-data-7.py` (the layout, solved offline), `harness7.js`, `backdrop.html` (all four
candidates over one mock of the real page), `index7.html` (the landing page and the byte table), and
`check-7.mjs` (**20 headless checks** plus the encode ladder). Open `web/previews/index7.html` under
`npm run dev`.

**The `check-5.mjs` rule was honored and it earned its keep three times.** That rule — *confirm a
preview can PERFORM the behavior being judged*, written after a preview was handed over inert on
2026-08-28 — is why `check-7.mjs` asserts each candidate actually animates, that reduced motion and a
streaming run each stop it, that a stopped layer is **drawn rather than blank**, and that the video
candidates say what to run instead of showing nothing.

Seven things the plan got wrong or could not see.

1. **THE PLAN'S RECOMMENDATION WAS WRONG, AND THE MEASUREMENT IS WHY THE STEP EXISTS.** §8 step 1 said
   of candidate B: *"this is the one I would build first."* At the resolution the page renders at,
   candidate B costs **12,414 KB for ten seconds** — roughly **four times the entire current page**,
   for a decoration. It is not close to viable at 1600 and no amount of taste would have revealed
   that.

2. **MY EXPLANATION FOR WHY WAS ALSO WRONG, AND I NEARLY WROTE IT DOWN OFF A BROKEN CONTROL.** The
   hypothesis was that 1,465 dots each oscillating on its own period is the pathological case for
   inter-frame prediction. So I added `?tw=0` to remove the twinkle and measured. It came back
   **identical to four significant figures**, which I briefly read as "the twinkle is free."

   **It was not a finding. It was a bug in my own harness.** `chrome()` rebuilds the URL with
   `history.replaceState` from a fixed list of parameters, so `tw` was stripped before the renderer
   read it — the two capture passes were byte-identical because they were *the same run twice*.
   Caught by `cmp` on frame 150, not by reading the code. Fixed by making every parameter round-trip
   through `sync()`.

   **Re-measured correctly, the answer was the same: 12,414 KB against 12,416 KB.** The twinkle really
   is free. That coincidence is the part worth keeping — **a broken measurement agreed with the true
   one, so nothing downstream would have looked wrong**, and the only reason the bug surfaced at all
   is that two probes printing identical numbers to the byte was too tidy to believe.

3. **The real cause is spatial detail at native resolution, and it is wildly non-linear.**
   1,465 one-pixel dots and 5,058 hairline edges are close to pure high-frequency energy — a single
   captured PNG frame is **2.8 MB**. Downscaling averages them into shapes a codec can predict:

   | width | VP9 crf40, 10s | factor |
   |---|---|---|
   | 1600 | 12,414 KB | — |
   | 960 | 1,266 KB | **÷ 9.8** |
   | 640 | 293 KB | **÷ 4.3** |

   Halving the width divides the file by roughly ten, twice over. **This is the whole media budget
   question**, and it is a good one to have found in a preview rather than in step 2.

4. **The first render was effectively invisible, and it would have made the comparison meaningless.**
   The veil shipped at 0.55/0.78 over node alphas of 0.24–0.42, and the screenshot came back
   near-black with a faint texture. **All four candidates would have looked identical** and any
   decision taken from it would have been a decision about the veil. The wash is now a **slider** with
   the number in the URL, which turns the actual design tension — the backdrop only earns its place if
   it is visible, the text only stays legible if it is not — into something he sets rather than
   something I picked. Where it lands is a real number owed to this doc.

5. **Candidate C was rendered dimmer than its rivals, which is not a fair control.** It was drawn at
   five blobs of `0x22` alpha while A was clearly legible under the same veil. **A control that loses
   because it was drawn faint has not been tested**, and C exists precisely so that "the corpus is the
   backdrop" has to beat something rather than win by being the only one rendered properly. Now seven
   blobs at `0x55`, matched by eye against A in the same screenshot.

6. **The chrome bar overlapped the hero on candidates whose note wraps to three lines.** Fixed by
   measuring the bar rather than hard-coding 132px. Trivial, and listed because it was invisible until
   a screenshot was actually looked at — which is the same lesson as 4 and 5 arriving a third time.

7. **`build-data-7.py` independently confirmed the corpus figures.** 7 components, **1,465 of 1,479**
   nodes in the largest, 5,058 edges inside it. Not taken from `CLAUDE.md`; computed from the pinned
   artifact by a script written for a different purpose. Runs in 2.5 seconds and emits 90 KB.

**The measured table, ten seconds at 30 fps** — the media budget comes out of this and nothing else:

| encode | size | per second | read |
|---|---|---|---|
| 1600 · VP9 crf40 | 12,414 KB | 1,241 KB/s | unusable |
| 1600 · VP9 crf48 | 3,931 KB | 393 KB/s | unusable, and visibly soft anyway |
| 960 · VP9 crf40 | 1,266 KB | 127 KB/s | plausible; a third of the page again |
| **640 · VP9 crf40** | **293 KB** | 29 KB/s | **cheap enough to stop thinking about** |
| 960 · AV1 crf40 | 650 KB | 65 KB/s | half of VP9; slower to decode on old hardware |
| 960 · H.264 crf28 | 1,186 KB | 119 KB/s | the Safari fallback, and why a second file exists |
| poster · AVIF | 283 KB | — | measured because DoD 9 makes the poster the LCP element |

**My read, which is not the decision.** At 640 the backdrop reads as depth of field rather than as a
mistake, and at 313 KB it stops being a budget argument at all. If that holds on his screen, candidate
D at 640 — video in the hero, nothing behind the working surface — costs about **700 KB all in** with
a poster and an H.264 fallback, and a **media cap of 1.0 MB** would fit it with room and still refuse
anything careless. Candidate A remains the only one at literally zero bytes, and it is the one whose
cost is somebody's battery rather than their bandwidth.

#### 1.1 The decision — sjtroxel, 2026-09-08, from the running previews

**CANDIDATE A. The live canvas drift of the real 1,465-node component.** His words: *"I like A a lot."*
Also decided in the same sitting: **little or no veil** — *"let people see it"* — and **the motion
stays prominent**.

**This deletes step 2 and shrinks step 3, which is the largest scope change in the phase so far.**
Candidate A ships no media at all, so:

| | was planned | now |
|---|---|---|
| Step 2 — offline renderer | Playwright + ffmpeg, frame capture, manifest, encode ladder | **not needed** |
| Step 3 — `Backdrop.tsx` | a `<video>` with poster, `preload`, codec fallbacks | a canvas component |
| New dev dependencies | Playwright, ffmpeg in the pipeline | **none** |
| `media` budget cap | a number set from the encode table | **stays 0, permanently** |

A `media` cap of zero stops being a temporary placeholder and becomes a **standing guarantee that this
site ships no video**, which is a stronger and more honest thing for the budget to say than any number
would have been.

**A CORRECTION TO MY OWN COPY: candidate A is not "0 extra bytes" in production, and the preview said
it was.** The preview loads `data-7.json` as its own file, so the claim was true there and false as a
statement about the built site. In the SPA the corpus is **not** loaded at first paint — DoD 5 forbids
it and `App.test.tsx` asserts the page requests nothing on load, which is why `useStaticGraph` is gated
behind `enabled`. A hero backdrop needs positions *before* any run starts. So candidate A costs a small
**precomputed positions file, about 90 KB as it stands and trimmable**, fetched at load.

That is still **3.2x cheaper than the cheapest viable video** (293 KB at 640) and it reflows to any
viewport, so nothing about the decision changes. But "free" was wrong and it was my sentence.

**The veil and the node alpha, measured rather than eyeballed — 2026-09-08.** DoD 9 requires contrast
against the backdrop's **brightest region**, not against `--ground`, so this samples the brightest
composited pixel in the hero text band and computes WCAG contrast from it:

| veil | node alpha | brightest pixel | `--ink` | `--ink-soft` |
|---|---|---|---|---|
| 0 | 1.0 | rgb(218,86,157) | **3.20:1** | 1.76:1 |
| 0 | **0.6** | rgb(157,77,131) | **4.84:1** | 2.66:1 |
| 0 | 0.45 | rgb(136,73,121) | 5.65:1 | 3.11:1 |
| 0.12 | 0.5 | rgb(132,69,116) | 6.00:1 | 3.30:1 |
| 0.42 | 1.0 | rgb(155,62,116) | 5.54:1 | 3.05:1 |

**The finding: the pixels that fail are a few dozen full-strength genre dots, not the field.** So the
lever is the dots, not a wash over everything — and that is the lever that keeps *"let people see it"*
true, because what reads as the corpus is the filaments and clusters, not the hot spots. **At veil 0
and node alpha 0.6, `--ink` clears the 4.5:1 AA bar at 4.84:1 with no wash at all.** That is the
setting this plan will build to unless he says otherwise.

**One caveat stated rather than buried:** `--ink-soft` does not clear 4.5:1 against the brightest dot
at any setting measured. It is the tagline's color. Either the tagline moves to `--ink` where it
overlaps the backdrop, or it sits where the backdrop is already dark. Step 3 owes an answer.

**`prefers-reduced-motion` is HONORED — decided 2026-09-08, and the round trip is worth recording.**
He first said *"no need to do prefers-reduced-motion — I LIKE THE MOTION."* Raised back once, because
the instruction and the intent did not match: honoring the query does not dim anything for him or for
any visitor who has not switched it on, and `styles.css:959` already ships a global reduced-motion
block, so dropping it would have been a regression rather than declining to add something.

His answer, verbatim: *"Oh I didn't realize prefers-reduced-motion was a user accessibility thing. in
that case keep it. but i want most users to have the full-motion experience. only those who have gone
out of their way to select their accessibility for reduced-motion should have the lesser one."*

**That is exactly what the query does, and the sentence is kept because it is the requirement.** The
backdrop drifts at full strength for every visitor by default. A visitor who has set Reduce Motion in
macOS or turned animations off in Windows gets a **still frame of the same graph — drawn, never
blank**, which `check-7.mjs` already asserts. No third state, no toggle in the UI, no reduced version
for anyone who did not ask for one.

**The near-miss is the lesson, not the outcome.** A literal reading of the first instruction would have
shipped an accessibility regression that he did not want and had not been asked about, on the surface
most likely to be reviewed by another engineer. The instruction was clear; the premise under it was
not, and the cheap move was to say so once rather than to comply or to override.

#### 1.2 An out-of-order fix: the home page's own column, 2026-09-08

Not a step 1 item, and done anyway because he reported it while looking at the previews. **The real
SPA's tagline and footer were capped at the 34rem reading measure inside a 46rem column**, so at 1440px
they ran **544px** against **696px** for the lockup, the ask form, the chips and the coverage panel.
The page opened and closed narrower than its middle, and the footer's `border-top` stopped 152px short
of everything above it, which reads as a broken rule rather than as a measure.

Below ~34rem both were already full width, which is exactly why he guessed it might be a desktop-only
fault. It was.

Widened both to the column rather than narrowing the middle, because **the page's own precedent is
already full-width small prose** — the coverage panel's paragraphs run the whole 696px at 0.85rem.
`--measure` is untouched everywhere else, where a claim list genuinely wants a short line. Verified:
all four blocks now report `left 372, width 696`. Frontend suite **177 passed**, unchanged.



### Step 2 — The backdrop renderer — **DELETED 2026-09-08, candidate A ships no media**

> **THIS STEP IS DELETED.** Step 1 chose candidate A, which renders on a canvas at runtime and ships no
> video, so there is nothing to encode. Deleted rather than deferred: the offline renderer existed only
> to produce a file candidate A does not need. What it would have cost — Playwright and ffmpeg as
> pipeline dependencies, a manifest, a codec fallback matrix, a poster, and somewhere between 293 KB
> and 12.4 MB of media — is all avoided. The `media` budget cap **stays 0 permanently**, which turns a
> placeholder into a standing guarantee that this site ships no video.
>
> **What survives:** `build-data-7.py` becomes production work in step 3, because the positions still
> have to be solved offline. That was always the honest half of this step. The prototype is in
> `web/previews/`; the plan is kept below, struck through, because the reasoning about determinism and
> seeds transfers to the positions file unchanged.

~~`web/scripts/render-backdrop.mjs`. Playwright drives an offscreen page running the real `layout.ts` over
the real pinned graph, captures a fixed frame count from a fixed seed with no wall-clock input, and hands
the frames to `ffmpeg`.~~

Encodes: **VP9 `.webm`** primary, **H.264 `.mp4`** fallback, **AVIF poster with JPEG fallback**. Output to
`web/public/media/`, **committed**, so neither CI nor the deploy job needs Playwright or ffmpeg. Both are
local dev dependencies only; `ffmpeg 6.1.1` is already on this machine, Playwright is not and will be added
under `web/devDependencies`.

A `media/manifest.json` records artifact pin, seed, frame count, source commit and encoder settings, so the
file can be regenerated identically and so a backdrop rendered from a stale pin is visible rather than
inferred. Same discipline as the artifact manifest.

**Root discipline: nothing here reaches the repo root.** Root is at 17 of 18 and this step adds a scripts
file under `web/` and assets under `web/public/`, both already-existing directories.

**Done when:** two consecutive runs at the same pin and seed produce identical manifests, the encoded set
is inside the step 1 budget, and `make check` still passes with the assets present.

### Step 3 — The backdrop component, and the rules that are tests — **DONE 2026-09-08**

**Rewritten 2026-09-08 after step 1 chose candidate A.** `web/src/components/Backdrop.tsx` is a
**canvas** component, not a `<video>`: a `requestAnimationFrame` loop drawing precomputed positions,
with the drift arithmetic split into a pure module the way `graph/motion.ts` already is, so the timing
is testable in jsdom even though the pixels are not.

**The settings are measured, not chosen at build time** — step 1 §1.1: **veil 0, genre-node alpha 0.6**,
which puts `--ink` at 4.84:1 against the brightest composited pixel in the hero band. The positions ship
as a precomputed file of roughly 90 KB, because DoD 5 forbids fetching the 2.6 MB corpus before first
paint; trimming it is a step 3 task and the asset budget's `graph` class is where it lands.

Rules 1, 3, 4 and 6 below are unchanged. **Rules 2 and 5 are gone with the video** — there is no file to
withhold on a save-data connection and no poster to be the LCP element. Rule 6 gains a second half from
the measurement: `--ink-soft` does not clear 4.5:1 against the brightest dot at any setting tried, so
the tagline either moves to `--ink` where it overlaps the backdrop or sits where the backdrop is dark.

~~A `<video muted playsinline loop preload="none" poster=...>` behind the hero~~, plus `Backdrop.test.tsx`.

Six rules, each one a test, because every one of them is a thing that quietly stops being true:

1. **`prefers-reduced-motion: reduce` → never plays.** Poster only. Not "slower".
2. **`prefers-reduced-data: reduce` or `navigator.connection.saveData` → never loads.** Poster only.
3. **Tab hidden → paused.** `visibilitychange`, not a timer.
4. **A run is streaming → paused, and does not resume for that run.** The §6 rule.
5. **Never the LCP element.** `preload="none"`, poster carries first paint, video attaches after.
6. **Contrast is measured against the poster's brightest region, not against `--ground`.** The palette was
   validated against a flat dark ground; a video changes what is behind the text on every frame. Same
   validator the palette used, new denominator.

**Done when:** all six tests pass, the frontend suite is green, and Lighthouse on the deployed preview
shows no LCP regression against the current deploy.

#### 3.0 The color preview, built 2026-09-08 — **DECIDED: S4 + T3, high node alpha**

Built before the component, at his request: *"the preview leading into step 3 is exactly what I need,
so I can pick out the colors from that."* Same pattern as the palette in phase 5 and the backdrop in
step 1 — render the candidates in the real app, decide by looking, record the decision and its
reasoning. `web/previews/palette7.html`, verified by `check-colors.mjs` (7 checks), with
`drift.js` factored out so the color page and the backdrop page draw the **same** renderer. Two copies
would be how a color gets chosen against a picture the product does not draw.

**Nothing on the page invents a color.** The palette was decided 2026-08-30 from three candidates in
the real app; re-opening it now would be re-deciding a settled thing at the worst possible moment.
Every value is a token already in `styles.css`. The question is only which token goes where once text
has to sit on a moving picture.

**Four backdrop schemes x four tagline treatments, every combination measured across the drift.**
Contrast over a moving picture is not one number — the camera drifts, so different pixels pass under
the tagline, and a setting that passes on average can fail for two seconds at a time. The table below
is the **worst reading at eight points around the loop**, against the brightest pixel under each block,
which is DoD 9's rule.

| scheme | T1 `--ink-soft` | T2 `--ink` | T3 `+ scrim` | T4 `+ halo` | title |
|---|---|---|---|---|---|
| S1 as measured | 2.68 | **4.88** | **5.96** | 2.68 | 5.26 |
| S2 two accents | 2.85 | **5.17** | **6.11** | 2.85 | 5.31 |
| S3 ink only | 2.14 | 3.89 | **5.33** | 2.14 | 3.94 |
| S4 lit edges | 1.63 | 2.96 | 4.67 | 1.63 | **2.84** |

Bold clears AA at every point in the drift; the tagline bar is 4.5 and the title's is 3.0 because it is
large text. **5 of 16 combinations pass.** T1 — what the app ships today — fails under every scheme,
which is the finding step 1 predicted and this table confirms.

Three things worth keeping.

1. **THE LOUD COLOR IS THE SAFE ONE, WHICH IS THE OPPOSITE OF WHAT I EXPECTED.** Measured relative
   luminance: `--accent` rose **0.320**, `--ink-soft` lavender **0.460**, `--contested` cyan **0.586**.
   The hot pink is the *darkest* of the three visible tokens — a saturated mid-tone, where the quiet
   lavender is genuinely light. That is why S1 and S2, which put the accent on the nodes, score best
   behind text, and why S3 "ink only" — the most restrained scheme on the page — is the one that makes
   the title struggle at 3.94. Restraint in hue is not restraint in luminance.

2. **S4's problem is not its edges, and halving them proved it.** It first measured at 2.84 for the
   title with edges at 0.22 alpha, below even the large-text bar. I dropped edge alpha to 0.10 —
   **less than half** — and it moved to 2.84. The bright pixels are the ink-colored *nodes*, not the
   accent edges. Recorded because the instinct was to keep tuning, and the second measurement is what
   said to stop and report instead. S4 is the scheme that best expresses the thesis — draw the network,
   not the nodes — and it is the hardest one to put text on.

3. **T4's number is a floor, not a score, and the page says so.** The arithmetic cannot model a
   text-shadow halo, so T4 reports its plain `--ink-soft` figure. Printing that number without the
   caveat would be the vacuous-truth failure the eval suite already guards against, in a different
   costume: a metric that returns a confident value for a case it cannot actually measure.

**My read, which is not the decision.** S1/T3 and S2/T3 both clear comfortably and keep the deliberate
hierarchy between title and tagline, buying the contrast locally behind one block rather than washing
the page — which is what *"let people see it"* asked for. S2 is the more interesting picture, because
genre-rose and artist-cyan draws the two axes the corpus actually has in the two colors the app already
uses for two different things. **Open at `web/previews/palette7.html`.**

#### 3.1 The decision — sjtroxel, 2026-09-08

**S4 "lit edges" + T3 plate, at a high node alpha.** His words: *"I think I like s4 and t3 with a sort
of high node-alpha."* The glowing accent network over quiet nodes — the scheme that draws the thesis
rather than the nodes — with a plate under the opening block instead of a wash over the page.

**He picked the one combination on the table that failed, and the failing element got worse with
exactly the thing he asked for.** Swept at plate 0.55: the title never cleared its 3.0 large-text bar
at any node alpha, and fell from 2.81 to **2.35** as brightness rose to 1.0. The right response was
not to report that back as a veto. It was to find the version of what he picked that works, because
§3.0 finding 2 had already established *why* S4 was bright — the ink-colored **nodes**, not the accent
edges — and that is a fixable cause rather than a property of the scheme.

**Two changes, both aimed at the measured cause:**

1. **S4's nodes darkened**, `--ink-soft`/`--ink-faint` to `--ink-faint`/`--edge-context`. The edges keep
   the accent and can now run bright, which is the part he actually liked. **Title 2.35 → 8.04 at full
   node alpha.**
2. **T3's scrim became a plate behind the whole opening block, title included.** It covered the tagline
   alone, which under S4 protected the wrong element — the title is the block that fails there. It also
   simply reads better: one shape, rather than a patch under one paragraph.

**Then the tagline was left sitting on the bar, which is its own failure mode.** At plate 0.55 it
measured **4.42** against a 4.5 requirement across the drift — a fail by 0.08, and the readings bounced
between 4.42 and 4.65 depending on which pixels the camera brought under the text. **A number that
close to a threshold is not a pass that needs rounding, it is a design with no headroom**, and this
project has already learned once that a number which barely moves is a reason to look harder rather
than to relax. Swept the plate:

| plate | title (needs 3.0) | tagline (needs 4.5) | headroom |
|---|---|---|---|
| 0.55 | 8.04 | **4.42 FAIL** | -0.08 |
| **0.68** | **10.62** | **5.84** | **+1.34** |
| 0.80 | 13.38 | 7.36 | +2.86 |

**Settled: plate 0.68, node alpha 1.0, veil 0.** Measured live at 10.90 and 5.82 in the running page.
The plate covers the opening block and nothing else, so *"let people see it"* holds everywhere the
text is not — which at node alpha 1.0 is a considerably brighter network than any earlier setting.

**The preview now defaults to his pick and gained a plate slider**, because the plate stopped being a
fixed property of a treatment and became a real parameter with a measured value. `check-colors.mjs`
re-run: 7 checks pass, and the table's shape changed in a way worth noting — at node alpha 1.0
**every `--ink`-only combination now fails and all four plate combinations pass**. The plate, not the
scheme, is what makes text survive a bright backdrop.

#### 3.2 As built — 2026-09-08. **STEP 3 DONE.**

**Verified on completion:** `make check` green, exit 0. Python **1465 passed** (from 1461), mypy clean
over **101** source files, frontend **192 passed across 18 files** (from 177/17). Scripted eval gates
unchanged at **4 passed / 0 failed / 2 N/A of six**. Root 17 of 18. Asset budget:

```
  ok   script   267.9 KB of  320.0 KB (84% of cap)
  ok   media      0.0 KB of    0.0 KB
```

Shipped: `src/musical_mycelium/graph/backdrop.py` and `make backdrop`, the generated
`web/src/graph/backdropData.ts`, `web/src/graph/backdrop.ts` (pure), `web/src/components/Backdrop.tsx`,
`Backdrop.test.tsx` (15), `tests/test_backdrop.py` (4), and the plate in `styles.css`.

Six things the plan did not know.

1. **The data is INLINED, and that was forced by DoD 5 rather than chosen.** `App.test.tsx` asserts the
   page makes no network request on load — phase 5's DoD 5, whose reason is that first paint must not
   wait on anything. A backdrop that fetched its positions would fail that test. The options were to
   weaken DoD 5 or to make the data small enough to ship in the bundle. **Small enough won**, because a
   decorative layer is a bad reason to relax a guarantee about first paint. Packed to uint16 positions,
   a one-bit kind field and uint16 edge indices, base64'd: **35 KB**, and the script budget went 230.7
   to 267.9 KB against a 320 cap. Degree is derived in the browser rather than shipped — 1,465 bytes
   for something computable is exactly what the budget exists to catch.

2. **THE BACKDROP BROKE TEN TESTS THAT WERE NOT ABOUT THE BACKDROP, AND THE CAUSE GENERALISES.**
   `explore.test.tsx` stubs `getContext` on the **prototype** and returns one shared recording context,
   then counts and positions the `arc` calls the map makes. That was correct while the page held
   exactly one canvas. The backdrop added a second that draws 1,465 arcs a frame into the same
   recorder. **A test that selects `querySelector("canvas")` is silently asserting "there is one
   canvas on this page"** — an assumption nobody wrote down and nobody could have grepped for. Fixed by
   scoping the recorder to `.map__canvas` and handing every other canvas a silent context. Deliberately
   *not* fixed by returning `null` for the backdrop: `Backdrop` treats a null context as "this browser
   cannot draw me", so that would have made the tests pass while exercising a path no browser takes.

3. **A generator and a formatter cannot both own a file.** Prettier reflowed the emitted base64 onto
   its own line, which left the tree unformatted after every `make backdrop` and broke the regex in
   `tests/test_backdrop.py` with a `KeyError` on a field that was plainly there. `backdropData.ts` is
   now in `.prettierignore` — the same reasoning already applied to `public/graph` — and the parser
   tolerates the wrap anyway.

4. **THE PLATE COVERED THE WRONG THINGS, AND ONLY A SCREENSHOT FOUND IT.** Step 3's preview measured
   the title and the tagline, so those two were plated and cleared comfortably. The built page put
   **"ASK ABOUT A GENRE OR AN ARTIST"** (`--ink-faint`, the lightest text on the page) and the
   **"Trace it"** button (an unfilled `--accent` outline) directly onto a bright network. Both were
   effectively unreadable. **A contrast measurement covers the elements you point it at**; two were
   measured and four were exposed. The plate now spans the masthead and the ask row as one shape.

5. **The plate is 0.92, and the rule is worth more than the number: it returns the page to the contrast
   it had before the backdrop existed.** `--ink-faint` on plain `--ground` measures **4.98:1**. It
   passed for six phases; the backdrop took it to **3.42**. That is a regression the decoration caused
   on an element nobody touched, and the honest repair is to give it back rather than to redesign the
   label around the wallpaper. Measured on the built page:

   | plate | ask label | Trace it | tagline | title |
   |---|---|---|---|---|
   | 0.68 | **3.42 FAIL** | **4.46 FAIL** | 6.60 | 12.70 |
   | 0.82 | **4.37 FAIL** | 5.64 | 8.01 | — |
   | **0.92** | **5.02** | **6.45** | **8.82** | **16.22** |

   5.02 against an original 4.98. Nothing inside the plate had to change to survive a decoration behind
   it, and roughly 85% of the viewport still shows the network at full strength — which is what *"let
   people see it"* asked for, about a page-wide veil rather than about a local card.

6. **`paused` is `steps.length > 0`, not "a run is in flight".** Once the visitor has asked anything,
   the ambient layer stays still for the rest of the visit. Restarting the drift after every answer
   would put motion behind the claims exactly when the claims are the thing to read, and it would
   flicker. The backdrop's job is the first three seconds.

**The four rules are tests, not intentions** — `Backdrop.test.tsx`: reduced motion draws one frame and
starts no loop; a hidden tab cancels it; a run in flight stops it; and a still backdrop is **drawn,
never blank**, because a layer that renders nothing is indistinguishable from a loop that threw on
frame one. A fifth test asserts the page still renders when there is no 2D context at all.

`tests/test_backdrop.py` re-solves the layout from the pinned artifact and fails if the committed file
and the corpus have drifted apart — the same guard `test_chips.py` puts on the chip set, and it matters
more here because a backdrop drawn from a stale corpus still looks exactly like a backdrop.

**Not done, and owed by later steps:** the tagline's own colour question is closed by the plate rather
than by a token change; step 4's motion system, step 5's tour and step 6's timeline are untouched.

### Step 4 — The motion system, beyond the backdrop

The motion-graphics half: hero type, chip row, panel entrances, claim rows arriving, section transitions.

**Decision, and it is the one contentious call in this plan: no animation library.** Not framer-motion, not
GSAP. The reason is `motion.ts`'s own design note — the arithmetic was deliberately split out of the canvas
*so that timing is testable in jsdom where pixels are not*. A library puts timing back inside the component
and behind a rAF the test environment does not run, and the 168-test frontend suite gets quieter in exactly
the area this phase is expanding. It also spends the step 0 script budget: framer-motion is roughly 120 KB
before tree-shaking against a 236 KB app.

Instead: extend `motion.ts` with the easings and staggers the new surfaces need, keeping every one a pure
function of elapsed milliseconds, and drive them from CSS transitions and the existing loop.

**This is a trade, not a free win.** Hand-rolled motion is more code and more chances to get the feel
wrong, and a library would make step 6 easier. If he wants the library, the honest cost is the budget line
and the test coverage, and I will build it that way instead — but it should be chosen, not defaulted into.

**Done when:** every new motion honors `prefers-reduced-motion`, the script budget still passes, and the
timing constants carry the same kind of note `EDGE_MS` does — what was tried, what was picked, by whom.

### Step 5 — The guided tour, agent side

The C-shaped query from `SPEC.md` §2. *"Take me from delta blues to Detroit techno."* The agent plans a
path between two nodes and narrates it.

**The trap, named up front, because it is the claims-first leak wearing a new hat.** A tour *plans a path*,
and a planned path is a tempting thing to narrate — it is right there, it is ordered, it reads like an
outline. It is not a claim set. Every edge the narration mentions must be a `Claim` that passed the
deterministic gate, exactly as today, and `synthesize` still takes exactly one claim-bearing parameter. A
path the planner walked but the gate did not approve gets walked by the camera and **not** spoken.

**One-way door #4 gets tested here for real.** *"Adding a tool must never require editing the loop. If it
does, the seam is broken."* The tour is the first genuinely new tool since the seam was written. If
`agent/loop.py` needs an edit to accommodate it, that is a finding and it goes in this doc in bold, not a
quiet patch.

**Done when:** a two-node query returns a planned path whose narrated edges are all gate-approved, with
`agent/loop.py` unmodified.

### Step 6 — One timeline, demonstrably

Scope doc DoD item 2: *"Narration and camera are driven by one timeline, demonstrably — desynchronization
should be impossible by construction, not merely unobserved."*

The primitive: a single ordered cue list derived from the SSE event order — `{ atMs, kind, payload }` —
and **two consumers reading one cursor**. Not two loops that agree. Not a camera that listens to the same
events. One array, one index, both renderers read it.

"Impossible by construction" is only a claim if something checks it, so: a property test over generated cue
sequences asserting the text cursor and the camera cursor are never on different cues at the same
timestamp. That is the difference between the DoD item being closed and being asserted.

**Done when:** the property test exists and passes, and the demo runs end to end in the real app.

### Step 7 — The tour's own dataset

`eval/datasets/tour_v1.json`, per §4. Scored by the **existing** metrics only — the scope doc's not-list
forbids new metrics and this plan does not argue with it. Runs scripted and free on every commit.

Gold stays at 38, adversarial at 20, live at 56, and the live baseline stays valid. **No $2.61 re-measure
is triggered by this phase**, and if a later step wants one it is a decision he makes at a freeze, not a
side effect.

**Done when:** the tour set runs in the free suite, and `make eval-live` still reports six gates rather
than a `NOT GATED` banner.

### Step 8 — The demo route, picked from measured density

Scope doc risk: *"If phase 6's density work did not reach the region a demo walks through, the demo shows
the corpus skew rather than the system. Pick the tour route from measured density, not from taste."*

A script scores candidate node pairs on path length, per-edge verification tier, corroboration, and whether
the path crosses a membership edge or a contested pair. He picks from the top handful. The chosen route and
its measurements go in this doc, so the demo's quality is a recorded property rather than a lucky pick.

**Done when:** the route is chosen from a ranked list, and its numbers are written down here.

## 9. Decisions this plan does not make

- ~~**Whether to split 7 and 7.5.**~~ **DECIDED 2026-09-08 — approved.** §7.
- **Which backdrop treatment.** Step 1 exists to decide it in the running app, not here.
- **The media byte budget.** Step 1, from measurements.
- **Animation library or not.** Step 4 recommends against and states the cost of overruling it.
- **Anything about the held-out set.** It stays sealed at run count 1. Nothing in this phase reads it,
  needs it, or has an opinion about it.
- **The writeup's words.** His, for the reason in §7.

## 10. Not in this phase

New corpus. New metrics. New agent capability that is not the tour. Any architectural change. Re-measuring
the live floor. Opening the held-out set. A light theme — the palette note at `styles.css:14` settled that
and it is still right.

If something here needs a seam edited, that is a finding and it belongs in its own phase.

## 11. One-way doors touched

| door | touched? | how it is satisfied |
|---|---|---|
| 1. Claims first, prose second | **yes, and it is the risk** | step 5: the planned path is not a claim set; `synthesize` keeps one claim-bearing parameter |
| 2. Provenance on every edge | no | read-only consumer |
| 3. Validated graph semantics | no | P279 still not ingested |
| 4. Agent-to-data tool contract | **yes, and it is the test** | step 5: the tour tool lands with `agent/loop.py` unmodified, or it is a finding |
| 5. Everything in Terraform | yes, lightly | media assets deploy through the existing S3 sync; no new resource clicked |
| 6. Package boundaries | no | all frontend, plus one tool in `agent/` |
| 7. LLM provider seam | no | |
| 8. Lambda container image | no | |
| 9. Response streaming | **yes, and it is the enabler** | step 6's timeline derives from the SSE event order that streaming already produces |

## 12. Files expected to change, by path

**New:** `web/scripts/asset-budget.mjs`, `web/scripts/render-backdrop.mjs`,
`web/src/components/Backdrop.tsx`, `web/src/components/Backdrop.test.tsx`, `web/src/tour/timeline.ts`,
`web/src/tour/timeline.test.ts`, `web/public/media/*`, `web/previews/backdrop*.html`,
`src/musical_mycelium/agent/tools.py` (one tool), `src/musical_mycelium/eval/datasets/tour_v1.json`,
`tests/test_tour.py`.

**Modified:** `web/src/App.tsx`, `web/src/styles.css`, `web/src/graph/motion.ts`,
`web/src/graph/GraphView.tsx`, `web/src/useLineageRun.ts`, `web/package.json`, `Makefile`,
`docs/ROADMAP.md`, `docs/KNOWN-GAPS.md`, and this doc.

**Not modified, and it matters:** `agent/loop.py` (door 4), `agent/claims.py`, `eval/thresholds.json`,
`eval/noise_floor.json`, `eval/datasets/gold_v0_1.json`, `eval/datasets/adversarial_v1.json`.

## 13. Testing, and which eval metrics apply

The frontend suite carries most of this — 168 tests today, and steps 3, 4 and 6 add to it. The timeline
property test in step 6 is the one that closes a DoD item rather than covering a component.

**Eval metrics: the existing six, unchanged, plus the tour set scored by them.** `edge_groundedness` and
`citation_resolution` are the ones the tour can actually break, because a narrated path is where an
unapproved edge would slip into prose. Both are already gated at 100% on the free run.

`contested_disclosure` deserves a note: if the demo route crosses a contested pair, the disclosure event
must still fire before the first prose token. Step 8's scoring can prefer a route that crosses one, which
would make the most-demoed path also the one that shows the honest disagreement. That is a nice outcome
and it is a preference, not a requirement.

## 14. Cost, and the guardrail

**Bedrock:** the tour is a new query shape and step 5 will burn some tokens iterating. At the measured
6,624 input + 421 output tokens per query (~$0.009), a hundred development queries is about a dollar. The
60,000-token accumulation cap and the turn cap both still apply.

**No live eval re-baseline is triggered** — §4 and step 7. That is the expensive thing in this project and
this plan routes around it deliberately.

**CloudFront egress for the video: not the risk, and I checked rather than assuming.** The always-free tier
is 1 TB out per month. A 6 MB backdrop served to a thousand visitors is 6 GB, or 0.6% of it. **The cost of
video here is load performance, not dollars** — which is why step 0 gates bytes and nothing gates spend.

**Fixed monthly infrastructure stays approximately $0.** No new always-on resource, no new managed service,
nothing outside the existing S3 and CloudFront. Scope DoD item 7 asks for that verified against a real bill
rather than the estimate, and that verification is a phase 7.5 item.

## 15. Genuinely uncertain

- **Whether candidate B beats candidate A on the actual page.** Pre-rendered video is the better bet on
  paper and I would build it first. But a rAF loop that reflows to the viewport may simply look better
  than a fixed-aspect file cropped by `object-fit: cover`, and I will not know until step 1 renders both.
- **Whether the timeline primitive survives contact with the camera.** The cue-list shape is the third time
  this project has designed a "one ordered structure" and the first two — the walked path in v0.1, the
  motion frame in phase 5 — both changed shape once something real read from them.
- **How much of step 4 is worth doing.** Motion on the page chrome is the least measurable work in the
  phase and the easiest to keep fiddling with. The scope doc's first named risk is that polish is
  unbounded, and step 4 is where that risk actually lives. If a step gets cut for time, this is the one.
- **Whether the tour tool really lands without touching the loop.** Door 4 has never been tested by a tool
  that plans rather than looks up. I expect it holds. I would not bet the phase on it.
