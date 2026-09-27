variable "aws_region" {
  description = "AWS region used for the project"
  type        = string
}

variable "project_name" {
  description = "Name of the project"
  type        = string
  default     = "gha-runner"
}

variable "vpc_cidr_block" {
  type = string
}

variable "public_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
}

variable "private_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
}