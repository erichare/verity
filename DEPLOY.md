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

Any other container host works the same way — point it at `services/api/Dockerfile`
with the repo root as build context (`fly launch --dockerfile services/api/Dockerfile`,
Render, Cloud Run, …).

## 2. Web → Vercel

The `verity` project keeps the default **Root Directory `.`** and is deployed **from
`services/web`** (where the Next.js `package.json` lives — the frontend is
standalone and needs nothing else from the repo):

```bash
cd services/web
vercel link                                         # link to the `verity` project
vercel env add NEXT_PUBLIC_API_URL production        # = https://api.verity.codes
vercel --prod                                        # build + deploy from here
```

`NEXT_PUBLIC_API_URL` is inlined at **build time**, so always redeploy after
changing it.

> **Do not deploy from the repo root.** The root holds `services/catalog/.verity`
> — a multi-GB, GPL-sourced X3P data cache that must never leave the machine. It's
> git-ignored, but if you ever do deploy from the root, add a `.vercelignore` that
> excludes `**/.verity`, `**/target`, and `**/*.x3p`.

## 3. Verify

Open https://verity.codes, pick a mark type, upload scans (a bullet's lands for
striated; a breech face for impressed), and Compare. If you see "Failed to fetch,"
confirm `NEXT_PUBLIC_API_URL` is the API's public URL and `VERITY_CORS_ORIGINS`
allows the web origin (or is `*`).
