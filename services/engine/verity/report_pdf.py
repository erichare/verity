"""Court-ready per-comparison report — one comparison rendered to a PDF.

The artifact an examiner attaches to a case file: the calibrated likelihood ratio
with its credible interval and verbal weight, the named-scope statement, the
reference population and its cost, the method/pipeline version, the SHA-256
provenance of the input scans, and the attribution overlay showing *which* regions
drove the match. It consumes a :class:`~verity.report.ComparisonReport`'s dict (the
same payload the API returns), so the page agrees with the on-screen result.

Rendering uses matplotlib (the ``viz`` extra); imported lazily.
"""

from __future__ import annotations

import hashlib
import textwrap
from pathlib import Path

from .viz.attribution import render_attribution_axes


def _fmt_lr(lr: float) -> str:
    if lr >= 1000 or (0 < lr < 0.01):
        return f"{lr:.2e}"
    return f"{lr:.1f}" if lr >= 1 else f"{lr:.3f}"


def _findings_page(pdf, report: dict, *, case_id: str | None, examiner: str | None) -> None:
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.5, 0.95, "Verity — Comparison Report", ha="center", fontsize=20, weight="bold")
    fig.text(
        0.5,
        0.915,
        "Calibrated weight of evidence for a forensic surface comparison",
        ha="center",
        fontsize=10,
        style="italic",
        color="#444444",
    )

    y = 0.86
    if case_id or examiner:
        fig.text(0.12, y, f"Case/exhibit: {case_id or '—'}", fontsize=10)
        fig.text(0.62, y, f"Examiner: {examiner or '—'}", fontsize=10)
        y -= 0.045

    lr = float(report["likelihood_ratio"])
    log10_lr = float(report["log10_lr"])
    ci_lo, ci_hi = report.get("log10_lr_ci_lo"), report.get("log10_lr_ci_hi")
    ci_txt = ""
    if ci_lo is not None and ci_hi is not None:
        ci_txt = f"   (95% CI on log₁₀ LR: [{ci_lo:.2f}, {ci_hi:.2f}])"

    fig.text(0.12, y, "Likelihood ratio", fontsize=12, weight="bold", color="#1F4E79")
    fig.text(
        0.12,
        y - 0.04,
        f"LR = {_fmt_lr(lr)}    log₁₀ LR = {log10_lr:+.2f}{ci_txt}",
        fontsize=13,
        family="monospace",
    )
    fig.text(0.12, y - 0.075, report.get("verbal", ""), fontsize=12)
    y -= 0.13

    ref = report.get("reference", {})
    # Reference name on its own full-width line (it is long) before the two-col rows.
    fig.text(0.12, y, "Reference population", fontsize=10.5)
    fig.text(0.46, y, ref.get("name", "—"), fontsize=8.5, style="italic")
    y -= 0.033
    rows = [
        ("Direction", report.get("direction", "—")),
        ("Score", f"{report.get('score', float('nan')):.4f}  ({report.get('score_kind', '—')})"),
        (
            "Reference size",
            f"{ref.get('n_km', '—')} same-source / {ref.get('n_knm', '—')} different",
        ),
        (
            "Calibration cost (Cllr)",
            f"{ref.get('cllr', float('nan')):.3f}  (floor {ref.get('cllr_min', float('nan')):.3f})",
        ),
        ("Discrimination (AUC)", f"{ref.get('auc', float('nan')):.3f}"),
        ("LR bound |log10 LR|", f"{report.get('lr_bound_log10') or float('nan'):.2f}"),
        ("Domain", report.get("domain", "—")),
    ]
    for k, v in rows:
        fig.text(0.12, y, k, fontsize=10.5)
        fig.text(0.46, y, str(v), fontsize=10.5, weight="bold")
        y -= 0.033

    prov = report.get("provenance", {})
    fig.text(0.12, y - 0.01, "Method & provenance", fontsize=12, weight="bold", color="#1F4E79")
    y -= 0.05
    meta = [
        (
            "Engine / API version",
            f"{prov.get('engine_version', '—')} / {prov.get('api_version', '—')}",
        ),
        ("Scorer", prov.get("scorer", report.get("score_kind", "—"))),
    ]
    for k, v in meta:
        fig.text(0.12, y, k, fontsize=10)
        fig.text(0.46, y, str(v), fontsize=10, family="monospace")
        y -= 0.03
    # Input provenance: a count + a single combined hash that pins the exact set
    # of scans (per-scan hashes live in the JSON record). Scales to any number of
    # lands without overrunning the page.
    hashes = prov.get("input_hashes", {})
    a_h, b_h = hashes.get("mark_a", []), hashes.get("mark_b", [])
    if a_h or b_h:
        fig.text(0.12, y, "Input scans", fontsize=10)
        fig.text(0.46, y, f"Mark A: {len(a_h)}   ·   Mark B: {len(b_h)}", fontsize=10)
        y -= 0.03
        combined = hashlib.sha256("".join(sorted(a_h + b_h)).encode()).hexdigest()
        fig.text(0.12, y, "Combined SHA-256", fontsize=10)
        fig.text(0.46, y, combined, fontsize=8, family="monospace")
        y -= 0.024
        fig.text(
            0.46,
            y,
            "pins the exact input set; per-scan hashes in the data record",
            fontsize=7.5,
            color="#999999",
        )
        y -= 0.03

    # Scope note — manually wrapped (matplotlib's wrap=True is unreliable) so it
    # never runs past the margin or into the footer.
    scope = textwrap.fill("Scope.  " + report.get("scope_note", ""), width=96)
    fig.text(
        0.12,
        y - 0.02,
        scope,
        fontsize=9,
        va="top",
        linespacing=1.5,
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#f2f2f2", "edgecolor": "#cccccc"},
    )
    fig.text(
        0.5,
        0.04,
        "Verity · glass-box, calibrated likelihood ratios — verity.codes",
        ha="center",
        fontsize=8,
        color="#888888",
    )
    pdf.savefig(fig)
    plt.close(fig)


def _attribution_page(pdf, report: dict) -> None:
    import matplotlib.pyplot as plt

    previews = report.get("previews", {})
    if not previews.get("a") or not previews.get("b"):
        return
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.2))
    render_attribution_axes(
        ax1, previews["a"], report.get("attribution", []), title="Mark A — matched regions"
    )
    render_attribution_axes(
        ax2, previews["b"], report.get("attribution_b", []), title="Mark B — matched regions"
    )
    fig.suptitle("Attribution — the congruent regions that drove the comparison", fontsize=12)
    fig.text(
        0.5,
        0.02,
        "Highlighted regions are the congruent matching regions (the examiner-facing evidence). "
        "This shows what the score is built on; it is not a separate claim.",
        ha="center",
        fontsize=8,
        color="#666666",
    )
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    pdf.savefig(fig)
    plt.close(fig)


def render_comparison_pdf(
    report: dict, out_path: str, *, case_id: str | None = None, examiner: str | None = None
) -> None:
    """Render one comparison report (the API/`ComparisonReport` dict) to a
    court-ready PDF at ``out_path``."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.backends.backend_pdf import PdfPages

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(out) as pdf:
        _findings_page(pdf, report, case_id=case_id, examiner=examiner)
        _attribution_page(pdf, report)
