"""``graph.coverage`` — the corpus skew as arithmetic.

Same two-layer shape as ``test_structure``: synthetic graphs whose answer is known by construction
carry the weight, and the assertions against the pinned corpus are a weaker second layer that pins what
v0.5.0 actually measures so a corpus change has to be acknowledged rather than absorbed.

Those pinned numbers are **measurements, not targets.** When a re-ingest moves them, update them here
and say so; do not treat the movement as a failure.
"""

from __future__ import annotations

import pytest

from musical_mycelium.graph.coverage import ERA_BOUNDS, analyse, era_of
from musical_mycelium.graph.memory import InMemoryGraphStore, artifact_directory
from musical_mycelium.graph.schema import (
    NODE_KIND_ARTIST,
    NODE_KIND_GENRE,
    Artifact,
    Node,
)

WHEN = "2026-08-06T00:00:00+00:00"


def node(
    qid: str,
    *,
    kind: str = NODE_KIND_GENRE,
    year: int | None = None,
    precision: int | None = None,
    countries: tuple[str, ...] = (),
) -> Node:
    return Node(
        id=qid,
        label=f"node {qid}",
        source="wikidata",
        source_id=qid,
        retrieved_at=WHEN,
        kind=kind,
        inception_year=year,
        inception_precision=precision,
        countries=countries,
    )


# --- known by construction ---------------------------------------------------------------------


def test_an_empty_corpus_measures_zero_rather_than_erroring() -> None:
    """The vacuous guard ``.claude/rules/evals.md`` requires. An empty corpus must report emptiness,
    not crash and not produce a healthy-looking default."""
    result = analyse(Artifact(nodes=(), edges=()))

    assert result.genres == 0
    assert result.without_inception == 0
    assert result.top_country == ""
    assert result.top_country_share == 0.0
    assert sum(result.eras.values()) == 0


def test_the_undated_are_counted_not_dropped() -> None:
    """The whole point of DoD #7. A genre with no P571 is the measurement, not a hole in it — so it
    appears in ``without_inception`` **and** as ``unknown`` in the era histogram. An era breakdown that
    silently omitted it would make the covered eras look more complete than they are."""
    result = analyse(Artifact(nodes=(node("Q1", year=1975), node("Q2")), edges=()))

    assert result.without_inception == 1
    assert result.eras["unknown"] == 1
    assert sum(result.eras.values()) == result.genres, "every genre lands in exactly one bucket"


def test_every_era_bucket_is_present_even_at_zero() -> None:
    """A missing key reads as "not measured" and this is measured — the same rule
    ``Artifact.verification_counts`` follows."""
    result = analyse(Artifact(nodes=(node("Q1", year=1975),), edges=()))

    assert set(result.eras) == {name for name, _, _ in ERA_BOUNDS} | {"unknown"}
    assert result.eras["pre-1900"] == 0


@pytest.mark.parametrize(
    ("year", "era"),
    [
        (500, "pre-1900"),
        (1899, "pre-1900"),
        (1900, "1900-1949"),
        (1969, "1950-1969"),
        (2026, "2010-"),
    ],
)
def test_era_boundaries_are_inclusive(year: int, era: str) -> None:
    assert era_of(year) == era


def test_a_genre_with_two_countries_counts_once_for_each() -> None:
    """P495 is genuinely multi-valued — one v0.5.0 genre is credited to both the US and the UK.
    Collapsing that to one country would invent a fact; so the country histogram sums to more than the
    number of genres that have any country at all, and that is correct rather than a bug."""
    result = analyse(
        Artifact(nodes=(node("Q1", countries=("United States", "United Kingdom")),), edges=())
    )

    assert result.countries == {"United States": 1, "United Kingdom": 1}
    assert result.without_country == 0
    assert sum(result.countries.values()) > result.genres - result.without_country


def test_coarse_precision_is_counted_so_the_eras_can_be_read_as_approximate() -> None:
    """19 of v0.5.0's dated genres carry decade or century precision. Rendering those as exact years
    would state something Wikidata does not."""
    result = analyse(
        Artifact(
            nodes=(
                node("Q1", year=1975, precision=9),
                node("Q2", year=1970, precision=8),
                node("Q3", year=1600, precision=7),
            ),
            edges=(),
        )
    )
    assert result.coarser_than_year == 2


def test_artist_nodes_are_not_in_the_genre_denominator() -> None:
    """P571 and P495 are genre properties; an artist's equivalents are different properties and are not
    ingested. Counting 804 never-asked artist nodes as "no country recorded" would dilute the genre
    figure toward zero and read as a far thinner corpus than it is."""
    result = analyse(
        Artifact(
            nodes=(
                node("Q1", year=1975, countries=("United States",)),
                node("Q9", kind=NODE_KIND_ARTIST),
                node("Q10", kind=NODE_KIND_ARTIST),
            ),
            edges=(),
        )
    )

    assert result.genres == 1
    assert result.without_country == 0, "the artists must not be counted as missing a country"


def test_top_country_share_is_of_those_that_have_one() -> None:
    """The denominator is genres with *any* country, not all genres. Dividing by all of them would
    understate the concentration by folding the unmeasured in with the diverse."""
    result = analyse(
        Artifact(
            nodes=(
                node("Q1", countries=("United States",)),
                node("Q2", countries=("United States",)),
                node("Q3", countries=("Japan",)),
                node("Q4"),
            ),
            edges=(),
        )
    )
    assert result.top_country == "United States"
    assert result.top_country_share == pytest.approx(2 / 3, abs=0.001)


# --- the pinned corpus -------------------------------------------------------------------------


@pytest.fixture(scope="module")
def store() -> InMemoryGraphStore:
    return InMemoryGraphStore.from_directory(artifact_directory())


def test_the_pinned_corpus_coverage(store: InMemoryGraphStore) -> None:
    """v0.6.0 as measured 2026-09-03. Update deliberately when the corpus moves; do not delete.

    **These numbers are the DoD #7 deliverable.** The corpus skews Western, anglophone and recent by
    construction, and this is that skew as arithmetic rather than as a disclaimer.

    v0.5.0, for comparison: 169 / 28 / 48 / 19. The membership crawl roughly tripled the genre count and
    the gaps grew with it -- ``without_inception`` 28 -> 131, ``without_country`` 48 -> 164. A bigger
    corpus is not a better-documented one, and these four numbers are where that shows.
    """
    c = store.coverage

    assert c.genres == 509
    assert c.without_inception == 131
    assert c.without_country == 164
    assert c.coarser_than_year == 51
    assert c.top_country == "United States"


def test_the_corpus_is_recent_and_says_so(store: InMemoryGraphStore) -> None:
    """Only 53 of 509 genres originate before 1950, against 147 in 1970-1989 alone. A product built on
    this corpus cannot speak about early music history, and the number is what makes that checkable
    rather than a matter of impression.

    **The multiple loosened at v0.6.0 and the bound was widened to match, which is the direction that
    needs saying out loud.** v0.5.0 was 13 against 47, a 3.6x concentration, and the assertion read
    ``> before_1950 * 3``. v0.6.0 is 53 against 147: still lopsided, but 2.8x. The corpus got *less*
    concentrated in the era it is worst at, so this bound is being relaxed because the measurement
    improved, not to accommodate a regression. If it ever has to be relaxed the other way, that is a
    finding and not a maintenance task.
    """
    c = store.coverage
    before_1950 = c.eras["pre-1900"] + c.eras["1900-1949"]

    assert before_1950 == 53
    assert c.eras["1970-1989"] > before_1950 * 2.5


def test_the_corpus_is_anglophone_dense_and_says_so(store: InMemoryGraphStore) -> None:
    """Dense, not exclusive — and the arithmetic has to say which.

    This assertion originally read ``countries["United States"] + countries["United Kingdom"] == 93``
    and called that 77% of the 121 country-bearing genres. **That was wrong**: it adds two country
    totals, so every genre credited to both is counted twice, inflating the apparent concentration.
    The honest figure is a count of *genres*.

    **Moved 77 -> 78 on 2026-08-07** when ``UK drill -> Brixton`` was found counting as "names no UK"
    (see ``coverage.PLACE_TO_COUNTRY``). Note the direction: correcting the place normalisation makes
    the corpus look *more* anglophone, not less. That is the point — the fix was applied because it was
    right, not because of which way it moved the number.

    **v0.6.0 moved the share the uncomfortable way: 78/121 = 0.64 became 253/345 = 0.73.** The
    membership crawl was seeded from the artists already in the corpus, and those artists are
    anglophone, so the genres it reached are more anglophone than the ones it started from. The corpus
    grew three times larger and got *more* concentrated, not less. ``top_country_share`` says the same
    thing from the other side, 0.421 -> 0.562.

    This is the number a coverage panel is most tempted to leave out, because two other figures moved
    the flattering way at the same time — distinct places 29 -> 50, genres naming neither US nor UK
    43 -> 92. All three are true and the honest report carries all three. The band below is widened to
    contain the measurement rather than to contain the claim.
    """
    c = store.coverage
    with_country = c.genres - c.without_country
    naming_us_or_uk = with_country - c.genres_without_us_or_uk

    assert with_country == 345
    assert naming_us_or_uk == 253
    assert 0.7 < naming_us_or_uk / with_country < 0.8


def test_the_corpus_is_not_only_anglophone_and_the_numbers_must_say_that_too(
    store: InMemoryGraphStore,
) -> None:
    """The counterweight, asserted so a bias figure can never ship without it.

    92 genres name no US or UK connection at all, across 50 distinct places — kuduro, bachata,
    cadence-lypso, bossa nova, Mizrahi music, Anatolian rock, Manila sound. **Concentration and absence
    are different claims**, and reporting only the first invites the second to be inferred. That
    inference was made on 2026-08-06 and corrected by sjtroxel, who was reading the corpus rather than
    the aggregate.

    **v0.6.0: 43 -> 92 and 29 -> 50.** Both counterweights grew, and neither cancels the concentration
    figure in the test above, which grew too. Quoting this pair without that one is the failure mode
    this docstring already warns about, pointed the other way.

    **43, not 44, since 2026-08-07.** ``UK drill``'s P495 is ``Brixton`` — a London district — which an
    exact-string test against ``ANGLOPHONE_CORE`` read as "names no UK". The counterweight figure gets
    audited as hard as the bias figure; see ``coverage.PLACE_TO_COUNTRY``.
    """
    c = store.coverage

    assert c.genres_without_us_or_uk == 92
    assert c.distinct_countries == 50


def test_a_sub_national_place_still_counts_toward_its_country() -> None:
    """The regression lock for the Brixton fix, on a synthetic corpus so it cannot drift with Wikidata.

    Both halves are asserted, because they pull in opposite directions: the recorded label stays
    **verbatim** (``countries`` is a faithful record of the source, and collapsing it would silently
    rewrite what Wikidata said), while the US/UK membership test **resolves** it.
    """
    artifact = Artifact(
        nodes=(
            node("Q1", countries=("Brixton",)),
            node("Q2", countries=("Angola",)),
        ),
        edges=(),
    )
    c = analyse(artifact)

    assert c.countries["Brixton"] == 1, "the recorded place label must not be rewritten"
    assert c.genres_without_us_or_uk == 1, "Angola only — Brixton resolves to the UK"


def test_a_supranational_place_is_folded_into_neither_country() -> None:
    """``Europe`` and ``Scandinavia`` must NOT resolve to the UK.

    Folding a multi-country label into a core country would assert an origin the source never claimed —
    the opposite error to the Brixton one, and the worse of the two. They count as neither.
    """
    artifact = Artifact(nodes=(node("Q1", countries=("Europe",)),), edges=())

    assert analyse(artifact).genres_without_us_or_uk == 1


def test_the_corpus_spans_far_more_than_the_post_war_era(store: InMemoryGraphStore) -> None:
    """The same correction on the time axis. The earliest genres date to 500 — medieval and classical
    music — with opera and Baroque at 1600 and blues at 1890. Thin is not empty, and "post-war" is a
    description of where the mass sits, never of what the corpus contains.

    6 -> 14 at v0.6.0."""
    c = store.coverage
    assert c.eras["pre-1900"] == 14
