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
  a better resume line.
- **Bedrock spend is the only real line item.** Route traversal and tool turns to the cheap model and use a
  stronger model only for synthesis and judging. Agentic loops are input-heavy — every turn re-sends
  accumulated context. Any operation that spends money at scale (the eval suite above all) goes behind an
  explicit confirmation prompt, ported from Patchwork's `confirm_spend`.
- **Track real token cost to CloudWatch from day one** so measured numbers replace the estimates.
