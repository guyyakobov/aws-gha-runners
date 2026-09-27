resource "aws_sqs_queue" "jobs_dlq" {
  name                      = "${var.project_name}-jobs-dlq"
  message_retention_seconds = 1209600

  tags = {
    Name = "${var.project_name}-jobs-dlq"
  }
}

resource "aws_sqs_queue" "jobs" {
  name                      = "${var.project_name}-jobs"
  message_retention_seconds = 86400
  visibility_timeout_seconds = 180

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.jobs_dlq.arn
    maxReceiveCount     = 10
  })

  tags = {
    Name = "${var.project_name}-jobs"
  }
}