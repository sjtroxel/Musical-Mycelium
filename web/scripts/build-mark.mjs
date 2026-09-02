/*
 * Regenerates `public/favicon.svg` from `src/components/mark.ts`, which is the single source of the
 * geometry. `mark.test.ts` fails if the shipped file has drifted, so this is the only correct way to
 * change the mark: edit `mark.ts`, run `npm run mark`.
 *
 * Node strips the TypeScript natively (22.18+), so this needs no build step and no new dependency.
 */
import { writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { faviconSvg } from "../src/components/mark.ts";

const out = fileURLToPath(new URL("../public/favicon.svg", import.meta.url));
writeFileSync(out, faviconSvg() + "\n");
console.log(`wrote ${out}`);
