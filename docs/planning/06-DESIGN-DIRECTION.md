# Music Lineage Project — Visual Design Direction (2026-07-27)

> Raised after `05-EVOLUTION-PLAN.md`: this app is about music, which is an art form, and it should look like it.
> Previous projects have been functional-first; this one should push further.
>
> **Verdict: agreed, and this is the right project for it — but aim at a different reference class than "marketing
> agency," because that target is both easier and less impressive than what this app actually wants to be.**

---

## 1. Why the instinct is right here specifically

This is not decoration bolted onto a backend. For this app, **the visualization is the product**:

- The core artifact is **a graph** — a thing that literally cannot be understood as a list. Rendering it well *is* the
  feature, not a wrapper around the feature.
- The domain has a **time axis spanning millennia** (inception dates reaching ~2000 BCE per `01-DATA-SOURCES.md`), which
  is an unusually rich visual problem: lineage, diffusion, geography, density-over-time.
- The agent **streams its reasoning** (`04-RISK-REGISTER.md` §3.1). A visible reasoning trace synchronized with a graph
  that moves as the agent traverses it is **inherently cinematic** — and it's the single best demonstration that the
  agent loop is real and hand-built rather than a chatbot wrapper.
- Music has a deep existing visual vocabulary to draw from and no obligation to invent one from scratch.

So: the ambition is justified on product grounds, not just aesthetic ones. That matters, because design effort that
serves the product survives scrutiny and design effort that doesn't reads as padding.

## 2. The reference class to aim at — and the one to avoid

**Avoid: the marketing-agency / awards-site aesthetic.** Scroll-jacking, full-bleed hero video, parallax, a cursor that
becomes a blob, text that assembles letter by letter. That genre optimizes for a **thirty-second impression on a
stranger**. It is a real craft, but it is the wrong craft here, and to an engineering audience it often reads as
*substance-free* — the exact opposite of what this project is trying to prove. It also actively fights a tool whose
purpose is to let someone explore a dense structure for twenty minutes.

**Aim at: the explorable-explanation / editorial-data-visualization tradition.** The reference points:

- **The Pudding** — essays that are interactive visualizations; heavily music-focused, so the domain overlap is direct.
- **NYT / Reuters / Bloomberg graphics desks** — the working standard for making a complex structure legible and
  beautiful at once.
- **Every Noise at Once** — the closest existing thing to this project's domain; worth studying for what it gets right
  (staggering density made navigable) *and* wrong (visually raw, hard to enter).
- **Observable notebooks / D3 gallery** — the craft baseline for graph and network rendering.

This tradition is **harder** than the agency aesthetic, not easier. It requires the visual polish *and* the information
design to be right simultaneously. Hitting it is a genuine differentiator; hitting the agency look is not.

## 3. The premise worth correcting

The framing was *"everyone's doing it and simple does-it-work doesn't cut it anymore."* Two separate claims, and they
have different truth values.

**"Everyone's doing it" — not in this space.** The overwhelming majority of AI-engineering portfolio projects look like
a Streamlit app, an unmodified component-library default, or a chat box. That is the actual baseline being competed
against. **Doing serious data-visualization craft would make this project unusual, not average.** The anxiety is
pointed at a crowd that isn't there.

**"Does-it-work doesn't cut it" — true for this project, false as a career diagnosis.** Worth separating cleanly:

- **As a product judgment about this app: correct.** A graph tool that works but is illegible has failed at its actual
  job. Ship it beautiful.
- **As a theory of why applications haven't landed: not supported.** The evidence in `applications/TRACKER.md` says
  rejections are landing *upstream* of anyone opening a link — automated screens, tenure filters, Easy-Apply volume.
  Nothing in the record shows a project being passed over for looking plain. **Visual polish is worth doing because it
  makes the work better, and it will not move the hiring gate.** Doing it for the first reason is sustainable; doing it
  for the second leads to over-investing and then feeling cheated when the phone still doesn't ring.

Build it beautiful because the graph deserves it. Not as a fix for something design can't fix.

## 4. Design is a systems problem, which is the good news

A common trap: treating visual design as taste, intuition, or an innate eye — a framing that makes it feel like foreign
territory for someone who identifies as a strong systemizer.

**Serious data-visualization design is not taste-driven. It is rule-driven**, and the rules are the interesting kind:

- **Perceptual constraints** — which visual channels encode which data types, and in what order of accuracy (position >
  length > angle > area > color).
- **Color as a system** — sequential vs. diverging vs. categorical, contrast ratios, colorblind-safe construction,
  light and dark parity. This is a formula that can be validated, not a vibe.
- **Motion with a job** — animation that shows a state *transition* (this node became that node) aids comprehension;
  animation that merely decorates costs attention and, for some users, physically hurts.
- **Type and spacing scales** — ratios, not guesses.
- **A token system** — every color, space, duration, and easing defined once and referenced everywhere.

This is a spec-and-constraints problem wearing an aesthetic costume. **It is squarely in the systemizer lane.** The
output of good design work here is a *design system*, which is a build artifact like any other.

Practical note: when preview-building actually starts, load the **`dataviz` skill** first — it carries the color
formula, a runnable palette validator, mark specs, and interaction rules. Do not hand-roll a palette.

## 5. What this app can do that the previous seven couldn't

Concrete opportunities, ordered by payoff:

1. **The signature moment: synchronized narration and camera.** As the agent streams its reasoning, the graph animates
   the traversal it is describing — camera easing along the lineage path, nodes illuminating as they are cited, the
   citation appearing as the claim is made. **One shared timeline driving both the text and the view.** Nobody's
   portfolio has this, it is only possible because the streaming decision was made in `04` §3.1, and it is the single
   most demo-able thing in the entire project.
2. **Time as a real spatial axis.** Most graph viz is force-directed mush. Anchoring the y-axis (or x) to actual
   chronology turns the layout into an argument: influence flows in one direction, eras become bands, the sparse
   ancient end becomes visibly ancient rather than accidentally empty.
3. **Density and coverage as a visual, not a caveat.** `04` §4.5 flagged that the data is Western/anglophone/recent-
   biased and recommended making coverage a first-class metric. **Rendered honestly — thin regions look thin — the
   bias-by-construction stance becomes something a viewer can see rather than a disclaimer they skip.** That is a
   design decision doing epistemic work, and it is a genuinely strong interview story.
4. **Geographic diffusion.** Where forms traveled, when. A second view over the same graph.
5. **Restraint as the house style.** Dark ground, restrained palette, one accent for the active path, generous space,
   type that behaves. Let the graph carry the visual interest. This ages far better than effects.

## 6. Architectural implications — small, but one is real

The good news from `05-EVOLUTION-PLAN.md` §2.2: **the frontend is a two-way door.** The API contract is the boundary,
so the SPA can be rebuilt from scratch — twice — without touching the backend. Design ambition does not threaten the
architecture and does not need to be resolved before the build starts.

Two things are worth deciding *with* the ambition in mind rather than discovering later:

- **The rendering engine.** SVG/canvas libraries (Cytoscape) are excellent for modest graphs and awkward for smooth
  camera work over thousands of nodes. WebGL renderers (Sigma.js, deck.gl, regl-based custom) handle scale and
  animation but cost more effort. **If the signature moment in §5.1 is wanted, that argues for WebGL.** Decide when the
  frontend starts (v0.5), but decide it knowing the target rather than by default.
- **API payload shape.** `04` §3.5 already requires returning a *subgraph* around the queried node rather than the whole
  graph. Cinematic traversal wants that subgraph to include **the path the agent walked, in order** — cheap to include
  from the start, annoying to add once the response schema has consumers.

Everything else — palette, layout, motion system, typography — is fill-in-later by construction.

## 7. Process: see it to pick it

The established pattern, and it applies directly: **3–6 throwaway preview files per design decision**, rendered and
compared side by side rather than argued about in prose. That process produced the Patchwork Phase 4.5 work and the
launch carousel; the tooling is already on this machine (headless Chromium is installed and documented).

Sequence, so this doesn't turn into a design project that eats the build:

- **Now:** nothing. Direction is recorded; no design work before the walking skeleton exists.
- **At v0.5 (frontend):** engine decision, then previews for layout, then palette, then motion.
- **Keep to the hard rule from `04` §8.5:** the *frontend* loads instantly even when the *agent* takes twenty seconds to
  think. Motion must never be in the critical path of first paint. Respect `prefers-reduced-motion` — animation that
  can't be turned off is a defect, not a flourish.

## 8. Bottom line

- The instinct is right and this is the correct project for it: here the visualization **is** the product.
- Aim at **explorable explanations and editorial data-viz**, not marketing-agency motion. Harder target, better fit,
  and far more persuasive to the audience that matters.
- **"Everyone's doing it" is false** — the portfolio baseline in this space is a Streamlit default. Doing this well is
  differentiating.
- **Do it because the graph deserves it, not to fix the application funnel** — the record says rejections happen before
  anyone clicks a link.
- Design here is **a systems problem**: tokens, perceptual rules, a validated palette, motion with a job.
- Architecturally it costs almost nothing to want this. Two decisions to make knowingly (rendering engine, path-in-payload),
  and everything else stays a two-way door.
