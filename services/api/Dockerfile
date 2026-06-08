# Verity comparison API — container image (multi-stage).
#
# The Next.js frontend deploys to Vercel; the engine API is a heavy Python+Rust
# stack (scipy / scikit-image / scikit-learn + the maturin-built verity_x3p
# binding) that exceeds serverless limits, so it runs as a container on any host
# (Railway, Fly.io, Render, Cloud Run, …). Build from the REPO ROOT so the API's
# path dependencies (../engine, ../../bindings/python, crates/) are in context:
#
#   docker build -f services/api/Dockerfile -t verity-api .
#   docker run -p 8000:8000 -e VERITY_CORS_ORIGINS="https://<your-vercel-app>" verity-api
#
# Stage 1 compiles verity_x3p (Rust) and builds the venv; stage 2 ships only the
# venv + app source on a clean slim base — no Rust toolchain, no compilers.

# ---- builder: Rust + gcc + uv; compiles verity_x3p into the venv ----
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# uv (package manager) + Rust toolchain (to build the verity_x3p binding via maturin)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates
COPY bindings ./bindings
COPY services/engine ./services/engine
COPY services/api ./services/api

WORKDIR /app/services/api
# Builds the verity_x3p wheel (.so -> .venv site-packages) + installs the
# scientific stack. --no-dev excludes test/lint deps; the heavy `learn` (torch)
# extra is not a base dependency, so it stays out.
RUN uv sync --no-dev --compile-bytecode

# ---- runtime: clean slim base, venv only, no toolchain ----
FROM python:3.12-slim AS runtime

WORKDIR /app/services/api
# The venv (incl. the compiled verity_x3p .so) lives in services/api/.venv; the
# editable `verity` engine resolves to services/engine. Copy just those two —
# NOT the Rust target/, crates/, or bindings/ (build-only inputs). Same base
# image as the builder, so the venv's python symlink + the extension ABI match.
COPY --from=builder /app/services/engine /app/services/engine
COPY --from=builder /app/services/api /app/services/api

# Put the venv on PATH so uvicorn runs without uv or an activate step.
# NB: CORS defaults to localhost only (see main.py); set VERITY_CORS_ORIGINS to the
# real front-end origin(s) at deploy time. Do NOT bake "*" into the image.
ENV PATH="/app/services/api/.venv/bin:${PATH}" \
    PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uvicorn verity_api.main:app --host 0.0.0.0 --port ${PORT}"]
