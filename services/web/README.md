# verity-web

The Verity web UI — the Next.js front end of the Phase-5 platform. It calls the
`verity-api` (`services/api`) `/compare` endpoint and renders the calibrated
**comparison report**: the likelihood ratio + ENFSI verbal weight of evidence, the
reference diagnostics that scope it (AUC, Cllr/Cllr_min, KM/KNM), provenance, and
the honest scope statement.

Stack: Next.js (App Router) + TypeScript + Tailwind v4.

The same app serves the comparison workspace at `verity.codes`, the Studio at
`app.verity.codes`, and the documentation at `docs.verity.codes`. The public
`/plugins` documentation has separate Claude Code and Codex installation guides.
Plugin packages and their marketplace manifests live at the repository root.

## Run

```bash
cp .env.example .env.local        # point NEXT_PUBLIC_API_URL at the API
corepack enable                  # package.json pins the supported pnpm version
pnpm install --frozen-lockfile
pnpm dev                          # http://localhost:3000  (API on :8000)
```

Pick a mark type, choose two `.x3p` scans, and Compare. The decision stays in the
engine's bounded-LR firewall; this UI only renders what the API returns.

For the docs shell, visit `http://docs.localhost:3000/plugins`. For the Studio,
visit `http://app.localhost:3000`. These local host aliases use port 3000.

## Verify

```bash
pnpm typecheck  # regenerates Next route types before checking
pnpm test       # comparison provenance and walkthrough regression tests
pnpm build
```

The Studio requests a recipe with each live comparison. Its scorer configuration
comes from that response, and its walkthrough selects the same lands as the
report's attribution. Optional stage failures keep the comparison visible.
