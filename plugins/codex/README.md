# Verity for Codex

Compare forensic X3P scans and explain calibrated likelihood ratios with explicit evidence limits.

## Install

Install release 0.1.0 from the repository marketplace:

```bash
codex plugin marketplace add erichare/verity@plugins-v0.1.0
codex plugin add verity@verity
```

For a downloaded ZIP, extract it and use the absolute extracted directory instead of `erichare/verity@plugins-v0.1.0` in `marketplace add`. The archive includes its own marketplace, with the plugin directly at its root. A local checkout path also works.

Start a new session. You can also run `/plugins` in the Codex CLI and select Verity from the configured marketplace. The package manifest is `.codex-plugin/plugin.json`.

## Use

First prompt: **“Use Verity to check service health and list the calibration references. Do not upload any scans.”**

The plugin provides three skills: `service-check`, `compare-marks`, and `explain-result`. Ask for the workflow by name or select it from the available skills. Example: **“Use Verity to compare these two cartridge breech-face X3P scans. Include the reference, uncertainty, scope warnings, and recipe handle.”**

The plugin connects to `https://api.verity.codes/mcp` over Streamable HTTP. No local Python runtime or API key is required. It provides `service_health`, `list_references`, `scorer_config`, `detect_mark_type`, `compare_marks`, and `calibrate_score`.

Comparison tools upload base64 X3P bytes to the hosted service. The server cannot read local paths. Your agent must read and encode only the files supplied for the task. For large files or a self-hosted API, use the local stdio setup in the [MCP documentation](https://github.com/erichare/verity/tree/plugins-v0.1.0/services/mcp). Local stdio also uploads bytes unless it points at a local API.

Choose `striated` for bullet lands, `impressed` for cartridge breech faces, and `toolmark` for striated toolmarks. Single-land bullet results are diagnostic only. Preserve every refusal, scope warning, and evidence restriction. Verity reports weight of evidence on a named reference, never an identity or match verdict.

If tools are missing, enable the plugin and restart the session. If the service is unreachable, report that error. See the repository's [plugin guide](https://github.com/erichare/verity/tree/plugins-v0.1.0/plugins) for self-hosting and build instructions. This package is not a public directory listing or a change to your account settings.
