# Musical Mycelium — the single entry point for every routine task.
# `make help` lists targets. `make check` is what CI runs.

.DEFAULT_GOAL := help
.PHONY: help install fmt lint typecheck test cov check root-check clean dev ingest

UV := $(shell command -v uv 2>/dev/null)

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

check: lint typecheck test root-check ## Everything CI runs

# Hits Wikidata, so it is deliberately NOT part of `check` and never runs in CI. The artifact it writes
# is committed; rebuilding it is an explicit act. Costs $0 — Wikidata is free — but it is network I/O
# against a service that is degraded in 2026, so run it when the corpus changes, not on every loop.
ingest: ## Rebuild the pinned graph artifact from Wikidata (local only; requires --force to overwrite)
	uv run python -m musical_mycelium.ingest.wikidata $(ARGS)

clean: ## Remove caches and build artifacts
	rm -rf .pytest_cache .mypy_cache .ruff_cache dist build .coverage
	find . -type d -name __pycache__ -prune -exec rm -rf {} +

dev: ## Run the local API + web dev servers (arrives with the v0.1 API in phase 1)
	@echo "Not wired yet — there is no API to run. The v0.1 IMPLEMENTATION doc adds this target's body."
	@echo "Until then: 'make check' is the loop."
	@exit 1
