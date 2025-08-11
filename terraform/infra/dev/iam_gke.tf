# Depends on ../common.

data "aws_region" "current" {}

# From: serverless-functions/profile_retrieval/serverless.yml
data "aws_iam_policy_document" "dynamo_read" {
  statement {
    sid = "AllowRead"
    actions = [
      "dynamodb:DescribeTable",
      "dynamodb:GetItem",
      "dynamodb:Query",
      "dynamodb:Scan",
    ]
    resources = [
      aws_dynamodb_table.dynamo.arn,
      "${aws_dynamodb_table.dynamo.arn}/*",
    ]
  }
}

resource "aws_iam_policy" "cis_dynamo_read" {
  name   = "CISDynamoRead"
  policy = data.aws_iam_policy_document.dynamo_read.json
}

module "cis_profile_retrieval_api" {
  source              = "github.com/mozilla/terraform-modules//aws_gke_oidc_role?ref=aws_gke_oidc_config-0.1.0"
  role_name           = "GKE${title(var.environment)}CISProfileRetrievalAPI"
  aws_region          = data.aws_region.current.region
  gcp_region          = var.gcp_region
  gke_cluster_name    = var.gke_cluster_name
  gcp_project_id      = var.gcp_project_id
  gke_namespace       = var.gke_namespace
  gke_service_account = "gha-cis-profile-retrieval-api"
  iam_policy_arns     = [aws_iam_policy.cis_dynamo_read.arn]
}
