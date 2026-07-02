// The Studio "run": a forensic comparison decomposed into the ordered pipeline stages
// the full-screen theater animates (app.verity.codes). Every headline number here is the
// engine's — score, LR, CI, AUC, Cllr, attribution counts all come straight from the real
// comparison report (gallery.json today; tour.json once `verity-build-tour` runs). The
// per-stage *imagery* (the form-removal morph, the rotate→flatten, the CMR vote scatter) is
// a faithful visualization of those real artifacts, never fabricated evidence.

import manifest from "./gallery.json";
import { GALLERY_COMPARISONS, getSpecimen } from "./gallery";
import { formatLRx } from "./format";
import type {
  AttributionRegion,
  ComparisonReport,
  GalleryCalibration,
  GalleryCmr,
  GalleryComparison,
  GallerySignatures,
  GalleryVote,
  MarkDomain,
} from "./types";

const CONFIG_HASH = (manifest as { version: string }).version;

// ── Stage model ──────────────────────────────────────────────────────────────

export type StageId =
  | "ingest"
  | "preprocess"
  | "orient"
  | "areal"
  | "align"
  | "cmr"
  | "attribution"
  | "calibrate"
  | "verdict";

export interface Readout {
  label: string;
  value: string;
}

// A rendered consensus-scatter vote: plot coords in [0,1], consensus membership, and (real
// votes only) the labelled raw values for the mouseover. Real votes come from the engine
// (`GalleryCmr`); synthetic ones are generated for the upload fallback (no `tip`).
export type Vote = GalleryVote;

export type StageDisplay =
  | { type: "surfaces"; variant: "raw" | "bandpassed" | "attribution" }
  | { type: "areal"; grid: number[][] }
  | {
      type: "signatures";
      a: number[];
      b: number[];
      bandsA: GallerySignatures["bandsA"];
      bandsB: GallerySignatures["bandsB"];
    }
  | {
      type: "cmr";
      relation: "KM" | "KNM";
      votes: Vote[];
      nConsensus: number;
      axisX: string;
      axisY: string;
      // True when the votes are the synthetic upload fallback (no real per-window votes from
      // the live API) — the renderer must badge the plot as a schematic, not evidence.
      schematic?: boolean;
    }
  | { type: "calibration"; km: number[]; knm: number[]; score: number; lrLabel: string }
  | { type: "verdict"; report: ComparisonReport };

export interface Stage {
  id: StageId;
  num: number;
  label: string;
  caption: string;
  why: string;
  readouts: Readout[];
  display: StageDisplay;
  recede: boolean; // does the 3-D scene fall back behind a 2-D overlay?
}

export interface StudioRun {
  id: string;
  domain: MarkDomain;
  relation: "KM" | "KNM";
  provenance: "gallery" | "upload";
  aLabel: string;
  bLabel: string;
  gridA: number[][];
  gridB: number[][];
  // The ingest view: the raw land scan WITH the bullet's gross form (real measured curvature),
  // before form removal. Falls back to gridA (flat) when no raw source is available.
  rawFormA: number[][];
  rawFormB: number[][];
  bandA: number[][];
  bandB: number[][];
  regionsA: AttributionRegion[];
  regionsB: AttributionRegion[];
  report: ComparisonReport;
  signatures?: GallerySignatures;
  calibration?: GalleryCalibration;
  // Real per-window CMR votes for the consensus scatter (curated gallery only).
  cmr?: GalleryCmr;
  // True when the 3-D grids were tiled from the 1-D signature purely for display (toolmarks
  // ship no 2-D scan) — the ingest stage must say so instead of claiming a measured surface.
  ridgedFromSignature?: boolean;
  // Real intermediates from the live /v1/steps walk (absent on the curated gallery path).
  align?: { lag: number; ccf: number };
  arealRaw?: number[][];
  tiltDeg?: number;
  stages: Stage[];
  configHash: string;
}

// ── Deterministic helpers (stable across renders → no hydration drift) ────────

function hashSeed(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

function mulberry32(seed: number): () => number {
  let a = seed;
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function mean(grid: number[][]): number {
  let s = 0;
  let n = 0;
  for (const row of grid)
    for (const v of row)
      if (Number.isFinite(v)) {
        s += v;
        n++;
      }
  return n ? s / n : 0;
}

// Center a [0,1] preview around zero and amplify a touch so the relief reads in 3-D.
function center(grid: number[][], gain = 1.7): number[][] {
  const m = mean(grid);
  return grid.map((row) => row.map((v) => (Number.isFinite(v) ? (v - m) * gain : 0)));
}

// Rescale a grid to [0,1] for the viridis areal heatmap.
function normalize01(grid: number[][]): number[][] {
  let lo = Infinity;
  let hi = -Infinity;
  for (const row of grid)
    for (const v of row)
      if (Number.isFinite(v)) {
        if (v < lo) lo = v;
        if (v > hi) hi = v;
      }
  const span = hi - lo || 1;
  return grid.map((row) => row.map((v) => (Number.isFinite(v) ? (v - lo) / span : 0)));
}

// A separable box blur — the "low-pass / form" component of a surface.
function blur(grid: number[][], radius: number): number[][] {
  const rows = grid.length;
  const cols = grid[0]?.length ?? 0;
  const tmp = grid.map((r) => r.slice());
  const out = grid.map((r) => r.slice());
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      let s = 0;
      let n = 0;
      for (let k = -radius; k <= radius; k++) {
        const xx = x + k;
        if (xx >= 0 && xx < cols) {
          s += grid[y][xx];
          n++;
        }
      }
      tmp[y][x] = s / (n || 1);
    }
  }
  for (let y = 0; y < rows; y++) {
    for (let x = 0; x < cols; x++) {
      let s = 0;
      let n = 0;
      for (let k = -radius; k <= radius; k++) {
        const yy = y + k;
        if (yy >= 0 && yy < rows) {
          s += tmp[yy][x];
          n++;
        }
      }
      out[y][x] = s / (n || 1);
    }
  }
  return out;
}

// Roughness = surface − form (a visualization of ISO form removal + roughness band).
function highpass(grid: number[][]): number[][] {
  const size = Math.max(grid.length, grid[0]?.length ?? 1);
  const lo = blur(grid, Math.max(2, Math.round(size / 7)));
  return grid.map((row, y) => row.map((v, x) => (v - lo[y][x]) * 2.2));
}

// Toolmarks ship a 1-D striation profile, not a 2-D scan — tile it into a ridged surface
// (the striae run down the sample) so the 3-D stage reads as machined metal.
function ridgeFromSignature(sig: number[], cols = 60, rows = 48, seed = 1): number[][] {
  const rng = mulberry32(seed);
  const step = Math.max(1, Math.floor(sig.length / cols));
  const lane: number[] = [];
  for (let i = 0; i < cols; i++) lane.push(sig[i * step] ?? 0);
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of lane) {
    if (v < lo) lo = v;
    if (v > hi) hi = v;
  }
  const span = hi - lo || 1;
  const norm = lane.map((v) => (v - lo) / span - 0.5);
  const out: number[][] = [];
  for (let y = 0; y < rows; y++) {
    const jitter = (rng() - 0.5) * 0.06;
    out.push(norm.map((v) => (v + jitter) * 1.4));
  }
  return out;
}

// Synthetic votes for the upload fallback only (no real per-window votes from the live API):
// a central consensus blob + scattered dissent in [0,1], mirroring the real-vote layout so the
// renderer is identical. No `tip` — uploads carry no measured registration values to show.
function generateVotes(nConsensus: number, seed: number): Vote[] {
  const rng = mulberry32(seed);
  const BUDGET = 46;
  const cons = Math.max(0, Math.min(40, nConsensus));
  const clamp = (v: number) => Math.min(0.98, Math.max(0.02, v));
  const gauss = () => rng() + rng() + rng() - 1.5; // ~N(0, ~0.5)
  const votes: Vote[] = [];
  for (let i = 0; i < BUDGET; i++) {
    const consensus = i < cons;
    if (consensus) {
      votes.push({
        consensus,
        x: clamp(0.5 + gauss() * 0.08),
        y: clamp(0.55 + gauss() * 0.08),
        corr: 0.7 + rng() * 0.25, // plausible strength for the opacity encoding (no real value)
      });
    } else {
      votes.push({
        consensus,
        x: clamp(0.06 + rng() * 0.88),
        y: clamp(0.08 + rng() * 0.86),
        corr: 0.25 + rng() * 0.5,
      });
    }
  }
  return votes;
}

// ── Captions (forensic-examiner voice) ───────────────────────────────────────

const COPY: Record<StageId, { label: string; caption: string; why: string }> = {
  ingest: {
    label: "Raw",
    caption: "Two surface scans, measured to the sub-micron.",
    why: "Before any judgment, we look at the raw topography — the evidence mark and the one it is compared against.",
  },
  preprocess: {
    label: "Preprocess",
    caption: "Subtract the gross shape; keep what the tool left behind.",
    why: "Removing the curve of the barrel or case leaves only the fine working marks that carry source information.",
  },
  orient: {
    label: "Orient",
    caption: "The striae are rotated upright and averaged into one profile.",
    why: "A one-dimensional signature of the cut, independent of how the scan happened to be oriented.",
  },
  areal: {
    label: "Areal map",
    caption: "The breech-face impression is flattened into a calibrated areal map.",
    why: "Every pixel becomes a normalized height, ready for cell-by-cell comparison.",
  },
  align: {
    label: "Align",
    caption: "Slid to the single best alignment — the agreement measured there.",
    why: "Matched striae line up vertically and in parallel; that consistent correspondence is what a real match looks like.",
  },
  cmr: {
    label: "Consensus",
    caption: "Comparison windows vote on how to line the marks up.",
    why: "When they converge on one alignment, that agreement — not raw similarity — is the evidence.",
  },
  attribution: {
    label: "Attribution",
    caption: "The exact regions that drove the result, on both marks.",
    why: "Nothing is hidden: the matched topography is shown at its position on each surface.",
  },
  calibrate: {
    label: "Calibrate",
    caption: "The score is placed against a reference population.",
    why: "Known same-source and known different-source comparisons calibrate the strength — not the raw similarity.",
  },
  verdict: {
    label: "Verdict",
    caption: "The weight of evidence — a calibrated likelihood ratio, with its uncertainty.",
    why: "Verity reports it; it never decides. This is a likelihood ratio, not the probability of a match.",
  },
};

// ── Run construction ─────────────────────────────────────────────────────────

function dims(grid: number[][]): string {
  return `${grid[0]?.length ?? 0}×${grid.length}`;
}

function buildStages(run: Omit<StudioRun, "stages">): Stage[] {
  const { domain, relation, report, regionsA, gridA, signatures, calibration } = run;
  const stages: Stage[] = [];
  const push = (
    id: StageId,
    display: StageDisplay,
    readouts: Readout[],
    recede: boolean,
    copy?: Partial<Pick<Stage, "caption" | "why">>,
  ) => {
    stages.push({ id, num: stages.length + 1, ...COPY[id], ...copy, readouts, display, recede });
  };

  // When the 3-D surface was tiled from the 1-D signature (toolmarks: no 2-D scan), say so —
  // and report the real profile length, not the display tiling's dimensions.
  const ridgedSig = run.ridgedFromSignature ? signatures : undefined;
  push(
    "ingest",
    { type: "surfaces", variant: "raw" },
    [
      ridgedSig
        ? { label: "signature", value: `${ridgedSig.a.length}-sample profile` }
        : { label: "resolution", value: dims(gridA) },
      { label: "domain", value: domain },
      { label: "role", value: "evidence vs reference" },
    ],
    false,
    ridgedSig
      ? { caption: "A measured striation profile, rendered as a ridged surface for display." }
      : undefined,
  );

  push(
    "preprocess",
    { type: "surfaces", variant: "bandpassed" },
    [
      { label: "form", value: "ISO polynomial" },
      { label: "band", value: "roughness λ" },
    ],
    false,
  );

  if (domain === "impressed") {
    push(
      "areal",
      { type: "areal", grid: run.arealRaw ?? normalize01(gridA) },
      [
        { label: "areal map", value: dims(run.arealRaw ?? gridA) },
        { label: "normalize", value: "unit-norm" },
      ],
      true,
    );
  } else if (signatures) {
    const orientReadouts: Readout[] = [{ label: "signature", value: `${signatures.a.length} samples` }];
    if (run.tiltDeg != null) orientReadouts.push({ label: "striae tilt", value: `${run.tiltDeg.toFixed(1)}°` });
    push(
      "orient",
      { type: "signatures", a: signatures.a, b: signatures.b, bandsA: [], bandsB: [] },
      orientReadouts,
      true,
    );
    const alignReadouts: Readout[] = run.align
      ? [
          { label: "peak CCF", value: run.align.ccf.toFixed(3) },
          { label: "lag", value: `${run.align.lag}` },
        ]
      : [{ label: "matched striae", value: `${Math.min(signatures.bandsA.length, signatures.bandsB.length)}` }];
    push(
      "align",
      {
        type: "signatures",
        a: signatures.a,
        b: signatures.b,
        bandsA: signatures.bandsA,
        bandsB: signatures.bandsB,
      },
      alignReadouts,
      true,
    );
  }

  // Prefer the engine's REAL per-window votes (curated gallery); fall back to synthetic only
  // for live uploads, where the API exposes no per-window votes.
  const realCmr = run.cmr;
  const nConsensus =
    realCmr?.nConsensus ??
    (domain === "striated" ? regionsA.length || Math.round(report.score) : Math.round(report.score));
  push(
    "cmr",
    realCmr
      ? {
          type: "cmr",
          relation,
          votes: realCmr.votes,
          nConsensus,
          axisX: realCmr.axisX,
          axisY: realCmr.axisY,
        }
      : {
          type: "cmr",
          relation,
          votes: generateVotes(nConsensus, hashSeed(run.id)),
          nConsensus,
          axisX: "proposed shift",
          axisY: "proposed twist",
          schematic: true,
        },
    // Real votes → the engine's measured consensus count. Synthetic fallback → the count is
    // itself a proxy derived from the report (attribution regions or the CMR score): say so.
    [
      realCmr
        ? { label: "congruent regions", value: `${nConsensus}` }
        : { label: "regions (derived)", value: `${nConsensus}` },
    ],
    true,
    realCmr
      ? {
          caption: `${realCmr.votes.length} comparison windows vote on how to line the marks up.`,
          why:
            realCmr.kind === "areal"
              ? "When they converge on one shift and twist, that agreement — not raw similarity — is the evidence."
              : "When they converge on one alignment, that agreement — not raw similarity — is the evidence.",
        }
      : {
          caption: "Comparison windows vote on how to line the marks up — drawn here as a schematic.",
          why: "The live API does not expose per-window votes for uploads, so this scatter illustrates the mechanism. The region count and verdict are derived from the real report.",
        },
  );

  if (regionsA.length > 0) {
    push(
      "attribution",
      { type: "surfaces", variant: "attribution" },
      [{ label: "regions", value: `${regionsA.length}` }],
      false,
    );
  }

  if (calibration) {
    push(
      "calibrate",
      {
        type: "calibration",
        km: calibration.km,
        knm: calibration.knm,
        score: calibration.score,
        lrLabel: calibration.lrLabel,
      },
      [
        { label: "score", value: report.score.toFixed(3) },
        { label: "reference AUC", value: report.reference.auc.toFixed(3) },
        { label: "reference", value: report.reference.name },
      ],
      true,
    );
  }

  push(
    "verdict",
    { type: "verdict", report },
    [
      { label: "LR", value: formatLRx(report.likelihood_ratio) },
      { label: "log10 LR", value: report.log10_lr.toFixed(2) },
      { label: "verbal", value: report.verbal },
    ],
    true,
  );

  return stages;
}

interface RunInput {
  id: string;
  domain: MarkDomain;
  relation: "KM" | "KNM";
  provenance: "gallery" | "upload";
  aLabel: string;
  bLabel: string;
  report: ComparisonReport;
  signatures?: GallerySignatures;
  calibration?: GalleryCalibration;
  cmr?: GalleryCmr;
  // Real intermediates from the live /v1/steps walk; each falls back to a derivation.
  rawA?: number[][];
  rawB?: number[][];
  bandA?: number[][];
  bandB?: number[][];
  align?: { lag: number; ccf: number };
  arealRaw?: number[][];
  tiltDeg?: number;
}

function makeRun(input: RunInput): StudioRun {
  const { report, signatures } = input;
  const previews = report.previews;
  let gridA: number[][];
  let gridB: number[][];
  let ridgedFromSignature = false;
  if (input.rawA && input.rawB) {
    gridA = center(input.rawA);
    gridB = center(input.rawB);
  } else if (previews) {
    gridA = center(previews.a);
    gridB = center(previews.b);
  } else if (signatures) {
    const s = hashSeed(input.id);
    gridA = ridgeFromSignature(signatures.a, 60, 48, s);
    gridB = ridgeFromSignature(signatures.b, 60, 48, s + 1);
    ridgedFromSignature = true;
  } else {
    gridA = [[0, 0], [0, 0]];
    gridB = [[0, 0], [0, 0]];
  }
  // Ingest view: the raw scan with the bullet's gross form. Prefer a real raw source — the
  // live /v1/steps raw_preview, or the gallery's raw_a/raw_b — so the curvature is the
  // measured one; otherwise fall back to the (flat) main grid, never a fabricated shape.
  const rawFormA = input.rawA ? center(input.rawA) : previews?.raw_a ? center(previews.raw_a) : gridA;
  const rawFormB = input.rawB ? center(input.rawB) : previews?.raw_b ? center(previews.raw_b) : gridB;
  const partial: Omit<StudioRun, "stages"> = {
    ...input,
    gridA,
    gridB,
    ridgedFromSignature,
    rawFormA,
    rawFormB,
    bandA: input.bandA ? center(input.bandA) : highpass(gridA),
    bandB: input.bandB ? center(input.bandB) : highpass(gridB),
    regionsA: report.attribution ?? [],
    regionsB: report.attribution_b ?? [],
    configHash: CONFIG_HASH,
  };
  return { ...partial, stages: buildStages(partial) };
}

// The full-field areal map is emitted once per A specimen (it's identical across that A's
// comparisons), so index it by aId and let every comparison sharing that A reuse it.
const AREAL_BY_AID: Record<string, number[][]> = {};
for (const c of GALLERY_COMPARISONS) {
  const ar = c.report.previews?.areal_a;
  if (ar && !AREAL_BY_AID[c.aId]) AREAL_BY_AID[c.aId] = ar;
}

function comparisonToRun(c: GalleryComparison): StudioRun {
  const a = getSpecimen(c.aId);
  const b = getSpecimen(c.bId);
  return makeRun({
    id: c.id,
    domain: (a?.domain ?? c.report.domain) as MarkDomain,
    relation: c.relation,
    provenance: "gallery",
    aLabel: a?.label ?? c.aId,
    bLabel: b?.label ?? c.bId,
    report: c.report,
    signatures: c.signatures,
    calibration: c.calibration,
    cmr: c.cmr,
    // Impressed: the full-field native areal map for the flat heatmap stage (whole breech face).
    arealRaw: c.report.previews?.areal_a ?? AREAL_BY_AID[c.aId],
  });
}

// All curated runs, indexed by `${domain}:${relation}` for the tray + match toggle.
export const TOUR_RUNS: Record<string, StudioRun> = Object.fromEntries(
  GALLERY_COMPARISONS.map((c) => {
    const run = comparisonToRun(c);
    return [`${run.domain}:${run.relation}`, run] as const;
  }),
);

export const TOUR_DOMAINS: MarkDomain[] = ["striated", "impressed", "toolmark"];

export const DOMAIN_LABEL: Record<string, string> = {
  striated: "Bullet",
  impressed: "Cartridge",
  toolmark: "Toolmark",
};

export function tourRun(domain: MarkDomain, relation: "KM" | "KNM"): StudioRun | undefined {
  return TOUR_RUNS[`${domain}:${relation}`] ?? TOUR_RUNS[`${domain}:KM`];
}

export const FLAGSHIP: StudioRun | undefined = tourRun("striated", "KM");

// Extras gathered from the live /v1/steps walk on an uploaded pair (any may be absent —
// each one missing falls back to a derivation, so a partial walk still produces a full run).
export interface LiveExtras {
  rawA?: number[][];
  rawB?: number[][];
  bandA?: number[][];
  bandB?: number[][];
  signatures?: GallerySignatures;
  align?: { lag: number; ccf: number };
  arealRaw?: number[][];
  tiltDeg?: number;
  idSuffix?: string;
}

// Build a run from a live upload. With no extras it uses just the lean /compare report
// (previews + attribution); with the /v1/steps artifacts it shows real raw/bandpassed
// grids, the real 1-D signature, the real peak CCF, and the real areal map.
export function uploadRunRich(
  report: ComparisonReport,
  domain: MarkDomain,
  extras: LiveExtras = {},
): StudioRun {
  return makeRun({
    id: `upload-${extras.idSuffix ?? "0"}`,
    domain,
    relation: "KM",
    provenance: "upload",
    aLabel: "Mark A",
    bLabel: "Mark B",
    report,
    signatures: extras.signatures,
    rawA: extras.rawA,
    rawB: extras.rawB,
    bandA: extras.bandA,
    bandB: extras.bandB,
    align: extras.align,
    arealRaw: extras.arealRaw,
    tiltDeg: extras.tiltDeg,
  });
}

export function uploadRun(report: ComparisonReport, domain: MarkDomain): StudioRun {
  return uploadRunRich(report, domain);
}
