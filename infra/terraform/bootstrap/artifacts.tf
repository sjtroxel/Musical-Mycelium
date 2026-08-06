# The bucket that holds the published corpus artifacts.
#
# Scope-doc DoD #1 requires the artifact to land in S3. Phase 1 baked it into the container image
# instead, for a good reason: no S3 fetch on the cold path, no IAM round trip, no network dependency at
# INIT. This is **both, not either** — the image copy stays and remains what the Lambda actually reads;
# this bucket is the versioned, immutable *record*.
#
# What that record buys, stated honestly: the artifacts are already in git, so this is not the only
# durable copy. What it adds is a copy outside the repo that CI writes on every deploy, so "which corpus
# did that eval score" has an answer that does not depend on a git checkout being intact.
#
# It lives in bootstrap/ rather than main/ on purpose. `terraform destroy` on main/ is meant to be a real
# and complete off-switch for the running service; it should not also erase the record of what the
# service was serving.
#
# Cost: a few MB with versioning on. Inside the S3 free tier, nowhere near a rounding error against the
# $20/month ceiling, and **no always-on component** — the rule this project is built around
# (.claude/rules/aws-and-cost.md).

resource "aws_s3_bucket" "artifacts" {
  bucket = local.artifacts_bucket

  # Same argument as the state bucket, same conclusion: invariant 5 says `terraform destroy` must be a
  # REAL and COMPLETE off-switch, and a versioned bucket holding objects refuses to delete without this.
  # `prevent_destroy` would trade a complete off-switch for a guardrail that only fires once you have
  # already typed `terraform destroy` in the bootstrap directory on purpose.
  force_destroy = true
}

# Versioning here is belt-and-braces rather than the primary mechanism. Each artifact version is its own
# KEY, so a correctly-behaved build never overwrites anything and never creates a noncurrent version at
# all. Versioning exists to make an *incorrect* build — one that rewrites a released version in place —
# recoverable instead of silent.
resource "aws_s3_bucket_versioning" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# **No noncurrent-version expiration here, and that is the difference from the state bucket.** State
# history is disposable after thirty days; a corpus artifact is the thing an eval result is pinned to,
# and quietly deleting it months later would make an old benchmark unverifiable — the exact failure the
# pin exists to prevent (.claude/rules/evals.md). Only incomplete uploads are cleaned up, which is
# hygiene rather than retention.
resource "aws_s3_bucket_lifecycle_configuration" "artifacts" {
  bucket = aws_s3_bucket.artifacts.id

  depends_on = [aws_s3_bucket_versioning.artifacts]

  rule {
    id     = "abort-incomplete-uploads"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
