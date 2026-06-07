# verity-web

The Verity web UI — the Next.js front end of the Phase-5 platform. It calls the
`verity-api` (`services/api`) `/compare` endpoint and renders the calibrated
**comparison report**: the likelihood ratio + ENFSI verbal weight of evidence, the
reference diagnostics that scope it (AUC, Cllr/Cllr_min, KM/KNM), provenance, and
the honest scope statement.

Stack: Next.js (App Router) + TypeScript + Tailwind v4.

## Run

```bash
cp .env.example .env.local        # point NEXT_PUBLIC_API_URL at the API
pnpm install
pnpm dev                          # http://localhost:3000  (API on :8000)
```

Pick a mark type, choose two `.x3p` scans, and Compare. The decision stays in the
engine's bounded-LR firewall; this UI only renders what the API returns.

## Roadmap

v1 renders the report card. Next: Tippett/ECE plots, the congruent-region
attribution overlay (CMR's regions as the examiner-facing CMS visual), and the
2-D/3-D surface viewer.
