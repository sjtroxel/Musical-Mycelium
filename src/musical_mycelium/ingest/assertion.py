"""The influence-assertion filter: does this sentence *assert* influence, or merely mention the object?

The prose check answers "is the object named in genuine body prose". On the genre axis that is close
enough to the right question, because naming another genre in a genre article is usually about
derivation. **On the artist axis it is not close at all.** Artists are named constantly for tours,
covers, studios, session work, band membership and chart comparisons, so a mention is cheap. Measured
on a 300-candidate slice, the prose check accepted 73 artist edges and the accepted evidence included
a recording truck (`Deep Purple <- The Rolling Stones`, via the *Rolling Stones Mobile Studio*), the
English pronoun "them" (`Deep Purple <- Them`), a cover version, a support slot and a band-membership
list. Ingesting on that would have written roughly 1,200 confidently wrong edges into a corpus whose
entire genre graph is 133.

**Three outcomes, not two** (scope doc A6.1, decided by sjtroxel 2026-08-05). Hand-reading the sample
turned up a class sitting between assertion and noise, at roughly a quarter of it: *"as a teenager he
listened to Alice Cooper"*, *"he is a fan of Xavier Naidoo"*, *"his sister took him to the Apollo to
see James Brown"*. These record **formative exposure** and never assert influence. Music journalism
uses them precisely to convey it and Wikidata editors visibly cite them, so discarding them throws away
a quarter of the genuine signal — but counting them silently would mean "grounded" sometimes rests on a
listening habit. So they are ingested at a **weaker verification tier and flagged**, the same move
``verification: HAND | PROSE_AUTO`` already makes for the genre axis.

## Provenance of these patterns, stated because it bounds what the numbers mean

**They were derived by reading the 60 hand-labelled sentences in
``eval/datasets/artist_assertion_labels_v1.json``.** Measured against that same set they score 98%
precision and 94% recall on keep-vs-drop, and that figure is therefore a **training number and an upper
bound**, not a validation number. `.claude/rules/evals.md` requires a held-out set that development
never looked at, and this module is frozen *before* that set is labelled precisely so the held-out
measurement is honest. Do not quote the 98% as the filter's accuracy.

One failure mode is known to be **under-represented** in the derivation set: peer co-mention with
influence language present, as in *"Deep Purple are cited as one of the pioneers of hard rock and heavy
metal, along with Led Zeppelin and Black Sabbath"* — influence vocabulary, zero assertion about Led
Zeppelin. The stratified sample caps at two rows per subject, which fixed one bias and may have hidden
this one. If the held-out set shows it is common, a direction test is required and these patterns are
not sufficient.
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from enum import StrEnum

#: Language that asserts influence outright: the subject says, or the article says of the subject, that
#: the object shaped them. Derived from the labelled set, longest-standing forms first.
ASSERT_PATTERNS = re.compile(
    r"""
      influenc            # influence, influenced, influences, influential
    | inspir              # inspired, inspiration, inspirations
    | cited\s             # "cited X as an influence"
    | credit              # "credits X", "credited X as"
    | idol                # "his main idol is X"
    | enthrall
    | \bimpressed\sby
    | spiritual\sheir
    | drew\s(?:from|on)
    | learned\sfrom
    | \bteacher
    """,
    re.IGNORECASE | re.VERBOSE,
)

#: Language that records formative exposure without asserting influence. Kept, flagged, and ingested at
#: the weaker tier rather than discarded — A6.1.
EXPOSURE_PATTERNS = re.compile(
    r"""
      listened\sto
    | listening
    | \bfan\sof
    | discovered
    | immers              # "immersing himself in the music of"
    | introduced\sto
    | \bheard\b
    | watched
    """,
    re.IGNORECASE | re.VERBOSE,
)


class Assertion(StrEnum):
    """What the evidence does. Mirrors the three-valued label set.

    **These are not three points on one scale.** Two are objective and the middle one is subjective
    (scope doc A6.3), and that distinction predicts this module's error shape rather than merely
    describing it: everything the filter misses lands in ``EXPOSURE``, because a judgement call cannot
    be pattern-matched. Do not read a low ``EXPOSURE`` recall as a defect to be tuned away.
    """

    #: **Objective.** The text explicitly states influence. Bounded vocabulary — *influenced, inspired,
    #: cited, credits, idol* — which is exactly why it is detectable at 98% precision.
    ASSERTS = "ASSERTS"

    #: **Subjective.** The floor, agreed 2026-08-05: *the text records real-world contact or engagement
    #: between the two, short of a stated influence claim.* Duets, tours, covers, shared households and
    #: documented rivalry all qualify — every one is contact. A critic comparing two artists does
    #: **not**: that is evidence about the music, not a record of the people meeting it.
    #:
    #: The floor exists so the tier does not become a dumping ground. "Any plausible connection" would
    #: admit anything carrying a name match, and the tier would stop carrying information.
    EXPOSURE = "EXPOSURE"

    #: **Objective.** No connection is recorded anywhere in the article. Checkable by absence.
    NONE = "NONE"


def classify(sentence: str) -> Assertion:
    """Classify one supporting sentence. Deterministic, free, and order-dependent by design.

    ``ASSERTS`` is tested first: a sentence carrying both vocabularies ("he grew up listening to X and
    cites him as an influence") is an assertion, and the weaker reading must not win just because its
    pattern appears earlier in the string.
    """
    if not sentence or not sentence.strip():
        return Assertion.NONE
    if ASSERT_PATTERNS.search(sentence):
        return Assertion.ASSERTS
    if EXPOSURE_PATTERNS.search(sentence):
        return Assertion.EXPOSURE
    return Assertion.NONE


#: Strongest first. Extra evidence can only ever raise a verdict, never lower it: a second sentence
#: cannot un-assert what a first one asserted.
_STRENGTH = (Assertion.ASSERTS, Assertion.EXPOSURE, Assertion.NONE)


def classify_all(sentences: Sequence[str]) -> Assertion:
    """The **strongest** verdict across every sentence that mentions the object.

    This is the correct unit and ``classify`` alone is not. Found 2026-08-05, by sjtroxel asking
    whether Sam Ryder's article mentioned Elton John anywhere else: the first matching sentence read
    *"He caught the attention of musicians such as Elton John"* — the wrong direction entirely — while
    the second read *"He **cites** David Bowie, Elton John, Freddie Mercury and Queen among his music
    **influences**."* Judging the first sentence alone gets that edge exactly backwards.

    **38% of prose-accepted artist edges carry more than one matching sentence** (measured over 188 on
    2026-08-05; one carried sixteen), so this is the common case, not an edge case.
    """
    verdicts = {classify(s) for s in sentences}
    for level in _STRENGTH:
        if level in verdicts:
            return level
    return Assertion.NONE


def supports_edge(sentences: str | Sequence[str]) -> bool:
    """Whether the edge may be ingested at all. ``EXPOSURE`` counts — at a weaker tier (A6.1)."""
    if isinstance(sentences, str):
        sentences = [sentences]
    return classify_all(sentences) is not Assertion.NONE
