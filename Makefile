# Musical Mycelium — the single entry point for every routine task.
# `make help` lists targets. `make check` is what CI runs.

.DEFAULT_GOAL := help
.PHONY: help install fmt lint typecheck test cov check root-check clean dev ingest \
        image image-run tf-fmt tf-validate tf-bootstrap tf-init tf-plan tf-apply tf-destroy image-push \
        heldout-key heldout-draw heldout-seal heldout-verify heldout-check \
        eval eval-live eval-noise eval-label eval-judge eval-tier2 eval-heldout \
        hooks hooks-uninstall

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
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
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

# `eval` is in here as of 2026-08-17. It was NOT, while this line claimed to be "everything CI runs" --
# CI's check job ends with `make eval` and `make check` did not, so a change that broke the scripted
# tier 1 run passed locally and failed on push. That is a real divergence and it is what makes a
# pre-commit hook worth installing: the hook is only useful if green locally means green in CI.
check: lint typecheck test root-check tf-validate eval ## Everything CI runs

# --- git hooks ---------------------------------------------------------------
# Automates the thing that otherwise depends on remembering: run the checks before the commit, not
# after the push. Deliberately a GIT hook rather than a Claude Code hook or a skill -- commits are
# human-run here, often in a plain terminal with no agent involved, and a guard that only fires when
# an assistant is in the loop is not a guard.
#
# Skip it once when you mean to:  git commit --no-verify
# Remove it:                     make hooks-uninstall

HOOK_MARKER := installed by make hooks

hooks: ## Install a git pre-commit hook that runs `make check`
	@if [ -e .git/hooks/pre-commit ] && ! grep -q '$(HOOK_MARKER)' .git/hooks/pre-commit; then \
		echo "refusing to overwrite an existing .git/hooks/pre-commit that this target did not write."; \
		echo "inspect it, then move it aside if you want ours."; \
		exit 1; \
	fi
	@printf '%s\n' \
		'#!/bin/sh' \
		'# $(HOOK_MARKER) -- runs the same checks CI runs.' \
		'# Skip once: git commit --no-verify' \
		'echo "pre-commit: make check (skip with --no-verify)"' \
		'exec make check' > .git/hooks/pre-commit
	@chmod +x .git/hooks/pre-commit
	@echo "installed .git/hooks/pre-commit -> make check"

hooks-uninstall: ## Remove the pre-commit hook this repo installed
	@if [ -e .git/hooks/pre-commit ] && ! grep -q '$(HOOK_MARKER)' .git/hooks/pre-commit; then \
		echo "leaving .git/hooks/pre-commit alone: this target did not write it."; \
		exit 1; \
	fi
	@rm -f .git/hooks/pre-commit
	@echo "removed .git/hooks/pre-commit"

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

# --- evaluation ---------------------------------------------------------------
# Tier 1 over the gold set, driven by ScriptedLLM. Costs $0, needs no AWS, and runs on every commit.
#
# READ THE SCRIPT-DETERMINED MARKERS IN THE OUTPUT BEFORE QUOTING ANY NUMBER FROM IT. A scripted run
# shows that the gate and the loop refuse unsupported claims; it does NOT show that a real model walks
# the graph correctly. traversal_recall, traversal_precision and plan_adherence are decided by the trace
# policy in eval/gold.py, not by a model. Real-model numbers are `eval-live`, which spends money.

eval: ## Tier 1 over the gold set, scripted (free, no AWS)
	uv run python -m musical_mycelium.eval.suite

# SPENDS MONEY. Gold + adversarial through Bedrock, behind confirm_spend.
#
# RUN THIS YOURSELF, IN YOUR OWN TERMINAL. It refuses to start without an interactive terminal --
# that is layer 2 of the spend gate and it is deliberate, because the incident that produced
# confirm_spend was a run that billed with nobody watching. There is no --yes flag.
#
# It asks ONCE, up front, then runs unattended for roughly 25-45 minutes at 10 RPM. Walk away after
# you type yes. If it aborts on budget it still writes partial results marked complete: false.
#
# Prove the wiring first for a couple of cents:  make eval-live ARGS='--cases 1'
# Check one behaviour, wherever its case sits:   make eval-live ARGS='--case-ids gold_v0_1_021'
# Neither form is gated -- a subset is not a smaller version of the 41-case baseline.
eval-live: ## SPENDS MONEY. Tier 1 through Bedrock, behind an explicit confirmation
	uv run python -m musical_mycelium.eval.live $(ARGS)

# FREE. Reads result files that eval-live already wrote and reports how much the suite moves against
# itself. Phase 4 step 6, and it runs BEFORE step 5 sets thresholds -- two runs on 2026-08-16 differed
# by 6.5pp on traversal_recall, which is wider than the 5pp gate step 5 was going to adopt.
#
# Defaults to the newest 5 *-bedrock.json. It REFUSES to pool runs that disagree on dataset, model,
# artifact or the code revision that produced them, and names the offender rather than quietly
# dropping it. Add --write to record the floor to eval/noise_floor.json.
#
#   make eval-noise                        the newest 5
#   make eval-noise ARGS='--runs 3'        the newest 3, reported as PROVISIONAL
#   make eval-noise ARGS='--write'         and record it
eval-noise: ## FREE. The noise floor across recent live runs
	uv run python -m musical_mycelium.eval.noise $(ARGS)

# FREE. The hand-labeling flow for the judge pool -- phase 4 step 7b, and the one piece of this phase
# that is your time rather than a machine's.
#
# ONE ITEM AT A TIME, and it is resumable. Every `record` writes immediately, so stopping after four
# items costs nothing and picking it up next week costs nothing. Ten is a sitting, not a target.
#
#   make eval-label ARGS='build --transcript src/musical_mycelium/eval/transcripts/A.json \
#                               --transcript .../B.json'     sample 30 items (needs ~2 live runs)
#   make eval-label ARGS='status'                            how many done, which is next
#   make eval-label ARGS='next'                              show the next unlabeled item
#   make eval-label ARGS='record judge_pool_v1_007 SUPPORTED 4 --note "..."'
eval-label: ## FREE. Hand-label the judge pool, one item at a time
	uv run python -m musical_mycelium.eval.labelling $(ARGS)

# SPENDS MONEY. Nova Pro scores the same pool you labeled, then agreement is measured and printed.
#
# It refuses to start on an unlabeled pool, refuses a judge model from the generator's family, and
# refuses labels whose digest no longer matches the pool -- all three BEFORE the spend prompt, so a
# misconfigured judge never costs anything. Thirty items is one request each: small.
eval-judge: ## SPENDS MONEY. Run the validated judge over the labeled pool
	uv run python -m musical_mycelium.eval.judge $(ARGS)

# SPENDS MONEY. Phase 4 step 8. The same judge, pointed at a SAMPLE OF A RELEASE CANDIDATE rather than
# at the labeled pool -- so the number it produces is about the AGENT, where eval-judge's number is
# about the JUDGE.
#
# There are no human labels here and there should not be: the labels validate the judge, and
# re-labeling every candidate would make having a judge pointless. So the agreement figure is
# INHERITED from the committed judge runs, as a range, and it is a required field on the result --
# the score and the figure that says what it is worth cannot be separated.
#
# It refuses, all BEFORE the spend prompt, so a misconfigured run costs nothing: no committed judge
# run to inherit from, judge runs that disagree with each other, a rubric the labels were not written
# against, a judge the agreement was not measured on, a same-family judge, a source whose code
# revision is dirty or unknown, or a transcript too thin to sample.
#
#   make eval-tier2                                          the newest transcript, 20 items
#   make eval-tier2 ARGS='--size 25'                         a larger sample if the run supports it
#   make eval-tier2 ARGS='--transcript src/.../transcripts/A.json'
eval-tier2: ## SPENDS MONEY. Tier 2 judged over a release candidate (tracked, never blocking)
	uv run python -m musical_mycelium.eval.tier2 $(ARGS)

# --- the sealed held-out set -------------------------------------------------
# .claude/rules/evals.md requires a held-out set "never looked at during development". The threat is the
# coding agent, not the author: an agent greps, opens files to check a schema, and reads test failures,
# and a plaintext held-out set reaches its context eventually. See src/musical_mycelium/eval/heldout.py.
#
# THE KEY LIVES OUTSIDE THIS REPO and losing it loses access permanently — the ciphertext is committed so
# the data survives, but a set that cannot be opened after a live run can never be re-authored clean.

HELDOUT_KEY := $(HOME)/.config/musical-mycelium/heldout.key

heldout-key: ## Generate the held-out key (refuses to overwrite an existing one)
	@if [ -f "$(HELDOUT_KEY)" ]; then \
		echo "A key already exists at $(HELDOUT_KEY)."; \
		echo "Overwriting it would make the sealed set unopenable forever. Refusing."; \
		exit 1; \
	fi
	@mkdir -p "$(dir $(HELDOUT_KEY))"
	@openssl rand -base64 48 > "$(HELDOUT_KEY)"
	@chmod 600 "$(HELDOUT_KEY)"
	@echo "key written to $(HELDOUT_KEY)"
	@echo "BACK IT UP NOW — password manager, and one copy off this machine."

# PLAINTEXT= must point OUTSIDE this repo. Sealing streams through memory and writes only the ciphertext
# and the public manifest; the authored file is left untouched for you to move or delete.
heldout-draw: ## Draw a held-out set. Usage: make heldout-draw SEED='...' OUT=~/heldout_v1.json
	@test -n "$(SEED)" || { echo "Usage: make heldout-draw SEED='something only you know' OUT=~/heldout_v1.json"; exit 1; }
	@test -n "$(OUT)" || { echo "Usage: make heldout-draw SEED='something only you know' OUT=~/heldout_v1.json"; exit 1; }
	uv run python -m musical_mycelium.eval.heldout_draw --seed "$(SEED)" --out "$(OUT)"

heldout-seal: ## Seal an authored held-out set. Usage: make heldout-seal PLAINTEXT=~/path/heldout_v1.json
	@test -n "$(PLAINTEXT)" || { echo "Usage: make heldout-seal PLAINTEXT=~/path/heldout_v1.json"; exit 1; }
	uv run python -m musical_mycelium.eval.heldout --key "$(HELDOUT_KEY)" seal "$(PLAINTEXT)"

heldout-verify: ## Check the sealed set against its manifest (no key, no decryption — CI-safe)
	uv run python -m musical_mycelium.eval.heldout verify

# Run this when the artifact version moves. Prints case ids and problem codes, never case content, so
# running it does not open the set.
heldout-check: ## Validate the sealed set against the pinned corpus (needs the key)
	uv run python -m musical_mycelium.eval.heldout --key "$(HELDOUT_KEY)" check

# SPENDS MONEY, and it is the one run in this project that must never be repeated to get a better
# number. Roughly ten cases at the measured per-case rate; the confirmation names the estimate.
#
# It decrypts in memory, verifies the seal, checks the set against the pinned corpus, refuses on any
# finding, then runs. Output is aggregate metrics, slice rates and case ids -- NEVER case content, and
# no transcript. src/musical_mycelium/eval/heldout_run.py holds the four locks and the reasoning;
# tests/test_heldout_run.py breaks each of them deliberately.
#
# If a number here comes back bad and is not diagnosable from ids and error types alone, the correct
# outcome is to report it undiagnosed. Opening the set to debug it is what the seal exists to prevent.
eval-heldout: ## SPENDS MONEY. The sealed held-out set, run once, reported without being read
	uv run python -m musical_mycelium.eval.heldout_run --key "$(HELDOUT_KEY)" $(ARGS)

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

# MYCELIUM_LLM_PROVIDER=local is the default here on purpose: it runs the whole stack with no AWS
# account, no credentials and no spend.
#
# **KNOW WHAT THE STUB CANNOT DO BEFORE YOU JUDGE AN ANSWER BY IT (learned 2026-08-26).** `LocalLLM`
# walks ONE fixed path — resolve, then get_influences, then stop — and has no route to
# `get_descendants` at all. So every "who did X influence?" query refuses under it, no matter what the
# corpus holds: Kate Bush and Elvis Presley both refuse locally and both answer on Bedrock, with 7 and
# 5 cited claims. That is a property of the fixture, not of the system. Use `make dev-live` before
# concluding an answer is bad.
dev: ## Run the API locally on :8000 (local stub LLM — no AWS, and see the caveat above)
	MYCELIUM_LLM_PROVIDER=$${MYCELIUM_LLM_PROVIDER:-local} \
		uv run uvicorn musical_mycelium.api.app:app --reload --port 8000
	@exit 1

# The same server on the real model. Roughly a cent a query (6,624 input + 421 output tokens on
# average, measured 2026-08-24), hard-capped near $0.075 by MAX_ACCUMULATED_TOKENS. Needs AWS
# credentials. This is what the deployed site runs, and it is the only local mode whose ANSWERS are
# representative.
dev-live: ## SPENDS MONEY. Run the API locally on :8000 against Bedrock, like production
	MYCELIUM_LLM_PROVIDER=bedrock \
		uv run uvicorn musical_mycelium.api.app:app --reload --port 8000
	@exit 1

web-install: ## Install the SPA's dependencies
	npm --prefix web ci

web-dev: ## Run the SPA on :5173, proxying /api to whatever is on :8000
	npm --prefix web run dev

web-check: ## SPA types, unit tests, and production build
	npm --prefix web run check
