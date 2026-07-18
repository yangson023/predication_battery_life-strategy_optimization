"""Describe early-cycle feature stability for protocol-censored LMB full cells.

This audit reads only small feature, schema, and censor-audit tables. It does
not fit a model or make causal comparisons between distinct protocols.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


CELL_COLUMNS = [
    "cell_id", "protocol_id", "feature_name", "feature_family", "same_signal_source_risk",
    "valid_row_count", "first_valid_long_cycle", "last_valid_long_cycle", "mean", "std", "min", "max",
    "coefficient_of_variation", "within_cell_slope_per_cycle", "audit_interpretation", "model_training_allowed",
]
PROTOCOL_COLUMNS = [
    "protocol_id", "feature_name", "feature_family", "same_signal_source_risk", "cell_count", "value_count",
    "mean", "std", "min", "max", "audit_interpretation", "model_training_allowed",
]
COVERAGE_COLUMNS = ["feature_name", "feature_family", "same_signal_source_risk", "total_rows", "non_empty_rows", "coverage_fraction", "model_training_allowed"]
COMPARISON_COLUMNS = [
    "feature_name", "protocol_a", "protocol_b", "protocol_a_mean", "protocol_b_mean", "descriptive_mean_difference",
    "comparison_status", "reason", "model_training_allowed",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", type=Path, required=True)
    parser.add_argument("--feature-schema", type=Path, required=True)
    parser.add_argument("--protocol-censor-audit", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def to_float(value: Any) -> float | None:
    try:
        text = str(value or "").strip()
        return float(text) if text else None
    except ValueError:
        return None


def to_int(value: Any) -> int | None:
    number = to_float(value)
    return int(number) if number is not None else None


def slope(points: list[tuple[int, float]]) -> float | str:
    if len(points) < 2:
        return ""
    x_mean = statistics.fmean(point[0] for point in points)
    y_mean = statistics.fmean(point[1] for point in points)
    denominator = sum((x - x_mean) ** 2 for x, _ in points)
    return sum((x - x_mean) * (y - y_mean) for x, y in points) / denominator if denominator else ""


def audit_early_feature_stability(
    features_path: Path,
    feature_schema_path: Path,
    protocol_censor_audit_path: Path,
    output_root: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    feature_rows = read_csv(features_path)
    schema_rows = read_csv(feature_schema_path)
    censor_rows = read_csv(protocol_censor_audit_path)
    schema = {row["feature_name"]: row for row in schema_rows}
    feature_names = list(schema)
    if not feature_rows:
        raise ValueError("Feature input is empty")
    censor_cells = {row["cell_id"] for row in censor_rows if row.get("event_observed") == "False"}
    feature_cells = {row["cell_id"] for row in feature_rows}
    if not feature_cells.issubset(censor_cells):
        raise ValueError("Feature rows include cells absent from the protocol-censor audit")
    if any(row.get("training_allowed_now") != "False" for row in feature_rows):
        raise ValueError("Early feature audit requires training_allowed_now=False")

    per_cell: list[dict[str, Any]] = []
    per_protocol_values: dict[tuple[str, str], list[float]] = defaultdict(list)
    coverage: list[dict[str, Any]] = []
    for feature in feature_names:
        metadata = schema[feature]
        valid = [to_float(row.get(feature)) for row in feature_rows]
        values = [value for value in valid if value is not None]
        coverage.append({
            "feature_name": feature,
            "feature_family": metadata.get("feature_family", ""),
            "same_signal_source_risk": metadata.get("same_signal_source_risk", ""),
            "total_rows": len(feature_rows),
            "non_empty_rows": len(values),
            "coverage_fraction": len(values) / len(feature_rows),
            "model_training_allowed": False,
        })
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in feature_rows:
        grouped[(row["cell_id"], row["protocol_id"], row["export_suffix"])].append(row)
    for (cell_id, protocol_id, _), rows in grouped.items():
        for feature in feature_names:
            metadata = schema[feature]
            points = [(to_int(row.get("current_long_cycle_index")) or 0, value) for row in rows if (value := to_float(row.get(feature))) is not None]
            values = [value for _, value in points]
            if values:
                mean_value = statistics.fmean(values)
                std_value = statistics.pstdev(values) if len(values) > 1 else 0.0
                cv = abs(std_value / mean_value) if mean_value else ""
                per_protocol_values[(protocol_id, feature)].extend(values)
            else:
                mean_value = std_value = ""
                cv = ""
            per_cell.append({
                "cell_id": cell_id,
                "protocol_id": protocol_id,
                "feature_name": feature,
                "feature_family": metadata.get("feature_family", ""),
                "same_signal_source_risk": metadata.get("same_signal_source_risk", ""),
                "valid_row_count": len(points),
                "first_valid_long_cycle": points[0][0] if points else "",
                "last_valid_long_cycle": points[-1][0] if points else "",
                "mean": mean_value,
                "std": std_value,
                "min": min(values) if values else "",
                "max": max(values) if values else "",
                "coefficient_of_variation": cv,
                "within_cell_slope_per_cycle": slope(points),
                "audit_interpretation": "descriptive_past_only_feature_summary_not_model_signal",
                "model_training_allowed": False,
            })
    protocol_summary: list[dict[str, Any]] = []
    cells_by_protocol: dict[str, set[str]] = defaultdict(set)
    for row in feature_rows:
        cells_by_protocol[row["protocol_id"]].add(row["cell_id"])
    for (protocol_id, feature), values in sorted(per_protocol_values.items()):
        metadata = schema[feature]
        protocol_summary.append({
            "protocol_id": protocol_id,
            "feature_name": feature,
            "feature_family": metadata.get("feature_family", ""),
            "same_signal_source_risk": metadata.get("same_signal_source_risk", ""),
            "cell_count": len(cells_by_protocol[protocol_id]),
            "value_count": len(values),
            "mean": statistics.fmean(values),
            "std": statistics.pstdev(values) if len(values) > 1 else 0.0,
            "min": min(values),
            "max": max(values),
            "audit_interpretation": "within_protocol_descriptive_summary_only",
            "model_training_allowed": False,
        })
    comparisons: list[dict[str, Any]] = []
    protocols = sorted(cells_by_protocol)
    if len(protocols) == 2:
        first, second = protocols
        for feature in feature_names:
            first_values = per_protocol_values.get((first, feature), [])
            second_values = per_protocol_values.get((second, feature), [])
            if not first_values or not second_values:
                continue
            first_mean, second_mean = statistics.fmean(first_values), statistics.fmean(second_values)
            comparisons.append({
                "feature_name": feature, "protocol_a": first, "protocol_b": second,
                "protocol_a_mean": first_mean, "protocol_b_mean": second_mean,
                "descriptive_mean_difference": second_mean - first_mean,
                "comparison_status": "confounded_design_and_operation_comparison_not_causal",
                "reason": "Cathode diameter and charge/discharge protocol differ together; electrolyte code is constant, so no causal electrolyte or protocol effect can be claimed.",
                "model_training_allowed": False,
            })
    write_csv(output_root / "lmb_full_cell_early_feature_cell_summary.csv", per_cell, CELL_COLUMNS)
    write_csv(output_root / "lmb_full_cell_early_feature_protocol_summary.csv", protocol_summary, PROTOCOL_COLUMNS)
    write_csv(output_root / "lmb_full_cell_early_feature_coverage.csv", coverage, COVERAGE_COLUMNS)
    write_csv(output_root / "lmb_full_cell_protocol_difference_audit.csv", comparisons, COMPARISON_COLUMNS)
    report = {
        "protocol_censored_cell_count": len(censor_cells),
        "early_feature_row_count": len(feature_rows),
        "protocol_count": len(protocols),
        "feature_count": len(feature_names),
        "same_signal_source_risk_feature_count": sum(row.get("same_signal_source_risk") == "True" for row in schema_rows),
        "comparison_status": "confounded_design_and_operation_comparison_not_causal",
        "audit_only": True,
        "model_training_allowed": False,
        "model_performance_claimed": False,
        "next_gate": "Add observed-failure full-cell data under documented conditions; use current descriptive summaries only for feature-family retention and data-quality review.",
    }
    (output_root / "lmb_full_cell_early_feature_stability_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = [
        "# LMB Full-Cell Early-Cycle Feature Stability Audit", "",
        "This is descriptive feature and protocol audit only, not model performance.", "",
        f"- Protocol-censored cells: `{len(censor_cells)}`",
        f"- Early feature rows: `{len(feature_rows)}`",
        f"- Protocols represented: `{len(protocols)}`",
        f"- Feature families reviewed: `{len(feature_names)}`",
        "", "## Interpretation Boundary", "",
        "The two protocols differ in cathode diameter and charge/discharge conditions. Their descriptive feature differences are confounded and cannot establish a causal protocol, electrolyte, or material effect.",
        "", "```text", "audit_only=True", "model_training_allowed=False", "model_performance_claimed=False", "```",
    ]
    (output_root / "lmb_full_cell_early_feature_stability_report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return report


def main() -> None:
    args = parse_args()
    audit_early_feature_stability(args.features, args.feature_schema, args.protocol_censor_audit, args.output_root, args.overwrite)


if __name__ == "__main__":
    main()
