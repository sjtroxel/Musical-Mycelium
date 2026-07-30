# Phase 0 — Scaffold and Spine

> **Scope doc.** Written retroactively on 2026-07-29, after the work, for parity with the phase-doc pattern.
> Every later phase gets its scope doc *before* building. This one is backfilled so phase 0 is not the only
> phase whose intent lives solely in git history.

## What this phase is for

A repository that can be built in without stopping to make infrastructure decisions, with the project's
invariants written down where an agent will actually read them, and the last open product question settled.

The test of a good phase 0 is negative: after it, no later phase should have to pause and retrofit lint
config, CI, a dev runner, or a doc convention. Every previous project had to do exactly that.

## Delivers

- The Python toolchain, configured in `pyproject.toml` and nowhere else.
- CI that runs lint, types, tests, and a repo-root cap on every push.
- `CLAUDE.md` carrying the nine one-way-door invariants, plus `.claude/rules/` for the four rule domains and
  a `start-a-phase` skill that enforces the doc pattern mechanically.
- The five package boundaries as real directories, each documenting its own contract, with architecture
  tests that fail if the boundaries or the dependency direction are violated.
- `docs/ROADMAP.md` (phase spine + scaffolding ledger) and `docs/SPEC.md` (contracts).
- **The product shape decided** — the last open item from the pre-build series (`09` §2).

## Explicitly not in this phase

- Any application code. The five packages contain docstrings and no logic, on purpose.
- Any AWS resource, any Terraform, any Dockerfile. Their subjects do not exist yet.
- The frontend. `web/` is reserved and empty.
- Any eval metric. `tests/` holds architecture tests only.

## Definition of done

1. `make check` passes locally: format, lint, types, tests, root cap.
2. CI passes on a real push to `main`.
3. The repo root is at or under its cap.
4. The product shape and the first screen are recorded in `SPEC.md`.
5. Nothing in `docs/planning/09` §7 remains unstarted except the phase 1 IMPLEMENTATION doc and AWS signup.

## Governing principle

**Structure now, content when its subject exists.** Front-loading structure is preparation; front-loading
content is clutter wearing preparation's clothes. This is the same rule as *scope the density, never the
structure*, pointed at the repo instead of the data. The mechanism that keeps deferred items from being
forgotten is the scaffolding ledger in `ROADMAP.md` §3, not memory.
