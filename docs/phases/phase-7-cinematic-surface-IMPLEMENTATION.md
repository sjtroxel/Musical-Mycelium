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
- `@media (prefers-reduced-motion: reduce)` at `styles.css:959`, already honoured.

## 3. The scope doc, re-read: four places reality moved

Required by the `start-a-phase` skill, and all four are real.

1. **"The deployed URL still runs a template stub" is stale.** That amendment was written 2026-08-24 and
   phase 6 closed it: `v0.6.0` is tagged at `51f2c21` and deployed, `/health` serves artifact 0.7.1, and a
   real Bedrock query streamed a claim and its narration. **This phase inherits a working deployed
   product**, which is the state the scope doc hoped for and could not assume.
2. **"Polish, no architecture change" undersells it, and the scope doc already said so.** It is right. The
   guided tour is a new agent behaviour and the backdrop is a new asset class with a new build step.
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
   skipped**. `classify` sends anything it does not recognise to `shell`, which carries the smallest cap,
   so a new asset type arriving unannounced fails a build instead of being silently exempt. A budget that
   ignores what it does not recognise stops covering the thing it was written for, which is the failure
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
   before the number could be set. Measure the thing the gate measures, not its neighbour.

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

### Step 1 — Treatments, behind throwaway previews

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

### Step 2 — The backdrop renderer

`web/scripts/render-backdrop.mjs`. Playwright drives an offscreen page running the real `layout.ts` over
the real pinned graph, captures a fixed frame count from a fixed seed with no wall-clock input, and hands
the frames to `ffmpeg`.

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

### Step 3 — The backdrop component, and the rules that are tests

`web/src/components/Backdrop.tsx`. A `<video muted playsinline loop preload="none" poster=...>` behind the
hero, plus `Backdrop.test.tsx`.

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

**Done when:** every new motion honours `prefers-reduced-motion`, the script budget still passes, and the
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
