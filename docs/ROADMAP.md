# ROADMAP — Musical Mycelium

The version spine, the scaffolding ledger, and the decision history. `CLAUDE.md` is the short version of
the invariants; this is the depth. Contracts live in `SPEC.md`.

## 1. What this project's job is

Stated once, because it settles arguments when two things compete for a session
(`planning/09-PRIORITIES-AND-OPEN-DECISIONS.md` §1):

1. **The job search.** The build never displaces an application that would otherwise have been sent.
2. **This project's job within that search:** close the AWS gap with a **deployed URL plus real eval
   numbers** — the two things a recruiter or an interviewer can actually touch.
3. **The project as a project** — density, the SPA, the cinematic traversal, v1.0 polish.

On a tired week, 2 beats 3, and 1 beats both.

**Resume-ready is roughly v0.3–v0.4, not v1.0.** Deployed URL, real agent loop, published eval numbers.
This is written down now so a bad week does not relitigate it later.

> **Corrected 2026-08-24.** This paragraph read *"'Deployed on AWS Lambda and Bedrock with a deterministic
> groundedness gate at 100%' is fully claimable at v0.3."* **It is not claimable, at v0.3 or at v0.4.**
> The gate half is true and measured. The *deployed on Bedrock* half is not: the public URL runs
> `llm_provider=local`, and the redeploy was deliberately deferred to phase 5 (`KNOWN-GAPS.md`, DoD #8).
> **That deferral ended the same day: phase 5 step 0 shipped the redeploy on 2026-08-24, and the line IS
> claimable now.** The correction stands as the record of a claim that was false for 25 days.
> Every other place in this repo states this correctly — the phase 3 ledger below, `KNOWN-GAPS.md`,
> `README.md`, `docs/eval-suite-explained.md`. This was the one place it slipped, and it is the section
> that feeds recruiter copy, which is exactly why it is corrected in place rather than quietly edited.
>
> **What IS claimable at v0.4**, and it is not a small list: a hand-built Bedrock Converse tool loop
> measured across 41 development cases; a deterministic groundedness gate at 100% and citation resolution
> at 100%; a noise floor measured over five identical runs before any threshold was set; a validated
> non-Anthropic judge with agreement reported as a range beside every judged number; and a sealed
> held-out set opened once at 10/10. What is missing is the redeploy, not the work.

## 2. The version spine

From `planning/05-EVOLUTION-PLAN.md` §5. Read the right-hand column: no row requires rewriting a previous
row. That is what planning for expansion actually means — not predicting the feature set, but making sure
every future addition lands in a slot that already exists.

**Two version lines, and they are independent.** The **product** version tracks phases; the **artifact**
version tracks the corpus. They have now crossed — phase 3 ships product v0.3.0 against artifact v0.5.0 —
so both columns are labeled. Reading one as the other is the confusion this header exists to prevent.
*(Clarified 2026-08-07, phase 3 scope-doc amendment A3. Doc fix only.)*

| Phase | Product version | Artifact pin | What thickens | Which seam absorbs it |
|---|---|---|---|---|
| **0** `scaffold-and-spine` | — | — | The repo itself | Complete 2026-07-29 |
| **1** `walking-skeleton` | **v0.1** | v0.1.0 | Everything present, connected, deployed, and tiny | — |
| **2** `corpus-and-traversal` **DONE 2026-08-06** | **v0.2** | **v0.5.0** | Full corpus ingested; real multi-hop traversal | `GraphStore` impl + ingestion artifact; agent untouched |
| **3** `agent-loop` **DONE 2026-08-12** | **v0.3** | **v0.5.0** (unchanged) | Real agent loop: planning, **7** tools, corroboration | Tool registry; loop untouched |
| **4** `eval-suite` **DONE 2026-08-24** | **v0.4** | **v0.5.0** (unchanged) | The eval suite proper | Independent scorers over a pinned artifact |
| **5** `spa-and-visualization` **DONE 2026-09-02** | **v0.5** | **v0.5.0** (unchanged) | React + TS SPA on S3/CloudFront, graph visualization | A pure consumer of an already-stable API |
| **6** `density-and-coverage` **DONE 2026-09-06, `v0.6.0` deployed** | **v0.6** | **v0.7.1** | Density: **second sources**, geography, time; coverage displayed | Ingestion + artifact schema, additive fields |
| **6.5** `debt-and-disagreement` **COMPLETE 2026-09-07** | **v0.6.5** | **v0.7.1** (pinned, unchanged) | The behavioral half of phase 6, delivered: `contested` reaches an answer, three honest refusal states, `ResolveSource` verifies DBpedia, 9 gold + 2 adversarial cases, a sixth gate, and a live suite gated on a measured floor | Agent package, which phase 6 DoD #6 forbade |
| **7** `cinematic-surface` **COMPLETE 2026-09-09** | **v0.8** | **v0.7.1** (pinned, unchanged) | The guided tour, the signature moment on one timeline, and the design half: full-page backdrop, motion system, asset budget | Frontend, plus one tool behind the existing tool contract |
| **7.5** `portfolio-and-writeup` | **v1.0** | **v0.7.1** (pinned, unchanged) | The published eval report, the trend view, the writeup, the README and the recruiter path; the Terraform round-trip and a verified bill | No architecture change |
| **8** `membership-tour` **SCOPED 2026-09-09, not started** | **v1.1** | **v0.7.1** (pinned, unchanged) | The tour crosses axes: genre to artist to genre, so the corpus's one connected component becomes something the product can walk rather than a number in a structure report | `agent/claims.py:ALLOWED_PREDICATES`, a one-way door opened on purpose |

**Phase 8 was scoped on 2026-09-09 and is deliberately after v1.0.** It is the first phase past the
release, which is why it carries **v1.1** rather than extending the v0.x spine.
`docs/phases/phase-8-membership-tour.md` is the authority; the decision history below records why it sits
after 7.5 rather than before.

**Phase 7 was split in two on 2026-09-08**, along the line its own scope doc named: *"If this phase starts
to feel like two phases, it is — split it."* It did. `polish-and-portfolio` became **`cinematic-surface`**
(things that move) and **`portfolio-and-writeup`** (things that are read). Decision history below;
`phase-7-cinematic-surface.md` §0 is the authority.

**Product v0.7 is deliberately never used.** The artifact pin is v0.7.1, and the header above already names
reading one version line as the other as the confusion it exists to prevent. A product v0.7 beside an
artifact v0.7.1 is that confusion delivered rather than prevented, so the product line skips from v0.6.5 to
**v0.8**.

**Phases 3, 4 and 5 do not cut a new artifact.** The corpus does not change, and re-cutting it would
silently invalidate every prior benchmark for nothing. Phase 5's pin read `pinned, TBD` until 2026-08-24;
it is `v0.5.0` for the same reason phase 4's is — a frontend consumes the API, and the API reads whatever
the backend has pinned. **Phase 6 is the next new cut.**

~~**Phase 6 gained a named dependency on 2026-08-07:** a **second source per edge**.~~ **SATISFIED
2026-09-04, phase 6 step 4.** DBpedia's `dbo:stylisticOrigin` supplies 1,336 influence edges alongside
Wikidata's 949, so contested-claim detection stopped being unbuildable and **2 pairs are contested**.
Decision A1 is closed by its stated precondition arriving, not re-litigated. See
`phase-3-agent-loop.md` A1 and `phase-2-corpus-and-traversal.md` A7 for the original reasoning.

**AWS signup is phase 1's step zero**, not a phase: account on the paid plan, Bedrock model access, and budget
alarms armed. It is a gate, and one successful `converse` call is task one of the build.

### Phase doc status

Two layers per phase, written at different times — see `CLAUDE.md` for the rule and `.claude/skills/start-a-phase/`
for the workflow. Scope docs are written up front; IMPLEMENTATION docs are written immediately before each build.

| Phase | Scope doc | IMPLEMENTATION doc |
|---|---|---|
| 0 | written (retroactively) | written (as-built) |
| 1 | written | written (as-built) |
| 2 | written; **amended 2026-08-04 (A1–A4)**, **A5–A6.8 during the build**, **A7 retroactively 2026-08-07** | written 2026-08-04; **all 8 steps built, phase complete** |
| 3 | written; **amended 2026-08-07 (A1–A5)** | written 2026-08-07; **built; phase complete 2026-08-12, tagged `v0.3.0-local`** |
| 4 | written; **amended 2026-08-12 (§0, at the phase 3 release step)** | written 2026-08-15; **all 9 steps built, phase complete 2026-08-24, tagged `v0.4.0`** |
| 5 | written; **amended 2026-08-24 (§0) at phase start** | written 2026-08-24; **all 10 steps built, phase complete 2026-09-02, tagged `v0.5.0`** |
| 6 | written 2026-07-31, after the validation | written 2026-09-02; **steps 0-7 built 09-02 to 09-04; step 8 next** |
| 7 | written 2026-07-30; **amended 2026-08-24 (§0), and 2026-09-08 (§0) at phase start when the phase split** | **written 2026-09-08 at phase start; awaiting the build** |
| 7.5 | **written 2026-09-08**, at the moment the phase was conceived | at phase start — deliberately not yet, so it can absorb what phase 7 teaches |

Phase 6's scope doc was deliberately last. It is density and coverage, the phase most directly exposed to what
the P279 taxonomy can actually carry, and hand-validating the edges first meant it could be written against
evidence rather than assumption. That paid off: the validation falsified the assumption the phase was going to
be built on. See `docs/graph-semantics.md`.

**v0.1 definition of done:** a public URL that streams a grounded, cited, two-sentence answer about one
genre's origins, deployed by CI, provisioned by Terraform, with a passing eval in the pipeline and a budget
alarm armed. A deeply unimpressive product and a completely correct skeleton.

### Where the build actually is — 2026-09-09

**Phases 0 through 5 are COMPLETE. PHASE 6 IS BUILT — steps 0 through 10 are all done. PHASE 6.5 IS
COMPLETE — steps 0 through 8, all in one day, 2026-09-07.** Its as-built is
`docs/phases/phase-6.5-debt-and-disagreement-IMPLEMENTATION.md`; **read that rather than restating it
here.** The three decisions phase 6 left open are all now closed: the live threshold set was measured,
the noise floor was re-measured with it, and **the held-out set was NOT run and stays sealed at run
count 1.**

Tier 1 live at v0.7.1 (45 cases) and judged tier 2 both ran 2026-09-06, and the copy audit closed the same
day. **`v0.6.0` is tagged at `51f2c21` and deployed** — run `34058614241`, verified by hand: the deployed
`/health` serves artifact 0.7.1 with 7 components and 2 contested pairs, the SPA bundle carries the matching
pin, and a real Bedrock query streamed a claim and its narration. As-builts:
`docs/phases/phase-6-density-and-coverage-IMPLEMENTATION.md` §9.0 and §10.0. **The debt phase 6 could not
close was scoped as phase 6.5** — `docs/phases/phase-6.5-debt-and-disagreement.md` — **and phase 6.5 is
complete.**
`v0.3.0-local`, `v0.4.0` and `v0.5.0` are tagged; v0.6.0, v0.7.0 and v0.7.1 are cut but not tagged.

*(Two staleness bugs were fixed in this paragraph on 2026-09-08. It carried a dangling "What" from an
earlier edit, and it still said "what remains open from phase 6 is step 9's three decisions" — directly
contradicting the paragraph above it, which says all three closed. Both are the ordinary failure mode this
section keeps re-learning: a paragraph edited at the top and not at the bottom.)*

**PHASE 7 IS COMPLETE — 2026-09-09.** `phase-7-cinematic-surface.md` (v0.8): **steps 0, 1, 3, 4, 5, 5.5,
6, 7 and 8 are done**, step 2 was **deleted**, and step 5.5 was **inserted mid-phase**. The
definition-of-done audit is `phase-7-cinematic-surface-IMPLEMENTATION.md` §8.9 and the close is §8.10 —
**read those rather than restating them here.** The audit found one real defect (the backdrop did not
yield to the tour, because a replayed run never touches `steps`), which is the argument for auditing
rather than ticking. `phase-7.5-portfolio-and-writeup.md` (v1.0) carries the half
that left, and **its IMPLEMENTATION doc was written 2026-09-09, an hour after phase 7 closed** —
`phase-7.5-portfolio-and-writeup-IMPLEMENTATION.md`. That is the convention satisfied rather than jumped:
"immediately before 7.5 is built" is exactly a gap with no phase in it, and phase 7's lessons were as
fresh as they will ever be. ~~Phase 7.5 is planned and not started; step 0 is next.~~ **Approved and
under way 2026-09-10: step 0 is done** — the README's current-state figures are generated and gated —
**and step 0.5, the `_sentences` fix, was inserted ahead of the report and is done the same day. So is
step 1, the generated report page at `/report/index.html`, and step 2, the trend view on it. Step 3,
the v1.0 deploy with a real `terraform destroy`/`apply` round-trip, is next.**

**Step 4 built the motion system with no animation library and no Web Animations API** — CSS keyframes
on `transform` and `opacity`, with the delays computed by pure functions in `graph/motion.ts` so they are
testable where a running animation is not. It also produced two measurements worth carrying forward: a
prose token was costing a **full canvas redraw** before `memo` and a `useMemo` closed it, and the
backdrop's real per-frame cost is **0.90 ms at p95, 5.4% of a 60fps budget**, which cancelled the one
optimization the plan had queued. **`ENTER_MS` was compared in the running app and kept** — a keep
rather than a decisive pick, recorded that way; the two stagger constants were not part of that sitting.

**Measured 2026-09-09, not recalled:** `make check` green — **1465 passed**, 14 deselected, mypy clean
over **101** source files, frontend **210 passed** across 21 files, root 17 of 18, scripted eval gates
**4 passed / 0 failed / 2 N/A of six**. The asset budget reports script **268.4 KB of 320**, style
**10.7 KB of 40**, graph **2.57 MB of 3.00**, media **0 of 0**. *(The budget's `observed` fields had
drifted since step 0 and were re-measured on 2026-09-09; they are not gated, which is why nothing caught
it.)*

**The corpus has a second source, and `contested` is reachable.** Artifact **v0.7.1 is pinned** —
`graph/memory.py:34`, `ingest/wikidata.py:59` and the SPA's `GRAPH_PIN` all read it. 1,479 nodes and
5,066 edges, against v0.5.0's 973 and 950. The influence layer went 949 edges to **2,284** (measured 2026-09-06; 2,285 was the count before
`c697712` honored hand-rejected edges),
components 169 to **7**, and the deepest chain 6 hops to **12**. Decision **A1 is closed by its own
stated precondition arriving**: two pairs are now contested between sources.

**Three things a cold session most needs, all of which are easy to get backwards:**

1. **`contested` is REACHABLE and means two DIFFERENT sources disagree** — v0.7.1 holds 6 reciprocal
   pairs and only **2** are contested. "A reciprocal pair exists" overcounts by 3x.
2. **DO NOT DEPLOY is LIFTED — step 8, 2026-09-05.** Both pins read `0.7.1`, with
   `web/public/graph/v0.7.1/` staged. ~~The frontend pin deliberately lags at `0.5.0`~~ was true until
   then and is **stale — do not write it again.** A deploy is a step 10 act, not a casual one.
3. **The LIVE suite GATES AGAIN as of 2026-09-07, and there are SIX properties, not five.**
   ~~gates nothing~~, ~~zero of five evaluated~~: both stale, both false since step 7. Bounds were
   re-measured over five identical runs of the 56-case set ($2.61, ~2.4 hours) and all five runs pass
   all six gates. `contested_disclosure` joined at step 6. The **scripted** every-commit gates read
   **4 passed / 0 failed / 2 N/A of six**; do not read one for the other.

   **The number most likely to be misread is `traversal_recall` at 97.1%.** It was identical in all
   five runs and that is NOT stability: 37 cases score perfectly every run and `gold_v0_1_020` fails
   identically every run. `eval/thresholds.json` gates it **per case over those 37**, never as a band.
   A threshold written off the apparent 0.0pp spread would fire the first time that case is fixed.

`docs/KNOWN-GAPS.md` newest-first carries the as-built for every step; **read it rather than restating
it here.**

**The deployed CloudFront URL serves the finished phase 5 SPA** — the streaming cited answer, the
explorable map, the coverage panel and the mark. Verified 2026-09-02 by fetching the live bundle and
grepping it rather than by trusting a green workflow run: `index-C2MKRG0e.js` carries `setLineDash`,
the step 9 "solid outline" caption and the coverage panel, and all three icon assets serve 200.
~~The deployed URL serves the step 2 SPA~~ and ~~nothing since step 2 has been deployed~~ were true on
2026-08-31 and are **stale — do not write either again.**

**The cheapest check that a deploy built what you think it did:** the ECR image tag equals
`git rev-parse HEAD`. Measured `82061589629b` == `8206158` on the phase 5 deploy. A green workflow run
does not establish this; that comparison does.

~~**One live foot-gun before any phase 6 infrastructure work.**~~ **FIXED 2026-09-02 at phase 6 step 0:**
the `tf-*` targets now refuse to run without `IMAGE_TAG`, `LLM_PROVIDER` and `RESERVED_CONCURRENCY`, and
`tf-apply` / `tf-destroy` / `heldout-seal` are denied in `.claude/settings.json`.

> **This section was rewritten on 2026-08-24, and the rewrite is the point.** It used to be a running
> status board — an eight-row phase 2 step table, a phase 3 step table, a phase 2 definition-of-done
> audit, and the full AWS quota narrative — carried inline and hand-updated. The project outgrew that.
> Per-step as-built detail now lives in each phase's IMPLEMENTATION doc, the open-item list lives in
> **[`docs/KNOWN-GAPS.md`](KNOWN-GAPS.md)**, and findings that outlive the step that produced them are
> filed in §4 below. Three copies of the same status, drifting apart at different rates, is how the
> stale-doc problem starts, and by 2026-08-24 this section was eighteen days behind while the rest of
> the repo was current. What replaced it is a pointer and a small set of facts that are true right now.

| Phase | State | Detail |
|---|---|---|
| 0 `scaffold-and-spine` | complete 2026-07-29 | §3 below |
| 1 `walking-skeleton` | complete | `phase-1-walking-skeleton-IMPLEMENTATION.md` |
| 2 `corpus-and-traversal` | complete 2026-08-06, 8 steps | `phase-2-corpus-and-traversal-IMPLEMENTATION.md` |
| 3 `agent-loop` | complete 2026-08-12, tagged `v0.3.0-local` | `phase-3-agent-loop-IMPLEMENTATION.md` §11 |
| 4 `eval-suite` | complete 2026-08-24, 9 steps, tagged `v0.4.0` | `phase-4-eval-suite-IMPLEMENTATION.md` |
| 5 `spa-and-visualization` | **mid-build**, steps 0-7 of 11 | `phase-5-spa-and-visualization-IMPLEMENTATION.md` §12 |

**Corpus as shipped: artifact `v0.5.0`, 973 nodes, 950 edges** — 22 `HAND`, 111 `PROSE_AUTO`, 760
`ASSERTS_AUTO`, 57 `EXPOSURE_AUTO`. Live on AWS. `v0.1.0` through `v0.4.0` stay on disk and in S3 as
frozen records; `v0.1.0` and `v0.2.0` are deliberately unloadable under the current schema.

**Structure, measured rather than assumed:** 169 components over 973 nodes, largest 458, diameter 16,
and the deepest chain `path()` can return is **six hops**. The genre-only corpus those figures replaced
was 41 components, largest 31, deepest chain **two** — the artist axis is the entire difference, and
`tests/test_structure.py::test_the_depth_arrived_with_the_artist_axis` records both halves. Coverage is
likewise a computed number and ships on `/health`; the figures and the reasoning are in `SPEC.md` §6 and
`docs/graph-semantics.md`.

**CLOSED 2026-08-24 at phase 5 step 0.** This paragraph read *"the one gap with consequences outside the
repo: the deployed URL still runs `llm_provider=local`, so its prose is a template and its token counts
are synthetic."* The redeploy happened: deploy run `32780499772`, `model_id`
`us.anthropic.claude-haiku-4-5-20251001-v1:0` verified from the `done` frame, streaming at a 0.038
TTFB/total ratio, and per-query cost reaching CloudWatch from real usage. **Phase 4's DoD #8 goes from
partial to closed, and the resume line is true.** Detail and the four findings that came with it are in
`docs/KNOWN-GAPS.md`.

## 3. Scaffolding ledger

The point of this section is that nothing gets retrofitted. Past projects reached a point where CI, lint
config, or a dev runner had to be bolted on after the fact, and each of those retrofits was worse than
doing it first. The rule applied here: **structure now, content when its subject exists.** A Dockerfile
before a Lambda exists is not preparation, it is clutter.

### In place as of 2026-07-29

| Item | Where |
|---|---|
| Agent operating manual | `CLAUDE.md` |
| Agent rules: grounding, cost, graph semantics, evals | `.claude/rules/` |
| Phase-start workflow enforcing IMPLEMENTATION-doc-first | `.claude/skills/start-a-phase/` |
| Root-clutter audit command | `.claude/commands/root-check.md` |
| Commit/push and spend guardrails | `.claude/settings.json` |
| Python toolchain, single config file | `pyproject.toml` |
| Single-command entry point | `Makefile` (`make help`) |
| Local pre-commit guardrails | `.pre-commit-config.yaml` |
| CI: lint, types, tests, root cap | `.github/workflows/ci.yml` |
| Dependency freshness | `.github/dependabot.yml` |
| Package boundaries with contracts documented | `src/musical_mycelium/*/` |
| Architecture tests guarding the boundaries | `tests/test_architecture.py` |
| Secret and state leak prevention | `.gitignore` |
| Pinned dependency lockfile | `uv.lock` (committed; CI runs `uv sync --locked`) |
| Product shape and canonical queries | `SPEC.md` |
| Phase spine and the two-layer phase-doc pattern | `CLAUDE.md`, `docs/phases/` |
| Scope docs, **all phases 0–7** | `docs/phases/phase-{0..7}-*.md` (6 written 2026-07-31, after the validation) |
| Terraform 1.15.8, Docker Engine 29.6.2 | Installed on WSL2, 2026-07-30 |
| AWS account, `us-east-1`, PAID plan | Budget armed at $20 with 25/50/100% alerts; Cost Explorer on |

### Arrives with its subject, not before

| Item | Trigger |
|---|---|
| ~~Scope doc, phase 6~~ | **Done 2026-07-31.** Validation ran first, as intended |
| `infra/terraform/` | AWS account exists |
| `infra/docker/Dockerfile` | There is code to package |
| Deploy workflow with OIDC | AWS account exists; no long-lived keys, ever |
| `make dev` body | The v0.1 API exists |
| `web/` SPA scaffold | v0.5. Initialized **inside** `web/`, never at the root |
| Frozen eval datasets | Hand-authored **before** the agent is coded, or they are contaminated |
| Graph-viz engine choice | v0.5, via throwaway previews |
| ~~Logo and banner~~ | **Done 2026-09-02**, phase 5 step 10. Three noteheads on a beam, which is also the real `blues -> blues rock -> heavy metal` component. `web/src/components/mark.ts` |

### Local prerequisites

All present as of 2026-07-30: `uv`, Terraform 1.15.8, Docker Engine 29.6.2 (in-distro, not Desktop), Node 22,
Make. Python is 3.12 locally; `uv` provisions the 3.13 this project targets, so there is no `.python-version`
file.

**There is no remaining local prerequisite.** Bedrock was the last one and it cleared 2026-08-11; see
§4's `2026-08-11` entry for the full resolution. The account is live, both Terraform roots are applied, the
deployed Lambda serves a public streaming URL on `llm_provider=local`, and `BedrockLLM` has been executed
against the live Converse API.

**Two things to keep straight, because they are easy to conflate.** The *provider seam* is verified —
single-turn, streaming with real usage, and a real tool-use turn — and as of 2026-08-12 the *agent loop*
on top of it is verified too: plan, multi-tool traversal, gate, synthesis and prose, end to end against a
real model.

*(Corrected 2026-08-24. This paragraph continued "What is not demonstrated is real model behavior
**measured across a set**: refusal accuracy, traversal recall and injection resistance are recorded only
against scripted traces." **That has been false since 2026-08-16.** Phase 4 measured all three against a
live model over the 41-case development set, took a noise floor over five identical runs, ran a judged
tier 2 pass, and opened the sealed held-out set once at 10/10.)*

What remains true is narrower and it is the whole of it: **the deployed URL has not been redeployed onto
Bedrock**, so the live demo's prose is a template and its token counts are synthetic. The full list is
`docs/KNOWN-GAPS.md`.

## 4. Decision history

Decisions made before the repo existed live in `planning/00`–`09`. Recorded here from the point the repo
exists.

*(The five entries below were rescued from §2's status board on 2026-08-24 when it was replaced. They are
findings that outlive the step that produced them, which is what this section is for; the status board was
not.)*

- **2026-09-09 — Phase 8 `membership-tour` scoped at v1.1, and placed AFTER v1.0 rather than before it.**
  Found in phase 7 step 5's re-read: the guided tour's canonical route, *"take me from delta blues to
  Detroit techno"*, has **no path** at artifact v0.7.1 in either direction, and none undirected either.
  Measured the same day — over `influenced_by` alone the corpus holds **138 components, largest 534**;
  `Delta blues` sits in a two-node one with no sourced parents at all. The familiar **7 components, 1,465
  in the largest** counts `plays_genre`, which is precisely `CLAUDE.md`'s claim that the organism is
  connected through the people who play across it. **The thesis is true, measured, and undemonstrable by
  the product**, because `agent/claims.py:ALLOWED_PREDICATES` admits one predicate. Opening it is a seam,
  and phase 7's not-list already ruled that a seam edit *"belongs in its own phase"*.
  **Placed after v1.0 for three reasons**, in order of weight: the showcase works without it — step 5
  retargeted the demo to `Detroit techno -> ... -> blues`, four sourced hops, so this is upside rather than
  a blocker; a second predicate through the gate would move the claim model in the week 7.5's writeup
  describes it; and new eval cases hit `eval/thresholds.py:_ungateable`, which un-gates the entire live
  suite at a restoration cost of **$2.61 and roughly 2.4 hours**. Decided with sjtroxel the same day, who
  raised the phase and agreed the placement. **The alternative considered and rejected was inserting it as
  7.3**, before the portfolio half; rejected because it delays the release surface for a capability the
  release does not need.
- **2026-09-08 — Phase 7 split into 7 `cinematic-surface` (v0.8) and 7.5 `portfolio-and-writeup` (v1.0).**
  The scope doc written 2026-07-30 carried its own trigger — *"If this phase starts to feel like two
  phases, it is — split it"* — and its own first named risk, *"polish is unbounded."* Two things pulled the
  trigger on the same day. sjtroxel scoped **full-page video backdrops and a motion-graphics pass** as a
  named deliverable, which is a build with a renderer, an asset pipeline and a byte budget in it rather
  than a styling pass. And re-reading phases 5 and 6 as the scope doc instructed showed the tour is
  **cheaper** than it looked — phase 5 left a tested motion module, phase 6 left a corpus dense enough to
  walk — but not **small**. Four deliverables under an unbounded-scope risk is how the risk collects. The
  line the split follows was already there: **things that move** stayed in 7, **things that are read** went
  to 7.5. Numbered 7.5 rather than 8 because it records that these were one phase and were carved apart,
  the same thing 6.5 records. **Product v0.7 is deliberately skipped** — the artifact pin is v0.7.1 and §2
  already names reading one version line as the other as the confusion it exists to prevent. Authority:
  `phase-7-cinematic-surface.md` §0.
- **2026-09-08 — The tour's eval cases get their own dataset, because adding one live case costs $2.61.**
  Read out of `thresholds.py:592-612`, not recalled. `_ungateable` returns **before** any per-metric check,
  so the entire live suite prints `NOT GATED` the moment the live case count changes by one — it has
  already bitten twice, at 45 against 41 on 2026-09-06 and again at 56 after phase 6.5 step 5. Restoring
  the gates means re-measuring the floor over five identical runs: **$2.61 and about 2.4 hours**. The
  guided tour is a new query shape, so folding its cases into `gold_v0_1` would carry a bill that has
  nothing to do with the tour and would not surface until the next `make eval-live`. `tour_v1.json` is
  separate; gold stays at 38. `ThresholdSet.matches` keys on dataset **and** provider, so a new dataset
  name matches no set and prints the loud `render_unmatched` banner rather than silently borrowing a
  baseline measured over different questions. **The containment already existed; the decision is to not
  defeat it.**
- **2026-09-08 — The project gates six correctness properties and zero bytes.** Looked for an asset-weight
  guard before adding video and there is none: `make root-check` caps root *entries*, `thresholds.py` gates
  correctness, and the "split size guard" in the phase 6.5 step 6 commit message is about **threshold set
  sizes** — `git show 2957832 --stat` touches ten files, none in `web/`. `stage-graph.mjs:46` prints a KB
  figure and asserts nothing about it. Measured the same day: the SPA ships **236 KB of script, 10 KB of
  style and a 2.6 MB graph**, ~2.9 MB of real payload. A budget authored after the asset exists is a
  description of the asset rather than a constraint on it, so the budget lands as phase 7 step 0, before
  the first frame is rendered.

- **2026-09-02 — C1: the connectivity question is answered. Lineage from a second source, structure
  from membership.** The decision `docs/graph-semantics.md` §5 recorded as open and belonging to sjtroxel
  since 2026-07-31. What closed it was a measurement, not a preference: **the corpus already holds
  roughly 95% of every genre on Wikidata carrying a P737 influence edge at all** — 331 such edges exist in
  the whole of Wikidata and discovery was never bounded — so "ingest more genres" was never available.
  Density can only come from a second source. **DBpedia's `dbo:stylisticOrigin` has 5,124 genre-to-genre
  origin edges against Wikidata's 331**, and on the 459 corpus genres that align through `owl:sameAs` it
  corroborates 80 existing edges, adds **1,100** new ones, and **reverses the direction of 2 — which is
  what makes `contested` reachable for the first time.** *(Re-measured 2026-09-04 against v0.6.0. The
  alignment and new-edge figures read 155 and 237 until then, both measured on the 169-genre v0.5.0
  corpus before step 2 tripled the genre count; corroborated, corpus-only and reversed are unchanged
  because all three are scoped by the corpus's own 133 genre edges, which step 2 did not touch.)* Separately, `P136` (artist works in genre) joins the
  two axes that have never touched, at 1,313 pairs. **P279 is still not ingested**; P136 takes the
  structural role P279 was proposed for because it makes no derivation claim in any reading, where P279's
  whole risk was that it does. Full record: `graph-semantics.md` §5.2. Reasoning:
  `docs/phases/phase-6-density-and-coverage-IMPLEMENTATION.md` §3.
- **2026-09-02 — A deny pattern naming a command does not cover a wrapper that runs it.**
  `.claude/settings.json` denied `terraform apply` and `terraform destroy` while allowing `make *`, and
  `make tf-apply` / `make tf-destroy` run exactly those. The wrappers are now denied and the Makefile
  targets refuse to guess `image_tag`, `llm_provider` or `reserved_concurrency` rather than defaulting
  them — all three defaults disagreed with the live stack. **The guard inside the thing being run is the
  half that cannot be routed around by invoking it differently**; the deny pattern is defense in depth.
- **2026-08-09 — Delimiting untrusted text needs a return path.** Marking tool payloads without stripping
  the marks off *incoming* tool arguments breaks the walk it was protecting: a model hands a wrapped node
  id straight back and every id-taking tool answers `unknown node`. Found by building phase 3 step 5.
- **2026-08-09 — A streamed call reported no usage, so synthesis was billed and never counted.**
  Survivable while one model does everything; uncostable the moment two roles run on differently-priced
  models. `LLM.stream` is now `Generator[str, None, Usage]` and `done` reports cost **per role, never
  summed** — summing is a presentation choice belonging to whoever knows both prices.
- **2026-08-11 — A fabricated edge cannot reach the gate through a tool at all.** Every proposal is built
  by a tool from a real artifact edge, so the only channel by which a model states a triple of its own is
  `asserted_premise` on the plan turn. This narrowed the adversarial harness while it was being written,
  and it is a stronger result than the test it replaced.
- **2026-08-11 — The adversarial set only ever walks `HAND`-verified edges** — all 7 approved claims
  across 16 cases — so that baseline says nothing about the `PROSE_AUTO` majority of the corpus. A gap in
  the **dataset**, locked by a test so it could not quietly stop being true. **Closed 2026-08-14 by the
  completed gold set**, whose 67 claims break down `ASSERTS_AUTO` 29, `PROSE_AUTO` 21, `HAND` 15,
  `EXPOSURE_AUTO` 2 — all four tiers, with the two weakest deliberately walked rather than avoided.
- **2026-08-06 — Phase 2 met its definition of done with two items stated honestly rather than generously.**
  **DoD #3:** the artist axis works and `U2` returns six gated claims, but **Kate Bush has zero outgoing
  `P737` and seven incoming**, so the literal `SPEC.md` query *"Who influenced Kate Bush?"* **correctly
  refuses**. The capability shipped; the example chosen for it happens to be a node with no parents, and
  that refusal is now the corpus's best coverage-honesty demo rather than a defect. **DoD #6:** `run()`
  was not edited, but **`gate()` was**, once — it gained a `CROSS_AXIS` rejection so a genre-to-artist
  claim is refused rather than narrated. That is invariant 3 being enforced rather than the corpus being
  accommodated, but it *is* an edit to `gate()` caused by a corpus change, and calling it anything else
  would be reading the item generously.
- **2026-08-14 — The gold set is complete at 25 cases / 67 claims, and two schema decisions came with it.**
  Size decided by sjtroxel: 25, not the 27 of the composition draft — `.claude/rules/evals.md` requires
  20–30 and both sit inside it. **(a) `citation_status`**, an optional per-claim flag for claims whose
  supporting sentence Wikipedia leaves unsourced. Silence stays forbidden; what is now permitted is
  saying so out loud, with the sources searched recorded. The two obvious alternatives were both worse:
  attaching an article's general reference list passes the test while hiding the weakness, and dropping
  the cases buys a 100% citation rate by excluding the global south and then reports that rate as a
  property of the system. 8 of 67 claims carry it, and `tests/test_gold_set.py` locks the count.
  **Searching other languages before flagging is mandatory** — it rescued two of four candidates, and
  `kuduro`'s Spanish citation is the strongest in the set. **(b) The gold harness became shape-aware.**
  Every case had carried a `shape` field since v0.1 and **nothing read it**; three separate places
  assumed the origins direction and none of them raised — they answered the opposite question and passed.
- **2026-08-14 — The held-out 10 is drawn, not hand-authored.** Decided by sjtroxel.
  `eval/heldout_draw.py` takes a seed only he holds and samples the pinned artifact to the gold set's
  shape distribution. Its job is detecting overfitting to the gold set, and **a curated held-out set
  inherits the same blind spots the gold set already has**; an unbiased sample does not. It also removes
  the hallucination surface entirely, which a model-authored set could not. The test written for it
  immediately found that `heldout.check_against_corpus` was origins-only — a sealed descendants or path
  case would have been reported as diverged while being correct, undebuggably, since findings never
  disclose content.
- **2026-07-24 — Concept locked.** Music-history influence and lineage graph. Data verified live: ~6,324
  Wikidata genres, ~7,936 derivation edges, inception dates reaching ~2000 BCE.
- **2026-07-27 — Neptune killed.** ~$80/mo floor with no free tier, against a ~$20 ceiling. No managed
  database at all, which also deletes the VPC and the ~$32/mo NAT gateway. Behind the `GraphStore` seam, so
  it is a swappable implementation and not a permanent commitment.
- **2026-07-27 — Claims-first pipeline.** The independent review caught a leak in the eval design: claims
  emitted *alongside* prose let prose assert an edge that never became a claim, so groundedness would read
  100% while the text hallucinated. Prose is now generated **from** the gated claim set.
- **2026-07-29 — Named.** Musical Mycelium. No domain purchase; deploys to S3 + CloudFront.
- **2026-07-29 — Product shape settled** (the last open item from the pre-build series). Question-answerer
  as the v0.x spine, guided tour as the v1.0 showcase, explorable map as the ambient surface the SPA
  provides. First screen is a search box with canonical query chips. See `SPEC.md` §1.
- **2026-07-29 — Root capped at 18 entries, enforced in CI** (15 in use). Patchwork Assurance and Heritage Odyssey both
  reached 26 root entries by accretion where every individual addition looked reasonable. The cap makes the
  accretion visible. The largest single lever was reserving `web/` so the SPA's five config files never
  land in the root.
- **2026-07-30 — AWS account live, `us-east-1`, PAID plan.** Budget armed at $20 with 25/50/100% alerts;
  Cost Explorer on. Terraform and Docker installed locally. Root MFA and Cost Anomaly Detection still owed.
  Bedrock quotas all read 0 TPM/RPM and are the sole remaining gate on phase 1.
- **2026-07-30 — Scope docs written for phases 3, 4, 5, and 7; phase 6 deferred.** Phase 6 is density and
  coverage, and it is the phase whose edges depend most directly on what P279 turns out to assert. Writing it
  after the 20-edge hand-validation costs one day and buys a doc written against evidence.
- **2026-07-31 — The P279/P737 validation ran and falsified the plan's central assumption.** P279 is category
  membership, not derivation; the lineage predicate is P737, which yields 351 genre edges of which 158 survive
  a Wikipedia prose check, forming 46 disconnected components rather than one graph. `01-DATA-SOURCES.md` is
  amended in place. Deferring phase 6's scope doc was the right call — it would otherwise have been written
  against an assumption that turned out to be wrong. Full findings in `docs/graph-semantics.md`.
- **2026-07-31 — The Wikipedia prose check moves into ingestion rather than becoming a curation pass.** It is
  deterministic, free, and needs no model call, so it is a corpus filter, a displayed coverage metric, and a
  Tier 1 eval at once. Method contributed by sjtroxel. Wikipedia cannot *confirm* a Wikidata edge (shared
  editorial ecosystem) but can *disconfirm* one, and the circularity hypothesis was tested and rejected at
  11 of 227 infobox-only.
- **2026-07-31 — Phase 6's scope doc names the 46-component question rather than answering it.** A scope doc
  is a map, not a contract; the resolution needs to know how phases 1–5 actually went, and the phase 6
  IMPLEMENTATION doc is where it gets decided.
- **2026-07-30 — Phase 3 owns the eval work for the behaviors phase 3 introduces.** `planning/07` §12 assigns
  the adversarial set, refusal accuracy, injection resistance, contested flagging, and slicing to v0.3 while
  the spine calls phase 4 "the eval suite." Both are right: phase 3 measures what it builds, phase 4 builds
  the suite — judge, validation, noise floor, thresholds, held-out set, metric unit tests, report.
- **2026-08-04 — Phase 2's scope doc amended in four places (A1–A4) before building.** It was written
  2026-07-29, two days before the P279/P737 validation, and four items rested on the falsified assumption.
  A1: its corpus numbers were P279 counts described as "derivation" — the real target is 120–160 P737 edges,
  not 7,936. A2: MusicBrainz moves to phase 6; no query in `SPEC.md` §2 needs a release, and it carries a
  licensing surface for nothing. A3: P279 ingestion moves to phase 6, so DoD #4 is restated as bounded type
  filtering. A4: DoD #6 was stricter than invariant 4 — it forbade editing the *agent package*, which would
  have forbidden registering a tool; it now names `run()` and `gate()`. Reasoning in the phase-2
  IMPLEMENTATION doc §1.
- **2026-08-04 — `GraphStore.path()` belongs to phase 2, not phase 5.** `SPEC.md` §2.2, `graph/store.py`
  and `graph/memory.py` all said phase 5, written while `path()` was a phase-1 deferral. The spine assigns
  "real multi-hop traversal" to phase 2 and its DoD #2 requires a three-hop path. Phase 5 consumes it.
- **2026-08-04 — `graph-semantics.md` §4.6's `groove metal` example was wrong, and a phase-1 rejection with
  it.** Re-measured live while building `ingest/prosecheck.py`: the article has 6–7 genuine prose mentions,
  not the documented zero. The markup defect is real (stripping retains 29% of the raw wikitext and halves
  the hit count) but groove metal is a §4.7 case, and **`groove metal <- thrash metal` is a false rejection**
  — its lead sentence reads "primarily derived from thrash metal." Corrected in place; the v0.1 artifact is
  pinned and was not rewritten. The lesson is in the code now: a tier is not evidence, the sentences are.
- **2026-08-04 — The derived-stem rule is deleted from the prose check; Wikidata aliases do the work.**
  `name_variants` stripped generic suffixes ("country music" → "country") on the assumption that aliases
  alone would miss the known under-accepts. Measured over the full population, the aliases rescue every
  real case — Wikidata publishes `country`, `dub` and `heavy metal` — and the stem rule contributed
  **three false accepts and zero true ones**. The structural worry (it also narrows the subject names
  used for self-match masking) was settled by re-crawling and diffing: exactly the three predicted edges
  left and **zero were gained**. The cause was a fixture gap — the tests that justified the rule passed
  label and title but no aliases, while the live fetch has always requested them. `graph-semantics.md`
  §4.9.
- **2026-08-04 — The hand-verification lists override the automated check in BOTH directions.** The
  prose check re-admits **six of the seven** edges the 2026-08-02 pass rejected; it cannot tell synonymy,
  contradiction, taxonomy or a wrong-way-in-time mention from a real influence claim. Building the corpus
  from the screening alone would have silently re-admitted five of them, which is exactly what
  `REJECTED_EDGES` was written to prevent. `ingest.wikidata.select_edges` is now the corpus policy:
  **`discovery` gathers evidence, `wikidata` decides the corpus.** `groove metal <- thrash metal` moved
  the other way, into `HAND_VERIFIED_EDGES`, because a human read the sentence.
- **2026-08-04 — `Edge.verification` is a required field with no default.** Decided by sjtroxel. Any
  default is wrong for one half of the corpus — `HAND` overstates the 111 machine-verified edges,
  `PROSE_AUTO` understates the 22 a human read — and silently mislabelling verification strength is the
  "grounded slides into correct" failure `CLAUDE.md` forbids. The accepted consequence is that artifact
  `v0.1.0` no longer loads and raises loudly rather than degrading quietly.
- **2026-08-04 — The gold set was re-pinned to `v0.2.0`, not re-authored.** Safe only because the
  neighbor set of all five case subjects is identical under both corpora, checked pair by pair rather
  than assumed. The file now carries a `repin_history` note stating the rule for next time: **if a
  corpus change moves any case's neighbors, re-author rather than re-pin** — re-pinning past a real
  divergence is how a benchmark silently stops measuring anything.
- **2026-08-05 — Diameter and path depth are different measurements, and the plan conflated them.**
  Phase 2 §4.4 carried "diameter 14 hops" forward as the traversal depth available to `path()`.
  Diameter is measured ignoring edge direction; a path has to follow it. Over artifact v0.2.0 the
  diameter is 10 and **the deepest chain `path()` can return is 2** — 133 ordered pairs at one hop, 13 at
  two, none at three or more. The corpus is broad and shallow, discovery is already global over P737, and
  so **phase 2 DoD #2 ("three or more hops") is not satisfiable from genre-level P737 at all.** Recorded
  as a measurement rather than quietly restated as a success. **Resolved the same day: DoD #2 is amended
  to the depth the corpus supports (scope doc A5), and `max_path_hops` is published on `/health`.** The
  artist axis is the identified route to depth and stays cuttable. Numbers in `docs/graph-semantics.md` §5.1.
- **2026-08-11 — Bedrock access restored; the twelve-day block was two gates, not one.** The
  tokens-per-day zero was AWS's and cleared silently, with no reply on case `178545883500013`. The
  `AccessDeniedException` that followed on Anthropic models was **ours**: a Marketplace subscription that
  any identity with `aws-marketplace:Subscribe` can create by invoking once, fixed self-serve in minutes.
  The lesson worth keeping is diagnostic, not procedural — the second error *looked* like a continuation
  of the first and was a different problem with a different owner. Reading the error text precisely, and
  separating "genuinely blocked" from "feels blocked," is what turned an assumed two-week wait into a
  five-minute fix. **Model choice settled at the same time:** Claude Haiku 4.5 on the `us.` geo
  cross-region profile, with **RPM (10) binding before TPM (5M)**, which is a phase 4 input.
- **2026-08-11 — The recorded Converse fixture is now a real recording.** `test_agent_loop.py`'s parser
  test previously ran against a payload shaped the way the docs describe, with an explicit instruction to
  replace it once a real call landed. It has been replaced with a verbatim capture. The documented shape
  was correct, but the live envelope carries `role`, a `metrics` block, and cache-token keys that the
  assumed one did not — so the fixture now proves the parser tolerates the real wire format, extra keys
  and all, rather than proving it can parse our own assumptions back to us.
- **2026-08-05 — Structure is recomputed at load, not read from the manifest.** `build_manifest` records
  it for every future build, but the pinned v0.2.0 manifest was **not** rewritten to add it: artifacts are
  immutable, and rewriting one under its own version is what the pin exists to prevent. The runtime
  computes connectivity from the corpus in hand, so the displayed number cannot drift from the graph it
  describes, and an artifact built before the field existed still answers.
- **2026-07-29 — Python 3.13, uv, ruff, mypy, pytest.** Lambda supports 3.13 as both a managed runtime and
  a container base image, and 3.13 is the current LTS with support through October 2029. 3.14 is available
  on Lambda but 3.13 has the wider dependency support today.

### Known doc inconsistency

`planning/05-EVOLUTION-PLAN.md` §8 says "eight decisions" are one-way doors while §2.1 lists **nine** — the
ninth (structured `Claim` emission) was added by `07-EVAL-SPEC.md` §2 and §8 was never updated. Nine is
correct. `CLAUDE.md` carries the authoritative list.

## 5. Backlog

Things that belong to the project but not to the current phase. Anything that would widen a phase goes here
instead.

- ~~Contested-claim UI treatment: how a disputed edge looks to a user.~~ **DELIVERED 2026-09-07, phase 6.5
  step 4** — a distinct SSE event before the first prose token, naming both directions and both sources and
  picking no winner. Left in place struck through rather than deleted, because a backlog that silently loses
  completed rows stops being a record of what was wanted.
- Coverage and density rendered honestly, so bias-by-construction is visible rather than disclaimed.
- ~~The signature moment: the graph animating the traversal as the agent streams its reasoning, one shared
  timeline driving both text and view (`planning/06` §5.1).~~ **Left the backlog 2026-09-08 — it is phase 7,
  steps 6 and 5.**
- Time as a real spatial axis in the layout rather than force-directed placement.
- ~~A plain-English write-up per phase, accumulating into the project writeup.~~ **Left the backlog
  2026-09-08 — it is phase 7.5, and its per-phase halves are already written as each phase was built.**
- Contested pair rendering inside the guided tour's camera walk, if the demo route crosses one. Preference,
  not a requirement — `phase-7-cinematic-surface-IMPLEMENTATION.md` §13.
