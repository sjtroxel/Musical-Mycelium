# Phase 3 — Agent Loop (v0.3)

> **Scope doc.** Written 2026-07-30, before building. Re-read it at the start of phase 3 and amend it where
> phases 1 and 2 taught something different — it was written before any of this existed.

## What this phase is for

To make the agent an agent. Phase 1 ships a loop that can call two tools and take one hardcoded hop; phase 2
gives that loop a real graph to walk. This phase is where the loop starts *deciding* — planning a traversal
before executing it, choosing among five to eight tools, cross-referencing what it finds, and stopping when
it has enough rather than when a counter runs out.

This is the phase the project is actually about. Everything before it exists so that this one has somewhere
to stand, and everything after it is measurement, presentation, and density. It is also the phase that makes
the resume claim true: **v0.3 is the point where "deployed on AWS Lambda and Bedrock with a deterministic
groundedness gate at 100%" is fully claimable** (`ROADMAP.md` §1).

The seam under test is invariant 4. Adding a tool must never require editing the loop. If it does, the seam
is broken, and finding that out here is the whole reason the tool contract was written in phase 1.

## Delivers

- **A planning step.** Given a query, the agent produces an explicit traversal plan before executing it, and
  the plan is inspectable rather than implicit in the transcript.
- **Five to eight tools behind the registry** — graph node lookup, neighbors, path, semantic search over
  node embeddings, source resolution, and artifact-backed text retrieval. Registered, not hardcoded.
- **Cross-referencing.** The agent consults more than one source for a claim and represents agreement,
  disagreement, and single-sourcing as distinct states.
- **Contested as a first-class output state.** Where sources disagree, the claim is emitted flagged, not
  resolved and not dropped.
- **Refusal as a real behavior.** An unsourced influence edge is refused rather than narrated, and the
  refusal is legible to the caller rather than swallowed.
- **Model routing.** Traversal and tool turns go to the cheap model; synthesis goes to the stronger one.
- **The adversarial eval set, hand-authored and running** — refusal accuracy, injection resistance, contested
  flagging, and result slicing (`planning/07` §12).

## The eval boundary with phase 4, stated because it is genuinely blurry

`planning/07` §12 assigns the adversarial set, refusal accuracy, injection resistance, contested flagging,
and slicing to **v0.3**, not v0.4. That is deliberate and it is not a scoping error: those five measure
behaviors that do not exist until this loop exists, and a behavior shipped unmeasured is a behavior nobody
can defend in an interview.

The split is therefore: **phase 3 ships the metrics for the behaviors phase 3 introduces. Phase 4 ships the
suite** — the judge, validation, the noise floor, thresholds set from measured baseline, the held-out set,
metric unit tests, and the report. If phase 3 starts growing a report generator, that belongs to phase 4.

The adversarial set is **hand-authored before the loop is coded**, same rule as the gold set. A dataset
written after watching the agent fail is a dataset shaped by the agent.

## Explicitly not in this phase

The SPA, any visualization, the guided tour, the judge, narrative-quality scoring, the held-out set, density
work beyond what phase 2 ingested, caching, and any design work. `curl` is still the client.

## Key decisions this phase makes

- **The tool registry contract.** What registering a tool costs: a schema, a handler, and nothing else. This
  is the decision the phase exists to prove, so it gets tested by adding the last tool *after* the loop is
  considered finished and confirming the loop file does not change.
- **How planning is represented.** An explicit plan object the agent emits and then executes against, versus
  planning that is emergent in the tool-call sequence. The first is inspectable, evaluable, and streamable
  to a future UI; the second is less code. Lean explicit — the guided tour in v1.0 needs a plan to narrate.
- **Loop termination.** Turn budget, token budget, and a stop condition that is a judgment rather than a
  cap. Agentic loops are input-heavy: every turn re-sends accumulated context, so an unbounded loop is a
  cost bug before it is a latency bug.
- **What cross-referencing means concretely.** Two sources asserting the same edge, one asserting and one
  silent, and two in conflict are three different situations and only one of them is "contested."
- **Where untrusted text is delimited.** Retrieved content is data, never instructions, and it never reaches
  a tool-invocation decision unmediated (`planning/04` §6.3).

## Definition of done

1. A query produces an inspectable plan, then a traversal that follows it.
2. Five to eight tools are registered and callable, and the last one added required no edit to the loop.
3. A claim supported by two sources, a claim supported by one, and a contested claim are distinguishable in
   the output.
4. A false-premise query is refused, and the refusal is reported as a refusal.
5. A planted injection string in a fixture is ignored, and there is a test that fails if it stops being.
6. Refusal accuracy is reported as a **pair** — true refusals and false refusals — never as one number.
7. Results are sliced by era, region, density, and query type, and the sparse slices are reported rather
   than averaged away.
8. Cheap-model and strong-model turns are routed separately, and token cost per query is measured.
9. Phase 2's eval still passes against the same pinned artifact.

## Known risks

- **Cost.** This is the first phase where the agent burns real tokens per query and the loop can run away.
  The mitigation is a hard turn budget from the first commit, not after the first surprising bill.
- **Refusing everything scores perfectly.** A system that refuses every query has zero hallucinations and no
  value. This is why the metric is a pair, and why it is stated here rather than discovered in phase 4.
- **The tool seam failing quietly.** It breaks by erosion — one special case in the loop for one tool that
  "just needs" it. The test is mechanical: add a tool last, diff the loop.
- **Injection through ingested content.** Wikipedia and MusicBrainz are user-editable. Treat all retrieved
  text as untrusted data.
- **Scope creep into phase 4.** The line between "measure the behavior I just built" and "build the eval
  suite" is thin, and `planning/04` §8.2 flags scope creep as a documented pattern. The boundary above is
  the fence.
- **Cold articulation.** Write the plain-English explanation of the loop, the plan, and the gate **as this
  is built**, not after. This phase is the hardest one to explain cold and the most likely to be asked about.

## Left for the IMPLEMENTATION doc

The exact tool list and their schemas; the plan object's shape; the turn and token budgets; the contested
detection rule; which models fill the cheap and strong slots; the adversarial set's 15–20 cases; how slicing
is keyed off the artifact's era and region fields.
