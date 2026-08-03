# The bucket that holds main/'s Terraform state.
#
# Cost: fractions of a cent. A state file for this project is tens of KB, and S3 has no always-on
# component — which is the rule this project is built around (.claude/rules/aws-and-cost.md).

resource "aws_s3_bucket" "state" {
  bucket = local.state_bucket

  # force_destroy = true is a deliberate choice and it deserves the argument.
  #
  # The instinct here is `lifecycle { prevent_destroy = true }`, because a deleted state bucket is a
  # bad day. But invariant 5 says `terraform destroy` must be a REAL and COMPLETE off-switch, and a
  # versioned bucket holding objects refuses to delete without this flag — so prevent_destroy would
  # trade a complete off-switch for a guardrail that only fires when you have already typed
  # `terraform destroy` in the bootstrap directory on purpose.
  #
  # The ordering rule that makes this safe is in infra/README.md and it is not optional: destroy
  # `main/` FIRST, then `bootstrap/`. Reversing it deletes the state that describes main's resources
  # and leaves them running and unmanaged, which is the expensive failure, not this flag.
  force_destroy = true
}

resource "aws_s3_bucket_versioning" "state" {
  bucket = aws_s3_bucket.state.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "state" {
  bucket = aws_s3_bucket.state.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# Versioning is what makes a corrupted or truncated state recoverable, and it is also what makes an
# otherwise-free bucket accumulate objects forever. Thirty days is long enough to notice and roll back
# a bad apply, short enough that history does not become a line item.
resource "aws_s3_bucket_lifecycle_configuration" "state" {
  bucket = aws_s3_bucket.state.id

  # The provider requires versioning to be settled before lifecycle rules reference noncurrent
  # versions; without this the first apply can race and fail.
  depends_on = [aws_s3_bucket_versioning.state]

  rule {
    id     = "expire-noncurrent-state-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
