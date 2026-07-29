# Music Lineage Project — Evolution Plan: Building a Thin v1 That Doesn't Get Thrown Away (2026-07-27)

> Answers the question raised after `04-RISK-REGISTER.md` §8.1: *how do we build a thin slice first without painting
> ourselves into a corner that forces a rewrite when we expand?*
>
> Short version: **build thin in DEPTH, correct in SHAPE.** Get a small number of structural decisions right up front;
> deliberately fake or shrink everything else. The technique has a name and a body of practice behind it.

---

## 1. The distinction that decides everything: prototype vs. walking skeleton

There are two different things people mean by "build a thin version first," and only one of them survives contact with
expansion.

**A prototype / spike** is built to answer a question and then deleted. It cuts corners *everywhere*, including
structural ones. It is genuinely useful — but it is throwaway by design, and pretending otherwise is how projects end
up rewritten.

**A walking skeleton** (Alistair Cockburn's term, and the standard practice for exactly this problem) is a tiny
implementation that performs **a small end-to-end slice of real function using the real architecture**. Every
architectural component is present, connected, and deployed — each one just does the least interesting possible version
of its job. You then grow it by thickening components in place. Nothing gets thrown away, because nothing was
structurally wrong; it was only ever *small*.

**This project wants a walking skeleton.** The v0.1 in `04-RISK-REGISTER.md` §8.1 — one genre, hardcoded traversal, one
Bedrock call, one deployed URL — is a walking skeleton *if and only if* the pieces below are real from the start.

**The key insight, and it's already his own:** the 7/24 design call in `02-ARCHITECTURE-AND-GAPS.md` was *"model the
full-history skeleton as ONE connected structure spanning all eras, and let DENSITY fill in over time — scope the
density, never the structure."* That is precisely the walking-skeleton principle, correctly applied to the data axis.
**This document does nothing more than apply the same rule to the code axis.** He already had the instinct; it just
needs to be stated as an engineering discipline instead of a data-modeling one.

---

## 2. One-way doors vs. two-way doors

The practical tool for deciding what to get right now. Some decisions are cheap to reverse later (walk back through the
door). Some are expensive (the door locks behind you). **Spend the up-front thinking budget entirely on the one-way
doors and be aggressively lazy about everything else.**

### 2.1 One-way doors — get these right in v0.1

| Decision | Why it locks | What "right" means in v0.1 |
|---|---|---|
| **Streaming vs. request/response API contract** | Changing it later rewrites both the API layer and every frontend call site | Ship the response-streaming path (`04` §3.1) even though v0.1's answer is 3 words |
| **Provenance on every edge** | Retrofitting source-tracking means re-ingesting everything and invalidating every eval | Every node/edge carries `source`, `source_id`, `retrieved_at` **from the first row** |
| **Graph semantics** (what P279 vs. P737 actually mean here) | The foundation; changing it invalidates ingestion, evals, and the gold set at once | Validated by hand and written down (`04` §4.4) before ingestion is coded |
| **Agent-to-data tool contract** | The seam the entire agent loop is built on; changing it rewrites every tool and every eval | Defined as an explicit interface (§3.1), even with 2 tools |
| **Everything in Terraform** | Retrofitting IaC over console-created resources is manual, error-prone, and makes `destroy` unreliable | Nothing clicked in the console except account setup + Bedrock access |
| **Package boundaries** | Untangling an agent that grew inside an HTTP handler is a rewrite | `ingest / graph / agent / api / eval` as separate modules from commit one |
| **LLM provider seam** | Cheap now, invasive later | A `build_llm`-style factory (Patchwork already has the pattern) |
| **Lambda container image** | Switching packaging changes the whole build/deploy pipeline | Container image from the start (`04` §3.2 makes it necessary anyway) |
| **Structured `Claim` emission alongside prose** *(added 7/27 by `07-EVAL-SPEC.md` §2)* | Without machine-readable claims, every correctness metric degrades to fuzzy text matching — the exact failure that produced Patchwork's difflib coverage bug | The agent emits `Claim(subject, predicate, object, source_ids, span)` with every narrative, from v0.1 |

**Nine** decisions. That's the whole list. It is much shorter than the risk register, and that's the point.

### 2.2 Two-way doors — defer freely, change later at low cost

| Decision | Why it's cheap to change |
|---|---|
| **How much data is ingested** | Density, not structure — his own principle |
| **Which storage backend** (S3 / SQLite / DuckDB / DynamoDB) | Hidden behind the `GraphStore` interface (§3.2) — swap the implementation, nothing else moves |
| **Which model** (Haiku vs. Sonnet, per-call) | Config value behind the provider seam |
| **How many tools the agent has** | Additive by construction if §3.1 holds |
| **How many eval metrics** | Additive; each is an independent scorer |
| **Frontend richness, graph-viz library** | The API contract is the boundary; the SPA can be rebuilt entirely without touching the backend |
| **Caching, pagination, rate limiting** | Layered in later at the edges |
| **Step Functions vs. local ingestion** | Ingestion output is a file in S3; how it gets produced is invisible downstream |

**Read that table again when it feels like there's too much to decide.** Most of the surface area of this project is in
the right-hand column.

---

## 3. The seams — the actual mechanism that makes growth additive

Three interfaces do nearly all the work. Define them in v0.1 with trivial implementations behind them.

### 3.1 The tool contract (agent ↔ everything)

The agent's tools are the seam between "the model reasons" and "the system knows things." Define the *shape* once:

```python
# agent/tools.py
class Tool(Protocol):
    name: str
    description: str
    input_schema: dict          # JSON schema, handed to Bedrock Converse
    def run(self, **kwargs) -> ToolResult: ...

@dataclass
class ToolResult:
    data: Any
    sources: list[Source]       # provenance travels WITH the result, never bolted on after
```

v0.1 registers two tools (`get_genre`, `get_influences`). v1.0 registers a dozen. **Adding a tool is a new file and a
registry entry — never a change to the loop.** If adding a tool ever requires editing the agent loop, the seam has
broken and that's the signal to stop and fix it.

Note `sources` on `ToolResult`: **provenance is structural, not a feature.** The grounded-and-cited promise is the
product, and the only way it stays true under expansion is if it's impossible for data to reach the model without its
source attached.

### 3.2 The graph store interface (the storage decision, deferred)

This is the seam that specifically protects against the scenario worried about — outgrowing the v1 storage choice.

```python
# graph/store.py
class GraphStore(Protocol):
    def get_node(self, node_id: str) -> Node | None: ...
    def neighbors(self, node_id: str, edge_types: list[str], direction: str) -> list[Edge]: ...
    def search(self, query: str, k: int) -> list[Node]: ...      # semantic or lexical
    def path(self, src: str, dst: str, max_hops: int) -> list[Edge]: ...
```

v0.1 implements this over **an in-memory dict loaded from a JSON file in S3**. That is a genuinely fine implementation
for ~6.3k genres and it costs $0.

If the corpus later grows 100x, the migration is: write `DuckDBGraphStore` or `DynamoDBGraphStore`, satisfy the same
four methods, flip one line of wiring. **The agent doesn't know. The API doesn't know. The evals don't know.** That is
the whole point, and it's why `03-COST-MODEL.md`'s "no managed database" recommendation is safe rather than a corner —
it's not a permanent commitment, it's a swappable implementation of a stable interface.

### 3.3 The ingestion output contract (the artifact)

Ingestion's job is to produce **one versioned artifact** in S3 with a stable schema — nodes, edges, provenance,
embeddings, and a `manifest.json` recording source versions, counts, and build date.

Everything downstream reads the artifact, never the internet (`04` §4.1 makes this mandatory anyway, since WDQS can't be
a runtime dependency). This means:

- Ingestion can be rewritten freely — locally, Step Functions, Fargate — with zero downstream impact.
- The artifact is **versioned**, so a bad rebuild is a one-line rollback rather than an outage.
- Evals run against a **pinned artifact version**, which is what makes eval results comparable over time. Without this,
  every corpus change silently invalidates every prior benchmark — a mistake that is very annoying to discover late.

---

## 4. v0.1 — what's real and what's deliberately fake

**Real (structural, per §2.1):** Terraform-provisioned; container-image Lambda; streaming response path; the three
interfaces in §3; provenance on every edge; the package layout; CI with OIDC; budget alarms; one eval that runs in CI.

**Deliberately fake or tiny (fill in later):** the corpus is a few hundred genres, not 6,324. Two tools, not twelve. The
"traversal" is one hardcoded hop. No React — the API returns JSON and `curl` is the client. One eval metric
(groundedness), five gold cases. No caching, no pagination, no auth, no viz.

**Definition of done for v0.1:** a public URL that streams a grounded, cited, two-sentence answer about one genre's
origins, deployed by CI, provisioned by Terraform, with a passing eval in the pipeline and a budget alarm armed.

That is a *deeply* unimpressive product and a *completely* correct skeleton. Everything after it is thickening.

---

## 5. The growth path — each step additive, none structural

| Version | What thickens | Which seam absorbs it |
|---|---|---|
| **v0.2** | Full corpus ingested; real multi-hop traversal | `GraphStore` impl + ingestion artifact — agent untouched |
| **v0.3** | Real agent loop: planning, 5–8 tools, cross-referencing | Tool registry — loop untouched |
| **v0.4** | Eval suite proper: groundedness, citation accuracy, recall@k, hallucination, refuse-unsourced gate, LLM-judge | Independent scorers over a pinned artifact |
| **v0.5** | React + TS SPA on S3/CloudFront, graph visualization | Pure consumer of an already-stable API |
| **v0.6** | Density and coverage: artists, geography, time; coverage metrics displayed (`04` §4.5) | Ingestion + artifact schema (additive fields) |
| **v1.0** | Polish, README, writeup, portfolio surface | No architecture change |

Read down the right-hand column: **no row requires rewriting a previous row.** That is what "planned for expansion"
actually means in practice — not predicting the final feature set, but ensuring every future addition lands in a slot
that already exists.

---

## 6. What is honestly still at risk of rework

Being straight about this, because "we planned so nothing will surprise us" is not a claim that survives any real build:

- **The graph model itself.** If hand-validating the Wikidata properties (`04` §4.4) reveals the taxonomy doesn't
  support historical lineage the way the concept assumes, the node/edge model changes — and that's genuinely
  foundational. **This is exactly why §9 of the risk register puts that validation before ingestion is written.** It's
  the one item worth being slow and careful about.
- **Streaming ergonomics.** Response streaming from Lambda has rough edges. The contract is right; the plumbing may take
  a fight.
- **Eval metric definitions.** These always get revised once real output exists — cheap, since scorers are independent.
- **Prompt and tool-description design.** Continuous churn, by nature. Not architecture.

**The goal was never zero rework. It's bounded rework — nothing that forces starting over.** A skeleton whose bones are
right can have any amount of muscle rearranged.

---

## 7. Why thin-first is the *risk* strategy, not just the fast one

The framing worth carrying into the build: **the cost of discovering a surprise scales with the size of the system it
surprises you in.**

The unknown unknowns are real — there will be things not in `04-RISK-REGISTER.md`. The defense isn't planning harder
(there are diminishing returns, and this project is already past the point where more planning beats more building).
The defense is **making the system deployable and observable while it is small**, so that when the surprise arrives it
arrives in a 400-line codebase instead of a 4,000-line one.

Concretely, that means the first week's goal is *not* good code. It's **"something is deployed and I can see it run in
AWS."** Every one of the four unfamiliar technologies (`04` §8.1) reveals its actual behavior on first contact, not in
documentation — and first contact should happen against a system small enough that being wrong is a Tuesday, not a
crisis.

---

## 8. Bottom line

- Build a **walking skeleton**, not a prototype: thin in depth, correct in shape.
- **Eight decisions** are one-way doors (§2.1). Everything else can be changed later cheaply — including the storage
  choice, which is the one that felt most like a corner and is actually just an interface implementation.
- **Three interfaces** (§3) do the structural work: the tool contract, the graph store, the ingestion artifact.
- Every growth step (§5) lands in a slot that already exists.
- Some rework is coming anyway, and that's normal. Bounded, not catastrophic, is the target.
- His own 7/24 principle — **scope the density, never the structure** — was the right idea all along. This is that idea,
  applied to code.
