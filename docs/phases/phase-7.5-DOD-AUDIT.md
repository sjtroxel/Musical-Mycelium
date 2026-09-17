# Phase 7.5 — definition-of-done audit

Step 6. **A pass, not a checklist**, for the reason phase 7 proved: every DoD item there had a test, and
the test for item 9 passed the entire time the item was broken, because it tested a component in
isolation and the defect was in a caller that did not exist when the test was written.

Run 2026-09-16 and 2026-09-17 against artifact **v0.10.0**, the pin phase 7.6 cut, not v0.7.1.

**All seven pass. Phase closed 2026-09-17.**

| # | item | verdict |
|---|---|---|
| 1 | report has slices, judge-human agreement, noise floor | **PASS** |
| 2 | trend reads stored runs, does not join across cohorts | **PASS** |
| 3 | the writeup exists and he can walk through it cold | **PASS**, on his report |
| 4 | `terraform destroy` removes everything, `apply` rebuilds it | **PASS**, carried evidence |
| 5 | fixed monthly infrastructure cost still ~$0, against a real bill | **PASS** |
| 6 | nothing overstates what "grounded" means | **PASS** |
| 7 | the report shows what did not work | **PASS** |

## 1 — slices, judge-human agreement, noise floor — PASS

Verified against the **live page**, not the generator: `https://musical-mycelium.vercel.app/report/index.html`,
fetched 2026-09-16. "noise floor" appears 4 times, "kappa" twice, "slice" 5 times. Checked on the served
page rather than the committed HTML because the deployed artifact and the repo have disagreed before
(phase 7.7, the report generator never compared `dataset_version` to the sealed manifest).

## 2 — the trend reads stored runs, and does not join — PASS

The page charts 12 runs per metric from stored results, and carries a **"Shown, and not joined"** section
listing every cohort excluded from a line with the reason in a `why it is not on a line` column: too few
runs for a spread, a subset of the cases, or a run that did not finish. The not-joining is the half that
is easy to claim and hard to show, and it is shown.

## 3 — the writeup exists, and he can walk through it cold — PASS

**The writeup exists**: `~/job-search-headquarters/portfolio/musical-mycelium-launch/POST.md`, draft 2,
2,512 characters, published to LinkedIn 2026-09-17 morning with a seven-tile carousel.

**The cold walk-through: he reports it done, 2026-09-17, shortly after publishing.** Recorded as his
report rather than as something this audit observed, which is the honest distinction — no one else can
witness it, and the item is his to close.

This is the articulation rep and the reason the item exists; Claude drafted the prose under the
2026-09-11 permission, which makes the rep more necessary rather than less. The standing note in his
profile is that he builds faster than he can cold-recall, and that review-time understanding is what
hiring turns on. **If a question about this post ever catches him flat in an interview, the answer is
another rep, not a rewrite** — the post is accurate, and `CLAIM-AUDIT.md` is the map back to the
evidence for every sentence in it.

## 4 — destroy / apply round-trip — PASS, on carried evidence

A real `terraform destroy` and re-apply ran **2026-09-10**, 33 resources, and the site came back. Step 6's
own note says step 3's round-trip evidence carries over to this pin while the deployed build does not.
**Recorded honestly: this was run at phase 7.5 step 3, not re-run for this audit.** Three deploys have
applied cleanly since, most recently run `35102925770` on 2026-09-16.

## 5 — fixed monthly cost still ~$0, verified against a real bill — PASS

Read from the console 2026-09-17, account `178870257607`, **not from the estimate**.

- **August 2026: issued, closed, grand total USD 0.00.** Invoices `2803790005` and `2802961061`.
- **September 2026 month-to-date: estimated grand total USD 0.00**, nine active services.
- **Every standing service line is $0.00** — S3, CloudFront, ECR, CloudWatch, Data Transfer, KMS. Those
  are the lines that bill without a visitor, and they are the claim. Lambda and Bedrock are pure usage.
- **No domain was registered**, so DoD 5's conditional does not fire and the sentence is unchanged.
- Structural reason it is zero and not luck: no managed database, so no VPC and no NAT gateway.

**Recorded beside the pass, because it is true and moving:** gross usage before credits is climbing.
Month-to-date **$12.89 against $3.77** for the same period in August; forecast **$17.17 against $6.28**
for August's total. **Two budgets are over threshold and four budget alerts have fired.** The invoice is
$0.00 only while credits absorb that. The forecast also predates the 2026-09-17 launch post, so it does
not include whatever traffic the post brings, at roughly a cent a question.

**Fixed cost is $0 and that is what this item asks.** The usage trend is not a DoD 5 failure and is not
filed as one.

## 6 — nothing overstates what "grounded" means — PASS

Both halves.

**The repo**: the three places that define the term all define it correctly — `docs/eval-suite-explained.md:68`
("It does **not** mean the edge is true"), `web/src/App.tsx:199` ("Grounded means traceable, not true"),
and the published evaluation page ("The gates below prove the first. Nothing on this page claims the
second"). A search for constructions that would overstate it returned nothing.

**The copy audit**, which this phase owns: every use of *correct*, *true*, *accurate*, *verified*,
*proven* and *guarantee* in the post and in all eight carousel captions was read in context. Four hits,
all clean. Full table in `job-search-headquarters/portfolio/musical-mycelium-launch/CLAIM-AUDIT.md`.
Nothing claims the agent gives correct, accurate or true music history.

## 7 — the report shows what did not work — PASS

On the live page: `gold_v0_1_020` appears 5 times, the **Joy Orbison / Roy Orbison** failure is named,
and there is an explicit "did not work" section. Every judged run is listed rather than only the newest,
including the two that came in under the `refusal_accuracy` bound on 2026-09-13 and 2026-09-14.

## The close

**Phase 7.5 is CLOSED, 2026-09-17**, all seven items with a verdict and evidence. Recorded in
`ROADMAP.md` and `docs/KNOWN-GAPS.md` the same day.

**What the phase shipped:** the published eval report with slices, judge-human agreement and the measured
noise floor; the trend view over stored runs; the Terraform round-trip; the verified bill; the copy audit;
and the writeup, which became a LinkedIn launch post with a seven-tile carousel, published 2026-09-17.

**Carried forward, not closed by this phase:** `adv_018` re-authoring is still owed. Gross AWS usage is
tripling month over month and two budgets are over threshold; the invoice is $0.00 only while credits
last (item 5).
