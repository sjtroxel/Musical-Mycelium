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
so both columns are labelled. Reading one as the other is the confusion this header exists to prevent.
*(Clarified 2026-08-07, phase 3 scope-doc amendment A3. Doc fix only.)*

| Phase | Product version | Artifact pin | What thickens | Which seam absorbs it |
|---|---|---|---|---|
| **0** `scaffold-and-spine` | — | — | The repo itself | Complete 2026-07-29 |
| **1** `walking-skeleton` | **v0.1** | v0.1.0 | Everything present, connected, deployed, and tiny | — |
| **2** `corpus-and-traversal` **DONE 2026-08-06** | **v0.2** | **v0.5.0** | Full corpus ingested; real multi-hop traversal | `GraphStore` impl + ingestion artifact; agent untouched |
| **3** `agent-loop` **DONE 2026-08-12** | **v0.3** | **v0.5.0** (unchanged) | Real agent loop: planning, **7** tools, corroboration | Tool registry; loop untouched |
| **4** `eval-suite` **DONE 2026-08-24** | **v0.4** | **v0.5.0** (unchanged) | The eval suite proper | Independent scorers over a pinned artifact |
| **5** `spa-and-visualization` | **v0.5** | **v0.5.0** (unchanged) | React + TS SPA on S3/CloudFront, graph visualization | A pure consumer of an already-stable API |
| **6** `density-and-coverage` | **v0.6** | new cut | Density: **second sources**, geography, time; coverage displayed | Ingestion + artifact schema, additive fields |
| **7** `polish-and-portfolio` | **v1.0** | pinned | Polish, writeup, portfolio surface | No architecture change |

**Phases 3, 4 and 5 do not cut a new artifact.** The corpus does not change, and re-cutting it would
silently invalidate every prior benchmark for nothing. Phase 5's pin read `pinned, TBD` until 2026-08-24;
it is `v0.5.0` for the same reason phase 4's is — a frontend consumes the API, and the API reads whatever
the backend has pinned. **Phase 6 is the next new cut.**

**Phase 6 gained a named dependency on 2026-08-07:** a **second source per edge**. Every edge in v0.5.0
has exactly one, always Wikidata, which is why contested-claim detection is unbuildable before then. See
`phase-3-agent-loop.md` A1 and `phase-2-corpus-and-traversal.md` A7.

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
| 5 | written; **amended 2026-08-24 (§0) at phase start** | **written and approved 2026-08-24; step 0 next** |
| 6 | written 2026-07-31, after the validation | at phase start |
| 7 | written | at phase start |

Phase 6's scope doc was deliberately last. It is density and coverage, the phase most directly exposed to what
the P279 taxonomy can actually carry, and hand-validating the edges first meant it could be written against
evidence rather than assumption. That paid off: the validation falsified the assumption the phase was going to
be built on. See `docs/graph-semantics.md`.

**v0.1 definition of done:** a public URL that streams a grounded, cited, two-sentence answer about one
genre's origins, deployed by CI, provisioned by Terraform, with a passing eval in the pipeline and a budget
alarm armed. A deeply unimpressive product and a completely correct skeleton.

### Where the build actually is — 2026-08-31

**Phases 0 through 4 are complete and phase 5 is mid-build: steps 0 through 7 of 11 are done.**
`v0.3.0-local` and `v0.4.0` are tagged; `v0.5.0` is step 10's and not cut.

**The one thing to know before reading anything else about phase 5:** the deployed CloudFront URL
serves the **step 2** SPA. Steps 4 through 7 — the map, the layout, the palette and the motion — are
built, tested and **local only**. Verified 2026-08-31 by fetching the live bundle: it contains the chip
row and the grounded footer and none of the map's caption strings. Nothing since step 2 has been
deployed, no AWS resource has been touched since step 0, and the redeploy is not blocked on anything —
it simply has not been done.

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
| Logo and banner | **After** the first successful Bedrock call, not before — **unblocked 2026-08-11**; phase 5 owns it |

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

*(Corrected 2026-08-24. This paragraph continued "What is not demonstrated is real model behaviour
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
  neighbour set of all five case subjects is identical under both corpora, checked pair by pair rather
  than assumed. The file now carries a `repin_history` note stating the rule for next time: **if a
  corpus change moves any case's neighbours, re-author rather than re-pin** — re-pinning past a real
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

- Contested-claim UI treatment: how a disputed edge looks to a user.
- Coverage and density rendered honestly, so bias-by-construction is visible rather than disclaimed.
- The signature moment: the graph animating the traversal as the agent streams its reasoning, one shared
  timeline driving both text and view (`planning/06` §5.1).
- Time as a real spatial axis in the layout rather than force-directed placement.
- A plain-English write-up per phase, accumulating into the project writeup.
