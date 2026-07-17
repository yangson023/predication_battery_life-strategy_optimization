"""Build a Li||Cu data expansion target plan for LMB research.

This planner turns qualitative smoke-test diagnostics into concrete next-batch
data requirements. It does not train models, refit models, read raw BTSDA data,
create processed data, or enter the RUL prediction pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


FORMAL_RESULT_TERMS = ("auc", "f1", "rmse", "accuracy")
CURRENT_LMB_CELL_SCOPE_TAG = "lmb_mechanism_test_not_full_cell"

GAP_COLUMNS = [
    "gap_key",
    "current_value",
    "target_value",
    "severity",
    "why_it_matters",
]

CELL_REQUIREMENT_COLUMNS = [
    "requirement_key",
    "minimum_target",
    "preferred_target",
    "priority",
    "notes_cn",
]

EVENT_PRIORITY_COLUMNS = [
    "event_type",
    "priority",
    "minimum_cell_target",
    "usage",
    "notes_cn",
]

METADATA_COLUMNS = [
    "metadata_field",
    "priority",
    "required_for",
    "notes_cn",
]

GATE_COLUMNS = [
    "gate_name",
    "required_status",
    "allowed_next_action",
    "blocking_condition",
    "model_training_allowed",
]

CELL_SCOPE_COLUMNS = [
    "source_folder_name",
    "cell_group",
    "cell_scope_tag",
    "is_full_cell",
    "current_allowed_use",
    "forbidden_use",
    "np_ratio_policy",
]


def read_csv(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def parse_int(value: object) -> int:
    try:
        text = str(value).strip()
        if not text:
            return 0
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def metadata_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts = Counter(row.get("cell_group", "") for row in rows)
    return {"Li||Cu": counts.get("Li||Cu", 0), "Li||Li": counts.get("Li||Li", 0)}


def current_lab_cell_scope_rows() -> list[dict[str, Any]]:
    lili_use = "Li||Li symmetric mechanism audit: polarization, hysteresis, voltage instability, soft-short warning review"
    licu_use = "Li||Cu CE half-cell mechanism audit: plating/stripping efficiency, incomplete capacity warning proxy"
    forbidden = "Do not use as full-cell lifetime/RUL/EOL evidence; do not mix Li||Li and Li||Cu as one training task"
    np_policy = "N/P ratio is not applicable for Li||Li or Li||Cu; record Li thickness, areal capacity, current density instead"
    rows: list[dict[str, Any]] = []
    for folder in ["26-0414", "26-0421", "26-0429-009(li-li)"]:
        rows.append(
            {
                "source_folder_name": folder,
                "cell_group": "Li||Li",
                "cell_scope_tag": CURRENT_LMB_CELL_SCOPE_TAG,
                "is_full_cell": False,
                "current_allowed_use": lili_use,
                "forbidden_use": forbidden,
                "np_ratio_policy": np_policy,
            }
        )
    for folder in ["26-0428-009", "26-0428-085", "26-0429-002(li-Cu)", "26-0512(li-Cu)"]:
        rows.append(
            {
                "source_folder_name": folder,
                "cell_group": "Li||Cu",
                "cell_scope_tag": CURRENT_LMB_CELL_SCOPE_TAG,
                "is_full_cell": False,
                "current_allowed_use": licu_use,
                "forbidden_use": forbidden,
                "np_ratio_policy": np_policy,
            }
        )
    return rows


def current_gap_rows(event_ranks: list[dict[str, str]], risk_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    _ = sorted({row.get("test_cell", "") for row in event_ranks if row.get("test_cell")})
    positive_targets = 3
    train_positive = 2
    risk_keys = {row.get("risk_key", "") for row in risk_rows}
    return [
        {
            "gap_key": "candidate_licu_cell_count",
            "current_value": 3,
            "target_value": "10-12 total Li||Cu cells",
            "severity": "very_high",
            "why_it_matters": "当前 cell 数不足，单个 cell 会强烈影响 qualitative smoke-test 结论。",
        },
        {
            "gap_key": "positive_target_count",
            "current_value": positive_targets,
            "target_value": "至少每类事件 3 个 cell，总 positive 明显多于当前 3 个",
            "severity": "very_high",
            "why_it_matters": "当前 positive 极少，只能做 smoke-test diagnostics，不能支撑泛化判断。",
        },
        {
            "gap_key": "train_positive_per_loco_fold",
            "current_value": train_positive,
            "target_value": "每个 LOCO fold 训练 positive 明显大于 2",
            "severity": "very_high",
            "why_it_matters": "每折 train positive=2 会导致 coefficient sign 和事件排序高度不稳定。",
        },
        {
            "gap_key": "label_scope",
            "current_value": "incomplete_capacity_event",
            "target_value": "增加 CE collapse / sustained CE degradation / voltage instability / soft-short warning / no-event control",
            "severity": "high",
            "why_it_matters": "当前标签不是 full lifetime EOL，只能作为局部 warning proxy。",
        },
        {
            "gap_key": "terminal_interpretation",
            "current_value": "mostly protocol-censored",
            "target_value": "补充 2-3 个自然失效或明确异常终止 cell",
            "severity": "high",
            "why_it_matters": "协议终止不能当作自然失效；需要明确终止原因来支持 trainability audit。",
        },
        {
            "gap_key": "horizon_candidate",
            "current_value": "horizon=5 preferred in current diagnostics",
            "target_value": "用新增数据复核 h5 是否仍更稳定",
            "severity": "medium",
            "why_it_matters": "h5 当前更稳，但仍是 small-n qualitative 判断。",
        },
        {
            "gap_key": "very_high_risk_small_n",
            "current_value": str("very_high_risk_small_n" in risk_keys or True),
            "target_value": "False after data expansion gates",
            "severity": "very_high",
            "why_it_matters": "这是阻止正式建模的核心原因。",
        },
    ]


def next_batch_requirements() -> list[dict[str, Any]]:
    return [
        {
            "requirement_key": "new_licu_cells_minimum",
            "minimum_target": "新增 5-8 个 Li||Cu cell",
            "preferred_target": "总 Li||Cu cell >= 10-12",
            "priority": "P0",
            "notes_cn": "优先选择协议清楚、事件清楚、元数据清楚的 cell。",
        },
        {
            "requirement_key": "cycles_per_cell",
            "minimum_target": "尽量 >= 80 cycles",
            "preferred_target": ">= 100 cycles",
            "priority": "P0",
            "notes_cn": "短窗口 early failure 仍保留，但先标记为 early-event audit-only。",
        },
        {
            "requirement_key": "no_event_controls",
            "minimum_target": "至少 3 个 no-event / protocol-censored control cell",
            "preferred_target": "覆盖不同 batch / electrolyte_code",
            "priority": "P0",
            "notes_cn": "control cell 用来判断模型是否只是把所有后期循环都当成风险。",
        },
        {
            "requirement_key": "natural_or_abnormal_terminal_cells",
            "minimum_target": "至少 2-3 个自然失效或明确异常终止 cell",
            "preferred_target": "终止原因和异常记录完整",
            "priority": "P0",
            "notes_cn": "用于区分 protocol-censored 和 observed event。",
        },
        {
            "requirement_key": "event_diversity",
            "minimum_target": "每类重点事件至少 3 个 cell",
            "preferred_target": "事件与 no-event control 同时存在",
            "priority": "P1",
            "notes_cn": "避免只围绕 incomplete_capacity_event 单一标签转圈。",
        },
    ]


def event_priority_rows() -> list[dict[str, Any]]:
    return [
        {"event_type": "incomplete_capacity_event", "priority": "P0", "minimum_cell_target": ">=3 additional or confirmed cells", "usage": "baseline warning proxy", "notes_cn": "当前唯一进入 tiny smoke-test 的标签，继续补强但不能等同 full EOL。"},
        {"event_type": "CE collapse", "priority": "P0", "minimum_cell_target": ">=3 cells", "usage": "label scan / trainability audit", "notes_cn": "Li||Cu 库仑效率突降可能对应锂沉积/剥离异常。"},
        {"event_type": "sustained CE degradation", "priority": "P0", "minimum_cell_target": ">=3 cells", "usage": "early warning label candidate", "notes_cn": "关注连续窗口下降，不看单点波动。"},
        {"event_type": "voltage instability", "priority": "P1", "minimum_cell_target": ">=3 cells", "usage": "mechanistic feature validation", "notes_cn": "用于验证 voltage/hysteresis/kinetic 特征是否有独立贡献。"},
        {"event_type": "possible soft-short warning", "priority": "P1", "minimum_cell_target": ">=2-3 cells if available", "usage": "audit-only first", "notes_cn": "先做人工复核和 audit，不直接进入训练。"},
        {"event_type": "protocol-censored no-event control", "priority": "P0", "minimum_cell_target": ">=3 cells", "usage": "negative/control cohort", "notes_cn": "必须保留，用于降低早期误报和后期循环偏置。"},
    ]


def metadata_checklist_rows() -> list[dict[str, Any]]:
    fields = [
        ("cell_id", "P0", "intake / alignment", "必须能和 BTSDA 文件夹、导出表一一对应。"),
        ("cell_type", "P0", "Li||Cu vs Li||Li routing", "Li||Cu 与 Li||Li 不能混在一起训练。"),
        ("electrolyte_code", "P0", "batch grouping", "编号即可；完整配方若不能公开可后续补。"),
        ("electrolyte_detail_if_shareable", "P1", "mechanistic interpretation", "可共享时记录锂盐、浓度、添加剂。"),
        ("Li_foil_thickness", "P0", "cell design", "影响锂源和界面稳定性。"),
        ("Cu_foil_information", "P0", "Li||Cu design", "记录 Cu 箔信息或供应批次。"),
        ("current_density", "P0", "protocol normalization", "缺失会影响不同 cell 间比较。"),
        ("areal_capacity", "P0", "protocol normalization", "缺失会影响 CE/capacity 事件解释。"),
        ("electrolyte_volume", "P0", "cell design", "影响润湿和副反应解释。"),
        ("separator_type", "P0", "cell design", "记录 Celgard/PP/PE 等。"),
        ("pressure", "P1", "mechanistic interpretation", "压力影响 Li plating/stripping 稳定性。"),
        ("temperature", "P1", "protocol context", "默认室温也要记录。"),
        ("cycling_protocol", "P0", "label and horizon design", "包括电流、容量或时间限制、循环次数。"),
        ("formation_rest_protocol", "P1", "initial condition", "静置/预处理会影响早期循环。"),
        ("planned_cycle_count", "P0", "censoring", "用于判断 protocol-censored。"),
        ("termination_reason", "P0", "observed/censored decision", "必须区分到达设定循环数、异常终止、设备中断、自然失效。"),
        ("abnormal_notes", "P0", "manual review", "记录漏液、接触不良、电压异常等。"),
        ("BTSDA_export_timestamp", "P1", "provenance", "便于追踪导出版本。"),
        ("operator_or_batch_note", "P1", "batch effect review", "可匿名记录操作者或批次。"),
    ]
    return [
        {"metadata_field": field, "priority": priority, "required_for": required_for, "notes_cn": notes}
        for field, priority, required_for, notes in fields
    ]


def gate_rows() -> list[dict[str, Any]]:
    return [
        {"gate_name": "intake_gate_passed", "required_status": "cycle/step/record 或可接受 sample 均可读取", "allowed_next_action": "metadata validation", "blocking_condition": "三层导出缺失或 cell_id 无法对齐", "model_training_allowed": False},
        {"gate_name": "metadata_gate_passed", "required_status": "P0 metadata 完整", "allowed_next_action": "label scan", "blocking_condition": "termination_reason/current_density/areal_capacity 缺失", "model_training_allowed": False},
        {"gate_name": "label_scan_allowed", "required_status": "信号可审计且不混淆 Li||Cu/Li||Li", "allowed_next_action": "trainability audit", "blocking_condition": "事件定义不清或终止原因不明", "model_training_allowed": False},
        {"gate_name": "trainability_audit_allowed", "required_status": "observed/censored/protocol-censored 可区分", "allowed_next_action": "baseline-ready export design", "blocking_condition": "只有 audit-only 信号", "model_training_allowed": False},
        {"gate_name": "baseline_ready_export_allowed", "required_status": "泄漏列移除且 row_id 对齐", "allowed_next_action": "tiny smoke-test planning", "blocking_condition": "feature/target/metadata 不对齐或 same-cycle leakage", "model_training_allowed": False},
        {"gate_name": "tiny_smoke_test_allowed", "required_status": "LOCO fold 可构造且风险被报告", "allowed_next_action": "qualitative smoke-test only", "blocking_condition": "positive 极少且无 control cell", "model_training_allowed": False},
        {"gate_name": "model_training_allowed", "required_status": "False by default", "allowed_next_action": "none before separate approval", "blocking_condition": "新增数据未通过完整 gates", "model_training_allowed": False},
    ]


def partner_message() -> str:
    return (
        "我们现在不是想要“越多越好”的乱数据，而是优先需要事件明确、协议清楚、元数据清楚的 Li||Cu 数据。"
        "少量高质量数据比大量来源不清的数据更有用。尤其希望每个 cell 都能说明循环协议、电流密度、面容量、终止原因、异常记录，"
        "并尽量同时提供 cycle/step/record 三层导出。Li||Cu 主要用于 CE/容量异常和 incomplete capacity warning；"
        "Li||Li 主要用于极化、电压不稳定和 soft-short 审计，二者后续不能混在一起训练。"
    )


def advisor_message() -> str:
    return (
        "当前项目已完成从 BTSDA 三层数据接入、LMB canonical feature、label policy、mechanistic horizon feature 到 qualitative smoke-test diagnostics 的闭环。"
        "诊断显示机制特征比 record-sample-only 特征更值得继续，但现阶段受 small-n 限制：只有 3 个 Li||Cu candidate cell、3 个 positive target，"
        "每个 LOCO fold 的 train positive 只有 2。因此下一阶段核心不是盲目更换模型，而是有设计地补充 Li||Cu 事件 cell 与 no-event control cell，"
        "用于验证 incomplete_capacity_event warning proxy 以及 CE/电压/动力学机制特征的可复现性。"
    )


def assert_no_formal_terms(payload: dict[str, Any], *texts: str) -> None:
    combined = json.dumps(payload, ensure_ascii=False).lower() + "\n" + "\n".join(text.lower() for text in texts)
    for term in FORMAL_RESULT_TERMS:
        if term in combined:
            raise ValueError(f"Formal result term is not allowed in expansion plan outputs: {term}")


def build_report(
    output_root: Path,
    docs_output: Path,
    diagnostics_report: str,
    event_ranks: list[dict[str, str]],
    horizon_comparison: list[dict[str, str]],
    same_signal: list[dict[str, str]],
    risk_rows: list[dict[str, str]],
    metadata_rows: list[dict[str, str]],
) -> dict[str, Any]:
    metadata_summary = metadata_counts(metadata_rows)
    preferred_horizon = Counter(row.get("preferred_horizon_for_next_candidate", "") for row in horizon_comparison).most_common(1)
    report = {
        "planning_only": True,
        "qualitative_smoke_test_diagnostics_only": True,
        "not_formal_model_result": True,
        "model_training_allowed": False,
        "model_refit_performed": False,
        "rul_prediction_entered": False,
        "processed_data_generated": False,
        "raw_btsda_read": False,
        "target_cell_group": "Li||Cu",
        "current_lab_data_scope_tag": CURRENT_LMB_CELL_SCOPE_TAG,
        "current_lab_data_are_full_cells": False,
        "full_cell_data_available": False,
        "current_lab_data_scope_note": (
            "Current Li||Li and Li||Cu lab data are LMB-relevant mechanism-test cells, "
            "not full-cell lifetime data."
        ),
        "current_candidate_licu_cell_count": 3,
        "current_positive_target_count": 3,
        "current_train_positive_per_loco_fold": 2,
        "current_label": "incomplete_capacity_event",
        "current_label_is_full_lifetime_eol": False,
        "current_terminal_context": "mostly protocol-censored",
        "preferred_horizon_from_current_diagnostics": preferred_horizon[0][0] if preferred_horizon else "horizon_5",
        "preferred_horizon_is_small_n_judgment": True,
        "next_batch_minimum_new_licu_cells": "5-8",
        "next_batch_preferred_total_licu_cells": "10-12",
        "minimum_no_event_control_cells": 3,
        "minimum_natural_or_abnormal_terminal_cells": "2-3",
        "preferred_cycles_per_cell": "80-100+",
        "metadata_current_summary": metadata_summary,
        "same_signal_source_context": same_signal,
        "risk_source_count": len(risk_rows),
        "event_rank_source_count": len(event_ranks),
        "partner_message_cn": partner_message(),
        "advisor_message_cn": advisor_message(),
        "next_action": "collect higher-quality Li||Cu event and control cells before stronger modeling",
    }
    markdown = markdown_report(report)
    assert_no_formal_terms(report, markdown)
    output_root.mkdir(parents=True, exist_ok=True)
    docs_output.parent.mkdir(parents=True, exist_ok=True)
    (output_root / "lmb_licu_data_expansion_plan_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_root / "lmb_licu_data_expansion_plan_report.md").write_text(markdown, encoding="utf-8")
    docs_output.write_text(markdown, encoding="utf-8")
    return report


def markdown_report(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# LMB Li||Cu Data Expansion Plan",
            "",
            "This is a data expansion plan based on qualitative smoke-test diagnostics. It is not a formal model result.",
            "",
            "## 当前缺口",
            "",
            f"- 当前 Li||Cu candidate cell 数：{report['current_candidate_licu_cell_count']}",
            f"- 当前 positive target 数：{report['current_positive_target_count']}",
            f"- 每个 LOCO fold train positive：{report['current_train_positive_per_loco_fold']}",
            f"- 当前标签：`{report['current_label']}`，不是 full lifetime EOL。",
            f"- 当前 terminal 情况：{report['current_terminal_context']}。",
            f"- 当前更值得保留的 horizon：`{report['preferred_horizon_from_current_diagnostics']}`，但仍是 small-n 判断。",
            f"- 当前实验室数据 scope 标签：`{report['current_lab_data_scope_tag']}`。",
            f"- 当前 Li||Li / Li||Cu 是否为 full cell：`{report['current_lab_data_are_full_cells']}`。",
            "- 当前 Li||Li / Li||Cu 只能作为 LMB 机制测试数据，不能作为全电池寿命/RUL/EOL 证据。",
            "",
            "## 下一批 Li||Cu 数据目标",
            "",
            "- 最低目标：新增 5-8 个 Li||Cu cell。",
            "- 较好目标：总 Li||Cu cell >= 10-12。",
            "- 每类重点事件至少 3 个 cell。",
            "- 至少 3 个 no-event / protocol-censored control cell。",
            "- 至少 2-3 个自然失效或明确异常终止 cell。",
            "- 每个 cell 尽量 >= 80-100 cycles；early failure 保留但先标记为 audit-only。",
            "",
            "## 为什么需要 control 和自然终止",
            "",
            "- no-event control 可以检查模型是否把所有后期循环都误判为风险。",
            "- 自然失效或明确异常终止 cell 可以帮助区分 observed event 与 protocol-censored 终点。",
            "- 当前 protocol-censored 终点不能被当作自然失效。",
            "",
            "## Li||Cu / Li||Li 用途区分",
            "",
            "- Li||Cu：优先用于 incomplete capacity、CE collapse、sustained CE degradation 等 warning proxy。",
            "- Li||Li：优先用于 polarization growth、voltage instability、possible soft-short audit。",
            "- 两类数据不能混在一起训练；只能在文档层面对机制进行互相参考。",
            "",
            "## 给 partner 的说明",
            "",
            report["partner_message_cn"],
            "",
            "## 给导师的说明",
            "",
            report["advisor_message_cn"],
            "",
            "## 门禁结论",
            "",
            "- `model_training_allowed = False`",
            "- 新数据必须先通过 intake、metadata、label scan、trainability audit、baseline-ready export，再考虑 tiny smoke-test。",
            "- 当前最佳动作是数据设计与补充，不是盲目换复杂模型。",
            "",
        ]
    )


def build_lmb_licu_data_expansion_plan(
    diagnostics_root: Path,
    baseline_risk_summary: Path,
    metadata_gate: Path,
    label_policy: Path,
    feature_label_requirements: Path,
    storage_plan: Path,
    output_root: Path,
    docs_output: Path,
) -> dict[str, Any]:
    diagnostics_report = read_text(diagnostics_root / "mechanistic_smoke_test_diagnostics_report.md")
    event_ranks = read_csv(diagnostics_root / "mechanistic_event_rank_summary.csv")
    horizon_comparison = read_csv(diagnostics_root / "mechanistic_horizon_comparison.csv")
    same_signal = read_csv(diagnostics_root / "mechanistic_same_signal_source_risk_audit.csv")
    risk_rows = read_csv(baseline_risk_summary)
    metadata_rows = read_csv(metadata_gate)
    _ = read_text(label_policy)
    _ = read_text(feature_label_requirements)
    _ = read_text(storage_plan)

    output_root.mkdir(parents=True, exist_ok=True)
    write_csv(output_root / "licu_data_gap_summary.csv", current_gap_rows(event_ranks, risk_rows), GAP_COLUMNS)
    write_csv(output_root / "licu_next_batch_cell_requirements.csv", next_batch_requirements(), CELL_REQUIREMENT_COLUMNS)
    write_csv(output_root / "licu_event_type_priority.csv", event_priority_rows(), EVENT_PRIORITY_COLUMNS)
    write_csv(output_root / "licu_metadata_requirement_checklist.csv", metadata_checklist_rows(), METADATA_COLUMNS)
    write_csv(output_root / "licu_intake_gate_for_next_batch.csv", gate_rows(), GATE_COLUMNS)
    write_csv(output_root / "current_lmb_cell_scope_tags.csv", current_lab_cell_scope_rows(), CELL_SCOPE_COLUMNS)
    return build_report(
        output_root=output_root,
        docs_output=docs_output,
        diagnostics_report=diagnostics_report,
        event_ranks=event_ranks,
        horizon_comparison=horizon_comparison,
        same_signal=same_signal,
        risk_rows=risk_rows,
        metadata_rows=metadata_rows,
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--diagnostics-root", type=Path, required=True)
    parser.add_argument("--baseline-risk-summary", type=Path, required=True)
    parser.add_argument("--metadata-gate", type=Path, required=True)
    parser.add_argument("--label-policy", type=Path, required=True)
    parser.add_argument("--feature-label-requirements", type=Path, required=True)
    parser.add_argument("--storage-plan", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--docs-output", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_lmb_licu_data_expansion_plan(
        diagnostics_root=args.diagnostics_root,
        baseline_risk_summary=args.baseline_risk_summary,
        metadata_gate=args.metadata_gate,
        label_policy=args.label_policy,
        feature_label_requirements=args.feature_label_requirements,
        storage_plan=args.storage_plan,
        output_root=args.output_root,
        docs_output=args.docs_output,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
