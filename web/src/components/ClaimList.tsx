import type { Claim } from "../types";
import { STREAMED_DELAY } from "../graph/motion";
import { PREDICATE_INFLUENCED_BY, PREDICATE_STUDIED_WITH } from "../graph/staticGraph";
import { shortSourceId, wikidataUrl } from "../wikidata";

/**
 * The relationship a claim states, in words, **read from its predicate** (phase 7.6 step 8).
 *
 * This said " influenced by " on every claim until teaching became claimable, which would have
 * printed "Ludwig van Beethoven influenced by Joseph Haydn" under a source that says "student of".
 * A predicate with no entry here prints as its own name rather than falling back to either verb: the
 * rule in `SPEC.md` §7 is that a claim's predicate is always shown, and a fallback verb is how a new
 * one would be shown as something it is not.
 */
const PREDICATE_WORDING: Record<string, string> = {
  [PREDICATE_INFLUENCED_BY]: "influenced by",
  [PREDICATE_STUDIED_WITH]: "studied with",
};

export const relationOf = (predicate: string): string =>
  PREDICATE_WORDING[predicate] ?? predicate.split("_").join(" ");

/**
 * Human-readable wording for the verification tier.
 *
 * **These say how hard ONE source was checked. They are not a count of agreeing sources and not a
 * disputed flag.** Whether a second source agrees is `Edge.corroboration`, a different field with a
 * different guarantee, and collapsing the two is reading the opposite of the truth. Wording that
 * implied consensus would be the "grounded slides into correct" failure `CLAUDE.md` forbids.
 *
 * *(This read "every edge in this corpus has exactly one source, always Wikidata, so nothing here
 * could corroborate anything" until phase 6 step 8, citing decision A1. A1 was correct when written
 * and closed by its own stated precondition arriving: v0.7.0 ingested DBpedia. 2,202 of 2,284
 * influence edges are still single-source.)*
 *
 * **Three tiers were missing here and a real claim carried one of them.** Until step 8 this map held
 * only the original four, so an `INFOBOX_AUTO` claim fell through the `??` below and printed the raw
 * constant at a reader.
 */
const VERIFICATION_WORDING: Record<string, string> = {
  HAND: "a person read the source article",
  PROSE_AUTO: "an automated check found the object named in the article prose",
  ASSERTS_AUTO: "an automated check found the article asserting the influence",
  EXPOSURE_AUTO: "an automated check found evidence of exposure, not of influence",
  // Deliberately says "the same article". INFOBOX_AUTO is one page agreeing with itself -- the
  // candidate came from the infobox and the confirmation from that article's own prose -- so it is
  // WEAKER than PROSE_AUTO, not stronger, and must never read as two sources agreeing.
  INFOBOX_AUTO: "an automated check found the object in the same article's infobox and its prose",
  // These sit on `plays_genre` edges, which the gate never approves, so they cannot appear on a
  // claim. They are here because the map draws membership as context and the inspector names it.
  MEMBERSHIP_CITED: "a genre membership statement carrying a reference",
  MEMBERSHIP_BARE: "a genre membership statement with no reference beyond the statement itself",
  // Teaching, artifact v0.10.0. The hand check found about one in ten of these resting on a sentence
  // that names the teacher without being about study, so the wording says what was checked and stops.
  TEACHING_PROSE_AUTO:
    "an automated check found the teacher named in the student's article prose, not that the sentence is about study",
};

interface Props {
  claims: Claim[];
  labels: Map<string, string>;
}

export function ClaimList({ claims, labels }: Props) {
  if (claims.length === 0) return null;

  const name = (id: string) => labels.get(id) ?? id;

  return (
    <section className="claims" aria-label="Approved claims">
      <h3 className="claims__heading">
        {claims.length} cited {claims.length === 1 ? "claim" : "claims"}
      </h3>
      <ol className="claims__list">
        {/* Phase 7 step 4. `STREAMED_DELAY` is zero on purpose: these arrive one at a time as the gate
            approves them, so the stream has already staggered them with the real timing of the real
            work. The key is stable per position, so an appended claim mounts and animates while the
            ones above it stay exactly where they are. */}
        {claims.map((claim, index) => (
          <li
            className="claim enter"
            style={STREAMED_DELAY as React.CSSProperties}
            key={`${claim.subject_id}-${claim.object_id}-${index}`}
          >
            <p className="claim__statement">
              <span className="claim__node">{name(claim.subject_id)}</span>
              <span className="claim__predicate"> {relationOf(claim.predicate)} </span>
              <span className="claim__node">{name(claim.object_id)}</span>
            </p>
            <p className="claim__verification">
              {VERIFICATION_WORDING[claim.verification] ?? claim.verification}
            </p>
            <ul className="claim__sources">
              {claim.source_ids.map((sourceId) => {
                const href = wikidataUrl(sourceId);
                return (
                  <li key={sourceId}>
                    {href === null ? (
                      <code>{shortSourceId(sourceId)}</code>
                    ) : (
                      <a href={href} target="_blank" rel="noreferrer noopener">
                        <code>{shortSourceId(sourceId)}</code>
                      </a>
                    )}
                  </li>
                );
              })}
            </ul>
          </li>
        ))}
      </ol>
    </section>
  );
}
