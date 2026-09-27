resource "aws_lambda_function" "webhook" {
  function_name = "${var.project_name}-webhook"

  s3_bucket = var.artifacts_bucket
  s3_key    = var.webhook_artifact_key

  role    = aws_iam_role.webhook.arn
  handler = "lambdas.webhook.main.lambda_handler"
  runtime = "python3.12"

  environment {
    variables = {
      SQS_QUEUE_URL                = var.sqs_queue_url
      WEBHOOK_SECRET_SSM_PARAMETER = var.webhook_secret_ssm_parameter
      SUPPORTED_FLAVORS            = join(",", var.supported_flavors)
      DEFAULT_FLAVOR               = var.default_flavor
    }
  }

  tags = {
    Name = "${var.project_name}-webhook"
  }
}