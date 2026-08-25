# The function, its role, its logs, and its public URL.
#
# No VPC anywhere in this file, and that absence is load-bearing twice over. It was a cost decision —
# a Lambda needing both a private subnet and the internet requires a NAT gateway at ~$32/month, which
# is more than this project's entire budget. It is ALSO a correctness requirement: AWS documents that
# Function URLs do not support response streaming inside a VPC, so adding one would break invariant 9
# silently. See docs/streaming-verification.md.

# --- logs -------------------------------------------------------------------------------------
#
# Created here, BEFORE the function, and not left to Lambda. A log group Lambda creates for itself
# has no retention policy, which means never-expire, which bills forever. Creating it explicitly is
# how the retention setting becomes a fact rather than an intention.
resource "aws_cloudwatch_log_group" "app" {
  name              = local.log_group_name
  retention_in_days = var.log_retention_days
}

# --- execution role ---------------------------------------------------------------------------

data "aws_iam_policy_document" "lambda_assume" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "exec" {
  name               = local.exec_role_name
  description        = "Execution role for the ${var.project} Lambda. Logs and Bedrock invoke, nothing else."
  assume_role_policy = data.aws_iam_policy_document.lambda_assume.json
}

data "aws_iam_policy_document" "exec" {
  # The obvious move here is to attach the AWSLambdaBasicExecutionRole managed policy. It is not used
  # deliberately: it grants logs:CreateLogGroup, which lets the function create a REPLACEMENT log
  # group with no retention if the Terraform-managed one is ever missing — quietly reintroducing the
  # never-expire default this project has a hard rule against. The function does not need to create a
  # log group. It needs to write to the one above.
  statement {
    sid       = "WriteToItsOwnLogGroup"
    effect    = "Allow"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.app.arn}:*"]
  }

  statement {
    sid    = "InvokeBedrock"
    effect = "Allow"
    actions = [
      "bedrock:InvokeModel",
      "bedrock:InvokeModelWithResponseStream",
    ]

    # Two ARN shapes, and both are required for a cross-region inference profile to work.
    #
    # The call names the inference profile, but Bedrock then routes it to a foundation model in
    # whichever region has capacity — so the caller needs invoke permission on the foundation model in
    # regions it never names. That is why the foundation-model ARN carries a wildcard region and an
    # empty account field; it is the documented shape, not a shortcut.
    #
    # Whether a cross-region profile is required at all is still open (variables.tf, model_id) and the
    # first live converse call settles it. Granting both now means that answer does not also require
    # an IAM change.
    resources = [
      "arn:aws:bedrock:*::foundation-model/*",
      "arn:aws:bedrock:${var.region}:${local.account_id}:inference-profile/*",
      "arn:aws:bedrock:*:${local.account_id}:inference-profile/*",
    ]
  }
}

resource "aws_iam_role_policy" "exec" {
  name   = "${var.project}-exec"
  role   = aws_iam_role.exec.id
  policy = data.aws_iam_policy_document.exec.json
}

# --- the function -----------------------------------------------------------------------------

resource "aws_lambda_function" "app" {
  function_name = local.function_name
  role          = aws_iam_role.exec.arn
  description   = "Musical Mycelium: streams a grounded, cited genre lineage from a pinned graph artifact."

  # Container image rather than a zip. The 250MB unzipped limit on zip packages is what forces this
  # (invariant 8); container images get 10GB.
  package_type = "Image"
  image_uri    = local.image_uri

  # x86_64 to match the mandatory `--platform linux/amd64` in the Dockerfile. An arm64 image against
  # an x86_64 function builds, pushes, deploys, and then fails at invoke.
  architectures = ["x86_64"]

  memory_size = var.memory_mb
  timeout     = var.timeout_seconds

  reserved_concurrent_executions = var.reserved_concurrency

  environment {
    variables = {
      # The image defaults to bedrock; setting it here means the deployed configuration is readable in
      # the console without going and reading a Dockerfile, AND that it can be changed without
      # rebuilding the image. `-var llm_provider=local` deploys a working, streaming, fully grounded
      # endpoint with no model call at all — how this shipped through the quota block, and still the
      # deployed state until a deliberate redeploy onto Bedrock (restored 2026-08-11).
      MYCELIUM_LLM_PROVIDER = var.llm_provider
      MYCELIUM_MODEL_ID     = var.model_id
      AWS_REGION_NAME       = var.region

      # Empty by default, and that is a working configuration: token counts still reach CloudWatch and
      # dollar figures stay silent. Present here rather than absent so the silence is visibly deliberate
      # — see `variables.tf` and `api/telemetry.py` for why a hardcoded price is worse than no price.
      MYCELIUM_TOKEN_PRICES = var.token_prices
    }
  }

  # Without this the first apply can create the function, watch Lambda auto-create an unretained log
  # group a millisecond before Terraform creates the managed one, and fail on a name collision.
  depends_on = [
    aws_cloudwatch_log_group.app,
    aws_iam_role_policy.exec,
  ]
}

# --- the public URL ---------------------------------------------------------------------------

resource "aws_lambda_function_url" "app" {
  function_name = aws_lambda_function.app.function_name

  # Public and unauthenticated, on purpose: this is a portfolio demo whose whole value is that a
  # recruiter can click a link. The exposure is bounded by reserved concurrency, a tight timeout, and
  # the budget ladder rather than by a credential — and the endpoint is read-only over a graph that is
  # baked into the image, so there is nothing behind it to protect.
  authorization_type = "NONE"

  # HALF of invariant 9. The other half is AWS_LWA_INVOKE_MODE=response_stream in the Dockerfile.
  # Both are required. With only one, every request still returns 200 and streaming silently does not
  # happen — which is the failure mode that eats an afternoon because nothing looks broken.
  invoke_mode = "RESPONSE_STREAM"

  # Narrowed from ["*"] at phase 5 step 1, 2026-08-25. The CloudFront domain is READ FROM THE RESOURCE
  # rather than passed as a variable value: the distribution's domain does not exist until the apply
  # that creates it, so a literal value would need two applies with the wildcard live in between, and
  # would go stale if the distribution were ever replaced. There is no dependency cycle — CloudFront
  # does not front this Function URL (IMPLEMENTATION §4.1), so nothing points back the other way.
  #
  # `cors_extra_origins` is the escape hatch for a Vite dev server calling the DEPLOYED backend. It is
  # empty by default so that shape has to be asked for.
  cors {
    allow_origins = concat(
      ["https://${aws_cloudfront_distribution.spa.domain_name}"],
      var.cors_extra_origins,
    )
    allow_methods = ["GET"]
    allow_headers = ["content-type"]
    max_age       = 3600
  }
}
