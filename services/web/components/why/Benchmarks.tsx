import benchmarkData from "@/lib/benchmark-data.json";

interface Side {
  auc: number | null;
  cllr: number | null;
  cllrMin: number | null;
  overallAuc: number | null;
  nFolds: number;
}
interface StudyRow {
  study: string;
  nPairs: number;
  nKm: number;
  nKnm: number;
  verity: Side;
  baseline: Side;
}
interface DomainGroup {
  domain: string;
  domainTag: string;
  baseline: string;
  baselineNote: string;
  studies: StudyRow[];
}
interface BreadthRow {
  study: string;
  nBullets: number;
  nBarrels: number;
  nPairs: number;
  nKm: number;
  nKnm: number;
  auc: number | null;
  cllr: number | null;
  cllrMin: number | null;
  overallAuc: number | null;
  nFolds: number;
}

const data = benchmarkData as unknown as { headToHead: DomainGroup[]; breadth: BreadthRow[] };

function fmt(x: number | null): string {
  return x == null ? "—" : x.toFixed(3);
}

// AUC: higher is better. Cllr: lower is better. Returns the accent for the winning cell.
function win(a: number | null, b: number | null, higherWins: boolean): [boolean, boolean] {
  if (a == null || b == null || a === b) return [false, false];
  const aWins = higherWins ? a > b : a < b;
  return [aWins, !aWins];
}

// AUC in [0.5, 1] mapped to a 0–100% bar.
function bar(x: number | null): number {
  if (x == null) return 0;
  return Math.max(0, Math.min(100, ((x - 0.5) / 0.5) * 100));
}

function Metric({
  value,
  highlight,
  showBar = false,
}: {
  value: number | null;
  highlight: boolean;
  showBar?: boolean;
}) {
  return (
    <td className="px-2 py-2.5 text-center align-middle sm:px-3">
      <span className={`font-mono text-sm ${highlight ? "accent-text font-semibold" : "text-foreground/80"}`}>
        {fmt(value)}
      </span>
      {showBar && value != null && (
        <span className="mx-auto mt-1 block h-1 w-12 overflow-hidden rounded-full bg-foreground/10">
          <span
            className={`block h-full rounded-full ${highlight ? "bg-accent" : "bg-foreground/30"}`}
            style={{ width: `${bar(value)}%` }}
          />
        </span>
      )}
    </td>
  );
}

function DomainCard({ g }: { g: DomainGroup }) {
  if (!g.studies.length) return null;
  return (
    <div className="glass overflow-hidden rounded-2xl">
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1 border-b border-border px-4 py-3.5 sm:px-5">
        <h3 className="font-display text-base font-medium text-foreground">
          {g.domain}
          <span className="ml-2 rounded-full bg-foreground/[0.06] px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted">
            {g.domainTag}
          </span>
        </h3>
        <p className="text-xs text-muted">
          vs <span className="text-foreground/80">{g.baseline}</span> — {g.baselineNote}
        </p>
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[460px] border-collapse text-sm">
          <thead>
            <tr className="text-[11px] uppercase tracking-wider text-muted">
              <th className="px-4 py-2.5 text-left font-medium sm:px-5">Study</th>
              <th className="px-2 py-2.5 text-center font-medium sm:px-3">Verity AUC</th>
              <th className="px-2 py-2.5 text-center font-medium sm:px-3">{g.baseline} AUC</th>
              <th className="px-2 py-2.5 text-center font-medium sm:px-3">Verity C<sub>llr</sub></th>
              <th className="px-2 py-2.5 text-center font-medium sm:px-3">{g.baseline} C<sub>llr</sub></th>
            </tr>
          </thead>
          <tbody>
            {g.studies.map((s) => {
              const [vAuc, bAuc] = win(s.verity.auc, s.baseline.auc, true);
              const [vCllr, bCllr] = win(s.verity.cllr, s.baseline.cllr, false);
              return (
                <tr key={s.study} className="border-t border-border">
                  <td className="px-4 py-2.5 sm:px-5">
                    <div className="font-medium text-foreground">{s.study}</div>
                    <div className="text-[11px] text-muted">
                      {s.nKm} KM · {s.nKnm} KNM
                    </div>
                  </td>
                  <Metric value={s.verity.auc} highlight={vAuc} showBar />
                  <Metric value={s.baseline.auc} highlight={bAuc} showBar />
                  <Metric value={s.verity.cllr} highlight={vCllr} />
                  <Metric value={s.baseline.cllr} highlight={bCllr} />
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

export function Benchmarks() {
  return (
    <>
      <div className="mt-6 grid gap-5">
        {data.headToHead.map((g) => (
          <DomainCard key={g.domain} g={g} />
        ))}
      </div>

      {data.breadth.length > 0 && (
        <div className="glass mt-5 overflow-hidden rounded-2xl">
          <div className="border-b border-border px-4 py-3.5 sm:px-5">
            <h3 className="font-display text-base font-medium text-foreground">
              Validated on further studies
            </h3>
            <p className="text-xs text-muted">
              Verity, source-disjoint, on bullet studies where no specialist baseline was run here.
            </p>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[420px] border-collapse text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-muted">
                  <th className="px-4 py-2.5 text-left font-medium sm:px-5">Study</th>
                  <th className="px-2 py-2.5 text-center font-medium sm:px-3">Barrels</th>
                  <th className="px-2 py-2.5 text-center font-medium sm:px-3">AUC</th>
                  <th className="px-2 py-2.5 text-center font-medium sm:px-3">
                    C<sub>llr</sub>
                  </th>
                  <th className="px-2 py-2.5 text-center font-medium sm:px-3">
                    C<sub>llr</sub> min
                  </th>
                </tr>
              </thead>
              <tbody>
                {data.breadth.map((s) => (
                  <tr key={s.study} className="border-t border-border">
                    <td className="px-4 py-2.5 sm:px-5">
                      <div className="font-medium text-foreground">{s.study}</div>
                      <div className="text-[11px] text-muted">
                        {s.nKm} KM · {s.nKnm} KNM
                      </div>
                    </td>
                    <td className="px-2 py-2.5 text-center font-mono text-sm text-foreground/80 sm:px-3">
                      {s.nBarrels}
                    </td>
                    <Metric value={s.auc} highlight={false} showBar />
                    <td className="px-2 py-2.5 text-center font-mono text-sm text-foreground/80 sm:px-3">
                      {fmt(s.cllr)}
                    </td>
                    <td className="px-2 py-2.5 text-center font-mono text-sm text-muted sm:px-3">
                      {fmt(s.cllrMin)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </>
  );
}
