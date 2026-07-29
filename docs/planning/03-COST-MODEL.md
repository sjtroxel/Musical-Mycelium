# Music Lineage Project — Cost Model & Budget Safety (2026-07-27)

> Written before naming/implementation because one component in the 7/24 architecture (`02-ARCHITECTURE-AND-GAPS.md` §2)
> would cost roughly **4x the entire monthly budget** by itself. Prices below were checked 2026-07-27 (US East, on-demand).
> AWS pricing moves; re-verify before provisioning anything.

## 1. The headline finding: kill Neptune

`02-ARCHITECTURE-AND-GAPS.md` §2 left the graph store as an OPEN DECISION — **AWS Neptune vs. graph-on-Postgres** —
and flagged that Neptune is "not trivially free-tier." That flag was correct but badly understated.

| Option | Real monthly floor | Verdict |
|---|---|---|
| **Neptune Serverless** | **~$80/mo** — 1 NCU minimum @ ~$0.1098/NCU-hr x 730 hrs, **plus** storage and I/O billed separately | **OUT** |
| **Aurora Serverless v2** | **~$44/mo** — 0.5 ACU minimum @ ~$0.12/ACU-hr, plus storage/IO | **OUT** |
| **RDS `db.t4g.micro`** | **$0 for 12 months** (new-account free tier), then **~$21.90/mo** | **OUT** — see §1.2 |
| **No managed database at all** | **$0** | **RECOMMENDED** — see §2 |

There is **no Neptune free tier**. The minimum viable Neptune cluster is an always-on charge that starts the hour it is
created and does not stop until it is deleted. At ~$80/mo it consumes the ~$20/mo ceiling four times over, and it is the
exact failure mode already on record: an always-on resource quietly accruing (cf. the Railway always-on bill, and the
spending slip that produced `eval/safety.py:confirm_spend`).

**Decision: the graph store is NOT a managed graph database.** Do not reopen without a specific reason.

### 1.1 What is actually lost by dropping Neptune

Less than it looks like. The 7/24 argument for Neptune was "the strongest *real graph infra* resume line." Honest read:

- Essentially **no job posting in his tracker asks for Neptune**. It is a niche managed service, not a market keyword.
- The transferable, interview-defensible line is **"designed a graph data model and wrote the traversal layer"** — and
  that line is *more* true if he implements traversal himself than if a managed engine does it behind Gremlin.
- Hand-built traversal is consistent with every other architecture decision already made here: **avoid Bedrock Agents,
  AgentCore, and Knowledge Bases because they hide the engineering.** Neptune hides the graph engineering for the same
  reason. Dropping it makes the project *more* internally consistent, not less.

### 1.2 Why RDS-on-free-tier is still the wrong answer

It looks free and isn't, in three ways:

1. **A 12-month cliff.** The free tier ends and the meter starts at ~$21.90/mo — a year from now, on a project he may
   not be actively touching. Cost cliffs on dormant side projects are how the bill surprises you.
2. **Free-tier eligibility is genuinely uncertain right now.** AWS restructured the free tier in mid-2025 (new accounts
   choose a **Free Plan**, ~6 months, or a **Paid Plan**, both with up to **$200 in credits**). Whether the classic
   12-month RDS allowance still applies to an account opened today is not something to assume. See §5.
3. **The VPC tax — this is the real trap.** RDS/Aurora/Neptune all live in a VPC. A Lambda that must reach both the
   database *and* the internet (Wikidata, MusicBrainz, Wikipedia, Bedrock) needs a **NAT Gateway at roughly $32/mo
   plus data-processing charges**. That cost is invisible in the database's own pricing page and is one of the most
   common surprise AWS bills there is.

**Choosing no managed database also deletes the VPC, which also deletes the NAT Gateway.** One decision removes three
recurring charges.

## 2. What replaces it: the data is small

The decisive fact is in `01-DATA-SOURCES.md`. The verified Wikidata pull was **6,324 genres and ~7,936 genre-derivation
edges**. Even after adding artist nodes and `influenced by` edges and Wikipedia summary text, the lineage graph is
plausibly **tens of megabytes** — not gigabytes. This is a dataset that fits comfortably in a Lambda's memory.

That reframes the whole storage question. It is a **read-only, rebuilt-on-a-schedule, public dataset**, which is
precisely the shape that does not need a database server. Options, cheapest-first:

- **Serialized graph in S3, loaded at Lambda init.** The ingestion job writes the built graph to S3; the API Lambda
  loads it once per cold container and serves traversals from memory. Fastest queries available, ~$0 storage.
- **SQLite baked into the Lambda container image.** Edge/node tables, real SQL, atomic deploys, zero running cost.
  Pairs well with the Docker-via-Lambda-container-image "containers without Kubernetes" line already in §2 of the
  architecture doc.
- **DuckDB over Parquet in S3.** Reads columnar files directly from S3; genuinely modern analytics engineering.
- **DynamoDB adjacency-list.** The one *managed* option that stays free: its 25 GB / 25 RCU / 25 WCU free tier is
  **always-free, not 12-month**. Adjacency-list modeling for graphs is a documented, well-respected DynamoDB pattern
  and is a legitimate AWS resume line.

**Embeddings need no vector database either.** At ~6k genres plus artists, a `numpy` array loaded from S3 and a
brute-force cosine similarity is *exact* (not approximate like a vector index), returns in milliseconds, and costs
nothing. pgvector was only ever in the plan because Postgres was. Revisit only if the corpus grows by orders of magnitude.

## 3. What this project actually costs

### 3.1 Fixed monthly infrastructure: approximately $0

| Component | Cost at portfolio traffic |
|---|---|
| Lambda | **$0** — always-free tier is 1M requests + 400k GB-seconds **per month, never expires** |
| API Gateway | **$0** within the 1M-calls/mo free allowance (note: REST API free tier is **12 months**, not always-free; HTTP APIs are cheaper if it ever matters) |
| S3 (graph artifacts + React build) | **pennies** at tens of MB |
| CloudFront | **$0–pennies** at portfolio traffic |
| CloudWatch | **$0–low** *if retention is set* — see §4 |
| Graph store (§2) | **$0** |
| **Total fixed** | **~$0/mo** |

The serverless choice is doing real work here: with no always-on compute and no managed database, **an idle month bills
essentially nothing.** That is the single most important budget property of this design, and it is worth protecting.

### 3.2 Variable cost: Bedrock tokens — the only meaningful spend

Bedrock charges the same per-token rates as the Anthropic API in standard commercial regions:

- **Claude Haiku 4.5** — ~$1 / $5 per million input / output tokens
- **Claude Sonnet 5** — ~$2 / $10 per million (introductory, through 2026-08-31; then ~$3 / $15)
- Note: regional/multi-region endpoints carry a **~10% premium** over global endpoints on recent Claude models.

A multi-step agentic tool loop is **input-heavy**, because each turn re-sends the accumulated conversation plus tool
results. Rough order-of-magnitude per lineage query (estimate, to be replaced with measured numbers once the loop exists):

| | Haiku 4.5 | Sonnet 5 |
|---|---|---|
| One lineage query (~5-8 tool turns, ~30k cumulative input, ~2k output) | **~$0.04** | **~$0.08** |
| 100 interactive queries | ~$4 | ~$8 |
| One full judged eval run | **~$5–15** | **~$10–25** |

The eval suite is the real budget line, not interactive use — exactly as it was on Patchwork, where the judged runs cost
**$4.57** and **$10.55**. Same discipline applies: **evals are the thing to gate, meter, and run deliberately.**

**Two levers keep this cheap, and both are already house style:**
- **Haiku for the traversal/tool-calling turns, a stronger model only for final synthesis and judging.** Phase 14
  already proved the governing principle: *grounding beats model tier* (grounded DeepSeek at $0.11 beat raw Fable-5 at
  $5.83). The retrieval and graph work here is grounded by construction, so the cheap model should carry most of it.
- **Cache the corpus-heavy prompt prefixes**, and cache built lineages in S3 so a repeated query costs $0.

### 3.3 One-time / credits

If the AWS account is new, **$100 in credits on activation plus up to $100 more** for five onboarding tasks (~$20 each).
Two of those tasks are things this project needs anyway: **deploy a Lambda function** and **test a prompt in Bedrock**.
A third is **set up a cost budget in AWS Budgets** — which is §4 item one. Realistically **$200 in credits covers all
Bedrock spend for the entire build**, making the true out-of-pocket for v1 plausibly **$0**.

## 4. Guardrails to put in place BEFORE the first `terraform apply`

Non-negotiable, and cheap to do:

1. **AWS Budgets** — alerts at $5 / $10 / $20 with email notification. (Also earns a $20 onboarding credit.)
2. **Billing alerts + Cost Anomaly Detection** turned on at account level.
3. **CloudWatch log retention set explicitly in Terraform** (7 or 14 days). The default is **never expire**, and
   forgotten logs are a slow, silent accrual.
4. **Everything in Terraform, nothing clicked in the console.** This is what makes `terraform destroy` a real, complete
   off switch — the cost equivalent of Patchwork's pause/resume scripts, and it is the strongest guarantee that an
   abandoned project stops billing.
5. **Port `confirm_spend`** from Patchwork to gate every eval run before it fans out to Bedrock.
6. **Token + cost tracking to CloudWatch from day one** (already in the architecture doc §2) — so the estimates in §3.2
   get replaced by measured numbers early.
7. **No provisioned concurrency.** It is the obvious fix for Lambda cold starts and it is an always-on charge. Cold
   starts are a known dislike, but the honest tradeoff here is: accept a slower first request, or pay monthly forever.
   Mitigate with a small container image and lazy loading instead.

## 5. Open question for him

**Does he already have an AWS account, and how old is it?** This determines:

- whether the **$200 in credits** is available (new accounts only), and
- whether 12-month free-tier allowances (API Gateway REST, RDS if it were used) apply at all.

It does **not** change the architecture recommendation — the §2 design is ~$0/mo with or without credits, which is the
entire point of choosing it. Credits just determine whether Bedrock spend during the build comes out of pocket.

## 6. Bottom line

- **Neptune is out** (~$80/mo). **Aurora is out** (~$44/mo). **RDS is out** (12-month cliff + VPC/NAT tax).
- **No managed database**: the graph is small enough to live in S3/SQLite/DuckDB/DynamoDB for **$0**.
- **Fixed infrastructure ~$0/mo.** An idle month costs essentially nothing.
- **The only real spend is Bedrock tokens**, it is usage-driven and gate-able, and **$200 in new-account credits
  plausibly covers the entire v1 build**.
- The worry was well-placed — it just points at **one component**, not at AWS as a whole. Serverless-plus-no-database is
  genuinely among the cheapest ways to build this, and it stays inside the ~$20/mo ceiling with room to spare.
