resource "aws_lambda_function" "webhook" {
  function_name = "${var.project_name}-webhook"

  s3_bucket = var.artifacts_bucket
  s3_key    = var.webhook_artifact_key

  role    = aws_iam_role.webhook.arn
  handler = var.lambda_handler
  runtime = var.lambda_runtime

  environment {
    variables = {
      SQS_QUEUE_URL                = var.sqs_queue_url
      WEBHOOK_SECRET_SSM_PARAMETER = var.webhook_secret_ssm_parameter
      SUPPORTED_FLAVORS            = join(",", var.supported_flavors)
      DEFAULT_FLAVOR               = var.default_flavor
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.webhook,
    aws_iam_role_policy.webhook
  ]
  
  tags = {
    Name = "${var.project_name}-webhook"
  }
} 

resource "aws_cloudwatch_log_group" "webhook" {
  name              = "/aws/lambda/${var.project_name}-webhook"
  retention_in_days = 14

  tags = {
    Name = "${var.project_name}-webhook-logs"
  }
}