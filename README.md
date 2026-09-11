# Musical Mycelium

**Music history is a network, not a timeline.**

Genres look like separate things. Underneath they are one connected organism, and most of the
connections are not written down anywhere in one place. Musical Mycelium is a goal-directed research
agent that walks that network and cites every link it draws.

Every connection it reports is sourced. The ones it cannot source, it does not claim.

- **The app:** https://musical-mycelium.vercel.app
- **How it is evaluated, including what did not work:**
  https://musical-mycelium.vercel.app/report/index.html
- **The code:** this repository

---

## Try it

Open the app and press **Take the guided tour**. It walks from groove metal back to the blues in five
hops, with the map, the claims and the narration moving together. The tour replays a recorded answer, so
it costs nothing and works even if the model is unavailable.

Then ask it something. The suggested questions under the search box are checked against the corpus on
every build, so each one does what it says. "How is the blues connected to heavy metal?" answers in two
hand-checked hops. "Where did acid jazz come from?" fans out to four parents. "Kate Bush" asks both
ways. Who influenced her is refused, correctly: she has <!-- n:refusal_example_influenced -->7<!-- /n --> incoming influence edges and <!-- n:refusal_example_influenced_by -->0<!-- /n -->
outgoing ones, so the graph genuinely cannot answer it, and it says so instead of guessing. Who she
influenced then answers.

Every answer streams in as structured claims first and prose second. Each claim links to the source it
came from and states how strongly that source was checked.

## Status, 2026-09-11

**v1.0 is deployed.** The live site serves this repository's build: artifact
v<!-- n:artifact -->0.7.1<!-- /n -->, the contested-source disclosure, the animated corpus backdrop, the guided tour, and the
evaluation report. It sits behind a free Vercel proxy so the address survives a full
`terraform destroy` and `terraform apply`, and that round-trip has been run for real, not assumed.

Phases 0 through 7 are complete. Phase 7.5 (the release) is in progress: the report, the trend view, the
deploy, the round-trip and this README are done, and the writeup and a final definition-of-done audit
remain. Phase 8, which lets the agent narrate artist-to-genre membership as well as influence, is scoped
for v1.1 and not started. Every open item is listed in [`docs/KNOWN-GAPS.md`](docs/KNOWN-GAPS.md), newest
first.

The version spine is in [`docs/ROADMAP.md`](docs/ROADMAP.md), the contracts in
[`docs/SPEC.md`](docs/SPEC.md), and the pre-build planning, which is closed, in
[`docs/planning/`](docs/planning/): ten documents covering concept, data sources, architecture, cost,
risk, evolution, design and evaluation, plus an independent review.

## What it is

A hand-built tool-use loop on Amazon Bedrock's Converse API. Given a genre or an artist, it plans a
traversal, walks a pre-built provenance graph of musical influence using <!-- n:tools -->7<!-- /n --> registered tools, and
synthesizes a grounded, cited lineage. It can also take two points and walk the chain between them, hop
by hop, in whichever order you name them.

- **Claims first, prose second.** The agent emits structured claims. A deterministic gate, plain code
  and not a model, approves or rejects each one against the pinned corpus. The narrative is then written
  from the approved claims alone. The model cannot narrate an edge the gate did not pass, and it cannot
  supply a citation: sources are read off the corpus by the gate, never accepted from the model.
- **Grounded means provenance, not truth.** Every edge traces to a checkable source. Wikidata and DBpedia
  can both be wrong, and musical influence is genuinely contested. The system tells you where a claim
  came from and how hard it was checked. It does not tell you the claim is correct.
- **Disagreement is shown, not settled.** When an answer crosses a pair that two different sources
  describe in opposite directions, it streams a separate notice before the first word of prose, naming
  both directions and both sources and picking neither. That notice is never a claim and never enters
  the prose, because prose is written from approved claims alone.
- **Refusal is correct behavior.** An edge that is not in the corpus is refused rather than narrated, and
  refusal is scored as a pair, true refusals and false refusals together, because a system that refuses
  everything would otherwise look perfect.

## How it is evaluated

Evaluation is a first-class deliverable here, not a test suite, and the
[report](https://musical-mycelium.vercel.app/report/index.html) publishes all of it, generated from
committed result files by the same code that runs the suite. The build fails if the page falls out of
date.

- **Correctness is a lookup, not a judgment.** Because the ground truth is a graph this project owns,
  the headline metrics are deterministic: does this edge exist in the pinned artifact, does this
  citation resolve. The free, scripted part runs on every commit.
- **The live suite runs a real model** over <!-- n:live_cases -->56<!-- /n --> development cases and blocks a release on six
  correctness properties, among them 100% edge groundedness, 100% citation resolution, zero successful
  prompt injections and zero contested pairs crossed silently. Its bounds were set only after measuring
  the noise floor over five identical runs at the current corpus, on 2026-09-07. A full run costs about
  half a dollar.
- **The noise floor changed what counted as a result.** Four of 56 cases changed verdict between
  identical runs. One case failed three runs in a row and passed the next two, so stopping at three runs
  would have recorded a coin flip as a permanent defect. And one metric read an identical 97.1% in all
  five runs, which looked like stability and was really 37 cases scoring perfectly every time and one
  failing the same way every time. The report shows the per-case data under every aggregate for that reason.
- **Quality is judged, and the judge's weakness is published.** Citation support and narrative quality
  are scored by a model from a different family (Amazon Nova Pro) on a sample, tracked and never gated.
  Its agreement with a human is moderate on citation support, Cohen's kappa 0.44 to 0.48, and it also
  disagrees with itself: the same 30 items scored 14, then 12, then 11 across three runs. Both facts sit
  next to every judged number.
- **A sealed held-out set** of ten cases, drawn from the corpus by a seed only the author holds and
  stored encrypted, was run once, on 2026-08-24, and came back 10 of 10. That is one observation, not a
  rate. It was measured at artifact 0.5.0, before the corpus roughly tripled, and re-running it would
  spend the property it exists to have.

## What it does not do

- **It cannot say where most influence claims are disputed.** <!-- n:single_source -->2,202<!-- /n --> of <!-- n:influence_edges -->2,284<!-- /n --> influence edges have a
  single source. A second source speaks on <!-- n:corroborated -->82<!-- /n --> of them, and <!-- n:contested_pairs -->2<!-- /n --> pairs are contested, meaning two
  different sources assert opposite directions. Of the <!-- n:reciprocal_pairs -->6<!-- /n --> pairs that point both ways, only <!-- n:contested_pairs -->2<!-- /n --> are
  a disagreement; the other four are one source describing mutual influence, and counting them would
  overstate disagreement <!-- n:contested_overcount -->3x<!-- /n -->. Two separate fields carry this and are never merged: `verification`
  says how strongly one source was checked, `corroboration` says whether a second source agrees.
- **It cannot catch a model that confuses two real names.** Joy Orbison and Roy Orbison are one edit
  apart and both are in the corpus. A model that typed one for the other would get a fully grounded,
  correctly cited answer about the wrong person, and no metric here would notice. A near-miss name
  suggester was measured and rejected for the same reason: it trades an honest refusal for a confident
  wrong answer.
- **It does not narrate membership.** An artist is recorded as playing a genre, and the map draws that,
  but membership is never presented as one thing coming out of another. That is phase 8's work, and
  the difference between the two statements is the reason it gets a phase of its own.
- **Its coverage is skewed.** The corpus leans Western, anglophone and recent. The app states this with
  figures rather than a footnote, and concentration is not absence: the corpus reaches back to
  <!-- n:earliest_genre_year -->500<!-- /n --> CE across <!-- n:places -->65<!-- /n --> places, and <!-- n:genres_without_us_or_uk -->136<!-- /n --> of its genres name no US or UK origin at all. Whether answers hold up
  as well on older or non-Western material is untested.

## The corpus

**Artifact v<!-- n:artifact -->0.7.1<!-- /n -->: <!-- n:nodes -->1,479<!-- /n --> nodes and <!-- n:edges -->5,066<!-- /n --> edges** from two sources, Wikidata and DBpedia, across two
kinds of edge that are never mixed. **<!-- n:influence_edges -->2,284<!-- /n --> influence edges** say one thing influenced another.
**<!-- n:membership_edges -->2,782<!-- /n --> membership edges** say an artist plays a genre, and those are never narrated as
derivation. The agent reads only this versioned, immutable artifact at runtime; it never queries
Wikidata live.

Every edge records how strongly it was checked: **<!-- n:verified_hand -->22<!-- /n --> read by hand**, <!-- n:verified_prose -->111<!-- /n --> passed an automated
Wikipedia prose check, <!-- n:verified_asserts -->759<!-- /n --> passed an influence-assertion filter, <!-- n:verified_infobox -->1,335<!-- /n --> came from a DBpedia infobox,
and <!-- n:verified_exposure -->57<!-- /n --> rest on documented exposure rather than a stated influence claim, with <!-- n:verified_membership -->2,782<!-- /n --> more across the
two membership tiers. The exposure filter was measured at 20% recall on held-out data on 2026-08-06, so
that count is a floor on what the sources contain, never a count of it.

The organism is connected, in one specific way. Counting both kinds of edge, <!-- n:backdrop_nodes -->1,465<!-- /n --> of the <!-- n:nodes -->1,479<!-- /n --> nodes
sit in one component, and that component, with its <!-- n:backdrop_edges -->5,058<!-- /n --> edges, is the backdrop drifting behind the
app. Through influence edges alone the graph is far more fragmented. What actually ties genres together here is
the musicians who play across them, not an unbroken chain of genre-to-genre influence, and nothing in
the app says otherwise. [`docs/graph-semantics.md`](docs/graph-semantics.md) covers how the corpus was
bounded and why it is this size.

## Data and licenses

Wikidata (CC0) supplies the genre and influence graph. DBpedia (CC BY-SA 3.0) supplies stylistic-origin
edges, the second source that makes disagreement detectable. Wikipedia text (CC BY-SA) is used as a
**disconfirmation** check rather than a source, because it shares an editorial ecosystem with Wikidata
and can refute an edge far more credibly than it can confirm one. Attribution is displayed in the app,
not in a buried credits page. [`DATA-LICENSES.md`](DATA-LICENSES.md) has the detail.

MusicBrainz is not used. It has no influence relationship in its schema, so it cannot supply a lineage
edge; its CC0 core tables would add releases and identifiers, which no query here needs.

## Stack and cost

Python 3.13 on AWS Lambda as a container image, streaming typed server-sent events from a Function URL.
Claude Haiku 4.5 on Bedrock for the agent. React and TypeScript for the frontend, on S3 and CloudFront.
Terraform for every resource, so `terraform destroy` is a complete off-switch. GitHub Actions deploys
with OIDC and no long-lived AWS keys. No managed database, which also means no VPC and therefore no NAT
gateway. Budget alarms and log retention were in place before the first apply.

Fixed infrastructure is designed to cost approximately nothing, and Bedrock tokens are the only real
line item. A typical query measured in August used about 7,000 tokens, roughly a cent, and every query
has a hard token cap. August 2026, the last complete month, recorded $6.28 of usage, all of it covered by
credits, so the invoice read $0.00. The invoice applies the credits line by line and shows every service
at $0.00, so it does not say how that $6.28 splits between Bedrock and the rest. The claim that Bedrock
is the line item rests on measured eval spend, not on the invoice.

At least <!-- n:python_tests_floor -->1,500<!-- /n --> Python tests and at least <!-- n:web_tests_floor -->400<!-- /n --> frontend tests, plus <!-- n:costs_money_tests -->14<!-- /n --> that spend real money and are
deselected by default. `make check` also gates the built page's size, per asset class, and fails if any
figure in this README drifts from its source.

## Repo layout

```
src/musical_mycelium/
  ingest/   Wikidata + DBpedia -> a versioned artifact. Runs locally, not in Lambda.
  graph/    the GraphStore seam; the only way anything reads the graph.
  agent/    the hand-built Bedrock Converse tool loop; emits claims.
  api/      the streaming HTTP surface. Thin, owns no logic.
  eval/     deterministic scorers, the judge, the frozen datasets, the report generator.
tests/      unit, integration, and the architecture tests.
infra/      terraform/, docker/ and vercel/ -- deployment lives here, not in the repo root.
web/        the React + TypeScript SPA, so its toolchain never reaches the repo root.
docs/       planning/ (00-09, closed), phases/, archive/, ROADMAP.md, SPEC.md, KNOWN-GAPS.md
```

The repo root is capped at 18 entries and CI enforces it. Tool configuration goes in `pyproject.toml`,
deployment configuration goes in `infra/`, and nothing else earns a place at the top level.

## Working on it

```
make install    # provisions Python 3.13 via uv and installs everything
make check      # format, lint, types, tests, root cap -- what CI runs
make help       # everything else
```

## Why the name

Mycelium is the underground thread network that connects trees which look like separate organisms.
That is the claim this project makes about musical genres.
