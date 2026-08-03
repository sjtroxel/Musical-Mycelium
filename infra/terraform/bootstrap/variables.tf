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
  description = "owner/repo that CI runs from. Used to scope which workflow may assume the deploy role."
  type        = string
  default     = "sjtroxel/Musical-Mycelium"
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

    ECR storage bills at ~$0.10/GB-month beyond the 500MB free allowance, and this image is ~256MB
    uncompressed. Unbounded retention is how a $0 project quietly starts costing a few dollars a month
    for images nobody will ever roll back to.
  EOT
  type        = number
  default     = 3
}
