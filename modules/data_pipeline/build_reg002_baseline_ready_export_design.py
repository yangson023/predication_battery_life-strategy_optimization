"""Design a REG-002 exploratory baseline-ready export.

This module turns the REG-002 capacity-degradation tiny validation output into
reviewable horizon rows and planning gates. It does not train a model, does not
create a formal training set, and keeps observed/censored labels separated.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


HORIZONS = [5, 10]
LABEL_KEYS = ["capacity_eol_80", "capacity_eol_70"]
FORMAL_BLOCKERS = [
    "missing_terminal_reason",
    "missing_planned_cycle_count",
    "missing_protocol_metadata_in_small_mat_files",
    "missing_step_or_record_layer_in_small_mat_files",
]

DESIGN_COLUMNS = [
    "source_id",
    "dataset_role",
    "cell_scope",
    "group_id",
    "cell_id",
    "label_key",
    "horizon_k",
    "row_id",
    "target_row_index",
    "target_equiv_cycle",
    "feature_window_end_row_index",
    "feature_window_end_equiv_cycle",
    "excluded_recent_window_start_row_index",
    "excluded_recent_window_end_row_index",
    "first_event_row_index",
    "first_event_equiv_cycle",
    "target_event_at_cycle",
    "discharge_capacity_retention_lag_k",
    "discharge_capacity_trend_past_5",
    "discharge_capacity_trend_past_10",
    "charge_capacity_trend_past_5",
    "charge_discharge_capacity_gap_lag_k",
    "early_cycle_capacity_slope",
    "feature_valid_count_past_5",
    "feature_valid_count_past_10",
    "split_policy",
    "random_row_split_used",
    "exploratory_export_candidate",
    "formal_training_set_created",
    "model_training_allowed",
]

POLICY_COLUMNS = [
    "feature_name",
    "feature_family",
    "uses_only_past_cycles",
    "horizon_dependent",
    "same_signal_source_risk",
    "allowed_in_exploratory_design",
    "formal_training_allowed_now",
    "note",
]

EXCLUDED_COLUMNS = [
    "source_id",
    "dataset_role",
    "cell_scope",
    "group_id",
    "cell_id",
    "label_key",
    "event_observed",
    "rul_is_censored",
    "exclusion_or_censoring_reason",
    "retained_use",
    "formal_training_set_created",
    "model_training_allowed",
]

LOCO_COLUMNS = [
    "label_key",
    "horizon_k",
    "split_type",
    "test_cell_id",
    "train_cell_count",
    "test_cell_count",
    "train_observed_cell_count",
    "test_observed_cell_count",
    "train_positive_targets",
    "test_positive_targets",
    "train_design_rows",
    "test_design_rows",
    "random_row_split_used",
    "planning_gate_status",
    "formal_training_set_created",
    "model_training_allowed",
]


@dataclass(frozen=True)
class LabelInfo:
    source_id: str
    dataset_role: str
    cell_scope: str
    group_id: str
    cell_id: str
    label_key: str
    event_observed: bool
    event_row_index: int | None
    event_equiv_cycle: float | None
    rul_is_censored: bool
    label_quality: str


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def parse_bool(value: Any) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def parse_int_or_none(value: Any) -> int | None:
    text = str(value).strip()
    if not text:
        return None
    return int(float(text))


def parse_float_or_none(value: Any) -> float | None:
    text = str(value).strip()
    if not text:
        return None
    return float(text)


def load_labels(label_path: Path) -> dict[tuple[str, str], LabelInfo]:
    labels: dict[tuple[str, str], LabelInfo] = {}
    for row in read_csv(label_path):
        if row["label_key"] not in LABEL_KEYS:
            continue
        label = LabelInfo(
            source_id=row["source_id"],
            dataset_role=row["dataset_role"],
            cell_scope=row["cell_scope"],
            group_id=row["group_id"],
            cell_id=row["cell_id"],
            label_key=row["label_key"],
            event_observed=parse_bool(row["event_observed"]),
            event_row_index=parse_int_or_none(row["event_row_index"]),
            event_equiv_cycle=parse_float_or_none(row["event_equiv_cycle"]),
            rul_is_censored=parse_bool(row["rul_is_censored"]),
            label_quality=row["label_quality"],
        )
        labels[(label.cell_id, label.label_key)] = label
    return labels


def group_long_rows(long_rows: list[dict[str, str]]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in long_rows:
        converted = dict(row)
        converted["row_index"] = int(float(row["row_index"]))
        converted["equiv_cycle"] = float(row["equiv_cycle"])
        converted["charge_capacity"] = float(row["charge_capacity"])
        converted["discharge_capacity"] = float(row["discharge_capacity"])
        converted["capacity_retention"] = float(row["capacity_retention"])
        grouped[row["cell_id"]].append(converted)
    for rows in grouped.values():
        rows.sort(key=lambda item: item["row_index"])
    return grouped


def slope(rows: list[dict[str, Any]], value_key: str) -> float | str:
    if len(rows) < 2:
        return ""
    first = rows[0]
    last = rows[-1]
    denom = float(last["equiv_cycle"]) - float(first["equiv_cycle"])
    if denom == 0:
        return ""
    return (float(last[value_key]) - float(first[value_key])) / denom


def window_ending_at(rows: list[dict[str, Any]], end_pos: int, size: int) -> list[dict[str, Any]]:
    if end_pos < 0:
        return []
    start = max(0, end_pos - size + 1)
    return rows[start : end_pos + 1]


def early_cycle_capacity_slope(rows: list[dict[str, Any]]) -> float | str:
    return slope(rows[: min(10, len(rows))], "discharge_capacity")


def build_design_rows_for_label(
    grouped_rows: dict[str, list[dict[str, Any]]],
    labels: dict[tuple[str, str], LabelInfo],
    label_key: str,
    horizon_k: int,
) -> list[dict[str, Any]]:
    design_rows: list[dict[str, Any]] = []
    for cell_id, rows in grouped_rows.items():
        label = labels.get((cell_id, label_key))
        if label is None or not label.event_observed or label.event_row_index is None:
            continue
        event_idx = label.event_row_index
        by_index = {row["row_index"]: row for row in rows}
        if event_idx not in by_index:
            continue
        early_slope = early_cycle_capacity_slope(rows)
        for target_idx in range(horizon_k, event_idx + 1):
            if target_idx not in by_index:
                continue
            feature_end_idx = target_idx - horizon_k
            if feature_end_idx not in by_index:
                continue
            feature_end_position = next(i for i, row in enumerate(rows) if row["row_index"] == feature_end_idx)
            lag_row = by_index[feature_end_idx]
            window5 = window_ending_at(rows, feature_end_position, 5)
            window10 = window_ending_at(rows, feature_end_position, 10)
            target_row = by_index[target_idx]
            design_rows.append(
                {
                    "source_id": label.source_id,
                    "dataset_role": label.dataset_role,
                    "cell_scope": label.cell_scope,
                    "group_id": label.group_id,
                    "cell_id": cell_id,
                    "label_key": label_key,
                    "horizon_k": horizon_k,
                    "row_id": f"REG-002__{label_key}__h{horizon_k}__{cell_id}__target_{target_idx}",
                    "target_row_index": target_idx,
                    "target_equiv_cycle": target_row["equiv_cycle"],
                    "feature_window_end_row_index": feature_end_idx,
                    "feature_window_end_equiv_cycle": lag_row["equiv_cycle"],
                    "excluded_recent_window_start_row_index": feature_end_idx + 1,
                    "excluded_recent_window_end_row_index": target_idx,
                    "first_event_row_index": event_idx,
                    "first_event_equiv_cycle": label.event_equiv_cycle,
                    "target_event_at_cycle": int(target_idx == event_idx),
                    "discharge_capacity_retention_lag_k": lag_row["capacity_retention"],
                    "discharge_capacity_trend_past_5": slope(window5, "discharge_capacity"),
                    "discharge_capacity_trend_past_10": slope(window10, "discharge_capacity"),
                    "charge_capacity_trend_past_5": slope(window5, "charge_capacity"),
                    "charge_discharge_capacity_gap_lag_k": lag_row["charge_capacity"] - lag_row["discharge_capacity"],
                    "early_cycle_capacity_slope": early_slope,
                    "feature_valid_count_past_5": len(window5),
                    "feature_valid_count_past_10": len(window10),
                    "split_policy": "leave_one_cell_out_planning_only",
                    "random_row_split_used": False,
                    "exploratory_export_candidate": True,
                    "formal_training_set_created": False,
                    "model_training_allowed": False,
                }
            )
    return design_rows


def build_feature_policy_rows() -> list[dict[str, Any]]:
    return [
        {
            "feature_name": "discharge_capacity_retention_lag_k",
            "feature_family": "capacity_retention",
            "uses_only_past_cycles": True,
            "horizon_dependent": True,
            "same_signal_source_risk": True,
            "allowed_in_exploratory_design": True,
            "formal_training_allowed_now": False,
            "note": "Uses capacity history before target cycle; useful for method development but same-signal-source risk remains.",
        },
        {
            "feature_name": "discharge_capacity_trend_past_5",
            "feature_family": "capacity_trend",
            "uses_only_past_cycles": True,
            "horizon_dependent": True,
            "same_signal_source_risk": True,
            "allowed_in_exploratory_design": True,
            "formal_training_allowed_now": False,
            "note": "Past-only trend ending at t-k.",
        },
        {
            "feature_name": "discharge_capacity_trend_past_10",
            "feature_family": "capacity_trend",
            "uses_only_past_cycles": True,
            "horizon_dependent": True,
            "same_signal_source_risk": True,
            "allowed_in_exploratory_design": True,
            "formal_training_allowed_now": False,
            "note": "Longer past-only capacity trend ending at t-k.",
        },
        {
            "feature_name": "charge_capacity_trend_past_5",
            "feature_family": "charge_capacity_trend",
            "uses_only_past_cycles": True,
            "horizon_dependent": True,
            "same_signal_source_risk": True,
            "allowed_in_exploratory_design": True,
            "formal_training_allowed_now": False,
            "note": "Charge-capacity trend can support full-cell method development but is not mechanism-complete.",
        },
        {
            "feature_name": "charge_discharge_capacity_gap_lag_k",
            "feature_family": "capacity_gap",
            "uses_only_past_cycles": True,
            "horizon_dependent": True,
            "same_signal_source_risk": True,
            "allowed_in_exploratory_design": True,
            "formal_training_allowed_now": False,
            "note": "Past cycle charge/discharge gap proxy; needs protocol metadata before formal use.",
        },
        {
            "feature_name": "early_cycle_capacity_slope",
            "feature_family": "early_capacity_shape",
            "uses_only_past_cycles": True,
            "horizon_dependent": False,
            "same_signal_source_risk": True,
            "allowed_in_exploratory_design": True,
            "formal_training_allowed_now": False,
            "note": "Cell-level early trend, included only as method-development candidate.",
        },
    ]


def build_excluded_rows(labels: dict[tuple[str, str], LabelInfo]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label in labels.values():
        if label.event_observed:
            continue
        rows.append(
            {
                "source_id": label.source_id,
                "dataset_role": label.dataset_role,
                "cell_scope": label.cell_scope,
                "group_id": label.group_id,
                "cell_id": label.cell_id,
                "label_key": label.label_key,
                "event_observed": label.event_observed,
                "rul_is_censored": label.rul_is_censored,
                "exclusion_or_censoring_reason": "right_censored_or_protocol_unknown_no_threshold_crossing",
                "retained_use": "censored_context_for_future_protocol_review",
                "formal_training_set_created": False,
                "model_training_allowed": False,
            }
        )
    return rows


def build_loco_rows(all_design_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_label_horizon: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in all_design_rows:
        by_label_horizon[(row["label_key"], int(row["horizon_k"]))].append(row)
    for (label_key, horizon_k), design_rows in sorted(by_label_horizon.items()):
        cells = sorted({str(row["cell_id"]) for row in design_rows})
        for test_cell in cells:
            train_rows = [row for row in design_rows if row["cell_id"] != test_cell]
            test_rows = [row for row in design_rows if row["cell_id"] == test_cell]
            train_positive = sum(int(row["target_event_at_cycle"]) for row in train_rows)
            test_positive = sum(int(row["target_event_at_cycle"]) for row in test_rows)
            status = (
                "pass_for_tiny_exploratory_baseline_planning"
                if label_key == "capacity_eol_80" and train_positive >= 8 and test_positive == 1
                else "audit_only_small_observed_count"
            )
            rows.append(
                {
                    "label_key": label_key,
                    "horizon_k": horizon_k,
                    "split_type": "leave_one_cell_out",
                    "test_cell_id": test_cell,
                    "train_cell_count": len(cells) - 1,
                    "test_cell_count": 1,
                    "train_observed_cell_count": train_positive,
                    "test_observed_cell_count": test_positive,
                    "train_positive_targets": train_positive,
                    "test_positive_targets": test_positive,
                    "train_design_rows": len(train_rows),
                    "test_design_rows": len(test_rows),
                    "random_row_split_used": False,
                    "planning_gate_status": status,
                    "formal_training_set_created": False,
                    "model_training_allowed": False,
                }
            )
    return rows


def build_report_md(report: dict[str, Any]) -> str:
    return f"""# REG-002 Baseline-Ready Export Design

```text
exploratory_method_development_only=True
formal_training_set_created=False
model_training_allowed=False
random_row_split_used=False
```

## 结论

REG-002 适合进入 exploratory baseline-ready export design，尤其是 `capacity_eol_80`。这一数据包是公开 LMB full-cell 方法开发候选，不是本项目最终实验室数据，也不是正式训练集。

## 证据

- capacity_eol_80 observed cells: {report['capacity_eol_80_observed_cells']}
- capacity_eol_70 observed cells: {report['capacity_eol_70_observed_cells']}
- capacity_eol_80 design rows: {report['capacity_eol_80_design_rows']}
- capacity_eol_70 design rows: {report['capacity_eol_70_design_rows']}
- horizons: {', '.join(str(item) for item in report['horizons'])}
- split design: leave-one-cell-out planning only

## 风险

正式训练仍被阻断，原因包括：

{chr(10).join(f'- {item}' for item in report['formal_training_blockers'])}

这些小 MAT 文件目前只能支撑容量曲线方法开发和标签审计。它们不能替代实验室条件清晰、协议完整、终止原因明确的 full-cell 数据。

## 下一步

- 允许进入 tiny exploratory baseline planning: {report['allow_tiny_exploratory_baseline_planning']}
- 仍禁止正式模型训练: True
- 建议 Trae 并行补充 REG-002 的论文语义、protocol、组别配置和终止信息。
"""


def build_reg002_baseline_ready_export_design(input_root: Path, output_root: Path, overwrite: bool = False) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root already exists: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    long_rows = read_csv(input_root / "reg002_capacity_degradation_long.csv")
    label_rows = load_labels(input_root / "reg002_capacity_label_audit.csv")
    grouped_rows = group_long_rows(long_rows)

    design_by_label: dict[str, list[dict[str, Any]]] = {}
    all_design_rows: list[dict[str, Any]] = []
    for label_key in LABEL_KEYS:
        rows_for_label: list[dict[str, Any]] = []
        for horizon_k in HORIZONS:
            rows_for_label.extend(build_design_rows_for_label(grouped_rows, label_rows, label_key, horizon_k))
        design_by_label[label_key] = rows_for_label
        all_design_rows.extend(rows_for_label)

    policy_rows = build_feature_policy_rows()
    excluded_rows = build_excluded_rows(label_rows)
    loco_rows = build_loco_rows(all_design_rows)

    observed_counts = {
        label_key: sum(1 for label in label_rows.values() if label.label_key == label_key and label.event_observed)
        for label_key in LABEL_KEYS
    }
    censored_counts = {
        label_key: sum(1 for label in label_rows.values() if label.label_key == label_key and not label.event_observed)
        for label_key in LABEL_KEYS
    }
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_id": "REG-002",
        "dataset_role": "true_lmb",
        "cell_scope": "lmb_full_cell",
        "exploratory_method_development_only": True,
        "formal_training_set_created": False,
        "model_training_allowed": False,
        "random_row_split_used": False,
        "features_targets_metadata_separated_in_design": True,
        "horizons": HORIZONS,
        "capacity_eol_80_observed_cells": observed_counts["capacity_eol_80"],
        "capacity_eol_80_censored_cells": censored_counts["capacity_eol_80"],
        "capacity_eol_70_observed_cells": observed_counts["capacity_eol_70"],
        "capacity_eol_70_censored_cells": censored_counts["capacity_eol_70"],
        "capacity_eol_80_design_rows": len(design_by_label["capacity_eol_80"]),
        "capacity_eol_70_design_rows": len(design_by_label["capacity_eol_70"]),
        "formal_training_blockers": FORMAL_BLOCKERS,
        "allow_tiny_exploratory_baseline_planning": observed_counts["capacity_eol_80"] >= 8,
        "capacity_eol_80_preferred_over_capacity_eol_70": True,
        "recommendation": "Use REG-002 for exploratory full-cell LMB method-development planning; wait for protocol metadata before any formal training gate.",
    }

    write_csv(output_root / "reg002_capacity_eol80_export_design.csv", design_by_label["capacity_eol_80"], DESIGN_COLUMNS)
    write_csv(output_root / "reg002_capacity_eol70_export_design.csv", design_by_label["capacity_eol_70"], DESIGN_COLUMNS)
    write_csv(output_root / "reg002_candidate_feature_policy.csv", policy_rows, POLICY_COLUMNS)
    write_csv(output_root / "reg002_excluded_or_censored_cells.csv", excluded_rows, EXCLUDED_COLUMNS)
    write_csv(output_root / "reg002_loco_planning_gate.csv", loco_rows, LOCO_COLUMNS)
    write_json(output_root / "reg002_baseline_ready_export_design_report.json", report)
    (output_root / "reg002_baseline_ready_export_design_report.md").write_text(build_report_md(report), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    build_reg002_baseline_ready_export_design(args.input_root, args.output_root, args.overwrite)


if __name__ == "__main__":
    main()
