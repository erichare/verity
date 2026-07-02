# Verity — readout for Dr. Alicia Carriquiry

*Prepared 2026-06-13 for the Monday review. Companion docs:*
[`headline-numbers.md`](headline-numbers.md) *(every number, scoped)* ·
[`toolmark-roadmap.md`](toolmark-roadmap.md) *(other marks we can add)* ·
[`whitepaper/verity-whitepaper.tex`](whitepaper/verity-whitepaper.tex).

## The one claim

One algorithm (**Congruent Matching Regions**), one **frozen scorer config** (hash
`ea4ddd…`), reduced to three mark families and validated **source-disjoint** in each — and
the output is never a "match," it is a **calibrated likelihood ratio with a credible
interval** on a *named* reference population, plus the region-level attribution that drove it.

## What the numbers actually say (all in `headline-numbers.md`)

Frozen open-benchmark protocol (published, externally reproducible; mean over folds):

| Mark family | Reduction | Cllr | AUC |
|---|---|---|---|
| Bullet lands (striated) | CMS, 1-D | 0.205 ± 0.125 | 0.979 |
| Cartridge breech faces (impressed) | CMC, 2-D | 0.398 ± 0.202 | 0.922 |
| Screwdriver toolmarks (striated) | Chumbley striae, 1-D | 0.330 ± 0.047 | 0.944 |

`Cllr < 1` = informative; lower is better; these are **weight of evidence on the named
references, not field error rates**. Single best study (Hamby-252 alone, barrel-disjoint)
is **Cllr 0.113**; the trained `bulletxtrctr` specialist still leads there (0.064) — Verity's
bullet contribution is the calibrated, bounded, deployable LR layer, not a better matcher.

**Two honesty points we are surfacing rather than hiding:**
- *In-sample vs. source-disjoint.* The live report's `reference` block carries the
  reference's **in-sample** fit (pooled bullet Cllr 0.193). The honest validation number is
  the **source-disjoint** Cllr (0.186 pooled) — and the two are nearly identical, which is the
  point: low calibration loss. Every public sample is now scope-labeled to say so.
- *Cartridge AUC cross-protocol gap.* The frozen benchmark reads AUC 0.922 (fold mean) /
  0.941 (pooled); internal source-disjoint reads 0.991. With **only 10 same-source pairs**,
  per-fold AUC is unstable and the fold rules differ — a small-n artifact, not a contradiction.
  We quote the **frozen benchmark** as primary for cartridge. (Where her input is most valuable.)

## The statistician-facing feature to show: per-decision uncertainty

Every LR ships with a **percentile credible interval on log10 LR**, from a bootstrap of the
reference that is **clustered by source/barrel** (honest — lands from one barrel are
correlated) and refits the calibration per replicate. Verified live this weekend on Fadul:
- KM pair → LR 10, interval **[1.0, 1.20] log10**, pinned at the empirical cap.
- KNM pair → LR 1.2, interval **[−1.15, 0.88]**, correctly flagged *"direction not resolved at
  the 95% level."*

This directly answers the "no characterized uncertainty" critique at the level of an
individual reported decision, not just an aggregate.

## Integrity guarantees (the anti-black-box story)

- **Frozen scorer-config hash** — every reference records the hash it was built under; a runtime
  mismatch refuses the calibrated LR (the firewall against silent config drift).
- **Empirical cap (ELUB-inspired)** — the LR cannot exceed what the reference can support;
  bound-limited LRs are flagged in the payload and the scope note.
- **Out-of-domain refusal** — resolution/modality scope guard refuses an LR on scans the
  reference doesn't cover, rather than extrapolating.
- **Reproducible by construction** — content-addressed recipes + provenance sidecars; a result
  is replayable from its handle.

## Honest gaps (lead with these)

1. **No independent external validation yet.** Ablation and validation reuse the four NBTRD
   bullet studies. **The fix is in reach:** the Weller cartridge set (11 consecutively-made
   Ruger slides, CC-BY, available now) makes the impressed result a two-study, cross-instrument
   claim — see `toolmark-roadmap.md`.
2. **Cartridge small-n.** 10 same-source pairs; AUC unstable across protocols (above).
3. **Learned representation overfits** on 210 scans (held-out AUC ≈ 0.67) — documented as a
   data limit, not deployed; only the hand-engineered `diag_contrast` ships.
4. **Standards positioning (roadmap, not a claim).** Verity's calibrated-LR output aligns with
   the **ENFSI evaluative-reporting** framework (LR on a defined population, not a categorical
   conclusion) and is complementary to the AFTE/SWGGUN "sufficient agreement" status quo it
   aims to make quantitative. **ISO/IEC 17025** accreditation is a roadmap item; the
   reproducibility machinery (frozen hash, content-addressed recipes) is the foundation a
   17025 validation would build on. No accreditation is claimed today.

## Other marks we can include (full detail in `toolmark-roadmap.md`)

The architecture is domain-general, so a new family is *data + a registry entry*, not new
science. The catalog schema already accepts `firing_pin`, `ejector`, `aperture_shear`
(verified). Sequence: **Weller breech faces** (available now, 2nd independent impressed study)
→ **firing-pin impressions** (schema + CMR-2D ready; needs crater segmentation of the existing
primer scans) → ejector/aperture-shear striae → non-firearm tool striae → fractured surfaces (3-D).

## Hardened this weekend (table-stakes, done)

- Hosted **MCP endpoint now rate-limited** (CPU-bound compare can't bypass the per-IP cap).
- **Security headers** (HSTS, X-Frame-Options, nosniff, Referrer-Policy, CSP frame-ancestors)
  on the API and the data catalog.
- **CI security scanning** (cargo-audit, pip-audit, bandit) added report-only.
- Confirm in prod: `VERITY_MCP_ALLOWED_HOSTS` is set on Railway (DNS-rebinding guard).

## Where her input is most valuable

- The cartridge AUC cross-protocol gap and the right primary metric for small-n impressed sets.
- Whether the clustered-bootstrap credible interval is the right uncertainty object for court
  use, and how to express "direction not resolved at 95%" to a trier of fact.
- Prioritizing the independent-validation path (Weller now; a blind/pre-registered challenge next).
- Standards: the most credible ENFSI/SWGGUN framing and a realistic ISO 17025 validation path.
