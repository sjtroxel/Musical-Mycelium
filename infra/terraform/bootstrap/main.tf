provider "aws" {
  region = var.region

  # Every resource this project creates is tagged, so a cost report can answer "what is Musical
  # Mycelium costing me" without guessing from resource names. On an account that will hold more than
  # one portfolio project, that is the difference between a readable bill and an unreadable one.
  default_tags {
    tags = {
      Project   = var.project
      ManagedBy = "terraform"
      Root      = "bootstrap"
    }
  }
}

data "aws_caller_identity" "current" {}

locals {
  account_id = data.aws_caller_identity.current.account_id

  # Bucket names are globally unique across all of AWS, so the account id is the disambiguator that
  # does not require inventing one.
  state_bucket = "${var.project}-tfstate-${local.account_id}"
}
