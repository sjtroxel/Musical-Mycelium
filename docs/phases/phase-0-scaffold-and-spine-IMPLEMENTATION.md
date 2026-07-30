# Phase 0 — Scaffold and Spine: IMPLEMENTATION

> As-built record. Completed 2026-07-29. CI verified green on the first push.

## What was actually built

| Area | Files |
|---|---|
| Agent operating manual | `CLAUDE.md` — nine invariants, stack, conventions, cost, the grounded-vs-true caveat |
| Agent rules | `.claude/rules/{grounding-and-claims,aws-and-cost,graph-semantics,evals}.md` |
| Agent workflow | `.claude/skills/start-a-phase/SKILL.md`, `.claude/commands/root-check.md` |
| Guardrails | `.claude/settings.json` — denies git commit/push, `terraform apply`/`destroy`, `aws *` |
| Toolchain | `pyproject.toml` — project, deps, ruff, mypy, pytest, coverage. No other tool config file exists |
| Dev runner | `Makefile` — `make help`, `make check` is what CI runs |
| Local hooks | `.pre-commit-config.yaml` |
| CI | `.github/workflows/ci.yml` (two jobs), `.github/dependabot.yml` |
| Packages | `src/musical_mycelium/{ingest,graph,agent,api,eval}/__init__.py`, contracts documented, no logic |
| Tests | `tests/test_architecture.py` — 7 tests guarding boundaries and dependency direction |
| Docs | `docs/ROADMAP.md`, `docs/SPEC.md`, `docs/phases/`, `docs/archive/` |
| Reserved | `infra/README.md`, `web/README.md` — both empty of code, both documenting why they exist |

## Verification

CI run `30502152043`, both jobs green in 20 seconds. The runner downloaded `cpython-3.13.14`, matching local
exactly. All nine pre-commit hooks pass on tracked files. `make check` green: 7 files formatted, lint clean,
mypy clean on 7 source files, 7 tests passed, root at 15 entries.

## Deviations from the plan, and defects found

- **Root cap raised 16 → 18.** `uv.lock` is a forced root file that was not counted in the original estimate.
  15 entries in use. The standing rule: raise the cap only for something genuinely unrelocatable, otherwise
  relocate it.
- **`.gitignore` was ignoring `.terraform.lock.hcl`.** That file pins provider versions and hashes and must be
  committed, exactly like `uv.lock`. Fixed before the first commit.
- **`.gitignore` had a `!data/manifest.json` exception** that would have put a tracked file in an otherwise
  untracked directory, defeating the root discipline. `data/` is now fully untracked; the pinned-artifact
  pointer is deferred to the phase 1 IMPLEMENTATION doc.
- **E501 versus the formatter.** `ruff format` cannot reflow prose in docstrings, so E501 fought every doc
  line. E501 is now off and `[tool.ruff.lint.pycodestyle] max-doc-length = 110` replaces it.
- **`requires-python = ">=3.13"` resolved to CPython 3.14.6.** uv takes the newest available interpreter
  without an upper bound, which silently disagreed with CI and the intended Lambda base image. Now
  `>=3.13,<3.14`.
- **A silently inert mypy override.** `module = "tests.*"` never matched, because without `tests/__init__.py`
  mypy names the module `test_architecture`. `test_*` is also invalid — mypy wildcards replace whole
  components only. Resolved by dropping the exemption and annotating the tests.
- **`astral-sh/setup-uv@v9` does not exist.** That action publishes no floating major tag. Pinned to
  `@v9.0.0`. This would have failed CI at the install step on the first push; it was found by verifying the
  tag against the GitHub API rather than trusting the pattern `actions/checkout@v7` set.
- **Removed `no-commit-to-branch --branch main`** from pre-commit. This is a solo repo where commits go
  straight to main; the hook would have blocked every commit.

## Carried forward

- The phase-doc pattern was initially implemented with only the IMPLEMENTATION layer. The scope-doc layer was
  added the same evening after checking Patchwork, Heritage Odyssey, and Wildlife Sentinel, all three of
  which show scope docs landing up front and implementation docs landing per-build. Naming had drifted three
  ways across those projects; this project standardizes on Patchwork's lowercase-kebab convention.
- Local prerequisites still absent: Terraform, Docker. Both are phase 1 blockers.
