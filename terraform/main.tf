module "network" {
  source = "./modules/network"

  project_name         = var.project_name
  vpc_cidr_block       = var.vpc_cidr_block
  public_subnets       = var.public_subnets
  private_subnets      = var.private_subnets
  enable_ecr_endpoints = var.enable_ecr_endpoints
  enable_sts_endpoint  = var.enable_sts_endpoint

  vpc_endpoint_allowed_security_group_ids = {
    runner = module.runner.security_group_id
  }
}

module "runner" {
  source = "./modules/runner"

  project_name         = var.project_name
  vpc_id               = module.network.vpc_id
  ami_name_prefix      = var.runner_ami_name_prefix
  jit_ssm_parameter_prefix = var.jit_ssm_parameter_prefix
}

module "webhook" {
  source = "./modules/webhook"

  project_name                 = var.project_name
  artifacts_bucket_name        = aws_s3_bucket.lambda_artifacts.bucket
  webhook_artifact_key         = var.webhook_artifact_key
  webhook_secret_ssm_parameter = var.webhook_secret_ssm_parameter
  sqs_queue_url                = aws_sqs_queue.jobs.url
  sqs_queue_arn                = aws_sqs_queue.jobs.arn
  supported_flavors            = local.supported_flavors
  default_flavor               = local.default_flavor

  enable_waf     = var.enable_waf
  waf_rate_limit = var.waf_rate_limit
}

module "provisioner" {
  source = "./modules/provisioner"

  project_name             = var.project_name
  artifacts_bucket_name    = aws_s3_bucket.lambda_artifacts.bucket
  provisioner_artifact_key = var.provisioner_artifact_key
  sqs_queue_arn            = aws_sqs_queue.jobs.arn
  lambda_timeout           = var.provisioner_lambda_timeout

  github_app_id                    = var.github_app_id
  github_private_key_ssm_parameter = var.github_private_key_ssm_parameter
  github_runner_group_id           = var.github_runner_group_id

  runner_role_arn                = module.runner.role_arn
  runner_launch_template_id      = module.runner.launch_template_id
  runner_launch_template_version = tostring(module.runner.launch_template_version)
  runner_subnet_ids              = module.network.private_subnet_ids

  general_instance_type = var.general_instance_type
  heavy_instance_type   = var.heavy_instance_type
  max_runners           = var.max_runners

  jit_ssm_parameter_prefix = var.jit_ssm_parameter_prefix
}
