"""Build feature tables from normalized external battery sample data."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


GROUP_ID_COLUMNS = [
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
]


@dataclass
class FeatureBuildSummary:
    feature_table: str
    source_file: str
    rows_in: int
    rows_out: int
    columns_out: int
    status: str
    notes: str


def numeric_series(frame: pd.DataFrame, column: str) -> pd.Series:
    if column not in frame.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(frame[column], errors="coerce").dropna()


def last_numeric_value(frame: pd.DataFrame, column: str) -> float:
    values = numeric_series(frame, column)
    return float(values.iloc[-1]) if not values.empty else np.nan


def add_numeric_summary(
    features: dict[str, object],
    frame: pd.DataFrame,
    column: str,
    prefix: str,
) -> None:
    values = numeric_series(frame, column)
    if values.empty:
        features[f"{prefix}_mean"] = np.nan
        features[f"{prefix}_std"] = np.nan
        features[f"{prefix}_min"] = np.nan
        features[f"{prefix}_max"] = np.nan
        features[f"{prefix}_last"] = np.nan
        return
    features[f"{prefix}_mean"] = float(values.mean())
    features[f"{prefix}_std"] = float(values.std(ddof=1)) if len(values) > 1 else 0.0
    features[f"{prefix}_min"] = float(values.min())
    features[f"{prefix}_max"] = float(values.max())
    features[f"{prefix}_last"] = float(values.iloc[-1])


def elapsed_seconds_from_relative_time(value: object) -> float:
    if pd.isna(value):
        return np.nan
    text = str(value).strip()
    parts = text.split(":")
    try:
        if len(parts) == 3:
            hours, minutes, seconds = parts
            return int(hours) * 3600 + int(minutes) * 60 + float(seconds)
        if len(parts) == 2:
            minutes, seconds = parts
            return int(minutes) * 60 + float(seconds)
        return float(text)
    except ValueError:
        return np.nan


def infer_duration_s(frame: pd.DataFrame) -> float:
    if "elapsed_time_s" in frame.columns:
        values = numeric_series(frame, "elapsed_time_s")
        if not values.empty:
            return float(values.max() - values.min())
    if "relative_time_raw" in frame.columns:
        values = frame["relative_time_raw"].map(elapsed_seconds_from_relative_time).dropna()
        if not values.empty:
            return float(values.max() - values.min())
    for column in frame.columns:
        lowered = column.lower()
        if lowered.startswith("time") or lowered.endswith("_time_s") or "time_sec" in lowered:
            values = numeric_series(frame, column)
            if not values.empty:
                return float(values.max() - values.min())
    return np.nan


def state_fraction(frame: pd.DataFrame, pattern: str) -> float:
    if "state" not in frame.columns or frame.empty:
        return np.nan
    matches = frame["state"].astype(str).str.contains(pattern, case=False, na=False)
    return float(matches.mean())


def base_group_identity(group: pd.DataFrame) -> dict[str, object]:
    identity = {}
    for column in GROUP_ID_COLUMNS:
        identity[column] = group[column].iloc[0] if column in group.columns else ""
    return identity


def build_cycle_features(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    group_columns = GROUP_ID_COLUMNS + ["cycle_index"]
    available_groups = [column for column in group_columns if column in frame.columns]
    rows = []
    for _, group in frame.groupby(available_groups, dropna=False, sort=True):
        features = base_group_identity(group)
        features["cycle_index"] = group["cycle_index"].iloc[0] if "cycle_index" in group.columns else ""
        features["sample_rows"] = int(len(group))
        features["duration_s"] = infer_duration_s(group)
        add_numeric_summary(features, group, "current_a", "current_a")
        add_numeric_summary(features, group, "voltage_v", "voltage_v")
        add_numeric_summary(features, group, "capacity_ah", "capacity_ah")
        add_numeric_summary(features, group, "energy_wh", "energy_wh")
        features["charge_state_fraction"] = state_fraction(group, "chg|charge")
        features["discharge_state_fraction"] = state_fraction(group, "dchg|discharge")
        features["absolute_current_mean_a"] = float(numeric_series(group, "current_a").abs().mean())
        features["capacity_delta_ah"] = (
            features["capacity_ah_max"] - features["capacity_ah_min"]
            if pd.notna(features["capacity_ah_max"]) and pd.notna(features["capacity_ah_min"])
            else np.nan
        )
        rows.append(features)
    output = pd.DataFrame(rows)
    return output.sort_values(["cell_id", "cycle_index", "source_archive_name"], na_position="last")


def build_rpt_features(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    group_columns = GROUP_ID_COLUMNS + ["diagnostic_part"]
    available_groups = [column for column in group_columns if column in frame.columns]
    rows = []
    for _, group in frame.groupby(available_groups, dropna=False, sort=True):
        features = base_group_identity(group)
        features["diagnostic_part"] = (
            group["diagnostic_part"].iloc[0] if "diagnostic_part" in group.columns else ""
        )
        features["sample_rows"] = int(len(group))
        features["duration_s"] = infer_duration_s(group)
        add_numeric_summary(features, group, "current_a", "current_a")
        add_numeric_summary(features, group, "voltage_v", "voltage_v")
        add_numeric_summary(features, group, "capacity_ah", "capacity_ah")
        add_numeric_summary(features, group, "energy_wh", "energy_wh")
        add_numeric_summary(features, group, "pulse_soc", "pulse_soc")
        features["capacity_delta_ah"] = (
            features["capacity_ah_max"] - features["capacity_ah_min"]
            if pd.notna(features["capacity_ah_max"]) and pd.notna(features["capacity_ah_min"])
            else np.nan
        )
        features["voltage_drop_v"] = (
            features["voltage_v_max"] - features["voltage_v_min"]
            if pd.notna(features["voltage_v_max"]) and pd.notna(features["voltage_v_min"])
            else np.nan
        )
        features["pulse_type_count"] = (
            int(group["pulse_type"].nunique(dropna=True)) if "pulse_type" in group.columns else 0
        )
        rows.append(features)
    output = pd.DataFrame(rows)
    return output.sort_values(["cell_id", "diagnostic_part", "source_archive_name"], na_position="last")


def matching_columns(frame: pd.DataFrame, keywords: tuple[str, ...]) -> list[str]:
    return [
        column
        for column in frame.columns
        if any(keyword in column.lower() for keyword in keywords)
    ]


def max_across_columns(frame: pd.DataFrame, columns: list[str]) -> float:
    values = [numeric_series(frame, column) for column in columns]
    values = [series for series in values if not series.empty]
    if not values:
        return np.nan
    return float(pd.concat(values).max())


def min_across_columns(frame: pd.DataFrame, columns: list[str]) -> float:
    values = [numeric_series(frame, column) for column in columns]
    values = [series for series in values if not series.empty]
    if not values:
        return np.nan
    return float(pd.concat(values).min())


def build_thermal_runaway_features(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return pd.DataFrame()
    group_columns = GROUP_ID_COLUMNS + [
        "nominal_capacity_mah",
        "replicate_id",
        "soc_percent",
    ]
    available_groups = [column for column in group_columns if column in frame.columns]
    rows = []
    for _, group in frame.groupby(available_groups, dropna=False, sort=True):
        features = base_group_identity(group)
        features["nominal_capacity_mah"] = (
            group["nominal_capacity_mah"].iloc[0] if "nominal_capacity_mah" in group.columns else ""
        )
        features["replicate_id"] = group["replicate_id"].iloc[0] if "replicate_id" in group.columns else ""
        features["soc_percent"] = group["soc_percent"].iloc[0] if "soc_percent" in group.columns else ""
        features["sample_rows"] = int(len(group))
        features["duration_s"] = infer_duration_s(group)
        voltage_columns = matching_columns(group, ("voltage",))
        temperature_columns = matching_columns(group, ("temp", "temperature"))
        force_columns = matching_columns(group, ("force", "load"))
        displacement_columns = matching_columns(group, ("displacement",))
        features["voltage_min_v"] = min_across_columns(group, voltage_columns)
        features["voltage_max_v"] = max_across_columns(group, voltage_columns)
        features["temperature_max_c"] = max_across_columns(group, temperature_columns)
        features["force_max"] = max_across_columns(group, force_columns)
        features["displacement_max_mm"] = max_across_columns(group, displacement_columns)
        features["safety_event_hint"] = bool(
            (pd.notna(features["temperature_max_c"]) and features["temperature_max_c"] >= 60.0)
            or (pd.notna(features["voltage_min_v"]) and features["voltage_min_v"] <= 1.0)
        )
        rows.append(features)
    output = pd.DataFrame(rows)
    return output.sort_values(["cell_id", "source_archive_name"], na_position="last")


def write_csv(frame: pd.DataFrame, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def write_json(path: Path, content: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2), encoding="utf-8")


def build_all_features(input_root: Path, output_root: Path) -> list[FeatureBuildSummary]:
    output_root.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("cycle_features_sample.csv", input_root / "cycle_timeseries_sample.csv", build_cycle_features),
        ("rpt_features_sample.csv", input_root / "rpt_diagnostic_sample.csv", build_rpt_features),
        (
            "thermal_runaway_features_sample.csv",
            input_root / "abuse_test_timeseries_sample.csv",
            build_thermal_runaway_features,
        ),
    ]
    summaries: list[FeatureBuildSummary] = []
    for output_name, source_path, builder in jobs:
        if not source_path.exists():
            summaries.append(
                FeatureBuildSummary(
                    feature_table=output_name,
                    source_file=str(source_path),
                    rows_in=0,
                    rows_out=0,
                    columns_out=0,
                    status="skipped",
                    notes="source file not found",
                )
            )
            continue
        source = pd.read_csv(source_path)
        features = builder(source)
        write_csv(features, output_root / output_name)
        summaries.append(
            FeatureBuildSummary(
                feature_table=output_name,
                source_file=str(source_path),
                rows_in=int(source.shape[0]),
                rows_out=int(features.shape[0]),
                columns_out=int(features.shape[1]),
                status="written",
                notes="",
            )
        )
    summary_frame = pd.DataFrame([asdict(item) for item in summaries])
    write_csv(summary_frame, output_root / "feature_build_summary.csv")
    write_json(output_root / "feature_build_summary.json", [asdict(item) for item in summaries])
    return summaries


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build sample feature tables for external battery datasets."
    )
    parser.add_argument(
        "--input-root",
        type=Path,
        default=Path("data/processed/external_battery_datasets/extracted"),
    )
    parser.add_argument(
        "--output-root",
        type=Path,
        default=Path("data/features/external_battery_datasets"),
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summaries = build_all_features(args.input_root, args.output_root)
    for summary in summaries:
        print(
            f"{summary.feature_table}: {summary.status}, "
            f"rows_in={summary.rows_in}, rows_out={summary.rows_out}"
        )


if __name__ == "__main__":
    main()
