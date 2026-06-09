import sample from "./sample-screwdriver.json";
import type { ComparisonReport } from "./types";

// The slice of the committed screwdriver sample this module renders. The file is generated
// from a REAL same-tool-edge tmaRks comparison (CMR-1D, calibrated on the committed
// toolmark reference) by `verity-build-sample-screwdriver`, so the homepage "Load a sample"
// report stays honest and reproducible and never drifts.
interface ScrewdriverSample {
  domain: string;
  score: number;
  score_kind: string;
  likelihood_ratio: number;
  log10_lr: number;
  log10_lr_ci_lo: number;
  log10_lr_ci_hi: number;
  verbal: string;
  lr_bound_log10: number | null;
  reference: { name: string; auc: number; cllr: number; cllr_min: number; n_km: number; n_knm: number };
  pair: string[];
  scope_note: string;
}

const data = sample as unknown as ScrewdriverSample;

/**
 * A precomputed `ComparisonReport` from a real same-source screwdriver-toolmark comparison
 * (tmaRks, scored with CMR-1D and calibrated on the committed toolmark reference) — so a
 * visitor sees the actual report artifact without owning any .x3p scans, on a non-firearm
 * mark. Every figure is real; nothing is fabricated. Region attribution is omitted here
 * (the homepage's live proof and the /method walkthrough carry the visual attribution).
 */
export function buildSampleReport(): ComparisonReport {
  return {
    domain: data.domain,
    score: data.score,
    score_kind: data.score_kind,
    likelihood_ratio: data.likelihood_ratio,
    log10_lr: data.log10_lr,
    log10_lr_ci_lo: data.log10_lr_ci_lo,
    log10_lr_ci_hi: data.log10_lr_ci_hi,
    direction: "same_source",
    verbal: data.verbal,
    lr_bound_log10: data.lr_bound_log10,
    reference: {
      name: data.reference.name,
      n_km: data.reference.n_km,
      n_knm: data.reference.n_knm,
      cllr: data.reference.cllr,
      cllr_min: data.reference.cllr_min,
      auc: data.reference.auc,
    },
    attribution: [],
    provenance: { sample: true, dataset: "tmaRks", pairing: "same-tool-edge", pair: data.pair },
    scope_note: data.scope_note,
  };
}
