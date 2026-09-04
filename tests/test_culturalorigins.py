"""The ``cultural_origins`` parser, phase 6 step 6.

**The tests that matter here are the precision ones.** A parser that reads "1950s" as the year 1950
produces a confident, precise-looking, wrong number — and in a corpus that publishes its own coverage
gaps that is worse than no date at all. ``Node.inception_precision`` exists because rendering a
decade-precision value as a year states something the source does not; this parser must not commit that
error with a new source to blame.

Every fixture below is a real value taken from a live article on 2026-09-04, not invented, so the tests
fail if Wikipedia's actual conventions differ from the ones assumed.
"""

from __future__ import annotations

import pytest

from musical_mycelium.ingest.culturalorigins import (
    PRECISION_CENTURY,
    PRECISION_DECADE,
    PRECISION_YEAR,
    extract_field,
    parse,
    parse_date,
    parse_places,
    strip_markup,
)

COUNTRIES = frozenset(
    {"United States", "United Kingdom", "Cuba", "Philippines", "Puerto Rico", "Israel", "Jamaica"}
)


# --- precision, which is the whole point ---------------------------------------------------------


@pytest.mark.parametrize(
    ("text", "year", "precision"),
    [
        ("1990s", 1990, PRECISION_DECADE),
        ("Early 2010s", 2010, PRECISION_DECADE),
        ("Late 1980s", 1980, PRECISION_DECADE),
        ("mid-1970s", 1970, PRECISION_DECADE),
        ("17th century", 1600, PRECISION_CENTURY),
        ("Late 19th century", 1800, PRECISION_CENTURY),
        ("Late 18th century", 1700, PRECISION_CENTURY),
        ("1971", 1971, PRECISION_YEAR),
    ],
)
def test_a_date_keeps_the_precision_it_was_stated_at(text: str, year: int, precision: int) -> None:
    assert parse_date(text) == (year, precision)


def test_a_decade_is_never_read_as_a_year() -> None:
    """``1950s`` contains ``1950``. Reading it as year-precision is the error this module exists to
    avoid, and it is the single most likely way for this parser to be quietly wrong."""
    year, precision = parse_date("1950s, Manila, Philippines")
    assert (year, precision) == (1950, PRECISION_DECADE)
    assert precision != PRECISION_YEAR


def test_a_century_is_never_read_as_a_two_digit_year() -> None:
    """``17th century`` contains ``17`` — which is exactly what DBpedia's extractor returns for it."""
    assert parse_date("17th century, Puerto Rico") == (1600, PRECISION_CENTURY)


def test_the_century_convention_matches_the_corpus_not_an_invention() -> None:
    """``opera`` is 1600 at precision 7 and means the 17th century; ``mariachi`` 1800 means the 19th.

    So Nth century maps to ``(N - 1) * 100``. Checked against the corpus rather than assumed, because an
    off-by-one-century date would look entirely plausible in a lineage answer.
    """
    assert parse_date("17th century")[0] == 1600
    assert parse_date("19th century")[0] == 1800
    assert parse_date("12th century")[0] == 1100


def test_a_range_takes_the_earliest_value() -> None:
    """Real value from the Mizrahi music article. ``cultural_origins`` is about where a genre began."""
    assert parse_date("Late 1950s-Early 1960s, Israel.") == (1950, PRECISION_DECADE)


# --- refusing rather than guessing ---------------------------------------------------------------


@pytest.mark.parametrize(
    "text", ["Ancient, worldwide", "Indigenous music worldwide", "Alps region"]
)
def test_a_vague_era_yields_no_date_rather_than_a_guess(text: str) -> None:
    """These are real values. A corpus that publishes its coverage gaps must not fill one with a guess."""
    assert parse_date(text) == (None, None)


def test_a_place_with_no_date_yields_the_place_and_no_date() -> None:
    """``plena`` is exactly this: ``[[Puerto Rico]]`` and nothing temporal."""
    result = parse("[[Puerto Rico]]", COUNTRIES)
    assert result.year is None
    assert result.countries == ("Puerto Rico",)
    assert not result.has_date


# --- markup and places ---------------------------------------------------------------------------


def test_wikilinks_flatten_to_their_display_text() -> None:
    """``[[Captaincy General of Puerto Rico|Puerto Rico]]`` is what the ``bomba`` article actually says."""
    assert (
        strip_markup("17th century, [[Captaincy General of Puerto Rico|Puerto Rico]]")
        == "17th century, Puerto Rico"
    )


def test_citation_years_inside_refs_are_not_read_as_the_date() -> None:
    """A ``<ref>`` routinely contains a four-digit year. Stripping refs first is not cosmetic."""
    assert parse_date(strip_markup("1990s<ref>Smith, 1974, p. 12</ref>")) == (
        1990,
        PRECISION_DECADE,
    )


def test_only_country_labels_the_corpus_already_uses_are_accepted() -> None:
    """Conservative on purpose: ``Ibero-America`` and ``Metro Manila`` are not P495 country labels, and
    inventing one would put an unsourced geography into the published coverage numbers."""
    assert parse_places("Early 1940s, Ibero-America", COUNTRIES) == ()
    assert parse_places("1950s, Metro Manila, Philippines", COUNTRIES) == ("Philippines",)


def test_a_place_is_reported_once_even_if_named_twice() -> None:
    assert parse_places("Cuba, Cuba", COUNTRIES) == ("Cuba",)


# --- the field extractor -------------------------------------------------------------------------


def test_extract_field_reads_a_value_that_wraps_across_lines() -> None:
    """A line-based match silently truncates the place half, which is the quiet half of this parse."""
    wikitext = (
        "{{Infobox music genre\n"
        "| name = Bomba\n"
        "| cultural_origins = 17th century,\n"
        "  [[Puerto Rico]]\n"
        "| stylistic_origins = [[African music]]\n"
        "}}\n"
    )
    assert "Puerto Rico" in extract_field(wikitext)
    assert "stylistic_origins" not in extract_field(wikitext)


def test_extract_field_returns_empty_when_the_infobox_has_no_such_row() -> None:
    assert extract_field("{{Infobox music genre\n| name = Jingle\n}}") == ""


def test_parse_carries_the_raw_text_so_the_parse_is_checkable() -> None:
    """A reader must be able to see what the number was made from, rather than trust it."""
    result = parse("Late 1950s-Early 1960s, [[Israel]].", COUNTRIES)
    assert result.raw == "Late 1950s-Early 1960s, Israel."
    assert result.year == 1950
    assert result.countries == ("Israel",)


# --- defects found by running it against live articles, not by fixtures --------------------------


def test_an_empty_field_does_not_swallow_the_row_below_it() -> None:
    """``comedy music`` parsed as though its cultural origins were a list of instruments.

    ``| cultural_origins  =`` with an empty value, followed by ``| instruments = ...``. With ``\\s*``
    after the ``=`` the whitespace class crosses the newline and the capture runs on into the next
    field. Fixtures all had values, so only a live run could find this.
    """
    wikitext = (
        "{{Infobox music genre\n"
        "| cultural_origins  = \n"
        "| instruments       = {{hlist|Vocals|various instruments}}\n"
        "| popularity        = \n"
        "}}\n"
    )
    assert extract_field(wikitext) == ""


def test_a_country_is_found_when_it_is_not_its_own_comma_delimited_token() -> None:
    """``C-pop`` states "1920s China" with no comma. Splitting on punctuation missed it entirely."""
    assert parse_places("1920s China", frozenset({"China"})) == ("China",)


def test_common_country_abbreviations_resolve() -> None:
    """``hill country blues`` states "Mississippi, U.S." — the country is there, abbreviated."""
    assert parse_places("Mississippi, U.S.", frozenset({"United States"})) == ("United States",)
    assert parse_places("Early 1950s, US", frozenset({"United States"})) == ("United States",)


def test_a_country_name_inside_a_longer_word_does_not_match() -> None:
    """Word boundaries are load-bearing: ``Chinatown`` is not ``China``, and a substring match here
    would attach a country to a genre on the strength of a coincidence."""
    assert parse_places("Chinatown, San Francisco", frozenset({"China"})) == ()


def test_an_alias_is_not_matched_inside_a_longer_token() -> None:
    """``us`` is an alias for the United States and also the end of a great many words."""
    assert parse_places("Belarus", frozenset({"United States"})) == ()
    assert parse_places("various", frozenset({"United States"})) == ()
