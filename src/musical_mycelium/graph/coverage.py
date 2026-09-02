"""Coverage as a recorded quantity, not a disclaimer.

Scope-doc DoD #7. The corpus skews Western, anglophone and recent **by construction** — it is built from
English Wikipedia prose over Wikidata's P737 — and ``CLAUDE.md`` requires that bias to be *visible in
output* rather than footnoted. This module turns it into numbers.

**The absences are the measurement, not a gap in it.** 28 of 169 genres carry no inception date and 48
carry no country of origin. Those two counts are the honest answer to "how thin are the early eras" and
"how Western is this", and they are reported first rather than buried under the eras that *are* covered.

**Concentration is not absence, and this module reports both halves for that reason.** The corpus is
dense in post-war anglophone material — and it also spans 1,500 years (medieval and classical music at
500, opera and Baroque at 1600) across 29 distinct places, with 43 genres naming no US or UK connection
at all: kuduro, bachata, cadence-lypso, bossa nova, Mizrahi music, Anatolian rock, Manila sound,
Krautrock, kayōkyoku. Quoting ``top_country_share`` alone invites "so it is only Western music", which
is false. ``distinct_countries`` and ``genres_without_us_or_uk`` are the counterweight, and they are not
optional garnish — a bias figure presented without them misdescribes the corpus in the other direction.

**The counterweight is held to the same standard as the bias figure, which is why it moved.** It read 44
until 2026-08-07, when a review found ``UK drill -> Brixton`` counting as "names no UK" — P495 records
places, not countries, and an exact-string test cannot tell a London district from a foreign one. See
:data:`PLACE_TO_COUNTRY`. Overstating the counterweight flatters the corpus exactly as much as
understating the bias would, and this module exists to do neither.

**Genre axis only, and stated rather than implied.** P571 and P495 are genre properties; an artist's
equivalents are different properties entirely (date of birth, country of citizenship) and are not
ingested. Reporting one number over both axes would let 804 unmeasured artist nodes dilute a genre
coverage figure toward zero and read as a much thinner corpus than it is.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from musical_mycelium.graph.schema import (
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    Artifact,
)

#: Era buckets, chosen once and fixed so the numbers stay comparable across corpus versions.
#:
#: The boundaries are **not** neutral and should not be presented as if they were: they are dense where
#: this corpus is dense (post-war popular music) and coarse where it is thin (everything before 1900 in
#: one bucket). That shape is itself a statement about what the corpus can and cannot talk about.
ERA_BOUNDS: tuple[tuple[str, int, int], ...] = (
    ("pre-1900", -9999, 1899),
    ("1900-1949", 1900, 1949),
    ("1950-1969", 1950, 1969),
    ("1970-1989", 1970, 1989),
    ("1990-2009", 1990, 2009),
    ("2010-", 2010, 9999),
)

#: Wikidata time-precision codes, for reading ``Node.inception_precision``.
PRECISION_CENTURY = 7
PRECISION_DECADE = 8
PRECISION_YEAR = 9

#: The two places this corpus is densest in, named explicitly so ``genres_without_us_or_uk`` means
#: something checkable rather than resting on an undefined notion of "Western". Deliberately just these
#: two: they are the measured concentration, not a judgement about which music is central.
ANGLOPHONE_CORE = frozenset({"United States", "United Kingdom"})

#: P495 does not promise a *country*. It promises whatever a Wikidata editor put there, and this corpus
#: contains sub-national places (``Brixton``), supranational ones (``Europe``, ``Scandinavia``) and
#: dependencies (``Hawaii``, ``French West Indies``). An exact-string test against
#: :data:`ANGLOPHONE_CORE` therefore reads a London district as "names no UK" — which inflated
#: ``genres_without_us_or_uk`` to 44 when the honest figure is 43. Caught 2026-08-07 in review.
#:
#: **Only entries that change the US/UK test belong here.** ``Europe`` and ``Scandinavia`` are genuinely
#: multi-country and must NOT be folded into either core country: doing so would assert a UK origin the
#: source never claimed, which is the opposite error and the worse one. They stay as they are and simply
#: count as neither.
#:
#: Applied to the US/UK test only, never to :attr:`Coverage.countries`, which stays a faithful record of
#: the labels the source actually carries.
PLACE_TO_COUNTRY: dict[str, str] = {
    "Brixton": "United Kingdom",
}


def _country_set(labels: tuple[str, ...]) -> set[str]:
    """Place labels normalised far enough to answer the US/UK question, and no further."""
    return {PLACE_TO_COUNTRY.get(label, label) for label in labels}


def era_of(year: int) -> str:
    for name, low, high in ERA_BOUNDS:
        if low <= year <= high:
            return name
    return "unknown"


@dataclass(frozen=True, slots=True)
class Coverage:
    """What the corpus can and cannot speak about, measured on the genre axis.

    Every field is a measurement of one pinned artifact. None is a target. They move whenever the
    corpus does, which is why they are recomputed rather than remembered.
    """

    #: Genre nodes considered. The denominator for everything below.
    genres: int

    #: Genres with no P571 at all. **Reported before the era histogram on purpose** — an era breakdown
    #: that silently omits the undated makes the covered eras look more complete than they are.
    without_inception: int

    #: Genres with no P495 at all, for the same reason.
    without_country: int

    #: Genre count per era bucket, plus ``"unknown"`` for the undated. Sums to ``genres``.
    eras: dict[str, int]

    #: How many dated genres carry a precision *coarser than a year* — 8 (decade) or 7 (century).
    #: Non-zero means some era assignments rest on a rounded value, and the era histogram should be
    #: read as approximate at its edges rather than exact.
    coarser_than_year: int

    #: Genre count per country label. A genre credited to two countries counts once for each, so this
    #: sums to more than ``genres`` minus ``without_country``.
    countries: dict[str, int]

    #: How many distinct places appear at all. Reported next to the concentration figures because
    #: concentration and absence are **different claims**, and quoting only the former invites the
    #: latter to be inferred.
    distinct_countries: int

    #: Genres that name a place and name **neither** the US nor the UK. The honest counterweight to
    #: ``top_country_share``: the corpus is dense in anglophone material, not devoid of anything else.
    #:
    #: A count of genres, deliberately, **not** a sum of country mentions. Adding the US total to the
    #: UK total double-counts every genre credited to both and inflates the apparent concentration —
    #: that error briefly stood at "93, or 77%" on 2026-08-06 before the arithmetic was checked.
    #:
    #: The membership test runs over :func:`_country_set`, not the raw labels, because P495 carries
    #: places rather than countries: ``UK drill -> Brixton`` counted as "names no UK" and put this at
    #: **44 until 2026-08-07, when the honest figure is 43**. A counterweight figure that overstates
    #: the counterweight is the same failure as one that understates the bias.
    genres_without_us_or_uk: int

    #: Genres that are never the **subject** of an ``influenced_by`` edge: the corpus records nothing
    #: about where they came from. **Direction matters and this is the project's named failure mode** —
    #: ``subject influenced_by object``, so this is not a count of genres that influenced nothing.
    #:
    #: Moved here from ``web/src/corpus-facts.json`` at v0.6.0. It was computed in the frontend during
    #: phase 5 only because putting it in ``Coverage`` is an edit to a serialized contract every eval
    #: number reads, which phase 5's DoD 9 forbade.
    genres_without_recorded_origins: int

    #: Genres touching exactly one ``influenced_by`` edge in either direction. The commonest state.
    genres_with_one_connection: int

    #: The largest number of ``influenced_by`` edges on any single genre. Small in absolute terms, and
    #: saying so is the point: this corpus is broad and shallow.
    busiest_genre_connections: int

    #: Degree histogram over the genre axis, keyed by degree as a string so it survives JSON. Every
    #: genre appears in exactly one bucket, so the values sum to ``genres``.
    connections: dict[str, int]

    #: The single most-credited country and its share of genres that have any country at all. The
    #: blunt version of "this corpus is not global", expressed without inventing a category like
    #: "Western" that nobody has defined.
    top_country: str
    top_country_share: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "genres": self.genres,
            "without_inception": self.without_inception,
            "without_country": self.without_country,
            "eras": self.eras,
            "coarser_than_year": self.coarser_than_year,
            "countries": self.countries,
            "distinct_countries": self.distinct_countries,
            "genres_without_us_or_uk": self.genres_without_us_or_uk,
            "top_country": self.top_country,
            "top_country_share": self.top_country_share,
        }


def analyse(artifact: Artifact) -> Coverage:
    """Measure coverage over the genre axis of one artifact."""
    genres = [node for node in artifact.nodes if node.kind == NODE_KIND_GENRE]

    eras: Counter[str] = Counter()
    countries: Counter[str] = Counter()
    without_inception = 0
    without_country = 0
    coarser = 0
    without_us_or_uk = 0

    for node in genres:
        if node.inception_year is None:
            without_inception += 1
            eras["unknown"] += 1
        else:
            eras[era_of(node.inception_year)] += 1
            if node.inception_precision is not None and node.inception_precision < PRECISION_YEAR:
                coarser += 1

        if not node.countries:
            without_country += 1
        else:
            countries.update(node.countries)
            # Normalised for this test only — see PLACE_TO_COUNTRY. The recorded label stays verbatim.
            if not ANGLOPHONE_CORE & _country_set(node.countries):
                without_us_or_uk += 1

    # Density, over INFLUENCE edges only. ``plays_genre`` is deliberately excluded and this is the
    # load-bearing line: membership edges outnumber influence edges roughly three to one at v0.6.0, so
    # counting them here would report a corpus three times denser in the one dimension this project
    # claims to measure. Density is about what the corpus knows of derivation, not about how many
    # artists were tagged.
    genre_ids = {node.id for node in genres}
    degree: Counter[str] = Counter()
    origins: Counter[str] = Counter()
    for edge in artifact.edges:
        if edge.predicate != PREDICATE_INFLUENCED_BY:
            continue
        if edge.subject_id in genre_ids and edge.object_id in genre_ids:
            degree[edge.subject_id] += 1
            degree[edge.object_id] += 1
            origins[edge.subject_id] += 1

    histogram: Counter[str] = Counter()
    for node in genres:
        histogram[str(degree.get(node.id, 0))] += 1

    # Every bucket present, including the empty ones. A missing key reads as "not measured" and this
    # is measured — the same rule ``Artifact.verification_counts`` follows.
    era_counts = {name: eras.get(name, 0) for name, _, _ in ERA_BOUNDS}
    era_counts["unknown"] = eras.get("unknown", 0)

    with_country = len(genres) - without_country
    top_country, top_count = countries.most_common(1)[0] if countries else ("", 0)
    share = round(top_count / with_country, 3) if with_country else 0.0

    return Coverage(
        genres=len(genres),
        distinct_countries=len(countries),
        genres_without_us_or_uk=without_us_or_uk,
        genres_without_recorded_origins=sum(1 for n in genres if origins.get(n.id, 0) == 0),
        genres_with_one_connection=sum(1 for n in genres if degree.get(n.id, 0) == 1),
        busiest_genre_connections=max((degree.get(n.id, 0) for n in genres), default=0),
        connections=dict(sorted(histogram.items(), key=lambda kv: int(kv[0]))),
        without_inception=without_inception,
        without_country=without_country,
        eras=era_counts,
        coarser_than_year=coarser,
        countries=dict(countries.most_common()),
        top_country=top_country,
        top_country_share=share,
    )
