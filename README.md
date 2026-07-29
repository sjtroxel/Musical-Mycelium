# Musical Mycelium

**Music history is a network, not a timeline.**

Genres look like separate things. Underneath they are one connected organism, and most of the
connections are not written down anywhere in one place. Musical Mycelium is a goal-directed research
agent that walks that network and cites every link it draws.

Every connection it reports is sourced. The ones it cannot source, it does not claim.

---

## Status

**Pre-build.** Named 2026-07-29. No code yet, no AWS account yet, nothing deployed.

What exists is the planning series in [`docs/planning/`](docs/planning/) — ten documents covering the
concept, data sources, architecture, cost model, risk register, evolution plan, design direction, and
evaluation spec, plus an independent review. Planning is closed. The next artifacts are an
IMPLEMENTATION doc and a walking skeleton.

## What it will be

A hand-built tool-use loop on Amazon Bedrock's Converse API. Given a genre or an artist, it plans a
traversal across a pre-built provenance graph of musical influence, cross-references, and synthesizes a
grounded, cited lineage.

- **Claims first, prose second.** The agent emits structured claims that a deterministic gate approves;
  the narrative is generated *from* the approved claims. The model cannot narrate an edge the gate
  did not pass.
- **Grounded means provenance, not truth.** Every edge traces to a checkable source. Contested claims
  are flagged as contested rather than resolved.
- **Evaluation is a first-class deliverable.** Because the ground truth is a graph we own, the headline
  correctness metrics are deterministic dictionary lookups rather than judged text comparisons. They
  cost nothing and run on every commit.

Planned stack: Python on AWS Lambda, Bedrock for the agent, Terraform for everything, S3 + CloudFront
for the frontend, GitHub Actions with OIDC for deploys. No managed database — the graph is small enough
to live in a versioned artifact in S3.

## Data

Wikidata (CC0) for the genre and influence graph, MusicBrainz core tables (CC0) for artists and
releases, Wikipedia (CC BY-SA, attribution displayed) for narrative depth. Licensing rules and the
per-source gotchas are in [`docs/planning/01-DATA-SOURCES.md`](docs/planning/01-DATA-SOURCES.md) and
[`docs/planning/04-RISK-REGISTER.md`](docs/planning/04-RISK-REGISTER.md).

## Repo layout

```
docs/planning/    the ten pre-build planning documents (00-09) plus the naming worksheet
docs/archive/     superseded docs move here rather than being deleted
```

## Why the name

Mycelium is the underground thread network that connects trees which look like separate organisms.
That is the claim this project makes about musical genres.
