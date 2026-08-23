"""Which code produced a result file. The one dimension a result file was missing.

Every other axis a run can differ on is already recorded: the dataset, its version, the provider, the
model id, the artifact version and the pin it was authored against. The code was not, and on
2026-08-16 that turned out to matter. Two live runs twenty minutes apart differed on
``traversal_precision`` by 18 points, and the cause was not the model — it was a metric fix landing
between them. Both files declare the same dataset, the same model and the same artifact, so nothing in
either one says they must not be averaged together.

**A noise floor computed across a code change is not a noise floor.** It is a diff wearing a
statistic's clothes, and it is unfalsifiable after the fact: the two files look identical in every
field a reader would think to check. So the revision is recorded at write time, and ``noise.py``
refuses to pool runs that disagree about it.

**Dirty counts as dirty, untracked included.** ``git status --porcelain`` reports untracked files, and
they are not noise in this context — an uncommitted module or a stray ``.env`` changes behaviour just
as well as an edited one. The conservative reading is the useful one here, because the cost of a false
"dirty" is that a floor is marked provisional and re-run, while the cost of a false "clean" is a
number nobody can ever check again.

**With two exemptions, both of them directories a run writes its own output into.** Amended
2026-08-23. A run writes a result file into ``eval/results/`` and a transcript into
``eval/transcripts/``, so the *output* of run N made the tree untracked-dirty for run N+1 — run 3 of the
judge was stamped ``fd79865-dirty`` while its code was byte-identical to run 2's. That is a **false**
dirty, and false-dirty is the direction that costs something: ``is_pinnable`` rejects a dirty revision,
``noise.py`` refuses to pool revisions that disagree, and ``tier2.sample_from`` refuses an unpinnable
source outright — so two runs of identical code could not be pooled, and neither could be judged. The
workaround — commit between every run — is precisely the discipline this module exists so nobody has to
maintain.

Both directories are named explicitly rather than covered by a wildcard over ``eval/``, and that is the
whole design: they contain no code, and this function answers a question about code. Everywhere else,
untracked still counts as dirty, and a line this function cannot parse counts as dirty too.

**Never raises.** A result file that failed to record its revision is worth more than a run that
crashed after spending money, so every failure path returns ``UNKNOWN`` and lets the consumer decide
what an unknown revision is worth. ``noise.py`` decides it is worth *provisional*.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path

#: What is recorded when git cannot answer: not installed, not a repository, or a call that failed.
#: A sentinel rather than an empty string so it survives a round trip through JSON and reads as a
#: deliberate value in a file a human opens.
UNKNOWN = "unknown"

#: Appended when the working tree has any modification, staged or not, tracked or not.
DIRTY_SUFFIX = "-dirty"

#: ``src/musical_mycelium/eval/provenance.py`` -> the repo root.
REPO_ROOT = Path(__file__).resolve().parents[3]

Runner = Callable[[Sequence[str], Path], str | None]

#: The path prefixes a modification does not dirty the stamp for, repo-relative and slash-separated.
#: See the module docstring: these directories hold run output, and this module answers a question about
#: code. Keep the list short; every entry needs its own argument for why nothing in it can change
#: behaviour.
EXEMPT_PREFIXES = (
    "src/musical_mycelium/eval/results/",
    "src/musical_mycelium/eval/transcripts/",
)


def _changed_paths(line: str) -> list[str]:
    """The repo-relative path(s) one ``git status --porcelain`` line refers to.

    Returns an empty list for a line this cannot read, and the caller treats that as dirty. Guessing
    is the wrong instinct here: an unparsed line that is assumed to be exempt is a false *clean*, and
    that is the direction with no recovery.
    """
    # `XY path`, `XY "quoted path"`, or `XY old -> new` for a rename. The status is two columns and
    # a space, so anything shorter is not a status line at all.
    if len(line) < 4 or line[2] != " ":
        return []
    rest = line[3:].strip()
    if not rest:
        return []
    # A rename dirties on either side: moving a source file *into* the results directory is still a
    # change to the code, and moving one out of it is too.
    parts = rest.split(" -> ") if " -> " in rest else [rest]
    return [part.strip().strip('"') for part in parts if part.strip()]


def _is_dirty(status: str) -> bool:
    """Whether a porcelain status describes a tree change that matters to the code identity."""
    for raw in status.splitlines():
        if not raw.strip():
            continue
        paths = _changed_paths(raw)
        if not paths:
            return True
        if any(not path.startswith(EXEMPT_PREFIXES) for path in paths):
            return True
    return False


def _run(command: Sequence[str], cwd: Path) -> str | None:
    """Run a git command and return its stdout, or ``None`` on any failure at all.

    The broad except is the point rather than an oversight: this is provenance metadata gathered on
    the way out of a billable run, and there is no failure mode here worth losing that run over.
    """
    try:
        completed = subprocess.run(
            list(command),
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if completed.returncode != 0:
        return None
    return completed.stdout


def code_revision(*, root: Path | None = None, run: Runner | None = None) -> str:
    """``24517e1``, ``24517e1-dirty``, or ``unknown``.

    ``run`` is injected so the tests can drive every branch — including the ones that need git to
    fail — without constructing throwaway repositories or depending on the state of this one.
    """
    where = REPO_ROOT if root is None else root
    call = _run if run is None else run

    head = call(("git", "rev-parse", "--short", "HEAD"), where)
    if head is None or not head.strip():
        return UNKNOWN

    revision = head.strip()
    status = call(("git", "status", "--porcelain"), where)
    if status is None:
        # HEAD resolved but the cleanliness question did not. Unknown-clean is the dangerous
        # answer, so this reports the revision it knows and assumes the worst about the tree.
        return revision + DIRTY_SUFFIX
    if _is_dirty(status):
        return revision + DIRTY_SUFFIX
    return revision


def is_pinnable(revision: str) -> bool:
    """Whether a recorded revision identifies the code well enough to pool a run under it.

    ``unknown`` does not, and neither does a dirty tree: two runs both labelled ``24517e1-dirty``
    can have been produced by entirely different working trees, so the label is not an identity even
    when the strings match.
    """
    return revision != UNKNOWN and not revision.endswith(DIRTY_SUFFIX)
