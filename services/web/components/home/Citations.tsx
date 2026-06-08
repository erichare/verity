/** The scholarly record behind the homepage claim — kept collapsed by default. */
export function Citations() {
  const refs: [string, string, string][] = [
    ["National Research Council (2009)", "Strengthening Forensic Science in the United States: A Path Forward.", "https://doi.org/10.17226/12589"],
    ["PCAST (2016)", "Forensic Science in Criminal Courts: Ensuring Scientific Validity of Feature-Comparison Methods.", "https://obamawhitehouse.archives.gov/sites/default/files/microsites/ostp/PCAST/pcast_forensic_science_report_final.pdf"],
    ["Cuellar, Vanderplas, Luby & Rosenblum (2024)", "Methodological problems in every black-box study of forensic firearm comparisons.", "https://doi.org/10.1093/lpr/mgae015"],
    ["Song (2013)", "Proposed congruent matching cells (CMC) method for ballistic identification.", "https://www.nist.gov/publications/proposed-congruent-matching-cells-cmc-method-ballistic-identifications-and-evidence"],
    ["Hare, Hofmann & Carriquiry (2017)", "Automatic matching of bullet land impressions. Annals of Applied Statistics.", "https://doi.org/10.1214/17-AOAS1080"],
    ["Brümmer & du Preez (2006)", "Application-independent evaluation of speaker detection — the Cllr cost.", "https://doi.org/10.1016/j.csl.2005.08.001"],
  ];
  return (
    <ul className="mt-4 space-y-1.5 text-xs text-muted">
      {refs.map(([who, what, href]) => (
        <li key={who} className="leading-relaxed">
          <a
            href={href}
            target="_blank"
            rel="noopener noreferrer"
            className="group inline transition hover:text-foreground/80"
          >
            <span className="text-foreground/80 underline decoration-border underline-offset-2 transition group-hover:decoration-accent group-hover:text-accent">
              {who}
            </span>{" "}
            — <span className="italic">{what}</span>
            <span aria-hidden className="ml-0.5 not-italic text-muted/60 transition group-hover:text-accent">↗</span>
          </a>
        </li>
      ))}
    </ul>
  );
}
