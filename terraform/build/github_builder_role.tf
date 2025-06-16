# In general, for use with the code under:
#
# * ci/
# * .github/workflows

locals {
  environments = [
    "development",
    "testing",
    "production",
  ]
}

data "aws_iam_policy_document" "github_cis_assume_role" {
  statement {
    sid = "AllowGitHubCis"
    principals {
      type = "Federated"
      identifiers = [
        aws_iam_openid_connect_provider.github_mozilla_iam_cis.arn,
      ]
    }
    actions = ["sts:AssumeRoleWithWebIdentity"]
    condition {
      test     = "StringEquals"
      variable = "token.actions.githubusercontent.com:aud"
      values   = ["sts.amazonaws.com"]
    }
    condition {
      test     = "ForAnyValue:StringLike"
      variable = "token.actions.githubusercontent.com:sub"
      values = [
        "repo:mozilla-iam/cis:ref:refs/heads/master",
        "repo:mozilla-iam/cis:ref:refs/tags/*",
      ]
    }
  }
}

data "aws_iam_policy_document" "cis_build_and_publish" {
  statement {
    sid = "AllowWriteLambdaLayer"
    actions = [
      "lambda:PublishLayerVersion",
    ]
    resources = [
      "arn:aws:lambda:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:layer:cis-*"
    ]
  }
  statement {
    sid     = "AllowWriteLatestLayerInSSM"
    actions = ["ssm:PutParameter"]
    resources = formatlist(
      "arn:aws:ssm:${data.aws_region.current.region}:${data.aws_caller_identity.current.account_id}:parameter/iam/cis/%s/build/lambda_layer_arn",
      local.environments
    )
  }
}

resource "aws_iam_policy" "cis_build_and_publish" {
  name        = "CISBuildAndPublish"
  description = "A minimal policy to allow a role/user to publish new CIS builds"
  policy      = data.aws_iam_policy_document.cis_build_and_publish.json
}

resource "aws_iam_role" "github_cis" {
  name               = "GitHubCIS"
  assume_role_policy = data.aws_iam_policy_document.github_cis_assume_role.json
}

resource "aws_iam_role_policy_attachment" "github_cis_build_and_publish" {
  role       = aws_iam_role.github_cis.name
  policy_arn = aws_iam_policy.cis_build_and_publish.arn
}
