import methodData from "@/lib/method-data.json";
import { formatLRx } from "@/lib/format";

interface MarkExample {
  lr: number;
  verbal: string;
  reference: { name: string; auc: number };
}
const data = methodData as unknown as {
  km: MarkExample;
  others?: { cartridge?: MarkExample; screwdriver?: MarkExample };
};

interface Card {
  badge: string;
  title: string;
  ex?: MarkExample;
}
const CARDS: Card[] = [
  { badge: "Striated · bullet land", title: "Bullet", ex: data.km },
  { badge: "Impressed · breech face", title: "Cartridge case", ex: data.others?.cartridge },
  { badge: "Striated · toolmark", title: "Screwdriver", ex: data.others?.screwdriver },
];

/** Proof of generality: the same pipeline, three different mark types, three real LRs. */
export function MarkBreadth() {
  const cards = CARDS.filter((c): c is Required<Card> => Boolean(c.ex));
  return (
    <section>
      <div className="text-center">
        <span className="glass inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs text-foreground/70">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" />
          Same pipeline, zero re-tuning
        </span>
        <h2 className="mt-5 font-display text-2xl font-medium text-foreground sm:text-3xl">
          One method, <span className="accent-text">three kinds of mark</span>
        </h2>
        <p className="mx-auto mt-3 max-w-2xl text-sm leading-relaxed text-foreground/80">
          Bullets, cartridge breech faces, toolmarks — no mark-specific feature engineering. Only
          the registration changes (a 1-D shift, or a 2-D shift-plus-rotation); everything else is
          shared.
        </p>
      </div>

      <div className="mt-8 grid gap-4 sm:grid-cols-3">
        {cards.map((c) => {
          const positive = c.ex.lr >= 1;
          return (
            <div key={c.title} className="glass flex flex-col rounded-2xl p-5">
              <span className="self-start rounded-full bg-foreground/[0.06] px-2.5 py-1 text-[11px] uppercase tracking-wider text-muted">
                {c.badge}
              </span>
              <h3 className="mt-3 font-display text-lg font-medium text-foreground">{c.title}</h3>
              <p
                className={`mt-2 font-mono text-4xl font-semibold ${
                  positive ? "accent-text" : "text-oxblood"
                }`}
              >
                {formatLRx(c.ex.lr)}
              </p>
              <p className="mt-2 text-xs leading-snug text-foreground/70">{c.ex.verbal}.</p>
              <p className="mt-auto pt-3 text-[11px] text-muted">
                {c.ex.reference.name} · AUC {c.ex.reference.auc.toFixed(3)}
              </p>
            </div>
          );
        })}
      </div>

      <div className="mt-6 text-center">
        <a
          href="/method"
          className="glass inline-block rounded-full px-6 py-3 text-sm font-medium text-foreground/80 transition hover:text-foreground"
        >
          Watch it generalize, step by step →
        </a>
      </div>
    </section>
  );
}
