# Phase 8 — Membership Tour (v1.1)

> **Scope doc.** Written 2026-09-09, at the moment the phase was conceived, which is the rule: *"A phase
> conceived later gets its own scope doc when it is conceived."* Written before anything in it is built and
> before its IMPLEMENTATION doc exists — that doc is written immediately before phase 8 is built, not now,
> so it can absorb what phases 7 and 7.5 actually teach.
>
> **The slug is provisional.** `membership-tour` names the mechanism. If the build shows the phase is really
> about something else, rename it then rather than defending the name.

> **Amended 2026-09-11: this is no longer the first phase to open `ALLOWED_PREDICATES`.** Phase 7.6
> `classical-lineage` (v0.9, before v1.0) opens it first, for `studied_with` from Wikidata P1066. So
> phase 8 is the second opening. Whatever 7.6 builds for predicate-typed claims and hops is what this phase
> inherits rather than designs, and §4's question "whether the tour is one structure or two" has a
> first answer from 7.6: **mixed routes are one path with typed hops** (his decision, 2026-09-11, for
> teaching plus influence). Note what does not transfer: teaching and influence both run forward in
> time, and membership does not, so phase 8 still has to decide whether that answer is safe for it. §6's framing ("this phase is someone editing that line
> on purpose") now describes 7.6 first. Nothing else here changes: membership stays un-narratable until
> this phase, and §3's "no new corpus" still holds here, because the new corpus arrives in 7.6.

## 0. Why this phase exists, and why it is after v1.0

**It was found in phase 7 step 5's re-read, on 2026-09-09**, and the finding is recorded in
`phase-7-cinematic-surface-IMPLEMENTATION.md` step 5 and `SPEC.md` §1. The short version: the guided tour's
canonical route, *"take me from delta blues to Detroit techno"*, has **no path** at artifact v0.7.1 — not in
either direction, and not undirected either.

The measurement that explains it, and it is the whole premise of this phase:

| over | components | largest |
|---|---|---|
| `influenced_by` only (2,284 edges) | **138** | 534 |
| both predicates (`plays_genre` adds 2,782) | 7 | 1,465 |

**The corpus is one connected organism only when membership is counted.** That is not a defect and it is not
news — `CLAUDE.md` states it as the project's central claim, and `docs/graph-semantics.md` §5.2 records it as
the answer phase 6 delivered: *"the organism is connected through the people who play across it. Membership,
not an unbroken chain of genre-to-genre influence."*

**What is new is noticing that the product cannot show it.** The connectedness lives in `graph/`, in a
structure report and a component count. Every surface the user touches walks `influenced_by` and only
`influenced_by`, because `agent/claims.py:62` is
`ALLOWED_PREDICATES = frozenset({PREDICATE_INFLUENCED_BY})`. The thesis is true, measured, and undemonstrable
by the thing built to demonstrate it.

**Why it is a phase and not a step.** `phase-7-cinematic-surface.md`'s not-list already ruled: *"If something
here requires editing a seam, that is a finding and it belongs in its own phase."* A second predicate through
the deterministic gate is a seam.

**Why it comes after v1.0 — decided with sjtroxel, 2026-09-09.** Three reasons, and the first is the one
that settles it:

1. **The showcase works without it.** Step 5 retargeted the demo to
   `Detroit techno -> Chicago house -> hip-hop -> rhythm and blues -> blues` — four hops, every hop sourced.
   This phase is upside, not a blocker for a release.
2. **It moves the claim model.** Phase 7.5's writeup describes how grounding works. Changing what the gate
   admits the week before that gets written is how a writeup describes a system that no longer exists.
3. **It costs the live gates.** New eval cases hit `eval/thresholds.py:_ungateable`, which returns before any
   per-metric check and un-gates the entire live suite. Restoring the bounds is **$2.61 and roughly 2.4
   hours** over five identical runs. v1.0 should not be paying that.

## 1. What this phase is for

**To make the thesis walkable rather than merely true.**

A tour that crosses from a genre to the musicians who played it and back out into another genre is the
project's own claim, performed. It is also the more honest claim: what actually connects musical genres in
history is people who moved between them, not an unbroken chain of derivation, and this is the only phase
that lets the product say so.

## 2. Delivers

- **A second predicate through the gate.** `plays_genre` claims, gated by the same deterministic check that
  `influenced_by` claims pass, carrying their own `MEMBERSHIP_*` verification tiers.
- **A cross-axis route.** Genre to artist to genre, planned and walked, with each hop's predicate visible
  rather than flattened into "connected".
- **Disclosure that makes membership structurally unable to read as derivation.** The hard part, and §4
  treats it as the phase's central decision rather than an implementation detail.
- **The eval cases**, in their own dataset, scored by the existing metrics.
- **The delta blues route, answered** — the sentence that started this, made true rather than retired.

## 3. Explicitly not in this phase

New corpus or new ingestion. Any change to `influenced_by` semantics. Making `checks_disagree` reachable —
it stays declared `UNREACHABLE` in `agent/claims.py` and this phase does not touch it. Re-running the
held-out set. Anything that lets `plays_genre` be narrated as derivation, in prose or in a caption or in a
tooltip; that is not a bug to be found in review, it is the failure mode this phase is most likely to ship.

## 4. Key decisions this phase makes

- **Whether a membership hop is a `Claim` at all.** This is the phase, and both answers cost something.
  - **As a claim:** `ALLOWED_PREDICATES` admits `plays_genre`, the gate checks it against the artifact like
    any other edge, and `synthesize` can narrate it. Every existing grounding metric covers it for free. The
    risk is that one claim type now means two different things, and a UI or a sentence that treats them alike
    states something false about history.
  - **Beside the claims:** the shape phase 6.5 chose for `Contested` — a distinct event, gated by its own
    disclosure check, riding *next to* the narration and never inside it, because `synthesize` takes exactly
    one claim-bearing parameter and a second one reintroduces the claims-first leak. The risk is a tour whose
    prose goes silent at exactly the hop that makes the thesis.
  - **Neither is obviously right and the IMPLEMENTATION doc decides with the code in front of it.** What is
    already decided: whichever wins, `verification` and `corroboration` stay two fields, and a membership
    tier never reads as an influence tier.
- **Whether the tour is one structure or two.** A route that alternates predicates may be one path with typed
  hops, or an influence chain with membership bridges between chains. That choice determines what
  `PathWalked.chain` means, and `chain` currently has a contract — descendant-first, claim-ordered, empty
  when a hop was rejected — that a mixed route may not satisfy.
- **What the answer says when a route exists only through membership.** *"These two genres share musicians"*
  is true and useful. *"These two genres are connected"* is the sentence that quietly becomes derivation in
  the reader's head.

## 5. Definition of done

1. A cross-axis query returns a route whose every hop is gated, cited, and **typed** — the predicate of each
   hop is in the payload, not inferred from the node kinds at its ends.
2. `delta blues -> Detroit techno` is answerable, and its answer names membership as membership.
3. A test asserts that no prose path exists by which a `plays_genre` hop can be narrated as influence. Not a
   review checklist; a test, in the shape of `ContestedDisclosure`.
4. `verification` and `corroboration` remain two fields, and a `MEMBERSHIP_*` tier never appears where an
   influence tier is expected.
5. The tour's eval cases run in the free suite, and the live suite reports its gates rather than a
   `NOT GATED` banner. If restoring the live bounds is required, that is an explicit spend decision at a
   freeze, taken by sjtroxel, not a side effect of this phase.
6. `agent/loop.py` is unmodified, or the edit is a finding recorded in bold in the IMPLEMENTATION doc.
7. `make check` green, and the repo root still inside its cap.

## 6. The one-way door, named up front

`ALLOWED_PREDICATES` is a one-line frozenset with a comment above it explaining that it is *"a second lock on
the same door"* — the first being that P279 is not ingested at all. Its whole purpose is that a corpus which
later carries a taxonomic predicate cannot have it narrated as derivation **without someone editing that line
on purpose.**

**This phase is someone editing that line on purpose.** That is legitimate, and it is exactly why it gets a
scope doc, a decision record, and a disclosure test rather than a commit. The thing to preserve is the
property, not the line: after this phase there must still be no path by which a non-influence edge reaches
prose as an influence claim. If the phase cannot hold that property, the phase is wrong and the corpus keeps
its 138 influence components.

## 7. Known risks

- **The failure is invisible and it flatters.** A membership hop narrated as influence produces a fluent,
  cited, plausible sentence about music history that is false. Every metric this project owns would score it
  perfectly, because the edge is real and the citation resolves. This is the same shape as the phase 2
  synthesis bug where an unrecognised claim set rendered as an origins query with a blank subject and every
  metric read 100%.
- **`plays_genre` is per-row noisy.** `graph-semantics.md` records it: P136's meaning is not in question, its
  risk is an artist tagged with a genre they barely touched. 2,782 edges is a lot of surface for that.
- **A cross-axis route is longer and less legible.** Four influence hops read as a story. Genre to artist to
  genre to artist to genre may read as a graph traversal, which is what it is and not what a demo wants.
- **Scope creep back into the tour.** The camera work, the timeline and the route ranking all belong to phase
  7 and are done by the time this starts. If this phase finds itself adjusting motion, it has drifted.

## 8. Left for the IMPLEMENTATION doc

Which of §4's two shapes a membership hop takes, and the reasoning with the code in front of it. Whether the
route planner is a new tool or an argument to `trace_lineage` — noting that a new tool is the answer the seam
was built for. What the tour's eval cases are and where they live. Whether the live suite is re-gated in this
phase or at the next freeze, and what that costs. Whether `delta blues -> Detroit techno` is still the demo
anyone wants by then, or whether step 8's ranked pick has already found something better.
