"""The Wikipedia prose check: a **disconfirmation** test for Wikidata P737 edges.

His method, 2026-07-31. The asymmetry that makes it work:

  Wikipedia **cannot confirm** a P737 edge — it shares an editorial ecosystem with Wikidata, so
  agreement is close to the graph agreeing with itself.

  But Wikipedia **can disconfirm** one, and strongly, for exactly that reason. If Wikidata asserts
  ``A <- B`` and A's own article never mentions B, the edge is an orphan: unsupported even by its
  sibling source.

Three tiers, because infobox agreement is weak evidence — genre infoboxes are casually edited, rarely
cited, and plausibly the thing Wikidata harvested in the first place. ``PROSE`` (the object appears in
body text outside the infobox) beats ``INFOBOX_ONLY`` beats ``ORPHAN``. The circularity hypothesis was
tested and rejected at 11 of 227 infobox-only (``docs/graph-semantics.md`` 4.3), so the check is sound.

**No LLM, no cost, fully deterministic.** That is what lets one piece of code be a corpus filter, a
displayed coverage metric, and a Tier 1 eval at once (``.claude/rules/evals.md``).

## What is hardened here, and why it had to be

The 7/31 scripts scored 158 of 351 edges as PROSE. Phase 1 then hand-read 28 of those and rejected 7,
and three of the rejections were **defects in the checker, all of which inflate the tier**
(``docs/graph-semantics.md`` 4.6). Running the original code over the full corpus would have written a
confidently wrong artifact:

1. **Markup counted as prose.** The old stripper removed only ``{{Infobox…}}``, so ``[[Category:Heavy
   metal genres]]``, navbox templates and ``<ref>`` citation titles all counted as body mentions. Fixed
   by :func:`strip_markup`, which retains 29% of the raw wikitext on a typical genre article and halves
   the hit count on the ``groove metal`` article (12 raw to 6 genuine, measured 2026-08-04).

   *Correction, 2026-08-04:* ``docs/graph-semantics.md`` 4.6 cites both ``groove metal`` edges as having
   **zero** genuine prose. Measured live, that is wrong — they have 6 and 7. The defect is real and this
   stripper is necessary, but groove metal is a 4.7 case (prose that does not assert influence), not a
   4.6 one, and ``groove metal <- thrash metal`` is a **false rejection**: its lead sentence reads
   *"primarily derived from thrash metal"*, which is the exact claim shape the product promises.
2. **Self-match.** ``Western swing <- swing`` scored 28 hits because ``\\bswing\\b`` matches the "swing"
   inside "Western swing" — the article matching against its own title. Fixed by
   :func:`find_mentions`, which discards any object match contained inside a subject-label match.
3. **Redirect collapse, the worst of the three.** ``disco house`` sitelinks to a title that redirects to
   **French house**. The old fetcher passed ``redirects=1`` and never checked where it landed, so it read
   a different genre's article, found "disco" discussed throughout, and produced **confident false
   support**. Fixed by :func:`resolve_article`, which reports the redirect instead of following it
   silently.

A fourth defect runs the other way: exact-label matching **under**-accepts. ``country rock <- country
music`` scores zero because the lead says "fuses rock and country", and ``dubstep <- dub music`` scores
zero because the article says "sparse dub production". :func:`name_variants` tries **Wikidata aliases**
for this, and every result records *which* name matched so the correction is auditable rather than
assumed.

*That audit was run on 2026-08-04, and it removed a rule.* An earlier version of this module also
generated a **stem** by stripping generic trailing words ("country music" to "country"), on the
assumption that the aliases alone would not reach those two edges. Measured across the full 351-candidate
population, the assumption was wrong twice over: Wikidata already publishes ``country`` as an alias of
``country music`` and ``dub`` as an alias of ``dub music``, so the aliases rescue both edges on their
own — and the stem rule's *entire* contribution to the accepted corpus was **three false accepts**
(``folk punk <- traditional folk music`` matching "more traditional spaces"; ``J-core <- anime music``
matching the medium; ``occult rock <- occult music`` matching the theme). Zero true positives, three
false positives, so it is gone. The lesson is the same one groove metal taught the day before: the tier
is not the evidence, and a rule that has never been measured is a guess with good manners.

## What this check still cannot do, and must not claim to

It cannot tell whether a sentence **asserts influence** or merely mentions the object. Of the 7 phase-1
rejections, 4 failed on exactly that: synonymy, contradiction, taxonomy, and a mention running the wrong
way in time all read as PROSE (``docs/graph-semantics.md`` 4.7). ``extreme metal <- heavy metal`` is the
canonical case — *"an umbrella term for a number of related heavy metal subgenres"* is taxonomy riding on
the influence predicate, and "is a subgenre of Y" contains a real, findable mention of Y.

:attr:`ProseCheck.taxonomic_lead` is a **heuristic flag for triage, not a verdict**: it reports whether
the article's *lead* supporting sentence reads as category membership, which is where a definitional
claim lives. It does not reject anything on its own.

So the tier over-accepts by roughly a fifth on hand-reading, and the honest output of this module is a
measured rate with a known error bar in both directions — never a claim that the check is exact.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

WD_API = "https://www.wikidata.org/w/api.php"
WP_API = "https://en.wikipedia.org/w/api.php"

#: Wikimedia expects a contactable User-Agent and this project is in no position to be sloppy about it.
USER_AGENT = "MusicalMycelium/0.2 (https://github.com/sjtroxel; sjtroxel@protonmail.com)"


class Tier(StrEnum):
    """The outcome for one candidate edge.

    ``PROSE``, ``INFOBOX_ONLY`` and ``ORPHAN`` are the three evidence tiers and match
    ``graph.schema.PROSE_TIERS``. The rest are **exclusion reasons** — states in which no evidence could
    be gathered at all — and never reach an ``Edge``, whose ``prose_tier`` only ever holds ``PROSE``.
    Keeping them in one enum means every candidate lands in exactly one bucket and the counts add up.
    """

    PROSE = "PROSE"
    INFOBOX_ONLY = "INFOBOX_ONLY"
    ORPHAN = "ORPHAN"

    #: The subject has no English Wikipedia article. 35% of the 351 at the 7/31 measurement.
    NO_ARTICLE = "NO_ARTICLE"

    #: The subject's sitelink redirects to a *different* title. Defect 3: reading it would score another
    #: genre's article as support for this edge.
    REDIRECTED = "REDIRECTED"

    #: The article could not be read. Distinct from ORPHAN on purpose — absent evidence is not evidence
    #: of absence, and a network failure must never be recorded as a disconfirmation.
    FETCH_FAILED = "FETCH_FAILED"


#: Tiers that carry actual evidence about the edge. The others describe why we could not look.
EVIDENCE_TIERS = frozenset({Tier.PROSE, Tier.INFOBOX_ONLY, Tier.ORPHAN})

#: Appendix headings. Everything from the first one to the end of the article is citation apparatus,
#: navigation and listing — a rich source of genre names that are not prose about the subject.
_APPENDIX_HEADINGS = (
    "see also",
    "references",
    "notes",
    "citations",
    "footnotes",
    "sources",
    "bibliography",
    "further reading",
    "external links",
)

#: Phrases that mark a sentence as taxonomic rather than historical. Triage only — see the module
#: docstring. Drawn from the real phase-1 rejections, not invented.
_TAXONOMY_MARKERS = (
    "subgenre",
    "sub-genre",
    "umbrella term",
    "is a form of",
    "is a style of",
    "is a type of",
    "is a category of",
    "is a subset of",
    "broad term",
    "blanket term",
    "collectively known as",
)

_COMMENT_RE = re.compile(r"<!--.*?-->", re.S)
_REF_RE = re.compile(r"<ref[^>]*?/>|<ref[^>]*?>.*?</ref>", re.S | re.I)
_TAG_BLOCK_RE = re.compile(
    r"<(gallery|timeline|math|score|syntaxhighlight|imagemap)[^>]*>.*?</\1>", re.S | re.I
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_HEADING_RE = re.compile(r"^\s*(={2,6})\s*(.+?)\s*\1\s*$", re.M)
_EMPHASIS_RE = re.compile(r"'{2,5}")
_STYLISTIC_ORIGINS_RE = re.compile(
    r"\|\s*stylistic_origins\s*=(.*?)(?=\n\s*\|\s*\w+\s*=|\n\}\})", re.S | re.I
)
_SENTENCE_SPLIT_RE = re.compile(r"(?<=[.!?])\s+")


# --- pure analysis ---------------------------------------------------------------------------------
# Everything below this line is a pure function of its arguments. That is deliberate: it is what lets
# each of the three defects have a real regression test built from the article text that produced it,
# with no network in the test suite.


def _strip_nested(text: str, opener: str, closer: str) -> str:
    """Remove ``opener … closer`` regions, honouring nesting.

    A regex cannot do this: ``{{Infobox … {{nowrap|x}} … }}`` closes at the wrong brace with a lazy
    match and swallows the article with a greedy one. Templates and tables both nest routinely.

    On unbalanced markup the remainder of the text is dropped. That is the safe direction — it can only
    *remove* evidence, and this module's entire purpose is to stop the tier being inflated.
    """
    out: list[str] = []
    depth = 0
    i = 0
    while i < len(text):
        if text.startswith(opener, i):
            depth += 1
            i += len(opener)
        elif depth and text.startswith(closer, i):
            depth -= 1
            i += len(closer)
        else:
            if not depth:
                out.append(text[i])
            i += 1
    return "".join(out)


def _match_double_bracket(text: str, start: int) -> int:
    """Index of the ``]]`` closing the ``[[`` at ``start``, or -1. Nesting-aware."""
    depth = 0
    i = start
    while i < len(text):
        if text.startswith("[[", i):
            depth += 1
            i += 2
        elif text.startswith("]]", i):
            depth -= 1
            if depth == 0:
                return i
            i += 2
        else:
            i += 1
    return -1


def _process_wikilinks(text: str) -> str:
    """Drop file/category links; reduce every other link to the text a reader sees.

    ``[[blues rock|blues-rock]]`` displays "blues-rock", and the displayed text is what a human reads as
    prose, so that is what gets searched. ``[[Category:…]]`` is defect 1's biggest single contributor and
    is removed outright. File captions go with them: they are short, they list genre names, and dropping
    them errs toward under-accepting, which is this module's safe direction.
    """
    out: list[str] = []
    i = 0
    while i < len(text):
        if text.startswith("[[", i):
            close = _match_double_bracket(text, i)
            if close == -1:
                out.append(text[i])
                i += 1
                continue
            inner = text[i + 2 : close]
            if inner.lstrip().lower().startswith(("file:", "image:", "category:")):
                i = close + 2
                continue
            inner = _process_wikilinks(inner)
            out.append(inner.rsplit("|", 1)[-1])
            i = close + 2
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


def _truncate_at_appendix(text: str) -> str:
    for match in _HEADING_RE.finditer(text):
        if match.group(2).strip().lower() in _APPENDIX_HEADINGS:
            return text[: match.start()]
    return text


def strip_markup(wikitext: str) -> str:
    """Reduce raw wikitext to the body prose a reader actually reads.

    Defect 1's fix. Order matters and is not arbitrary: comments and ``<ref>`` blocks first (they contain
    citation *titles*, which are full of genre names), then templates and tables as nested regions (this
    is what removes both the infobox and every navbox), then category and file links, then the appendix
    sections, and only then the ordinary wikilinks whose display text is genuine prose.
    """
    text = _COMMENT_RE.sub(" ", wikitext)
    text = _REF_RE.sub(" ", text)
    text = _TAG_BLOCK_RE.sub(" ", text)
    text = _strip_nested(text, "{{", "}}")
    text = _strip_nested(text, "{|", "|}")
    text = _process_wikilinks(text)
    text = _truncate_at_appendix(text)
    text = _HTML_TAG_RE.sub(" ", text)
    text = _EMPHASIS_RE.sub("", text)
    return re.sub(r"[ \t]+", " ", text)


def stylistic_origins(wikitext: str) -> str:
    """The infobox ``stylistic_origins`` field, or an empty string.

    Read from **raw** wikitext, before :func:`strip_markup` removes the infobox. This is the weak signal
    that separates ``INFOBOX_ONLY`` from ``ORPHAN``, and it is only weak — never grounds for ingestion.
    """
    match = _STYLISTIC_ORIGINS_RE.search(wikitext)
    return " ".join(match.group(1).split()) if match else ""


def name_variants(label: str, title: str = "", aliases: Iterable[str] = ()) -> tuple[str, ...]:
    """Every string a reader might use for this genre, longest first.

    **Wikidata aliases are the only source, deliberately.** They are curated, they are attributable,
    and measured against the full population they already carry the short forms prose actually uses —
    ``country`` for ``country music``, ``dub`` for ``dub music``. The derived-stem rule that used to
    supplement them was removed on 2026-08-04 after it scored zero true positives and three false
    positives; see the module docstring. Anything added back here must clear the same bar.

    Longest-first ordering is load-bearing: :func:`find_mentions` attributes a hit to the first variant
    that matches, so a shortest-first list would report a full-label match as an alias rescue and
    misdescribe how the edge was supported.
    """
    names: list[str] = []
    for raw in (label, title, *aliases):
        cleaned = " ".join(raw.split())
        if cleaned and cleaned.casefold() not in {n.casefold() for n in names}:
            names.append(cleaned)

    return tuple(sorted(names, key=lambda n: (-len(n), n)))


def _spans(text: str, names: Sequence[str]) -> list[tuple[int, int, str]]:
    found: list[tuple[int, int, str]] = []
    for name in names:
        pattern = re.compile(rf"(?<!\w){re.escape(name)}(?!\w)", re.I)
        found.extend((m.start(), m.end(), name) for m in pattern.finditer(text))
    return found


@dataclass(frozen=True, slots=True)
class Mention:
    """One surviving occurrence of the object's name in the subject's prose."""

    name: str
    start: int
    end: int
    sentence: str


def _sentence_at(text: str, index: int) -> str:
    start = text.rfind("\n", 0, index) + 1
    end = text.find("\n", index)
    line = text[start : end if end != -1 else len(text)]
    offset = index - start
    cursor = 0
    for piece in _SENTENCE_SPLIT_RE.split(line):
        cursor = line.find(piece, cursor)
        if cursor <= offset < cursor + len(piece):
            return " ".join(piece.split())
        cursor += len(piece)
    return " ".join(line.split())


def find_mentions(
    body: str, object_names: Sequence[str], subject_names: Sequence[str]
) -> list[Mention]:
    """Occurrences of the object in the body, with self-matches removed.

    Defect 2's fix, and the containment test is what makes it work in **both** directions. An object
    match is discarded only when it sits wholly inside a subject match: ``Western swing <- swing``
    discards the "swing" inside "Western swing" and keeps standalone "swing", while ``swing <- Western
    swing`` keeps every "Western swing" because the longer object match is not contained in the shorter
    subject one. Masking by substring replacement gets the second case wrong.
    """
    masked = _spans(body, subject_names)
    mentions: list[Mention] = []
    seen: set[int] = set()

    for start, end, name in sorted(_spans(body, object_names), key=lambda s: (s[0], -(s[1]))):
        if start in seen:
            continue
        if any(m_start <= start and end <= m_end for m_start, m_end, _ in masked):
            continue
        seen.add(start)
        mentions.append(
            Mention(name=name, start=start, end=end, sentence=_sentence_at(body, start))
        )

    return mentions


def is_taxonomic(sentence: str) -> bool:
    """True when one sentence reads as category membership rather than history."""
    lowered = sentence.casefold()
    return any(marker in lowered for marker in _TAXONOMY_MARKERS)


def count_taxonomic(sentences: Sequence[str]) -> int:
    return sum(1 for sentence in sentences if is_taxonomic(sentence))


def has_taxonomic_lead(sentences: Sequence[str]) -> bool:
    """True when the **first** supporting sentence in document order reads as taxonomy.

    An earlier version of this flag required *every* supporting sentence to be taxonomic. Measured
    against the real articles on 2026-08-04 that rule never fires: `extreme metal <- heavy metal` — the
    canonical 4.8 case — carries the umbrella-term sentence *and* an ordinary descriptive one, so an
    all-sentences rule scored it clean. Any article long enough to be worth checking has some
    non-taxonomic sentence mentioning the object.

    The lead sentence is the right anchor because that is where an article's definitional claim lives.
    `groove metal` leads with "is a subgenre of heavy metal music" (taxonomy) but with "primarily
    derived from thrash metal" (history) for its other edge — one flag, correct both times.

    Still triage, not a verdict. Pair it with :func:`count_taxonomic` rather than reading it alone.
    """
    return bool(sentences) and is_taxonomic(sentences[0])


@dataclass(frozen=True, slots=True)
class ProseCheck:
    """The verdict on one candidate edge, with the evidence that produced it.

    ``sentences`` is the point of the whole dataclass. Phase 1 recorded supporting prose per edge by
    hand (``docs/phases/phase-1-edge-verification.md``); carrying it here makes that record reproducible
    and gives the "asserts influence?" gate — the one thing this check cannot automate — something to be
    applied to.
    """

    subject_id: str
    object_id: str
    tier: Tier
    subject_label: str = ""
    object_label: str = ""
    article_title: str = ""
    prose_hits: int = 0
    matched_names: tuple[str, ...] = ()
    sentences: tuple[str, ...] = ()
    #: The lead supporting sentence reads as category membership rather than history. Triage for the
    #: one thing this check structurally cannot do (module docstring), never an automatic rejection.
    taxonomic_lead: bool = False
    #: How many supporting sentences carry a taxonomy marker. Reported alongside the flag so the
    #: strength of the signal is visible rather than collapsed into a boolean.
    taxonomic_hits: int = 0
    detail: str = ""

    @property
    def usable(self) -> bool:
        """Whether this edge may be ingested. Only PROSE, and only for this phase's corpus."""
        return self.tier is Tier.PROSE

    @property
    def exclusion_reason(self) -> str:
        """Why this candidate was dropped, for the exclusions file. Empty when it was not."""
        if self.usable:
            return ""
        base = {
            Tier.INFOBOX_ONLY: "mentioned only in the infobox; genre infoboxes are weak evidence",
            Tier.ORPHAN: "subject article never mentions the object",
            Tier.NO_ARTICLE: "subject has no English Wikipedia article",
            Tier.REDIRECTED: "subject article redirects to a different title",
            Tier.FETCH_FAILED: "article could not be read",
        }[self.tier]
        return f"{base}: {self.detail}" if self.detail else base


#: Sentinel returned when the object's own article title is unknown. Keeps the analysis signature
#: honest — an empty string is not a name and must never be searched for.
_NO_TITLE = ""


def check_edge(
    *,
    subject_id: str,
    object_id: str,
    subject_label: str,
    object_label: str,
    article: Article,
    object_title: str = _NO_TITLE,
    object_aliases: Iterable[str] = (),
    subject_aliases: Iterable[str] = (),
) -> ProseCheck:
    """Classify one edge against one fetched article. Pure, given the article.

    The subject's own names are needed here and not only the object's, because defect 2 is a collision
    *between* them.
    """

    def verdict(tier: Tier, **extra: Any) -> ProseCheck:
        return ProseCheck(
            subject_id=subject_id,
            object_id=object_id,
            subject_label=subject_label,
            object_label=object_label,
            article_title=article.resolved_title,
            tier=tier,
            **extra,
        )

    if article.tier is not None:
        return verdict(article.tier, detail=article.detail)

    object_names = name_variants(object_label, object_title, object_aliases)
    subject_names = name_variants(subject_label, article.requested_title, subject_aliases)

    body = strip_markup(article.wikitext)
    mentions = find_mentions(body, object_names, subject_names)

    if mentions:
        matched = tuple(dict.fromkeys(m.name for m in mentions))
        sentences = tuple(dict.fromkeys(m.sentence for m in mentions if m.sentence))
        return verdict(
            Tier.PROSE,
            prose_hits=len(mentions),
            matched_names=matched,
            sentences=sentences,
            taxonomic_lead=has_taxonomic_lead(sentences),
            taxonomic_hits=count_taxonomic(sentences),
        )

    origins = stylistic_origins(article.wikitext)
    if origins and find_mentions(origins, object_names, subject_names):
        return verdict(Tier.INFOBOX_ONLY, detail=origins[:300])

    return verdict(Tier.ORPHAN)


# --- fetching --------------------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class Article:
    """One fetched article, or the reason there is not one.

    ``tier`` is non-``None`` exactly when no evidence could be gathered, which is what
    :func:`check_edge` short-circuits on. ``requested_title`` is kept alongside ``resolved_title``
    because their disagreement *is* defect 3.
    """

    requested_title: str = ""
    resolved_title: str = ""
    wikitext: str = ""
    tier: Tier | None = None
    detail: str = ""


@dataclass(frozen=True, slots=True)
class Entity:
    """What one Wikidata read tells us about an entity's naming and its article."""

    qid: str
    label: str = ""
    enwiki_title: str = ""
    aliases: tuple[str, ...] = ()


class ProseCheckError(RuntimeError):
    """The checker could not proceed. Distinct from an edge that simply failed the check."""


#: Retryable status codes. Kept identical to ``ingest.wikidata._RETRYABLE`` and for the same reason:
#: a transient 5xx from one article must not abort a crawl of several hundred.
_RETRYABLE = frozenset({429, 500, 502, 503, 504})


def _get(url: str, timeout: int = 45, attempts: int = 4) -> Any:
    """One polite GET with backoff. Mirrors ``ingest.wikidata._get`` deliberately."""
    request = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
    )
    delay = 5.0
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            if exc.code not in _RETRYABLE or attempt == attempts:
                raise
            time.sleep(delay)
            delay *= 2
    raise ProseCheckError("unreachable")


def fetch_entities(qids: Sequence[str], *, pause: float = 1.0) -> dict[str, Entity]:
    """Labels, English article titles and aliases, in batches of 40.

    Aliases come from the same round trip as the sitelinks because they cost nothing extra there and
    they are the principled fix for the under-accept defect — a hand-written variant list would be one
    more thing to be wrong.
    """
    out: dict[str, Entity] = {}
    for start in range(0, len(qids), 40):
        chunk = list(qids[start : start + 40])
        url = (
            WD_API
            + "?"
            + urllib.parse.urlencode(
                {
                    "action": "wbgetentities",
                    "ids": "|".join(chunk),
                    "props": "labels|aliases|sitelinks",
                    "languages": "en",
                    "sitefilter": "enwiki",
                    "format": "json",
                }
            )
        )
        entities: dict[str, Any] = _get(url).get("entities", {})
        for qid, entity in entities.items():
            sitelink = entity.get("sitelinks", {}).get("enwiki", {})
            out[qid] = Entity(
                qid=qid,
                label=entity.get("labels", {}).get("en", {}).get("value", ""),
                enwiki_title=sitelink.get("title", ""),
                aliases=tuple(
                    alias["value"] for alias in entity.get("aliases", {}).get("en", []) if alias
                ),
            )
        time.sleep(pause)
    return out


def resolve_article(title: str, *, pause: float = 1.0) -> Article:
    """Fetch one article's wikitext, **reporting redirects instead of following them silently**.

    Defect 3's fix, and the distinction that makes it correct is between the API's ``normalized`` list
    and its ``redirects`` list. Normalisation ("disco_house" to "Disco house") is cosmetic and must be
    accepted. A redirect means the sitelink points at a page that now forwards somewhere else, and
    ``disco house`` forwards to ``French house`` — a *different genre*, whose article discusses disco
    throughout. Following it produced confident false support, which is worse than a missing signal.

    Excluded rather than flagged-and-kept: the redirect target is recorded in ``detail`` so any
    individual case can be rescued by hand, but nothing is ingested on evidence read from the wrong page.
    """
    url = (
        WP_API
        + "?"
        + urllib.parse.urlencode(
            {
                "action": "query",
                "prop": "revisions",
                "rvprop": "content",
                "rvslots": "main",
                "titles": title,
                "redirects": 1,
                "format": "json",
            }
        )
    )
    payload = _get(url)
    time.sleep(pause)

    query = payload.get("query", {})
    redirects = query.get("redirects", [])
    if redirects:
        target = redirects[-1].get("to", "?")
        return Article(
            requested_title=title,
            resolved_title=target,
            tier=Tier.REDIRECTED,
            detail=f"{title!r} redirects to {target!r}",
        )

    for page in query.get("pages", {}).values():
        if "missing" in page:
            return Article(requested_title=title, tier=Tier.NO_ARTICLE, detail=title)
        try:
            wikitext = page["revisions"][0]["slots"]["main"]["*"]
        except (KeyError, IndexError):
            return Article(requested_title=title, tier=Tier.FETCH_FAILED, detail=title)
        return Article(
            requested_title=title,
            resolved_title=page.get("title", title),
            wikitext=wikitext,
        )

    return Article(requested_title=title, tier=Tier.FETCH_FAILED, detail=title)
