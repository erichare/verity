# Verity for Claude Code

Compare forensic X3P scans and explain calibrated likelihood ratios with explicit evidence limits.

## Install

Install release 0.1.1 from the repository marketplace:

```bash
claude plugin marketplace add erichare/verity@plugins-v0.1.1
claude plugin install verity@verity
```

For a downloaded ZIP, extract it and use the absolute extracted directory instead of `erichare/verity@plugins-v0.1.1` in `marketplace add`. The archive includes its own marketplace. A local checkout path also works. Start a new session after installation.

For a preview without installation, run `claude --plugin-dir /absolute/path/to/extracted-plugin`. The folder must directly contain `.claude-plugin/plugin.json`.

## Use

- `/verity:service-check` — check the service and references without uploading scans.
- `/verity:compare-marks` — compare supplied scans with the appropriate reference.
- `/verity:explain-result` — explain a report's uncertainty, provenance, and limits.

First prompt: **“Use Verity to check service health and list the calibration references. Do not upload any scans.”**

The plugin connects to `https://api.verity.codes/mcp` over Streamable HTTP. No local Python runtime or API key is required. It provides `service_health`, `list_references`, `scorer_config`, `detect_mark_type`, `compare_marks`, and `calibrate_score`.

Comparison tools upload base64 X3P bytes to the hosted service. The server cannot read local paths. Your agent must read and encode only the files supplied for the task. For large files or a self-hosted API, use the local stdio setup in the [MCP documentation](https://github.com/erichare/verity/tree/plugins-v0.1.1/services/mcp). Local stdio also uploads bytes unless it points at a local API.

Choose `striated` for bullet lands, `impressed` for cartridge breech faces, and `toolmark` for striated toolmarks. Single-land bullet results are diagnostic only. Preserve every refusal, scope warning, and evidence restriction. Verity reports weight of evidence on a named reference, never an identity or match verdict.

If tools are missing, enable the plugin and restart the session. If the service is unreachable, report that error. See the repository's [plugin guide](https://github.com/erichare/verity/tree/plugins-v0.1.1/plugins) for self-hosting and build instructions. This package is not the Claude Desktop `.mcpb` extension.
