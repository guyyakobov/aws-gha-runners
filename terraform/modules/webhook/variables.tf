variable "project_name" {
  type = string
}

variable "sqs_queue_url" {
  type = string
}

variable "sqs_queue_arn" {
  type = string
}

variable "artifacts_bucket" {
  type = string
}

variable "webhook_artifact_key" {
  type = string
}

variable "webhook_secret_ssm_parameter" {
  type = string
}

variable "webhook_secret_ssm_parameter_arn" {
  type = string
}

variable "supported_flavors" {
  type = set(string)
}

variable "default_flavor" {
  type = string
}