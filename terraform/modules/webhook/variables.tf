variable "project_name" {
  type = string
  description = "Name prefix used for webhook resources"
}

variable "sqs_queue_url" {
  type        = string
  description = "URL of the jobs queue that receives accepted webhook events"
}

variable "sqs_queue_arn" {
  type        = string
  description = "ARN of the jobs queue that receives accepted webhook events"
}

variable "artifacts_bucket_name" {
  type        = string
  description = "Name of the S3 bucket containing the webhook deployment package"
}

variable "webhook_artifact_key" {
  type        = string
  description = "S3 object key for the webhook Lambda deployment package"
}

variable "webhook_secret_ssm_parameter" {
  description = "SSM parameter path containing the webhook secret"
  type        = string

  validation {
    condition = (
      startswith(var.webhook_secret_ssm_parameter, "/") &&
      !endswith(var.webhook_secret_ssm_parameter, "/")
    )
    error_message = "webhook_secret_ssm_parameter must start with '/' and must not end with '/'."
  }
}

variable "supported_flavors" {
  description = "Runner flavor labels accepted from jobs"
  type        = set(string)

  validation {
    condition     = length(var.supported_flavors) > 0
    error_message = "supported_flavors must contain at least one flavor."
  }
}

variable "default_flavor" {
  description = "Runner flavor used when an accepted job has no explicit supported flavor"
  type        = string

  validation {
    condition     = contains(var.supported_flavors, var.default_flavor)
    error_message = "default_flavor must be included in supported_flavors"
  }
}

variable "lambda_runtime" {
  type    = string
  description = "Runtime used by the webhook Lambda function"
  default = "python3.12"
}

variable "lambda_handler" {
  type    = string
  description = "Handler used by the webhook Lambda function"
  default = "lambdas.webhook.main.lambda_handler"
}

variable "enable_waf" {
  type        = bool
  description = "Whether to enable WAF protection for the webhook API"
  default     = false
}

variable "waf_rate_limit" {
  type        = number
  description = "Request rate threshold per source IP for the WAF rate-based rule"
  default     = 1000
}
