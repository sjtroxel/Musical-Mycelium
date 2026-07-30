# CLAUDE.md — Musical Mycelium

Operating manual for AI coding agents in this repo. Read this first; it is the short version of the
invariants. Depth lives in `docs/ROADMAP.md`. Contracts live in `docs/SPEC.md`. The pre-build analysis
lives in `docs/planning/00`–`09` and is closed — do not add numbered planning docs.

## What this is

A goal-directed research agent that maps the history of music. Given a genre or an artist, it plans a
traversal across a pre-built provenance graph of musical influence, cross-references it, and synthesizes
a grounded, cited lineage. Built on AWS Lambda + Bedrock, Python-primary, Terraform for everything.

The thesis: music history is a network, not a timeline. Genres look like separate things; underneath they
are one connected organism, and most of the connections are not written down in one place.

## Where to look

- `docs/ROADMAP.md` — the version spine (v0.1 → v1.0), the scaffolding ledger, decision history.
- `docs/SPEC.md` — canonical contracts: the product shape, the data model, the API surface. Defined
  **once** here and referenced, never duplicated.
- `docs/planning/00`–`09` — the pre-build series. `09` §7 is the sequence; `05` §2.1 is the one-way-door
  table; `07` is the eval spec; `04` is the risk register. Read these for *why*, not *what now*.
- `docs/phases/phase-N-*-IMPLEMENTATION.md` — the as-built plan for each phase, written **when the phase
  begins**, not up front, so it reflects how earlier phases actually turned out.
- `docs/archive/` — superseded docs move here rather than being deleted.

This repo shares one Claude memory store with `job-search-headquarters` and `patchwork-assurance` via a
symlink; the canonical store is `job-search-headquarters`. Recall from those sessions is available here and
anything saved here writes back to the same place. Read `MEMORY.md` first.

## Architecture invariants (do not violate)

These are the nine one-way doors from `05` §2.1. Reversing any of them later is a rewrite, not an edit.

1. **Claims first, prose second.** The agent emits structured `Claim` objects; a deterministic gate
   approves them; the narrative is generated *from* the approved claim set. The model must not be able to
   narrate an edge the gate did not pass. See `.claude/rules/grounding-and-claims.md`.
2. **Provenance on every edge, from the first row.** Every node and edge carries `source`, `source_id`,
   `retrieved_at`. Retrofitting source-tracking means re-ingesting everything and invalidating every eval.
3. **Validated graph semantics.** Wikidata P279 is `subclass of` — taxonomic, not historical. Hand-check
   before ingesting. See `.claude/rules/graph-semantics.md`.
4. **An explicit agent-to-data tool contract.** Adding a tool must never require editing the loop. If it
   does, the seam is broken.
5. **Everything in Terraform.** Nothing clicked in the console except account setup and Bedrock access.
   `terraform destroy` must be a real, complete off-switch.
6. **Package boundaries: `ingest / graph / agent / api / eval`.** Separate modules from commit one. An
   agent that grows inside an HTTP handler is a rewrite.
7. **An LLM provider seam.** A `build_llm`-style factory, so the model and the provider are config.
8. **Lambda container image.** The 250MB unzipped limit makes this necessary, not optional.
9. **Response streaming, not request/response.** API Gateway REST times out at 29s and a multi-step tool
   loop will exceed it. Streaming is a product decision (`04` §3.1), not a workaround.

Everything *not* on that list is a two-way door (`05` §2.2) — how much data, which storage backend, which
model, how many tools, how many metrics, the whole frontend. Be aggressively lazy about those.

## Stack and layout

Python 3.13, managed with `uv` (uv installs the interpreter; there is no `.python-version`). `ruff` for
lint and format, `mypy` for types, `pytest` for tests — all configured in `pyproject.toml` and nowhere
else.

```
src/musical_mycelium/
  ingest/   Wikidata + MusicBrainz -> a versioned artifact. Runs locally, not in Lambda.
  graph/    the GraphStore seam; loads the artifact, answers node/neighbor/path queries.
  agent/    the hand-built Bedrock Converse tool loop; emits Claims.
  api/      the streaming HTTP surface. Thin. Owns no logic.
  eval/     the eval harness: deterministic scorers, the judge, the frozen datasets.
tests/      unit + integration, mirroring the package layout.
infra/      terraform/ and docker/ — deployment lives here, not in root.
web/        reserved for the SPA. Its package.json never reaches the repo root.
docs/       planning/, phases/, archive/.
```

**Root discipline:** the repo root is capped at 18 entries and CI enforces it (15 in use). Before adding a root file,
check whether it can live in `infra/`, `docs/`, `web/`, or a `pyproject.toml` section. Tool configs go in
`pyproject.toml`. Deployment configs go in `infra/`. This was a deliberate decision on 2026-07-29 after
Patchwork and Heritage Odyssey both reached 26 root entries.

## Conventions

- **The IMPLEMENTATION doc comes before the code.** Starting a phase means writing and getting approval on
  `docs/phases/phase-N-*-IMPLEMENTATION.md` first. "Let's get a move on" does not mean skip the plan. Use
  the `start-a-phase` skill.
- **One command:** `make check` runs format, lint, types, and tests. `make help` lists everything.
- **Never run `git commit` or `git push`.** Provide the command; he runs it. Enforced in
  `.claude/settings.json`. One-line commit messages, no AI attribution or `Co-Authored-By` trailers.
- **No new emoji** in code, docs, or commit messages.
- **Verify against the repo, not memory.** Before asserting that something is or is not built, grep for it.
  A grep miss is not proof of absence — read the target or try two or three spellings.
- **The ingestion artifact is the only data source at runtime.** The agent never queries Wikidata live.
- **Evals run against a pinned artifact version.** Otherwise every corpus change silently invalidates
  every previous benchmark.

## Cost and safety

Fixed infrastructure is designed to cost approximately $0/month: Lambda's always-free tier, S3 and
CloudFront pennies, no managed database, no VPC, no NAT gateway, no provisioned concurrency. **The only
meaningful spend is Bedrock tokens**, and the eval suite is the real line item (~$5–25/run, based on
Patchwork's actual $4.57 and $10.55 judged runs).

Hard rules in `.claude/rules/aws-and-cost.md`. The short version: no always-on resources, budget alarms
before the first `terraform apply`, explicit CloudWatch log retention (the default is never-expire), and
any operation that spends money at scale goes behind an explicit confirmation.

## Grounded means provenance, not truth

This is the project's central honest claim and it must not be overstated. "Grounded" means every edge
traces to a checkable source. It does **not** mean the edge is true. Wikidata can be wrong; musical
influence is genuinely contested. Contested claims are flagged as contested, not resolved. When writing
copy, docs, or interview material about this project, never let "grounded" slide into "correct."
