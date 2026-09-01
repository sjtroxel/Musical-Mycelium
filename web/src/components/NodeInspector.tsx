import type { ArtifactEdge, StaticGraph } from "../graph/staticGraph";
import type { RenderNode } from "../graph/subgraph";

/**
 * What one node is, and where you can go from it.
 *
 * **This is the accessible half of the map, not a panel bolted next to it — decision D4.** A canvas
 * has no elements, so a click-only map is unreachable by keyboard and invisible to a screen reader.
 * Everything the canvas lets you do with a pointer is a real `<button>` here: choosing a node,
 * following an edge out of it, revealing its connections, asking the agent about it. The canvas
 * keeps `role="img"` with a written description and is the shortcut, not the only way in.
 *
 * That is also why the no-selection state exists. Without it a keyboard user could operate the
 * inspector but could never open it, because the only way to select a first node would be a click on
 * a picture they cannot point at.
 *
 * **What this panel may and may not say.** It reads the pinned artifact directly, so every sentence
 * here is about what the CORPUS holds — never about what the answer found. Following an edge from
 * here reveals corpus and cannot approve anything: claims come from `claim` frames and nowhere else
 * (`.claude/rules/grounding-and-claims.md`). "Trace this" is the one control that produces claims,
 * and it does it the long way round — a real `/lineage` query, a real traversal, the same gate.
 */

/** Which way the influence runs, from this node's point of view. */
function split(
  graph: StaticGraph,
  id: string,
): { parents: ArtifactEdge[]; children: ArtifactEdge[] } {
  const incident = [...(graph.incident.get(id) ?? [])];
  return {
    // `subject influenced_by object`: influence runs object -> subject. So an edge where THIS node
    // is the subject is one of its parents. Getting this backwards is the project's named failure
    // mode and it would label the whole panel the wrong way round.
    parents: incident.filter((edge) => edge.subject_id === id),
    children: incident.filter((edge) => edge.object_id === id),
  };
}

const other = (edge: ArtifactEdge, id: string): string =>
  edge.subject_id === id ? edge.object_id : edge.subject_id;

/**
 * The question to ask the agent about this node.
 *
 * Both wordings are shapes the corpus and the planner already handle — they are two of the five
 * canonical chips in `chips.json`, which `tests/test_chips.py` validates against the artifact. An
 * invented phrasing would be the interface guessing at what the agent can parse.
 */
export function annotationQuery(node: RenderNode): string {
  return node.kind === "artist"
    ? `Who influenced ${node.label}?`
    : `Where did ${node.label} come from?`;
}

function NeighbourList({
  title,
  edges,
  id,
  graph,
  onFollow,
}: {
  title: string;
  edges: ArtifactEdge[];
  id: string;
  graph: StaticGraph;
  onFollow: (fromId: string, toId: string) => void;
}) {
  if (edges.length === 0) return null;

  const named = edges
    .map((edge) => {
      const neighbourId = other(edge, id);
      return {
        id: neighbourId,
        label: graph.nodes.get(neighbourId)?.label ?? neighbourId,
      };
    })
    .sort((left, right) => left.label.localeCompare(right.label));

  return (
    <div className="inspector__group">
      <h4 className="inspector__groupTitle">{title}</h4>
      <ul className="inspector__list">
        {named.map((neighbour) => (
          <li key={neighbour.id}>
            <button
              type="button"
              className="inspector__link"
              onClick={() => onFollow(id, neighbour.id)}
            >
              {neighbour.label}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

export function NodeInspector({
  node,
  graph,
  walkedNodes,
  opened,
  busy,
  onSelect,
  onOpen,
  onFollow,
  onAnnotate,
}: {
  node: RenderNode | null;
  graph: StaticGraph;
  /** The nodes this answer reached, so the map can be entered without pointing at it. */
  walkedNodes: RenderNode[];
  opened: boolean;
  busy: boolean;
  onSelect: (id: string | null) => void;
  onOpen: (id: string) => void;
  onFollow: (fromId: string, toId: string) => void;
  onAnnotate: (query: string) => void;
}) {
  if (node === null) {
    if (walkedNodes.length === 0) return null;
    return (
      <details className="inspector inspector--closed">
        <summary className="inspector__summary">Explore this map without pointing at it</summary>
        <ul className="inspector__list">
          {walkedNodes.map((walked) => (
            <li key={walked.id}>
              <button type="button" className="inspector__link" onClick={() => onSelect(walked.id)}>
                {walked.label}
              </button>
            </li>
          ))}
        </ul>
      </details>
    );
  }

  const { parents, children } = split(graph, node.id);
  const degree = parents.length + children.length;

  return (
    <aside className="inspector" aria-label={`About ${node.label}`}>
      <div className="inspector__head">
        <h3 className="inspector__title">{node.label}</h3>
        <button
          type="button"
          className="inspector__close"
          onClick={() => onSelect(null)}
          aria-label="Close"
        >
          &times;
        </button>
      </div>

      <p className="inspector__facts">
        {node.kind}
        {node.year === null ? ", no inception date in the corpus" : `, ${node.year}`}.{" "}
        {/* Which of the two things this node is, said in words. A visitor who clicks a faint dot
            must not be left to infer from a ring whether the answer went there. */}
        {node.role === "walked"
          ? "Reached by this answer."
          : "Held by the corpus around this answer, and not walked by it."}{" "}
        <a
          className="inspector__source"
          href={`https://www.wikidata.org/wiki/${node.id}`}
          target="_blank"
          rel="noreferrer"
        >
          {node.id}
        </a>
      </p>

      {degree === 0 ? (
        <p className="inspector__facts">
          {/* Never a negative claim about the music — the same rule the refusal panel follows. */}
          The corpus records no influences for this node in either direction. That is the state of
          the sources, not a finding about the music.
        </p>
      ) : (
        <>
          {!opened && (
            <button type="button" className="inspector__action" onClick={() => onOpen(node.id)}>
              Show its {degree} {degree === 1 ? "connection" : "connections"} on the map
            </button>
          )}

          <NeighbourList
            title="Came out of"
            edges={parents}
            id={node.id}
            graph={graph}
            onFollow={onFollow}
          />
          <NeighbourList
            title="Led to"
            edges={children}
            id={node.id}
            graph={graph}
            onFollow={onFollow}
          />
        </>
      )}

      {/* The one control here that costs money and produces claims. Everything above reads a file
          that is already in the browser; this asks the agent, and the answer comes back through the
          gate like any other. Disabled while a stream is in flight — see `annotate`. */}
      <button
        type="button"
        className="inspector__action inspector__action--ask"
        onClick={() => onAnnotate(annotationQuery(node))}
        disabled={busy}
      >
        Ask the agent about {node.label}
      </button>
    </aside>
  );
}
