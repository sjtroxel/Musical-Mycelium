import { cleanup, render, screen } from "@testing-library/react";
import { act } from "react";
import { createRoot } from "react-dom/client";
import { afterEach, describe, expect, it } from "vitest";
import { ClaimList, relationOf } from "./components/ClaimList";
import { WhenArtistsWereBorn } from "./components/CoveragePanel";
import type { ArtistFacts } from "./components/CoveragePanel";
import { split } from "./components/NodeInspector";
import { GraphView } from "./graph/GraphView";
import { layerOf } from "./graph/layout";
import {
  PREDICATE_INFLUENCED_BY,
  PREDICATE_PLAYS_GENRE,
  PREDICATE_STUDIED_WITH,
  indexArtifact,
} from "./graph/staticGraph";
import type { Artifact, ArtifactEdge, ArtifactNode } from "./graph/staticGraph";
import { buildRenderGraph, sharedTeachingPairs } from "./graph/subgraph";
import type { RenderEdge, RenderGraph, RenderNode } from "./graph/subgraph";
import type { Claim } from "./types";

/**
 * **Teaching is not influence, and no surface of the page may say it is.** Phase 7.6 step 8, trap 6.
 *
 * Four places could have lost the distinction, and each did in the code as it stood: the claim list
 * printed " influenced by " on every claim, the map stamped every claimed edge `influenced_by`, the
 * draw loop styled anything that was not influence as membership, and the inspector's split knew only
 * influence and membership, so teaching vanished from it. Each is asserted below in the form that
 * fails with the fix removed.
 *
 * Ids are Wikidata's real ones for these four people, read off artifact v0.10.0; the edges are the
 * ones it holds between them. Beethoven studied with Haydn AND was influenced by him, as two sourced
 * edges, which is the pair every "one picked out of two" failure shows up on.
 */

afterEach(cleanup);

const BEETHOVEN = "Q255";
const HAYDN = "Q7349";
const CZERNY = "Q215333";
const SALIERI = "Q51088";
const STUDIED = PREDICATE_STUDIED_WITH;
const INFLUENCED = PREDICATE_INFLUENCED_BY;

const person = (id: string, label: string, born: number): ArtifactNode => ({
  id,
  label,
  kind: "artist",
  inception_year: null,
  inception_precision: null,
  countries: [],
  birth_year: born,
  source: "wikidata",
  source_id: id,
  retrieved_at: "2026-09-11T00:00:00+00:00",
  revision_id: null,
});

const edge = (subject: string, object: string, predicate: string): ArtifactEdge => ({
  subject_id: subject,
  object_id: object,
  predicate,
  verification: predicate === STUDIED ? "TEACHING_PROSE_AUTO" : "HAND",
  prose_tier: "PROSE",
  source: "wikidata",
  source_id: `http://www.wikidata.org/entity/statement/${subject}-${predicate}`,
  retrieved_at: "2026-09-11T00:00:00+00:00",
});

const claim = (subject: string, object: string, predicate: string): Claim => ({
  subject_id: subject,
  predicate,
  object_id: object,
  source_ids: [`http://www.wikidata.org/entity/statement/${subject}-${predicate}`],
  verification: predicate === STUDIED ? "TEACHING_PROSE_AUTO" : "HAND",
  span: null,
});

const ARTIFACT: Artifact = {
  nodes: [
    person(BEETHOVEN, "Ludwig van Beethoven", 1770),
    person(HAYDN, "Joseph Haydn", 1732),
    person(CZERNY, "Carl Czerny", 1791),
    person(SALIERI, "Antonio Salieri", 1750),
  ],
  edges: [
    edge(BEETHOVEN, HAYDN, STUDIED),
    edge(BEETHOVEN, HAYDN, INFLUENCED),
    edge(BEETHOVEN, SALIERI, STUDIED),
    edge(CZERNY, BEETHOVEN, STUDIED),
  ],
};

const graph = indexArtifact("0.10.0", ARTIFACT);
const LABELS = new Map(ARTIFACT.nodes.map((node) => [node.id, node.label]));

// --- the claim list --------------------------------------------------------------------------------

describe("the claim list says each claim's own relationship", () => {
  it("words a teaching claim as study and an influence claim as influence", () => {
    const { container } = render(
      <ClaimList
        claims={[claim(BEETHOVEN, SALIERI, STUDIED), claim(BEETHOVEN, HAYDN, INFLUENCED)]}
        labels={LABELS}
      />,
    );
    const statements = [...container.querySelectorAll(".claim__statement")].map(
      (node) => node.textContent,
    );
    expect(statements).toEqual([
      "Ludwig van Beethoven studied with Antonio Salieri",
      "Ludwig van Beethoven influenced by Joseph Haydn",
    ]);
  });

  it("says what the teaching tier checked, never the raw constant", () => {
    render(<ClaimList claims={[claim(BEETHOVEN, SALIERI, STUDIED)]} labels={LABELS} />);
    expect(screen.queryByText("TEACHING_PROSE_AUTO")).toBeNull();
    expect(screen.getByText(/teacher named in the student's article prose/)).not.toBeNull();
  });

  it("prints an unknown predicate as itself rather than as either verb", () => {
    expect(relationOf(PREDICATE_PLAYS_GENRE)).toBe("plays genre");
    expect(relationOf("some_new_predicate")).not.toMatch(/influenced|studied/);
  });
});

// --- the render graph ----------------------------------------------------------------------------

const EMPTY = { pathNodeIds: [], toolNodeIds: [] };

describe("the map draws a teaching claim as teaching", () => {
  it("reads a claimed edge's predicate from its claim, teacher to student", () => {
    const rendered = buildRenderGraph(graph, {
      ...EMPTY,
      claims: [claim(BEETHOVEN, SALIERI, STUDIED)],
    });
    const claimed = rendered.edges.filter((e) => e.kind === "claimed");
    expect(claimed).toEqual([
      expect.objectContaining({ from: SALIERI, to: BEETHOVEN, predicate: STUDIED }),
    ]);
  });

  it("draws both edges of a pair approved under both predicates, not whichever came first", () => {
    const rendered = buildRenderGraph(graph, {
      ...EMPTY,
      claims: [claim(BEETHOVEN, HAYDN, STUDIED), claim(BEETHOVEN, HAYDN, INFLUENCED)],
    });
    const claimed = rendered.edges.filter((e) => e.kind === "claimed");
    expect(claimed.map((e) => e.predicate).sort()).toEqual([INFLUENCED, STUDIED]);
    expect([...sharedTeachingPairs(rendered.edges)]).toEqual([`${HAYDN}>${BEETHOVEN}`]);
  });

  it("still shows the influence edge as context when only the teaching one was claimed", () => {
    // Keyed on the pair alone, the claimed teaching edge would have marked the influence edge as
    // drawn, and a sourced statement would have silently left the picture.
    const rendered = buildRenderGraph(graph, {
      ...EMPTY,
      claims: [claim(BEETHOVEN, HAYDN, STUDIED)],
    });
    expect(rendered.edges).toContainEqual(
      expect.objectContaining({
        from: HAYDN,
        to: BEETHOVEN,
        kind: "context",
        predicate: INFLUENCED,
      }),
    );
  });

  it("refuses a claim whose predicate the gate cannot approve", () => {
    expect(() =>
      buildRenderGraph(graph, {
        ...EMPTY,
        claims: [claim(BEETHOVEN, HAYDN, PREDICATE_PLAYS_GENRE)],
      }),
    ).toThrow(/plays_genre/);
  });

  it("carries a person's birth year onto the node, and leaves `year` as inception", () => {
    const rendered = buildRenderGraph(graph, {
      ...EMPTY,
      claims: [claim(BEETHOVEN, SALIERI, STUDIED)],
    });
    const beethoven = rendered.nodes.find((n) => n.id === BEETHOVEN)!;
    expect(beethoven.born).toBe(1770);
    expect(beethoven.year).toBeNull();
  });
});

// --- layout ---------------------------------------------------------------------------------------

const renderNode = (id: string, label: string): RenderNode => ({
  id,
  label,
  kind: "artist",
  year: null,
  role: "walked",
  hidden: 0,
});

const renderEdge = (
  from: string,
  to: string,
  predicate: string,
  kind: RenderEdge["kind"] = "context",
): RenderEdge => ({
  from,
  to,
  kind,
  predicate,
  order: kind === "claimed" ? 1 : null,
  verification: null,
});

const NODES = [
  renderNode(HAYDN, "Joseph Haydn"),
  renderNode(BEETHOVEN, "Ludwig van Beethoven"),
  renderNode(CZERNY, "Carl Czerny"),
];

describe("teaching creates no influence depth", () => {
  it("gives the identical layering with the teaching edges removed", () => {
    // The plan keeps time ordering influence-only in this phase. Teaching runs the same way in time,
    // but moving a student a column right would be the map asserting the order through a relation
    // `layerOf` was never reviewed for.
    const withTeaching = layerOf(NODES, [
      renderEdge(HAYDN, BEETHOVEN, INFLUENCED),
      renderEdge(BEETHOVEN, CZERNY, STUDIED),
    ]);
    const without = layerOf(NODES, [renderEdge(HAYDN, BEETHOVEN, INFLUENCED)]);
    expect([...withTeaching.entries()].sort()).toEqual([...without.entries()].sort());
  });
});

// --- drawing --------------------------------------------------------------------------------------

interface Call {
  op: string;
  args: number[];
}

function draw(edges: RenderEdge[]): { calls: Call[]; caption: string } {
  const calls: Call[] = [];
  const rec =
    (op: string) =>
    (...args: unknown[]) => {
      calls.push({ op, args: args.filter((a): a is number => typeof a === "number") });
    };
  const ctx = {
    save: rec("save"),
    restore: rec("restore"),
    beginPath: rec("beginPath"),
    closePath: rec("closePath"),
    moveTo: rec("moveTo"),
    lineTo: rec("lineTo"),
    stroke: rec("stroke"),
    setLineDash: (pattern: number[]) => calls.push({ op: "setLineDash", args: pattern }),
    fill: rec("fill"),
    arc: rec("arc"),
    clearRect: rec("clearRect"),
    setTransform: rec("setTransform"),
    fillText: rec("fillText"),
    strokeText: rec("strokeText"),
    measureText: () => ({ width: 42 }),
    font: "",
    textAlign: "left",
    textBaseline: "middle",
    globalAlpha: 1,
    strokeStyle: "",
    fillStyle: "",
    lineWidth: 1,
  };

  const rendered: RenderGraph = {
    nodes: NODES,
    edges,
    claimed: edges.filter((e) => e.kind === "claimed").length,
    context: edges.filter((e) => e.kind === "context").length,
    opened: 0,
    truncated: false,
  };

  const outer = HTMLCanvasElement.prototype.getContext;
  HTMLCanvasElement.prototype.getContext = ((): unknown => ctx) as HTMLCanvasElement["getContext"];
  const host = document.createElement("div");
  document.body.append(host);
  const root = createRoot(host);
  act(() => root.render(<GraphView graph={rendered} motion="none" />));
  const caption = host.querySelector("figcaption")?.textContent ?? "";
  act(() => root.unmount());
  host.remove();
  HTMLCanvasElement.prototype.getContext = outer;
  return { calls, caption };
}

const dashesOf = (calls: Call[], pattern: number[]) =>
  calls.filter(
    (call) =>
      call.op === "setLineDash" &&
      call.args.length === pattern.length &&
      call.args.every((value, index) => value === pattern[index]),
  );

const TEACHING_DASH = [6, 3];
const MEMBERSHIP_DOTS = [1, 3];

describe("teaching is drawn as its own kind of line", () => {
  it("dashes a teaching context edge, and does not dot it as membership", () => {
    const { calls } = draw([renderEdge(BEETHOVEN, CZERNY, STUDIED)]);
    expect(dashesOf(calls, TEACHING_DASH)).not.toHaveLength(0);
    expect(dashesOf(calls, MEMBERSHIP_DOTS)).toHaveLength(0);
  });

  it("dashes a claimed teaching edge too: approval does not make it influence", () => {
    const { calls } = draw([renderEdge(BEETHOVEN, CZERNY, STUDIED, "claimed")]);
    expect(dashesOf(calls, TEACHING_DASH)).not.toHaveLength(0);
  });

  it("leaves influence solid, claimed or not", () => {
    const { calls } = draw([
      renderEdge(HAYDN, BEETHOVEN, INFLUENCED),
      renderEdge(HAYDN, BEETHOVEN, INFLUENCED, "claimed"),
    ]);
    expect(dashesOf(calls, TEACHING_DASH)).toHaveLength(0);
  });

  it("resets the dash so teaching cannot leak onto the lines after it", () => {
    const { calls } = draw([
      renderEdge(BEETHOVEN, CZERNY, STUDIED),
      renderEdge(HAYDN, BEETHOVEN, INFLUENCED),
    ]);
    const resets = calls.filter((call) => call.op === "setLineDash" && call.args.length === 0);
    expect(resets.length).toBeGreaterThanOrEqual(dashesOf(calls, TEACHING_DASH).length);
  });

  it("says what a dashed line means, and only when one is drawn", () => {
    expect(draw([renderEdge(BEETHOVEN, CZERNY, STUDIED)]).caption).toMatch(
      /Dashed lines are teaching/,
    );
    expect(draw([renderEdge(HAYDN, BEETHOVEN, INFLUENCED)]).caption).not.toMatch(/Dashed/);
  });
});

// --- the inspector --------------------------------------------------------------------------------

const others = (edges: ArtifactEdge[], self: string) =>
  edges.map((e) => (e.subject_id === self ? e.object_id : e.subject_id)).sort();

describe("the inspector names teaching as teaching", () => {
  it("lists a student's teachers under their own heading, apart from influence", () => {
    const { parents, children, membership, teachers, students } = split(graph, BEETHOVEN);
    expect(others(teachers, BEETHOVEN)).toEqual([SALIERI, HAYDN].sort());
    expect(others(students, BEETHOVEN)).toEqual([CZERNY]);
    // Haydn is in parents because of the separate INFLUENCE edge, and only once.
    expect(others(parents, BEETHOVEN)).toEqual([HAYDN]);
    expect(children).toHaveLength(0);
    expect(membership).toHaveLength(0);
  });

  it("does not swap teachers and students", () => {
    const { teachers, students } = split(graph, HAYDN);
    expect(teachers).toHaveLength(0);
    expect(others(students, HAYDN)).toEqual([BEETHOVEN]);
  });
});

// --- coverage ---------------------------------------------------------------------------------------

const BIRTHS: ArtistFacts = {
  artists: 2889,
  with_birth_year: 2652,
  born_before_1900: 2111,
  birth_eras: {
    "pre-1900": 2111,
    "1900-1949": 203,
    "1950-1969": 108,
    "1970-1989": 145,
    "1990-2009": 85,
    "2010-": 0,
    unknown: 237,
  },
};

describe("the coverage panel counts artists by birth, and says what that is not", () => {
  it("states the born-before-1900 figure with its skew in the same sentence block", () => {
    const { container } = render(<WhenArtistsWereBorn figures={BIRTHS} />);
    const note = container.querySelector(".cov__note")!.textContent!;
    expect(note).toMatch(/2111 of the 2889 artists were born before 1900/);
    expect(note).toMatch(/not a period of activity/);
    expect(note).toMatch(/Western European/);
  });

  it("draws the artists with no birth year as a bucket rather than dropping them", () => {
    const { container } = render(<WhenArtistsWereBorn figures={BIRTHS} />);
    const total = [...container.querySelectorAll(".cov__rowCount")].reduce(
      (sum, node) => sum + Number(node.textContent),
      0,
    );
    expect(total).toBe(BIRTHS.artists);
  });

  it("says a corpus with no birth years has none, instead of reporting a zero as a measurement", () => {
    const none: ArtistFacts = {
      ...BIRTHS,
      artists: 804,
      with_birth_year: 0,
      born_before_1900: 0,
      birth_eras: { ...BIRTHS.birth_eras, "pre-1900": 0, unknown: 804 },
    };
    const { container } = render(<WhenArtistsWereBorn figures={none} />);
    expect(container.textContent).toMatch(/records no birth year for any of its 804 artists/);
    expect(container.textContent).not.toMatch(/born before 1900/);
  });
});
