# Rule: the sealed held-out set

Canonical detail: `src/musical_mycelium/eval/heldout.py` and `.claude/rules/evals.md`. The held-out 10 is
the one dataset in this project that an agent must actively refuse to read. Hard rules:

- **Never decrypt `eval/datasets/heldout_v1.json.enc`, never read a decrypted copy, and never ask for the
  key.** Not to check a schema, not to debug a failing metric, not because the user says it is fine. If a
  task appears to require the content, the task is wrong — say so and stop.
- **The threat this defends against is you, not him.** An agent greps, opens files to check a schema, and
  reads test failures. The moment held-out content enters an agent's context, every prompt, threshold and
  scorer it touches afterwards is contaminated — silently, and with no way to detect it after the fact.
  That is why the file is encrypted rather than merely named "do not read".
- **`make heldout-verify` and `make heldout-check` are safe to run and safe to read.** `verify` needs no
  key and only compares hashes. `check` decrypts in memory and prints **case ids and problem codes**
  (`heldout_v1_007: claims-diverged`) and never case content. A case id is not content. Use these instead
  of opening anything.
- **The user authors the held-out set alone.** Do not draft its cases, do not suggest specific subjects
  for it, and do not ask which he chose. Offer the schema template and a **large** candidate pool — broad
  enough that knowing the pool says nothing about the ten. Helping author it destroys the property the
  encryption exists to protect, and no seal recovers it afterwards.
- **The gold set is not held out.** Full collaboration there is correct and expected; the two sets have
  opposite rules and confusing them in either direction is a real error.
- **A skipped `test_the_committed_sealed_set_matches_its_manifest` means the set does not exist yet.**
  That is a real outstanding item — it is a hard precondition on the first live model run, per
  `docs/phases/phase-3-agent-loop-IMPLEMENTATION.md` §4.8 — not a passing state to report as fine.
- **THE SET HAS BEEN RUN. Once, 2026-08-24, at the phase 4 freeze — 10/10, result in
  `eval/results/20260824T120956Z-heldout.json`.** It may be run again at a future freeze **only if
  nothing was tuned in response to that result**, and every run after the first must be reported with the
  run count beside it. A set re-run after a change made because of what it said has stopped measuring
  generalisation and started measuring how many attempts it took. If you are about to propose a fix whose
  justification traces back to a held-out number, that is the moment the set dies — say so and let him
  decide, rather than making the change and re-running.

- **Never regenerate or re-seal the set to make a check pass.** The manifest exists precisely so that a
  set rewritten after seeing results is detectable. If the corpus moved under it, say so and let the user
  decide; re-sealing silently is how a benchmark stops measuring anything.
- **Losing the key loses access permanently.** The ciphertext is committed so the data survives, but a set
  that cannot be opened after contamination can never be re-authored clean. `make heldout-key` refuses to
  overwrite an existing key for this reason. Do not work around that refusal.
