# Phase 1 — Walking Skeleton (v0.1)

> **Scope doc.** Written 2026-07-29, before building. The IMPLEMENTATION doc for this phase is the next
> artifact and is written immediately before the build starts.

## What this phase is for

To get *something* deployed and running in AWS, so that unknown-unknowns surface in a 400-line codebase
instead of a 4,000-line one. The first week's goal is not good code — it is "something is deployed and I can
watch it run."

This is a **walking skeleton**, not a prototype. Every architectural component is present, connected, and
deployed; each one does the least interesting possible version of its job. Nothing here gets thrown away,
because nothing is structurally wrong — it is only small.

Read the two-way-door table in `planning/05` §2.2 when this feels like too much to decide. Most of the
project's surface area is in that column and is deliberately deferred.

## Step zero — the AWS gate

Not a build step and not its own phase, but nothing else in this phase can start until it passes.

1. **Sign up on the PAID plan.** Not the Free Plan, which auto-closes the account at 6 months or credit
   exhaustion. This is portfolio infrastructure that must stay live through a job search.
2. **Never join this account to an AWS Organization** — it forfeits activation credits immediately. Credits
   expire 12 months from account creation.
3. **Get Bedrock model access:** the Anthropic First-Time-Use form plus Marketplace permissions. This is not
   automatic.
4. **Arm the budget alarms before anything else** — Budgets at $5/$10/$20 plus Cost Anomaly Detection.
5. **One successful `converse` call is task one.** If it is blocked, everything waits. Do not build around it.

## Delivers

A public URL that streams a grounded, cited, two-sentence answer about **one genre's origins**, deployed by
CI, provisioned by Terraform, with one eval passing in the pipeline and a budget alarm armed.

"A deeply unimpressive product and a completely correct skeleton."

## How each one-way door is satisfied at v0.1

| Invariant | v0.1 form |
|---|---|
| Claims first, prose second | Real. The gate is deterministic code; prose sees only approved claims |
| Provenance on every edge | Real. `source`, `source_id`, `retrieved_at` on every row from the first row |
| Validated graph semantics | **Done 2026-07-31** — 47 edges read, findings in `docs/graph-semantics.md`. v0.1 ingests P737 genre-to-genre only |
| Agent-to-data tool contract | Real interface, 2 tools behind it |
| Everything in Terraform | Real. Nothing clicked in the console except account setup and Bedrock access |
| Package boundaries | Already done in phase 0 |
| LLM provider seam | Real `build_llm`-style factory, one implementation |
| Lambda container image | Real. Required anyway by the 250MB unzipped limit |
| Response streaming | Real. Lambda Function URL with response streaming, even though the answer is two sentences. **VERIFIED 2026-07-31** — Python needs the Lambda Web Adapter; TTFB 0.214s vs 10.22s total. See `docs/streaming-verification.md` |

## Deliberately fake or thin

- ~15 hand-verified edges, not the full corpus. *(Amended 2026-08-01 from "a few hundred genres" — the
  P279/P737 validation showed the sourced-lineage corpus is ~158 edges total; see the IMPLEMENTATION doc §2.)*
- **Two tools**, and one hardcoded traversal hop. No planning.
- **No React.** `curl` is the v0.1 client.
- **One eval metric, five gold cases.** Not the suite.
- Genre axis only, on P737 genre-to-genre edges. *(Amended 2026-08-01 — originally "P279; the artist axis
  (P737) is phase 2." P279 is category membership and cannot carry an origins answer; P737 runs
  genre-to-genre as well as artist-to-artist. The **artist** axis is still phase 2. IMPLEMENTATION doc §2.)*

## Explicitly not in this phase

The full corpus, real multi-hop planning, the SPA, any visualization, more than one eval metric, the LLM
judge, the artist axis, contested-claim UI, caching, and any density work. Each has a later phase.

## Definition of done

1. One successful Bedrock `converse` call, made and logged.
2. `terraform apply` provisions everything; `terraform destroy` removes everything.
3. A public URL returns a **streamed** response.
4. That response is generated from gated claims, and every claim resolves to a real source.
5. One eval metric runs in CI against a pinned artifact and passes.
6. Budget alarms armed; CloudWatch log retention set explicitly in Terraform.
7. Token cost is measured and logged, not estimated.

## Prerequisites

**Resolved 2026-07-30:** Terraform 1.15.8 and Docker Engine 29.6.2 are installed on WSL2 (the engine inside
the distro, not Docker Desktop). The AWS account exists on the paid plan in `us-east-1` with the $20 budget
armed.

**Still gating:** all 160 Bedrock quotas read 0 TPM and 0 RPM. Nothing in this phase can make a `converse`
call until that clears, which is exactly why step zero is step zero. It does not block writing the
IMPLEMENTATION doc.

## Cost

Fixed infrastructure is ~$0/month by design. The only spend is Bedrock tokens, and at v0.1 volumes that is
cents. Route tool turns to the cheap model. The eval suite is the real line item later, not now.

## Known risks

- **Bedrock access denial or delay.** Highest-impact risk in the phase; that is why it is task one.
- **Streaming plumbing.** The genuinely fiddly part. Retrofitting it later is real rework, which is why it is
  in v0.1 despite a two-sentence answer.
- **Docker on WSL2.** An environment problem, not a code problem, and it will still eat a session.
- **Graph semantics.** If hand-validating P279 shows the taxonomy cannot carry historical lineage, that is a
  real finding and it lands *before* ingestion is coded, which is the whole point of validating first.
- **Four unfamiliar things at once** — AWS, Terraform, Bedrock, Python under a year. This is the argument for
  the thinnest possible slice, and the reason "no React" is a feature of this phase.

## Left for the IMPLEMENTATION doc

Artifact schema; the graph-store backend pick among the $0 options; the streaming response contract and the
path-in-payload shape; the `Claim` model in code; which two tools; the five gold cases (hand-authored
**before** the agent is coded); Terraform module layout; the CI deploy job with OIDC.
