# Musical Mycelium — the single entry point for every routine task.
# `make help` lists targets. `make check` is what CI runs.

.DEFAULT_GOAL := help
.PHONY: help install fmt lint typecheck test cov check root-check clean dev ingest \
        image image-run tf-fmt tf-validate tf-bootstrap tf-init tf-plan tf-apply tf-destroy image-push

UV := $(shell command -v uv 2>/dev/null)

# --- deployment settings -----------------------------------------------------
# Every value here is also a Terraform variable default. They are repeated rather than read out of
# Terraform because these targets have to work before any state exists.
PROJECT   := musical-mycelium
AWS_REGION := us-east-1
IMAGE     := $(PROJECT):local
BOOTSTRAP := infra/terraform/bootstrap
TF_MAIN   := infra/terraform/main

help: ## List available targets
	@grep -hE '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[1m%-12s\033[0m %s\n", $$1, $$2}'

install: ## Create the venv and install all dependencies (installs Python 3.13 if needed)
ifndef UV
	@echo "uv is not installed. Install it with:"
	@echo "  curl -LsSf https://astral.sh/uv/install.sh | sh"
	@echo "Then re-run 'make install'. uv provisions Python 3.13 itself."
	@exit 1
endif
	uv sync

fmt: ## Format the code
	uv run ruff format src tests
	uv run ruff check --fix src tests

lint: ## Check formatting and lint without modifying anything
	uv run ruff format --check src tests
	uv run ruff check src tests

typecheck: ## Run mypy
	uv run mypy

test: ## Run the test suite
	uv run pytest

cov: ## Run the test suite with a coverage report
	uv run pytest --cov --cov-report=term-missing

# Counts tracked AND untracked-but-not-ignored paths, so the cap is enforced before a commit
# rather than only after one.
root-check: ## Fail if the repo root has grown past its cap (see CLAUDE.md)
	@files=$$(git ls-files --cached --others --exclude-standard); \
	count=$$(echo "$$files" | awk -F/ 'NF==1' | wc -l); \
	dirs=$$(echo "$$files" | awk -F/ 'NF>1 {print $$1}' | sort -u | wc -l); \
	total=$$((count + dirs)); \
	echo "repo root: $$count files + $$dirs dirs = $$total entries (cap 18)"; \
	if [ $$total -gt 18 ]; then \
		echo "Root has grown past the cap. Can it live in infra/, docs/, web/, or pyproject.toml?"; \
		exit 1; \
	fi

check: lint typecheck test root-check tf-validate ## Everything CI runs

# --- deployment --------------------------------------------------------------
# These wrap the flags so nobody has to remember them. Two of them are not style preferences:
# --provenance=false --sbom=false is MANDATORY (Docker 29 attaches attestations that Lambda rejects
# outright), and --platform linux/amd64 must match the function's architecture. Both were established
# by a real deploy — docs/streaming-verification.md.

image: ## Build the Lambda container image locally
	docker buildx build \
		--platform linux/amd64 \
		--provenance=false --sbom=false \
		-f infra/docker/Dockerfile \
		-t $(IMAGE) --load .
	@docker image inspect $(IMAGE) --format '{{.Size}}' \
		| awk '{printf "image size: %.1f MB on disk\n", $$1/1048576}'

# Runs the deployed artifact, not the source tree, with the no-AWS stub LLM. This is the check that
# catches an image which builds and then fails to start — a broken console-script shebang, a missing
# package, an artifact that did not make it into the wheel.
image-run: image ## Build the image and serve it on :8099 with the local stub LLM
	@docker rm -f $(PROJECT)-local >/dev/null 2>&1 || true
	docker run --rm -p 8099:8080 -e MYCELIUM_LLM_PROVIDER=local --name $(PROJECT)-local $(IMAGE)

image-push: image ## Log in to ECR, tag, and push (needs AWS credentials)
	@account=$$(aws sts get-caller-identity --query Account --output text); \
	registry=$$account.dkr.ecr.$(AWS_REGION).amazonaws.com; \
	aws ecr get-login-password --region $(AWS_REGION) \
		| docker login --username AWS --password-stdin $$registry; \
	docker tag $(IMAGE) $$registry/$(PROJECT):latest; \
	docker push $$registry/$(PROJECT):latest

tf-fmt: ## Format all Terraform
	terraform fmt -recursive infra/terraform

# -backend=false is what makes this credential-free: backend initialisation is the only part of
# `init` that authenticates. Runs in `make check` and in CI for that reason.
tf-validate: ## Check Terraform formatting and validity (no AWS credentials needed)
	@command -v terraform >/dev/null || { echo "terraform is not installed"; exit 1; }
	terraform fmt -check -recursive infra/terraform
	@for dir in infra/terraform/*/; do \
		terraform -chdir=$$dir init -backend=false -input=false -no-color >/dev/null || exit 1; \
		terraform -chdir=$$dir validate -no-color || exit 1; \
	done

# STAGE ONE of the two-stage apply. Creates the state bucket, the ECR repository, and the GitHub OIDC
# deploy role — the three things everything else depends on and none of which can create themselves.
# Run once. Uses local state; see infra/README.md.
tf-bootstrap: ## Apply the bootstrap root (state bucket, ECR, OIDC role)
	terraform -chdir=$(BOOTSTRAP) init
	terraform -chdir=$(BOOTSTRAP) apply

# The state bucket name contains the account id and backend blocks cannot interpolate variables, so
# it is resolved here rather than hardcoded into a public repository.
tf-init: ## Initialise the main root against the bootstrap state bucket
	@account=$$(aws sts get-caller-identity --query Account --output text); \
	terraform -chdir=$(TF_MAIN) init -backend-config=bucket=$(PROJECT)-tfstate-$$account

tf-plan: ## Plan the main root (requires TF_VAR_alert_email)
	terraform -chdir=$(TF_MAIN) plan

tf-apply: ## Apply the main root (requires TF_VAR_alert_email and an image already in ECR)
	terraform -chdir=$(TF_MAIN) apply

# The off-switch, and the ORDER IS NOT OPTIONAL: main first, then bootstrap. Destroying bootstrap
# first deletes the bucket holding main's state and leaves main's resources running and unmanaged.
tf-destroy: ## Destroy the main root. Bootstrap is destroyed separately and AFTER this.
	terraform -chdir=$(TF_MAIN) destroy
	@echo
	@echo "main/ is gone. To remove the rest (state bucket, ECR, OIDC role):"
	@echo "  terraform -chdir=$(BOOTSTRAP) destroy"

# Hits Wikidata, so it is deliberately NOT part of `check` and never runs in CI. The artifact it writes
# is committed; rebuilding it is an explicit act. Costs $0 — Wikidata is free — but it is network I/O
# against a service that is degraded in 2026, so run it when the corpus changes, not on every loop.
ingest: ## Rebuild the pinned graph artifact from Wikidata (local only; requires --force to overwrite)
	uv run python -m musical_mycelium.ingest.wikidata $(ARGS)

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

# MYCELIUM_LLM_PROVIDER=local is the default here on purpose: it runs the whole stack with no AWS
# account, no credentials and no spend. Set it to `bedrock` once the quota clears.
dev: ## Run the API locally on :8000 (local stub LLM by default — no AWS needed)
	MYCELIUM_LLM_PROVIDER=$${MYCELIUM_LLM_PROVIDER:-local} \
		uv run uvicorn musical_mycelium.api.app:app --reload --port 8000
	@exit 1
