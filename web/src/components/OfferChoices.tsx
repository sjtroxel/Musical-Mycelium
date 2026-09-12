import type { OfferCandidate, OfferFrame } from "../types";

/**
 * The choices offered when a typed name resolved to nothing.
 *
 * **This is the one screen in the app where the person, not the system, resolves a name.** A near-miss
 * suggester was measured and rejected for this project: Joy Orbison and Roy Orbison are one edit apart
 * and both are in the corpus, so automatic resolution trades an honest refusal for a confident answer
 * about the wrong person. Clicking is the whole mechanism. Nothing here resolves anything on its own,
 * and the refusal above it stays on the screen afterwards.
 *
 * **It is not a new colour, and that is a rule rather than a preference.** `StepPanel`'s own docstring
 * says a refusal is styled by a modifier that changes the heading wording only — no warning hue, no
 * icon, no lighter weight — because the visitor reads "broken" before they read a word. An offer sits
 * inside that same card at the same weight. If you find yourself reaching for a colour here, the
 * refusal has become an error state.
 *
 * **The candidate list is never ranked or truncated.** Over the cap the API sends no candidates at all
 * and states the count, so this component has two states to render and never a "top five". Which is
 * why `total` is read rather than `candidates.length` — see `SPEC.md` §6.
 */

/**
 * The question to ask when a candidate is chosen. D9.
 *
 * The original question with the matched term swapped for the chosen exact label, so "who did mozart
 * study with" becomes "who did Wolfgang Amadeus Mozart study with" rather than throwing the sentence
 * away and asking a bare name. The re-asked query then resolves by exact label like any other query —
 * **choosing a candidate does not resolve it, it asks a question that happens to resolve.**
 *
 * Three attempts, in order, because `term` is what the model passed to `resolve_node` and need not be
 * spelled the way the person typed it:
 *   1. a literal occurrence, which D9 specifies and which covers the ordinary case;
 *   2. a case-insensitive occurrence, so a model that title-cased the term does not cost the sentence;
 *   3. the bare label, D9's stated fallback, when the term is not in the query at all.
 */
export function reAsk(query: string, term: string, label: string): string {
  if (term !== "") {
    const literal = query.indexOf(term);
    if (literal !== -1) {
      return query.slice(0, literal) + label + query.slice(literal + term.length);
    }
    const folded = query.toLowerCase().indexOf(term.toLowerCase());
    if (folded !== -1) {
      return query.slice(0, folded) + label + query.slice(folded + term.length);
    }
  }
  return label;
}

/** Why this candidate is in the list. D7: an offer that cannot be explained is a guess with a button. */
function Because({ candidate }: { candidate: OfferCandidate }) {
  if (candidate.via === "label" || candidate.alias === null) return null;
  return <span className="offer__why">also known as &ldquo;{candidate.alias}&rdquo;</span>;
}

function Choices({
  offer,
  query,
  busy,
  onAsk,
}: {
  offer: OfferFrame;
  query: string;
  busy: boolean;
  onAsk: (query: string) => void;
}) {
  // D4's other state: too many to list, so the count is stated and more of the name is asked for.
  // `total` rather than `candidates.length`, which is 0 here and would report "no matches" for 34.
  if (offer.candidates.length === 0) {
    return (
      <p className="offer__broad">
        {offer.total} names in this graph contain &ldquo;{offer.term}&rdquo;. That is too many to
        choose between &mdash; try more of the name.
      </p>
    );
  }

  return (
    <ul className="offer__list">
      {offer.candidates.map((candidate) => (
        <li key={candidate.node_id}>
          <button
            type="button"
            className="offer__choice"
            disabled={busy}
            onClick={() => onAsk(reAsk(query, offer.term, candidate.label))}
          >
            <span className="offer__label">{candidate.label}</span>
            <Because candidate={candidate} />
          </button>
        </li>
      ))}
    </ul>
  );
}

export function OfferChoices({
  offers,
  query,
  busy = false,
  onAsk,
}: {
  offers: OfferFrame[];
  query: string;
  busy?: boolean;
  onAsk: (query: string) => void;
}) {
  if (offers.length === 0) return null;

  return (
    <section className="offer" aria-label="Did you mean">
      {offers.map((offer) => (
        <div className="offer__group" key={offer.term}>
          <h3 className="offer__heading">
            {offer.candidates.length === 0
              ? `“${offer.term}” matches too much`
              : offer.total === 1
                ? `This graph has one name like “${offer.term}”`
                : `This graph has ${offer.total} names like “${offer.term}”`}
          </h3>
          <Choices offer={offer} query={query} busy={busy} onAsk={onAsk} />
        </div>
      ))}
    </section>
  );
}
