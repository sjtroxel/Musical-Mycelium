"""The held-out seal: does it actually keep the set shut, and can it still be checked while shut.

These tests never touch the real sealed set's content. They build a synthetic one, seal it under a
throwaway key in ``tmp_path``, and assert the properties the mechanism claims. The single test that
touches the real artefact only verifies its hash — which needs no key and reads nothing.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import pytest

from musical_mycelium.eval import heldout
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory

pytestmark = pytest.mark.skipif(
    shutil.which("openssl") is None, reason="openssl is not installed on this machine"
)


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


@pytest.fixture
def key(tmp_path: Path) -> Path:
    path = tmp_path / "throwaway.key"
    path.write_bytes(b"not the real key, and never written into the repo\n")
    return path


@pytest.fixture
def dataset(store: InMemoryGraphStore) -> dict[str, Any]:
    """A synthetic held-out set built from a node the corpus really holds, so the corpus check has
    something true to agree with."""
    return {
        "dataset": "heldout_synthetic",
        "artifact_version_pin": store.artifact_version,
        "cases": [
            {
                "case_id": "heldout_synthetic_001",
                "query": "SECRET-QUERY-TEXT-THAT-MUST-NOT-LEAK",
                "shape": "origins",
                "expected_resolution": {"name": "blues rock", "node_id": "Q193355"},
                "expected_refusal": False,
                "expected_path": ["Q193355", "Q9759"],
                "expected_claims": [
                    {"subject_id": "Q193355", "predicate": "influenced_by", "object_id": "Q9759"}
                ],
            },
            {
                "case_id": "heldout_synthetic_002",
                "query": "ANOTHER-SECRET",
                "shape": "refusal",
                "expected_resolution": {"name": "blues", "node_id": "Q9759"},
                "expected_refusal": True,
                "expected_path": ["Q9759"],
                "expected_claims": [],
            },
        ],
    }


@pytest.fixture
def sealed_here(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Point the module's committed paths at tmp_path. Without this, sealing in a test would overwrite
    the real held-out set — which, once it exists, is unrecoverable."""
    monkeypatch.setattr(heldout, "SEALED_PATH", tmp_path / "heldout_v1.json.enc")
    monkeypatch.setattr(heldout, "MANIFEST_PATH", tmp_path / "heldout_v1.manifest.json")
    return tmp_path


# --- the cipher --------------------------------------------------------------------------------


def test_encrypt_then_decrypt_returns_the_original_bytes(key: Path) -> None:
    payload = b'{"cases": [{"case_id": "x"}]}'
    assert heldout.decrypt(heldout.encrypt(payload, key), key) == payload


def test_the_ciphertext_does_not_contain_the_plaintext(key: Path) -> None:
    """The point of the exercise. A grep over the repo must not surface a case."""
    payload = b"SECRET-QUERY-TEXT-THAT-MUST-NOT-LEAK"
    assert b"SECRET" not in heldout.encrypt(payload, key)


def test_the_wrong_key_cannot_open_it(tmp_path: Path, key: Path) -> None:
    other = tmp_path / "other.key"
    other.write_bytes(b"a different key entirely\n")
    with pytest.raises(heldout.SealError):
        heldout.decrypt(heldout.encrypt(b'{"cases": []}', key), other)


def test_encrypting_twice_gives_different_ciphertext(key: Path) -> None:
    """``-salt`` is on, so identical plaintext does not produce identical bytes. Without it, committing
    two versions would reveal that the set had not changed between them."""
    payload = b'{"cases": [{"case_id": "x"}]}'
    assert heldout.encrypt(payload, key) != heldout.encrypt(payload, key)


# --- the manifest is public, so it must disclose nothing -------------------------------------------


def test_manifest_holds_only_the_allowed_keys(dataset: dict[str, Any], key: Path) -> None:
    """The manifest is committed in plaintext. A field added carelessly to ``summarise`` is a
    disclosure, so the permitted set is asserted rather than trusted."""
    raw = json.dumps(dataset).encode()
    manifest = heldout.summarise(dataset, heldout.encrypt(raw, key), raw)
    assert set(manifest) == set(heldout.MANIFEST_KEYS)


def test_manifest_contains_no_case_content(dataset: dict[str, Any], key: Path) -> None:
    """Aggregates only: no query, no node id, no label. Checked by looking for the actual strings."""
    raw = json.dumps(dataset).encode()
    rendered = json.dumps(heldout.summarise(dataset, heldout.encrypt(raw, key), raw))

    for forbidden in ("SECRET", "Q193355", "Q9759", "blues", "heldout_synthetic_001"):
        assert forbidden not in rendered, f"the manifest leaked {forbidden!r}"


def test_manifest_records_composition_without_naming_anything(
    dataset: dict[str, Any], key: Path
) -> None:
    raw = json.dumps(dataset).encode()
    manifest = heldout.summarise(dataset, heldout.encrypt(raw, key), raw)
    assert manifest["case_count"] == 2
    assert manifest["refusal_count"] == 1
    assert manifest["shapes"] == {"origins": 1, "refusal": 1}


# --- sealing, and detecting a set that was quietly rewritten ---------------------------------------


def test_seal_writes_a_ciphertext_that_verifies(
    dataset: dict[str, Any], key: Path, sealed_here: Path, tmp_path: Path
) -> None:
    plaintext = tmp_path / "authored.json"
    plaintext.write_text(json.dumps(dataset), encoding="utf-8")

    manifest = heldout.seal(plaintext, key)
    assert heldout.verify_seal()["sha256_ciphertext"] == manifest["sha256_ciphertext"]


def test_a_tampered_ciphertext_fails_verification(
    dataset: dict[str, Any], key: Path, sealed_here: Path, tmp_path: Path
) -> None:
    """A held-out set that can be regenerated after seeing the results is not a held-out set. The
    manifest is what makes rewriting it detectable rather than invisible."""
    plaintext = tmp_path / "authored.json"
    plaintext.write_text(json.dumps(dataset), encoding="utf-8")
    heldout.seal(plaintext, key)

    corrupted = bytearray(heldout.SEALED_PATH.read_bytes())
    corrupted[-1] ^= 0xFF
    heldout.SEALED_PATH.write_bytes(bytes(corrupted))

    with pytest.raises(heldout.SealError, match="does not match its manifest"):
        heldout.verify_seal()


def test_load_sealed_round_trips_through_the_manifest(
    dataset: dict[str, Any], key: Path, sealed_here: Path, tmp_path: Path
) -> None:
    plaintext = tmp_path / "authored.json"
    plaintext.write_text(json.dumps(dataset), encoding="utf-8")
    heldout.seal(plaintext, key)

    assert heldout.load_sealed(key) == dataset


def test_sealing_leaves_no_plaintext_beside_the_ciphertext(
    dataset: dict[str, Any], key: Path, sealed_here: Path, tmp_path: Path
) -> None:
    """Sealing streams through memory. Nothing decrypted may be left in the datasets directory."""
    plaintext = tmp_path / "authored.json"
    plaintext.write_text(json.dumps(dataset), encoding="utf-8")
    heldout.seal(plaintext, key)

    written = {p.name for p in sealed_here.iterdir()}
    assert written == {
        "authored.json",
        "throwaway.key",
        "heldout_v1.json.enc",
        "heldout_v1.manifest.json",
    }


# --- checking it while it stays shut ---------------------------------------------------------------


def test_a_set_that_agrees_with_the_corpus_reports_nothing(
    dataset: dict[str, Any], store: InMemoryGraphStore
) -> None:
    assert heldout.check_against_corpus(dataset, store) == []


def test_a_diverged_case_is_reported_by_id_and_code_only(
    dataset: dict[str, Any], store: InMemoryGraphStore
) -> None:
    """The property that makes the set checkable while sealed: a real failure report that discloses
    nothing. Phase 6 moves the corpus, and a held-out case whose neighbours shift has to be findable
    without opening the file."""
    dataset["cases"][0]["expected_claims"] = [
        {"subject_id": "Q193355", "predicate": "influenced_by", "object_id": "Q11401"}
    ]
    findings = heldout.check_against_corpus(dataset, store)

    codes = {f.code for f in findings}
    assert "claims-diverged" in codes

    rendered = " ".join(str(f) for f in findings)
    for forbidden in ("SECRET", "blues rock", "Q11401"):
        assert forbidden not in rendered, f"a finding leaked {forbidden!r}"


def test_an_artifact_bump_is_caught(dataset: dict[str, Any], store: InMemoryGraphStore) -> None:
    dataset["artifact_version_pin"] = "9.9.9"
    assert any(f.code == "artifact-pin-moved" for f in heldout.check_against_corpus(dataset, store))


def test_a_path_narrower_than_its_claims_is_caught(
    dataset: dict[str, Any], store: InMemoryGraphStore
) -> None:
    dataset["cases"][0]["expected_path"] = ["Q193355"]
    assert any(
        f.code == "path-narrower-than-claims" for f in heldout.check_against_corpus(dataset, store)
    )


# --- the real one, hash only -----------------------------------------------------------------------


def test_the_committed_sealed_set_matches_its_manifest() -> None:
    """Runs in CI, needs no key, and reads no content. Skips until the set is authored, and the skip is
    the honest state: **the held-out 10 does not exist yet**, and it must be authored before the first
    live model run or the property is destroyed permanently."""
    if not heldout.MANIFEST_PATH.exists():
        pytest.skip("the held-out set has not been authored and sealed yet")
    heldout.verify_seal()
