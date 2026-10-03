variable "project_name" {
  type        = string
  description = "Name prefix used for runner resources"
}

variable "vpc_id" {
  type        = string
  description = "ID of the VPC in which runner resources are created"
}

variable "ami_name_prefix" {
  description = "Name prefix used to select the most recent runner AMI"
  type        = string
  default     = null
}

variable "jit_ssm_parameter_prefix" {
  description = "SSM parameter path prefix for runner JIT configurations"
  type        = string

  validation {
    condition = (
      startswith(var.jit_ssm_parameter_prefix, "/") &&
      !endswith(var.jit_ssm_parameter_prefix, "/")
    )
    error_message = "jit_ssm_parameter_prefix must start with '/' and must not end with '/'."
  }
}