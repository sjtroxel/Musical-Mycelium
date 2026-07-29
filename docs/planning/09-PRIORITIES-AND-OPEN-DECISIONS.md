# Music Lineage Project — Priorities and What Actually Remains Before Naming (Fable, 2026-07-27)

> Forward-looking half of the 7/27 review (`08-REVIEW-VERDICT-AND-CATCHES.md` is the backward-looking half).
> Everything here is either a conversation to have or a checklist to run — no new analysis, no new planning docs.

---

## 1. The priority stack, stated once

When two things compete for a session, this is the order:

1. **The job search.** Applications continue at the current rhythm; the tripwire re-evaluation happens at n≈65 as he
   designed. The build never displaces an application he would otherwise have sent.
2. **This project's job within the search:** close the AWS gap (~7 appearances in the tracker) with a **deployed URL
   plus real eval numbers** — the two things a recruiter or interviewer can actually touch. Everything in the project
   serves that before it serves anything else.
3. **The project as a project** — the full vision: density, the SPA, the cinematic traversal, v1.0 polish.

Order matters most under pressure: on a tired week, priority 2 beats priority 3 (ship the skeleton, defer the beauty),
and priority 1 beats both.

## 2. The one remaining conversation of substance: what does a user actually DO

This is the largest genuine gap in `00`–`07`, and it should be settled **before** naming, because a name names the
product, and right now the product is an architecture with a concept attached. Three different products are consistent
with everything written so far:

- **A. The question-answerer** — a search box; ask about a genre/artist; receive a streamed, cited lineage narrative.
- **B. The explorable map** — the graph is the interface; wander, zoom, follow edges; the agent annotates on demand.
- **C. The guided tour** — "take me from delta blues to Detroit techno"; the agent plans a path and narrates it as the
  camera walks it.

These have different frontends, different API shapes, and different names. (`06` quietly assumed a blend of A and C;
`07` assumes A-shaped queries; the concept in `00` sounds like B. That inconsistency is the tell that nobody decided.)

**Recommendation, offered for his call, not made for him: A as the v0.x spine, C as the v1.0 showcase, B as the
ambient surface the SPA provides for free once the graph renders.** A is what the walking skeleton already builds
toward and what evals measure cleanly; C is the signature demo `06` §5.1 identified; B alone would abandon the agent
(and the agent is the resume). But this is a product-taste decision and it is his.

**To run the conversation, five questions, ~30 minutes:**
1. Name the 5–7 **canonical queries** — the exact strings a first-time visitor should be able to type and get something
   great back. (These become gold-set cases and demo material; write them down verbatim.)
2. What does the **first screen** show before the user does anything?
3. What's the **30-second recruiter path** — someone clicks the resume link, does what, sees what, remembers what?
4. Who is the **imagined non-recruiter user** — a music-curious person, a student, himself?
5. What does the app **refuse to be**? (One line — e.g., "not a music recommender, not a streaming companion" — this
   fences scope creep better than any feature list.)

## 3. Pre-decisions to write down while calm (from `08` §5)

- **The build survives the tripwire.** n≈65 lands mid-build at the current pace. Every plausible outcome of that
  re-evaluation still wants the AWS gap closed; there is no branch where abandoning the half-built project is right.
  Decided now so a bad week doesn't decide it later.
- **Cadence:** applications keep their existing rhythm; the project gets a stated number of sessions per week (his
  number to pick — 2–4 is the realistic band given the Patchwork history). The point is that both numbers exist, so
  neither loop silently eats the other.
- **Resume-ready threshold ≠ v1.0.** The project goes on the resume, LinkedIn, and application free-text boxes at
  roughly **v0.3–v0.4** — deployed URL, real agent loop, eval suite with published numbers — not when it's beautiful.
  Patchwork ran 14 phases; the resume line must not wait for this project's equivalent. Guard the
  discount-the-win reflex: "deployed on AWS Lambda + Bedrock with a deterministic groundedness gate at 100%" is fully
  claimable at v0.3, and September profile-evidence timing favors claiming it early.

## 4. Naming session — agenda (his ritual, his name; support only)

1. Product conversation (§2) first — name follows product.
2. Generate freely; his bar from `00` §6 applies (six-seconds-distinct, genuinely his).
3. **Availability screen before falling in love:** domain (.com or a good TLD), GitHub repo/org name, a general web
   search for collisions — especially existing music-tech brands (the space is crowded: Music Genome/Pandora,
   Every Noise at Once, MusicMap, etc. are taken territory, and near-collisions cost more than they look).
4. Recruiter-surface test: pronounceable, spellable on a phone screen, survives being said cold in an interview.
5. Then it's named, and `music-lineage-planning/` migrates to the new repo per `00`'s header note.

## 5. Repo bootstrap checklist (mechanical; run once after naming)

- New repo; migrate `music-lineage-planning/` docs in (per `00` header) — renumber as the project's `docs/planning/`.
- Extend the shared-brain memory symlink over the new repo (canonical store stays `job-search-headquarters`).
- `.gitignore` **on the first commit**: `.env`, `.tfstate`, editor litter — per `04` §6.2, before anything exists to leak.
- Doc pattern from day one: ROADMAP + SPEC + per-phase IMPLEMENTATION docs, archive-superseded discipline.
- Single-command dev runner from the first week (standing preference; retrofitting is always worse).
- Then the AWS signup checklist (`04` §9 items 1–3), with the two credit nuances from `08` §4: credits expire 12 months
  from account creation; never join an AWS Organization with this account.

## 6. What goes in the IMPLEMENTATION doc (not now, not here — listed so nothing is lost)

Accumulated assignments from the whole series, gathered in one place:

- The claims-first → prose-from-claims agent pipeline (`08` §2) — now a structural requirement.
- The P279/P737 20-edge hand-validation, plus the genre-domain boundary predicate (`04` §4.4, `08` §4).
- v1 scope + explicit not-in-v1 list (`05` §8.2); definition of done for v0.1 (`05` §4).
- Graph store pick among the $0 options; Terraform vs. CDK (recommendations already on record).
- Judge-model choice (non-Anthropic family, source per `08` §4); Sonnet-5 adaptive-thinking handling per call site.
- Streaming implementation shape (Function URL + response streaming) and the path-in-payload schema (`06` §6).
- Testing strategy beyond evals: unit/integration layout, metric unit tests (`07` §8) in CI from v0.1.
- Eval build order mapped to versions (`07` §12), gold-set authoring session scheduled **before** agent coding starts.

## 7. The sequence from here

**Product conversation (§2) → naming session (§4) → new repo + bootstrap (§5) → IMPLEMENTATION doc (§6) → AWS signup
(`04` §9) → walking skeleton.**

Two conversations and a checklist stand between now and writing the IMPLEMENTATION doc. Planning is closed;
`08` §6 says why, and this doc is deliberately the last one with a number.
