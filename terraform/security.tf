resource "aws_vpc_security_group_ingress_rule" "runner_to_vpc_endpoints" {
  security_group_id            = module.network.vpc_endpoints_security_group_id
  referenced_security_group_id = module.runner.security_group_id

  description = "Allow HTTPS from GitHub Actions runners"
  from_port   = 443
  to_port     = 443
  ip_protocol = "tcp"
}