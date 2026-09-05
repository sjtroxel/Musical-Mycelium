import chips from "../chips.json";
import type { Verification } from "../types";

/**
 * The pinned graph artifact, loaded once into the browser and read for **navigation only**.
 *
 * Phase 5 IMPLEMENTATION 4.2 decided this: the whole corpus ships as a static asset and the map is
 * entirely client-side, which costs zero Lambda invocations and zero dollars to pan around. The
 * alternative was a `/subgraph` route, which would have been a backend edit made to accommodate the
 * frontend, the thing DoD 9 forbids.
 *
 * **The line that matters more than any of that:** rendering an edge from this file is not narrating
 * it. The agent remains the only source of claims. Nothing read from here may enter the claim list or
 * the prose, and `subgraph.ts` keeps claimed and context edges in separate structures rather than
 * behind a style flag so that stays true by construction. See `.claude/rules/grounding-and-claims.md`.
 */

export interface ArtifactNode {
  id: string;
  label: string;
  kind: string;
  inception_year: number | null;
  inception_precision: string | null;
  countries: string[];
  source: string;
  source_id: string;
  retrieved_at: string;
  revision_id: number | null;
}

/**
 * The two predicates this corpus holds, named once so nothing compares against a bare string.
 *
 * **They are different KINDS of statement and the map must never let one read as the other.**
 * `influenced_by` is a claim about derivation: this came out of that, and it runs in time.
 * `plays_genre` is a claim about membership: this artist worked in that genre, which says nothing
 * about what came first. At artifact v0.7.1 membership is the MAJORITY of the edge set (2,782 of
 * 5,066), so a renderer that treats every edge as influence is wrong about most of the picture.
 *
 * Mirrors `graph/schema.py`'s `PREDICATE_INFLUENCED_BY` / `PREDICATE_PLAYS_GENRE`. Only the first is
 * in `agent/claims.py:ALLOWED_PREDICATES`, so a *claimed* edge is always influence and a membership
 * edge can only ever reach the map as context.
 */
export const PREDICATE_INFLUENCED_BY = "influenced_by";
export const PREDICATE_PLAYS_GENRE = "plays_genre";

export interface ArtifactEdge {
  subject_id: string;
  object_id: string;
  predicate: string;
  verification: Verification;
  prose_tier: string;
  source: string;
  source_id: string;
  retrieved_at: string;
}

export interface Artifact {
  nodes: ArtifactNode[];
  edges: ArtifactEdge[];
}

export interface StaticGraph {
  /** The artifact version this was loaded from. Checked against every answer's `done` frame. */
  version: string;
  nodes: ReadonlyMap<string, ArtifactNode>;
  /** Every edge touching a node, in either direction. The map is undirected for navigation. */
  incident: ReadonlyMap<string, readonly ArtifactEdge[]>;
  edge(subjectId: string, objectId: string): ArtifactEdge | null;
  degree(id: string): number;
}

/**
 * The corpus version, taken from `chips.json` rather than written here.
 *
 * That file is already validated against the artifact by `tests/test_chips.py`, so the pin exists in
 * exactly one place and a corpus change fails the build rather than a demo, which is the standing rule
 * adopted 2026-08-02. `scripts/stage-graph.mjs` reads the same field to decide what to copy.
 */
export const GRAPH_PIN: string = chips.artifact_version;

/** Version-pinned on purpose: a new corpus is a new URL, so the immutable cache header is correct. */
export function graphUrl(pin: string = GRAPH_PIN): string {
  return `${import.meta.env.BASE_URL}graph/v${pin}/graph.json`;
}

const edgeKey = (subjectId: string, objectId: string) => `${subjectId}>${objectId}`;

export function indexArtifact(version: string, artifact: Artifact): StaticGraph {
  const nodes = new Map<string, ArtifactNode>();
  for (const node of artifact.nodes) nodes.set(node.id, node);

  const incident = new Map<string, ArtifactEdge[]>();
  const byPair = new Map<string, ArtifactEdge>();

  const attach = (id: string, edge: ArtifactEdge) => {
    const list = incident.get(id);
    if (list === undefined) incident.set(id, [edge]);
    else list.push(edge);
  };

  for (const edge of artifact.edges) {
    attach(edge.subject_id, edge);
    attach(edge.object_id, edge);
    byPair.set(edgeKey(edge.subject_id, edge.object_id), edge);
  }

  return {
    version,
    nodes,
    incident,
    edge: (subjectId, objectId) => byPair.get(edgeKey(subjectId, objectId)) ?? null,
    degree: (id) => incident.get(id)?.length ?? 0,
  };
}

let pending: Promise<StaticGraph> | null = null;

/**
 * Fetch and index the artifact, once per page.
 *
 * **Never call this on mount.** `App.test.tsx` asserts that loading the page makes no network request
 * at all, which is DoD 5 (the frontend loads instantly and independently of the agent) and is the
 * easiest thing in this directory to break by accident. `useStaticGraph` starts the fetch when a run
 * starts, alongside the stream rather than in front of first paint.
 */
export function loadStaticGraph(pin: string = GRAPH_PIN): Promise<StaticGraph> {
  if (pending === null) {
    pending = fetch(graphUrl(pin))
      .then(async (response) => {
        if (!response.ok) throw new Error(`the graph answered ${response.status}`);
        return indexArtifact(pin, (await response.json()) as Artifact);
      })
      .catch((error: unknown) => {
        // A failed load must not poison every later attempt. The map is an enhancement; the answer
        // and its citations are already on screen without it.
        pending = null;
        throw error;
      });
  }
  return pending;
}

/** Test seam. The module-level memo is a cache, and a cache that survives a test is a shared fixture. */
export function resetStaticGraphCache(): void {
  pending = null;
}
