import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Reveal } from "@/components/Reveal";
import { CodeBlock } from "@/components/docs/CodeBlock";
import { CodeTabs } from "@/components/docs/CodeTabs";
import { DocsNav, type NavSection } from "@/components/docs/DocsNav";
import { SiteNav } from "@/components/SiteNav";

export const metadata: Metadata = {
  title: "Verity Docs — REST API, X3P codec, and method",
  description:
    "Use Verity: the calibrated likelihood-ratio comparison API, the native X3P (ISO 25178-72) codec for Rust/Python/R, the data catalog, and the core concepts (LR, Cllr, Congruent Matching Regions).",
};

const SECTIONS: NavSection[] = [
  { id: "overview", label: "Overview" },
  { id: "quickstart", label: "Quickstart" },
  { id: "concepts", label: "Core concepts" },
  { id: "api", label: "REST API" },
  { id: "reproducibility", label: "Reproducibility" },
  { id: "codec", label: "X3P codec" },
  { id: "catalog", label: "Data catalog" },
  { id: "architecture", label: "Architecture" },
  { id: "reference", label: "Reference" },
];

const API_BASE = "https://api.verity.codes";

function Section({
  id,
  eyebrow,
  title,
  children,
}: {
  id: string;
  eyebrow?: string;
  title: string;
  children: ReactNode;
}) {
  return (
    <Reveal>
      <section id={id} className="scroll-mt-24 border-t border-border pt-12 first:border-0 first:pt-0">
        {eyebrow && (
          <div className="font-display text-sm font-semibold text-accent">{eyebrow}</div>
        )}
        <h2 className="mt-1 font-display text-2xl font-medium text-foreground sm:text-3xl">{title}</h2>
        <div className="mt-4 space-y-4 text-sm leading-relaxed text-foreground/80">{children}</div>
      </section>
    </Reveal>
  );
}

function Endpoint({ method, path, children }: { method: string; path: string; children: ReactNode }) {
  const tone =
    method === "GET" ? "text-emerald-500 dark:text-emerald-300" : "text-accent";
  return (
    <div className="rounded-xl border border-border bg-foreground/[0.02] p-4">
      <div className="flex items-center gap-3">
        <span className={`font-mono text-xs font-semibold ${tone}`}>{method}</span>
        <code className="font-mono text-sm text-foreground">{path}</code>
      </div>
      <div className="mt-2 text-sm text-foreground/75">{children}</div>
    </div>
  );
}

function Field({ name, children }: { name: string; children: ReactNode }) {
  return (
    <tr className="border-t border-border align-top">
      <td className="py-2 pr-4">
        <code className="font-mono text-xs text-accent">{name}</code>
      </td>
      <td className="py-2 text-foreground/75">{children}</td>
    </tr>
  );
}

const QUICKSTART_TABS = [
  {
    label: "curl",
    code: `# Which mark types have a calibrated reference?
curl -s ${API_BASE}/health

# Compare two bullets — upload every land scan of each.
curl -s -X POST ${API_BASE}/compare \\
  -F domain=striated \\
  -F mark_a=@bulletA_land1.x3p -F mark_a=@bulletA_land2.x3p \\
  -F mark_b=@bulletB_land1.x3p -F mark_b=@bulletB_land2.x3p`,
  },
  {
    label: "Python",
    code: `import requests

BASE = "${API_BASE}"
lands_a = ["bulletA_land1.x3p", "bulletA_land2.x3p"]
lands_b = ["bulletB_land1.x3p", "bulletB_land2.x3p"]

files = [("mark_a", open(p, "rb")) for p in lands_a]
files += [("mark_b", open(p, "rb")) for p in lands_b]

r = requests.post(f"{BASE}/compare", data={"domain": "striated"}, files=files)
report = r.json()
print(report["likelihood_ratio"], "—", report["verbal"])`,
  },
  {
    label: "JavaScript",
    code: `const form = new FormData();
form.append("domain", "striated");
for (const f of landsA) form.append("mark_a", f); // File objects
for (const f of landsB) form.append("mark_b", f);

const res = await fetch("${API_BASE}/compare", { method: "POST", body: form });
const report = await res.json();
console.log(report.likelihood_ratio, report.verbal);`,
  },
];

const COMPARE_RESPONSE = `{
  "domain": "striated",
  "likelihood_ratio": 146.0,
  "log10_lr": 2.16,
  "direction": "same source",
  "verbal": "moderately strong support for same source",
  "lr_bound_log10": 2.16,
  "score": 0.153,
  "score_kind": "bullet-contrast",
  "reference": {
    "name": "pooled bullet-land reference (Hamby-252 & 173, …)",
    "n_km": 146, "n_knm": 1755, "auc": 0.984, "cllr": 0.193, "cllr_min": 0.168
  },
  "attribution":   [{ "x_frac": 0.0,  "w_frac": 0.167, "corr": 0.91, "…": "…" }],
  "attribution_b": [{ "x_frac": 0.008,"w_frac": 0.167, "corr": 0.91, "…": "…" }],
  "previews": { "a": "[[…]] downsampled height grid", "b": "[[…]]" },
  "scope_note": "A calibrated weight of evidence on the named reference; not a
                 claim about the error rate of examination, which remains unknown."
}`;

const RECIPE_EXCERPT = `{
  "handle": "sha256:632d8a8b9943fb71…",        // the content address of this computation
  "engine_version": "0.1.0",
  "scorer_config_hash": "ea4ddd513b57…",
  "inputs": { "mark_a": ["8ab45f56…"], "mark_b": ["ed232b90…"] },   // SHA-256 of each scan
  "reference": {
    "name": "Fadul cartridge cases", "scorer_config_hash": "ea4ddd513b57…",
    "diagnostics": { "n_km": 10, "n_knm": 180, "auc": 0.997, "cllr_min": 0.07 }
  },
  "result": { "likelihood_ratio": 10.0, "log10_lr": 1.0, "verbal": "moderate support…" },
  "steps": [
    { "step": "decode",          "code": "verity_x3p.read_x3p" },
    { "step": "preprocess",      "code": "verity.preprocess", "params": { "lambda_s": 4e-6, "lambda_c": 250e-6 } },
    { "step": "areal-signature", "code": "verity.areal.areal_signature" },
    { "step": "compare",         "code": "verity.cmr.cmr_count" },
    { "step": "calibrate",       "code": "verity.decision.lr.ScoreLRModel", "params": { "lr_bound": "auto" } },
    { "step": "uncertainty",     "code": "verity.decision.uncertainty.lr_credible_interval" }
  ]
}`;

const REPRODUCE_TABS = [
  {
    label: "Python",
    code: `from verity_client import VerityClient        # clients/python
v = VerityClient("${API_BASE}")

r = v.compare("impressed", "breech_a.x3p", "breech_b.x3p")
print(r["likelihood_ratio"], r["handle"])     # the content address

# verify a published LR — a one-line hash-equality check
assert v.reproduce("impressed", "breech_a.x3p", "breech_b.x3p",
                   expect_handle=r["handle"])`,
  },
  {
    label: "R",
    code: `source("clients/r/verity.R")                  # clients/r

r <- verity_compare("impressed", "breech_a.x3p", "breech_b.x3p")
cat(r$likelihood_ratio, r$handle, "\\n")

again <- verity_compare("impressed", "breech_a.x3p", "breech_b.x3p", include = "recipe")
stopifnot(identical(again$handle, r$handle))  # same computation -> same handle`,
  },
];

const CODEC_TABS = [
  {
    label: "Rust",
    code: `use verity_x3p::{read_x3p, write_x3p, WriteOptions};

let surface = read_x3p("scan.x3p")?;          // verifies the stored MD5
println!("{} x {} points", surface.nx(), surface.ny());
write_x3p(&surface, "copy.x3p", &WriteOptions::default())?;`,
  },
  {
    label: "Python",
    code: `import verity_x3p

s = verity_x3p.read_x3p("scan.x3p")            # verifies the stored MD5
print(s.nx, s.ny, s.data.shape, s.data.dtype)  # 741 419 (419, 741) float64

# s.data and s.mask are NumPy arrays of shape (ny, nx).
verity_x3p.write_x3p(s, "copy.x3p", z_type="D")`,
  },
  {
    label: "R",
    code: `library(verityx3p)

s <- read_x3p("scan.x3p")            # verifies the stored MD5
dim(s$surface)                       # nx-by-ny matrix (x3ptools convention)
write_x3p(s, tempfile(fileext = ".x3p"))`,
  },
];

export default function DocsPage() {
  return (
    <>
      <SiteNav />

      <main className="mx-auto w-full max-w-6xl px-6 pb-24 pt-28 sm:pt-32">
        {/* Intro */}
        <div className="rise max-w-3xl">
          <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
            <span className="h-1.5 w-1.5 rounded-full bg-accent" />
            Documentation
          </span>
          <h1 className="mt-6 font-display text-5xl font-semibold tracking-tight sm:text-6xl">
            Build with <span className="accent-text">Verity</span>
          </h1>
          <p className="mt-5 text-lg leading-relaxed text-foreground/80">
            Everything to use Verity in your own work: the calibrated comparison{" "}
            <strong className="text-foreground">REST API</strong>, the native{" "}
            <strong className="text-foreground">X3P codec</strong> for Rust, Python, and R, the data
            catalog, and the concepts behind the numbers. For the science narrative, see{" "}
            <a href="/method" className="text-accent hover:underline">the method</a> and{" "}
            <a href="/why" className="text-accent hover:underline">why Verity exists</a>.
          </p>
        </div>

        {/* Two-column: sticky nav + content */}
        <div className="mt-12 grid gap-10 lg:grid-cols-[200px_minmax(0,1fr)]">
          <DocsNav sections={SECTIONS} />

          <div className="min-w-0 space-y-12">
            <Section id="overview" title="Overview">
              <p>
                Verity turns a pair of 3-D surface-topography scans into a{" "}
                <strong className="text-foreground">calibrated, bounded likelihood ratio</strong> —
                an auditable weight of evidence — with a characterized cost (Cllr) and region-level
                attribution. One method spans <em>striated</em> marks (bullet lands, toolmarks) and{" "}
                <em>impressed</em> marks (cartridge breech faces).
              </p>
              <p>
                There are three ways in: the hosted <strong className="text-foreground">web app</strong>{" "}
                at <a href="/" className="text-accent hover:underline">verity.codes</a>, the{" "}
                <strong className="text-foreground">REST API</strong> below, and the{" "}
                <strong className="text-foreground">open-source</strong> Rust/Python/R libraries. The
                decision always stays behind a glass-box statistical firewall — the representation
                only produces a score; the reportable LR is a monotone, bounded transform of it.
              </p>
            </Section>

            <Section id="quickstart" eyebrow="Get going" title="Quickstart">
              <p>
                The fastest path is the hosted API. <code className="font-mono text-xs">GET /health</code>{" "}
                lists the calibrated mark types; <code className="font-mono text-xs">POST /compare</code>{" "}
                returns the report. For bullets, upload <em>all</em> of each bullet&rsquo;s land scans —
                aggregating the lands is the strong path.
              </p>
              <CodeTabs tabs={QUICKSTART_TABS} />
              <p className="text-xs text-muted">
                No <code className="font-mono">.x3p</code> files handy? The web app&rsquo;s{" "}
                <a href="/#compare" className="text-accent hover:underline">Compare tool</a> has a
                &ldquo;Load a sample&rdquo; button that runs a real comparison.
              </p>
            </Section>

            <Section id="concepts" eyebrow="The ideas" title="Core concepts">
              <p>
                <strong className="text-foreground">Likelihood ratio (LR).</strong> The reportable
                answer is not a &ldquo;match&rdquo; — it is how much more probable the observed
                similarity is if the marks share a source than if they do not. Verbal equivalents
                (&ldquo;moderately strong support&rdquo;) map directly from the LR.
              </p>
              <p>
                <strong className="text-foreground">Calibration &amp; Cllr.</strong> A raw score is not
                evidence until it is calibrated against a <em>named</em> reference of known
                same-source (KM) and different-source (KNM) pairs. Cllr is the cost of the calibrated
                LRs (lower is better; &lt;1 is informative); the Cllr&minus;Cllr<sub>min</sub> gap is
                the calibration loss. Verity also reports an <strong className="text-foreground">ELUB
                bound</strong> — the strongest claim the reference data can support.
              </p>
              <p>
                <strong className="text-foreground">Congruent Matching Regions (CMR).</strong> Verity&rsquo;s
                domain-general similarity principle: partition a mark into regions, register each
                against the other mark, and count the regions that agree on one common geometry. It
                generalizes Song&rsquo;s Congruent Matching Cells (CMC) from 2-D cells to regions of
                any dimension — the set of congruent regions <em>is</em> the attribution map.
              </p>
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full min-w-[520px] text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-wider text-muted">
                      <th className="px-4 py-3 text-left font-medium">Modality</th>
                      <th className="px-4 py-3 text-left font-medium">Region</th>
                      <th className="px-4 py-3 text-left font-medium">Transform group</th>
                      <th className="px-4 py-3 text-left font-medium">Reduces to</th>
                    </tr>
                  </thead>
                  <tbody className="text-foreground/80">
                    <tr className="border-t border-border">
                      <td className="px-4 py-3">Striated</td>
                      <td className="px-4 py-3">1-D profile window</td>
                      <td className="px-4 py-3">1-D translation</td>
                      <td className="px-4 py-3">Chumbley / CMS</td>
                    </tr>
                    <tr className="border-t border-border">
                      <td className="px-4 py-3">Impressed</td>
                      <td className="px-4 py-3">2-D grid cell</td>
                      <td className="px-4 py-3">2-D translation + rotation</td>
                      <td className="px-4 py-3 text-accent">= CMC</td>
                    </tr>
                    <tr className="border-t border-border">
                      <td className="px-4 py-3">Fractured</td>
                      <td className="px-4 py-3">3-D mesh patch</td>
                      <td className="px-4 py-3">3-D rigid pose</td>
                      <td className="px-4 py-3 text-muted">research</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted">
                Full write-up:{" "}
                <a
                  href="https://github.com/erichare/verity/blob/main/docs/congruent-matching-regions.md"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:underline"
                >
                  docs/congruent-matching-regions.md ↗
                </a>
              </p>
            </Section>

            <Section id="api" eyebrow="HTTP" title="REST API">
              <p>
                Base URL <code className="font-mono text-xs text-foreground">{API_BASE}</code>. The API
                is OpenAPI-described — an interactive reference (Scalar) lives at{" "}
                <a
                  href={`${API_BASE}/scalar`}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:underline"
                >
                  /scalar
                </a>{" "}
                (Swagger UI at <code className="font-mono text-xs">/docs</code>, ReDoc at{" "}
                <code className="font-mono text-xs">/redoc</code>).
              </p>

              <div className="space-y-3">
                <Endpoint method="GET" path="/health">
                  Service status and the list of calibrated domains.
                </Endpoint>
                <CodeBlock
                  label="200 OK"
                  code={`{ "status": "ok", "engine_version": "0.1.0", "domains": ["impressed", "striated", "toolmark"] }`}
                />

                <Endpoint method="POST" path="/detect">
                  Suggest a mark type from one scan (multipart field <code className="font-mono text-xs">scan</code>),
                  from striation anisotropy. The UI pre-selects it; you confirm.
                </Endpoint>
                <CodeBlock
                  label="curl"
                  code={`curl -s -X POST ${API_BASE}/detect -F scan=@mark.x3p
# { "domain": "striated", "coherence": 0.72 }`}
                />

                <Endpoint method="POST" path="/compare">
                  The core call. Multipart form: <code className="font-mono text-xs">domain</code>{" "}
                  (<code className="font-mono text-xs">striated</code>,{" "}
                  <code className="font-mono text-xs">impressed</code>, or{" "}
                  <code className="font-mono text-xs">toolmark</code>), plus repeated{" "}
                  <code className="font-mono text-xs">mark_a</code> /{" "}
                  <code className="font-mono text-xs">mark_b</code> file fields. For striated bullets,
                  send every land scan of each bullet; for impressed, one breech-face scan per mark;
                  for toolmark, one striated profile scan per mark.
                </Endpoint>
              </div>

              <p className="pt-2 font-medium text-foreground">Response — the ComparisonReport</p>
              <CodeBlock label="200 OK" code={COMPARE_RESPONSE} />
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full min-w-[520px] text-sm">
                  <tbody>
                    <Field name="likelihood_ratio">
                      The calibrated LR — the reportable weight of evidence (LR &lt; 1 supports
                      different sources).
                    </Field>
                    <Field name="log10_lr · lr_bound_log10">
                      log₁₀ of the LR, and the ELUB bound — the strongest claim the reference supports.
                    </Field>
                    <Field name="verbal · direction">
                      Verbal equivalent of the LR, and which source hypothesis it favors.
                    </Field>
                    <Field name="score · score_kind">The raw similarity score and which scorer produced it.</Field>
                    <Field name="reference">
                      The named calibration population and its diagnostics (<code className="font-mono text-xs">n_km</code>,{" "}
                      <code className="font-mono text-xs">n_knm</code>, <code className="font-mono text-xs">auc</code>,{" "}
                      <code className="font-mono text-xs">cllr</code>, <code className="font-mono text-xs">cllr_min</code>).
                    </Field>
                    <Field name="attribution · attribution_b">
                      The matched regions on Mark A and Mark B — the explanation of the score.
                    </Field>
                    <Field name="previews">Downsampled height grids of the rendered surfaces, for overlaying attribution.</Field>
                    <Field name="scope_note">An explicit statement of what the number does and does not claim.</Field>
                  </tbody>
                </table>
              </div>
              <p className="text-xs text-muted">
                CORS: the API answers the web origin (configurable via{" "}
                <code className="font-mono text-xs">VERITY_CORS_ORIGINS</code>). Errors return a JSON{" "}
                <code className="font-mono text-xs">detail</code> with a 400 status for bad uploads or
                an uncalibrated domain.
              </p>
            </Section>

            <Section id="reproducibility" eyebrow="Show your work" title="Reproducibility & the glass-box API">
              <p>
                Every <code className="font-mono text-xs">/v1/compare</code> carries a{" "}
                <strong className="text-foreground">recipe</strong> — the methods section as JSON:
                every pipeline step and its parameters, the engine version, the SHA-256 of each
                input scan, and the reference&rsquo;s provenance — stamped with a content{" "}
                <strong className="text-foreground">handle</strong>. Same inputs + scorer config +
                reference + engine produce the same handle, so verifying a published likelihood
                ratio is a hash-equality check, not an act of trust.
              </p>
              <CodeBlock label="recipe (excerpt)" code={RECIPE_EXCERPT} />

              <p>
                <strong className="text-foreground">Every step is addressable.</strong> Upload a
                scan for a content handle, then chain the pipeline — each intermediate is fetchable
                and links to its inputs, a content-addressed graph from scan to score.
              </p>
              <div className="space-y-3">
                <Endpoint method="POST" path="/v1/artifacts">
                  Upload a scan → a surface handle (the graph entry point).
                </Endpoint>
                <Endpoint method="POST" path="/v1/steps/{preprocess,signature,areal-signature,align,features}">
                  Each wraps one engine step, taking its inputs as content handles and returning the
                  output handle + provenance.
                </Endpoint>
                <Endpoint method="GET" path="/v1/artifacts/{handle}">
                  The intermediate&rsquo;s record (kind + provenance); add{" "}
                  <code className="font-mono text-xs">/data</code> for the raw{" "}
                  <code className="font-mono text-xs">.npy</code> (ETag = handle) or{" "}
                  <code className="font-mono text-xs">/preview</code> for a downsampled view.
                </Endpoint>
              </div>

              <p>
                <strong className="text-foreground">The calibration firewall.</strong> A likelihood
                ratio is valid only when the score was produced under the <em>same</em> scorer config
                as the reference. <code className="font-mono text-xs">/v1/steps/calibrate</code> — and
                a <code className="font-mono text-xs">scorer_config</code> override on{" "}
                <code className="font-mono text-xs">/v1/compare</code> — refuse to emit a calibrated LR
                when the config hashes disagree, returning the raw score with{" "}
                <code className="font-mono text-xs">calibrated: false</code> rather than a mis-scaled
                number.
              </p>
              <div className="space-y-3">
                <Endpoint method="GET" path="/v1/scorer-config">
                  The deployed scorer hyperparameters + their content hash.
                </Endpoint>
                <Endpoint method="GET" path="/v1/references">
                  Every calibration reference&rsquo;s scorer hash, source datasets, and
                  Cllr/Cllr<sub>min</sub>/AUC — exactly what each LR is calibrated on.
                </Endpoint>
                <Endpoint method="POST" path="/v1/steps/calibrate">
                  Map a score → bounded LR against a reference; refuses an off-config score (the
                  firewall).
                </Endpoint>
              </div>

              <p>
                <strong className="text-foreground">Clients.</strong> Thin Python and R clients wrap
                the API; <code className="font-mono text-xs">reproduce()</code> re-runs a comparison
                and checks the handle matches.
              </p>
              <CodeTabs tabs={REPRODUCE_TABS} />
              <p className="text-xs text-muted">
                Clients:{" "}
                <a
                  href="https://github.com/erichare/verity/tree/main/clients"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-accent hover:underline"
                >
                  clients/ ↗
                </a>
              </p>
            </Section>

            <Section id="codec" eyebrow="The format" title="X3P codec">
              <p>
                Verity reads and writes <strong className="text-foreground">X3P</strong> (ISO 25178-72)
                — the open container for 3-D surface topography — through a single native Rust core,{" "}
                <code className="font-mono text-xs">verity-x3p</code>, with thin per-language bindings.
                A file written from any binding reads back <strong className="text-foreground">bit-identically</strong>{" "}
                in every other. Heights are an <code className="font-mono text-xs">(ny, nx)</code> matrix of{" "}
                <code className="font-mono text-xs">f64</code> (invalid points are NaN) with a parallel
                validity mask and the X3P axis/provenance metadata.
              </p>
              <CodeTabs tabs={CODEC_TABS} />
              <p className="text-xs text-muted">
                Install: Python builds with <code className="font-mono text-xs">maturin develop</code>{" "}
                (PyPI wheels to follow); R via <code className="font-mono text-xs">R CMD INSTALL bindings/r/verityx3p</code>.
                Both require a Rust toolchain today. TypeScript / Swift / Java bindings are planned.
              </p>
            </Section>

            <Section id="catalog" eyebrow="The data" title="Data catalog">
              <p>
                <code className="font-mono text-xs">verity-catalog</code> is a normalized catalog +
                content-addressed (SHA-256) store + manifest-driven ingestion for forensic X3P scans
                harvested from NIST NBTRD (U.S. public domain), CSAFE-ISU&rsquo;s cartridge-case
                scans on Figshare (CC BY 4.0), and the tmaRks toolmark set (MIT). It is{" "}
                <strong className="text-foreground">local-first</strong> (SQLite + a blob directory, no
                external services) and scales to Postgres + object storage by setting{" "}
                <code className="font-mono text-xs">VERITY_CATALOG_*</code> env vars — no code change.
                Same-source (KM/KNM) labels fall out of the Study → Firearm → Bullet → Land → Scan
                hierarchy, and every scan is validated with <code className="font-mono text-xs">verity-x3p</code>{" "}
                on ingest.
              </p>
              <CodeBlock
                label="bash"
                code={`uv run verity-catalog init-db
uv run verity-catalog ingest hamby252-barrel1-sample --limit 2  # ~2.9 MB scans from NBTRD
uv run verity-catalog info`}
              />
            </Section>

            <Section id="architecture" eyebrow="How it fits" title="Architecture">
              <p>
                Verity is a polyglot monorepo: one Rust codec core, thin language bindings, and the
                Python science + service stack on top.
              </p>
              <div className="overflow-x-auto rounded-xl border border-border">
                <table className="w-full min-w-[560px] text-sm">
                  <thead>
                    <tr className="text-xs uppercase tracking-wider text-muted">
                      <th className="px-4 py-3 text-left font-medium">Package</th>
                      <th className="px-4 py-3 text-left font-medium">Lang</th>
                      <th className="px-4 py-3 text-left font-medium">Role</th>
                    </tr>
                  </thead>
                  <tbody className="text-foreground/80">
                    <tr className="border-t border-border">
                      <td className="px-4 py-3 font-mono text-xs">crates/verity-x3p</td>
                      <td className="px-4 py-3">Rust</td>
                      <td className="px-4 py-3">Native X3P reader/writer — the format&rsquo;s single source of truth.</td>
                    </tr>
                    <tr className="border-t border-border">
                      <td className="px-4 py-3 font-mono text-xs">bindings/python · bindings/r</td>
                      <td className="px-4 py-3">PyO3 · extendr</td>
                      <td className="px-4 py-3">Thin wrappers over the core for bit-identical I/O.</td>
                    </tr>
                    <tr className="border-t border-border">
                      <td className="px-4 py-3 font-mono text-xs">services/engine</td>
                      <td className="px-4 py-3">Python</td>
                      <td className="px-4 py-3">Metrology preprocessing, registration, CMR, the calibrated-LR decision layer.</td>
                    </tr>
                    <tr className="border-t border-border">
                      <td className="px-4 py-3 font-mono text-xs">services/api</td>
                      <td className="px-4 py-3">FastAPI</td>
                      <td className="px-4 py-3">The comparison HTTP API serving the ComparisonReport.</td>
                    </tr>
                    <tr className="border-t border-border">
                      <td className="px-4 py-3 font-mono text-xs">services/catalog</td>
                      <td className="px-4 py-3">Python</td>
                      <td className="px-4 py-3">Catalog + content-addressed store + ingestion.</td>
                    </tr>
                    <tr className="border-t border-border">
                      <td className="px-4 py-3 font-mono text-xs">services/web</td>
                      <td className="px-4 py-3">Next.js</td>
                      <td className="px-4 py-3">This site and the interactive comparison UI.</td>
                    </tr>
                  </tbody>
                </table>
              </div>
              <p>
                <strong className="text-foreground">The firewall.</strong> A learned or hand-engineered
                representation produces a <em>score</em>; a transparent, ELUB-bounded calibration turns
                that score into the reportable LR. The report is interpretable regardless of how the
                score was computed — the defense against the black box.
              </p>
            </Section>

            <Section id="reference" eyebrow="Pointers" title="Reference">
              <ul className="grid gap-2 sm:grid-cols-2">
                {[
                  ["Interactive API reference (Scalar)", `${API_BASE}/scalar`],
                  ["Source on GitHub", "https://github.com/erichare/verity"],
                  ["How the method works", "/method"],
                  ["Why Verity exists", "/why"],
                  ["CMR write-up", "https://github.com/erichare/verity/blob/main/docs/congruent-matching-regions.md"],
                  ["Try a comparison", "/#compare"],
                ].map(([label, href]) => (
                  <li key={label}>
                    <a
                      href={href}
                      target={href.startsWith("http") ? "_blank" : undefined}
                      rel={href.startsWith("http") ? "noopener noreferrer" : undefined}
                      className="glass flex items-center justify-between rounded-xl px-4 py-3 text-sm text-foreground/80 transition hover:text-foreground"
                    >
                      {label}
                      <span aria-hidden className="text-muted">→</span>
                    </a>
                  </li>
                ))}
              </ul>
              <p className="pt-4 text-xs leading-relaxed text-muted">
                Licensed MIT / Apache-2.0. Verity reports a calibrated weight of evidence; it never
                makes the decision, and makes no claim about the error rate of forensic examination,
                which remains unknown.
              </p>
            </Section>
          </div>
        </div>
      </main>
    </>
  );
}
