"""Prose-check tests, built from the edges that actually broke the 7/31 checker.

Every fixture here reproduces a **real** defect from `docs/graph-semantics.md` 4.6-4.8, with a known
correct answer recorded during the phase-1 hand-verification. That is the point: a synthetic fixture
proves the code does what it does, while these prove it does what hand-reading 28 edges said it should.

The three inflating defects each get a test that fails on the old implementation:

1. Category tags, navboxes and reference titles counted as body prose. `MARKUP_ONLY` is the pure case.
2. `Western swing <- swing` scored 28 hits by matching the "swing" inside its own title.
3. `disco house` sitelinks to a title that redirects to `French house`, so the checker read a different
   genre's article and scored confident false support.

Plus the counter-defect, which runs the other way and under-accepts, and the taxonomy tell from 4.8.

**One documented claim did not survive being run against the real articles on 2026-08-04**, which is why
these fixtures are annotated rather than trusted: `graph-semantics.md` 4.6 says both `groove metal` edges
have zero genuine prose, and they have 6 and 7. See `MARKUP_ONLY` for what that changed.

No network. `check_edge` takes an already-fetched `Article`, which is why the analysis layer is pure.
"""

from __future__ import annotations

import pytest

from musical_mycelium.ingest.prosecheck import (
    Article,
    Tier,
    check_edge,
    count_taxonomic,
    find_mentions,
    has_taxonomic_lead,
    name_variants,
    sitelink_matches_subject,
    strip_markup,
    stylistic_origins,
)

# --- fixtures, each reproducing one documented defect ------------------------------------------------

#: Defect 1, in its pure form: an article whose *only* occurrences of the object are a navbox, two
#: categories, a reference title and an appendix link. The prose describes the genre without ever
#: naming it, so the correct answer is ORPHAN and the old stripper scored it PROSE.
#:
#: **Not the groove metal article**, despite `docs/graph-semantics.md` 4.6 citing it as this defect's
#: example. Measured live on 2026-08-04, that article carries 6 genuine prose mentions of "heavy metal";
#: markup stripping takes it from 12 hits to 6 rather than to 0. Defect 1 is real and the stripper does
#: real work — 71% of that article's raw wikitext is markup — but groove metal is a section 4.7 case
#: (prose that does not assert influence), not a section 4.6 one. See `test_markup_only_mentions`.
MARKUP_ONLY = """\
{{Infobox music genre
| name = Groove metal
| stylistic_origins = {{hlist|[[Thrash metal]]|[[Hardcore punk]]}}
}}
'''Groove metal''' is a style that emerged in the early 1990s. Its bands slowed the tempo of their
predecessors and emphasised mid-paced, syncopated riffing.<ref>{{cite book|title=The Heavy Metal
Encyclopedia|page=44}}</ref>

== See also ==
* [[List of heavy metal bands]]

== References ==
{{reflist}}

{{Heavy metal}}
[[Category:Heavy metal genres]]
[[Category:American styles of music]]
"""

#: Defect 2. Two occurrences of the bare object label ("swing") and several of the subject label, which
#: contains it. Only the standalone occurrences are evidence.
WESTERN_SWING = """\
{{Infobox music genre
| name = Western swing
| stylistic_origins = [[Swing music|Swing]], [[Country music|country]]
}}
'''Western swing''' is a subgenre of country music. Western swing bands played for dancers, and
Western swing was popular across the Southwest. The style drew directly on swing, whose big-band
arrangements its fiddlers adapted for string ensembles.
"""

#: The counter-defect. Both of these are genuinely supported edges that exact-label matching scores at
#: zero, because prose drops the generic suffix the Wikidata label carries.
COUNTRY_ROCK = """\
'''Country rock''' is a genre that fuses rock and country, and it emerged in the late 1960s.
"""

DUBSTEP = """\
'''Dubstep''' is characterised by sparse dub production and a heavy emphasis on sub-bass.
"""

#: Section 4.8. A P737 edge whose only support is taxonomic. The prose check structurally cannot reject
#: this — "is a subgenre of Y" contains a real, findable mention of Y — so the most it can do is flag it.
EXTREME_METAL = """\
'''Extreme metal''' is a loosely defined umbrella term for a number of related heavy metal subgenres.
"""

#: The honest negative: the object is named in the infobox and nowhere in the body. This is the
#: acid-jazz-and-disco catch that produced the three-tier split in the first place.
INFOBOX_ONLY_ARTICLE = """\
{{Infobox music genre
| name = Acid jazz
| stylistic_origins = [[Jazz]], [[Funk]], [[Disco]]
}}
'''Acid jazz''' developed in the London club scene, drawing on jazz and funk.
"""


def article(wikitext: str, title: str = "Subject") -> Article:
    return Article(requested_title=title, resolved_title=title, wikitext=wikitext)


# --- defect 1: markup counted as prose ---------------------------------------------------------------


def test_strip_markup_removes_categories_navboxes_and_references() -> None:
    body = strip_markup(MARKUP_ONLY)

    assert "Category:" not in body
    assert "cite book" not in body
    assert "Heavy Metal Encyclopedia" not in body, "reference titles are full of genre names"
    assert "reflist" not in body
    assert "syncopated riffing" in body, "genuine prose must survive"


def test_strip_markup_truncates_at_the_first_appendix_heading() -> None:
    body = strip_markup(MARKUP_ONLY)
    assert "List of heavy metal bands" not in body


def test_markup_only_mentions_are_an_orphan_not_prose() -> None:
    """The headline regression: every occurrence of the object is markup, so there is no evidence."""
    result = check_edge(
        subject_id="Q241662",
        object_id="Q38848",
        subject_label="groove metal",
        object_label="heavy metal music",
        article=article(MARKUP_ONLY, "Groove metal"),
        object_title="Heavy metal music",
    )

    assert result.tier is Tier.ORPHAN
    assert result.prose_hits == 0
    assert not result.usable
    assert "never mentions the object" in result.exclusion_reason


def test_strip_markup_handles_nested_templates() -> None:
    """A regex cannot: a lazy match closes at the inner brace, a greedy one eats the article."""
    text = "{{Infobox|a={{hlist|x|y}}|b=z}} Real prose here."
    assert strip_markup(text).strip() == "Real prose here."


def test_strip_markup_keeps_wikilink_display_text() -> None:
    """`[[blues rock|blues-rock]]` reads as "blues-rock" and that is what a human reads as prose."""
    assert "blues-rock" in strip_markup("It grew out of [[blues rock|blues-rock]] in Britain.")
    assert "blues rock" in strip_markup("It grew out of [[blues rock]] in Britain.")


def test_strip_markup_drops_file_captions() -> None:
    assert "Jazz" not in strip_markup("[[File:x.jpg|thumb|A [[Jazz]] band]] Prose.")


# --- defect 2: self-match ----------------------------------------------------------------------------


def test_find_mentions_discards_the_object_inside_the_subject_label() -> None:
    """`Western swing <- swing`: the article was matching against its own title."""
    body = strip_markup(WESTERN_SWING)

    unmasked = find_mentions(body, ["swing"], [])
    masked = find_mentions(body, ["swing"], ["Western swing"])

    assert len(unmasked) > len(masked), "without masking the subject title inflates the count"
    assert len(masked) == 1
    assert "big-band" in masked[0].sentence


def test_masking_does_not_discard_a_longer_object_inside_a_shorter_subject() -> None:
    """The reverse direction. Substring replacement gets this wrong; containment does not.

    `swing <- Western swing` must keep every "Western swing", because the longer object match is not
    contained in the shorter subject match even though the strings overlap.
    """
    body = "Swing later gave rise to Western swing in the Southwest."
    assert len(find_mentions(body, ["Western swing"], ["swing"])) == 1


def test_western_swing_survives_as_prose_with_one_supporting_sentence() -> None:
    result = check_edge(
        subject_id="Q1730388",
        object_id="Q203775",
        subject_label="Western swing",
        object_label="swing",
        article=article(WESTERN_SWING, "Western swing"),
        object_title="Swing music",
    )

    assert result.tier is Tier.PROSE
    assert result.prose_hits == 1
    assert result.sentences and "big-band" in result.sentences[0]


# --- defect 3: redirect collapse ---------------------------------------------------------------------


def test_a_redirected_article_is_excluded_not_read() -> None:
    """`disco house` forwards to `French house`. Reading it produced confident FALSE support."""
    redirected = Article(
        requested_title="Disco house",
        resolved_title="French house",
        tier=Tier.REDIRECTED,
        detail="'Disco house' redirects to 'French house'",
    )
    result = check_edge(
        subject_id="Q360596",
        object_id="Q58339",
        subject_label="disco house",
        object_label="disco",
        article=redirected,
    )

    assert result.tier is Tier.REDIRECTED
    assert not result.usable
    assert "French house" in result.exclusion_reason, "the target is recorded so it can be rescued"


# --- defect 4: the entity's label and its sitelink name different people -----------------------------


def test_a_mislinked_entity_is_excluded_rather_than_read() -> None:
    """The real case, found on the artist axis 2026-08-05.

    Wikidata's ``Q58462848`` is labelled *TheGrefg* and its English sitelink points at the *Lola
    Indigo* article. They are collaborators and two different people. Nothing here redirects, so
    defect 3's guard is blind to it, and reading that article would score a stranger's influences.
    """
    mislinked = Article(
        requested_title="Lola Índigo",
        resolved_title="Lola Índigo",
        wikitext="Lola Índigo is a Spanish singer influenced by flamenco and pop.",
    )
    result = check_edge(
        subject_id="Q58462848",
        object_id="Q000000",
        subject_label="TheGrefg",
        object_label="flamenco",
        article=mislinked,
    )

    assert result.tier is Tier.MISLINKED
    assert not result.usable
    assert "TheGrefg" in result.exclusion_reason
    assert "Lola Índigo" in result.exclusion_reason, "both names are recorded so it can be audited"


def test_a_disambiguated_title_is_not_a_mislink() -> None:
    """`David Gray` -> `David Gray (British musician)` is the same person and must survive. The guard
    that cannot tell a disambiguator from a wrong entity would reject most of the artist axis."""
    assert sitelink_matches_subject("David Gray (British musician)", "David Gray")
    assert sitelink_matches_subject("Blink-182", "Blink-182")
    assert sitelink_matches_subject("Rosalía", "Rosalia"), "diacritics are folded"
    assert sitelink_matches_subject("", "anyone"), "an absent title is not evidence of a mislink"


def test_an_alias_rescues_a_stage_name() -> None:
    """A performer whose article sits at a stage name is under-described, not mislinked — so the
    curated aliases are checked before flagging. This is the guard's known false-positive direction."""
    assert sitelink_matches_subject("Lady Gaga", "Stefani Germanotta", ("Lady Gaga",))
    assert not sitelink_matches_subject("Lady Gaga", "Stefani Germanotta", ("Miss Germanotta",))


# --- the counter-defect: exact matching under-accepts -------------------------------------------------


def test_the_short_forms_that_matter_come_from_wikidata_aliases() -> None:
    """The three short forms the removed stem rule was written to produce. Wikidata publishes all of
    them, verified against the live entities on 2026-08-04."""
    assert "country" in name_variants("country music", aliases=["country"])
    assert "dub" in name_variants("dub music", aliases=["dub"])
    assert "heavy metal" in name_variants("heavy metal music", aliases=["heavy metal"])


def test_name_variants_keeps_a_bare_label_intact() -> None:
    """ "jazz" must not become "" and "swing" must not lose anything."""
    assert name_variants("jazz") == ("jazz",)
    assert "swing" in name_variants("swing")


def test_name_variants_are_longest_first() -> None:
    """Ordering is load-bearing: `find_mentions` attributes a hit to the first variant that matches, so
    a shortest-first list would report a full-label match as an alias rescue."""
    variants = name_variants("heavy metal music", aliases=["metal", "heavy metal"])
    assert variants[0] == "heavy metal music"
    assert variants.index("heavy metal") < variants.index("metal")
    assert list(variants) == sorted(variants, key=len, reverse=True)


def test_name_variants_dedupes_case_variants() -> None:
    """The enwiki title differs from the label only by capitalisation on most genres, and matching is
    case-insensitive, so carrying both would double every variant list for nothing."""
    assert name_variants("heavy metal music", "Heavy metal music") == ("heavy metal music",)


def test_name_variants_derives_nothing_the_source_did_not_publish() -> None:
    """The removed stem rule, kept as a standing guard.

    It turned "country music" into "country" and "occult music" into "occult". Measured across the
    full 351-candidate population on 2026-08-04 that produced **three false accepts and zero true
    ones**, because Wikidata already publishes the short forms that matter as aliases. Anything
    derived here in future has to clear the bar that rule failed, and this test is what makes adding
    one back a deliberate act rather than a quiet one.
    """
    assert name_variants("country music") == ("country music",)
    assert name_variants("occult music") == ("occult music",)
    assert name_variants("traditional folk music") == ("traditional folk music",)


def test_country_rock_is_rescued_by_the_alias_not_by_a_derived_stem() -> None:
    """`fuses rock and country` supports the edge; exact-label matching alone scores it zero.

    The aliases passed here are the real ones on Q83440. The earlier version of this test omitted
    them, which is exactly why the stem rule looked necessary: the fixture was missing data the live
    fetch has always supplied, since `fetch_entities` requests aliases in the same round trip.
    """
    result = check_edge(
        subject_id="Q613408",
        object_id="Q83440",
        subject_label="country rock",
        object_label="country music",
        article=article(COUNTRY_ROCK, "Country rock"),
        object_title="Country music",
        object_aliases=("country and western", "country & western", "country"),
    )

    assert result.tier is Tier.PROSE
    assert "country" in result.matched_names


def test_dubstep_is_rescued_by_the_alias() -> None:
    """Q212688 publishes `dub` as an alias of `dub music`. That is the whole rescue."""
    result = check_edge(
        subject_id="Q20474",
        object_id="Q212688",
        subject_label="dubstep",
        object_label="dub music",
        article=article(DUBSTEP, "Dubstep"),
        object_title="Dub music",
        object_aliases=("dub",),
    )

    assert result.tier is Tier.PROSE
    assert "dub" in result.matched_names


def test_without_an_alias_a_short_form_is_not_invented() -> None:
    """The resulting under-accept is real, and is the safe direction.

    `occult rock <- occult music` scored PROSE only because "occult" was derived, and every one of
    those hits was the *theme*, not a genre name. Refusing to invent the short form makes this edge an
    honest ORPHAN instead of a confident false accept.
    """
    result = check_edge(
        subject_id="Q1",
        object_id="Q2",
        subject_label="occult rock",
        object_label="occult music",
        article=article(
            "The genre commonly incorporates lyrics referencing the occult.", "Occult rock"
        ),
        object_title="Occult music",
    )

    assert result.tier is Tier.ORPHAN


# --- section 4.8: taxonomy riding on the influence predicate ------------------------------------------


def test_extreme_metal_is_prose_but_flagged_taxonomic() -> None:
    """The check cannot reject this and must not pretend to. It can flag it for triage.

    The `heavy metal` alias is required and is real (Q38848, verified 2026-08-04): the article says
    "heavy metal subgenres", never the full label "heavy metal music". Before the stem rule was
    removed this fixture passed without it, which quietly hid the fact that the match depends on
    Wikidata publishing the short form.
    """
    result = check_edge(
        subject_id="Q465978",
        object_id="Q38848",
        subject_label="extreme metal",
        object_label="heavy metal music",
        article=article(EXTREME_METAL, "Extreme metal"),
        object_title="Heavy metal music",
        object_aliases=("heavy metal",),
    )

    assert result.tier is Tier.PROSE, (
        "the mention is real; the check cannot see that it is taxonomic"
    )
    assert result.taxonomic_lead
    assert result.taxonomic_hits == 1


def test_the_flag_anchors_on_the_lead_sentence_not_on_all_of_them() -> None:
    """Measured against the real articles on 2026-08-04, an all-sentences rule never fires.

    The real `extreme metal` article pairs its umbrella-term lead with an ordinary descriptive sentence,
    so requiring every sentence to be taxonomic scored the canonical 4.8 case clean. Any article long
    enough to be worth checking has some non-taxonomic sentence mentioning the object.
    """
    taxonomic_lead = ["Bebop is a subgenre of jazz.", "It was played in Harlem clubs."]
    historical_lead = ["Bebop developed out of swing in the 1940s.", "It is a subgenre of jazz."]

    assert has_taxonomic_lead(taxonomic_lead)
    assert not has_taxonomic_lead(historical_lead)
    assert not has_taxonomic_lead([])

    assert count_taxonomic(taxonomic_lead) == 1
    assert count_taxonomic(historical_lead) == 1, (
        "the count is direction-blind; the lead flag is not"
    )


def test_a_derivation_lead_is_not_flagged() -> None:
    """`groove metal <- thrash metal` leads with "primarily derived from thrash metal" — history, and
    one flag has to get both groove metal edges right in opposite directions."""
    assert not has_taxonomic_lead(
        ["The genre is primarily derived from thrash metal, but played in slower tempos."]
    )
    assert has_taxonomic_lead(["Groove metal is a subgenre of heavy metal music."])


# --- tiers -------------------------------------------------------------------------------------------


def test_infobox_only_is_not_prose() -> None:
    """The acid-jazz catch: "disco" appears once, inside the infobox, and the prose never discusses it."""
    result = check_edge(
        subject_id="Q221772",
        object_id="Q58339",
        subject_label="acid jazz",
        object_label="disco",
        article=article(INFOBOX_ONLY_ARTICLE, "Acid jazz"),
        object_title="Disco",
    )

    assert result.tier is Tier.INFOBOX_ONLY
    assert not result.usable


def test_stylistic_origins_reads_from_raw_wikitext() -> None:
    """It must run before `strip_markup` removes the infobox, or the weak signal disappears entirely."""
    origins = stylistic_origins(INFOBOX_ONLY_ARTICLE)
    assert "Disco" in origins
    assert stylistic_origins(strip_markup(INFOBOX_ONLY_ARTICLE)) == ""


def test_a_genuine_prose_edge_passes() -> None:
    result = check_edge(
        subject_id="Q221772",
        object_id="Q8341",
        subject_label="acid jazz",
        object_label="jazz",
        article=article(INFOBOX_ONLY_ARTICLE, "Acid jazz"),
        object_title="Jazz",
    )

    assert result.tier is Tier.PROSE
    assert result.usable
    assert result.exclusion_reason == ""


@pytest.mark.parametrize(
    ("tier", "expected"),
    [
        (Tier.NO_ARTICLE, "no English Wikipedia article"),
        (Tier.FETCH_FAILED, "could not be read"),
    ],
)
def test_non_evidence_tiers_short_circuit_with_a_reason(tier: Tier, expected: str) -> None:
    """A network failure must never be recorded as a disconfirmation."""
    result = check_edge(
        subject_id="Q1",
        object_id="Q2",
        subject_label="x",
        object_label="y",
        article=Article(requested_title="X", tier=tier, detail="X"),
    )

    assert result.tier is tier
    assert not result.usable
    assert expected in result.exclusion_reason
