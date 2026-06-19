"""Generate the homepage "studio" pipeline tour from REAL marks.

Sibling of :mod:`verity.examples.build_gallery`. Where ``build_gallery`` emits
``services/web/lib/gallery.json`` (specimens + final, calibrated comparisons), this
emits ``services/web/lib/tour.json`` — the *same* real comparisons, on the *same*
committed references and the *same* local caches, enriched with the **per-stage
intermediate artifacts** so the web studio can animate every step of the pipeline:
raw surface -> form-removed / bandpassed -> FFT-oriented -> 1-D signature ->
alignment -> the per-cell / per-window CMR votes and their consensus cluster ->
calibrated likelihood ratio.

Every number is computed by the real engine on real catalog marks — nothing is
fabricated, no new data dependency is introduced. It reuses ``build_gallery``'s
data discovery, specimen/pair selection, JSON-encoding helpers and its
scorer-config-hash stamping verbatim (imported), so a tour comparison's ``report``
and ``calibration`` are byte-identical to the gallery's for the same pair; only the
extra ``stages`` object is new.

The one artifact the API does *not* expose is the per-vote CMR cluster (each cell /
window's best-fit transform, correlation, home location, and whether it is a member
of the winning consensus). That is emitted here straight from the engine
(:func:`verity.cmr.striated_votes` / :func:`verity.cmr.areal_votes` +
:func:`verity.cmr.consensus_members`).

Writes ``services/web/lib/tour.json``. Reproducible from the committed references +
the local caches; no network. There is no ``pyproject`` ``[project.scripts]`` entry
for this script (do not add one); run it directly with the engine env:

    cd services/engine && uv run python -m verity.examples.build_tour

(the gallery equivalent is ``uv run verity-build-gallery``).
"""

from __future__ import annotations

import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from verity import land_trace
from verity.areal import areal_signature
from verity.cmr import (
    areal_votes,
    cmr_regions_1d_pair,
    cmr_score_1d,
    consensus_members,
    striated_votes,
)
from verity.compare import (
    _land_fields,
    _to_preview,
    compare_bullets_with_previews,
    compare_with_previews,
)
from verity.decision import DEFAULT_SCORER_CONFIG

# Reuse build_gallery's data discovery, ID/label helpers, selection and the JSON
# encoders verbatim — the tour's specimens/comparisons must match the gallery's
# exactly (only `stages` is added). These are module-level functions/constants in
# build_gallery, so importing keeps a single source of truth.
from verity.examples.build_gallery import (
    _REF_BULLET,
    _REF_CART,
    _REF_TOOL,
    _THUMB,
    _TM_IDS,
    _TM_PAIRS,
    _bullet_id,
    _bullet_label,
    _bullets,
    _calibration,
    _norm_sig,
    _round_grid,
    _surface,
    _tool_id,
    _tool_label,
)
from verity.report import build_comparison_report
from verity.trace import LandTrace

_CFG = DEFAULT_SCORER_CONFIG
_ROOT = Path(__file__).resolve().parents[4]
_OUT = _ROOT / "services/web/lib/tour.json"

_SURF = 56  # final comparison preview grid (matches build_gallery's _SURF)
_GRID = 120  # per-stage 2-D preview grid (matches intermediates.py's default)
_SIG_MAX = 512  # per-stage 1-D signature cap (matches intermediates.py's default)


# ── stage encoders ──────────────────────────────────────────────────────────
# Replicated (not imported) from services/api/verity_api/intermediates.py:
# `_downsample_grid` and `_decimate_1d`. They live in the *API* package; importing
# across services would add an engine->api dependency, so the two small functions
# are mirrored here with identical sizes/normalization (~120 grid, <=512 signature,
# 2-98 percentile clip to [0,1], NaN -> 0) so tour grids match the API's previews.
def _downsample_grid(arr: np.ndarray, size: int = _GRID) -> list[list[float]]:
    a = np.asarray(arr, dtype=np.float64)
    step = max(1, max(a.shape) // size)
    small = a[::step, ::step][:size, :size]
    finite = small[np.isfinite(small) & (small != 0.0)]
    if finite.size:
        lo, hi = np.percentile(finite, [2, 98])
        small = np.clip((small - lo) / (hi - lo + 1e-9), 0.0, 1.0)
    return np.nan_to_num(small).round(4).tolist()


def _decimate_1d(arr: np.ndarray, max_len: int = _SIG_MAX) -> list[float]:
    a = np.asarray(arr, dtype=np.float64)
    if a.size > max_len:
        a = a[:: a.size // max_len + 1]
    return np.nan_to_num(a).round(5).tolist()


def _trace_stages(trace: LandTrace) -> dict:
    """The raw / bandpassed / rotated stages of one land (mirrors
    intermediates.trace_dict's grids + scalars)."""
    return {
        "raw": _downsample_grid(trace.raw),
        "bandpassed": _downsample_grid(trace.bandpassed),
        "rotated": _downsample_grid(trace.rotated),
        "tiltDeg": round(float(trace.tilt_deg), 3),
        "striaeAngleDeg": round(float(trace.striae_angle_deg), 3),
        "crop": [int(trace.crop[0]), int(trace.crop[1])],
        "shapeRaw": [int(trace.raw.shape[0]), int(trace.raw.shape[1])],
    }


def _striated_votes_stage(sig_a: np.ndarray, sig_b: np.ndarray) -> dict:
    """The per-window 1-D CMR votes + the winning consensus cluster. Each vote
    carries its best lag, registration correlation, home/window location, and an
    ``inConsensus`` flag — the artifact the API does not expose."""
    votes = striated_votes(sig_a, sig_b)
    members = consensus_members(
        votes, corr_thresh=_CFG.cmr_1d_corr, transform_tol=(_CFG.cmr_1d_lag,)
    )
    member_keys = {id(v) for v in members}
    length = max(len(sig_a), 1)
    out_votes = [
        {
            "lag": round(float(transform[0]), 2),
            "corr": round(float(corr), 4),
            "home": int(home),
            "window": int(window),
            "homeFrac": round(home / length, 4),
            "inConsensus": id(votes[k]) in member_keys,
        }
        for k, (transform, corr, (home, window)) in enumerate(votes)
    ]
    return {
        "kind": "striated-1d",
        "votes": out_votes,
        "nTotal": len(out_votes),
        "nConsensus": len(members),
        "corrThresh": float(_CFG.cmr_1d_corr),
        "lagTol": float(_CFG.cmr_1d_lag),
    }


def _areal_votes_stage(sig_a: np.ndarray, sig_b: np.ndarray) -> dict:
    """The per-cell 2-D CMR (CMC) votes + the winning consensus cluster. Each cell
    votes its best ``(dy, dx, theta)`` registration; ``inConsensus`` marks the
    congruent matching regions that drove the score."""
    votes = areal_votes(sig_a, sig_b)
    members = consensus_members(votes, corr_thresh=_CFG.cmr_corr, transform_tol=_CFG.cmr_tol)
    member_keys = {id(v) for v in members}
    h, w = sig_a.shape
    out_votes = [
        {
            "dy": round(float(transform[0]), 2),
            "dx": round(float(transform[1]), 2),
            "theta": round(float(transform[2]), 2),
            "corr": round(float(corr), 4),
            "y": int(y),
            "x": int(x),
            "h": int(ch),
            "w": int(cw),
            "yFrac": round(y / h, 4) if h else 0.0,
            "xFrac": round(x / w, 4) if w else 0.0,
            "inConsensus": id(votes[k]) in member_keys,
        }
        for k, (transform, corr, (y, x, ch, cw)) in enumerate(votes)
    ]
    return {
        "kind": "areal-2d",
        "votes": out_votes,
        "nTotal": len(out_votes),
        "nConsensus": len(members),
        "corrThresh": float(_CFG.cmr_corr),
        "transformTol": list(_CFG.cmr_tol),
    }


def _align_1d_stage(sig_a: np.ndarray, sig_b: np.ndarray) -> dict:
    """The 1-D alignment peak (lag + peak CCF) for a striated/toolmark pair."""
    from verity.registration.align import align_1d

    lag, ccf = align_1d(sig_a, sig_b)
    return {"kind": "ccf-1d", "lag": int(lag), "peakCcf": round(float(ccf), 4)}


def _align_matrix_stage(cmp) -> dict:
    """The bullet land×land CCF matrix, winning offset, and the winning diagonal —
    the alignment evidence behind the aggregate bullet score (mirrors
    intermediates.bullet_features_dict)."""
    i = int(np.argmax(cmp.diag_ccf))
    j = (i + cmp.offset) % cmp.ccf.shape[1]
    return {
        "kind": "ccf-matrix",
        "offset": int(cmp.offset),
        "matrix": np.round(cmp.ccf, 4).tolist(),  # bullets have few lands -> small
        "diagCcf": cmp.diag_ccf.round(4).tolist(),
        "bestLandA": i,
        "bestLandB": j,
        "features": {k: round(float(v), 5) for k, v in cmp.features().items()},
    }


# ── comparison assembly (mirrors build_gallery._comp + adds `stages`) ────────
def _comp(
    a_id: str,
    b_id: str,
    relation: str,
    rep: dict,
    scores: np.ndarray,
    labels: np.ndarray,
    score: float,
    stages: dict,
    *,
    signatures: dict | None = None,
    previews: dict | None = None,
) -> dict:
    report = rep if previews is None else {**rep, "previews": previews}
    out: dict = {
        "id": f"{a_id}__{b_id}",
        "aId": a_id,
        "bId": b_id,
        "relation": relation,
        "report": report,
        "calibration": _calibration(scores, labels, score, float(rep["likelihood_ratio"])),
        "stages": stages,
    }
    if signatures is not None:
        out["signatures"] = signatures
    return out


# ── toolmarks (1-D striation profiles; tmaRks) ──────────────────────────────
def build_toolmarks() -> tuple[list[dict], list[dict]]:
    from verity.examples.toolmark_tmaRks import export_tmaRks, load_tmaRks_marks

    if not export_tmaRks():
        return [], []
    marks = {tid: sig for _edge, tid, sig in load_tmaRks_marks(level="edge")}
    ref = np.load(_REF_TOOL, allow_pickle=False)
    scores, labels = ref["scores"], ref["labels"]

    specs = [
        {
            "id": _tool_id(t),
            "domain": "toolmark",
            "label": _tool_label(t),
            "source": "tmaRks",
            "signature": _norm_sig(marks[t]),
            "pairs": [],
        }
        for t in _TM_IDS
    ]

    comps = []
    for a, b, rel in _TM_PAIRS:
        sig_a, sig_b = marks[a], marks[b]
        score = float(
            cmr_score_1d(sig_a, sig_b, corr_thresh=_CFG.cmr_1d_corr, lag_tol=_CFG.cmr_1d_lag)
        )
        bands_a, bands_b = cmr_regions_1d_pair(
            sig_a, sig_b, corr_thresh=_CFG.cmr_1d_corr, lag_tol=_CFG.cmr_1d_lag
        )
        rep = build_comparison_report(
            score=score,
            reference_scores=scores,
            reference_labels=labels,
            domain="striated-toolmark",
            reference_name="tmaRks screwdriver toolmarks",
            score_kind="cmr-1d",
            ci=True,
        ).to_dict()
        # The tmaRks marks are already 1-D signatures (no surface to trace), so the
        # tour for this domain animates: signature -> align -> CMR votes.
        stages = {
            "signature": {"a": _decimate_1d(sig_a), "b": _decimate_1d(sig_b)},
            "align": _align_1d_stage(sig_a, sig_b),
            "cmr": _striated_votes_stage(sig_a, sig_b),
        }
        comps.append(
            _comp(
                _tool_id(a), _tool_id(b), rel, rep, scores, labels, score, stages,
                signatures={
                    "a": _norm_sig(sig_a),
                    "b": _norm_sig(sig_b),
                    "bandsA": bands_a,
                    "bandsB": bands_b,
                },
            )
        )
    return specs, comps


# ── bullets (striated lands; Hamby-252) ─────────────────────────────────────
def build_bullets() -> tuple[list[dict], list[dict]]:
    if not _bullet_manifest():
        return [], []
    bullets = _bullets()
    keys = list(bullets)
    b1 = next(k for k in keys if k[0] == 1)
    b1b = next(k for k in keys if k[0] == 1 and k != b1)
    other = next(k for k in keys if k[0] != 1)
    ref = np.load(_REF_BULLET, allow_pickle=False)
    scores, labels = ref["scores"], ref["labels"]

    specs = []
    for key in (b1, b1b, other):
        _sig0, band0 = _land_fields(_surface(bullets[key][0]), _CFG)
        specs.append(
            {
                "id": _bullet_id(key),
                "domain": "striated",
                "label": _bullet_label(key),
                "source": "Hamby-252",
                "thumb": _round_grid(_to_preview(band0, _THUMB)),
                "pairs": [],
            }
        )

    comps = []
    for ka, kb, rel in ((b1, b1b, "KM"), (b1, other, "KNM")):
        sa = [_surface(p) for p in bullets[ka]]
        sb = [_surface(p) for p in bullets[kb]]
        report, previews = compare_bullets_with_previews(
            sa, sb,
            reference_scores=scores,
            reference_labels=labels,
            reference_name="pooled bullet-land",
            preview_size=_SURF,
        )
        rep = report.to_dict()
        comps.append(_bullet_comp(ka, kb, rel, rep, scores, labels, sa, sb, previews))
    return specs, comps


def _bullet_comp(
    ka, kb, rel, rep, scores, labels, sa, sb, previews
) -> dict:
    """Assemble one bullet comparison's `stages` from the winning lands' traces and
    the land×land CCF matrix, then the per-window CMR votes on the best land pair."""
    from verity.aggregate import bullet_comparison

    ia = int(rep["provenance"]["best_land_a"])
    ib = int(rep["provenance"]["best_land_b"])
    trace_a = land_trace(sa[ia], lambda_s=_CFG.lambda_s, lambda_c=_CFG.lambda_c)
    trace_b = land_trace(sb[ib], lambda_s=_CFG.lambda_s, lambda_c=_CFG.lambda_c)
    sig_a, sig_b = trace_a.signature, trace_b.signature

    fields_a = [_land_fields(s, _CFG)[0] for s in sa]
    fields_b = [_land_fields(s, _CFG)[0] for s in sb]
    cmp = bullet_comparison(fields_a, fields_b)
    stages = {
        "raw": {"a": _trace_stages(trace_a), "b": _trace_stages(trace_b)},
        "signature": {"a": _decimate_1d(sig_a), "b": _decimate_1d(sig_b)},
        "align": _align_matrix_stage(cmp) if cmp is not None else {"kind": "ccf-matrix"},
        "cmr": _striated_votes_stage(sig_a, sig_b),
    }
    return _comp(
        _bullet_id(ka), _bullet_id(kb), rel, rep, scores, labels, rep["score"], stages,
        signatures={
            "a": _norm_sig(sig_a),
            "b": _norm_sig(sig_b),
            "bandsA": rep["attribution"],
            "bandsB": rep["attribution_b"],
        },
        previews={"a": _round_grid(previews["a"]), "b": _round_grid(previews["b"])},
    )


def _bullet_manifest() -> bool:
    """True when the bullet cache manifest is present (build_gallery._bullets reads
    it). Mirrors build_gallery.build_bullets' own guard."""
    # build_gallery._bullets() resolves the cache path internally; reuse its manifest
    # location by reading the same CSV it iterates.
    from verity.examples.build_gallery import _BULLET_CACHE

    return (_BULLET_CACHE / "manifest.csv").exists()


# ── cartridge cases (impressed breech faces; Fadul) ─────────────────────────
def build_cartridges() -> tuple[list[dict], list[dict]]:
    from verity.examples.cartridge_fadul import _FADUL_RE, _read_surface, fetch_fadul

    masked = fetch_fadul()
    if masked is None:
        return [], []
    slides: dict[int, list[Path]] = defaultdict(list)
    for p in sorted(masked.glob("*.x3p")):
        m = _FADUL_RE.search(p.name)
        if m:
            slides[int(m.group(1))].append(p)
    km_slide = next((s for s, ps in sorted(slides.items()) if len(ps) >= 2), None)
    knm_slide = next((s for s in sorted(slides) if s != km_slide), None)
    if km_slide is None or knm_slide is None:
        return [], []

    def _cart_id(p: Path) -> str:
        m = _FADUL_RE.search(p.name)
        return f"cart-{m.group(1)}-{m.group(2)}" if m else "cart-?"

    def _cart_label(p: Path) -> str:
        m = _FADUL_RE.search(p.name)
        return f"Fadul · slide {m.group(1)} · breech face {m.group(2)}"

    a_path, b_path = slides[km_slide][0], slides[km_slide][1]
    c_path = slides[knm_slide][0]
    ref = np.load(_REF_CART, allow_pickle=False)
    scores, labels = ref["scores"], ref["labels"]

    specs = []
    for p in (a_path, b_path, c_path):
        surf = _read_surface(p)
        specs.append(
            {
                "id": _cart_id(p),
                "domain": "impressed",
                "label": _cart_label(p),
                "source": "Fadul cartridge cases",
                "thumb": _round_grid(_to_preview(surf.heights, _THUMB)),
                "pairs": [],
            }
        )

    comps = []
    for pa, pb, rel in ((a_path, b_path, "KM"), (a_path, c_path, "KNM")):
        comps.append(
            _cartridge_comp(_cart_id, pa, pb, rel, scores, labels, _read_surface)
        )
    return specs, comps


def _cartridge_comp(cart_id, pa, pb, rel, scores, labels, read_surface) -> dict:
    """Assemble one impressed comparison's `stages`: raw surfaces, the 256² areal
    maps, and the per-cell 2-D CMR (CMC) votes + consensus cluster."""
    surf_a, surf_b = read_surface(pa), read_surface(pb)
    report, previews = compare_with_previews(
        surf_a, surf_b,
        domain="impressed",
        reference_scores=scores,
        reference_labels=labels,
        reference_name="Fadul cartridge cases",
        preview_size=_SURF,
    )
    rep = report.to_dict()
    areal_a = areal_signature(surf_a)
    areal_b = areal_signature(surf_b)
    stages = {
        "raw": {
            "a": _downsample_grid(surf_a.heights),
            "b": _downsample_grid(surf_b.heights),
        },
        "areal": {"a": _downsample_grid(areal_a), "b": _downsample_grid(areal_b)},
        "cmr": _areal_votes_stage(areal_a, areal_b),
    }
    return _comp(
        cart_id(pa), cart_id(pb), rel, rep, scores, labels, rep["score"], stages,
        previews={"a": _round_grid(previews["a"]), "b": _round_grid(previews["b"])},
    )


def _fill_pairs(specimens: list[dict], comparisons: list[dict]) -> None:
    """Record, on each specimen, the ids it has a precomputed comparison with
    (identical to build_gallery._fill_pairs)."""
    by_id = {s["id"]: s for s in specimens}
    for c in comparisons:
        if c["aId"] in by_id and c["bId"] not in by_id[c["aId"]]["pairs"]:
            by_id[c["aId"]]["pairs"].append(c["bId"])
        if c["bId"] in by_id and c["aId"] not in by_id[c["bId"]]["pairs"]:
            by_id[c["bId"]]["pairs"].append(c["aId"])


def main() -> None:
    specimens: list[dict] = []
    comparisons: list[dict] = []
    builders = (
        ("toolmark", build_toolmarks),
        ("bullet", build_bullets),
        ("cartridge", build_cartridges),
    )
    for name, fn in builders:
        try:
            specs, comps = fn()
        except Exception as exc:  # noqa: BLE001
            print(f"  {name}: skipped ({exc})")
            continue
        if not comps:
            print(f"  {name}: skipped (data unavailable)")
            continue
        specimens += specs
        comparisons += comps
        for c in comps:
            print(
                f"  {name} {c['relation']}: {c['aId']} vs {c['bId']} "
                f"stages={list(c['stages'])} "
                f"LR={c['report']['likelihood_ratio']:,.2f} '{c['report']['verbal']}'"
            )

    if not comparisons:
        raise SystemExit("no specimens built — are the references and caches present?")

    _fill_pairs(specimens, comparisons)
    manifest = {
        "version": _CFG.config_hash,
        "specimens": specimens,
        "comparisons": comparisons,
    }
    _OUT.write_text(json.dumps(manifest, separators=(",", ":")))
    print(
        f"wrote {_OUT} ({_OUT.stat().st_size / 1024:.0f} KB) — "
        f"{len(specimens)} specimens, {len(comparisons)} comparisons"
    )


if __name__ == "__main__":
    main()
