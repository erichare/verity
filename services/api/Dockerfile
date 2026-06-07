# Verity comparison API — container image.
#
# The Next.js frontend deploys to Vercel; the engine API is a heavy Python+Rust
# stack (scipy / scikit-image / scikit-learn + the maturin-built verity_x3p
# binding) that exceeds serverless limits, so it runs as a container on any host
# (Fly.io, Render, Railway, Cloud Run, …). Build from the REPO ROOT so the API's
# path dependencies (../engine, ../../bindings/python, crates/) are in context:
#
#   docker build -f services/api/Dockerfile -t verity-api .
#   docker run -p 8000:8000 -e VERITY_CORS_ORIGINS="https://<your-vercel-app>" verity-api

FROM python:3.12-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# uv (package manager) + Rust toolchain (to build the verity_x3p binding via maturin)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/
RUN curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y --profile minimal
ENV PATH="/root/.cargo/bin:${PATH}"

WORKDIR /app
# Only the parts the API needs (keeps the context lean with .dockerignore).
COPY Cargo.toml Cargo.lock ./
COPY crates ./crates
COPY bindings ./bindings
COPY services/engine ./services/engine
COPY services/api ./services/api

WORKDIR /app/services/api
RUN uv sync --no-dev

# Allow the deployed frontend's origin (set to your Vercel URL; "*" for an open demo).
ENV VERITY_CORS_ORIGINS="*" \
    PORT=8000
EXPOSE 8000
CMD ["sh", "-c", "uv run uvicorn verity_api.main:app --host 0.0.0.0 --port ${PORT}"]
