#!/usr/bin/env bash
# Session orientation. Prints, in one shot, the state a fresh session would otherwise
# rebuild by hand: git position, the active phase's next step, the newest KNOWN-GAPS
# section, and the memory router. Safe to run any time; reads only, writes nothing.
set -uo pipefail
cd "$(dirname "$0")/.." || exit 1

MEM="$HOME/.claude/projects/-home-sjtroxel-job-search-headquarters/memory"

echo "=============================================================="
echo " ORIENT  $(date '+%A %Y-%m-%d %H:%M %Z')  branch $(git rev-parse --abbrev-ref HEAD)"
echo "=============================================================="

echo
echo "## Git"
git log --oneline -8
echo
echo "  push state (left=origin ahead, right=local ahead):"
echo -n "  "
git rev-list --left-right --count origin/main...main 2>/dev/null || echo "  (no origin/main)"
echo "  tags: $(git tag --sort=-creatordate | head -3 | tr '\n' ' ')"
echo
echo "  working tree:"
if [ -z "$(git status --short)" ]; then echo "    clean"; else git status --short | sed 's/^/    /'; fi

echo
echo "## Active phase"
PHASE_DOC=$(ls docs/phases/phase-*-IMPLEMENTATION.md 2>/dev/null \
  | sed -E 's/.*phase-([0-9]+)-.*/\1 &/' | sort -rn | head -1 | cut -d' ' -f2-)
if [ -n "$PHASE_DOC" ]; then
  echo "  doc: $PHASE_DOC"
  echo
  echo "  steps:"
  grep -nE '^### Step ' "$PHASE_DOC" | sed -E 's/^([0-9]+):### /    L\1  /' \
    | sed -E 's/(\*\*DONE[^*]*\*\*)/[done]/'
  echo
  NEXT=$(grep -nE '^### Step ' "$PHASE_DOC" | grep -v 'DONE' | head -1)
  if [ -n "$NEXT" ]; then
    LN=${NEXT%%:*}
    echo "  >>> NEXT UNFINISHED STEP (line $LN):"
    echo "$NEXT" | sed -E 's/^[0-9]+:### /      /'
    echo
    # body of that step only: stop at the next ### heading, cap at 30 lines
    awk -v start="$LN" 'NR>start { if ($0 ~ /^### /) exit; print }' "$PHASE_DOC" \
      | grep -v '^[[:space:]]*$' | head -30 | sed 's/^/      /'
  else
    echo "  >>> every step in this doc is marked DONE"
  fi
fi

echo
echo "## KNOWN-GAPS -- newest section only (file is newest-first, $(wc -l < docs/KNOWN-GAPS.md) lines total)"
awk '/^## /{n++} n==1{print} n==2{exit}' docs/KNOWN-GAPS.md | head -60 | sed 's/^/  /'

echo
echo "## ROADMAP -- where the build actually is"
sed -n '/### Where the build actually is/,/^### /p' docs/ROADMAP.md | head -20 | sed 's/^/  /'

echo
echo "## Recorded suite counts (NOT re-measured -- run 'make check' to verify)"
grep -rhoE '(make check|Python)[^.]{0,30}\b1[0-9]{3}\b|frontend [0-9]{3}' docs/KNOWN-GAPS.md 2>/dev/null | head -3 | sed 's/^/  /'

echo
echo "## Memory router"
if [ -f "$MEM/MEMORY.md" ]; then
  sed -n '/## Current focus/,/^## /p' "$MEM/MEMORY.md" | head -30 | sed 's/^/  /'
else
  echo "  (memory store not found at $MEM)"
fi

echo
echo "## Project rules in force"
ls .claude/rules/ 2>/dev/null | sed 's/^/  .claude\/rules\//'
ls .claude/skills/ 2>/dev/null | sed 's/^/  .claude\/skills\//'

echo
echo "=============================================================="
echo " Reminders: he runs git commit/push, never you. Round down on"
echo " every count. Verify against the repo, not against this dump."
echo "=============================================================="
