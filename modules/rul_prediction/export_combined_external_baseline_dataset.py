"""Export a controlled combined external dataset for exploratory LOCO baselines."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd


DEFAULT_AUDIT_ROOT = Path("outputs/label_audit/external_trainable_labels")
DEFAULT_OUTPUT_ROOT = Path("models/rul_prediction/external_loco_binary_baseline/combined_main_input")
SOURCE_FEATURE_ROOTS = {
    "six_minobs20": Path("data/features/external_battery_datasets"),
    "high_minobs20": Path("data/features/external_battery_datasets_candidates_high_obs"),
}
ALLOWED_LABEL_KEYS = ["capacity_eol_75", "capacity_eol_80"]
ALLOWED_SOURCE_SPLITS = ["six_minobs20", "high_minobs20"]
COMBINED_DATASET_SPLIT = "combined_main"
JOIN_KEYS = ["dataset_split_name", "cell_id", "batch_id", "part_id", "label_key", "cycle_index"]
LABEL_COLUMNS = [
    "dataset_split_name",
    "source_dataset_split_name",
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
FEATURE_METADATA_COLUMNS = [
    "dataset_split_name",
    "source_dataset_split_name",
    "cell_id",
    "batch_id",
    "part_id",
    "label_key",
    "cycle_index",
]
TARGET_COLUMNS = [
    *FEATURE_METADATA_COLUMNS,
    "target_threshold_crossed",
    "cycles_to_eol_at_row",
]
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
EXACT_REMOVED_COLUMNS = {
    "sample_rows": "acquisition_artifact_column",
    "cycle_index_numeric": "temporal_helper_column",
    "capacity_delta_ah": "explicit_leakage_or_target_column",
    "capacity": "explicit_leakage_or_target_column",
    "capacity_retention": "explicit_leakage_or_target_column",
    "SOH": "explicit_leakage_or_target_column",
    "RUL": "explicit_leakage_or_target_column",
    "eol_observation_index": "explicit_leakage_or_target_column",
    "eol_cycle_index": "explicit_leakage_or_target_column",
    "final_capacity": "explicit_leakage_or_target_column",
}


def normalize_protocol(value: object) -> str:
    if pd.isna(value) or str(value).strip() == "":
        return ""
    numeric = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(numeric):
        return str(value).strip()
    return str(int(numeric)) if float(numeric).is_integer() else str(float(numeric))


def parse_bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def removal_reason(column: str) -> str:
    if column in EXACT_REMOVED_COLUMNS:
        return EXACT_REMOVED_COLUMNS[column]
    if column.lower().startswith("capacity_ah_"):
        return "direct_capacity_measurement_column"
    if column.lower().startswith("protocol_"):
        return "protocol_helper_column"
    return ""


def split_feature_columns(columns: list[str]) -> tuple[list[str], pd.DataFrame]:
    feature_columns: list[str] = []
    removed = []
    for column in columns:
        if column in IDENTITY_COLUMNS or column in {"cycle_index", "protocol_regime_index"}:
            continue
        reason = removal_reason(column)
        if reason:
            removed.append({"column": column, "reason": reason})
        else:
            feature_columns.append(column)
    return feature_columns, pd.DataFrame(removed)


def load_trainable_labels(audit_root: Path) -> pd.DataFrame:
    path = audit_root / "trainable_label_summary.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing trainable label summary: {path}")
    labels = pd.read_csv(path)
    labels["eol_observed"] = parse_bool_series(labels["eol_observed"])
    labels["protocol_regime_normalized"] = labels["protocol_regime_index"].map(normalize_protocol)
    selected = labels[
        labels["dataset_split_name"].isin(ALLOWED_SOURCE_SPLITS)
        & labels["source_table"].eq("cycle_features.csv")
        & labels["label_key"].isin(ALLOWED_LABEL_KEYS)
        & labels["eol_observed"].eq(True)
        & labels["eol_boundary_quality"].eq("away_from_protocol_boundary")
        & labels["protocol_regime_normalized"].eq("2")
        & labels["trainable_label_quality"].eq("trainable_observed_protocol_consistent")
    ].copy()
    selected["source_dataset_split_name"] = selected["dataset_split_name"]
    selected["dataset_split_name"] = COMBINED_DATASET_SPLIT
    if selected.empty:
        raise ValueError("No labels matched the combined_main selection rules.")
    return selected


def load_source_features(source_feature_roots: dict[str, Path]) -> dict[str, pd.DataFrame]:
    tables = {}
    for split_name, root in source_feature_roots.items():
        path = root / "cycle_features.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing cycle features for {split_name}: {path}")
        frame = pd.read_csv(path)
        frame["protocol_regime_normalized"] = frame["protocol_regime_index"].map(normalize_protocol)
        frame["cycle_index_numeric"] = pd.to_numeric(frame["cycle_index"], errors="coerce")
        tables[split_name] = frame
    return tables


def build_feature_and_target_rows(
    labels: pd.DataFrame,
    source_features: dict[str, pd.DataFrame],
    feature_columns: list[str],
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    feature_outputs = []
    target_outputs = []
    alignment_rows = []

    for label in labels.to_dict("records"):
        source_split = label["source_dataset_split_name"]
        features = source_features[source_split]
        eol_cycle = pd.to_numeric(pd.Series([label["eol_observation_index"]]), errors="coerce").iloc[0]
        label_mask = (
            features["cell_id"].eq(label["cell_id"])
            & features["batch_id"].eq(label["batch_id"])
            & features["part_id"].eq(label["part_id"])
            & features["protocol_regime_normalized"].eq(normalize_protocol(label["protocol_regime_index"]))
        )
        matched = features.loc[label_mask].copy()
        rows_in_regime = int(len(matched))
        if not pd.isna(eol_cycle):
            matched = matched.loc[matched["cycle_index_numeric"].le(eol_cycle)].copy()
        rows_before_or_at_eol = int(len(matched))
        duplicate_keys = int(matched.duplicated(["cell_id", "cycle_index"]).sum())

        matched["dataset_split_name"] = COMBINED_DATASET_SPLIT
        matched["source_dataset_split_name"] = source_split
        matched["label_key"] = label["label_key"]
        matched["target_threshold_crossed"] = matched["cycle_index_numeric"].eq(eol_cycle)
        matched["cycles_to_eol_at_row"] = eol_cycle - matched["cycle_index_numeric"]
        positive_rows = int(matched["target_threshold_crossed"].sum())

        feature_outputs.append(matched[FEATURE_METADATA_COLUMNS + feature_columns])
        target_outputs.append(matched[TARGET_COLUMNS])
        alignment_rows.append(
            {
                "dataset_split_name": COMBINED_DATASET_SPLIT,
                "source_dataset_split_name": source_split,
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

    return (
        pd.concat(feature_outputs, ignore_index=True),
        pd.concat(target_outputs, ignore_index=True),
        pd.DataFrame(alignment_rows),
    )


def value_counts_records(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, object]]:
    if frame.empty:
        return []
    return frame.groupby(columns, dropna=False).size().reset_index(name="count").to_dict("records")


def feature_statistics_by_source_run(feature_rows: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    rows = []
    for (source_split, batch_id, part_id), group in feature_rows.groupby(
        ["source_dataset_split_name", "batch_id", "part_id"], dropna=False
    ):
        for feature in feature_columns:
            values = pd.to_numeric(group[feature], errors="coerce")
            rows.append(
                {
                    "source_dataset_split_name": source_split,
                    "batch_id": batch_id,
                    "part_id": part_id,
                    "feature": feature,
                    "count": int(values.count()),
                    "mean": values.mean(),
                    "std": values.std(),
                    "min": values.min(),
                    "max": values.max(),
                }
            )
    return pd.DataFrame(rows)


def build_report(
    labels: pd.DataFrame,
    feature_rows: pd.DataFrame,
    targets: pd.DataFrame,
    alignment: pd.DataFrame,
    feature_columns: list[str],
) -> dict[str, object]:
    return {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "dataset_split": COMBINED_DATASET_SPLIT,
        "source_pipeline_runs": ALLOWED_SOURCE_SPLITS,
        "is_formal_model_performance": False,
        "trained_model": False,
        "selection_rules": {
            "source_table": "cycle_features.csv",
            "protocol_regime_index": "2",
            "eol_observed": True,
            "eol_boundary_quality": "away_from_protocol_boundary",
            "label_keys": ALLOWED_LABEL_KEYS,
        },
        "label_count": int(len(labels)),
        "feature_row_count": int(len(feature_rows)),
        "target_row_count": int(len(targets)),
        "cell_count": int(labels["cell_id"].nunique()),
        "label_counts_by_key": value_counts_records(labels, ["label_key"]),
        "label_counts_by_source_run": value_counts_records(
            labels, ["source_dataset_split_name", "label_key"]
        ),
        "label_counts_by_cell": value_counts_records(labels, ["cell_id", "label_key"]),
        "feature_row_counts_by_source_run": value_counts_records(
            feature_rows, ["source_dataset_split_name", "label_key"]
        ),
        "alignment_status": (
            "pass"
            if not alignment.empty and alignment["alignment_quality"].eq("pass").all()
            else "fail"
        ),
        "feature_column_count": len(feature_columns),
        "interpretation_limits": [
            "combined from six_minobs20 and high_minobs20 pipeline runs",
            "potential inter-run confound is not fully controlled",
            "exploratory baseline input only",
        ],
    }


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


def build_markdown_report(report: dict[str, object]) -> str:
    return "\n".join(
        [
            "# Combined External Baseline Input",
            "",
            "This export is an exploratory baseline input. It is not a model result.",
            "",
            f"- Labels: {report['label_count']}",
            f"- Cells: {report['cell_count']}",
            f"- Feature rows: {report['feature_row_count']}",
            f"- Alignment: {report['alignment_status']}",
            "",
            "## Labels By Key",
            markdown_table(report["label_counts_by_key"], ["label_key", "count"]),
            "## Labels By Source Run",
            markdown_table(
                report["label_counts_by_source_run"],
                ["source_dataset_split_name", "label_key", "count"],
            ),
            "## Labels By Cell",
            markdown_table(report["label_counts_by_cell"], ["cell_id", "label_key", "count"]),
            "## Interpretation Limits",
            "- Combined from six_minobs20 and high_minobs20.",
            "- Potential inter-run confound is not fully controlled.",
            "- Use only as an exploratory diagnostic input.",
        ]
    )


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def export_combined_external_baseline_dataset(
    audit_root: Path = DEFAULT_AUDIT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    source_feature_roots: dict[str, Path] | None = None,
) -> dict[str, object]:
    source_feature_roots = source_feature_roots or SOURCE_FEATURE_ROOTS
    labels = load_trainable_labels(audit_root)
    source_features = load_source_features(source_feature_roots)
    reference_columns = source_features["high_minobs20"].columns.tolist()
    feature_columns, removed_columns = split_feature_columns(reference_columns)
    feature_rows, targets, alignment = build_feature_and_target_rows(
        labels, source_features, feature_columns
    )
    for column in LABEL_COLUMNS:
        if column not in labels.columns:
            labels[column] = ""

    output_root.mkdir(parents=True, exist_ok=True)
    write_csv(labels[LABEL_COLUMNS], output_root / "baseline_ready_labels.csv")
    write_csv(feature_rows, output_root / "baseline_ready_feature_rows.csv")
    write_csv(targets, output_root / "baseline_ready_targets.csv")
    write_csv(alignment, output_root / "alignment_check.csv")
    write_csv(removed_columns, output_root / "removed_feature_columns.csv")
    write_csv(
        feature_statistics_by_source_run(feature_rows, feature_columns),
        output_root / "feature_statistics_per_source_run.csv",
    )
    (output_root / "features_columns.txt").write_text("\n".join(feature_columns) + "\n", encoding="utf-8")

    report = build_report(labels, feature_rows, targets, alignment, feature_columns)
    (output_root / "dataset_manifest.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_root / "combined_dataset_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_root / "combined_dataset_report.md").write_text(
        build_markdown_report(report),
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export combined_main external baseline-ready input without training a model."
    )
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_AUDIT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = export_combined_external_baseline_dataset(
        audit_root=args.audit_root,
        output_root=args.output_root,
    )
    print(
        "combined external baseline input exported: "
        f"labels={report['label_count']}, "
        f"cells={report['cell_count']}, "
        f"feature_rows={report['feature_row_count']}, "
        f"alignment={report['alignment_status']}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
