resource "aws_lambda_event_source_mapping" "jobs" {
  event_source_arn = var.sqs_queue_arn
  function_name    = aws_lambda_function.provisioner.arn

  batch_size = 1
  enabled    = true

  depends_on = [
    aws_iam_role_policy.provisioner
  ]
}