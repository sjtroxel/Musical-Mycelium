# Response streaming on Python Lambda — verified 2026-07-31

**Status: invariant 9 holds.** Verified by a throwaway spike deployed to the real account and destroyed
afterward. This doc exists because `CLAUDE.md` invariant 9 is a one-way door and was, until tonight, an
assumption. The phase 1 IMPLEMENTATION doc should absorb everything here.

## The result

| measurement | value |
|---|---|
| time to first byte | **0.214 s** |
| total response time | **10.22 s** |
| ratio | ~48x |

A ten-chunk response, one second apart, through a Lambda Function URL. Buffered responses show TTFB
within milliseconds of total; these differ by a factor of 48. Streaming is real.

Image size **216 MB**.

*(Corrected 2026-08-03 during phase 1 step 8. This line originally read "comfortably inside the 250 MB
unzipped limit that forced invariant 8," which misstates what that limit is. The 250 MB unzipped
ceiling applies to **.zip deployment packages** — it is the reason this project ships a container at
all, not a ceiling on the container. Container images are allowed 10 GB. Image size still matters here,
because it is cold-start latency on a public URL with no provisioned concurrency, but it is a
performance concern rather than a correctness one and should not be cited as a hard limit. The phase-1
image measures ~256 MB on disk, ~67 MB compressed.)*

## Python has no native response streaming

Verbatim from `configuration-response-streaming.html`:

> "Lambda supports response streaming on Node.js managed runtimes. For other languages, **including
> Python**, you can use a custom runtime with a custom Runtime API integration to stream responses or use
> the **Lambda Web Adapter**."

The Lambda Web Adapter path is what was verified. Three things are required and all three matter:

```dockerfile
FROM public.ecr.aws/awsguru/aws-lambda-adapter:1.0.1 AS adapter
FROM python:3.13-slim
COPY --from=adapter /lambda-adapter /opt/extensions/lambda-adapter
ENV AWS_LWA_INVOKE_MODE=response_stream   # default is "buffered"
```

plus the Function URL at `invoke_mode = "RESPONSE_STREAM"` (Terraform `aws_lambda_function_url`).

**`AWS_LWA_INVOKE_MODE` defaulting to `buffered` is the trap.** Omit it and everything deploys, every
request succeeds, and streaming silently does not happen.

## The failure that no documentation predicted

**Docker 29's BuildKit attaches provenance and SBOM attestations by default**, which wraps the image in a
manifest list. Lambda rejects it:

```
InvalidParameterValueException: The image manifest, config or layer media type
for the source image ... is not supported.
```

The tell is in the build output — `exporting attestation manifest` and `exporting manifest list`. The fix:

```
docker buildx build --platform linux/amd64 --provenance=false --sbom=false -t <tag> --load .
```

A correct build exports `manifest` and `config` only, with no manifest list. **This is mandatory for every
Lambda container image in this project**, and it is the single strongest argument for having run the spike
at all: it appears in none of the AWS documentation consulted, and it would otherwise have surfaced during
phase 1 tangled up with application code.

## Consequences for the build

- **The `api/` package is a real web framework** (FastAPI under uvicorn behind LWA), not a bare Lambda
  handler. Still thin and still owns no logic per `SPEC.md`, but it is a server.
- **The no-VPC decision is now load-bearing for two independent reasons.** It was made on cost grounds
  (no NAT gateway at ~$32/mo). It is also *required*: AWS docs state Lambda function URLs do not support
  response streaming inside a VPC. Reversing the VPC decision would break invariant 9, not just the budget.
- **Ingestion order is two-stage.** A Lambda pointing at an image URI cannot be created before that image
  exists, so ECR is applied first, the image is pushed, then everything else. Phase 1's Terraform needs
  this shape or a `null_resource` build step.
- **Streaming makes the Lambda timeout a cost control.** Per AWS: *"streamed responses are not interrupted
  or stopped when the invoking client connection is broken. Customers are billed for the full function
  duration."* A visitor who opens the public URL, triggers a multi-step agent loop, and closes the tab
  bills the full timeout. On a $20 budget with a recruiter-facing URL this belongs in
  `.claude/rules/aws-and-cost.md`, not just in a Terraform file.

## An unrelated finding worth keeping

The identical image reported `done in 3.33s` for a 4.8-second run locally under WSL2, and reported
correctly (`done in 10.03s` for a 10.2-second run) on Lambda. Best explanation is WSL2 wall-clock resync
mid-request — `time.time()` is wall clock while `asyncio.sleep` runs on the event loop's monotonic clock.
Not verified, but the operational rule is clear: **use `time.monotonic()` for anything measured, and do
not trust local wall-clock latency numbers on this machine.** This matters because latency and cost are
planned eval metrics.

## Reproducing

The spike lived in a session scratchpad (`app.py`, `Dockerfile`, `main.tf`, `RUN.md`) with local Terraform
state, deliberately outside the repo so it would not pre-empt phase 1's Terraform layout or the
state-bootstrap decision, both still open. It was destroyed after measurement. Cost was effectively zero:
Lambda free tier, ECR inside the 500 MB allowance, CloudWatch logs pinned to 1-day retention.
