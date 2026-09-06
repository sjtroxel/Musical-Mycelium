# Musical Mycelium

**Music history is a network, not a timeline.**

Genres look like separate things. Underneath they are one connected organism, and most of the
connections are not written down anywhere in one place. Musical Mycelium is a goal-directed research
agent that walks that network and cites every link it draws.

Every connection it reports is sourced. The ones it cannot source, it does not claim.

---

## Status

**Deployed, and honestly incomplete.** Last updated 2026-09-06. Phases 0 through **6** are complete and
tagged (`v0.3.0-local`, `v0.4.0`, `v0.5.0`, `v0.6.0`). The live URL serves the SPA at artifact **v0.7.1**
— a streaming cited answer, an explorable map of the neighbourhood around it, and a coverage panel that
states what the corpus does not hold. Phase 6 gave the corpus a **second, independent source**, which is
what makes disagreement between sources detectable at all: **82 of 2,284 influence edges carry a second
source and 2 pairs are contested.** What it did **not** do is make an answer able to say so — that is
scoped as phase 6.5, `docs/phases/phase-6.5-debt-and-disagreement.md`.
Every open item is enumerated in [`docs/KNOWN-GAPS.md`](docs/KNOWN-GAPS.md).

Live on AWS: a public Lambda Function URL streams a grounded, cited lineage as typed server-sent events,
provisioned entirely by Terraform, with budget alarms and log retention armed before the first apply.
Every claim it emits is checked against a pinned artifact by a deterministic gate before any prose is
generated. 1189 Python tests and 146 frontend tests, plus 14 that spend real money and are
deselected by default.

**The prose comes from a real model on Bedrock as of 2026-08-24** — Claude Haiku 4.5 on a cross-region
inference profile, deployed by CI with no long-lived AWS keys. A live query streams first byte in ~0.24s
against a ~6.4s total, and reports its own token usage per role — traversal and synthesis counted
separately, never summed, because two roles may run on differently-priced models and one combined number
cannot be turned into dollars by anyone downstream. Per-query cost lands in CloudWatch from real traffic.

**The corpus is artifact v0.7.1: 1,479 nodes and 5,066 edges**, from **two** sources — Wikidata and
DBpedia — across two predicates that are never mixed. **2,284 influence edges** say one thing influenced
another; **2,782 membership edges** say an artist plays a genre, and membership is never narrated as
derivation. Every edge carries how strongly it was checked: **22 read by hand**, 111 passed an automated
Wikipedia prose check, 759 passed an influence-assertion filter, 1,335 came from a DBpedia infobox, and
57 rest on documented exposure rather than a stated influence claim, with 2,782 more across the two
membership tiers. The exposure tier is measured at **20% recall**, so it is a floor on what exists in the
sources and is never quoted as a count of it.

Two things are deliberately not done, and saying so is the point of this section:

- **The corpus has two sources now, and disagreement is visible only where both of them speak.**
  *(This bullet said the corpus was one source deep and that `contested` was locked as unreachable. That
  was true, and arithmetic, until DBpedia was ingested at artifact v0.7.0.)* **2,202 of 2,284 influence
  edges are still single-source**, so a second opinion exists on **82** of them, and **2 pairs are
  contested** — two different sources asserting opposite directions for the same pair. Six pairs point
  both ways; only two of those are a disagreement, and the loose reading overcounts by 3x. Two separate
  fields carry this and must never be collapsed: `verification` says **how strongly one source was
  checked**, `corroboration` says **whether a second source agrees**. Reading a verification tier as
  corroboration is still reading the opposite of the truth.
- **Disagreement is a corpus-level statistic and is not yet something an answer can say.** The contested
  pairs are derived in `graph/`, served by the corpus summary and shown in the coverage panel. **The
  agent does not read them, no answer will tell you a lineage is disputed, and no eval case exercises
  it.** That is the honest state after phase 6 and it is scheduled work, not a claim in waiting.
- **Coverage generalisation is untested, and the held-out run is a single observation.** Real-model
  behaviour *is* now measured rather than demonstrated: 45 development cases against a live model, a
  noise floor taken over five identical runs, a judged tier 2 pass with judge-human agreement reported as
  a range beside every judged number, and a sealed held-out set opened once, on 2026-08-24, that came
  back 10 of 10 with every metric matching the development set. That is a real negative on the
  overfitting question. What it is *not* is a rate: **n=1 with no error bar** — the noise floor showed
  refusal accuracy swinging 12.5 points across five identical runs, and the held-out set has 2 refusal
  cases, so one flip moves that metric 50 points. It cannot be given an error bar without re-running the
  set, and re-running spends the property the set exists to have. Worse for the coverage claim
  specifically: **9 of its 10 subjects are undated and 9 of 10 have no stated region**, because a
  stratified random draw inherits the corpus's missingness where the gold set was curated to span. So the
  set cannot answer "does this hold up on older or non-Western material." That question is open, not
  passed. **Both that run and the noise floor were measured at artifact v0.5.0**, and the corpus is now
  v0.7.1 — roughly three times larger. Neither has been re-measured against it, so no movement in a
  v0.7.1 number can currently be called noise, and held-out generalisation is untested at this corpus
  rather than passed on it.

**Coverage is a computed number, not a disclaimer.** The corpus skews Western, anglophone and recent, and
the output says so with figures rather than a footnote. But concentration is not absence: it spans 500 CE
to the present across 29 places, and **43 of its genres name no US or UK origin at all**. See
[`docs/graph-semantics.md`](docs/graph-semantics.md) for how the corpus was bounded and why it is this
size, which is the most interesting document in this repo.

The version spine and what lands when are in [`docs/ROADMAP.md`](docs/ROADMAP.md). The contracts are in
[`docs/SPEC.md`](docs/SPEC.md). Planning is closed and lives in [`docs/planning/`](docs/planning/) —
ten documents covering concept, data sources, architecture, cost, risk, evolution, design and evaluation,
plus an independent review.

## What it is

A hand-built tool-use loop on Amazon Bedrock's Converse API. Given a genre or an artist, it plans a
traversal, walks a pre-built provenance graph of musical influence across seven registered tools, and
synthesizes a grounded, cited lineage.

You ask it where something came from — "Where did Detroit techno come from?" — and it streams back a
lineage with a source on every link. It will also take two points and walk the chain between them, hop by
hop, in whichever order you name them.

- **Claims first, prose second.** The agent emits structured claims that a deterministic gate approves;
  the narrative is generated *from* the approved claims. The model cannot narrate an edge the gate
  did not pass, and it cannot supply a citation — sources are read off the artifact by the gate, never
  accepted from the model.
- **Grounded means provenance, not truth.** Every edge traces to a checkable source. Wikidata and
  DBpedia can both be wrong, and musical influence is genuinely contested. **The second source arrived at
  artifact v0.7.0, so detecting disagreement is now possible where both sources speak — 82 edges of
  2,284.** Everywhere else the output still distinguishes only how strongly a single source was checked.
  It does not claim to have adjudicated a dispute, because it has not.
- **Refusal is correct behavior.** An unsourced edge is refused rather than narrated, and the refusal is
  reported as one. "Who influenced Kate Bush?" refuses on this corpus: she has seven incoming influence
  edges and zero outgoing ones, so the graph genuinely cannot answer it.
- **Evaluation is a first-class deliverable.** Because the ground truth is a graph we own, the headline
  correctness metrics are deterministic dictionary lookups rather than judged text comparisons. They
  cost nothing and run on every commit, where they gate **three** of five correctness properties — the
  other two need a real model and therefore money. **The paid live suite gates nothing at artifact
  v0.7.1**: its thresholds were measured over a 41-case development set and the set is now 45 cases, so a
  live run reports `NOT GATED` rather than a number measured against a different set. Re-measuring that
  baseline is deliberately deferred until the datasets stop moving. Skipped is not passed, and the report
  says so in those words.

Stack: Python 3.13 on AWS Lambda as a container image, Bedrock for the agent, Terraform for everything,
GitHub Actions with OIDC for deploys and no long-lived keys. S3 + CloudFront for the frontend, which
arrives at v0.5. No managed database — which also means no VPC, and therefore no NAT gateway. Fixed
infrastructure is designed to cost approximately nothing; Bedrock tokens are the only real line item.

## Data

Wikidata (CC0) for the genre and influence graph, and Wikipedia (CC BY-SA, attribution displayed) — used
as a **disconfirmation** check rather than a source, because it shares an editorial ecosystem with
Wikidata and so can refute an edge far more credibly than it can confirm one.

**Artists are already in, from Wikidata P737, not MusicBrainz.** MusicBrainz has no influence
relationship at all, so it cannot supply lineage edges and must not be planned for as though it fixes
coverage — its CC0 core tables would add releases and identifiers, and that is a phase 6 question.
Contributor-generated MusicBrainz data is CC BY-NC-SA 3.0 and is out of scope entirely. Licensing rules and the per-source gotchas are in
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
web/        the React + TypeScript SPA, so its toolchain never reaches the repo root.
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
