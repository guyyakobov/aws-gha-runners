data "aws_caller_identity" "current" {}
data "aws_region" "current" {}

locals {
  jit_ssm_parameter_arn = "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter${var.jit_ssm_parameter_prefix}/*"
  ami_name_prefix       = var.ami_name_prefix != null ? var.ami_name_prefix : var.project_name
}
