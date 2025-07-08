# Locked with:
# terraform providers lock -platform darwin_amd64 -platform darwin_arm64 -platform linux_amd64 -platform linux_arm64
terraform {
  required_version = ">= 1.5.0"
  backend "s3" {
    # Re-using the one from mozilla-iam/iam-infra, to save having multiple
    # places to audit.
    bucket = "eks-terraform-shared-state"
    key    = "cis/terraform/build/terraform.tfstate"
    region = "us-west-2"
  }
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region = "us-west-2"
  default_tags {
    tags = {
      Component      = "CIS"
      FunctionalArea = "SSO"
      Owner          = "IAM"
      Repository     = "github.com/mozilla-iam/cis"
    }
  }
}
