"""Preprocess NASA lithium-ion battery .mat files into project data folders."""

from __future__ import annotations

import argparse
import json
import math
import shutil
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
from scipy.io import loadmat


BATTERY_TYPE = "li_ion"
DATASET = "nasa"


@dataclass
class BatteryManifest:
    dataset: str
    battery_type: str
    cell_id: str
    raw_file: str
    processed_dir: str
    charge_cycles: int
    discharge_cycles: int
    impedance_cycles: int
    total_cycles: int


def matlab_time_to_iso(value: Any) -> str:
    parts = np.asarray(value).astype(float).tolist()
    if len(parts) != 6 or any(math.isnan(x) for x in parts):
        return ""
    year, month, day, hour, minute, second = parts
    whole_second = int(second)
    microsecond = int(round((second - whole_second) * 1_000_000))
    return datetime(
        int(year),
        int(month),
        int(day),
        int(hour),
        int(minute),
        whole_second,
        microsecond,
    ).isoformat()


def as_1d(value: Any) -> np.ndarray:
    arr = np.asarray(value)
    if arr.ndim == 0:
        return np.asarray([arr.item()])
    return arr.reshape(-1)


def scalar_or_nan(value: Any) -> float:
    arr = as_1d(value)
    if arr.size == 0:
        return float("nan")
    item = arr[0]
    if np.iscomplexobj(item):
        return float(np.real(item))
    try:
        return float(item)
    except (TypeError, ValueError):
        return float("nan")


def numeric_stats(prefix: str, value: Any) -> dict[str, float]:
    arr = as_1d(value)
    if arr.size == 0 or np.iscomplexobj(arr):
        return {}
    arr = arr.astype(float)
    return {
        f"{prefix}_min": float(np.nanmin(arr)),
        f"{prefix}_max": float(np.nanmax(arr)),
        f"{prefix}_mean": float(np.nanmean(arr)),
    }


def append_measurement_rows(
    rows: list[dict[str, Any]],
    cell_id: str,
    cycle_index: int,
    cycle_type: str,
    start_time: str,
    ambient_temperature_c: float,
    data: Any,
) -> None:
    fields = data._fieldnames
    time = as_1d(getattr(data, "Time", []))
    sample_count = int(time.size)
    arrays = {
        field: as_1d(getattr(data, field))
        for field in fields
        if field != "Capacity" and not np.iscomplexobj(as_1d(getattr(data, field)))
    }
    capacity = scalar_or_nan(getattr(data, "Capacity", np.nan)) if "Capacity" in fields else np.nan

    for sample_index in range(sample_count):
        row = {
            "dataset": DATASET,
            "battery_type": BATTERY_TYPE,
            "cell_id": cell_id,
            "cycle_index": cycle_index,
            "cycle_type": cycle_type,
            "sample_index": sample_index,
            "start_time": start_time,
            "ambient_temperature_c": ambient_temperature_c,
            "capacity_ah": capacity,
        }
        for field, arr in arrays.items():
            if sample_index < arr.size:
                row[to_column_name(field)] = arr[sample_index]
        rows.append(row)


def append_impedance_rows(
    rows: list[dict[str, Any]],
    cell_id: str,
    cycle_index: int,
    start_time: str,
    ambient_temperature_c: float,
    data: Any,
) -> None:
    fields = data._fieldnames
    complex_fields = [
        field for field in fields if np.iscomplexobj(as_1d(getattr(data, field)))
    ]
    max_count = max((as_1d(getattr(data, field)).size for field in complex_fields), default=0)
    for sample_index in range(max_count):
        row = {
            "dataset": DATASET,
            "battery_type": BATTERY_TYPE,
            "cell_id": cell_id,
            "cycle_index": cycle_index,
            "cycle_type": "impedance",
            "sample_index": sample_index,
            "start_time": start_time,
            "ambient_temperature_c": ambient_temperature_c,
            "re_ohm": scalar_or_nan(getattr(data, "Re", np.nan)),
            "rct_ohm": scalar_or_nan(getattr(data, "Rct", np.nan)),
        }
        for field in complex_fields:
            arr = as_1d(getattr(data, field))
            if sample_index >= arr.size:
                continue
            value = arr[sample_index]
            base = to_column_name(field)
            row[f"{base}_real"] = float(np.real(value))
            row[f"{base}_imag"] = float(np.imag(value))
            row[f"{base}_magnitude"] = float(np.abs(value))
            row[f"{base}_phase_rad"] = float(np.angle(value))
        rows.append(row)


def to_column_name(field: str) -> str:
    mapping = {
        "Voltage_measured": "voltage_measured_v",
        "Current_measured": "current_measured_a",
        "Temperature_measured": "temperature_measured_c",
        "Current_charge": "current_charge_a",
        "Voltage_charge": "voltage_charge_v",
        "Current_load": "current_load_a",
        "Voltage_load": "voltage_load_v",
        "Time": "elapsed_time_s",
        "Re": "re_ohm",
        "Rct": "rct_ohm",
    }
    return mapping.get(field, field.lower())


def preprocess_file(mat_file: Path, project_root: Path) -> BatteryManifest:
    cell_id = mat_file.stem
    raw_dir = project_root / "data" / "raw" / DATASET / BATTERY_TYPE / cell_id
    processed_dir = project_root / "data" / "processed" / DATASET / BATTERY_TYPE / cell_id
    raw_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)

    raw_copy = raw_dir / mat_file.name
    shutil.copy2(mat_file, raw_copy)

    mat = loadmat(mat_file, squeeze_me=True, struct_as_record=False)
    root = mat[cell_id]

    cycle_summary_rows: list[dict[str, Any]] = []
    charge_rows: list[dict[str, Any]] = []
    discharge_rows: list[dict[str, Any]] = []
    impedance_rows: list[dict[str, Any]] = []

    counts = {"charge": 0, "discharge": 0, "impedance": 0}

    for cycle_index, cycle in enumerate(root.cycle, start=1):
        cycle_type = str(cycle.type)
        counts[cycle_type] = counts.get(cycle_type, 0) + 1
        data = cycle.data
        fields = data._fieldnames
        start_time = matlab_time_to_iso(cycle.time)
        ambient_temperature_c = float(cycle.ambient_temperature)
        sample_count = int(as_1d(getattr(data, "Time", [])).size)

        summary = {
            "dataset": DATASET,
            "battery_type": BATTERY_TYPE,
            "cell_id": cell_id,
            "cycle_index": cycle_index,
            "cycle_type": cycle_type,
            "cycle_number_within_type": counts[cycle_type],
            "start_time": start_time,
            "ambient_temperature_c": ambient_temperature_c,
            "sample_count": sample_count,
            "capacity_ah": scalar_or_nan(getattr(data, "Capacity", np.nan))
            if "Capacity" in fields
            else np.nan,
            "re_ohm": scalar_or_nan(getattr(data, "Re", np.nan)) if "Re" in fields else np.nan,
            "rct_ohm": scalar_or_nan(getattr(data, "Rct", np.nan)) if "Rct" in fields else np.nan,
        }
        if "Time" in fields and sample_count:
            time = as_1d(getattr(data, "Time")).astype(float)
            summary["duration_s"] = float(np.nanmax(time) - np.nanmin(time))
        for field in fields:
            summary.update(numeric_stats(to_column_name(field), getattr(data, field)))
        cycle_summary_rows.append(summary)

        if cycle_type == "charge":
            append_measurement_rows(
                charge_rows,
                cell_id,
                cycle_index,
                cycle_type,
                start_time,
                ambient_temperature_c,
                data,
            )
        elif cycle_type == "discharge":
            append_measurement_rows(
                discharge_rows,
                cell_id,
                cycle_index,
                cycle_type,
                start_time,
                ambient_temperature_c,
                data,
            )
        elif cycle_type == "impedance":
            append_impedance_rows(
                impedance_rows,
                cell_id,
                cycle_index,
                start_time,
                ambient_temperature_c,
                data,
            )

    pd.DataFrame(cycle_summary_rows).to_csv(processed_dir / "cycle_summary.csv", index=False)
    pd.DataFrame(charge_rows).to_csv(processed_dir / "charge_timeseries.csv", index=False)
    pd.DataFrame(discharge_rows).to_csv(processed_dir / "discharge_timeseries.csv", index=False)
    pd.DataFrame(impedance_rows).to_csv(processed_dir / "impedance_spectra.csv", index=False)

    manifest = BatteryManifest(
        dataset=DATASET,
        battery_type=BATTERY_TYPE,
        cell_id=cell_id,
        raw_file=str(raw_copy.relative_to(project_root)),
        processed_dir=str(processed_dir.relative_to(project_root)),
        charge_cycles=counts.get("charge", 0),
        discharge_cycles=counts.get("discharge", 0),
        impedance_cycles=counts.get("impedance", 0),
        total_cycles=sum(counts.values()),
    )
    with (processed_dir / "manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(asdict(manifest), fh, indent=2)
    return manifest


def write_dataset_manifest(project_root: Path, manifests: list[BatteryManifest]) -> None:
    manifest_dir = project_root / "data" / "processed" / DATASET / BATTERY_TYPE
    manifest_dir.mkdir(parents=True, exist_ok=True)
    rows = [asdict(item) for item in manifests]
    pd.DataFrame(rows).to_csv(manifest_dir / "dataset_manifest.csv", index=False)
    with (manifest_dir / "dataset_manifest.json").open("w", encoding="utf-8") as fh:
        json.dump(rows, fh, indent=2)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("mat_files", type=Path, nargs="+")
    args = parser.parse_args()

    manifests = [preprocess_file(path, args.project_root) for path in args.mat_files]
    write_dataset_manifest(args.project_root, manifests)

    for manifest in manifests:
        print(
            f"{manifest.cell_id}: charge={manifest.charge_cycles}, "
            f"discharge={manifest.discharge_cycles}, impedance={manifest.impedance_cycles}"
        )


if __name__ == "__main__":
    main()
