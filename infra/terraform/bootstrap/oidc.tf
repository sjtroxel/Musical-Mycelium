# GitHub Actions authentication, without a long-lived AWS key.
#
# .claude/rules/aws-and-cost.md: "No long-lived AWS keys. Lambda gets an execution role; GitHub
# Actions uses OIDC." A workflow run presents a short-lived GitHub-signed token, AWS validates it
# against the provider below, and STS returns credentials that expire with the job. There is no
# secret in the repository to leak, rotate, or forget to rotate.

resource "aws_iam_openid_connect_provider" "github" {
  count = var.create_github_oidc_provider ? 1 : 0

  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]

  # IAM no longer verifies this thumbprint for the GitHub issuer — it validates the certificate chain
  # against its own trust store — but the argument is still required by the API, so the well-known
  # value goes here. It does not need rotating when GitHub rotates its certificate; that was the old
  # behaviour and it is the reason stale guides tell you to update it.
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]
}

data "aws_iam_openid_connect_provider" "existing" {
  count = var.create_github_oidc_provider ? 0 : 1

  url = "https://token.actions.githubusercontent.com"
}

locals {
  oidc_provider_arn = var.create_github_oidc_provider ? aws_iam_openid_connect_provider.github[0].arn : data.aws_iam_openid_connect_provider.existing[0].arn

  # These names are duplicated in infra/terraform/main/. That coupling is real: this policy has to
  # name the exact ARNs main/ will create, and a role that grants itself `*` to avoid the coupling is
  # not a security posture. If a name changes in main/, it changes here too — the outputs below exist
  # partly so a mismatch shows up as a failed apply rather than as a silently over-broad grant.
  function_name  = var.project
  exec_role_name = "${var.project}-lambda-exec"
  log_group_name = "/aws/lambda/${var.project}"

  function_arn  = "arn:aws:lambda:${var.region}:${local.account_id}:function:${local.function_name}"
  exec_role_arn = "arn:aws:iam::${local.account_id}:role/${local.exec_role_name}"
  log_group_arn = "arn:aws:logs:${var.region}:${local.account_id}:log-group:${local.log_group_name}"
}

data "aws_iam_policy_document" "github_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRoleWithWebIdentity"]

    principals {
      type        = "Federated"
      identifiers = [local.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }

    # The load-bearing condition. Without it, ANY GitHub repository in the world can assume this role.
    # Pinned to one repo and one branch ref, so a pull request — including one from a fork — cannot
    # mint credentials: its token's `sub` reads `repo:owner/name:pull_request`, not
    # `repo:owner/name:ref:refs/heads/main`.
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:sub"
      values   = ["repo:${var.github_repo}:ref:refs/heads/${var.github_branch}"]
    }
  }
}

resource "aws_iam_role" "github_deploy" {
  name               = "${var.project}-github-deploy"
  description        = "Assumed by GitHub Actions via OIDC to build, push, and apply infra/terraform/main."
  assume_role_policy = data.aws_iam_policy_document.github_assume.json

  # An hour is longer than any deploy this project will ever run, and it is the shortest ceiling that
  # does not risk a build expiring mid-push.
  max_session_duration = 3600
}

data "aws_iam_policy_document" "github_deploy" {
  # --- Terraform state ---
  statement {
    sid       = "TerraformState"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.state.arn]
  }

  statement {
    sid    = "TerraformStateObjects"
    effect = "Allow"
    # DeleteObject is required for S3 native locking (use_lockfile): the lock IS an object, and a job
    # that cannot delete it leaves the next run blocked on a lock nobody holds.
    actions   = ["s3:GetObject", "s3:PutObject", "s3:DeleteObject"]
    resources = ["${aws_s3_bucket.state.arn}/*"]
  }

  # --- Published corpus artifacts ---
  #
  # ListBucket is separated from the object statement for the same reason it is on the state bucket: it
  # is a *bucket* action and naming `bucket/*` as its resource silently grants nothing, which then fails
  # at plan time rather than at apply time and reads as a Terraform bug.
  statement {
    sid       = "ArtifactBucket"
    effect    = "Allow"
    actions   = ["s3:ListBucket", "s3:GetBucketLocation"]
    resources = [aws_s3_bucket.artifacts.arn]
  }

  statement {
    sid    = "ArtifactObjects"
    effect = "Allow"
    # **No DeleteObject, deliberately.** Published artifacts are immutable and a deploy has no business
    # removing one; the state bucket needs delete only because its lock IS an object. GetObject is here
    # so `terraform plan` can read existing object metadata without a permissions failure.
    actions   = ["s3:GetObject", "s3:PutObject"]
    resources = ["${aws_s3_bucket.artifacts.arn}/*"]
  }

  # --- Container image ---
  statement {
    sid       = "EcrLogin"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"] # This action does not support resource-level permissions.
  }

  # ListTagsForResource is not a push permission and is here anyway: `data "aws_ecr_repository"` in
  # main/ reads tags as part of resolving the repository, so the *plan* fails without it, before a
  # single resource is touched. Added 2026-08-05 after the workflow's first successful credential
  # exchange got eight steps in and died here. A local apply never finds this — `mycelium-dev` is a
  # broader key, and a least-privilege CI role is only ever proven by CI.
  statement {
    sid    = "EcrPush"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:BatchGetImage",
      "ecr:CompleteLayerUpload",
      "ecr:DescribeImages",
      "ecr:DescribeRepositories",
      "ecr:GetDownloadUrlForLayer",
      "ecr:InitiateLayerUpload",
      "ecr:ListImages",
      "ecr:ListTagsForResource",
      "ecr:PutImage",
      "ecr:UploadLayerPart",
    ]
    resources = [aws_ecr_repository.app.arn]
  }

  # --- The function itself ---
  #
  # Scoped by resource rather than by action. Enumerating every lambda:* verb the provider calls
  # across create, update, tag, concurrency, function-URL and destroy is a list that is wrong until
  # the fourth failed deploy; confining the wildcard to one function ARN is the honest trade, and it
  # is a genuinely tight blast radius.
  statement {
    sid       = "LambdaFunction"
    effect    = "Allow"
    actions   = ["lambda:*"]
    resources = [local.function_arn, "${local.function_arn}:*"]
  }

  statement {
    sid       = "LambdaAccountRead"
    effect    = "Allow"
    actions   = ["lambda:GetAccountSettings", "lambda:ListFunctions"]
    resources = ["*"] # Neither supports resource-level permissions.
  }

  # --- The execution role main/ creates and passes to the function ---
  statement {
    sid    = "ExecutionRoleLifecycle"
    effect = "Allow"
    actions = [
      "iam:CreateRole",
      "iam:DeleteRole",
      "iam:GetRole",
      "iam:TagRole",
      "iam:UntagRole",
      "iam:UpdateRole",
      "iam:UpdateAssumeRolePolicy",
      "iam:PutRolePolicy",
      "iam:GetRolePolicy",
      "iam:DeleteRolePolicy",
      "iam:ListRolePolicies",
      "iam:ListAttachedRolePolicies",
      "iam:ListInstanceProfilesForRole",
      "iam:ListRoleTags",
    ]
    resources = [local.exec_role_arn]
  }

  # PassRole is the permission that actually matters here: without the resource constraint, a
  # compromised workflow could attach ANY role in the account to a Lambda it controls and inherit that
  # role's permissions. Constrained to one role, and to Lambda as the only service that may receive it.
  statement {
    sid       = "PassExecutionRoleToLambdaOnly"
    effect    = "Allow"
    actions   = ["iam:PassRole"]
    resources = [local.exec_role_arn]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["lambda.amazonaws.com"]
    }
  }

  # --- Logs ---
  statement {
    sid    = "LogGroup"
    effect = "Allow"
    actions = [
      "logs:CreateLogGroup",
      "logs:DeleteLogGroup",
      "logs:PutRetentionPolicy",
      "logs:DeleteRetentionPolicy",
      "logs:TagResource",
      "logs:UntagResource",
      "logs:ListTagsForResource",
    ]
    resources = [local.log_group_arn, "${local.log_group_arn}:*"]
  }

  statement {
    sid       = "LogGroupRead"
    effect    = "Allow"
    actions   = ["logs:DescribeLogGroups"]
    resources = ["*"] # Does not support resource-level permissions.
  }

  # --- Cost guardrails ---
  statement {
    sid       = "Budgets"
    effect    = "Allow"
    actions   = ["budgets:*"]
    resources = ["arn:aws:budgets::${local.account_id}:budget/*"]
  }

  statement {
    sid    = "CostAnomalyDetection"
    effect = "Allow"
    actions = [
      "ce:CreateAnomalyMonitor",
      "ce:UpdateAnomalyMonitor",
      "ce:DeleteAnomalyMonitor",
      "ce:GetAnomalyMonitors",
      "ce:CreateAnomalySubscription",
      "ce:UpdateAnomalySubscription",
      "ce:DeleteAnomalySubscription",
      "ce:GetAnomalySubscriptions",
      "ce:TagResource",
      "ce:UntagResource",
      "ce:ListTagsForResource",
    ]
    resources = ["*"] # Cost Explorer does not support resource-level permissions for these.
  }
}

resource "aws_iam_role_policy" "github_deploy" {
  name   = "${var.project}-deploy"
  role   = aws_iam_role.github_deploy.id
  policy = data.aws_iam_policy_document.github_deploy.json
}
