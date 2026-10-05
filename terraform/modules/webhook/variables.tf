variable "project_name" {
  type        = string
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

variable "webhook_secret_ssm_parameter" {
  description = "SSM parameter path containing the webhook secret"
  type        = string

  validation {
    condition = (
      startswith(var.webhook_secret_ssm_parameter, "/") &&
      !endswith(var.webhook_secret_ssm_parameter, "/")
    )
    error_message = "webhook_secret_ssm_parameter must start with '/' and must not end with '/'"
  }
}

variable "supported_flavors" {
  description = "Runner flavor labels accepted from jobs"
  type        = set(string)

  validation {
    condition     = length(var.supported_flavors) > 0
    error_message = "supported_flavors must contain at least one flavor"
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

variable "lambda_timeout" {
  type        = number
  description = "Webhook Lambda timeout in seconds"

  validation {
    condition = (
      var.lambda_timeout >= 1 &&
      var.lambda_timeout <= 900 &&
      floor(var.lambda_timeout) == var.lambda_timeout
    )
    error_message = "lambda_timeout must be an integer from 1 through 900."
  }
}

variable "lambda_runtime" {
  type        = string
  description = "Runtime used by the webhook Lambda function"
  default     = "python3.12"
}

variable "lambda_handler" {
  type        = string
  description = "Handler used by the webhook Lambda function"
  default     = "main.lambda_handler"
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
  validation {
    condition = (
      var.waf_rate_limit >= 10 &&
      var.waf_rate_limit <= 2000000000 &&
      floor(var.waf_rate_limit) == var.waf_rate_limit
    )
    error_message = "waf_rate_limit must be an integer from 10 through 2000000000."
  }
}

variable "waf_evaluation_window_sec" {
  type        = number
  description = "Evaluation window in seconds for the WAF rate-based rule"
  default     = 300
  validation {
    condition     = contains([60, 120, 300, 600], var.waf_evaluation_window_sec)
    error_message = "waf_evaluation_window_sec must be 60, 120, 300, or 600"
  }
}
