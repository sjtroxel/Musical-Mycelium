# The SPA, explained

Written at phase 5 step 2, 2026-08-26. Companion to `docs/eval-suite-explained.md`, and written for the
same reason: the interesting decisions in this project are not visible from the code, and an interview
answer assembled on the spot is worse than one written down while the reasons were fresh.

Plain English throughout. Where a number appears, it was measured on the date given.

## What this is

A React app at `https://d2vtdkpgmecreg.cloudfront.net` that lets someone ask how two pieces of music
history connect, and watch a grounded answer assemble itself.

It is a client for an API that already existed. The backend was finished, deployed and measured before a
line of frontend was written — 41 evaluation cases, a deterministic groundedness gate, a sealed held-out
set. The SPA adds no reasoning of its own and is not allowed to.

## The one rule the frontend has to keep

**Claims first, prose second.** The agent proposes claims, a deterministic gate approves or rejects each
one against the pinned corpus, and only the approved set is shown to the model that writes the prose.

The client's share of that contract is narrow but real, and it is two things it must *not* do:

1. Never render a rejected proposal as a claim.
2. Never manufacture prose from anything except the tokens the synthesis model actually emitted.

Both are one-line mistakes to make. Neither is visible by eye. So both are tested directly, in
`web/src/useLineageRun.test.ts`, including a test that feeds the reducer a rejected triple and then
asserts those node ids appear nowhere in the rendered claim set.

There is a nice side effect. Because the gate runs before synthesis, the citations arrive *before* the
sentences do. Watching the claim list fill and only then watching prose stream in underneath it is the
architecture becoming visible on screen. That was not designed for; it fell out of the ordering.

## Why `fetch` and not `EventSource`

`EventSource` is the browser's built-in Server-Sent Events client and it is the obvious choice. It is the
wrong one here, for a reason that has nothing to do with elegance.

**`EventSource` reconnects automatically when the server closes the stream.** That is correct for a live
feed and catastrophic for a one-shot query: every successful `/lineage` run ends with the server closing
the stream, so the client would immediately re-run the whole agent loop. On a public URL, in a tab
someone left open, forever.

The per-visitor cost ceiling in this project is the token budget — `MAX_ACCUMULATED_TOKENS = 60_000`,
roughly $0.075 a query. An auto-reconnecting client multiplies that ceiling by however long the tab stays
open, which is not a ceiling at all.

So the client is `fetch` plus a `ReadableStream` reader and an `AbortController`: one request, no
reconnect, and an explicit stop. The abort also fires when the component unmounts, because AWS bills the
full Lambda duration on a streamed response *even after the client disconnects* — so hanging up promptly
is a cost control and not just tidiness.

## Why the refusal was the hardest part

The system declines to answer when the corpus has no sourced edge, and refusing is correct behaviour
rather than a failure. But a casual visitor's first read of a declined answer is *this thing is broken*,
and losing that argument on the first screen loses the whole point of the project.

Hiding refusals is not available — a system that always answers is indistinguishable from one that
invents. So the refusal is staged instead, under five rules:

1. **No error chrome, ever.** Same card, same typography, same weight as an answer. This is enforced
   structurally: the refusal and the answer are *the same React component*, and the only difference is
   the wording inside it. Two components would drift, and the drift always goes one way — a warning
   colour, an icon, a lighter weight — and by then the visitor has read "broken" before reading a word.
2. **Show what the graph does know.** Kate Bush is *in* the corpus and richly connected; seven artists
   cite her.
3. **Attribute the gap to the sources, not the software.** "This graph has no sourced answer" — the
   refusal sentence is generated deterministically on the server, with no model call, so it cannot
   hallucinate the thing it is declining to state.
4. **No reachable dead end.** The Kate Bush chip is a *pair*: one click runs the refusal and then runs
   the answerable direction. A refusal is never the last thing on screen. This is asserted in
   `tests/test_chips.py` — any chip containing a refusal step must end on an answer step.
5. **Never a negative claim.** "Nobody influenced Kate Bush" is false and this corpus cannot support it.
   **542 of the corpus's 973 nodes record no influences at all**, so a missing edge is overwhelmingly
   not evidence of a missing influence. That sentence is on screen, and both figures are checked against
   the artifact by `tests/test_corpus_facts.py` rather than typed into a paragraph.

Rule 5 is the one worth dwelling on in conversation. It is the difference between a system that says
*"the sources are silent here"* and one that says *"this did not happen"* — and only the first is true.

## Where the chips come from

Five buttons on the first screen. Four answer; the fifth refuses and then answers.

They live in `web/src/chips.json`, which is data rather than TypeScript for one specific reason: a Python
test reads the same file and validates every chip against the pinned corpus — that each node exists, that
an "expect: answer" chip has edges in the direction it names, that an "expect: refusal" chip has none.

So a corpus change breaks CI instead of breaking a demo in front of somebody.

**The direction assertions are the load-bearing half**, and they caught something. The blues-to-metal
chip stores its endpoints as `start_id: Q38848` (heavy metal), `end_id: Q9759` (blues) — backwards from
how the question reads. `path("Q9759", "Q38848")` returns nothing at all; the edges run
descendant-to-ancestor. Writing the endpoints in the order the *label* suggests would have shipped a
headline chip that renders an empty answer. This project has had three separate bugs from assuming the
origins direction, and none of them raised — each silently answered the opposite question and passed.

## What is deliberately missing

**There is no graph on the screen yet.** The map, the layout, the palette and the motion are steps 3
through 7 of this phase, each behind throwaway previews, in that order. The styling here is restrained on
purpose — legible typography and one column, nothing a palette decision would have to undo.

That ordering is a fence, not a schedule. The engine choice comes before layout, layout before colour,
colour before motion; and the guided tour is v1.0. Doing them out of order is how a frontend eats a
month.

**Coverage is present but minimal.** The footer states the corpus size, its component count, and its
skew as counts. The full treatment — coverage rendered honestly as a first-class part of the interface —
is step 9.

## How it is tested, and how little

Frontend tests are thin on purpose. The frontend is an explicit two-way door: the API is the boundary,
and the SPA can be rebuilt from scratch twice without touching the backend. Over-testing something
designed to be thrown away is waste.

So there are no component snapshots. What is tested is what would fail silently:

- **The stream parser**, against frames split at every awkward boundary including one character at a
  time. A frame split across two network reads is invisible locally and shows up only in production.
- **The claim/prose separation**, described above.
- **The DoD requirements that are absences** — no error chrome, no negative claim, no dead end. An
  absence is exactly what stops being true when someone refactors innocently.
- **The contract with the backend**, using *real captured bytes* from a local run of the API rather than
  hand-written strings. The two halves deploy on different schedules — the Lambda through a workflow, the
  SPA through an S3 sync — so a field that quietly changes name has no other place to fail loudly.

Each of these locks was verified by deliberately breaking it and watching it fail, then restoring it.
That practice caught something worth keeping: two DoD requirements were originally asserted inside a
single test, so breaking both produced *one* failure. One signal for two unrelated requirements tells you
something is wrong without telling you which thing. They are separate tests now.

## How it ships

`terraform apply` creates a private S3 bucket and a CloudFront distribution in front of it. The bucket is
never public; an Origin Access Control is the only read path, which is verified by behaviour — a direct
read of the object returns `403`.

CloudFront serves the SPA. **It does not front the API.** Two origins, two hostnames, deliberately: the
streaming path cost a full verification spike to establish, and putting an untested intermediary in front
of it is the one place in this phase where a wrong call is expensive.

The API's address is baked into the bundle at build time rather than fetched at runtime, because a config
fetch in front of first paint is exactly what the "loads instantly" requirement forbids. Assets are
content-hashed and cached for a year; `index.html` is never cached, or a visitor keeps loading the
previous build's filenames and gets a blank page.
