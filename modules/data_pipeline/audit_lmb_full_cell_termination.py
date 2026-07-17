"""Audit termination semantics for active LMB full-cell feature-audit exports.

The tool reads only the active-cell manifest and small paired-cycle summary
tables. It never reads raw BTSDA data, creates labels, or enables model
training. Unknown termination reasons remain unresolved by design.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


TERMINATION_COLUMNS = [
    "cell_id", "source_folder_name", "export_suffix", "dataset_role", "cell_scope", "electrolyte_code",
    "protocol_id", "termination_reason", "planned_long_cycle_count", "termination_metadata_status", "termination_interpretation",
    "paired_cycle_count", "long_cycle_pair_count", "unpaired_step_count", "terminal_pairing_status",
    "censoring_semantics_confirmed", "censored_at_long_cycle_index", "observed_failure_semantics_confirmed",
    "failure_event_long_cycle_index", "failure_mode", "failure_evidence_location", "observed_failure_label_created",
    "protocol_censored_label_created", "label_trainability_allowed",
    "model_training_allowed", "required_partner_confirmation",
]

GATE_COLUMNS = ["gate_name", "status", "evidence", "consequence"]
PARTNER_TEMPLATE_COLUMNS = [
    "cell_id", "原始数据文件夹", "导出编号", "已配对长循环数", "计划长循环数", "实际终止原因",
    "末端未配对充电的原因", "终止时是否出现异常", "实验日志或工步文件位置", "补充说明", "填写状态",
]
OBSERVED_FAILURE_TEMPLATE_COLUMNS = [
    "cell_id", "source_folder_name", "export_suffix", "termination_reason", "failure_event_long_cycle_index",
    "failure_mode", "failure_evidence_location", "reviewer", "metadata_complete", "notes",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--cell-summary", type=Path, required=True)
    parser.add_argument("--unpaired-step-audit", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def to_int(value: Any) -> int:
    try:
        return int(float(str(value or "0")))
    except ValueError:
        return 0


def interpret_termination(reason: str) -> tuple[str, str, bool]:
    normalized = reason.strip().lower()
    if not normalized or normalized in {"unknown", "未知", "待确认", "n/a"}:
        return "unresolved_termination_reason", "请确认是否为达到计划循环、自然失效、安全停止、设备故障或人为停止。", False
    if normalized in {"natural_failure", "confirmed_failure", "safety_stop", "soft_short", "自然失效", "确认失效", "安全停止", "软短路"}:
        return "observed_failure_candidate_requires_failure_evidence", "请提供终止时的实验记录或失效说明；当前不自动生成 observed label。", False
    if normalized in {"planned_cycle_count_reached", "reached_set_cycle_count", "protocol_complete", "达到设定循环数", "达到计划循环数", "协议完成"}:
        return "protocol_censored_confirmed_planned_count_value_missing", "请补充计划循环数的具体数值；该值用于复核导出范围，不改变当前 protocol-censored 语义。", True
    if normalized in {"equipment_fault", "data_export_interrupted", "operator_stop", "设备故障", "数据导出中断", "人为停止"}:
        return "administrative_censored_needs_review", "该记录不能作为 observed failure；请补充中断时的电池状态。", False
    return "unrecognized_termination_reason_needs_review", "终止原因不是受控枚举值；请使用标准原因或补充说明。", False


def observed_failure_is_confirmed(cell: dict[str, Any], long_cycle_count: int, interpretation: str) -> bool:
    """Require an in-window event location, failure mode, and evidence location.

    These conditions confirm intake semantics only. They never create a
    trainable target by themselves.
    """
    if interpretation != "observed_failure_candidate_requires_failure_evidence":
        return False
    event_index = to_int(cell.get("failure_event_long_cycle_index"))
    failure_mode = str(cell.get("failure_mode", "")).strip()
    evidence = str(cell.get("failure_evidence_location", "")).strip()
    return bool(event_index and 1 <= event_index <= long_cycle_count and failure_mode and evidence)


def audit_termination(
    manifest_path: Path,
    cell_summary_path: Path,
    unpaired_step_audit_path: Path,
    output_root: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    summaries = {row["cell_id"]: row for row in read_csv(cell_summary_path)}
    unpaired_by_cell = Counter(row["cell_id"] for row in read_csv(unpaired_step_audit_path))
    active_cells = [
        cell for cell in manifest.get("cells", [])
        if cell.get("dataset_role") == "true_lmb" and cell.get("use_status") == "active_feature_audit"
    ]
    rows: list[dict[str, Any]] = []
    partner_template_rows: list[dict[str, Any]] = []
    observed_failure_template_rows: list[dict[str, Any]] = []
    for cell in active_cells:
        cell_id = cell["cell_id"]
        summary = summaries.get(cell_id, {})
        reason = str(cell.get("termination_reason", "unknown"))
        interpretation, request, censoring_confirmed = interpret_termination(reason)
        long_cycle_count = to_int(summary.get("long_cycle_pair_count"))
        observed_confirmed = observed_failure_is_confirmed(cell, long_cycle_count, interpretation)
        unpaired_count = unpaired_by_cell[cell_id]
        pairing = "terminal_unpaired_charge_needs_review" if unpaired_count else "all_steps_paired_in_export"
        rows.append({
            "cell_id": cell_id,
            "source_folder_name": cell.get("source_folder_name", ""),
            "export_suffix": cell.get("export_suffix", ""),
            "dataset_role": cell.get("dataset_role", ""),
            "cell_scope": cell.get("cell_scope", ""),
            "electrolyte_code": cell.get("electrolyte_code", ""),
            "protocol_id": cell.get("protocol_id", ""),
            "termination_reason": reason,
            "planned_long_cycle_count": cell.get("planned_long_cycle_count") if cell.get("planned_long_cycle_count") is not None else "",
            "termination_metadata_status": "missing" if interpretation == "unresolved_termination_reason" else "present_needs_review",
            "termination_interpretation": interpretation,
            "paired_cycle_count": to_int(summary.get("paired_cycle_count")),
            "long_cycle_pair_count": long_cycle_count,
            "unpaired_step_count": unpaired_count,
            "terminal_pairing_status": pairing,
            "censoring_semantics_confirmed": censoring_confirmed,
            "censored_at_long_cycle_index": long_cycle_count if censoring_confirmed else "",
            "observed_failure_semantics_confirmed": observed_confirmed,
            "failure_event_long_cycle_index": cell.get("failure_event_long_cycle_index", ""),
            "failure_mode": cell.get("failure_mode", ""),
            "failure_evidence_location": cell.get("failure_evidence_location", ""),
            "observed_failure_label_created": False,
            "protocol_censored_label_created": False,
            "label_trainability_allowed": False,
            "model_training_allowed": False,
            "required_partner_confirmation": request,
        })
        if interpretation == "observed_failure_candidate_requires_failure_evidence" and not observed_confirmed:
            observed_failure_template_rows.append({
                "cell_id": cell_id,
                "source_folder_name": cell.get("source_folder_name", ""),
                "export_suffix": cell.get("export_suffix", ""),
                "termination_reason": reason,
                "failure_event_long_cycle_index": "required: last complete long-cycle index at or immediately before confirmed failure",
                "failure_mode": "required: capacity failure / voltage instability / soft-short / safety stop / other",
                "failure_evidence_location": "required: lab log, BTSDA screenshot, or reviewed note path",
                "reviewer": "required",
                "metadata_complete": "pending",
                "notes": "",
            })
        partner_template_rows.append({
            "cell_id": cell_id,
            "原始数据文件夹": cell.get("source_folder_name", ""),
            "导出编号": cell.get("export_suffix", ""),
            "已配对长循环数": to_int(summary.get("long_cycle_pair_count")),
            "计划长循环数": "待填写",
            "实际终止原因": "待填写：达到计划循环数 / 自然失效 / 安全停止 / 设备故障 / 人为停止 / 导出中断 / 其他",
            "末端未配对充电的原因": "待填写：导出边界 / 实验中断 / 设备中断 / 异常停止 / 其他",
            "终止时是否出现异常": "待填写：无 / 有（请说明） / 不清楚",
            "实验日志或工步文件位置": "待填写",
            "补充说明": "",
            "填写状态": "待 partner 确认",
        })
    interpretation_counts = Counter(row["termination_interpretation"] for row in rows)
    missing_count = sum(row["termination_metadata_status"] == "missing" for row in rows)
    confirmed_censor_count = sum(bool(row["censoring_semantics_confirmed"]) for row in rows)
    confirmed_observed_failure_count = sum(bool(row["observed_failure_semantics_confirmed"]) for row in rows)
    gates = [
        {
            "gate_name": "active_true_lmb_full_cell_manifest", "status": "pass",
            "evidence": f"{len(rows)} active true_lmb/lmb_full_cell exports; LHCE diagnostic-only export is absent.",
            "consequence": "Feature audit scope is correctly limited to the active full-cell mainline.",
        },
        {
            "gate_name": "termination_reason_confirmed", "status": "fail" if missing_count else "pass",
            "evidence": f"missing_or_unknown_termination_reason_count={missing_count}",
            "consequence": "Confirmed planned-cycle endpoints are kept as protocol-censored semantics, never as observed failure.",
        },
        {
            "gate_name": "terminal_step_pairing_review", "status": "review_required" if sum(unpaired_by_cell.values()) else "pass",
            "evidence": f"terminal_unpaired_step_count={sum(unpaired_by_cell.values())}",
            "consequence": "Do not infer failure or censoring from an export ending with an unmatched charge step.",
        },
        {
            "gate_name": "observed_failure_intake", "status": "ready_for_future_data" if not confirmed_observed_failure_count else "review_required",
            "evidence": f"observed_failure_semantics_confirmed_count={confirmed_observed_failure_count}",
            "consequence": "Future natural-failure exports require event cycle, failure mode, and evidence location before any label audit.",
        },
        {
            "gate_name": "label_trainability", "status": "blocked",
            "evidence": f"protocol_censored_confirmed_count={confirmed_censor_count}; observed_failure_confirmed_count={confirmed_observed_failure_count}; no labels are generated by this audit.",
            "consequence": "label_trainability_allowed=False",
        },
        {
            "gate_name": "model_training", "status": "blocked",
            "evidence": "This is metadata and termination audit only.",
            "consequence": "model_training_allowed=False",
        },
    ]
    write_csv(output_root / "lmb_full_cell_termination_audit.csv", rows, TERMINATION_COLUMNS)
    write_csv(output_root / "lmb_full_cell_trainability_gate.csv", gates, GATE_COLUMNS)
    write_csv(output_root / "partner_termination_confirmation_template.csv", partner_template_rows, PARTNER_TEMPLATE_COLUMNS)
    write_csv(output_root / "partner_observed_failure_intake_template.csv", observed_failure_template_rows, OBSERVED_FAILURE_TEMPLATE_COLUMNS)
    report = {
        "active_true_lmb_full_cell_export_count": len(rows),
        "termination_interpretation_counts": dict(interpretation_counts),
        "missing_or_unknown_termination_reason_count": missing_count,
        "protocol_censored_semantics_confirmed_count": confirmed_censor_count,
        "observed_failure_semantics_confirmed_count": confirmed_observed_failure_count,
        "terminal_unpaired_step_count": sum(unpaired_by_cell.values()),
        "observed_failure_label_created": False,
        "protocol_censored_label_created": False,
        "label_trainability_allowed": False,
        "model_training_allowed": False,
        "model_performance_claimed": False,
        "next_gate": "For each future observed full-cell failure, provide an in-window failure event cycle, failure mode, and evidence location; then rerun this audit before feature/label work. Model training remains blocked until observed-event and censoring data jointly pass trainability review.",
    }
    (output_root / "lmb_full_cell_termination_audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = [
        "# LMB Full-Cell Termination Semantics Audit", "",
        "This is a metadata audit. It creates no labels and reports no model performance.", "",
        f"- Active true-LMB full-cell exports: `{len(rows)}`",
        f"- Missing or unknown termination reasons: `{missing_count}`",
        f"- Terminal unmatched steps: `{sum(unpaired_by_cell.values())}`",
        f"- Confirmed protocol-censored semantics: `{confirmed_censor_count}`",
        f"- Confirmed observed-failure semantics: `{confirmed_observed_failure_count}`",
        "- Observed failure labels created: `False`",
        "- Protocol-censored labels created: `False`",
        "", "## Required Confirmation", "",
        "Partner has confirmed that all active exports reached their planned cycle count. They are therefore protocol-censored at the last complete long-cycle pair, not observed failures. The remaining P1 review is the numeric planned cycle count and the reason the final charge is unpaired.",
        "",
        "For future natural-failure data, the same audit requires an in-window event cycle, a reviewed failure mode, and a reproducible evidence location before it can be called an observed-failure candidate.",
        "", "```text", "label_trainability_allowed=False", "model_training_allowed=False", "model_performance_claimed=False", "```",
    ]
    (output_root / "lmb_full_cell_termination_audit_report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return report


def main() -> None:
    args = parse_args()
    audit_termination(
        manifest_path=args.manifest,
        cell_summary_path=args.cell_summary,
        unpaired_step_audit_path=args.unpaired_step_audit,
        output_root=args.output_root,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
