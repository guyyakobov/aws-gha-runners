resource "aws_lambda_function" "provisioner" {
  function_name = "${var.project_name}-provisioner"

  s3_bucket = var.artifacts_bucket
  s3_key    = var.provisioner_artifact_key

  role    = aws_iam_role.provisioner.arn
  handler = var.lambda_handler
  runtime = var.lambda_runtime

  timeout                        = var.lambda_timeout
  reserved_concurrent_executions = 1

  environment {
    variables = {
      GITHUB_APP_ID                  = var.github_app_id
      GITHUB_PRIVATE_KEY_PARAMETER   = var.github_private_key_parameter
      GITHUB_RUNNER_GROUP_ID         = var.github_runner_group_id

      RUNNER_LAUNCH_TEMPLATE_ID      = var.runner_launch_template_id
      RUNNER_LAUNCH_TEMPLATE_VERSION = var.runner_launch_template_version
      RUNNER_SUBNET_IDS              = join(",", var.runner_subnet_ids)

      GENERAL_INSTANCE_TYPE          = var.general_instance_type
      HEAVY_INSTANCE_TYPE            = var.heavy_instance_type
      MAX_RUNNERS                    = tostring(var.max_runners)

      JIT_PARAMETER_PREFIX           = var.jit_parameter_prefix
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