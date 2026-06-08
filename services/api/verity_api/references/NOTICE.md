# Bundled reference data — attribution

`cartridge_fadul.npz` contains *derived* per-pair **congruent-matching-region
(CMR) counts** and KM/KNM labels (not the scans) — the same impressed-mark scorer
the live API uses — computed by Verity from the **Fadul** cartridge-case breech-
face scans, plus per-pair slide IDs, used only to calibrate and scope the
impressed-mark likelihood ratio.

Source scans: **CSAFE-ISU/cartridgeCaseScans** (`fadulMasked/`), licensed
**CC-BY 4.0** (Creative Commons Attribution). https://github.com/CSAFE-ISU/cartridgeCaseScans

Underlying study: Fadul et al., *An Empirical Study to Improve the Scientific
Foundation of Forensic Firearm and Tool Mark Identification Utilizing 10
Consecutively Manufactured Slides* (2011).

`bullet_pooled.npz` contains *derived* per-pair **diag-contrast** bullet scores
(the deployed bullet scorer) and same-barrel labels (not the scans) computed by
Verity from four public bullet-land studies — **Hamby (2009) Barrel Sets 252 &
173, PGPD Beretta, and Phoenix PD (Ruger P-95)** (NIST NBTRD / CSAFE; public) —
pooled into one striated-mark reference (146 same-source pairs), plus per-pair
barrel IDs, used only to calibrate and scope the striated likelihood ratio.
Within-study pairs only (no trivial cross-make negatives).

Each `.npz` ships a `*.provenance.json` sidecar recording the exact scorer
configuration (and its hash), the contributing datasets, the generation commit,
the cluster scheme, and the reference diagnostics (AUC / Cllr / Cllr_min) — so each
bundled LR is traceable to the data and code that produced it. The per-pair cluster
IDs power the honest *clustered* bootstrap (resampling whole barrels/slides).
Regenerate deterministically with `verity-build-references --write` (engine).

