# infra/

Everything about deploying this project lives here rather than in the repo root. That is a deliberate
choice — see the root-discipline note in `CLAUDE.md`.

```
infra/
  terraform/   all AWS resources. Nothing is created by clicking in the console.
  docker/      the Lambda container image. Built with `docker build -f infra/docker/Dockerfile .`
```

Neither directory has contents yet, and that is correct: there is no AWS account and no code to package.
Both arrive at the walking-skeleton phase, and the `make` targets that wrap them arrive with them so the
`-f` flag never has to be typed by hand.

## Local prerequisites, when that phase starts

Neither tool is installed on this machine yet:

- **Terraform** — needed before the first `terraform plan`.
- **Docker** — needed to build the Lambda container image. On WSL2 this means Docker Desktop with WSL
  integration, or the engine installed inside the distro.

## Non-negotiables when this fills in

- **Everything in Terraform**, so `terraform destroy` is a real and complete off-switch. That is this
  project's version of Patchwork's pause/resume scripts.
- **Budget alarms before the first `terraform apply`** — $5/$10/$20, plus Cost Anomaly Detection.
- **CloudWatch log retention set explicitly.** The default is never-expire, which bills forever.
- **No always-on resources**, no VPC, no NAT gateway, no provisioned concurrency.
- **No long-lived AWS keys.** Lambda gets an execution role; GitHub Actions authenticates with OIDC.

Full rules in `.claude/rules/aws-and-cost.md`; full analysis in `docs/planning/03-COST-MODEL.md` and
`docs/planning/04-RISK-REGISTER.md`.
