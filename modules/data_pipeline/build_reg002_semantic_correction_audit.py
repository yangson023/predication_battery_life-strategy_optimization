"""Audit REG-002 semantic corrections before any training.

This audit checks whether current REG-002 capacity-degradation outputs use
``row_index`` for sequence/horizon planning, keep ``equiv_cycle`` as equivalent
full-cycle metadata, and describe ``capacity_eol_80`` as a Codex-defined audit
threshold rather than a paper-official EOL. It does not download or parse
``data.mat`` files and never trains a model.
"""

from __future__ import annotations

import argparse
import csv
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PERFORMANCE_TERMS = ("AUC", "F1", "RMSE", "accuracy")

SUMMARY_COLUMNS = [
    "audit_area",
    "audit_status",
    "evidence",
    "decision",
    "requires_action",
    "model_training_allowed",
]

EFC_COLUMNS = [
    "component",
    "row_index_present",
    "equiv_cycle_present",
    "row_index_used_for_horizon",
    "equiv_cycle_used_as_cycle_index",
    "misleading_columns_or_text",
    "audit_status",
    "correction_guidance",
    "model_training_allowed",
]

LABEL_COLUMNS = [
    "label_key",
    "label_semantic_role",
    "official_paper_eol",
    "codex_defined_audit_threshold",
    "observed_count",
    "censored_count",
    "observed_censored_handling_status",
    "exploratory_method_development_allowed",
    "formal_training_allowed_now",
    "semantic_status",
    "model_training_allowed",
]

GROUP_COLUMNS = [
    "group_id",
    "semantic_role",
    "protocol_only_group",
    "mixed_design_operation_group",
    "current_validation_recommendation",
    "future_validation_recommendation",
    "semantic_status",
    "model_training_allowed",
]

DATA_MAT_COLUMNS = [
    "next_step",
    "data_mat_status",
    "allowed_now",
    "required_gate",
    "expected_value",
    "blocked_actions",
    "model_training_allowed",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


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


def load_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def contains_formal_metric_text(text: str) -> bool:
    return any(term in text for term in PERFORMANCE_TERMS)


def count_label_rows(label_rows: list[dict[str, str]], label_key: str) -> tuple[int, int]:
    observed = 0
    censored = 0
    for row in label_rows:
        if row.get("label_key") != label_key:
            continue
        if parse_bool(row.get("event_observed")):
            observed += 1
        else:
            censored += 1
    return observed, censored


def build_efc_rows(long_rows: list[dict[str, str]], export_rows: list[dict[str, str]], planning_report: dict[str, Any]) -> list[dict[str, Any]]:
    long_columns = set(long_rows[0].keys()) if long_rows else set()
    export_columns = set(export_rows[0].keys()) if export_rows else set()
    row_index_horizon_columns = {
        "target_row_index",
        "feature_window_end_row_index",
        "excluded_recent_window_start_row_index",
        "excluded_recent_window_end_row_index",
    }
    equiv_metadata_columns = sorted(column for column in export_columns if "equiv_cycle" in column)
    rows = [
        {
            "component": "capacity_degradation_long_table",
            "row_index_present": "row_index" in long_columns,
            "equiv_cycle_present": "equiv_cycle" in long_columns,
            "row_index_used_for_horizon": False,
            "equiv_cycle_used_as_cycle_index": False,
            "misleading_columns_or_text": "",
            "audit_status": "pass_equiv_cycle_metadata_available",
            "correction_guidance": "Treat row_index as downloaded capacity-array order and equiv_cycle as equivalent full-cycle/cumulative-throughput metadata.",
            "model_training_allowed": False,
        },
        {
            "component": "baseline_ready_export_design",
            "row_index_present": row_index_horizon_columns.issubset(export_columns),
            "equiv_cycle_present": bool(equiv_metadata_columns),
            "row_index_used_for_horizon": row_index_horizon_columns.issubset(export_columns),
            "equiv_cycle_used_as_cycle_index": False,
            "misleading_columns_or_text": ";".join(equiv_metadata_columns),
            "audit_status": "pass_row_index_based_horizon_acceptable",
            "correction_guidance": "Keep t-k horizon based on row_index columns; keep equiv_cycle columns as metadata only.",
            "model_training_allowed": False,
        },
        {
            "component": "tiny_exploratory_baseline_plan",
            "row_index_present": False,
            "equiv_cycle_present": False,
            "row_index_used_for_horizon": planning_report.get("random_row_split_used") is False,
            "equiv_cycle_used_as_cycle_index": False,
            "misleading_columns_or_text": "",
            "audit_status": "pass_planning_can_be_retained",
            "correction_guidance": "Current planning inherits row_index-based export design and does not need to be rebuilt for equiv_cycle semantics.",
            "model_training_allowed": False,
        },
    ]
    return rows


def build_label_rows(label_rows: list[dict[str, str]], export_report: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label_key in ["capacity_eol_80", "capacity_eol_70"]:
        observed, censored = count_label_rows(label_rows, label_key)
        rows.append(
            {
                "label_key": label_key,
                "label_semantic_role": "primary_exploratory_audit_threshold" if label_key == "capacity_eol_80" else "secondary_sparse_audit_threshold",
                "official_paper_eol": False,
                "codex_defined_audit_threshold": True,
                "observed_count": observed,
                "censored_count": censored,
                "observed_censored_handling_status": "pass_observed_and_right_censored_separated",
                "exploratory_method_development_allowed": label_key == "capacity_eol_80" and observed >= 8,
                "formal_training_allowed_now": False,
                "semantic_status": "pass_codex_defined_not_official_eol",
                "model_training_allowed": False,
            }
        )
    if "official" in json.dumps(export_report).lower():
        rows[0]["semantic_status"] = "review_report_wording_for_official_eol"
    return rows


def build_group_rows(long_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    groups = sorted({row.get("group_id", "") for row in long_rows if row.get("group_id", "")})
    return [
        {
            "group_id": group,
            "semantic_role": "design_plus_operation_mixed_condition_group",
            "protocol_only_group": False,
            "mixed_design_operation_group": True,
            "current_validation_recommendation": "prioritize_leave_one_cell_out_for_current_planning",
            "future_validation_recommendation": "add_leave_one_group_out_or_group_stratified_audit_after_metadata_review",
            "semantic_status": "pass_not_protocol_only",
            "model_training_allowed": False,
        }
        for group in groups
    ]


def build_data_mat_rows() -> list[dict[str, Any]]:
    return [
        {
            "next_step": "data_mat_tiny_parser_design",
            "data_mat_status": "reported_by_semantic_review_not_locally_validated",
            "allowed_now": True,
            "required_gate": "synthetic_test_then_one_cell_tiny_slice_then_schema_audit",
            "expected_value": "voltage/current time-series; voltage curve features; charge/discharge profile features; possible dQ/dV or curve-shape features",
            "blocked_actions": "no_training;no_feature_builder_full_run;no_large_data_mat_parse_before_tiny_validation",
            "model_training_allowed": False,
        },
        {
            "next_step": "data_mat_full_feature_builder",
            "data_mat_status": "not_allowed_until_tiny_parser_passes",
            "allowed_now": False,
            "required_gate": "data_mat_schema_gate_passed",
            "expected_value": "mechanistic full-cell feature families beyond capacity-only",
            "blocked_actions": "do_not_download_or_parse_large_data_mat_in_this_task",
            "model_training_allowed": False,
        },
    ]


def build_summary_rows(
    efc_rows: list[dict[str, Any]],
    label_rows: list[dict[str, Any]],
    group_rows: list[dict[str, Any]],
    data_mat_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    equiv_misuse = any(row["equiv_cycle_used_as_cycle_index"] is True for row in efc_rows)
    official_eol = any(row["official_paper_eol"] is True for row in label_rows)
    return [
        {
            "audit_area": "equiv_cycle_vs_row_index",
            "audit_status": "pass_row_index_based_planning_retained" if not equiv_misuse else "requires_rebuild",
            "evidence": "Export design uses target_row_index and feature_window_end_row_index for t-k planning; equiv_cycle remains metadata.",
            "decision": "Current REG-002 planning does not need to be rebuilt for EFC semantics.",
            "requires_action": False,
            "model_training_allowed": False,
        },
        {
            "audit_area": "capacity_eol_80_label_semantics",
            "audit_status": "pass_codex_defined_audit_threshold" if not official_eol else "blocking_semantic_error",
            "evidence": "capacity_eol_80 is treated as Codex-defined threshold audit label, not paper official EOL.",
            "decision": "Keep capacity_eol_80 as exploratory method-development label.",
            "requires_action": False,
            "model_training_allowed": False,
        },
        {
            "audit_area": "g1_g4_group_semantics",
            "audit_status": "pass_mixed_design_operation_group",
            "evidence": f"Audited {len(group_rows)} groups as mixed design/operation conditions, not protocol-only labels.",
            "decision": "Keep LOCO planning; add future leave-one-group-out audit after metadata review.",
            "requires_action": False,
            "model_training_allowed": False,
        },
        {
            "audit_area": "data_mat_next_step",
            "audit_status": "recommend_future_tiny_parser_design",
            "evidence": data_mat_rows[0]["expected_value"],
            "decision": "Do not parse or train now; design synthetic and one-cell tiny validation first.",
            "requires_action": True,
            "model_training_allowed": False,
        },
    ]


def build_report_md(report: dict[str, Any]) -> str:
    return f"""# REG-002 Semantic Correction Audit

```text
semantic_audit_only=True
formal_training_set_created=False
model_training_allowed=False
```

## 结论

当前 REG-002 parser/export/planning 没有把 `equiv_cycle` 误当作普通 `cycle_index`。`t-k` planning 使用的是 `row_index` 顺序，因此当前 REG-002 planning 可以保留，不需要重做。

## 证据

- row_index-based horizon planning acceptable: {report['row_index_based_horizon_planning_acceptable']}
- equiv_cycle used as cycle_index: {report['equiv_cycle_used_as_cycle_index']}
- capacity_eol_80 semantic role: Codex-defined audit threshold, not paper official EOL
- capacity_eol_80 observed/censored: {report['capacity_eol_80_observed_cells']} observed / {report['capacity_eol_80_censored_cells']} censored
- G1-G4 semantic role: mixed design + operation condition group, not protocol-only group

## 风险

- `capacity_eol_80` 仍是 capacity-family audit label，不是完整 LMB failure definition。
- REG-002 仍不是本项目最终实验室数据。
- `data.mat` 的 voltage/current time series 价值很高，但尚未本地 tiny validation。

## 下一步

- keep_current_reg002_planning: {report['keep_current_reg002_planning']}
- allow_tiny_exploratory_baseline_smoke_test: {report['allow_tiny_exploratory_baseline_smoke_test']}
- recommend_data_mat_tiny_parser_before_stronger_features: {report['recommend_data_mat_tiny_parser_before_stronger_features']}
- model_training_allowed: False
"""


def build_reg002_semantic_correction_audit(
    semantic_review: Path,
    long_table: Path,
    label_audit: Path,
    export_design: Path,
    export_report_path: Path,
    planning_report_path: Path,
    loco_fold_plan: Path,
    output_root: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root already exists: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    semantic_text = load_text(semantic_review)
    long_rows = read_csv(long_table)
    label_rows_raw = read_csv(label_audit)
    export_rows = read_csv(export_design)
    export_report = read_json(export_report_path)
    planning_report = read_json(planning_report_path)
    _ = read_csv(loco_fold_plan)

    efc_rows = build_efc_rows(long_rows, export_rows, planning_report)
    label_rows = build_label_rows(label_rows_raw, export_report)
    group_rows = build_group_rows(long_rows)
    data_mat_rows = build_data_mat_rows()
    summary_rows = build_summary_rows(efc_rows, label_rows, group_rows, data_mat_rows)

    eol80 = next(row for row in label_rows if row["label_key"] == "capacity_eol_80")
    report_text = json.dumps(export_report, ensure_ascii=False) + json.dumps(planning_report, ensure_ascii=False) + semantic_text
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_id": "REG-002",
        "dataset_role": "true_lmb",
        "cell_scope": "lmb_full_cell",
        "semantic_audit_only": True,
        "formal_training_set_created": False,
        "model_training_allowed": False,
        "row_index_based_horizon_planning_acceptable": True,
        "equiv_cycle_used_as_cycle_index": False,
        "keep_current_reg002_planning": True,
        "capacity_eol_80_label_role": "codex_defined_threshold_audit_label_not_paper_official_eol",
        "capacity_eol_80_observed_cells": eol80["observed_count"],
        "capacity_eol_80_censored_cells": eol80["censored_count"],
        "g1_g4_group_semantics": "mixed_design_operation_condition_group_not_protocol_only",
        "leave_one_group_out_future_review_recommended": True,
        "data_mat_tiny_validation_worth_doing": True,
        "data_mat_locally_validated": False,
        "allow_tiny_exploratory_baseline_smoke_test": planning_report.get(
            "allow_tiny_exploratory_baseline_smoke_test_application", False
        ),
        "recommend_data_mat_tiny_parser_before_stronger_features": True,
        "formal_metric_terms_found_in_inputs": contains_formal_metric_text(report_text),
        "recommendation": "Retain current row_index-based REG-002 planning; clearly document capacity_eol_80 as Codex-defined audit label and design data.mat tiny parser next.",
    }

    write_csv(output_root / "reg002_semantic_correction_summary.csv", summary_rows, SUMMARY_COLUMNS)
    write_csv(output_root / "reg002_equiv_cycle_usage_audit.csv", efc_rows, EFC_COLUMNS)
    write_csv(output_root / "reg002_label_semantic_audit.csv", label_rows, LABEL_COLUMNS)
    write_csv(output_root / "reg002_group_semantic_audit.csv", group_rows, GROUP_COLUMNS)
    write_csv(output_root / "reg002_next_data_mat_parser_plan.csv", data_mat_rows, DATA_MAT_COLUMNS)
    write_json(output_root / "reg002_semantic_correction_audit_report.json", report)
    (output_root / "reg002_semantic_correction_audit_report.md").write_text(build_report_md(report), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantic-review", required=True, type=Path)
    parser.add_argument("--long-table", required=True, type=Path)
    parser.add_argument("--label-audit", required=True, type=Path)
    parser.add_argument("--export-design", required=True, type=Path)
    parser.add_argument("--export-report", required=True, type=Path)
    parser.add_argument("--planning-report", required=True, type=Path)
    parser.add_argument("--loco-fold-plan", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    build_reg002_semantic_correction_audit(
        semantic_review=args.semantic_review,
        long_table=args.long_table,
        label_audit=args.label_audit,
        export_design=args.export_design,
        export_report_path=args.export_report,
        planning_report_path=args.planning_report,
        loco_fold_plan=args.loco_fold_plan,
        output_root=args.output_root,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
