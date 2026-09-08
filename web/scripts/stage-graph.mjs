// Copy the pinned graph artifact into `public/` so Vite ships it as a static asset.
//
// Phase 5 IMPLEMENTATION 4.2: the whole graph goes to the browser and the map is entirely
// client-side. This script is the seam that makes that true without a second copy of the corpus
// living in git.
//
// Three things about this are deliberate:
//
//   1. **The artifact is copied VERBATIM, not slimmed.** Measured: 640 KB raw, 55 KB gzipped, and
//      `frontend.tf` sets `compress = true`. A slimmed shape (id/label/kind/year only) would be
//      20 KB gzipped — 35 KB saved for a second representation of the corpus that can silently
//      diverge from the pin, and it would throw away `source_id`, which is the citation itself.
//      Decided by sjtroxel 2026-08-29.
//   2. **The output path carries the version.** A corpus cut is a new URL, which is why the deploy
//      job's `--cache-control immutable` sync is already correct for this file and `deploy.yml`
//      needed no change at all.
//   3. **The pin comes from `chips.json`, not from a constant here.** That file is already validated
//      against the artifact by `tests/test_chips.py`, so there is exactly one place the corpus
//      version is written down and a mismatch fails the build rather than a demo.
//   4. **Stale pins are pruned -- see `PRUNES_STALE_PINS` below.** Added 2026-09-08, phase 7 step 0,
//      because the asset budget found one on its first run.

import { copyFileSync, mkdirSync, readFileSync, readdirSync, rmSync, statSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPO = resolve(WEB, "..");

const pin = JSON.parse(readFileSync(resolve(WEB, "src/chips.json"), "utf8")).artifact_version;
if (typeof pin !== "string" || !/^\d+\.\d+\.\d+$/.test(pin)) {
  throw new Error(`chips.json has no usable artifact_version (got ${JSON.stringify(pin)})`);
}

const source = resolve(REPO, `src/musical_mycelium/artifacts/v${pin}/graph.json`);
const target = resolve(WEB, `public/graph/v${pin}/graph.json`);

// A missing artifact must stop the build. The alternative is a deployed site that fetches 404 and
// renders an empty map, which looks like a design problem rather than a missing file.
if (!statSync(source, { throwIfNoEntry: false })?.isFile()) {
  throw new Error(`the pinned artifact is missing: ${source}`);
}

mkdirSync(dirname(target), { recursive: true });
copyFileSync(source, target);

// PRUNES_STALE_PINS -- added 2026-09-08, phase 7 step 0.
//
// **Found by the asset budget on the first run it ever did**, which is the argument for step 0 in one
// artifact. This script only ever *wrote* the current pin and never removed the last one, so
// `public/graph/` had accumulated `v0.5.0/graph.json` (655 KB) alongside `v0.7.1/`. Nothing fetches
// it -- `staticGraph.ts` builds its URL from `GRAPH_PIN` alone -- so it was invisible to every test
// and to every reader, and `.gitignore` excludes `web/public/graph/`, so it never showed up in a diff
// either. It was still copied into `dist/` by Vite and would still have been synced to CloudFront by
// the deploy job.
//
// Deleting rather than warning: the directory is generated output, `.gitignore`d, and rebuilt from
// the artifact in git by this script's own `prebuild`. There is nothing to lose and a warning nobody
// reads is how it accumulated in the first place.
const graphRoot = resolve(WEB, "public/graph");
for (const entry of readdirSync(graphRoot, { withFileTypes: true })) {
  if (entry.isDirectory() && entry.name !== `v${pin}`) {
    rmSync(resolve(graphRoot, entry.name), { recursive: true, force: true });
    console.log(`pruned stale staged artifact ${entry.name}`);
  }
}

const kb = (statSync(target).size / 1024).toFixed(0);
console.log(`staged artifact v${pin} (${kb} KB) at public/graph/v${pin}/graph.json`);
