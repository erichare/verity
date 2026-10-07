---
name: service-check
description: Check that the Verity plugin is connected and inspect available forensic domains, calibration references, scorer configuration, and provenance without uploading scans. Use for setup verification and connection troubleshooting.
---

# Check Verity readiness

1. Find the Verity tools from the installed plugin. If unavailable, ask the user to enable the plugin and start a new session. Do not claim setup success based on a manifest alone.
2. Call `service_health`, `list_references`, and `scorer_config`.
3. Report service status, available domains, named references, and current scorer-config hash from the responses. Explain reference/scorer mismatches as a reason to investigate before calibrating. Do not fabricate missing metadata.
4. Distinguish a working connection from validation of the forensic method and from the admissibility of any future result. This check uploads no scans and performs no comparison.

The packaged endpoint is `https://api.verity.codes/mcp` using Streamable HTTP. If unreachable, report the actual error and consult the README's local stdio or self-hosted options. Do not alter account settings, disable transport protections, install unrelated packages, or change server destinations without the user's request.

A useful first prompt is: “Use Verity to check service health and list the calibration references. Do not upload any scans.”
