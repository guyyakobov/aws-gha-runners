variable "aws_region" {
  type        = string
  description = "AWS region used to build the runner AMI"
  default     = "us-east-1"
}

variable "vpc_id" {
  type        = string
  description = "VPC used by the temporary Packer builder"
}

variable "subnet_id" {
  type        = string
  description = "Public subnet used by the temporary Packer builder"
}

variable "builder_instance_type" {
  type        = string
  description = "EC2 instance type used to build the AMI"
  default     = "t3.small"
}

variable "ami_name_prefix" {
  type        = string
  description = "Prefix for GitHub Actions runner AMIs"
  default     = "github-runner"
}