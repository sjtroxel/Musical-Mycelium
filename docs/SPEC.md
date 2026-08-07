# SPEC — Musical Mycelium

Canonical contracts. Anything defined here is defined **once** and referenced elsewhere, never duplicated.

Sections marked **OPEN** are owned by the v0.1 IMPLEMENTATION doc and are deliberately empty rather than
guessed at.

## 1. Product shape (decided 2026-07-29)

This settles the last open question from the pre-build series
(`planning/09-PRIORITIES-AND-OPEN-DECISIONS.md` §2), which had gone unanswered because three different
products were consistent with docs `00`–`07`.

**The question-answerer is the spine. The guided tour is the v1.0 showcase. The explorable map is ambient.**

| | What it is | When |
|---|---|---|
| **A. Question-answerer** | A box. Ask about a genre or an artist, receive a streamed, cited lineage. | The v0.x spine, from v0.1 |
| **C. Guided tour** | "Take me from delta blues to Detroit techno." The agent plans a path and narrates it as the camera walks it. | v1.0 showcase |
| **B. Explorable map** | The graph as interface: wander, zoom, follow edges; the agent annotates on demand. | Ambient, falls out of the SPA at v0.5 |

Why this ordering: A is what the walking skeleton already builds toward and the only one of the three that
evaluates cleanly (one query in, claims out). C is the signature demo identified in `planning/06` §5.1 and
is only possible because streaming was chosen. B alone would demote the agent, and the agent is the resume.

**C and B are commitments, not maybes.** He stated plainly on 2026-07-29 that reaching the guided tour and
**especially the explorable map** matters to him, while agreeing the question-answerer is the right thing to
build first. "Ambient" and "falls out for free" describe *how B arrives* — as a consequence of the SPA
rendering a graph the API already returns — not how much it matters. Anything that would make B or C
materially harder to reach later is a bad trade even when it makes A slightly easier now. The two specific
places that shows up, both already decided: the API returns the agent's walked path in order, and the graph
payload is shaped for a renderer rather than for prose.

**The first screen** is a search box with 5–7 clickable canonical query chips beneath it. No blank-page
problem, and the chips double as the demo script and the gold-set cases. Rejected: an auto-streaming
featured lineage (costs a Bedrock call per pageview unless cached), and a static hero graph (needs
visualization that `planning/06` defers to v0.5).

**The 30-second recruiter path:** land, click a chip without having to invent a question, watch a cited
lineage stream in with citations resolving as claims are made, leave remembering that every edge had a
source.

## 2. Canonical queries (decided 2026-08-02)

These are load-bearing in four places at once: the chips on the first screen, the demo script, the gold-set
cases, and the eval slices.

**Edited 2026-08-02, decided by sjtroxel.** The original seven were written on 2026-07-29, before the
P279/P737 validation established that the sourced-lineage corpus is 158 prose-verified edges. Checked
against that corpus, five of the seven are unanswerable. They are not deleted — they are separated into
what the graph supports now and what it is being built toward, so the ambition stays visible and the
v0.1 gold set stays honest.

### 2.1 Validated queries — the v0.1 set

Every one of these was checked against the PROSE tier of the 2026-07-31 validation before being written
here. They are the five hand-authored gold cases of phase 1.

**Amended 2026-08-02 after hand-verification.** Cases 2 and 5 changed. The originals were written against
the automated PROSE tier; reading the sources by hand rejected them. Full record in
`docs/phases/phase-1-edge-verification.md`.

| # | Query | Shape | What the corpus holds |
|---|---|---|---|
| 1 | "Where did blues rock come from?" | A, origins | 1 edge: `blues rock (Q193355) <- blues (Q9759)` |
| 2 | "Where did acid jazz come from?" | A, origins | 4 edges: `acid jazz (Q221772) <- jazz (Q8341), funk (Q164444), soul (Q131272), hip-hop (Q11401)` |
| 3 | "Where did trip hop come from?" | A, origins | 2 edges: `trip hop (Q205560) <- hip-hop (Q11401), electronica (Q817138)` |
| 4 | "Where did Western swing come from?" | A, origins | 2 edges: `Western swing (Q1730388) <- swing (Q203775), country music (Q83440)` |
| 5 | "Where did the blues come from?" | A, **refusal** | `blues (Q9759)` resolves and is cited as the source in case 1, but has **zero** sourced parent edges. The correct answer is that the graph does not support this |

Notes on the composition, since it is doing work:

- All five are **origins-shaped**, because v0.1's `get_influences` walks parents only. Descendant queries
  ("what came out of X") are a direction the tool does not walk until the phase-2 corpus arrives.
  *(2026-08-05: `trace_lineage` walks it. It searches ancestry first and descent second and reports the
  chain descendant-first either way, so a descendant-shaped question is answered without ever inverting an
  influence claim. The five gold cases above are unchanged and stay origins-shaped.)*

  *(2026-08-07: only **between two named nodes**. There is still no fan-out descendant tool, so an
  open-ended "what came out of the blues?" — one node in, many out — remains unanswerable.
  `Direction.INFLUENCED` has been supported by `GraphStore` since phase 2 and no registered tool exposes
  it. Phase 3 adds `get_descendants`; see `phase-3-agent-loop.md` A2.)*

  *(2026-08-07, later: **DONE.** `get_descendants` is registered and "what came out of the blues?" is
  answerable — one node in, many out, each hop proposed from the **edge** so a descendant query cannot
  emit a reversed influence claim. The registry went from three tools to seven at phase 3 step 2:
  `get_descendants`, `describe_node`, `resolve_source`, `corpus_coverage`. The five gold cases above are
  unchanged and stay origins-shaped.)*
- 1 is the trivial case and 2 is the showpiece, at four parents — the richest node in the artifact, and the
  case most likely to expose a traversal that stops early. It also carries a story: acid jazz is the genre
  whose article started the prose check on 2026-07-31.
- 3 and 4 are deliberately **boring middles**. `.claude/rules/evals.md` requires them: a gold set made only
  of memorable cases hides the steps that are easy to skip. 4 carries a second trap — the Western swing
  article's *first* sentence is taxonomic and only the sentence after it is a derivation claim.
- 5 is the **coverage-honesty case, and it is not optional.** `.claude/rules/grounding-and-claims.md` makes
  refusal correct behavior, so the gold set must contain at least one case where refusing is the right
  answer; without it, refusal accuracy has no true refusal to measure. It is the **resolved-but-unsourced**
  refusal, which is the stronger of the two shapes: the system demonstrably knows the node, cites it
  elsewhere, and still declines to state its origins. 13 of the artifact's 28 nodes are in this position.

**Two originals were rejected on the evidence, and the reasons are worth keeping.** "Where did heavy metal
come from?" rested on `heavy metal <- classical music`, but the article says *"classical and metal are
rooted in different cultural traditions and practices"* — Wikipedia contradicts the edge. And
`griot (Q511054)` is typed as an occupation, not a music genre, so it cannot survive the artifact's type
filter; the regional coverage-honesty case moves to phase 2, where the corpus has real non-Western nodes.

**Standing rule, adopted 2026-08-02.** Every query in this section is validated against the pinned artifact:
it is either answerable or deliberately labeled as a coverage-honesty case. The check is deterministic and
becomes a Tier-1 eval row, so a corpus change that silently breaks a demo query fails CI instead of a demo.

### 2.2 Aspirational queries — the v0.5 chip set

The first screen ships at v0.5 with 5–7 chips. These are the intended set. Each carries the corpus work it
is waiting on, so nothing here is a surprise later.

| Query | Shape | Blocked on |
|---|---|---|
| "Where did Detroit techno come from?" | A, origins | Absent from all 351 P737 edges. Needs a second source — `dbo:stylisticOrigin` is the phase-6 candidate |
| "What did bebop grow out of?" | A, origins | `bebop <- swing` is not in the corpus. Same second-source dependency |
| "Who influenced Kate Bush?" | A, **artist axis** | **Nothing — the axis shipped 2026-08-06, phase 2 step 6c.** But the query now **correctly refuses**, and that is the answer rather than a defect: Kate Bush has **zero outgoing P737 and seven incoming**, so the corpus records who *she* influenced and not who influenced *her*. See the note below. |
| "What came out of Jamaican ska?" | A, descendants | Ska is absent entirely, and the descendant direction is not walked at v0.1 |
| "Trace the roots of Brazilian tropicália." | A, origins | 1 edge, fails the prose check. Needs corpus expansion |
| "How is the blues connected to heavy metal?" | **C, path** | **Nothing — delivered 2026-08-05, phase 2 step 5.** It answers end to end through `trace_lineage`, with both hops gated and cited. *(Corrected 2026-08-04: this said phase 5, written while `path()` was a phase-1 deferral. The ROADMAP assigns multi-hop traversal to phase 2; phase 5 consumes it for the guided tour.)* *(Amended 2026-08-02: the chain originally read through to `extreme metal`; that edge was rejected on hand-reading as taxonomic, so the path is two hops, not three.)* *(2026-08-05: typed verbatim, this query first **refused** — the node is labelled `heavy metal music` and 32 of 169 labels carry that suffix. `label_key` now makes a trailing "music" optional on both sides.)* |

**On the Kate Bush row, resolved 2026-08-07.** It had read "Blocked on: the ~31k artist-level P737 edges.
Phase 2" since 2026-08-02, which was stale from the moment the axis landed — a canonical doc asserting a
blocker that no longer exists. Two options were on the table and **the row is annotated rather than
swapped**, for a reason worth stating: this is the single best coverage-honesty chip the corpus has.
Every other refusal in the set is "the graph does not contain this." Kate Bush is *in* the graph, is
richly connected, is cited elsewhere in answers — **and the system still declines**, because the edges
run the other way. A visitor who clicks it learns more about what "grounded" means here than any
successful answer teaches them.

The alternative remains open and is a **v0.5 chip-selection call, not a contract change**: swap in an
artist with outgoing edges (U2 answers with six gated claims) if the chip row needs a working artist
demo alongside. Both can ship — seven slots, and one of them being an honest refusal is a feature.

A second thing the row should carry when the chips are built: the natural follow-up **"who did Kate Bush
influence?"** *is* answerable, and answering it immediately after the refusal is a stronger demo than
either alone. That needs `get_descendants`, which phase 3 adds (A2).

The last row replaces the original "How is delta blues connected to hip hop?", which was the intended
signature demo. Delta blues is absent from the corpus and no path exists between blues and hip-hop, but the
blues-to-metal chain is the same shape, the same memorability, and it is real. It is the strongest argument
in the corpus for the project's thesis that music history is a network rather than a timeline.

## 3. What this refuses to be

One line, because a scope fence does more work than a feature list:

> Not a music recommender, not a streaming companion, not a taste engine, and not an authority on what is
> true — it shows what is documented, and who documented it.

"Not a recommender" is the important one. It is the obvious thing to assume a music AI does, and it is the
opposite of this project: recommendation optimizes for what you will enjoy next, this optimizes for what
can be sourced.

## 4. The imagined user — OPEN

`planning/09` §2 question 4 asks who the non-recruiter user is: a music-curious adult, a student, or
himself. Left open deliberately; it changes reading level and how much context each answer assumes, and it
is a product-taste call. Answer before the SPA copy is written at v0.5. It does not block v0.1.

## 5. Data contracts — OPEN

Owned by the v0.1 IMPLEMENTATION doc. Fixed already by `CLAUDE.md` invariants regardless of how the schema
lands:

- Every node and edge carries `source`, `source_id`, `retrieved_at`.
- The artifact is versioned and immutable, with a manifest. Everything downstream reads a pinned version.
- P279 (`subclass of`, taxonomic) and P737 (`influenced by`) are distinct and separately validated, with an
  explicit boundary predicate so P279 chains do not climb out of the genre domain.

**Added 2026-08-04 (phase 2 step 3), extended 2026-08-06 (step 6c), table corrected 2026-08-07.** Every
edge carries `verification`, one of **four** values. *(This table listed only the first two until
2026-08-07; the artist axis added the other two at v0.4.0 and SPEC was not updated with it. Anyone
implementing against the stale table would have built a two-value enum.)*

| value | count at v0.5.0 | meaning |
|---|---|---|
| `HAND` | 22 | a human read the subject's article and judged that its prose asserts influence |
| `PROSE_AUTO` | 111 | the automated prose check passed, and nothing more |
| `ASSERTS_AUTO` | 760 | the influence-assertion filter found an explicit statement of influence |
| `EXPOSURE_AUTO` | 57 | the text records real-world contact or engagement, short of a stated influence claim |

It is **required, with no default**, and the tiers are ordered by strength but are **not points on one
scale**. `HAND` and `ASSERTS_AUTO` rest on what a source *states*; `EXPOSURE_AUTO` rests on what a
reader would reasonably *infer*, which is a different kind of claim and is why it is labelled rather
than merged. `PROSE_AUTO` is strictly weaker than `HAND`: the check confirms the article names the
object in body prose but cannot judge whether the sentence *asserts* influence.

**Measured, and published rather than smoothed:** the assertion filter runs at **97% precision / 95%
recall** on held-out data for `ASSERTS_AUTO`, and **20% recall** for `EXPOSURE_AUTO`. The exposure tier
is therefore a **floor on what exists in the sources, never a count of it.**

The manifest carries the per-level counts, derived from the edges rather than passed in. An unmarked
mixture of these tiers would be worse than any one alone, which is why the field cannot be omitted.

**Added 2026-08-07 (phase 3).** `verification` also rides on every approved **`Claim`**, copied off the
edge by the gate exactly as `source_ids` is, so a reader can tell per claim — not only in aggregate —
which evidence tier they are looking at. Two further states are **defined and deliberately unreachable**,
each with its precondition recorded: `contested` needs a second source (every edge here has exactly one,
always Wikidata), and `checks_disagree` needs a corpus policy that flags conflicting checks rather than
excluding them. A test locks both. See `phases/phase-3-agent-loop.md` A1.1.

## 6. API contract — OPEN

Owned by the v0.1 IMPLEMENTATION doc, and it should be written **before** anything calls it. Fixed already:

- Response streaming, not request/response (invariant 9).
- The payload includes the agent's walked **path, in order** — cheap now, annoying once the schema has
  consumers.

**Added 2026-08-04 (phase 2 step 3).** `/health` and the `done` frame both carry a `corpus` object:

```json
{ "artifact_version": "0.2.0", "nodes": 169, "edges": 133,
  "verification": { "HAND": 22, "PROSE_AUTO": 111 }, "predicate": "influenced_by" }
```

Coverage is on the screen, not in a footnote (`planning/04` §4.5), and `verification` is the honest half
of it: a corpus that is mostly machine-verified is noisier per edge, and the product states the split
rather than presenting one undifferentiated edge count.

**Added 2026-08-05 (phase 2 step 4).** The corpus object also carries `structure`:

```json
{ "component_count": 41, "largest_component": 31, "diameter": 10,
  "isolated_nodes": 0, "max_path_hops": 2 }
```

This is the connectivity half of the same honesty, and it is the half a visitor cannot infer. An edge
count alone implies one connected graph; the corpus is **41 disconnected islands**, so relating two
genres is a capability *within* a component and two genres in different components have no sourced path
at all. `max_path_hops` is the deepest chain `path()` can return anywhere in the corpus. Publishing both
is what keeps an empty answer legible as a **boundary rather than a failure** — which matters because
refusal is correct behaviour here and has to be distinguishable from breakage.

Derived, never stored: the store recomputes it on load rather than trusting the manifest, so it cannot
drift from the corpus in hand.

**Added 2026-08-06 (phase 2 step 8), recorded here 2026-08-07.** The corpus object also carries
`coverage`, the genre-axis measurement of what the graph can and cannot speak about. *(Shipped in
`/health` and `done` since step 8; SPEC missed it, so the deployed contract was a superset of the
canonical one for a day.)*

```json
{ "genres": 169, "without_inception": 28, "without_country": 48,
  "eras": { "pre-1900": 6, "1900-1949": 7, "1950-1969": 29, "1970-1989": 47,
            "1990-2009": 39, "2010-": 13, "unknown": 28 },
  "coarser_than_year": 19, "distinct_countries": 29,
  "genres_without_us_or_uk": 43, "top_country": "United States", "top_country_share": 0.421,
  "countries": { "United States": 51, "United Kingdom": 42, "Japan": 14, "…": 0 } }
```

**Both halves ship or neither does.** `top_country_share` alone invites "so it is only Western music",
which is false; `distinct_countries` and `genres_without_us_or_uk` are the counterweight, and they are
held to the same standard — `genres_without_us_or_uk` read 44 until 2026-08-07, when `UK drill`'s P495
of `Brixton` was found counting as "names no UK". Genre axis only, stated rather than implied: P571 and
P495 are genre properties, and averaging 804 unmeasured artist nodes into a genre figure would read as a
far thinner corpus than it is.

Also derived on load, for the same reason as `structure`.

**Added 2026-08-05 (phase 2 step 5).** The `path` frame carries two orderings, not one:

```json
{ "node_ids": ["Q9759", "Q38848", "Q193355"], "labels": ["blues", "heavy metal music", "blues rock"],
  "chain": ["Q38848", "Q193355", "Q9759"],
  "chain_labels": ["heavy metal music", "blues rock", "blues"] }
```

`node_ids` is the walk — the order the agent touched things, which is the transparency the streaming
demo is for. `chain` is the **approved line of descent, descendant-first**, and it exists as its own
field because the two are genuinely different and inferring one from the other states false history: a
lineage question resolves both endpoints before it traces between them, so the walk opens *blues, heavy
metal* while the descent runs the other way. `chain` is empty for an origins query (a fan-out of
influences is a set, not a sequence) and empty when the gate rejected any hop — a broken chain is never
displayed as a chain, and the surviving claims are listed instead.

## 7. Claim contract — OPEN in detail, fixed in shape

`Claim(subject_id, predicate, object_id, source_ids, span)`. The pipeline is claims first, prose second:
the agent emits claims, a deterministic gate approves them, and prose is generated from the approved set
only. Prose generation cannot see anything else. See `.claude/rules/grounding-and-claims.md`.
