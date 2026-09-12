"""The locks that make phase 7.7 safe to build. Step 1, written before any behaviour changes.

Phase 7.7 widens what a *candidate* is — labels today, labels plus aliases after step 2 — without
widening what *resolves*. That property lives in one line, ``exact_matches`` comparing
``label_key(node.label)`` and nothing else (``graph/memory.py``), and the whole phase is worthless if a
later edit compares an alias there: every alias would become a silent resolution, which is the opposite
of the phase's purpose. Trap 1 and trap 10 in the IMPLEMENTATION doc name it; this file is the lock.

**These tests pass against unchanged behaviour, deliberately.** A guard that only goes green once the
feature lands was never a guard — it is a specification wearing a test's clothes. So the alias-driven
cases here are written against synthetic nodes and against alias strings the artifact really holds,
and they assert what must *keep* being true after step 2 rather than what step 2 will add.

``candidate_baseline_v0_10_0.json`` is the "before" half: what ``search`` reaches today, what
``exact_matches`` accepts today, and what label+alias matching *would* reach, all measured on artifact
0.10.0 on 2026-09-12. Same arrangement as ``resolution_snapshot_v0_7_1.json`` and the same rule —
**written once and not regenerated**, because a baseline regenerated on the corpus it is meant to
measure compares that corpus with itself.
"""

from __future__ import annotations

import json
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from musical_mycelium.graph.memory import (
    OFFER_CAP,
    InMemoryGraphStore,
    _contains_words,
    default_store,
    exact_matches,
    label_key,
    normalise,
    offer_candidates,
    resolve_exact,
)
from musical_mycelium.graph.schema import Node

BASELINE = Path(__file__).with_name("candidate_baseline_v0_10_0.json")


def baseline() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(BASELINE.read_text(encoding="utf-8"))
    return data


def nodes_of(store: InMemoryGraphStore) -> list[Node]:
    return list(store._artifact.nodes)


def labels_by_key(store: InMemoryGraphStore) -> dict[str, list[Node]]:
    index: dict[str, list[Node]] = defaultdict(list)
    for node in nodes_of(store):
        index[label_key(node.label)].append(node)
    return index


def alias_label_collisions(store: InMemoryGraphStore) -> list[tuple[str, str, list[Node]]]:
    """``(alias, id of the node holding it, nodes whose LABEL folds to the same key)``.

    The sharp edge of aliasing: ``heavy metal`` is an alias of ``traditional heavy metal`` while a
    different node is *labelled* ``heavy metal``. After step 2 both are candidates for one query, and
    only the label owner may ever resolve.
    """
    index = labels_by_key(store)
    out = []
    for node in nodes_of(store):
        for alias in node.aliases:
            owners = index.get(label_key(alias), [])
            if any(owner.id != node.id for owner in owners):
                out.append((alias, node.id, owners))
    return out


def candidates_with_aliases(store: InMemoryGraphStore, query: str) -> list[Node]:
    """What whole-word matching over labels **and aliases** would reach.

    Mirrors ``search``'s matching rule (``_contains_words`` over ``normalise``) widened to aliases, so
    the recorded target counts are measured rather than imagined. This is a measuring instrument for the
    baseline, not the step-2 implementation: ``offer_candidates`` will own ordering, provenance and the
    D4 cap, none of which this needs.
    """
    key = normalise(query)
    if not key:
        return []
    reached: dict[str, Node] = {}
    for node in nodes_of(store):
        for name in (node.label, *node.aliases):
            if _contains_words(normalise(name), key):
                reached[node.id] = node
                break
    return list(reached.values())


def is_non_latin(text: str) -> bool:
    """True if any letter in ``text`` is outside the Latin script. See the baseline's own note."""
    for char in text:
        if char.isspace() or not char.isalpha():
            continue
        try:
            if not unicodedata.name(char).startswith("LATIN"):
                return True
        except ValueError:
            return True
    return False


def alias_statistics(store: InMemoryGraphStore) -> dict[str, int]:
    nodes = nodes_of(store)
    aliases = [alias for node in nodes for alias in node.aliases]
    collisions = alias_label_collisions(store)
    claimed_normalise: dict[str, set[str]] = defaultdict(set)
    claimed_label_key: dict[str, set[str]] = defaultdict(set)
    for node in nodes:
        for alias in node.aliases:
            claimed_normalise[normalise(alias)].add(node.id)
            claimed_label_key[label_key(alias)].add(node.id)
    return {
        "total": len(aliases),
        "nodes_with_aliases": sum(1 for node in nodes if node.aliases),
        "equal_to_another_nodes_label": len(collisions),
        "collisions_with_one_label_owner": sum(1 for _, _, o in collisions if len(o) == 1),
        "collisions_ambiguous_by_label": sum(1 for _, _, o in collisions if len(o) > 1),
        "keys_claimed_by_multiple_nodes_normalise": sum(
            1 for ids in claimed_normalise.values() if len(ids) > 1
        ),
        "keys_claimed_by_multiple_nodes_label_key": sum(
            1 for ids in claimed_label_key.values() if len(ids) > 1
        ),
        "non_latin_script": sum(1 for alias in aliases if is_non_latin(alias)),
        "non_ascii": sum(1 for alias in aliases if not alias.isascii()),
        "two_chars_or_fewer": sum(1 for alias in aliases if len(normalise(alias)) <= 2),
    }


# --- the two behavioural locks ---------------------------------------------------------------------


def test_exact_matches_compares_labels_and_never_aliases() -> None:
    """Trap 1, with the alias deliberately equal to the query.

    If this ever fails, phase 7.7 has inverted itself: every alias in the corpus would resolve
    silently, and the Joy/Roy Orbison rejection that shaped this phase would be undone. The node is
    synthetic so the test states the rule rather than a fact about today's corpus.
    """
    decoy = Node(
        id="Q-decoy",
        label="Timbaland",
        kind="artist",
        source="test",
        source_id="test",
        retrieved_at="2026-09-12",
        aliases=("mozart", "Mozart Timadeas"),
    )
    assert exact_matches([decoy], "mozart") == []
    assert exact_matches([decoy], "Mozart Timadeas") == []
    # The label still resolves, or the test would pass for the wrong reason.
    assert exact_matches([decoy], "timbaland") == [decoy]


def test_an_alias_equal_to_another_nodes_label_never_resolves_to_the_alias_holder() -> None:
    """Trap 1 again, on real data: 37 aliases in this corpus equal a *different* node's label.

    ``heavy metal`` is an alias of ``traditional heavy metal`` and also the label of another node;
    ``jazz-rock`` is an alias of ``jazz fusion`` while ``jazz rock`` is a label. Resolution must land on
    the label owner, or refuse — never on the node that merely lists the string as an alias.

    Two of the 37 refuse for a reason that has nothing to do with aliases: ``big band`` and
    ``big band music`` are two labels folding to one key under ``label_key``, so that query is ambiguous
    and ambiguity refuses. That is correct, and it is why this asserts "never the alias holder" rather
    than "always the label owner" — the weaker claim is the true one.
    """
    store = default_store()
    collisions = alias_label_collisions(store)
    assert collisions, "no alias collides with a label; this guard has nothing to protect"
    recorded = baseline()["collision_resolutions"]

    wrong = []
    for alias, holder_id, owners in collisions:
        resolved = resolve_exact(store, alias)
        if resolved is not None:
            assert resolved.id != holder_id, (
                f"{alias!r} resolved to the node holding it as an ALIAS, not the node labelled it"
            )
            assert resolved.id in {owner.id for owner in owners}, (
                f"{alias!r} resolved to {resolved.label!r}, neither a label owner nor expected"
            )
        # Pinned per alias, because "resolved is None" must not be an escape hatch. Breaking
        # ``exact_matches`` to compare aliases turns most of these AMBIGUOUS rather than wrong, and a
        # guard that skips None passes that break: a system that refuses everything scores perfectly.
        got = resolved.label if resolved else None
        if got != recorded.get(alias, "<unrecorded>"):
            wrong.append(f"  {alias!r}: recorded {recorded.get(alias)!r}, measured {got!r}")
    assert not wrong, "collision resolutions moved since 2026-09-12:\n" + "\n".join(wrong)


# --- the recorded baseline -------------------------------------------------------------------------


def test_todays_candidate_counts_match_the_recorded_baseline() -> None:
    """The "before" numbers, asserted rather than remembered — which is the whole point of step 1.

    ``search_today`` is label-only whole-word matching, ``exact_today`` is what actually resolves, and
    ``candidates_with_aliases`` is what step 2 opens up. A corpus change that moves any of these is a
    finding and a decision, exactly as ``RESOLUTION_CHANGES`` is in ``test_resolution_stability.py``.
    """
    store = default_store()
    recorded = baseline()
    assert recorded["artifact"] == store.artifact_version

    drift = []
    for query, want in recorded["queries"].items():
        found = store.search(query)
        got = {
            "search_today": len(found),
            "exact_today": len(exact_matches(found, query)),
            "candidates_with_aliases": len(candidates_with_aliases(store, query)),
        }
        for field, expected in want.items():
            if got[field] != expected:
                drift.append(f"  {query!r} {field}: recorded {expected}, measured {got[field]}")
    assert not drift, "candidate counts moved since 2026-09-12:\n" + "\n".join(drift)


def test_the_recorded_alias_statistics_still_hold() -> None:
    """The alias facts every step-2 rule is designed around.

    ``collisions_ambiguous_by_label`` and the two ``keys_claimed_by_multiple_nodes_*`` counts are the
    ones to read closely. The same question answered with ``normalise`` gives 27 and with ``label_key``
    gives 32, because ``label_key`` folds a trailing "music"; ``search`` uses the former and
    ``exact_matches`` the latter, so an alias index has to say which one it means. Recording both is how
    that stops being a detail somebody remembers.
    """
    store = default_store()
    recorded = baseline()["aliases"]
    measured = alias_statistics(store)
    assert measured == recorded, (
        "alias statistics moved since 2026-09-12; step 2's rules were sized against the recorded ones"
    )


def test_the_two_flagship_offer_lists_are_unchanged() -> None:
    """``mozart`` and ``x``: the examples that justify the D4 cap and the D5 one-character rule.

    ``mozart`` reaches five nodes and two of them are noise — Timbaland via "Mozart Timadeas", Samuel
    Wesley via "English Mozart". ``x`` reaches four through tokenised initials. If either list changes,
    the argument for those two rules changes with it.
    """
    store = default_store()
    recorded = baseline()["flagship"]
    for query, want in recorded.items():
        got = sorted(node.label for node in candidates_with_aliases(store, query))
        assert got == want, f"the {query!r} offer list changed: recorded {want}, measured {got}"


# --- step 2: the alias index and offer_candidates ---------------------------------------------------


def test_offer_candidates_reproduces_the_measured_table() -> None:
    """Step 2's "done when", against the baseline measured before any of it was built.

    ``candidates_with_aliases`` in this file is an independent instrument — it walks every node and
    applies ``_contains_words`` itself — so agreement between it and ``offer_candidates`` is two
    implementations of the same rule landing on the same 16 numbers, not one asserting itself.
    """
    store = default_store()
    recorded = baseline()["queries"]
    drift = []
    for query, want in recorded.items():
        offer = offer_candidates(store, query)
        if offer.total != want["candidates_with_aliases"]:
            drift.append(
                f"  {query!r}: recorded {want['candidates_with_aliases']}, offered {offer.total}"
            )
        assert offer.term == query
    assert not drift, "offer_candidates disagrees with the measured baseline:\n" + "\n".join(drift)


def test_the_d4_cap_is_all_or_nothing_and_always_states_the_total() -> None:
    """25 shown or none shown, and the true count either way.

    The rejected alternative was showing the first N of a longer list, which is ranking under another
    name. So the assertion that matters is the pair: over the cap, ``candidates`` is **empty** while
    ``total`` still tells the truth about how ambiguous the query was.
    """
    store = default_store()
    for query, expected_total in (("metal", 34), ("john", 42), ("music", 235)):
        offer = offer_candidates(store, query)
        assert offer.over_cap and offer.total == expected_total
        assert offer.candidates == () and offer.shown == 0, "over the cap nothing is shown"

    for query, expected_total in (("bach", 14), ("black", 9), ("r&b", 6), ("mozart", 5)):
        offer = offer_candidates(store, query)
        assert not offer.over_cap
        assert offer.total == offer.shown == len(offer.candidates) == expected_total

    assert OFFER_CAP == 25, "D4's cap moved; the measured effects above were sized against 25"


def test_d5_kills_the_single_character_path_and_nothing_else() -> None:
    """A query of one character matches nothing, and ``r&b`` survives the rule.

    The instrument is asserted alongside it on purpose: ``x`` really does reach four nodes through
    tokenised initials, so the rule is doing work rather than describing an empty set. ``normalise``
    turns ``r&b`` into ``rb``, two characters, which is why the D4 table still shows 6 for it.
    """
    store = default_store()
    assert len(candidates_with_aliases(store, "x")) == 4, "the x path exists, so D5 has a job"
    assert offer_candidates(store, "x").total == 0
    assert offer_candidates(store, "X").total == 0
    assert offer_candidates(store, "").total == 0
    assert offer_candidates(store, "   ").total == 0
    assert offer_candidates(store, "r&b").total == 6, "r&b normalises to two characters, not one"
    # A one-character token inside a longer query is untouched: "f x mozart" is a real alias.
    assert offer_candidates(store, "f x mozart").total >= 1


def test_every_offered_candidate_says_why_it_was_offered() -> None:
    """D7. An alias hit carries the alias text exactly as the source wrote it."""
    store = default_store()
    offer = offer_candidates(store, "mozart")
    assert offer.total == 5
    for candidate in offer.candidates:
        assert candidate.via in {"label", "alias"}
        assert (candidate.alias is not None) == (candidate.via == "alias"), (
            f"{candidate.label!r} has via={candidate.via!r} and alias={candidate.alias!r}"
        )
    noise = {c.label: c.alias for c in offer.candidates if c.via == "alias"}
    assert noise == {"Timbaland": "Mozart Timadeas", "Samuel Wesley": "The English Mozart"}, (
        "the two noise candidates are the argument for D7; their aliases must be legible"
    )


def test_the_alias_index_is_not_the_name_index() -> None:
    """Trap 10, asserted on the built store rather than trusted.

    Merging aliases into ``_by_name`` would change the zero/one/two arithmetic ``exact_matches`` uses,
    which is the arithmetic that produces "ambiguous". Two dicts is the whole defence.
    """
    store = default_store()
    aliases = store.alias_index()
    assert aliases, "no alias index was built"
    assert aliases is not store._by_name
    assert "mozart timadeas" in aliases, "aliases are keyed on normalise, like _by_name"
    # The decisive one: an alias key that is NOT any node's normalised label must be absent from
    # _by_name entirely, or the exact bucket has been widened.
    alias_only = {key for key in aliases if key not in store._by_name}
    assert alias_only, "every alias equals a label, so this guard proves nothing on this corpus"
    for key in sorted(alias_only)[:50]:
        assert key not in store._by_name
        # The assertion that means something: an alias-only key cannot RESOLVE, because the exact
        # bucket it would have to come from does not contain it.
        assert exact_matches(store.search(key), key) == [], (
            f"{key!r} is nobody's label and yet resolves; the exact bucket has been widened"
        )


def test_search_and_exact_matches_never_see_an_alias() -> None:
    """The property the whole phase rests on, after step 2 rather than before it.

    ``search`` was deliberately **not** widened to aliases (see the phase doc's step 2 as-built). So
    the recorded ``search_today`` and ``exact_today`` counts must be untouched by everything above,
    and an alias string that is nobody's label must still resolve to nothing.
    """
    store = default_store()
    recorded = baseline()["queries"]
    for query, want in recorded.items():
        found = store.search(query)
        assert len(found) == want["search_today"], f"search({query!r}) changed"
        assert len(exact_matches(found, query)) == want["exact_today"], f"exact({query!r}) changed"

    # "Mozart Timadeas" is Timbaland's alias and nobody's label. It may be OFFERED and never resolved.
    assert offer_candidates(store, "Mozart Timadeas").total >= 1
    assert resolve_exact(store, "Mozart Timadeas") is None


def test_the_music_fold_offers_a_choice_and_resolves_nothing() -> None:
    """His decision, 2026-09-12: offers only.

    ``label_key`` folds a trailing "music", so ``electro music`` and ``electro`` are one key at the
    ``exact_matches`` filter — but the index ``search`` reads is built on ``normalise``, so the query
    gathered no candidates and refused. The fold now produces an **offer**. What it must not do is
    resolve, and the rejected full fold would additionally have cost ``big band music`` its resolution
    by making it ambiguous against ``big band``.
    """
    store = default_store()
    for query, expected in (("electro music", "electro"), ("jerk music", "jerk")):
        offer = offer_candidates(store, query)
        assert expected in {c.label for c in offer.candidates}, f"{query!r} offers no {expected!r}"
        assert resolve_exact(store, query) is None, f"{query!r} must offer, never resolve"
        assert store.search(query) == [], "the fold must not reach the resolution path"

    kept = resolve_exact(store, "big band music")
    assert kept is not None and kept.label == "big band music", (
        "the full index fold was rejected to keep this resolving; it has stopped resolving anyway"
    )
