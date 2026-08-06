# These outputs are the interface between bootstrap and everything downstream: the backend config for
# `main/`, the two values GitHub Actions needs, and the registry URL for a local push.
#
# `make tf-bootstrap-outputs` prints them in a copy-pasteable form.

output "state_bucket" {
  description = "Pass to main/ as `terraform init -backend-config=bucket=<this>`."
  value       = aws_s3_bucket.state.id
}

output "ecr_repository_url" {
  description = "Push target for the Lambda image."
  value       = aws_ecr_repository.app.repository_url
}

output "github_deploy_role_arn" {
  description = "Set as the AWS_DEPLOY_ROLE_ARN repository variable in GitHub."
  value       = aws_iam_role.github_deploy.arn
}

output "account_id" {
  description = "Handy for constructing ARNs by hand; not a secret, but not worth pasting publicly either."
  value       = local.account_id
}

output "artifacts_bucket" {
  description = "Versioned, immutable record of every published corpus artifact."
  value       = aws_s3_bucket.artifacts.id
}
