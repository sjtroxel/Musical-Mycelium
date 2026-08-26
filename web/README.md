# web/

Reserved for the React + TypeScript SPA. Empty on purpose — **but not for much longer: phase 5 is next
as of 2026-08-24**, and phase 5 is this directory.

This directory exists from day one for one specific reason: a JavaScript toolchain wants to put
`package.json`, `package-lock.json`, `tsconfig.json`, `vite.config.ts`, and `index.html` in whatever
directory it is initialized in. Initializing the frontend **here** rather than at the repo root keeps five
files out of the root permanently. Initializing it at the root and moving it later is the kind of
retrofit this project is trying to avoid.

So: when the SPA starts, it starts with `cd web` first.

## What is already decided

- **React + TypeScript** — his strongest lane and dominant in his target job postings. Graph-viz engines
  are framework-agnostic, so visualization was not the deciding factor.
- **Hosted on S3 + CloudFront**, all-AWS, no cold start.
- **The first screen is a search box with 5–7 clickable canonical query chips.** See `docs/SPEC.md` §2.
- **The frontend loads instantly even when the agent takes 20 seconds.** Motion is never in the critical
  path of first paint, and `prefers-reduced-motion` is respected.

## What is deliberately not decided

The rendering engine and all visual design work are deferred to **v0.5** (`docs/planning/06-DESIGN-DIRECTION.md`
§7). The frontend is an explicit two-way door: the API contract is the boundary, and the SPA can be rebuilt
from scratch twice without touching the backend. The client through v0.4 is `curl`.

**Two things phase 5 inherits that this file predates** (both 2026-08-24):

- **The API it consumes is settled and streaming.** `SPEC.md` §6 is no longer marked open — `plan`,
  `claim`, `rejection`, `path` and `done` all ship, and `path` carries the walked order *and* the approved
  line of descent as separate fields, which is the decision this file called out as the one worth getting
  right early.
- **The backend it points at still runs a template stub.** The Bedrock redeploy was deferred into phase 5,
  so wiring the SPA to the live URL and putting a real model behind that URL are the same piece of work.

The one thing worth getting right early, because it is annoying to change once the schema has consumers:
the response payload includes the agent's walked **path, in order**.

## Running it — READ THIS BEFORE JUDGING AN ANSWER

Two terminals:

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
