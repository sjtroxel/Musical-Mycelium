# Musical Mycelium

**Music history is a network, not a timeline.**

Genres look like separate things. Underneath they are one connected organism, and most of the
connections are not written down anywhere in one place. Musical Mycelium is a goal-directed research
agent that walks that network and cites every link it draws.

Every connection it reports is sourced. The ones it cannot source, it does not claim.

---

## Status

**Deployed, and honestly incomplete.** Last updated 2026-08-04.

The walking skeleton is live on AWS: a public Lambda Function URL streams a grounded, cited lineage as
typed server-sent events, provisioned entirely by Terraform, with budget alarms and log retention armed
before the first apply. Every claim it emits is checked against a pinned artifact by a deterministic gate
before any prose is generated.

Two things are deliberately not done, and saying so is the point of this section:

- **The agent is running its local provider, not Bedrock.** Every Bedrock token quota on this account
  reads zero — a new-account provisioning condition, not a model-access one — so the deployed loop walks
  the graph, gates the claims and cites real Wikidata statement URIs, but the prose comes from a template
  rather than a model. The provider is a deploy-time variable precisely so this was survivable.
- **The corpus is small.** v0.1 ships 21 hand-verified influence edges over 28 genres. Phase 2 is
  replacing that with the full Wikidata P737 corpus, filtered by an automated Wikipedia disconfirmation
  check. The honest expected size is 120–160 edges, not thousands — see
  [`docs/graph-semantics.md`](docs/graph-semantics.md) for why, which is the most interesting document
  in this repo.

The version spine and what lands when are in [`docs/ROADMAP.md`](docs/ROADMAP.md). The contracts are in
[`docs/SPEC.md`](docs/SPEC.md). Planning is closed and lives in [`docs/planning/`](docs/planning/) —
ten documents covering concept, data sources, architecture, cost, risk, evolution, design and evaluation,
plus an independent review.

## What it is

A hand-built tool-use loop on Amazon Bedrock's Converse API. Given a genre or an artist, it plans a
traversal across a pre-built provenance graph of musical influence, cross-references, and synthesizes a
grounded, cited lineage.

You ask it where something came from — "Where did Detroit techno come from?", "Who influenced Kate
Bush?" — and it streams back a lineage with a source on every link. Later, it will take two points and
walk the path between them: delta blues to Detroit techno, narrated hop by hop.

- **Claims first, prose second.** The agent emits structured claims that a deterministic gate approves;
  the narrative is generated *from* the approved claims. The model cannot narrate an edge the gate
  did not pass.
- **Grounded means provenance, not truth.** Every edge traces to a checkable source. Contested claims
  are flagged as contested rather than resolved.
- **Evaluation is a first-class deliverable.** Because the ground truth is a graph we own, the headline
  correctness metrics are deterministic dictionary lookups rather than judged text comparisons. They
  cost nothing and run on every commit.

Stack: Python 3.13 on AWS Lambda as a container image, Bedrock for the agent, Terraform for everything,
GitHub Actions with OIDC for deploys and no long-lived keys. S3 + CloudFront for the frontend, which
arrives at v0.5. No managed database — which also means no VPC, and therefore no NAT gateway. Fixed
infrastructure is designed to cost approximately nothing; Bedrock tokens are the only real line item.

## Data

Wikidata (CC0) for the genre and influence graph, and Wikipedia (CC BY-SA, attribution displayed) — used
as a **disconfirmation** check rather than a source, because it shares an editorial ecosystem with
Wikidata and so can refute an edge far more credibly than it can confirm one. MusicBrainz core tables
(CC0) for artists and releases arrive at v0.6; contributor-generated MusicBrainz data is CC BY-NC-SA 3.0
and is out of scope. Licensing rules and the per-source gotchas are in
[`docs/planning/01-DATA-SOURCES.md`](docs/planning/01-DATA-SOURCES.md) and
[`docs/planning/04-RISK-REGISTER.md`](docs/planning/04-RISK-REGISTER.md).

## Repo layout

```
src/musical_mycelium/
  ingest/   Wikidata + MusicBrainz -> a versioned artifact. Runs locally, not in Lambda.
  graph/    the GraphStore seam; the only way anything reads the graph.
  agent/    the hand-built Bedrock Converse tool loop; emits claims.
  api/      the streaming HTTP surface. Thin, owns no logic.
  eval/     deterministic scorers, the judge, the frozen datasets.
tests/      unit, integration, and the architecture tests.
infra/      terraform/ and docker/ — deployment lives here, not in the repo root.
web/        reserved for the SPA, so its toolchain never reaches the repo root.
docs/       planning/ (00-09, closed), phases/, archive/, ROADMAP.md, SPEC.md
```

The repo root is capped at 18 entries and CI enforces it. Tool configuration goes in `pyproject.toml`,
deployment configuration goes in `infra/`, and nothing else earns a place at the top level.

## Working on it

```
make install    # provisions Python 3.13 via uv and installs everything
make check      # format, lint, types, tests, root cap — what CI runs
make help       # everything else
```

## Why the name

Mycelium is the underground thread network that connects trees which look like separate organisms.
That is the claim this project makes about musical genres.
