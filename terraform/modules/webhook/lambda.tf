data "archive_file" "webhook" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambdas/webhook"
  output_path = "${path.module}/../../../lambdas/webhook.zip"
}

resource "aws_lambda_function" "webhook" {
  function_name = "${var.project_name}-webhook"

  filename         = data.archive_file.webhook.output_path
  source_code_hash = data.archive_file.webhook.output_base64sha256
  architectures    = ["x86_64"]

  role    = aws_iam_role.webhook.arn
  handler = var.lambda_handler
  runtime = var.lambda_runtime

  timeout = var.lambda_timeout

  environment {
    variables = {
      PYTHONPATH                   = "/var/task/package:/var/runtime"
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
