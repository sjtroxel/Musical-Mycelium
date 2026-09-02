# The SPA, explained

Written at phase 5 step 2, 2026-08-26. **Extended at step 10, 2026-09-02, when the phase closed** —
the sections from *How the map is laid out* onward are new, and two claims in the original text ("there
is no graph on the screen yet", "coverage is present but minimal") were true when written and are now
struck. Companion to `docs/eval-suite-explained.md`, and written for the same reason: the interesting
decisions in this project are not visible from the code, and an interview answer assembled on the spot
is worse than one written down while the reasons were fresh.

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

## Why the graph is drawn on a canvas

Three renderers were built against the real corpus and looked at: SVG, Canvas 2D, and WebGL via Sigma.
Canvas won, and the reason is a measurement rather than a preference.

The planning documents argued for WebGL, on the grounds that smooth camera work over thousands of nodes
is what WebGL is for. Then the corpus was measured: the largest connected component is **458 nodes**, and
the graphs an actual answer draws are **3 and 31**. WebGL's advantage is real and, at this size, entirely
unspent. Canvas is comfortable an order of magnitude above where this corpus sits.

What canvas charges is that hit-testing, dragging and label placement are yours to write — roughly forty
lines that SVG gets free from the DOM. What it buys is that every visual effect after that is just
drawing, with no renderer to negotiate with. Since everything remaining in this phase is design work,
that trade is the right way round.

Sigma was also rejected for a reason that has nothing to do with graphics: it touches
`WebGL2RenderingContext` when the module loads, so it cannot be imported in jsdom, and the frontend tests
run in jsdom. Choosing it would have meant mocking the graph component out of the one test in this phase
that genuinely carries weight — the test that the app cannot narrate the static graph. Cosmograph was
rejected on licensing: it is `CC-BY-NC-4.0`, and a project whose whole pitch is correct attribution
cannot be casual about its own licenses.

## What the map can honestly show

The corpus is not one connected organism, and the interface must not imply that it is.

Measured: 973 nodes fall into **169 separate components**, and artists and genres never touch — 128
components are purely artists, 41 are purely genres, and **none are mixed**. The largest component is 458
nodes and every one of them is an artist. The blues-to-heavy-metal example that opens the app is a
component of **three nodes**.

None of this is broken. Only one Wikidata property is ingested — `P737`, *influenced by* — and it does
not link artists to genres. The property that would, `P136`, is not in the corpus, and adding it means
cutting a new artifact, which would invalidate every published evaluation number.

> **Scheduled to change, and this section is written against v0.5.0.** Phase 6 decided on 2026-09-02 to
> ingest `P136` as a separate, non-narratable predicate — decision C1, `docs/graph-semantics.md` §5.2 —
> which joins the two axes and makes the map able to show one component containing both artists and
> genres for the first time. **Every number in this section is still correct today** and stops being
> correct at phase 6 step 2. Rewrite it there, against measurements, rather than against this note.

So the map shows a neighbourhood, and says so. The alternative — drawing all 169 islands at once and
letting it look like one graph — would be a picture that argues for a claim the data does not make.

## How the map is laid out, and why time is not an axis

Horizontal position is **influence depth** — how many `influenced by` hops a node sits from the subject.
Vertical position is the year, but only as an ordering *within* a column: oldest at the top. There is no
simulation, no settling, no physics. `layout()` is a pure function of the graph, so the same answer draws
the same map twice and a screenshot in a document matches what a visitor sees.

The obvious alternative — put the year on the x-axis and let the map be a timeline — was built, looked
at, and rejected for a reason that only appeared once it was measured. **Not one node on either Kate Bush
panel carries a date.** A time axis silently falls back to something else on two of the six panels the
app can draw, and a design that becomes a different design 40% of the time is worse than one that never
claimed chronology.

Measuring for that decision turned up something more interesting than the decision. **Six of the 102
datable edges in the corpus run backwards in time** — the influence is recorded as older than its own
cause — and one of them is inside a demo chip: `swing (1930) -> Western swing (1928)`. That is not a data
error to clean up. A Wikidata `inception year` is a field somebody typed, not a measurement, and a genre
does not begin on a date. It is a reason not to build geometry on top of those numbers, which is what the
layout now does not do.

The undated nodes sort to the *end* of their column rather than to the ancient beginning, and there is a
test for it. Sorting a missing year to zero would be the map inventing dates for precisely the nodes the
corpus is thinnest on — and the three undated genres are the same three every time: Na mele paleoleo,
Pinoy hip hop, sampledelia. Hawaiian, Filipino, and one studio technique.

## The palette means something, which constrains it

Dark only, neon on near-black. That is a commitment rather than an omission: neon reads as emitted light,
and the same hue on a paper-white ground reads as a bright sticker, so a light variant would not be a
tint of this design but a second and different one.

The load-bearing part is that **the accent colour means `gate-approved`**. The map paints a walked node
and a claim the gate passed in the accent, and nothing else, ever. A visitor clicking a faint context
node must not make it look like one the gate approved — that is the same slide from *traceable* to
*asserted* that the whole project exists to prevent, arriving through the palette instead of through
words. So selection is drawn in a different token entirely, and the completeness marking is a third
channel again.

That discipline is why one context edge is deliberately below the usual contrast bar and one is not.
Context edges were originally sharing a token with the panel borders. A border is a separator and low
contrast is right for it; a context edge is **content** — the caption counts them out loud, "the faint
lines are 10 further connections" — and at the shared value a visitor could not find the thing that
sentence promises.

## Motion, and the one mode that survived

Three motion treatments were built and put behind a URL switch. The user ran them and reported that all
three looked identical, which was accurate: two defects were making them so. That is worth writing down,
because "they look the same" is a report about the screen and never a verdict on the design — the right
response is to go and find out why, not to conclude the design was subtle.

What ships is one mode at 850ms: edges draw in the order the agent actually walked them, nodes fade in
rather than blink on. Because the layout is deterministic there is nothing to race — the motion animates
between two known positions. `prefers-reduced-motion` needs no special branch in the layout for the same
reason, and where it does apply it is honoured.

## The map admits what it is not showing

Every node carries a count of how many of its corpus connections are *not* drawn. Zero means the picture
is complete, and a node whose record is complete is drawn with a **solid outline**; one with more behind
it is drawn broken. *A closed outline means a closed record.*

Without that, a node with one line is ambiguous between "the corpus records one influence here" and
"there are five more you have not opened" — so a genuinely thin region and an unexplored one look
identical, and making thinness visible is the entire point.

A faint outer halo was the most legible of the three candidates in isolation, and lost anyway. Stacked
under the selection ring it turned a selected incomplete node into three concentric circles, and
selection stopped reading as its own state. That is a channel collision rather than a taste call, and it
is only visible in a screenshot of a *selected* node — which is to say, it is not reachable from the test
suite at all.

On two of the five chips the caption says so outright: *"Every node here is drawn with a solid outline:
this is everything the corpus holds around this answer, not a portion of it."*

## Coverage is a panel, not a footnote

Three axes, drawn, open on arrival: **when** the corpus's genres begin, **where** they are from, and
**how densely** they connect. All counts, never percentages, and `no date recorded: 28` is drawn as a bar
rather than dropped — the missing data is data.

The skew is real and structural: the United States and the United Kingdom are the top two places by a
distance. The counterweight sits in the same block rather than in a disclaimer, because **concentration
is not absence** — 43 of the 169 genres name neither, and 48 name no place at all. A test fails if a
future corpus ever turns that counterweight into a fig leaf.

The panel renders **below** the results, always. It was originally above them, on the reasoning that
coverage is the frame you read an answer through. Every test passed. The user clicked a chip and thought
nothing had happened: the panel was a full screen tall, the answer rendered below the fold, and the
streaming animation had finished by the time he scrolled to it. *A frame nobody sees the answer inside is
not a frame.*

There is a third kind of thinness the panel does not chart, and it is the sharpest one: **85 of the 169
genres have no recorded origin at all, 108 have exactly one connection, and the busiest has six.** Those
figures live in `web/src/corpus-facts.json`, asserted against the pinned artifact by a Python test.

## The mark

Three noteheads joined by a beam. It is also three nodes joined by two edges, and they are real ones:
`blues (1890) -> blues rock (1960) -> heavy metal music (1970)`, both edges hand-verified, and the whole
connected component behind the app's headline question. It ascends left to right because those years do.

It is drawn entirely in the accent, which — per the rule above — is exactly what the map itself renders
for this component, since all three nodes are walked and both edges passed the gate. A hollow notehead
was tried and rejected twice over: it is the map's *incomplete record* encoding, which would be false
here, and a beam means an eighth note or shorter, which is never hollow.

The geometry is written once, in `web/src/components/mark.ts`. The favicon file is generated from it and
a test fails if the shipped file has drifted, because a logo and a favicon quietly becoming two slightly
different pictures is the ordinary outcome otherwise.

## What is deliberately still missing

**The guided tour** — the synchronized narration-and-camera moment — is v1.0, not this phase. Pulling it
forward is how v0.5 becomes v1.0 with no evaluation work in between.

**A second source.** Four of the six aspirational chips are blocked on it, and it is the precondition for
this system ever being able to say that a claim is *contested*. On today's corpus every edge has exactly
one source and it is always Wikidata, so nothing can disagree with anything — that is arithmetic, not
effort, and any copy implying otherwise is overstating it.

**A readable URL.** CloudFront assigns the hostname and there is no vanity subdomain to claim at any
price; a nicer address means registering a real domain, which is phase 7.

The step ordering was a fence, not a schedule: engine, then layout, then colour, then motion. Doing them
out of order is how a frontend eats a month.

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
