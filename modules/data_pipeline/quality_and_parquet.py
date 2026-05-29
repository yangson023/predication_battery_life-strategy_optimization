"""Generate data quality reports and optional Parquet files for processed data."""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


REQUIRED_CELL_FILES = [
    "cycle_summary.csv",
    "charge_timeseries.csv",
    "discharge_timeseries.csv",
    "impedance_spectra.csv",
    "manifest.json",
]

PHYSICAL_RANGES = {
    "voltage": (0.0, 5.0),
    "current": (-10.0, 10.0),
    "temperature": (-20.0, 80.0),
    "capacity": (0.0, 5.0),
    "impedance": (0.0, 100.0),
}


@dataclass
class FileQualityReport:
    dataset: str
    battery_type: str
    cell_id: str
    file_name: str
    rows: int
    columns: int
    missing_cells: int
    missing_ratio: float
    duplicate_rows: int
    time_monotonic_failures: int
    voltage_out_of_range: int
    current_out_of_range: int
    temperature_out_of_range: int
    capacity_out_of_range: int
    impedance_out_of_range: int
    capacity_jump_warnings: int
    parquet_written: bool
    parquet_path: str
    parquet_status: str
    status: str
    notes: str


def parquet_engine_available() -> bool:
    return (
        importlib.util.find_spec("pyarrow") is not None
        or importlib.util.find_spec("fastparquet") is not None
    )


def out_of_range_count(
    frame: pd.DataFrame,
    name_part: str,
    low: float,
    high: float,
    excluded_parts: tuple[str, ...] = (),
) -> int:
    total = 0
    for column in frame.columns:
        lowered = column.lower()
        if name_part not in lowered or any(part in lowered for part in excluded_parts):
            continue
        values = pd.to_numeric(frame[column], errors="coerce")
        total += int(values.lt(low).sum() + values.gt(high).sum())
    return total


def impedance_out_of_range_count(frame: pd.DataFrame) -> int:
    total = 0
    scalar_columns = [column for column in frame.columns if column.lower() in {"re_ohm", "rct_ohm"}]
    magnitude_columns = [
        column
        for column in frame.columns
        if "impedance" in column.lower() and column.lower().endswith("_magnitude")
    ]
    for column in scalar_columns + magnitude_columns:
        values = pd.to_numeric(frame[column], errors="coerce")
        low, high = PHYSICAL_RANGES["impedance"]
        total += int(values.lt(low).sum() + values.gt(high).sum())
    return total


def count_time_monotonic_failures(frame: pd.DataFrame) -> int:
    if "elapsed_time_s" not in frame.columns or "cycle_index" not in frame.columns:
        return 0
    failures = 0
    for _, group in frame.groupby("cycle_index", sort=False):
        values = pd.to_numeric(group["elapsed_time_s"], errors="coerce").dropna()
        if len(values) > 1 and (values.diff().dropna() < 0).any():
            failures += 1
    return failures


def count_capacity_jump_warnings(frame: pd.DataFrame, threshold_ratio: float) -> int:
    if "cycle_type" not in frame.columns or "capacity_ah" not in frame.columns:
        return 0
    discharge = (
        frame.loc[frame["cycle_type"].eq("discharge"), ["cycle_index", "capacity_ah"]]
        .dropna()
        .sort_values("cycle_index")
    )
    if len(discharge) < 2:
        return 0
    capacity = pd.to_numeric(discharge["capacity_ah"], errors="coerce").dropna()
    if len(capacity) < 2:
        return 0
    relative_jump = capacity.diff().abs() / capacity.shift(1).replace(0, np.nan)
    return int(relative_jump.gt(threshold_ratio).sum())


def summarize_csv(
    csv_path: Path,
    root: Path,
    dataset: str,
    battery_type: str,
    cell_id: str,
    has_parquet_engine: bool,
    capacity_jump_threshold: float,
) -> FileQualityReport:
    notes: list[str] = []
    parquet_written = False
    parquet_path = csv_path.with_suffix(".parquet")
    parquet_status = "skipped_no_engine"

    try:
        frame = pd.read_csv(csv_path)
    except Exception as exc:  # pragma: no cover - defensive reporting
        return FileQualityReport(
            dataset,
            battery_type,
            cell_id,
            csv_path.name,
            0,
            0,
            0,
            math.nan,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            0,
            False,
            "",
            "read_failed",
            "fail",
            str(exc),
        )

    rows, columns = frame.shape
    missing_cells = int(frame.isna().sum().sum())
    missing_ratio = float(missing_cells / (rows * columns)) if rows and columns else 0.0
    duplicate_rows = int(frame.duplicated().sum())
    time_failures = count_time_monotonic_failures(frame)
    voltage_oob = out_of_range_count(frame, "voltage", *PHYSICAL_RANGES["voltage"])
    current_oob = (
        0
        if csv_path.name == "impedance_spectra.csv"
        else out_of_range_count(frame, "current", *PHYSICAL_RANGES["current"])
    )
    temperature_oob = out_of_range_count(
        frame, "temperature", *PHYSICAL_RANGES["temperature"]
    )
    capacity_oob = out_of_range_count(frame, "capacity", *PHYSICAL_RANGES["capacity"])
    impedance_oob = impedance_out_of_range_count(frame)
    capacity_jumps = count_capacity_jump_warnings(frame, capacity_jump_threshold)

    if has_parquet_engine:
        try:
            frame.to_parquet(parquet_path, index=False)
            parquet_written = True
            parquet_status = "written"
        except Exception as exc:  # pragma: no cover - depends on optional engines
            parquet_status = "write_failed"
            notes.append(f"parquet_write_failed={exc}")

    if rows == 0 or columns == 0:
        status = "fail"
        notes.append("empty_file")
    elif time_failures or voltage_oob or current_oob or temperature_oob:
        status = "warn"
    elif duplicate_rows or capacity_oob or impedance_oob or capacity_jumps:
        status = "warn"
    else:
        status = "pass"

    return FileQualityReport(
        dataset=dataset,
        battery_type=battery_type,
        cell_id=cell_id,
        file_name=csv_path.name,
        rows=int(rows),
        columns=int(columns),
        missing_cells=missing_cells,
        missing_ratio=missing_ratio,
        duplicate_rows=duplicate_rows,
        time_monotonic_failures=time_failures,
        voltage_out_of_range=voltage_oob,
        current_out_of_range=current_oob,
        temperature_out_of_range=temperature_oob,
        capacity_out_of_range=capacity_oob,
        impedance_out_of_range=impedance_oob,
        capacity_jump_warnings=capacity_jumps,
        parquet_written=parquet_written,
        parquet_path=str(parquet_path.relative_to(root)) if parquet_written else "",
        parquet_status=parquet_status,
        status=status,
        notes="; ".join(notes),
    )


def missing_file_reports(
    cell_dir: Path,
    root: Path,
    dataset: str,
    battery_type: str,
) -> list[FileQualityReport]:
    reports = []
    cell_id = cell_dir.name
    for file_name in REQUIRED_CELL_FILES:
        if (cell_dir / file_name).exists():
            continue
        reports.append(
            FileQualityReport(
                dataset,
                battery_type,
                cell_id,
                file_name,
                0,
                0,
                0,
                0.0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                0,
                False,
                "",
                "not_applicable",
                "fail",
                f"missing_required_file={file_name}",
            )
        )
    return reports


def load_metadata(metadata_path: Path) -> pd.DataFrame:
    metadata = pd.read_csv(metadata_path)
    required = {"dataset", "battery_type", "cell_id", "discharge_cutoff_voltage_v"}
    missing = required - set(metadata.columns)
    if missing:
        raise ValueError(f"Metadata missing required columns: {sorted(missing)}")
    return metadata


def write_cell_json(cell_dir: Path, reports: list[FileQualityReport]) -> None:
    with (cell_dir / "quality_report.json").open("w", encoding="utf-8") as fh:
        json.dump([asdict(report) for report in reports], fh, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--processed-root",
        type=Path,
        default=Path("data/processed/nasa/li_ion"),
    )
    parser.add_argument(
        "--metadata",
        type=Path,
        default=Path("configs/datasets/nasa_li_ion_cells.csv"),
    )
    parser.add_argument("--capacity-jump-threshold", type=float, default=0.05)
    args = parser.parse_args()

    metadata = load_metadata(args.metadata)
    dataset_values = metadata["dataset"].unique()
    battery_type_values = metadata["battery_type"].unique()
    dataset = dataset_values[0] if len(dataset_values) == 1 else "mixed"
    battery_type = battery_type_values[0] if len(battery_type_values) == 1 else "mixed"
    known_cells = set(metadata["cell_id"].astype(str))
    has_parquet_engine = parquet_engine_available()

    all_reports: list[FileQualityReport] = []
    cell_dirs = [path for path in sorted(args.processed_root.iterdir()) if path.is_dir()]
    for cell_dir in cell_dirs:
        cell_id = cell_dir.name
        cell_reports = missing_file_reports(cell_dir, args.processed_root, dataset, battery_type)
        if cell_id not in known_cells:
            cell_reports.append(
                FileQualityReport(
                    dataset,
                    battery_type,
                    cell_id,
                    "metadata",
                    0,
                    0,
                    0,
                    0.0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    0,
                    False,
                    "",
                    "not_applicable",
                    "warn",
                    "cell_id_not_found_in_metadata",
                )
            )
        for csv_path in sorted(cell_dir.glob("*.csv")):
            cell_reports.append(
                summarize_csv(
                    csv_path=csv_path,
                    root=args.processed_root,
                    dataset=dataset,
                    battery_type=battery_type,
                    cell_id=cell_id,
                    has_parquet_engine=has_parquet_engine,
                    capacity_jump_threshold=args.capacity_jump_threshold,
                )
            )
        write_cell_json(cell_dir, cell_reports)
        all_reports.extend(cell_reports)

    report_frame = pd.DataFrame([asdict(report) for report in all_reports])
    args.processed_root.mkdir(parents=True, exist_ok=True)
    report_frame.to_csv(args.processed_root / "quality_report.csv", index=False)
    with (args.processed_root / "quality_report.json").open("w", encoding="utf-8") as fh:
        json.dump([asdict(report) for report in all_reports], fh, indent=2)

    status_counts = report_frame["status"].value_counts().to_dict() if not report_frame.empty else {}
    parquet_counts = (
        report_frame["parquet_status"].value_counts().to_dict() if not report_frame.empty else {}
    )
    print(f"quality rows={len(report_frame)} status={status_counts}")
    print(f"parquet_engine={has_parquet_engine} parquet_status={parquet_counts}")


if __name__ == "__main__":
    main()
