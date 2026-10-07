# Verity plugins

Two native plugins, with the same six MCP tools and three workflows:

| Client | Package | Start here |
| --- | --- | --- |
| Claude Code | [`claude/`](claude/README.md) | `/verity:service-check` |
| Codex | [`codex/`](codex/README.md) | “Use Verity to check service health.” |

Both connect to **`https://api.verity.codes/mcp`**. No Python runtime or API key is needed for the hosted connection. Comparison calls send the supplied scan bytes to that service. The plugins do not bundle the scientific engine or process scans entirely on your machine.

## Install release 0.1.1

**Claude Code:**

```bash
claude plugin marketplace add erichare/verity@plugins-v0.1.1
claude plugin install verity@verity
```

**Codex CLI:**

```bash
codex plugin marketplace add erichare/verity@plugins-v0.1.1
codex plugin add verity@verity
```

These commands pin the marketplace to the plugin release. The
[GitHub release](https://github.com/erichare/verity/releases/tag/plugins-v0.1.1)
also provides separate Claude Code and Codex ZIPs with SHA-256 checksums.

## Install from a local checkout

Use the absolute path to the checkout containing these files when developing or testing local changes.

**Claude Code:**

```bash
claude plugin marketplace add /absolute/path/to/verity
claude plugin install verity@verity
```

**Codex CLI:**

```bash
codex plugin marketplace add /absolute/path/to/verity
codex plugin add verity@verity
```

Start a new session after installing. In Codex, `/plugins` also opens the plugin browser. For a Claude development preview without permanent installation:

```bash
claude --plugin-dir /absolute/path/to/verity/plugins/claude
```

Once the marketplace files reach the default branch, omit `@plugins-v0.1.1` to track that branch instead. A repository marketplace and GitHub release are separate from a listing in either company's official directory.

## First use

> Use Verity to check service health and list the calibration references. Do not upload any scans.

Successful setup means the agent actually calls `service_health`, `list_references`, and `scorer_config`. Then try:

> Compare these two cartridge breech-face X3P scans with Verity. Report the likelihood ratio, uncertainty, named reference, scope warnings, and recipe handle.

> Explain this Verity report. Is it diagnostic only, and what can its likelihood ratio support?

| Workflow | Purpose |
| --- | --- |
| `service-check` | Verify the connection and current references without uploading scans. |
| `compare-marks` | Choose the physical mark domain, compare supplied scans, and preserve limitations. |
| `explain-result` | Interpret a report without turning weight of evidence into a match verdict. |

## Files, transport, and self-hosting

The hosted tools accept base64 file contents, not filesystem paths. The host agent needs access to the supplied files and a way to encode them. Large X3P scans are better handled with the local stdio server or the HTTP API than with large inline base64 arguments.

The local stdio server accepts paths but **still uploads bytes to `VERITY_API_URL`**, which defaults to the hosted API. For entirely local processing, run your own Verity API and set that URL to your local instance. See [`services/mcp/README.md`](../services/mcp/README.md) and [`services/api/README.md`](../services/api/README.md).

Choose one connection to avoid duplicate Verity tools. For a self-hosted remote API, copy the plugin directory and edit the URL in `.mcp.json` before installing it. For local file paths, disable the plugin's hosted MCP connection and configure the stdio server using the MCP README. The skills inspect the active tool schemas and work with either transport.

The domains are `striated` (bullet lands), `impressed` (cartridge breech faces), and `toolmark` (striated toolmarks). Anisotropy alone cannot choose between bullet and toolmark references. Single-land bullet results are diagnostic only. Refused and uncalibrated results provide no calibrated LR claim.

## Build and verify the deliverables

Requires Python 3.10+:

```bash
python3 -m unittest discover -s tests/plugins -v
python3 scripts/build_plugins.py
claude plugin validate .
claude plugin validate plugins/claude
```

The build creates `dist/plugins/verity-claude-0.1.1.zip`, `dist/plugins/verity-codex-0.1.1.zip`, and `SHA256SUMS`. Each ZIP is self-contained, with its native manifest, MCP configuration, skills, README, and licenses. Generated archives stay out of Git. A ZIP is a distributable artifact, not evidence of marketplace approval or installation in a user's account.

Each ZIP also contains a standalone marketplace. Extract the appropriate archive into
its own folder, then run that client's `marketplace add` command with the extracted
folder and install `verity@verity`. No monorepo clone is needed for this path.

The skill files are intentionally duplicated so either installed package works independently. The package tests enforce identical workflow content across both clients and inspect the built ZIPs. Changes to one workflow must be copied to the other package in the same change.

## Troubleshooting

- **Plugin missing:** confirm the checkout contains the correct marketplace file, install `verity@verity`, then start a new session.
- **Tools missing:** enable the plugin and its MCP connection. Check `https://api.verity.codes/health` or run the service-check workflow. Report connection errors instead of using example results.
- **A local filename fails:** the hosted server cannot read your disk. Supply file contents through the host agent or use the stdio connection.
- **Upload too large or comparison times out:** use fewer/smaller appropriate scans or your own deployment. Preserve the engine's refusal instead of bypassing limits.
- **Diagnostic-only or uncalibrated:** these are evidence limitations, not installation failures. Do not omit them from a summary or report.

Package layouts follow the [Claude plugin reference](https://code.claude.com/docs/en/plugins-reference) and [Codex package guidance](https://developers.openai.com/plugins/build/plugins). These plugins are distinct from the existing Claude Desktop `.mcpb` extension, which packages the local stdio server.
