"use client";

import dynamic from "next/dynamic";
import { useState, type ReactNode } from "react";
import methodData from "@/lib/method-data.json";
import { Reveal } from "@/components/Reveal";
import { Heatmap } from "@/components/method/Heatmap";
import { SignaturePlot } from "@/components/method/SignaturePlot";
import { AlignedSignatures } from "@/components/method/AlignedSignatures";
import { CalibrationChart } from "@/components/method/CalibrationChart";
import { ThemeToggle } from "@/components/theme/ThemeToggle";

const SurfaceViewer = dynamic(() => import("@/components/three/SurfaceViewer"), { ssr: false });

interface Region {
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
const data = methodData as unknown as { km: Example; knm: Example; calibration: Calibration };

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

export default function MethodPage() {
  const [mode, setMode] = useState<"km" | "knm">("km");
  const ex = data[mode];
  const cal = data.calibration;
  const positive = ex.log10_lr > 0;

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-30">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
          <a href="/" className="font-display text-xl font-semibold tracking-tight">
            <span className="accent-text">Verity</span>
          </a>
          <div className="flex items-center gap-5">
            <a href="/why" className="text-sm text-foreground/70 transition hover:text-foreground">
              Why
            </a>
            <a href="/#compare" className="text-sm text-foreground/70 transition hover:text-foreground">
              Compare
            </a>
            <ThemeToggle />
          </div>
        </div>
      </header>

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
            its work at every step. Below is a <strong className="text-foreground">real comparison</strong>{" "}
            of two Hamby-252 bullets, walked through the whole pipeline. Flip between two bullets from{" "}
            <em>the same</em> firearm and two from <em>different</em> firearms, and watch the same
            algorithm reach opposite conclusions.
          </p>
        </section>

        {/* Toggle + live verdict */}
        <div className="rise mt-10">
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
                lag={ex.lag}
                bandsA={ex.bandsA}
                bandsB={ex.bandsB}
                className="h-44"
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
              ? "Here the two signatures ride on top of each other across many bands — a real match."
              : "Here they never settle on a shared shift — only a couple of accidental bands."}
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
        </Stage>

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
