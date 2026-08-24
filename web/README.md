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
