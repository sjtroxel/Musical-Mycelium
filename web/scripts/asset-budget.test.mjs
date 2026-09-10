// Tests for the asset budget. Phase 7 step 0.
//
// `.mjs` rather than `.ts` on purpose: `tsconfig.json` includes only `src` and `vite.config.ts`, so
// `scripts/` is not typechecked, and a `.test.ts` living here would be run by vitest while being
// invisible to `tsc`. Vitest's default include covers `*.test.mjs`, so this runs in the same suite as
// the other 16 files without pretending to a typecheck it does not get.

import { describe, expect, it } from "vitest";
import { BUDGET, audit, classify } from "./asset-budget.mjs";

describe("classify", () => {
  it("routes each asset class to its own budget", () => {
    expect(classify("assets/index-abc123.js")).toBe("script");
    expect(classify("assets/index-abc123.css")).toBe("style");
    expect(classify("graph/v0.7.1/graph.json")).toBe("graph");
    expect(classify("media/backdrop.webm")).toBe("media");
    expect(classify("index.html")).toBe("shell");
  });

  it("sends an unrecognised file to the smallest cap rather than ignoring it", () => {
    // The failure this guards: a new asset type lands, matches no rule, is skipped, and the budget
    // silently stops covering the thing it was written for.
    expect(classify("some-new-thing.wasm")).toBe("shell");
    expect(BUDGET.shell.cap).toBeLessThan(BUDGET.script.cap);
  });

  it("gives the published report its own class, by directory", () => {
    // The report is one HTML file. By extension it would land in `shell` and spend the favicons' cap.
    expect(classify("report/index.html")).toBe("report");
  });

  it("classifies media by directory, not by extension", () => {
    // A poster frame is media even though `.avif` is not a video extension, and a `.js` shipped
    // inside media/ is still media -- the directory is the decision.
    expect(classify("media/poster.avif")).toBe("media");
    expect(classify("media/player.js")).toBe("media");
  });
});

describe("audit", () => {
  it("passes a dist that is inside every cap", () => {
    const { failed } = audit([
      { path: "assets/app.js", bytes: 200_000 },
      { path: "assets/app.css", bytes: 8_000 },
      { path: "graph/v0.7.1/graph.json", bytes: 2_700_000 },
      { path: "index.html", bytes: 1_000 },
    ]);
    expect(failed).toEqual([]);
  });

  it("FAILS an oversized class and names it", () => {
    const { failed } = audit([{ path: "assets/app.js", bytes: 400_000 }]);
    expect(failed).toHaveLength(1);
    expect(failed[0]?.name).toBe("script");
  });

  it("fails the moment any media ships, because the cap is deliberately zero", () => {
    // Phase 7 step 1 sets this number from what the rendered treatments actually weigh. Until then
    // zero means "no media may ship", and this test is the thing that makes that true rather than
    // aspirational.
    expect(BUDGET.media.cap).toBe(0);
    const { failed } = audit([{ path: "media/backdrop.webm", bytes: 1 }]);
    expect(failed.map((row) => row.name)).toEqual(["media"]);
  });

  it("does not let one class hide behind another", () => {
    // The argument for per-class caps: a total would pass this, since 400 KB of script sits under
    // the combined headroom of a graph that came in small.
    const { failed } = audit([
      { path: "assets/app.js", bytes: 400_000 },
      { path: "graph/v0.7.1/graph.json", bytes: 100_000 },
    ]);
    expect(failed.map((row) => row.name)).toEqual(["script"]);
  });

  it("reports every class even when nothing is over", () => {
    const { rows } = audit([{ path: "index.html", bytes: 10 }]);
    expect(rows.map((row) => row.name).sort()).toEqual(
      ["graph", "media", "report", "script", "shell", "style"].sort(),
    );
  });

  it("keeps a reason beside every cap", () => {
    // A threshold whose justification lives in a commit message is one nobody can re-derive. Same
    // rule `eval/thresholds.json` follows.
    for (const [name, entry] of Object.entries(BUDGET)) {
      expect(entry.why, `${name} has no recorded reasoning`).toBeTruthy();
      expect(entry.why.length, `${name}'s reasoning is too thin to be a reason`).toBeGreaterThan(
        60,
      );
    }
  });
});
