"""How a Wikidata label and its aliases are read. One place, used by every fetch path.

**Why this module exists: the `mul` bug, found 2026-09-11 when "mozart" refused on the live site.**
Every fetch in this package asked Wikidata for English (`en`) labels only. Wikidata now lets an item keep
its label in `mul`, a default shared across languages, with no separate `en` label, and some very famous
items have moved there: Wolfgang Amadeus Mozart (`Q254`) has only `mul`, and so do Muse and Christina
Aguilera. Their labels came back as empty strings, and screening then excluded them as `MISLINKED`,
because an empty label cannot match the article it links to. 44 entities with an English article were
lost that way, Mozart, Taylor Swift and B. B. King among them. Phase 7.6 IMPLEMENTATION §3, trap 9.

**Three fetch paths had the same fault, which is why the fix is a shared helper rather than three
edits:** ``prosecheck.fetch_entities`` (artists), ``wikidata.fetch_entities`` (genre facts, and the
membership layer's genre labels) and the SPARQL label service in ``ingest.coverage``. A fix in one of
them would have left the next `mul` migration reopening the gap in the other two.

**The rule:** `en` wins when both exist, because it is the label every artifact so far was written with
and changing an existing node's label would move resolution under the eval datasets. `mul` is the
fallback. Aliases are the union of both, in that order, without duplicates and without the label itself.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

#: For ``wbgetentities``' ``languages`` parameter: both codes, pipe-separated.
WBGETENTITIES_LANGUAGES = "en|mul"

#: For the SPARQL label service's ``wikibase:language``: a comma-separated fallback list, tried in order.
SPARQL_LABEL_LANGUAGES = "en,mul"

#: Label languages in preference order. `en` first; see the module docstring.
_PREFERENCE = ("en", "mul")


def entity_label(entity: Mapping[str, Any]) -> str:
    """The entity's label: `en` if Wikidata has one, else `mul`, else the empty string.

    The empty string is kept as the "no label" value it has always been, so every caller's existing
    handling of it (``Node`` refuses a blank label; screening reports it) is unchanged.
    """
    labels: Mapping[str, Any] = entity.get("labels", {})
    for language in _PREFERENCE:
        value = labels.get(language, {}).get("value", "")
        if value:
            return str(value)
    return ""


def entity_aliases(entity: Mapping[str, Any]) -> tuple[str, ...]:
    """Every `en` and `mul` alias, `en` first, deduplicated, never repeating the label."""
    label = entity_label(entity)
    seen: set[str] = {label} if label else set()
    out: list[str] = []
    aliases: Mapping[str, Any] = entity.get("aliases", {})
    for language in _PREFERENCE:
        for alias in aliases.get(language, []):
            value = alias.get("value", "") if isinstance(alias, Mapping) else ""
            if value and value not in seen:
                seen.add(value)
                out.append(str(value))
    return tuple(out)
