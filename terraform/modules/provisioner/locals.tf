data "aws_region" "current" {}
data "aws_caller_identity" "current" {}


locals {
  github_private_key_ssm_parameter_arn = "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter${var.github_private_key_ssm_parameter}"

  jit_ssm_parameter_arn = "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter${var.jit_ssm_parameter_prefix}/*"
}
