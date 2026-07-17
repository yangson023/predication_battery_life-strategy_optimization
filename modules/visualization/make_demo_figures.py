from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = PROJECT_ROOT / "outputs" / "demo" / "figures"


COLORS = {
    "blue": "#246BFE",
    "teal": "#00A676",
    "orange": "#F97316",
    "red": "#DC2626",
    "purple": "#7C3AED",
    "gray": "#64748B",
    "dark": "#1F2937",
    "light": "#F8FAFC",
}


def set_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": "#CBD5E1",
            "axes.labelcolor": COLORS["dark"],
            "axes.titlecolor": COLORS["dark"],
            "xtick.color": "#475569",
            "ytick.color": "#475569",
            "grid.color": "#E2E8F0",
            "grid.linewidth": 0.8,
            "font.size": 10,
            "axes.titlesize": 14,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "legend.fontsize": 9,
            "savefig.dpi": 180,
            "savefig.bbox": "tight",
        }
    )


def save(fig: plt.Figure, name: str) -> Path:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    path = OUTPUT_ROOT / name
    fig.savefig(path)
    plt.close(fig)
    return path


def plot_nasa_soh_curves() -> Path:
    labels = pd.read_csv(
        PROJECT_ROOT / "data" / "features" / "nasa" / "li_ion" / "soh_rul_labels_multi_threshold.csv"
    )
    labels = labels[labels["label_key"] == "capacity_eol_70"].copy()

    fig, ax = plt.subplots(figsize=(11.5, 6.2))
    palette = [COLORS["blue"], COLORS["orange"], COLORS["teal"], COLORS["purple"]]
    for color, (cell_id, group) in zip(palette, labels.groupby("cell_id")):
        group = group.sort_values("discharge_cycle")
        ax.plot(
            group["discharge_cycle"],
            group["soh_capacity_ratio"] * 100,
            label=cell_id,
            linewidth=2.2,
            color=color,
        )
        observed = group[group["eol_observed"]]
        if not observed.empty:
            eol_cycle = observed["eol_discharge_cycle"].iloc[0]
            eol_rows = group[group["discharge_cycle"] == eol_cycle]
            if not eol_rows.empty:
                ax.scatter(
                    [eol_cycle],
                    [eol_rows["soh_capacity_ratio"].iloc[0] * 100],
                    color=color,
                    edgecolor="white",
                    linewidth=1.5,
                    s=75,
                    zorder=4,
                )

    ax.axhline(80, color=COLORS["orange"], linestyle="--", linewidth=1.4, alpha=0.85)
    ax.axhline(70, color=COLORS["red"], linestyle="--", linewidth=1.4, alpha=0.85)
    ax.text(171, 80.6, "80% common EOL", color=COLORS["orange"], ha="right")
    ax.text(171, 70.6, "70% project threshold", color=COLORS["red"], ha="right")
    ax.set_title("NASA Battery SOH Degradation Curves")
    ax.set_xlabel("Discharge cycle")
    ax.set_ylabel("SOH based on capacity (%)")
    ax.set_xlim(0, 175)
    ax.set_ylim(52, 104)
    ax.grid(True, axis="both")
    ax.legend(title="Cell", frameon=False, ncol=4, loc="upper right")
    return save(fig, "01_nasa_soh_degradation_curves.png")


def plot_nasa_label_summary() -> Path:
    summary = pd.read_csv(PROJECT_ROOT / "data" / "features" / "nasa" / "li_ion" / "label_summary.csv")
    summary = summary.sort_values("cell_id")

    fig, axes = plt.subplots(1, 2, figsize=(12, 5.4), gridspec_kw={"width_ratios": [1.1, 1]})
    ax = axes[0]
    x = np.arange(len(summary))
    width = 0.36
    ax.bar(x - width / 2, summary["initial_capacity_ah"], width, label="Initial capacity", color=COLORS["blue"])
    ax.bar(x + width / 2, summary["last_capacity_ah"], width, label="Last capacity", color=COLORS["teal"])
    ax.set_xticks(x, summary["cell_id"])
    ax.set_ylabel("Capacity (Ah)")
    ax.set_title("Capacity Fade Summary")
    ax.grid(True, axis="y")
    ax.legend(frameon=False)

    ax = axes[1]
    observed = summary["eol_observed"].map({True: "Observed EOL", False: "Censored"}).value_counts()
    labels = ["Observed EOL", "Censored"]
    values = [int(observed.get(label, 0)) for label in labels]
    wedges, _ = ax.pie(
        values,
        startangle=90,
        colors=[COLORS["red"], COLORS["gray"]],
        wedgeprops={"width": 0.45, "edgecolor": "white"},
    )
    ax.legend(
        wedges,
        [f"{label}: {value}" for label, value in zip(labels, values)],
        frameon=False,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.08),
    )
    ax.set_title("70% EOL Label Status")
    ax.text(0, 0, f"{sum(values)}\ncells", ha="center", va="center", fontsize=16, weight="bold", color=COLORS["dark"])
    return save(fig, "02_nasa_label_summary.png")


def plot_external_protocol_regimes() -> Path:
    cycle = pd.read_csv(PROJECT_ROOT / "data" / "features" / "external_battery_datasets" / "cycle_features.csv")
    cycle = cycle.sort_values(["cell_id", "cycle_index"]).copy()
    cells = cycle["cell_id"].dropna().unique().tolist()

    fig, axes = plt.subplots(len(cells), 1, figsize=(12, max(6, len(cells) * 1.25)), sharex=False)
    if len(cells) == 1:
        axes = [axes]
    regime_colors = [COLORS["blue"], COLORS["teal"], COLORS["orange"], COLORS["purple"], COLORS["red"], COLORS["gray"]]

    for ax, cell_id in zip(axes, cells):
        group = cycle[cycle["cell_id"] == cell_id]
        for regime, regime_group in group.groupby("protocol_regime_index"):
            color = regime_colors[int(regime - 1) % len(regime_colors)] if pd.notna(regime) else COLORS["gray"]
            ax.plot(
                regime_group["cycle_index"],
                regime_group["capacity_delta_ah"],
                marker="o",
                markersize=3.8,
                linewidth=1.5,
                color=color,
                label=f"Regime {int(regime)}" if pd.notna(regime) else "Unknown",
            )
        boundaries = group[group["protocol_boundary_flag"].astype(bool)]
        if not boundaries.empty:
            ax.scatter(
                boundaries["cycle_index"],
                boundaries["capacity_delta_ah"],
                s=65,
                marker="x",
                linewidth=2.0,
                color=COLORS["red"],
                label="Protocol boundary",
                zorder=5,
            )
        ax.set_ylabel(cell_id, rotation=0, ha="right", va="center", labelpad=26, weight="bold")
        ax.grid(True, axis="both")

    handles, labels = axes[0].get_legend_handles_labels()
    dedup = dict(zip(labels, handles))
    fig.legend(
        dedup.values(),
        dedup.keys(),
        frameon=False,
        loc="upper center",
        bbox_to_anchor=(0.5, 0.94),
        ncol=min(6, len(dedup)),
    )
    fig.suptitle("External Cycling Data: Protocol Regime Diagnostics", y=0.99, fontsize=15, weight="bold")
    axes[-1].set_xlabel("Cycle index")
    fig.text(0.02, 0.5, "Capacity delta (Ah)", rotation=90, va="center", color=COLORS["dark"])
    fig.tight_layout(rect=[0.04, 0.02, 1, 0.9])
    return save(fig, "03_external_protocol_regimes.png")


def plot_label_audit() -> Path:
    with (PROJECT_ROOT / "outputs" / "label_audit" / "external_trainable_labels" / "label_audit_report.json").open(
        "r", encoding="utf-8"
    ) as handle:
        report = json.load(handle)
    trainable = int(report["trainable_summary_rows"])
    excluded = int(report["excluded_summary_rows"])
    excluded_summary = pd.read_csv(
        PROJECT_ROOT / "outputs" / "label_audit" / "external_trainable_labels" / "excluded_label_summary.csv"
    )
    reason_counts = excluded_summary["trainable_label_quality"].value_counts().sort_values()

    fig, axes = plt.subplots(1, 2, figsize=(13, 5.5), gridspec_kw={"width_ratios": [0.85, 1.35]})
    ax = axes[0]
    wedges, _ = ax.pie(
        [trainable, excluded],
        startangle=90,
        colors=[COLORS["teal"], COLORS["gray"]],
        wedgeprops={"width": 0.42, "edgecolor": "white"},
    )
    ax.text(0, 0, f"{trainable}\ntrainable", ha="center", va="center", fontsize=15, weight="bold", color=COLORS["teal"])
    ax.legend(wedges, [f"Trainable: {trainable}", f"Excluded: {excluded}"], frameon=False, loc="lower center")
    ax.set_title("Audit Outcome")

    ax = axes[1]
    colors = [COLORS["gray"], COLORS["orange"], COLORS["red"], COLORS["purple"], COLORS["blue"]]
    ax.barh(reason_counts.index, reason_counts.values, color=colors[: len(reason_counts)])
    for y, value in enumerate(reason_counts.values):
        ax.text(value + 1, y, str(value), va="center", color=COLORS["dark"])
    ax.set_xlabel("Excluded label count")
    ax.set_title("Why Labels Were Excluded")
    ax.grid(True, axis="x")
    fig.suptitle("External Label Trainability Audit", y=1.02, fontsize=15, weight="bold")
    fig.tight_layout()
    return save(fig, "04_external_label_audit.png")


def plot_pipeline_overview() -> Path:
    fig, ax = plt.subplots(figsize=(13, 5.8))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    boxes = [
        ("Raw data", "NASA .mat\nExternal CSV/ZIP", 0.05, 0.58, COLORS["blue"]),
        ("Preprocessing", "cycle summary\ntimeseries\nimpedance/RPT", 0.25, 0.58, COLORS["teal"]),
        ("Feature system", "SOH features\nrolling trends\nprotocol regimes", 0.45, 0.58, COLORS["orange"]),
        ("Label system", "SOH/RUL\nmulti-threshold\ncensoring", 0.65, 0.58, COLORS["purple"]),
        ("Audit + demo", "trainable labels\nexclusions\nbaseline plot", 0.85, 0.58, COLORS["red"]),
    ]
    for title, body, x, y, color in boxes:
        rect = plt.Rectangle((x - 0.085, y - 0.16), 0.17, 0.28, facecolor="#FFFFFF", edgecolor=color, linewidth=2)
        ax.add_patch(rect)
        ax.text(x, y + 0.065, title, ha="center", va="center", fontsize=12, weight="bold", color=color)
        ax.text(x, y - 0.035, body, ha="center", va="center", fontsize=9.5, color=COLORS["dark"], linespacing=1.35)

    for i in range(len(boxes) - 1):
        x1 = boxes[i][2] + 0.09
        x2 = boxes[i + 1][2] - 0.09
        y = boxes[i][3]
        ax.annotate("", xy=(x2, y), xytext=(x1, y), arrowprops={"arrowstyle": "->", "lw": 1.8, "color": "#334155"})

    ax.text(
        0.5,
        0.18,
        "Positioning: a reproducible data and label foundation for later battery life prediction and strategy optimization",
        ha="center",
        va="center",
        fontsize=12,
        color=COLORS["dark"],
        weight="bold",
    )
    ax.set_title("Project Demo Storyline", fontsize=17, weight="bold", color=COLORS["dark"], pad=12)
    return save(fig, "05_project_pipeline_overview.png")


def main() -> None:
    set_style()
    paths = [
        plot_nasa_soh_curves(),
        plot_nasa_label_summary(),
        plot_external_protocol_regimes(),
        plot_label_audit(),
        plot_pipeline_overview(),
    ]
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
