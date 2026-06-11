# Deploying Verity

The platform is three pieces:

- **Web** (`services/web`) — a Next.js app → **Vercel**.
- **API** (`services/api`) — the engine over HTTP. It's a heavy Python + Rust
  stack (scipy / scikit-image / scikit-learn + the maturin `verity_x3p` binding),
  too large for serverless, so it runs as a **container** on any host (Railway,
  Fly.io, Render, Google Cloud Run, a VM…).
- **Data API** (`services/catalog`) — the catalog + open-benchmark REST API, a
  light pure-Python container (FastAPI over Postgres/Supabase + S3/R2) →
  **Railway** (service `verity-data`). See section 3.

The web app calls the API at `NEXT_PUBLIC_API_URL` and the data API at
`NEXT_PUBLIC_DATA_API_URL`; each API allows the web origin via its CORS env var
(`VERITY_CORS_ORIGINS` / `VERITY_CATALOG_CORS_ORIGINS`). Deploy the APIs first,
then point the web app at them.

> **Live deployment**
> - Web → Vercel (project `verity`): **https://verity.codes**
> - API → Railway (project `verity-api`): **https://api.verity.codes**
>   (underlying service domain: `verity-api-production-b4c4.up.railway.app`)
> - Data API → Railway (same project, service `verity-data`):
>   **https://verity-data-production.up.railway.app** — the intended public
>   domain **https://data.verity.codes** is not wired yet (DNS still points at
>   Vercel); see "Custom domain" in section 3.

## 1. API → Railway (container)

`railway.json` at the repo root pins the Dockerfile builder, so deploy from the
**repo root** (the API's path deps live in `../engine` and `../../bindings`, so the
whole repo is the build context):

```bash
railway init --name verity-api      # once
railway up                          # builds services/api/Dockerfile, repo as context
railway domain                      # mint the public *.up.railway.app URL
```

**Port:** the image binds `$PORT` and defaults `PORT=8000`. Pin it explicitly so
the app and any custom-domain routing agree:

```bash
railway variables --set "PORT=8000"   # triggers a redeploy
```

**Custom domain** (`api.verity.codes`):

1. Railway → service → **Settings → Networking → Custom Domain** → `api.verity.codes`
   (target port **8000**). Railway returns a CNAME target like `xxxx.up.railway.app`.
2. Add the DNS record at your registrar. For a Vercel-managed domain:
   ```bash
   vercel dns add verity.codes api CNAME <target>.up.railway.app
   ```
3. Railway issues the TLS cert once the CNAME resolves (a few minutes). Verify:
   ```bash
   curl https://api.verity.codes/health   # {"status":"ok","domains":[...]}
   ```

**CORS:** the image defaults `VERITY_CORS_ORIGINS="*"` (answers any origin). To lock
it down, set a Railway service variable, e.g.
`VERITY_CORS_ORIGINS=https://verity.codes`.

**Remote MCP endpoint:** the API also serves a hosted MCP server (streamable HTTP) at
`https://api.verity.codes/mcp` — the same calibrated tools as the stdio server in
`services/mcp`, for AI agents, with no local install. It needs no extra deploy step (it's
mounted in the same app). DNS-rebinding host validation is **off by default** (the endpoint
is reached over the custom domain, the `*.up.railway.app` domain, and health checks); to
lock it down, set `VERITY_MCP_ALLOWED_HOSTS=api.verity.codes` (comma-separated, plus
`VERITY_MCP_ALLOWED_ORIGINS` for browser clients). Verify:
```bash
curl -sS -X POST https://api.verity.codes/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

**Bootstrap-ensemble cost (optional):** every fresh process rebuilds each
reference's 1000-replicate bootstrap calibration ensemble (the toolmark reference
is 167k clustered pairs — minutes on small machines). Two knobs:

- `VERITY_LR_BOOTSTRAP_N` — replicate count (default 1000). Lower it on CI or
  constrained hosts. It is recorded in each comparison's content-addressed
  recipe, so a deployment running fewer replicates (correctly) reports different
  recipe handles.
- `VERITY_ENSEMBLE_CACHE_DIR` — when set (e.g. to a mounted volume), fitted
  ensembles persist to a content-keyed disk cache (~3 KB per reference), so a
  warm restart restores them in milliseconds instead of refitting. A cache hit
  is bit-identical to a cold fit — same seed, method, and bound per replicate.

Any other container host works the same way — point it at `services/api/Dockerfile`
with the repo root as build context (`fly launch --dockerfile services/api/Dockerfile`,
Render, Cloud Run, …).

## 2. Web → Vercel

The `verity` project has **Root Directory `services/web`** and is connected to Git,
so **pushing to `main` auto-deploys** — Vercel clones the repo and builds
`services/web`. Set the API URL once, then just push:

```bash
# one-time
vercel link                                       # link the repo to the `verity` project
vercel env add NEXT_PUBLIC_API_URL production      # = https://api.verity.codes
git push origin main                               # auto-deploys
```

`NEXT_PUBLIC_API_URL` is inlined at **build time**, so any change needs a fresh
deploy (just push again).

For a manual deploy, run from the **repo ROOT** (so the Root Directory setting
resolves — `services/web` is found inside the upload):

```bash
vercel --prod        # from the repo ROOT, not services/web
```

> The repo root holds `services/catalog/.verity` — a multi-GB, GPL-sourced X3P data
> cache that must never ship. It's git-ignored (so Git deploys never see it), and
> the root `.vercelignore` keeps it out of any manual CLI upload too.

## 3. Data API (catalog + benchmark) → Railway

The data API (`services/catalog`) serves the scan catalog, the frozen
open-benchmark splits, replication kits, and the leaderboard. It runs as the
`verity-data` service **inside the same Railway project as the comparison API**
(`verity-api`), backed by a Supabase Postgres catalog and an S3/R2 blob store.

### Deploy the container

Always deploy through the staging script:

```bash
./services/catalog/deploy-railway.sh
```

**Never run bare `railway up` from the repo root for this service.** The repo
root's `railway.json` pins the *comparison* API's Dockerfile
(`services/api/Dockerfile`) as config-as-code, and the per-service
`RAILWAY_DOCKERFILE_PATH` variable does **not** override config-as-code — a root
upload silently builds the wrong image. The script instead stages a minimal
build context (the catalog's `pyproject.toml`/`uv.lock`/`Dockerfile`/source +
the `bindings/python/pyproject.toml` metadata stub + the **catalog's**
`railway.json`) into a temp dir and deploys that. The stage dir is recreated on
every run and is therefore never linked, so the script explicitly runs
`railway link --project … --environment production --service verity-data` first
— an unlinked directory would make `railway up` silently create a brand-new
Railway project. `RAILWAY_SERVICE` / `RAILWAY_PROJECT_ID` env vars override the
defaults.

The catalog `railway.json` health-checks `/healthz`; the image binds `$PORT`
(default 8001).

### Service env vars (Railway → `verity-data` → Variables)

Required:

| Variable | Value |
|---|---|
| `VERITY_CATALOG_DATABASE_URL` | the Supabase **pooler** URL, with the psycopg3 scheme: `postgresql+psycopg://postgres.<ref>:<pw>@aws-1-….pooler.supabase.com:5432/postgres?sslmode=require` (the direct `db.<ref>.supabase.co` host is IPv6-only; `postgresql://` alone selects psycopg2, which isn't installed) |
| `VERITY_CATALOG_CORS_ORIGINS` | `https://verity.codes` (comma-separated for more origins) |
| `VERITY_TRUST_PROXY_HEADERS` | `1` — rate-limit by the client IP the Railway edge appends to `X-Forwarded-For` (the rightmost entry) |
| `PORT` | `8001` |

Optional:

- `VERITY_CATALOG_PUBLIC_URL` — the public base URL baked into replication-kit
  submission instructions. Defaults to `https://data.verity.codes`; until that
  domain is wired, set it to the live service URL
  (`https://verity-data-production.up.railway.app`) so downloaded kits are
  followable.
- `VERITY_BENCHMARK_SUBMIT_TOKEN` — when set, submissions must carry it in
  `X-Benchmark-Token` (a soft close valve).
- `VERITY_BENCHMARK_RATE_LIMIT` / `VERITY_BENCHMARK_RATE_WINDOW_S` — submission
  rate limit per client IP (default 5 per 3600 s).
- `VERITY_CATALOG_MAX_BODY_BYTES` — request-body cap (default 64 MiB; oversized
  submissions get 413).
- Blob store (for `/scans/{id}/x3p` downloads):
  `VERITY_CATALOG_BLOB_STORE_BACKEND=s3`, `VERITY_CATALOG_BLOB_STORE_BUCKET`,
  `VERITY_CATALOG_BLOB_STORE_ENDPOINT_URL` (R2:
  `https://<account>.r2.cloudflarestorage.com`),
  `VERITY_CATALOG_S3_ACCESS_KEY_ID`, `VERITY_CATALOG_S3_SECRET_ACCESS_KEY`,
  `VERITY_CATALOG_S3_REGION` (`auto` for R2), and optionally
  `VERITY_CATALOG_BLOB_STORE_PUBLIC_BASE_URL` to 302-redirect downloads to a
  public bucket domain.

### Load the data (from a local checkout with the live local catalog)

All commands run in `services/catalog` against the Supabase **pooler** URL
(the `postgresql+psycopg://…` form above; the `postgres` extra provides the
driver):

```bash
cd services/catalog
POOLER="postgresql+psycopg://postgres.<ref>:<pw>@aws-1-….pooler.supabase.com:5432/postgres?sslmode=require"

# 1. Schema + RLS policies (Alembic; the URL comes from the env var, not alembic.ini)
VERITY_CATALOG_DATABASE_URL="$POOLER" uv run --extra postgres alembic upgrade head

# 2. Catalog rows (studies → scans), copied from the local SQLite; idempotent
uv run --extra postgres verity-catalog migrate-db --to "$POOLER" --no-create-schema

# 3. Frozen benchmark splits + reference submissions (+ the marks.csv.gz
#    mark→scan mapping the kit ships); idempotent by split name
uv run --extra postgres verity-catalog load-benchmark benchmarks --to "$POOLER"

# 4. Blobs → S3/R2, each verified by SHA-256 read-back; idempotent
uv run --extra s3 verity-catalog sync-blobs --to s3
```

> **Status note:** the blob store is **not yet synced in prod** — step 4 is
> outstanding, so `/scans/{id}/x3p` cannot serve bytes there yet.

Note `migrate-db` is the *row copy* (data), distinct from the Alembic *schema*
migrations in step 1 — run Alembic first and pass `--no-create-schema` so the
schema is exactly what the migrations (and their RLS policies) define.

### Custom domain (`data.verity.codes` — not wired yet)

1. Railway → `verity-data` → **Settings → Networking → Custom Domain** →
   `data.verity.codes` (target port **8001**). This must be done in the
   dashboard — the CLI `railway domain` is permission-blocked for this service.
   Railway returns a CNAME target.
2. Point DNS at it (the apex is Vercel-managed; today the `data` record points
   at Vercel, which is why the domain is dead):
   ```bash
   vercel dns add verity.codes data CNAME <target>.up.railway.app
   ```
3. Once TLS is issued and `curl https://data.verity.codes/healthz` answers,
   update the Vercel env `NEXT_PUBLIC_DATA_API_URL` (or remove it — the web app
   defaults to `https://data.verity.codes`) and redeploy the web app (push), and
   drop any interim `VERITY_CATALOG_PUBLIC_URL` override on the Railway service
   so kits advertise the public domain again.

## 4. Verify

Open https://verity.codes, pick a mark type, upload scans (a bullet's lands for
striated; a breech face for impressed), and Compare. If you see "Failed to fetch,"
confirm `NEXT_PUBLIC_API_URL` is the API's public URL and `VERITY_CORS_ORIGINS`
allows the web origin (or is `*`).

For the data API: `curl <data-api>/healthz` should report the database and
store backend, https://verity.codes/benchmark should render the leaderboard
(it reads `NEXT_PUBLIC_DATA_API_URL`), and a downloaded replication kit's
README should point submissions at a URL that actually answers
(`VERITY_CATALOG_PUBLIC_URL`).
