# For current VPC allocations, see:
# https://mozilla-hub.atlassian.net/wiki/spaces/IAM/database/1695515017

locals {
  subnet_azs = {
    "us-west-2a" : 0,
    "us-west-2b" : 1,
    "us-west-2c" : 2,
  }
  public_subnet_azs = {
    "us-west-2a" : 0,
    "us-west-2b" : 1,
    "us-west-2c" : 2,
  }
}

resource "aws_vpc" "cis" {
  cidr_block                       = "10.1.0.0/16"
  assign_generated_ipv6_cidr_block = true
  enable_dns_hostnames             = true
  tags = {
    Name = "${var.environment}-cis"
  }
}

resource "aws_subnet" "public" {
  for_each                                       = local.public_subnet_azs
  vpc_id                                         = aws_vpc.cis.id
  availability_zone                              = each.key
  cidr_block                                     = cidrsubnet(aws_vpc.cis.cidr_block, 8, length(local.subnet_azs) + each.value)
  ipv6_cidr_block                                = cidrsubnet(aws_vpc.cis.ipv6_cidr_block, 8, length(local.subnet_azs) + each.value)
  assign_ipv6_address_on_creation                = true
  enable_resource_name_dns_aaaa_record_on_launch = true
  enable_resource_name_dns_a_record_on_launch    = true
  tags = {
    Name = "${var.environment}-public-${each.key}"
  }
}

resource "aws_default_route_table" "default" {
  default_route_table_id = aws_vpc.cis.default_route_table_id
  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.default.id
  }
  route {
    ipv6_cidr_block = "::/0"
    gateway_id      = aws_internet_gateway.default.id
  }
  tags = {
    Name = "${var.environment}-cis"
  }
}

resource "aws_egress_only_internet_gateway" "default" {
  vpc_id = aws_vpc.cis.id
  tags = {
    Name = "${var.environment}-cis"
  }
}

resource "aws_internet_gateway" "default" {
  vpc_id = aws_vpc.cis.id
}

resource "aws_eip" "nat" {
  for_each         = local.subnet_azs
  domain           = "vpc"
  public_ipv4_pool = "amazon"
  tags = {
    Name = "${var.environment}-cis-nat-${each.key}"
  }
}

resource "aws_nat_gateway" "cis" {
  for_each          = local.subnet_azs
  allocation_id     = aws_eip.nat[each.key].id
  subnet_id         = aws_subnet.public[each.key].id
  connectivity_type = "public"
  tags = {
    Name = "${var.environment}-cis-${each.key}"
  }
}

resource "aws_subnet" "private" {
  for_each                                       = local.subnet_azs
  vpc_id                                         = aws_vpc.cis.id
  availability_zone                              = each.key
  cidr_block                                     = cidrsubnet(aws_vpc.cis.cidr_block, 8, each.value)
  ipv6_cidr_block                                = cidrsubnet(aws_vpc.cis.ipv6_cidr_block, 8, each.value)
  assign_ipv6_address_on_creation                = true
  enable_resource_name_dns_aaaa_record_on_launch = true
  enable_resource_name_dns_a_record_on_launch    = true
  tags = {
    Name = "${var.environment}-${each.key}"
  }
}

output "private_subnets" {
  value = [for subnet in aws_subnet.private : subnet.id]
}

resource "aws_route_table" "private" {
  for_each = local.subnet_azs
  vpc_id   = aws_vpc.cis.id
  route {
    cidr_block     = "0.0.0.0/0"
    nat_gateway_id = aws_nat_gateway.cis[each.key].id
  }
  route {
    ipv6_cidr_block        = "::/0"
    egress_only_gateway_id = aws_egress_only_internet_gateway.default.id
  }
  tags = {
    Name = "${var.environment}-cis-${each.key}"
  }
}

resource "aws_route_table_association" "private" {
  for_each       = local.subnet_azs
  subnet_id      = aws_subnet.private[each.key].id
  route_table_id = aws_route_table.private[each.key].id
}

resource "aws_dax_subnet_group" "cis" {
  name       = "${var.environment}-id"
  subnet_ids = [for subnet in aws_subnet.private : subnet.id]
}

resource "aws_security_group" "dax" {
  name        = "dax"
  description = "Allow connections to and from AWS Dax."
  vpc_id      = aws_vpc.cis.id
  tags = {
    Name = "${var.environment}-dax"
  }
}

resource "aws_vpc_security_group_ingress_rule" "lambda_dax" {
  security_group_id            = aws_security_group.dax.id
  referenced_security_group_id = aws_security_group.lambda.id
  ip_protocol                  = -1
}

resource "aws_security_group" "lambda" {
  name        = "lambda"
  description = "Allow all connections."
  vpc_id      = aws_vpc.cis.id
  tags = {
    Name = "${var.environment}-cis-lambdas"
  }
}

output "lambda_security_group" {
  value = aws_security_group.lambda.id
}

resource "aws_vpc_security_group_ingress_rule" "lambda_all4" {
  security_group_id = aws_security_group.lambda.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = -1
}

resource "aws_vpc_security_group_ingress_rule" "lambda_all6" {
  security_group_id = aws_security_group.lambda.id
  cidr_ipv6         = "::/0"
  ip_protocol       = -1
}

resource "aws_vpc_security_group_egress_rule" "lambda_all4" {
  security_group_id = aws_security_group.lambda.id
  cidr_ipv4         = "0.0.0.0/0"
  ip_protocol       = -1
}

resource "aws_vpc_security_group_egress_rule" "lambda_all6" {
  security_group_id = aws_security_group.lambda.id
  cidr_ipv6         = "::/0"
  ip_protocol       = -1
}
