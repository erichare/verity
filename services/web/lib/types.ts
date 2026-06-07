// Mirror of verity.report.ComparisonReport (the API serves this verbatim).
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
  attribution: Array<Record<string, unknown>>;
  provenance: Record<string, unknown>;
  scope_note: string;
}
