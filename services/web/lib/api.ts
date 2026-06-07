import type { ComparisonReport } from "./types";

const API_BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export async function getDomains(): Promise<string[]> {
  try {
    const res = await fetch(`${API_BASE}/health`, { cache: "no-store" });
    if (!res.ok) return [];
    const body = await res.json();
    return body.domains ?? [];
  } catch {
    return [];
  }
}

export interface Detection {
  domain: string;
  coherence: number;
}

/** Suggest a mark type from one scan (null if detection is unavailable). */
export async function detectDomain(file: File): Promise<Detection | null> {
  try {
    const form = new FormData();
    form.append("scan", file);
    const res = await fetch(`${API_BASE}/detect`, { method: "POST", body: form });
    if (!res.ok) return null;
    return await res.json();
  } catch {
    return null;
  }
}

export async function compareMarks(
  domain: string,
  marksA: File[],
  marksB: File[],
): Promise<ComparisonReport> {
  const form = new FormData();
  form.append("domain", domain);
  // each mark may be several scans (a bullet's lands); the field repeats
  for (const f of marksA) form.append("mark_a", f);
  for (const f of marksB) form.append("mark_b", f);
  const res = await fetch(`${API_BASE}/compare`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "comparison failed");
  }
  return res.json();
}
