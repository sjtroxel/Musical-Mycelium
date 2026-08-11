# Rule: AWS and cost

Canonical detail: `docs/planning/03-COST-MODEL.md` and `04-RISK-REGISTER.md` §1–3. The budget ceiling is
roughly $20/month total across all tooling, and there is a history of a real spending slip. Hard rules:

- **No always-on resources. Ever.** This killed Neptune Serverless (~$80/mo floor, no free tier, accruing
  from the hour it is created), Aurora Serverless v2 (~$44/mo), and RDS `db.t4g.micro` (free 12 months,
  then a ~$21.90/mo cliff on a dormant side project).
- **No managed database at all, and therefore no VPC.** The graph is tens of MB and fits in a Lambda's
  memory. Choosing no database deletes the VPC, which deletes the **NAT gateway at ~$32/mo** — a Lambda
  needing both a private database and the internet requires one. This is a cost decision, not a
  permanent architecture commitment: it sits behind the `GraphStore` seam and is swappable.
- **No provisioned concurrency.** It is the obvious cold-start fix and it is an always-on charge. Mitigate
  cold starts with a small image, module-scope caching, and streaming that masks latency instead.
- **Guardrails before the first `terraform apply`:** AWS Budgets at $5/$10/$20, Cost Anomaly Detection,
  and **CloudWatch log retention set explicitly in Terraform** — the default is never-expire, which bills
  forever.
- **Everything in Terraform so `terraform destroy` is a real off-switch.** That is this project's version
  of Patchwork's pause/resume scripts.
- **The account is on the PAID plan, not the Free Plan.** The Free Plan auto-closes the account at 6 months
  or credit exhaustion. This is portfolio infrastructure that has to stay live through a job search; a
  timer-based self-destruct could kill the deployed site mid-recruiter-visit with no visible failure.
- **Never join this account to an AWS Organization** — it forfeits the activation credits immediately.
  Credits expire 12 months from account creation.
- **No long-lived AWS keys.** Lambda gets an execution role; GitHub Actions uses OIDC. Better security and
  a better resume line. *(Amended 2026-07-31: this rule did not contemplate LOCAL developer credentials.
  IAM Identity Center is the right answer but requires an organization instance, which requires creating an
  AWS Organization — colliding with the credits rule above. Interim: a scoped IAM user with an access key,
  time-boxed and deleted after use. The credits question is unresolved and worth asking AWS directly.)*
- **The Lambda timeout is a COST control when streaming.** Verified 2026-07-31; AWS docs are explicit that
  *"streamed responses are not interrupted or stopped when the invoking client connection is broken.
  Customers are billed for the full function duration."* A visitor who triggers a multi-step agent loop on
  the public URL and closes the tab bills the full timeout. Set it as tight as the workload allows.
- **Bedrock spend is the only real line item.** Route traversal and tool turns to the cheap model and use a
  stronger model only for synthesis and judging. Agentic loops are input-heavy — every turn re-sends
  accumulated context. Any operation that spends money at scale (the eval suite above all) goes behind an
  explicit confirmation prompt, ported from Patchwork's `confirm_spend`.
- **Track real token cost to CloudWatch from day one** so measured numbers replace the estimates.
- **Bedrock access, as actually provisioned (confirmed by live calls 2026-08-11).** The account read 0
  across every quota from 07-30 and the standard allocation was restored on 08-11. Working today:
  **Claude Haiku 4.5** on `us.anthropic.claude-haiku-4-5-20251001-v1:0` (geo cross-region, 5M TPM /
  10 RPM), Sonnet 4.6 (6M / 10), and **Nova Pro** (2M / 25) — the non-Anthropic judge `evals.md` requires,
  which needs no Marketplace step at all. **Newest-generation rows read 0** (Opus 5, Sonnet 5, Fable 5,
  Opus 4.7/4.8): normal provisioning lag, not an account fault, so do not diagnose it as one.
- **RPM is the binding constraint, not TPM, and this is a design input.** 10 requests/minute against 5M
  tokens/minute means a fan-out workload exhausts requests first. The eval suite must throttle and back
  off; `planning/07` §315 already caps concurrency at 2–4 with exponential backoff, and that number is now
  a measured requirement rather than a precaution. More context budget does not help.
- **Third-party models need a one-time Marketplace subscription, and a scoped key cannot create it.**
  Bedrock's "Model access" page is retired; serverless models auto-enable on first invocation, but for
  Marketplace-served models (all Anthropic ones) the *first* invocation must come from an identity holding
  `aws-marketplace:Subscribe`. `mycelium-dev` deliberately does not have it. Done once for this account on
  2026-08-11 (agreement `agmt-khy4nwv8klfzzthldwq47ty1`, $0.00, no end date) via the console as root, which
  invariant 5 explicitly permits. **Do not add Marketplace permissions to the dev key or the Lambda
  execution role** — the entitlement is account-wide and `bedrock:InvokeModel` is sufficient afterwards.
