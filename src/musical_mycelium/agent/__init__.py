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

Nothing is implemented yet. One successful Bedrock ``converse`` call is task one of the build.
"""
