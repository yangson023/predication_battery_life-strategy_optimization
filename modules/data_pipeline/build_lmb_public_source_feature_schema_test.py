"""Build an audit-only public LMB source-data feature schema test.

This module consumes the already-created Nature source-data parser outputs and
turns them into feature-family, label-inspiration, and partner-data bridge
tables. It does not train models, create a formal training set, or enter the
RUL prediction pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


FEATURE_SCHEMA_COLUMNS = [
    "feature_family",
    "source_columns",
    "derived_feature_candidates",
    "applicable_cell_scope",
    "lmb_mechanistic_meaning",
    "partner_full_cell_required_raw_fields",
    "leakage_risk",
    "label_relevance",
    "training_allowed_now",
    "source_data_audit_only",
    "feature_schema_test_only",
]

SHEET_AVAILABILITY_COLUMNS = [
    "workbook_name",
    "paper_id",
    "sheet_name",
    "inferred_sheet_type",
    "cell_scope",
    "parsed_rows",
    "feature_family_available",
    "label_signal_available",
    "full_cell_relevance",
    "anode_free_relevance",
    "strategy_optimization_relevance",
    "usable_for_feature_schema_test",
    "usable_for_label_audit",
    "usable_for_training_now",
    "limitation_reason",
    "source_data_audit_only",
    "feature_schema_test_only",
    "model_training_allowed",
]

LABEL_MATRIX_COLUMNS = [
    "label_candidate",
    "source_signal",
    "source_sheet_examples",
    "can_define_observed_event_now",
    "can_define_censored_status_now",
    "needs_partner_full_cell_metadata",
    "risk",
    "recommended_future_use",
    "training_allowed_now",
    "source_data_audit_only",
    "feature_schema_test_only",
]

PARTNER_BRIDGE_COLUMNS = [
    "public_source_feature",
    "partner_required_field",
    "required_data_layer",
    "priority",
    "reason",
    "missing_if_not_available",
    "downstream_gate_affected",
    "training_allowed_now",
    "source_data_audit_only",
    "feature_schema_test_only",
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
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_bool(value: str) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def as_int(value: str) -> int:
    try:
        return int(float(str(value).strip()))
    except (TypeError, ValueError):
        return 0


def unique_join(values: list[str]) -> str:
    seen: list[str] = []
    for value in values:
        if value and value not in seen:
            seen.append(value)
    return ";".join(seen)


def base_feature_schema_rows() -> list[dict[str, Any]]:
    return [
        {
            "feature_family": "capacity_retention",
            "source_columns": "capacity;normalized_capacity;cycle_index",
            "derived_feature_candidates": "capacity_retention_proxy;capacity_fade_trend;early_capacity_drop_proxy;capacity_window_slope",
            "applicable_cell_scope": "anode_free_full_cell;lmb_full_cell",
            "lmb_mechanistic_meaning": "Tracks full-cell or anode-free full-cell capacity loss and lithium inventory fade proxy.",
            "partner_full_cell_required_raw_fields": "cycle_index;charge_capacity;discharge_capacity;planned_cycle_count;termination_reason",
            "leakage_risk": "Medium: capacity trends must be past-only and separated from target cycle.",
            "label_relevance": "capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible",
        },
        {
            "feature_family": "coulombic_efficiency",
            "source_columns": "CE;cycle_index",
            "derived_feature_candidates": "CE_rolling_trend_candidate;CE_collapse_candidate;CE_instability_candidate;CE_window_std",
            "applicable_cell_scope": "anode_free_full_cell;lmb_full_cell;Li||Cu_audit",
            "lmb_mechanistic_meaning": "Reflects reversibility, lithium loss, parasitic reaction, and possible unstable plating/stripping.",
            "partner_full_cell_required_raw_fields": "cycle_index;charge_capacity;discharge_capacity;CE;termination_reason",
            "leakage_risk": "Medium-high: CE can be close to CE-derived labels and must be horizon-separated.",
            "label_relevance": "CE_failure_possible;CE_instability_possible;audit_only_label_signal",
        },
        {
            "feature_family": "voltage_time",
            "source_columns": "voltage;time_index;current",
            "derived_feature_candidates": "time_voltage_curve_proxy;voltage_plateau_proxy;polarization_proxy;relaxation_or_time_voltage_shape_proxy",
            "applicable_cell_scope": "anode_free_full_cell;lmb_full_cell;Li||Li_audit",
            "lmb_mechanistic_meaning": "Captures polarization, overpotential growth, relaxation, plateau shape, and voltage instability.",
            "partner_full_cell_required_raw_fields": "record_time;voltage;current;step_type;cycle_index;rest_voltage_if_available",
            "leakage_risk": "Low-medium if extracted only from cycles before the target horizon.",
            "label_relevance": "polarization_failure_possible;voltage_instability_possible;soft_short_warning_possible",
        },
        {
            "feature_family": "electrolyte_strategy",
            "source_columns": "electrolyte_descriptor;C20_proxy;strategy_condition;CC/MPC/protocol_condition;active_learning_metric",
            "derived_feature_candidates": "electrolyte_code_context;C20_proxy_only;protocol_strategy_condition;active_learning_reference",
            "applicable_cell_scope": "anode_free_full_cell;lmb_full_cell;strategy_audit",
            "lmb_mechanistic_meaning": "Supports electrolyte and protocol comparison as strategy context, not direct lifetime proof.",
            "partner_full_cell_required_raw_fields": "electrolyte_code;electrolyte_detail_if_shareable;protocol_name;current_density;areal_capacity;voltage_cutoff",
            "leakage_risk": "High if C20 proxy is treated as full lifetime endpoint; keep as proxy only.",
            "label_relevance": "C20_proxy_only;strategy_reward_proxy;audit_only_label_signal",
        },
        {
            "feature_family": "label_inspiration",
            "source_columns": "capacity;normalized_capacity;CE;voltage;time_index;protocol_condition",
            "derived_feature_candidates": "capacity_eol_80_possible;capacity_eol_70_possible;CE_failure_possible;protocol_censored_possible;audit_only_label_signal",
            "applicable_cell_scope": "anode_free_full_cell;lmb_full_cell",
            "lmb_mechanistic_meaning": "Provides candidate label families that must be redefined with partner metadata and terminal reason.",
            "partner_full_cell_required_raw_fields": "planned_cycle_count;termination_reason;failure_mode;protocol_changes;abnormal_notes",
            "leakage_risk": "High until observed/censored/protocol-censored states are reviewed.",
            "label_relevance": "label_policy_design_only;not_training_now",
        },
    ]


def infer_sheet_feature_families(sheet_type: str, long_rows: list[dict[str, str]]) -> list[str]:
    families: list[str] = []
    if sheet_type in {"cycle_capacity_ce", "capacity_voltage_curve"}:
        families.append("capacity_retention")
    if any(row.get("CE") for row in long_rows) or sheet_type == "cycle_capacity_ce":
        families.append("coulombic_efficiency")
    if sheet_type in {"time_voltage_current", "capacity_voltage_curve"} or any(row.get("voltage") for row in long_rows):
        families.append("voltage_time")
    if sheet_type in {"electrolyte_descriptor", "active_learning_metric"}:
        families.append("electrolyte_strategy")
    if families:
        families.append("label_inspiration")
    return families or ["audit_only_unknown"]


def infer_label_signals(families: list[str], sheet_type: str) -> list[str]:
    signals: list[str] = []
    if "capacity_retention" in families:
        signals.extend(["capacity_eol_80_possible", "capacity_eol_70_possible", "protocol_censored_possible"])
    if "coulombic_efficiency" in families:
        signals.extend(["CE_failure_possible", "CE_instability_possible"])
    if "voltage_time" in families:
        signals.extend(["polarization_failure_possible", "voltage_instability_possible"])
    if sheet_type == "electrolyte_descriptor":
        signals.extend(["C20_proxy_only", "audit_only_label_signal"])
    return signals or ["audit_only_label_signal"]


def make_sheet_lookup(sheet_inventory: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, str]]:
    return {
        (row.get("workbook_name", ""), row.get("sheet_name", "")): row
        for row in sheet_inventory
    }


def make_long_lookup(long_rows: list[dict[str, str]]) -> dict[tuple[str, str], list[dict[str, str]]]:
    grouped: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    for row in long_rows:
        grouped[(row.get("workbook_name", ""), row.get("sheet_name", ""))].append(row)
    return grouped


def build_sheet_availability_rows(
    parse_manifest: list[dict[str, str]],
    sheet_inventory: list[dict[str, str]],
    long_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    sheet_lookup = make_sheet_lookup(sheet_inventory)
    long_lookup = make_long_lookup(long_rows)
    rows: list[dict[str, Any]] = []
    for parsed in parse_manifest:
        key = (parsed.get("workbook_name", ""), parsed.get("sheet_name", ""))
        sheet = sheet_lookup.get(key, {})
        sheet_long_rows = long_lookup.get(key, [])
        sheet_type = parsed.get("inferred_sheet_type", "") or sheet.get("inferred_sheet_type", "")
        cell_scope = sheet.get("cell_scope", "") or (sheet_long_rows[0].get("cell_scope", "") if sheet_long_rows else "")
        families = infer_sheet_feature_families(sheet_type, sheet_long_rows)
        signals = infer_label_signals(families, sheet_type)
        is_full_or_anode_free = cell_scope in {"anode_free_full_cell", "lmb_full_cell"}
        usable_for_schema = parsed.get("parse_status") == "parsed" and "audit_only_unknown" not in families
        usable_for_label = usable_for_schema and any("possible" in signal or "proxy" in signal for signal in signals)
        limitation = []
        if not is_full_or_anode_free:
            limitation.append("mechanism_test_not_full_cell")
        if sheet_type == "electrolyte_descriptor":
            limitation.append("C20_proxy_only_not_full_RUL_or_EOL")
        if parsed.get("parser_warning"):
            limitation.append(parsed["parser_warning"])
        if not limitation:
            limitation.append("requires_partner_metadata_for_observed_or_censored_label")
        rows.append(
            {
                "workbook_name": parsed.get("workbook_name", ""),
                "paper_id": parsed.get("paper_id", ""),
                "sheet_name": parsed.get("sheet_name", ""),
                "inferred_sheet_type": sheet_type,
                "cell_scope": cell_scope,
                "parsed_rows": parsed.get("parsed_rows", ""),
                "feature_family_available": unique_join(families),
                "label_signal_available": unique_join(signals),
                "full_cell_relevance": "high" if cell_scope == "lmb_full_cell" else ("proxy_context" if cell_scope == "anode_free_full_cell" else "not_full_cell"),
                "anode_free_relevance": "high" if cell_scope == "anode_free_full_cell" else "context_only",
                "strategy_optimization_relevance": "high" if sheet_type in {"electrolyte_descriptor", "active_learning_metric"} or any("strategy" in family for family in families) else "medium",
                "usable_for_feature_schema_test": usable_for_schema,
                "usable_for_label_audit": usable_for_label,
                "usable_for_training_now": False,
                "limitation_reason": unique_join(limitation),
                "source_data_audit_only": True,
                "feature_schema_test_only": True,
                "model_training_allowed": False,
            }
        )
    return rows


def build_label_matrix_rows(sheet_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    examples: dict[str, list[str]] = defaultdict(list)
    for row in sheet_rows:
        for signal in str(row["label_signal_available"]).split(";"):
            if signal:
                examples[signal].append(f"{row['workbook_name']}::{row['sheet_name']}")

    definitions = {
        "capacity_eol_80_possible": {
            "source_signal": "capacity or normalized_capacity decline",
            "risk": "Needs terminal reason and planned cycle count before observed/censored status.",
            "recommended_future_use": "Partner full-cell capacity label policy candidate.",
        },
        "capacity_eol_70_possible": {
            "source_signal": "capacity or normalized_capacity deeper fade",
            "risk": "May be too late or unavailable for protocol-censored cells.",
            "recommended_future_use": "Secondary degradation-depth label candidate.",
        },
        "CE_failure_possible": {
            "source_signal": "CE collapse or sustained CE decrease",
            "risk": "Same-signal-source leakage if CE-derived features are not horizon separated.",
            "recommended_future_use": "Audit before trainability; useful for anode-free and Li||Cu warning proxy.",
        },
        "CE_instability_possible": {
            "source_signal": "CE variance or repeated CE excursions",
            "risk": "Requires protocol context and instrument-quality review.",
            "recommended_future_use": "Instability label design candidate.",
        },
        "polarization_failure_possible": {
            "source_signal": "voltage-time curve shape or plateau shift",
            "risk": "Needs record/step layer and consistent current density.",
            "recommended_future_use": "Mechanistic label candidate for full-cell and Li||Li audit.",
        },
        "voltage_instability_possible": {
            "source_signal": "voltage excursions, relaxation shape, or plateau instability",
            "risk": "Could reflect protocol or sampling differences without metadata.",
            "recommended_future_use": "Audit-only until step/record alignment is verified.",
        },
        "protocol_censored_possible": {
            "source_signal": "trace ends without confirmed failure",
            "risk": "Cannot be resolved from figure-source data alone.",
            "recommended_future_use": "Mandatory censoring state for partner full-cell label policy.",
        },
        "C20_proxy_only": {
            "source_signal": "20th-cycle capacity proxy or descriptor-linked C20 value",
            "risk": "Not full lifetime RUL/EOL and must not be treated as such.",
            "recommended_future_use": "Electrolyte/strategy proxy only.",
        },
        "audit_only_label_signal": {
            "source_signal": "source-data pattern needing manual context",
            "risk": "Insufficient metadata for trainable label definition.",
            "recommended_future_use": "Manual review and label policy refinement.",
        },
    }
    rows: list[dict[str, Any]] = []
    for label, meta in definitions.items():
        rows.append(
            {
                "label_candidate": label,
                "source_signal": meta["source_signal"],
                "source_sheet_examples": unique_join(examples.get(label, [])[:8]),
                "can_define_observed_event_now": False,
                "can_define_censored_status_now": False,
                "needs_partner_full_cell_metadata": True,
                "risk": meta["risk"],
                "recommended_future_use": meta["recommended_future_use"],
                "training_allowed_now": False,
                "source_data_audit_only": True,
                "feature_schema_test_only": True,
            }
        )
    return rows


def build_partner_bridge_rows() -> list[dict[str, Any]]:
    base = [
        ("capacity_retention", "cycle_index", "cycle layer", "P0", "Needed to align degradation trajectory by cycle.", "Cannot compute capacity trends.", "feature_schema_check;label_scan"),
        ("capacity_retention", "charge_capacity", "cycle layer", "P0", "Needed for CE and charge/discharge balance.", "Cannot audit CE or incomplete capacity.", "feature_schema_check;label_scan"),
        ("capacity_retention", "discharge_capacity", "cycle layer", "P0", "Needed for capacity retention and EOL thresholds.", "Cannot define capacity_eol_80 candidate.", "label_policy;trainability_audit"),
        ("coulombic_efficiency", "CE", "cycle layer", "P0", "Direct CE signal for LMB reversibility and instability audit.", "CE label family becomes unreliable.", "label_scan;leakage_review"),
        ("voltage_time", "step_type", "step layer", "P0", "Needed to separate charge, discharge, and rest behavior.", "Voltage features may mix protocol states.", "feature_schema_check"),
        ("voltage_time", "step_duration", "step layer", "P1", "Supports kinetic and polarization proxy features.", "Duration trend features unavailable.", "feature_schema_check"),
        ("voltage_time", "voltage", "record layer", "P0", "Needed for plateau, relaxation, and polarization proxies.", "Record-level mechanistic features unavailable.", "feature_schema_check;label_scan"),
        ("voltage_time", "current", "record layer", "P0", "Needed to normalize voltage behavior by current state.", "Voltage/current alignment cannot be verified.", "feature_schema_check"),
        ("electrolyte_strategy", "electrolyte_code", "metadata", "P0", "Required to compare strategy conditions without revealing full formula.", "Cannot group strategy/electrolyte context.", "metadata_gate"),
        ("electrolyte_strategy", "electrolyte_detail_if_shareable", "metadata", "P1", "Improves mechanism interpretation if partner can share.", "Only code-level interpretation allowed.", "metadata_gate;advisor_review"),
        ("electrolyte_strategy", "current_density", "metadata", "P0", "Needed for fair comparison across cells.", "Capacity and voltage behavior cannot be normalized.", "metadata_gate;feature_schema_check"),
        ("electrolyte_strategy", "areal_capacity", "metadata", "P0", "Needed for practical LMB relevance and normalization.", "Model-ready comparability is blocked.", "metadata_gate;trainability_audit"),
        ("label_inspiration", "termination_reason", "metadata", "P0", "Required to distinguish observed failure from protocol censoring.", "Observed/censored labels cannot be trusted.", "label_policy;trainability_audit"),
        ("label_inspiration", "planned_cycle_count", "metadata", "P0", "Needed to identify protocol-censored terminal state.", "Protocol censoring cannot be reviewed.", "label_policy"),
    ]
    return [
        {
            "public_source_feature": feature,
            "partner_required_field": field,
            "required_data_layer": layer,
            "priority": priority,
            "reason": reason,
            "missing_if_not_available": missing,
            "downstream_gate_affected": gate,
            "training_allowed_now": False,
            "source_data_audit_only": True,
            "feature_schema_test_only": True,
        }
        for feature, field, layer, priority, reason, missing, gate in base
    ]


def finalize_feature_schema_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    finalized = []
    for row in rows:
        enriched = dict(row)
        enriched["training_allowed_now"] = False
        enriched["source_data_audit_only"] = True
        enriched["feature_schema_test_only"] = True
        finalized.append(enriched)
    return finalized


def build_report_md(report: dict[str, Any], sheet_rows: list[dict[str, Any]]) -> str:
    family_counts = report["feature_family_counts"]
    transferable = report["transferable_feature_families"]
    audit_only = report["audit_only_or_proxy_signals"]
    lines = [
        "# LMB Public Source Feature Schema Test",
        "",
        f"Generated: {report['generated_at']}",
        "",
        "This is a source-data and feature-schema audit. It is not a formal training set, not a model run, and not a performance result.",
        "",
        "```text",
        "source_data_audit_only=True",
        "feature_schema_test_only=True",
        "model_training_allowed=False",
        "```",
        "",
        "## Core Findings",
        "",
        "- Nature source data is most useful for defining feature families around capacity retention, CE behavior, voltage/time shape, and electrolyte/protocol strategy context.",
        "- Capacity, CE, voltage/time, and protocol/metadata requirements can be transferred into the partner full-cell intake framework.",
        "- C20 proxy is only an electrolyte or strategy proxy. It is not full lifetime RUL/EOL.",
        "- CC/MPC/protocol traces are useful for future strategy optimization design, but they cannot be randomly mixed as independent training samples.",
        "- Observed/censored labels still require partner metadata: termination reason, planned cycle count, protocol changes, current density, areal capacity, voltage cutoff, and electrolyte context.",
        "",
        "## Feature Family Counts",
        "",
    ]
    for family, count in family_counts.items():
        lines.append(f"- `{family}`: {count}")
    lines.extend(
        [
            "",
            "## Transferable To Partner Full-Cell Intake",
            "",
        ]
    )
    for family in transferable:
        lines.append(f"- `{family}`")
    lines.extend(
        [
            "",
            "## Audit-Only Or Proxy Signals",
            "",
        ]
    )
    for item in audit_only:
        lines.append(f"- `{item}`")
    lines.extend(
        [
            "",
            "## Selected Sheet Use",
            "",
            "| workbook | sheet | cell_scope | feature families | label signals | training now | limitation |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for row in sheet_rows:
        lines.append(
            f"| {row['workbook_name']} | {row['sheet_name']} | {row['cell_scope']} | "
            f"{row['feature_family_available']} | {row['label_signal_available']} | "
            f"{row['usable_for_training_now']} | {row['limitation_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Gate Decision",
            "",
            f"- public_source_label_audit_design_allowed={report['public_source_label_audit_design_allowed']}",
            "- model_training_allowed=False",
            "- direct_training_set_export_allowed=False",
            "",
            "Next step: design a public-source label-audit policy, still audit-only, before any partner full-cell trainability gate.",
        ]
    )
    return "\n".join(lines) + "\n"


def build_long_term_doc(report_md: str) -> str:
    return (
        "# LMB Public Source Feature Schema Test\n\n"
        "This project document mirrors the generated report in a durable form for future partner full-cell intake work.\n\n"
        + report_md.split("\n", 1)[1]
        + "\n## Long-Term Rule\n\n"
        "Public Nature source data can guide feature schema and label-audit design, but partner full-cell data remains the validation subject. "
        "Do not treat figure-source C20 proxy, Li||Cu mechanism traces, or Li||Li mechanism traces as full-cell lifetime training data.\n"
    )


def build_public_source_feature_schema_test(
    input_root: Path,
    output_root: Path,
    docs_output: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root already exists: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    sheet_inventory = read_csv(input_root / "source_sheet_inventory.csv")
    parse_manifest = read_csv(input_root / "selected_sheet_parse_manifest.csv")
    long_rows = read_csv(input_root / "public_lmb_source_long_preview.csv")

    feature_schema = finalize_feature_schema_rows(base_feature_schema_rows())
    sheet_rows = build_sheet_availability_rows(parse_manifest, sheet_inventory, long_rows)
    label_matrix = build_label_matrix_rows(sheet_rows)
    partner_bridge = build_partner_bridge_rows()

    family_counts = Counter()
    for row in sheet_rows:
        for family in str(row["feature_family_available"]).split(";"):
            if family:
                family_counts[family] += 1

    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source_data_audit_only": True,
        "feature_schema_test_only": True,
        "model_training_allowed": False,
        "direct_training_set_export_allowed": False,
        "formal_model_performance_claimed": False,
        "public_source_label_audit_design_allowed": True,
        "input_root": str(input_root),
        "output_root": str(output_root),
        "selected_sheet_count": len(sheet_rows),
        "long_preview_rows": len(long_rows),
        "feature_family_counts": dict(sorted(family_counts.items())),
        "transferable_feature_families": [
            "capacity_retention",
            "coulombic_efficiency",
            "voltage_time",
            "electrolyte_strategy",
        ],
        "audit_only_or_proxy_signals": [
            "C20_proxy_only",
            "protocol_censored_possible_without_terminal_metadata",
            "Li||Cu_or_Li||Li_mechanism_context_not_full_cell",
        ],
        "missing_metadata_for_real_label_audit": [
            "termination_reason",
            "planned_cycle_count",
            "current_density",
            "areal_capacity",
            "voltage_cutoff",
            "electrolyte_detail_if_shareable",
            "protocol_change_notes",
        ],
    }

    write_csv(output_root / "public_source_feature_family_schema.csv", feature_schema, FEATURE_SCHEMA_COLUMNS)
    write_csv(output_root / "public_source_sheet_feature_availability.csv", sheet_rows, SHEET_AVAILABILITY_COLUMNS)
    write_csv(output_root / "public_source_label_inspiration_matrix.csv", label_matrix, LABEL_MATRIX_COLUMNS)
    write_csv(output_root / "public_source_partner_data_requirement_bridge.csv", partner_bridge, PARTNER_BRIDGE_COLUMNS)
    write_json(output_root / "public_source_feature_schema_test_report.json", report)
    report_md = build_report_md(report, sheet_rows)
    (output_root / "public_source_feature_schema_test_report.md").write_text(report_md, encoding="utf-8")
    docs_output.parent.mkdir(parents=True, exist_ok=True)
    docs_output.write_text(build_long_term_doc(report_md), encoding="utf-8")
    return report


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--docs-output", required=True, type=Path)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    build_public_source_feature_schema_test(
        input_root=args.input_root,
        output_root=args.output_root,
        docs_output=args.docs_output,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
