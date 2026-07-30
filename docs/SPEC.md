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

## 2. Canonical queries — DRAFT, his to edit

These are load-bearing in four places at once: the chips on the first screen, the demo script, the gold-set
cases, and the eval slices. `planning/09` §2 asks for them verbatim, so they are written here as a starting
point to react to rather than a blank page. **Edit freely — this list is not approved yet.**

1. "Where did Detroit techno come from?"
2. "What did bebop grow out of?"
3. "Who influenced Kate Bush?"
4. "What came out of Jamaican ska?"
5. "Trace the roots of Brazilian tropicália."
6. "How is delta blues connected to hip hop?"
7. "What descends from West African griot traditions?"

Notes on the set, since the composition is doing work:

- 1, 2, 4, 5 are **A-shaped** (origins and descendants of one node) — the v0.1 spine.
- 3 is the **artist axis** (P737), not the genre axis (P279). Both need to work; they are different
  predicates and conflating them is invariant 3.
- 6 is **C-shaped** — a path between two nodes. It belongs in the set because it is the most memorable
  query type, but it should be honestly labeled as arriving later than the others.
- 7 deliberately targets a **sparse, non-Western region** of the corpus. It is in the set precisely because
  it is the one most likely to expose thin coverage, and coverage honesty is a stated metric. If the answer
  is "the graph does not support this well," that is the correct answer and it should say so.

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

## 6. API contract — OPEN

Owned by the v0.1 IMPLEMENTATION doc, and it should be written **before** anything calls it. Fixed already:

- Response streaming, not request/response (invariant 9).
- The payload includes the agent's walked **path, in order** — cheap now, annoying once the schema has
  consumers.

## 7. Claim contract — OPEN in detail, fixed in shape

`Claim(subject_id, predicate, object_id, source_ids, span)`. The pipeline is claims first, prose second:
the agent emits claims, a deterministic gate approves them, and prose is generated from the approved set
only. Prose generation cannot see anything else. See `.claude/rules/grounding-and-claims.md`.
