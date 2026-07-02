/**
 * The single source of truth for the scholarly record behind Verity.
 *
 * Every citation the site shows — the collapsed list on the homepage
 * (components/home/Citations.tsx) and the full bibliography at /references —
 * is rendered from this array. Add or correct a reference once, here.
 *
 * Grouping mirrors how the work is used: the foundational methods Verity builds
 * on, the standards/critiques that motivated it, the public datasets + open
 * tooling it is validated against, and the statistical machinery it borrows.
 */

export type ReferenceGroup =
  | "foundational"
  | "standards"
  | "datasets"
  | "statistics";

export interface Reference {
  /** Stable key for React lists and cross-referencing. */
  id: string;
  authors: string;
  year: number;
  title: string;
  /** Journal, report, repository, or package registry. */
  venue: string;
  group: ReferenceGroup;
  /** Canonical link — a DOI URL where one exists, otherwise the primary source. */
  url: string;
  /**
   * When the canonical URL is a best-effort landing page rather than a verified
   * DOI, set this so reviewers can spot links that still need confirmation.
   */
  urlUnverified?: boolean;
  /** One-line note on how Verity relates to this work (shown on /references). */
  relevance?: string;
}

export const GROUP_LABELS: Record<ReferenceGroup, string> = {
  foundational: "Foundational method",
  standards: "Standards & critiques",
  datasets: "Datasets & tooling",
  statistics: "Statistics",
};

export const GROUP_BLURBS: Record<ReferenceGroup, string> = {
  foundational:
    "The automatic-matching and congruent-cell methods Verity generalizes into one calibrated pipeline.",
  standards:
    "Two decades of community review that named the gaps Verity sets out to close.",
  datasets:
    "The public benchmark data and open-source tooling Verity is validated against and interoperates with.",
  statistics:
    "The calibration and weight-of-evidence machinery Verity borrows from forensic speaker comparison.",
};

/** Display order for grouped rendering. */
export const GROUP_ORDER: ReferenceGroup[] = [
  "foundational",
  "standards",
  "datasets",
  "statistics",
];

export const REFERENCES: Reference[] = [
  // ── Foundational method ───────────────────────────────────────────────
  {
    id: "hare-2017",
    authors: "Hare, E., Hofmann, H. & Carriquiry, A.",
    year: 2017,
    title: "Automatic matching of bullet land impressions",
    venue: "Annals of Applied Statistics 11(4), 2332–2356",
    group: "foundational",
    url: "https://doi.org/10.1214/17-AOAS1080",
    relevance:
      "The CSAFE/Iowa State automatic bullet-matching method Verity generalizes and deploys.",
  },
  {
    id: "song-2015",
    authors: "Song, J.",
    year: 2015,
    title:
      "Proposed congruent matching cells (CMC) method for ballistic identification and error rate estimation",
    venue: "AFTE Journal 47(3), 177–185 · NIST",
    group: "foundational",
    url: "https://www.nist.gov/publications/proposed-congruent-matching-cells-cmc-method-ballistic-identifications-and-evidence",
    relevance:
      "Congruent Matching Cells — the cell-counting idea Verity extends to Congruent Matching Regions for any mark.",
  },
  {
    id: "song-2018",
    authors: "Song, J., Vorburger, T. V., Chu, W., Yen, J., Soons, J. A., Ott, D. B. & Zhang, N. F.",
    year: 2018,
    title: "Estimating error rates for firearm evidence identifications in forensic science",
    venue: "Forensic Science International 284, 15–32",
    group: "foundational",
    url: "https://doi.org/10.1016/j.forsciint.2017.12.013",
    relevance:
      "The NIST CMC line on error-rate estimation that Verity reframes as a calibrated, bounded likelihood ratio.",
  },
  {
    id: "chumbley-2010",
    authors:
      "Chumbley, L. S., Morris, M. D., Kreiser, M. J., Fisher, C., Craft, J., Genalo, L. J., Davis, S., Faden, D. & Kidd, J.",
    year: 2010,
    title:
      "Validation of tool mark comparisons obtained using a quantitative, comparative, statistical algorithm",
    venue: "Journal of Forensic Sciences 55(4), 953–961",
    group: "foundational",
    url: "https://doi.org/10.1111/j.1556-4029.2010.01424.x",
    relevance:
      "The objective screwdriver-toolmark comparison (the Chumbley U-statistic) Verity benchmarks against on striated toolmarks.",
  },

  // ── Standards & critiques ─────────────────────────────────────────────
  {
    id: "nrc-2009",
    authors: "National Research Council",
    year: 2009,
    title: "Strengthening Forensic Science in the United States: A Path Forward",
    venue: "The National Academies Press",
    group: "standards",
    url: "https://doi.org/10.17226/12589",
    relevance:
      "The landmark report calling for measurable, validated foundations in forensic comparison.",
  },
  {
    id: "pcast-2016",
    authors: "President's Council of Advisors on Science and Technology (PCAST)",
    year: 2016,
    title:
      "Forensic Science in Criminal Courts: Ensuring Scientific Validity of Feature-Comparison Methods",
    venue: "Executive Office of the President",
    group: "standards",
    url: "https://obamawhitehouse.archives.gov/sites/default/files/microsites/ostp/PCAST/pcast_forensic_science_report_final.pdf",
    relevance:
      "Set the bar for empirical validity and characterized error rates in feature-comparison disciplines.",
  },
  {
    id: "cuellar-2024",
    authors: "Cuellar, M., Vanderplas, S., Luby, A. & Rosenblum, M.",
    year: 2024,
    title: "Methodological problems in every black-box study of forensic firearm comparisons",
    venue: "Law, Probability and Risk 23(1), mgae015",
    group: "standards",
    url: "https://doi.org/10.1093/lpr/mgae015",
    relevance:
      "Found that no firearms discipline has a characterized error rate — a gap Verity answers with a calibrated weight of evidence on declared references, not a field error rate.",
  },
  {
    id: "hamby-2009",
    authors: "Hamby, J. E., Brundage, D. J. & Thorpe, J. W.",
    year: 2009,
    title:
      "The identification of bullets fired from 10 consecutively rifled 9 mm Ruger pistol barrels: a research project involving 507 participants from 20 countries",
    venue: "AFTE Journal 41(2), 99–110",
    group: "standards",
    url: "https://afte.org/resources/searchable-journal-index",
    relevance:
      "The Hamby 10-barrel test sets (e.g. 252, 173) — the canonical bullet benchmark Verity is validated on.",
  },
  {
    id: "fadul-2011",
    authors: "Fadul, T. G., Hernandez, G. A., Stoiloff, S. & Gulati, S.",
    year: 2011,
    title:
      "An empirical study to improve the scientific foundation of forensic firearm and tool mark identification utilizing 10 consecutively manufactured slides",
    venue: "NIJ Grant Final Report NCJ 237960 · Award 2009-DN-BX-K230",
    group: "standards",
    url: "https://www.ojp.gov/ncjrs/virtual-library/abstracts/empirical-study-improve-scientific-foundation-forensic-firearm-and",
    relevance:
      "The Fadul consecutively-manufactured cartridge-case study — the impressed-mark benchmark Verity reports on.",
  },

  // ── Datasets & tooling ────────────────────────────────────────────────
  {
    id: "nbtrd-2020",
    authors: "Zheng, X., Soons, J., Thompson, R., Singh, S. & Constantin, C. (NIST)",
    year: 2020,
    title: "NIST Ballistics Toolmark Research Database",
    venue: "Journal of Research of NIST 125, 125004 · tsapps.nist.gov/NRBTD",
    group: "datasets",
    url: "https://doi.org/10.6028/jres.125.004",
    relevance:
      "The open NBTRD repository of 3-D bullet/cartridge/toolmark scans Verity's data catalog harvests and labels.",
  },
  {
    id: "x3ptools-2024",
    authors: "Hofmann, H., Vanderplas, S., Krishnan, G. & Hare, E.",
    year: 2024,
    title: "x3ptools: Tools for Working with 3D Surface Measurements",
    venue: "R package (CRAN), v0.0.4",
    group: "datasets",
    url: "https://doi.org/10.32614/CRAN.package.x3ptools",
    relevance:
      "The reference R reader/writer for the X3P (ISO 25178-72) format Verity's native Rust codec is interoperable with.",
  },
  {
    id: "vanderplas-2020",
    authors: "Vanderplas, S., Nally, M., Klep, T., Cadevall, C. & Hofmann, H.",
    year: 2020,
    title: "Comparison of three similarity scores for bullet LEA matching",
    venue: "Forensic Science International 308, 110167",
    group: "datasets",
    url: "https://doi.org/10.1016/j.forsciint.2020.110167",
    relevance:
      "The automatic bullet-analysis pipeline (bulletxtrctr) Verity benchmarks its bullet-land scores against.",
  },
  {
    id: "cartridgecasescans-2022",
    authors: "Zemmels, J., VanderPlas, S. & Hofmann, H. (CSAFE-ISU)",
    year: 2022,
    title: "cartridgeCaseScans: masked consecutively-manufactured cartridge-case scans",
    venue: "GitHub repository (CC BY 4.0)",
    group: "datasets",
    url: "https://github.com/CSAFE-ISU/cartridgeCaseScans",
    relevance:
      "The open scan repository the Fadul breech-face set is mirrored from — the data behind Verity's deployed impressed-mark reference.",
  },
  {
    id: "tmarks-2022",
    authors: "Hofmann, H. & Cuellar, M.",
    year: 2022,
    title: "tmaRks: compare screwdriver marks",
    venue: "GitHub repository (MIT)",
    group: "datasets",
    url: "https://github.com/heike/tmaRks",
    relevance:
      "The consecutively-manufactured slotted-screwdriver toolmark profiles Verity's striated-toolmark validation is built on.",
  },

  // ── Statistics ────────────────────────────────────────────────────────
  {
    id: "brummer-2006",
    authors: "Brümmer, N. & du Preez, J.",
    year: 2006,
    title: "Application-independent evaluation of speaker detection",
    venue: "Computer Speech & Language 20(2–3), 230–275",
    group: "statistics",
    url: "https://doi.org/10.1016/j.csl.2005.08.001",
    relevance:
      "The origin of the Cllr cost — Verity's calibration metric for the weight of evidence.",
  },
];

/** References for a single group, preserving array order. */
export function referencesByGroup(group: ReferenceGroup): Reference[] {
  return REFERENCES.filter((r) => r.group === group);
}
