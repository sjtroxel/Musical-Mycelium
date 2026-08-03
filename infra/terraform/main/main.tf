provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Root      = "main"
    }
  }
}

data "aws_caller_identity" "current" {}

# Read, not managed. The repository belongs to bootstrap/ because the image has to exist before this
# root can create a function that references it. Reading it by name keeps the two roots decoupled —
# no remote-state data source, no shared lock, and `main/` can be destroyed and reapplied without
# touching bootstrap at all.
data "aws_ecr_repository" "app" {
  name = var.project
}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # These four names are mirrored in bootstrap/oidc.tf, where the deploy role's policy names their
  # ARNs explicitly. Changing one without the other produces an AccessDenied in CI, which is the
  # intended failure — the alternative is a deploy role holding `*`.
  function_name  = var.project
  exec_role_name = "${var.project}-lambda-exec"
  log_group_name = "/aws/lambda/${var.project}"

  image_uri = "${data.aws_ecr_repository.app.repository_url}:${var.image_tag}"
}
