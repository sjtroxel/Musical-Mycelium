terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.57"
    }
  }

  backend "s3" {
    # PARTIAL CONFIGURATION on purpose. `bucket` is deliberately absent.
    #
    # The bucket name contains the AWS account id (bootstrap/main.tf), backend blocks cannot
    # interpolate variables, and hardcoding an account id into a public repository is a small,
    # permanent, avoidable disclosure. So it is supplied at init time:
    #
    #   terraform -chdir=infra/terraform/main init -backend-config=bucket=<state_bucket>
    #
    # `make tf-init` reads the bucket from bootstrap's outputs and does this for you; the deploy
    # workflow resolves it from sts:GetCallerIdentity.
    key    = "musical-mycelium/main.tfstate"
    region = "us-east-1"

    encrypt = true

    # S3 native locking, added in Terraform 1.10. The old answer was a DynamoDB table purely to hold
    # a lock row — a second always-on-shaped resource to protect a solo project's state. This uses a
    # lock object in the same bucket, which costs nothing and deletes the whole DynamoDB line item.
    use_lockfile = true
  }
}
