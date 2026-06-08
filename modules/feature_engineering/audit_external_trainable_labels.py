"""Audit external trainable health labels before any model training."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


DEFAULT_INPUTS = [
    ("six_default", Path("data/features/external_battery_datasets")),
    ("six_minobs20", Path("data/features/external_battery_datasets_sensitivity_minobs20")),
    ("high_default", Path("data/features/external_battery_datasets_candidates_high_obs")),
    ("high_minobs20", Path("data/features/external_battery_datasets_candidates_high_obs_minobs20")),
]

AUDIT_COLUMNS = [
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


@dataclass(frozen=True)
class LabelDataset:
    name: str
    root: Path


def parse_bool_series(series: pd.Series) -> pd.Series:
    if series.dtype == bool:
        return series
    return series.astype(str).str.lower().isin({"true", "1", "yes"})


def parse_inputs(values: list[str]) -> list[LabelDataset]:
    if not values:
        return [LabelDataset(name, path) for name, path in DEFAULT_INPUTS]
    datasets = []
    for value in values:
        if "=" not in value:
            raise ValueError(f"Input must use NAME=PATH format: {value}")
        name, path = value.split("=", 1)
        datasets.append(LabelDataset(name.strip(), Path(path.strip())))
    return datasets


def split_group_id(group_id: object) -> dict[str, object]:
    parts = str(group_id).split("|")
    return {
        "dataset_id_from_group": parts[0] if len(parts) > 0 else "",
        "cell_id_from_group": parts[1] if len(parts) > 1 else "",
        "source_archive_name_from_group": parts[2] if len(parts) > 2 else "",
    }


def representative_identity(labels: pd.DataFrame) -> pd.DataFrame:
    identity_columns = [
        "source_table",
        "label_key",
        "cell_id",
        "batch_id",
        "part_id",
        "source_archive_name",
        "protocol_regime_index",
    ]
    available = [column for column in identity_columns if column in labels.columns]
    if not available:
        return pd.DataFrame()
    identity = labels[available].copy()
    return identity.drop_duplicates()


def enrich_summary(summary: pd.DataFrame, labels: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    output = summary.copy()
    output["dataset_split_name"] = dataset_name
    parsed = output["group_id"].map(split_group_id).apply(pd.Series)
    output = pd.concat([output, parsed], axis=1)

    identity = representative_identity(labels)
    if not identity.empty:
        output = output.merge(
            identity,
            how="left",
            left_on=[
                "source_table",
                "label_key",
                "cell_id_from_group",
                "source_archive_name_from_group",
                "protocol_regime_index",
            ],
            right_on=[
                "source_table",
                "label_key",
                "cell_id",
                "source_archive_name",
                "protocol_regime_index",
            ],
        )

    output["cell_id"] = output.get("cell_id", output["cell_id_from_group"]).fillna(
        output["cell_id_from_group"]
    )
    for column in ["batch_id", "part_id"]:
        if column not in output.columns:
            output[column] = ""
        output[column] = output[column].fillna("")

    if "trainable_label" not in output.columns:
        output["trainable_label"] = False
    output["trainable_label"] = parse_bool_series(output["trainable_label"])

    for column in AUDIT_COLUMNS:
        if column not in output.columns:
            output[column] = ""
    return output


def read_label_dataset(dataset: LabelDataset) -> pd.DataFrame:
    summary_path = dataset.root / "external_label_summary.csv"
    labels_path = dataset.root / "external_health_labels.csv"
    if not summary_path.exists() or not labels_path.exists():
        raise FileNotFoundError(f"Missing label files under {dataset.root}")
    summary = pd.read_csv(summary_path)
    labels = pd.read_csv(labels_path)
    return enrich_summary(summary, labels, dataset.name)


def trainable_candidates(audit: pd.DataFrame) -> pd.DataFrame:
    return audit[
        audit["source_table"].eq("cycle_features.csv") & audit["trainable_label"].eq(True)
    ].copy()


def excluded_labels(audit: pd.DataFrame) -> pd.DataFrame:
    trainable_index = trainable_candidates(audit).index
    return audit.loc[~audit.index.isin(trainable_index)].copy()


def value_counts_dict(frame: pd.DataFrame, columns: list[str]) -> list[dict[str, object]]:
    if frame.empty:
        return []
    return frame.groupby(columns, dropna=False).size().reset_index(name="count").to_dict("records")


def build_coverage_matrix(trainable: pd.DataFrame) -> pd.DataFrame:
    if trainable.empty:
        return pd.DataFrame(
            columns=["dataset_split_name", "cell_id", "batch_id", "part_id"]
        )
    matrix = (
        trainable.assign(trainable=1)
        .pivot_table(
            index=["dataset_split_name", "cell_id", "batch_id", "part_id"],
            columns="label_key",
            values="trainable",
            aggfunc="max",
            fill_value=0,
        )
        .reset_index()
    )
    matrix.columns.name = None
    return matrix


def build_report(audit: pd.DataFrame, trainable: pd.DataFrame, excluded: pd.DataFrame) -> dict[str, object]:
    rpt_excluded = excluded[excluded["source_table"].eq("rpt_features.csv")]
    boundary_excluded = excluded[
        excluded["trainable_label_quality"].eq("excluded_unreliable_boundary_crossing")
    ]
    return {
        "datasets": sorted(audit["dataset_split_name"].dropna().unique().tolist()),
        "total_summary_rows": int(len(audit)),
        "trainable_summary_rows": int(len(trainable)),
        "excluded_summary_rows": int(len(excluded)),
        "rpt_excluded_rows": int(len(rpt_excluded)),
        "boundary_excluded_rows": int(len(boundary_excluded)),
        "trainable_by_dataset": value_counts_dict(trainable, ["dataset_split_name"]),
        "excluded_by_dataset": value_counts_dict(excluded, ["dataset_split_name"]),
        "trainable_by_label_key": value_counts_dict(trainable, ["label_key"]),
        "trainable_by_cell_id": value_counts_dict(trainable, ["dataset_split_name", "cell_id"]),
        "trainable_by_batch_part": value_counts_dict(
            trainable, ["dataset_split_name", "batch_id", "part_id"]
        ),
        "excluded_by_quality": value_counts_dict(
            excluded, ["source_table", "trainable_label_quality"]
        ),
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
            "# External Trainable Label Audit",
            "",
            "This report audits label trainability only. It is not a model result.",
            "",
            f"- Total summary rows: {report['total_summary_rows']}",
            f"- Trainable summary rows: {report['trainable_summary_rows']}",
            f"- Excluded summary rows: {report['excluded_summary_rows']}",
            f"- RPT excluded rows: {report['rpt_excluded_rows']}",
            f"- Boundary-excluded rows: {report['boundary_excluded_rows']}",
            "",
            "## Trainable By Dataset",
            markdown_table(report["trainable_by_dataset"], ["dataset_split_name", "count"]),
            "## Trainable By Label Key",
            markdown_table(report["trainable_by_label_key"], ["label_key", "count"]),
            "## Trainable By Cell",
            markdown_table(report["trainable_by_cell_id"], ["dataset_split_name", "cell_id", "count"]),
            "## Trainable By Batch/Part",
            markdown_table(
                report["trainable_by_batch_part"],
                ["dataset_split_name", "batch_id", "part_id", "count"],
            ),
            "## Excluded By Quality",
            markdown_table(
                report["excluded_by_quality"],
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


def audit_external_trainable_labels(
    datasets: list[LabelDataset],
    output_root: Path,
) -> dict[str, object]:
    audit = pd.concat([read_label_dataset(dataset) for dataset in datasets], ignore_index=True)
    trainable = trainable_candidates(audit)
    excluded = excluded_labels(audit)
    coverage = build_coverage_matrix(trainable)

    write_csv(trainable[AUDIT_COLUMNS], output_root / "trainable_label_summary.csv")
    write_csv(excluded[AUDIT_COLUMNS], output_root / "excluded_label_summary.csv")
    write_csv(coverage, output_root / "label_coverage_matrix.csv")

    report = build_report(audit, trainable, excluded)
    write_json(report, output_root / "label_audit_report.json")
    (output_root / "label_audit_report.md").write_text(
        build_markdown_report(report),
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Audit external trainable labels without training a model."
    )
    parser.add_argument(
        "--input",
        action="append",
        default=[],
        help="Optional NAME=PATH label output. Defaults to the four external label outputs.",
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("outputs/label_audit/external_trainable_labels"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = audit_external_trainable_labels(
        datasets=parse_inputs(args.input),
        output_root=args.output_root,
    )
    print(
        "label audit complete: "
        f"trainable={report['trainable_summary_rows']}, "
        f"excluded={report['excluded_summary_rows']}, "
        f"rpt_excluded={report['rpt_excluded_rows']}, "
        f"boundary_excluded={report['boundary_excluded_rows']}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
