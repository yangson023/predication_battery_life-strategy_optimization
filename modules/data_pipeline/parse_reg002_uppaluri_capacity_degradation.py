"""Parse REG-002 Uppaluri/Onori public LMB capacity-degradation MAT files.

This is a tiny-validation/audit parser. It converts small
``*_capacity_degradation.mat`` files into long cycle tables and label-audit
summaries. It does not train models or create a formal training set.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import scipy.io as sio


LONG_COLUMNS = [
    "source_id",
    "dataset_role",
    "cell_scope",
    "group_id",
    "cell_id",
    "file_name",
    "row_index",
    "equiv_cycle",
    "charge_capacity",
    "discharge_capacity",
    "capacity_retention",
    "source_data_audit_only",
    "tiny_validation_only",
    "model_training_allowed",
]

SUMMARY_COLUMNS = [
    "source_id",
    "dataset_role",
    "cell_scope",
    "group_id",
    "cell_id",
    "file_name",
    "n_rows",
    "initial_discharge_capacity",
    "final_discharge_capacity",
    "min_discharge_capacity",
    "max_discharge_capacity",
    "initial_charge_capacity",
    "final_charge_capacity",
    "max_equiv_cycle",
    "min_capacity_retention",
    "final_capacity_retention",
    "has_charge_capacity",
    "has_discharge_capacity",
    "has_equiv_cycle",
    "quality_status",
    "quality_note",
    "source_data_audit_only",
    "tiny_validation_only",
    "model_training_allowed",
]

LABEL_COLUMNS = [
    "source_id",
    "dataset_role",
    "cell_scope",
    "group_id",
    "cell_id",
    "label_key",
    "threshold",
    "event_observed",
    "event_row_index",
    "event_equiv_cycle",
    "duration_until_event_or_last_equiv_cycle",
    "rul_is_censored",
    "label_quality",
    "exploratory_candidate_label",
    "formal_trainable_label",
    "blocking_reason",
    "source_data_audit_only",
    "tiny_validation_only",
    "model_training_allowed",
]

GATE_COLUMNS = [
    "gate_name",
    "gate_status",
    "evidence",
    "required_next_action",
    "model_training_allowed",
]


@dataclass
class ParsedCell:
    group_id: str
    cell_id: str
    file_name: str
    charge_capacity: np.ndarray
    discharge_capacity: np.ndarray
    equiv_cycle: np.ndarray


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_group_cell(file_name: str) -> tuple[str, str]:
    match = re.search(r"(G\d+)-Cell(\d+)_capacity_degradation\.mat$", file_name)
    if not match:
        raise ValueError(f"Unrecognized REG-002 capacity file name: {file_name}")
    group_id = match.group(1)
    return group_id, f"{group_id}_Cell{match.group(2)}"


def flatten_numeric(data: dict[str, Any], key: str) -> np.ndarray:
    if key not in data:
        return np.array([], dtype=float)
    values = np.asarray(data[key], dtype=float).reshape(-1)
    return values[np.isfinite(values)]


def load_capacity_file(path: Path) -> ParsedCell:
    data = sio.loadmat(path)
    group_id, cell_id = parse_group_cell(path.name)
    charge_capacity = flatten_numeric(data, "cap_chg_per_cycle")
    discharge_capacity = flatten_numeric(data, "cap_dischg_per_cycle")
    equiv_cycle = flatten_numeric(data, "equiv_cycle")
    lengths = {len(charge_capacity), len(discharge_capacity), len(equiv_cycle)}
    lengths.discard(0)
    if len(lengths) > 1:
        common_length = min(lengths)
        charge_capacity = charge_capacity[:common_length]
        discharge_capacity = discharge_capacity[:common_length]
        equiv_cycle = equiv_cycle[:common_length]
    return ParsedCell(
        group_id=group_id,
        cell_id=cell_id,
        file_name=path.name,
        charge_capacity=charge_capacity,
        discharge_capacity=discharge_capacity,
        equiv_cycle=equiv_cycle,
    )


def quality_status(cell: ParsedCell) -> tuple[str, str]:
    if not len(cell.discharge_capacity):
        return "fail_missing_discharge_capacity", "No discharge capacity array."
    if not len(cell.equiv_cycle):
        return "fail_missing_equiv_cycle", "No equivalent cycle array."
    if len(cell.discharge_capacity) < 50:
        return "caution_short_cycle_window", "Less than 50 observations."
    if cell.discharge_capacity[0] <= 0:
        return "fail_invalid_initial_capacity", "Initial discharge capacity is non-positive."
    return "pass_for_capacity_label_audit", "Capacity and equivalent cycle arrays are usable for audit."


def build_long_rows(cells: list[ParsedCell]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        initial = float(cell.discharge_capacity[0]) if len(cell.discharge_capacity) else np.nan
        n = min(len(cell.charge_capacity), len(cell.discharge_capacity), len(cell.equiv_cycle))
        for idx in range(n):
            discharge = float(cell.discharge_capacity[idx])
            rows.append(
                {
                    "source_id": "REG-002",
                    "dataset_role": "true_lmb",
                    "cell_scope": "lmb_full_cell",
                    "group_id": cell.group_id,
                    "cell_id": cell.cell_id,
                    "file_name": cell.file_name,
                    "row_index": idx,
                    "equiv_cycle": float(cell.equiv_cycle[idx]),
                    "charge_capacity": float(cell.charge_capacity[idx]),
                    "discharge_capacity": discharge,
                    "capacity_retention": discharge / initial if initial > 0 else "",
                    "source_data_audit_only": True,
                    "tiny_validation_only": True,
                    "model_training_allowed": False,
                }
            )
    return rows


def build_summary_rows(cells: list[ParsedCell]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        status, note = quality_status(cell)
        cap = cell.discharge_capacity
        chg = cell.charge_capacity
        efc = cell.equiv_cycle
        initial = float(cap[0]) if len(cap) else np.nan
        rows.append(
            {
                "source_id": "REG-002",
                "dataset_role": "true_lmb",
                "cell_scope": "lmb_full_cell",
                "group_id": cell.group_id,
                "cell_id": cell.cell_id,
                "file_name": cell.file_name,
                "n_rows": len(cap),
                "initial_discharge_capacity": initial if len(cap) else "",
                "final_discharge_capacity": float(cap[-1]) if len(cap) else "",
                "min_discharge_capacity": float(np.nanmin(cap)) if len(cap) else "",
                "max_discharge_capacity": float(np.nanmax(cap)) if len(cap) else "",
                "initial_charge_capacity": float(chg[0]) if len(chg) else "",
                "final_charge_capacity": float(chg[-1]) if len(chg) else "",
                "max_equiv_cycle": float(np.nanmax(efc)) if len(efc) else "",
                "min_capacity_retention": float(np.nanmin(cap / initial)) if len(cap) and initial > 0 else "",
                "final_capacity_retention": float(cap[-1] / initial) if len(cap) and initial > 0 else "",
                "has_charge_capacity": bool(len(chg)),
                "has_discharge_capacity": bool(len(cap)),
                "has_equiv_cycle": bool(len(efc)),
                "quality_status": status,
                "quality_note": note,
                "source_data_audit_only": True,
                "tiny_validation_only": True,
                "model_training_allowed": False,
            }
        )
    return rows


def first_threshold_crossing(capacity_retention: np.ndarray, threshold: float) -> int | None:
    crossing = np.where(capacity_retention <= threshold)[0]
    if not len(crossing):
        return None
    return int(crossing[0])


def build_label_rows(cells: list[ParsedCell], thresholds: list[float]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for cell in cells:
        status, _ = quality_status(cell)
        if status.startswith("fail"):
            continue
        cap = cell.discharge_capacity
        efc = cell.equiv_cycle
        initial = float(cap[0])
        retention = cap / initial
        last_efc = float(efc[-1])
        for threshold in thresholds:
            event_idx = first_threshold_crossing(retention, threshold)
            observed = event_idx is not None
            label_key = f"capacity_eol_{int(threshold * 100)}"
            label_quality = (
                "exploratory_observed_capacity_threshold"
                if observed
                else "right_censored_no_threshold_crossing_in_downloaded_window"
            )
            blocking = "missing_protocol_and_terminal_reason;formal_training_blocked_until_metadata_gate"
            rows.append(
                {
                    "source_id": "REG-002",
                    "dataset_role": "true_lmb",
                    "cell_scope": "lmb_full_cell",
                    "group_id": cell.group_id,
                    "cell_id": cell.cell_id,
                    "label_key": label_key,
                    "threshold": threshold,
                    "event_observed": observed,
                    "event_row_index": event_idx if observed else "",
                    "event_equiv_cycle": float(efc[event_idx]) if observed else "",
                    "duration_until_event_or_last_equiv_cycle": float(efc[event_idx]) if observed else last_efc,
                    "rul_is_censored": not observed,
                    "label_quality": label_quality,
                    "exploratory_candidate_label": observed,
                    "formal_trainable_label": False,
                    "blocking_reason": blocking,
                    "source_data_audit_only": True,
                    "tiny_validation_only": True,
                    "model_training_allowed": False,
                }
            )
    return rows


def build_gate_rows(cells: list[ParsedCell], label_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    observed_eol80 = sum(
        1
        for row in label_rows
        if row["label_key"] == "capacity_eol_80" and row["event_observed"] is True
    )
    return [
        {
            "gate_name": "data_role_gate",
            "gate_status": "pass_for_public_lmb_full_cell_tiny_validation",
            "evidence": "REG-002 is treated as true_lmb / lmb_full_cell public data candidate.",
            "required_next_action": "Keep public-source caveat in reports.",
            "model_training_allowed": False,
        },
        {
            "gate_name": "machine_readable_capacity_gate",
            "gate_status": "pass",
            "evidence": f"{len(cells)} MAT files parsed with charge/discharge capacity and equivalent cycle arrays.",
            "required_next_action": "Generate reviewed features and labels from long table.",
            "model_training_allowed": False,
        },
        {
            "gate_name": "capacity_eol80_candidate_gate",
            "gate_status": "pass_for_exploratory_label_audit",
            "evidence": f"{observed_eol80} cells have observed capacity_eol_80 crossing in downloaded capacity-degradation files.",
            "required_next_action": "Review protocol and terminal reasons before training.",
            "model_training_allowed": False,
        },
        {
            "gate_name": "metadata_and_protocol_gate",
            "gate_status": "blocked_for_formal_training",
            "evidence": "Downloaded small MAT files do not include terminal reason, planned cycle count, step/record layer, or protocol metadata.",
            "required_next_action": "Download/read documentation or larger Data.mat only after parser review.",
            "model_training_allowed": False,
        },
        {
            "gate_name": "formal_training_gate",
            "gate_status": "blocked",
            "evidence": "Tiny validation and label audit are not model performance or a formal training set.",
            "required_next_action": "Run trainability audit after metadata/protocol review.",
            "model_training_allowed": False,
        },
    ]


def build_report_md(report: dict[str, Any]) -> str:
    return f"""# REG-002 Uppaluri/Onori Capacity Degradation Tiny Validation

```text
source_data_audit_only=True
tiny_validation_only=True
model_training_allowed=False
formal_training_set_created=False
```

## Summary

- Parsed capacity-degradation MAT files: {report['parsed_files']}
- Long rows: {report['long_rows']}
- Cells with observed capacity_eol_80 crossing: {report['capacity_eol_80_observed_cells']}
- Cells with observed capacity_eol_70 crossing: {report['capacity_eol_70_observed_cells']}

## Interpretation

REG-002 is currently the strongest public LMB full-cell data candidate in this project. The small `capacity_degradation.mat` files are machine-readable and contain charge capacity, discharge capacity, and equivalent cycle arrays.

However, this run is still a tiny validation and label audit. It does not create a formal training set because terminal reason, planned cycle count, protocol details, and step/record layers are not present in these small MAT files.

## Gate Decision

- Allow REG-002 feature/label audit: True
- Allow exploratory baseline planning after metadata review: Conditional
- Allow formal training now: False
- Next step: build a reviewed REG-002 baseline-ready export only after protocol/metadata gate and leakage rules are documented.
"""


def parse_reg002_capacity_degradation(input_root: Path, output_root: Path, overwrite: bool = False) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root already exists: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    cells = [load_capacity_file(path) for path in sorted(input_root.glob("*_capacity_degradation.mat"))]
    long_rows = build_long_rows(cells)
    summary_rows = build_summary_rows(cells)
    label_rows = build_label_rows(cells, thresholds=[0.8, 0.7])
    gate_rows = build_gate_rows(cells, label_rows)

    observed_eol80 = sum(
        1 for row in label_rows if row["label_key"] == "capacity_eol_80" and row["event_observed"] is True
    )
    observed_eol70 = sum(
        1 for row in label_rows if row["label_key"] == "capacity_eol_70" and row["event_observed"] is True
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_id": "REG-002",
        "dataset_role": "true_lmb",
        "cell_scope": "lmb_full_cell",
        "source_data_audit_only": True,
        "tiny_validation_only": True,
        "model_training_allowed": False,
        "formal_training_set_created": False,
        "parsed_files": len(cells),
        "long_rows": len(long_rows),
        "capacity_eol_80_observed_cells": observed_eol80,
        "capacity_eol_70_observed_cells": observed_eol70,
        "formal_training_blockers": [
            "missing_terminal_reason",
            "missing_planned_cycle_count",
            "missing_protocol_metadata_in_small_mat_files",
            "missing_step_or_record_layer_in_small_mat_files",
        ],
        "next_recommended_action": "Review protocol metadata and then create a REG-002 exploratory baseline-ready export; do not train yet.",
    }

    write_csv(output_root / "reg002_capacity_degradation_long.csv", long_rows, LONG_COLUMNS)
    write_csv(output_root / "reg002_cell_summary.csv", summary_rows, SUMMARY_COLUMNS)
    write_csv(output_root / "reg002_capacity_label_audit.csv", label_rows, LABEL_COLUMNS)
    write_csv(output_root / "reg002_trainability_gate.csv", gate_rows, GATE_COLUMNS)
    write_json(output_root / "reg002_capacity_tiny_validation_report.json", report)
    (output_root / "reg002_capacity_tiny_validation_report.md").write_text(build_report_md(report), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    parse_reg002_capacity_degradation(args.input_root, args.output_root, args.overwrite)


if __name__ == "__main__":
    main()
