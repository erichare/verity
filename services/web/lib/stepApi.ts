// Client for the glass-box step API (api.verity.codes/v1/*) — the live, per-stage walk of
// the pipeline on an uploaded mark. Mirrors lib/api.ts. Each step takes input handle(s),
// runs one computation, and returns an output handle + a JSON preview, so the Studio can
// render every intermediate the way `verity-build-tour` bakes it for the curated tour.
// Shapes mirror services/api/verity_api/{steps.py,intermediates.py,artifacts.py} exactly.

import { fetchWithTimeout, SHORT_TIMEOUT_MS } from "./http";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export interface ArtifactRef {
  handle: string;
  kind: string;
  meta?: Record<string, unknown>;
  bytes?: number;
}

// The full striated trace returned inline by /v1/steps/signature (trace_dict): one call
// backfills the raw, bandpassed, and rotated stages plus the 1-D signature.
export interface TracePreview {
  tilt_deg: number;
  striae_angle_deg: number;
  crop: [number, number];
  dx_um: number;
  dy_um: number;
  shape_raw: [number, number];
  raw_preview: number[][];
  bandpassed_preview: number[][];
  rotated_preview: number[][];
  signature: number[];
}

export interface GridPreview {
  grid: number[][];
}

export interface AlignResult {
  lag: number;
  ccf: number;
}

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const res = await fetchWithTimeout(`${API_BASE}${path}`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? `${path} failed`);
  }
  return res.json() as Promise<T>;
}

/** Upload an .x3p → a reusable, content-addressed surface handle. */
export async function ingestArtifact(file: File): Promise<ArtifactRef> {
  const form = new FormData();
  form.append("scan", file);
  return postForm<ArtifactRef>("/v1/artifacts", form);
}

/** Form removal + roughness-band isolation → bandpassed handle + grid preview. */
export async function preprocessStep(handle: string): Promise<ArtifactRef & { preview: GridPreview }> {
  const form = new FormData();
  form.append("surface", handle);
  return postForm("/v1/steps/preprocess", form);
}

/** Striae orientation + 1-D signature → handle + the full inline trace preview. */
export async function signatureStep(handle: string): Promise<ArtifactRef & { preview: TracePreview }> {
  const form = new FormData();
  form.append("surface", handle);
  return postForm("/v1/steps/signature", form);
}

/** 256² normalized areal map (impressed) → handle + grid preview. */
export async function arealSignatureStep(
  handle: string,
): Promise<ArtifactRef & { preview: GridPreview }> {
  const form = new FormData();
  form.append("surface", handle);
  return postForm("/v1/steps/areal-signature", form);
}

/** Peak normalized cross-correlation between two 1-D signature handles. */
export async function alignStep(a: string, b: string): Promise<AlignResult> {
  const form = new FormData();
  form.append("a", a);
  form.append("b", b);
  return postForm<AlignResult>("/v1/steps/align", form);
}

export interface ScorerConfig {
  config_hash?: string;
  [k: string]: unknown;
}

/** The deployed scorer config — compare its hash to a baked tour's to detect drift. */
export async function getScorerConfig(): Promise<ScorerConfig | null> {
  try {
    const res = await fetchWithTimeout(
      `${API_BASE}/v1/scorer-config`,
      { cache: "no-store" },
      SHORT_TIMEOUT_MS,
    );
    if (!res.ok) return null;
    return (await res.json()) as ScorerConfig;
  } catch {
    return null;
  }
}
