// Fail the build when the README's frontend test count is no longer true. Phase 7.5 step 0.
//
// The README states each suite's size as a FLOOR rounded down to the hundred ("at least 400"), and
// `make readme` writes it. A floor is true by construction the moment it is written and stays true as
// the suite grows, so the only way it goes wrong is by the suite crossing the next hundred -- which is
// the moment the claim starts understating, and the moment this fails.
//
// **Why this half lives in `web/` and not in `tests/test_published_numbers.py`.** The backend CI job
// has no Node, so the Python check cannot count these tests. The suite that owns the number checks it,
// and it reads the JSON report `npm run test` writes in the same run rather than collecting a second
// time. Run on its own after a stale test run, it checks a stale count; `npm run check` never does.

import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const REPORT = resolve(WEB, "node_modules", ".cache", "vitest-results.json");
const README = resolve(WEB, "..", "README.md");

// Must match `FLOOR_STEP` in `src/musical_mycelium/eval/published.py`, which writes the marker.
const FLOOR_STEP = 100;
const MARKER = /<!-- n:web_tests_floor -->(.*?)<!-- \/n -->/g;

function fail(message) {
  console.error(`readme-count: ${message}`);
  process.exit(1);
}

const total = JSON.parse(readFileSync(REPORT, "utf8")).numTotalTests;
const expected = (Math.floor(total / FLOOR_STEP) * FLOOR_STEP).toLocaleString("en-US");
const found = [...readFileSync(README, "utf8").matchAll(MARKER)].map((match) => match[1]);

if (found.length === 0) {
  fail("README.md carries no web_tests_floor marker, so its frontend count is unprotected.");
}
const wrong = found.find((value) => value !== expected);
if (wrong !== undefined) {
  fail(
    `README.md says at least ${wrong} frontend tests; the suite has ${total}, so the floor is ` +
      `${expected}. Run \`make readme\`.`,
  );
}
console.log(`readme-count: frontend floor ${expected} holds (suite has ${total})`);
