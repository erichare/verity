// Read-only client for the open-benchmark leaderboard (Supabase PostgREST).
// Same access model as lib/catalog.ts: the anon key is public and the benchmark
// tables are SELECT-only under row-level security; submissions are written only
// through the data API's scored POST endpoint.

const SB_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SB_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const benchmarkConfigured = Boolean(SB_URL && SB_KEY);

// The catalog/benchmark data API (kit downloads + submissions).
export const DATA_API_URL =
  process.env.NEXT_PUBLIC_DATA_API_URL ?? "https://data.verity.codes";

function authHeaders(): Record<string, string> {
  return { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` };
}

export interface BenchmarkSplit {
  id: number;
  name: string;
  title: string;
  modality: string;
  split_hash: string;
  protocol_version: number;
  n_pairs: number;
  n_km: number;
  n_sources: number;
  n_folds: number;
}

export interface BenchmarkSubmission {
  split_id: number;
  submitter: string;
  method: string;
  url: string | null;
  is_reference: boolean;
  cllr: number;
  cllr_std: number;
  cllr_min: number;
  auc: number;
  calibration_loss: number;
  created_at: string;
}

export async function getSplits(): Promise<BenchmarkSplit[]> {
  if (!benchmarkConfigured) return [];
  const params = new URLSearchParams({
    select:
      "id,name,title,modality,split_hash,protocol_version,n_pairs,n_km,n_sources,n_folds",
    order: "name",
  });
  const res = await fetch(`${SB_URL}/rest/v1/benchmarksplit?${params}`, {
    headers: authHeaders(),
    next: { revalidate: 300 },
  });
  if (!res.ok) return [];
  return res.json();
}

/** Every leaderboard row, ranked by total Cllr (the proper scoring rule) —
 * grouped per split by the caller. */
export async function getSubmissions(): Promise<BenchmarkSubmission[]> {
  if (!benchmarkConfigured) return [];
  const params = new URLSearchParams({
    select:
      "split_id,submitter,method,url,is_reference,cllr,cllr_std,cllr_min,auc,calibration_loss,created_at",
    order: "cllr.asc",
    limit: "400",
  });
  const res = await fetch(`${SB_URL}/rest/v1/benchmarksubmission?${params}`, {
    headers: authHeaders(),
    next: { revalidate: 300 },
  });
  if (!res.ok) return [];
  return res.json();
}

export function kitUrl(split: BenchmarkSplit): string {
  return `${DATA_API_URL}/benchmark/splits/${split.name}/kit`;
}

export function submitUrl(split: BenchmarkSplit): string {
  return `${DATA_API_URL}/benchmark/splits/${split.name}/submissions`;
}

const MODALITY_LABELS: Record<string, string> = {
  "striated-bullet": "Bullet lands · striated",
  "striated-toolmark": "Screwdriver toolmarks · striated",
  impressed: "Cartridge breech faces · impressed",
};

export function modalityLabel(modality: string): string {
  return MODALITY_LABELS[modality] ?? modality;
}
