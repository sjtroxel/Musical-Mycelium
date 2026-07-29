# Music Lineage Project — Independent Review of the Planning Series (Fable, 2026-07-27)

> sjtroxel asked for a fresh-eyes review of the whole 7/24–7/27 planning effort (`00`–`07`), the session that produced
> it, and the wider repo/memory context: what's missed, what else needs thinking out before naming, and what the
> ultimate priorities are. This doc is the verdict and the specific catches. `09-PRIORITIES-AND-OPEN-DECISIONS.md` is
> the forward-looking half: what actually remains before naming.

---

## 1. Overall verdict

**The series is genuinely strong, and I mean that as an assessment, not encouragement.** The decisions cross-reference
each other, superseded material is marked rather than deleted, every load-bearing external fact was web-verified on the
day it was written, and — rarest of all in planning docs — each one states what it is *still* wrong about. The five
biggest calls are correct:

- **Killing Neptune** (`03`) — right, and the VPC/NAT-gateway chain reasoning is the part most people miss.
- **Paid Plan at signup** (`04` §1.1) — right, and it was caught *before* account creation, which is the only cheap
  moment to catch it.
- **Streaming as a product decision, not a workaround** (`04` §3.1) — right.
- **Walking skeleton with nine one-way doors** (`05`) — right, and correctly anchored to his own
  "scope the density, never the structure" principle rather than presented as imported wisdom.
- **Deterministic groundedness as the headline eval** (`07` §2) — the single best idea in the series. It converts the
  project's core promise from a claim into a checkable property, and it collapses eval spend to near-zero.

The process discipline was also right: costs were checked before naming (his instinct), risks before architecture
romance, and Opus explicitly called the end of the planning phase rather than feeding more of it. I'm going to respect
that call — §4 below is deliberately short.

**What follows are the real findings: two substantive catches, several small ones, and a wider-context observation the
series couldn't have made because it wasn't looking at the job-search timeline.**

---

## 2. Catch #1 (technical, the important one): the eval spec's headline metric has a leak

`07` §2 specifies that the agent emits structured `Claim` objects **alongside** prose, and §4.1 defines edge
groundedness over *the emitted claims*. Here is the hole:

**Nothing checks that the prose contains only what the claims capture.** The model can emit five dutiful, fully
grounded `Claim`s and *also* write a sixth influence assertion in the prose that never became a claim. That assertion
is invisible to the groundedness check. The metric reads 100% while the text hallucinates — the gate is airtight around
a door that isn't the only door.

This is precisely the class of bug `07` §8 teaches you to hunt for (the vacuous-truth guard is its cousin), applied to
the spec's own flagship metric. Two-part fix, both cheap if adopted now:

1. **Invert the generation order: claims first, prose from claims.** Don't generate prose and extract claims from it —
   have the agent's traversal produce the claim set, gate it deterministically, and *then* have the model write prose
   **from the gated claim set as its only substantive input**. The pipeline structure itself then constrains what the
   prose can assert. (This mirrors Patchwork's own architecture: deterministic gate decides, LLM writes prose only —
   the pattern was already in the house; it just hadn't been applied here.)
2. **Add a claim-coverage audit as a metric** — "does the prose assert any influence/derivation relationship absent
   from the claim set?" This is a judged, *sampled* check (it's semantic, so it can't be a lookup), sitting in Tier 2
   next to citation support. It exists to verify the pipeline constraint actually holds, because LLMs drift even when
   structurally constrained.

`07` §2 has been amended with a pointer to this section, and this becomes an agent-pipeline requirement in the
IMPLEMENTATION doc. With the fix, the claims-first pipeline is arguably a *stronger* architecture story than the
original: "the model literally cannot narrate an edge the gate didn't approve" is a better sentence than "we check the
claims it tells us about."

## 3. Catch #2 (framing): "grounded" means "in Wikidata," and an interviewer will ask

Deterministic groundedness proves the system's output is consistent with **its own artifact** — which is built from
Wikidata and MusicBrainz. It does not prove the artifact is *true*. Wikidata influence edges are crowd-entered; some are
wrong; some are vandalism that survived patrol.

The docs already know this in spirit (bias-by-construction, contested-claim flagging, coverage honesty), but the
interview answer in `07` §13 — "the system cannot assert a musical influence that isn't in its sourced graph" — invites
the obvious follow-up: *"and what if the graph is wrong?"* He should have the answer ready rather than discover the
question live:

> Groundedness is a **provenance** guarantee, not a **truth** guarantee — and that's the honest limit of any RAG-class
> system. What it buys is that every assertion is *traceable to a named source that a human can check*, that contested
> claims are flagged rather than silently resolved, and that the gold set (`07` §3.1) cites sources **independent of
> Wikidata**, so the eval suite would surface a region where Wikidata and the scholarship diverge.

One sentence of humility that converts a weakness into evidence of calibration. It belongs in the eventual writeup too.

## 4. Small catches (each one line of action, none worth its own section)

- **`01` vs `04` licensing discrepancy:** `01` says MusicBrainz CC BY-NC-SA fields are "portfolio/non-commercial =
  fine"; `04` §4.2 says stay on CC0 core tables. **`04`'s stricter rule governs** — a hiring-portfolio piece is
  arguably promotional use, and the strict rule costs nothing. Noted here so the two docs don't fight later.
- **Credits nuance (verified 7/27):** the $200 expires **12 months after account creation** on either plan, and
  **joining an AWS Organization forfeits remaining credits immediately**. Neither threatens the plan; both belong on
  the signup checklist in `09`.
- **Judge-model diversity** (`07` §6 requires a judge from a different family): Bedrock itself carries non-Anthropic
  families (Nova, Llama, Mistral, DeepSeek), and the OpenRouter wallet exists as a fallback. No blocker — just decide
  in the IMPLEMENTATION doc rather than discovering the constraint at v0.4.
- **Sonnet 5 adaptive-thinking gotcha** (from Patchwork memory, applies on Bedrock too): thinking is ON by default when
  the parameter is omitted, which silently spends tokens on structured calls. Handle per-call-site in the
  IMPLEMENTATION doc, exactly as Patchwork did.
- **P279 chains don't stop at genres.** Beyond the historical-vs-taxonomic question `04` §4.4 already flags, subclass
  chains climb out of the genre domain entirely (genre → "art form" → …). The ingestion filter needs an explicit
  boundary predicate — one more reason the 20-edge hand-read comes before ingestion code.

## 5. The wider-context observation the series couldn't make: the tripwire lands mid-build

This is the one thing that comes from reading the whole repo rather than the planning folder.

He is at **45 applications**; the self-set re-evaluation point is **n≈65 apply-only**. At the recent application pace,
n≈65 arrives in roughly **3–6 weeks — which is almost certainly mid-build.** So the strategic re-evaluation he
committed to will fire while this project is half-finished, quite possibly during the unglamorous middle where the
skeleton works but nothing is impressive yet.

**The pre-decision to make now, while calm:** *the build survives the tripwire, whatever the tripwire concludes.*
Check the logic: every plausible outcome of that re-evaluation — double down on the current lane, pivot harder to
founding-engineer roles, add contract/freelance, reweight toward a different market segment — **still wants the AWS gap
closed**, because AWS is the single most recurring hard filter in his tracker (~7 appearances). There is no branch of
the n≈65 decision tree in which "abandon the AWS project half-built" is the right move. Writing that down now is cheap
insurance against a bad week deciding it later.

(The reverse guard also holds and `04` §8.3 already named it: the build is parallel to applications, not a substitute.
`09` proposes the concrete cadence.)

## 6. What I am deliberately NOT recommending

To keep faith with the planning-is-done call:

- **No more risk/architecture/design planning docs.** The series is past the point of diminishing returns; `04` §7's
  own argument (surprises are cheapest met in a small deployed system) now applies to the planning itself.
- **No technology-learning plan.** The walking skeleton is the learning plan.
- **No marketing/positioning doc.** v1.0 work, on the established pattern (Patchwork's launch overhaul happened at
  launch, correctly).
- **No second review pass.** This one stands unless something material changes.

`09-PRIORITIES-AND-OPEN-DECISIONS.md` holds the short list of what genuinely remains — and it is short: one product
conversation, a handful of pre-decisions, the naming session, and the bootstrap mechanics.
