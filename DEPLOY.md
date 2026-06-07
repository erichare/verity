# Deploying Verity

The platform is two pieces:

- **Web** (`services/web`) — a Next.js app → **Vercel**.
- **API** (`services/api`) — the engine over HTTP. It's a heavy Python + Rust
  stack (scipy / scikit-image / scikit-learn + the maturin `verity_x3p` binding),
  too large for serverless, so it runs as a **container** on any host (Fly.io,
  Render, Railway, Google Cloud Run, a VM…).

The web app calls the API at `NEXT_PUBLIC_API_URL`; the API allows the web origin
via `VERITY_CORS_ORIGINS`. Deploy the API first, then point the web app at it.

## 1. API (container)

```bash
# build from the repo root (the API's path deps live in ../engine, ../../bindings)
docker build -f services/api/Dockerfile -t verity-api .

# run locally
docker run -p 8000:8000 -e VERITY_CORS_ORIGINS="*" verity-api
curl localhost:8000/health        # {"status":"ok","domains":["impressed","striated"]}
```

Deploy that image to any container host and note its public URL, e.g.

```bash
fly launch --dockerfile services/api/Dockerfile     # Fly.io
# or: render.com / railway.app / Cloud Run — point them at services/api/Dockerfile
```

Set on the host: `VERITY_CORS_ORIGINS=https://<your-vercel-app>.vercel.app`
(hosts that inject `$PORT`, e.g. Cloud Run/Render, are handled — the image binds `$PORT`).

## 2. Web (Vercel)

The repo is a monorepo, so set the project's **Root Directory** to `services/web`.

```bash
cd services/web
vercel link            # or import the repo in the Vercel dashboard
vercel env add NEXT_PUBLIC_API_URL     # = https://<your-api-host>
vercel --prod
```

Or in the dashboard: **New Project → import repo → Root Directory `services/web` →
add env `NEXT_PUBLIC_API_URL` → Deploy.**

## 3. Verify

Open the Vercel URL, pick a mark type, upload scans (a bullet's lands for
striated; a breech face for impressed), and Compare. If you see "Failed to
fetch," the API origin isn't allowed — confirm `VERITY_CORS_ORIGINS` includes the
Vercel domain and `NEXT_PUBLIC_API_URL` is the API's public URL.
