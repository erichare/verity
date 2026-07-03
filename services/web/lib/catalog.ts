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
  // The 3D system the scan was acquired on, when known (e.g. the multi-instrument
  // virtual-kits set). Null for single-instrument sources.
  instrument: { external_id: string | null; manufacturer: string | null } | null;
}

export type MarkClass = "all" | "bullet" | "cartridge" | "toolmark";

const MARK_TYPE_LABELS: Record<string, string> = {
  breech_face: "Cartridge breech face",
  firing_pin: "Cartridge firing pin",
  ejector: "Cartridge ejector",
  full_headstamp: "Cartridge full headstamp",
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
  figshare: "Figshare",
};

/** The display label for a scan's source repository (e.g. NBTRD, CSAFE-ISU). */
export function sourceLabel(scan: Scan): string {
  return SOURCE_LABELS[scan.source] ?? scan.source.toUpperCase();
}

/** The 3D system a scan was acquired on (e.g. EvoFinder), or "—" when unknown. */
export function instrumentLabel(scan: Scan): string {
  if (!scan.instrument) return "—";
  return scan.instrument.external_id ?? scan.instrument.manufacturer ?? "—";
}

/** The distinct instrument names available in the catalog (for the filter). */
export async function getInstruments(): Promise<string[]> {
  if (!catalogConfigured) return [];
  const res = await fetch(
    `${SB_URL}/rest/v1/instrument?select=external_id&order=external_id`,
    { headers: authHeaders(), cache: "no-store" },
  );
  if (!res.ok) return [];
  const rows: { external_id: string | null }[] = await res.json();
  return rows.map((r) => r.external_id).filter((x): x is string => Boolean(x));
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
  instrument?: string;
  limit?: number;
  offset?: number;
  // `error` distinguishes an outage (fetch failed / non-2xx) from a legitimate empty
  // result set, so the UI can show "temporarily unavailable" instead of "no scans".
}): Promise<{ scans: Scan[]; total: number; error?: boolean }> {
  if (!catalogConfigured) return { scans: [], total: 0 };
  const { search = "", markClass = "all", instrument = "", limit = 50, offset = 0 } = opts;
  // Filtering by instrument needs an inner join on the embedded resource; the
  // unfiltered view left-joins it so non-instrument scans still appear.
  const instrumentEmbed = instrument
    ? "instrument!inner(external_id,manufacturer)"
    : "instrument(external_id,manufacturer)";
  const params = new URLSearchParams({
    select: `id,filename,modality,content_hash,lateral_resolution_x,source,source_ref,land(id),mark(mark_type),toolmark(edge),${instrumentEmbed}`,
    order: "id",
    limit: String(limit),
    offset: String(offset),
  });
  if (search.trim()) params.set("filename", `ilike.*${search.trim()}*`);
  if (markClass === "bullet") params.set("land_id", "not.is.null");
  if (markClass === "cartridge") params.set("mark_id", "not.is.null");
  if (markClass === "toolmark") params.set("toolmark_id", "not.is.null");
  if (instrument) params.set("instrument.external_id", `eq.${instrument}`);
  try {
    const res = await fetch(`${SB_URL}/rest/v1/scan?${params.toString()}`, {
      headers: { ...authHeaders(), Prefer: "count=exact" },
      cache: "no-store",
    });
    if (!res.ok) return { scans: [], total: 0, error: true };
    const range = res.headers.get("content-range") ?? "*/0";
    const total = Number(range.split("/")[1] || 0);
    return { scans: await res.json(), total };
  } catch {
    // Network failure (DNS, CORS, offline) — an outage, not an empty result.
    return { scans: [], total: 0, error: true };
  }
}
