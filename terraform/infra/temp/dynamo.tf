resource "aws_dynamodb_table" "dynamo" {
  billing_mode                = "PAY_PER_REQUEST"
  deletion_protection_enabled = false
  hash_key                    = "id"
  name                        = "${var.environment}-identity-vault-2"
  region                      = "us-west-2"
  stream_enabled              = true
  stream_view_type            = "KEYS_ONLY"
  table_class                 = "STANDARD"


  attribute {
    name = "id"
    type = "S"
  }
  attribute {
    name = "primary_email"
    type = "S"
  }
  attribute {
    name = "primary_username"
    type = "S"
  }
  attribute {
    name = "sequence_number"
    type = "N"
  }
  attribute {
    name = "user_uuid"
    type = "S"
  }
  attribute {
    name = "connection_name"
    type = "S"
  }
  attribute {
    name = "cn_bucket"
    type = "S"
  }
  attribute {
    name = "active_bucket"
    type = "S"
  }
  attribute {
    name = "id_hash_bin"
    type = "B"
  }

  global_secondary_index {
    name            = "${var.environment}-identity-vault-cn-bucket"
    hash_key        = "cn_bucket"
    range_key       = "id_hash_bin"
    projection_type = "ALL"
  }
  global_secondary_index {
    name            = "${var.environment}-identity-vault-cn-bucket-active"
    hash_key        = "active_bucket"
    range_key       = "id_hash_bin"
    projection_type = "ALL"
  }
  global_secondary_index {
    hash_key           = "primary_email"
    name               = "${var.environment}-identity-vault-primary_email"
    non_key_attributes = []
    projection_type    = "ALL"
    range_key          = "id"
    read_capacity      = 0
    write_capacity     = 0
  }
  global_secondary_index {
    hash_key           = "primary_username"
    name               = "${var.environment}-identity-vault-primary_username"
    non_key_attributes = []
    projection_type    = "ALL"
    range_key          = "id"
    read_capacity      = 0
    write_capacity     = 0
  }
  global_secondary_index {
    hash_key           = "sequence_number"
    name               = "${var.environment}-identity-vault-sequence_number"
    non_key_attributes = []
    projection_type    = "ALL"
    read_capacity      = 0
    write_capacity     = 0
  }
  global_secondary_index {
    hash_key           = "user_uuid"
    name               = "${var.environment}-identity-vault-user_uuid"
    non_key_attributes = []
    projection_type    = "ALL"
    range_key          = "id"
    read_capacity      = 0
    write_capacity     = 0
  }
  global_secondary_index {
    hash_key           = "connection_name"
    name               = "${var.environment}-identity-vault-connection"
    non_key_attributes = []
    projection_type    = "ALL"
    range_key          = "id_hash_bin"
    read_capacity      = 0
    write_capacity     = 0
  }

  point_in_time_recovery {
    enabled                 = true
    recovery_period_in_days = 35
  }
  ttl {
    enabled        = false
  }
  tags = {
    application     = "identity-vault"
    cis_environment = "temp"
  }
}
