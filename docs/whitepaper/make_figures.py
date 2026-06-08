"""Generate the white paper's figures from the barrel-disjoint ablation results.

Reads ``docs/whitepaper/data/ablation.json`` (the source of truth) and emits two
honest, minimal PDF figures into ``docs/whitepaper/``:

* ``fig_cllr_by_study.pdf`` — barrel-disjoint test Cllr per study, baseline
  (diag_mean) vs deployed (diag_contrast). Lower is better; both bars carry the
  cross-fold SD as an error bar so the small-set uncertainty is visible.
* ``fig_scorer_selection.pdf`` — mean barrel-disjoint test Cllr across the four
  studies for the candidate scorers, the data behind the scorer-selection claim.

Run from the engine package so the viz extra is available::

    cd services/engine && uv run --extra viz python ../../docs/whitepaper/make_figures.py
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "ablation.json"

# Serious, print-friendly defaults.
plt.rcParams.update(
    {
        "font.family": "serif",
        "font.size": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.alpha": 0.25,
        "grid.linewidth": 0.5,
        "figure.dpi": 200,
    }
)

# Muted, colour-blind-safe palette.
C_BASE = "#9aa7b8"  # diag_mean (baseline)
C_PROD = "#1f4e79"  # diag_contrast (deployed)
C_FUSE = "#c0762f"  # fusion(logit)

SHORT = {
    "Hamby (2009) Barrel Set 252": "Hamby-252",
    "PGPD Beretta Barrels — full (NBTRD)": "PGPD\nBeretta",
    "Phoenix PD (Ruger P-95) — known barrels (NBTRD)": "Phoenix\nRuger",
    "Hamby (2009) Barrel Set 173 — full (NBTRD)": "Hamby-173",
}


def load() -> list[dict]:
    with DATA.open() as fh:
        return json.load(fh)


def fig_cllr_by_study(studies: list[dict]) -> None:
    labels = [SHORT.get(s["title"], s["title"]) for s in studies]
    base = [s["levers"]["diag_mean"]["cllr"] for s in studies]
    base_sd = [s["levers"]["diag_mean"]["cllr_sd"] for s in studies]
    prod = [s["levers"]["diag_contrast"]["cllr"] for s in studies]
    prod_sd = [s["levers"]["diag_contrast"]["cllr_sd"] for s in studies]

    x = range(len(labels))
    w = 0.38
    fig, ax = plt.subplots(figsize=(5.4, 3.0))
    ax.bar(
        [i - w / 2 for i in x], base, w, yerr=base_sd, capsize=2.5,
        color=C_BASE, label=r"$\mathrm{diag\_mean}$ (Phase-1 baseline)",
        error_kw={"elinewidth": 0.8, "ecolor": "#5a6470"},
    )
    ax.bar(
        [i + w / 2 for i in x], prod, w, yerr=prod_sd, capsize=2.5,
        color=C_PROD, label=r"$\mathrm{diag\_contrast}$ (deployed)",
        error_kw={"elinewidth": 0.8, "ecolor": "#102a44"},
    )
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels)
    ax.set_ylabel(r"Barrel-disjoint test $C_{\mathrm{llr}}$  (lower is better)")
    ax.set_ylim(0, max(base + prod) + max(base_sd + prod_sd) + 0.05)
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.tight_layout()
    out = HERE / "fig_cllr_by_study.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def fig_scorer_selection(studies: list[dict]) -> None:
    levers = ["diag_mean", "diag_contrast", "fusion(logit)", "fusion(iso)"]
    names = [
        r"$\mathrm{diag\_mean}$",
        r"$\mathrm{diag\_contrast}$",
        "fusion (logit)",
        "fusion (isotonic)",
    ]
    colours = [C_BASE, C_PROD, C_FUSE, "#7a4f86"]
    means = [
        sum(s["levers"][lev]["cllr"] for s in studies) / len(studies) for lev in levers
    ]
    fig, ax = plt.subplots(figsize=(5.4, 2.8))
    bars = ax.bar(names, means, color=colours, width=0.6)
    for b, m in zip(bars, means):
        ax.text(b.get_x() + b.get_width() / 2, m + 0.006, f"{m:.3f}",
                ha="center", va="bottom", fontsize=8)
    ax.set_ylabel(r"Mean barrel-disjoint $C_{\mathrm{llr}}$ (4 studies)")
    ax.set_ylim(0, max(means) + 0.06)
    ax.tick_params(axis="x", labelsize=8)
    fig.tight_layout()
    out = HERE / "fig_scorer_selection.pdf"
    fig.savefig(out)
    plt.close(fig)
    print(f"wrote {out}")


def main() -> None:
    studies = load()
    fig_cllr_by_study(studies)
    fig_scorer_selection(studies)


if __name__ == "__main__":
    main()
