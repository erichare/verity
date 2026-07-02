---
name: Bug report
about: Something is broken in the codec, engine, API, catalog, or web app
title: "[bug] "
labels: bug
assignees: ''
---

## What happened

A clear description of the bug — what you did, what you expected, what you got
instead. Paste exact error messages / stack traces / response bodies where
possible.

## Where

- **Component**: (crates/verity-x3p | bindings/python | bindings/r |
  services/engine | services/api | services/catalog | services/mcp |
  services/web)
- **Endpoint** (if API-related): e.g. `POST https://api.verity.codes/compare`,
  `GET https://data.verity.codes/scans`, or your local URL
- **Engine / package version**: commit SHA, PyPI/crates version, or the
  `/version` response of the deployed service

## Input data (for scan-processing bugs)

Bugs in reading, preprocessing, or comparison usually depend on the scan:

- **X3P provenance**: which dataset / study the file came from (e.g. NBTRD
  study id, Figshare DOI, your own acquisition) — attach or link the file if
  it is shareable
- **Instrument**: make/model and acquisition mode (e.g. Sensofar S neox,
  confocal), lateral resolution / increments if known
- **Mark type**: bullet land (striated) | cartridge breech face (impressed) |
  toolmark | other

## Steps to reproduce

1. …
2. …
3. …

## Environment

- OS / architecture:
- Python / Rust / Node version (as relevant):
- Install method: (uv sync / maturin develop / pnpm install / live site)

## Additional context

Logs, screenshots, or anything else that helps.
