# web/

The React + TypeScript SPA. **Rewritten 2026-08-31**; this file previously said the directory was
"empty on purpose", which stopped being true when phase 5 step 2 shipped the SPA on 2026-08-26.

The frontend lives here rather than at the repo root so a JavaScript toolchain cannot put
`package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts` and `index.html` into the root.
That was decided before a line of it existed and it held: the root is 15 of its 18-entry cap.

## Running it — READ THIS BEFORE JUDGING AN ANSWER

Two terminals, one command each:

```
make dev-live     # the API on :8000, against Bedrock. Costs about a cent a query.
make web-dev      # the SPA on :5173, proxying /api to :8000
```

**`make dev` (the free local stub) will lie to you about answers, and it did on 2026-08-26.** `LocalLLM`
is a development fixture that walks exactly one path — resolve, then `get_influences`, then stop. It has
**no route to `get_descendants`**, so every *"who did X influence?"* query refuses under it regardless of
what the corpus contains. Kate Bush and Elvis Presley both refuse locally; both answer on Bedrock with
seven and five cited claims respectively.

The stub is still the right default for working on the SSE plumbing, the reducer, or anything about
rendering — it is free, instant and deterministic. It is the wrong tool for deciding whether an answer is
any good. `make dev-live` is what the deployed site runs.

`make web-check` runs types, the unit suite and a production build.

## What is built

| | |
|---|---|
| `src/stream.ts`, `src/useLineageRun.ts` | the SSE parser and the reducer over `plan` / `tool` / `claim` / `rejection` / `path` / `token` / `refused` / `done` |
| `src/components/` | the chip row, one panel per query, the cited claim list |
| `src/graph/staticGraph.ts`, `useStaticGraph.ts` | the pinned artifact as a version-checked static asset, fetched with the first run and never before it |
| `src/graph/subgraph.ts` | which nodes and edges the map is allowed to show, as pure functions |
| `src/graph/layout.ts` | where they go: x is influence depth, y is year within the column, no simulation |
| `src/graph/GraphView.tsx` | the drawing. Canvas 2D. Decides nothing |
| `src/graph/motion.ts` | how a picture changes into the next one |
| `src/styles.css` | the palette, as tokens. Dark only, deliberately |

**The one structural rule in here:** claimed and context edges are two different types, not one type
with a style flag. A flag is one careless `.filter()` away from putting an unclaimed corpus edge in
front of a visitor as though the gate had approved it, and invariant 1 says the model must not be able
to narrate an edge the gate did not pass. The map is a place that could quietly do it.

## What is decided, and where the reasoning lives

Every one of these was decided by looking at the real thing running, not at a mock-up. Full reasoning
is in `docs/phases/phase-5-spa-and-visualization-IMPLEMENTATION.md` §12, step by step.

- **Canvas 2D**, not WebGL or SVG (step 3). The measured worst case is 458 nodes; the demo surfaces are
  3 and 31. What canvas charges is hit-testing and label placement by hand.
- **Layout is influence depth, and time is not a spatial axis** (step 5). 6 of the 102 datable edges in
  the corpus run backwards in time, and the undated nodes are the non-Western ones.
- **System sans, no webfont** (step 6). A portfolio site that must stay live through a job search should
  not put its text rendering behind another CDN.
- **Hot magenta on venue-dark, dark only** (step 6). Neon needs a dark ground; a light variant would be
  a second design rather than a tint of this one.
- **One motion mode at 850ms per edge** (step 7). A claim edge draws itself in as the gate approves it,
  and the camera moves with it. `prefers-reduced-motion` gives a single draw with no loop at all.

## Two things that are easy to get wrong here

- **`prefers-reduced-motion` is not handled by the CSS blanket rule alone.** That rule zeroes transition
  and animation durations, and a canvas driven by `requestAnimationFrame` has neither. The canvas checks
  the media query itself. Deleting either half leaves a gap that looks handled.
- **jsdom returns `null` from `getContext`, so the map draws nothing under test.** A completely dead
  render loop passes every test that renders the component normally. `src/graph/motion.test.tsx` stubs a
  recording context and drives `requestAnimationFrame` by hand for exactly this reason; the selection
  logic lives in `subgraph.ts` rather than in the render loop for the same one.

## Not built yet

Steps 8 through 10 of phase 5: the explorable map (pan, zoom, follow an edge, annotate — DoD 4),
coverage rendered honestly in the interface rather than disclaimed in a footnote (DoD 7), and the
favicon, logo and `v0.5.0` tag. The guided tour and the synchronized narration-and-camera moment are
**v1.0**, deliberately, and pulling them forward is how v0.5 becomes v1.0 with no eval work in between.

**Nothing since step 2 is deployed.** The live CloudFront URL serves the step 2 SPA: chips, streaming
answers, inline citations, the refusal, the grounded footer — and no map. Verified 2026-08-31 by
fetching the live bundle and finding none of the map's caption strings in it.
