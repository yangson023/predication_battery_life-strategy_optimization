"""Plan REG-002 tiny exploratory baseline gates without training.

The planner reads REG-002 export-design tables and creates a leave-one-cell-out
planning report for capacity_eol_80. It does not train, refit, enter
``rul-prediction``, or report formal model metrics.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TARGET_LABEL_KEY = "capacity_eol_80"
SECONDARY_LABEL_KEY = "capacity_eol_70"
FORBIDDEN_FEATURE_TOKENS = ("target", "label", "future", "event")

FOLD_COLUMNS = [
    "label_key",
    "horizon_k",
    "fold_id",
    "split_type",
    "test_cell_id",
    "train_cell_ids",
    "train_observed_cell_count",
    "test_observed_cell_count",
    "train_rows",
    "test_rows",
    "train_positive_targets",
    "test_positive_targets",
    "train_negative_targets",
    "test_negative_targets",
    "random_row_split_used",
    "fold_gate_status",
    "tiny_smoke_test_application_allowed",
    "formal_training_set_created",
    "model_training_allowed",
]

RISK_COLUMNS = [
    "horizon_k",
    "risk_key",
    "risk_level",
    "evidence",
    "decision_impact",
    "model_training_allowed",
]

FEATURE_RISK_COLUMNS = [
    "feature_name",
    "feature_family",
    "uses_only_past_cycles",
    "horizon_dependent",
    "same_signal_source_risk",
    "forbidden_token_found",
    "risk_level",
    "allowed_for_tiny_smoke_test_candidate",
    "formal_training_allowed_now",
    "note",
]

CENSORED_COLUMNS = [
    "source_id",
    "dataset_role",
    "cell_scope",
    "group_id",
    "cell_id",
    "label_key",
    "event_observed",
    "rul_is_censored",
    "censored_handling",
    "included_in_loco_planning",
    "model_training_allowed",
]


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


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes", "y"}


def parse_int(value: object) -> int:
    text = str(value).strip()
    if not text:
        return 0
    return int(float(text))


def load_report(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def group_by_horizon(rows: list[dict[str, str]]) -> dict[int, list[dict[str, str]]]:
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("label_key") != TARGET_LABEL_KEY:
            continue
        grouped[parse_int(row.get("horizon_k"))].append(row)
    return dict(sorted(grouped.items()))


def build_loco_fold_rows(design_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    grouped = group_by_horizon(design_rows)
    for horizon_k, horizon_rows in grouped.items():
        cells = sorted({row["cell_id"] for row in horizon_rows})
        by_cell: dict[str, list[dict[str, str]]] = {
            cell: [row for row in horizon_rows if row["cell_id"] == cell] for cell in cells
        }
        for fold_index, test_cell in enumerate(cells, start=1):
            train_cells = [cell for cell in cells if cell != test_cell]
            train_rows = [row for cell in train_cells for row in by_cell[cell]]
            test_rows = by_cell[test_cell]
            train_positive = sum(parse_int(row["target_event_at_cycle"]) for row in train_rows)
            test_positive = sum(parse_int(row["target_event_at_cycle"]) for row in test_rows)
            fold_pass = len(train_cells) >= 8 and train_positive >= 8 and test_positive == 1
            rows.append(
                {
                    "label_key": TARGET_LABEL_KEY,
                    "horizon_k": horizon_k,
                    "fold_id": f"h{horizon_k}_LOCO_{fold_index}",
                    "split_type": "leave_one_cell_out",
                    "test_cell_id": test_cell,
                    "train_cell_ids": ";".join(train_cells),
                    "train_observed_cell_count": len(train_cells),
                    "test_observed_cell_count": 1,
                    "train_rows": len(train_rows),
                    "test_rows": len(test_rows),
                    "train_positive_targets": train_positive,
                    "test_positive_targets": test_positive,
                    "train_negative_targets": len(train_rows) - train_positive,
                    "test_negative_targets": len(test_rows) - test_positive,
                    "random_row_split_used": False,
                    "fold_gate_status": "pass_for_tiny_exploratory_smoke_test_application" if fold_pass else "blocked_or_high_risk_fold",
                    "tiny_smoke_test_application_allowed": fold_pass,
                    "formal_training_set_created": False,
                    "model_training_allowed": False,
                }
            )
    return rows


def forbidden_token_in_feature(feature_name: str) -> str:
    lower = feature_name.lower()
    found = [token for token in FORBIDDEN_FEATURE_TOKENS if token in lower]
    return ";".join(found)


def build_feature_risk_rows(policy_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in policy_rows:
        same_signal = parse_bool(row.get("same_signal_source_risk"))
        past_only = parse_bool(row.get("uses_only_past_cycles"))
        forbidden = forbidden_token_in_feature(row.get("feature_name", ""))
        risk_level = "blocking" if forbidden or not past_only else "high" if same_signal else "review"
        rows.append(
            {
                "feature_name": row.get("feature_name", ""),
                "feature_family": row.get("feature_family", ""),
                "uses_only_past_cycles": past_only,
                "horizon_dependent": parse_bool(row.get("horizon_dependent")),
                "same_signal_source_risk": same_signal,
                "forbidden_token_found": forbidden,
                "risk_level": risk_level,
                "allowed_for_tiny_smoke_test_candidate": not bool(forbidden) and past_only,
                "formal_training_allowed_now": False,
                "note": row.get("note", ""),
            }
        )
    return rows


def build_censored_audit_rows(excluded_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in excluded_rows:
        if row.get("label_key") != TARGET_LABEL_KEY:
            continue
        rows.append(
            {
                "source_id": row.get("source_id", ""),
                "dataset_role": row.get("dataset_role", ""),
                "cell_scope": row.get("cell_scope", ""),
                "group_id": row.get("group_id", ""),
                "cell_id": row.get("cell_id", ""),
                "label_key": row.get("label_key", ""),
                "event_observed": False,
                "rul_is_censored": parse_bool(row.get("rul_is_censored")),
                "censored_handling": "excluded_from_observed_loco_planning;retained_for_protocol_review",
                "included_in_loco_planning": False,
                "model_training_allowed": False,
            }
        )
    return rows


def build_risk_rows(
    grouped_rows: dict[int, list[dict[str, str]]],
    fold_rows: list[dict[str, Any]],
    feature_risk_rows: list[dict[str, Any]],
    censored_rows: list[dict[str, Any]],
    export_report: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    same_signal_count = sum(1 for row in feature_risk_rows if row["same_signal_source_risk"] is True)
    for horizon_k, horizon_rows in grouped_rows.items():
        cells = sorted({row["cell_id"] for row in horizon_rows})
        positive_targets = sum(parse_int(row["target_event_at_cycle"]) for row in horizon_rows)
        folds_for_horizon = [row for row in fold_rows if row["horizon_k"] == horizon_k]
        min_train_observed = min((int(row["train_observed_cell_count"]) for row in folds_for_horizon), default=0)
        min_train_positive = min((int(row["train_positive_targets"]) for row in folds_for_horizon), default=0)
        rows.extend(
            [
                {
                    "horizon_k": horizon_k,
                    "risk_key": "public_method_development_data_not_lab_final_dataset",
                    "risk_level": "medium",
                    "evidence": "REG-002 is public LMB full-cell method-development data; it is not the final lab dataset.",
                    "decision_impact": "Keep exploratory wording and wait for lab full-cell data for primary validation.",
                    "model_training_allowed": False,
                },
                {
                    "horizon_k": horizon_k,
                    "risk_key": "observed_cell_count_for_loco",
                    "risk_level": "medium" if min_train_observed >= 8 else "high",
                    "evidence": f"{len(cells)} observed cells; minimum train observed cells per LOCO fold is {min_train_observed}.",
                    "decision_impact": "Allows tiny smoke-test application only, not formal training.",
                    "model_training_allowed": False,
                },
                {
                    "horizon_k": horizon_k,
                    "risk_key": "positive_target_count",
                    "risk_level": "medium" if min_train_positive >= 8 else "high",
                    "evidence": f"{positive_targets} positive target rows; minimum train positives per fold is {min_train_positive}.",
                    "decision_impact": "Enough for planning, still exploratory because each cell contributes one threshold event.",
                    "model_training_allowed": False,
                },
                {
                    "horizon_k": horizon_k,
                    "risk_key": "capacity_same_signal_source_risk",
                    "risk_level": "high" if same_signal_count else "review",
                    "evidence": f"{same_signal_count} candidate features share the capacity signal family with capacity_eol_80.",
                    "decision_impact": "Any tiny smoke-test must be described as capacity-curve method development.",
                    "model_training_allowed": False,
                },
                {
                    "horizon_k": horizon_k,
                    "risk_key": "censored_cells_excluded_from_observed_loco",
                    "risk_level": "medium" if censored_rows else "low",
                    "evidence": f"{len(censored_rows)} capacity_eol_80 censored cells are retained for review but excluded from observed LOCO planning.",
                    "decision_impact": "Prevents censored cells from being treated as observed failures.",
                    "model_training_allowed": False,
                },
                {
                    "horizon_k": horizon_k,
                    "risk_key": "formal_metadata_blockers",
                    "risk_level": "blocking_for_formal_training",
                    "evidence": ";".join(export_report.get("formal_training_blockers", [])),
                    "decision_impact": "Blocks formal training until protocol and terminal metadata are reviewed.",
                    "model_training_allowed": False,
                },
            ]
        )
    if set(grouped_rows) >= {5, 10}:
        h5_rows = len(grouped_rows[5])
        h10_rows = len(grouped_rows[10])
        rows.append(
            {
                "horizon_k": "comparison",
                "risk_key": "horizon_10_vs_5_tradeoff",
                "risk_level": "review",
                "evidence": f"horizon=5 rows={h5_rows}; horizon=10 rows={h10_rows}. Horizon=10 gives longer separation but fewer usable rows.",
                "decision_impact": "Keep h5 and h10 separate; do not mix horizons.",
                "model_training_allowed": False,
            }
        )
    eol70_observed = export_report.get("capacity_eol_70_observed_cells", 0)
    rows.append(
        {
            "horizon_k": "secondary_label",
            "risk_key": "capacity_eol70_too_sparse_for_main_planning",
            "risk_level": "high",
            "evidence": f"capacity_eol_70 observed cells={eol70_observed}; retain only as secondary audit reference.",
            "decision_impact": "Do not use capacity_eol_70 as the first REG-002 tiny baseline target.",
            "model_training_allowed": False,
        }
    )
    return rows


def build_report_md(report: dict[str, Any]) -> str:
    return f"""# REG-002 Tiny Exploratory Baseline Planning

```text
planning_only=True
target_label=capacity_eol_80
formal_training_set_created=False
model_training_allowed=False
random_row_split_used=False
```

## 结论

REG-002 的 `capacity_eol_80` 可以申请进入 tiny exploratory baseline smoke-test，但这仍然只是公开 LMB full-cell 方法开发，不是正式模型训练，也不是本项目最终实验室数据结论。

## 证据

- observed cells for capacity_eol_80: {report['capacity_eol_80_observed_cells']}
- censored cells for capacity_eol_80: {report['capacity_eol_80_censored_cells']}
- horizon=5 design rows: {report['horizon_summary']['5']['rows']}
- horizon=10 design rows: {report['horizon_summary']['10']['rows']}
- minimum train observed cells per LOCO fold: {report['minimum_train_observed_cells_per_fold']}
- minimum train positive targets per LOCO fold: {report['minimum_train_positive_targets_per_fold']}

## 风险

- 所有候选特征仍是 capacity-family same-signal-source risk。
- REG-002 小 MAT 文件缺少 terminal reason、planned cycle count、protocol metadata、step/record layer。
- `capacity_eol_70` observed cell 太少，只能作为次级审计参考。
- horizon=10 相比 horizon=5 有更长预测间隔，但行数更少；两个 horizon 不能混合。

## 下一步

- allow_tiny_exploratory_baseline_smoke_test_application: {report['allow_tiny_exploratory_baseline_smoke_test_application']}
- model_training_allowed: False
- 建议下一步只运行 logistic-regression tiny smoke-test，并继续禁止正式性能表述。
"""


def plan_reg002_tiny_exploratory_baseline(input_root: Path, output_root: Path, overwrite: bool = False) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root already exists: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    eol80_rows = read_csv(input_root / "reg002_capacity_eol80_export_design.csv")
    policy_rows = read_csv(input_root / "reg002_candidate_feature_policy.csv")
    excluded_rows = read_csv(input_root / "reg002_excluded_or_censored_cells.csv")
    export_report = load_report(input_root / "reg002_baseline_ready_export_design_report.json")

    grouped = group_by_horizon(eol80_rows)
    fold_rows = build_loco_fold_rows(eol80_rows)
    feature_risk_rows = build_feature_risk_rows(policy_rows)
    censored_rows = build_censored_audit_rows(excluded_rows)
    risk_rows = build_risk_rows(grouped, fold_rows, feature_risk_rows, censored_rows, export_report)

    min_train_observed = min((int(row["train_observed_cell_count"]) for row in fold_rows), default=0)
    min_train_positive = min((int(row["train_positive_targets"]) for row in fold_rows), default=0)
    horizon_summary = {
        str(horizon): {
            "rows": len(rows),
            "cells": len({row["cell_id"] for row in rows}),
            "positive_targets": sum(parse_int(row["target_event_at_cycle"]) for row in rows),
        }
        for horizon, rows in grouped.items()
    }
    forbidden_feature_count = sum(1 for row in feature_risk_rows if row["forbidden_token_found"])
    allow_application = (
        min_train_observed >= 8
        and min_train_positive >= 8
        and forbidden_feature_count == 0
        and all(parse_bool(row["random_row_split_used"]) is False for row in fold_rows)
    )
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_id": "REG-002",
        "dataset_role": "true_lmb",
        "cell_scope": "lmb_full_cell",
        "planning_only": True,
        "target_label": TARGET_LABEL_KEY,
        "secondary_label_reference_only": SECONDARY_LABEL_KEY,
        "formal_training_set_created": False,
        "model_training_allowed": False,
        "random_row_split_used": False,
        "capacity_eol_80_observed_cells": export_report.get("capacity_eol_80_observed_cells", 0),
        "capacity_eol_80_censored_cells": export_report.get("capacity_eol_80_censored_cells", len(censored_rows)),
        "capacity_eol_70_observed_cells": export_report.get("capacity_eol_70_observed_cells", 0),
        "horizon_summary": horizon_summary,
        "fold_count": len(fold_rows),
        "minimum_train_observed_cells_per_fold": min_train_observed,
        "minimum_train_positive_targets_per_fold": min_train_positive,
        "same_signal_source_feature_count": sum(1 for row in feature_risk_rows if row["same_signal_source_risk"] is True),
        "forbidden_feature_count": forbidden_feature_count,
        "allow_tiny_exploratory_baseline_smoke_test_application": allow_application,
        "formal_training_blockers": export_report.get("formal_training_blockers", []),
        "recommendation": "Apply for a tiny exploratory smoke-test only; do not make formal model claims.",
    }

    write_csv(output_root / "reg002_capacity_eol80_loco_fold_plan.csv", fold_rows, FOLD_COLUMNS)
    write_csv(output_root / "reg002_capacity_eol80_data_risk_summary.csv", risk_rows, RISK_COLUMNS)
    write_csv(output_root / "reg002_capacity_eol80_feature_risk_audit.csv", feature_risk_rows, FEATURE_RISK_COLUMNS)
    write_csv(output_root / "reg002_capacity_eol80_censored_cell_audit.csv", censored_rows, CENSORED_COLUMNS)
    write_json(output_root / "reg002_tiny_exploratory_baseline_plan_report.json", report)
    (output_root / "reg002_tiny_exploratory_baseline_plan_report.md").write_text(build_report_md(report), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    plan_reg002_tiny_exploratory_baseline(args.input_root, args.output_root, args.overwrite)


if __name__ == "__main__":
    main()
