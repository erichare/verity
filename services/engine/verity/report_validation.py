"""Validation-report generator — a court-ready PDF characterizing a calibrated LR
system on a named dataset.

Point :func:`generate_validation_report` at a reference population's KM/KNM scores
(and, ideally, the source/barrel of each comparison) and it produces a paginated
PDF — score distributions, Tippett plot, ROC + DET, the calibration decomposition
(``Cllr``/``Cllr_min``/ECE with the ELUB bound), and a **source-disjoint**
summary — plus a machine-readable :class:`ValidationSummary` JSON sidecar. Every
number comes from :mod:`verity.decision.metrics` / :mod:`verity.decision.validation`,
so the report is the same evidence the engine calibrates on, rendered.

The honest-scope statement is on the cover: this characterizes the weight of
evidence on *this dataset*, not a field-wide error rate.

PDF rendering uses matplotlib (the ``viz`` extra); import it lazily so the core
engine has no hard matplotlib dependency.
"""

from __future__ import annotations

import json
import textwrap
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from . import __version__
from .decision.lr import ScoreLRModel, cllr_min
from .decision.metrics import cllr, ece, eer, margin, roc_auc, tippett
from .decision.validation import barrel_disjoint_folds, summarize_folds

__all__ = ["ValidationSummary", "compute_validation_summary", "generate_validation_report"]


@dataclass(frozen=True)
class ValidationSummary:
    """The scalar summary of a validation run — the single source of truth shared
    by the PDF and the JSON sidecar (and diffed by the reproducibility kit)."""

    reference_name: str
    domain: str
    n_km: int
    n_knm: int
    n_sources: int | None
    auc: float
    eer: float
    cllr: float  # in-sample, deployed bounded calibration
    cllr_min: float  # PAV discrimination floor (in-sample)
    calibration_loss: float  # cllr - cllr_min
    ece: float
    lr_bound_log10: float | None
    cohens_d: float
    pct_gap: float
    barrel_disjoint: dict | None  # mean ± sd test metrics; None if too few sources
    pipeline_version: str
    generated_at: str | None

    def to_dict(self) -> dict:
        return asdict(self)


def compute_validation_summary(
    scores: np.ndarray,
    labels: np.ndarray,
    *,
    reference_name: str,
    domain: str,
    barrels_a: np.ndarray | None = None,
    barrels_b: np.ndarray | None = None,
    lr_bound: str | float | None = "auto",
    generated_at: str | None = None,
    seed: int = 0,
) -> ValidationSummary:
    """All validation scalars for a reference population. When ``barrels_a/b`` are
    given, a source-disjoint (barrel-disjoint) summary is included — the honest
    generalization claim."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)

    model = ScoreLRModel(lr_bound=lr_bound).fit(scores, labels)
    lr = model.predict_lr(scores)
    lr_km, lr_knm = lr[labels == 1], lr[labels == 0]
    sep = margin(scores, labels)

    bd = None
    n_sources: int | None = None
    if barrels_a is not None and barrels_b is not None:
        ba = np.asarray(barrels_a)
        bb = np.asarray(barrels_b)
        n_sources = len(set(ba.tolist()) | set(bb.tolist()))
        bd = summarize_folds(barrel_disjoint_folds(scores, labels, ba, bb, seed=seed))

    cllr_val = float(cllr(lr_km, lr_knm))
    cllr_min_val = float(cllr_min(scores, labels))
    return ValidationSummary(
        reference_name=reference_name,
        domain=domain,
        n_km=int((labels == 1).sum()),
        n_knm=int((labels == 0).sum()),
        n_sources=n_sources,
        auc=float(roc_auc(scores, labels)),
        eer=float(eer(scores, labels)),
        cllr=cllr_val,
        cllr_min=cllr_min_val,
        calibration_loss=float(cllr_val - cllr_min_val),
        ece=float(ece(lr_km, lr_knm)),
        lr_bound_log10=model._log_bound,
        cohens_d=float(sep["cohens_d"]),
        pct_gap=float(sep["pct_gap"]),
        barrel_disjoint=bd,
        pipeline_version=__version__,
        generated_at=generated_at,
    )


# --- PDF rendering ----------------------------------------------------------


def _cover_page(pdf, summary: ValidationSummary) -> None:
    import matplotlib.pyplot as plt

    fig = plt.figure(figsize=(8.5, 11))
    fig.text(0.5, 0.93, "Verity — Validation Report", ha="center", fontsize=20, weight="bold")
    fig.text(0.5, 0.89, summary.reference_name, ha="center", fontsize=12, style="italic")

    src = "—" if summary.n_sources is None else str(summary.n_sources)
    when = summary.generated_at or "—"
    rows = [
        ("Domain", summary.domain),
        ("Same-source comparisons (KM)", f"{summary.n_km}"),
        ("Different-source comparisons (KNM)", f"{summary.n_knm}"),
        ("Distinct sources (barrels)", src),
        ("Pipeline version", summary.pipeline_version),
        ("Generated", when),
    ]
    y = 0.80
    for k, v in rows:
        fig.text(0.12, y, k, fontsize=11)
        fig.text(0.62, y, v, fontsize=11, weight="bold")
        y -= 0.035

    headline = (
        f"AUC = {summary.auc:.3f}    Cllr = {summary.cllr:.3f}    Cllr_min = {summary.cllr_min:.3f}"
    )
    fig.text(0.12, 0.55, "Headline", fontsize=12, weight="bold")
    fig.text(0.12, 0.515, headline, fontsize=12, family="monospace")

    scope = (
        "Scope. This report characterizes the weight of evidence on the named "
        f"reference population above; it is not a claim about the error rate of "
        f"{summary.domain} examination, which remains unknown. The likelihood ratio "
        "is calibrated by a monotone, bounded (ELUB) transform of the comparison "
        "score and is reported with a characterized cost (Cllr). Out-of-sample "
        "behaviour is summarized on the source-disjoint page."
    )
    fig.text(
        0.12,
        0.40,
        textwrap.fill(scope, width=92),
        fontsize=10,
        va="top",
        linespacing=1.5,
        bbox={"boxstyle": "round,pad=0.5", "facecolor": "#f2f2f2", "edgecolor": "#cccccc"},
    )
    fig.text(
        0.5,
        0.05,
        "Verity · calibrated, glass-box likelihood ratios for forensic surface comparison",
        ha="center",
        fontsize=8,
        color="#888888",
    )
    pdf.savefig(fig)
    plt.close(fig)


def _distributions_page(pdf, scores: np.ndarray, labels: np.ndarray, summary) -> None:
    import matplotlib.pyplot as plt

    km, knm = scores[labels == 1], scores[labels == 0]
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    bins = np.linspace(float(scores.min()), float(scores.max()), 40)
    ax.hist(
        knm,
        bins=bins,
        alpha=0.55,
        label=f"different source (n={knm.size})",
        color="#c0392b",
        density=True,
    )
    ax.hist(
        km, bins=bins, alpha=0.55, label=f"same source (n={km.size})", color="#2e86de", density=True
    )
    ax.set_xlabel("comparison score")
    ax.set_ylabel("density")
    ax.set_title("Score distributions — same vs different source")
    ax.legend()
    ax.text(
        0.02,
        0.97,
        f"Cohen's d = {summary.cohens_d:.2f}\n5/95 gap = {summary.pct_gap:.3f}",
        transform=ax.transAxes,
        va="top",
        fontsize=9,
        bbox={"boxstyle": "round", "facecolor": "white", "edgecolor": "#cccccc"},
    )
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _tippett_page(pdf, lr_km: np.ndarray, lr_knm: np.ndarray) -> None:
    import matplotlib.pyplot as plt

    thr, km_prop, knm_prop = tippett(lr_km, lr_knm)
    log10_thr = np.log10(thr)
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.plot(log10_thr, km_prop, color="#2e86de", label="same source: P(log10 LR ≥ x)")
    ax.plot(log10_thr, knm_prop, color="#c0392b", label="different source: P(log10 LR ≥ x)")
    ax.axvline(0.0, color="#888888", ls="--", lw=1)
    ax.set_xlabel("log10 likelihood ratio threshold")
    ax.set_ylabel("proportion with LR ≥ threshold")
    ax.set_title("Tippett plot")
    ax.legend()
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _roc_det_page(pdf, scores: np.ndarray, labels: np.ndarray, summary) -> None:
    import matplotlib.pyplot as plt
    from scipy.stats import norm
    from sklearn.metrics import roc_curve

    fpr, tpr, _ = roc_curve(labels, scores)
    fnr = 1.0 - tpr
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.0))

    ax1.plot(fpr, tpr, color="#2e86de")
    ax1.plot([0, 1], [0, 1], color="#cccccc", ls="--")
    ax1.set_xlabel("false positive rate")
    ax1.set_ylabel("true positive rate")
    ax1.set_title(f"ROC (AUC = {summary.auc:.3f})")

    # DET on standard-normal-deviate axes (clip to avoid ±inf at 0/1).
    eps = 1e-3
    fpr_c = np.clip(fpr, eps, 1 - eps)
    fnr_c = np.clip(fnr, eps, 1 - eps)
    ax2.plot(norm.ppf(fpr_c), norm.ppf(fnr_c), color="#8e44ad")
    ticks = [0.01, 0.05, 0.2, 0.4]
    ax2.set_xticks(norm.ppf(ticks))
    ax2.set_xticklabels([f"{t:.0%}" for t in ticks])
    ax2.set_yticks(norm.ppf(ticks))
    ax2.set_yticklabels([f"{t:.0%}" for t in ticks])
    ax2.set_xlabel("false positive rate")
    ax2.set_ylabel("false negative rate")
    ax2.set_title(f"DET (EER = {summary.eer:.1%})")
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _calibration_page(pdf, scores: np.ndarray, labels: np.ndarray, summary) -> None:
    import matplotlib.pyplot as plt

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5.0))

    # The two monotone calibration maps: deployed logistic (bounded) vs PAV floor.
    order = np.argsort(scores)
    xs = scores[order]
    logistic = ScoreLRModel(method="logistic").fit(scores, labels)
    isotonic = ScoreLRModel(method="isotonic", lr_bound=None).fit(scores, labels)
    ax1.plot(
        xs,
        np.log10(logistic.predict_lr(xs)),
        color="#2e86de",
        label="deployed logistic (ELUB-bounded)",
    )
    ax1.plot(
        xs,
        np.log10(isotonic.predict_lr(xs)),
        color="#16a085",
        ls="--",
        label="PAV floor (Cllr_min)",
    )
    ax1.axhline(0.0, color="#cccccc", lw=1)
    ax1.set_xlabel("comparison score")
    ax1.set_ylabel("log10 LR")
    ax1.set_title("Calibration map (monotone — the audit firewall)")
    ax1.legend(fontsize=8)

    ax2.axis("off")
    bound = "—" if summary.lr_bound_log10 is None else f"{summary.lr_bound_log10:.2f}"
    lines = [
        ("Cllr (deployed)", f"{summary.cllr:.3f}"),
        ("Cllr_min (floor)", f"{summary.cllr_min:.3f}"),
        ("calibration loss", f"{summary.calibration_loss:+.3f}"),
        ("ECE", f"{summary.ece:.3f}"),
        ("AUC", f"{summary.auc:.3f}"),
        ("EER", f"{summary.eer:.1%}"),
        ("ELUB bound |log10 LR|", bound),
    ]
    y = 0.9
    ax2.text(
        0.0,
        y + 0.06,
        "Calibration decomposition",
        fontsize=12,
        weight="bold",
        transform=ax2.transAxes,
    )
    for k, v in lines:
        ax2.text(0.0, y, k, fontsize=11, transform=ax2.transAxes)
        ax2.text(0.7, y, v, fontsize=11, weight="bold", family="monospace", transform=ax2.transAxes)
        y -= 0.1
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def _disjoint_page(pdf, summary) -> None:
    import matplotlib.pyplot as plt

    bd = summary.barrel_disjoint
    fig, ax = plt.subplots(figsize=(8.5, 5.5))
    ax.axis("off")
    ax.text(
        0.5,
        0.95,
        "Source-disjoint validation",
        ha="center",
        fontsize=14,
        weight="bold",
        transform=ax.transAxes,
    )
    if not bd:
        ax.text(
            0.5,
            0.5,
            "Too few distinct sources for a source-disjoint split.\n"
            "Report the named-reference characterization above with this caveat.",
            ha="center",
            va="center",
            fontsize=11,
            transform=ax.transAxes,
        )
    else:
        intro = (
            f"No barrel spans train and test. Mean ± sd over {bd['n_folds']} "
            "splits — the out-of-sample weight-of-evidence cost. This is the "
            "characterization that answers Cuellar et al. (2024): a Cllr on a "
            "named dataset under a source-disjoint protocol."
        )
        ax.text(
            0.05,
            0.84,
            textwrap.fill(intro, width=82),
            fontsize=10,
            va="top",
            linespacing=1.5,
            transform=ax.transAxes,
        )
        lines = [
            ("test Cllr", f"{bd['cllr_mean']:.3f} ± {bd['cllr_std']:.3f}"),
            ("test Cllr_min", f"{bd['cllr_min_mean']:.3f} ± {bd['cllr_min_std']:.3f}"),
            ("test AUC", f"{bd['auc_mean']:.3f} ± {bd['auc_std']:.3f}"),
            ("calibration loss", f"{bd['calibration_loss']:+.3f}"),
        ]
        y = 0.55
        for k, v in lines:
            ax.text(0.12, y, k, fontsize=12, transform=ax.transAxes)
            ax.text(
                0.6, y, v, fontsize=12, weight="bold", family="monospace", transform=ax.transAxes
            )
            y -= 0.09
    fig.tight_layout()
    pdf.savefig(fig)
    plt.close(fig)


def generate_validation_report(
    scores: np.ndarray,
    labels: np.ndarray,
    *,
    reference_name: str,
    domain: str,
    out_path: str,
    barrels_a: np.ndarray | None = None,
    barrels_b: np.ndarray | None = None,
    lr_bound: str | float | None = "auto",
    generated_at: str | None = None,
    seed: int = 0,
) -> ValidationSummary:
    """Render the validation PDF to ``out_path`` and write a ``.json`` sidecar of
    the :class:`ValidationSummary` next to it. Returns the summary."""
    import matplotlib

    matplotlib.use("Agg")
    from matplotlib.backends.backend_pdf import PdfPages

    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=np.float64)
    summary = compute_validation_summary(
        scores,
        labels,
        reference_name=reference_name,
        domain=domain,
        barrels_a=barrels_a,
        barrels_b=barrels_b,
        lr_bound=lr_bound,
        generated_at=generated_at,
        seed=seed,
    )

    model = ScoreLRModel(lr_bound=lr_bound).fit(scores, labels)
    lr = model.predict_lr(scores)
    lr_km, lr_knm = lr[labels == 1], lr[labels == 0]

    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    with PdfPages(out) as pdf:
        _cover_page(pdf, summary)
        _distributions_page(pdf, scores, labels, summary)
        _tippett_page(pdf, lr_km, lr_knm)
        _roc_det_page(pdf, scores, labels, summary)
        _calibration_page(pdf, scores, labels, summary)
        _disjoint_page(pdf, summary)

    out.with_suffix(".json").write_text(json.dumps(summary.to_dict(), indent=2))
    return summary


def main() -> None:
    """CLI: ``verity-validation-report <study-external-id|''> [out.pdf]``.

    Loads a bullet study from the local catalog, scores every bullet pair
    (``diag_contrast``), and writes a validation PDF + JSON. With no id, defaults
    to the Hamby-252 anchor."""
    import sys
    from datetime import date

    from verity.examples.hamby_validation import (
        _resolve_study,
        load_study_bullets,
        pairwise_scores,
    )

    args = sys.argv[1:]
    study_id = args[0] if args and args[0] else None
    out_path = args[1] if len(args) > 1 else "validation_report.pdf"

    from sqlmodel import Session, create_engine
    from verity_catalog.store import LocalBlobStore

    from verity.examples.hamby_km_knm import _catalog_dir

    cdir = _catalog_dir()
    engine = create_engine(f"sqlite:///{cdir / 'verity_catalog.db'}")
    store = LocalBlobStore(cdir / ".verity" / "blobs")
    with Session(engine) as session:
        study = _resolve_study(session, study_id)
        if study is None:
            print("No bullet study found — ingest a manifest (e.g. 'hamby-252') first.")
            return
        bullets = load_study_bullets(session, store, study)
        title = study.title or study.external_id
    scores, labels, ba, bb = pairwise_scores(bullets)
    if not len(scores):
        print(f"No comparable bullet pairs in {title!r}.")
        return
    summary = generate_validation_report(
        scores,
        labels,
        reference_name=title,
        domain="striated",
        out_path=out_path,
        barrels_a=ba,
        barrels_b=bb,
        generated_at=date.today().isoformat(),
    )
    bd = summary.barrel_disjoint
    print(f"Wrote {out_path} ({summary.n_km} KM / {summary.n_knm} KNM, AUC={summary.auc:.3f})")
    if bd:
        print(f"  barrel-disjoint test Cllr = {bd['cllr_mean']:.3f} ± {bd['cllr_std']:.3f}")


if __name__ == "__main__":
    main()
