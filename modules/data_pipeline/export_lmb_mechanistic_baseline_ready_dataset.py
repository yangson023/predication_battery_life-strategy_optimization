"""Export LMB Li||Cu mechanistic horizon candidate datasets.

This script packages already-audited past-only horizon features into candidate
baseline-ready exports. It does not train, refit, split randomly, enter the RUL
pipeline, or report model performance.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TARGET_CELL_GROUP = "Li||Cu"
TARGET_LABEL_KEY = "incomplete_capacity_event"
EARLY_EVENT_CELL_ID = "26-0428-009"
COVERAGE_MINIMUM = 0.80

FORBIDDEN_MODEL_COLUMNS = {
    "coulombic_efficiency_percent",
    "charge_capacity_mah",
    "discharge_capacity_mah",
    "incomplete_cycle_flag",
}
FORBIDDEN_MODEL_TOKENS = (
    "record_voltage_",
    "record_current_",
    "target_event",
    "future",
    "label",
)

TARGET_COLUMNS = [
    "row_id",
    "source_folder_name",
    "selected_dataset_name",
    "target_cycle",
    "horizon_k",
    "label_key",
    "target_event_at_cycle",
    "first_event_cycle",
    "candidate_export_only",
    "training_allowed_now",
]

METADATA_COLUMNS = [
    "row_id",
    "source_folder_name",
    "selected_dataset_name",
    "target_cycle",
    "horizon_k",
    "cell_group",
    "label_key",
    "first_event_cycle",
    "baseline_ready_export_candidate",
    "protocol_censored_terminal",
    "feature_window_start",
    "feature_window_end",
    "excluded_recent_window_start",
    "excluded_recent_window_end",
    "same_signal_source_feature_columns",
    "candidate_export_only",
    "model_feature_allowed",
    "training_allowed_now",
]

REMOVED_COLUMNS = [
    "horizon_k",
    "column_name",
    "block_reason",
    "present_in_source",
    "blocked_from_model_features",
    "retained_elsewhere",
]

EXCLUDED_COLUMNS = [
    "horizon_k",
    "source_folder_name",
    "selected_dataset_name",
    "target_cycle",
    "exclusion_scope",
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


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def parse_int(value: object) -> int:
    try:
        text = str(value).strip()
        if not text:
            return 0
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def parse_float(value: object) -> float:
    try:
        text = str(value).strip()
        if not text:
            return 0.0
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def design_by_cell(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("source_folder_name", ""): row for row in rows if row.get("source_folder_name")}


def schema_feature_rows(rows: list[dict[str, str]]) -> list[dict[str, str]]:
    return [row for row in rows if parse_bool(row.get("model_feature_candidate"))]


def coverage_by_horizon(rows: list[dict[str, str]]) -> dict[int, dict[str, float]]:
    out: dict[int, dict[str, float]] = defaultdict(dict)
    for row in rows:
        out[parse_int(row.get("horizon_k"))][row.get("feature_name", "")] = parse_float(row.get("coverage_fraction"))
    return dict(out)


def leakage_passed(rows: list[dict[str, str]]) -> bool:
    return bool(rows) and all(str(row.get("status", "")).strip().lower() == "pass" for row in rows)


def is_forbidden_model_column(column: str) -> bool:
    lower = column.lower()
    if column in FORBIDDEN_MODEL_COLUMNS:
        return True
    return any(token in lower for token in FORBIDDEN_MODEL_TOKENS)


def model_columns_for_horizon(
    schema_rows: list[dict[str, str]],
    coverage: dict[int, dict[str, float]],
    horizon: int,
    source_columns: set[str],
) -> tuple[list[str], list[str], list[dict[str, Any]]]:
    model_columns: list[str] = []
    same_signal_columns: list[str] = []
    blocked: list[dict[str, Any]] = []
    horizon_coverage = coverage.get(horizon, {})
    for row in schema_feature_rows(schema_rows):
        column = row.get("field_name", "")
        if not column:
            continue
        present = column in source_columns
        reason = ""
        if not present:
            reason = "missing_from_horizon_feature_table"
        elif is_forbidden_model_column(column):
            reason = "direct_or_semantic_leakage_column"
        elif horizon_coverage.get(column, 0.0) < COVERAGE_MINIMUM:
            reason = "coverage_below_80_percent"
        if reason:
            blocked.append(
                {
                    "horizon_k": horizon,
                    "column_name": column,
                    "block_reason": reason,
                    "present_in_source": present,
                    "blocked_from_model_features": True,
                    "retained_elsewhere": False,
                }
            )
            continue
        model_columns.append(column)
        if parse_bool(row.get("same_signal_source_risk")):
            same_signal_columns.append(column)
    return model_columns, same_signal_columns, blocked


def excluded_row(
    horizon: int,
    row: dict[str, str],
    scope: str,
    reason: str,
    target_cycle: int | str = "",
) -> dict[str, Any]:
    return {
        "horizon_k": horizon,
        "source_folder_name": row.get("source_folder_name", ""),
        "selected_dataset_name": row.get("selected_dataset_name", ""),
        "target_cycle": target_cycle if target_cycle != "" else row.get("target_cycle", ""),
        "exclusion_scope": scope,
        "exclusion_reason": reason,
    }


def rows_by_cell(rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get("source_folder_name", "")].append(row)
    return {cell: sorted(items, key=lambda item: parse_int(item.get("target_cycle"))) for cell, items in grouped.items() if cell}


def build_horizon_export(
    horizon: int,
    horizon_rows: list[dict[str, str]],
    schema_rows: list[dict[str, str]],
    coverage: dict[int, dict[str, float]],
    design: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], list[str], list[str]]:
    source_columns = set(horizon_rows[0].keys()) if horizon_rows else set()
    model_columns, same_signal_columns, blocked_columns = model_columns_for_horizon(schema_rows, coverage, horizon, source_columns)
    feature_rows: list[dict[str, Any]] = []
    target_rows: list[dict[str, Any]] = []
    metadata_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []

    for cell_id, rows in rows_by_cell(horizon_rows).items():
        design_row = design.get(cell_id, {})
        first_event = parse_int(design_row.get("first_event_cycle") or rows[0].get("first_event_cycle"))
        if cell_id == EARLY_EVENT_CELL_ID:
            excluded_rows.append(excluded_row(horizon, design_row or rows[0], "cell", "early_event_cell_audit_only"))
            continue
        if design_row.get("cell_group") != TARGET_CELL_GROUP or design_row.get("label_key") != TARGET_LABEL_KEY:
            excluded_rows.append(excluded_row(horizon, design_row or rows[0], "cell", "not_target_licu_incomplete_capacity_event"))
            continue
        if not parse_bool(design_row.get("baseline_ready_export_candidate")):
            excluded_rows.append(excluded_row(horizon, design_row or rows[0], "cell", "baseline_ready_export_candidate_false"))
            continue
        if first_event <= 0:
            excluded_rows.append(excluded_row(horizon, design_row or rows[0], "cell", "missing_first_event_cycle"))
            continue
        event_rows = [row for row in rows if parse_int(row.get("target_cycle")) == first_event]
        if not event_rows:
            excluded_rows.append(excluded_row(horizon, design_row or rows[0], "cell", "positive_event_row_missing_for_horizon", first_event))
            continue
        eligible_rows = [row for row in rows if parse_int(row.get("target_cycle")) <= first_event]
        for row in rows:
            target_cycle = parse_int(row.get("target_cycle"))
            if target_cycle > first_event:
                excluded_rows.append(excluded_row(horizon, row, "row", "post_event_target_cycle_excluded", target_cycle))
        for row in eligible_rows:
            target_cycle = parse_int(row.get("target_cycle"))
            row_id = row.get("row_id", f"{cell_id}__target_cycle_{target_cycle}__h{horizon}")
            target_value = 1 if target_cycle == first_event else 0
            feature_payload = {"row_id": row_id}
            for column in model_columns:
                feature_payload[column] = row.get(column, "")
            feature_rows.append(feature_payload)
            target_rows.append(
                {
                    "row_id": row_id,
                    "source_folder_name": cell_id,
                    "selected_dataset_name": row.get("selected_dataset_name", design_row.get("selected_dataset_name", "")),
                    "target_cycle": target_cycle,
                    "horizon_k": horizon,
                    "label_key": TARGET_LABEL_KEY,
                    "target_event_at_cycle": target_value,
                    "first_event_cycle": first_event,
                    "candidate_export_only": True,
                    "training_allowed_now": False,
                }
            )
            metadata_rows.append(
                {
                    "row_id": row_id,
                    "source_folder_name": cell_id,
                    "selected_dataset_name": row.get("selected_dataset_name", design_row.get("selected_dataset_name", "")),
                    "target_cycle": target_cycle,
                    "horizon_k": horizon,
                    "cell_group": TARGET_CELL_GROUP,
                    "label_key": TARGET_LABEL_KEY,
                    "first_event_cycle": first_event,
                    "baseline_ready_export_candidate": True,
                    "protocol_censored_terminal": design_row.get("protocol_censored_terminal", row.get("protocol_censored_terminal", "")),
                    "feature_window_start": row.get("feature_window_start", ""),
                    "feature_window_end": row.get("feature_window_end", ""),
                    "excluded_recent_window_start": row.get("excluded_recent_window_start", ""),
                    "excluded_recent_window_end": row.get("excluded_recent_window_end", ""),
                    "same_signal_source_feature_columns": ";".join(same_signal_columns),
                    "candidate_export_only": True,
                    "model_feature_allowed": False,
                    "training_allowed_now": False,
                }
            )

    return feature_rows, target_rows, metadata_rows, blocked_columns, excluded_rows, model_columns, same_signal_columns


def per_cell_counts(targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in targets:
        grouped[str(row["source_folder_name"])].append(row)
    out = []
    for cell_id, rows in sorted(grouped.items()):
        positives = sum(int(row["target_event_at_cycle"]) for row in rows)
        out.append(
            {
                "cell_id": cell_id,
                "rows": len(rows),
                "positive_targets": positives,
                "negative_targets": len(rows) - positives,
            }
        )
    return out


def horizon_report(features: list[dict[str, Any]], targets: list[dict[str, Any]], model_columns: list[str]) -> dict[str, Any]:
    counts = Counter(int(row["target_event_at_cycle"]) for row in targets)
    return {
        "exported_cell_count": len({row["source_folder_name"] for row in targets}),
        "feature_rows": len(features),
        "target_rows": len(targets),
        "positive_targets": counts.get(1, 0),
        "negative_targets": counts.get(0, 0),
        "model_feature_column_count": len(model_columns),
        "model_feature_columns": model_columns,
        "per_cell_counts": per_cell_counts(targets),
    }


def write_manifest_and_report(
    output_root: Path,
    leakage_ok: bool,
    horizon_payloads: dict[int, dict[str, Any]],
    removed_rows: list[dict[str, Any]],
    excluded_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    report = {
        "candidate_export_only": True,
        "not_model_performance": True,
        "model_training_allowed": False,
        "training_allowed_now": False,
        "rul_prediction_entered": False,
        "random_row_split_used": False,
        "formal_performance_metrics_computed": False,
        "target_cell_group": TARGET_CELL_GROUP,
        "target_label_key": TARGET_LABEL_KEY,
        "leakage_check_passed": leakage_ok,
        "same_signal_source_risk_feature_columns": {
            str(horizon): payload["same_signal_columns"] for horizon, payload in sorted(horizon_payloads.items())
        },
        "horizons": {
            str(horizon): horizon_report(payload["features"], payload["targets"], payload["model_columns"])
            for horizon, payload in sorted(horizon_payloads.items())
        },
        "excluded_row_or_cell_count": len(excluded_rows),
        "removed_or_blocked_column_count": len(removed_rows),
        "tiny_mechanistic_baseline_planning_allowed": leakage_ok
        and all(payload["targets"] for payload in horizon_payloads.values())
        and all(sum(int(row["target_event_at_cycle"]) for row in payload["targets"]) > 0 for payload in horizon_payloads.values()),
        "model_training_allowed_after_export": False,
        "output_files": [
            "horizon3_mechanistic_features.csv",
            "horizon3_mechanistic_targets.csv",
            "horizon3_mechanistic_metadata.csv",
            "horizon5_mechanistic_features.csv",
            "horizon5_mechanistic_targets.csv",
            "horizon5_mechanistic_metadata.csv",
            "mechanistic_removed_or_blocked_columns.csv",
            "mechanistic_excluded_rows_or_cells.csv",
            "mechanistic_baseline_ready_manifest.json",
            "mechanistic_baseline_ready_export_report.md",
        ],
    }
    (output_root / "mechanistic_baseline_ready_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# LMB Mechanistic Baseline-Ready Candidate Export",
        "",
        "This is a candidate data package only. It does not train a model, does not refit a model, and does not claim model performance.",
        "",
        "## Gate",
        "",
        f"- `leakage_check_passed = {leakage_ok}`",
        f"- `tiny_mechanistic_baseline_planning_allowed = {report['tiny_mechanistic_baseline_planning_allowed']}`",
        "- `model_training_allowed = False`",
        "- `candidate_export_only = True`",
        "",
        "## Horizon Counts",
        "",
        "| horizon | cells | feature rows | positive targets | negative targets |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for horizon, payload in sorted(horizon_payloads.items()):
        summary = report["horizons"][str(horizon)]
        lines.append(
            f"| {horizon} | {summary['exported_cell_count']} | {summary['feature_rows']} | {summary['positive_targets']} | {summary['negative_targets']} |"
        )
    lines.extend(["", "## Per Cell", ""])
    for horizon, payload in sorted(horizon_payloads.items()):
        lines.extend([f"### Horizon {horizon}", "", "| cell | rows | positive targets | negative targets |", "| --- | ---: | ---: | ---: |"])
        for row in report["horizons"][str(horizon)]["per_cell_counts"]:
            lines.append(f"| {row['cell_id']} | {row['rows']} | {row['positive_targets']} | {row['negative_targets']} |")
        lines.append("")
    lines.extend(
        [
            "## Feature Risk",
            "",
            "- CE/capacity trend columns are retained only as past-only horizon features and are listed as same-signal-source risk in the manifest.",
            "- Direct CE, direct capacity, incomplete-cycle flags, target/event/future columns, and record-sample columns are blocked from model features.",
            "- Metadata and censoring fields are separated from feature tables.",
            "",
            "## Decision",
            "",
            "The export may be used for the next planning step only. Model training remains prohibited until a separate user-approved tiny baseline run and gate review.",
        ]
    )
    (output_root / "mechanistic_baseline_ready_export_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def export_lmb_mechanistic_baseline_ready_dataset(
    horizon3_features: Path,
    horizon5_features: Path,
    mechanistic_feature_schema: Path,
    horizon_leakage_check: Path,
    horizon_feature_coverage_summary: Path,
    label_design: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    horizon_inputs = {
        3: read_csv(horizon3_features),
        5: read_csv(horizon5_features),
    }
    schema_rows = read_csv(mechanistic_feature_schema)
    coverage = coverage_by_horizon(read_csv(horizon_feature_coverage_summary))
    design = design_by_cell(read_csv(label_design))
    leakage_ok = leakage_passed(read_csv(horizon_leakage_check))

    horizon_payloads: dict[int, dict[str, Any]] = {}
    removed_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    for horizon, rows in horizon_inputs.items():
        features, targets, metadata, blocked, excluded, model_columns, same_signal_columns = build_horizon_export(
            horizon=horizon,
            horizon_rows=rows,
            schema_rows=schema_rows,
            coverage=coverage,
            design=design,
        )
        horizon_payloads[horizon] = {
            "features": features,
            "targets": targets,
            "metadata": metadata,
            "model_columns": model_columns,
            "same_signal_columns": same_signal_columns,
        }
        removed_rows.extend(blocked)
        excluded_rows.extend(excluded)
        write_csv(output_root / f"horizon{horizon}_mechanistic_features.csv", features, ["row_id"] + model_columns)
        write_csv(output_root / f"horizon{horizon}_mechanistic_targets.csv", targets, TARGET_COLUMNS)
        write_csv(output_root / f"horizon{horizon}_mechanistic_metadata.csv", metadata, METADATA_COLUMNS)

    write_csv(output_root / "mechanistic_removed_or_blocked_columns.csv", removed_rows, REMOVED_COLUMNS)
    write_csv(output_root / "mechanistic_excluded_rows_or_cells.csv", excluded_rows, EXCLUDED_COLUMNS)
    return write_manifest_and_report(output_root, leakage_ok, horizon_payloads, removed_rows, excluded_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--horizon3-features", type=Path, required=True)
    parser.add_argument("--horizon5-features", type=Path, required=True)
    parser.add_argument("--mechanistic-feature-schema", type=Path, required=True)
    parser.add_argument("--horizon-leakage-check", type=Path, required=True)
    parser.add_argument("--horizon-feature-coverage-summary", type=Path, required=True)
    parser.add_argument("--label-design", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = export_lmb_mechanistic_baseline_ready_dataset(
        horizon3_features=args.horizon3_features,
        horizon5_features=args.horizon5_features,
        mechanistic_feature_schema=args.mechanistic_feature_schema,
        horizon_leakage_check=args.horizon_leakage_check,
        horizon_feature_coverage_summary=args.horizon_feature_coverage_summary,
        label_design=args.label_design,
        output_root=args.output_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
