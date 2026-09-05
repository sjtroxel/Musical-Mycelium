import { describe, expect, it } from "vitest";
import { indexArtifact } from "../graph/staticGraph";
import type { Artifact } from "../graph/staticGraph";
import { split } from "./NodeInspector";

/**
 * **The prose half of "membership is not derivation".**
 *
 * `GraphView` keeps the two apart in ink and `layerOf` keeps them apart in geometry
 * (`graph/membership.test.tsx`). This file covers the third place the distinction can be lost, and
 * the one where losing it is least deniable: the inspector states the relation in English.
 *
 * `plays_genre` is stored as `artist plays_genre genre`. Run through a two-way subject/object split
 * — which is all this function did until artifact v0.7.1, when every edge was still an influence
 * edge — the artist lands in the genre's "Led to" list and the genre lands in the artist's "Came out
 * of" list. The panel then reads *Miles Davis came out of jazz* and *jazz led to Miles Davis*, which
 * is a derivation claim the corpus never made about a musician who simply played the music.
 */

const node = (id: string, label: string, kind: string) => ({
  id,
  label,
  kind,
  inception_year: null,
  inception_precision: null,
  countries: [],
  source: "wikidata",
  source_id: id,
  retrieved_at: "2026-09-05T00:00:00+00:00",
  revision_id: null,
});

const edge = (subject: string, object: string, predicate: string) => ({
  subject_id: subject,
  object_id: object,
  predicate,
  verification: "HAND" as const,
  prose_tier: "PROSE",
  source: "wikidata",
  source_id: `http://www.wikidata.org/entity/statement/${subject}-x`,
  retrieved_at: "2026-09-05T00:00:00+00:00",
});

const ARTIFACT: Artifact = {
  nodes: [
    node("Q_blues", "blues", "genre"),
    node("Q_jazz", "jazz", "genre"),
    node("Q_miles", "Miles Davis", "artist"),
  ],
  // `jazz influenced_by blues`, and Miles Davis plays jazz.
  edges: [
    edge("Q_jazz", "Q_blues", "influenced_by"),
    edge("Q_miles", "Q_jazz", "plays_genre"),
  ],
};

const graph = indexArtifact("0.7.1", ARTIFACT);
const ids = (edges: { subject_id: string; object_id: string }[], self: string) =>
  edges.map((e) => (e.subject_id === self ? e.object_id : e.subject_id));

describe("an artist does not descend from the genre they played", () => {
  it("keeps the genre out of the artist's influence lists", () => {
    const { parents, children, membership } = split(graph, "Q_miles");

    // The failing assertion before this was fixed: `parents` held jazz, and `parents` renders under
    // the heading "Came out of".
    expect(ids(parents, "Q_miles")).toEqual([]);
    expect(ids(children, "Q_miles")).toEqual([]);
    expect(ids(membership, "Q_miles")).toEqual(["Q_jazz"]);
  });

  it("keeps the artist out of the genre's influence lists", () => {
    const { parents, children, membership } = split(graph, "Q_jazz");

    // Jazz still came out of blues -- the influence half must survive the filtering, or the fix
    // would be "show nothing", which passes the test above and breaks the product.
    expect(ids(parents, "Q_jazz")).toEqual(["Q_blues"]);
    // And it did NOT lead to Miles Davis. This is where the old split put him.
    expect(ids(children, "Q_jazz")).toEqual([]);
    expect(ids(membership, "Q_jazz")).toEqual(["Q_miles"]);
  });

  it("counts membership toward the node's degree", () => {
    // Degree drives the "all N of its connections are on the map" copy and the zero-degree refusal
    // text. Filtering membership out of the influence lists must not make it vanish from the count,
    // or the panel would tell a visitor the corpus holds nothing about an artist it holds a genre
    // for -- a negative claim, which is the one thing that copy exists to avoid.
    const { parents, children, membership } = split(graph, "Q_miles");
    expect(parents.length + children.length + membership.length).toBe(1);
  });
});
