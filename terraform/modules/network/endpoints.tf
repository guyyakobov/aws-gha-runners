resource "aws_vpc_endpoint" "ecr" {
  for_each = var.enable_ecr_endpoints ? local.ecr_interface_endpoints : {}

  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.${each.value}"
  vpc_endpoint_type = "Interface"

  subnet_ids = [
    for subnet in aws_subnet.private : subnet.id
  ]

  security_group_ids = [
    aws_security_group.vpc_endpoints.id
  ]

  private_dns_enabled = true

  tags = {
    Name = "${var.project_name}-ecr-${each.key}-vpce"
  }
}

resource "aws_vpc_endpoint" "s3" {
  count = var.enable_ecr_endpoints ? 1 : 0

  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.s3"
  vpc_endpoint_type = "Gateway"

  route_table_ids = [
    for route_table in aws_route_table.private : route_table.id
  ]

  tags = {
    Name = "${var.project_name}-s3-vpce"
  }
}

resource "aws_vpc_endpoint" "sts" {
  count = var.enable_sts_endpoint ? 1 : 0

  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${data.aws_region.current.region}.sts"
  vpc_endpoint_type = "Interface"

  subnet_ids = [
    for subnet in aws_subnet.private : subnet.id
  ]

  security_group_ids = [
    aws_security_group.vpc_endpoints.id
  ]

  private_dns_enabled = true

  tags = {
    Name = "${var.project_name}-sts-vpce"
  }
}
