"""Build metadata-aware LMB audit summaries.

This module joins partner-provided structured metadata with existing
audit-only LMB label scans. It never reads raw BTSDA data, creates trainable
labels, trains models, or enters the RUL prediction pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from openpyxl import load_workbook


SHEET_NAME = "填写模板"

CELL_SUMMARY_COLUMNS = [
    "cell_id",
    "cell_group",
    "cell_type",
    "source_folder_name",
    "electrolyte_code",
    "electrolyte_code_source",
    "electrolyte_detail_status",
    "separator",
    "pressure",
    "rest_time",
    "li_thickness_um",
    "cu_substrate_info",
    "metadata_gate_status",
    "termination_resolution_status",
    "protocol_readiness_status",
    "feature_rows",
    "observed_candidate_total",
    "labels_with_observed_candidates",
    "top_observed_label_keys",
    "trainability_audit_allowed",
    "training_allowed_now",
    "recommended_next_review",
]

ELECTROLYTE_COLUMNS = [
    "cell_group",
    "electrolyte_code",
    "electrolyte_detail_status",
    "cell_count",
    "cell_ids",
    "observed_candidate_total",
    "top_observed_label_keys",
    "trainability_audit_allowed",
]

LABEL_BY_METADATA_COLUMNS = [
    "cell_group",
    "electrolyte_code",
    "label_key",
    "cell_count",
    "observed_candidate_count",
    "limited_window_count",
    "protocol_censored_count",
    "first_observed_candidate_cycle_min",
    "last_cycle_index_max",
    "interpretation_limit",
]

RISK_COLUMNS = [
    "cell_id",
    "cell_group",
    "risk_key",
    "risk_level",
    "risk_detail",
    "blocks_trainability_audit",
]

REQUIRED_FOR_TRAINABILITY = [
    "终止原因",
    "循环协议",
    "电流密度(mA/cm²)",
    "面容量(mAh/cm²)",
]

ELECTROLYTE_DETAIL_FIELDS = ["锂盐", "锂盐浓度", "电解液添加剂"]


def normalize(value: Any) -> str:
    if value is None:
        return ""
    text = str(value).strip()
    return "" if text.lower() == "none" else text


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


def parse_int(value: Any) -> int | None:
    try:
        text = normalize(value)
        if text == "":
            return None
        return int(float(text))
    except (TypeError, ValueError):
        return None


def read_metadata_workbook(path: Path) -> dict[str, dict[str, str]]:
    workbook = load_workbook(path, data_only=True, read_only=True)
    try:
        if SHEET_NAME not in workbook.sheetnames:
            raise ValueError(f"Workbook must contain sheet: {SHEET_NAME}")
        sheet = workbook[SHEET_NAME]
        rows = list(sheet.iter_rows(values_only=True))
        if not rows:
            return {}
        headers = [normalize(value) for value in rows[0]]
        result: dict[str, dict[str, str]] = {}
        for row in rows[1:]:
            record = {headers[index]: normalize(value) for index, value in enumerate(row) if index < len(headers)}
            cell_id = record.get("电池编号", "")
            if cell_id:
                result[cell_id] = record
        return result
    finally:
        workbook.close()


def count_feature_rows(lili_features: Path, licu_features: Path) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for path in [lili_features, licu_features]:
        for row in read_csv(path):
            counts[row.get("source_folder_name", "")] += 1
    return dict(counts)


def observed_counts_by_cell(summary_rows: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    grouped: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in summary_rows:
        cell_id = row.get("source_folder_name", "")
        label_key = row.get("label_key", "")
        grouped[cell_id][label_key] += parse_int(row.get("observed_candidate_count")) or 0
    return grouped


def summary_rows_by_cell(summary_rows: list[dict[str, str]]) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in summary_rows:
        grouped[row.get("source_folder_name", "")].append(row)
    return grouped


def gate_by_cell(gate_rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("电池编号", ""): row for row in gate_rows if row.get("电池编号")}


def electrolyte_detail_status(metadata: dict[str, str]) -> str:
    missing = [field for field in ELECTROLYTE_DETAIL_FIELDS if not metadata.get(field)]
    return "electrolyte_detail_available" if not missing else "electrolyte_detail_missing"


def termination_status(metadata: dict[str, str]) -> str:
    return "termination_reason_available" if metadata.get("终止原因") else "unresolved_termination_reason"


def protocol_status(metadata: dict[str, str]) -> str:
    missing = [field for field in REQUIRED_FOR_TRAINABILITY if not metadata.get(field)]
    return "protocol_ready_for_trainability_review" if not missing else "protocol_metadata_incomplete"


def trainability_allowed(metadata: dict[str, str]) -> bool:
    return (
        termination_status(metadata) == "termination_reason_available"
        and protocol_status(metadata) == "protocol_ready_for_trainability_review"
        and electrolyte_detail_status(metadata) == "electrolyte_detail_available"
    )


def top_labels(label_counts: dict[str, int], limit: int = 3) -> str:
    nonzero = [(label, count) for label, count in label_counts.items() if count > 0]
    nonzero.sort(key=lambda item: (-item[1], item[0]))
    return ";".join(f"{label}:{count}" for label, count in nonzero[:limit])


def recommendation(cell_group: str, label_counts: dict[str, int], metadata: dict[str, str]) -> str:
    if cell_group == "Li||Cu":
        if label_counts.get("incomplete_capacity_event", 0) > 0 or label_counts.get("ce_collapse", 0) > 0:
            return "review_licu_capacity_and_ce_terminal_signals"
        return "review_licu_ce_instability_thresholds"
    if cell_group == "Li||Li":
        if label_counts.get("polarization_growth", 0) > 0 or label_counts.get("voltage_hysteresis_failure", 0) > 0:
            return "review_lili_voltage_hysteresis_and_polarization"
        return "audit_only_low_voltage_event_density"
    return "metadata_review_first"


def risk_rows_for_cell(cell_id: str, cell_group: str, metadata: dict[str, str]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    missing_electrolyte = [field for field in ELECTROLYTE_DETAIL_FIELDS if not metadata.get(field)]
    if missing_electrolyte:
        risks.append(
            {
                "cell_id": cell_id,
                "cell_group": cell_group,
                "risk_key": "electrolyte_detail_missing",
                "risk_level": "high",
                "risk_detail": ";".join(missing_electrolyte),
                "blocks_trainability_audit": True,
            }
        )
    if not metadata.get("终止原因"):
        risks.append(
            {
                "cell_id": cell_id,
                "cell_group": cell_group,
                "risk_key": "unresolved_termination_reason",
                "risk_level": "high",
                "risk_detail": "终止原因缺失，observed/censored 不能正式解释。",
                "blocks_trainability_audit": True,
            }
        )
    missing_protocol = [field for field in REQUIRED_FOR_TRAINABILITY if not metadata.get(field)]
    if missing_protocol:
        risks.append(
            {
                "cell_id": cell_id,
                "cell_group": cell_group,
                "risk_key": "protocol_metadata_incomplete",
                "risk_level": "high",
                "risk_detail": ";".join(missing_protocol),
                "blocks_trainability_audit": True,
            }
        )
    if not metadata.get("是否协议变化"):
        risks.append(
            {
                "cell_id": cell_id,
                "cell_group": cell_group,
                "risk_key": "protocol_change_unknown",
                "risk_level": "medium",
                "risk_detail": "是否协议变化未填写。",
                "blocks_trainability_audit": True,
            }
        )
    if not metadata.get("是否异常实验"):
        risks.append(
            {
                "cell_id": cell_id,
                "cell_group": cell_group,
                "risk_key": "abnormal_run_unknown",
                "risk_level": "medium",
                "risk_detail": "是否异常实验未填写。",
                "blocks_trainability_audit": True,
            }
        )
    return risks


def build_cell_summary(
    metadata_by_cell: dict[str, dict[str, str]],
    gates: dict[str, dict[str, str]],
    label_counts: dict[str, dict[str, int]],
    feature_counts: dict[str, int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    cell_rows: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    for cell_id, metadata in sorted(metadata_by_cell.items()):
        gate = gates.get(cell_id, {})
        cell_group = gate.get("cell_group") or ("Li||Li" if "Li||Li" in metadata.get("电池类型", "") else "Li||Cu" if "Li||Cu" in metadata.get("电池类型", "") else "Unknown")
        counts = label_counts.get(cell_id, {})
        observed_total = sum(counts.values())
        labels_with_observed = sum(1 for count in counts.values() if count > 0)
        allowed = trainability_allowed(metadata)
        row = {
            "cell_id": cell_id,
            "cell_group": cell_group,
            "cell_type": metadata.get("电池类型", ""),
            "source_folder_name": cell_id,
            "electrolyte_code": metadata.get("电解液溶剂", "") or "unknown",
            "electrolyte_code_source": "partner_provided_electrolyte_code",
            "electrolyte_detail_status": electrolyte_detail_status(metadata),
            "separator": metadata.get("隔膜材料/型号", ""),
            "pressure": metadata.get("压力条件", ""),
            "rest_time": metadata.get("静置时间", ""),
            "li_thickness_um": metadata.get("锂片厚度(μm)", ""),
            "cu_substrate_info": metadata.get("铜箔/基底信息", ""),
            "metadata_gate_status": gate.get("metadata_gate_status", "metadata_gate_missing"),
            "termination_resolution_status": termination_status(metadata),
            "protocol_readiness_status": protocol_status(metadata),
            "feature_rows": feature_counts.get(cell_id, 0),
            "observed_candidate_total": observed_total,
            "labels_with_observed_candidates": labels_with_observed,
            "top_observed_label_keys": top_labels(counts),
            "trainability_audit_allowed": allowed,
            "training_allowed_now": False,
            "recommended_next_review": recommendation(cell_group, counts, metadata),
        }
        cell_rows.append(row)
        risk_rows.extend(risk_rows_for_cell(cell_id, cell_group, metadata))
    return cell_rows, risk_rows


def build_label_by_metadata(
    metadata_by_cell: dict[str, dict[str, str]],
    gates: dict[str, dict[str, str]],
    summary_by_cell_rows: dict[str, list[dict[str, str]]],
) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str, str], list[dict[str, str]]] = defaultdict(list)
    for cell_id, rows in summary_by_cell_rows.items():
        metadata = metadata_by_cell.get(cell_id, {})
        gate = gates.get(cell_id, {})
        cell_group = gate.get("cell_group", "")
        electrolyte_code = metadata.get("电解液溶剂", "") or "unknown"
        for row in rows:
            grouped[(cell_group, electrolyte_code, row.get("label_key", ""))].append(row)

    output: list[dict[str, Any]] = []
    for (cell_group, electrolyte_code, label_key), rows in sorted(grouped.items()):
        observed = sum(parse_int(row.get("observed_candidate_count")) or 0 for row in rows)
        limited = sum(parse_int(row.get("limited_window_count")) or 0 for row in rows)
        protocol = sum(parse_int(row.get("protocol_censored_count")) or 0 for row in rows)
        first_cycles = [
            parse_int(row.get("first_observed_candidate_cycle"))
            for row in rows
            if parse_int(row.get("first_observed_candidate_cycle")) is not None
        ]
        last_cycles = [parse_int(row.get("last_cycle_index")) for row in rows if parse_int(row.get("last_cycle_index")) is not None]
        output.append(
            {
                "cell_group": cell_group,
                "electrolyte_code": electrolyte_code,
                "label_key": label_key,
                "cell_count": len({row.get("source_folder_name") for row in rows}),
                "observed_candidate_count": observed,
                "limited_window_count": limited,
                "protocol_censored_count": protocol,
                "first_observed_candidate_cycle_min": min(first_cycles) if first_cycles else "",
                "last_cycle_index_max": max(last_cycles) if last_cycles else "",
                "interpretation_limit": "unresolved_termination_reason",
            }
        )
    return output


def build_electrolyte_summary(cell_rows: list[dict[str, Any]], label_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped_cells: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in cell_rows:
        grouped_cells[(row["cell_group"], row["electrolyte_code"])].append(row)

    labels_by_group: dict[tuple[str, str], Counter[str]] = defaultdict(Counter)
    for row in label_rows:
        labels_by_group[(row["cell_group"], row["electrolyte_code"])][row["label_key"]] += int(row["observed_candidate_count"] or 0)

    output: list[dict[str, Any]] = []
    for (cell_group, electrolyte_code), rows in sorted(grouped_cells.items()):
        label_counter = labels_by_group.get((cell_group, electrolyte_code), Counter())
        output.append(
            {
                "cell_group": cell_group,
                "electrolyte_code": electrolyte_code,
                "electrolyte_detail_status": "electrolyte_detail_available"
                if all(row["electrolyte_detail_status"] == "electrolyte_detail_available" for row in rows)
                else "electrolyte_detail_missing",
                "cell_count": len(rows),
                "cell_ids": ";".join(row["cell_id"] for row in rows),
                "observed_candidate_total": sum(label_counter.values()),
                "top_observed_label_keys": top_labels(dict(label_counter)),
                "trainability_audit_allowed": all(bool(row["trainability_audit_allowed"]) for row in rows),
            }
        )
    return output


def write_report(
    output_root: Path,
    cell_rows: list[dict[str, Any]],
    electrolyte_rows: list[dict[str, Any]],
    label_rows: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    group_counts = Counter(row["cell_group"] for row in cell_rows)
    electrolyte_codes = sorted({row["electrolyte_code"] for row in cell_rows})
    signal_counts = Counter()
    for row in label_rows:
        signal_counts[row["label_key"]] += int(row["observed_candidate_count"] or 0)
    trainability_allowed = all(bool(row["trainability_audit_allowed"]) for row in cell_rows) if cell_rows else False
    report = {
        "training_allowed_now": False,
        "model_training_allowed": False,
        "labels_generated": False,
        "raw_btsda_data_read": False,
        "metadata_aware_audit_allowed": True,
        "trainability_audit_allowed": trainability_allowed,
        "cell_count": len(cell_rows),
        "cell_group_counts": dict(group_counts),
        "electrolyte_codes": electrolyte_codes,
        "observed_candidate_counts_by_label": dict(signal_counts),
        "risk_count": len(risk_rows),
        "current_interpretable_metadata": [
            "电池类型",
            "电解液编号",
            "隔膜材料/型号",
            "压力条件",
            "静置时间",
            "锂片厚度",
            "Li||Cu 铜箔/基底信息",
        ],
        "current_blockers": [
            "终止原因缺失",
            "循环协议缺失",
            "电流密度缺失",
            "面容量缺失",
            "锂盐/浓度/添加剂缺失，因此电解液编号不能解释为完整配方",
        ],
        "recommended_manual_review": [
            "Li||Cu incomplete_capacity_event and ce_collapse by electrolyte code",
            "Li||Li polarization_growth and voltage_hysteresis_failure, especially 26-0414",
            "Confirm whether each test ended by natural failure, protocol stop, equipment interruption, or manual stop",
        ],
    }
    report["current_interpretable_metadata"] = [
        "cell_type",
        "electrolyte_code_or_composition_text",
        "separator",
        "pressure",
        "rest_time",
        "lithium_thickness",
        "current_density",
        "areal_capacity",
        "termination_reason",
        "Li||Cu copper_or_substrate_info",
    ]
    report["current_blockers"] = sorted({row["risk_key"] for row in risk_rows}) if risk_rows else [
        "none_for_metadata_aware_label_trainability_audit"
    ]
    report["recommended_manual_review"] = [
        "Li||Cu incomplete_capacity_event and ce_collapse by electrolyte code",
        "Li||Li polarization_growth and voltage_hysteresis_failure, especially 26-0414",
        "Treat planned-cycle-count endings as protocol-censored, not observed failures",
    ]
    with (output_root / "lmb_metadata_aware_audit_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    lines = [
        "# LMB Metadata-Aware Audit Report",
        "",
        "This report joins partner-provided metadata with audit-only label scans. It is not model performance and does not create training labels.",
        "",
        f"- Cell count: {len(cell_rows)}",
        f"- Li||Li cells: {group_counts.get('Li||Li', 0)}",
        f"- Li||Cu cells: {group_counts.get('Li||Cu', 0)}",
        f"- Electrolyte codes: {', '.join(electrolyte_codes)}",
        f"- Metadata-aware audit allowed: {report['metadata_aware_audit_allowed']}",
        f"- Trainability audit allowed: {report['trainability_audit_allowed']}",
        f"- Training allowed now: {report['training_allowed_now']}",
        "",
        "## Current Interpretable Metadata",
        "",
    ]
    lines.extend(f"- {item}" for item in report["current_interpretable_metadata"])
    lines.extend(["", "## Current Blockers", ""])
    lines.extend(f"- {item}" for item in report["current_blockers"])
    lines.extend(["", "## Electrolyte Code Summary", "", "| cell_group | electrolyte_code | cells | observed candidates | top signals |", "| --- | --- | --- | ---: | --- |"])
    for row in electrolyte_rows:
        lines.append(
            f"| {row['cell_group']} | `{row['electrolyte_code']}` | {row['cell_ids']} | {row['observed_candidate_total']} | {row['top_observed_label_keys']} |"
        )
    lines.extend(
        [
            "",
            "## Gate Decision",
            "",
            "- `metadata_aware_audit_allowed = True`",
            f"- `trainability_audit_allowed = {report['trainability_audit_allowed']}`",
            "- `model_training_allowed = False`",
            "- Planned-cycle-count endings should be treated as protocol-censored unless the lab confirms observed failure.",
        ]
    )
    (output_root / "lmb_metadata_aware_audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_metadata_aware_audit(
    metadata_workbook: Path,
    metadata_gate: Path,
    audit_label_summary: Path,
    audit_event_scan: Path,
    lili_features: Path,
    licu_features: Path,
    output_root: Path,
) -> dict[str, Any]:
    metadata = read_metadata_workbook(metadata_workbook)
    gates = gate_by_cell(read_csv(metadata_gate))
    summary_rows = read_csv(audit_label_summary)
    # Read event scan only to verify the file is available and audit-only; do not
    # use it as training rows.
    event_rows = read_csv(audit_event_scan)
    if any(row.get("trainable_label", "").lower() == "true" for row in event_rows):
        raise ValueError("Audit event scan unexpectedly contains trainable labels.")

    label_counts = observed_counts_by_cell(summary_rows)
    summary_grouped = summary_rows_by_cell(summary_rows)
    feature_counts = count_feature_rows(lili_features, licu_features)

    cell_rows, risk_rows = build_cell_summary(metadata, gates, label_counts, feature_counts)
    label_rows = build_label_by_metadata(metadata, gates, summary_grouped)
    electrolyte_rows = build_electrolyte_summary(cell_rows, label_rows)

    output_root.mkdir(parents=True, exist_ok=True)
    write_csv(output_root / "metadata_aware_cell_summary.csv", cell_rows, CELL_SUMMARY_COLUMNS)
    write_csv(output_root / "electrolyte_code_audit_summary.csv", electrolyte_rows, ELECTROLYTE_COLUMNS)
    write_csv(output_root / "label_signal_by_metadata_summary.csv", label_rows, LABEL_BY_METADATA_COLUMNS)
    write_csv(output_root / "unresolved_metadata_risks.csv", risk_rows, RISK_COLUMNS)
    return write_report(output_root, cell_rows, electrolyte_rows, label_rows, risk_rows)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-workbook", required=True)
    parser.add_argument("--metadata-gate", required=True)
    parser.add_argument("--audit-label-summary", required=True)
    parser.add_argument("--audit-event-scan", required=True)
    parser.add_argument("--lili-features", required=True)
    parser.add_argument("--licu-features", required=True)
    parser.add_argument("--output-root", required=True)
    return parser


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    args = build_arg_parser().parse_args()
    report = build_metadata_aware_audit(
        metadata_workbook=Path(args.metadata_workbook),
        metadata_gate=Path(args.metadata_gate),
        audit_label_summary=Path(args.audit_label_summary),
        audit_event_scan=Path(args.audit_event_scan),
        lili_features=Path(args.lili_features),
        licu_features=Path(args.licu_features),
        output_root=Path(args.output_root),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
