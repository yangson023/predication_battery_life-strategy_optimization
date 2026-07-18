"""Export guarded external cycle labels as an exploratory baseline dataset."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DEFAULT_AUDIT_ROOT = Path("outputs/label_audit/external_trainable_labels")
DEFAULT_FEATURE_ROOT = Path("data/features/external_battery_datasets_candidates_high_obs")
DEFAULT_OUTPUT_ROOT = DEFAULT_AUDIT_ROOT / "baseline_ready_high_minobs20"
DEFAULT_DATASET_SPLIT = "high_minobs20"
DEFAULT_LABEL_KEYS = ["capacity_eol_75", "capacity_eol_80"]

LABEL_COLUMNS = [
    "dataset_split_name",
    "source_table",
    "cell_id",
    "batch_id",
    "part_id",
    "label_key",
    "protocol_regime_index",
    "observations",
    "eol_observed",
    "eol_observation_index",
    "eol_boundary_quality",
    "eol_distance_from_regime_start",
    "eol_distance_to_regime_end",
    "trainable_label_quality",
]

MODEL_METADATA_COLUMNS = [
    "dataset_split_name",
    "cell_id",
    "batch_id",
    "part_id",
    "label_key",
    "cycle_index",
]

TARGET_COLUMNS = [
    "dataset_split_name",
    "cell_id",
    "batch_id",
    "part_id",
    "label_key",
    "cycle_index",
    "target_threshold_crossed",
    "cycles_to_eol_at_row",
]

EXACT_LEAKAGE_COLUMNS = {
    "sample_rows",
    "capacity",
    "capacity_delta_ah",
    "capacity_retention",
    "SOH",
    "RUL",
    "eol_observation_index",
    "eol_cycle_index",
    "final_capacity",
}

IDENTITY_COLUMNS = {
    "dataset_id",
    "dataset_family",
    "data_category",
    "measurement_type",
    "chemistry",
    "cell_id",
    "batch_id",
    "part_id",
    "source_archive_name",
    "archive_member_path",
}


def parse_bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def normalize_protocol(value: object) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return ""
    number = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(number):
        return str(value).strip()
    if float(number).is_integer():
        return str(int(number))
    return str(float(number))


def is_trainable_quality(value: object) -> bool:
    return str(value).startswith("trainable_")


def leakage_reason(column: str) -> str:
    if column in EXACT_LEAKAGE_COLUMNS:
        if column == "sample_rows":
            return "acquisition_artifact_column"
        return "explicit_leakage_or_target_column"
    lower = column.lower()
    if lower.startswith("protocol_"):
        return "protocol_helper_column"
    if lower.startswith("capacity_ah_"):
        return "direct_capacity_measurement_column"
    return ""


def split_feature_columns(columns: list[str]) -> tuple[list[str], list[dict[str, str]]]:
    feature_columns = []
    removed_columns = []
    for column in columns:
        if column in IDENTITY_COLUMNS or column in {"cycle_index", "protocol_regime_index"}:
            continue
        reason = leakage_reason(column)
        if reason:
            removed_columns.append({"column": column, "reason": reason})
            continue
        feature_columns.append(column)
    return feature_columns, removed_columns


def read_audit_tables(audit_root: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    trainable_path = audit_root / "trainable_label_summary.csv"
    excluded_path = audit_root / "excluded_label_summary.csv"
    if not trainable_path.exists():
        raise FileNotFoundError(f"Missing trainable label summary: {trainable_path}")
    if not excluded_path.exists():
        raise FileNotFoundError(f"Missing excluded label summary: {excluded_path}")
    return pd.read_csv(trainable_path), pd.read_csv(excluded_path)


def read_cycle_features(feature_root: Path) -> pd.DataFrame:
    feature_path = feature_root / "cycle_features.csv"
    if not feature_path.exists():
        raise FileNotFoundError(f"Missing cycle features: {feature_path}")
    return pd.read_csv(feature_path)


def rejection_reason(row: pd.Series, dataset_split: str, allowed_label_keys: set[str]) -> str:
    reasons = []
    if row.get("dataset_split_name") != dataset_split:
        reasons.append("non_main_dataset_split")
    if row.get("source_table") != "cycle_features.csv":
        reasons.append("non_cycle_source")
    if row.get("label_key") not in allowed_label_keys:
        reasons.append("label_key_not_in_main_thresholds")
    if not is_trainable_quality(row.get("trainable_label_quality", "")):
        reasons.append("not_trainable_quality")
    if str(row.get("eol_boundary_quality", "")) == "unreliable_boundary_crossing":
        reasons.append("boundary_crossing")
    if not bool(row.get("eol_observed", False)):
        reasons.append("censored_or_unobserved")
    if normalize_protocol(row.get("protocol_regime_index")) != "2":
        reasons.append("non_regime_2")
    return ";".join(reasons) if reasons else ""


def select_baseline_labels(
    trainable: pd.DataFrame,
    dataset_split: str,
    allowed_label_keys: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    labels = trainable.copy()
    if "eol_observed" in labels.columns:
        labels["eol_observed"] = parse_bool_series(labels["eol_observed"])
    else:
        labels["eol_observed"] = False
    labels["protocol_regime_normalized"] = labels["protocol_regime_index"].map(normalize_protocol)

    allowed = set(allowed_label_keys)
    labels["main_export_rejection_reason"] = labels.apply(
        lambda row: rejection_reason(row, dataset_split, allowed),
        axis=1,
    )
    selected = labels[labels["main_export_rejection_reason"].eq("")].copy()
    rejected = labels[~labels["main_export_rejection_reason"].eq("")].copy()
    return selected, rejected


def build_feature_rows(
    selected_labels: pd.DataFrame,
    cycle_features: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feature_rows = []
    target_rows = []
    alignment_rows = []
    features = cycle_features.copy()
    features["protocol_regime_normalized"] = features["protocol_regime_index"].map(normalize_protocol)
    features["cycle_index_numeric"] = pd.to_numeric(features["cycle_index"], errors="coerce")

    for label in selected_labels.to_dict("records"):
        eol_cycle = pd.to_numeric(pd.Series([label["eol_observation_index"]]), errors="coerce").iloc[0]
        label_mask = (
            features["cell_id"].eq(label["cell_id"])
            & features["batch_id"].eq(label["batch_id"])
            & features["part_id"].eq(label["part_id"])
            & features["protocol_regime_normalized"].eq(normalize_protocol(label["protocol_regime_index"]))
        )
        matched = features[label_mask].copy()
        rows_in_regime = int(len(matched))
        duplicate_keys = int(matched.duplicated(["cell_id", "cycle_index"]).sum())
        if not pd.isna(eol_cycle):
            matched = matched[matched["cycle_index_numeric"].le(eol_cycle)].copy()
        rows_before_or_at_eol = int(len(matched))
        positive_rows = 0
        if not matched.empty:
            matched["dataset_split_name"] = label["dataset_split_name"]
            matched["label_key"] = label["label_key"]
            matched["target_threshold_crossed"] = matched["cycle_index_numeric"].eq(eol_cycle)
            matched["cycles_to_eol_at_row"] = eol_cycle - matched["cycle_index_numeric"]
            positive_rows = int(matched["target_threshold_crossed"].sum())
            feature_rows.append(matched[MODEL_METADATA_COLUMNS + feature_columns])
            target_rows.append(matched[TARGET_COLUMNS])
        alignment_rows.append(
            {
                "dataset_split_name": label["dataset_split_name"],
                "cell_id": label["cell_id"],
                "batch_id": label["batch_id"],
                "part_id": label["part_id"],
                "label_key": label["label_key"],
                "protocol_regime_index": label["protocol_regime_index"],
                "eol_observation_index": label["eol_observation_index"],
                "rows_in_protocol_regime": rows_in_regime,
                "rows_before_or_at_eol": rows_before_or_at_eol,
                "positive_target_rows": positive_rows,
                "duplicate_feature_keys": duplicate_keys,
                "alignment_quality": (
                    "pass"
                    if rows_before_or_at_eol > 0 and positive_rows == 1 and duplicate_keys == 0
                    else "fail"
                ),
            }
        )

    if feature_rows:
        feature_output = pd.concat(feature_rows, ignore_index=True)
    else:
        feature_output = pd.DataFrame(columns=MODEL_METADATA_COLUMNS + feature_columns)
    if target_rows:
        target_output = pd.concat(target_rows, ignore_index=True)
    else:
        target_output = pd.DataFrame(columns=TARGET_COLUMNS)
    return feature_output, target_output, pd.DataFrame(alignment_rows)


def value_counts_records(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, object]]:
    if frame.empty:
        return []
    return frame.groupby(columns, dropna=False).size().reset_index(name="count").to_dict("records")


def build_label_counts_per_cell(labels: pd.DataFrame) -> pd.DataFrame:
    if labels.empty:
        return pd.DataFrame(columns=["cell_id", "label_key", "eol_observed", "count"])
    return labels.groupby(["cell_id", "label_key", "eol_observed"], dropna=False).size().reset_index(name="count")


def build_feature_statistics(feature_rows: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    numeric_columns = [
        column for column in feature_columns if column in feature_rows.columns and pd.api.types.is_numeric_dtype(feature_rows[column])
    ]
    rows = []
    for (batch_id, part_id), group in feature_rows.groupby(["batch_id", "part_id"], dropna=False):
        for column in numeric_columns:
            rows.append(
                {
                    "batch_id": batch_id,
                    "part_id": part_id,
                    "feature": column,
                    "count": int(group[column].count()),
                    "mean": group[column].mean(),
                    "std": group[column].std(),
                    "min": group[column].min(),
                    "max": group[column].max(),
                }
            )
    return pd.DataFrame(rows)


def markdown_table(rows: list[dict[str, object]], columns: list[str]) -> str:
    if not rows:
        return "_None_\n"
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    return "\n".join(lines) + "\n"


def build_report_markdown(report: dict[str, object]) -> str:
    return "\n".join(
        [
            "# Baseline-Ready External Dataset Export",
            "",
            "This is a guarded data export for exploratory baseline design. It is not a model result.",
            "",
            f"- Exported labels: {report['exported_label_count']}",
            f"- Exported feature rows: {report['exported_feature_row_count']}",
            f"- Cells: {report['cell_count']}",
            f"- Alignment status: {report['alignment_status']}",
            "",
            "## Labels By Key",
            markdown_table(report["labels_by_key"], ["label_key", "count"]),
            "## Labels By Cell",
            markdown_table(report["labels_by_cell"], ["cell_id", "count"]),
            "## Labels By Batch/Part",
            markdown_table(report["labels_by_batch_part"], ["batch_id", "part_id", "count"]),
            "## Rejected Trainable Audit Rows",
            markdown_table(
                report["rejected_trainable_by_reason"],
                ["main_export_rejection_reason", "count"],
            ),
            "## Audit Exclusions",
            markdown_table(
                report["audit_excluded_by_quality"],
                ["source_table", "trainable_label_quality", "count"],
            ),
        ]
    )


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def write_json(content: object, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def export_baseline_ready_dataset(
    audit_root: Path,
    feature_root: Path,
    output_root: Path,
    dataset_split: str = DEFAULT_DATASET_SPLIT,
    allowed_label_keys: list[str] | None = None,
) -> dict[str, object]:
    allowed = allowed_label_keys or DEFAULT_LABEL_KEYS
    trainable, excluded = read_audit_tables(audit_root)
    cycle_features = read_cycle_features(feature_root)
    selected_labels, rejected_trainable = select_baseline_labels(trainable, dataset_split, allowed)
    feature_columns, removed_columns = split_feature_columns(cycle_features.columns.tolist())
    feature_rows, target_rows, alignment = build_feature_rows(
        selected_labels, cycle_features, feature_columns
    )

    missing_label_columns = [column for column in LABEL_COLUMNS if column not in selected_labels.columns]
    for column in missing_label_columns:
        selected_labels[column] = ""
    baseline_labels = selected_labels[LABEL_COLUMNS].copy()

    label_counts = build_label_counts_per_cell(baseline_labels)
    feature_stats = build_feature_statistics(feature_rows, feature_columns)
    output_root.mkdir(parents=True, exist_ok=True)
    write_csv(baseline_labels, output_root / "baseline_ready_labels.csv")
    write_csv(feature_rows, output_root / "baseline_ready_feature_rows.csv")
    write_csv(target_rows, output_root / "baseline_ready_targets.csv")
    write_csv(rejected_trainable, output_root / "rejected_trainable_labels.csv")
    write_csv(label_counts, output_root / "label_counts_per_cell.csv")
    write_csv(feature_stats, output_root / "feature_statistics_per_batch.csv")
    write_csv(alignment, output_root / "alignment_check.csv")
    write_csv(pd.DataFrame(removed_columns), output_root / "removed_feature_columns.csv")
    (output_root / "features_columns.txt").write_text("\n".join(feature_columns) + "\n", encoding="utf-8")

    audit_excluded_by_quality = value_counts_records(
        excluded, ["source_table", "trainable_label_quality"]
    )
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "audit_root": str(audit_root),
        "feature_root": str(feature_root),
        "output_root": str(output_root),
        "dataset_split": dataset_split,
        "allowed_label_keys": allowed,
        "filter_rules": {
            "source_table": "cycle_features.csv",
            "eol_observed": True,
            "protocol_regime_index": "2",
            "eol_boundary_quality": "not unreliable_boundary_crossing",
            "trainable_label_quality": "starts with trainable_",
        },
        "exported_label_count": int(len(baseline_labels)),
        "exported_feature_row_count": int(len(feature_rows)),
        "exported_target_row_count": int(len(target_rows)),
        "cell_count": int(baseline_labels["cell_id"].nunique()) if not baseline_labels.empty else 0,
        "labels_by_key": value_counts_records(baseline_labels, ["label_key"]),
        "labels_by_cell": value_counts_records(baseline_labels, ["cell_id"]),
        "labels_by_batch_part": value_counts_records(baseline_labels, ["batch_id", "part_id"]),
        "feature_rows_by_cell_label": value_counts_records(feature_rows, ["cell_id", "label_key"]),
        "rejected_trainable_by_reason": value_counts_records(
            rejected_trainable, ["main_export_rejection_reason"]
        ),
        "audit_excluded_by_quality": audit_excluded_by_quality,
        "removed_feature_columns": removed_columns,
        "feature_column_count": len(feature_columns),
        "alignment_status": (
            "pass"
            if not alignment.empty and alignment["alignment_quality"].eq("pass").all()
            else "fail"
        ),
        "is_model_result": False,
    }
    write_json(report, output_root / "baseline_ready_dataset_report.json")
    write_json(report, output_root / "dataset_manifest.json")
    (output_root / "baseline_ready_dataset_report.md").write_text(
        build_report_markdown(report),
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export guarded high-observation cycle labels for exploratory baseline input."
    )
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    parser.add_argument("--feature-root", type=Path, default=DEFAULT_FEATURE_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--dataset-split", default=DEFAULT_DATASET_SPLIT)
    parser.add_argument(
        "--label-key",
        action="append",
        dest="label_keys",
        default=[],
        help="Allowed label key. Defaults to capacity_eol_75 and capacity_eol_80.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = export_baseline_ready_dataset(
        audit_root=args.audit_root,
        feature_root=args.feature_root,
        output_root=args.output_root,
        dataset_split=args.dataset_split,
        allowed_label_keys=args.label_keys or DEFAULT_LABEL_KEYS,
    )
    print(
        "baseline-ready export complete: "
        f"labels={report['exported_label_count']}, "
        f"feature_rows={report['exported_feature_row_count']}, "
        f"cells={report['cell_count']}, "
        f"alignment={report['alignment_status']}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
