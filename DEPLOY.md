# Deploying Verity

The platform is two pieces:

- **Web** (`services/web`) — a Next.js app → **Vercel**.
- **API** (`services/api`) — the engine over HTTP. It's a heavy Python + Rust
  stack (scipy / scikit-image / scikit-learn + the maturin `verity_x3p` binding),
  too large for serverless, so it runs as a **container** on any host (Railway,
  Fly.io, Render, Google Cloud Run, a VM…).

The web app calls the API at `NEXT_PUBLIC_API_URL`; the API allows the web origin
via `VERITY_CORS_ORIGINS`. Deploy the API first, then point the web app at it.

> **Live deployment**
> - Web → Vercel (project `verity`): **https://verity.codes**
> - API → Railway (project `verity-api`): **https://api.verity.codes**
>   (underlying service domain: `verity-api-production-b4c4.up.railway.app`)

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

## 3. Verify

Open https://verity.codes, pick a mark type, upload scans (a bullet's lands for
striated; a breech face for impressed), and Compare. If you see "Failed to fetch,"
confirm `NEXT_PUBLIC_API_URL` is the API's public URL and `VERITY_CORS_ORIGINS`
allows the web origin (or is `*`).
