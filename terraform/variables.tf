variable "aws_region" {
  type        = string
  description = "AWS region in which to deploy the project"
}

variable "project_name" {
  type        = string
  description = "Name prefix used across project resources"
  default     = "gha-runners"
}

variable "vpc_cidr_block" {
  type        = string
  description = "IPv4 CIDR block for the project VPC"
}

variable "public_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
  description = "Public subnets used for NAT gateways"
}

variable "private_subnets" {
  description = "Private subnets paired with public subnets by key and availability zone"
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
}

variable "enable_ecr_endpoints" {
  type        = bool
  description = "Whether to create private ECR and S3 endpoints to reduce traffic through NAT gateways"
  default     = false
}

variable "enable_sts_endpoint" {
  type        = bool
  description = "Whether to create a private STS interface endpoint to reduce traffic through NAT gateways"
  default     = false
}

variable "webhook_lambda_timeout" {
  type        = number
  description = "Webhook Lambda timeout in seconds"
  default     = 10
}

variable "webhook_artifact_key" {
  type        = string
  description = "S3 object key for the webhook Lambda deployment package"
}

variable "provisioner_artifact_key" {
  type        = string
  description = "S3 object key for the provisioner Lambda deployment package"
}

variable "webhook_secret_ssm_parameter" {
  type        = string
  description = "SSM parameter path containing the webhook secret"
}

variable "github_private_key_ssm_parameter" {
  type        = string
  description = "SSM parameter path containing the GitHub App private key"
}

variable "github_app_id" {
  type        = string
  description = "GitHub App ID used by the provisioner"
}

variable "github_runner_group_id" {
  type        = number
  description = "GitHub Actions runner group ID assigned to provisioned runners"
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
}

variable "jit_ssm_parameter_prefix" {
  type        = string
  description = "SSM parameter path prefix for runner JIT configurations"

}

variable "runner_ami_name_prefix" {
  type        = string
  description = "Optional runner AMI name prefix. defaults to project_name"
  default     = null
}

variable "provisioner_lambda_timeout" {
  type        = number
  description = "Provisioner Lambda timeout in seconds; the jobs queue visibility timeout is six times this value"
  default     = 30
}

variable "enable_waf" {
  type        = bool
  description = "Whether to enable per-IP rate limiting for the webhook API through WAF"
  default     = false
}

variable "waf_rate_limit" {
  type        = number
  description = "Request threshold per source IP within the AWS WAF evaluation window"
  default     = 1000
}

variable "waf_evaluation_window_sec" {
  type        = number
  description = "Evaluation window in seconds for the WAF rate-based rule"
  default     = 300
}