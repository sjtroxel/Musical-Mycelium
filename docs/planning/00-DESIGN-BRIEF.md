# Music Lineage Project — Design Brief

- **Name:** **Musical Mycelium** (locked 2026-07-29; see `NAMING-WORKSHEET.md` for the process and the availability screen)
- **Tagline (working):** *the hidden network beneath the history of music* — the name is deliberately oblique, so the tagline is load-bearing and belongs on every surface
- **Status:** CONCEPT LOCKED, data verified live. Pre-IMPLEMENTATION-doc.
- **Date captured:** 2026-07-24
- **Read order:** `00-DESIGN-BRIEF` (this) → `01-DATA-SOURCES` → `02-ARCHITECTURE-AND-GAPS`

> This folder is the staging ground for the AWS/Bedrock "next project," captured 2026-07-24 at the end of a long design session. It migrates into the project's own new repo once the project is named. Canonical memory lives in `job-search-headquarters` (see the shared-brain symlink note in memory).

---

## 1. The concept (one line)

An AI system that reconstructs the hidden **history of music** — where genres and forms came from, how they interconnect, and who influenced whom across time and geography — as an explorable, **grounded, cited lineage graph**.

## 2. Why this project (the motivation — do not lose this)

- **Portfolio driver (from `DEVELOPER_PROFILE_MAY_2026.md`):** the projects sjtroxel actually *finishes* are the ones hooked to a genuine fascination with a **hidden real-world system**. Asteroid Bonanza's true hook was the resource *economics*, not "space." Wildlife Sentinel's was the *precariousness* of endangered species. The emotional/intellectual hook is a professional asset, not a soft detail.
- **The unlock — Baron-Cohen's empathizing–systemizing theory (his own insight):** sjtroxel is a strong **systemizer** / weak empathizer. That is *why* he had never built anything in culture or play — he reads culture as emotional, therefore un-systematic, therefore not for him. The reframe that broke it open: **music itself is emotional, but the *history* of music is a system** — a graph of descent, influence, and diffusion. He builds the *structural skeleton underneath the emotion*, not an emotion engine. This resolves the culture-avoidance and lands squarely in his sweet spot.
- **Fresh territory (six-seconds-distinct):** across eight prior projects — space (Asteroid Bonanza), wildlife/environment (Wildlife Sentinel), history×2 (ChronoQuizzr, Heritage Odyssey), law (Patchwork Assurance), historical posters (Poster Pilot), agriculture (SoilProve), travel/mapping (Strawberry Star, Mighty Mileage Meetup) — he has **nothing** in human culture, and **nothing** that is a pure "hidden connections" graph. A recruiter glancing for six seconds sees something new, not a sequel.

## 3. Design principles (locked)

1. **Full-history skeleton; density fills in.** Model the *whole* structure of music history as one connected graph spanning all eras. Do **not** scope the *domain* down to the well-documented era. Ancient/oral/folk traditions are nodes that *exist and connect* — just sparsely populated at first. Density fills in over time. **Scope the density, never the structure.** (sjtroxel's instinct; adopted over Claude's earlier "v1 stops where the data is rich.")
2. **Grounded + cited; bias by construction.** "Influence" is subjective and contested. The system only reports **sourced** connections and **explains with citations** — it never asserts an unsourced influence edge, and it flags contested claims. This is Patchwork Assurance's deterministic-gate DNA generalized, and it doubles as the neutrality guarantee.
3. **Analytical, goal-directed agent — not world-acting.** See §4.
4. **Stateless / read-only.** Public, read-only source data → nothing to protect → no SQL + auth. Preserves the stateless-over-auth invariant.

## 4. The shape decision (and the deferred second project)

- On **2026-07-19** the lean was a goal-directed agent that *takes actions in the real world* — a "doer," specifically to answer the interview jab "you just built a chatbot."
- **Decision 2026-07-24:** this project is a **goal-directed research / analysis agent** — given a genre or artist it *plans* a traversal, makes *multi-step tool-calls* across the data sources, cross-references, and *synthesizes* a grounded, cited lineage. This is still meaningfully different from Patchwork Assurance (multi-step planning + tool-use, not single-shot RAG), so it adds shape-range to the portfolio. But it is **analytical, not world-acting** — no emails, no external state mutation.
- **sjtroxel confirmed this is the right call:** no single project cleanly covers *both* the AWS/Bedrock/Python gap-fill *and* the "do stuff in the real world" goal — honestly, that takes **two** projects. The world-acting "doer" is therefore a **separate future project (deferred, not dropped).**

## 5. Open questions / next steps

- **NAME:** not chosen yet. Brainstorm session over the weekend (his ritual — he names it; Claude helps generate options).
- Then: **IMPLEMENTATION doc first** (his standing rule) before any code.
- Then: **new repo**, and extend the shared-brain memory symlink over it (canonical store = `job-search-headquarters`).
- **Design question to keep warm:** graph store = **AWS Neptune vs. graph-on-Postgres** (details in `02-ARCHITECTURE-AND-GAPS`).

## 6. How we got here (decision log, so the reasoning survives)

- Many domain ideas were offered and rejected against a hard bar: *six-seconds-distinct from all 8 prior projects* **and** *genuinely exciting to build* **and** *clean free data* **and** *employable*. Rejected along the way: government/civic data (spending, vehicles, filings, bills — clean but not exciting to him), single-feed natural-hazard monitors (read as "Wildlife Sentinel 2.0"), art/museums (overlaps Poster Pilot), books/Gutenberg (overlaps Heritage Odyssey).
- A mid-session reframe worth remembering: differentiation *from his own portfolio* matters far less to a recruiter (who compares him to *other candidates*) than it feels — but he still, legitimately, wanted the *fun* of new ground, and the fun is load-bearing for a project that must actually get finished.
- The breakthrough was his E-S self-observation (§2), which reframed "culture is emotional, not for me" into "the *history* of music is a system I'd love to map."
