import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";
import { ACCENT, GROUND, faviconSvg, geometry } from "./mark";

/*
 * Resolved from the vitest root (`web/`), not from `import.meta.url`: under Vite's transform
 * `import.meta.url` is an http:// URL, not a file:// one, and `new URL(..., import.meta.url)` throws
 * "The URL must be of scheme file". Caught by running these tests, not by reading them.
 */
const repoFile = (rel: string) => resolve(process.cwd(), rel);

const shipped = () => readFileSync(repoFile("public/favicon.svg"), "utf8").trim();

describe("the mark", () => {
  /*
   * The drift guard. `Mark.tsx` renders `geometry()` and `public/favicon.svg` is generated from it,
   * so editing one and not the other is the failure this test exists to catch. Run `npm run mark`.
   */
  it("ships a favicon that is byte-identical to the generated one", () => {
    expect(shipped()).toBe(faviconSvg());
  });

  it("draws three noteheads and two edges - the real blues -> blues rock -> heavy metal component", () => {
    const g = geometry();
    expect(g.match(/<circle/g)).toHaveLength(3);
    // three stems and one beam; the beam spans the outer two stems, which is the two edges
    expect(g.match(/<line/g)).toHaveLength(3);
    expect(g.match(/<polygon/g)).toHaveLength(1);
  });

  it("is drawn only in the accent, which is what the map uses for a gate-approved edge", () => {
    const colours = new Set(geometry().match(/#[0-9a-f]{6}/g));
    expect([...colours]).toEqual([ACCENT]);
  });

  it("ascends left to right, because 1890 < 1960 < 1970", () => {
    const heads = [...geometry().matchAll(/<circle cx="([\d.]+)" cy="([\d.]+)"/g)].map((m) => ({
      x: Number(m[1]),
      y: Number(m[2]),
    }));
    expect(heads).toHaveLength(3);
    heads.forEach((head, i) => {
      const prev = heads[i - 1];
      if (!prev) return;
      expect(head.x).toBeGreaterThan(prev.x); // later in time, further right
      expect(head.y).toBeLessThan(prev.y); // and higher up
    });
  });

  it("gives the favicon a ground, so a light tab strip cannot wash it out", () => {
    expect(faviconSvg()).toContain(`fill="${GROUND}"`);
  });

  /*
   * The beam is a polygon with VERTICAL end cuts. Drawn as a stroked line it gets a perpendicular
   * butt cap, and on a slanted beam that leaves a spur poking above the last stem - a defect that
   * survived two rounds of previews. A polygon whose first two x-coordinates repeat as its last two,
   * in reverse, is the shape that cannot do that.
   */
  it("beams with vertical end cuts, not a perpendicular butt cap", () => {
    const pts = /<polygon points="([^"]+)"/.exec(geometry())?.[1];
    expect(pts).toBeDefined();
    const corners = (pts ?? "").split(" ").map((p) => {
      const [x, y] = p.split(",").map(Number);
      return { x: x ?? NaN, y: y ?? NaN };
    });
    expect(corners).toHaveLength(4);
    const [a, b, c, d] = corners as [
      (typeof corners)[number],
      (typeof corners)[number],
      (typeof corners)[number],
      (typeof corners)[number],
    ];
    expect(a.x).toBe(d.x); // left edge is vertical
    expect(b.x).toBe(c.x); // right edge is vertical
    expect(b.y).toBeLessThan(a.y); // and the beam rises with the notes
  });
});

/*
 * The raster fallbacks. `favicon.svg` is generated from `mark.ts` and guarded above; the .ico and the
 * apple-touch .png are RASTERISED from that same SVG in a headless browser, which is not a repo
 * dependency, so they are committed binaries rather than build output. That makes them the piece
 * most able to rot quietly - hence these checks on their actual bytes.
 *
 * To regenerate after changing the mark: `npm run mark`, then re-rasterise (see the step 10 record in
 * docs/phases/phase-5-spa-and-visualization-IMPLEMENTATION.md).
 *
 * These exist because a favicon <link> pointing at a missing file is the exact defect step 10 is
 * closing: `/favicon.ico` 404ed for the whole of this phase and only a browser console showed it.
 */
describe("the raster fallbacks index.html points at", () => {
  const asset = (name: string) => readFileSync(repoFile(`public/${name}`));

  it("ships an apple-touch-icon that is a real 180x180 PNG", () => {
    const png = asset("apple-touch-icon.png");
    expect(png.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a"); // PNG magic
    expect(png.readUInt32BE(16)).toBe(180); // IHDR width
    expect(png.readUInt32BE(20)).toBe(180); // IHDR height
  });

  it("ships an .ico carrying 16, 32 and 48 px images", () => {
    const ico = asset("favicon.ico");
    expect(ico.readUInt16LE(0)).toBe(0); // reserved
    expect(ico.readUInt16LE(2)).toBe(1); // type: icon
    const count = ico.readUInt16LE(4);
    expect(count).toBe(3);
    const widths = Array.from({ length: count }, (_, i) => ico.readUInt8(6 + i * 16));
    expect(widths).toEqual([16, 32, 48]);
    // every directory entry must point at bytes that are actually inside the file
    for (let i = 0; i < count; i += 1) {
      const size = ico.readUInt32LE(6 + i * 16 + 8);
      const offset = ico.readUInt32LE(6 + i * 16 + 12);
      expect(size).toBeGreaterThan(0);
      expect(offset + size).toBeLessThanOrEqual(ico.length);
      expect(ico.subarray(offset, offset + 8).toString("hex")).toBe("89504e470d0a1a0a");
    }
  });

  it("is referenced by index.html, so the files and the links cannot drift apart", () => {
    const html = readFileSync(repoFile("index.html"), "utf8");
    expect(html).toContain('href="/favicon.svg"');
    expect(html).toContain('href="/favicon.ico"');
    expect(html).toContain('href="/apple-touch-icon.png"');
  });
});
