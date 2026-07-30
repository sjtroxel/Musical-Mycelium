---
name: start-a-phase
description: Use when beginning any new phase or version of Musical Mycelium (v0.1, v0.2, a new capability, "let's start building X"). Enforces the standing rule that the phase IMPLEMENTATION doc is written and approved before any code is written.
---

# Starting a phase

The standing rule: **the phase IMPLEMENTATION doc is written and approved before any code.** "Let's get a
move on" does not mean skip the plan. This exists because skipping it has cost real rework before.

Every phase already has a **scope doc** (`docs/phases/phase-N-<slug>.md`) written up front. This skill covers
the second layer: turning that scope into an approved implementation plan at the moment the phase starts.

## Steps

1. **Confirm which phase.** Check `docs/ROADMAP.md` for the phase spine and confirm the phase number and
   target version with him. Do not infer it.

2. **Re-read that phase's scope doc first.** It was written before any building, so check it against what
   the intervening phases actually taught. Where reality has diverged, say so explicitly and offer to amend
   the scope doc — do not silently let the IMPLEMENTATION doc contradict it. If the phase has no scope doc
   because it was conceived later, write the scope doc first and get it approved as its own step.

3. **Read the inherited assignments.** `docs/planning/09-PRIORITIES-AND-OPEN-DECISIONS.md` §6 gathers every
   accumulated assignment from the pre-build series. Check which ones this phase is responsible for and
   carry them forward explicitly — that list exists so nothing gets lost between planning and building.

4. **Write `docs/phases/phase-N-<slug>-IMPLEMENTATION.md`** covering, at minimum:
   - What this phase delivers, in one sentence, and its definition of done
   - The explicit **not-in-this-phase** list (this is the scope fence; it does more work than the feature list)
   - Which one-way doors from `CLAUDE.md` this phase touches, and how each is satisfied
   - The files and modules that will change, by path
   - How it will be tested, including which eval metrics apply
   - Cost impact, if any, and the guardrail for it
   - Anything genuinely uncertain, named as uncertain rather than smoothed over

5. **Get explicit approval on the doc.** Present it and stop. Do not begin writing code in the same turn.

6. **Then build**, keeping the doc updated as the as-built record when reality diverges from the plan.
   The doc is allowed to be wrong; it is not allowed to be silently wrong.

7. **Write the plain-English explanation as you go.** A short write-up of what this phase does, in language
   with no jargon, phase by phase. This is the cold-articulation rep — it is genuinely useful interview
   preparation and it is much harder to reconstruct months later.

## Do not

- Do not propose new numbered planning docs. `docs/planning/09` is the last one; planning is closed.
- Do not let the phase quietly widen. If something new belongs in the project but not in this phase, it
  goes in the ROADMAP backlog, not in this phase's scope.
- Do not run `git commit` or `git push`. Provide the command.
