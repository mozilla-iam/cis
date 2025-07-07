resource "aws_iam_openid_connect_provider" "github_mozilla_iam_cis" {
  url            = "https://token.actions.githubusercontent.com"
  client_id_list = ["sts.amazonaws.com"]
}
