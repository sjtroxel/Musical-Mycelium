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

``plan.py`` arrived at phase 3 step 3: an explicit traversal plan the agent emits before it walks. Note
what it is not — nothing in ``loop.py`` reads the plan back. Execution is still the model driving the
registry turn by turn, and the plan is inspectable without being an authority. A plan that decided
control flow would be a second, ungated way for the model to steer the answer.

Note the two claim types. ``ClaimProposal`` is what the model may emit and it carries **no sources**;
``Claim`` carries ``source_ids`` and can only be produced by ``gate()``, which reads them off the artifact
edge. A model that cannot name a citation cannot fabricate one, and that is enforced by the types rather
than by review.

The same shape appears again one level up: ``loop.synthesize()`` takes only an ``ApprovedClaimSet``, so
prose generation has no parameter through which the query, the graph, or a rejected claim could reach it.

``BedrockLLM`` was **first executed against the live API on 2026-08-11**, after a quota block that ran
from 07-30. Single-turn, streaming and tool-use all parse correctly. Everything in this package still
runs against ``ScriptedLLM`` by default, because free offline tests are the right default, not because
Bedrock is unavailable — and swapping the implementation changes nothing above the seam, which is the
whole point of invariant 7.

**The loop itself has still never run end to end against a real model.** The provider underneath it is
verified; the multi-turn behaviour on top of it is not. Anything that depends on how a real model
*behaves* — tool selection, injection resistance — remains unproven and is listed as open in the phase
3 IMPLEMENTATION doc rather than quietly implied to be covered.
"""
