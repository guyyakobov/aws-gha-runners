variable "project_name" {
  type = string
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

variable "enable_ecr_endpoints" {
  type    = bool
  default = false
}

variable "enable_sts_endpoint" {
  type    = bool
  default = false
}