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

export async function compareMarks(
  domain: string,
  markA: File,
  markB: File,
): Promise<ComparisonReport> {
  const form = new FormData();
  form.append("domain", domain);
  form.append("mark_a", markA);
  form.append("mark_b", markB);
  const res = await fetch(`${API_BASE}/compare`, { method: "POST", body: form });
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "comparison failed");
  }
  return res.json();
}
