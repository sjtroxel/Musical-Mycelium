# Phase 5 — SPA and Visualization (v0.5)

> **Scope doc.** Written 2026-07-30, before building. Re-read it at the start of phase 5 and amend it where
> phases 1–4 taught something different — it was written before any of this existed.
>
> **Amended 2026-08-24, at phase 5 start.** It was re-read and four things had gone stale. See §0. The
> sections below are unedited except where a marked blockquote says otherwise. The as-built plan is
> [`phase-5-spa-and-visualization-IMPLEMENTATION.md`](phase-5-spa-and-visualization-IMPLEMENTATION.md).

## 0. What phases 2–4 changed

Read this before the sections below. This doc was written before the corpus, the agent, the eval suite, or
a single Bedrock call existed — it is the oldest unamended plan in the repo, and four of its assumptions
did not survive.

### It inherits the Bedrock redeploy, and that goes first

Phase 4 closed its DoD #8 as **partial** on 2026-08-24 and deferred the redeploy into this phase, because
phase 5 needs a live backend anyway and the auth-and-throttling decision should be made once. This doc
predates that by 25 days and does not mention it.

By `ROADMAP.md` §1's ordering it is the highest-priority item here: priority 2 is *a deployed URL plus real
eval numbers*, the eval numbers closed on 2026-08-24, and this is the other half. **It is step 0.** Until
it lands, "deployed on AWS Lambda and Bedrock" is not claimable.

### "the subgraph the API already returns" — the API does not return one

Verified 2026-08-24: `api/app.py` registers exactly two routes, `/health` and `/lineage`. `/lineage`
streams a *trace* — `plan`, `tool`, `claim`, `rejected`, `path`, `token`, `done` — from which a client can
reconstruct the walked path and the approved claims. That is enough for DoD #3. It is **not** enough for
DoD #4's *follow an edge*, which needs neighbour data the stream never sends.

Resolved without a backend edit: the pinned artifact is **640 KB raw, 56 KB gzipped**, so the whole graph
ships to the browser as a static asset and the map is client-side. Pan, zoom and follow-edge then cost
zero Lambda invocations. Detail in the IMPLEMENTATION doc §4.2.

### The chip set it points at is four-sixths blocked

Of `SPEC.md` §2.2's six aspirational chips, one answers, one refuses deliberately, and **four are blocked
on phase 6's second source**. The chip row is therefore drawn from §2.1's validated five plus the two
working §2.2 rows. **Six chips, one refusal** — decided by sjtroxel 2026-08-24.

### Two of its four "key decisions" are already made

- **The imagined user** is answered: **a music-curious adult.** No music theory and no Wikidata literacy
  assumed; every genre gets a one-clause gloss and `P737` never appears on screen. `SPEC.md` §4 is updated
  to match.
- **The rendering engine and the time axis are still open**, and both are decided in this phase via
  throwaway previews against the real graph — not from the planning docs. The measured complication the
  planning docs could not know: **832 of 973 nodes carry no inception date** (28 of 169 genres, and all
  804 artists), so "is time a spatial axis" is really "where do 832 undated nodes go".

## What this phase is for

To give the graph a face. Through v0.4 the client is `curl` and the product is a stream of text with
citations in it. This phase builds the React + TypeScript SPA on S3 and CloudFront, renders the graph, and
turns the explorable map — surface B in `SPEC.md` §1 — into something a person can wander.

The architectural bet from `planning/05` §2.2 gets cashed here: **the frontend is a two-way door.** The API
contract is the boundary, so this SPA can be thrown away and rebuilt twice without touching the backend.
That is what makes design ambition safe in this phase and only in this phase.

This is also the first phase where design work is allowed at all. Nothing before v0.5 gets a palette, a
layout, or a logo, and that restraint is deliberate: design before the skeleton exists is procrastination
wearing a nice font.

## Delivers

- **The React + TypeScript SPA**, scaffolded **inside `web/`** — its `package.json` never reaches the repo
  root — built to S3 and served through CloudFront, provisioned by Terraform like everything else.
- **The first screen from `SPEC.md` §1:** a search box with 5–7 canonical query chips beneath it. No blank
  page, and the chips double as the demo script.

  > **Amended 2026-08-24 — see §0.** Six chips, one of them a refusal. The §2.2 set this pointed at is
  > four-sixths blocked on phase 6.

- **Graph visualization** of the subgraph the API already returns, with the agent's walked path rendered in
  order rather than reconstructed.
- **Surface B, the explorable map** — wander, zoom, follow edges, ask the agent to annotate. It falls out of
  rendering a graph the API already returns, but it is a commitment, not a byproduct.

  > **Corrected 2026-08-24 — see §0.** "the subgraph the API already returns" and "falls out of rendering a
  > graph the API already returns" are both **false**: there are two routes and neither returns a subgraph.
  > Surface B does not fall out of anything. It is delivered by shipping the pinned artifact to the browser
  > as a static asset — which is why it remains a commitment rather than a byproduct, exactly as this
  > bullet insisted.
- **Citations visible as claims are made**, not collected in a footer. The 30-second recruiter path is: land,
  click a chip without inventing a question, watch a cited lineage stream in, leave remembering that every
  edge had a source.
- **Coverage rendered honestly.** Thin regions look thin. This is the design decision doing epistemic work
  (`planning/06` §5.3) and it is the strongest interview story in the phase.
- **The favicon and the logo.** Identity work that was deliberately held until there was something to put it
  on.

## Explicitly not in this phase

The guided tour and the synchronized narration-and-camera moment — those are v1.0 and they are the showcase,
not the scaffolding. New agent capability, new corpus, new metrics. Auth of any kind: this is public,
read-only data, there is nothing to protect, and statelessness is an invariant, not an omission.

## Key decisions this phase makes

- **The rendering engine, decided knowing the target.** SVG and canvas libraries are excellent for modest
  graphs and awkward for smooth camera work over thousands of nodes; WebGL renderers handle scale and
  animation and cost more effort. **The signature moment in v1.0 argues for WebGL** (`planning/06` §6). Decide
  it here, deliberately, rather than by default — v1.0 inherits this choice and cannot cheaply revisit it.
- **Layout, then palette, then motion, in that order**, each through 3–6 throwaway preview files rendered and
  compared side by side rather than argued about in prose. Headless Chromium is already on this machine.
- **Whether time is a spatial axis.** Anchoring an axis to real chronology turns the layout into an argument:
  influence flows one way, eras become bands, the sparse ancient end looks ancient rather than accidentally
  empty. Force-directed placement is the default and the default is mush.
- ~~**The imagined user**~~ — `SPEC.md` §4, left open on purpose and due here. It sets reading level and how much
  context each answer assumes, and SPA copy cannot be written without it.

  > **Answered 2026-08-24 by sjtroxel: a music-curious adult.** No music theory assumed, no Wikidata
  > literacy assumed, every genre glossed in a clause, `P737` never on screen. This decision is closed;
  > `SPEC.md` §4 carries it.

## Definition of done

> **Amended 2026-08-24.** A tenth item is added, and it comes first: **the Bedrock redeploy** (§0), which
> this doc could not know it was inheriting. An eleventh covers the refusal treatment — see the
> IMPLEMENTATION doc §10.

0. `llm_provider = bedrock` on the deployed stack, per-query cost reaching CloudWatch, and the resume line
   "deployed on AWS Lambda and Bedrock with a deterministic groundedness gate at 100%" **true**.
1. A public CloudFront URL loads the SPA and the first screen renders a search box with the canonical chips.
2. Clicking a chip streams a cited lineage, with citations appearing as claims are made.
3. The graph renders the returned subgraph and highlights the walked path in the order it was walked.
4. The map is explorable: pan, zoom, follow an edge, request an annotation.
5. **The frontend loads instantly even when the agent takes twenty seconds to think.** These are separate
   problems and only the second one is allowed to be slow (`planning/04` §8.5).
6. `prefers-reduced-motion` is respected. Animation that cannot be turned off is a defect.
7. Coverage is visible in the interface, not disclaimed in a footnote.
8. `web/` contains the entire frontend and the root entry count is unchanged.
9. The backend was not edited to accommodate the frontend.

## Known risks

- **This is the phase most likely to eat the project.** Design is unbounded and the previews are enjoyable.
  The fence is the sequence — engine, layout, palette, motion — and the fact that the tour is v1.0.
- **The engine choice is the one expensive decision here.** Everything else in this phase is a two-way door;
  swapping renderers after the motion system is built is not.
- **Motion in the critical path of first paint.** The hard rule exists because the fix is architectural, not
  a tweak.
- **A beautiful front end over a thin graph.** If phase 6's density work is what the visualization actually
  needs, that is a finding worth acting on rather than papering over with animation.
- **Scope pressure from v1.0.** The guided tour will look reachable from inside this phase. It is not this
  phase, and pulling it forward is how v0.5 becomes v1.0 with no eval work in between.

## Left for the IMPLEMENTATION doc

The engine pick; the layout system; the palette and type scale; the motion vocabulary; the chip set as
finalized in `SPEC.md` §2; the CloudFront and S3 Terraform module; the build-and-deploy CI job; how the
streaming response is consumed in the browser; the imagined-user answer and what it changes about the copy.
