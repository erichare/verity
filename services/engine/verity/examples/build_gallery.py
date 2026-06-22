"""Generate the homepage compare-workspace gallery from REAL marks.

The redesigned homepage opens into a curated gallery: a visitor picks two real
specimens and watches the alignment + calibrated likelihood ratio resolve, with no
.x3p file of their own. Those gallery comparisons are *precomputed* here (instant,
animated, offline/on-stage safe) — every number comes from the real engine on real
catalog marks, never fabricated. Live uploads still hit the API.

Curated set: 3 specimens per domain, each domain carrying one same-source (KM) and
one different-source (KNM) comparison that share a common specimen — so a visitor
picks A once and flips between the matching and non-matching partner. The exact
pairs mirror the already-vetted, documented sample/live-proof generators.

Writes ``services/web/lib/gallery.json``. Reproducible from the committed references
+ the local caches; no network. Run:

    cd services/engine && uv run verity-build-gallery
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from verity.cmr import cmr_regions_1d_pair, cmr_score_1d
from verity.compare import (
    _land_fields,
    _to_preview,
    compare_bullets_with_previews,
    compare_with_previews,
)
from verity.decision import DEFAULT_SCORER_CONFIG
from verity.report import build_comparison_report
from verity.surface import Surface

_CFG = DEFAULT_SCORER_CONFIG
_ROOT = Path(__file__).resolve().parents[4]
_OUT = _ROOT / "services/web/lib/gallery.json"

_REF_BULLET = _ROOT / "services/api/verity_api/references/bullet_pooled.npz"
_REF_CART = _ROOT / "services/api/verity_api/references/cartridge_fadul.npz"
_REF_TOOL = _ROOT / "services/api/verity_api/references/toolmark_tmaRks.npz"
_BULLET_CACHE = (
    _ROOT / "services/catalog/.verity/cache/bulletxtrctr/c09aaa86-5d60-4acb-9031-46dad2c0ad32"
)

_SURF = 56  # idle SurfaceViewer / comparison preview grid (downsampled, kept lean)
_THUMB = 24  # gallery-card thumbnail grid


# ── small, deterministic helpers ────────────────────────────────────────────
def _round_grid(grid: list[list[float]], dp: int = 3) -> list[list[float]]:
    return [[round(float(v), dp) for v in row] for row in grid]


def _norm_sig(s: np.ndarray) -> list[float]:
    s = np.nan_to_num(np.asarray(s, dtype=float), nan=0.0)
    s = s - s.mean()
    scale = float(np.max(np.abs(s))) or 1.0
    return [round(float(x / scale), 4) for x in s]


def _subsample(arr: np.ndarray, n: int = 300) -> list[float]:
    # Deterministic, order-independent: evenly-spaced indices (the KDE doesn't care
    # about order). Keeps gallery.json byte-stable across re-runs for a drift check.
    a = np.asarray(arr, dtype=float)
    if a.size > n:
        a = a[:: max(1, a.size // n)][:n]
    return [round(float(x), 4) for x in a]


def _lr_label(lr: float) -> str:
    if not np.isfinite(lr) or lr <= 0:
        return "—"
    if lr >= 1:
        return f"{lr:,.0f}" if lr >= 10 else f"{lr:.1f}"
    inv = 1.0 / lr
    return f"1 / {inv:,.0f}" if inv >= 10 else f"1 / {inv:.1f}"


def _calibration(scores: np.ndarray, labels: np.ndarray, score: float, lr: float) -> dict:
    return {
        "km": _subsample(scores[labels == 1]),
        "knm": _subsample(scores[labels == 0]),
        "score": round(float(score), 4),
        "lrLabel": _lr_label(float(lr)),
    }


def _comp(
    a_id: str,
    b_id: str,
    relation: str,
    rep: dict,
    scores: np.ndarray,
    labels: np.ndarray,
    score: float,
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
    }
    if signatures is not None:
        out["signatures"] = signatures
    return out


def _surface(path: Path) -> Surface:
    import verity_x3p

    s = verity_x3p.read_x3p(str(path))
    return Surface(heights=np.asarray(s.data, dtype=float), dx=s.increment_x, dy=s.increment_y)


# ── toolmarks (1-D striation profiles; tmaRks) ──────────────────────────────
_TM_IDS = ["T01SB-F80-01", "T01SB-F80-02", "T03LA-F80-01"]
_TM_PAIRS = [("T01SB-F80-01", "T01SB-F80-02", "KM"), ("T01SB-F80-01", "T03LA-F80-01", "KNM")]


def _tool_id(tid: str) -> str:
    return "tool-" + tid


def _tool_label(tid: str) -> str:
    te = tid.split("-")[0]  # "T01SB"
    mark = tid.split("-")[-1]  # "01"
    return f"Screwdriver {te[:3]} · edge {te[3:]} · mark {mark}"


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
        comps.append(
            _comp(
                _tool_id(a), _tool_id(b), rel, rep, scores, labels, score,
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
def _bullets() -> dict[tuple[int, int], list[Path]]:
    by: dict[tuple[int, int], list[tuple[int, Path]]] = defaultdict(list)
    for r in csv.DictReader((_BULLET_CACHE / "manifest.csv").open()):
        f = _BULLET_CACHE / "x3p" / f"{r['file']}.x3p"
        if f.exists():
            by[(int(r["barrel"]), int(r["bullet"]))].append((int(r["land"]), f))
    return {k: [f for _, f in sorted(v)] for k, v in sorted(by.items())}


def _bullet_id(key: tuple[int, int]) -> str:
    return f"bullet-b{key[0]}-{key[1]}"


def _bullet_label(key: tuple[int, int]) -> str:
    return f"Hamby-252 · barrel {key[0]} · bullet {key[1]}"


def build_bullets() -> tuple[list[dict], list[dict]]:
    if not (_BULLET_CACHE / "manifest.csv").exists():
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
        ia, ib = int(rep["provenance"]["best_land_a"]), int(rep["provenance"]["best_land_b"])
        sig_a = _land_fields(sa[ia], _CFG)[0]
        sig_b = _land_fields(sb[ib], _CFG)[0]
        comps.append(
            _comp(
                _bullet_id(ka), _bullet_id(kb), rel, rep, scores, labels, rep["score"],
                signatures={
                    "a": _norm_sig(sig_a),
                    "b": _norm_sig(sig_b),
                    "bandsA": rep["attribution"],
                    "bandsB": rep["attribution_b"],
                },
                # `a`/`b` are the form-removed striae bands (the preprocess view); `raw_a`/`raw_b`
                # are the genuine raw land scans WITH the bullet's gross form still present (the
                # ingest view), so the raw→preprocess step honestly shows ISO form removal.
                previews={
                    "a": _round_grid(previews["a"]),
                    "b": _round_grid(previews["b"]),
                    "raw_a": _round_grid(_to_preview(sa[ia].heights, _SURF)),
                    "raw_b": _round_grid(_to_preview(sb[ib].heights, _SURF)),
                },
            )
        )
    return specs, comps


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

    def _case(p: Path) -> str:
        m = _FADUL_RE.search(p.name)
        return m.group(2) if m else "?"

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
        report, previews = compare_with_previews(
            _read_surface(pa),
            _read_surface(pb),
            domain="impressed",
            reference_scores=scores,
            reference_labels=labels,
            reference_name="Fadul cartridge cases",
            preview_size=_SURF,
        )
        rep = report.to_dict()
        comps.append(
            _comp(
                _cart_id(pa), _cart_id(pb), rel, rep, scores, labels, rep["score"],
                previews={"a": _round_grid(previews["a"]), "b": _round_grid(previews["b"])},
            )
        )
    return specs, comps


def _fill_pairs(specimens: list[dict], comparisons: list[dict]) -> None:
    """Record, on each specimen, the ids it has a precomputed comparison with."""
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
