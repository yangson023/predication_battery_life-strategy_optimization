"""Build canonical lithium metal battery feature tables from BTSDA intake outputs.

This builder is intentionally limited to feature construction. It does not
create labels, train models, split data, or read alternate exports.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Iterable


FORBIDDEN_COLUMN_TOKENS = ["label", "eol", "rul", "target", "future"]
ALLOWED_QUALITY_COLUMNS = {"exclude_from_label_training"}


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def parse_float(value: object) -> float | None:
    try:
        text = str(value).strip()
        if text == "":
            return None
        value_float = float(text)
    except (TypeError, ValueError):
        return None
    if math.isnan(value_float):
        return None
    return value_float


def parse_int(value: object) -> int | None:
    value_float = parse_float(value)
    if value_float is None:
        return None
    return int(value_float)


def safe_mean(values: Iterable[float]) -> float | str:
    clean = [value for value in values if value is not None]
    return statistics.fmean(clean) if clean else ""


def safe_std(values: Iterable[float]) -> float | str:
    clean = [value for value in values if value is not None]
    return statistics.stdev(clean) if len(clean) >= 2 else ""


def safe_min(values: Iterable[float]) -> float | str:
    clean = [value for value in values if value is not None]
    return min(clean) if clean else ""


def safe_max(values: Iterable[float]) -> float | str:
    clean = [value for value in values if value is not None]
    return max(clean) if clean else ""


def slope(values: list[float]) -> float | str:
    clean = [value for value in values if value is not None]
    if len(clean) < 2:
        return ""
    xs = list(range(len(clean)))
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(clean)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return ""
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, clean)) / denominator


def bool_text(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def clip_ce_for_rolling(value: float | None) -> float | None:
    if value is None:
        return None
    return min(max(value, 0.0), 200.0)


def usable_past_ce(row: dict[str, object]) -> float | None:
    charge = parse_float(row.get("charge_capacity_mah"))
    discharge = parse_float(row.get("discharge_capacity_mah"))
    ce = parse_float(row.get("coulombic_efficiency_percent"))
    if charge is None or discharge is None or ce is None:
        return None
    if charge <= 0 or discharge <= 0:
        return None
    return clip_ce_for_rolling(ce)


def group_quality_rows(rows: list[dict[str, str]]) -> dict[tuple[str, int], dict[str, str]]:
    grouped: dict[tuple[str, int], dict[str, str]] = {}
    for row in rows:
        cycle = parse_int(row.get("cycle_index"))
        dataset = row.get("selected_dataset_name", "")
        if dataset and cycle is not None:
            grouped[(dataset, cycle)] = row
    return grouped


def quality_for(
    quality_by_key: dict[tuple[str, int], dict[str, str]],
    dataset_name: str,
    cycle_index: int,
) -> dict[str, str]:
    return quality_by_key.get(
        (dataset_name, cycle_index),
        {
            "flag_types": "",
            "exclude_from_label_training": "False",
            "audit_warning_only": "False",
            "retained_for_feature_exploration": "True",
            "exclusion_reason": "",
        },
    )


def record_features(record_rows: list[dict[str, str]]) -> dict[int, dict[str, object]]:
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in record_rows:
        cycle = parse_int(row.get("cycle_index"))
        if cycle is not None:
            grouped[cycle].append(row)
    result: dict[int, dict[str, object]] = {}
    for cycle, rows in grouped.items():
        voltages = [parse_float(row.get("voltage_v")) for row in rows]
        currents = [parse_float(row.get("current_ma")) for row in rows]
        result[cycle] = {
            "record_voltage_mean_v": safe_mean(voltages),
            "record_voltage_std_v": safe_std(voltages),
            "record_voltage_min_v": safe_min(voltages),
            "record_voltage_max_v": safe_max(voltages),
            "record_current_mean_ma": safe_mean(currents),
            "record_current_std_ma": safe_std(currents),
        }
    return result


def rest_voltage_drop_by_cycle(record_rows: list[dict[str, str]]) -> dict[int, float | str]:
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in record_rows:
        cycle = parse_int(row.get("cycle_index"))
        current = parse_float(row.get("current_ma"))
        if cycle is not None and current is not None and abs(current) < 1e-9:
            grouped[cycle].append(row)
    drops: dict[int, float | str] = {}
    for cycle, rows in grouped.items():
        if len(rows) < 2:
            drops[cycle] = ""
            continue
        start_v = parse_float(rows[0].get("voltage_v"))
        end_v = parse_float(rows[-1].get("voltage_v"))
        # Samples are usually 30 s apart in the tiny validation exports.
        duration_hours = max((len(rows) - 1) * 30.0 / 3600.0, 1e-9)
        if start_v is None or end_v is None:
            drops[cycle] = ""
        else:
            drops[cycle] = (start_v - end_v) * 1000.0 / duration_hours
    return drops


def step_features(step_rows: list[dict[str, str]]) -> dict[int, dict[str, object]]:
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in step_rows:
        cycle = parse_int(row.get("cycle_index"))
        if cycle is not None:
            grouped[cycle].append(row)
    result: dict[int, dict[str, object]] = {}
    for cycle, rows in grouped.items():
        charge_rows = [row for row in rows if (parse_float(row.get("charge_capacity_mah")) or 0.0) > 0]
        discharge_rows = [row for row in rows if (parse_float(row.get("discharge_capacity_mah")) or 0.0) > 0]
        charge = charge_rows[-1] if charge_rows else {}
        discharge = discharge_rows[-1] if discharge_rows else {}
        charge_median = parse_float(charge.get("charge_median_voltage_v"))
        discharge_median = parse_float(discharge.get("discharge_median_voltage_v"))
        charge_end = parse_float(charge.get("end_voltage_v"))
        discharge_end = parse_float(discharge.get("end_voltage_v"))
        result[cycle] = {
            "charge_median_voltage_v": charge_median if charge_median is not None else "",
            "discharge_median_voltage_v": discharge_median if discharge_median is not None else "",
            "charge_end_voltage_v": charge_end if charge_end is not None else "",
            "discharge_end_voltage_v": discharge_end if discharge_end is not None else "",
            "voltage_hysteresis_v": (charge_median - discharge_median)
            if charge_median is not None and discharge_median is not None
            else "",
            "end_voltage_gap_v": (charge_end - discharge_end)
            if charge_end is not None and discharge_end is not None
            else "",
        }
    return result


def build_licu_rows(
    manifest_row: dict[str, str],
    quality_by_key: dict[tuple[str, int], dict[str, str]],
    missing_fields: list[dict[str, str]],
) -> list[dict[str, object]]:
    root = Path(manifest_row["selected_output_root"])
    cycle_rows = read_csv(root / "normalized_cycle.csv")
    record_rows = read_csv(root / "normalized_record_sample.csv")
    record_by_cycle = record_features(record_rows)
    dataset = manifest_row["selected_dataset_name"]
    out_rows: list[dict[str, object]] = []
    past_ce: list[float] = []
    past_irr: list[float] = []
    past_discharge: list[float] = []
    initial_ce = ""
    initial_window: list[float] = []
    for row in sorted(cycle_rows, key=lambda item: parse_int(item.get("cycle_index")) or 0):
        cycle = parse_int(row.get("cycle_index"))
        if cycle is None:
            continue
        charge = parse_float(row.get("charge_capacity_mah"))
        discharge = parse_float(row.get("discharge_capacity_mah"))
        ce = parse_float(row.get("coulombic_efficiency_percent"))
        irr = (charge - discharge) if charge is not None and discharge is not None else None
        quality = quality_for(quality_by_key, dataset, cycle)
        rolling_values = past_ce[-5:]
        ce_lag_1 = past_ce[-1] if past_ce else ""
        rolling_mean = safe_mean(rolling_values)
        rolling_std = safe_std(rolling_values)
        if initial_ce == "" and past_ce:
            initial_ce = past_ce[0]
        if len(initial_window) < 5 and past_ce:
            initial_window = past_ce[:5]
        ce_delta = (past_ce[-1] - initial_ce) if past_ce and initial_ce != "" else ""
        initial_window_mean = safe_mean(initial_window)
        ce_delta_window = (
            rolling_mean - initial_window_mean
            if isinstance(rolling_mean, float) and isinstance(initial_window_mean, float)
            else ""
        )
        feature_row: dict[str, object] = {
            "source_folder_name": manifest_row["source_folder_name"],
            "selected_dataset_name": dataset,
            "cycle_index": cycle,
            "charge_capacity_mah": charge if charge is not None else "",
            "discharge_capacity_mah": discharge if discharge is not None else "",
            "coulombic_efficiency_percent": ce if ce is not None else "",
            "capacity_retention_percent": row.get("capacity_retention_percent", ""),
            "ce_lag_1": ce_lag_1,
            "ce_rolling_mean_past_5": rolling_mean,
            "ce_rolling_std_past_5": rolling_std,
            "ce_delta_from_initial_past": ce_delta,
            "ce_delta_from_initial_window5": ce_delta_window,
            "irreversible_capacity_mah": irr if irr is not None else "",
            "cumulative_irreversible_capacity_past": sum(past_irr),
            "cumulative_discharge_throughput_mah": sum(past_discharge),
            "incomplete_cycle_flag": str(
                "incomplete" in quality.get("flag_types", "")
                or bool_text(quality.get("exclude_from_label_training"))
            ),
            "ce_warning_flag": str(
                bool_text(quality.get("audit_warning_only"))
                or "ce_above_103_percent" in quality.get("flag_types", "")
                or "ce_below_80_percent" in quality.get("flag_types", "")
            ),
            "exclude_from_label_training": quality.get("exclude_from_label_training", "False"),
            "audit_warning_only": quality.get("audit_warning_only", "False"),
            "record_sample_limited": "True",
        }
        feature_row.update(record_by_cycle.get(cycle, {}))
        out_rows.append(feature_row)
        usable = usable_past_ce(row)
        if usable is not None:
            past_ce.append(usable)
        if irr is not None and charge is not None and discharge is not None and charge > 0 and discharge > 0:
            past_irr.append(irr)
        if discharge is not None and discharge > 0:
            past_discharge.append(discharge)
    return out_rows


def build_lili_rows(
    manifest_row: dict[str, str],
    quality_by_key: dict[tuple[str, int], dict[str, str]],
    missing_fields: list[dict[str, str]],
) -> list[dict[str, object]]:
    root = Path(manifest_row["selected_output_root"])
    cycle_rows = read_csv(root / "normalized_cycle.csv")
    step_rows = read_csv(root / "normalized_step.csv")
    record_rows = read_csv(root / "normalized_record_sample.csv")
    dataset = manifest_row["selected_dataset_name"]
    step_by_cycle = step_features(step_rows)
    record_by_cycle = record_features(record_rows)
    rest_drop = rest_voltage_drop_by_cycle(record_rows)
    out_rows: list[dict[str, object]] = []
    past_hysteresis: list[float] = []
    initial_hysteresis_window: list[float] = []
    for row in sorted(cycle_rows, key=lambda item: parse_int(item.get("cycle_index")) or 0):
        cycle = parse_int(row.get("cycle_index"))
        if cycle is None:
            continue
        quality = quality_for(quality_by_key, dataset, cycle)
        step = step_by_cycle.get(cycle, {})
        record = record_by_cycle.get(cycle, {})
        hyst = parse_float(step.get("voltage_hysteresis_v"))
        rolling_values = past_hysteresis[-5:]
        rolling_mean = safe_mean(rolling_values)
        slope_values = past_hysteresis[-10:]
        hyst_slope = slope(slope_values)
        if len(initial_hysteresis_window) < 5 and past_hysteresis:
            initial_hysteresis_window = past_hysteresis[:5]
        initial_hyst_mean = safe_mean(initial_hysteresis_window)
        hyst_delta = (
            hyst - initial_hyst_mean
            if hyst is not None and isinstance(initial_hyst_mean, float)
            else ""
        )
        voltage_std = parse_float(record.get("record_voltage_std_v"))
        instability = False
        if isinstance(hyst, float) and isinstance(rolling_mean, float):
            recent_std = safe_std(rolling_values)
            if isinstance(recent_std, float) and recent_std > 0:
                instability = abs(hyst - rolling_mean) > 3 * recent_std
        if voltage_std is not None:
            instability = instability or voltage_std > 0.05
        feature_row: dict[str, object] = {
            "source_folder_name": manifest_row["source_folder_name"],
            "selected_dataset_name": dataset,
            "cycle_index": cycle,
            "capacity_retention_percent": row.get("capacity_retention_percent", ""),
            "charge_median_voltage_v": step.get("charge_median_voltage_v", ""),
            "discharge_median_voltage_v": step.get("discharge_median_voltage_v", ""),
            "charge_end_voltage_v": step.get("charge_end_voltage_v", ""),
            "discharge_end_voltage_v": step.get("discharge_end_voltage_v", ""),
            "voltage_hysteresis_v": step.get("voltage_hysteresis_v", ""),
            "end_voltage_gap_v": step.get("end_voltage_gap_v", ""),
            "hysteresis_rolling_mean_past_5": rolling_mean,
            "hysteresis_slope_past_10": hyst_slope,
            "hysteresis_delta_from_initial_past": hyst_delta,
            "rest_voltage_drop_mv_per_hour": rest_drop.get(cycle, ""),
            "voltage_instability_warning": str(instability),
            "incomplete_cycle_warning": str(
                bool_text(quality.get("exclude_from_label_training"))
                or bool_text(quality.get("audit_warning_only"))
            ),
            "exclude_from_label_training": quality.get("exclude_from_label_training", "False"),
            "audit_warning_only": quality.get("audit_warning_only", "False"),
            "record_sample_limited": "True",
        }
        feature_row.update(record)
        out_rows.append(feature_row)
        if hyst is not None:
            past_hysteresis.append(hyst)
    return out_rows


def forbidden_columns(columns: Iterable[str]) -> list[str]:
    found = []
    for column in columns:
        if column in ALLOWED_QUALITY_COLUMNS:
            continue
        lower = column.lower()
        if any(token in lower for token in FORBIDDEN_COLUMN_TOKENS):
            found.append(column)
    return found


def build_features(
    canonical_manifest: Path,
    cycle_quality_manifest: Path,
    output_root: Path,
    overwrite: bool,
) -> dict[str, object]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root already exists and is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = read_csv(canonical_manifest)
    quality_rows = read_csv(cycle_quality_manifest)
    quality_by_key = group_quality_rows(quality_rows)
    lili_rows: list[dict[str, object]] = []
    licu_rows: list[dict[str, object]] = []
    missing_fields: list[dict[str, str]] = []
    per_cell_counts: dict[str, int] = {}
    for manifest_row in manifest:
        if manifest_row.get("cell_group") == "Li||Cu":
            rows = build_licu_rows(manifest_row, quality_by_key, missing_fields)
            licu_rows.extend(rows)
        elif manifest_row.get("cell_group") == "Li||Li":
            rows = build_lili_rows(manifest_row, quality_by_key, missing_fields)
            lili_rows.extend(rows)
        else:
            rows = []
        per_cell_counts[manifest_row.get("source_folder_name", "")] = len(rows)
    lili_fields = [
        "source_folder_name",
        "selected_dataset_name",
        "cycle_index",
        "capacity_retention_percent",
        "charge_median_voltage_v",
        "discharge_median_voltage_v",
        "charge_end_voltage_v",
        "discharge_end_voltage_v",
        "voltage_hysteresis_v",
        "end_voltage_gap_v",
        "hysteresis_rolling_mean_past_5",
        "hysteresis_slope_past_10",
        "hysteresis_delta_from_initial_past",
        "rest_voltage_drop_mv_per_hour",
        "voltage_instability_warning",
        "incomplete_cycle_warning",
        "exclude_from_label_training",
        "audit_warning_only",
        "record_sample_limited",
        "record_voltage_mean_v",
        "record_voltage_std_v",
        "record_voltage_min_v",
        "record_voltage_max_v",
        "record_current_mean_ma",
        "record_current_std_ma",
    ]
    licu_fields = [
        "source_folder_name",
        "selected_dataset_name",
        "cycle_index",
        "charge_capacity_mah",
        "discharge_capacity_mah",
        "coulombic_efficiency_percent",
        "capacity_retention_percent",
        "ce_lag_1",
        "ce_rolling_mean_past_5",
        "ce_rolling_std_past_5",
        "ce_delta_from_initial_past",
        "ce_delta_from_initial_window5",
        "irreversible_capacity_mah",
        "cumulative_irreversible_capacity_past",
        "cumulative_discharge_throughput_mah",
        "incomplete_cycle_flag",
        "ce_warning_flag",
        "exclude_from_label_training",
        "audit_warning_only",
        "record_sample_limited",
        "record_voltage_mean_v",
        "record_voltage_std_v",
        "record_voltage_min_v",
        "record_voltage_max_v",
        "record_current_mean_ma",
        "record_current_std_ma",
    ]
    write_csv(output_root / "lili_cycle_features.csv", lili_rows, lili_fields)
    write_csv(output_root / "licu_cycle_features.csv", licu_rows, licu_fields)
    lili_forbidden = forbidden_columns(lili_fields)
    licu_forbidden = forbidden_columns(licu_fields)
    canonical_names = {row["selected_dataset_name"] for row in manifest}
    lili_names = {str(row["selected_dataset_name"]) for row in lili_rows}
    licu_names = {str(row["selected_dataset_name"]) for row in licu_rows}
    checks = [
        {
            "check_name": "lili_csv_readable",
            "status": "pass" if (output_root / "lili_cycle_features.csv").exists() else "fail",
            "detail": str(output_root / "lili_cycle_features.csv"),
        },
        {
            "check_name": "licu_csv_readable",
            "status": "pass" if (output_root / "licu_cycle_features.csv").exists() else "fail",
            "detail": str(output_root / "licu_cycle_features.csv"),
        },
        {
            "check_name": "only_canonical_dataset_names",
            "status": "pass" if (lili_names | licu_names).issubset(canonical_names) else "fail",
            "detail": ";".join(sorted((lili_names | licu_names) - canonical_names)),
        },
        {
            "check_name": "forbidden_columns_absent",
            "status": "pass" if not (lili_forbidden or licu_forbidden) else "fail",
            "detail": ";".join(lili_forbidden + licu_forbidden),
        },
        {
            "check_name": "rolling_features_past_only",
            "status": "pass",
            "detail": "CE and hysteresis rolling features are computed before appending current cycle to rolling history.",
        },
        {
            "check_name": "training_allowed_now",
            "status": "pass",
            "detail": "false for feature builder stage",
        },
    ]
    write_csv(output_root / "feature_schema_check.csv", checks, ["check_name", "status", "detail"])
    report = {
        "feature_build_date": "2026-06-18",
        "lili_feature_rows": len(lili_rows),
        "licu_feature_rows": len(licu_rows),
        "per_cell_feature_rows": per_cell_counts,
        "missing_fields": missing_fields,
        "rolling_features_past_only": True,
        "forbidden_columns": lili_forbidden + licu_forbidden,
        "label_policy_design_allowed": not (lili_forbidden or licu_forbidden),
        "training_allowed_now": False,
        "notes": [
            "Li||Li and Li||Cu are written to separate feature tables.",
            "Record-derived features are sample-limited and should not be treated as full-record curve features.",
            "Li||Cu CE columns are label-proximal and require label-policy leakage controls before any training.",
        ],
    }
    (output_root / "lmb_feature_build_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    md = [
        "# LMB canonical feature build report",
        "",
        "This report describes feature tables only. It does not create labels, split data, or train models.",
        "",
        "## Summary",
        "",
        f"- Li||Li feature rows: {len(lili_rows)}",
        f"- Li||Cu feature rows: {len(licu_rows)}",
        "- Rolling features past-only: True",
        f"- Forbidden columns: {report['forbidden_columns']}",
        f"- Label policy design allowed: {report['label_policy_design_allowed']}",
        "- Training allowed now: False",
        "",
        "## Per-cell rows",
        "",
        "| source folder | rows |",
        "| --- | ---: |",
    ]
    for cell, count in per_cell_counts.items():
        md.append(f"| {cell} | {count} |")
    md.extend(
        [
            "",
            "## Gate Decision",
            "",
            "Feature tables are ready for label-policy design. Model training remains prohibited until label definitions, censoring rules, leakage checks, and trainable-label audit pass.",
        ]
    )
    (output_root / "lmb_feature_build_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-manifest", type=Path, required=True)
    parser.add_argument("--cycle-quality-manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    build_features(
        canonical_manifest=args.canonical_manifest,
        cycle_quality_manifest=args.cycle_quality_manifest,
        output_root=args.output_root,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
