# Phase 7 — Polish and Portfolio (v1.0)

> **Scope doc.** Written 2026-07-30, before building. Re-read it at the start of phase 7 and amend it where
> phases 1–6 taught something different — it was written before any of this existed.

## What this phase is for

To make the project land on someone who did not build it. Everything through v0.6 is correct, measured, and
visible. This phase makes it *memorable*: the guided tour, the moment where the narration and the camera move
on one timeline, the writeup, and the recruiter surface.

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

## Delivers

- **The guided tour — surface C.** "Take me from delta blues to Detroit techno." The agent plans a path
  between two nodes and narrates it as the camera walks it. This is the C-shaped query type from `SPEC.md`
  §2, honestly labeled all along as arriving later than the others.
- **The signature moment.** As the agent streams its reasoning, the graph animates the traversal it is
  describing: camera easing along the path, nodes illuminating as they are cited, the citation appearing as
  the claim is made. **One shared timeline driving both the text and the view.** This is only possible
  because streaming was chosen in v0.1, and it is the single most demo-able thing in the project.
- **The full eval report**, published — per-metric, per-slice, with judge-human agreement and the noise floor
  on the page — plus a historical trend view over stored runs.
- **The writeup**, assembled from the per-phase plain-English explanations written as each phase was built,
  not reconstructed at the end.
- **The portfolio surface:** README, the recruiter path, the demo script, and the media.
- **A stated coverage position.** What the graph covers, what it does not, and why — visible, not
  apologized for.

## Explicitly not in this phase

New corpus, new metrics, new tools, a new agent capability that is not the tour. Any architectural change. If
something here requires editing a seam, that is a finding and it belongs in its own phase.

## Key decisions this phase makes

- **Whether the tour is its own phase.** Decide this at phase start by looking at what phases 5 and 6
  actually produced, not now.
- **What the timeline primitive is.** The narration and the camera must be driven by one ordered structure,
  not two loops that happen to agree. This is the one place where getting it right early matters, and the
  walked-path-in-order decision from v0.1 exists to make it possible.
- **How the coverage position is worded.** This is where "grounded" is most likely to slide into "correct"
  under the pressure of writing marketing copy for your own work. It must not.
- **What the recruiter sees in thirty seconds**, and what is one click deeper.

## Definition of done

1. A two-node query produces a planned path, narrated as the camera walks it, with citations resolving as
   claims are made.
2. Narration and camera are driven by one timeline, demonstrably — desynchronization should be impossible by
   construction, not merely unobserved.
3. The published eval report includes slices, judge-human agreement, and the noise floor.
4. The trend view reads stored historical runs rather than a hand-maintained table.
5. The writeup exists and he can walk through it cold. This is the articulation rep, and it is the point of
   having written it phase by phase.
6. `terraform destroy` still removes everything, and `terraform apply` still rebuilds it.
7. Fixed monthly infrastructure cost is still approximately $0, verified against a real bill rather than the
   estimate.
8. Nothing in the repo overstates what "grounded" means.

## Known risks

- **Polish is unbounded.** There is no natural stopping point, which is why the definition of done above is
  eight checkable items and not "it feels finished."
- **This phase competes with the job search and has the weakest claim on the time.** Items 2 and 3 of the
  priority stack, and 1 beats both (`ROADMAP.md` §1).
- **The honest-claim slide.** Portfolio copy is written to persuade, and "every edge traces to a checkable
  source" is one careless edit away from "every edge is correct." Wikidata can be wrong, musical influence is
  genuinely contested, and contested claims are flagged rather than resolved. Audit the copy for this
  specifically.
- **The signature moment being demoed on a thin graph.** If phase 6's density work did not reach the region a
  demo walks through, the demo shows the corpus skew rather than the system. Pick the tour route from
  measured density, not from taste.
- **Cold articulation, one last time.** This is the phase whose output is most likely to be read by someone
  who will then ask him about it in a live round.

## Left for the IMPLEMENTATION doc

The timeline primitive's shape; the tour's path-planning behavior and how it differs from the A-shaped query
path; the report's published location; the trend view's storage format; the demo route; the writeup's
structure; the media list.
