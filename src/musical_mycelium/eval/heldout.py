"""The sealed held-out set: authored once, never read during development, still checkable.

``.claude/rules/evals.md`` requires "a held-out set of 10 that is **never looked at** during development".
A promise cannot deliver that. This module delivers it as a mechanism, and the threat it is built against
is **the coding agent**, not the author: an agent greps, opens files to check a schema, and reads test
failures. A plaintext held-out set in ``eval/datasets/`` reaches an agent's context eventually, and from
that moment every prompt and threshold it touches is contaminated silently and unfalsifiably. Encryption
is what makes the rule enforceable rather than aspirational.

Three properties, each of which cost a design decision:

**1. The plaintext never touches disk after sealing.** ``openssl`` reads stdin and writes stdout, so
sealing streams through memory, and :func:`load_sealed` decrypts into a Python object. There is no temp
file to shred and no window in which a stray ``cat`` finds anything. Sealing is the only operation that
reads the author's plaintext, and it prints the manifest rather than the content.

**2. Failures are reported as case ids and problem codes, never as case content.** This is what makes the
set *checkable while sealed*. The held-out cases pin to an artifact version, and phase 6 will move the
corpus — a case whose neighbours shift silently stops matching, and you cannot normally discover that
without opening the set, which destroys it. ``heldout_v1_007: claims-diverged`` says everything needed to
act and discloses nothing. A case id is not content.

**3. The manifest is public and deliberately thin.** It carries hashes, a count, and the shape
distribution — enough to prove composition and detect a quietly regenerated set, and no query, node id, or
claim. :func:`summarise` is locked by a test that asserts exactly which keys may appear.

The key lives outside the repository (``~/.config/musical-mycelium/heldout.key`` by default). Losing it
does not lose the data — the ciphertext is committed and versioned — but it does lose access, and access
lost after the first live run can never be re-earned, because the set cannot be re-authored clean. Back
the key up off this machine.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime
from hashlib import sha256
from pathlib import Path
from typing import Any

from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.store import Direction

#: Where the sealed set and its public manifest live. Committed; the key is not.
DATASETS_DIR = Path(__file__).resolve().parent / "datasets"
SEALED_PATH = DATASETS_DIR / "heldout_v1.json.enc"
MANIFEST_PATH = DATASETS_DIR / "heldout_v1.manifest.json"

#: Outside the repository on purpose. ``.gitignore`` also covers ``*.key`` as a second line of defence.
DEFAULT_KEY_PATH = Path.home() / ".config" / "musical-mycelium" / "heldout.key"

#: Recorded in the manifest so a future reader knows how to open the file without guessing.
CIPHER = "aes-256-cbc pbkdf2 sha256 600000"
_ITERATIONS = "600000"

#: The only keys :func:`summarise` may emit. Locked by a test — the manifest is public, so a field added
#: carelessly here is a disclosure, not a convenience.
MANIFEST_KEYS = frozenset(
    {
        "dataset",
        "sealed_at",
        "cipher",
        "artifact_version_pin",
        "case_count",
        "refusal_count",
        "shapes",
        "sha256_ciphertext",
        "sha256_plaintext",
    }
)


class SealError(RuntimeError):
    """Sealing, opening, or verifying the held-out set failed."""


@dataclass(frozen=True, slots=True)
class Finding:
    """A problem with one held-out case, expressed so that reporting it discloses nothing.

    ``case_id`` is an ordinal (``heldout_v1_007``) and ``code`` is drawn from a fixed vocabulary. Neither
    is content, which is the whole reason the sealed set can be validated in the first place.
    """

    case_id: str
    code: str

    def __str__(self) -> str:
        return f"{self.case_id}: {self.code}"


# --- encryption ---------------------------------------------------------------------------------


def _openssl(args: list[str], payload: bytes) -> bytes:
    """Run openssl over a pipe. The key is passed as ``-pass file:`` and never as an argument, because
    arguments are visible to any other process on the machine via ``ps``."""
    try:
        done = subprocess.run(
            ["openssl", *args],
            input=payload,
            capture_output=True,
            check=True,
        )
    except FileNotFoundError as exc:  # pragma: no cover - environment failure
        raise SealError("openssl is not installed") from exc
    except subprocess.CalledProcessError as exc:
        detail = exc.stderr.decode("utf-8", "replace").strip()
        raise SealError(f"openssl failed: {detail}") from exc
    return done.stdout


def _cipher_args(key_path: Path) -> list[str]:
    return [
        "enc",
        "-aes-256-cbc",
        "-md",
        "sha256",
        "-pbkdf2",
        "-iter",
        _ITERATIONS,
        "-salt",
        "-pass",
        f"file:{key_path}",
    ]


def encrypt(plaintext: bytes, key_path: Path) -> bytes:
    """Encrypt in memory. No temp file exists at any point."""
    if not key_path.exists():
        raise SealError(f"no key at {key_path}. Create one with: make heldout-key")
    return _openssl(_cipher_args(key_path), plaintext)


def decrypt(ciphertext: bytes, key_path: Path) -> bytes:
    """Decrypt in memory. The caller gets bytes, not a path, so nothing lands on disk."""
    if not key_path.exists():
        raise SealError(f"no key at {key_path}")
    return _openssl([*_cipher_args(key_path), "-d"], ciphertext)


def sha256_hex(data: bytes) -> str:
    return sha256(data).hexdigest()


# --- the manifest -------------------------------------------------------------------------------


def summarise(data: dict[str, Any], ciphertext: bytes, plaintext: bytes) -> dict[str, Any]:
    """Build the public manifest. Aggregates only.

    The shape distribution is the maximum this may disclose: it proves the set was composed to the
    intended spread without naming a single subject. ``MANIFEST_KEYS`` is asserted by a test.
    """
    cases = data.get("cases", [])
    shapes: dict[str, int] = {}
    for case in cases:
        shape = str(case.get("shape", "unknown"))
        shapes[shape] = shapes.get(shape, 0) + 1

    return {
        "dataset": str(data.get("dataset", "heldout_v1")),
        "sealed_at": datetime.now(UTC).strftime("%Y-%m-%d"),
        "cipher": CIPHER,
        "artifact_version_pin": str(data.get("artifact_version_pin", "")),
        "case_count": len(cases),
        "refusal_count": sum(1 for c in cases if c.get("expected_refusal")),
        "shapes": dict(sorted(shapes.items())),
        "sha256_ciphertext": sha256_hex(ciphertext),
        "sha256_plaintext": sha256_hex(plaintext),
    }


def seal(plaintext_path: Path, key_path: Path = DEFAULT_KEY_PATH) -> dict[str, Any]:
    """Encrypt an authored held-out set and write the ciphertext plus its manifest.

    The only function here that reads the author's plaintext. It returns the manifest, so a caller can
    print a full result without printing any case.
    """
    raw = plaintext_path.read_bytes()
    data: dict[str, Any] = json.loads(raw)
    if not data.get("cases"):
        raise SealError(f"{plaintext_path} holds no cases")

    ciphertext = encrypt(raw, key_path)
    manifest = summarise(data, ciphertext, raw)

    SEALED_PATH.write_bytes(ciphertext)
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def read_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        raise SealError(f"no manifest at {MANIFEST_PATH}; the set has not been sealed")
    data: dict[str, Any] = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    return data


def verify_seal() -> dict[str, Any]:
    """Check the ciphertext against the manifest. **Needs no key**, so CI can run it.

    This is the tamper check: a held-out set quietly regenerated after seeing results would change the
    ciphertext hash, and a benchmark you can rewrite after the fact is not a benchmark.
    """
    manifest = read_manifest()
    if not SEALED_PATH.exists():
        raise SealError(f"manifest exists but {SEALED_PATH} does not")

    actual = sha256_hex(SEALED_PATH.read_bytes())
    expected = manifest.get("sha256_ciphertext")
    if actual != expected:
        raise SealError(
            f"sealed set does not match its manifest: {actual[:12]}... != {str(expected)[:12]}..."
        )
    return manifest


def load_sealed(key_path: Path = DEFAULT_KEY_PATH) -> dict[str, Any]:
    """Decrypt into memory. Callers must not print what this returns."""
    if not SEALED_PATH.exists():
        raise SealError(f"nothing sealed at {SEALED_PATH}")
    plaintext = decrypt(SEALED_PATH.read_bytes(), key_path)

    manifest = read_manifest()
    if sha256_hex(plaintext) != manifest.get("sha256_plaintext"):
        raise SealError("decrypted content does not match the manifest's plaintext hash")

    data: dict[str, Any] = json.loads(plaintext)
    return data


# --- checking the sealed set without opening it ---------------------------------------------------


def _corpus_edges(
    case: dict[str, Any], node_id: str, store: InMemoryGraphStore
) -> set[tuple[str, str]]:
    """The edges the corpus holds for this case, read in the direction the case actually asked about.

    An unknown shape returns the empty set rather than raising, so a malformed case surfaces as a
    ``claims-diverged`` finding — an id and a code — instead of a traceback that would print the case.
    """
    shape = str(case.get("shape", "origins"))
    if shape == "descendants":
        return {(e.subject_id, e.object_id) for e in store.neighbors(node_id, Direction.INFLUENCED)}
    if shape == "path":
        end_id = str(case.get("expected_terminus", {}).get("node_id", ""))
        if not end_id:
            return set()
        return {(e.subject_id, e.object_id) for e in store.path(node_id, end_id)}
    return {(e.subject_id, e.object_id) for e in store.neighbors(node_id, Direction.INFLUENCED_BY)}


def check_against_corpus(data: dict[str, Any], store: InMemoryGraphStore) -> list[Finding]:
    """Validate held-out cases against the pinned corpus, reporting ids and codes only.

    The same agreement rules ``tests/test_gold_set.py`` applies to the gold set. Kept here rather than
    imported from the tests because the tests print assertion context on failure — which is exactly the
    disclosure this module exists to prevent.

    **Shape-aware since 2026-08-14, and it was not before.** This function read ``store.neighbors``
    with its default direction, which answers "what influenced this node" for every case regardless of
    what the case asked. A sealed set containing a descendants or path case would therefore have been
    reported as ``claims-diverged`` and ``refusal-flipped`` while being entirely correct — and because
    findings never disclose content, that false alarm would have been undebuggable without opening the
    set and destroying it. Found by ``tests/test_heldout_draw.py`` on its first run.
    """
    findings: list[Finding] = []

    pinned = str(data.get("artifact_version_pin", ""))
    if pinned != store.artifact_version:
        findings.append(Finding(data.get("dataset", "heldout"), "artifact-pin-moved"))

    for case in data.get("cases", []):
        case_id = str(case.get("case_id", "unknown"))
        node_id = str(case.get("expected_resolution", {}).get("node_id", ""))
        name = str(case.get("expected_resolution", {}).get("name", ""))

        hits = store.search(name)
        if not hits or hits[0].id != node_id:
            findings.append(Finding(case_id, "resolution-drift"))

        expected = {(c["subject_id"], c["object_id"]) for c in case.get("expected_claims", [])}
        actual = _corpus_edges(case, node_id, store)
        if actual != expected:
            findings.append(Finding(case_id, "claims-diverged"))

        if bool(actual) is bool(case.get("expected_refusal")):
            findings.append(Finding(case_id, "refusal-flipped"))

        path = set(case.get("expected_path", []))
        if not path:
            findings.append(Finding(case_id, "path-missing"))
        if any(store.get_node(n) is None for n in path):
            findings.append(Finding(case_id, "path-node-not-in-corpus"))
        if node_id and node_id not in path:
            findings.append(Finding(case_id, "path-missing-subject"))
        for claim in case.get("expected_claims", []):
            if claim["subject_id"] not in path or claim["object_id"] not in path:
                findings.append(Finding(case_id, "path-narrower-than-claims"))
                break

    return findings


# --- CLI ----------------------------------------------------------------------------------------


def _cmd_seal(args: argparse.Namespace) -> int:
    manifest = seal(Path(args.plaintext), Path(args.key))
    print(json.dumps(manifest, indent=2))
    print(f"\nsealed -> {SEALED_PATH}")
    print("The plaintext is untouched. Move it off this machine or delete it, and back up the key.")
    return 0


def _cmd_verify(_: argparse.Namespace) -> int:
    manifest = verify_seal()
    print(f"sealed set matches its manifest: {manifest['case_count']} cases, {manifest['shapes']}")
    return 0


def _cmd_check(args: argparse.Namespace) -> int:
    store = InMemoryGraphStore.from_directory(artifact_directory())
    findings = check_against_corpus(load_sealed(Path(args.key)), store)
    if not findings:
        print(f"sealed set still agrees with artifact {store.artifact_version}")
        return 0
    print(f"{len(findings)} problem(s) against artifact {store.artifact_version}:")
    for finding in findings:
        print(f"  {finding}")
    print("\nIds and codes only, by design. Opening the set to see more destroys it.")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="heldout", description=__doc__.splitlines()[0])
    parser.add_argument("--key", default=str(DEFAULT_KEY_PATH), help="path to the key file")
    subs = parser.add_subparsers(dest="command", required=True)

    seal_cmd = subs.add_parser("seal", help="encrypt an authored held-out set")
    seal_cmd.add_argument("plaintext", help="path to the authored JSON, outside this repo")
    seal_cmd.set_defaults(func=_cmd_seal)

    subs.add_parser(
        "verify", help="check the ciphertext against its manifest (no key)"
    ).set_defaults(func=_cmd_verify)
    subs.add_parser("check", help="validate the sealed set against the corpus").set_defaults(
        func=_cmd_check
    )

    args = parser.parse_args(argv)
    try:
        result: int = args.func(args)
    except SealError as exc:
        print(f"error: {exc}")
        return 2
    return result


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
