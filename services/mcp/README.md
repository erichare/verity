# Verity MCP server — forensic mark comparison for AI agents

An [MCP](https://modelcontextprotocol.io) server that exposes Verity's calibrated,
reproducible forensic comparison to any MCP client (Claude Desktop, Claude Code, …). It
wraps the REST API ([api.verity.codes](https://api.verity.codes)), so it inherits the
engine's guarantees and stays in sync with the deployment.

## Why this is safe to hand to an agent

Verity is unusually well-suited to an LLM, because the model **cannot fabricate a forensic
conclusion**:

- **The calibration firewall** — a likelihood ratio is only emitted when the score's
  scorer-config hash matches the reference's; otherwise the tool returns the raw score with
  `status: "uncalibrated"`, never a mis-scaled LR.
- **The scope guard** — an out-of-domain scan (wrong resolution, wrong mark type) is
  *refused*, returned as `status: "refused"` with the reason, not a guessed answer.
- **Reproducibility** — every comparison carries a content **handle**; the same inputs
  reproduce it, so a claim can be checked.

So "Claude, compare these two cartridge cases" yields a calibrated weight of evidence with
a reproducible recipe — or an honest refusal.

## Tools

| Tool | What it does |
|---|---|
| `detect_mark_type(scan)` | Suggest striated vs impressed for one `.x3p` scan. |
| `compare_marks(domain, mark_a, mark_b, scorer_config?)` | Calibrated LR + verbal weight + reference + content handle (or a refusal). |
| `calibrate_score(score, reference, scorer_config_hash?)` | Map a score → bounded LR (the firewall step). |
| `list_references()` | The calibration references + provenance (what each LR is calibrated on). |
| `scorer_config()` | The deployed scorer hyperparameters + hash. |
| `service_health()` | Status + calibrated domains. |

Scans are local `.x3p` file paths the agent already has access to; the server uploads them
to the API. Set `VERITY_API_URL` to point at the hosted instance (default) or your own.

## Install — Claude Code

Add to your project's `.mcp.json` (or `claude mcp add`), then approve the server:

```json
{
  "mcpServers": {
    "verity": {
      "type": "stdio",
      "command": "uv",
      "args": ["run", "--directory", "services/mcp", "verity-mcp"],
      "env": { "VERITY_API_URL": "https://api.verity.codes" }
    }
  }
}
```

`uv run` resolves the server's dependencies (`mcp`, `requests`) automatically. Without uv:
`pip install -e services/mcp && verity-mcp`.

## Install — Claude Desktop (one-click extension)

Build the `.mcpb` bundle and double-click it (Claude Desktop prompts for the API URL):

```bash
bash services/mcp/build_mcpb.sh   # → verity-forensics.mcpb
```

## Remote (hosted) endpoint

The same tools are also served **directly by the API** at
**`https://api.verity.codes/mcp`** (streamable HTTP, stateless) — no local install, nothing
to run. Add it as a remote MCP server:

```json
{
  "mcpServers": {
    "verity": { "type": "http", "url": "https://api.verity.codes/mcp" }
  }
}
```

The one difference from the stdio server above: a hosted server **cannot read your local
files**, so the scan-taking tools accept the `.x3p` bytes **inline, base64-encoded**
(`detect_mark_type(scan_base64)`, `compare_marks(domain, mark_a_base64, mark_b_base64)`)
rather than file paths. Everything else — the calibration firewall, the scope guard, the
reproducible recipe handles — is identical, because the endpoint runs the same engine as
the REST API. Use the **stdio** server when the agent already has the scans on disk (no
base64, no upload size to worry about); use the **remote** endpoint for zero-install access.

> Implementation note: the remote endpoint lives in the API service
> (`services/api/verity_api/mcp_server.py`, mounted at `/mcp`), not in this package — it
> shares the engine in-process. This package remains the stdio server for local file paths.

## Example

> **You:** Are these two cartridge cases from the same firearm? `case_A.x3p`, `case_B.x3p`
>
> **Claude** (via `compare_marks`): *moderately strong support for same source* (LR ≈ 146×),
> calibrated on the Fadul cartridge-case reference (AUC 0.997). Reproducible recipe handle
> `sha256:…`. This is a calibrated weight of evidence on a named reference, not a claim about
> the error rate of examination.

## Notes

- Mirrors the Python/R clients in [`clients/`](../../clients); the server adds agent-friendly
  summaries and surfaces refusals.
- stdio transport: the server never writes to stdout (it carries the JSON-RPC protocol).
- Tests: `cd services/mcp && PYTHONPATH=$PWD uv run --with pytest python -m pytest` (the
  formatters are unit-tested; the HTTP path is smoke-tested against a running API).
