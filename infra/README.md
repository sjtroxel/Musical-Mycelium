# infra/

Everything about deploying this project lives here rather than in the repo root. That is a deliberate
choice — see the root-discipline note in `CLAUDE.md`.

```
infra/
  terraform/
    bootstrap/   state bucket, ECR repository, GitHub OIDC deploy role.  LOCAL state. Applied once.
    main/        Lambda, Function URL, execution role, log group, budgets, anomaly detection.
                 S3 backend. Applied by CI and by you.
  docker/
    Dockerfile              the Lambda container image
    Dockerfile.dockerignore build-context excludes (BuildKit reads this in preference to a root one)
```

Built at **phase 1 step 8**, 2026-08-03. Every `make` target that wraps these is in the root
`Makefile`; the flags below never have to be typed by hand.

## Why there are two Terraform roots

Not tidiness. A `aws_lambda_function` with `package_type = "IMAGE"` cannot be created until an image
already exists at the URI it names, and CI cannot assume a deploy role that CI has not yet created.
Both are ordering constraints, and `bootstrap/` turns them into a property of the directory layout
instead of a `-target` incantation somebody has to remember under pressure.

`bootstrap/` holds only what must exist before anything else can. It is applied once, from your
machine, and then largely forgotten.

## Local prerequisites — all present as of 2026-08-02

The original text here said none of these were installed. That was true when it was written on 2026-07-29
and stopped being true during the 2026-07-31 streaming spike, which built and pushed a real image.

| tool | version | notes |
|---|---|---|
| Terraform | 1.15.8 | |
| Docker | **29**.6.2 | daemon reachable from WSL2 |
| AWS CLI | 2.36.14 | |

**Docker 29 is the version that breaks Lambda image pushes by default.** Its BuildKit attaches provenance
and SBOM attestations, which wraps the image in a manifest list that Lambda rejects with
`InvalidParameterValueException`. Every image build in this project must pass
`--provenance=false --sbom=false`. See `docs/streaming-verification.md`.

## First deploy, in order

Nothing below has been run yet. Steps 0–2 need AWS credentials; everything above them does not.

**0. Deal with the hand-armed budgets first.** The $5/$10/$20 ladder was created outside Terraform,
and `main/cost.tf` now declares the same three budgets. Applying without resolving this either fails
on a name collision or, worse, silently creates a second set beside the originals. List what exists:

```bash
aws budgets describe-budgets --account-id "$(aws sts get-caller-identity --query Account --output text)" \
  --query 'Budgets[].BudgetName'
```

Terraform expects the names `musical-mycelium-monthly-5`, `-10`, and `-20`. If the existing names
match, import them (this happens after step 2, once `main/` is initialised):

```bash
acct="$(aws sts get-caller-identity --query Account --output text)"
for n in 5 10 20; do
  terraform -chdir=infra/terraform/main import \
    "aws_budgets_budget.monthly[\"$n\"]" "$acct:musical-mycelium-monthly-$n"
done
```

If they do not match, delete the console-created ones and let Terraform create its own. Budgets are
free and take effect immediately, so there is no window of exposure worth engineering around — but do
not skip the step and leave guardrails outside Terraform, because the guardrails are the last thing
that should be the exception to invariant 5.

**1. Apply bootstrap.**

```bash
make tf-bootstrap
terraform -chdir=infra/terraform/bootstrap output
```

Then set the deploy role ARN as a GitHub **repository variable** named `AWS_DEPLOY_ROLE_ARN`, and
your alert address as a repository **secret** named `ALERT_EMAIL`:

```bash
gh variable set AWS_DEPLOY_ROLE_ARN --body "$(terraform -chdir=infra/terraform/bootstrap output -raw github_deploy_role_arn)"
gh secret set ALERT_EMAIL
```

**2. Push an image, then apply main.** This is the two-stage part, and the order is the whole point —
`main/` reads the ECR repository by name and points the function at a tag that has to already exist.

```bash
make image-push
export TF_VAR_alert_email=you@example.com
make tf-init
make tf-plan     # read it
make tf-apply
```

**Deploying without spending anything on model calls.** Add `-var llm_provider=local`:

```bash
terraform -chdir=infra/terraform/main apply -var llm_provider=local
```

That deploys a real, public, streaming endpoint that walks the graph, gates every claim, and cites
real Wikidata statement URIs — with no model call and no spend. It proves the infrastructure, the
grounding path, and SSE-through-LWA. The prose comes from a template rather than a model, so a `local`
deploy alone does **not** close phase 1's definition of done.

This was the only way to deploy at all during the 2026-07-30 to 08-11 Bedrock quota block, and it is
still the current deployed state. Quota was restored on 08-11 and phase 1 DoD #1 (a real `converse`
call) is satisfied locally, but the public URL has not been redeployed onto Bedrock.

**Before dropping the flag, decide the timeout.** Per `.claude/rules/aws-and-cost.md`, streamed
responses are billed for the full function duration even when the client disconnects, so a public URL
on a real model bills for every visitor who triggers the loop and closes the tab. The flag is a spend
decision, not a formality.

This is only possible because of the LLM provider seam (invariant 7). It is the seam paying out.

**3. Verify it actually streams.** A 200 is not evidence. `TestClient` buffers and so does a
misconfigured Function URL, so the only real check is time-to-first-byte against total:

```bash
url="$(terraform -chdir=infra/terraform/main output -raw function_url)"
curl -fsS "${url}health"
curl -sN -o /dev/null -w 'ttfb %{time_starttransfer}s  total %{time_total}s\n' "${url}lineage?q=thrash%20metal"
```

The 2026-07-31 spike measured 0.214s against 10.22s. A ratio near 1.0 means the response is buffered
and one of the two required settings is missing — `AWS_LWA_INVOKE_MODE=response_stream` in the
Dockerfile, or `invoke_mode = "RESPONSE_STREAM"` on `aws_lambda_function_url`. Both are required, and
with only one, every request still returns 200.

## The off-switch

```bash
make tf-destroy                                  # main/ — the function, URL, role, logs, guardrails
terraform -chdir=infra/terraform/bootstrap destroy  # then the rest
```

**The order is not optional.** `bootstrap/` owns the bucket that holds `main/`'s state; destroying it
first deletes the record of what `main/` created and leaves those resources running and unmanaged.

## Migrating bootstrap state (optional)

`bootstrap/` uses local state, so its `terraform.tfstate` lives on one machine and is gitignored. That
is an accepted risk — it holds a handful of resources with predictable names, so the recovery is a few
`terraform import` calls rather than a rebuild. If you would rather not carry it, the bucket it
creates can hold its own state once it exists: add a `backend "s3"` block to
`bootstrap/versions.tf` with key `musical-mycelium/bootstrap.tfstate`, then
`terraform -chdir=infra/terraform/bootstrap init -migrate-state -backend-config=bucket=<bucket>`.

## Non-negotiables

- **Everything in Terraform**, so `terraform destroy` is a real and complete off-switch. That is this
  project's version of Patchwork's pause/resume scripts.
- **Budget alarms before the first `terraform apply`** — $5/$10/$20, plus Cost Anomaly Detection.
- **CloudWatch log retention set explicitly.** The default is never-expire, which bills forever. The
  execution role deliberately does not use the `AWSLambdaBasicExecutionRole` managed policy, because
  that grants `logs:CreateLogGroup` and lets the function recreate an unretained group.
- **No always-on resources**, no VPC, no NAT gateway, no provisioned concurrency. The absent VPC is
  load-bearing twice: ~$32/mo for a NAT gateway, and Function URLs cannot stream inside a VPC.
- **Reserved concurrency is a cost control and is not provisioned concurrency.** It is free and caps
  how much a public URL can bill; provisioned concurrency is banned.
- **The Lambda timeout is a cost control.** AWS bills the full duration of a streamed response even
  when the client disconnects.
- **No long-lived AWS keys.** Lambda gets an execution role; GitHub Actions authenticates with OIDC,
  scoped by trust policy to one repository and one branch.

Full rules in `.claude/rules/aws-and-cost.md`; full analysis in `docs/planning/03-COST-MODEL.md` and
`docs/planning/04-RISK-REGISTER.md`.
