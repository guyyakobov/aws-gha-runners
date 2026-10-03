data "aws_region" "current" {}

locals {
  ecr_interface_endpoints = {
    api = "ecr.api"
    dkr = "ecr.dkr"
  }
}