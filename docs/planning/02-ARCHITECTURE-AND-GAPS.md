# Music Lineage Project — Architecture & Gap-Fill (2026-07-24)

## 1. Why this project, for the job search

Fills the two most recurring gaps in his applications **in one build**:

- **AWS / cloud-native** — the single most recurring filter gap across his applications (appeared ~6×: Just Appraised, Pam, INVOKE, Kustomer, Vytalize, Voltus, PlanSource, ArcheSys...). This is the #1 reason to build it.
- **Python tenure < 1yr** — this is a **Python-primary** build. Lambda's most first-class language is Python; Bedrock's SDK (`boto3`) is Python. Closes two thin spots at once.

**Keyword strategy: earn keywords by building it *properly*, do not cram.** Building this correctly yields, as honest byproducts (all load-bearing, none padding): REST API, Infrastructure-as-Code, CI/CD, testing, observability, RAG / embeddings / agents. The organizing question is not "what keywords can I stuff in," but "what does building this properly already include."

## 2. Candidate architecture

> **STACK LOCKED 2026-07-24.** Frontend = **React + TypeScript SPA** (his strongest lane, and the framework dominantly listed across his target job postings; graph-viz engines are framework-agnostic so viz was *not* the deciding factor). Backend = **Python + FastAPI** (the most in-demand Python backend in his target postings; keeps the entire backend/AI layer Python). Hosting = React build on **S3 + CloudFront** (all-AWS, no cold start); FastAPI on **Lambda + API Gateway**. **Angular 22 deferred to its own future project** — don't stack a new frontend framework under the AWS/Bedrock/Python learning curve.

- **Ingestion (Python):** pull Wikidata SPARQL + MusicBrainz dumps → normalize → build the lineage graph.
- **Graph store — ~~OPEN DECISION~~ SUPERSEDED 2026-07-27, see `03-COST-MODEL.md` §1–2.** Original framing: **AWS Neptune** (managed graph DB — the strongest "real graph infra" resume line, but more cost/complexity and *not* trivially free-tier) **vs. graph-on-Postgres** (edge tables + `pgvector` for embeddings; cheaper, more familiar, and pgvector doubles as semantic search). **Costing killed both branches: Neptune has no free tier and floors at ~$80/mo; Aurora Serverless v2 floors at ~$44/mo; RDS free tier hits a ~$21.90/mo cliff at 12 months — and any of them puts Lambda in a VPC, which adds a ~$32/mo NAT Gateway. Recommendation: NO managed database.** The verified corpus (~6.3k genres / ~7.9k edges) is small enough to serve from S3 / SQLite-in-container / DuckDB / DynamoDB-adjacency-list at ~$0, and brute-force cosine over a `numpy` array replaces `pgvector` exactly. Awaiting his call.
- **Reasoning agent (Bedrock):** a **hand-built tool-use loop on the Bedrock Converse API**. Given a genre/artist, it *plans* a traversal, calls tools (graph queries, semantic search, Wikipedia fetch), cross-references, and *synthesizes* a grounded + cited lineage. Embeddings via Bedrock for semantic search over artists/genres.
  - **AVOID** managed **Bedrock Agents** / **AgentCore** and **Bedrock Knowledge Bases** — they *hide* the hand-built engineering that is the entire point (and the legibility that makes it his). Same reason Patchwork hand-rolls its RAG.
- **API surface:** API Gateway → Lambda (REST).
- **IaC:** Terraform (or AWS SAM/CDK) — highest-value keyword *and* the correct way to build AWS anyway.
- **CI/CD:** GitHub Actions, deploy-on-push.
- **Observability:** CloudWatch logs / metrics / traces, plus token + cost tracking.
- **Tests:** pytest.
- **LLM evals (FIRST-CLASS — a core deliverable, not an afterthought; he explicitly wants to keep developing this):** continues and deepens the Patchwork Assurance + Heritage Odyssey eval work, Python-native, run in CI as a regression gate (eval-as-gate). Natural eval surface here:
  - **Groundedness / faithfulness** — every asserted influence edge or lineage claim traces to a real source (Wikidata edge or cited Wikipedia passage).
  - **Citation accuracy** — the cited source actually supports the claim.
  - **Retrieval / traversal quality** — recall@k over a *gold set of known lineages* (e.g., the documented delta-blues → rock chain): did the agent's graph traversal + retrieval pull the right nodes?
  - **Hallucination detection** — does it invent influence edges not in the data? **This is more central here than in Patchwork**: "influence" is subjective and LLMs love to confabulate plausible-but-false connections, so this is a rich, genuinely hard eval surface.
  - **Refuse-unsourced gate** — feed a false-premise query and confirm the agent *declines* rather than fabricates (the deterministic-gate differentiator, made measurable).
  - **LLM-as-judge** — narrative quality/coherence of the synthesized lineage.
  - **Why it's load-bearing:** the grounded/cited/bias-by-construction promise (design principle §3.2) is only *credible* if evals prove it. Evals aren't decoration here; they're what makes the product's correctness claim true. They also double as Python tenure and hit keywords his target postings ask for outright (e.g., Hatch listed "LLM-as-a-judge evaluations"). Run against Bedrock models with cost/latency tracked via CloudWatch.
- **Optional honest "containers" line:** Docker via Lambda container image — an honest containers credential **without** Kubernetes.

## 3. Explicitly OUT (decided — do not reopen without his say)

- **Kubernetes** — the opposite of serverless, always-on cost hits the ~$20/mo ceiling, and it's the keyword-cram trap. If ever wanted, it's a *separate* project.
- **SQL + auth** — this is read-only public data; the app stays stateless (nothing to protect). Preserves the stateless-over-auth invariant.
- **Managed Bedrock Agents / AgentCore / Knowledge Bases** — hide the engineering.
- **Zapier / n8n** — no-code glue that undercuts the "real engineering" point.
- **The world-acting "doer" shape** — deferred to a *separate future project* (see `00-DESIGN-BRIEF` §4).

## 4. Budget / cost safety

- One ~$20/mo plan; AWS must run on **free-tier / near-$0**. Put a **hard cost gate up front** (reuse Patchwork's spend-safety discipline — there was a prior spending slip).
- Watch AWS free-tier footguns. **Neptune in particular is not free-tier-trivial** — factor that directly into the Neptune-vs-Postgres decision in §2.

## 5. What this proves to an employer

An AWS-native, Python-primary, IaC'd, observable, tested **agentic system** that reconstructs a real hidden graph from open data with grounded, cited reasoning — i.e., every gap keyword, demonstrated by a project that is genuinely his and genuinely interesting, not a keyword checklist.
