variable "project_name" {
  type        = string
  description = "Name prefix used for network resources"
}

variable "vpc_cidr_block" {
  type        = string
  description = "IPv4 CIDR block for the VPC"
}

variable "public_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
  description = "Public subnets used to host NAT gateways"
}

variable "private_subnets" {
  type = map(object({
    cidr_block        = string
    availability_zone = string
  }))
  validation {
    condition = alltrue([
      for key, subnet in var.private_subnets :
      contains(keys(var.public_subnets), key) &&
      var.public_subnets[key].availability_zone == subnet.availability_zone
    ])

    error_message = "Each private subnet must have a matching public subnet in the same AZ"
  }
  description = "Private subnets paired with public subnets by key and availability zone"
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

variable "vpc_endpoint_allowed_security_group_ids" {
  type        = map(string)
  description = "Security group IDs allowed to reach interface endpoints over HTTPS, keyed by a stable caller-defined label"
  default     = {}
}
