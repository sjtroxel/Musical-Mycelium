# Start here — orientation for a cold session

Written 2026-07-29 in the `job-search-headquarters` chat that named this project, for the next Claude Code
session opened inside this repo. Delete or rewrite once the build is underway.

## What this is

**Musical Mycelium** — a goal-directed research agent on AWS Lambda + Bedrock that traverses a
provenance-backed graph of musical influence and cites every claim. Named 2026-07-29 after a long
naming session; concept locked 2026-07-24.

**This repo shares the same Claude memory store as `job-search-headquarters` and `patchwork-assurance`**
via a symlink, so recall from those sessions is available here and anything saved here writes back to the
same canonical store. Nothing was copied or forked. Read `MEMORY.md` first.

## Reading order

1. `docs/planning/00-DESIGN-BRIEF.md` — the concept and why it exists
2. `docs/planning/09-PRIORITIES-AND-OPEN-DECISIONS.md` — the forward-looking half; §7 is the sequence
3. `docs/planning/08-REVIEW-VERDICT-AND-CATCHES.md` — the independent review and its two substantive catches
4. Everything else as needed: `01` data sources, `02` architecture, `03` cost, `04` risk, `05` evolution,
   `06` design, `07` evals

`09` is the last numbered planning doc. **Planning is closed** — do not propose more planning docs
(`08` §6 says why). The naming worksheet is kept for the record only.

## The sequence from here (`09` §7)

1. ~~Product conversation~~ — partially settled during naming; the first screen question is still open
2. ~~Naming~~ — done
3. **Repo bootstrap** — this file's doing; remaining items listed below
4. **IMPLEMENTATION doc** — `09` §6 gathers every accumulated assignment from the whole series. This is
   the next real deliverable. His standing rule: the phase IMPLEMENTATION doc is written and approved
   **before** any code.
5. **AWS signup** — `04` §9 items 1–3
6. **Walking skeleton**

## Bootstrap items still outstanding

- [ ] Create the GitHub repo and add the remote (planned for the afternoon of 2026-07-29)
- [ ] First commit (he runs it; never commit or push on his behalf — `.claude/settings.json` denies it)
- [ ] Single-command dev runner, from the first week — retrofitting is always worse
- [ ] `ROADMAP.md` and `SPEC.md` once the IMPLEMENTATION doc exists

## Things that will bite if you don't know them

- **AWS signup: use the PAID plan, not the Free Plan.** The Free Plan auto-closes the account at 6 months
  or credit exhaustion. This is portfolio infra that has to stay live through a job search. `04` §1.
- **One successful Bedrock `converse` call is task one.** Anthropic models on Bedrock need a
  First-Time-Use form and Marketplace permissions. If that is blocked, everything waits.
- **Never query Wikidata live from the agent.** WDQS is materially degraded; all tool calls hit the
  pre-built local artifact. `04` §4.
- **Streaming is a product decision, not a workaround.** API Gateway REST times out at 29s and a
  multi-step tool loop will exceed it. Lambda Function URL + response streaming is the recommendation,
  and retrofitting it later is real rework. `04` §3.1.
- **Validate the graph semantics before ingesting.** Wikidata P279 is `subclass of`, which is taxonomic,
  not historical. Hand-check 20 edges first. `04` §4.4.
- **Cost guardrails before the first `terraform apply`** — Budgets at $5/$10/$20, explicit CloudWatch log
  retention (the default is never-expire), everything in Terraform so `terraform destroy` is a real
  off-switch. `03` §4.
- **Identity work is first-class here** (the name is deliberately oblique so the tagline carries meaning),
  **but** the logo/banner session comes *after* the first successful Bedrock call, not before. The
  graph-visualization work stays deferred to v0.5 per `06`.

## Priority stack (`09` §1)

1. The job search. The build never displaces an application he would otherwise have sent.
2. This project's job within that search: a deployed URL plus real eval numbers, to close the AWS gap.
3. The project as a project — density, the SPA, the cinematic traversal.

Resume-ready is roughly **v0.3–v0.4**, not v1.0.
