"use client";

import dynamic from "next/dynamic";
import { useState, type ReactNode } from "react";
import methodData from "@/lib/method-data.json";
import cmrValidation from "@/lib/cmr-validation.json";
import { Reveal } from "@/components/Reveal";
import { Heatmap } from "@/components/method/Heatmap";
import { SignaturePlot } from "@/components/method/SignaturePlot";
import { AlignedSignatures } from "@/components/method/AlignedSignatures";
import { CalibrationChart } from "@/components/method/CalibrationChart";
import { SiteNav } from "@/components/SiteNav";

const SurfaceViewer = dynamic(() => import("@/components/three/SurfaceViewer"), { ssr: false });

interface Region {
  x: number;
  y: number;
  w: number;
  h: number;
  x_frac: number;
  y_frac: number;
  w_frac: number;
  h_frac: number;
  corr: number;
}
interface Example {
  sameSource: boolean;
  label: string;
  sublabel: string;
  scan: number[][];
  leveled: number[][];
  roughness: number[][];
  signatureA: number[];
  signatureB: number[];
  lag: number;
  bandsA: Region[];
  bandsB: Region[];
  score: number;
  scoreKind: string;
  lr: number;
  log10_lr: number;
  verbal: string;
  lrBound: number | null;
  reference: { name: string; auc: number; cllr: number; nKm: number; nKnm: number };
}
interface Calibration {
  km: number[];
  knm: number[];
  auc: number;
  cllr: number;
  cllrMin: number;
  name: string;
  nKm: number;
  nKnm: number;
}
interface OtherEx {
  domain: "impressed" | "striated";
  bandsA: Region[];
  bandsB: Region[];
  scanA?: number[][];
  scanB?: number[][];
  signatureA?: number[];
  signatureB?: number[];
  score: number;
  lr: number;
  verbal: string;
  reference: { name: string; auc: number };
}
interface Others {
  cartridge?: OtherEx;
  screwdriver?: OtherEx;
}
const data = methodData as unknown as {
  km: Example;
  knm: Example;
  calibration: Calibration;
  others?: Others;
};

interface CmrReduction {
  modality: string;
  label: string;
  reduction: string;
  specialist: string;
  reference: string;
  n_km: number;
  n_knm: number;
  in_sample_auc: number;
  source_disjoint: { cllr: number; cllr_sd: number; auc: number; n_folds: number };
}
const cmr = cmrValidation as unknown as {
  scorer_config_hash: string;
  claim: string;
  reductions: CmrReduction[];
  note: string;
};
const cmrByModality: Record<string, CmrReduction> = Object.fromEntries(
  cmr.reductions.map((r) => [r.modality, r]),
);

function formatLR(lr: number): string {
  const human = (x: number) =>
    x >= 100 ? Math.round(x).toLocaleString("en-US") : x.toFixed(1).replace(/\.0$/, "");
  return lr >= 1 ? `${human(lr)}×` : `1 / ${human(1 / lr)}`;
}

function Frame({ children, className }: { children: ReactNode; className?: string }) {
  return (
    <div className={`overflow-hidden rounded-xl border border-border bg-foreground/[0.02] ${className ?? ""}`}>
      {children}
    </div>
  );
}

function Stage({
  n,
  title,
  children,
  viz,
}: {
  n: string;
  title: string;
  children: ReactNode;
  viz: ReactNode;
}) {
  return (
    <Reveal className="mt-16 grid gap-6 sm:mt-24 sm:grid-cols-[1fr_1.1fr] sm:items-center sm:gap-10">
      <div>
        <div className="font-display text-sm font-semibold text-accent">{n}</div>
        <h3 className="mt-1 font-display text-2xl font-medium text-foreground sm:text-3xl">{title}</h3>
        <div className="mt-3 space-y-3 text-sm leading-relaxed text-foreground/80">{children}</div>
      </div>
      <div>{viz}</div>
    </Reveal>
  );
}

// ---- Multi-modal swap -------------------------------------------------------

type ModalityKey = "bullet" | "cartridge" | "screwdriver";

interface ModalityPanel {
  badge: string;
  lr: number;
  verbal: string;
  regions: number;
  regionWord: string;
  registration: string;
  refName: string;
  auc: number;
  nKm: number;
  nKnm: number;
  viz: ReactNode;
}

const MODALITY_PILLS: { key: ModalityKey; pill: string }[] = [
  { key: "bullet", pill: "Bullet land" },
  { key: "cartridge", pill: "Cartridge case" },
  { key: "screwdriver", pill: "Screwdriver" },
];

// Resolve the comparison panel for the active mark. Each modality shows the SAME
// concept — congruent matching regions — rendered in its natural geometry: a 1-D
// aligned-signature view for striated marks, the 2-D breech-face surfaces for the
// impression. Verdict (LR, verbal) comes from the real example in method-data;
// the reference's AUC + pair counts come from cmr-validation.json so the card can
// never contradict the source-disjoint table further down the page.
function buildPanel(key: ModalityKey, others?: Others): ModalityPanel | null {
  if (key === "bullet") {
    const r = cmrByModality["striated"];
    const ex = data.km;
    return {
      badge: "Striated · 1-D signature",
      lr: ex.lr,
      verbal: ex.verbal,
      regions: ex.bandsA.length,
      regionWord: "congruent matching regions",
      registration: "a single 1-D shift",
      refName: ex.reference.name,
      auc: r.in_sample_auc,
      nKm: r.n_km,
      nKnm: r.n_knm,
      viz: (
        <Frame className="p-3">
          <AlignedSignatures
            a={ex.signatureA}
            b={ex.signatureB}
            bandsA={ex.bandsA}
            bandsB={ex.bandsB}
            className="h-48 sm:h-56"
          />
        </Frame>
      ),
    };
  }
  const c = others?.cartridge;
  if (key === "cartridge" && c?.scanA && c.scanB) {
    const scanA = c.scanA;
    const scanB = c.scanB;
    const r = cmrByModality["impressed"];
    return {
      badge: "Impressed · 2-D areal",
      lr: c.lr,
      verbal: c.verbal,
      regions: c.bandsA.length,
      regionWord: "congruent matching cells",
      registration: "a 2-D shift + rotation",
      refName: c.reference.name,
      auc: r.in_sample_auc,
      nKm: r.n_km,
      nKnm: r.n_knm,
      viz: (
        <div className="grid grid-cols-2 gap-3">
          <Frame className="h-48 sm:h-56">
            <SurfaceViewer grid={scanA} regions={c.bandsA} className="h-full w-full" />
          </Frame>
          <Frame className="h-48 sm:h-56">
            <SurfaceViewer grid={scanB} regions={c.bandsB} className="h-full w-full" />
          </Frame>
        </div>
      ),
    };
  }
  const s = others?.screwdriver;
  if (key === "screwdriver" && s?.signatureA && s.signatureB) {
    const sigA = s.signatureA;
    const sigB = s.signatureB;
    const r = cmrByModality["striated-toolmark"];
    return {
      badge: "Striated · 1-D toolmark",
      lr: s.lr,
      verbal: s.verbal,
      regions: s.bandsA.length,
      regionWord: "matched striae",
      registration: "a single 1-D shift",
      refName: s.reference.name,
      auc: r.in_sample_auc,
      nKm: r.n_km,
      nKnm: r.n_knm,
      viz: (
        <Frame className="p-3">
          <AlignedSignatures
            a={sigA}
            b={sigB}
            bandsA={s.bandsA}
            bandsB={s.bandsB}
            className="h-48 sm:h-56"
          />
        </Frame>
      ),
    };
  }
  return null;
}

function ModalitySwap({ others }: { others?: Others }) {
  const [modality, setModality] = useState<ModalityKey>("bullet");
  const panel = buildPanel(modality, others);
  const positive = (panel?.lr ?? 1) >= 1;

  return (
    <section className="rise mt-12">
      <div className="text-center">
        <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          One pipeline · three marks
        </span>
      </div>

      <div className="mt-5 flex justify-center">
        <div className="inline-flex rounded-full border border-border bg-foreground/[0.03] p-1 text-sm">
          {MODALITY_PILLS.map(({ key, pill }) => (
            <button
              key={key}
              onClick={() => setModality(key)}
              aria-pressed={modality === key}
              className={`rounded-full px-4 py-1.5 font-medium transition ${
                modality === key
                  ? "bg-gradient-to-r from-indigo-500 to-cyan-400 text-slate-950"
                  : "text-foreground/70 hover:text-foreground"
              }`}
            >
              {pill}
            </button>
          ))}
        </div>
      </div>

      {panel && (
        <div className="glass mt-6 rounded-2xl p-5 sm:p-8">
          <div className="flex items-center justify-between gap-3">
            <span className="rounded-full bg-foreground/[0.06] px-2.5 py-1 text-[11px] uppercase tracking-wider text-muted">
              {panel.badge}
            </span>
            <span className="text-xs text-muted">
              {panel.regions} {panel.regionWord}
            </span>
          </div>

          <div className="mt-4">{panel.viz}</div>
          <p className="mt-2 px-1 text-xs text-muted">
            <span style={{ color: "var(--accent)" }}>mark A</span> vs{" "}
            <span style={{ color: "var(--accent-2)" }}>mark B</span> — registered by{" "}
            {panel.registration}, then scored by the same congruent-regions algorithm.
          </p>

          <div className="mt-5 flex flex-wrap items-end justify-between gap-4 border-t border-border pt-4">
            <div>
              <p className="text-[11px] uppercase tracking-wider text-muted">Likelihood ratio</p>
              <p
                className={`font-mono text-4xl font-semibold sm:text-5xl ${
                  positive ? "accent-text" : "text-rose-500 dark:text-rose-300"
                }`}
              >
                {formatLR(panel.lr)}
              </p>
              <p className="mt-1 text-sm text-foreground/80">{panel.verbal}.</p>
            </div>
            <p className="max-w-[16rem] text-right text-xs leading-snug text-muted">
              {panel.refName}
              <br />
              AUC {panel.auc.toFixed(3)} · {panel.nKm.toLocaleString("en-US")} +{" "}
              {panel.nKnm.toLocaleString("en-US")} reference pairs
            </p>
          </div>
        </div>
      )}
    </section>
  );
}

export default function MethodPage() {
  const [mode, setMode] = useState<"km" | "knm">("km");
  const ex = data[mode];
  const cal = data.calibration;
  const others = data.others;
  const positive = ex.log10_lr > 0;

  return (
    <>
      <SiteNav />

      <main className="mx-auto w-full max-w-4xl px-6 pb-24 pt-28 sm:pt-36">
        {/* Intro */}
        <section className="rise">
          <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            How it works
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold tracking-tight sm:text-6xl">
            One method, <span className="accent-text">end to end</span>
          </h1>
          <p className="mt-5 max-w-2xl text-lg leading-relaxed text-foreground/80">
            Verity turns a pair of 3-D surface scans into a calibrated likelihood ratio — and shows
            its work at every step. The <strong className="text-foreground">same pipeline</strong>{" "}
            weighs three different kinds of mark; swap between them to see three real, calibrated
            verdicts from one algorithm — then follow the entire pipeline, step by step, on a bullet.
          </p>
        </section>

        {/* Multi-modal swap — the same method on three marks */}
        <ModalitySwap others={others} />

        {/* The full pipeline, on a bullet */}
        <Reveal className="mt-20 sm:mt-28">
          <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            How the bullet was scored
          </span>
          <h2 className="mt-5 font-display text-3xl font-medium text-foreground sm:text-4xl">
            The full pipeline, <span className="accent-text">step by step</span>
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-relaxed text-foreground/80 sm:text-base">
            Here is the entire machine on a real Hamby-252 bullet — six steps from raw scan to
            calibrated evidence. Flip between two bullets fired from <em>the same</em> firearm and two
            from <em>different</em> firearms, and watch the same algorithm reach opposite conclusions.
          </p>

          <div className="mt-6">
            <div className="inline-flex rounded-full border border-border bg-foreground/[0.03] p-1 text-sm">
              {(["km", "knm"] as const).map((k) => (
                <button
                  key={k}
                  onClick={() => setMode(k)}
                  className={`rounded-full px-4 py-1.5 font-medium transition ${
                    mode === k ? "bg-gradient-to-r from-indigo-500 to-cyan-400 text-slate-950" : "text-foreground/70 hover:text-foreground"
                  }`}
                >
                  {k === "km" ? "Same firearm" : "Different firearms"}
                </button>
              ))}
            </div>
            <div className="glass mt-4 flex flex-wrap items-baseline justify-between gap-3 rounded-2xl p-5">
              <div>
                <p className="text-xs uppercase tracking-wider text-muted">{ex.sublabel}</p>
                <p className={`font-mono text-4xl font-semibold ${positive ? "accent-text" : "text-rose-500 dark:text-rose-300"}`}>
                  {formatLR(ex.lr)}
                </p>
              </div>
              <p className="max-w-xs text-sm leading-relaxed text-foreground/70">
                {ex.verbal}. The reference can support at most{" "}
                <strong className="text-foreground">{cal.nKm}:1</strong> either way (the bound), and the
                same algorithm produced this with zero parameters tuned to these bullets.
              </p>
            </div>
          </div>
        </Reveal>

        {/* Stage 1 */}
        <Stage
          n="01"
          title="Every mark is a surface"
          viz={
            <Frame className="h-72">
              <SurfaceViewer grid={ex.scan} className="h-full w-full" />
            </Frame>
          }
        >
          <p>
            A bullet land, a breech face, a toolmark — each is a 3-D height field <code>z(x, y)</code>,
            measured as an X3P topography scan. Verity never looks at a photograph; it works on the
            geometry itself, so lighting and color are irrelevant. Drag to rotate the real scan.
          </p>
        </Stage>

        {/* Stage 2 */}
        <Stage
          n="02"
          title="Isolate what individualizes"
          viz={
            <div className="grid grid-cols-2 gap-3">
              <div>
                <Frame className="aspect-square">
                  <Heatmap grid={ex.leveled} className="h-full w-full" />
                </Frame>
                <p className="mt-1.5 text-center text-xs text-muted">leveled scan</p>
              </div>
              <div>
                <Frame className="aspect-square">
                  <Heatmap grid={ex.roughness} className="h-full w-full" />
                </Frame>
                <p className="mt-1.5 text-center text-xs text-muted">individualizing band</p>
              </div>
            </div>
          }
        >
          <p>
            The overall <em>form</em> (the curve of the barrel) and broad <em>waviness</em> are shared
            by many sources — they hide the signal. An ISO&nbsp;16610 band-pass removes them and keeps
            the fine roughness band that the specific tool left behind.
          </p>
        </Stage>

        {/* Stage 3 */}
        <Stage
          n="03"
          title="Reduce to a signature"
          viz={
            <Frame className="p-3">
              <SignaturePlot values={ex.signatureA} className="h-36" />
            </Frame>
          }
        >
          <p>
            The striae run in one direction. Verity orients them, collapses along them, and crops the
            high, common groove shoulders — leaving a 1-D <strong className="text-foreground">striation
            signature</strong>, the object we actually compare. (Impressed marks keep a 2-D areal map
            instead; the rest of the pipeline is identical.)
          </p>
        </Stage>

        {/* Stage 4 */}
        <Stage
          n="04"
          title="Find the regions that agree"
          viz={
            <Frame className="p-3">
              <AlignedSignatures
                a={ex.signatureA}
                b={ex.signatureB}
                bandsA={ex.bandsA}
                bandsB={ex.bandsB}
                className="h-48"
              />
              <p className="mt-1 px-1 text-xs text-muted">
                {ex.bandsA.length} congruent matching {ex.bandsA.length === 1 ? "region" : "regions"}
                {" — "}
                <span style={{ color: "var(--accent)" }}>mark A</span> vs{" "}
                <span style={{ color: "var(--accent-2)" }}>mark B</span>
              </p>
            </Frame>
          }
        >
          <p>
            Slide windows of one signature against the other. Genuine matches make many windows lock
            onto <em>one common shift</em>; coincidences scatter. The windows that agree are the{" "}
            <strong className="text-foreground">congruent matching regions</strong> — a generalization
            of the consecutive-matching-striae and CMC ideas to any mark. Their count is the score.
          </p>
          <p className="text-muted">
            {positive
              ? "Here many regions link up with near-parallel connectors — a consistent, real correspondence."
              : "Here only a couple of regions weakly link, at scattered offsets — no consistent match."}
          </p>
        </Stage>

        {/* Stage 5 */}
        <Stage
          n="05"
          title="Turn the score into evidence"
          viz={
            <Frame className="p-3">
              <CalibrationChart
                km={cal.km}
                knm={cal.knm}
                score={ex.score}
                lrLabel={formatLR(ex.lr)}
                className="h-52"
              />
              <p className="mt-1 px-1 text-xs text-muted">
                {cal.nKm} same-source · {cal.nKnm} different-source reference pairs · AUC {cal.auc} · Cllr {cal.cllr}
              </p>
            </Frame>
          }
        >
          <p>
            A score is not evidence until it is calibrated. Verity compares this score against a named
            reference of <strong className="text-foreground">known</strong> same-source and
            different-source pairs, and maps it to a <strong className="text-foreground">likelihood
            ratio</strong> — with a characterized cost (Cllr) and a bound on how strong a claim the
            data can support. The decision stays a transparent, monotone transform of the score.
          </p>
        </Stage>

        {/* Stage 6 */}
        <Stage
          n="06"
          title="Report — don't decide"
          viz={
            <div className="glass rounded-2xl p-6">
              <p className="text-xs uppercase tracking-wider text-muted">Likelihood ratio</p>
              <p className={`font-mono text-5xl font-semibold ${positive ? "accent-text" : "text-rose-500 dark:text-rose-300"}`}>
                {formatLR(ex.lr)}
              </p>
              <p className="mt-2 text-sm text-foreground/80">{ex.verbal}.</p>
              <p className="mt-4 border-t border-border pt-3 text-xs italic leading-relaxed text-muted">
                A calibrated weight of evidence on the {ex.reference.name} reference — not a claim about
                the error rate of examination, which remains unknown.
              </p>
            </div>
          }
        >
          <p>
            The output is a number an examiner and a court can audit: the likelihood ratio, its verbal
            weight, the exact regions that drove it, and an explicit statement of scope. Because the
            calibration is a bounded, monotone map, the report is interpretable{" "}
            <em>regardless of how the score was computed</em> — the firewall against the black box.
          </p>
          <p>
            And it ships a reproducible <strong className="text-foreground">recipe</strong> — every
            step, parameter, and input hash — under a content handle, so the result can be verified by
            re-running it.{" "}
            <a href="/docs#reproducibility" className="text-accent hover:underline">
              See the glass-box API →
            </a>
          </p>
        </Stage>

        {/* Three reductions, validated source-disjoint */}
        <Reveal className="mt-20 sm:mt-28">
          <div className="text-center">
            <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
              <span className="h-1.5 w-1.5 rounded-full bg-accent" />
              One config, every modality
            </span>
            <h2 className="mt-5 font-display text-2xl font-medium text-foreground sm:text-3xl">
              Three reductions, validated source-disjoint
            </h2>
            <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-foreground/80">
              The same congruent-matching-regions algorithm, under one scorer config, reduces to the
              field-standard method for each mark — and recovers it. Each figure is the held-out
              (source-disjoint) weight-of-evidence cost on the named reference, recomputed from the
              committed calibration data.
            </p>
          </div>

          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            {cmr.reductions.map((r) => (
              <div key={r.modality} className="glass flex flex-col rounded-2xl p-5">
                <p className="text-xs uppercase tracking-wider text-muted">{r.label}</p>
                <p className="mt-1 text-sm text-foreground/80">
                  recovers <strong className="text-foreground">{r.reduction}</strong>
                </p>
                <div className="mt-4 flex items-baseline gap-2">
                  <span className="font-mono text-3xl font-semibold accent-text">
                    {r.source_disjoint.cllr.toFixed(2)}
                  </span>
                  <span className="text-xs text-muted">
                    ± {r.source_disjoint.cllr_sd.toFixed(2)} Cllr
                  </span>
                </div>
                <p className="mt-1 text-xs text-muted">
                  AUC {r.source_disjoint.auc.toFixed(3)} · {r.n_km} same-source pairs ·{" "}
                  {r.source_disjoint.n_folds} folds
                </p>
                <p className="mt-auto border-t border-border pt-3 text-[11px] leading-snug text-foreground/60">
                  {r.reference}
                  <span className="mt-1 block text-muted">vs. specialist: {r.specialist}</span>
                </p>
              </div>
            ))}
          </div>

          <p className="mx-auto mt-5 max-w-2xl text-center text-[11px] leading-relaxed text-muted">
            All three references share one scorer-config hash (
            <span className="font-mono">{cmr.scorer_config_hash.slice(0, 12)}…</span>) — the same
            algorithm and parameters, not three tuned pipelines. These characterize weight of evidence
            on the named references, not field-wide error rates.
          </p>
        </Reveal>

        {/* Closing */}
        <Reveal className="mt-20 sm:mt-28">
          <div className="glass rounded-2xl p-8 text-center">
            <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
              The same six steps, for any mark
            </h2>
            <p className="mx-auto mt-3 max-w-xl text-sm leading-relaxed text-foreground/80">
              Bullets, toolmarks, cartridge breech faces — they differ only in the registration group
              (a 1-D shift, or a 2-D shift-plus-rotation). Everything else is shared, which is what
              makes Verity one calibrated, explainable method rather than a pile of bespoke ones.
            </p>
            <a
              href="/#compare"
              className="mt-6 inline-block rounded-full bg-gradient-to-r from-indigo-500 via-sky-500 to-cyan-400 px-6 py-3 text-sm font-semibold text-slate-950 shadow-lg shadow-cyan-500/20 transition hover:opacity-90"
            >
              Try it on your own scans →
            </a>
          </div>
        </Reveal>
      </main>
    </>
  );
}
