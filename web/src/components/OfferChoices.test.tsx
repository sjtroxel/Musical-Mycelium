import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { OfferChoices, reAsk } from "./OfferChoices";
import type { OfferCandidate, OfferFrame } from "../types";

/**
 * Phase 7.7 step 5.
 *
 * The property under test is not "the buttons render". It is that **a click asks a question and does
 * not resolve a name**: the re-asked query goes back through the same resolver every other query uses,
 * so an alias can never become a resolution by way of the interface. `reAsk` is exported and tested
 * directly because it is the only logic on this path, and a wrong substitution would silently ask about
 * the wrong thing while looking like it worked.
 */

afterEach(cleanup);

function candidate(overrides: Partial<OfferCandidate> = {}): OfferCandidate {
  return {
    node_id: "Q254",
    label: "Wolfgang Amadeus Mozart",
    kind: "artist",
    via: "label",
    alias: null,
    ...overrides,
  };
}

const MOZART: OfferFrame = {
  type: "offer",
  term: "mozart",
  total: 5,
  shown: 5,
  candidates: [
    candidate(),
    candidate({ node_id: "Q156280", label: "Leopold Mozart" }),
    candidate({ node_id: "Q156023", label: "Franz Xaver Wolfgang Mozart" }),
    candidate({
      node_id: "Q179257",
      label: "Timbaland",
      via: "alias",
      alias: "Mozart Timadeas",
    }),
    candidate({
      node_id: "Q1969627",
      label: "Samuel Wesley",
      via: "alias",
      alias: "The English Mozart",
    }),
  ],
};

/** D4's other state, captured from the API in `metal-offer-over-cap.sse`. */
const METAL: OfferFrame = {
  type: "offer",
  term: "metal",
  total: 34,
  shown: 0,
  candidates: [],
};

describe("reAsk", () => {
  it("keeps the sentence and swaps only the matched term", () => {
    expect(reAsk("who did mozart study with", "mozart", "Wolfgang Amadeus Mozart")).toBe(
      "who did Wolfgang Amadeus Mozart study with",
    );
  });

  it("swaps a term the model spelled with different case", () => {
    // `term` is what the model passed to `resolve_node`, not what the person typed.
    expect(reAsk("Where did mozart come from?", "Mozart", "Leopold Mozart")).toBe(
      "Where did Leopold Mozart come from?",
    );
  });

  it("replaces only the first occurrence, leaving a repeated word alone", () => {
    expect(reAsk("mozart and mozart", "mozart", "Leopold Mozart")).toBe(
      "Leopold Mozart and mozart",
    );
  });

  it("falls back to the bare label when the term is not in the query", () => {
    // D9's stated fallback. Asking a mangled sentence would be worse than asking the plain name.
    expect(reAsk("tell me about the composer", "mozart", "Leopold Mozart")).toBe("Leopold Mozart");
    expect(reAsk("anything", "", "Leopold Mozart")).toBe("Leopold Mozart");
  });
});

describe("OfferChoices", () => {
  it("renders nothing when there is nothing to choose between", () => {
    const { container } = render(
      <OfferChoices offers={[]} query="Where did zzz come from?" onAsk={() => {}} />,
    );
    expect(container.innerHTML).toBe("");
  });

  it("offers every candidate and says why the noisy ones are there", () => {
    render(<OfferChoices offers={[MOZART]} query="Where did mozart come from?" onAsk={() => {}} />);

    expect(screen.getAllByRole("button")).toHaveLength(5);
    expect(screen.getByText("Timbaland")).toBeTruthy();
    // D7. Without this the list looks like a mistake rather than an honest noisy source.
    expect(screen.getByText(/also known as .Mozart Timadeas./)).toBeTruthy();
    expect(screen.getByText(/also known as .The English Mozart./)).toBeTruthy();
    // A label match needs no explanation, and giving it one would be noise on four rows out of five.
    expect(screen.queryAllByText(/also known as/)).toHaveLength(2);
  });

  it("asks the original question with the chosen label substituted", () => {
    const onAsk = vi.fn();
    render(<OfferChoices offers={[MOZART]} query="Where did mozart come from?" onAsk={onAsk} />);

    fireEvent.click(screen.getByText("Timbaland"));
    // The point of D9: a question, not a resolution. "Timbaland" then resolves by exact label the way
    // any typed name does, so the alias never resolved anything.
    expect(onAsk).toHaveBeenCalledWith("Where did Timbaland come from?");
  });

  it("states the count and asks for more of the name when the list is capped away", () => {
    render(<OfferChoices offers={[METAL]} query="Where did metal come from?" onAsk={() => {}} />);

    // `total`, never `candidates.length` -- which is 0 here and would read as "no matches" for 34.
    expect(screen.getByText(/34 names in this graph/)).toBeTruthy();
    expect(screen.getByText(/try more of the name/)).toBeTruthy();
    expect(screen.queryAllByRole("button")).toHaveLength(0);
  });

  it("reads its heading from total, not from the rendered row count", () => {
    const one: OfferFrame = {
      ...MOZART,
      term: "dolly",
      total: 1,
      shown: 1,
      candidates: [candidate({ node_id: "Q40912", label: "Dolly Parton" })],
    };
    render(<OfferChoices offers={[one]} query="Where did dolly come from?" onAsk={() => {}} />);
    expect(screen.getByText(/one name like .dolly./)).toBeTruthy();
  });

  it("disables every choice while a run is in flight", () => {
    render(<OfferChoices offers={[MOZART]} query="q" busy onAsk={() => {}} />);
    for (const button of screen.getAllByRole("button")) {
      expect((button as HTMLButtonElement).disabled).toBe(true);
    }
  });

  it("keeps both offers when one query failed to resolve two names", () => {
    const second: OfferFrame = { ...MOZART, term: "bach", total: 14, shown: 14 };
    render(<OfferChoices offers={[MOZART, second]} query="q" onAsk={() => {}} />);
    expect(screen.getByText(/5 names like .mozart./)).toBeTruthy();
    expect(screen.getByText(/14 names like .bach./)).toBeTruthy();
  });
});
