import methodData from "./method-data.json";
import type { ComparisonReport } from "./types";

// The slices of method-data.json this module reads. The file is the single
// source of truth for the real Hamby-252 comparison shown across the site, so
// the "Load sample" report on the homepage stays honest and never drifts.
interface KmExample {
  score: number;
  scoreKind: string;
  lr: number;
  log10_lr: number;
  verbal: string;
  lrBound: number | null;
  reference: { name: string; auc: number; cllr: number; nKm: number; nKnm: number };
}
interface CalibrationSlice {
  cllrMin: number;
}

const data = methodData as unknown as { km: KmExample; calibration: CalibrationSlice };

/**
 * A precomputed `ComparisonReport` from the real same-source Hamby-252 bullet
 * comparison in method-data.json — so a visitor can see the actual report
 * artifact without owning any .x3p scans. Every figure is real; nothing is
 * fabricated. Region attribution is intentionally omitted here (the homepage's
 * live proof and the /method walkthrough carry the visual attribution).
 */
export function buildSampleReport(): ComparisonReport {
  const { km, calibration } = data;
  return {
    domain: "striated",
    score: km.score,
    score_kind: km.scoreKind,
    likelihood_ratio: km.lr,
    log10_lr: km.log10_lr,
    direction: "same_source",
    verbal: km.verbal,
    lr_bound_log10: km.lrBound,
    reference: {
      name: km.reference.name,
      n_km: km.reference.nKm,
      n_knm: km.reference.nKnm,
      cllr: km.reference.cllr,
      cllr_min: calibration.cllrMin,
      auc: km.reference.auc,
    },
    attribution: [],
    provenance: { sample: true, dataset: "Hamby-252", pairing: "same-source" },
    scope_note:
      "A precomputed sample — a real same-source Hamby-252 bullet comparison on the pooled bullet-land reference. Not a claim about the error rate of examination, which remains unknown.",
  };
}
