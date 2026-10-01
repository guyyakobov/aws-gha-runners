resource "aws_security_group" "runner" {
  name        = "${var.project_name}-runner"
  description = "Security group for GitHub Actions runners"
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.project_name}-runner"
  }
}

resource "aws_vpc_security_group_egress_rule" "runner" {
  security_group_id = aws_security_group.runner.id

  ip_protocol = "-1"
  cidr_ipv4   = "0.0.0.0/0"
}'יש