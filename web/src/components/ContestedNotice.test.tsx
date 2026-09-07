import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import { ContestedNotice } from "./ContestedNotice";
import type { ContestedFrame } from "../types";

function edge(subject: string, object: string, source: string) {
  return {
    subject_id: subject,
    predicate: "influenced_by",
    object_id: object,
    source,
    source_id: `${source}:${subject}`,
    retrieved_at: "2026-09-04T00:00:00+00:00",
    prose_tier: "PROSE",
    verification: "PROSE_AUTO" as const,
    corroboration: null,
  };
}

const PAIR: ContestedFrame = {
  type: "contested",
  pair: {
    a: "Q188450",
    b: "Q861823",
    a_from_b: edge("Q188450", "Q861823", "wikidata"),
    b_from_a: edge("Q861823", "Q188450", "dbpedia"),
  },
  a_label: "electropop",
  b_label: "electroclash",
};

afterEach(cleanup);

describe("ContestedNotice", () => {
  it("renders nothing when the sources agree, which is the ordinary case", () => {
    // 2,202 of 2,284 influence edges are single-source, so an empty list is not an edge case.
    const { container } = render(<ContestedNotice contested={[]} />);
    expect(container.innerHTML).toBe("");
  });

  it("names both sources", () => {
    render(<ContestedNotice contested={[PAIR]} />);
    expect(screen.queryByText("wikidata")).not.toBeNull();
    expect(screen.queryByText("dbpedia")).not.toBeNull();
  });

  it("states both directions rather than choosing one", () => {
    render(<ContestedNotice contested={[PAIR]} />);
    const text = screen.getByLabelText("Where the sources disagree").textContent ?? "";
    // Both orderings appear. A component that rendered one direction would be picking a winner in
    // markup, which the corpus does not license: it records a disagreement, not a verdict.
    expect(text).toContain("wikidata");
    expect(text).toContain("dbpedia");
    expect(text.indexOf("electropop")).toBeGreaterThan(-1);
    expect(text.indexOf("electroclash")).toBeGreaterThan(-1);
    expect(text).toContain("does not resolve which is right");
  });

  it("never presents the disagreement as a verification tier", () => {
    render(<ContestedNotice contested={[PAIR]} />);
    const text = screen.getByLabelText("Where the sources disagree").textContent ?? "";
    // `verification` says how strongly ONE source was checked; this says a SECOND source contradicts
    // it. A UI showing one number where there are two has reintroduced the defect.
    expect(text).not.toContain("PROSE_AUTO");
    expect(text).not.toContain("a person read the source article");
  });
});
