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
  source: string;
  source_ref: string;
  // A scan hangs off exactly one of a bullet land, a cartridge-case mark, or a
  // tool mark (e.g. a screwdriver striation profile).
  land: { id: number } | null;
  mark: { mark_type: string } | null;
  toolmark: { edge: string | null } | null;
}

export type MarkClass = "all" | "bullet" | "cartridge" | "toolmark";

const MARK_TYPE_LABELS: Record<string, string> = {
  breech_face: "Cartridge breech face",
  firing_pin: "Cartridge firing pin",
  ejector: "Cartridge ejector",
  aperture_shear: "Aperture shear",
};

/** The human-readable mark type for a scan (bullet land, cartridge mark, or tool mark). */
export function scanMarkType(scan: Scan): string {
  if (scan.mark) return MARK_TYPE_LABELS[scan.mark.mark_type] ?? scan.mark.mark_type;
  if (scan.toolmark) return "Tool mark";
  if (scan.land) return "Bullet land";
  return "—";
}

const SOURCE_LABELS: Record<string, string> = {
  nbtrd: "NBTRD",
  "csafe-isu": "CSAFE-ISU",
  tmarks: "tmaRks",
};

/** The display label for a scan's source repository (e.g. NBTRD, CSAFE-ISU). */
export function sourceLabel(scan: Scan): string {
  return SOURCE_LABELS[scan.source] ?? scan.source.toUpperCase();
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
  markClass?: MarkClass;
  limit?: number;
  offset?: number;
}): Promise<{ scans: Scan[]; total: number }> {
  if (!catalogConfigured) return { scans: [], total: 0 };
  const { search = "", markClass = "all", limit = 50, offset = 0 } = opts;
  const params = new URLSearchParams({
    select:
      "id,filename,modality,content_hash,lateral_resolution_x,source,source_ref,land(id),mark(mark_type),toolmark(edge)",
    order: "id",
    limit: String(limit),
    offset: String(offset),
  });
  if (search.trim()) params.set("filename", `ilike.*${search.trim()}*`);
  if (markClass === "bullet") params.set("land_id", "not.is.null");
  if (markClass === "cartridge") params.set("mark_id", "not.is.null");
  if (markClass === "toolmark") params.set("toolmark_id", "not.is.null");
  const res = await fetch(`${SB_URL}/rest/v1/scan?${params.toString()}`, {
    headers: { ...authHeaders(), Prefer: "count=exact" },
    cache: "no-store",
  });
  if (!res.ok) return { scans: [], total: 0 };
  const range = res.headers.get("content-range") ?? "*/0";
  const total = Number(range.split("/")[1] || 0);
  return { scans: await res.json(), total };
}
