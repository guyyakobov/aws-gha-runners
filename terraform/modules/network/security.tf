resource "aws_security_group" "vpc_endpoints" {
  name        = "${var.project_name}-vpce-sg"
  description = "Security group for VPC interface endpoints"
  vpc_id      = aws_vpc.main.id

  tags = {
    Name = "${var.project_name}-vpce-sg"
  }
}

resource "aws_vpc_security_group_ingress_rule" "vpc_endpoints_https" {
  for_each = var.vpc_endpoint_allowed_security_group_ids

  security_group_id            = aws_security_group.vpc_endpoints.id
  referenced_security_group_id = each.value

  description = "Allow HTTPS from ${each.key}"
  from_port   = 443
  to_port     = 443
  ip_protocol = "tcp"
}
