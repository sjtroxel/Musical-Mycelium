"""The DBpedia ``stylisticOrigin`` layer, phase 6 step 4.

As in ``test_membership``, the tests that earn their place are about **what must not happen**, because
each of these failures is silent — the artifact builds, the suite passes, and the corpus is wrong:

- an edge entering without clearing the same prose check every Wikidata edge cleared,
- the closure walking the wrong way and collecting descendants instead of ancestry,
- a node being credited to DBpedia when its label and revision were read from Wikidata,
- an unresolved endpoint being dropped silently rather than counted,
- a paged read being trusted after a short page.

The direction test is the one to keep. ``MEMORY.md`` records assuming the origins direction as a
recurring failure mode with three instances in one night, **none of which raised** — each silently
answered the opposite question and passed. A reversed walk here returns a set of real music genres that
looks entirely plausible, so only an assertion that names the expected members can catch it.
"""

from __future__ import annotations

import pytest

from musical_mycelium.graph.schema import (
    NODE_KIND_GENRE,
    PREDICATE_INFLUENCED_BY,
    SOURCE_DBPEDIA,
    SOURCE_WIKIDATA,
    VERIFICATION_INFOBOX_AUTO,
    VERIFICATION_LEVELS,
)
from musical_mycelium.ingest.dbpedia import (
    DBPEDIA_RESOURCE_PREFIX,
    WIKIDATA_ENTITY_PREFIX,
    DBpediaError,
    Origin,
    align,
    alignment_query,
    build,
    closure,
    fetch_origin_graph,
    origin_graph_query,
    to_origins,
)

R = DBPEDIA_RESOURCE_PREFIX


def res(name: str) -> str:
    return f"{R}{name}"


def binding(subject: str, obj: str) -> dict[str, object]:
    return {"s": {"value": subject}, "o": {"value": obj}}


# --- the queries -------------------------------------------------------------------------------


def test_alignment_query_refuses_an_empty_id_list() -> None:
    """An unbounded ``owl:sameAs`` read is the whole web, not a corpus alignment."""
    with pytest.raises(ValueError, match="unbounded"):
        alignment_query([])


def test_alignment_query_filters_to_dbpedia_resources() -> None:
    """Without the prefix filter this counts interwiki links, not genres.

    ``owl:sameAs`` on a DBpedia resource fans out to Freebase, YAGO and every language chapter, so the
    same genre returns a dozen times and the alignment rate silently inflates.
    """
    query = alignment_query(["Q11399"])
    assert f'STRSTARTS(STR(?res), "{DBPEDIA_RESOURCE_PREFIX}")' in query
    assert "a <http://dbpedia.org/ontology/MusicGenre>" in query
    assert f"<{WIKIDATA_ENTITY_PREFIX}Q11399>" in query


def test_origin_graph_query_is_distinct_and_ordered() -> None:
    """The counting trap and the paging trap, asserted rather than remembered.

    ``COUNT(*)`` over this join multiplies rows across named graphs — the first run of it returned
    35,947 against an unfiltered total of 5,124, which is impossible. And paging an unordered result
    set drops rows between pages.
    """
    query = origin_graph_query(offset=20, limit=10)
    assert "SELECT DISTINCT" in query
    assert "ORDER BY" in query
    assert "LIMIT 10 OFFSET 20" in query


def test_alignment_query_is_stable_across_id_ordering() -> None:
    """Two callers with the same QIDs in different orders must produce the same query text."""
    assert alignment_query(["Q2", "Q1"]) == alignment_query(["Q1", "Q2"])


# --- alignment ---------------------------------------------------------------------------------


def test_align_chunks_and_merges() -> None:
    seen: list[str] = []

    def runner(query: str) -> list[dict[str, object]]:
        seen.append(query)
        qids = [
            part.split("/")[-1].rstrip(">")
            for part in query.split()
            if part.startswith(f"<{WIKIDATA_ENTITY_PREFIX}")
        ]
        return [
            {"wd": {"value": f"{WIKIDATA_ENTITY_PREFIX}{q}"}, "res": {"value": res(q)}}
            for q in qids
        ]

    out = align([f"Q{n}" for n in range(5)], runner=runner, chunk=2, pause=0.0)
    assert len(seen) == 3, "five ids at a chunk of two is three round trips"
    assert ("Q3", res("Q3")) in out
    assert len(out) == 5


def test_align_omits_genres_dbpedia_does_not_hold() -> None:
    """A Wikidata genre with no DBpedia resource is absent from the second source, not an error."""
    out = align(["Q1", "Q2"], runner=lambda _q: [], chunk=10, pause=0.0)
    assert out == ()


# --- the origin graph and its paging -----------------------------------------------------------


def test_fetch_origin_graph_stops_on_a_short_page() -> None:
    calls: list[int] = []

    def runner(query: str) -> list[dict[str, object]]:
        calls.append(len(calls))
        return [binding(res("a"), res("b"))] if len(calls) == 1 else []

    pairs = fetch_origin_graph(runner=runner, pause=0.0)
    assert pairs == frozenset({(res("a"), res("b"))})
    assert len(calls) == 1, "a page shorter than PAGE means the result set is exhausted"


def test_fetch_origin_graph_refuses_an_empty_result() -> None:
    """Screening an empty candidate set would write an artifact that looks finished and is not."""
    with pytest.raises(DBpediaError, match="empty candidate set"):
        fetch_origin_graph(runner=lambda _q: [], pause=0.0)


def test_fetch_origin_graph_refuses_to_page_forever() -> None:
    """An endpoint ignoring OFFSET would otherwise loop, returning the same rows until memory ran out."""
    full = [binding(res(f"a{i}"), res(f"b{i}")) for i in range(10_000)]
    with pytest.raises(DBpediaError, match="looping rather than paging"):
        fetch_origin_graph(runner=lambda _q: full, pause=0.0, max_pages=3)


# --- the closure -------------------------------------------------------------------------------


def test_closure_walks_from_a_genre_to_what_it_came_out_of() -> None:
    """**The direction test.** Reverse the walk and this returns descendants, which look just as real.

    ``bebop -> jazz -> blues`` is ancestry; ``bebop <- hard bop`` is descent. Seeded on ``bebop``, the
    closure must reach jazz and blues and must NOT reach hard bop. A reversed implementation returns
    ``{bebop, hard bop}`` — a perfectly plausible set of music genres, and wrong.
    """
    pairs = frozenset(
        {
            (res("bebop"), res("jazz")),
            (res("jazz"), res("blues")),
            (res("hard_bop"), res("bebop")),
        }
    )
    reached, growth = closure([res("bebop")], pairs)
    assert res("jazz") in reached, "jazz is what bebop came out of; the walk must reach it"
    assert res("blues") in reached, "the walk is transitive, not one hop"
    assert res("hard_bop") not in reached, (
        "hard bop came out of bebop -- reaching it means the walk is running backwards and "
        "collecting descendants as though they were ancestry"
    )
    assert growth == (1, 1), "one genre added per hop, then termination"


def test_closure_terminates_on_a_cycle() -> None:
    """A cycle in the source must not hang the build. DBpedia is user-edited; cycles happen."""
    pairs = frozenset({(res("a"), res("b")), (res("b"), res("a"))})
    reached, growth = closure([res("a")], pairs)
    assert reached == frozenset({res("a"), res("b")})
    assert growth == (1,)


def test_closure_reports_growth_so_termination_is_evidenced() -> None:
    """`It terminates` is a claim that ships with its evidence attached, not an assertion."""
    pairs = frozenset({(res("a"), res("b")), (res("b"), res("c")), (res("c"), res("d"))})
    _, growth = closure([res("a")], pairs)
    assert growth == (1, 1, 1)


def test_closure_raises_rather_than_looping_on_a_pathological_graph() -> None:
    chain = frozenset({(res(f"g{i}"), res(f"g{i + 1}")) for i in range(30)})
    with pytest.raises(DBpediaError, match="did not terminate"):
        closure([res("g0")], chain, max_hops=4)


# --- translation into QID space ----------------------------------------------------------------


def test_to_origins_keeps_unresolved_pairs_rather_than_dropping_them() -> None:
    """A silent drop makes the alignment rate look better than it is, and that rate is published."""
    mapping = {res("jazz"): "Q8341", res("blues"): "Q9759"}
    origins, unresolved = to_origins(
        [(res("jazz"), res("blues")), (res("jazz"), res("nowhere"))], mapping
    )
    assert [o.pair for o in origins] == [("Q8341", "Q9759")]
    assert unresolved == ((res("jazz"), res("nowhere")),)


def test_to_origins_drops_a_genre_that_is_its_own_origin() -> None:
    """A self-loop is not an influence claim and every traversal would special-case it forever."""
    mapping = {res("jazz"): "Q8341"}
    origins, unresolved = to_origins([(res("jazz"), res("jazz"))], mapping)
    assert origins == ()
    assert unresolved == ()


def test_origin_carries_the_subject_resource_as_its_attribution_link() -> None:
    """CC BY-SA requires a link back, and ``source_id`` is where this project puts attribution."""
    origins, _ = to_origins([(res("jazz"), res("blues"))], {res("jazz"): "Q1", res("blues"): "Q2"})
    assert origins[0].resource == res("jazz")
    assert origins[0].resource.startswith("http")


# --- the build ---------------------------------------------------------------------------------


def _origins() -> tuple[Origin, ...]:
    return (
        Origin(subject_id="Q1", object_id="Q2", resource=res("one")),
        Origin(subject_id="Q2", object_id="Q3", resource=res("two")),
    )


def test_build_sources_edges_to_dbpedia_and_nodes_to_wikidata() -> None:
    """The asymmetry is the honest reading, and it is the thing most likely to be 'tidied' later.

    DBpedia asserted the edge, so the edge is sourced there. The node's label and revision were read
    from Wikidata, so that is where its provenance points. Marking these nodes ``dbpedia`` would credit
    DBpedia with data it did not supply.
    """
    artifact = build(
        _origins(),
        labels={"Q1": "one", "Q2": "two", "Q3": "three"},
        revisions={"Q1": 11, "Q2": 22, "Q3": 33},
        known_genres=frozenset(),
        retrieved_at="2026-09-04T00:00:00+00:00",
    )
    assert {n.source for n in artifact.nodes} == {SOURCE_WIKIDATA}
    assert {e.source for e in artifact.edges} == {SOURCE_DBPEDIA}
    assert {n.revision_id for n in artifact.nodes} == {11, 22, 33}


def test_build_marks_every_edge_infobox_auto() -> None:
    """The tier is set by the builder, never supplied by a caller or a model."""
    artifact = build(
        _origins(),
        labels={"Q1": "one", "Q2": "two", "Q3": "three"},
        revisions={},
        known_genres=frozenset(),
    )
    assert {e.verification for e in artifact.edges} == {VERIFICATION_INFOBOX_AUTO}
    assert VERIFICATION_INFOBOX_AUTO in VERIFICATION_LEVELS
    assert {e.predicate for e in artifact.edges} == {PREDICATE_INFLUENCED_BY}


def test_build_never_emits_an_edge_pointing_at_a_node_that_does_not_exist() -> None:
    """A dangling edge builds, passes, and breaks traversal at runtime. It must be impossible here."""
    artifact = build(
        _origins(),
        labels={"Q1": "one", "Q2": "two"},  # Q3 has no label, so no node can be made for it
        revisions={},
        known_genres=frozenset(),
    )
    ids = {n.id for n in artifact.nodes} | frozenset()
    for edge in artifact.edges:
        assert edge.subject_id in ids and edge.object_id in ids


def test_build_does_not_duplicate_a_genre_the_corpus_already_holds() -> None:
    artifact = build(
        _origins(),
        labels={"Q1": "one", "Q2": "two", "Q3": "three"},
        revisions={},
        known_genres=frozenset({"Q1", "Q2"}),
    )
    assert [n.id for n in artifact.nodes] == ["Q3"]
    assert len(artifact.edges) == 2, "both edges survive; only the node is already held"


def test_build_makes_genre_nodes_only() -> None:
    """This axis is genre-to-genre. An artist node arriving here would cross the axes silently."""
    artifact = build(
        _origins(),
        labels={"Q1": "one", "Q2": "two", "Q3": "three"},
        revisions={},
        known_genres=frozenset(),
    )
    assert {n.kind for n in artifact.nodes} == {NODE_KIND_GENRE}


def test_build_stamps_one_retrieved_at_across_the_layer() -> None:
    """Per-row provenance, but one read is one moment; a layer with drifting stamps is a bug."""
    artifact = build(
        _origins(),
        labels={"Q1": "one", "Q2": "two", "Q3": "three"},
        revisions={},
        known_genres=frozenset(),
        retrieved_at="2026-09-04T12:00:00+00:00",
    )
    stamps = {n.retrieved_at for n in artifact.nodes} | {e.retrieved_at for e in artifact.edges}
    assert stamps == {"2026-09-04T12:00:00+00:00"}


# --- the screening decision, which is the whole justification for this axis ---------------------


def test_classify_admits_only_edges_the_prose_check_accepts() -> None:
    """**The one-standard lock.** A DBpedia edge enters only by clearing the bar Wikidata edges cleared.

    This is the decision the module exists to implement. ``dbo:stylisticOrigin`` is extracted from the
    Wikipedia infobox, and this project already refuses infobox-only evidence: ``prosecheck`` scores it
    ``INFOBOX_ONLY``, calls genre infoboxes weak, and excludes those edges. Admitting DBpedia's copy of
    the same evidence unscreened would apply two standards to one body of evidence, deciding by which
    service happened to serve it.

    So: the accepted edge is the one whose subject article discusses the object in body prose. The
    rejected one is named in the subject's infobox and nowhere else — which is precisely the shape of
    edge the Wikidata axis already throws away.
    """
    from musical_mycelium.ingest.dbpedia import classify
    from musical_mycelium.ingest.prosecheck import Article, Entity

    entities = {
        "Q1": Entity("Q1", label="blues rock", enwiki_title="Blues rock"),
        "Q2": Entity("Q2", label="blues", enwiki_title="Blues"),
        "Q3": Entity("Q3", label="tech house", enwiki_title="Tech house"),
    }
    prose = Article(
        requested_title="Blues rock",
        resolved_title="Blues rock",
        wikitext=(
            "Blues rock is a fusion genre that developed when musicians took the blues and "
            "played it with rock instrumentation.\n"
        ),
    )
    infobox_only = Article(
        requested_title="Tech house",
        resolved_title="Tech house",
        wikitext=(
            "{{Infobox music genre\n| stylistic_origins = [[Blues]]\n}}\n"
            "Tech house is an electronic dance music genre.\n"
        ),
    )
    origins = (
        Origin(subject_id="Q1", object_id="Q2", resource=res("Blues_rock")),
        Origin(subject_id="Q3", object_id="Q2", resource=res("Tech_house")),
    )

    accepted, excluded = classify(origins, entities, {"Q1": prose, "Q3": infobox_only})

    assert [o.subject_id for o in accepted] == ["Q1"], (
        "only the prose-supported edge may be ingested; admitting the infobox-only one is the "
        "two-standards failure this module exists to prevent"
    )
    assert [e.reason_code for e in excluded] == ["INFOBOX_ONLY"]


def test_classify_counts_a_subject_with_no_article_rather_than_raising() -> None:
    """The caller decides what it could fetch; this only reports what that implied."""
    from musical_mycelium.ingest.dbpedia import classify
    from musical_mycelium.ingest.prosecheck import Entity

    entities = {"Q1": Entity("Q1", label="one"), "Q2": Entity("Q2", label="two")}
    accepted, excluded = classify(
        (Origin(subject_id="Q1", object_id="Q2", resource=res("one")),), entities, {}
    )
    assert accepted == ()
    assert [e.reason_code for e in excluded] == ["NO_ARTICLE"]


def test_build_never_overwrites_an_existing_wikidata_edge() -> None:
    """**Caught before it shipped, and this is the regression lock.**

    ``artifact.merge_axes`` keys edges on ``(subject_id, predicate, object_id)`` and later inputs win.
    The DBpedia layer merges last, so an origin duplicating an existing Wikidata edge would replace it
    — statement URI overwritten by a resource URI, and a ``HAND`` or ``PROSE_AUTO`` row downgraded to
    ``INFOBOX_AUTO``. That is the ~80 corroborating edges being destroyed by the very thing that
    corroborates them, and the build would have reported success.

    The corroboration is step 5's to represent. What this artifact must not do is silently lose the
    stronger of the two rows.
    """
    from musical_mycelium.graph.schema import PREDICATE_INFLUENCED_BY as INF

    artifact = build(
        _origins(),
        labels={"Q1": "one", "Q2": "two", "Q3": "three"},
        revisions={},
        known_genres=frozenset({"Q1", "Q2", "Q3"}),
        known_edges=frozenset({("Q1", INF, "Q2")}),
    )
    assert [(e.subject_id, e.object_id) for e in artifact.edges] == [("Q2", "Q3")], (
        "the Q1->Q2 origin duplicates an edge the corpus already holds and must be held back; "
        "emitting it lets merge_axes overwrite the Wikidata row"
    )


def test_build_emits_a_duplicate_when_the_corpus_does_not_already_hold_it() -> None:
    """The guard must be a real comparison, not a blanket refusal that empties the layer."""
    artifact = build(
        _origins(),
        labels={"Q1": "one", "Q2": "two", "Q3": "three"},
        revisions={},
        known_genres=frozenset({"Q1", "Q2", "Q3"}),
        known_edges=frozenset({("Q9", PREDICATE_INFLUENCED_BY, "Q8")}),
    )
    assert len(artifact.edges) == 2


# --- the non-injective alignment, found in the first v0.7.0 cut ---------------------------------


def test_resource_to_qid_resolves_a_resource_claimed_by_two_genres_by_exact_label() -> None:
    """**The regression lock for the worst bug in this step.**

    DBpedia's ``Rock_music`` is ``owl:sameAs`` both ``rock music`` (Q11399) and ``rock and roll``
    (Q7749). Those are different genres, not duplicate Wikidata items. Inverting the alignment with a
    dict comprehension let iteration order choose, and in the first v0.7.0 cut it chose ``rock and
    roll`` — putting all 46 of that resource's edges on the wrong genre, in a corpus about influence,
    on one of its most central nodes.

    An exact label match is the only tie-break, because ``rock and roll`` is not a near miss on
    ``Rock_music``; it is a different string.
    """
    from musical_mycelium.ingest.dbpedia import resource_to_qid

    pairs = [("Q11399", res("Rock_music")), ("Q7749", res("Rock_music"))]
    labels = {"Q11399": "rock music", "Q7749": "rock and roll"}

    resolved, ambiguous = resource_to_qid(pairs, labels)

    assert resolved == {res("Rock_music"): "Q11399"}, (
        "the exact label match must win; picking Q7749 is the iteration-order bug returning"
    )
    assert ambiguous == ()


def test_resource_to_qid_drops_rather_than_guesses_when_no_label_matches() -> None:
    """A fuzzy tie-break would put a guess about node identity under every edge that node carries."""
    from musical_mycelium.ingest.dbpedia import resource_to_qid

    pairs = [("Q1", res("Acid_rock")), ("Q2", res("Acid_rock"))]
    labels = {"Q1": "psychedelic rock", "Q2": "garage rock"}

    resolved, ambiguous = resource_to_qid(pairs, labels)

    assert resolved == {}
    assert ambiguous == ((res("Acid_rock"), ("Q1", "Q2")),)


def test_resource_to_qid_drops_when_two_labels_match_identically() -> None:
    """Two QIDs with the same label is a Wikidata duplicate, and picking one is still a guess."""
    from musical_mycelium.ingest.dbpedia import resource_to_qid

    resolved, ambiguous = resource_to_qid(
        [("Q1", res("Trip_hop")), ("Q2", res("Trip_hop"))], {"Q1": "trip hop", "Q2": "Trip Hop"}
    )
    assert resolved == {}
    assert len(ambiguous) == 1


def test_resource_to_qid_passes_unambiguous_resources_straight_through() -> None:
    """The guard must not cost anything on the 454 resources that map cleanly."""
    from musical_mycelium.ingest.dbpedia import resource_to_qid

    resolved, ambiguous = resource_to_qid(
        [("Q1", res("Jazz")), ("Q2", res("Blues"))], {"Q1": "jazz", "Q2": "blues"}
    )
    assert resolved == {res("Jazz"): "Q1", res("Blues"): "Q2"}
    assert ambiguous == ()


def test_align_keeps_every_resource_when_one_qid_has_several() -> None:
    """**The second half of the ``owl:sameAs`` bug, and the one that hid the first.**

    Q7749 is ``sameAs`` both ``Rock_and_roll`` and ``Rock_music``. Accumulating into
    ``dict[qid] = resource`` kept one and discarded the other — and the discarded resource then looked
    like a genre the corpus had never seen, so it went down the discovery path where there are no
    labels to disambiguate with and was dropped entirely. Losing a resource this way is silent: the
    alignment count still looks healthy, because it counts QIDs.
    """

    def runner(_query: str) -> list[dict[str, object]]:
        return [
            {
                "wd": {"value": f"{WIKIDATA_ENTITY_PREFIX}Q7749"},
                "res": {"value": res("Rock_and_roll")},
            },
            {
                "wd": {"value": f"{WIKIDATA_ENTITY_PREFIX}Q7749"},
                "res": {"value": res("Rock_music")},
            },
        ]

    out = align(["Q7749"], runner=runner, chunk=10, pause=0.0)
    assert len(out) == 2, "both resources must survive; a dict keyed by QID keeps only one"
    assert {r for _, r in out} == {res("Rock_and_roll"), res("Rock_music")}


def test_resource_to_qid_resolves_the_real_rock_collision_end_to_end() -> None:
    """The actual v0.6.0 rows, so the fix is checked against the data that broke it, not a stand-in.

    Both resources exist and both carry both QIDs. Each must land on the genre whose label it matches,
    rather than one of them being dropped or both collapsing onto whichever sorted last.
    """
    from musical_mycelium.ingest.dbpedia import resource_to_qid

    pairs = [
        ("Q11399", res("Rock_music")),
        ("Q7749", res("Rock_music")),
        ("Q11399", res("Rock_and_roll")),
        ("Q7749", res("Rock_and_roll")),
    ]
    labels = {"Q11399": "rock music", "Q7749": "rock and roll"}

    resolved, ambiguous = resource_to_qid(pairs, labels)

    assert resolved == {res("Rock_music"): "Q11399", res("Rock_and_roll"): "Q7749"}
    assert ambiguous == ()
