"""The reproducible recipe — the "methods section as JSON" for one comparison.

Given a finished comparison response, the domain, the running scorer config, and the
reference's provenance sidecar, assemble the ordered pipeline (every step, its
parameters, the engine version, and the input/reference hashes) plus a content-hash
**handle** over that recipe. Two runs that produce the same handle are the same
computation on the same inputs --- reproducibility as a hash-equality check.

No new computation: every value here already lives in the response or the committed
reference. This is the glass-box answer to the black-box critique, made addressable.
"""

from __future__ import annotations

import hashlib
import json

from verity.decision import DEFAULT_SCORER_CONFIG, ScorerConfig, default_n_boot


def _canonical(obj: object) -> str:
    """Deterministic JSON for hashing: sorted keys, no whitespace, stable float repr."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), default=str)


def _round(value: object, ndigits: int = 6) -> object:
    """Round floats (recursively) so a content handle is stable against last-digit
    floating-point noise across platforms; leaves everything else untouched."""
    if isinstance(value, float):
        return round(value, ndigits)
    if isinstance(value, dict):
        return {k: _round(v, ndigits) for k, v in value.items()}
    if isinstance(value, list):
        return [_round(v, ndigits) for v in value]
    return value


def _steps(domain: str, cfg: ScorerConfig, provenance: dict, reference: dict) -> list[dict]:
    """The ordered pipeline for this modality, each step naming its code path and the
    exact parameters it ran under --- the auditable trail from scan to LR."""
    striated = domain == "striated"
    input_hashes = provenance.get("input_hashes")
    signature_step = (
        {
            "step": "signature",
            "code": "verity.signature.striation_signature",
            "params": {
                "lambda_s": cfg.lambda_s,
                "lambda_c": cfg.lambda_c,
                "form_degree": 2,
                "orient": "fft-power-spectrum",
                "keep": 0.5,
            },
            "produces": "1-D across-striae signature (FFT-oriented, groove-cropped)",
        }
        if striated
        else {
            "step": "areal-signature",
            "code": "verity.areal.areal_signature",
            "params": {
                "lambda_s": cfg.lambda_s,
                "lambda_c": cfg.lambda_c,
                "decimate": 5,
                "size": 256,
            },
            "produces": "decimated 2-D areal map",
        }
    )
    compare_step = (
        {
            "step": "compare",
            "code": "verity.aggregate.bullet_comparison + verity.decision.scorer.ContrastScorer",
            "params": {"metric": "normalized cross-correlation", "scorer": cfg.name},
            "produces": "land×land CCF matrix; diag_contrast = matched diagonal minus background",
        }
        if striated
        else {
            "step": "compare",
            "code": "verity.cmr.cmr_count (areal_votes -> consensus_members)",
            "params": {"cmr_corr": cfg.cmr_corr, "cmr_tol": list(cfg.cmr_tol)},
            "produces": "congruent matching regions (2-D cells under translation+rotation)",
        }
    )
    return [
        {
            "step": "decode",
            "code": "verity_x3p.read_x3p",
            "params": {},
            "inputs": input_hashes,
            "produces": "height field + pixel pitch (SI metres)",
        },
        {
            "step": "preprocess",
            "code": "verity.preprocess",
            "params": {"form_degree": 2, "lambda_s": cfg.lambda_s, "lambda_c": cfg.lambda_c},
            "produces": "ISO 25178 form removal + ISO 16610 roughness band (NaN-aware)",
        },
        signature_step,
        compare_step,
        {
            "step": "calibrate",
            "code": "verity.decision.lr.ScoreLRModel",
            "params": {"method": "logistic", "lr_bound": "auto"},
            "reference": reference,
            "produces": "monotone, ELUB-bounded score -> likelihood ratio",
        },
        {
            "step": "uncertainty",
            "code": "verity.decision.uncertainty.lr_credible_interval",
            # n_boot is the deployment's resolved VERITY_LR_BOOTSTRAP_N and is part
            # of the content-addressed recipe: a deployment running fewer replicates
            # is a different computation, so it (correctly) gets different handles.
            "params": {
                "n_boot": default_n_boot(),
                "seed": 0,
                "resample": "clustered when source IDs present",
            },
            "produces": "percentile credible interval on log10 LR",
        },
    ]


def build_recipe(
    resp: dict, *, domain: str, reference_provenance: dict, config: ScorerConfig | None = None
) -> dict:
    """Assemble the methods-as-JSON recipe for a comparison response and stamp it with a
    content-hash handle. ``reference_provenance`` is the reference's sidecar dict."""
    cfg = config or DEFAULT_SCORER_CONFIG
    prov = resp.get("provenance", {}) or {}
    reference = {
        "name": (resp.get("reference") or {}).get("name"),
        "scorer_config_hash": reference_provenance.get("scorer_config_hash"),
        "datasets": reference_provenance.get("datasets"),
        "diagnostics": reference_provenance.get("diagnostics"),
        "cluster_scheme": reference_provenance.get("cluster_scheme"),
        "git_commit": reference_provenance.get("git_commit"),
    }
    result = _round(
        {
            "score": resp.get("score"),
            "score_kind": resp.get("score_kind"),
            "likelihood_ratio": resp.get("likelihood_ratio"),
            "log10_lr": resp.get("log10_lr"),
            "log10_lr_ci": [resp.get("log10_lr_ci_lo"), resp.get("log10_lr_ci_hi")],
            "lr_ci_method": resp.get("lr_ci_method"),
            "lr_bound_log10": resp.get("lr_bound_log10"),
            "direction": resp.get("direction"),
            "verbal": resp.get("verbal"),
        }
    )
    recipe = {
        "engine_version": prov.get("engine_version"),
        "api_version": prov.get("api_version"),
        "domain": domain,
        "scorer_config": cfg.to_dict(),
        "scorer_config_hash": cfg.config_hash,
        "inputs": prov.get("input_hashes"),
        "reference": reference,
        "result": result,
        "steps": _steps(domain, cfg, prov, reference),
        "replay": (
            "POST /v1/compare with the same scans, domain, and scorer config (hash above) "
            "reproduces this handle; calibration is valid only when reference.scorer_config_hash "
            "matches scorer_config_hash."
        ),
    }
    recipe["handle"] = "sha256:" + hashlib.sha256(_canonical(recipe).encode("utf-8")).hexdigest()
    return recipe
