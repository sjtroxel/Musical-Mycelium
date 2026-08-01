# Status review — 2026-08-01 (Fable)

> Independent review of the whole project, requested during the Bedrock quota wait. Last Fable review was
> the pre-build pass that produced `planning/08` and `09`. This one covers everything since: scaffolding,
> the scope docs, the P279/P737 validation, the streaming spike, and the phase-1 IMPLEMENTATION doc.
> Findings are numbered; recommendations are marked. Decisions stay with sjtroxel.

## 1. Verdict

The project is in better shape than the mood around it. Since the planning series closed on 2026-07-27,
this repo has: a scaffolded, CI-green codebase with enforced package boundaries; scope docs for all seven
phases; the central data assumption tested and falsified *before* a line of ingestion was written; the
riskiest piece of plumbing (Python streaming on Lambda) verified by a real deploy and torn down cleanly;
and an IMPLEMENTATION doc for phase 1 that is specific, honest about uncertainty, and consistent with all
nine invariants.

Two of those deserve to be said plainly, because they are the planning discipline paying off rather than
luck:

- **The P279 falsification is the system working.** The risk register said validate the predicate before
  coding ingestion; the validation ran first and the assumption died on paper instead of in a shipped
  corpus. Most projects find this out after launch, from a user.
- **The streaming spike killed the right risk at the right time.** Invariant 9 is a one-way door, Python
  Lambda streaming was unverified, and it is now verified with numbers (TTFB 0.214s vs 10.22s), a known
  mandatory build flag, and a clean destroy.

The main finding of this review is not a flaw in the work. It is that **the project is far less blocked
than the current framing assumes** (finding 2).

## 2. Verified current state

Checked against the repo on 2026-08-01, not recalled from memory:

| Item | State |
|---|---|
| `make check` | Green: format, lint, mypy, 7 tests, root cap 15/18 |
| Credential scan | Clean. No credential-shaped files tracked; `.gitignore` covers state and secrets |
| Working tree | One untracked file: `docs/phases/phase-1-walking-skeleton-IMPLEMENTATION.md` |
| Source tree | Package skeletons only, per "structure now, content when its subject exists" |
| `infra/` | README only. Correct: the spike was scratchpad-quality and was destroyed |
| Scope docs | All seven phases, plus phase-0 as-built and the phase-1 IMPLEMENTATION doc |
| AWS | Account live, paid plan, us-east-1, $20 budget armed, root MFA on. Bedrock daily-token quotas 0.0 account-wide; case `178545883500013` escalated to the Bedrock service team |

## 3. The blocker, stated precisely

What the 8/1 diagnosis established: model **access is granted** (`ThrottlingException`, not
`AccessDeniedException`); the zero is one account-level tokens-per-day provisioning gate across every
vendor; the case was escalated past first-line support within five hours of filing, which is the opposite
of the auto-denial path the quota docs warn about. Zero business days have elapsed — the case was filed
Thursday evening and today is Saturday. The measured base rate from re:Post is 2–5 business days once
assigned, with a worst observed thread around 15. Silence through a weekend is the base rate, not a signal.

**The contingency already exists in the architecture.** Invariant 7 (the `build_llm` provider seam) was
adopted precisely so the model and provider are config. If the wait stretches past useful patience, the
loop can be *developed* against any provider behind the seam and swapped to `BedrockLLM` the day the quota
clears — the deployed product stays Lambda + Bedrock, the resume line stays true, and the only thing the
worst case costs is calendar time on the final deploy step. This is worth writing down because it bounds
the damage of every AWS outcome, including the bad ones.

Standing rules unchanged: do not re-file, do not open a second case, check the Service Quotas page before
assuming the block still holds (it can self-clear without a case reply).

## 4. Findings

### 4.1 The phase-1 IMPLEMENTATION doc contradicts itself about what the gate blocks — resolve it in favor of building

The doc's header says "The build is gated ... everything waits," quoting the scope doc's step-zero rule.
Its own §12 then says, correctly: **"Steps 2 through 8 need no AWS."**

Both cannot govern. The "do not build around it" rule was written on 2026-07-29, when the risk was an AWS
account that might never materialize — building a castle with no land. That risk is gone: the account
exists, streaming is verified by a real deploy, `terraform destroy` is proven, and access is granted. What
remains is a quota wait with an escalated case. The rule outlived the risk it guarded.

**Recommendation:** amend the header to say what §12 already knows: the `converse` smoke call gates all
AWS *spend and deploy* (steps 1 and 9); steps 2–8 — edge hand-verification, gold cases, ingestion,
`GraphStore`, `Claim` + gate + metric, tools, loop against a stub LLM, local SSE — proceed now. Roughly
80% of phase 1 is buildable this weekend without touching AWS.

### 4.2 The doc's own owed amendments are unapplied, and the doc is uncommitted

§2 of the IMPLEMENTATION doc lists four scope-doc/graph-semantics amendments "owed before this doc is
approved." All four targets still carry the old text (verified: `phase-1-walking-skeleton.md` lines 45,
55, 59; `graph-semantics.md` line 186). The doc itself is untracked.

**Recommendation:** approve the doc, apply the four amendments, commit both together. Until then the repo
asserts two different phase-1 plans.

### 4.3 Scratchpad artifacts were one reboot from deletion — backed up during this review

`docs/graph-semantics.md` §7 says the validation scripts are "not yet in the repo." They lived only in a
session scratchpad under `/tmp`, which WSL2 clears on shutdown. So did three things the docs do not
mention: the full prose-check output (`prosecheck351.json` — the evidence behind the 158 number), the
population pulls, and **the entire streaming spike** (`Dockerfile`, `main.tf`, `app.py`, `RUN.md`) — the
working reference implementation for phase 1's self-described fiddliest part.

**Done during this review:** everything copied to `~/mm-validation-scripts-backup-2026-07-31/` (25 files).

**Recommendation:** the validation scripts and the prose-check JSON belong in the repo — they are the
reproducibility story `graph-semantics.md` §7 promises and the seed of the phase-2 ingestion pipeline.
Where they land is a phase-2 IMPLEMENTATION decision; until then the backup suffices. The spike files are
reference material for phase 1's Docker/Terraform work; consult, do not commit (they are spike-quality and
contain a stale tfstate).

### 4.4 The canonical queries are drifting further from the corpus while they wait for an edit pass

`SPEC.md` §2 has been DRAFT since 2026-07-29. Two items the IMPLEMENTATION doc already flagged: chip 2
("What did bebop grow out of?") is unanswerable — `bebop <- swing` is not in the corpus; and the note
calling P737 "the artist axis" is wrong since the validation showed it runs genre-to-genre. A third worth
adding: chip 6 ("How is delta blues connected to hip hop?") is a cross-component path query in a graph
with 46 components — whether it is answerable is currently unknown, and it is the demo chip.

These chips are load-bearing in four places (first screen, demo script, gold set, eval slices), so drift
here propagates.

**Recommendation:** the edit pass is a decision task, not a build task — ideal recess work. And adopt a
standing rule worth its cheapness: **every chip is validated against the pinned artifact**, either
answerable or deliberately labeled as a coverage-honesty case. That check is deterministic and could
even be a Tier-1 eval row, so a corpus change that silently breaks a demo chip fails CI instead of a demo.

### 4.5 The frozen eval datasets are the highest-value work the blocker cannot touch

`.claude/rules/evals.md`: the three frozen datasets are hand-built **before the agent exists**, or they
are contaminated. The agent does not exist yet, the corpus is now known (158 PROSE edges), and none of
this needs AWS. The phase-1 plan authors only the five v0.1 gold cases; the full gold set (20–30),
adversarial set (15–20, injection included), and held-out 10 all have to exist before the phase-3 loop at
the latest — and every week of waiting is a week in which they could have been finished uncontaminated.

This is also genuinely human work: independent citations are substantially manual (AllMusic, Britannica
et al. 403 automated fetch), which makes it exactly the kind of task a blocked stretch is for.

**Recommendation:** use the recess to author the datasets, starting with the phase-1 five, continuing
into the full gold set. One procedural note: once the held-out 10 are written, seal them — they are read
at milestones only, by no one, including the AI pair.

### 4.6 Phase 6's most important measurement is runnable now, for free

Phase 6's key-decision list says the artist-axis bridging question "should be measured early, because a
positive result reshapes the whole decision." It is measurable today: WDQS queries plus component analysis
over data already pulled, using scripts that already exist. No AWS, no cost. Whether the ~31k artist-level
P737 edges bridge the 46 genre components is the single most important open empirical question for the
thesis ("one connected organism"), and it constrains phase 2's artifact schema before phase 2 is coded.

**Recommendation:** optional recess work, strictly time-boxed (an afternoon, not a rabbit hole), producing
a short appendix to `docs/graph-semantics.md`. Do not let it displace 4.5.

## 5. Opportunities the scope docs leave open

### 5.1 Wikipedia infobox origins as a *source*, not just a validator — the concrete candidate for phase 6's "second source"

Phase 6 resolution 3 ("supplement the corpus") is currently abstract. There is a specific candidate with
unusual leverage: Wikipedia genre infoboxes carry `stylistic_origins` — and the canonical edges the
product's pitch leads with, including `bebop <- swing`, are exactly what that field records. DBpedia
already extracts it in structured form (`dbo:stylisticOrigin`), so the edges are queryable without parsing
wikitext. Licensing is CC BY-SA with displayed attribution — a surface the project has already committed
to building. The 7/31 finding that infoboxes are casually edited cuts against trusting them raw, but the
prose check applies symmetrically: an infobox-derived edge can be required to clear the same PROSE tier
before ingestion, same pipeline, same displayed exclusion rate.

If it survives a feasibility look, this plausibly moves the sourced-influence corpus from ~158 edges to
the low thousands while keeping per-edge provenance — which would change the 46-component answer and the
strength of chip 6. It is a phase-6 decision (or a phase-2 schema consideration at most); the only thing
worth doing early is a one-query count of how many `dbo:stylisticOrigin` edges exist for the 6,328 genres,
so the phase-6 decision is made against a number.

### 5.2 A displayed corpus number from v0.1

Coverage honesty is scoped as a phase-6 deliverable, but the v0.1 manifest already carries node and edge
counts. Emitting them in the `done` SSE event (or a `/health`-style endpoint) costs minutes and starts the
"the corpus size is on the screen, not in a footnote" habit at the walking skeleton. Cheap, optional.

### 5.3 One licensing edge to keep an eye on at v0.1

The v0.1 claims cite Wikidata (CC0), so no attribution surface is owed yet. But the moment any answer
text or citation references Wikipedia (e.g. surfacing the prose-check tier as evidence), CC BY-SA
attribution obligations start — at v0.1, not at the v0.5 SPA. Worth one line in the phase-1 build notes so
it is a decision rather than an accident.

## 6. Recommended order for the recess

1. **Approve and commit the phase-1 IMPLEMENTATION doc**, with the 4.1 header amendment and the four owed
   scope-doc amendments (4.2).
2. **The SPEC §2 edit pass** — his decisions on the seven chips (4.4).
3. **Phase-1 steps 2–8**, in the doc's own order: hand-verify ~15 edges and author the five gold cases,
   then ingestion, store, gate, metric, tools, loop, local SSE (4.1).
4. **Continue the frozen datasets** beyond the five (4.5).
5. Optional, time-boxed: the artist-bridge measurement (4.6) and the `stylisticOrigin` count (5.1).

If the quota clears mid-list, step 1 of the build order (the `converse` smoke call) preempts everything,
per the plan.

## 7. Housekeeping ledger

- Delete the 0-byte `~/bedrock-quotas-2026-08-01.json`.
- Second root MFA device (a passkey on the Windows machine) still owed, next console visit.
- Cost Anomaly Detection still owed; already scoped into phase-1 Terraform.
- Backup at `~/mm-validation-scripts-backup-2026-07-31/` — delete after its contents have real homes.
