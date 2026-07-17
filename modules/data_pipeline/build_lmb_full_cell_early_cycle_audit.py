"""Build protocol-aware paired-cycle and early-cycle audit tables for LMB full cells.

This parser is deliberately conservative. It reconstructs charge/rest/discharge
pairs from BTSDA step order, streams record CSVs for lightweight summary
statistics, and produces past-only early-cycle feature *audit* tables. It does
not generate labels, EOL/RUL targets, or model-ready training data.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


CYCLE_ID = "循环号"
STEP_ID = "工步号"
STEP_SEQUENCE = "工步序号"
STEP_TYPE = "工步类型"
STEP_DURATION = "工步时间"
CHARGE_CAPACITY = "充电容量(mAh)"
DISCHARGE_CAPACITY = "放电容量(mAh)"
CHARGE_MEDIAN_VOLTAGE = "充电中值电压(V)"
DISCHARGE_MEDIAN_VOLTAGE = "放电中值电压(V)"
END_VOLTAGE = "结束电压(V)"
RECORD_VOLTAGE = "电压(V)"
RECORD_CURRENT = "电流(mA)"


PAIRED_COLUMNS = [
    "cell_id", "source_folder_name", "export_suffix", "dataset_role", "cell_scope",
    "electrolyte_code", "cathode_type", "cathode_diameter_cm", "protocol_id",
    "paired_cycle_index", "protocol_phase", "long_cycle_pair_index",
    "charge_btsda_cycle_index", "discharge_btsda_cycle_index", "charge_step_id",
    "discharge_step_id", "charge_step_sequence", "discharge_step_sequence",
    "charge_capacity_mah", "discharge_capacity_mah", "coulombic_efficiency_percent",
    "charge_duration_s", "discharge_duration_s", "charge_end_voltage_v",
    "discharge_end_voltage_v", "charge_median_voltage_v", "discharge_median_voltage_v",
    "voltage_hysteresis_v", "charge_record_count", "charge_record_voltage_mean_v",
    "charge_record_voltage_std_v", "charge_record_voltage_min_v", "charge_record_voltage_max_v",
    "charge_record_current_mean_ma", "charge_record_current_std_ma", "discharge_record_count",
    "discharge_record_voltage_mean_v", "discharge_record_voltage_std_v",
    "discharge_record_voltage_min_v", "discharge_record_voltage_max_v",
    "discharge_record_current_mean_ma", "discharge_record_current_std_ma", "is_complete_pair",
    "termination_reason", "protocol_censored_assigned", "training_allowed_now",
]

EARLY_FEATURE_COLUMNS = [
    "row_id", "cell_id", "source_folder_name", "export_suffix", "dataset_role", "cell_scope",
    "electrolyte_code", "protocol_id", "current_long_cycle_index", "feature_window_end_long_cycle_index",
    "early_cycle_limit", "discharge_capacity_lag_1_mah", "discharge_capacity_rolling_mean_past_3_mah",
    "discharge_capacity_slope_past_3_mah_per_cycle", "coulombic_efficiency_rolling_mean_past_3_percent",
    "voltage_hysteresis_rolling_mean_past_3_v", "charge_duration_rolling_mean_past_3_s",
    "discharge_duration_rolling_mean_past_3_s", "charge_end_voltage_lag_1_v",
    "discharge_end_voltage_lag_1_v", "feature_history_count", "training_allowed_now",
]

UNPAIRED_COLUMNS = [
    "cell_id", "source_folder_name", "export_suffix", "btsda_cycle_index", "step_id", "step_sequence",
    "step_type", "step_class", "reason", "training_allowed_now",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--early-cycle-limit", type=int, default=20)
    parser.add_argument("--encoding", default="gbk")
    parser.add_argument("--cell-ids", nargs="*")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def parse_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def parse_int(value: Any) -> int | None:
    number = parse_float(value)
    return int(number) if number is not None else None


def parse_duration_seconds(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    numeric = parse_float(text)
    if numeric is not None:
        return numeric
    parts = text.split(":")
    if len(parts) not in {2, 3}:
        return None
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return None
    if len(numbers) == 2:
        minutes, seconds = numbers
        return minutes * 60 + seconds
    hours, minutes, seconds = numbers
    return hours * 3600 + minutes * 60 + seconds


def step_class(value: Any) -> str:
    text = str(value or "")
    if "充电" in text:
        return "charge"
    if "放电" in text:
        return "discharge"
    if "静置" in text or "搁置" in text:
        return "rest"
    return "other"


def read_csv_rows(path: Path, encoding: str) -> list[dict[str, str]]:
    with path.open("r", encoding=encoding, newline="") as handle:
        return [row for row in csv.DictReader(handle) if any((value or "").strip() for value in row.values())]


def find_layer(root: Path, layer: str, suffix: str) -> Path:
    path = root / f"data_{layer}-{suffix}.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing {layer} layer for export {suffix}: {path}")
    return path


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


class OnlineStats:
    def __init__(self) -> None:
        self.count = 0
        self.mean = 0.0
        self.m2 = 0.0
        self.minimum: float | None = None
        self.maximum: float | None = None

    def add(self, value: float | None) -> None:
        if value is None:
            return
        self.count += 1
        delta = value - self.mean
        self.mean += delta / self.count
        self.m2 += delta * (value - self.mean)
        self.minimum = value if self.minimum is None else min(self.minimum, value)
        self.maximum = value if self.maximum is None else max(self.maximum, value)

    def output(self, prefix: str) -> dict[str, Any]:
        variance = self.m2 / self.count if self.count else None
        return {
            f"{prefix}_count": self.count,
            f"{prefix}_mean": self.mean if self.count else "",
            f"{prefix}_std": math.sqrt(variance) if variance is not None else "",
            f"{prefix}_min": self.minimum if self.minimum is not None else "",
            f"{prefix}_max": self.maximum if self.maximum is not None else "",
        }


def stream_record_stats(path: Path, encoding: str) -> dict[tuple[int, int], dict[str, OnlineStats]]:
    """Stream record rows; never concatenate the full record table in memory."""
    grouped: dict[tuple[int, int], dict[str, OnlineStats]] = defaultdict(
        lambda: {"voltage": OnlineStats(), "current": OnlineStats()}
    )
    with path.open("r", encoding=encoding, newline="") as handle:
        for row in csv.DictReader(handle):
            cycle_id, step_id = parse_int(row.get(CYCLE_ID)), parse_int(row.get(STEP_ID))
            if cycle_id is None or step_id is None:
                continue
            stats = grouped[(cycle_id, step_id)]
            stats["voltage"].add(parse_float(row.get(RECORD_VOLTAGE)))
            stats["current"].add(parse_float(row.get(RECORD_CURRENT)))
    return grouped


def summary_for_step(stats: dict[str, OnlineStats] | None, prefix: str) -> dict[str, Any]:
    if stats is None:
        return {
            f"{prefix}_record_count": 0,
            f"{prefix}_record_voltage_mean_v": "", f"{prefix}_record_voltage_std_v": "",
            f"{prefix}_record_voltage_min_v": "", f"{prefix}_record_voltage_max_v": "",
            f"{prefix}_record_current_mean_ma": "", f"{prefix}_record_current_std_ma": "",
        }
    voltage, current = stats["voltage"].output("voltage"), stats["current"].output("current")
    return {
        f"{prefix}_record_count": voltage["voltage_count"],
        f"{prefix}_record_voltage_mean_v": voltage["voltage_mean"],
        f"{prefix}_record_voltage_std_v": voltage["voltage_std"],
        f"{prefix}_record_voltage_min_v": voltage["voltage_min"],
        f"{prefix}_record_voltage_max_v": voltage["voltage_max"],
        f"{prefix}_record_current_mean_ma": current["current_mean"],
        f"{prefix}_record_current_std_ma": current["current_std"],
    }


def protocol_phase(charge_step_id: int | None, discharge_step_id: int | None) -> str:
    if charge_step_id == 2 and discharge_step_id == 4:
        return "formation"
    if charge_step_id == 7 and discharge_step_id == 9:
        return "long_cycle"
    return "mixed_transition_or_unknown"


def pair_steps(step_rows: list[dict[str, str]], cell: dict[str, Any], record_stats: dict[tuple[int, int], dict[str, OnlineStats]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    ordered = sorted(step_rows, key=lambda row: parse_int(row.get(STEP_SEQUENCE)) or 0)
    paired, unpaired = [], []
    open_charge: dict[str, str] | None = None
    long_cycle_index = 0
    for row in ordered:
        kind = step_class(row.get(STEP_TYPE))
        if kind == "charge":
            if open_charge is not None:
                unpaired.append(unpaired_step(open_charge, cell, "charge_replaced_before_discharge"))
            open_charge = row
            continue
        if kind != "discharge":
            continue
        if open_charge is None:
            unpaired.append(unpaired_step(row, cell, "discharge_without_prior_charge"))
            continue
        pair_index = len(paired) + 1
        charge_cycle, discharge_cycle = parse_int(open_charge.get(CYCLE_ID)), parse_int(row.get(CYCLE_ID))
        charge_step, discharge_step = parse_int(open_charge.get(STEP_ID)), parse_int(row.get(STEP_ID))
        phase = protocol_phase(charge_step, discharge_step)
        if phase == "long_cycle":
            long_cycle_index += 1
        charge_capacity, discharge_capacity = parse_float(open_charge.get(CHARGE_CAPACITY)), parse_float(row.get(DISCHARGE_CAPACITY))
        ce = 100 * discharge_capacity / charge_capacity if charge_capacity not in {None, 0} and discharge_capacity is not None else None
        charge_median, discharge_median = parse_float(open_charge.get(CHARGE_MEDIAN_VOLTAGE)), parse_float(row.get(DISCHARGE_MEDIAN_VOLTAGE))
        pair = {
            **cell_metadata(cell),
            "paired_cycle_index": pair_index,
            "protocol_phase": phase,
            "long_cycle_pair_index": long_cycle_index if phase == "long_cycle" else "",
            "charge_btsda_cycle_index": charge_cycle if charge_cycle is not None else "",
            "discharge_btsda_cycle_index": discharge_cycle if discharge_cycle is not None else "",
            "charge_step_id": charge_step if charge_step is not None else "",
            "discharge_step_id": discharge_step if discharge_step is not None else "",
            "charge_step_sequence": parse_int(open_charge.get(STEP_SEQUENCE)) or "",
            "discharge_step_sequence": parse_int(row.get(STEP_SEQUENCE)) or "",
            "charge_capacity_mah": charge_capacity if charge_capacity is not None else "",
            "discharge_capacity_mah": discharge_capacity if discharge_capacity is not None else "",
            "coulombic_efficiency_percent": ce if ce is not None else "",
            "charge_duration_s": parse_duration_seconds(open_charge.get(STEP_DURATION)) or "",
            "discharge_duration_s": parse_duration_seconds(row.get(STEP_DURATION)) or "",
            "charge_end_voltage_v": parse_float(open_charge.get(END_VOLTAGE)) or "",
            "discharge_end_voltage_v": parse_float(row.get(END_VOLTAGE)) or "",
            "charge_median_voltage_v": charge_median if charge_median is not None else "",
            "discharge_median_voltage_v": discharge_median if discharge_median is not None else "",
            "voltage_hysteresis_v": (charge_median - discharge_median) if charge_median is not None and discharge_median is not None else "",
            **summary_for_step(record_stats.get((charge_cycle, charge_step)) if charge_cycle is not None and charge_step is not None else None, "charge"),
            **summary_for_step(record_stats.get((discharge_cycle, discharge_step)) if discharge_cycle is not None and discharge_step is not None else None, "discharge"),
            "is_complete_pair": True,
            "termination_reason": cell.get("termination_reason", "unknown"),
            "protocol_censored_assigned": False,
            "training_allowed_now": False,
        }
        paired.append(pair)
        open_charge = None
    if open_charge is not None:
        unpaired.append(unpaired_step(open_charge, cell, "terminal_charge_without_discharge"))
    return paired, unpaired


def cell_metadata(cell: dict[str, Any]) -> dict[str, Any]:
    keys = ["cell_id", "source_folder_name", "export_suffix", "dataset_role", "cell_scope", "electrolyte_code", "cathode_type", "cathode_diameter_cm", "protocol_id"]
    return {key: cell.get(key, "") for key in keys}


def unpaired_step(row: dict[str, str], cell: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "cell_id": cell.get("cell_id", ""), "source_folder_name": cell.get("source_folder_name", ""),
        "export_suffix": cell.get("export_suffix", ""), "btsda_cycle_index": parse_int(row.get(CYCLE_ID)) or "",
        "step_id": parse_int(row.get(STEP_ID)) or "", "step_sequence": parse_int(row.get(STEP_SEQUENCE)) or "",
        "step_type": row.get(STEP_TYPE, ""), "step_class": step_class(row.get(STEP_TYPE)),
        "reason": reason, "training_allowed_now": False,
    }


def mean(values: list[float]) -> float | str:
    return statistics.fmean(values) if values else ""


def slope(values: list[float]) -> float | str:
    if len(values) < 2:
        return ""
    x_mean = (len(values) - 1) / 2
    y_mean = statistics.fmean(values)
    numerator = sum((index - x_mean) * (value - y_mean) for index, value in enumerate(values))
    denominator = sum((index - x_mean) ** 2 for index in range(len(values)))
    return numerator / denominator if denominator else ""


def numeric(row: dict[str, Any], column: str) -> float | None:
    return parse_float(row.get(column))


def build_early_features(pairs: list[dict[str, Any]], early_cycle_limit: int) -> list[dict[str, Any]]:
    by_cell: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for pair in pairs:
        if pair["protocol_phase"] == "long_cycle":
            by_cell[str(pair["cell_id"])].append(pair)
    output: list[dict[str, Any]] = []
    for cell_pairs in by_cell.values():
        ordered = sorted(cell_pairs, key=lambda row: int(row["long_cycle_pair_index"]))
        for index, current in enumerate(ordered):
            target_index = int(current["long_cycle_pair_index"])
            if target_index > early_cycle_limit:
                continue
            history = ordered[:index]
            recent = history[-3:]
            capacity_values = [value for row in recent if (value := numeric(row, "discharge_capacity_mah")) is not None]
            ce_values = [value for row in recent if (value := numeric(row, "coulombic_efficiency_percent")) is not None]
            hysteresis_values = [value for row in recent if (value := numeric(row, "voltage_hysteresis_v")) is not None]
            charge_duration_values = [value for row in recent if (value := numeric(row, "charge_duration_s")) is not None]
            discharge_duration_values = [value for row in recent if (value := numeric(row, "discharge_duration_s")) is not None]
            last = history[-1] if history else {}
            enough_three = len(recent) >= 3
            output.append({
                "row_id": f"{current['cell_id']}::long_cycle_{target_index}",
                **{key: current[key] for key in ["cell_id", "source_folder_name", "export_suffix", "dataset_role", "cell_scope", "electrolyte_code", "protocol_id"]},
                "current_long_cycle_index": target_index,
                "feature_window_end_long_cycle_index": target_index - 1 if history else "",
                "early_cycle_limit": early_cycle_limit,
                "discharge_capacity_lag_1_mah": numeric(last, "discharge_capacity_mah") if history else "",
                "discharge_capacity_rolling_mean_past_3_mah": mean(capacity_values) if enough_three else "",
                "discharge_capacity_slope_past_3_mah_per_cycle": slope(capacity_values) if enough_three and len(capacity_values) == 3 else "",
                "coulombic_efficiency_rolling_mean_past_3_percent": mean(ce_values) if enough_three else "",
                "voltage_hysteresis_rolling_mean_past_3_v": mean(hysteresis_values) if enough_three else "",
                "charge_duration_rolling_mean_past_3_s": mean(charge_duration_values) if enough_three else "",
                "discharge_duration_rolling_mean_past_3_s": mean(discharge_duration_values) if enough_three else "",
                "charge_end_voltage_lag_1_v": numeric(last, "charge_end_voltage_v") if history else "",
                "discharge_end_voltage_lag_1_v": numeric(last, "discharge_end_voltage_v") if history else "",
                "feature_history_count": len(history),
                "training_allowed_now": False,
            })
    return output


def feature_schema() -> list[dict[str, Any]]:
    definitions = [
        ("discharge_capacity_lag_1_mah", "capacity", True, True, "Previous long-cycle discharge capacity; audit-only candidate with same-signal-source risk."),
        ("discharge_capacity_rolling_mean_past_3_mah", "capacity", True, True, "Past three long-cycle capacities only."),
        ("discharge_capacity_slope_past_3_mah_per_cycle", "capacity", True, True, "Past three long-cycle capacity slope only."),
        ("coulombic_efficiency_rolling_mean_past_3_percent", "coulombic_efficiency", True, True, "Past CE summary only; direct same-signal-source risk requires later review."),
        ("voltage_hysteresis_rolling_mean_past_3_v", "polarization", True, False, "Past step-level voltage hysteresis."),
        ("charge_duration_rolling_mean_past_3_s", "kinetic", True, False, "Past charge duration under the documented protocol."),
        ("discharge_duration_rolling_mean_past_3_s", "kinetic", True, False, "Past discharge duration under the documented protocol."),
        ("charge_end_voltage_lag_1_v", "voltage", True, False, "Previous long-cycle charge endpoint."),
        ("discharge_end_voltage_lag_1_v", "voltage", True, False, "Previous long-cycle discharge endpoint."),
    ]
    return [
        {"feature_name": name, "feature_family": family, "past_only": past_only,
         "same_signal_source_risk": risk, "model_feature_candidate": False,
         "reason": reason, "training_allowed_now": False}
        for name, family, past_only, risk, reason in definitions
    ]


def build_audit(manifest_path: Path, output_root: Path, early_cycle_limit: int = 20, encoding: str = "gbk", cell_ids: list[str] | None = None, overwrite: bool = False) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    configured = manifest.get("cells", [])
    selected = [cell for cell in configured if not cell_ids or cell.get("cell_id") in set(cell_ids)]
    active = [cell for cell in selected if cell.get("dataset_role") == "true_lmb" and cell.get("use_status") == "active_feature_audit"]
    rejected = [cell.get("cell_id", "") for cell in selected if cell not in active]
    if not active:
        raise ValueError("No active true_lmb cells selected; diagnostic-only data cannot enter the full-cell feature audit.")

    all_pairs: list[dict[str, Any]] = []
    all_unpaired: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for cell in active:
        root, suffix = Path(cell["input_root"]), str(cell["export_suffix"])
        cycle_path = find_layer(root, "cycle", suffix)
        step_path, record_path = find_layer(root, "step", suffix), find_layer(root, "record", suffix)
        cycle_rows = read_csv_rows(cycle_path, encoding)
        if not cycle_rows or CYCLE_ID not in cycle_rows[0]:
            raise ValueError(f"{cell['cell_id']} cycle layer is missing required field: {CYCLE_ID}")
        step_rows = read_csv_rows(step_path, encoding)
        required = {CYCLE_ID, STEP_ID, STEP_SEQUENCE, STEP_TYPE, STEP_DURATION}
        missing = sorted(required - set(step_rows[0] if step_rows else {}))
        if missing:
            raise ValueError(f"{cell['cell_id']} missing required step fields: {missing}")
        pairs, unpaired = pair_steps(step_rows, cell, stream_record_stats(record_path, encoding))
        all_pairs.extend(pairs)
        all_unpaired.extend(unpaired)
        summaries.append({
            "cell_id": cell["cell_id"], "dataset_role": cell["dataset_role"], "cell_scope": cell["cell_scope"],
            "protocol_id": cell["protocol_id"], "paired_cycle_count": len(pairs),
            "cycle_layer_row_count": len(cycle_rows), "step_layer_row_count": len(step_rows),
            "formation_pair_count": sum(row["protocol_phase"] == "formation" for row in pairs),
            "long_cycle_pair_count": sum(row["protocol_phase"] == "long_cycle" for row in pairs),
            "mixed_transition_pair_count": sum(row["protocol_phase"] == "mixed_transition_or_unknown" for row in pairs),
            "unpaired_step_count": len(unpaired), "termination_reason": cell.get("termination_reason", "unknown"),
            "protocol_censored_assigned": False, "training_allowed_now": False,
        })

    features = build_early_features(all_pairs, early_cycle_limit)
    schema = feature_schema()
    write_csv(output_root / "lmb_full_cell_paired_cycle_audit.csv", all_pairs, PAIRED_COLUMNS)
    write_csv(output_root / "lmb_full_cell_early_cycle_features.csv", features, EARLY_FEATURE_COLUMNS)
    write_csv(output_root / "lmb_full_cell_unpaired_step_audit.csv", all_unpaired, UNPAIRED_COLUMNS)
    write_csv(output_root / "lmb_full_cell_feature_schema.csv", schema, list(schema[0]))
    summary_fields = list(summaries[0]) if summaries else ["cell_id"]
    write_csv(output_root / "lmb_full_cell_cell_summary.csv", summaries, summary_fields)
    report = {
        "manifest": str(manifest_path), "selected_active_cell_count": len(active), "rejected_cell_ids": rejected,
        "paired_cycle_count": len(all_pairs), "early_cycle_feature_row_count": len(features),
        "unpaired_step_count": len(all_unpaired), "early_cycle_limit": early_cycle_limit,
        "label_generation_allowed": False, "model_training_allowed": False,
        "model_performance_claimed": False,
        "protocol_censoring_status": "unassigned_until_termination_reason_is_confirmed",
        "scope_note": "True LMB full-cell feature audit only. No labels, EOL/RUL, targets, or model training are created.",
        "next_gate": "Verify protocol reconstruction on a small real export, then review metadata and termination reasons before label design.",
    }
    (output_root / "lmb_full_cell_intake_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = [
        "# LMB Full-Cell Early-Cycle Feature Audit", "",
        "This is a protocol-aware feature audit, not a training set or model result.", "",
        f"- Active true-LMB full-cell exports: `{len(active)}`",
        f"- Paired charge/discharge cycles: `{len(all_pairs)}`",
        f"- Early-cycle feature rows: `{len(features)}`",
        f"- Unpaired steps retained for audit: `{len(all_unpaired)}`",
        f"- Early long-cycle limit: `{early_cycle_limit}`",
        "- LHCE diagnostic-only export: excluded by manifest.",
        "- Termination reason: still unknown; protocol censoring is not assigned.",
        "", "```text", "label_generation_allowed=False", "model_training_allowed=False", "model_performance_claimed=False", "```", "",
        "Rolling features use only prior long-cycle pairs. Capacity and CE derivatives are explicitly marked as same-signal-source risk and are not approved model features.",
    ]
    (output_root / "lmb_full_cell_intake_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def main() -> None:
    args = parse_args()
    build_audit(args.manifest, args.output_root, args.early_cycle_limit, args.encoding, args.cell_ids, args.overwrite)


if __name__ == "__main__":
    main()
