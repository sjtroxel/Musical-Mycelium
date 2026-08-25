# The SPA's hosting spine: a private S3 bucket, a CloudFront distribution in front of it, and the
# Origin Access Control that is the only thing allowed to read the bucket.
#
# **This bucket lives in main/, not bootstrap/, and that is deliberate.** The artifacts bucket is in
# bootstrap because it is a *record* that must outlive any teardown of the application. This one is the
# application, and invariant 5 says `terraform destroy` has to be a real off-switch — a frontend left
# standing in a bucket bootstrap owns would be exactly the "easiest thing to accidentally make
# un-destroyable" the phase 5 plan names in its §7.
#
# **CloudFront does NOT front the Function URL.** Two origins, two hostnames, per IMPLEMENTATION §4.1:
# the streaming path cost a whole verification spike to establish and putting an untested intermediary
# in front of it is the one place in this phase where a wrong call is expensive.

locals {
  # Account-suffixed because S3 bucket names are globally unique and `musical-mycelium-web` is the kind
  # of name someone else already has. Same formula as the artifacts bucket, for the same reason.
  spa_bucket = "${var.project}-web-${local.account_id}"
}

resource "aws_s3_bucket" "spa" {
  bucket = local.spa_bucket

  # No force_destroy. The bucket holds a build output and nothing irreplaceable, but a `destroy` that
  # silently empties a bucket is a habit worth not having in a repo where another bucket holds the
  # published corpus. If a destroy fails on a non-empty bucket, empty it deliberately.
}

# The bucket is private and stays private. Every byte a visitor sees arrives through CloudFront, which
# is what makes the OAC below the only read path rather than one of two.
resource "aws_s3_bucket_public_access_block" "spa" {
  bucket = aws_s3_bucket.spa.id

  # All four, including block_public_policy. The OAC grant below is a bucket policy, and the reflex is
  # to disable that setting to let one through — which is wrong here. S3 judges a policy public when it
  # grants an unconditioned `*` principal; this one names a Service principal AND conditions on a single
  # distribution ARN, so it is not public by that test and does not need the block relaxed.
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# OAC rather than the older Origin Access Identity: OAI is legacy, does not support SigV4 against
# newer regions cleanly, and AWS's own guidance is OAC for anything new.
resource "aws_cloudfront_origin_access_control" "spa" {
  name                              = local.spa_bucket
  description                       = "CloudFront to the ${var.project} SPA bucket. The only read path."
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# Managed policies rather than hand-rolled ones. CachingOptimized is the standard static-asset policy
# (gzip/brotli on, query strings and cookies out of the cache key) and reading it as a data source
# means the id is resolved by name instead of pasted as a UUID nobody can verify by eye.
data "aws_cloudfront_cache_policy" "optimized" {
  name = "Managed-CachingOptimized"
}

resource "aws_cloudfront_distribution" "spa" {
  enabled             = true
  comment             = "${var.project} SPA"
  default_root_object = "index.html"

  # US, Canada, Europe. The cheapest class, and the audience for a portfolio demo is a recruiter, not
  # a global one. CloudFront's free tier covers 1 TB/month out regardless; this reduces the per-request
  # price outside that tier rather than the tier itself.
  price_class = "PriceClass_100"

  # Terraform's default is to block until the distribution reaches Deployed, which is 5-15 minutes on
  # every apply — paid for in Actions minutes on a deploy whose Lambda half finishes in one. The domain
  # name is returned at creation and propagation continues without anyone watching it. The cost is that
  # an apply can report success a few minutes before the edge actually serves the change; nothing in
  # this phase gates on that, and step 2's sync will need an explicit invalidation regardless.
  wait_for_deployment = false

  origin {
    domain_name              = aws_s3_bucket.spa.bucket_regional_domain_name
    origin_id                = "spa"
    origin_access_control_id = aws_cloudfront_origin_access_control.spa.id
  }

  default_cache_behavior {
    target_origin_id       = "spa"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    compress               = true
    cache_policy_id        = data.aws_cloudfront_cache_policy.optimized.id
  }

  # Client-side routing: a deep link to a path S3 has no object for must return the app, not S3's XML.
  # 403 is listed alongside 404 because a private bucket answers a missing key with AccessDenied — S3
  # will not confirm that an object it will not serve you also does not exist.
  #
  # Present in step 1, before there are any routes to deep-link to, because it is a property of the
  # distribution rather than of the app, and a distribution update is a slow thing to discover you need.
  dynamic "custom_error_response" {
    for_each = [403, 404]

    content {
      error_code            = custom_error_response.value
      response_code         = 200
      response_page_path    = "/index.html"
      error_caching_min_ttl = 0
    }
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    # The *.cloudfront.net certificate. No custom domain in this phase — IMPLEMENTATION §11 puts it
    # out of scope, and a custom domain drags in ACM in us-east-1 and a DNS zone.
    cloudfront_default_certificate = true
  }

  # No access logging. It needs a second bucket with an ACL-based grant, and there is nothing this
  # project would do with the logs. CloudWatch already carries the numbers that matter.
}

# The bucket policy is what the OAC actually spends: CloudFront signs requests as the service principal
# and this is the grant that honours them. `AWS:SourceArn` scoped to this one distribution is the
# difference between "CloudFront may read this bucket" and "*any* CloudFront distribution in any account
# may read this bucket", which is the confused-deputy shape this condition exists for.
data "aws_iam_policy_document" "spa" {
  statement {
    sid       = "CloudFrontReadViaOAC"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["${aws_s3_bucket.spa.arn}/*"]

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    condition {
      test     = "StringEquals"
      variable = "AWS:SourceArn"
      values   = [aws_cloudfront_distribution.spa.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "spa" {
  bucket = aws_s3_bucket.spa.id
  policy = data.aws_iam_policy_document.spa.json

  # Without this the policy can be written before the public access block settles and S3 rejects it.
  depends_on = [aws_s3_bucket_public_access_block.spa]
}

# --- The step 1 placeholder ---
#
# Terraform ships this, not CI, so that `terraform apply` on its own produces a working URL with no
# build step involved. That makes the destroy-then-apply check invariant 5 demands (§7) a single
# operation rather than a two-system dance, and it means step 1 can be verified today against nothing
# but the plan.
#
# **Step 2 replaces this with a real build synced from CI, and this resource goes away with it.** It is
# a placeholder in the literal sense: if it is still here when the SPA ships, something was skipped.
resource "aws_s3_object" "placeholder" {
  bucket = aws_s3_bucket.spa.id
  key    = "index.html"
  source = "${path.module}/placeholder.html"

  # Explicit, because the provider infers text/html from the KEY and the key here is index.html while
  # the file on disk is placeholder.html. Without this a browser would be offered a download.
  content_type = "text/html; charset=utf-8"

  # Same reason as the artifact objects: makes a changed file visible in the plan rather than silent.
  etag = filemd5("${path.module}/placeholder.html")
}
