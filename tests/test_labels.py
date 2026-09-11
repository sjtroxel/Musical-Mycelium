"""The `mul` label fix, phase 7.6 step 1: every fetch path reads `en`, then `mul`.

The shapes below are recorded from Wikidata's ``wbgetentities`` on 2026-09-11, trimmed to the fields
read. Mozart (``Q254``) is the case that found the bug: his label lives only under `mul`, so every fetch
that asked for `en` got an empty string, and screening excluded him as ``MISLINKED``.
"""

from __future__ import annotations

from typing import Any
from urllib.parse import parse_qs, urlparse

import pytest

from musical_mycelium.ingest import coverage, prosecheck, wikidata
from musical_mycelium.ingest.labels import (
    SPARQL_LABEL_LANGUAGES,
    WBGETENTITIES_LANGUAGES,
    entity_aliases,
    entity_label,
)

#: Mozart as Wikidata returned him on 2026-09-11: no `en` label at all.
MOZART: dict[str, Any] = {
    "id": "Q254",
    "lastrevid": 1,
    "labels": {"mul": {"language": "mul", "value": "Wolfgang Amadeus Mozart"}},
    "aliases": {
        "en": [{"language": "en", "value": "Mozart"}],
        "mul": [
            {"language": "mul", "value": "Mozart"},
            {"language": "mul", "value": "Wolfgang Amadeus Mozart"},
            {"language": "mul", "value": "W. A. Mozart"},
        ],
    },
    "sitelinks": {"enwiki": {"site": "enwiki", "title": "Wolfgang Amadeus Mozart"}},
}

#: Beethoven carries both, identical. The common case, and the one that must not move.
BEETHOVEN: dict[str, Any] = {
    "id": "Q255",
    "lastrevid": 2,
    "labels": {
        "en": {"language": "en", "value": "Ludwig van Beethoven"},
        "mul": {"language": "mul", "value": "Ludwig van Beethoven"},
    },
    "aliases": {"en": [{"language": "en", "value": "Beethoven"}]},
    "sitelinks": {"enwiki": {"site": "enwiki", "title": "Ludwig van Beethoven"}},
}

#: `en` and `mul` disagreeing. Synthetic: `en` must win, so no label already in an artifact moves.
DISAGREEING: dict[str, Any] = {
    "id": "Q1",
    "lastrevid": 3,
    "labels": {
        "en": {"language": "en", "value": "the English label"},
        "mul": {"language": "mul", "value": "the default label"},
    },
}

#: Neither language. The empty string it has always been, which `Node` still refuses.
UNLABELLED: dict[str, Any] = {
    "id": "Q2",
    "lastrevid": 4,
    "labels": {"de": {"value": "nur Deutsch"}},
}


# --- the helper -------------------------------------------------------------------------------------


def test_a_mul_only_entity_gets_its_label() -> None:
    """DoD 1's test: the exact shape that lost Mozart now yields his name."""
    assert entity_label(MOZART) == "Wolfgang Amadeus Mozart"


def test_en_wins_when_both_exist() -> None:
    assert entity_label(BEETHOVEN) == "Ludwig van Beethoven"
    assert entity_label(DISAGREEING) == "the English label"


def test_no_en_or_mul_label_is_still_the_empty_string() -> None:
    assert entity_label(UNLABELLED) == ""
    assert entity_label({}) == ""


def test_aliases_merge_en_then_mul_without_repeats_or_the_label() -> None:
    assert entity_aliases(MOZART) == ("Mozart", "W. A. Mozart")


def test_the_request_asks_for_both_languages() -> None:
    assert WBGETENTITIES_LANGUAGES.split("|") == ["en", "mul"]
    assert SPARQL_LABEL_LANGUAGES.split(",") == ["en", "mul"]


# --- the three fetch paths ----------------------------------------------------------------------------


def _languages(url: str) -> str:
    return parse_qs(urlparse(url).query)["languages"][0]


def test_prosecheck_fetch_entities_reads_mul(monkeypatch: pytest.MonkeyPatch) -> None:
    """The artist axis's path, the one that actually excluded Mozart."""
    requested: list[str] = []

    def fake_get(url: str, **_: Any) -> dict[str, Any]:
        requested.append(url)
        return {"entities": {"Q254": MOZART, "Q255": BEETHOVEN}}

    monkeypatch.setattr(prosecheck, "_get", fake_get)
    monkeypatch.setattr(prosecheck.time, "sleep", lambda _: None)

    entities = prosecheck.fetch_entities(["Q254", "Q255"])

    assert _languages(requested[0]) == "en|mul"
    assert entities["Q254"].label == "Wolfgang Amadeus Mozart"
    assert entities["Q254"].enwiki_title == "Wolfgang Amadeus Mozart"
    assert entities["Q254"].aliases == ("Mozart", "W. A. Mozart")
    assert entities["Q255"].label == "Ludwig van Beethoven"


def test_wikidata_fetch_entities_reads_mul(monkeypatch: pytest.MonkeyPatch) -> None:
    """The genre-facts path, which the membership layer also labels genres through."""
    requested: list[str] = []

    def fake_get(url: str, **_: Any) -> dict[str, Any]:
        requested.append(url)
        return {"entities": {"Q254": MOZART}}

    monkeypatch.setattr(wikidata, "_get", fake_get)
    monkeypatch.setattr(wikidata, "sparql", lambda _query: [])
    monkeypatch.setattr(wikidata.time, "sleep", lambda _: None)

    facts = wikidata.fetch_entities(["Q254"])

    assert _languages(requested[0]) == "en|mul"
    assert facts["Q254"].label == "Wolfgang Amadeus Mozart"


def test_the_coverage_query_falls_back_to_mul() -> None:
    """The SPARQL label service, which labels countries of origin."""
    assert f'wikibase:language "{SPARQL_LABEL_LANGUAGES}"' in coverage.coverage_query(["Q9759"])
