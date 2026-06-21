"""Export candidate baseline-ready LMB Li||Cu dataset.

This export is a candidate input package only. It does not train a model,
enter the RUL prediction pipeline, generate model performance, or claim a
formal training dataset.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


TARGET_CELL_GROUP = "Li||Cu"
TARGET_LABEL_KEY = "incomplete_capacity_event"
MIN_PRE_EVENT_ROWS = 10

IDENTIFIER_COLUMNS = ["source_folder_name", "selected_dataset_name", "cycle_index"]
EXPLICIT_LEAKAGE_COLUMNS = {
    "charge_capacity_mah",
    "discharge_capacity_mah",
    "coulombic_efficiency_percent",
    "irreversible_capacity_mah",
    "incomplete_cycle_flag",
    "ce_warning_flag",
    "capacity_retention_percent",
    "exclude_from_label_training",
}
SEMANTIC_BLOCK_KEYWORDS = (
    "target",
    "label",
    "future",
    "event",
    "capacity",
    "charge",
    "discharge",
    "throughput",
    "ce",
    "incomplete_cycle_flag",
)
QUALITY_METADATA_COLUMNS = {"audit_warning_only", "record_sample_limited"}

FEATURE_ID_COLUMN = "row_id"

TARGET_COLUMNS = [
    "row_id",
    "source_folder_name",
    "selected_dataset_name",
    "cycle_index",
    "label_key",
    "target_event_next_cycle",
    "target_event_cycle",
    "prediction_horizon_cycles",
    "candidate_export_only",
    "training_allowed_now",
]

METADATA_COLUMNS = [
    "row_id",
    "source_folder_name",
    "selected_dataset_name",
    "cycle_index",
    "cell_group",
    "label_key",
    "first_event_cycle",
    "last_cycle_index",
    "protocol_censored_terminal",
    "pre_event_cycle_count",
    "post_event_cycle_count",
    "target_event_next_cycle",
    "metadata_gate_status",
    "termination_interpretation",
    "candidate_export_only",
    "model_feature_allowed",
    "training_allowed_now",
]

REMOVED_COLUMNS = [
    "column_name",
    "present_in_source_features",
    "block_reason",
    "blocked_from_model_features",
    "retained_elsewhere",
]

EXCLUDED_CELL_COLUMNS = [
    "source_folder_name",
    "selected_dataset_name",
    "label_key",
    "first_event_cycle",
    "pre_event_cycle_count",
    "baseline_ready_export_candidate",
    "exclusion_reason",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_int(value: object) -> int:
    try:
        text = str(value).strip()
        if not text:
            return 0
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def source_columns(rows: list[dict[str, str]]) -> list[str]:
    if not rows:
        return []
    return list(rows[0].keys())


def metadata_by_cell(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("电池编号", ""): row for row in rows if row.get("电池编号")}


def design_by_cell(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("source_folder_name", ""): row for row in rows if row.get("source_folder_name")}


def blocked_column_reason(column: str) -> str | None:
    lower = column.lower()
    if column in IDENTIFIER_COLUMNS:
        return "identifier_or_alignment_metadata_not_model_feature"
    if column in EXPLICIT_LEAKAGE_COLUMNS:
        return "explicit_leakage_or_label_proximal_column"
    if column in QUALITY_METADATA_COLUMNS:
        return "quality_or_sampling_metadata_not_model_feature"
    if any(keyword in lower for keyword in SEMANTIC_BLOCK_KEYWORDS):
        return "target_label_future_event_semantic_leakage"
    return None


def blocked_columns(feature_columns: list[str]) -> dict[str, str]:
    blocked: dict[str, str] = {}
    for column in feature_columns:
        reason = blocked_column_reason(column)
        if reason:
            blocked[column] = reason
    for column in EXPLICIT_LEAKAGE_COLUMNS:
        blocked.setdefault(column, "explicit_leakage_or_label_proximal_column")
    return blocked


def allowed_feature_columns(feature_columns: list[str]) -> list[str]:
    blocked = blocked_columns(feature_columns)
    return [column for column in feature_columns if column not in blocked]


def row_id(cell_id: str, cycle_index: int) -> str:
    safe_cell = cell_id.replace(" ", "_")
    return f"{safe_cell}__cycle_{cycle_index}"


def excluded_cell_row(row: dict[str, str], reason: str) -> dict[str, Any]:
    return {
        "source_folder_name": row.get("source_folder_name", ""),
        "selected_dataset_name": row.get("selected_dataset_name", ""),
        "label_key": row.get("label_key", ""),
        "first_event_cycle": row.get("first_event_cycle", ""),
        "pre_event_cycle_count": row.get("pre_event_cycle_count", ""),
        "baseline_ready_export_candidate": row.get("baseline_ready_export_candidate", ""),
        "exclusion_reason": reason,
    }


def build_removed_rows(feature_columns: list[str]) -> list[dict[str, Any]]:
    blocked = blocked_columns(feature_columns)
    present = set(feature_columns)
    rows: list[dict[str, Any]] = []
    for column, reason in sorted(blocked.items()):
        rows.append(
            {
                "column_name": column,
                "present_in_source_features": column in present,
                "block_reason": reason,
                "blocked_from_model_features": True,
                "retained_elsewhere": column in IDENTIFIER_COLUMNS or column in QUALITY_METADATA_COLUMNS,
            }
        )
    return rows


def export_rows(
    design_rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    metadata_rows: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    metadata = metadata_by_cell(metadata_rows)
    designs = design_by_cell(design_rows)
    feature_columns = source_columns(feature_rows)
    model_columns = allowed_feature_columns(feature_columns)
    features_out: list[dict[str, Any]] = []
    targets_out: list[dict[str, Any]] = []
    metadata_out: list[dict[str, Any]] = []
    excluded_cells: list[dict[str, Any]] = []

    for design in design_rows:
        cell_id = design.get("source_folder_name", "")
        if design.get("cell_group") != TARGET_CELL_GROUP or design.get("label_key") != TARGET_LABEL_KEY:
            excluded_cells.append(excluded_cell_row(design, "not_target_licu_incomplete_capacity_event"))
            continue
        if not parse_bool(design.get("baseline_ready_export_candidate")):
            excluded_cells.append(excluded_cell_row(design, "baseline_ready_export_candidate_false_or_design_only"))
            continue
        pre_event_count = parse_int(design.get("pre_event_cycle_count"))
        if pre_event_count < MIN_PRE_EVENT_ROWS:
            excluded_cells.append(excluded_cell_row(design, "pre_event_history_below_minimum"))
            continue
        first_event = parse_int(design.get("first_event_cycle"))
        cell_features = [
            row
            for row in feature_rows
            if row.get("source_folder_name") == cell_id and parse_int(row.get("cycle_index")) < first_event
        ]
        if len(cell_features) < MIN_PRE_EVENT_ROWS:
            excluded_cells.append(excluded_cell_row(design, "exportable_feature_rows_below_minimum"))
            continue
        cell_meta = metadata.get(cell_id, {})
        for row in sorted(cell_features, key=lambda item: parse_int(item.get("cycle_index"))):
            cycle = parse_int(row.get("cycle_index"))
            rid = row_id(cell_id, cycle)
            target = 1 if cycle + 1 == first_event else 0
            feature_payload = {FEATURE_ID_COLUMN: rid}
            for column in model_columns:
                feature_payload[column] = row.get(column, "")
            features_out.append(feature_payload)
            targets_out.append(
                {
                    "row_id": rid,
                    "source_folder_name": cell_id,
                    "selected_dataset_name": row.get("selected_dataset_name", design.get("selected_dataset_name", "")),
                    "cycle_index": cycle,
                    "label_key": TARGET_LABEL_KEY,
                    "target_event_next_cycle": target,
                    "target_event_cycle": first_event,
                    "prediction_horizon_cycles": 1,
                    "candidate_export_only": True,
                    "training_allowed_now": False,
                }
            )
            metadata_out.append(
                {
                    "row_id": rid,
                    "source_folder_name": cell_id,
                    "selected_dataset_name": row.get("selected_dataset_name", design.get("selected_dataset_name", "")),
                    "cycle_index": cycle,
                    "cell_group": TARGET_CELL_GROUP,
                    "label_key": TARGET_LABEL_KEY,
                    "first_event_cycle": first_event,
                    "last_cycle_index": design.get("last_cycle_index", ""),
                    "protocol_censored_terminal": design.get("protocol_censored_terminal", ""),
                    "pre_event_cycle_count": pre_event_count,
                    "post_event_cycle_count": design.get("post_event_cycle_count", ""),
                    "target_event_next_cycle": target,
                    "metadata_gate_status": cell_meta.get("metadata_gate_status", ""),
                    "termination_interpretation": cell_meta.get("termination_interpretation", ""),
                    "candidate_export_only": True,
                    "model_feature_allowed": False,
                    "training_allowed_now": False,
                }
            )

    known_cells = {row.get("source_folder_name", "") for row in design_rows}
    for cell_id, design in sorted(designs.items()):
        if cell_id not in known_cells:
            excluded_cells.append(excluded_cell_row(design, "missing_from_design_rows"))
    return features_out, targets_out, metadata_out, excluded_cells, model_columns


def per_cell_counts(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in targets:
        grouped.setdefault(str(row["source_folder_name"]), []).append(row)
    output = []
    for cell_id, rows in sorted(grouped.items()):
        positives = sum(int(row["target_event_next_cycle"]) for row in rows)
        output.append({"cell_id": cell_id, "rows": len(rows), "positive_targets": positives, "negative_targets": len(rows) - positives})
    return output


def write_manifest_and_report(
    output_root: Path,
    features: list[dict[str, Any]],
    targets: list[dict[str, Any]],
    metadata: list[dict[str, Any]],
    excluded_cells: list[dict[str, Any]],
    removed_columns: list[dict[str, Any]],
    model_columns: list[str],
) -> dict[str, Any]:
    target_counts = Counter(int(row["target_event_next_cycle"]) for row in targets)
    exported_cells = sorted({str(row["source_folder_name"]) for row in targets})
    excluded_cell_ids = sorted({str(row["source_folder_name"]) for row in excluded_cells if row.get("source_folder_name")})
    report = {
        "candidate_export_only": True,
        "not_model_performance": True,
        "model_training_allowed": False,
        "training_allowed_now": False,
        "rul_prediction_entered": False,
        "formal_training_dataset_generated": False,
        "target_cell_group": TARGET_CELL_GROUP,
        "target_label_key": TARGET_LABEL_KEY,
        "design": "t_minus_1_predicts_t",
        "exported_cell_count": len(exported_cells),
        "exported_cells": exported_cells,
        "excluded_cell_count": len(excluded_cell_ids),
        "excluded_cells": excluded_cell_ids,
        "feature_rows": len(features),
        "target_rows": len(targets),
        "metadata_rows": len(metadata),
        "positive_target_count": target_counts.get(1, 0),
        "negative_target_count": target_counts.get(0, 0),
        "model_feature_column_count": len(model_columns),
        "model_feature_columns": model_columns,
        "removed_or_blocked_column_count": len(removed_columns),
        "per_cell_counts": per_cell_counts(targets),
        "exploratory_baseline_planning_allowed": bool(features) and target_counts.get(1, 0) > 0,
        "model_training_allowed_after_export": False,
        "output_files": [
            "baseline_ready_lmb_licu_features.csv",
            "baseline_ready_lmb_licu_targets.csv",
            "baseline_ready_lmb_licu_metadata.csv",
            "baseline_ready_lmb_licu_manifest.json",
            "baseline_ready_lmb_licu_export_report.md",
            "removed_or_blocked_columns.csv",
            "excluded_cells.csv",
        ],
    }
    with (output_root / "baseline_ready_lmb_licu_manifest.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    lines = [
        "# LMB Li||Cu Baseline-Ready Candidate Export",
        "",
        "This is a candidate export only. It is not model performance, does not train a model, and does not enter RUL prediction.",
        "",
        "## Gate Decision",
        "",
        f"- `exploratory_baseline_planning_allowed = {report['exploratory_baseline_planning_allowed']}`",
        "- `model_training_allowed = False`",
        "- `candidate_export_only = True`",
        "- `not_model_performance = True`",
        "",
        "## Counts",
        "",
        f"- Exported cells: {report['exported_cell_count']} ({', '.join(exported_cells)})",
        f"- Excluded cells: {report['excluded_cell_count']} ({', '.join(excluded_cell_ids)})",
        f"- Feature rows: {len(features)}",
        f"- Positive targets: {report['positive_target_count']}",
        f"- Negative targets: {report['negative_target_count']}",
        "",
        "## Per Cell",
        "",
        "| cell | rows | positive targets | negative targets |",
        "| --- | ---: | ---: | ---: |",
    ]
    for row in report["per_cell_counts"]:
        lines.append(f"| {row['cell_id']} | {row['rows']} | {row['positive_targets']} | {row['negative_targets']} |")
    lines.extend(["", "## Removed Or Blocked Columns", ""])
    lines.extend(f"- `{row['column_name']}`: {row['block_reason']}" for row in removed_columns)
    lines.extend(
        [
            "",
            "## Notes",
            "",
            "- Features and targets are separated.",
            "- Metadata and censoring fields are retained only in metadata/target outputs, not as model features.",
            "- Event-cycle and post-event rows are excluded from feature export.",
            "- The positive target row is the cycle immediately before the first incomplete-capacity event.",
        ]
    )
    (output_root / "baseline_ready_lmb_licu_export_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def export_lmb_baseline_ready_dataset(
    label_design: Path,
    excluded_feature_columns: Path,
    licu_features: Path,
    metadata_gate: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    design_rows = read_csv(label_design)
    source_feature_rows = read_csv(licu_features)
    metadata_rows = read_csv(metadata_gate)
    features, targets, metadata, excluded_cells, model_columns = export_rows(design_rows, source_feature_rows, metadata_rows)
    removed_rows = build_removed_rows(source_columns(source_feature_rows))
    design_removed = read_csv(excluded_feature_columns)
    existing_removed = {row["column_name"] for row in removed_rows}
    for row in design_removed:
        column = row.get("feature_column", "")
        if column and column not in existing_removed:
            removed_rows.append(
                {
                    "column_name": column,
                    "present_in_source_features": row.get("present_in_licu_features", ""),
                    "block_reason": row.get("exclusion_reason", "blocked_by_label_design"),
                    "blocked_from_model_features": True,
                    "retained_elsewhere": False,
                }
            )

    feature_columns = [FEATURE_ID_COLUMN] + model_columns
    write_csv(output_root / "baseline_ready_lmb_licu_features.csv", features, feature_columns)
    write_csv(output_root / "baseline_ready_lmb_licu_targets.csv", targets, TARGET_COLUMNS)
    write_csv(output_root / "baseline_ready_lmb_licu_metadata.csv", metadata, METADATA_COLUMNS)
    write_csv(output_root / "removed_or_blocked_columns.csv", removed_rows, REMOVED_COLUMNS)
    write_csv(output_root / "excluded_cells.csv", excluded_cells, EXCLUDED_CELL_COLUMNS)
    return write_manifest_and_report(output_root, features, targets, metadata, excluded_cells, removed_rows, model_columns)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label-design", required=True)
    parser.add_argument("--excluded-feature-columns", required=True)
    parser.add_argument("--licu-features", required=True)
    parser.add_argument("--metadata-gate", required=True)
    parser.add_argument("--output-root", required=True)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    report = export_lmb_baseline_ready_dataset(
        label_design=Path(args.label_design),
        excluded_feature_columns=Path(args.excluded_feature_columns),
        licu_features=Path(args.licu_features),
        metadata_gate=Path(args.metadata_gate),
        output_root=Path(args.output_root),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
