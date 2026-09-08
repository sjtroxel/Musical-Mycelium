# Phase 7 — Cinematic Surface (v0.8)

> **Scope doc.** Written 2026-07-30, before building. Re-read it at the start of phase 7 and amend it where
> phases 1–6 taught something different — it was written before any of this existed.
>
> **AMENDED 2026-09-08 AT PHASE START — §0. This phase was split in two and this file kept half.** It was
> `phase-7-polish-and-portfolio.md` and covered both halves; the portfolio half now lives in
> `phase-7.5-portfolio-and-writeup.md`. **Nothing below is withdrawn or deleted** — the Delivers and
> Definition-of-done lists are annotated in place with which half each item went to, because a scope doc
> that quietly loses four items is worse than one that is honest about being split.

## 0. The split, decided 2026-09-08 at phase start

This doc's own instruction, from the top of *What this phase is for*: *"If this phase starts to feel like
two phases, it is — split it, the way Patchwork gained 4.5 and 4.6 mid-arc. The up-front phase map is a
map, not a contract."* It does, and it has been.

**What forced it.** Two things arrived at once. The design half stopped being a coat of paint: on
2026-09-08 sjtroxel scoped full-page video backdrops and a motion-graphics pass as a named deliverable,
which is a build with a renderer, an asset pipeline and a byte budget in it, not a styling pass. And this
doc's own first named risk is *"polish is unbounded."* Four deliverables — tour, design, report, writeup
— inside a phase carrying that risk is how the risk collects.

| | **phase 7 — cinematic surface (v0.8)** | **phase 7.5 — portfolio and writeup (v1.0)** |
|---|---|---|
| Delivers | guided tour, signature moment, backdrop, motion system, demo route | eval report page, trend view, README, writeup, recruiter path, coverage position |
| DoD items from §Definition of done | **1, 2, 8**, plus **9, 10, 11** added the same day | **3, 4, 5, 6, 7** (restated in that doc's §5, not referenced) |
| Shape | build | build plus prose |
| His hands | picks treatments, picks the route | **writes the writeup himself** |

**Why the numbering is 7 and 7.5 rather than 7 and 8.** 7.5 records that these were one phase and were
carved apart, which is the same thing 6.5 records. An 8 would imply a phase that was always planned
separately, and none was.

**Why the product version skips v0.7.** The artifact pin is v0.7.1. `ROADMAP.md` §2 already names reading
the product line as the artifact line as "the confusion this header exists to prevent," and a product v0.7
sitting beside an artifact v0.7.1 is that confusion delivered rather than prevented. **Phase 7 is v0.8 and
phase 7.5 is v1.0**; v0.7 is deliberately never used.

**v1.0 moved to 7.5, and that is the honest place for it.** v1.0 is the release a recruiter is pointed at.
That is the writeup, the report and the README — not the day the camera first moves.

## What this phase is for

To make the project land on someone who did not build it. Everything through v0.6 is correct, measured, and
visible. This phase makes it *memorable*: the guided tour, the moment where the narration and the camera move
on one timeline, ~~the writeup, and the recruiter surface~~ **and, added 2026-09-08, the backdrop and motion
that make it land in the first three seconds.** *(The writeup and recruiter surface are phase 7.5 — §0.)*

Two things are worth saying plainly at the top.

**First: this phase is not only polish, and the spine undersells it.** `planning/05` §5 describes v1.0 as
"polish, README, writeup, portfolio surface — no architecture change," but `SPEC.md` §1 commits the **guided
tour** to v1.0, and the guided tour is a real feature with a real agent behavior underneath it. "No
architecture change" is accurate; "polish" is not. If this phase starts to feel like two phases, it is —
split it, the way Patchwork gained 4.5 and 4.6 mid-arc. The up-front phase map is a map, not a contract.

**Second: this phase is not the point.** Resume-ready is roughly v0.3–v0.4 (`ROADMAP.md` §1). By the time
this phase starts, the deployed URL and the published eval numbers already exist and have already done their
job in the job search. That ordering is written down so a bad week does not relitigate it, and it means v1.0
can be reached calmly or not at all without the project having failed.

> **Amended 2026-08-24, at the phase 4 close.** Half of that had happened by v0.4 and half had not. **The
> eval numbers exist and are real** — 41 development cases against a live model, a measured noise floor, a
> validated non-Anthropic judge, a sealed held-out set opened once at 10/10. **The deployed URL still runs
> a template stub**, because the Bedrock redeploy was deferred to phase 5. So the sentence above describes
> a state that phase 5 creates, not one this phase inherits automatically. If phase 5 ships the SPA without
> the redeploy, then this phase starts with the resume line still unclaimable, and closing it outranks
> everything in the list below.
>
> > **SUPERSEDED 2026-09-08, and the prediction was right.** Phase 5 shipped the SPA and phase 6 shipped the
> > redeploy: `v0.6.0` is tagged at `51f2c21` and deployed, the deployed `/health` serves artifact v0.7.1
> > with 7 components and 2 contested pairs, and a real Bedrock query streams a claim and its narration.
> > **The template stub is gone and the resume line is claimable.** This phase inherits a working deployed
> > product, which is the state the 2026-08-24 amendment hoped for and could not assume. Kept rather than
> > deleted because the amendment correctly named a dependency and correctly said what to do if it failed.

## Delivers

- **The guided tour — surface C.** "Take me from delta blues to Detroit techno." The agent plans a path
  between two nodes and narrates it as the camera walks it. This is the C-shaped query type from `SPEC.md`
  §2, honestly labeled all along as arriving later than the others.
- **The signature moment.** As the agent streams its reasoning, the graph animates the traversal it is
  describing: camera easing along the path, nodes illuminating as they are cited, the citation appearing as
  the claim is made. **One shared timeline driving both the text and the view.** This is only possible
  because streaming was chosen in v0.1, and it is the single most demo-able thing in the project.
- ~~**The full eval report**, published — per-metric, per-slice, with judge-human agreement and the noise floor
  on the page — plus a historical trend view over stored runs.~~ **→ phase 7.5.**
- ~~**The writeup**, assembled from the per-phase plain-English explanations written as each phase was built,
  not reconstructed at the end.~~ **→ phase 7.5.**
- ~~**The portfolio surface:** README, the recruiter path, the demo script, and the media.~~ **→ phase 7.5.**
- ~~**A stated coverage position.** What the graph covers, what it does not, and why — visible, not
  apologized for.~~ **→ phase 7.5.**

**Added 2026-09-08, the design half, and it is the reason the split happened:**

- **The backdrop.** A full-page motion backdrop behind the hero. The treatment is decided in the running
  app rather than here, but the position is not: **three of the four candidates render the actual corpus**
  — the real pinned graph through the real layout code — rather than stock footage, because on a project
  whose whole pitch is that what you see traces to something checkable, a bought clip is a small
  dishonesty and *"the background is the graph"* is a better sentence in a live round.
- **The motion system.** Page chrome that moves with intent: hero type, chip row, panel entrances, claim
  rows arriving. Extending the tested `motion.ts`, not importing a library — see the IMPLEMENTATION doc's
  step 4 for the cost of overruling that.
- **An asset budget that gates bytes.** The project gates six correctness properties and zero bytes, and
  the next thing it does is add video. The budget lands before the first frame does.

## Explicitly not in this phase

New corpus, new metrics, new tools, a new agent capability that is not the tour. Any architectural change. If
something here requires editing a seam, that is a finding and it belongs in its own phase.

## Key decisions this phase makes

- ~~**Whether the tour is its own phase.**~~ **DECIDED 2026-09-08 — §0.** Looking at what 5 and 6 actually
  produced, as instructed: phase 5 left a real canvas renderer with a tested motion module, and phase 6 left
  a corpus dense enough to walk. Both make the tour *cheaper* than it looked. Neither makes it *small*. The
  tour stays in phase 7; the **portfolio half** is what left.
- **What the timeline primitive is.** The narration and the camera must be driven by one ordered structure,
  not two loops that happen to agree. This is the one place where getting it right early matters, and the
  walked-path-in-order decision from v0.1 exists to make it possible.
- ~~**How the coverage position is worded.**~~ **→ phase 7.5.** The risk it names is real and unchanged;
  the decision now belongs to the phase that writes the copy.
- ~~**What the recruiter sees in thirty seconds**, and what is one click deeper.~~ **→ phase 7.5.**
- **Added 2026-09-08: the backdrop treatment, and the media byte budget.** Both decided in the running app
  from rendered candidates, the way the palette and the motion mode were decided in phase 5. Neither is
  decided here and neither is decided from taste alone: the budget comes from what the candidates weigh.
- **Added 2026-09-08: animation library or hand-rolled motion.** The IMPLEMENTATION doc recommends
  hand-rolled and states the cost of overruling it. It is a real trade, not a free win.

## Definition of done

1. A two-node query produces a planned path, narrated as the camera walks it, with citations resolving as
   claims are made.
2. Narration and camera are driven by one timeline, demonstrably — desynchronization should be impossible by
   construction, not merely unobserved.
3. ~~The published eval report includes slices, judge-human agreement, and the noise floor.~~ **→ 7.5.**
4. ~~The trend view reads stored historical runs rather than a hand-maintained table.~~ **→ 7.5.**
5. ~~The writeup exists and he can walk through it cold. This is the articulation rep, and it is the point of
   having written it phase by phase.~~ **→ 7.5.**
6. ~~`terraform destroy` still removes everything, and `terraform apply` still rebuilds it.~~ **→ 7.5.**
7. ~~Fixed monthly infrastructure cost is still approximately $0, verified against a real bill rather than the
   estimate.~~ **→ 7.5.**
8. Nothing in the repo overstates what "grounded" means. **Stays in both.** 7.5 owns the copy audit, but a
   backdrop and a tour can overstate grounding on their own — a camera that walks an edge the gate did not
   approve is the claims-first leak with a lens on it.

**Added 2026-09-08, and each is checkable rather than tasteful:**

9. The backdrop never plays under `prefers-reduced-motion`, ~~never loads under `prefers-reduced-data`~~
   **(moot from 2026-09-08 — candidate A ships no file, so there is nothing to withhold on a metered
   connection; the rule died with step 2 rather than being dropped)**, pauses
   when the tab is hidden, and **pauses the moment a run starts streaming and does not resume for that run.**
   Ambient motion yields to semantic motion, and it is a test rather than an intention.
10. `make check` fails on an over-budget `dist/`, with the budget split by asset class.
11. The demo route is chosen from a ranked measurement of path density, not from taste, and its numbers are
    written down.

## Known risks

- **Polish is unbounded.** There is no natural stopping point, which is why the definition of done above is
  eight checkable items and not "it feels finished." *(2026-09-08: this risk is the one that collected. It is
  why the phase split, and it is why the design half arrives with a byte budget attached rather than a mood.)*
- **This phase competes with the job search and has the weakest claim on the time.** Items 2 and 3 of the
  priority stack, and 1 beats both (`ROADMAP.md` §1).
- **The honest-claim slide.** Portfolio copy is written to persuade, and "every edge traces to a checkable
  source" is one careless edit away from "every edge is correct." Wikidata can be wrong, musical influence is
  genuinely contested, and contested claims are flagged rather than resolved. Audit the copy for this
  specifically. *(2026-09-08: the tense was wrong when written. `contested` was arithmetically unreachable
  until phase 6 step 4 ingested DBpedia; it is reachable now, 2 pairs at artifact v0.7.1, and phase 6.5 step
  4 shipped the disclosure surface. The risk is unchanged. The copy audit itself is **phase 7.5**.)*
- **The signature moment being demoed on a thin graph.** If phase 6's density work did not reach the region a
  demo walks through, the demo shows the corpus skew rather than the system. Pick the tour route from
  measured density, not from taste.
- ~~**Cold articulation, one last time.**~~ **→ phase 7.5**, which is where the writeup is.
- **Added 2026-09-08: ambient motion competing with semantic motion.** The signature moment *is* motion, on
  the most important surface, carrying real information. A loop playing behind it is smoother, larger and
  never stops, so the eye goes to the thing moving for no reason instead of the thing moving because a claim
  passed the gate. DoD 9 is the containment.
- **Added 2026-09-08: bytes.** The page already ships ~2.9 MB, 2.6 MB of it the graph. Video is the first
  asset class in this project that can grow without anything noticing. DoD 10 is the containment.

## Left for the IMPLEMENTATION doc

The timeline primitive's shape; the tour's path-planning behavior and how it differs from the A-shaped query
path; ~~the report's published location; the trend view's storage format;~~ **(→ 7.5)** the demo route;
~~the writeup's structure;~~ **(→ 7.5)** the media list.

**Added 2026-09-08:** the backdrop treatment and how it is rendered; the asset budget's classes and numbers;
whether the tour tool lands without editing `agent/loop.py`; and where the tour's eval cases live — which is
not a free choice, because adding one case to the live set un-gates the entire live suite until a $2.61
re-measure. All of it is in `phase-7-cinematic-surface-IMPLEMENTATION.md`.
