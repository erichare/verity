import methodData from "@/lib/method-data.json";

interface CalibrationSlice {
  auc: number;
  cllr: number;
  nKm: number;
  nKnm: number;
}
interface OthersSlice {
  cartridge?: unknown;
  screwdriver?: unknown;
}
const data = methodData as unknown as { calibration: CalibrationSlice; others?: OthersSlice };

// Real figures from the bullet-land reference + the count of mark types the
// same pipeline runs on (bullet, plus whichever "others" examples exist).
function buildStats(): { value: string; label: string }[] {
  const cal = data.calibration;
  const markTypes = 1 + Object.values(data.others ?? {}).filter(Boolean).length;
  return [
    { value: cal.auc.toFixed(2), label: "Reference AUC" },
    { value: cal.cllr.toFixed(2), label: "Cllr (cost)" },
    {
      value: `${cal.nKm.toLocaleString("en-US")} + ${cal.nKnm.toLocaleString("en-US")}`,
      label: "Reference pairs",
    },
    { value: `${markTypes}`, label: "Mark types, one pipeline" },
  ];
}

/** A thin row of real, verifiable numbers — the credibility the hero was missing. */
export function StatBand({ className }: { className?: string }) {
  const stats = buildStats();
  return (
    <dl
      className={`mx-auto flex max-w-2xl flex-wrap items-stretch justify-center gap-x-8 gap-y-4 ${className ?? ""}`}
    >
      {stats.map((s) => (
        <div key={s.label} className="flex flex-col items-center text-center">
          <dt className="font-mono text-2xl font-semibold accent-text sm:text-3xl">{s.value}</dt>
          <dd className="mt-0.5 text-[11px] uppercase tracking-wider text-muted">{s.label}</dd>
        </div>
      ))}
    </dl>
  );
}
