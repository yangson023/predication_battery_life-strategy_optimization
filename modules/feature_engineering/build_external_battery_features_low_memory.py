"""Build external battery feature tables with chunked CSV reads.

This module is intended for large per-cell external battery CSV files. It keeps
only per-cycle or per-diagnostic accumulators in memory and never materializes a
whole source CSV as one DataFrame.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from modules.feature_engineering.build_external_battery_features import (
    GROUP_ID_COLUMNS,
    add_protocol_diagnostics,
    build_protocol_regime_summary,
    elapsed_seconds_from_relative_time,
    write_csv,
)


NUMERIC_PREFIX_COLUMNS = {
    "current_a": "current_a",
    "voltage_v": "voltage_v",
    "capacity_ah": "capacity_ah",
    "energy_wh": "energy_wh",
    "pulse_soc": "pulse_soc",
}


CYCLE_EXPECTED_COLUMNS = [
    *GROUP_ID_COLUMNS,
    "cycle_index",
    "sample_rows",
    "duration_s",
    "current_a_mean",
    "current_a_std",
    "current_a_min",
    "current_a_max",
    "current_a_last",
    "voltage_v_mean",
    "voltage_v_std",
    "voltage_v_min",
    "voltage_v_max",
    "voltage_v_last",
    "capacity_ah_mean",
    "capacity_ah_std",
    "capacity_ah_min",
    "capacity_ah_max",
    "capacity_ah_last",
    "energy_wh_mean",
    "energy_wh_std",
    "energy_wh_min",
    "energy_wh_max",
    "energy_wh_last",
    "charge_state_fraction",
    "discharge_state_fraction",
    "absolute_current_mean_a",
    "capacity_delta_ah",
    "protocol_current_relative_change",
    "protocol_charge_fraction_delta",
    "protocol_duration_relative_change",
    "protocol_boundary_flag",
    "protocol_boundary_reason",
    "protocol_regime_index",
]


RPT_EXPECTED_COLUMNS = [
    *GROUP_ID_COLUMNS,
    "diagnostic_part",
    "sample_rows",
    "duration_s",
    "current_a_mean",
    "current_a_std",
    "current_a_min",
    "current_a_max",
    "current_a_last",
    "voltage_v_mean",
    "voltage_v_std",
    "voltage_v_min",
    "voltage_v_max",
    "voltage_v_last",
    "capacity_ah_mean",
    "capacity_ah_std",
    "capacity_ah_min",
    "capacity_ah_max",
    "capacity_ah_last",
    "energy_wh_mean",
    "energy_wh_std",
    "energy_wh_min",
    "energy_wh_max",
    "energy_wh_last",
    "pulse_soc_mean",
    "pulse_soc_std",
    "pulse_soc_min",
    "pulse_soc_max",
    "pulse_soc_last",
    "capacity_delta_ah",
    "voltage_drop_v",
    "pulse_type_count",
]


@dataclass
class LowMemoryFeatureBuildSummary:
    feature_table: str
    source_file: str
    rows_in: int
    rows_out: int
    columns_out: int
    chunks_read: int
    status: str
    notes: str


class NumericAccumulator:
    """Running numeric statistics for a single feature column."""

    def __init__(self) -> None:
        self.valid_count = 0
        self.missing_count = 0
        self.total_count = 0
        self.total = 0.0
        self.sum_squares = 0.0
        self.minimum = np.nan
        self.maximum = np.nan
        self.first = np.nan
        self.last = np.nan

    def update(self, values: pd.Series) -> None:
        numeric = pd.to_numeric(values, errors="coerce")
        self.total_count += int(len(numeric))
        self.missing_count += int(numeric.isna().sum())
        valid = numeric.dropna()
        if valid.empty:
            return
        self.valid_count += int(len(valid))
        self.total += float(valid.sum())
        self.sum_squares += float((valid.astype(float) ** 2).sum())
        current_min = float(valid.min())
        current_max = float(valid.max())
        self.minimum = current_min if pd.isna(self.minimum) else min(float(self.minimum), current_min)
        self.maximum = current_max if pd.isna(self.maximum) else max(float(self.maximum), current_max)
        if pd.isna(self.first):
            self.first = float(valid.iloc[0])
        self.last = float(valid.iloc[-1])

    @property
    def mean(self) -> float:
        if self.valid_count == 0:
            return np.nan
        return float(self.total / self.valid_count)

    @property
    def std(self) -> float:
        if self.valid_count == 0:
            return np.nan
        if self.valid_count == 1:
            return 0.0
        variance = (self.sum_squares - (self.total * self.total / self.valid_count)) / (
            self.valid_count - 1
        )
        return float(math.sqrt(max(variance, 0.0)))

    @property
    def missing_fraction(self) -> float:
        if self.total_count == 0:
            return np.nan
        return float(self.missing_count / self.total_count)

    def to_feature_values(self, prefix: str) -> dict[str, float]:
        return {
            f"{prefix}_mean": self.mean,
            f"{prefix}_std": self.std,
            f"{prefix}_min": self.minimum,
            f"{prefix}_max": self.maximum,
            f"{prefix}_last": self.last,
        }


class DurationAccumulator:
    """Running min/max duration candidates for one feature group."""

    def __init__(self) -> None:
        self.elapsed = NumericAccumulator()
        self.relative = NumericAccumulator()
        self.generic: dict[str, NumericAccumulator] = {}
        self.generic_order: list[str] = []

    def update(self, frame: pd.DataFrame) -> None:
        if "elapsed_time_s" in frame.columns:
            self.elapsed.update(frame["elapsed_time_s"])
        if "relative_time_raw" in frame.columns:
            parsed = frame["relative_time_raw"].map(elapsed_seconds_from_relative_time)
            self.relative.update(parsed)
        for column in frame.columns:
            lowered = column.lower()
            if column in {"elapsed_time_s", "relative_time_raw"}:
                continue
            if lowered.startswith("time") or lowered.endswith("_time_s") or "time_sec" in lowered:
                if column not in self.generic:
                    self.generic[column] = NumericAccumulator()
                    self.generic_order.append(column)
                self.generic[column].update(frame[column])

    @staticmethod
    def _duration_from(accumulator: NumericAccumulator) -> float:
        if accumulator.valid_count == 0:
            return np.nan
        return float(accumulator.maximum - accumulator.minimum)

    def duration_s(self) -> float:
        if self.elapsed.valid_count > 0:
            return self._duration_from(self.elapsed)
        if self.relative.valid_count > 0:
            return self._duration_from(self.relative)
        for column in self.generic_order:
            accumulator = self.generic[column]
            if accumulator.valid_count > 0:
                return self._duration_from(accumulator)
        return np.nan


def key_value(value: object) -> object:
    if pd.isna(value):
        return "__NA__"
    return value


def restore_key_value(value: object) -> object:
    return np.nan if value == "__NA__" else value


def charge_matches(states: pd.Series) -> pd.Series:
    lowered = states.astype(str).str.lower()
    discharge = lowered.str.contains("dchg|discharge", na=False)
    charge = lowered.str.contains("chg|charge", na=False) & ~discharge
    return charge


def discharge_matches(states: pd.Series) -> pd.Series:
    return states.astype(str).str.contains("dchg|discharge", case=False, na=False)


class FeatureGroupAccumulator:
    """Accumulates one cycle or RPT feature row across many chunks."""

    def __init__(self, table_type: str) -> None:
        self.table_type = table_type
        self.identity: dict[str, object] = {}
        self.group_value: object = ""
        self.sample_rows = 0
        self.numeric: dict[str, NumericAccumulator] = {}
        self.absolute_current = NumericAccumulator()
        self.duration = DurationAccumulator()
        self.has_state = False
        self.state_rows = 0
        self.charge_rows = 0
        self.discharge_rows = 0
        self.pulse_types: set[str] = set()

    def update(self, frame: pd.DataFrame, group_column: str) -> None:
        if frame.empty:
            return
        first_row = frame.iloc[0]
        if not self.identity:
            for column in GROUP_ID_COLUMNS:
                self.identity[column] = first_row[column] if column in frame.columns else ""
            self.group_value = first_row[group_column] if group_column in frame.columns else ""

        self.sample_rows += int(len(frame))
        self.duration.update(frame)
        for column, prefix in NUMERIC_PREFIX_COLUMNS.items():
            if column not in frame.columns and column != "pulse_soc":
                self.numeric.setdefault(prefix, NumericAccumulator())
                continue
            if column not in frame.columns:
                self.numeric.setdefault(prefix, NumericAccumulator())
                continue
            accumulator = self.numeric.setdefault(prefix, NumericAccumulator())
            accumulator.update(frame[column])

        if "current_a" in frame.columns:
            absolute_values = pd.to_numeric(frame["current_a"], errors="coerce").abs()
            self.absolute_current.update(absolute_values)

        if "state" in frame.columns:
            self.has_state = True
            self.state_rows += int(len(frame))
            self.charge_rows += int(charge_matches(frame["state"]).sum())
            self.discharge_rows += int(discharge_matches(frame["state"]).sum())

        if self.table_type == "rpt" and "pulse_type" in frame.columns:
            valid_types = frame["pulse_type"].dropna().astype(str)
            self.pulse_types.update(valid_types.tolist())

    def finalize(self) -> dict[str, object]:
        features = dict(self.identity)
        if self.table_type == "cycle":
            features["cycle_index"] = self.group_value
        else:
            features["diagnostic_part"] = self.group_value
        features["sample_rows"] = int(self.sample_rows)
        features["duration_s"] = self.duration.duration_s()

        required_prefixes = ["current_a", "voltage_v", "capacity_ah", "energy_wh"]
        if self.table_type == "rpt":
            required_prefixes.append("pulse_soc")
        for prefix in required_prefixes:
            accumulator = self.numeric.setdefault(prefix, NumericAccumulator())
            features.update(accumulator.to_feature_values(prefix))

        capacity = self.numeric.setdefault("capacity_ah", NumericAccumulator())
        features["capacity_delta_ah"] = (
            float(capacity.maximum - capacity.minimum)
            if capacity.valid_count > 0
            else np.nan
        )

        if self.table_type == "cycle":
            features["charge_state_fraction"] = (
                float(self.charge_rows / self.state_rows) if self.has_state and self.state_rows else np.nan
            )
            features["discharge_state_fraction"] = (
                float(self.discharge_rows / self.state_rows) if self.has_state and self.state_rows else np.nan
            )
            features["absolute_current_mean_a"] = self.absolute_current.mean
        else:
            voltage = self.numeric.setdefault("voltage_v", NumericAccumulator())
            features["voltage_drop_v"] = (
                float(voltage.maximum - voltage.minimum)
                if voltage.valid_count > 0
                else np.nan
            )
            features["pulse_type_count"] = int(len(self.pulse_types))

        return features


class TableAccumulator:
    """Accumulates all feature rows for one output table."""

    def __init__(self, table_type: str, group_column: str) -> None:
        self.table_type = table_type
        self.group_column = group_column
        self.group_columns: list[str] | None = None
        self.groups: dict[tuple[object, ...], FeatureGroupAccumulator] = {}
        self.rows_in = 0
        self.chunks_read = 0

    def update(self, chunk: pd.DataFrame) -> None:
        self.rows_in += int(len(chunk))
        self.chunks_read += 1
        if self.group_columns is None:
            desired = [*GROUP_ID_COLUMNS, self.group_column]
            self.group_columns = [column for column in desired if column in chunk.columns]
        if not self.group_columns:
            return

        for _, group in chunk.groupby(self.group_columns, dropna=False, sort=False):
            key = tuple(key_value(group[column].iloc[0]) for column in self.group_columns)
            accumulator = self.groups.setdefault(key, FeatureGroupAccumulator(self.table_type))
            accumulator.update(group, self.group_column)

    def to_frame(self) -> pd.DataFrame:
        rows = [accumulator.finalize() for accumulator in self.groups.values()]
        if not rows:
            return pd.DataFrame()
        output = pd.DataFrame(rows)
        if self.table_type == "cycle":
            sort_columns = [
                column
                for column in ["cell_id", "cycle_index", "source_archive_name", "archive_member_path"]
                if column in output.columns
            ]
            output = output.sort_values(sort_columns, na_position="last").reset_index(drop=True)
            output = add_protocol_diagnostics(output)
            return output.reindex(columns=CYCLE_EXPECTED_COLUMNS)
        sort_columns = [
            column
            for column in ["cell_id", "diagnostic_part", "source_archive_name", "archive_member_path"]
            if column in output.columns
        ]
        output = output.sort_values(sort_columns, na_position="last").reset_index(drop=True)
        return output.reindex(columns=RPT_EXPECTED_COLUMNS)


def read_csv_in_chunks(source_path: Path, chunksize: int) -> Any:
    return pd.read_csv(source_path, chunksize=chunksize)


def build_table_from_sources(
    sources: list[Path],
    table_type: str,
    source_name: str,
    chunksize: int,
) -> tuple[pd.DataFrame, LowMemoryFeatureBuildSummary, list[str]]:
    group_column = "cycle_index" if table_type == "cycle" else "diagnostic_part"
    accumulator = TableAccumulator(table_type=table_type, group_column=group_column)
    failures: list[str] = []
    for source_path in sources:
        try:
            for chunk in read_csv_in_chunks(source_path, chunksize):
                accumulator.update(chunk)
        except Exception as exc:  # pragma: no cover - exercised through integration failures
            failures.append(f"{source_path}: {exc}")

    features = accumulator.to_frame()
    summary = LowMemoryFeatureBuildSummary(
        feature_table="cycle_features.csv" if table_type == "cycle" else "rpt_features.csv",
        source_file=f"{len(sources)} per-cell {source_name} files",
        rows_in=int(accumulator.rows_in),
        rows_out=int(features.shape[0]),
        columns_out=int(features.shape[1]),
        chunks_read=int(accumulator.chunks_read),
        status="written" if not failures else "warn",
        notes="; ".join(failures[:5]),
    )
    return features, summary, failures


def schema_check_frame(cycle_features: pd.DataFrame, rpt_features: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for table_name, frame, expected in [
        ("cycle_features.csv", cycle_features, CYCLE_EXPECTED_COLUMNS),
        ("rpt_features.csv", rpt_features, RPT_EXPECTED_COLUMNS),
    ]:
        actual = list(frame.columns)
        missing = [column for column in expected if column not in actual]
        extra = [column for column in actual if column not in expected]
        rows.append(
            {
                "feature_table": table_name,
                "expected_columns": len(expected),
                "actual_columns": len(actual),
                "missing_columns": ";".join(missing),
                "extra_columns": ";".join(extra),
                "status": "pass" if not missing and not extra else "warn",
            }
        )
    return pd.DataFrame(rows)


def json_safe(value: object) -> object:
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [json_safe(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        if pd.isna(value):
            return None
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


def write_json(path: Path, content: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(json_safe(content), ensure_ascii=False, indent=2), encoding="utf-8")


def prepare_output_root(output_root: Path, overwrite: bool) -> None:
    if output_root.exists() and any(output_root.iterdir()):
        if not overwrite:
            raise FileExistsError(
                f"Output root is not empty: {output_root}. Use --overwrite to replace it."
            )
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)


def build_by_cell_features_low_memory(
    input_root: Path,
    output_root: Path,
    chunksize: int = 250_000,
    overwrite: bool = False,
) -> list[LowMemoryFeatureBuildSummary]:
    if chunksize <= 0:
        raise ValueError("chunksize must be positive")
    prepare_output_root(output_root, overwrite=overwrite)

    cycle_sources = sorted(input_root.glob("*/cycle_timeseries.csv"))
    rpt_sources = sorted(input_root.glob("*/rpt_diagnostic.csv"))

    cycle_features, cycle_summary, cycle_failures = build_table_from_sources(
        cycle_sources, "cycle", "cycle_timeseries.csv", chunksize
    )
    rpt_features, rpt_summary, rpt_failures = build_table_from_sources(
        rpt_sources, "rpt", "rpt_diagnostic.csv", chunksize
    )

    write_csv(cycle_features, output_root / "cycle_features.csv")
    write_csv(rpt_features, output_root / "rpt_features.csv")
    protocol_summary = build_protocol_regime_summary(cycle_features)
    write_csv(protocol_summary, output_root / "protocol_regime_summary.csv")

    schema_checks = schema_check_frame(cycle_features, rpt_features)
    write_csv(schema_checks, output_root / "feature_schema_check.csv")

    summaries = [cycle_summary, rpt_summary]
    summary_frame = pd.DataFrame([asdict(summary) for summary in summaries])
    write_csv(summary_frame, output_root / "feature_build_summary.csv")

    report = {
        "builder": "build_external_battery_features_low_memory",
        "source_mode": "by_cell",
        "input_root": str(input_root),
        "output_root": str(output_root),
        "chunksize": chunksize,
        "cycle_source_files": len(cycle_sources),
        "rpt_source_files": len(rpt_sources),
        "cycle_failures": cycle_failures,
        "rpt_failures": rpt_failures,
        "outputs": [asdict(summary) for summary in summaries],
        "schema_check": schema_checks.to_dict(orient="records"),
        "rpt_training_policy": "audit_only_excluded_from_training",
        "completion_status": "complete" if not cycle_failures and not rpt_failures else "complete_with_warnings",
    }
    write_json(output_root / "feature_build_report.json", report)
    write_json(output_root / "feature_build_summary.json", [asdict(summary) for summary in summaries])
    return summaries


def build_all_features_low_memory(
    input_root: Path,
    output_root: Path,
    source_mode: str = "by_cell",
    chunksize: int = 250_000,
    overwrite: bool = False,
) -> list[LowMemoryFeatureBuildSummary]:
    if source_mode != "by_cell":
        raise ValueError("The low-memory builder currently supports only --source-mode by_cell")
    return build_by_cell_features_low_memory(
        input_root=input_root,
        output_root=output_root,
        chunksize=chunksize,
        overwrite=overwrite,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build external battery feature tables using chunked CSV reads."
    )
    parser.add_argument("--source-mode", choices=["by_cell"], default="by_cell")
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--chunksize", type=int, default=250_000)
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing non-empty output directory.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    summaries = build_all_features_low_memory(
        input_root=args.input_root,
        output_root=args.output_root,
        source_mode=args.source_mode,
        chunksize=args.chunksize,
        overwrite=args.overwrite,
    )
    for summary in summaries:
        print(
            f"{summary.feature_table}: {summary.status}, rows_in={summary.rows_in}, "
            f"rows_out={summary.rows_out}, chunks_read={summary.chunks_read}"
        )


if __name__ == "__main__":
    main()
