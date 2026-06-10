# Verity data-catalog REST API — container image (multi-stage).
#
# Unlike the comparison API (services/api), the catalog API is a *light* Python
# service — sqlmodel/fastapi/uvicorn + psycopg + boto3, no Rust/engine/science
# stack. The X3P codec (verity_x3p) is only used by ingestion (the `ingest`
# extra), which is imported lazily and is NOT needed to run the read-only API, so
# this image needs no Rust toolchain or compilers.
#
# Build from the REPO ROOT so the catalog's path context is available:
#
#   docker build -f services/catalog/Dockerfile -t verity-catalog-api .
#   docker run -p 8001:8001 \
#     -e VERITY_CATALOG_DATABASE_URL="postgresql://…" \
#     -e VERITY_CATALOG_BLOB_STORE_BACKEND=s3 \
#     -e VERITY_CATALOG_BLOB_STORE_BUCKET=verity-scans \
#     -e VERITY_CATALOG_BLOB_STORE_ENDPOINT_URL="https://<acct>.r2.cloudflarestorage.com" \
#     -e VERITY_CATALOG_CORS_ORIGINS="https://verity.codes" \
#     verity-catalog-api
#
# Stage 1 builds the venv with the api + s3 + postgres extras; stage 2 ships only
# the venv + app source on a clean slim base.

# ---- builder: uv; installs the (pure-Python) catalog API venv ----
FROM python:3.12-slim AS builder

RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

WORKDIR /app/services/catalog
# uv.lock pins verity-x3p as a *path* source (../../bindings/python) for the
# optional `ingest` extra. It is never installed here, but uv still resolves its
# metadata — its pyproject.toml carries static name/version, so shipping just
# that one file satisfies uv without any Rust toolchain.
COPY bindings/python/pyproject.toml /app/bindings/python/pyproject.toml
COPY services/catalog/pyproject.toml services/catalog/uv.lock services/catalog/README.md ./
COPY services/catalog/verity_catalog ./verity_catalog

# Install just what the API needs (fastapi/uvicorn/yaml) plus the deploy-path
# backends (boto3 for R2/S3, psycopg for Postgres). --no-dev excludes test/lint
# deps; the heavy `ingest` extra (verity-x3p) is intentionally omitted.
RUN uv sync --no-dev --extra api --extra s3 --extra postgres --compile-bytecode

# ---- runtime: clean slim base, venv only ----
FROM python:3.12-slim AS runtime

WORKDIR /app/services/catalog
COPY --from=builder /app/services/catalog /app/services/catalog

ENV PATH="/app/services/catalog/.venv/bin:${PATH}" \
    VERITY_CATALOG_CORS_ORIGINS="https://verity.codes" \
    PORT=8001
EXPOSE 8001
CMD ["sh", "-c", "uvicorn verity_catalog.api.app:app --host 0.0.0.0 --port ${PORT}"]
