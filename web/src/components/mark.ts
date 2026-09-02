/*
 * The mark, step 10.
 *
 * WHAT IT DRAWS IS REAL. Three noteheads joined by a beam is three nodes joined by two edges, and
 * the three nodes are the actual component behind the headline chip:
 *
 *     blues (1890) -> blues rock (1960) -> heavy metal music (1970)
 *
 * Q9759 -> Q193355 -> Q38848, both edges `influenced_by`, both `verification: HAND`, and the whole
 * connected component in artifact v0.5.0 - step 3 measured it at exactly 3 nodes. It ascends left to
 * right because those years ascend. Nothing here is invented, which is the only kind of decoration
 * this project is entitled to.
 *
 * It is drawn entirely in `--accent`. GraphView draws a walked node and a gate-approved edge in the
 * accent and nothing else, and step 6 fixed the accent's meaning as GATE-APPROVED - so an all-accent
 * drawing is precisely what the map itself renders for this component. A hollow notehead was tried
 * and rejected twice over: it is the map's "incomplete record" encoding, which is false here, and a
 * beam means an eighth note or shorter, which is never hollow.
 *
 * ONE SOURCE OF TRUTH. `favicon.svg` is generated from `geometry()` below and `mark.test.ts` fails if
 * the shipped file has drifted from it. Regenerate with `npm run mark`.
 */

export const GROUND = "#0d0a14";
export const ACCENT = "#ff5cae";

const R = 4.2; // notehead radius
const STEM = 2.3; // stem width
const BEAM_H = 3.4; // beam thickness, measured vertically
const DROP = 11; // notehead centre to beam top edge
/*
 * Named rather than indexed: `tsconfig` runs `noUncheckedIndexedAccess`, so `HEADS[0][1]` is
 * `number | undefined` and the beam maths would need four non-null assertions to compile. Naming the
 * outer two is also what the geometry actually means - the beam spans FIRST to LAST.
 */
const FIRST = { x: 6.6, y: 23 } as const; // blues, 1890
const MIDDLE = { x: 16, y: 19 } as const; // blues rock, 1960
const LAST = { x: 25.4, y: 15 } as const; // heavy metal music, 1970
const HEADS = [FIRST, MIDDLE, LAST] as const;

/*
 * The beam is a POLYGON with vertical end cuts, the way notation is engraved - not a stroked line.
 * A stroked line gets a butt cap PERPENDICULAR to its direction, so a slanted beam ends on a
 * diagonal and leaves a visible spur above the last stem. That defect shipped through two rounds of
 * previews and was only caught in a 170px screenshot.
 */
export function geometry(): string {
  const stemX = (x: number) => x + R - STEM / 2;
  const xL = stemX(FIRST.x) - STEM / 2;
  const xR = stemX(LAST.x) + STEM / 2;
  const yTop = (x: number) => {
    const y1 = FIRST.y - DROP;
    const y2 = LAST.y - DROP;
    return y1 + ((x - xL) / (xR - xL)) * (y2 - y1);
  };
  const n = (v: number) => Number(v.toFixed(3));

  const beam = `<polygon points="${n(xL)},${n(yTop(xL))} ${n(xR)},${n(yTop(xR))} ${n(xR)},${n(yTop(xR) + BEAM_H)} ${n(xL)},${n(yTop(xL) + BEAM_H)}" fill="${ACCENT}"/>`;
  const stems = HEADS.map(
    ({ x, y }) =>
      `<line x1="${n(stemX(x))}" y1="${n(y)}" x2="${n(stemX(x))}" y2="${n(yTop(stemX(x)) + BEAM_H)}" stroke="${ACCENT}" stroke-width="${STEM}"/>`,
  ).join("");
  const heads = HEADS.map(
    ({ x, y }) => `<circle cx="${n(x)}" cy="${n(y)}" r="${R}" fill="${ACCENT}"/>`,
  ).join("");

  return stems + beam + heads;
}

/** The favicon: the mark on the app's own ground, so a light browser chrome cannot wash it out. */
export function faviconSvg(): string {
  return (
    `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32" role="img" aria-label="Musical Mycelium">` +
    `<title>Musical Mycelium</title>` +
    `<rect width="32" height="32" rx="6" fill="${GROUND}"/>` +
    geometry() +
    `</svg>`
  );
}
