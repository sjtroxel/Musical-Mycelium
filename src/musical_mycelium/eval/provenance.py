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
    if status.strip():
        return revision + DIRTY_SUFFIX
    return revision


def is_pinnable(revision: str) -> bool:
    """Whether a recorded revision identifies the code well enough to pool a run under it.

    ``unknown`` does not, and neither does a dirty tree: two runs both labelled ``24517e1-dirty``
    can have been produced by entirely different working trees, so the label is not an identity even
    when the strings match.
    """
    return revision != UNKNOWN and not revision.endswith(DIRTY_SUFFIX)
