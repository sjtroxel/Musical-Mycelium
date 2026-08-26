/**
 * Turning a source id into something a visitor can click.
 *
 * Every edge carries a Wikidata *statement* URI, e.g.
 * `http://www.wikidata.org/entity/statement/Q38848-2ff6204e-...`. That URI identifies the statement but
 * is not a page a person can read, so the link points at the subject entity instead, anchored to the
 * `influenced by` property. The statement id is still shown verbatim — it is the actual citation, and
 * shortening it to a friendly label would hide the thing being cited.
 */

const STATEMENT = /\/statement\/(Q\d+)-/;

/** The entity page for a statement id, or `null` when the id is not the shape we know. */
export function wikidataUrl(sourceId: string): string | null {
  const match = STATEMENT.exec(sourceId);
  if (match === null) {
    // Bare entity URIs, in case a future source writes them. Anything else gets no link rather than
    // a guessed one — a citation that leads somewhere wrong is worse than one that leads nowhere.
    const entity = /\/entity\/(Q\d+)$/.exec(sourceId);
    return entity ? `https://www.wikidata.org/wiki/${entity[1]}` : null;
  }
  return `https://www.wikidata.org/wiki/${match[1]}#P737`;
}

/** The trailing hash of a statement id, for display. Falls back to the whole string. */
export function shortSourceId(sourceId: string): string {
  const tail = sourceId.split("/").pop() ?? sourceId;
  return tail.length > 24 ? `${tail.slice(0, 24)}…` : tail;
}
