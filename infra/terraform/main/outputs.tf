output "function_url" {
  description = "The public endpoint. `curl -N \"$(terraform output -raw function_url)lineage?q=thrash%20metal\"`."
  value       = aws_lambda_function_url.app.function_url
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
