terraform {
  required_version = ">= 1.10"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.57"
    }
  }

  # No backend block: bootstrap uses LOCAL state, deliberately.
  #
  # This root exists to break a chicken-and-egg. It creates the S3 bucket that holds `main/`'s state,
  # the ECR repository that must contain an image before a Lambda can reference one, and the OIDC
  # role that CI has to assume before it can run Terraform at all. None of those can be created by a
  # configuration that already depends on them.
  #
  # The state file is gitignored and lives on one machine. That is an accepted risk rather than an
  # oversight: this root holds a handful of resources with stable, predictable names, so losing the
  # state costs a few `terraform import` commands, not a rebuild. If you would rather not carry even
  # that risk, see "Migrating bootstrap state" in infra/README.md — the bucket this root creates can
  # hold its own state once it exists.
}
