variable "project_name" {
  type = string
  description = "Name prefix used for provisioner resources"
}

variable "artifacts_bucket_name" {
  type        = string
  description = "Name of the S3 bucket containing the provisioner deployment package"
}

variable "provisioner_artifact_key" {
  type        = string
  description = "S3 object key for the provisioner Lambda deployment package"
}

variable "sqs_queue_arn" {
  type        = string
  description = "ARN of the jobs queue consumed by the provisioner"
}

variable "lambda_timeout" {
  type        = number
  description = "Provisioner Lambda timeout in seconds"
  validation {
    condition = (
      var.lambda_timeout >= 1 &&
      var.lambda_timeout <= 900 &&
      floor(var.lambda_timeout) == var.lambda_timeout
    )
    error_message = "lambda_timeout must be an integer from 1 through 900"
  }
}

variable "lambda_runtime" {
  type    = string
  default = "python3.12"
}

variable "lambda_handler" {
  type    = string
  default = "lambdas.provisioner.main.lambda_handler"
}

variable "github_app_id" {
  type        = string
  description = "GitHub App ID used by the provisioner"

  validation {
    condition     = can(regex("^[1-9][0-9]*$", var.github_app_id))
    error_message = "github_app_id must be a positive numeric ID."
  }
}

variable "github_private_key_ssm_parameter" {
  type        = string
  description = "SSM parameter path containing the GitHub App private key"
  validation {
    condition = (
      startswith(var.github_private_key_ssm_parameter, "/") &&
      !endswith(var.github_private_key_ssm_parameter, "/")
    )
    error_message = "github_private_key_ssm_parameter must start with '/' and must not end with '/'"
  }
}

variable "github_runner_group_id" {
  type = number
  description = "GitHub Actions runner group ID assigned to provisioned runners"
  validation {
    condition     = var.github_runner_group_id > 0 && floor(var.github_runner_group_id) == var.github_runner_group_id
    error_message = "github_runner_group_id must be a positive integer."
  }
}

variable "runner_role_arn" {
  type = string
  description = "IAM role ARN used by provisioned runner instances"
}

variable "runner_launch_template_id" {
  type = string
  description = "ID of the launch template used to create runner instances"
}

variable "runner_launch_template_version" {
  type = string
  description = "Launch template version used to create runner instances"
}

variable "runner_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs available for runner placement"
  validation {
    condition     = length(var.runner_subnet_ids) > 0
    error_message = "runner_subnet_ids must contain at least one subnet"
  }
}

variable "general_instance_type" {
  type        = string
  description = "EC2 instance type used for general runner jobs"
}

variable "heavy_instance_type" {
  type        = string
  description = "EC2 instance type used for heavy runner jobs"
}

variable "max_runners" {
  type        = number
  description = "Maximum number of pending and running runner instances"
  validation {
    condition     = var.max_runners > 0 && floor(var.max_runners) == var.max_runners
    error_message = "max_runners must be a positive integer"
  }
}

variable "jit_ssm_parameter_prefix" {
  type        = string
  description = "SSM parameter path prefix for runner JIT configurations"
  validation {
    condition     = (startswith(var.jit_ssm_parameter_prefix, "/") && !endswith(var.jit_ssm_parameter_prefix, "/"))
    error_message = "jit_ssm_parameter_prefix must start with '/' and must not end with '/'."
  }
}
