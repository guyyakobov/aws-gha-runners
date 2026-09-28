resource "aws_iam_role" "webhook" {
  name = "${var.project_name}-webhook-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.project_name}-webhook-role"
  }
}

data "aws_iam_policy_document" "webhook" {
  statement {
    effect = "Allow"

    actions = [
      "sqs:SendMessage"
    ]

    resources = [
      var.sqs_queue_arn
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "ssm:GetParameter"
    ]

    resources = [
      data.aws_ssm_parameter.webhook_secret.arn
    ]

  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = [
      "${aws_cloudwatch_log_group.webhook.arn}:*"
    ]
  }
}

resource "aws_iam_role_policy" "webhook" {
  name = "${var.project_name}-webhook-policy"
  role = aws_iam_role.webhook.id

  policy = data.aws_iam_policy_document.webhook.json
}

data "aws_ssm_parameter" "webhook_secret" {
  name = var.webhook_secret_ssm_parameter
}

