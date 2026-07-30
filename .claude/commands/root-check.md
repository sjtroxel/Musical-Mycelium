---
description: Audit the repo root for clutter and propose where stray files should live instead
---

Audit the repository root for clutter.

1. Run `make root-check` to get the current count against the cap of 18 entries.
2. List every tracked file in the root (`git ls-files | awk -F/ 'NF==1'`).
3. For each one, state whether it *must* be in root and why. The legitimate reasons are: git requires it
   (`.gitignore`), GitHub surfaces it (`README.md`, `LICENSE`), the tool cannot be configured elsewhere
   (`pyproject.toml`, `Makefile`, `.pre-commit-config.yaml`), or the agent harness requires it (`CLAUDE.md`).
4. For anything else, propose the destination: `infra/` for deployment and container config, `docs/` for
   prose, `web/` for anything belonging to the SPA's toolchain, a `pyproject.toml` section for Python tool
   config, or deletion if its subject does not exist yet.
5. Report findings concisely. Do not move files without approval.

Context: this repo caps the root deliberately. Patchwork Assurance and Heritage Odyssey both reached 26
root entries by accretion, and each individual addition looked reasonable at the time. The cap is the
mechanism that makes the accretion visible.
