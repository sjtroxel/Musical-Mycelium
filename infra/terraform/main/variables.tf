variable "project" {
  description = "Name prefix. Must match the value used in bootstrap/ — the deploy role's policy names these ARNs."
  type        = string
  default     = "musical-mycelium"
}

variable "region" {
  description = "AWS region. Must match the backend region and the region Bedrock is called in."
  type        = string
  default     = "us-east-1"
}

variable "image_tag" {
  description = <<-EOT
    Which image in ECR the function runs.

    CI passes the git sha, so what is deployed is always traceable to a commit and a rollback is
    "apply the previous sha". `latest` is the manual-apply convenience default and is the weaker
    choice: two applies with the same tag are indistinguishable to Terraform, so nothing changes in
    the plan even though the image did.
  EOT
  type        = string
  default     = "latest"
}

variable "alert_email" {
  description = <<-EOT
    Where budget and cost-anomaly notifications go. No default: an unset alert address is a guardrail
    that exists in the plan and not in reality, and this project's cost rules are the reason the
    account is survivable at all.

    Supply it as TF_VAR_alert_email rather than in a committed tfvars file.
  EOT
  type        = string

  validation {
    condition     = can(regex("^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$", var.alert_email))
    error_message = "alert_email must be an email address."
  }
}

variable "llm_provider" {
  description = <<-EOT
    Which LLM implementation the deployed function builds — `build_llm()`'s provider, as
    MYCELIUM_LLM_PROVIDER.

    This is a variable rather than a constant because it is the thing that decoupled DEPLOYING from
    the Bedrock quota, through the 2026-07-30 to 08-11 block. `local` runs the whole stack — tool loop,
    deterministic gate, real cited claims off the pinned artifact, SSE — with no model call and no
    spend, which is how the infrastructure was proven end to end while every daily-token quota read 0.

    Quota was restored 2026-08-11 and `bedrock` is now a working value, but the deployed function has
    NOT yet been flipped to it. Doing so is a redeploy and a spend decision, not a config typo: a
    public URL calling a real model bills for every visitor, and per aws-and-cost.md the Lambda timeout
    is the cost control that bounds it. Decide the timeout before flipping this.

    That is invariant 7 (the LLM provider seam) doing the job it was put there to do.

    Be honest about what a `local` deploy is: the prose comes from a template, not a model. It proves
    the plumbing, the grounding path, and the streaming. It does not close phase 1's definition of
    done, which requires a real converse call and measured token cost.
  EOT
  type        = string
  default     = "bedrock"

  validation {
    condition     = contains(["bedrock", "local"], var.llm_provider)
    error_message = "llm_provider must be `bedrock` or `local`. `scripted` is a test double and needs responses injected."
  }
}

variable "model_id" {
  description = <<-EOT
    The Bedrock model the agent calls, as MYCELIUM_MODEL_ID.

    Undecided from 2026-08-03 until the quota cleared; **settled 2026-08-11** by the first real
    `converse` call. The default below — Claude Haiku 4.5 on the `us.` geo cross-region inference
    profile — is confirmed working on this account at 5M TPM / 10 RPM.

    Note that RPM, not TPM, is the binding constraint: 10 requests per minute against 5M tokens per
    minute means a fan-out workload runs out of requests first. It stays configuration so the choice
    can change without touching code or rebuilding the image.
  EOT
  type        = string
  default     = "us.anthropic.claude-haiku-4-5-20251001-v1:0"
}

variable "memory_mb" {
  description = <<-EOT
    Lambda memory, which also buys proportional CPU.

    1024 is chosen for cold start, not for the request: the artifact parse and the FastAPI import
    happen during INIT, and more CPU makes that shorter. It stays inside the free tier by a wide
    margin — 400,000 GB-seconds/month is roughly 390,000 seconds at this size.
  EOT
  type        = number
  default     = 1024
}

variable "timeout_seconds" {
  description = <<-EOT
    THE LAMBDA TIMEOUT IS A COST CONTROL, not just a reliability setting.

    Verified against AWS documentation on 2026-07-31: "streamed responses are not interrupted or
    stopped when the invoking client connection is broken. Customers are billed for the full function
    duration." A visitor who opens the public URL, triggers the agent loop, and closes the tab bills
    the entire timeout. On a $20 ceiling with a recruiter-facing URL, this number is the exposure.

    30s is the starting point from IMPLEMENTATION 9. Measure the real loop and tighten it.
  EOT
  type        = number
  default     = 30
}

variable "reserved_concurrency" {
  description = <<-EOT
    Cap on simultaneous executions — the blast-radius control for a public, unauthenticated URL.

    Not to be confused with PROVISIONED concurrency, which is banned by .claude/rules/aws-and-cost.md
    because it bills whether or not anyone visits. Reserved concurrency is free; it only refuses to
    scale past the cap, which is exactly what should happen when a public URL is being hammered.

    -1 means unreserved. Set it to -1 if apply fails with "decreases account's
    UnreservedConcurrentExecution below its minimum value of [N]" — that means this account's
    concurrency ceiling is still at a new-account default, and the budget alarms carry the load until
    a limit increase lands.

    MEASURED 2026-08-03 on the first apply: the error named **[10]**, not the [100] this comment
    originally predicted. This account's entire concurrency ceiling is ~10 against a normal 1,000, so
    a reservation of 5 was refused and the deploy runs at -1 with the account ceiling doing the job.

    Worth knowing for a reason beyond Lambda: it was independent evidence that the Bedrock zero-token
    quota was new-account posture rather than anything specific to this account or its owner. Two
    unrelated services, clamped by the same automation.

    That inference was CONFIRMED on 2026-08-11, when Bedrock's standard allocation was restored
    without any change on this side. Worth keeping as a worked example: the reasoning that read a
    second, unrelated clamped service as evidence about the first turned out to be correct.
  EOT
  type        = number
  default     = 5
}

variable "log_retention_days" {
  description = <<-EOT
    CloudWatch log retention, set EXPLICITLY because the default is never-expire, which bills forever.
    That is a hard rule in .claude/rules/aws-and-cost.md and one of the named guardrails in the
    phase-1 definition of done.
  EOT
  type        = number
  default     = 14
}

variable "budget_thresholds" {
  description = "The $5/$10/$20 ladder from .claude/rules/aws-and-cost.md. Dollars, monthly."
  type        = list(number)
  default     = [5, 10, 20]
}

variable "cors_allowed_origins" {
  description = <<-EOT
    Origins allowed to call the Function URL from a browser.

    ["*"] while the only client is curl and the eventual SPA has no domain yet. Narrow this to the
    CloudFront domain when phase 5 ships a frontend — CORS is not a security boundary for a public
    read-only endpoint, but a wildcard that outlives its reason is how one stops being noticed.
  EOT
  type        = list(string)
  default     = ["*"]
}
