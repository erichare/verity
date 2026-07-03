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
>   **https://data.verity.codes** — live (underlying service domain:
>   `verity-data-production.up.railway.app`). Deploys are **manual**: run
>   `./services/catalog/deploy-railway.sh`; merging to `main` does **not**
>   auto-deploy this service (see section 3).

> **DNS note (2026-07-01):** the `verity.codes` zone is now served through
> **Cloudflare** (every host returns `server: cloudflare`) — DNS records are
> managed in the Cloudflare dashboard, not with `vercel dns`. The `vercel dns
> add` commands below are the historical record of how records were first
> created; for any change today, edit the record in Cloudflare, and keep
> Railway-hosted names **DNS-only (grey cloud)** so Railway can issue TLS.

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

**CORS:** the image defaults to the **localhost dev origins only**
(`http://localhost:3000,http://127.0.0.1:3000` — see `verity_api/main.py`; the
Dockerfile deliberately does not bake `"*"`). A deployed front end therefore fails
every fetch until you set the Railway service variable to the real origins:
`VERITY_CORS_ORIGINS=https://verity.codes,https://app.verity.codes`.

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

### `docs.verity.codes` cutover (the app / science split)

The redesign serves **two hosts from the one `verity` Vercel project**: `verity.codes`
is the app (the compare workspace), and `docs.verity.codes` is the science/docs
(method, why, benchmark, catalog, references, the docs page). Host routing lives in
`services/web/proxy.ts` (rewrites the docs host onto the internal `/docs-site` segment)
and the moved-path redirects live in `services/web/next.config.ts`.

**Deploy the code and attach the domain together** — until `docs.verity.codes` is
attached, the `verity.codes/<seg>` → `docs.verity.codes/<seg>` redirects 404, so old
`/method` etc. links break. One-time, by Eric:

```bash
# 1. Add the domain to the SAME project (no new project, no new env vars — the build
#    is shared; NEXT_PUBLIC_API_URL / NEXT_PUBLIC_DATA_API_URL already apply to both).
vercel domains add docs.verity.codes verity        # or dashboard → verity → Settings → Domains

# 2. DNS (the verity.codes zone is on Vercel): add the docs CNAME, then wait for TLS.
vercel dns add verity.codes docs CNAME cname.vercel-dns.com.

# 3. Smoke test after the deploy is live:
curl -I https://docs.verity.codes/method     # 200 (proxy → /docs-site/method)
curl -I https://verity.codes/method           # 308 → https://docs.verity.codes/method
curl -I https://verity.codes/docs-site/method # 308 → /method (internal segment guarded)
curl    https://verity.codes/robots.txt        # Disallow: /docs-site/ + sitemap

# 4. Google Search Console: add the docs.verity.codes property, submit
#    https://verity.codes/sitemap.xml, and request recrawl on a few moved paths
#    (/method, /benchmark) so the index moves to the docs host cleanly.
```

Local dev simulates the docs host with `*.localhost` (no hosts-file edit needed in
Chrome/Safari): the app at `http://localhost:3000`, the docs at
`http://docs.localhost:3000/method`.

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

Deploys are **manual**: this service is not wired to auto-deploy on pushes or
merges to `main`, so after any merge that touches `services/catalog`, re-run
the script above to publish the change.

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
  submission instructions. Defaults to `https://data.verity.codes` (live), so it
  normally needs no override; set it only if the public domain ever stops
  answering (e.g. to the underlying
  `https://verity-data-production.up.railway.app`) so downloaded kits stay
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

> **Status note (2026-07-02):** the prod blob store is **partially synced** —
> `/healthz?count=true` reports 1181 blobs for 1780 scans (the `tmarks` and
> `csafe-isu` blobs are outstanding), so `/scans/{id}/x3p` returns 404 for those
> scans (metadata serves; bytes do not). The API reports the gap per scan via
> `blob_available` (and `/scans?blob_available=false` lists it); re-run step 4
> to close it.

Note `migrate-db` is the *row copy* (data), distinct from the Alembic *schema*
migrations in step 1 — run Alembic first and pass `--no-create-schema` so the
schema is exactly what the migrations (and their RLS policies) define.

### One-off prod fix — leaderboard submission URLs (run once)

Verity baseline submissions loaded before the docs-host split carry the
pre-migration `https://verity.codes/method` URL (it bounces through a 308
today; the right URL is `https://docs.verity.codes/method`). The committed
loader now writes the docs URL, so future `load-benchmark` runs are correct;
fix the existing prod rows with one statement against the pooler URL
(idempotent — re-running is a no-op):

```sql
UPDATE benchmarksubmission SET url = replace(url, 'https://verity.codes/method', 'https://docs.verity.codes/method') WHERE url LIKE '%verity.codes/method%';
```

### Custom domain (`data.verity.codes` — **live**)

The domain is wired and answering: Railway holds `data.verity.codes` as the
custom domain on the `verity-data` service (target port **8001**), and the
Cloudflare `data` record is a **DNS-only (grey cloud)** CNAME to the Railway
target, so Railway terminates TLS with its own certificate.

```bash
curl https://data.verity.codes/healthz
# 200 — {"success":true,"data":{"status":"ok","database":"postgresql+psycopg",
#        "store_backend":"s3",…,"scan_count":1780},"error":null,…}
```

If it ever breaks again, the known failure mode (seen 2026-07-01, since fixed)
is the Cloudflare `data` record flipping to **proxied** (orange cloud) A
records that forward to Vercel — `https://data.verity.codes/healthz` then
answers 404 with `x-vercel-error: DEPLOYMENT_NOT_FOUND` while the underlying
`https://verity-data-production.up.railway.app/healthz` stays healthy.

**Re-wiring steps** (all **Eric-only** — Railway + Cloudflare dashboard access):

1. Railway → `verity-data` → **Settings → Networking**: confirm the custom
   domain `data.verity.codes` still exists (re-add it if not; target port
   **8001**) and copy the CNAME target Railway shows
   (`<target>.up.railway.app`). This must be done in the dashboard — the CLI
   `railway domain` is permission-blocked for this service.
2. Cloudflare dashboard → `verity.codes` → **DNS**: change the `data` record to
   a **CNAME** pointing at that Railway target, set to **DNS-only (grey
   cloud)**. Proxying it (orange cloud) keeps terminating TLS at
   Cloudflare→Vercel and blocks Railway from issuing its certificate.
3. Verify once TLS is issued (a few minutes):
   ```bash
   curl https://data.verity.codes/healthz   # 200 + database/store report
   ```
4. Then remove any interim `VERITY_CATALOG_PUBLIC_URL` override on the Railway
   service so downloaded replication kits advertise the public domain again,
   and check the Vercel env `NEXT_PUBLIC_DATA_API_URL` (or remove it — the web
   app defaults to `https://data.verity.codes`) and redeploy the web app
   (push).

## 4. Launch-day production env checklist

Verify **every** row below on Railway before any public launch. Each variable is
read by the code paths cited; the "failure mode" column is what actually happens
if it is unset (all cross-checked against the source, 2026-07-01).

### Comparison API (Railway service `verity-api`)

| Variable | Set to | Purpose / failure mode if unset |
|---|---|---|
| `VERITY_MCP_ALLOWED_HOSTS` | `api.verity.codes` | Host allow-list for the hosted `/mcp` endpoint. **Unset ⇒ DNS-rebinding protection is disabled entirely** (`verity_api/mcp_server.py` builds `TransportSecuritySettings(enable_dns_rebinding_protection=False)` when the list is empty). Pair with `VERITY_MCP_ALLOWED_ORIGINS` for browser-based MCP clients. |
| `VERITY_TRUST_PROXY_HEADERS` | `1` | Behind Railway's edge proxy, `request.client.host` is the proxy, so **unset ⇒ the per-IP rate limit collapses into one global bucket** — a single heavy client 429s everyone. When set, the limiter keys on the *rightmost* `X-Forwarded-For` entry (the hop the trusted edge appended; client-supplied entries are ignored). |
| `VERITY_CORS_ORIGINS` | `https://verity.codes,https://app.verity.codes` | Browser origins allowed to call the API. **Unset ⇒ localhost dev origins only** (`verity_api/main.py`), so both production front ends fail every fetch with a CORS error. |
| `VERITY_ENSEMBLE_CACHE_DIR` | a mounted-volume path | Warm-restart disk cache for bootstrap calibration ensembles (~3 KB/reference, bit-identical to a cold fit). **Unset ⇒ every restart/deploy refits every reference's ensemble** — minutes of CPU before the first LR is served. |
| `VERITY_LR_BOOTSTRAP_N` | leave at default `1000` in prod | Bootstrap replicate count; recorded in each comparison's content-addressed recipe, so changing it (correctly) changes reported recipe handles. Lower it only on CI/constrained hosts — not on the public API. |
| `VERITY_STRICT_REFERENCE` | `1` (recommended) | Scorer-config drift guard **raises at reference load** instead of logging a warning (`verity/decision/scorer_config.py`) — a stale bundled reference can't silently ship a bad LR. |
| `PORT` | `8000` | Pinned so the app and custom-domain routing agree (section 1). |

### Data API (Railway service `verity-data`)

| Variable | Set to | Purpose / failure mode if unset |
|---|---|---|
| `VERITY_CATALOG_DATABASE_URL` | the Supabase **pooler** URL (`postgresql+psycopg://…`, section 3) | **Unset ⇒ falls back to `sqlite:///verity_catalog.db`** (`verity_catalog/config.py`) — an empty, ephemeral in-container database; the catalog serves nothing. |
| `VERITY_TRUST_PROXY_HEADERS` | `1` | Same collapse as the API: **unset ⇒ benchmark-submission rate limiting becomes one global bucket** (`verity_catalog/api/routers/benchmark.py`). |
| `VERITY_CATALOG_CORS_ORIGINS` | every browser origin that reads the catalog directly | Code default is `https://verity.codes` only (`verity_catalog/api/app.py`); confirm it covers any other front (e.g. the docs host) that fetches the catalog from the browser. |
| `VERITY_BENCHMARK_SUBMIT_TOKEN` | decide **before** launch | Submission close valve: when set, leaderboard submissions must carry it in `X-Benchmark-Token` (else 403). **Unset ⇒ submissions are open to anyone**, guarded only by the 5-per-hour-per-IP rate limit (`VERITY_BENCHMARK_RATE_LIMIT`/`VERITY_BENCHMARK_RATE_WINDOW_S`). |
| Blob-store vars (`VERITY_CATALOG_BLOB_STORE_BACKEND=s3` + bucket/endpoint/keys, section 3) | as wired | **Unset ⇒ `/scans/{id}/x3p` serves no bytes** (metadata-only catalog). |
| `PORT` | `8001` | Matches the catalog `railway.json` health check + custom-domain target port. |

### External verification (run from any machine)

Rate limit binds to the *real* client, not a spoofable header — repeated
requests with a **changing spoofed `X-Forwarded-For`** must still trip 429
(Railway appends the real client IP as the rightmost entry, and the limiter
keys on that; if each spoof minted a fresh bucket, no 429 would ever appear):

```bash
# 200 requests, 16 in parallel (must finish inside the 60 s window), each with a
# DIFFERENT spoofed X-Forwarded-For:
seq 1 200 | xargs -P 16 -I{} curl -s -o /dev/null -w "%{http_code}\n" \
  -X POST https://api.verity.codes/detect \
  -H "X-Forwarded-For: 10.0.0.{}" -F "scan=@/dev/null;filename=empty.x3p" \
  | sort | uniq -c
# healthy: 429s appear (default limit: 120 per 60 s, keyed on the real client IP)
# broken:  no 429 at all — every spoofed header minted its own bucket
```

CORS preflight answers the production origins (repeat for each origin):

```bash
curl -s -o /dev/null -D - -X OPTIONS https://api.verity.codes/v1/compare \
  -H "Origin: https://verity.codes" \
  -H "Access-Control-Request-Method: POST" | grep -i access-control-allow-origin
# expect: access-control-allow-origin: https://verity.codes
```

Health endpoints:

```bash
curl https://api.verity.codes/health    # {"status":"ok","engine_version":…,"domains":[…]}
curl https://data.verity.codes/healthz  # envelope with database + store_count/scan_count
```

## 5. Monitoring

- **Sentry (API):** a parallel PR adds env-gated Sentry to `services/api` — set
  the Sentry DSN env var on the Railway `verity-api` service to enable it;
  leaving it unset keeps Sentry fully disabled (no-op).
- **Railway alerts:** configure alerts on a **429/503 spike** (rate-limit
  saturation / not-fully-published benchmark splits) and on **p95 `/compare`
  latency** (the CPU-bound path; a sustained rise usually means the bootstrap
  ensemble cache is cold or concurrency is saturated).
- **Health endpoints:** `api.verity.codes` serves **`/health`** (a parallel PR
  aliases `/healthz` so both answer); the data API serves **`/healthz`**. Point
  uptime checks at those.

## 6. Verify

Open https://verity.codes, pick a mark type, upload scans (a bullet's lands for
striated; a breech face for impressed), and Compare. If you see "Failed to fetch,"
confirm `NEXT_PUBLIC_API_URL` is the API's public URL and `VERITY_CORS_ORIGINS`
allows the web origin (or is `*`).

For the data API: `curl <data-api>/healthz` should report the database and
store backend, https://verity.codes/benchmark should render the leaderboard
(it reads `NEXT_PUBLIC_DATA_API_URL`), and a downloaded replication kit's
README should point submissions at a URL that actually answers
(`VERITY_CATALOG_PUBLIC_URL`).
