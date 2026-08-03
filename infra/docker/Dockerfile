# The Lambda container image — CLAUDE.md invariant 8.
#
# Build from the REPO ROOT, not from this directory:
#
#   docker buildx build --platform linux/amd64 --provenance=false --sbom=false \
#     -f infra/docker/Dockerfile -t musical-mycelium:local --load .
#
# `make image` wraps that so the flags are never retyped. Read the flags before changing them; two of
# them are load-bearing and were established by a real deploy (docs/streaming-verification.md).
#
#   --provenance=false --sbom=false   MANDATORY. Docker 29's BuildKit attaches provenance and SBOM
#                                     attestations by default, which wraps the image in a manifest
#                                     list. Lambda rejects it outright:
#                                       InvalidParameterValueException: The image manifest, config or
#                                       layer media type for the source image ... is not supported.
#                                     The tell is `exporting attestation manifest` in the build log.
#                                     This appears in no AWS documentation.
#   --platform linux/amd64            The function is x86_64. A silent arm64 build on an Apple host
#                                     deploys and then fails at runtime.
#
# The build context is the repo root, but the ignore file lives next to this Dockerfile as
# `Dockerfile.dockerignore` — BuildKit looks there first and only falls back to a context-root
# `.dockerignore`. That is deliberate: it keeps the repo root inside its CI-enforced cap of 18.

# --- the Lambda Web Adapter -------------------------------------------------------------------
# Python on Lambda has NO native response streaming. Verbatim from the AWS docs: "Lambda supports
# response streaming on Node.js managed runtimes. For other languages, including Python, you can use a
# custom runtime ... or use the Lambda Web Adapter." LWA is the path this project verified on 2026-07-31
# (TTFB 0.214s vs 10.22s total), and invariant 9 rests on it.
FROM public.ecr.aws/awsguru/aws-lambda-adapter:1.0.1 AS adapter

# --- dependency build -------------------------------------------------------------------------
# uv resolves from the committed uv.lock so the image gets byte-identical dependencies to local dev
# and to CI. Anything else reintroduces "works on my machine" at the one layer where it is hardest
# to debug.
#
# The uv binary is copied in from its own pinned image rather than using astral's combined
# uv+python tags. Two reasons: those combined tags are not published for every uv version (0.12.0 has
# no python3.13-bookworm-slim variant), and this way the interpreter comes from the same
# python:3.13-slim image the runtime stage uses, so builder and runtime cannot drift apart.
FROM python:3.13-slim AS builder
COPY --from=ghcr.io/astral-sh/uv:0.12.0 /uv /usr/local/bin/uv

# UV_PROJECT_ENVIRONMENT builds the virtualenv at the path it will occupy in the RUNTIME stage, not
# at ./.venv. That is not tidiness: console scripts like `uvicorn` are generated with an absolute
# shebang pointing at the interpreter that created them, so a venv built at /build/.venv and copied
# to /opt/venv produces `exec /opt/venv/bin/uvicorn: no such file or directory` at container start —
# after a build that succeeded and an image that looked correct. Build it where it will live.
ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never \
    UV_PROJECT_ENVIRONMENT=/opt/venv

WORKDIR /build

# Dependencies first, in their own layer, so editing application code does not re-resolve or
# re-download anything. --no-install-project is what makes that split possible.
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-dev --no-install-project --no-editable

# Then the project itself. --no-editable installs a real copy into site-packages rather than a link
# back to /build, so the source tree does not have to survive into the runtime stage. hatchling ships
# everything under src/musical_mycelium, which is why the pinned graph artifact travels with the
# package and needs no COPY step, no S3 fetch, and no IAM permission on the cold path.
COPY README.md ./
COPY src ./src
RUN uv sync --locked --no-dev --no-editable

# --- runtime ----------------------------------------------------------------------------------
FROM python:3.13-slim

# A precision worth keeping straight: the 250MB unzipped limit behind invariant 8 is the ceiling on
# .zip deployment packages, and it is the reason this project ships a container at all. Container
# images get 10GB, so it is not a ceiling on this file. Size still matters, because image size is
# cold-start latency and this is a public URL with no provisioned concurrency to hide behind — so the
# runtime stage carries the virtualenv and nothing else: no uv, no build tooling, no source tree.
# Measured 2026-08-03: ~256MB on disk, ~67MB compressed, ~53MB of that the virtualenv.
COPY --from=adapter /lambda-adapter /opt/extensions/lambda-adapter
COPY --from=builder /opt/venv /opt/venv

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

# AWS_LWA_INVOKE_MODE defaults to "buffered". THIS IS THE TRAP: omit it and the image builds, the
# function deploys, every request returns 200, and streaming silently does not happen. It must be set
# here AND the Function URL must be created with invoke_mode = "RESPONSE_STREAM" — both, or neither
# works. See infra/terraform/main/lambda.tf.
ENV AWS_LWA_INVOKE_MODE=response_stream \
    AWS_LWA_PORT=8080 \
    AWS_LWA_READINESS_CHECK_PATH=/health \
    PORT=8080

# bedrock is the deployed default; `make dev` overrides it to `local` so development needs no AWS.
# The model id is configuration rather than a constant because which model, and US vs Global
# inference profile, cannot be settled until the first live converse call (IMPLEMENTATION 10).
ENV MYCELIUM_LLM_PROVIDER=bedrock

EXPOSE 8080

# uvicorn directly, not `uv run`: uv is not in this stage, and a process manager between LWA and the
# server is one more thing that can buffer a response stream.
CMD ["uvicorn", "musical_mycelium.api.app:app", "--host", "0.0.0.0", "--port", "8080"]
