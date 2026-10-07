import type { Metadata } from "next";
import { CodeBlock } from "@/components/docs/CodeBlock";
import { Reveal } from "@/components/Reveal";
import { LinkArrow } from "@/components/LinkArrow";

const TITLE = "Claude Code & Codex plugins — Verity";
const DESCRIPTION =
  "Install Verity for Claude Code or Codex. Compare forensic marks, explain calibrated evidence, and check the service with purpose-built skills and the hosted MCP server.";

export const metadata: Metadata = {
  title: { absolute: TITLE },
  description: DESCRIPTION,
  alternates: { canonical: "/plugins" },
  openGraph: {
    type: "website",
    title: TITLE,
    description: DESCRIPTION,
    url: "/plugins",
  },
};

const PLUGINS = [
  {
    name: "Claude Code",
    path: "plugins/claude",
    code: "claude plugin marketplace add erichare/verity@plugins-v0.1.0\nclaude plugin install verity@verity",
    verify: "Open Claude Code and run /verity:service-check.",
  },
  {
    name: "Codex",
    path: "plugins/codex",
    code: "codex plugin marketplace add erichare/verity@plugins-v0.1.0\ncodex plugin add verity@verity",
    verify: "Open a new Codex chat and ask it to use the Verity service-check skill.",
  },
];

export default function PluginsPage() {
  return (
    <main id="main" className="mx-auto w-full max-w-6xl px-6 pb-24 pt-28 sm:pt-36">
      <section className="rise max-w-3xl">
        <p className="font-mono text-xs uppercase tracking-wider text-accent">Verity for agents</p>
        <h1 className="mt-4 font-display text-4xl font-semibold leading-tight tracking-tight sm:text-6xl">
          Claude Code &amp; Codex plugins
        </h1>
        <p className="mt-6 text-lg leading-relaxed text-foreground/80">
          Bring Verity&rsquo;s calibrated comparison into your agent. Each plugin connects the same
          hosted MCP server and adds three skills for checking the service, comparing scans, and
          explaining the evidence with its limits intact.
        </p>
        <p className="mt-4 text-sm leading-relaxed text-muted">
          Research preview. Verity reports a weight of evidence with uncertainty and scope.
          The examiner makes the decision.
        </p>
      </section>

      <Reveal>
        <section aria-labelledby="install-title" className="mt-12 border-t border-border pt-8">
          <h2 id="install-title" className="font-display text-2xl font-medium">Install release 0.1.0</h2>
          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-foreground/80">
            Add Verity&rsquo;s repository marketplace and install the plugin for your client.
            These commands pin version 0.1.0. You can also download separate plugin ZIPs and
            checksums from the{" "}
            <a href="https://github.com/erichare/verity/releases/tag/plugins-v0.1.0" className="text-accent hover:underline">
              GitHub release
            </a>.
          </p>
          <div className="mt-6 grid gap-6 lg:grid-cols-2">
            {PLUGINS.map((plugin) => (
              <article key={plugin.name} className="glass min-w-0 rounded-2xl p-6">
                <p className="font-mono text-[11px] uppercase tracking-wider text-muted">{plugin.path}</p>
                <h3 className="mt-2 font-display text-2xl font-medium">{plugin.name}</h3>
                <p className="mb-5 mt-2 text-sm text-foreground/75">
                  Plugin <code className="font-mono text-xs">verity</code> · marketplace{" "}
                  <code className="font-mono text-xs">verity</code>
                </p>
                <CodeBlock label="Terminal" code={plugin.code} />
                <p className="mt-4 text-sm leading-relaxed text-foreground/80">{plugin.verify}</p>
              </article>
            ))}
          </div>
          <p className="mt-5 text-sm text-muted">
            Use a current client with plugin support. Approve the Verity MCP connection when the
            client prompts, then verify that service-check returns the service health and available
            references before comparing scans.
          </p>
        </section>
      </Reveal>

      <Reveal>
        <section aria-labelledby="skills-title" className="mt-12 border-t border-border pt-8">
          <h2 id="skills-title" className="font-display text-2xl font-medium">Three clear starting points</h2>
          <div className="mt-6 grid gap-6 md:grid-cols-3">
            {[
              ["service-check", "Check the connection", "Confirm health, calibrated references, and scorer configuration before a comparison."],
              ["compare-marks", "Compare X3P scans", "Supply the mark type and both sets of scans. For bullets, include every available land of each bullet."],
              ["explain-result", "Read the evidence", "Explain the LR, uncertainty, reference population, diagnostic cautions, and scope without turning the result into a verdict."],
            ].map(([skill, title, description]) => (
              <article key={skill} className="rounded-xl border border-border p-5">
                <code className="font-mono text-xs text-accent">{skill}</code>
                <h3 className="mt-3 font-display text-lg font-medium">{title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-foreground/75">{description}</p>
              </article>
            ))}
          </div>
        </section>
      </Reveal>

      <Reveal>
        <section aria-labelledby="connection-title" className="mt-12 max-w-3xl border-t border-border pt-8">
          <h2 id="connection-title" className="font-display text-2xl font-medium">The connection and your scans</h2>
          <p className="mt-4 text-sm leading-relaxed text-foreground/80">
            Both plugins use <code className="font-mono text-xs">https://api.verity.codes/mcp</code>{" "}
            over streamable HTTP. Remote comparisons send the scan bytes as base64 to that service.
            A file path alone is not an upload. The agent needs access to the files and a way to encode
            them before calling the remote tools.
          </p>
          <p className="mt-4 text-sm leading-relaxed text-foreground/80">
            For path-based inputs, the local stdio server reads files and sends them to the configured
            comparison API. Set <code className="font-mono text-xs">VERITY_API_URL</code> to your own
            running API when the scan processing needs to stay local. The Claude Desktop bundle is a
            separate integration from the Claude Code plugin.
          </p>
          <div className="mt-5 flex flex-wrap gap-x-6 gap-y-3 text-sm">
            <a href="/docs#mcp" className="text-accent hover:underline">
              MCP setup and tools<LinkArrow className="ml-1" />
            </a>
            <a href="https://github.com/erichare/verity" className="text-accent hover:underline">
              Source and plugin README<LinkArrow kind="external" className="ml-1" />
            </a>
          </div>
          <p className="mt-4 text-xs text-muted">
            In the checkout, see <code className="font-mono">plugins/README.md</code> for local stdio
            configuration, verification, and troubleshooting.
          </p>
        </section>
      </Reveal>
    </main>
  );
}
