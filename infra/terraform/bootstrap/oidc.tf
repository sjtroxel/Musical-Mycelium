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

  # Added at phase 5 step 1, 2026-08-25. The SPA bucket is created by main/frontend.tf, NOT here —
  # unlike the state and artifact buckets above, which are records that must outlive a teardown. The
  # frontend is the application, and invariant 5 says `terraform destroy` on main/ has to take it with
  # it. So the name is mirrored here purely to scope the grant, the same coupling the comment above
  # describes.
  spa_bucket_name = "${var.project}-web-${local.account_id}"

  function_arn   = "arn:aws:lambda:${var.region}:${local.account_id}:function:${local.function_name}"
  exec_role_arn  = "arn:aws:iam::${local.account_id}:role/${local.exec_role_name}"
  log_group_arn  = "arn:aws:logs:${var.region}:${local.account_id}:log-group:${local.log_group_name}"
  spa_bucket_arn = "arn:aws:s3:::${local.spa_bucket_name}"
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
    #
    # **The *Tagging actions are not optional and cost a failed deploy to learn (2026-08-06, run
    # 31129597446).** `provider "aws"` in main/ sets `default_tags`, which the provider applies to
    # `aws_s3_object` too — and tagging an object is a SEPARATE IAM action from writing it. With
    # PutObject alone every upload returns 403 on `s3:PutObjectTagging`, naming an action nothing in
    # the Terraform config mentions. GetObjectTagging is here for the same reason ecr:ListTagsForResource
    # is in the EcrPush statement below: refresh reads tags, so its absence fails the *plan*.
    actions = [
      "s3:GetObject",
      "s3:GetObjectTagging",
      "s3:PutObject",
      "s3:PutObjectTagging",
    ]
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

  # --- The SPA bucket and its CloudFront distribution (phase 5 step 1) ---
  #
  # Scoped by resource, using the same reasoning the LambdaFunction statement above spells out:
  # enumerating every s3:* verb the provider calls across create, tag, policy, public-access-block,
  # object write and destroy is a list that is wrong until the fourth failed deploy, and the AWS
  # provider's *read* path for `aws_s3_bucket` alone calls a dozen Get* actions nothing in the config
  # mentions. One bucket ARN is a genuinely tight blast radius and an honest trade.
  #
  # Note this bucket does NOT exist in this root — main/ creates it. The grant therefore has to include
  # `s3:CreateBucket`, which is the one action here that reads oddly and is exactly right.
  statement {
    sid       = "SpaBucket"
    effect    = "Allow"
    actions   = ["s3:*"]
    resources = [local.spa_bucket_arn, "${local.spa_bucket_arn}/*"]
  }

  # CloudFront is the weaker of the two guardrails in this block and it is worth naming why rather than
  # letting `*` pass unremarked. **CloudFront does not support resource-level permissions for the
  # actions that matter**: `CreateDistribution` cannot be scoped to a distribution that does not exist
  # yet, and Origin Access Controls have no resource ARN form at all. Since scoping by resource is not
  # available, the bound has to come from the action list instead — which is the opposite trade from the
  # Lambda statement above, made for the opposite reason.
  #
  # `cloudfront:*` would be shorter and would silently include CreateKeyGroup, CreatePublicKey and the
  # signed-URL machinery, none of which this project uses. The list below is what a static-site
  # distribution actually needs, and a missing verb fails a plan loudly.
  statement {
    sid    = "CloudFrontDistribution"
    effect = "Allow"
    actions = [
      "cloudfront:CreateDistribution",
      "cloudfront:DeleteDistribution",
      "cloudfront:GetDistribution",
      "cloudfront:GetDistributionConfig",
      "cloudfront:ListDistributions",
      "cloudfront:UpdateDistribution",

      "cloudfront:CreateOriginAccessControl",
      "cloudfront:DeleteOriginAccessControl",
      "cloudfront:GetOriginAccessControl",
      "cloudfront:GetOriginAccessControlConfig",
      "cloudfront:ListOriginAccessControls",
      "cloudfront:UpdateOriginAccessControl",

      # `data "aws_cloudfront_cache_policy"` in main/frontend.tf resolves Managed-CachingOptimized by
      # name, so these fail the PLAN rather than the apply if absent — the same shape as
      # ecr:ListTagsForResource above, which cost a deploy to learn.
      "cloudfront:GetCachePolicy",
      "cloudfront:ListCachePolicies",

      # default_tags applies to the distribution, and tagging is a separate action from creating —
      # the lesson the ArtifactObjects statement above paid for with a failed deploy on 2026-08-06.
      "cloudfront:ListTagsForResource",
      "cloudfront:TagResource",
      "cloudfront:UntagResource",

      # Not needed until step 2, when CI syncs a real build and must invalidate the edge cache.
      # Included now on purpose: applying this root needs a local admin credential, and the standing
      # rule in .claude/rules/aws-and-cost.md is that the dev key is time-boxed and deleted after use.
      # A second bootstrap apply two steps from now costs more than three unused verbs do.
      "cloudfront:CreateInvalidation",
      "cloudfront:GetInvalidation",
      "cloudfront:ListInvalidations",
    ]
    resources = ["*"]
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
