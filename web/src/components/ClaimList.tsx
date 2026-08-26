import type { Claim } from "../types";
import { shortSourceId, wikidataUrl } from "../wikidata";

/**
 * Human-readable wording for the verification tier.
 *
 * **These say how hard ONE source was checked. They are not a count of agreeing sources and not a
 * disputed flag** — every edge in this corpus has exactly one source, always Wikidata, so nothing here
 * could corroborate anything. Wording that implied consensus would state the opposite of the truth,
 * which is the "grounded slides into correct" failure `CLAUDE.md` forbids. See decision A1.
 */
const VERIFICATION_WORDING: Record<string, string> = {
  HAND: "a person read the source article",
  PROSE_AUTO: "an automated check found the object named in the article prose",
  ASSERTS_AUTO: "an automated check found the article asserting the influence",
  EXPOSURE_AUTO: "an automated check found evidence of exposure, not of influence",
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
        {claims.map((claim, index) => (
          <li className="claim" key={`${claim.subject_id}-${claim.object_id}-${index}`}>
            <p className="claim__statement">
              <span className="claim__node">{name(claim.subject_id)}</span>
              <span className="claim__predicate"> influenced by </span>
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
