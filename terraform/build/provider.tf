# DEBT(bhee): There's now a _bunch_ of different places we have Terraform.
# There's been _some_ effort to centralize where, but I'm making an explicit
# call to keep CIS-related things in the CIS repository.
#
# This almost follows the pattern from dino park, except we also have
# mozilla-iam/iam-infra.
#
# There is no right decision here, only less wrong; and this is the one I made.


# Locked with:
# terraform providers lock -platform darwin_amd64 -platform darwin_arm64 -platform linux_amd64 -platform linux_arm64
terraform {
  required_version = ">= 1.5.0"
  backend "s3" {
    # Re-using the one from mozilla-iam/iam-infra, to save having multiple
    # places to audit.
    bucket = "eks-terraform-shared-state"
    key    = "cis/terraform/terraform.tfstate"
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
