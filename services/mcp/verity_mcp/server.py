"""Verity MCP server — calibrated, reproducible forensic surface comparison for AI agents.

Exposes the Verity API as MCP tools. Verity is unusually safe to hand to an agent: the
calibration firewall means a likelihood ratio is only emitted when the score's scorer
config matches the reference's, the scope guard refuses out-of-domain inputs, and every
result carries a reproducible recipe handle. So an agent gets a calibrated, auditable
answer — or an honest refusal — never a fabricated number.

The server wraps the REST API (set ``VERITY_API_URL``; default ``https://api.verity.codes``),
so it inherits the firewall and stays in sync with the deployment.

stdio transport note: never write to stdout (it carries the JSON-RPC protocol); the SDK
keeps it clean and any diagnostics must go to stderr.
"""

from __future__ import annotations

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from .api import VerityAPI, summarize_compare

mcp = FastMCP("verity")
_api = VerityAPI()

# Read-only analysis and metadata lookups still contact the configured remote API.
# Scan files are uploaded for analysis, but are never modified by these tools.
_TOOL_ANNOTATIONS = ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=True,
)


@mcp.tool(title="Check Verity service health", annotations=_TOOL_ANNOTATIONS)
def service_health() -> dict:
    """Verity service status and the mark types (domains) it can calibrate."""
    return _api.health()


@mcp.tool(title="Detect surface mark type", annotations=_TOOL_ANNOTATIONS)
def detect_mark_type(scan: str) -> dict:
    """Suggest whether a 3-D surface scan (.x3p) is a STRIATED mark (bullet land, toolmark)
    or an IMPRESSED mark (cartridge breech face), from striation anisotropy. `scan` is a
    local file path. This detects surface physics, not the calibration population: bullet
    lands use domain `striated`, while striated screwdriver marks use `toolmark`. Confirm
    the source material and domain before comparing."""
    return _api.detect(scan)


@mcp.tool(title="Compare forensic marks", annotations=_TOOL_ANNOTATIONS)
def compare_marks(
    domain: str,
    mark_a: list[str],
    mark_b: list[str],
    scorer_config: dict | None = None,
) -> dict:
    """Compare two forensic marks into a CALIBRATED likelihood ratio with a reproducible
    recipe handle and region-level attribution.

    - `domain`: "striated" (bullet lands), "impressed" (cartridge breech faces), or
      "toolmark" (striated screwdriver-style toolmarks). Toolmarks and bullet lands use
      different calibration populations. Passing a toolmark as `striated` yields an
      invalid LR even if the physical-modality guard accepts it.
    - `mark_a`, `mark_b`: local .x3p file paths — one per side for impressed; for a bullet,
      pass ALL of that bullet's land scans (aggregating the lands is the strong path).
      A single-land striated result is diagnostic only, not reportable evidence.
    - `scorer_config`: optional hyperparameter override (e.g. {"lambda_c": 8e-6}); if it
      doesn't match the reference's config, the result is the raw score with NO calibrated
      LR (the firewall).

    Returns the likelihood ratio + ENFSI verbal weight, the named reference it is calibrated
    on, the content handle (the same inputs reproduce it), and any scope caveats — or an
    honest refusal if an input is outside the validated domain. This is a calibrated weight
    of evidence on a named reference, not a claim about the error rate of examination."""
    return summarize_compare(_api.compare(domain, mark_a, mark_b, scorer_config))


@mcp.tool(title="List calibration references", annotations=_TOOL_ANNOTATIONS)
def list_references() -> list[dict]:
    """The calibration reference populations and their provenance — the scorer-config hash
    each was built under, its source datasets, and its discrimination/calibration
    diagnostics (AUC, Cllr). This is exactly what every likelihood ratio is calibrated on."""
    return _api.references()


@mcp.tool(title="Read scorer configuration", annotations=_TOOL_ANNOTATIONS)
def scorer_config() -> dict:
    """The deployed scorer hyperparameters and their content hash. A calibrated LR is valid
    only against a reference built under this same config hash (the firewall)."""
    return _api.scorer_config()


@mcp.tool(title="Calibrate a comparison score", annotations=_TOOL_ANNOTATIONS)
def calibrate_score(score: float, reference: str, scorer_config_hash: str | None = None) -> dict:
    """Map a comparison score to a bounded likelihood ratio against a named reference
    ("striated" | "impressed" | "toolmark" | "striated_single"), with its calibration curve
    and credible interval. If `scorer_config_hash` is given and doesn't match the reference's,
    calibration is refused (the firewall). If omitted, `config_verified` is false: this
    maps a caller-supplied score and does not establish its provenance or reportability."""
    return _api.calibrate(score, reference, scorer_config_hash)


def main() -> None:
    """Run the server over stdio (the entry point for Claude Desktop / Claude Code)."""
    mcp.run()


if __name__ == "__main__":
    main()
