"""Design baseline-ready label rules for LMB Li||Cu incomplete capacity events.

This module creates a pre-export design audit only. It does not create a formal
training dataset, train models, split rows, or enter the RUL prediction
pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


TARGET_CELL_GROUP = "Li||Cu"
TARGET_LABEL_KEY = "incomplete_capacity_event"
MIN_PRE_EVENT_HISTORY = 10

EXPLICIT_LEAKAGE_COLUMNS = [
    "charge_capacity_mah",
    "discharge_capacity_mah",
    "coulombic_efficiency_percent",
    "irreversible_capacity_mah",
    "incomplete_cycle_flag",
    "ce_warning_flag",
    "capacity_retention_percent",
]

LEAKAGE_KEYWORDS = ["target", "label", "future", "event"]

DESIGN_COLUMNS = [
    "cell_group",
    "source_folder_name",
    "selected_dataset_name",
    "label_key",
    "first_event_cycle",
    "last_cycle_index",
    "pre_event_negative_window",
    "pre_event_cycle_count",
    "positive_event_cycle",
    "positive_boundary_row_policy",
    "post_event_excluded_window",
    "post_event_cycle_count",
    "protocol_censored_terminal",
    "insufficient_pre_event_history",
    "baseline_ready_design_status",
    "baseline_ready_export_candidate",
    "training_allowed_now",
    "design_notes",
]

EXCLUDED_COLUMNS = [
    "feature_column",
    "present_in_licu_features",
    "exclusion_reason",
    "exclusion_stage",
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


def parse_int(value: object) -> int:
    try:
        text = str(value).strip()
        if not text:
            return 0
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"true", "1", "yes"}


def feature_columns(feature_rows: list[dict[str, str]]) -> list[str]:
    if not feature_rows:
        return []
    return list(feature_rows[0].keys())


def metadata_by_cell(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("电池编号", ""): row for row in rows if row.get("电池编号")}


def trainability_candidates(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        if (
            row.get("cell_group") == TARGET_CELL_GROUP
            and row.get("label_key") == TARGET_LABEL_KEY
            and row.get("trainability_level") == "trainable_candidate"
            and parse_bool(row.get("baseline_ready_label_design_allowed"))
        ):
            output[row.get("source_folder_name", "")] = row
    return output


def first_event_cycles(event_rows: list[dict[str, str]]) -> dict[str, int]:
    grouped: dict[str, list[int]] = {}
    for row in event_rows:
        if row.get("cell_group") != TARGET_CELL_GROUP or row.get("label_key") != TARGET_LABEL_KEY:
            continue
        if not parse_bool(row.get("observed_candidate")):
            continue
        cell_id = row.get("source_folder_name", "")
        cycle = parse_int(row.get("cycle_index"))
        if cell_id and cycle:
            grouped.setdefault(cell_id, []).append(cycle)
    return {cell_id: min(cycles) for cell_id, cycles in grouped.items() if cycles}


def design_status(first_event: int, last_cycle: int, protocol_censored_terminal: bool, candidate_exists: bool) -> tuple[str, bool, bool, str]:
    if not candidate_exists:
        return "blocked_not_trainability_candidate", False, True, "cell is not approved by trainability audit"
    if not first_event:
        return "blocked_no_observed_incomplete_capacity_event", False, True, "no observed event cycle found in audit scan"
    pre_event_count = max(0, first_event - 1)
    insufficient = pre_event_count < MIN_PRE_EVENT_HISTORY
    if insufficient:
        return (
            "design_only_insufficient_pre_event_history",
            False,
            True,
            f"only {pre_event_count} pre-event cycles; require at least {MIN_PRE_EVENT_HISTORY}",
        )
    if protocol_censored_terminal:
        return (
            "baseline_ready_design_candidate_protocol_censored_terminal",
            True,
            False,
            "planned-cycle ending is protocol-censored; event occurred before terminal censoring",
        )
    if first_event > last_cycle:
        return "blocked_event_after_last_cycle", False, True, "first event cycle exceeds last feature cycle"
    return "baseline_ready_design_candidate", True, False, "event occurs inside feature window with enough pre-event history"


def build_design_rows(
    trainability_rows: list[dict[str, str]],
    event_rows: list[dict[str, str]],
    feature_rows: list[dict[str, str]],
    metadata_rows: list[dict[str, str]],
) -> list[dict[str, Any]]:
    candidates = trainability_candidates(trainability_rows)
    first_events = first_event_cycles(event_rows)
    metadata = metadata_by_cell(metadata_rows)
    feature_by_cell: dict[str, list[int]] = {}
    for row in feature_rows:
        if row.get("source_folder_name"):
            feature_by_cell.setdefault(row["source_folder_name"], []).append(parse_int(row.get("cycle_index")))

    rows: list[dict[str, Any]] = []
    for cell_id, candidate in sorted(candidates.items()):
        cycles = [cycle for cycle in feature_by_cell.get(cell_id, []) if cycle]
        first_event = first_events.get(cell_id, parse_int(candidate.get("first_observed_candidate_cycle")))
        last_cycle = max(cycles) if cycles else parse_int(candidate.get("last_cycle_index"))
        pre_event_count = max(0, first_event - 1) if first_event else 0
        post_event_count = max(0, last_cycle - first_event) if first_event and last_cycle else 0
        protocol_censored_terminal = metadata.get(cell_id, {}).get("termination_interpretation") == "protocol_censored"
        status, export_candidate, insufficient, notes = design_status(
            first_event=first_event,
            last_cycle=last_cycle,
            protocol_censored_terminal=protocol_censored_terminal,
            candidate_exists=True,
        )
        rows.append(
            {
                "cell_group": TARGET_CELL_GROUP,
                "source_folder_name": cell_id,
                "selected_dataset_name": candidate.get("selected_dataset_name", ""),
                "label_key": TARGET_LABEL_KEY,
                "first_event_cycle": first_event,
                "last_cycle_index": last_cycle,
                "pre_event_negative_window": f"1..{first_event - 1}" if first_event > 1 else "",
                "pre_event_cycle_count": pre_event_count,
                "positive_event_cycle": first_event,
                "positive_boundary_row_policy": "design_only; prefer t_minus_1_predicts_t before export",
                "post_event_excluded_window": f"{first_event + 1}..{last_cycle}" if first_event and last_cycle and first_event < last_cycle else "",
                "post_event_cycle_count": post_event_count,
                "protocol_censored_terminal": protocol_censored_terminal,
                "insufficient_pre_event_history": insufficient,
                "baseline_ready_design_status": status,
                "baseline_ready_export_candidate": export_candidate,
                "training_allowed_now": False,
                "design_notes": notes,
            }
        )
    return rows


def build_excluded_feature_columns(feature_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    columns = feature_columns(feature_rows)
    column_set = set(columns)
    excluded: dict[str, dict[str, Any]] = {}
    for column in EXPLICIT_LEAKAGE_COLUMNS:
        excluded[column] = {
            "feature_column": column,
            "present_in_licu_features": column in column_set,
            "exclusion_reason": "label-proximal or same-cycle leakage risk for incomplete_capacity_event",
            "exclusion_stage": "before_baseline_ready_export",
        }
    for column in columns:
        lower = column.lower()
        if any(keyword in lower for keyword in LEAKAGE_KEYWORDS):
            excluded[column] = {
                "feature_column": column,
                "present_in_licu_features": True,
                "exclusion_reason": "target/label/future/event semantic leakage pattern",
                "exclusion_stage": "before_baseline_ready_export",
            }
    return [excluded[column] for column in sorted(excluded)]


def write_report(output_root: Path, design_rows: list[dict[str, Any]], excluded_columns: list[dict[str, Any]]) -> dict[str, Any]:
    status_counts = Counter(str(row["baseline_ready_design_status"]) for row in design_rows)
    export_candidate_count = sum(1 for row in design_rows if row["baseline_ready_export_candidate"])
    report = {
        "training_allowed_now": False,
        "model_training_allowed": False,
        "rul_prediction_entered": False,
        "formal_training_dataset_generated": False,
        "baseline_ready_label_design": True,
        "target_cell_group": TARGET_CELL_GROUP,
        "target_label_key": TARGET_LABEL_KEY,
        "min_pre_event_history": MIN_PRE_EVENT_HISTORY,
        "cell_count": len(design_rows),
        "baseline_ready_export_candidate_cell_count": export_candidate_count,
        "baseline_ready_export_allowed": export_candidate_count > 0,
        "status_counts": dict(status_counts),
        "excluded_feature_column_count": len(excluded_columns),
        "label_definition": {
            "positive_event_cycle": "first observed incomplete_capacity_event cycle from audit scan",
            "pre_event_negative_window": "cycles before first_event_cycle; usable only after leakage-screened export",
            "post_event_excluded_window": "cycles after first_event_cycle; excluded from baseline-ready label design",
            "protocol_censored_terminal": "planned-cycle-count ending; not an observed natural failure",
            "insufficient_pre_event_history": f"pre_event_cycle_count < {MIN_PRE_EVENT_HISTORY}",
        },
        "leakage_policy": [
            "Do not use same-cycle incomplete_cycle_flag.",
            "Do not use same-cycle charge_capacity_mah or discharge_capacity_mah to predict the event.",
            "Do not use future cycles.",
            "Prefer t-1 features to predict event at t before baseline-ready export.",
        ],
    }
    with (output_root / "licu_incomplete_capacity_design_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    lines = [
        "# Li||Cu Incomplete Capacity Baseline-Ready Label Design",
        "",
        "This is a label design audit only. It is not model performance and does not create a formal training dataset.",
        "",
        "## Gate Decision",
        "",
        f"- `baseline_ready_export_allowed = {report['baseline_ready_export_allowed']}`",
        "- `model_training_allowed = False`",
        "- `formal_training_dataset_generated = False`",
        "- Terminal planned-cycle endings are `protocol_censored`, not observed failures.",
        "",
        "## Label Definition",
        "",
    ]
    for key, value in report["label_definition"].items():
        lines.append(f"- `{key}`: {value}")
    lines.extend(["", "## Cell Design Summary", "", "| cell | first event | last cycle | pre-event cycles | post-event excluded | status |", "| --- | ---: | ---: | ---: | ---: | --- |"])
    for row in design_rows:
        lines.append(
            f"| {row['source_folder_name']} | {row['first_event_cycle']} | {row['last_cycle_index']} | "
            f"{row['pre_event_cycle_count']} | {row['post_event_cycle_count']} | `{row['baseline_ready_design_status']}` |"
        )
    lines.extend(["", "## Leakage Exclusion", ""])
    lines.extend(f"- `{row['feature_column']}`: {row['exclusion_reason']}" for row in excluded_columns)
    (output_root / "licu_incomplete_capacity_design_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_lmb_baseline_ready_label_design(
    trainability_per_cell: Path,
    trainability_summary: Path,
    audit_event_scan: Path,
    licu_features: Path,
    metadata_gate: Path,
    label_policy: Path,
    output_root: Path,
) -> dict[str, Any]:
    _ = read_csv(trainability_summary)
    _ = label_policy.read_text(encoding="utf-8") if label_policy.exists() else ""
    output_root.mkdir(parents=True, exist_ok=True)
    trainability_rows = read_csv(trainability_per_cell)
    event_rows = read_csv(audit_event_scan)
    feature_rows = read_csv(licu_features)
    metadata_rows = read_csv(metadata_gate)
    design_rows = build_design_rows(trainability_rows, event_rows, feature_rows, metadata_rows)
    excluded_columns = build_excluded_feature_columns(feature_rows)
    write_csv(output_root / "licu_incomplete_capacity_label_design.csv", design_rows, DESIGN_COLUMNS)
    write_csv(output_root / "licu_incomplete_capacity_excluded_feature_columns.csv", excluded_columns, EXCLUDED_COLUMNS)
    return write_report(output_root, design_rows, excluded_columns)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trainability-per-cell", required=True)
    parser.add_argument("--trainability-summary", required=True)
    parser.add_argument("--audit-event-scan", required=True)
    parser.add_argument("--licu-features", required=True)
    parser.add_argument("--metadata-gate", required=True)
    parser.add_argument("--label-policy", required=True)
    parser.add_argument("--output-root", required=True)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    report = build_lmb_baseline_ready_label_design(
        trainability_per_cell=Path(args.trainability_per_cell),
        trainability_summary=Path(args.trainability_summary),
        audit_event_scan=Path(args.audit_event_scan),
        licu_features=Path(args.licu_features),
        metadata_gate=Path(args.metadata_gate),
        label_policy=Path(args.label_policy),
        output_root=Path(args.output_root),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
