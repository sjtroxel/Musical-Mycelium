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

| Phase | Version | What thickens | Which seam absorbs it |
|---|---|---|---|
| **0** `scaffold-and-spine` | — | The repo itself | Complete 2026-07-29 |
| **1** `walking-skeleton` | **v0.1** | Everything present, connected, deployed, and tiny | — |
| **2** `corpus-and-traversal` | **v0.2** | Full corpus ingested; real multi-hop traversal | `GraphStore` impl + ingestion artifact; agent untouched |
| **3** `agent-loop` | **v0.3** | Real agent loop: planning, 5–8 tools, cross-referencing | Tool registry; loop untouched |
| **4** `eval-suite` | **v0.4** | The eval suite proper | Independent scorers over a pinned artifact |
| **5** `spa-and-visualization` | **v0.5** | React + TS SPA on S3/CloudFront, graph visualization | A pure consumer of an already-stable API |
| **6** `density-and-coverage` | **v0.6** | Density: artists, geography, time; coverage displayed | Ingestion + artifact schema, additive fields |
| **7** `polish-and-portfolio` | **v1.0** | Polish, writeup, portfolio surface | No architecture change |

**AWS signup is phase 1's step zero**, not a phase: account on the paid plan, Bedrock model access, and budget
alarms armed. It is a gate, and one successful `converse` call is task one of the build.

### Phase doc status

Two layers per phase, written at different times — see `CLAUDE.md` for the rule and `.claude/skills/start-a-phase/`
for the workflow. Scope docs are written up front; IMPLEMENTATION docs are written immediately before each build.

| Phase | Scope doc | IMPLEMENTATION doc |
|---|---|---|
| 0 | written (retroactively) | written (as-built) |
| 1 | written | **next artifact** |
| 2 | written | at phase start |
| 3–7 | **pending** — next session | at phase start |

**v0.1 definition of done:** a public URL that streams a grounded, cited, two-sentence answer about one
genre's origins, deployed by CI, provisioned by Terraform, with a passing eval in the pipeline and a budget
alarm armed. A deeply unimpressive product and a completely correct skeleton.

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
| Scope docs, phases 0–2 | `docs/phases/phase-{0,1,2}-*.md` |

### Arrives with its subject, not before

| Item | Trigger |
|---|---|
| Scope docs, phases 3–7 | Next session, in one pass, before phase 1 is built |
| `infra/terraform/` | AWS account exists |
| `infra/docker/Dockerfile` | There is code to package |
| Deploy workflow with OIDC | AWS account exists; no long-lived keys, ever |
| `make dev` body | The v0.1 API exists |
| `web/` SPA scaffold | v0.5. Initialized **inside** `web/`, never at the root |
| Frozen eval datasets | Hand-authored **before** the agent is coded, or they are contaminated |
| Graph-viz engine choice | v0.5, via throwaway previews |
| Logo and banner | **After** the first successful Bedrock call, not before |

### Prerequisites not yet installed on this machine

`uv`, Terraform, Docker. Node 22 and Make are present. Python is 3.12 locally; `uv` provisions the 3.13
this project targets, so there is no `.python-version` file.

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
