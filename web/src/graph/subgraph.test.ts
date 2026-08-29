import { describe, expect, it } from "vitest";
import type { Claim } from "../types";
import type { Artifact, ArtifactEdge, ArtifactNode } from "./staticGraph";
import { indexArtifact } from "./staticGraph";
import { buildRenderGraph, nodeIdsInArguments } from "./subgraph";

/**
 * The map's selection logic, tested where it can be tested.
 *
 * jsdom has no canvas, so nothing inside the render loop can be unit-tested at all — which is exactly
 * why the choosing lives in `subgraph.ts` and only the drawing lives in `GraphView.tsx`. The pixels get
 * checked in a real browser instead, after step 3 established that an unverified preview produces a
 * confident wrong reading rather than no reading.
 *
 * The two properties worth the most here: **claimed and context never mix**, and **the arrow points
 * the way history ran**. The second is this project's named failure mode arriving in a new place —
 * `tests/test_gold_set.py`, `eval/heldout.py` and `heldout_draw` each silently answered the opposite
 * question and none of them raised.
 */

function node(id: string, label: string, kind = "genre"): ArtifactNode {
  return {
    id,
    label,
    kind,
    inception_year: null,
    inception_precision: null,
    countries: [],
    source: "wikidata",
    source_id: id,
    retrieved_at: "2026-08-05T00:00:00+00:00",
    revision_id: null,
  };
}

/** `subject influenced_by object`: the influence runs object to subject. */
function edge(subjectId: string, objectId: string): ArtifactEdge {
  return {
    subject_id: subjectId,
    object_id: objectId,
    predicate: "influenced_by",
    verification: "HAND",
    prose_tier: "PROSE",
    source: "wikidata",
    source_id: `http://www.wikidata.org/entity/statement/${subjectId}-x`,
    retrieved_at: "2026-08-05T00:00:00+00:00",
  };
}

function claim(subjectId: string, objectId: string): Claim {
  return {
    subject_id: subjectId,
    predicate: "influenced_by",
    object_id: objectId,
    source_ids: [`http://www.wikidata.org/entity/statement/${subjectId}-x`],
    verification: "HAND",
    span: null,
  };
}

/** acid jazz came out of hip-hop, soul, funk and jazz; jazz has an unwalked neighbour of its own. */
const ARTIFACT: Artifact = {
  nodes: [
    node("Q221772", "acid jazz"),
    node("Q11401", "hip-hop"),
    node("Q131272", "soul"),
    node("Q164444", "funk"),
    node("Q8341", "jazz"),
    node("Q9759", "blues"),
  ],
  edges: [
    edge("Q221772", "Q11401"),
    edge("Q221772", "Q131272"),
    edge("Q221772", "Q164444"),
    edge("Q221772", "Q8341"),
    edge("Q8341", "Q9759"),
  ],
};

const graph = indexArtifact("0.5.0", ARTIFACT);

const EMPTY = { claims: [], pathNodeIds: [], toolNodeIds: [] };

describe("indexing the artifact", () => {
  it("makes an edge reachable from both of its endpoints", () => {
    // The map is undirected for navigation even though influence is not. Walking outward from jazz has
    // to find the acid jazz edge, which names jazz as the object rather than the subject.
    expect(graph.incident.get("Q8341")?.length).toBe(2);
    expect(graph.degree("Q9759")).toBe(1);
  });

  it("looks an edge up in the direction the artifact stores it, and not the other way", () => {
    expect(graph.edge("Q221772", "Q8341")).not.toBeNull();
    expect(graph.edge("Q8341", "Q221772")).toBeNull();
  });
});

describe("reading node ids out of tool arguments", () => {
  it("takes every id-shaped argument, whatever the tool called it", () => {
    // node_id, from_id and to_id all arrive without this function knowing their names, so a tool added
    // later needs no edit here. Same seam invariant 4 asks for on the backend.
    expect(nodeIdsInArguments({ node_id: "Q636" })).toEqual(["Q636"]);
    expect(nodeIdsInArguments({ from_id: "Q38848", to_id: "Q9759" })).toEqual(["Q38848", "Q9759"]);
  });

  it("takes nothing from a resolve_node call that only carries a name", () => {
    // This is the refusal fixture's only tool call. Inventing an id from the query text is how the map
    // would start showing a neighbourhood the run never established.
    expect(nodeIdsInArguments({ name: "Who influenced Kate Bush" })).toEqual([]);
    expect(nodeIdsInArguments({ name: "acid jazz", limit: 5 })).toEqual([]);
  });
});

describe("building the render graph", () => {
  const claims = [
    claim("Q221772", "Q11401"),
    claim("Q221772", "Q131272"),
    claim("Q221772", "Q164444"),
    claim("Q221772", "Q8341"),
  ];

  it("draws a claimed edge from the object to the subject, the way history ran", () => {
    const rendered = buildRenderGraph(graph, { ...EMPTY, claims: [claim("Q221772", "Q8341")] });
    const claimed = rendered.edges.filter((e) => e.kind === "claimed");

    expect(claimed).toHaveLength(1);
    // acid jazz came out of jazz, so the arrow runs jazz -> acid jazz. Reversed, this draws acid jazz
    // as an influence on jazz, which is a false historical claim rendered in a picture.
    expect(claimed[0]?.from).toBe("Q8341");
    expect(claimed[0]?.to).toBe("Q221772");
  });

  it("numbers claimed edges in the order the gate approved them", () => {
    const rendered = buildRenderGraph(graph, { ...EMPTY, claims });
    const orders = rendered.edges.filter((e) => e.kind === "claimed").map((e) => e.order);
    expect(orders).toEqual([1, 2, 3, 4]);
  });

  it("keeps context out of the claimed set entirely", () => {
    const rendered = buildRenderGraph(graph, { ...EMPTY, claims });

    // jazz -> blues is a real corpus edge that this answer never claimed. It must be on the map and it
    // must not be counted, ordered or typed as a claim.
    const context = rendered.edges.filter((e) => e.kind === "context");
    expect(context.map((e) => `${e.from}->${e.to}`)).toEqual(["Q9759->Q8341"]);
    expect(context.every((e) => e.order === null)).toBe(true);
    expect(rendered.claimed).toBe(4);
    expect(rendered.context).toBe(1);
  });

  it("does not draw a claimed edge a second time as context", () => {
    const rendered = buildRenderGraph(graph, { ...EMPTY, claims });
    const pairs = rendered.edges.map((e) => `${e.from}->${e.to}`);
    expect(new Set(pairs).size).toBe(pairs.length);
  });

  it("marks a node the run reached differently from one it never looked at", () => {
    const rendered = buildRenderGraph(graph, { ...EMPTY, claims });
    const roles = new Map(rendered.nodes.map((n) => [n.id, n.role]));
    expect(roles.get("Q221772")).toBe("walked");
    expect(roles.get("Q8341")).toBe("walked");
    expect(roles.get("Q9759")).toBe("context");
  });

  it("draws a neighbourhood from a tool argument alone, with nothing claimed", () => {
    // The refusal case as it arrives from a real model: a node was resolved, no claim survived the
    // gate. The map still has something honest to show, and none of it is a claim.
    const rendered = buildRenderGraph(graph, { ...EMPTY, toolNodeIds: ["Q8341"] });
    expect(rendered.claimed).toBe(0);
    expect(rendered.edges.every((e) => e.kind === "context")).toBe(true);
    expect(rendered.nodes.map((n) => n.id)).toContain("Q9759");
  });

  it("returns nothing at all when the run never named a node", () => {
    // The local stub's refusal. No ids anywhere, so there is no neighbourhood, so there is no map —
    // rather than a map centred on a node the interface guessed.
    expect(buildRenderGraph(graph, EMPTY).nodes).toHaveLength(0);
  });

  it("drops a claim whose endpoints are not in this corpus", () => {
    const rendered = buildRenderGraph(graph, { ...EMPTY, claims: [claim("Q221772", "Q999999")] });
    expect(rendered.claimed).toBe(0);
  });

  it("caps the neighbourhood and says so instead of implying the map is complete", () => {
    const hub = "Q221772";
    const big: Artifact = {
      nodes: [node(hub, "acid jazz"), ...Array.from({ length: 30 }, (_, i) => node(`Q${i + 1}`, `n${i}`))],
      edges: Array.from({ length: 30 }, (_, i) => edge(hub, `Q${i + 1}`)),
    };
    const rendered = buildRenderGraph(indexArtifact("0.5.0", big), { ...EMPTY, toolNodeIds: [hub] }, 5);

    expect(rendered.nodes.filter((n) => n.role === "context")).toHaveLength(5);
    expect(rendered.truncated).toBe(true);
  });
});
