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

  # Same disambiguator, different purpose. Kept distinct from the state bucket rather than sharing one
  # with prefixes: they have opposite retention rules — state history expires at 30 days, corpus
  # artifacts are kept indefinitely — and a single lifecycle configuration cannot express both without
  # a prefix filter that one careless edit would apply to the wrong half.
  artifacts_bucket = "${var.project}-artifacts-${local.account_id}"
}
