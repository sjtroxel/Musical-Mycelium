# Publish every corpus artifact in the repo to the record bucket.
#
# **Every version, not the pinned one, and that is the point.** The pinned version already lives in
# three places that have to move together — `ingest/wikidata.py:ARTIFACT_VERSION`,
# `graph/memory.py:PINNED_ARTIFACT_VERSION` and `eval/datasets/gold_v0_1.json:artifact_version_pin`.
# A Terraform variable naming it would be a fourth, and the fourth is the one that silently drifts.
# Uploading whatever versions exist on disk needs no pin at all and satisfies "one object per artifact
# version" directly.
#
# The Lambda does **not** read from here. It reads the copy baked into its image (ingest/wikidata.py),
# which is what keeps the cold path free of an S3 fetch and an IAM round trip. This is the record.

locals {
  # Mirrored from bootstrap/main.tf, deliberately, rather than read through a remote-state data source.
  # Same decoupling argument as the ECR repository above: no shared lock, no cross-root state
  # dependency, and `main/` can be destroyed and reapplied without touching bootstrap. The cost of
  # mirroring is that changing the formula in one place without the other produces an AccessDenied in
  # CI — which is the intended failure, and it is loud.
  artifacts_bucket = "${var.project}-artifacts-${local.account_id}"

  artifacts_dir = "${path.module}/../../../src/musical_mycelium/artifacts"

  # graph.json and manifest.json for every version directory present.
  artifact_files = fileset(local.artifacts_dir, "v*/*.json")
}

resource "aws_s3_object" "artifact" {
  for_each = local.artifact_files

  bucket = local.artifacts_bucket
  key    = "artifacts/${each.value}"
  source = "${local.artifacts_dir}/${each.value}"

  content_type = "application/json"

  # etag is what makes a changed published artifact *visible* in a plan instead of silent. A released
  # version should never change, so a diff here is a finding: it means something rewrote a version that
  # downstream evals are pinned to. v0.3.0's manifest legitimately changed once, on 2026-08-06, when
  # VERIFICATION_LEVELS widened and its counts gained two zero-valued keys — graph.json and its sha256
  # were untouched. That is the only kind of change that should ever appear here.
  etag = filemd5("${local.artifacts_dir}/${each.value}")
}
