import { ThemeToggle } from "@/components/theme/ThemeToggle";

/**
 * The shared top navigation for the site's content pages (Method, Why, Docs,
 * References, Partnership). The homepage keeps its own cinematic header (it has
 * a scrim/mask treatment and in-page anchors), but mirrors this same link set.
 *
 * One coherent definition of the nav lives here, so adding a destination is a
 * single edit. Links render as plain <a> tags to match the rest of the app.
 */

export interface NavLink {
  href: string;
  label: string;
  external?: boolean;
}

// The canonical site navigation. Order matters — left to right.
export const NAV_LINKS: NavLink[] = [
  { href: "/method", label: "Method" },
  { href: "/why", label: "Why" },
  { href: "/docs", label: "Docs" },
  { href: "/partnership", label: "Partnership" },
  { href: "/references", label: "References" },
  { href: "/whitepaper.pdf", label: "White paper", external: true },
  { href: "https://api.verity.codes/scalar", label: "API", external: true },
];

function NavAnchor({ link }: { link: NavLink }) {
  return (
    <a
      href={link.href}
      {...(link.external ? { target: "_blank", rel: "noopener noreferrer" } : {})}
      className="text-sm text-foreground/70 transition hover:text-foreground"
    >
      {link.label}
    </a>
  );
}

export function SiteNav() {
  return (
    <header className="fixed inset-x-0 top-0 z-30 backdrop-blur-md bg-[color-mix(in_srgb,var(--background)_55%,transparent)]">
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-6 py-4">
        <a href="/" className="font-display text-xl font-semibold tracking-tight">
          <span className="accent-text">Verity</span>
        </a>
        <div className="flex items-center gap-4 overflow-x-auto sm:gap-5">
          {NAV_LINKS.map((link) => (
            <NavAnchor key={link.label} link={link} />
          ))}
          <ThemeToggle />
        </div>
      </div>
    </header>
  );
}
