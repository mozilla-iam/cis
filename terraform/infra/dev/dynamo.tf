resource "aws_dynamodb_table" "dynamo" {
  name                        = "${var.environment}-identity-vault"
  billing_mode                = "PAY_PER_REQUEST"
  deletion_protection_enabled = false
  hash_key                    = "id"
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
    type = "S"
  }
  attribute {
    name = "user_uuid"
    type = "S"
  }
  global_secondary_index {
    hash_key           = "primary_email"
    name               = "${var.environment}-identity-vault-primary_email"
    non_key_attributes = []
    projection_type    = "ALL"
    range_key          = "id"
  }
  global_secondary_index {
    hash_key           = "primary_username"
    name               = "${var.environment}-identity-vault-primary_username"
    non_key_attributes = []
    projection_type    = "ALL"
    range_key          = "id"
  }
  global_secondary_index {
    hash_key           = "sequence_number"
    name               = "${var.environment}-identity-vault-sequence_number"
    non_key_attributes = []
    projection_type    = "ALL"
    range_key          = null
  }
  global_secondary_index {
    hash_key           = "user_uuid"
    name               = "${var.environment}-identity-vault-user_uuid"
    non_key_attributes = []
    projection_type    = "ALL"
    range_key          = "id"
  }
  point_in_time_recovery {
    enabled = false
  }
  ttl {
    enabled = false
  }
  tags = {
    application     = "identity-vault"
    cis_environment = "development"
  }
}
