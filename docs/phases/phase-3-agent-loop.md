# Phase 3 — Agent Loop (product v0.3.0, pinned to artifact v0.5.0)

> **A3, 2026-08-07 — two version lines, and they collided.** The ROADMAP maps this phase to **v0.3** while
> the *artifact* is already at **v0.5.0** and phase 5 maps to product **v0.5**. "v0.3 runs against v0.5.0"
> reads like a typo and is not one. The two lines are independent and always were: the **product version**
> tracks phases, the **artifact version** tracks the corpus. This phase ships **product v0.3.0** against
> **pinned artifact v0.5.0**, and `ROADMAP.md` §2 now labels both columns. Doc fix only, no code change.

> **Scope doc.** Written 2026-07-30, before building. Re-read it at the start of phase 3 and amend it where
> phases 1 and 2 taught something different — it was written before any of this existed.
>
> **AMENDED 2026-08-07, approved by sjtroxel.** It was written before the corpus, the artist axis, the
> deploy pipeline and the Bedrock quota block existed, and five items rested on assumptions those
> falsified. Amendments **A1** (contested has no substrate), **A2** (the tool list), **A3** (product
> version vs artifact version), **A4** (the Bedrock deferral and `v0.3.0-local`) and **A5** (three DoD
> items are closer to done than assumed) are applied below and marked inline. The reasoning is in
> `phase-3-agent-loop-IMPLEMENTATION.md` §1 — that is the record, this is the map.
>
> **A1.1 added the same morning**, after `docs/reviews/2026-08-07-fable-threshold-review.md` found that
> A1's replacement mechanism rested on a premise the artifact falsifies. The **decision** was sound; the
> **enum** was not. Per-claim `verification` ships instead. Read A1.1, not A1's first draft.
> Also from that review: `describe_node` emits no proposals, and the gold set plus the sealed held-out 10
> are now a hard precondition on step 8 rather than phase 4 work.

## What this phase is for

To make the agent an agent. Phase 1 ships a loop that can call two tools and take one hardcoded hop; phase 2
gives that loop a real graph to walk. This phase is where the loop starts *deciding* — planning a traversal
before executing it, choosing among five to eight tools, cross-referencing what it finds, and stopping when
it has enough rather than when a counter runs out.

> **A5, 2026-08-07.** The paragraph above understates where the build actually is, and the understatement
> matters because it makes three DoD items look unbuilt. As of artifact v0.5.0 the loop already has
> **three registered tools**, direction-aware multi-hop traversal reaching **six hops**, a deterministic
> gate with five checks and seven rejection reasons, and **refusal shipped as a real non-model code path**.
> Phase 3 is therefore not "make the loop real" — it is **planning, breadth, corroboration and
> measurement** on a loop that already works. DoD #4 is already met; DoD #5 is half met by construction.

This is the phase the project is actually about. Everything before it exists so that this one has somewhere
to stand, and everything after it is measurement, presentation, and density. It is also the phase that makes
the resume claim true: **v0.3 is the point where "deployed on AWS Lambda and Bedrock with a deterministic
groundedness gate at 100%" is fully claimable** (`ROADMAP.md` §1).

> **A4, 2026-08-07, decided by sjtroxel — the phase splits at the Bedrock line, and the resume claim
> travels with the Bedrock half.** Inference has never once succeeded on this account. AWS confirmed on
> 2026-08-06 that the block is an account-level provisioning fault at the runtime layer, named the root
> cause, and has an open internal review to restore the standard allocation. There is no ETA and no action
> owed by us.
>
> So the phase ships in two pieces:
>
> - **`v0.3.0-local`** — every deliverable that needs no model. This is the shipping gate, and it is most
>   of the phase.
> - **`v0.3.0`** — the Bedrock-dependent remainder, closed whenever quota lands, with **phase 4 as its
>   named home** if quota is still absent when the local work is done. Phase 4 cannot ship without real
>   model output anyway, so the dependency already exists there.
>
> **The resume line is NOT claimable at `v0.3.0-local`.** `planning/09` §3 puts the resume-ready threshold
> at v0.3–v0.4 and notes September timing favours claiming it early, so this is a real cost of the split
> and it is recorded rather than glossed. The mitigating fact is that the alternative was not "claim it
> sooner" — it was "build nothing for an unknown number of days."
>
> **If quota is still absent at the start of phase 4**, that is the point at which invariant 7 gets
> exercised for real and `build_llm` is pointed at a non-Bedrock provider. That is a budget decision, not
> a free swap.
>
> ---
>
> **A4 UPDATE, 2026-08-11: quota landed.** Access was restored hours after step 7b, so the deferral
> structure was never needed and the non-Bedrock fallback is off the table. Two consequences worth
> stating rather than assuming:
>
> - **The `v0.3.0` remainder is now reachable**, gated only by the gold set and held-out 10 — which are
>   *his* work and deliberately not schedule-pressured (see the IMPLEMENTATION doc's "After the release
>   step").
> - **The resume line is still not claimable at `v0.3.0-local`**, and being able to call Bedrock does not
>   change that. What makes it claimable is the loop running end to end against a real model with the
>   groundedness gate measured on that run. A verified provider seam is not that. The split's cost was
>   real and is not retroactively refunded by the quota clearing.

The seam under test is invariant 4. Adding a tool must never require editing the loop. If it does, the seam
is broken, and finding that out here is the whole reason the tool contract was written in phase 1.

## Delivers

- **A planning step.** Given a query, the agent produces an explicit traversal plan before executing it, and
  the plan is inspectable rather than implicit in the transcript.
- **Five to eight tools behind the registry** — graph node lookup, neighbors, path, semantic search over
  node embeddings, source resolution, and artifact-backed text retrieval. Registered, not hardcoded.

  > **A2, 2026-08-07.** **Seven tools**, and two of the six named above are dropped for cause.
  >
  > **Dropped — "semantic search over node embeddings."** Embeddings mean either a Bedrock embedding
  > model (spend; the quota wall this clause also cited is gone as of 2026-08-11, but the spend argument
  > was always the load-bearing one) or a local model (a large
  > dependency inside a 250MB-capped image). Both are the wrong trade for a 973-node corpus where
  > `store.search()` already resolves labels and where the honest failure — refusing an unresolvable
  > name — is a *feature* rather than a gap. Moved to the ROADMAP backlog.
  >
  > **Dropped — "artifact-backed text retrieval."** It has no substrate. There is no prose in the
  > artifact; nodes carry `label`, `kind`, `inception_year`, `inception_precision`, `countries` and
  > provenance. Replaced by `describe_node`, which returns the fields that exist.
  >
  > The seven: `resolve_node`, `get_influences`, `trace_lineage` (all three already shipped), plus
  > **`get_descendants`**, **`describe_node`**, **`resolve_source`** and **`corpus_coverage`**.
  >
  > **`get_descendants` closes a real gap rather than adding a feature.** `Direction.INFLUENCED` has been
  > supported by `GraphStore` since phase 2 and **no registered tool exposes it**, so "what came out of
  > the blues?" is currently unanswerable except as a side effect of `trace_lineage` between two named
  > nodes. It is the highest-value tool in the phase.
  >
  > **`corpus_coverage` is registered last, deliberately** — it returns a shape unlike any other tool (no
  > node id in, no edges out, **no proposals at all**), which makes it the strongest available test of
  > invariant 4. A tool contributing nothing to the claim set also checks that the loop does not assume
  > every result does.

- **Cross-referencing.** The agent consults more than one source for a claim and represents agreement,
  disagreement, and single-sourcing as distinct states.
- **Contested as a first-class output state.** Where sources disagree, the claim is emitted flagged, not
  resolved and not dropped.

  > **A1, 2026-08-07, decided by sjtroxel — THE amendment of this phase. Contested has no substrate in
  > this corpus, and shipping it anyway would be the exact overclaim this project exists to avoid.**
  >
  > **Every edge in artifact v0.5.0 has exactly one source, and that source is always Wikidata.**
  > `resolve_sources()` returns a 1-tuple or an empty tuple; no code path produces two. So "supported by
  > two sources" has no substrate, and "two sources in conflict" has less. `agent/claims.py:19` already
  > anticipated this in phase 1 — contested *"arrives with the data that justifies it, in phase 2 or 6"* —
  > and phase 2 did not bring it.
  >
  > **A1.1, SAME MORNING — RECALIBRATED after Fable's threshold review. Read this, not the first draft.**
  >
  > A1 first shipped a three-state `Corroboration` enum (`multiply_checked` / `single_check` /
  > `checks_disagree`) on the premise that *"`select_edges()` re-admitted 6 of 7 hand-REJECTED edges."*
  > **That is backwards.** `ingest/wikidata.py` rule 2 puts hand-rejected edges **out** — the human
  > verdict wins, the pairs go to a separate `overruled` list, and all three spot-checked pairs are
  > **absent from v0.5.0**. All 950 edges are `prose_tier: PROSE`. Phase 2 resolved every check
  > disagreement *by exclusion*, so **`checks_disagree` has population zero — structurally unreachable,
  > exactly like `contested`.** `multiply_checked` was also unsound: prose check plus assertion filter
  > are sequential stages of one pipeline over the same text, so counting them as independent would
  > have marked 80% of the corpus corroborated.
  >
  > **What ships instead — per-claim `verification`, and it is less code than the enum.**
  >
  > `Claim` gains a `verification` field, **copied by `gate()` off the artifact edge exactly as
  > `source_ids` already is**, and surfaced per claim in the stream. Four states, all reachable, all
  > from data the corpus already carries:
  >
  > | state | count in v0.5.0 | means |
  > |---|---|---|
  > | `HAND` | 22 | a human read the source article and judged that it asserts influence |
  > | `PROSE_AUTO` | 111 | the automated prose check passed, and nothing more |
  > | `ASSERTS_AUTO` | 760 | the influence-assertion filter accepted it |
  > | `EXPOSURE_AUTO` | 57 | documented contact short of a stated influence claim; **20% recall** |
  > | `contested` | — | **RESERVED. Needs a second SOURCE.** Test-locked unreachable. |
  > | `checks_disagree` | — | **RESERVED. Needs a corpus policy that flags rather than excludes.** Test-locked unreachable. |
  >
  > **This meets DoD #3's actual requirement better than the enum would have.** Today verification is
  > published only in aggregate; a reader of a five-claim answer cannot tell which claims rest on a
  > human reading and which rest on documented exposure. After this, they can. The field's docstring
  > must say these tiers record **how strongly one source was checked** — not how many sources agree,
  > and not whether anything is disputed.
  >
  > **The 6-of-7 overruled count is real and belongs in the manifest** — but it is an ingest statistic
  > over edges that are not in the artifact, and this phase cuts no artifact. **Phase 6 item.**
  >
  > Still rejected, unchanged: shipping `contested` as-named over the verification tiers.
- **Refusal as a real behavior.** An unsourced influence edge is refused rather than narrated, and the
  refusal is legible to the caller rather than swallowed.

  > **A5 (cont.), 2026-08-07 — already shipped.** `agent/loop.py:311` refuses via a deterministic
  > template with no model call, and `api/app.py` maps it to a `refused` SSE frame. Verified live
  > 2026-08-06: the SPEC signature query for Kate Bush correctly refuses, because she has zero outgoing
  > P737. This deliverable is re-scoped from **build** to **prove** — a regression test, not new code.

- **Model routing.** Traversal and tool turns go to the cheap model; synthesis goes to the stronger one.

  > **A4 (cont.).** The **seam** is local work and ships in `v0.3.0-local`: `build_llm` grows a role,
  > and the routing is proven by passing two distinct `ScriptedLLM` instances and asserting each script
  > was consumed by the right half of the loop. **Which models fill the two slots is not decided here**
  > and cannot be until a `converse` call succeeds — `agent/llm.py:26` says so already and is right.
  > Bedrock is partner-operated and prices separately from the first-party API, so **no first-party
  > per-token figure may be quoted as a Bedrock cost anywhere in this repo.**
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

**Added 2026-08-07 by A2:** semantic search over node embeddings, and artifact-backed text retrieval. The
first moves to the ROADMAP backlog; the second has no substrate and is replaced by `describe_node`.

**Added 2026-08-07 by A1:** true contested detection. It needs a second source and belongs to phase 6.

**Added 2026-08-07 by A4:** no new artifact version. The corpus does not change in this phase, so
re-cutting it would invalidate every prior benchmark for nothing. **Everything here pins artifact
v0.5.0.**

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

  > **A1 (cont.).** Decided, and the answer is that **none of those three situations can arise in this
  > corpus** — one source per edge, always Wikidata. The distinction that *is* available is between
  > independent **checks**, not sources, and the vocabulary changes to match. See A1 above. The original
  > sentence stays on the page because it remains the correct decision to make **once a second source
  > exists**, which is phase 6's job.
- **Where untrusted text is delimited.** Retrieved content is data, never instructions, and it never reaches
  a tool-invocation decision unmediated (`planning/04` §6.3).

## Definition of done

> **AMENDED 2026-08-07 by A1 and A4.** Item 3 is renamed to what the corpus can support. Items 5, 6 and 8
> each split along the Bedrock line, because each had a deterministic half and a model-behaviour half
> welded together. **LOCAL** items are the shipping gate for `v0.3.0-local`; **BEDROCK** items defer to
> `v0.3.0`, with phase 4 as their named home.

| # | Item | Needs |
|---|---|---|
| 1 | A query produces an inspectable plan, then a traversal that follows it | LOCAL |
| 2 | **Seven** tools registered and callable, and the last one added required no edit to the loop | LOCAL |
| 3 | **Every approved claim carries its own `verification` tier in the output** — `HAND` / `PROSE_AUTO` / `ASSERTS_AUTO` / `EXPOSURE_AUTO` distinguishable per claim, not only in aggregate; `contested` **and** `checks_disagree` both declared unreachable and locked by a test *(A1.1 — was: two sources / one source / contested, then briefly a three-state corroboration enum)* | LOCAL |
| 4 | A false-premise query is refused, and the refusal is reported as a refusal *(already met — regression test)* | LOCAL |
| 5 | A planted injection string in a fixture is ignored, and a test fails if that stops being true | LOCAL |
| 6 | Refusal accuracy reported as a **pair** — true refusals and false refusals — over the adversarial set against scripted traces | LOCAL |
| 7 | Results sliced by era, region, density and query type, with sparse slices reported rather than averaged away | LOCAL |
| 8 | Cheap-model and strong-model turns are routed separately through `build_llm`, proven with two distinct providers | LOCAL |
| 9 | Phase 2's eval still passes against the same pinned artifact | LOCAL |
| 10 | The model ignores an injected instruction in a real tool result *(split from 5)* | BEDROCK |
| 11 | Refusal accuracy and traversal recall measured on real model output *(split from 6)* | BEDROCK |
| 12 | Token cost per query measured and emitted to CloudWatch; the working model ID recorded *(split from 8)* | BEDROCK |

**`v0.3.0-local` ships when 1–9 are green.** Items 10–12 close whenever Bedrock does.

**Slices with n < 5 are reported with their n rather than a percentage.** A 100% on two items is not a
100%, and item 7 exists to stop exactly that.

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

> **A4 (cont.), 2026-08-07 — two risks the original list could not have anticipated.**
>
> - **Scripted-green read as model-competent.** Everything in `v0.3.0-local` proves the *machinery* routes,
>   gates and measures correctly. **None of it proves a real model plans well or picks correctly among
>   seven tools.** That is the actual open question of this phase, it cannot be answered without Bedrock,
>   and a green local suite must never be presented as evidence that it can. This is the single most
>   likely way this phase produces an overclaim.
> - **The deferred step quietly becoming permanent.** Mitigated structurally rather than by intention:
>   the Bedrock-dependent tests are **written now** and marked `@pytest.mark.costs_money` (the marker
>   `pyproject.toml` already registers for exactly this), deselected by default. They stay visible and
>   counted in every suite run. A test that does not exist is a task nobody remembers; a skipped test is
>   a standing reminder.
>
> **A third risk, added by the 8/7 review: the eval-contamination window closes at step 8.** Because
> Bedrock has never completed a call, nothing in this repo can currently be contaminated by model output
> — a state of grace that ends the moment step 8 runs. The full gold set and the sealed held-out 10 must
> therefore be authored **before step 8**, not in phase 4. They may trail steps 2–7.

## Left for the IMPLEMENTATION doc

The exact tool list and their schemas; the plan object's shape; the turn and token budgets; the contested
detection rule; which models fill the cheap and strong slots; the adversarial set's 15–20 cases; how slicing
is keyed off the artifact's era and region fields.

> **2026-08-07 — all of these are now settled in `phase-3-agent-loop-IMPLEMENTATION.md`, except one.**
> Tool list and schemas: §4.2. Plan shape: §4.3. Budgets: §4.4 — `MAX_TURNS` 5 → 8, plus a token budget,
> because turns are a poor proxy for spend when every turn re-sends accumulated context. Corroboration
> rule: §4.4 per A1. Adversarial set: §4.1, **18 cases, hand-authored before any loop code** per the
> standing rule that a dataset written after watching the agent fail is a dataset shaped by the agent.
> Slicing: §4.7, keyed off `coverage.era_of`, `Node.countries`, verification tier and `Plan.query_kind`.
>
> **Still open, and correctly so: which models fill the cheap and strong slots.** That is step 8 and it
> needs one successful `converse` call. See A4.
