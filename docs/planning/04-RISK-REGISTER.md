# Music Lineage Project — Risk Register (2026-07-27)

> Companion to `03-COST-MODEL.md`. That doc covered money. This one covers everything else that can bite, mapped
> **before** the naming session and before any code. Facts web-checked 2026-07-27; AWS and upstream data policies move,
> so re-verify anything load-bearing at build time.
>
> Severity: **BLOCKER** = decide before signup/first commit · **HIGH** = will cost real rework if discovered late ·
> **MEDIUM** = plan for it · **LOW** = know it exists.

---

## 1. Account setup

### 1.1 BLOCKER — Do NOT sign up on the AWS "Free Plan"

**Confirmed 2026-07-27: he has no AWS account,** so the plan choice at signup is live and it is the single highest-stakes
decision in this document.

AWS's 2025 restructure makes new accounts choose **Free Plan** or **Paid Plan** at signup. Both get the always-free
tiers and both get up to **$200 in credits**. The difference is fatal for this use case:

> **On the Free Plan, the account closes automatically at six months or when credits are exhausted, whichever comes
> first.** Running resources are shut down. Unused credits are forfeited. There is a 90-day window to upgrade to a Paid
> Plan and recover data before deletion.

This project is **portfolio infrastructure that must stay live through a job search**. An account that self-destructs on
a timer would take the deployed site down — plausibly while a recruiter is looking at it, with no failure that he'd
notice until someone tells him the link is dead.

**Decision: sign up on the PAID PLAN, with a card attached.** This is counterintuitive and it is correct:

- The **always-free tiers are identical** on both plans (Lambda's 1M requests/mo etc. never expire on either).
- The **$200 in credits is available on both**.
- The Paid Plan simply doesn't kill the account on a timer.
- The actual bill, given the §3 architecture in `03-COST-MODEL.md`, is ~$0/mo anyway.

The Free Plan's protection (can't overspend) is replaced by the §7 guardrails, which are better: they alert at $5 rather
than silently terminating everything at month six.

### 1.2 HIGH — Root account hygiene, done once, on day one

Standard but genuinely important, and easy to skip when eager to build:

- **MFA on the root account immediately.** A compromised root AWS account is an unbounded financial liability — this is
  the class of mistake that generates five-figure crypto-mining bills.
- **Never use root for daily work.** Create an IAM admin user (or IAM Identity Center) and use that.
- **Never create long-lived IAM access keys** if avoidable — see §6.1.
- **Set the account's alternate contacts** (billing/security email) so cost and abuse alerts actually arrive.

### 1.3 MEDIUM — Pick one region and never drift

Pick a region on day one and put it in Terraform. `us-east-1` is the default choice: broadest Bedrock model coverage,
cheapest, and where most documentation assumes you are.

The failure mode is subtle: **the console silently remembers a different region per service**, so resources get created
in two regions, half of them become invisible, and orphaned resources bill quietly. Cross-region data transfer also
costs money. Terraform-only provisioning (§7.4) mostly prevents this.

---

## 2. Bedrock — the dependency most likely to block day one

### 2.1 HIGH — Model access is not automatic, and Anthropic models have an extra gate

Bedrock does **not** give a new account access to models by default. For Anthropic models specifically:

- Model access must be requested in the Bedrock console (**Model access → Modify model access**).
- Anthropic requires a **First Time Use (FTU) form** — use-case details submitted once per account — before any invoke
  will succeed. Access is granted immediately on submission.
- A common failure: **AWS Marketplace permissions must be enabled** on the account (Billing → Marketplace settings), or
  the access request fails with an unhelpful error.
- **Availability varies by region and by country/territory.**

**Mitigation: make "enable Bedrock + Claude access and run one successful `converse` call" the very first task of the
build, before writing any application code.** It is a console/permissions task, not an engineering task, and finding out
it's blocked on day 12 instead of day 1 is a pointless week. It also earns one of the $20 onboarding credits.

### 2.2 MEDIUM — Model IDs and inference profiles are not the Anthropic API's

Bedrock model identifiers differ from the Anthropic API's, and recent Claude models are typically invoked through
**cross-region inference profiles** (IDs prefixed `us.anthropic....`) rather than bare model IDs. Code copied from
Anthropic-API examples will fail with a confusing validation error.

Also relevant to cost: **regional and multi-region endpoints carry a ~10% premium over global endpoints** on recent
Claude models (`03-COST-MODEL.md` §3.2).

**Mitigation:** keep the model ID in configuration, not scattered through the code — the same `build_llm` provider-seam
pattern Patchwork already uses. That seam is also what makes an eventual "run the same evals against two providers"
comparison cheap.

### 2.3 MEDIUM — New-account quotas and throttling

New accounts start with conservative Bedrock tokens-per-minute and requests-per-minute quotas. A parallel eval fan-out
is exactly the workload that trips them, and the symptom is `ThrottlingException` partway through a paid run — wasted
spend and a corrupted result set.

**Mitigation:** exponential-backoff retry in the client from the start; cap eval concurrency low (2–4); checkpoint eval
results incrementally so a throttled run is resumable rather than restarted. Request a quota increase only if a real
run demands it.

### 2.4 LOW — Model deprecation

Bedrock model versions get deprecated and retired on published schedules. A pinned model ID will eventually stop
working. Worth a note in the README so a future rebuild isn't a mystery; not worth engineering around now.

---

## 3. Serverless architecture limits — the ones that force redesigns

### 3.1 HIGH — The 29-second API Gateway timeout vs. a multi-step agent loop

**This is the pitfall most likely to force a mid-build rearchitecture.** API Gateway REST APIs default to a **29-second
integration timeout**. A hand-built Bedrock Converse tool loop that plans a traversal, makes 5–8 tool calls, and
synthesizes a cited narrative **will regularly exceed 29 seconds.** The user-visible symptom is a 504 on exactly the
queries that show the agent working hardest.

Options, and the honest tradeoffs:

1. **Request a quota increase.** Since June 2024 the integration timeout *can* be raised above 29s — but **only for
   Regional and private REST APIs** (not HTTP APIs, not WebSocket), via a Service Quotas request, and **it may require
   reducing the account-level throttle quota** in exchange. Viable, but it's a support-ticket dependency on a new
   account.
2. **Lambda Function URL with response streaming.** Bypasses API Gateway; streams tokens as they generate. Best UX by
   far — the user watches the agent reason instead of staring at a spinner — and it matches the SSE-streaming work
   already shipped in Asteroid Bonanza, so it's a known lane.
3. **Async job + polling.** POST returns a job ID immediately, Lambda writes progress/result to S3 or DynamoDB, the SPA
   polls. Most robust, most moving parts.

**Recommendation: design for streaming (option 2) from the start, and treat it as a first-class product decision rather
than a workaround.** A visible reasoning trace is the single best demonstration of a hand-built agent loop, and it makes
the 29-second problem disappear instead of being negotiated with. **Decide this before writing the API layer** —
retrofitting streaming into a request/response design is real rework.

### 3.2 MEDIUM — Lambda packaging limits vs. the Python data stack

A zipped Lambda deployment package is capped at **250 MB unzipped**. `numpy` + `pandas` + a graph library + `boto3`
approaches or exceeds that quickly.

**Mitigation: use a Lambda container image** (up to 10 GB). This was already in the plan as the optional "containers
without Kubernetes" resume line — it turns out to be *necessary*, not optional, which is a nice alignment. Note the
tradeoff: **container images have slower cold starts** than zip packages, which interacts with §3.4.

### 3.3 MEDIUM — The 15-minute Lambda ceiling vs. the ingestion job

Lambda's hard maximum execution time is **15 minutes**. Ingesting Wikidata + MusicBrainz, normalizing, building the
graph, and generating embeddings will not reliably fit — especially the embedding pass.

**Mitigation:** the ingestion job is **not** a Lambda. Options: chunk it into a **Step Functions** state machine
(good keyword, honest orchestration experience), run it as a **Fargate task**, or — simplest and cheapest — **run
ingestion locally on his own machine and upload the built artifact to S3.** For a corpus that rebuilds weekly at most,
local-build-and-upload is entirely defensible, costs $0, and removes a whole class of cloud complexity.

Recommend starting with local build → S3 upload, and only moving to Step Functions if he wants the orchestration line.

### 3.4 MEDIUM — Cold starts, and the expensive reflex fix

A container-image Lambda that loads a graph into memory has a real cold start (seconds). Given the documented dislike of
cold starts, the temptation is **provisioned concurrency** — which is an **always-on charge** and reintroduces exactly
the cost shape `03-COST-MODEL.md` eliminated.

**Mitigation, cheapest first:** keep the image small; load the graph lazily and cache it in the module-level scope so it
survives across warm invocations; consider a small periodic EventBridge ping to keep one container warm (near-free);
and let streaming (§3.1) mask the latency — a response that *starts* immediately reads as fast even if total time is
longer. **Accept a slower first request rather than paying monthly forever.**

### 3.5 LOW — Payload size limits

Lambda synchronous responses cap around **6 MB**; API Gateway around 10 MB. A full lineage graph serialized to JSON
could approach this if the API ever returns "the whole graph."

**Mitigation:** paginate/scope graph responses (return a subgraph around the queried node, not everything). Good API
design regardless.

---

## 4. Upstream data sources — reliability and licensing

### 4.1 HIGH — Wikidata Query Service is materially degraded, and cannot be a runtime dependency

WDQS in 2026 is **much slower than it used to be** — community reports show queries that ran in ~9 seconds now timing
out outright. Documented limits: **60 seconds of query time per minute** per IP+User-Agent (burst 120s), **5 parallel
queries per IP**, and error-rate caps.

Two distinct consequences:

- **Ingestion:** treat WDQS as *flaky*. Checkpoint every query's results to disk/S3 immediately, make the ingestion
  resumable, and never assume a full pull completes in one run. For bulk work, **prefer the Wikidata dumps** over the
  live endpoint.
- **Runtime — this is the important one: the agent's tools must NOT query WDQS live.** A Lambda's outbound IP is shared,
  the rate limits are per-IP, and the latency is unpredictable. **All agent tool calls should hit the pre-built local
  graph**, not the internet.

That last point is a genuine architectural constraint and it's a *good* one: it makes the system fast, deterministic,
free, and independently reproducible. Bake it in explicitly rather than discovering it when a demo hangs.

### 4.2 HIGH — MusicBrainz licensing is NOT uniformly CC0

`01-DATA-SOURCES.md` records MusicBrainz as "mostly CC0/public-domain." Precisely:

- **Core data: CC0.** Fine for any use.
- **Contributor-generated data (annotations, reviews, and similar): CC BY-NC-SA 3.0** — *non-commercial*, *share-alike*.

For a public portfolio project this is almost certainly fine, but **"almost certainly" should be replaced with "checked"
before ingesting a table**. The practical rule: **stay on the CC0 core tables**, and if any NC-licensed field gets used,
document it. A project whose entire selling point is *rigorous, cited, correctly-attributed grounding* cannot be sloppy
about the license on its own sources — that's an interviewer's easy question.

Also mandatory: MusicBrainz requires **max 1 request/second per IP** and **a meaningful User-Agent string with contact
info**. Violating either can get an IP blocked. Use the **bulk dumps** rather than the API wherever possible.

### 4.3 MEDIUM — Wikipedia text is CC BY-SA, which has attribution obligations

Wikipedia/DBpedia narrative content is **CC BY-SA** — attribution required, share-alike applies. If cited Wikipedia
passages are displayed in the UI (which is the plan, for grounded explanations), **display the attribution and link back**.
Cheap to do, awkward to retrofit, and it fits the product's own thesis about citation.

### 4.4 MEDIUM — Verify the graph semantics before building on them

`01-DATA-SOURCES.md` uses Wikidata **P279** for "genre→genre derivation" edges. P279 is **`subclass of`** — a taxonomic
relation, not a historical one. "Bebop is a subclass of jazz" and "bebop historically derived from swing" are different
claims, and conflating them would put a subtle, systematic error at the foundation of the entire graph.

This may well be intentional (a taxonomy is a reasonable spine, and P737 `influenced by` carries the influence edges).
But it should be **explicitly validated and documented in the implementation doc**, not assumed. Concretely: pull 20
edges, read them by hand, and decide what each property actually means in the model.

This is also the highest-value thing to get right, because it's the difference between "a graph of music history" and
"a graph of Wikidata's category structure."

### 4.5 MEDIUM — The data is biased, and the honest move is to measure it

Wikidata's coverage of musical influence is skewed Western, anglophone, male, and recent. Non-Western and pre-modern
traditions will be sparse — which collides directly with the *full-history skeleton* design (`02` §2, his call: model
all eras, let density fill in).

**This is an opportunity, not just a risk.** The bias-by-construction stance is already the differentiator: an agent
that **flags where the data is thin, declines to assert unsourced influence, and marks contested claims** is a stronger
product *and* a stronger interview story than one that silently pretends the map is complete. **Make coverage/density a
first-class, displayed metric** rather than a caveat in a README.

---

## 5. Correctness and evals

### 5.1 HIGH — The gold set is the hard part, and it gates the whole eval suite

`02` §2 makes evals a first-class deliverable and names "recall@k over a gold set of known lineages." Building that gold
set is the genuinely difficult, genuinely unglamorous work: **"influence" is subjective**, so a gold set is a set of
*defensible editorial judgments*, not ground truth.

**Mitigation:** keep it small and unimpeachable. 15–30 lineages that are documented and uncontroversial (delta blues →
Chicago blues → British invasion → hard rock; the bebop chain; hip-hop's funk sampling lineage). **Cite a source for
every gold edge.** Write it by hand, early, before the agent exists — a gold set built *after* seeing model output is
contaminated by it.

### 5.2 MEDIUM — Eval spend is the only real bill; gate it

Covered in `03-COST-MODEL.md` §3.2 (~$5–25/run). Port `confirm_spend` before the first fan-out, not after.

### 5.3 MEDIUM — Grounding claims must survive an interviewer

The product's promise is "grounded, cited, refuses unsourced edges." If a demo produces a plausible influence claim that
isn't in the data, that's not a bug in a side project — **it's the exact failure the project exists to prevent**, and it
would be caught in a live demo. The refuse-unsourced gate needs to be **deterministic** (Patchwork's architecture: the
model proposes, a deterministic gate decides), not a prompt instruction.

---

## 6. Security and credentials

### 6.1 HIGH — No long-lived AWS keys anywhere, especially in CI

The default-but-wrong approach is generating an IAM access key and pasting it into GitHub Actions secrets. Leaked AWS
keys are scraped from public repos within minutes and are the standard route to a catastrophic bill.

**Do it correctly, and it's a better resume line anyway:**

- **Lambda gets an IAM execution role.** No keys, ever. `boto3` picks up the role automatically.
- **GitHub Actions authenticates via OIDC** — a short-lived assumed role, no stored credentials.
- Scope both roles to least privilege (this specific S3 bucket, these specific Bedrock model ARNs).

"Configured OIDC federation between GitHub Actions and AWS IAM with least-privilege roles" is a legitimately senior line
and costs nothing extra to do properly the first time.

### 6.2 MEDIUM — Public S3 buckets and the repo itself

Block public access at the account level; serve the SPA through **CloudFront with Origin Access Control**, not a public
bucket. And since this repo goes public: **no account IDs, no ARNs with account numbers, no `.tfstate`, no `.env`** —
add them to `.gitignore` on the first commit, because scrubbing git history later is miserable.

### 6.3 MEDIUM — Prompt injection through ingested content

The agent reads Wikipedia and MusicBrainz text — **user-editable sources**. Text like "ignore previous instructions"
can and does appear in scraped corpora. (This is not hypothetical for him: a prompt-injection string was already spotted
inside a job posting on 7/17.)

**Mitigation:** treat all retrieved content as untrusted data, not instructions — clear delimiting, never let retrieved
text reach a tool-invocation decision unmediated, and keep the deterministic gate between the model and any consequential
action. Worth one explicit eval case: **inject a hostile string into a fixture and assert the agent ignores it.** That
single test is a strong interview artifact.

---

## 7. Infrastructure-as-code and operations

### 7.1 HIGH — Terraform state is a bootstrapping problem and a secret

- **State must not live in the repo.** It contains resource details and can contain secrets.
- Use an **S3 backend with locking** — but that bucket must exist *before* Terraform runs, which is the classic
  chicken-and-egg. Either create it manually once (documented in the README) or keep a tiny separate bootstrap config.
- **Never edit state by hand.** `terraform import` exists for a reason.

### 7.2 MEDIUM — `terraform destroy` is the real off switch, and it must actually work

The strongest cost guarantee in `03-COST-MODEL.md` is that everything is destroyable. That only holds if **everything**
is in Terraform. One resource clicked into existence in the console is invisible to `destroy` and bills forever.

**Discipline: nothing gets created in the console except the two things that can't be** (account setup, Bedrock model
access). Everything else is code. **Test `destroy` and re-`apply` early**, while the stack is small — discovering that
teardown is broken is much worse at month three.

### 7.3 MEDIUM — CloudWatch log retention defaults to "never expire"

Restating from `03-COST-MODEL.md` §4 because it's the most commonly forgotten line item: **set `retention_in_days`
explicitly on every log group in Terraform.** The default accumulates forever at $0.50/GB ingested.

### 7.4 LOW — Terraform vs. SAM/CDK

`02` §2 left this open ("Terraform or AWS SAM/CDK"). **Recommend Terraform:** it is cloud-agnostic, far more common in
job postings, and the more transferable skill. CDK would let him write infra in Python, which is tempting for a
Python-primary build, but it's the weaker market keyword. Decide in the implementation doc; don't leave it open into
the build.

---

## 8. Project risks — the ones that actually kill side projects

These are the least technical and the most likely to matter.

### 8.1 HIGH — This stacks four unfamiliar things at once

AWS (new), Terraform (new), Bedrock (new), and Python-primary (< 1 year) — simultaneously, plus a novel graph data
model. That is a lot of new surface, and every prior estimate of "how long will this take" was made without pricing
that in.

**Mitigation: build the thinnest possible vertical slice first, end to end.** One genre → one hardcoded traversal → one
Bedrock call → one JSON response → one deployed URL. No React, no evals, no graph richness. **Prove the pipeline works
in AWS before making anything good.** The failure mode to avoid is three weeks of beautiful local ingestion code that
has never once run in Lambda.

### 8.2 HIGH — Scope creep, against a documented pattern

The design docs already contain a rich feature surface, and the deferred pile (Angular, K8s, the world-acting agent) is
healthy evidence of good scoping discipline so far. The risk is that *this* project quietly absorbs them anyway.

**Mitigation: the implementation doc gets an explicit v1 scope and an explicit "not in v1" list**, and the naming session
produces a one-sentence definition of done. `feedback-implementation-doc-first-before-code` already requires the doc;
this is what it's for.

### 8.3 MEDIUM — It competes with the job search for time

He is at 45 applications with a self-set re-evaluation point at n≈65. This project is real portfolio work that closes
the single most recurring gap in his applications (AWS, ~7 appearances) — so it's not a distraction. But it is also not
a substitute for applying, and a multi-week build can quietly become one.

**Mitigation:** treat it the way Patchwork was treated — parallel to activation, not instead of it. Worth an explicit
weekly cadence decision at the naming session rather than a vague intention.

### 8.4 MEDIUM — Cold articulation

A known gap: he can build a system he can't yet walk through cold. A new project with unfamiliar infrastructure widens
that gap unless something closes it deliberately.

**Mitigation, and it's free:** write the plain-English explanation **as he builds**, phase by phase, not at the end.
Explaining the tool loop, the gate, and the graph model in his own words *is* the articulation rep, and it doubles as
the README and the LinkedIn post. This has already worked before.

### 8.5 LOW — Deployment aesthetics

`03-COST-MODEL.md` chose S3+CloudFront specifically to avoid a cold-start front end. Keep it that way: the *frontend*
must load instantly even if the *agent* takes 20 seconds to think. Those are separate problems and only the second one
is allowed to be slow.

---

## 9. Ordered pre-build checklist

Everything above, sequenced. Items 1–4 happen before any application code.

1. **Sign up on the PAID plan** (§1.1). MFA on root, IAM admin user, alternate contacts (§1.2). Pick the region (§1.3).
2. **Set AWS Budgets at $5/$10/$20 + Cost Anomaly Detection** (`03-COST-MODEL.md` §4) — also earns a $20 credit.
3. **Enable Bedrock model access + submit the Anthropic FTU form + confirm Marketplace permissions**, then make one
   successful `converse` call from the CLI (§2.1). Earns another $20 credit. **If this is blocked, everything else waits.**
4. **Decide the three open architectural questions in the implementation doc:** graph store (`03` §2 — recommend
   no managed DB), streaming vs. async vs. timeout-increase (§3.1 — recommend streaming), Terraform vs. CDK
   (§7.4 — recommend Terraform).
5. **Validate the Wikidata property semantics by hand** (§4.4) and confirm MusicBrainz table licensing (§4.2).
6. **Hand-write the gold lineage set** (§5.1), before the agent exists.
7. **Thin vertical slice deployed end-to-end** (§8.1), with OIDC-based CI (§6.1) and `destroy`/`apply` tested (§7.2).
8. *Then* build the real thing.

---

## 10. Bottom line

Nothing here says don't build it. The two findings that genuinely change plans are both cheap to act on **now** and
expensive to discover **later**:

- **Sign up on the Paid Plan**, because the Free Plan deletes the account — and the deployed portfolio project — at six
  months.
- **Design for streaming from the start**, because a multi-step agent loop does not fit inside API Gateway's
  29-second default.

The rest is ordinary diligence, and most of it converts directly into resume lines that are true: OIDC federation,
least-privilege IAM, IaC with a tested teardown, retry/backoff against quota limits, license-correct data handling, and
a prompt-injection test case.
