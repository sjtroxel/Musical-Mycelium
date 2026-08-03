"""The hand-built Bedrock Converse tool loop.

Deliberately hand-built rather than using managed Bedrock Agents or AgentCore: those hide exactly the
engineering this project exists to demonstrate, and they are more expensive and less legible.

Contract:

- **Claims first, prose second.** The loop emits structured ``Claim`` objects; a deterministic gate
  approves them; prose is generated *from the approved claim set only*. Prose generation must not be able
  to see anything else — that is the leak the 7/27 review caught. See
  ``.claude/rules/grounding-and-claims.md``.
- ``Claim`` carries ``subject_id``, ``predicate``, ``object_id``, ``source_ids``, ``span``.
- Tools satisfy an explicit protocol and return results carrying their ``sources``. Adding a tool must
  never require editing the loop.
- Tool calls hit the local pinned artifact through ``graph``. Never Wikidata live.
- The model is reached through a provider seam (a ``build_llm``-style factory), so model and provider are
  configuration, not structure.
- Refusal is correct behavior. An unsourced edge is refused, not narrated. Contested is a state, not an
  error.

**Built as of 2026-08-02 (phase 1, steps 5-6).** ``claims.py`` is the claim model and the deterministic
gate, built **before** the loop on purpose so the gate is not shaped to fit it. ``tools.py`` is the tool
contract and the two v0.1 tools. ``llm.py`` is the provider seam. ``loop.py`` is the loop itself, as a
generator of events.

Note the two claim types. ``ClaimProposal`` is what the model may emit and it carries **no sources**;
``Claim`` carries ``source_ids`` and can only be produced by ``gate()``, which reads them off the artifact
edge. A model that cannot name a citation cannot fabricate one, and that is enforced by the types rather
than by review.

The same shape appears again one level up: ``loop.synthesize()`` takes only an ``ApprovedClaimSet``, so
prose generation has no parameter through which the query, the graph, or a rejected claim could reach it.

``BedrockLLM`` is written but **has never been executed** — every Bedrock daily-token quota on the
account reads 0. Everything here runs today against ``ScriptedLLM``; the smoke call swaps the
implementation and nothing above the seam changes.
"""
