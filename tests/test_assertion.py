"""Assertion-filter tests, built from the sentences that made the filter necessary.

Every fixture here is a **real** sentence from the artist axis with a hand-assigned label recorded in
`eval/datasets/artist_assertion_labels_v1.json`. The junk cases are the ones the prose check accepted
on its own, which is the whole reason this module exists.
"""

from __future__ import annotations

from musical_mycelium.ingest.assertion import (
    Assertion,
    classify,
    classify_all,
    supports_edge,
)


def test_explicit_influence_language_asserts() -> None:
    for sentence in (
        "Kawakami has cited the British rock band Oasis and its guitarist Noel Gallagher as major "
        "influences on his musical style.",
        "Her musical influences include Whirr, Ovlov, Title Fight, the Cocteau Twins and Deftones.",
        "He was inspired to take up the tenor saxophone after hearing Coleman Hawkins on tour.",
        "His main idol is Art Tatum.",
    ):
        assert classify(sentence) is Assertion.ASSERTS


def test_formative_exposure_is_its_own_tier() -> None:
    """A6.1. Real signal, weaker claim — kept and flagged rather than discarded or counted as equal."""
    for sentence in (
        "As a teenager, he listened to rock bands like Hawkwind, Captain Beefheart and Alice Cooper.",
        "Growing up, Red listened to artists such as Gucci Mane, Lil Wayne and Nicki Minaj.",
        "He is a fan of James Blunt, James Morrison and Xavier Naidoo.",
    ):
        assert classify(sentence) is Assertion.EXPOSURE
        assert supports_edge(sentence)


def test_the_junk_the_prose_check_accepted_is_rejected() -> None:
    """Each of these was accepted by the prose check alone and is the reason this module exists."""
    for sentence in (
        "The album was due to be recorded at the Montreux Casino using the Rolling Stones Mobile "
        "Studio, but a fire during a Frank Zappa concert destroyed the venue.",
        "Deep Purple were ranked number 22 on VH1's Greatest Artists of Hard Rock programme, and a "
        "poll ranked them fifth among the greatest.",
        "Guest stars on the album included the Wu-Tang Clan and Gregory Isaac.",
        "In 1964, they beat the Beatles as the number one United Kingdom band in two surveys.",
        "In 1999, the band recorded a cover of Big Star's 1972 song 'In the Street'.",
    ):
        assert classify(sentence) is Assertion.NONE
        assert not supports_edge(sentence)


def test_an_assertion_beats_an_exposure_cue_in_the_same_sentence() -> None:
    """Order is deliberate: the weaker reading must not win by appearing earlier in the string."""
    sentence = (
        "Beihold grew up listening to Feist and Fiona Apple, and cites Regina Spektor as among "
        "her influences."
    )
    assert classify(sentence) is Assertion.ASSERTS


def test_an_empty_sentence_supports_nothing() -> None:
    """The vacuous-truth guard `.claude/rules/evals.md` requires: absent evidence is not evidence."""
    assert classify("") is Assertion.NONE
    assert classify("   ") is Assertion.NONE
    assert not supports_edge("")


def test_the_strongest_sentence_wins() -> None:
    """The Sam Ryder case, which is why `classify_all` exists.

    The first matching sentence points the wrong way; the second asserts influence outright. Judging
    only the first gets the edge backwards, and 38% of accepted artist edges have more than one.
    """
    sentences = [
        "He caught the attention of musicians such as Elton John, Sia, Justin Bieber, and Alicia Keys.",
        "He cites David Bowie, Elton John, Freddie Mercury, and Queen among his music influences.",
    ]
    assert classify(sentences[0]) is Assertion.NONE
    assert classify_all(sentences) is Assertion.ASSERTS
    assert supports_edge(sentences)


def test_extra_evidence_never_weakens_a_verdict() -> None:
    strong = "He cites Queen among his influences."
    assert classify_all([strong]) is Assertion.ASSERTS
    assert classify_all([strong, "They later toured Japan."]) is Assertion.ASSERTS
    assert classify_all(["He grew up listening to Queen.", strong]) is Assertion.ASSERTS


def test_no_sentences_supports_nothing() -> None:
    assert classify_all([]) is Assertion.NONE
    assert not supports_edge([])
