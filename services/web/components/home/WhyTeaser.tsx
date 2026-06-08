import { Citations } from "./Citations";

/**
 * The stakes + the scientific contribution in one block: why the field needed a
 * new method, and exactly what Verity adds. Routes to the full /why argument.
 */
export function WhyTeaser() {
  return (
    <section id="science" className="glass scroll-mt-20 rounded-2xl p-6 sm:p-8">
      <div className="grid gap-5 sm:grid-cols-[1.5fr_1fr] sm:items-start">
        <div>
          <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
            Why a new method was <span className="accent-text">necessary</span>
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-foreground/80">
            This is evidence used in criminal courts — yet two decades of review (NRC&nbsp;2009,
            PCAST&nbsp;2016, Cuellar et&nbsp;al.&nbsp;2024) found the field has no characterized error
            rate, and the existing tools are each bespoke to one mark type and stop at an uncalibrated
            score. Verity closes both gaps at once: a single, transparent method that returns a{" "}
            <strong className="text-foreground">calibrated likelihood ratio with a quantified cost (Cllr)</strong>{" "}
            and <strong className="text-foreground">region-level attribution</strong>, spanning striated
            marks (bullets, toolmarks) and impressed marks (breech faces) by generalizing the Congruent
            Matching Cells method (Song,&nbsp;2013) to arbitrary toolmarks. The score is only an input;
            the reportable decision is a monotone, bounded likelihood ratio — auditable however it was
            computed. Verity reports the weight of evidence; it never makes the decision for the examiner.
          </p>
        </div>
        <div className="flex flex-col gap-2 text-sm sm:items-end">
          <a
            href="/why"
            className="glass rounded-full px-6 py-3 font-medium text-foreground/80 transition hover:text-foreground"
          >
            The full argument →
          </a>
          <a
            href="https://api.verity.codes/scalar"
            target="_blank"
            rel="noopener noreferrer"
            className="px-2 text-xs text-muted underline decoration-border underline-offset-2 transition hover:text-accent hover:decoration-accent"
          >
            Read the API reference ↗
          </a>
        </div>
      </div>
      <details className="group mt-5">
        <summary className="cursor-pointer list-none text-xs font-medium uppercase tracking-wider text-muted transition hover:text-foreground/80">
          <span className="inline-block transition group-open:rotate-90">▸</span> References (6)
        </summary>
        <Citations />
      </details>
    </section>
  );
}
