// Mirror of verity.report.ComparisonReport (the API serves this verbatim).
export interface AttributionRegion {
  x: number;
  y: number;
  h: number;
  w: number;
  corr: number;
  // normalized [0,1] coords for overlaying on a rendered preview
  x_frac: number;
  y_frac: number;
  w_frac: number;
  h_frac: number;
}

export interface ComparisonReport {
  domain: string;
  score: number;
  score_kind: string;
  likelihood_ratio: number;
  log10_lr: number;
  direction: string;
  verbal: string;
  lr_bound_log10: number | null;
  reference: {
    name: string;
    n_km: number;
    n_knm: number;
    cllr: number;
    cllr_min: number;
    auc: number;
  };
  attribution: AttributionRegion[]; // matched regions on Mark A
  attribution_b?: AttributionRegion[]; // the same matches on Mark B
  provenance: Record<string, unknown>;
  scope_note: string;
  // API presentation: small grayscale previews of each mark to overlay regions on
  previews?: { a: number[][]; b: number[][] };
}
