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
"Deployed on AWS Lambda and Bedrock with a deterministic groundedness gate at 100%" is fully claimable at
v0.3. This is written down now so a bad week does not relitigate it later.

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
| **3** `agent-loop` | **v0.3** | **v0.5.0** (unchanged) | Real agent loop: planning, **7** tools, corroboration | Tool registry; loop untouched |
| **4** `eval-suite` | **v0.4** | pinned, TBD | The eval suite proper | Independent scorers over a pinned artifact |
| **5** `spa-and-visualization` | **v0.5** | pinned, TBD | React + TS SPA on S3/CloudFront, graph visualization | A pure consumer of an already-stable API |
| **6** `density-and-coverage` | **v0.6** | new cut | Density: **second sources**, geography, time; coverage displayed | Ingestion + artifact schema, additive fields |
| **7** `polish-and-portfolio` | **v1.0** | pinned | Polish, writeup, portfolio surface | No architecture change |

**Phase 3 does not cut a new artifact.** The corpus does not change, and re-cutting it would silently
invalidate every prior benchmark for nothing.

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
| 3 | written; **amended 2026-08-07 (A1–A5)** | **written 2026-08-07, approved; no code yet** |
| 4 | written | at phase start |
| 5 | written | at phase start |
| 6 | written 2026-07-31, after the validation | at phase start |
| 7 | written | at phase start |

Phase 6's scope doc was deliberately last. It is density and coverage, the phase most directly exposed to what
the P279 taxonomy can actually carry, and hand-validating the edges first meant it could be written against
evidence rather than assumption. That paid off: the validation falsified the assumption the phase was going to
be built on. See `docs/graph-semantics.md`.

**v0.1 definition of done:** a public URL that streams a grounded, cited, two-sentence answer about one
genre's origins, deployed by CI, provisioned by Terraform, with a passing eval in the pipeline and a budget
alarm armed. A deeply unimpressive product and a completely correct skeleton.

### Where the build actually is — 2026-08-06

**Phase 2 is COMPLETE. All eight steps are built, tested and deployed.**

| step | what | state |
|---|---|---|
| 1 | harden the prose check into `ingest/prosecheck.py` | done 2026-08-04 |
| 2 | full P737 discovery replaces the hand-verified list | done 2026-08-04 |
| 3 | the schema carries verification strength | done 2026-08-04 |
| 4 | `path()` and the component structure | done 2026-08-05 |
| 5 | multi-hop through the agent, without touching the loop | done 2026-08-05 |
| 6 | the artist axis — filter, held-out measurement, ingest | done 2026-08-06 |
| 7 | publish every artifact version to a versioned S3 record | done 2026-08-06 |
| 8 | coverage as a recorded number | done 2026-08-06 |

**Corpus as shipped: artifact `v0.5.0`, 973 nodes, 950 edges** — 22 `HAND`, 111 `PROSE_AUTO`, 760
`ASSERTS_AUTO`, 57 `EXPOSURE_AUTO`. Live on AWS. `v0.1.0` through `v0.4.0` stay on disk and in S3 as
frozen records; `v0.1.0` and `v0.2.0` are deliberately unloadable under the current schema.

**The one thing still blocking, and it is not a build gap:** the deployed stack runs on
`llm_provider=local`, so the prose is a template and the token counts are synthetic. **Two v0.1 DoD
items (#1 and #7) stay open until Bedrock has a non-zero quota.** Support case `178545883500013`; a
reproducible two-region defect report was submitted 2026-08-06 and nothing further is owed on it. Every
other part of the stack — Lambda, ECR, S3, CloudFront, Terraform, IAM, OIDC, CloudWatch, Budgets — is
applied and working.

**AWS update, 2026-08-06 23:48 CDT.** Support confirmed the diagnosis in their own words — the block is
"at the account level at the Bedrock runtime layer, not a per-model or per-region quota setting, which is
why the values visible in Service Quotas do not reflect what is being enforced." They report the root
cause identified and an active internal review to **restore the standard new-account inference
allocation**, and state that no action is required from us. No ETA. Do not re-file, do not open a second
case, do not chase it.

### Phase 3 — planned 2026-08-07, **steps 1–6 built (2026-08-09); step 7 is the last local one**

Scope doc amended (A1–A5) and IMPLEMENTATION doc written and approved the same night. Per-step as-built
records live in `docs/phases/phase-3-agent-loop-IMPLEMENTATION.md` §11 — that doc is the detail, this is
the ledger.

The phase is sequenced around the Bedrock block rather than waiting on it: **steps 1–7 need no model at
all** and ship as **`v0.3.0-local`**; **step 8 is a single skippable Bedrock gate** carrying DoD items
10–12, with **phase 4 as its named home** if quota is still absent when the local work finishes.

| step | what | needs | status |
|---|---|---|---|
| 1 | the adversarial set — 18 cases, hand-authored **before** any loop code | LOCAL | DONE 08-07 |
| 2 | four new tools (7 total); `corpus_coverage` registered last as the invariant-4 seam test | LOCAL | DONE 08-07 |
| 3 | the plan object and the `Planned` event; **3b** the backwards premise (DoD #13) | LOCAL | DONE 08-08 |
| 4 | per-claim `verification`, `MAX_TURNS` 5 → 8, and a token budget (DoD #3) | LOCAL | DONE 08-08 |
| 5 | untrusted-text delimiting; the three injection tests (DoD #5) | LOCAL | DONE 08-09 |
| 6 | the cheap/strong routing seam, proven with two `ScriptedLLM`s (DoD #8) | LOCAL | DONE 08-09 |
| 7 | the deterministic scorers and the era/region/density/query-type slicing | LOCAL | next |
| 8 | **the Bedrock gate — smoke call, model IDs, live adversarial run, cost to CloudWatch** | BEDROCK | blocked |

**Step 4 is not "corroboration".** This table said `Corroboration` until 2026-08-09; the A1 recalibration
of 2026-08-07 replaced it with per-claim `verification`, because **`contested` is unbuildable on a corpus
with one source per edge** — arithmetic, not effort. `contested` and `checks_disagree` ship as
test-locked-unreachable names. Do not re-litigate.

**Two things found by building, recorded here because they outlive the step that found them:**

- **Delimiting untrusted text needs a return path** (step 5). Marking tool payloads without stripping the
  marks off incoming tool arguments breaks the walk it was protecting — a model hands a wrapped node id
  straight back and every id-taking tool answers `unknown node`.
- **A streamed call reported no usage, so synthesis was billed and never counted** (step 6). Survivable
  while one model does everything; uncostable the moment two roles run on differently-priced models.
  `LLM.stream` is now `Generator[str, None, Usage]` and `done` reports cost **per role, never summed**.

**`get_descendants` closes a real gap:** `Direction.INFLUENCED` has been supported by `GraphStore` since
phase 2 and no registered tool exposes it, so "what came out of the blues?" is currently unanswerable
except as a side effect of `trace_lineage`.

**The resume line — "deployed on AWS Lambda and Bedrock with a deterministic groundedness gate at 100%" —
is NOT claimable at `v0.3.0-local`.** It travels with step 8. Recorded here rather than glossed.

#### Phase 2's definition of done, item by item

| # | item | state |
|---|---|---|
| 1 | corpus ingests locally, artifact + manifest + per-edge exclusions | **met** |
| 2 | a path of three or more hops, sourced on every edge | **met** — 5 hops: `Nine Inch Nails -> The Clash -> Ramones -> The Beatles -> Bob Dylan -> Woody Guthrie` |
| 3 | the artist axis answers "Who influenced Kate Bush?" end to end | **partially — see below** |
| 4 | type filter is a bounded membership test against `Q188451` | **met** |
| 5 | phase 1's five gold cases pass against the new pin | **met** |
| 6 | `run()` and `gate()` not edited to accommodate the corpus | **met with one named exception — see below** |
| 7 | coverage is a recorded number | **met** |
| 8 | the artifact is published to S3, versioned and immutable | **met** |

**DoD #3, stated honestly.** The artist axis works: `U2` resolves and returns six gated claims, each
citing a Wikidata statement URI. But **Kate Bush specifically has zero outgoing `P737` and seven
incoming** — Wikidata records nobody as having influenced her, while seven artists cite her. So the
literal SPEC query *"Who influenced Kate Bush?"* **correctly refuses**, and that refusal is right rather
than broken. The capability is delivered; the example chosen for it in `SPEC.md` §2.2 happens to be a
node with no parents. Either the DoD item or the SPEC example should be restated — a decision, not a
fix, and it is not phase 2's to make unilaterally.

**DoD #6, stated honestly.** `run()` was not edited. **`gate()` was**, once: it gained a `CROSS_AXIS`
rejection when the artist axis landed, so a genre-to-artist claim is refused rather than narrated. That
is invariant 3 being enforced rather than the corpus being accommodated, but it *is* an edit to `gate()`
caused by a corpus change, and calling it anything else would be reading the item generously.

**Connectivity, measured rather than assumed:** 169 components over 973 nodes, largest 458, diameter 16,
and the deepest chain `path()` can return is **six hops**.

Those numbers replace the genre-only ones — 41 components, largest 31, deepest chain **two** hops — and
the change is a finding rather than a drift. Step 4 measured that the genre axis could not supply depth
and said the depth would have to come from somewhere other than P737 among genres; **the artist axis is
that somewhere.** DoD #2 was amended to match the old constraint (scope doc A5); that amendment stands
as a decision about what to promise, but the constraint it reasoned around is gone.
`tests/test_structure.py::test_the_depth_arrived_with_the_artist_axis` records both halves.

**Coverage, also measured rather than assumed** (DoD #7, step 8): over 169 genres, **28 carry no
inception date and 48 no country of origin**. The corpus spans **500 CE to the present across 29
places** — medieval and classical music at 500, opera and Baroque at 1600, samba, kuduro, bachata,
Anatolian rock, kayōkyoku — and **43 genres name no US or UK connection at all**, while 78 of the 121
with any place do. **It is dense in post-war anglophone material and thin elsewhere; concentration is
not absence, and both halves ship together on `/health`** so neither can be quoted without the other.

*(43/78, not 44/77, since 2026-08-07: `UK drill`'s P495 is `Brixton`, a London district, which an
exact-string test read as "names no UK". P495 records places, not countries. The counterweight figure is
audited as hard as the bias figure, and note the correction made the corpus look **more** anglophone, not
less — it was applied because it was right, not because of which way it moved.)*

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
| Scope docs, phases 0–5 and 7 | `docs/phases/phase-{0,1,2,3,4,5,7}-*.md` |
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
| Logo and banner | **After** the first successful Bedrock call, not before |

### Local prerequisites

All present as of 2026-07-30: `uv`, Terraform 1.15.8, Docker Engine 29.6.2 (in-distro, not Desktop), Node 22,
Make. Python is 3.12 locally; `uv` provisions the 3.13 this project targets, so there is no `.python-version`
file.

**The one remaining gate is Bedrock quotas.** Diagnosed 2026-08-01: the failure is `ThrottlingException`,
not `AccessDenied`, so **model access is granted** and this is a quota gate. The dimension at zero is
**tokens per DAY**, and it reads 0.0 across every vendor in `us-east-1` — a new-account provisioning
condition, one switch rather than sixty, which is why "try a different model" is not a workaround. Support
case `178545883500013` was filed 2026-07-30 and escalated to the Bedrock service team on 07-31. Phase 1's
DoD #1 (a real `converse` call) and #7 (measured token cost) are blocked behind it.

**Nothing else is.** The account is live, both Terraform roots are applied, and the deployed Lambda serves a
public streaming URL on `llm_provider=local` — invariant 7 paying out. Ingestion, traversal, the corpus, the
prose check, evals and docs all touch Bedrock zero times.

## 4. Decision history

Decisions made before the repo existed live in `planning/00`–`09`. Recorded here from the point the repo
exists.

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
