resource "aws_iam_role" "provisioner" {
  name = "${var.project_name}-provisioner-role"

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
    Name = "${var.project_name}-provisioner-role"
  }
}

data "aws_iam_policy_document" "provisioner" {
  statement {
    effect = "Allow"

    actions = [
      "sqs:ReceiveMessage",
      "sqs:DeleteMessage",
      "sqs:GetQueueAttributes"
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
      local.github_private_key_ssm_parameter_arn
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "ssm:GetParameter",
      "ssm:PutParameter",
      "ssm:DeleteParameter"
    ]

    resources = [
      local.jit_ssm_parameter_arn
    ]
  }

  statement {
    effect = "Allow"

    actions = [
      "ec2:DescribeInstances",
      "ec2:CreateFleet",
      "ec2:RunInstances",
      "ec2:CreateTags"
    ]

    resources = ["*"]
  }

  statement {
    effect = "Allow"

    actions = [
      "iam:PassRole"
    ]

    resources = [
      var.runner_role_arn
    ]

    condition {
      test     = "StringEquals"
      variable = "iam:PassedToService"
      values   = ["ec2.amazonaws.com"]
    }
  }

  statement {
    effect = "Allow"

    actions = [
      "logs:CreateLogStream",
      "logs:PutLogEvents"
    ]

    resources = [
      "${aws_cloudwatch_log_group.provisioner.arn}:*"
    ]
  }
}

resource "aws_iam_role_policy" "provisioner" {
  name = "${var.project_name}-provisioner-policy"
  role = aws_iam_role.provisioner.id

  policy = data.aws_iam_policy_document.provisioner.json
}
