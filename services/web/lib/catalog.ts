// Read-only client for the hosted benchmark catalog (Supabase PostgREST).
// The anon key is public and the data is locked read-only by row-level security,
// so it is safe to query directly from the browser.

const SB_URL = process.env.NEXT_PUBLIC_SUPABASE_URL ?? "";
const SB_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY ?? "";

export const catalogConfigured = Boolean(SB_URL && SB_KEY);

function authHeaders(): Record<string, string> {
  return { apikey: SB_KEY, Authorization: `Bearer ${SB_KEY}` };
}

export interface Study {
  id: number;
  source: string;
  external_id: string;
  title: string;
  consecutively_manufactured: boolean;
}

export interface Scan {
  id: number;
  filename: string | null;
  modality: string;
  content_hash: string;
  lateral_resolution_x: number | null;
  source_ref: string;
}

export async function getStudies(): Promise<Study[]> {
  if (!catalogConfigured) return [];
  const res = await fetch(
    `${SB_URL}/rest/v1/study?select=id,source,external_id,title,consecutively_manufactured&order=id`,
    { headers: authHeaders(), cache: "no-store" },
  );
  if (!res.ok) return [];
  return res.json();
}

export async function getScans(opts: {
  search?: string;
  limit?: number;
  offset?: number;
}): Promise<{ scans: Scan[]; total: number }> {
  if (!catalogConfigured) return { scans: [], total: 0 };
  const { search = "", limit = 50, offset = 0 } = opts;
  const params = new URLSearchParams({
    select: "id,filename,modality,content_hash,lateral_resolution_x,source_ref",
    order: "id",
    limit: String(limit),
    offset: String(offset),
  });
  if (search.trim()) params.set("filename", `ilike.*${search.trim()}*`);
  const res = await fetch(`${SB_URL}/rest/v1/scan?${params.toString()}`, {
    headers: { ...authHeaders(), Prefer: "count=exact" },
    cache: "no-store",
  });
  if (!res.ok) return { scans: [], total: 0 };
  const range = res.headers.get("content-range") ?? "*/0";
  const total = Number(range.split("/")[1] || 0);
  return { scans: await res.json(), total };
}
