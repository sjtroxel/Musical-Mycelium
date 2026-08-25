output "function_url" {
  # The example query is a real question, not a bare noun. `thrash metal` was here until 2026-08-25 and
  # it routes to query_kind "coverage": the agent reports what the graph holds and correctly declines to
  # answer a question it was not asked, so it never narrates. Copy-pasting that as a first look at the
  # system shows the refusal path and none of the synthesis. Same defect the deploy smoke test had.
  description = "The public API endpoint. `curl -N --get --data-urlencode 'q=How is the blues connected to heavy metal?' \"$(terraform output -raw function_url)lineage\"`."
  value       = aws_lambda_function_url.app.function_url
}

output "site_url" {
  description = "The public SPA. This is the link a recruiter clicks."
  value       = "https://${aws_cloudfront_distribution.spa.domain_name}"
}

output "spa_bucket" {
  description = "Where the built frontend is synced. `aws s3 sync web/dist s3://<this>/` from step 2 on."
  value       = aws_s3_bucket.spa.id
}

output "distribution_id" {
  description = "For `aws cloudfront create-invalidation --distribution-id <this> --paths '/*'` after a sync."
  value       = aws_cloudfront_distribution.spa.id
}

output "function_name" {
  description = "For `aws logs tail /aws/lambda/<name> --follow`."
  value       = aws_lambda_function.app.function_name
}

output "image_uri" {
  description = "Exactly which image is deployed. The answer to 'is that the build I think it is'."
  value       = aws_lambda_function.app.image_uri
}

output "log_group" {
  description = "Where token cost and latency land."
  value       = aws_cloudwatch_log_group.app.name
}

output "published_artifacts" {
  description = "Corpus artifact objects this apply published to the record bucket."
  value       = sort([for o in aws_s3_object.artifact : "s3://${o.bucket}/${o.key}"])
}
