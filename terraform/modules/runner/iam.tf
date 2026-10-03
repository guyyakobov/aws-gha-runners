resource "aws_iam_role" "runner" {
  name = "${var.project_name}-runner-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [{
      Effect = "Allow"

      Principal = {
        Service = "ec2.amazonaws.com"
      }

      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name = "${var.project_name}-runner-role"
  }
}

data "aws_iam_policy_document" "runner" {
  statement {
    effect = "Allow"

    actions = [
      "ssm:GetParameter",
      "ssm:DeleteParameter"
    ]

    resources = [
      local.jit_ssm_parameter_arn
    ]
  }
}

resource "aws_iam_role_policy" "runner" {
  name   = "${var.project_name}-runner-policy"
  role   = aws_iam_role.runner.id
  policy = data.aws_iam_policy_document.runner.json
}

resource "aws_iam_instance_profile" "runner" {
  name = "${var.project_name}-runner"
  role = aws_iam_role.runner.name
}
