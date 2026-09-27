resource "aws_nat_gateway" "public" {
  for_each = var.public_subnets

  allocation_id = aws_eip.nat[each.key].id
  subnet_id     = aws_subnet.public[each.key].id
  depends_on    = [aws_internet_gateway.main]

  tags = {
    Name = "${var.project_name}-public-${each.key}-nat"
  }
}

resource "aws_eip" "nat" {
  for_each = var.public_subnets

  domain = "vpc"

  tags = {
    Name = "${var.project_name}-public-${each.key}-nat-eip"
  }
}