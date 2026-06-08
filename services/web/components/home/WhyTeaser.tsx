/** Raises the stakes the homepage was missing, and routes to the full /why argument. */
export function WhyTeaser() {
  return (
    <section className="glass rounded-2xl p-6 sm:p-8">
      <div className="grid gap-5 sm:grid-cols-[1.4fr_1fr] sm:items-center">
        <div>
          <h2 className="font-display text-2xl font-medium text-foreground sm:text-3xl">
            Why a new method was <span className="accent-text">necessary</span>
          </h2>
          <p className="mt-3 text-sm leading-relaxed text-foreground/80">
            This is evidence used in criminal courts — and two decades of review (NRC 2009, PCAST
            2016, Cuellar et&nbsp;al. 2024) found the field lacks a characterized error rate. The
            existing tools are excellent, but each is bespoke to one mark type and stops at an
            uncalibrated score. None delivers a calibrated likelihood ratio, region attribution, and
            cross-mark generality in one open method. Verity closes those gaps at once — and never
            makes the decision for the examiner.
          </p>
        </div>
        <div className="flex flex-col gap-2 text-sm sm:items-end">
          <a
            href="/why"
            className="glass rounded-full px-6 py-3 font-medium text-foreground/80 transition hover:text-foreground"
          >
            What was missing →
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
    </section>
  );
}
