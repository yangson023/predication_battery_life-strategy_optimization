"""Build audit-only lithium metal battery mechanism visualizations.

The generated figures are mechanism-audit artifacts only. They are not model
performance, do not create trainable labels, and do not enter the RUL pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd


FIGURE_FILES = [
    "licu_ce_trajectory_by_cell.png",
    "licu_incomplete_capacity_events.png",
    "licu_signal_counts_by_electrolyte_code.png",
    "lili_voltage_hysteresis_by_cell.png",
    "lili_polarization_candidates.png",
    "lili_signal_counts_by_electrolyte_code.png",
]

COLORS = {
    "blue": "#2563EB",
    "teal": "#0F766E",
    "orange": "#EA580C",
    "red": "#DC2626",
    "purple": "#7C3AED",
    "gray": "#64748B",
    "dark": "#111827",
    "light": "#F8FAFC",
}


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, encoding="utf-8-sig")


def bool_series(series: pd.Series) -> pd.Series:
    return series.astype(str).str.lower().isin(["true", "1", "yes"])


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
            "grid.color": "#E5E7EB",
            "grid.linewidth": 0.8,
            "axes.grid": True,
            "font.size": 9,
            "axes.titlesize": 12,
            "axes.titleweight": "bold",
            "axes.labelsize": 10,
            "legend.fontsize": 8,
            "savefig.dpi": 180,
            "savefig.bbox": "tight",
        }
    )


def save(fig: plt.Figure, output_root: Path, name: str) -> Path:
    output_root.mkdir(parents=True, exist_ok=True)
    path = output_root / name
    fig.savefig(path)
    plt.close(fig)
    return path


def annotate_gate(ax: plt.Axes) -> None:
    ax.text(
        0.99,
        0.02,
        "audit-only | not model performance",
        transform=ax.transAxes,
        ha="right",
        va="bottom",
        fontsize=8,
        color=COLORS["gray"],
    )


def with_metadata(features: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    if features.empty or metadata.empty:
        return features.copy()
    cols = ["cell_id", "source_folder_name", "electrolyte_code", "electrolyte_code_source"]
    meta = metadata[[col for col in cols if col in metadata.columns]].drop_duplicates()
    return features.merge(meta, on="source_folder_name", how="left")


def label_summary_with_metadata(label_summary: pd.DataFrame, metadata: pd.DataFrame) -> pd.DataFrame:
    if label_summary.empty or metadata.empty:
        return label_summary.copy()
    cols = ["source_folder_name", "electrolyte_code"]
    meta = metadata[[col for col in cols if col in metadata.columns]].drop_duplicates()
    if "source_folder_name" not in meta.columns:
        return label_summary.copy()
    return label_summary.merge(meta, on="source_folder_name", how="left")


def event_subset(events: pd.DataFrame, cell_group: str, label_keys: Iterable[str]) -> pd.DataFrame:
    if events.empty:
        return events.copy()
    subset = events[(events["cell_group"] == cell_group) & (events["label_key"].isin(list(label_keys)))].copy()
    if "observed_candidate" in subset.columns:
        subset = subset[bool_series(subset["observed_candidate"])]
    return subset


def plot_licu_ce_trajectory(licu: pd.DataFrame, events: pd.DataFrame, metadata: pd.DataFrame, output_root: Path) -> Path:
    data = with_metadata(licu, metadata)
    fig, ax = plt.subplots(figsize=(11, 6))
    for cell_id, group in data.groupby("source_folder_name"):
        group = group.sort_values("cycle_index")
        code = group["electrolyte_code"].iloc[0] if "electrolyte_code" in group and not group.empty else "unknown"
        ax.plot(group["cycle_index"], group["coulombic_efficiency_percent"], linewidth=1.6, label=f"{cell_id} ({code})")
    collapse = event_subset(events, "Li||Cu", ["ce_collapse"])
    if not collapse.empty:
        ax.scatter(
            collapse["cycle_index"],
            pd.to_numeric(collapse["signal_value"], errors="coerce"),
            color=COLORS["red"],
            s=18,
            marker="x",
            label="ce_collapse candidate",
            zorder=4,
        )
    ax.axhline(100, color=COLORS["gray"], linewidth=1.0, linestyle="--")
    ax.set_title("Li||Cu CE Trajectory by Cell")
    ax.set_xlabel("cycle_index")
    ax.set_ylabel("Coulombic efficiency (%)")
    ax.set_ylim(-10, 210)
    ax.legend(ncol=2)
    annotate_gate(ax)
    return save(fig, output_root, "licu_ce_trajectory_by_cell.png")


def plot_licu_incomplete_events(events: pd.DataFrame, output_root: Path) -> Path:
    incomplete = event_subset(events, "Li||Cu", ["incomplete_capacity_event"])
    collapse = event_subset(events, "Li||Cu", ["ce_collapse"])
    fig, ax = plt.subplots(figsize=(11, 5.8))
    cells = sorted(set(incomplete.get("source_folder_name", pd.Series(dtype=str))).union(set(collapse.get("source_folder_name", pd.Series(dtype=str)))))
    cell_to_y = {cell: index for index, cell in enumerate(cells)}
    if not incomplete.empty:
        ax.scatter(
            incomplete["cycle_index"],
            incomplete["source_folder_name"].map(cell_to_y),
            s=20,
            color=COLORS["orange"],
            label="incomplete_capacity_event",
        )
    if not collapse.empty:
        ax.scatter(
            collapse["cycle_index"],
            collapse["source_folder_name"].map(cell_to_y),
            s=26,
            color=COLORS["red"],
            marker="x",
            label="ce_collapse",
        )
    ax.set_yticks(list(cell_to_y.values()))
    ax.set_yticklabels(list(cell_to_y.keys()))
    ax.set_title("Li||Cu Audit Candidate Event Timeline")
    ax.set_xlabel("cycle_index")
    ax.set_ylabel("cell")
    ax.legend()
    annotate_gate(ax)
    return save(fig, output_root, "licu_incomplete_capacity_events.png")


def signal_counts_by_electrolyte(label_meta: pd.DataFrame, cell_group: str) -> pd.DataFrame:
    if label_meta.empty:
        return pd.DataFrame()
    subset = label_meta[label_meta["cell_group"] == cell_group].copy()
    if subset.empty:
        return pd.DataFrame()
    subset["observed_candidate_count"] = pd.to_numeric(subset["observed_candidate_count"], errors="coerce").fillna(0)
    grouped = (
        subset.groupby(["electrolyte_code", "label_key"], as_index=False)["observed_candidate_count"].sum()
        .pivot(index="electrolyte_code", columns="label_key", values="observed_candidate_count")
        .fillna(0)
        .sort_index()
    )
    return grouped


def plot_signal_counts(label_meta: pd.DataFrame, cell_group: str, output_root: Path, filename: str) -> Path:
    grouped = signal_counts_by_electrolyte(label_meta, cell_group)
    fig, ax = plt.subplots(figsize=(10.5, 5.8))
    if grouped.empty:
        ax.text(0.5, 0.5, f"No {cell_group} signal rows", ha="center", va="center")
    else:
        grouped.plot(kind="bar", stacked=True, ax=ax, colormap="tab20")
    ax.set_title(f"{cell_group} Audit Signal Counts by Electrolyte Code")
    ax.set_xlabel("partner-provided electrolyte code")
    ax.set_ylabel("observed candidate count")
    ax.legend(loc="upper left", bbox_to_anchor=(1.01, 1.0), title="audit signal")
    annotate_gate(ax)
    return save(fig, output_root, filename)


def plot_lili_hysteresis(lili: pd.DataFrame, events: pd.DataFrame, metadata: pd.DataFrame, output_root: Path) -> Path:
    data = with_metadata(lili, metadata)
    fig, ax = plt.subplots(figsize=(11, 6))
    for cell_id, group in data.groupby("source_folder_name"):
        group = group.sort_values("cycle_index")
        code = group["electrolyte_code"].iloc[0] if "electrolyte_code" in group and not group.empty else "unknown"
        linewidth = 2.4 if cell_id == "26-0414" else 1.5
        alpha = 1.0 if cell_id == "26-0414" else 0.75
        ax.plot(group["cycle_index"], group["voltage_hysteresis_v"], linewidth=linewidth, alpha=alpha, label=f"{cell_id} ({code})")
    failure = event_subset(events, "Li||Li", ["voltage_hysteresis_failure"])
    if not failure.empty:
        ax.scatter(
            failure["cycle_index"],
            pd.to_numeric(failure["signal_value"].astype(str).str.extract(r"hysteresis=([^;]+)")[0], errors="coerce"),
            color=COLORS["red"],
            s=18,
            marker="x",
            label="voltage_hysteresis_failure candidate",
        )
    ax.set_title("Li||Li Voltage Hysteresis by Cell")
    ax.set_xlabel("cycle_index")
    ax.set_ylabel("voltage_hysteresis_v")
    ax.legend(ncol=2)
    annotate_gate(ax)
    return save(fig, output_root, "lili_voltage_hysteresis_by_cell.png")


def plot_lili_polarization(lili: pd.DataFrame, events: pd.DataFrame, metadata: pd.DataFrame, output_root: Path) -> Path:
    data = with_metadata(lili, metadata)
    fig, ax = plt.subplots(figsize=(11, 6))
    for cell_id, group in data.groupby("source_folder_name"):
        group = group.sort_values("cycle_index")
        code = group["electrolyte_code"].iloc[0] if "electrolyte_code" in group and not group.empty else "unknown"
        linewidth = 2.4 if cell_id == "26-0414" else 1.5
        ax.plot(
            group["cycle_index"],
            group["hysteresis_rolling_mean_past_5"],
            linewidth=linewidth,
            label=f"{cell_id} ({code})",
        )
    polarization = event_subset(events, "Li||Li", ["polarization_growth"])
    if not polarization.empty:
        ax.scatter(
            polarization["cycle_index"],
            pd.to_numeric(polarization["signal_value"], errors="coerce"),
            color=COLORS["purple"],
            s=20,
            label="polarization_growth candidate",
            zorder=4,
        )
    ax.set_title("Li||Li Polarization Candidate Audit")
    ax.set_xlabel("cycle_index")
    ax.set_ylabel("hysteresis_rolling_mean_past_5")
    ax.legend(ncol=2)
    annotate_gate(ax)
    return save(fig, output_root, "lili_polarization_candidates.png")


def summarize_findings(metadata: pd.DataFrame, label_meta: pd.DataFrame) -> dict[str, object]:
    obvious_cells: list[dict[str, object]] = []
    if not metadata.empty:
        for _, row in metadata.iterrows():
            count = int(pd.to_numeric(pd.Series([row.get("observed_candidate_total", 0)]), errors="coerce").fillna(0).iloc[0])
            if count > 0:
                obvious_cells.append(
                    {
                        "cell_id": row.get("cell_id"),
                        "cell_group": row.get("cell_group"),
                        "electrolyte_code": row.get("electrolyte_code"),
                        "observed_candidate_total": count,
                        "top_observed_label_keys": row.get("top_observed_label_keys", ""),
                        "recommended_next_review": row.get("recommended_next_review", ""),
                    }
                )
    signal_counts = {}
    if not label_meta.empty:
        temp = label_meta.copy()
        temp["observed_candidate_count"] = pd.to_numeric(temp["observed_candidate_count"], errors="coerce").fillna(0)
        signal_counts = temp.groupby(["cell_group", "label_key"])["observed_candidate_count"].sum().to_dict()
        signal_counts = {f"{group}::{label}": int(count) for (group, label), count in signal_counts.items()}
    return {"obvious_candidate_cells": obvious_cells, "signal_counts": signal_counts}


def write_report(output_root: Path, figure_paths: list[Path], metadata: pd.DataFrame, label_meta: pd.DataFrame) -> dict[str, object]:
    findings = summarize_findings(metadata, label_meta)
    report = {
        "training_allowed_now": False,
        "model_training_allowed": False,
        "model_performance": False,
        "labels_generated": False,
        "raw_btsda_data_read": False,
        "audit_only": True,
        "record_sample_limited": True,
        "electrolyte_code_interpretation": "partner-provided code only, not a full electrolyte formula",
        "figures": [path.name for path in figure_paths],
        "findings": findings,
        "next_metadata_priorities": ["termination reason", "cycling protocol", "current density", "areal capacity", "full electrolyte salt/concentration/additive"],
        "training_gate": "model training remains prohibited",
    }
    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / "lmb_audit_visualization_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    lines = [
        "# LMB Audit Visualization Report",
        "",
        "These figures are audit-only mechanism views. They are not model performance, do not create training labels, and do not enter `rul-prediction`.",
        "",
        f"- Figures generated: {len(figure_paths)}",
        "- `training_allowed_now = False`",
        "- `model_performance = False`",
        "- Electrolyte values are partner-provided codes only, not full formulas.",
        "- Record-derived fields remain sample-limited where applicable.",
        "",
        "## Generated Figures",
        "",
    ]
    lines.extend(f"- `{path.name}`" for path in figure_paths)
    lines.extend(["", "## Candidate Cells to Review", ""])
    for item in findings["obvious_candidate_cells"]:
        lines.append(
            f"- `{item['cell_id']}` ({item['cell_group']}, {item['electrolyte_code']}): "
            f"{item['top_observed_label_keys']} -> {item['recommended_next_review']}"
        )
    lines.extend(
        [
            "",
            "## Interpretation Limits",
            "",
            "- Li||Cu CE and capacity event figures are audit signals, not labels.",
            "- Li||Li hysteresis and polarization candidates require manual mechanism review.",
            "- Current metadata still lacks termination reason, cycling protocol, current density, areal capacity, and full electrolyte details.",
            "- Therefore trainability audit and model training remain blocked.",
            "",
            "## Next Priorities",
            "",
            "1. Review Li||Cu `incomplete_capacity_event` and `ce_collapse` regions.",
            "2. Review Li||Li `26-0414` hysteresis and polarization regions.",
            "3. Ask partner/advisor for termination reason and protocol metadata before trainability audit.",
        ]
    )
    (output_root / "lmb_audit_visualization_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_lmb_audit_visualization(
    lili_features: Path,
    licu_features: Path,
    audit_event_scan: Path,
    audit_label_summary: Path,
    metadata_cell_summary: Path,
    electrolyte_summary: Path,
    output_root: Path,
) -> dict[str, object]:
    set_style()
    lili = read_csv(lili_features)
    licu = read_csv(licu_features)
    events = read_csv(audit_event_scan)
    label_meta = read_csv(audit_label_summary)
    metadata = read_csv(metadata_cell_summary)
    electrolyte = read_csv(electrolyte_summary)
    label_meta = label_summary_with_metadata(label_meta, metadata)

    # Keep the electrolyte summary read explicit so missing/renamed files fail
    # during tests and local validation instead of silently skipping metadata.
    if electrolyte.empty and not electrolyte_summary.exists():
        raise FileNotFoundError(electrolyte_summary)

    figure_paths = [
        plot_licu_ce_trajectory(licu, events, metadata, output_root),
        plot_licu_incomplete_events(events, output_root),
        plot_signal_counts(label_meta, "Li||Cu", output_root, "licu_signal_counts_by_electrolyte_code.png"),
        plot_lili_hysteresis(lili, events, metadata, output_root),
        plot_lili_polarization(lili, events, metadata, output_root),
        plot_signal_counts(label_meta, "Li||Li", output_root, "lili_signal_counts_by_electrolyte_code.png"),
    ]
    return write_report(output_root, figure_paths, metadata, label_meta)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lili-features", required=True)
    parser.add_argument("--licu-features", required=True)
    parser.add_argument("--audit-event-scan", required=True)
    parser.add_argument("--audit-label-summary", required=True)
    parser.add_argument("--metadata-cell-summary", required=True)
    parser.add_argument("--electrolyte-summary", required=True)
    parser.add_argument("--output-root", required=True)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    report = build_lmb_audit_visualization(
        lili_features=Path(args.lili_features),
        licu_features=Path(args.licu_features),
        audit_event_scan=Path(args.audit_event_scan),
        audit_label_summary=Path(args.audit_label_summary),
        metadata_cell_summary=Path(args.metadata_cell_summary),
        electrolyte_summary=Path(args.electrolyte_summary),
        output_root=Path(args.output_root),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
