import { PREDICATE_INFLUENCED_BY, PREDICATE_PLAYS_GENRE } from "../graph/staticGraph";
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

/**
 * This node's neighbours, separated by what the corpus actually says about each one.
 *
 * **Three lists, not two, and the third is why this function changed at phase 6 step 8.** Until
 * artifact v0.7.1 every incident edge was `influenced_by`, so subject/object was the only question
 * worth asking. v0.7.1 added 2,782 `plays_genre` edges, stored as `artist plays_genre genre` — and
 * run through the old two-way split they landed in the influence lists by their subject/object
 * position alone. The panel would have said Miles Davis **came out of** jazz, and jazz **led to**
 * Fred Astaire. That is derivation asserted in plain English about a membership fact, which is the
 * failure `CLAUDE.md` names and the map's dotted line exists to prevent in ink.
 *
 * Membership is therefore filtered out of both influence lists and returned as its own, with its own
 * heading. Playing a genre is not descent from it in either direction.
 */
export function split(
  graph: StaticGraph,
  id: string,
): { parents: ArtifactEdge[]; children: ArtifactEdge[]; membership: ArtifactEdge[] } {
  const incident = [...(graph.incident.get(id) ?? [])];
  const influence = incident.filter((edge) => edge.predicate === PREDICATE_INFLUENCED_BY);
  return {
    // `subject influenced_by object`: influence runs object -> subject. So an edge where THIS node
    // is the subject is one of its parents. Getting this backwards is the project's named failure
    // mode and it would label the whole panel the wrong way round.
    parents: influence.filter((edge) => edge.subject_id === id),
    children: influence.filter((edge) => edge.object_id === id),
    membership: incident.filter((edge) => edge.predicate === PREDICATE_PLAYS_GENRE),
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

  const { parents, children, membership } = split(graph, node.id);
  const degree = parents.length + children.length + membership.length;

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
          The corpus records no influences and no genre membership for this node in either
          direction. That is the state of the sources, not a finding about the music.
        </p>
      ) : (
        <>
          {/* Step 9, DoD 7, and the accessible half of the map's completeness marking (D4). The
              canvas can say "there is more here" with a stroke; only this can say how much, and a
              keyboard user gets the same information rather than a hint they cannot see.

              Driven by `hidden` rather than by whether the visitor clicked, which also fixes a
              small standing defect: `openedIds` holds only nodes someone followed, so a WALKED node
              — whose neighbours the automatic pass has already drawn — used to offer a button that
              revealed nothing. */}
          {node.hidden > 0 ? (
            <button type="button" className="inspector__action" onClick={() => onOpen(node.id)}>
              Show its {node.hidden} further {node.hidden === 1 ? "connection" : "connections"} on
              the map
            </button>
          ) : (
            <p className="inspector__facts">
              All {degree} of its recorded {degree === 1 ? "connection is" : "connections are"} on
              the map. That is everything the corpus holds about this node, not everything there is
              to know about the music.
            </p>
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
          {/* Membership, and the heading carries the whole distinction. "Came out of" and "Led to"
              are claims about descent; this one is a claim about who worked where, and it is
              deliberately worded so it cannot be read as either. It reads differently depending on
              which end you are standing at, because the relation is not symmetric in English even
              though it is one edge. */}
          <NeighbourList
            title={node.kind === "artist" ? "Played in" : "Artists recorded in it"}
            edges={membership}
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
