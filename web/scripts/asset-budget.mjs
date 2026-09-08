// Fail the build when `dist/` gets fat, per asset class.
//
// **Phase 7 step 0, and it is step 0 for a reason.** Before this file existed the project gated six
// correctness properties and zero bytes: `make root-check` caps root *entries*, `eval/thresholds.py`
// gates correctness, and `stage-graph.mjs` printed a KB figure while asserting nothing about it. The
// next thing phase 7 does is add full-page video. A budget written after the video exists is a
// description of the video rather than a constraint on it, which is the same argument the eval suite
// makes for measuring the noise floor before writing the gates.
//
// **Per class, not one total.** A single number for `dist/` would let 400 KB of script hide behind a
// graph that shrank, and the interesting movement in this project is always in one class at a time.
//
// **Raw bytes, not gzipped.** CloudFront sets `compress = true`, so the wire number is smaller and
// the honest one for load performance -- but it moves when the compressor changes and it is not what
// S3 stores or what a `terraform destroy`/`apply` round-trip has to move. The wire figure belongs in
// the docs beside the raw one; the gate is on the number that does not drift under it.

import { readdirSync, statSync } from "node:fs";
import { relative, resolve, sep } from "node:path";
import { dirname } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");

const KB = 1024;
const MB = 1024 * 1024;

/**
 * The budget, with every number's reasoning beside it -- the shape `eval/thresholds.json` uses,
 * because a threshold whose justification lives in a commit message is a threshold nobody can
 * re-derive.
 *
 * Measured 2026-09-08 against a clean `npm run build`. `observed` is that measurement and is not
 * used by the gate; it is there so the next person can see how much room a cap actually left.
 */
export const BUDGET = {
  script: {
    cap: 320 * KB,
    observed: 236210,
    why:
      "React 19 plus the whole app. The cap leaves ~84 KB for the guided tour and the timeline, and " +
      "deliberately not enough for an animation library -- framer-motion is roughly 120 KB before " +
      "tree-shaking, so importing one fails this gate and forces the trade to be argued rather than " +
      "absorbed. See the IMPLEMENTATION doc step 4.",
  },
  style: {
    cap: 40 * KB,
    observed: 10303,
    why:
      "982 lines of hand-written CSS today. The design half will grow this legitimately -- a backdrop " +
      "layer, motion states, a hero -- so the cap is 4x rather than tight. Style is the one class " +
      "where growth is the point.",
  },
  graph: {
    cap: 3 * MB,
    observed: 2694624,
    why:
      "The pinned artifact, copied verbatim by `stage-graph.mjs` (201 KB gzipped). It moves only when " +
      "the pin moves, so this cap is really a tripwire on an unplanned re-pin rather than a budget. " +
      "**It caught a real one on its first run** -- see `PRUNES_STALE_PINS` in `stage-graph.mjs`.",
  },
  media: {
    cap: 0,
    observed: 0,
    why:
      "**Deliberately zero until phase 7 step 1 measures the candidates.** Zero is not a placeholder: " +
      "it means no media may ship until a number is chosen from what the rendered treatments actually " +
      "weigh. Picking the cap now would be picking it from taste, which is the thing this file exists " +
      "to stop. The build fails the moment a backdrop lands without that decision having been made.",
  },
  shell: {
    cap: 32 * KB,
    observed: 10203,
    why:
      "index.html and the three favicons. Small, static, and here so that nothing lands in `dist/` " +
      "unclassified -- an unbudgeted class is how the first 6 MB arrives.",
  },
};

/**
 * Which budget a `dist/`-relative path spends from.
 *
 * Unknown extensions fall to `shell` rather than being ignored. **Silently skipping an unrecognised
 * file is how a budget stops covering the thing it was written for**, and `shell` has the smallest
 * cap, so a surprise lands loudly.
 *
 * @param {string} relPath a path relative to `dist/`, in POSIX or platform separators
 * @returns {keyof typeof BUDGET}
 */
export function classify(relPath) {
  const path = relPath.split(sep).join("/");
  if (path.startsWith("graph/")) return "graph";
  if (path.startsWith("media/")) return "media";
  if (/\.(m?js|cjs)$/.test(path)) return "script";
  if (/\.css$/.test(path)) return "style";
  return "shell";
}

/**
 * Total each class and compare it to its cap. Pure, so the arithmetic is testable without a build --
 * the same split `graph/motion.ts` makes for the same reason.
 *
 * @param {{path: string, bytes: number}[]} entries
 * @param {typeof BUDGET} budget
 */
export function audit(entries, budget = BUDGET) {
  const rows = Object.keys(budget).map((name) => {
    const files = entries.filter((entry) => classify(entry.path) === name);
    const bytes = files.reduce((total, entry) => total + entry.bytes, 0);
    return {
      name,
      bytes,
      files: files.length,
      cap: budget[name].cap,
      over: bytes > budget[name].cap,
    };
  });
  return { rows, failed: rows.filter((row) => row.over) };
}

const human = (bytes) =>
  bytes >= MB ? `${(bytes / MB).toFixed(2)} MB` : `${(bytes / KB).toFixed(1)} KB`;

/** Every file under `dir`, as `{path, bytes}` relative to it. */
export function walk(dir, root = dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = resolve(dir, entry.name);
    if (entry.isDirectory()) return walk(full, root);
    return [{ path: relative(root, full), bytes: statSync(full).size }];
  });
}

/** @param {string} dist */
export function report(dist) {
  const { rows, failed } = audit(walk(dist));
  const width = Math.max(...rows.map((row) => row.name.length));
  for (const row of rows) {
    const mark = row.over ? "OVER" : "ok  ";
    const pct = row.cap === 0 ? "" : ` (${((row.bytes / row.cap) * 100).toFixed(0)}% of cap)`;
    console.log(
      `  ${mark} ${row.name.padEnd(width)}  ${human(row.bytes).padStart(9)} of ${human(row.cap).padStart(9)}` +
        `${pct}  ${row.files} file(s)`,
    );
  }
  if (failed.length === 0) {
    console.log(`asset budget: ${rows.length} classes, all inside cap`);
    return 0;
  }
  for (const row of failed) {
    console.error(
      `asset budget FAILED: ${row.name} is ${human(row.bytes)} against a cap of ${human(row.cap)}.`,
    );
    console.error(`  why the cap is what it is: ${BUDGET[row.name].why}`);
  }
  console.error(
    "  Raise a cap only with its reasoning updated beside it. Do not raise one to go green.",
  );
  return 1;
}

// `import.meta.main` is Node 24+. This runs on 22, so compare the resolved paths instead.
if (resolve(process.argv[1] ?? "") === resolve(fileURLToPath(import.meta.url))) {
  const dist = resolve(WEB, "dist");
  if (!statSync(dist, { throwIfNoEntry: false })?.isDirectory()) {
    throw new Error(`no dist/ to audit at ${dist} -- run the build first`);
  }
  process.exit(report(dist));
}
