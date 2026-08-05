variable "project" {
  description = "Name prefix for every resource. Also the ECR repository name."
  type        = string
  default     = "musical-mycelium"
}

variable "region" {
  description = "AWS region. Bedrock model availability and the Function URL both live here."
  type        = string
  default     = "us-east-1"
}

variable "github_repo" {
  description = <<-EOT
    The repository whose workflows may assume the deploy role, in the exact form GitHub puts in the
    OIDC token's `sub` claim. Not a display name — a string AWS compares with `StringEquals`.

    **It carries numeric IDs, and that is not a typo.** Repositories created on or after
    2026-07-15 — and older ones that opted in — emit an *immutable* subject claim, which appends the
    permanent owner ID and repository ID after each name:

        repo:<owner>@<owner_id>/<repo>@<repo_id>:ref:refs/heads/<branch>

    The IDs are what make the claim immutable: deleting a repo and recreating one with the same name
    produces a new ID, so a stale trust policy cannot be used to mint credentials for it. A policy
    written against the old name-only form fails closed, with
    `Not authorized to perform sts:AssumeRoleWithWebIdentity` and no hint as to why — which is exactly
    what happened on 2026-08-05, on this workflow's first real run.

    Read the current value rather than assembling it by hand:

        gh api repos/<owner>/<repo>/actions/oidc/customization/sub

    and use its `sub_claim_prefix` verbatim.
  EOT
  type        = string
  default     = "sjtroxel@183318591/Musical-Mycelium@1316585483"
}

variable "github_branch" {
  description = <<-EOT
    The only branch whose workflow runs may assume the deploy role.

    This is the whole point of the OIDC trust policy. Scoped to a branch, a pull request from a fork
    cannot mint credentials for this account, because its token's `sub` claim names a pull-request ref
    rather than `refs/heads/main`. Widening this to `*` hands the account to anyone who can open a PR.
  EOT
  type        = string
  default     = "main"
}

variable "create_github_oidc_provider" {
  description = <<-EOT
    Whether to create the GitHub OIDC provider.

    An AWS account can hold exactly one IAM OIDC provider per issuer URL, so if any other project in
    this account has already registered token.actions.githubusercontent.com, creating a second one
    fails with EntityAlreadyExists. Set this to false in that case; the deploy role will attach to the
    existing provider by ARN.
  EOT
  type        = bool
  default     = true
}

variable "keep_image_count" {
  description = <<-EOT
    How many tagged images ECR retains before expiring the oldest.

    ECR storage bills at ~$0.10/GB-month beyond the 500MB free allowance. **ECR bills the COMPRESSED
    size**, which measured 63.8MB on the first real push (2026-08-03) — not the ~256MB uncompressed
    figure this comment previously quoted, which was the wrong number for a storage-billing decision.
    Three tags is therefore ~190MB, comfortably inside the free allowance.

    The cap stays anyway: unbounded retention is how a $0 project quietly starts costing a few dollars
    a month for images nobody will ever roll back to.
  EOT
  type        = number
  default     = 3
}
