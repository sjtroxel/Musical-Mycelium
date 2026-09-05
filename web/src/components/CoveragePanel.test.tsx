import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import facts from "../corpus-facts.json";
import { CoveragePanel, NAMED_PLACES } from "./CoveragePanel";

/**
 * **DoD 7: coverage is visible in the interface, not disclaimed in a footnote.**
 *
 * The figures themselves are checked against the pinned artifact by `tests/test_corpus_facts.py`, so
 * nothing here re-asserts arithmetic. What these tests guard is the part Python cannot see: that the
 * figures reach the screen, that the ones which must not be read alone are rendered together, and
 * that the panel is open rather than tucked behind a closed disclosure.
 *
 * The step 8 lesson this file is written against: **two tests passed with the rule they guarded
 * deleted**, and the tell in both was an assertion weaker than the behaviour it was named after -- a
 * bound instead of a resting place, a DOM flag instead of the effect. So these assert the rendered
 * numbers, not that "some text is present"; and the counterweight test asserts co-location in one
 * element, not that both figures appear somewhere on the page.
 */

afterEach(cleanup);

const panel = () =>
  screen.getByText("What this corpus covers").closest<HTMLDetailsElement>("details")!;

describe("the coverage panel", () => {
  it("is open on arrival, because a closed disclosure is a footnote with a triangle", () => {
    render(<CoveragePanel answeredVersion={null} />);
    expect(panel().open).toBe(true);
  });

  it("draws the undated genres as a bucket rather than dropping them", () => {
    render(<CoveragePanel answeredVersion={null} />);

    // The `unknown` era bucket is the whole reason `Coverage` does not report a tidier 141. A
    // histogram that silently omitted it would be the footnote this step removes, drawn as a chart.
    const row = screen.getByText("no date recorded").closest<HTMLElement>(".cov__row")!;
    expect(within(row).queryByText(String(facts.coverage.eras.unknown))).not.toBeNull();

    // Every genre is accounted for on screen: the six periods plus the absence bucket.
    const drawn = [...panel().querySelectorAll(".cov__axis")][0]!.querySelectorAll(
      ".cov__rowCount",
    );
    const total = [...drawn].reduce((sum, node) => sum + Number(node.textContent), 0);
    expect(total).toBe(facts.coverage.genres);
  });

  it("renders the US and UK counts and the figures that keep them from being the whole story", () => {
    render(<CoveragePanel answeredVersion={null} />);

    const where = screen
      .getByRole("heading", { name: "Where" })
      .closest<HTMLElement>(".cov__axis")!;
    const us = within(where).getByText("United States").closest<HTMLElement>(".cov__row")!;
    expect(
      within(us).queryByText(String(facts.coverage.countries["United States"])),
    ).not.toBeNull();

    // CONCENTRATION IS NOT ABSENCE. Asserting co-location in ONE element, not mere presence on the
    // page: the failure this guards against is the counterweight drifting into a note somewhere
    // below, which is exactly the arrangement DoD 7 calls a footnote.
    const note = within(where).getByText(/name a place that is/);
    expect(note.textContent).toContain(String(facts.coverage.genres_without_us_or_uk));
    expect(note.textContent).toContain(String(facts.coverage.distinct_countries));
    expect(note.textContent).toContain(String(facts.coverage.without_country));
  });

  it("names every place in the long tail rather than summarising it away", () => {
    render(<CoveragePanel answeredVersion={null} />);

    const where = screen
      .getByRole("heading", { name: "Where" })
      .closest<HTMLElement>(".cov__axis")!;
    const tail = where.querySelector<HTMLElement>(".cov__tailLabel")!;

    // Spread is the counterweight to concentration, so the tail has to be legible as places, not as
    // a number. Angola appearing by name is the difference between "and 21 others" and a corpus a
    // reader can see the shape of.
    for (const place of Object.keys(facts.coverage.countries)) {
      const shown =
        tail.textContent?.includes(place) ||
        within(where).queryAllByText(place).length > 0 ||
        false;
      expect(shown, `${place} is not on screen`).toBe(true);
    }
    expect(where.querySelectorAll(".cov__tick")).toHaveLength(
      facts.coverage.distinct_countries - NAMED_PLACES,
    );
  });

  it("says how many genres have no recorded origin, in that direction and not the other", () => {
    render(<CoveragePanel answeredVersion={null} />);

    // `subject influenced_by object`, so this is a count of genres the corpus records no ORIGIN for.
    // The wording is the assertion: "no recorded origin" and "where they came from" are the two
    // phrases that would have to change if someone flipped the direction, and this project has
    // silently answered the opposite question three times in one night before.
    const note = screen.getByText(/have no recorded origin at all/);
    expect(note.textContent).toContain(String(facts.density.genres_without_recorded_origins));
    expect(note.textContent).toContain("where they came from");
  });

  it("draws the connection histogram over every genre", () => {
    render(<CoveragePanel answeredVersion={null} />);

    const how = screen
      .getByRole("heading", { name: "How densely" })
      .closest<HTMLElement>(".cov__axis")!;
    const counts = [...how.querySelectorAll(".cov__rowCount")].map((node) =>
      Number(node.textContent),
    );
    expect(counts.reduce((sum, count) => sum + count, 0)).toBe(facts.coverage.genres);

    const one = within(how).getByText("1 connection").closest<HTMLElement>(".cov__row")!;
    expect(within(one).queryByText(String(facts.density.connections["1"]))).not.toBeNull();
  });

  it("uses no accent fill anywhere, because nothing here was approved by a gate", () => {
    const { container } = render(<CoveragePanel answeredVersion={null} />);

    // Step 6 fixed the accent's meaning. A coverage bar carrying it would say the corpus's shape had
    // been through the gate, which is the palette making a claim the words are careful not to.
    for (const node of container.querySelectorAll<HTMLElement>("[style]")) {
      expect(node.getAttribute("style")).not.toContain("--accent");
    }
    expect(container.querySelectorAll(".cov__bar").length).toBeGreaterThan(0);
  });

  it("says so when the answer came from a different corpus than these figures describe", () => {
    render(<CoveragePanel answeredVersion="9.9.9" />);

    const warning = screen.getByText(/describe corpus v/);
    expect(warning.textContent).toContain(facts.artifact_version);
    expect(warning.textContent).toContain("9.9.9");
  });

  it("stays quiet when the answer came from the corpus it describes", () => {
    render(<CoveragePanel answeredVersion={facts.artifact_version} />);
    expect(screen.queryByText(/describe corpus v/)).toBeNull();
  });
});

describe("where the sources disagree", () => {
  it("shows both directions of every contested pair and names both sources", () => {
    // The honest presentation, and the rule it comes from: flag disagreement, do not resolve it.
    // A display showing one direction would be the product picking a winner it has no basis to.
    const { container } = render(<CoveragePanel answeredVersion={null} />);
    const pairs = container.querySelectorAll<HTMLElement>(".cov__contestedPair");

    expect(pairs.length).toBe(facts.corroboration.contested.length);

    facts.corroboration.contested.forEach((pair, index) => {
      const rendered = pairs[index]!;
      const sides = rendered.querySelectorAll(".cov__contestedSide");
      expect(sides.length).toBe(2);

      // Both labels appear on both lines, in opposite roles.
      expect(rendered.textContent).toContain(pair.a.label);
      expect(rendered.textContent).toContain(pair.b.label);
      // And both sources are named, so a reader can see the disagreement is BETWEEN sources rather
      // than an inconsistency inside one.
      expect(rendered.textContent).toContain(pair.a_from_b.source);
      expect(rendered.textContent).toContain(pair.b_from_a.source);
      expect(pair.a_from_b.source).not.toBe(pair.b_from_a.source);
    });
  });

  it("reports the reciprocal count beside the contested one, never alone", () => {
    // 6 reciprocal, 2 contested at v0.7.1. The contested number alone reads as "everything else
    // agrees"; the reciprocal number alone overstates disagreement by 3x. The gap between them is
    // the finding, so both have to be on screen.
    render(<CoveragePanel answeredVersion={null} />);

    const note = screen.getByText(/pairs that point/);
    expect(note.textContent).toContain(String(facts.corroboration.reciprocal_pairs));
    expect(note.textContent).toContain(String(facts.corroboration.contested.length));
  });

  it("states the single-source denominator, because it is the limit of the claim", () => {
    // 2,202 of 2,284 influence edges have one source. Without this, "the sources disagree here"
    // reads as a survey of what is disputed about music rather than as what two sources happen to
    // contradict on the 82 edges where both speak.
    render(<CoveragePanel answeredVersion={null} />);

    const note = screen.getByText(/have exactly one source/);
    expect(note.textContent).toContain(String(facts.corroboration.single_source));
    expect(note.textContent).toContain(String(facts.corroboration.influence_edges));
    expect(note.textContent).toContain(String(facts.corroboration.corroborated));
  });

  it("does not put the accent on a contested pair", () => {
    // The accent means gate-approved. A contested pair is the one thing on this panel that is
    // emphatically not settled, so it must not borrow the colour that says something is.
    const { container } = render(<CoveragePanel answeredVersion={null} />);
    for (const pair of container.querySelectorAll<HTMLElement>(".cov__contestedPair")) {
      expect(pair.getAttribute("style") ?? "").not.toContain("--accent");
    }
  });
});
