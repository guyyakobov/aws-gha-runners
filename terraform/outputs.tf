output "lambda_artifacts_bucket_name" {
  description = "Name of the S3 bucket used for Lambda deployment artifacts"
  value       = aws_s3_bucket.lambda_artifacts.bucket
}

output "webhook_url" {
  description = "Public URL to configure as the GitHub App webhook endpoint"
  value       = module.webhook.webhook_url
}
