"""Parse BTSDA three-layer CSV exports for LMB tiny validation.

The parser is intentionally conservative:
- it reads cycle/step/record CSV exports from one cell directory,
- writes normalized cycle and step tables,
- writes only a bounded record sample by default,
- emits schema and data-quality gates,
- never enables model training.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Iterable


CYCLE_REQUIRED = [
    "循环号",
    "起始绝对时间",
    "结束绝对时间",
    "充电容量(mAh)",
    "放电容量(mAh)",
    "充放电效率(%)",
    "中值电压(V)",
    "容量保持率(%)",
]

STEP_REQUIRED = [
    "循环号",
    "工步号",
    "工步序号",
    "工步类型",
    "工步时间",
    "起始绝对时间",
    "结束绝对时间",
    "容量(mAh)",
    "充电容量(mAh)",
    "放电容量(mAh)",
    "起始电压(V)",
    "结束电压(V)",
    "充电中值电压(V)",
    "放电中值电压(V)",
]

RECORD_REQUIRED = [
    "数据序号",
    "循环号",
    "工步号",
    "工步类型",
    "时间",
    "总时间",
    "电流(mA)",
    "电压(V)",
    "容量(mAh)",
    "绝对时间",
    "功率(mW)",
]

CYCLE_MAP = {
    "cycle_index": "循环号",
    "cycle_start_time": "起始绝对时间",
    "cycle_end_time": "结束绝对时间",
    "charge_capacity_mah": "充电容量(mAh)",
    "discharge_capacity_mah": "放电容量(mAh)",
    "coulombic_efficiency_percent": "充放电效率(%)",
    "median_voltage_v": "中值电压(V)",
    "capacity_retention_percent": "容量保持率(%)",
}

STEP_MAP = {
    "cycle_index": "循环号",
    "step_id": "工步号",
    "step_sequence": "工步序号",
    "step_type": "工步类型",
    "step_duration": "工步时间",
    "step_start_time": "起始绝对时间",
    "step_end_time": "结束绝对时间",
    "capacity_mah": "容量(mAh)",
    "charge_capacity_mah": "充电容量(mAh)",
    "discharge_capacity_mah": "放电容量(mAh)",
    "start_voltage_v": "起始电压(V)",
    "end_voltage_v": "结束电压(V)",
    "charge_median_voltage_v": "充电中值电压(V)",
    "discharge_median_voltage_v": "放电中值电压(V)",
}

RECORD_MAP = {
    "record_index": "数据序号",
    "cycle_index": "循环号",
    "step_id": "工步号",
    "step_type": "工步类型",
    "step_time": "时间",
    "total_time": "总时间",
    "current_ma": "电流(mA)",
    "voltage_v": "电压(V)",
    "capacity_mah": "容量(mAh)",
    "absolute_time": "绝对时间",
    "power_mw": "功率(mW)",
}

NUMERIC_OUTPUT_COLUMNS = {
    "cycle_index",
    "charge_capacity_mah",
    "discharge_capacity_mah",
    "coulombic_efficiency_percent",
    "median_voltage_v",
    "capacity_retention_percent",
    "step_id",
    "step_sequence",
    "capacity_mah",
    "start_voltage_v",
    "end_voltage_v",
    "charge_median_voltage_v",
    "discharge_median_voltage_v",
    "record_index",
    "current_ma",
    "voltage_v",
    "power_mw",
}


@dataclass(frozen=True)
class LayerTable:
    layer: str
    path: Path
    header: list[str]
    rows: list[dict[str, str]]
    md5: str


def clean_header(header: list[str]) -> list[str]:
    return [column.strip() for column in header if column.strip()]


def repair_mojibake(value: str) -> str:
    """Repair UTF-8 text accidentally decoded as GBK when reversible.

    Some BTSDA exports contain mixed text encodings in categorical values while
    keeping GBK-compatible headers. If the conversion is not possible, keep the
    original value.
    """
    if not value:
        return value
    try:
        repaired = value.encode("gbk").decode("utf-8")
    except UnicodeError:
        try:
            repaired = value.encode("gbk", errors="replace").decode("utf-8", errors="replace")
        except UnicodeError:
            return value
    if "\ufffd" in repaired and "\ufffd" not in value:
        return value
    return repaired if repaired else value


def file_md5(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_csv_header(path: Path, encoding: str) -> list[str]:
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle)
        return clean_header(next(reader))


def csv_data_row_count(path: Path, encoding: str) -> int:
    try:
        with path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.reader(handle)
            next(reader, None)
            return sum(1 for row in reader if any(str(cell).strip() for cell in row))
    except Exception:
        return -1


def read_csv_table(path: Path, encoding: str) -> tuple[list[str], list[dict[str, str]]]:
    with path.open("r", encoding=encoding, newline="") as handle:
        reader = csv.reader(handle)
        raw_header = next(reader)
        header = clean_header(raw_header)
        rows = []
        for raw_row in reader:
            if not any(str(cell).strip() for cell in raw_row):
                continue
            row = {
                header[index]: repair_mojibake(raw_row[index].strip()) if index < len(raw_row) else ""
                for index in range(len(header))
            }
            rows.append(row)
    return header, rows


def required_for_layer(layer: str) -> list[str]:
    return {
        "cycle": CYCLE_REQUIRED,
        "step": STEP_REQUIRED,
        "record": RECORD_REQUIRED,
    }[layer]


def layer_match_score(path: Path, layer: str, encoding: str) -> tuple[int, int]:
    try:
        header = read_csv_header(path, encoding)
    except Exception:
        return (-1, -1)
    fields = set(header)
    required = required_for_layer(layer)
    return (sum(1 for column in required if column in fields), path.stat().st_size)


def export_suffix(path: Path) -> str:
    match = re.search(r"-(\d+)$", path.stem)
    return match.group(1) if match else path.stem


def find_layer_files(
    input_root: Path,
    encoding: str,
    requested_export_suffix: str | None = None,
) -> tuple[dict[str, Path], list[dict[str, object]]]:
    files = [path for path in input_root.iterdir() if path.is_file() and path.suffix.lower() == ".csv"]
    layer_files: dict[str, Path] = {}
    candidate_rows: list[dict[str, object]] = []
    scored_by_layer: dict[str, list[tuple[int, int, Path]]] = {}
    for layer in ["cycle", "step", "record"]:
        candidates = [path for path in files if layer in path.name.lower()]
        scored = []
        for path in candidates:
            score, size = layer_match_score(path, layer, encoding)
            scored.append((score, size, path))
            candidate_rows.append(
                {
                    "candidate_layer": layer,
                    "file_name": path.name,
                    "export_suffix": export_suffix(path),
                    "required_fields_matched": score,
                    "file_size_bytes": size,
                }
            )
        scored_by_layer[layer] = scored

    valid_by_layer = {
        layer: [item for item in scored if item[0] == len(required_for_layer(layer))]
        for layer, scored in scored_by_layer.items()
    }
    if requested_export_suffix:
        for layer in ["cycle", "step", "record"]:
            matches = [
                item
                for item in valid_by_layer.get(layer, [])
                if export_suffix(item[2]) == requested_export_suffix
            ]
            if matches:
                matches.sort(key=lambda item: (item[1], item[2].name), reverse=True)
                layer_files[layer] = matches[0][2]
        return layer_files, candidate_rows

    common_suffixes = set.intersection(
        *[
            {export_suffix(path) for _, _, path in valid_by_layer.get(layer, [])}
            for layer in ["cycle", "step", "record"]
        ]
    ) if all(valid_by_layer.get(layer) for layer in ["cycle", "step", "record"]) else set()
    if common_suffixes:
        grouped: list[tuple[int, int, str, dict[str, Path]]] = []
        for suffix in common_suffixes:
            group: dict[str, Path] = {}
            total_size = 0
            for layer in ["cycle", "step", "record"]:
                matches = [item for item in valid_by_layer[layer] if export_suffix(item[2]) == suffix]
                matches.sort(key=lambda item: (item[1], item[2].name), reverse=True)
                total_size += matches[0][1]
                group[layer] = matches[0][2]
            cycle_rows = csv_data_row_count(group["cycle"], encoding)
            grouped.append((cycle_rows, total_size, suffix, group))
        grouped.sort(key=lambda item: (item[0], item[1], item[2]), reverse=True)
        layer_files = grouped[0][3]
    else:
        for layer in ["cycle", "step", "record"]:
            scored = scored_by_layer.get(layer, [])
            valid = valid_by_layer.get(layer, [])
            pool = valid or scored
            if pool:
                pool.sort(key=lambda item: (item[0], item[1], item[2].name), reverse=True)
                layer_files[layer] = pool[0][2]
    return layer_files, candidate_rows


def load_layers(
    input_root: Path,
    encoding: str,
    requested_export_suffix: str | None = None,
) -> tuple[dict[str, LayerTable], list[dict[str, object]]]:
    files, candidates = find_layer_files(input_root, encoding, requested_export_suffix)
    checks: list[dict[str, object]] = []
    for candidate in candidates:
        checks.append(
            gate_row(
                "layer_candidate_scored",
                str(candidate["candidate_layer"]),
                True,
                f"{candidate['file_name']} suffix={candidate['export_suffix']} matched={candidate['required_fields_matched']} size={candidate['file_size_bytes']}",
            )
        )
    if requested_export_suffix:
        checks.append(
            gate_row(
                "requested_export_suffix",
                "all",
                True,
                f"requested suffix={requested_export_suffix}",
            )
        )
    layers: dict[str, LayerTable] = {}
    for layer in ["cycle", "step", "record"]:
        path = files.get(layer)
        if path is None:
            checks.append(gate_row("layer_present", layer, False, "missing layer CSV"))
            continue
        header, rows = read_csv_table(path, encoding)
        layers[layer] = LayerTable(layer=layer, path=path, header=header, rows=rows, md5=file_md5(path))
        checks.append(gate_row("layer_present", layer, True, str(path)))
        checks.append(gate_row("layer_has_rows", layer, bool(rows), f"rows={len(rows)}"))
    return layers, checks


def gate_row(check_name: str, layer: str, passed: bool, detail: str) -> dict[str, object]:
    return {
        "check_name": check_name,
        "layer": layer,
        "status": "pass" if passed else "fail",
        "detail": detail,
    }


def required_field_checks(layer: str, header: list[str], required: list[str]) -> list[dict[str, object]]:
    checks = []
    fields = set(header)
    for column in required:
        checks.append(gate_row("required_field_present", layer, column in fields, column))
    return checks


def normalize_row(row: dict[str, str], mapping: dict[str, str], dataset_name: str, cell_type: str) -> dict[str, object]:
    output: dict[str, object] = {
        "dataset_name": dataset_name,
        "cell_type": cell_type,
    }
    for out_col, in_col in mapping.items():
        value = row.get(in_col, "")
        if out_col in NUMERIC_OUTPUT_COLUMNS:
            output[out_col] = parse_float(value)
        else:
            output[out_col] = value
    return output


def parse_float(value: object) -> float | str:
    text = str(value or "").strip()
    if not text:
        return ""
    try:
        return float(text)
    except ValueError:
        return text


def parse_datetime(value: object) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    for fmt in ["%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"]:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def write_csv(path: Path, rows: Iterable[dict[str, object]], columns: list[str] | None = None) -> None:
    rows = list(rows)
    if columns is None:
        columns = list(rows[0].keys()) if rows else []
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in columns})


def cycle_indices(rows: list[dict[str, str]], column: str = "循环号") -> set[int]:
    values = set()
    for row in rows:
        value = parse_float(row.get(column))
        if isinstance(value, float):
            values.add(int(value))
    return values


def sampling_interval_mode(record_rows: list[dict[str, str]]) -> float | str:
    deltas = []
    previous = None
    for row in record_rows[:5000]:
        current = parse_datetime(row.get("绝对时间"))
        if previous and current:
            delta = (current - previous).total_seconds()
            if delta > 0:
                deltas.append(delta)
        if current:
            previous = current
    if not deltas:
        return ""
    return Counter(deltas).most_common(1)[0][0]


def build_quality_flags(cycle_rows: list[dict[str, str]], record_rows: list[dict[str, str]]) -> list[dict[str, object]]:
    flags: list[dict[str, object]] = []
    for row in cycle_rows:
        cycle = parse_float(row.get("循环号"))
        charge = parse_float(row.get("充电容量(mAh)"))
        discharge = parse_float(row.get("放电容量(mAh)"))
        ce = parse_float(row.get("充放电效率(%)"))
        row_flags = []
        if isinstance(ce, float) and ce > 103:
            row_flags.append("ce_gt_103")
        if isinstance(ce, float) and ce < 80:
            row_flags.append("ce_lt_80")
        if isinstance(charge, float) and isinstance(discharge, float) and (charge < 1.4 or discharge < 1.4):
            row_flags.append("incomplete_charge_or_discharge_capacity")
        if row_flags:
            flags.append(
                {
                    "source_layer": "cycle",
                    "cycle_index": int(cycle) if isinstance(cycle, float) else "",
                    "flags": ";".join(row_flags),
                    "charge_capacity_mah": charge,
                    "discharge_capacity_mah": discharge,
                    "coulombic_efficiency_percent": ce,
                }
            )
    for row in record_rows:
        voltage = parse_float(row.get("电压(V)"))
        if isinstance(voltage, float) and abs(voltage) > 2.0:
            cycle = parse_float(row.get("循环号"))
            flags.append(
                {
                    "source_layer": "record",
                    "cycle_index": int(cycle) if isinstance(cycle, float) else "",
                    "flags": "record_voltage_abs_gt_2v",
                    "charge_capacity_mah": "",
                    "discharge_capacity_mah": "",
                    "coulombic_efficiency_percent": "",
                }
            )
    return flags


def feature_direction(cell_type: str) -> str:
    cell_type_lower = cell_type.lower()
    if "li||li" in cell_type_lower or "symmetric" in cell_type_lower:
        return "Li||Li: polarization growth, voltage hysteresis, plating/stripping overpotential, voltage instability."
    if "li||cu" in cell_type_lower or "ce" in cell_type_lower:
        return "Li||Cu: CE stability, plating/stripping efficiency, incomplete-cycle filtering, soft-short warning."
    return "Unknown LMB-related cell: metadata recovery required before feature claims."


def parse_three_layer_export(
    input_root: Path,
    output_root: Path,
    dataset_name: str,
    cell_type: str,
    encoding: str = "gbk",
    overwrite: bool = False,
    record_sample_rows: int = 5000,
    export_suffix_filter: str | None = None,
) -> dict[str, object]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root already exists and is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    layers, checks = load_layers(input_root, encoding, export_suffix_filter)
    if "cycle" in layers:
        checks.extend(required_field_checks("cycle", layers["cycle"].header, CYCLE_REQUIRED))
    if "step" in layers:
        checks.extend(required_field_checks("step", layers["step"].header, STEP_REQUIRED))
    if "record" in layers:
        checks.extend(required_field_checks("record", layers["record"].header, RECORD_REQUIRED))

    if len(layers) == 3:
        md5s = [table.md5 for table in layers.values()]
        checks.append(gate_row("layers_are_distinct", "all", len(set(md5s)) == 3, "cycle/step/record md5 uniqueness"))

        cycle_set = cycle_indices(layers["cycle"].rows)
        step_set = cycle_indices(layers["step"].rows)
        record_set = cycle_indices(layers["record"].rows)
        aligned = bool(cycle_set) and cycle_set.issubset(step_set) and cycle_set.issubset(record_set)
        checks.append(
            gate_row(
                "cycle_index_alignment",
                "all",
                aligned,
                f"cycle={len(cycle_set)}, step={len(step_set)}, record={len(record_set)}",
            )
        )
    else:
        checks.append(gate_row("layers_are_distinct", "all", False, "not all layers are present"))
        checks.append(gate_row("cycle_index_alignment", "all", False, "not all layers are present"))

    record_has_core = False
    sample_interval: float | str = ""
    step_type_counts: dict[str, int] = {}
    quality_flags: list[dict[str, object]] = []

    if "cycle" in layers:
        cycle_norm = [normalize_row(row, CYCLE_MAP, dataset_name, cell_type) for row in layers["cycle"].rows]
        write_csv(output_root / "normalized_cycle.csv", cycle_norm)
    if "step" in layers:
        step_norm = [normalize_row(row, STEP_MAP, dataset_name, cell_type) for row in layers["step"].rows]
        write_csv(output_root / "normalized_step.csv", step_norm)
        step_type_counts = dict(Counter(row.get("工步类型", "") for row in layers["step"].rows))
    if "record" in layers:
        record_rows = layers["record"].rows
        record_norm = [
            normalize_row(row, RECORD_MAP, dataset_name, cell_type)
            for row in record_rows[: max(record_sample_rows, 0)]
        ]
        write_csv(output_root / "normalized_record_sample.csv", record_norm)
        record_has_core = all(column in layers["record"].header for column in ["电压(V)", "电流(mA)", "绝对时间", "时间"])
        sample_interval = sampling_interval_mode(record_rows)
        checks.append(gate_row("record_has_voltage_current_time", "record", record_has_core, "voltage/current/time columns"))
    else:
        checks.append(gate_row("record_has_voltage_current_time", "record", False, "record layer missing"))

    if "cycle" in layers and "record" in layers:
        quality_flags = build_quality_flags(layers["cycle"].rows, layers["record"].rows)
        write_csv(output_root / "quality_flags.csv", quality_flags, [
            "source_layer",
            "cycle_index",
            "flags",
            "charge_capacity_mah",
            "discharge_capacity_mah",
            "coulombic_efficiency_percent",
        ])

    checks.append(gate_row("training_allowed_now", "all", False, "always false for intake tiny validation"))
    write_csv(output_root / "schema_check.csv", checks, ["check_name", "layer", "status", "detail"])

    report = {
        "dataset_name": dataset_name,
        "cell_type": cell_type,
        "input_root": str(input_root),
        "output_root": str(output_root),
        "encoding": encoding,
        "export_suffix_filter": export_suffix_filter or "",
        "layers_present": sorted(layers.keys()),
        "layer_rows": {layer: len(table.rows) for layer, table in layers.items()},
        "layer_files": {layer: str(table.path) for layer, table in layers.items()},
        "all_schema_gates_passed": all(row["status"] == "pass" for row in checks if row["check_name"] != "training_allowed_now"),
        "record_layer_available": "record" in layers,
        "record_has_voltage_current_time": record_has_core,
        "record_sampling_interval_mode_s": sample_interval,
        "step_type_counts": step_type_counts,
        "quality_flag_count": len(quality_flags),
        "feature_direction": feature_direction(cell_type),
        "training_allowed_now": False,
        "training_gate_note": "Tiny validation and schema audit only. Training requires multi-cell label audit and reviewed trainability gates.",
    }
    with (output_root / "intake_schema_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
    write_markdown_report(output_root / "intake_schema_report.md", report)
    return report


def write_markdown_report(path: Path, report: dict[str, object]) -> None:
    lines = [
        f"# BTSDA LMB Intake Schema Report: {report['dataset_name']}",
        "",
        "This is a tiny-validation intake report. It is not model performance.",
        "",
        "## Gate Summary",
        "",
        f"- Cell type: `{report['cell_type']}`",
        f"- Export suffix filter: `{report['export_suffix_filter']}`",
        f"- Layers present: `{', '.join(report['layers_present'])}`",
        f"- All schema gates passed: `{report['all_schema_gates_passed']}`",
        f"- Record layer available: `{report['record_layer_available']}`",
        f"- Record has voltage/current/time: `{report['record_has_voltage_current_time']}`",
        f"- Record sampling interval mode (s): `{report['record_sampling_interval_mode_s']}`",
        f"- Quality flags: `{report['quality_flag_count']}`",
        f"- Training allowed now: `{report['training_allowed_now']}`",
        "",
        "## Layer Rows",
        "",
    ]
    for layer, count in report["layer_rows"].items():
        lines.append(f"- `{layer}`: {count}")
    lines.extend(
        [
            "",
            "## Step Types",
            "",
        ]
    )
    for step_type, count in report["step_type_counts"].items():
        lines.append(f"- `{step_type}`: {count}")
    lines.extend(
        [
            "",
            "## Feature Direction",
            "",
            str(report["feature_direction"]),
            "",
            "## Training Gate",
            "",
            str(report["training_gate_note"]),
        ]
    )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--cell-type", required=True)
    parser.add_argument("--encoding", default="gbk")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--record-sample-rows", type=int, default=5000)
    parser.add_argument("--export-suffix", default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    parse_three_layer_export(
        input_root=args.input_root,
        output_root=args.output_root,
        dataset_name=args.dataset_name,
        cell_type=args.cell_type,
        encoding=args.encoding,
        overwrite=args.overwrite,
        record_sample_rows=args.record_sample_rows,
        export_suffix_filter=args.export_suffix or None,
    )


if __name__ == "__main__":
    main()
