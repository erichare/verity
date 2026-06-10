#!/usr/bin/env bash
# Deploy the catalog/data API to Railway (service: verity-data).
#
# Why staging is required: `railway up` reads railway.json from the UPLOAD ROOT.
# The repo root's railway.json pins the *comparison* API's Dockerfile, so a naive
# root upload builds the wrong image for this service (and the per-service
# RAILWAY_DOCKERFILE_PATH variable does NOT override config-as-code). This script
# stages exactly the catalog build context + the catalog railway.json and deploys
# that directory.
#
#   ./services/catalog/deploy-railway.sh
#
# One-time setup (already done for verity-data): `railway add --service verity-data`
# with VERITY_CATALOG_DATABASE_URL / VERITY_TRUST_PROXY_HEADERS=1 /
# VERITY_CATALOG_CORS_ORIGINS / PORT=8001, and `railway link` to the verity-api
# project inside the stage dir on first run.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
STAGE="${TMPDIR:-/tmp}/verity-data-stage"
SERVICE="${RAILWAY_SERVICE:-verity-data}"

rm -rf "$STAGE"
mkdir -p "$STAGE/services/catalog" "$STAGE/bindings/python"
cp -R "$ROOT/services/catalog/pyproject.toml" "$ROOT/services/catalog/uv.lock" \
      "$ROOT/services/catalog/README.md" "$ROOT/services/catalog/Dockerfile" \
      "$ROOT/services/catalog/verity_catalog" "$STAGE/services/catalog/"
# Static metadata only — see the Dockerfile note about the verity-x3p path source.
cp "$ROOT/bindings/python/pyproject.toml" "$STAGE/bindings/python/"
cp "$ROOT/services/catalog/railway.json" "$STAGE/railway.json"
find "$STAGE" -name "__pycache__" -type d -exec rm -rf {} + 2>/dev/null || true

cd "$STAGE"
# The stage dir is recreated every run, so it is never linked — link explicitly,
# otherwise `railway up` silently creates a brand-new project.
railway link --project "${RAILWAY_PROJECT_ID:-313a0053-2b61-4b20-95c6-4f0a17feca7e}" \
  --environment production --service "$SERVICE"
exec railway up --service "$SERVICE" --ci
