variable "dax_replicas" {
  type    = number
  default = 1
}

data "aws_dynamodb_table" "identity_vault" {
  name = "${var.environment}-identity-vault"
}

data "aws_iam_policy_document" "cis_read_access" {
  statement {
    actions = [
      "dynamodb:BatchGetItem",
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = [
      "${data.aws_dynamodb_table.identity_vault.arn}",
      "${data.aws_dynamodb_table.identity_vault.arn}/*",
    ]
  }
}

resource "aws_iam_policy" "dax_cis_read_access" {
  name   = "AWSDaxCISReadAccess"
  policy = data.aws_iam_policy_document.cis_read_access.json
}

resource "aws_iam_role" "dax_cis" {
  name = "AWSDaxCIS"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "DaxAssumeRole"
      Action = "sts:AssumeRole"
      Effect = "Allow"
      Principal = {
        Service = "dax.amazonaws.com"
      }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "dax_cis_read" {
  role       = aws_iam_role.dax_cis.name
  policy_arn = aws_iam_policy.dax_cis_read_access.arn
}

resource "aws_dax_parameter_group" "cache" {
  name        = "cis-cache"
  description = "DAX parameter group. Generally for caching Scan operations."
  # Cache query/scan results for 2 hours -- the same amount of time we keep our
  # S3 cache around for.
  parameters {
    name  = "query-ttl-millis"
    value = "7200000"
  }
  # DANGER: We really shouldn't be using this unless we support cache
  # write-through.
  #
  # I'm (bhee) justifying it for scan results, since that's _existing_
  # behaviour (S3 cache). I'm unsure what the behaviour of returning
  # potentially stale user profiles will be.
  parameters {
    name  = "record-ttl-millis"
    value = "30000"
  }
}

resource "aws_dax_cluster" "cache" {
  # Max length: 20 characters
  cluster_name         = "${var.environment}-id"
  parameter_group_name = aws_dax_parameter_group.cache.name
  # The cheapest available that would comfortably fit a large chunk of our
  # dataset in memory.
  node_type = "dax.r7i.large"
  # For development, let's just use the one.
  replication_factor = var.dax_replicas
  iam_role_arn       = aws_iam_role.dax_cis.arn
  # 1AM - 3AM (UTC); 6PM - 8PM PDT; 9PM - 11PM EDT.
  maintenance_window               = "sat:01:00-sat:03:00"
  cluster_endpoint_encryption_type = "TLS"
  availability_zones               = slice(keys(local.subnet_azs), 0, var.dax_replicas)
  subnet_group_name                = aws_dax_subnet_group.cis.name
  security_group_ids               = [aws_security_group.dax.id]
  server_side_encryption {
    enabled = true
  }
}
