data "archive_file" "provisioner" {
  type        = "zip"
  source_dir  = "${path.module}/../../../lambdas/provisioner"
  output_path = "${path.module}/../../../lambdas/provisioner.zip"
}

resource "aws_lambda_function" "provisioner" {
  function_name = "${var.project_name}-provisioner"

  filename         = data.archive_file.provisioner.output_path
  source_code_hash = data.archive_file.provisioner.output_base64sha256
  architectures    = ["x86_64"]

  role    = aws_iam_role.provisioner.arn
  handler = var.lambda_handler
  runtime = var.lambda_runtime

  timeout                        = var.lambda_timeout
  reserved_concurrent_executions = 1

  environment {
    variables = {
      PYTHONPATH                       = "/var/task/package:/var/runtime"
      GITHUB_APP_ID                    = var.github_app_id
      GITHUB_PRIVATE_KEY_SSM_PARAMETER = var.github_private_key_ssm_parameter
      GITHUB_RUNNER_GROUP_ID           = tostring(var.github_runner_group_id)

      RUNNER_LAUNCH_TEMPLATE_ID      = var.runner_launch_template_id
      RUNNER_LAUNCH_TEMPLATE_VERSION = var.runner_launch_template_version
      RUNNER_SUBNET_IDS              = join(",", var.runner_subnet_ids)

      GENERAL_INSTANCE_TYPE = var.general_instance_type
      HEAVY_INSTANCE_TYPE   = var.heavy_instance_type
      MAX_RUNNERS           = tostring(var.max_runners)

      JIT_SSM_PARAMETER_PREFIX = var.jit_ssm_parameter_prefix
    }
  }

  depends_on = [
    aws_cloudwatch_log_group.provisioner,
    aws_iam_role_policy.provisioner
  ]

  tags = {
    Name = "${var.project_name}-provisioner"
  }
}

resource "aws_cloudwatch_log_group" "provisioner" {
  name              = "/aws/lambda/${var.project_name}-provisioner"
  retention_in_days = 14

  tags = {
    Name = "${var.project_name}-provisioner-logs"
  }
}
