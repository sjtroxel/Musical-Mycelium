# The registry the Lambda image is pushed to.
#
# This lives in bootstrap rather than main for a structural reason, not a stylistic one: a Lambda
# function with package_type = "IMAGE" cannot be created until an image already exists at the URI it
# names. That is the two-stage apply that docs/streaming-verification.md flagged. Putting ECR here
# turns the ordering into a property of the directory layout instead of a `-target` incantation
# somebody has to remember at 2am.

resource "aws_ecr_repository" "app" {
  name = var.project

  # MUTABLE because CI pushes both an immutable :<git-sha> tag and a moving :latest. The sha tag is
  # what the Lambda actually deploys, so rollback is "point at the previous sha", not "hope :latest
  # still means what it meant".
  image_tag_mutability = "MUTABLE"

  # Basic scanning is free. There is no reason to opt out of being told about a CVE in the base image.
  image_scanning_configuration {
    scan_on_push = true
  }

  # Same reasoning as force_destroy on the state bucket: a repository holding images will not delete
  # without it, and invariant 5 requires destroy to actually work.
  force_delete = true
}

resource "aws_ecr_lifecycle_policy" "app" {
  repository = aws_ecr_repository.app.name

  # Rules are evaluated in ascending rulePriority and the FIRST match wins, so the untagged rule must
  # come first: an image that has been superseded loses its tag before it is old enough for rule 2.
  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after a day; they are build litter."
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the most recent ${var.keep_image_count} tagged images."
        selection = {
          tagStatus      = "tagged"
          tagPatternList = ["*"]
          countType      = "imageCountMoreThan"
          countNumber    = var.keep_image_count
        }
        action = { type = "expire" }
      },
    ]
  })
}
