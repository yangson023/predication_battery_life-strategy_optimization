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
    "line": "#CBD5E1",
}


def set_style() -> None:
    plt.rcParams.update(
        {
            "figure.facecolor": "white",
            "axes.facecolor": "white",
            "axes.edgecolor": COLORS["line"],
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


def load_json(path: str) -> dict:
    with (PROJECT_ROOT / path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def plot_round1a_label_gate_progress() -> Path:
    before = load_json("outputs/label_audit/external_trainable_labels/label_audit_report.json")
    after = load_json("outputs/label_audit/external_trainable_labels_with_round1a/label_audit_report.json")

    def counts(report: dict) -> dict[str, int]:
        return {row["label_key"]: int(row["count"]) for row in report["trainable_by_label_key"]}

    before_counts = counts(before)
    after_counts = counts(after)
    label_keys = ["capacity_eol_75", "capacity_eol_80"]
    targets = {"capacity_eol_75": 9, "capacity_eol_80": 11}

    x = np.arange(len(label_keys))
    width = 0.28
    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    ax.bar(x - width, [before_counts.get(k, 0) for k in label_keys], width, color=COLORS["gray"], label="Before Round 1a")
    ax.bar(x, [after_counts.get(k, 0) for k in label_keys], width, color=COLORS["blue"], label="After Round 1a")
    ax.bar(x + width, [targets[k] for k in label_keys], width, color=COLORS["teal"], alpha=0.35, label="Minimum gate")

    for i, key in enumerate(label_keys):
        values = [before_counts.get(key, 0), after_counts.get(key, 0), targets[key]]
        for offset, value in zip([-width, 0, width], values):
            ax.text(i + offset, value + 0.25, str(value), ha="center", va="bottom", color=COLORS["dark"], weight="bold")
        status = "still blocked" if after_counts.get(key, 0) < targets[key] else "gate passed"
        ax.text(i, targets[key] + 1.2, status, ha="center", color=COLORS["red"] if status == "still blocked" else COLORS["teal"])

    ax.set_xticks(x, ["EOL 75%", "EOL 80%"])
    ax.set_ylabel("Strict candidate cells")
    ax.set_title("Round 1a Improved Label Coverage, But Training Gate Is Not Passed")
    ax.set_ylim(0, 14)
    ax.grid(True, axis="y")
    ax.legend(frameon=False, loc="upper left")
    return save(fig, "06_round1a_label_gate_progress.png")


def plot_round1a_expansion_funnel() -> Path:
    stages = [
        ("Added cells", 7, COLORS["blue"]),
        ("Archive members\nwritten", 568, COLORS["teal"]),
        ("Cycle feature\nrows", 280, COLORS["orange"]),
        ("RPT feature\nrows", 288, COLORS["purple"]),
        ("Strict exploratory\ncandidates", 5, COLORS["red"]),
    ]

    fig, ax = plt.subplots(figsize=(12, 5.4))
    ax.axis("off")
    xs = np.linspace(0.08, 0.92, len(stages))
    y = 0.52
    for i, ((title, value, color), x) in enumerate(zip(stages, xs)):
        circle = plt.Circle((x, y), 0.095, facecolor="white", edgecolor=color, linewidth=2.5)
        ax.add_patch(circle)
        ax.text(x, y + 0.025, f"{value}", ha="center", va="center", fontsize=19, weight="bold", color=color)
        ax.text(x, y - 0.145, title, ha="center", va="top", fontsize=10, color=COLORS["dark"], linespacing=1.25)
        if i < len(stages) - 1:
            ax.annotate(
                "",
                xy=(xs[i + 1] - 0.11, y),
                xytext=(x + 0.11, y),
                arrowprops={"arrowstyle": "->", "lw": 1.7, "color": "#334155"},
            )

    ax.text(
        0.5,
        0.12,
        "Round 1a is useful as an audit expansion: it increases evidence, but still does not authorize stronger model training.",
        ha="center",
        va="center",
        fontsize=11,
        color=COLORS["dark"],
        weight="bold",
    )
    ax.set_title("External Data Expansion Round 1a Audit Funnel", fontsize=15, weight="bold", pad=10)
    return save(fig, "07_round1a_expansion_funnel.png")


def plot_loco_timing_diagnostics() -> Path:
    df = pd.read_csv(
        PROJECT_ROOT
        / "models"
        / "rul_prediction"
        / "external_loco_binary_baseline"
        / "combined_main"
        / "diagnostics"
        / "prediction_timing_error.csv"
    )
    df = df.sort_values(["label_key", "prediction_timing_error_cycles", "cell_id"]).copy()
    df["case"] = df["label_key"].str.replace("capacity_eol_", "EOL ", regex=False) + " / " + df["cell_id"]
    colors = df["timing_class"].map({"exact_eol_hit": COLORS["teal"], "early_false_positive": COLORS["red"]}).fillna(COLORS["gray"])

    fig, ax = plt.subplots(figsize=(11.2, 6.2))
    y = np.arange(len(df))
    ax.barh(y, df["prediction_timing_error_cycles"], color=colors)
    ax.axvline(0, color=COLORS["dark"], linewidth=1)
    ax.set_yticks(y, df["case"])
    ax.set_xlabel("Prediction timing error in cycles (negative = early)")
    ax.set_title("Exploratory LOCO Baseline Mainly Produces Early Warnings")
    ax.grid(True, axis="x")
    for i, value in enumerate(df["prediction_timing_error_cycles"]):
        ax.text(value - 0.25 if value < 0 else value + 0.15, i, str(int(value)), va="center", ha="right" if value < 0 else "left")
    ax.text(
        0.98,
        0.08,
        "9 early false positives\n1 exact EOL hit",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        color=COLORS["dark"],
        bbox={"boxstyle": "round,pad=0.45", "facecolor": COLORS["light"], "edgecolor": COLORS["line"]},
    )
    return save(fig, "08_loco_timing_diagnostics.png")


def plot_feature_exclusion_diagnostics() -> Path:
    df = pd.read_csv(
        PROJECT_ROOT
        / "models"
        / "rul_prediction"
        / "external_loco_binary_baseline"
        / "combined_main"
        / "feature_exclusion_diagnostics"
        / "feature_exclusion_decisions.csv"
    )
    df = df.sort_values("timing_error_abs_improved_folds")
    x = np.arange(len(df))
    width = 0.32

    fig, ax = plt.subplots(figsize=(10.8, 5.8))
    ax.bar(x - width / 2, df["false_positive_reduced_folds"], width, color=COLORS["orange"], label="FP reduced folds")
    ax.bar(x + width / 2, df["timing_error_abs_improved_folds"], width, color=COLORS["blue"], label="Timing improved folds")
    for i, row in df.reset_index(drop=True).iterrows():
        top = max(row["false_positive_reduced_folds"], row["timing_error_abs_improved_folds"])
        ax.text(i, top + 0.22, row["diagnostic_decision"], ha="center", va="bottom", fontsize=9, color=COLORS["dark"])

    ax.set_xticks(x, df["excluded_feature"], rotation=0)
    ax.set_ylabel("Folds affected out of 10")
    ax.set_ylim(0, 4.4)
    ax.set_title("Single-Feature Exclusion Flags energy_wh_last As Possible Confound")
    ax.grid(True, axis="y")
    ax.legend(frameon=False, loc="upper left")
    return save(fig, "09_feature_exclusion_diagnostics.png")


def main() -> None:
    set_style()
    paths = [
        plot_round1a_label_gate_progress(),
        plot_round1a_expansion_funnel(),
        plot_loco_timing_diagnostics(),
        plot_feature_exclusion_diagnostics(),
    ]
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
