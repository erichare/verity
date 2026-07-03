"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { detectDomain } from "@/lib/api";
import { runLivePipeline } from "@/lib/liveStudio";
import {
  DOMAIN_LABEL,
  FLAGSHIP,
  TOUR_DOMAINS,
  tourRun,
  type StudioRun,
} from "@/lib/studio";
import { type MarkDomain, type RefusalResponse } from "@/lib/types";
import { FilePick } from "@/components/FilePick";
import RefusalView from "@/components/RefusalView";
import { SiteFooter } from "@/components/SiteFooter";
import { StudioNav } from "./StudioNav";
import { StageStage } from "./StageStage";
import { CaseFilePanel } from "./CaseFilePanel";
import { TimelineRail } from "./TimelineRail";
import { useTimeline } from "./useTimeline";

export function StudioController() {
  const [domain, setDomain] = useState<MarkDomain>("striated");
  const [relation, setRelation] = useState<"KM" | "KNM">("KM");
  const [upload, setUpload] = useState<StudioRun | null>(null);
  const [refusal, setRefusal] = useState<RefusalResponse | null>(null);
  const [uploadOpen, setUploadOpen] = useState(false);
  const [animate, setAnimate] = useState(true);

  // Respect prefers-reduced-motion on arrival: start with the rotation off
  // (WCAG 2.2.2). The Animate toggle / "A" key still lets the user opt back in.
  useEffect(() => {
    if (window.matchMedia?.("(prefers-reduced-motion: reduce)").matches) {
      setAnimate(false);
    }
  }, []);

  const run = upload ?? tourRun(domain, relation) ?? FLAGSHIP;
  const tl = useTimeline(run?.stages.length ?? 1, run?.id ?? "none");

  const pickDomain = useCallback((d: MarkDomain) => {
    setUpload(null);
    setDomain(d);
  }, []);

  // Keyboard: ← → step · space play/pause · Home/End jump · R restart · M match · U upload ·
  // A animate. Suspended while a dialog is open, and ignored whenever focus sits on an
  // interactive element so native activation (Space on a button, Enter on a link) wins.
  useEffect(() => {
    const modalOpen = uploadOpen || refusal !== null;
    const onKey = (e: KeyboardEvent) => {
      if (modalOpen) return;
      const el = e.target instanceof HTMLElement ? e.target : null;
      if (
        el &&
        el !== document.body &&
        (el.isContentEditable ||
          el.closest("input, select, textarea, button, a, [role='button'], [contenteditable]"))
      )
        return;
      switch (e.key) {
        case "ArrowRight":
          tl.next();
          break;
        case "ArrowLeft":
          tl.prev();
          break;
        case " ":
          e.preventDefault();
          tl.toggle();
          break;
        case "Home":
          tl.seekIndex(0);
          break;
        case "End":
          tl.seekIndex((run?.stages.length ?? 1) - 1);
          break;
        case "r":
        case "R":
          tl.restart();
          break;
        case "m":
        case "M":
          setUpload(null);
          setRelation((v) => (v === "KM" ? "KNM" : "KM"));
          break;
        case "u":
        case "U":
          setUploadOpen(true);
          break;
        case "a":
        case "A":
          setAnimate((v) => !v);
          break;
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [tl, run, uploadOpen, refusal]);

  if (!run) {
    return (
      <div className="flex h-[100svh] items-center justify-center text-muted">
        No specimens available.
      </div>
    );
  }

  const stage = run.stages[tl.index];

  return (
    <div className="flex h-[100svh] flex-col bg-background text-foreground">
      <StudioNav />

      <main className="flex min-h-0 flex-1 flex-col">
        <h1 className="sr-only">Verity Studio — a forensic comparison, step by step</h1>

        <div className="flex min-h-0 flex-1">
          <div className="relative min-w-0 flex-1">
            <StageStage run={run} stage={stage} progress={tl.progress} autoRotate={animate} />
            <UploadPill onOpen={() => setUploadOpen(true)} live={run.provenance === "upload"} />
          </div>
          <div className="hidden w-[340px] shrink-0 border-l border-border lg:block">
            <CaseFilePanel run={run} stage={stage} total={run.stages.length} />
          </div>
        </div>

        {/* Mobile caption strip (the full Case File panel is hidden below lg): the stage
            heading plus the provenance badge and key readouts, so phones still see whether
            this is a curated specimen or their scan, and the numbers behind each step. */}
        <div className="border-t border-border px-4 py-2 lg:hidden">
          <div className="flex items-center justify-between gap-2">
            <h2 className="font-mono text-[10px] uppercase tracking-wider text-brass-text">
              Step {stage.num} / {run.stages.length} · {stage.label}
            </h2>
            <span
              className={`inline-flex shrink-0 items-center gap-1 rounded-full border px-2 py-0.5 font-mono text-[9px] text-foreground/70 ${
                run.provenance === "upload"
                  ? "border-border bg-foreground/[0.04]"
                  : "border-brass/30 bg-brass/[0.08]"
              }`}
            >
              <span
                className={`h-1 w-1 rounded-full ${
                  run.provenance === "upload" ? "bg-foreground/50" : "bg-brass"
                }`}
              />
              {run.provenance === "upload" ? "Your scan" : "Curated specimen"}
            </span>
          </div>
          <p className="mt-0.5 truncate font-display text-sm text-foreground">{stage.caption}</p>
          {stage.readouts.length > 0 && (
            <p className="mt-0.5 truncate font-mono text-[10px] text-muted">
              {stage.readouts.map((r) => `${r.label} ${r.value}`).join(" · ")}
            </p>
          )}
        </div>

        <SubBar
          domain={domain}
          relation={relation}
          live={run.provenance === "upload"}
          animate={animate}
          onToggleAnimate={() => setAnimate((v) => !v)}
          onDomain={pickDomain}
          onRelation={(r) => {
            setUpload(null);
            setRelation(r);
          }}
          onReturnToTour={() => setUpload(null)}
        />

        <div className="border-t border-border">
          <TimelineRail
            stages={run.stages}
            index={tl.index}
            progress={tl.progress}
            playing={tl.playing}
            onToggle={tl.toggle}
            onSeek={tl.seekIndex}
            onRestart={tl.restart}
          />
        </div>
      </main>

      {/* One slim row of trust chrome — the Studio shell is viewport-locked, so the
          shared footer renders in its compact single-line variant. */}
      <SiteFooter variant="compact" />

      {uploadOpen && (
        <UploadModal
          onClose={() => setUploadOpen(false)}
          onResult={(liveRun) => {
            setUpload(liveRun);
            setRefusal(null);
            setUploadOpen(false);
          }}
          onRefused={(r) => {
            setRefusal(r);
            setUploadOpen(false);
          }}
        />
      )}

      {refusal && <RefusalModal refusal={refusal} onClose={() => setRefusal(null)} />}
    </div>
  );
}

function UploadPill({ onOpen, live }: { onOpen: () => void; live: boolean }) {
  return (
    <button
      type="button"
      onClick={onOpen}
      className="glass absolute right-4 top-4 z-10 rounded-full px-4 py-2 text-sm font-medium text-foreground/90 transition hover:text-foreground"
    >
      {live ? "Upload other marks" : "Upload your own marks"} ↑
    </button>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`rounded-full border px-3.5 py-1.5 text-xs font-medium transition ${
        active
          ? "border-brass/40 bg-brass/15 text-brass-text"
          : "border-border text-muted hover:text-foreground"
      }`}
    >
      {children}
    </button>
  );
}

function SubBar({
  domain,
  relation,
  live,
  animate,
  onToggleAnimate,
  onDomain,
  onRelation,
  onReturnToTour,
}: {
  domain: MarkDomain;
  relation: "KM" | "KNM";
  live: boolean;
  animate: boolean;
  onToggleAnimate: () => void;
  onDomain: (d: MarkDomain) => void;
  onRelation: (r: "KM" | "KNM") => void;
  onReturnToTour: () => void;
}) {
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border px-4 py-2.5 sm:px-6">
      <div className="flex items-center gap-2">
        <span className="hidden font-mono text-[10px] uppercase tracking-wider text-muted sm:inline">
          Specimen
        </span>
        {TOUR_DOMAINS.map((d) => (
          <Chip key={d} active={!live && domain === d} onClick={() => onDomain(d)}>
            {DOMAIN_LABEL[d] ?? d}
          </Chip>
        ))}
      </div>

      <div className="flex items-center gap-3">
        <button
          type="button"
          onClick={onToggleAnimate}
          aria-pressed={animate}
          title="Toggle the rotating 3-D view (A)"
          className={`flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition ${
            animate
              ? "border-brass/40 bg-brass/15 text-brass-text"
              : "border-border text-muted hover:text-foreground"
          }`}
        >
          <span className={animate ? "animate-spin-slow" : ""} aria-hidden>
            ⟳
          </span>
          Animate
        </button>
        {live && (
          <button
            type="button"
            onClick={onReturnToTour}
            className="text-xs font-medium text-accent transition hover:opacity-80"
          >
            ← Curated tour
          </button>
        )}
        <div className="flex overflow-hidden rounded-full border border-border text-xs">
          <button
            type="button"
            onClick={() => onRelation("KM")}
            aria-pressed={!live && relation === "KM"}
            className={`px-3.5 py-1.5 transition ${
              !live && relation === "KM" ? "bg-accent/15 text-accent" : "text-muted hover:text-foreground"
            }`}
          >
            Same source
          </button>
          <button
            type="button"
            onClick={() => onRelation("KNM")}
            aria-pressed={!live && relation === "KNM"}
            className={`px-3.5 py-1.5 transition ${
              !live && relation === "KNM"
                ? "bg-oxblood/15 text-oxblood"
                : "text-muted hover:text-foreground"
            }`}
          >
            Different source
          </button>
        </div>
      </div>
    </div>
  );
}

const DOMAIN_OPTIONS: { value: MarkDomain; label: string }[] = [
  { value: "striated", label: "Striated — bullet land(s)" },
  { value: "impressed", label: "Impressed — cartridge breech face" },
  { value: "toolmark", label: "Toolmark — striated" },
];

function UploadModal({
  onClose,
  onResult,
  onRefused,
}: {
  onClose: () => void;
  onResult: (run: StudioRun) => void;
  onRefused: (r: RefusalResponse) => void;
}) {
  const [domain, setDomain] = useState<MarkDomain>("striated");
  const [markA, setMarkA] = useState<File[]>([]);
  const [markB, setMarkB] = useState<File[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function onPickA(files: File[]) {
    setMarkA(files);
    if (!files.length) return;
    const d = await detectDomain(files[0]);
    if (d?.domain) setDomain(d.domain as MarkDomain);
  }

  async function run() {
    if (!markA.length || !markB.length) return;
    setLoading(true);
    setError(null);
    try {
      const res = await runLivePipeline(domain, markA, markB);
      if (res.kind === "refused") onRefused(res.refusal);
      else onResult(res.run);
    } catch (e) {
      setError(e instanceof Error ? e.message : "comparison failed");
    } finally {
      setLoading(false);
    }
  }

  const multiple = domain === "striated";

  return (
    <Backdrop onClose={onClose} labelledBy="upload-modal-title">
      <div className="glass w-full max-w-lg space-y-4 rounded-2xl p-6">
        <div className="flex items-start justify-between">
          <div>
            <h2 id="upload-modal-title" className="font-display text-xl text-foreground">
              Compare your own scans
            </h2>
            <p className="mt-1 text-sm text-muted">
              .x3p surface scans, compared live against the deployed engine.
            </p>
          </div>
          <button type="button" onClick={onClose} aria-label="Close" className="text-muted hover:text-foreground">
            ✕
          </button>
        </div>

        <div className="flex flex-col gap-1.5">
          <label htmlFor="studio-mark-type" className="text-sm font-medium text-foreground/80">
            Mark type
          </label>
          <select
            id="studio-mark-type"
            value={domain}
            onChange={(e) => setDomain(e.target.value as MarkDomain)}
            className="w-full rounded-lg border border-border bg-background/60 px-3 py-2 text-sm text-foreground outline-none focus:border-accent/60 focus-visible:ring-2 focus-visible:ring-accent"
          >
            {DOMAIN_OPTIONS.map((o) => (
              <option key={o.value} value={o.value}>
                {o.label}
              </option>
            ))}
          </select>
        </div>

        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          <FilePick label="Mark A" files={markA} onPick={onPickA} multiple={multiple} />
          <FilePick label="Mark B" files={markB} onPick={setMarkB} multiple={multiple} />
        </div>

        <button
          type="button"
          onClick={run}
          disabled={!markA.length || !markB.length || loading}
          className="w-full rounded-lg bg-primary px-4 py-3 font-semibold text-[#f4f1ea] transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {loading ? "Walking the pipeline…" : "Run the pipeline"}
        </button>

        {loading && (
          <p className="text-center text-xs text-muted">
            Running the real engine — the first comparison can take a minute or two while the
            reference calibration warms up.
          </p>
        )}

        {error && (
          <p className="rounded-lg border border-oxblood/30 bg-oxblood/10 p-3 text-sm text-oxblood">{error}</p>
        )}
      </div>
    </Backdrop>
  );
}

function RefusalModal({ refusal, onClose }: { refusal: RefusalResponse; onClose: () => void }) {
  return (
    <Backdrop onClose={onClose} label="Comparison refused — out of scope">
      <div className="w-full max-w-xl">
        <RefusalView result={refusal} />
        <div className="mt-3 text-center">
          <button
            type="button"
            onClick={onClose}
            className="glass rounded-full px-5 py-2 text-sm text-foreground/80 transition hover:text-foreground"
          >
            Close
          </button>
        </div>
      </div>
    </Backdrop>
  );
}

function Backdrop({
  onClose,
  labelledBy,
  label,
  children,
}: {
  onClose: () => void;
  labelledBy?: string;
  label?: string;
  children: React.ReactNode;
}) {
  const ref = useRef<HTMLDialogElement>(null);

  // Native <dialog> modality: showModal() moves focus into the dialog, makes everything
  // outside it inert, handles Escape (→ close event), and restores focus on close.
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);

  return (
    <dialog
      ref={ref}
      aria-labelledby={labelledBy}
      aria-label={label}
      onClose={onClose}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
      className="fixed inset-0 z-40 m-0 flex h-full max-h-none w-full max-w-none items-center justify-center bg-[color-mix(in_srgb,var(--background)_70%,transparent)] p-4 backdrop-blur-sm backdrop:bg-transparent"
    >
      {children}
    </dialog>
  );
}
