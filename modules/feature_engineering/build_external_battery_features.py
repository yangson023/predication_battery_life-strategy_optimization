"""Build feature tables from normalized external battery data."""

from __future__ import annotations

import argparse
import json
from collections.abc import Callable
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


PROTOCOL_CURRENT_RELATIVE_CHANGE_THRESHOLD = 0.30
PROTOCOL_CHARGE_FRACTION_DELTA_THRESHOLD = 0.08
PROTOCOL_DURATION_RELATIVE_CHANGE_THRESHOLD = 1.00
MIN_PROTOCOL_REGIME_OBSERVATIONS_FOR_LABELS = 50


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


def charge_state_fraction(frame: pd.DataFrame) -> float:
    if "state" not in frame.columns or frame.empty:
        return np.nan
    state = frame["state"].astype(str).str.lower()
    discharge = state.str.contains("dchg|discharge", na=False)
    charge = state.str.contains("chg|charge", na=False) & ~discharge
    return float(charge.mean())


def discharge_state_fraction(frame: pd.DataFrame) -> float:
    return state_fraction(frame, "dchg|discharge")


def relative_change(current: object, previous: object) -> float:
    current_value = pd.to_numeric(pd.Series([current]), errors="coerce").iloc[0]
    previous_value = pd.to_numeric(pd.Series([previous]), errors="coerce").iloc[0]
    if pd.isna(current_value) or pd.isna(previous_value) or abs(previous_value) <= 1e-12:
        return np.nan
    return float(abs(current_value - previous_value) / abs(previous_value))


def absolute_delta(current: object, previous: object) -> float:
    current_value = pd.to_numeric(pd.Series([current]), errors="coerce").iloc[0]
    previous_value = pd.to_numeric(pd.Series([previous]), errors="coerce").iloc[0]
    if pd.isna(current_value) or pd.isna(previous_value):
        return np.nan
    return float(abs(current_value - previous_value))


def protocol_boundary_reasons(row: pd.Series) -> list[str]:
    reasons = []
    current_change = row.get("protocol_current_relative_change", np.nan)
    charge_delta = row.get("protocol_charge_fraction_delta", np.nan)
    duration_change = row.get("protocol_duration_relative_change", np.nan)
    if pd.notna(current_change) and current_change > PROTOCOL_CURRENT_RELATIVE_CHANGE_THRESHOLD:
        reasons.append("absolute_current_mean_shift")
    if pd.notna(charge_delta) and charge_delta > PROTOCOL_CHARGE_FRACTION_DELTA_THRESHOLD:
        reasons.append("charge_state_fraction_shift")
    if pd.notna(duration_change) and duration_change > PROTOCOL_DURATION_RELATIVE_CHANGE_THRESHOLD:
        reasons.append("duration_shift")
    return reasons


def add_protocol_diagnostics(features: pd.DataFrame) -> pd.DataFrame:
    if features.empty or "cell_id" not in features.columns:
        return features
    output = features.copy()
    sort_columns = [
        column
        for column in ["cell_id", "cycle_index", "source_archive_name", "archive_member_path"]
        if column in output.columns
    ]
    output = output.sort_values(sort_columns, na_position="last").reset_index(drop=True)

    diagnostic_rows = []
    for _, group in output.groupby("cell_id", dropna=False, sort=False):
        previous = None
        regime_index = 1
        for _, row in group.iterrows():
            current_change = (
                relative_change(row.get("absolute_current_mean_a"), previous.get("absolute_current_mean_a"))
                if previous is not None
                else np.nan
            )
            charge_delta = (
                absolute_delta(row.get("charge_state_fraction"), previous.get("charge_state_fraction"))
                if previous is not None
                else np.nan
            )
            duration_change = (
                relative_change(row.get("duration_s"), previous.get("duration_s"))
                if previous is not None
                else np.nan
            )
            row = row.copy()
            row["protocol_current_relative_change"] = current_change
            row["protocol_charge_fraction_delta"] = charge_delta
            row["protocol_duration_relative_change"] = duration_change
            reasons = protocol_boundary_reasons(row)
            row["protocol_boundary_flag"] = bool(reasons)
            row["protocol_boundary_reason"] = ";".join(reasons)
            if reasons:
                regime_index += 1
            row["protocol_regime_index"] = regime_index
            diagnostic_rows.append(row)
            previous = row

    return pd.DataFrame(diagnostic_rows)


def build_protocol_regime_summary(cycle_features: pd.DataFrame) -> pd.DataFrame:
    if cycle_features.empty or "protocol_regime_index" not in cycle_features.columns:
        return pd.DataFrame()
    rows = []
    group_columns = ["cell_id", "protocol_regime_index"]
    for (cell_id, regime_index), group in cycle_features.groupby(group_columns, dropna=False, sort=True):
        observations = int(len(group))
        first_row = group.iloc[0]
        rows.append(
            {
                "cell_id": cell_id,
                "protocol_regime_index": int(regime_index),
                "observations": observations,
                "cycle_index_min": group["cycle_index"].min() if "cycle_index" in group.columns else "",
                "cycle_index_max": group["cycle_index"].max() if "cycle_index" in group.columns else "",
                "boundary_started_regime": bool(first_row.get("protocol_boundary_flag", False)),
                "boundary_reason": first_row.get("protocol_boundary_reason", ""),
                "absolute_current_mean_a_median": float(group["absolute_current_mean_a"].median())
                if "absolute_current_mean_a" in group.columns
                else np.nan,
                "charge_state_fraction_median": float(group["charge_state_fraction"].median())
                if "charge_state_fraction" in group.columns
                else np.nan,
                "duration_s_median": float(group["duration_s"].median()) if "duration_s" in group.columns else np.nan,
                "capacity_delta_ah_median": float(group["capacity_delta_ah"].median())
                if "capacity_delta_ah" in group.columns
                else np.nan,
                "protocol_window_quality": (
                    "usable_protocol_window"
                    if observations >= MIN_PROTOCOL_REGIME_OBSERVATIONS_FOR_LABELS
                    else f"limited_protocol_window_less_than_{MIN_PROTOCOL_REGIME_OBSERVATIONS_FOR_LABELS}_observations"
                ),
            }
        )
    return pd.DataFrame(rows)


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
        features["charge_state_fraction"] = charge_state_fraction(group)
        features["discharge_state_fraction"] = discharge_state_fraction(group)
        features["absolute_current_mean_a"] = float(numeric_series(group, "current_a").abs().mean())
        features["capacity_delta_ah"] = (
            features["capacity_ah_max"] - features["capacity_ah_min"]
            if pd.notna(features["capacity_ah_max"]) and pd.notna(features["capacity_ah_min"])
            else np.nan
        )
        rows.append(features)
    output = pd.DataFrame(rows)
    output = output.sort_values(["cell_id", "cycle_index", "source_archive_name"], na_position="last")
    return add_protocol_diagnostics(output)


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


def build_sample_features(input_root: Path, output_root: Path) -> list[FeatureBuildSummary]:
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


def build_features_from_sources(
    sources: list[Path],
    builder: Callable[[pd.DataFrame], pd.DataFrame],
) -> tuple[pd.DataFrame, int, list[str]]:
    features = []
    rows_in = 0
    failures = []
    for source_path in sources:
        try:
            source = pd.read_csv(source_path)
            rows_in += int(source.shape[0])
            feature_frame = builder(source)
            if not feature_frame.empty:
                features.append(feature_frame)
        except Exception as exc:
            failures.append(f"{source_path}: {exc}")
    if not features:
        return pd.DataFrame(), rows_in, failures
    return pd.concat(features, ignore_index=True), rows_in, failures


def build_by_cell_features(input_root: Path, output_root: Path) -> list[FeatureBuildSummary]:
    output_root.mkdir(parents=True, exist_ok=True)
    jobs = [
        ("cycle_features.csv", "cycle_timeseries.csv", build_cycle_features),
        ("rpt_features.csv", "rpt_diagnostic.csv", build_rpt_features),
    ]
    summaries = []
    for output_name, source_name, builder in jobs:
        sources = sorted(input_root.glob(f"*/{source_name}"))
        if not sources:
            summaries.append(
                FeatureBuildSummary(
                    feature_table=output_name,
                    source_file=str(input_root / f"*/{source_name}"),
                    rows_in=0,
                    rows_out=0,
                    columns_out=0,
                    status="skipped",
                    notes="no per-cell source files found",
                )
            )
            continue
        features, rows_in, failures = build_features_from_sources(sources, builder)
        write_csv(features, output_root / output_name)
        if output_name == "cycle_features.csv":
            protocol_summary = build_protocol_regime_summary(features)
            write_csv(protocol_summary, output_root / "protocol_regime_summary.csv")
            protocol_note = (
                f"protocol_regimes={len(protocol_summary)}"
                if not protocol_summary.empty
                else "protocol_regimes=0"
            )
        else:
            protocol_note = ""
        summaries.append(
            FeatureBuildSummary(
                feature_table=output_name,
                source_file=f"{len(sources)} per-cell files",
                rows_in=rows_in,
                rows_out=int(features.shape[0]),
                columns_out=int(features.shape[1]),
                status="written" if not failures else "warn",
                notes="; ".join([note for note in [protocol_note, *failures[:5]] if note]),
            )
        )
    summary_frame = pd.DataFrame([asdict(item) for item in summaries])
    write_csv(summary_frame, output_root / "feature_build_summary.csv")
    write_json(output_root / "feature_build_summary.json", [asdict(item) for item in summaries])
    return summaries


def build_all_features(input_root: Path, output_root: Path, source_mode: str = "sample") -> list[FeatureBuildSummary]:
    if source_mode == "sample":
        return build_sample_features(input_root, output_root)
    if source_mode == "by_cell":
        return build_by_cell_features(input_root, output_root)
    raise ValueError(f"Unsupported source mode: {source_mode}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build feature tables for external battery datasets."
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
    parser.add_argument(
        "--source-mode",
        choices=["sample", "by_cell"],
        default="sample",
        help="Use sample tables or per-cell chunk files as feature inputs.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summaries = build_all_features(args.input_root, args.output_root, args.source_mode)
    for summary in summaries:
        print(
            f"{summary.feature_table}: {summary.status}, "
            f"rows_in={summary.rows_in}, rows_out={summary.rows_out}"
        )


if __name__ == "__main__":
    main()
