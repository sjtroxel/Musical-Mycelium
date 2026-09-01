import type { Claim, Verification } from "../types";
import type { StaticGraph } from "./staticGraph";

/**
 * Choosing what the map shows, as pure functions.
 *
 * This is separated from the drawing for two reasons, and only one of them is taste. The practical one
 * is that jsdom has no canvas, so anything living inside the render loop cannot be unit-tested at all;
 * the load-bearing one is that **claimed and context edges are two different types here, not one type
 * with a style flag.** A flag is one careless `.filter()` away from putting an unclaimed corpus edge in
 * front of a visitor as though the gate had approved it. Invariant 1 says the model must not be able to
 * narrate an edge the gate did not pass, and the map is a place that could quietly do it.
 *
 * The rule, stated once: **`claimed` comes only from `claim` frames. `context` comes only from the
 * static artifact and is never spoken about as a finding.**
 *
 * **Step 8b adds a visitor who can wander, and does not add a way for wandering to make a claim.**
 * Following an edge grows the CONTEXT set and never the walked set — decision D2 — so `walked` keeps
 * meaning exactly one thing: the agent reached this. A node someone clicked their way to three hops
 * out is context, like every other unwalked node, however deliberately they got there. That is what
 * makes invariant 1 a property of this function rather than a promise about the interface: no
 * sequence of clicks can change the claimed edges, because `openedIds` is not consulted anywhere in
 * the claimed pass. `subgraph.test.ts` asserts it over arbitrary opened sets.
 */

/** `walked` is a node the run actually reached. `context` is a neighbour it never looked at. */
export type NodeRole = "walked" | "context";

export interface RenderNode {
  id: string;
  label: string;
  kind: string;
  year: number | null;
  role: NodeRole;
}

export interface RenderEdge {
  /**
   * The arrow of history. `subject influenced_by object` means the influence runs **object to
   * subject**, so `from` is the object and `to` is the subject. `web/previews/build-data.py` writes
   * the same conversion out longhand; getting it backwards is this project's named failure mode and
   * would draw time running the wrong way.
   */
  from: string;
  to: string;
  kind: "claimed" | "context";
  /** 1-based gate-approval order for a claimed edge, `null` for context. DoD 3's "in the order it was walked". */
  order: number | null;
  verification: Verification | null;
}

export interface RenderGraph {
  nodes: RenderNode[];
  edges: RenderEdge[];
  claimed: number;
  /** Faint edges in the answer's OWN one-hop neighbourhood. */
  context: number;
  /**
   * Faint edges on screen only because the visitor opened something.
   *
   * Counted separately so the caption can stay true. It says the faint lines are connections the
   * corpus holds "around them", meaning around the answer — and three hops into a wander that is
   * false. Splitting the count is what lets the sentence keep matching the picture (D3).
   */
  opened: number;
  /** True when the one-hop neighbourhood was cut off by the cap. Said out loud, never implied away. */
  truncated: boolean;
}

/** What one query produced, reduced to the only three things the map is allowed to read. */
export interface RunView {
  claims: readonly Claim[];
  pathNodeIds: readonly string[];
  toolNodeIds: readonly string[];
  /**
   * Nodes the VISITOR opened by following an edge. Navigation only.
   *
   * Read exclusively by the context passes below. Nothing here can reach the claimed pass, and that
   * is the point rather than an implementation detail — see D2 in this file's header.
   */
  openedIds?: readonly string[];
}

/**
 * How much unwalked corpus to draw around the answer.
 *
 * Measured at step 3: the largest component is 458 nodes and the median degree is 1, so the
 * neighbourhood of a hub such as The Beatles (degree 25) would swamp a three-node answer without a
 * bound. 40 is a legibility number, not a performance one; canvas is comfortable far above it.
 */
export const MAX_CONTEXT_NODES = 40;

/**
 * How many further context nodes each deliberately opened node is allowed to bring with it.
 *
 * **Measured, not chosen.** The highest degree in artifact v0.5.0 is 25 and no node at all exceeds
 * 30, so this budget cannot truncate any single node's neighbourhood: opening a node shows all of
 * its connections or the corpus does not hold them. The automatic neighbourhood keeps its own
 * separate cap of 40, which is a legibility number for a picture nobody asked for — a deliberate
 * click is a different thing and gets a different budget.
 */
export const NEIGHBOURS_PER_OPEN = 30;

const pairKey = (from: string, to: string) => `${from}>${to}`;

/**
 * The node ids named in a tool call's arguments.
 *
 * Top-level string values shaped like a QID, so `node_id`, `from_id` and `to_id` are all picked up and
 * **a tool added later needs no edit here** — the same seam invariant 4 asks for on the backend.
 *
 * These are model-proposed arguments, not gate-approved claims, and they are used for exactly one
 * thing: deciding which part of the corpus to look at. That is navigation. A node id from here can put
 * a node on the map; it can never put a claim in the list.
 */
export function nodeIdsInArguments(args: Record<string, unknown>): string[] {
  return Object.values(args).filter(
    (value): value is string => typeof value === "string" && /^Q\d+$/.test(value),
  );
}

/** Ordered, de-duplicated, and filtered to ids the pinned corpus actually holds. */
function walkedIds(graph: StaticGraph, view: RunView): string[] {
  const seen = new Set<string>();
  const ordered: string[] = [];

  const add = (id: string) => {
    if (seen.has(id) || !graph.nodes.has(id)) return;
    seen.add(id);
    ordered.push(id);
  };

  // Claims first, so the nodes the gate approved anchor the layout before anything else does.
  for (const claim of view.claims) {
    add(claim.subject_id);
    add(claim.object_id);
  }
  for (const id of view.pathNodeIds) add(id);
  for (const id of view.toolNodeIds) add(id);

  return ordered;
}

export function buildRenderGraph(
  graph: StaticGraph,
  view: RunView,
  maxContextNodes: number = MAX_CONTEXT_NODES,
): RenderGraph {
  const walked = walkedIds(graph, view);
  const roles = new Map<string, NodeRole>(walked.map((id) => [id, "walked"]));

  const edges: RenderEdge[] = [];
  const drawn = new Set<string>();

  // 1. The claimed edges, in gate-approval order. A claim whose endpoints are not both in the pinned
  //    corpus is dropped rather than drawn: the gate only approves edges that exist in the artifact,
  //    so this can only happen when the SPA's graph and the answer's graph are different versions,
  //    and `StepPanel` refuses to draw the map at all in that case.
  view.claims.forEach((claim, index) => {
    if (!graph.nodes.has(claim.subject_id) || !graph.nodes.has(claim.object_id)) return;
    const key = pairKey(claim.object_id, claim.subject_id);
    if (drawn.has(key)) return;
    drawn.add(key);
    edges.push({
      from: claim.object_id,
      to: claim.subject_id,
      kind: "claimed",
      order: index + 1,
      verification: claim.verification,
    });
  });
  const claimed = edges.length;

  // 2. One hop of unwalked corpus around every walked node, capped and deterministic. Sorted by the
  //    neighbour's label so the same answer draws the same map twice, and so the cap cuts a stable
  //    set rather than whatever order the artifact happened to be written in.
  //
  // 3. Then the same again from whatever the visitor opened, on its own larger budget.
  //
  // Two passes rather than one over a combined list, purely so the two counts can be reported
  // separately. The caption promises the faint lines are what the corpus holds AROUND THE ANSWER,
  // and once someone has wandered, some of them are not — D3.
  let truncated = false;
  const contextNodeCount = () => roles.size - walked.length;

  const expand = (ids: readonly string[], ceiling: number): number => {
    const before = edges.length;

    for (const id of ids) {
      const incident = [...(graph.incident.get(id) ?? [])].sort((a, b) => {
        const left = graph.nodes.get(a.subject_id === id ? a.object_id : a.subject_id)?.label ?? "";
        const right =
          graph.nodes.get(b.subject_id === id ? b.object_id : b.subject_id)?.label ?? "";
        return left.localeCompare(right);
      });

      for (const edge of incident) {
        const other = edge.subject_id === id ? edge.object_id : edge.subject_id;

        if (!roles.has(other)) {
          if (contextNodeCount() >= ceiling) {
            truncated = true;
            continue;
          }
          roles.set(other, "context");
        }

        const key = pairKey(edge.object_id, edge.subject_id);
        if (drawn.has(key)) continue;
        drawn.add(key);
        edges.push({
          from: edge.object_id,
          to: edge.subject_id,
          kind: "context",
          order: null,
          verification: edge.verification,
        });
      }
    }

    return edges.length - before;
  };

  const context = expand(walked, maxContextNodes);

  // Opened ids the corpus does not hold are dropped, exactly as walked ids are. An id that IS held
  // but is not yet on the map is given a context role first: expanding from a node the picture does
  // not contain would draw edges to a node that is never drawn.
  const opened = (view.openedIds ?? []).filter((id) => graph.nodes.has(id));
  for (const id of opened) if (!roles.has(id)) roles.set(id, "context");

  const openedEdges =
    opened.length === 0 ? 0 : expand(opened, maxContextNodes + opened.length * NEIGHBOURS_PER_OPEN);

  const nodes: RenderNode[] = [...roles].flatMap(([id, role]) => {
    const node = graph.nodes.get(id);
    if (node === undefined) return [];
    return [
      {
        id,
        label: node.label,
        kind: node.kind,
        year: node.inception_year,
        role,
      },
    ];
  });

  return { nodes, edges, claimed, context, opened: openedEdges, truncated };
}
