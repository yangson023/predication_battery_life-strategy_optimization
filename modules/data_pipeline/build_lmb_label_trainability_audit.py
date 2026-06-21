"""Build lithium metal battery label trainability audit outputs.

This audit reviews existing audit-only label scans against metadata gates. It
does not create a training dataset, train models, split rows, or enter the RUL
prediction pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


PER_CELL_COLUMNS = [
    "cell_group",
    "source_folder_name",
    "selected_dataset_name",
    "label_key",
    "trainability_level",
    "trainability_reason",
    "rows_scanned",
    "observed_candidate_count",
    "censored_candidate_count",
    "limited_window_count",
    "protocol_censored_count",
    "first_observed_candidate_cycle",
    "last_cycle_index",
    "termination_interpretation",
    "metadata_gate_status",
    "metadata_trainability_prerequisite",
    "terminal_protocol_censored",
    "terminal_censoring_affects_interpretation",
    "event_rows_scanned",
    "event_observed_rows",
    "event_audit_only_rows",
    "baseline_ready_label_design_allowed",
    "training_allowed_now",
]

SUMMARY_COLUMNS = [
    "cell_group",
    "label_key",
    "trainability_level",
    "cell_count",
    "trainable_candidate_cell_count",
    "audit_only_cell_count",
    "protocol_censored_only_cell_count",
    "needs_manual_review_cell_count",
    "observed_candidate_total",
    "censored_candidate_total",
    "limited_window_total",
    "protocol_censored_total",
    "first_observed_candidate_cycle_min",
    "last_cycle_index_max",
    "baseline_ready_label_design_allowed",
    "training_allowed_now",
    "summary_reason",
]

EXCLUDED_COLUMNS = [
    "cell_group",
    "source_folder_name",
    "selected_dataset_name",
    "label_key",
    "trainability_level",
    "exclusion_reason",
    "observed_candidate_count",
    "terminal_protocol_censored",
    "terminal_censoring_affects_interpretation",
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


def cell_key(row: dict[str, str]) -> str:
    return row.get("source_folder_name") or row.get("cell_id") or row.get("电池编号") or ""


def metadata_by_cell(rows: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    output: dict[str, dict[str, str]] = {}
    for row in rows:
        key = row.get("电池编号") or row.get("source_folder_name") or row.get("cell_id")
        if key:
            output[key] = row
    return output


def feature_counts(rows: list[dict[str, str]]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for row in rows:
        key = cell_key(row)
        if key:
            counts[key] += 1
    return dict(counts)


def event_stats(rows: list[dict[str, str]]) -> dict[tuple[str, str], dict[str, int]]:
    grouped: dict[tuple[str, str], dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for row in rows:
        key = (cell_key(row), row.get("label_key", ""))
        grouped[key]["event_rows_scanned"] += 1
        if parse_bool(row.get("observed_candidate")):
            grouped[key]["event_observed_rows"] += 1
        if parse_bool(row.get("audit_only")):
            grouped[key]["event_audit_only_rows"] += 1
        if parse_bool(row.get("protocol_censored")):
            grouped[key]["event_protocol_censored_rows"] += 1
    return grouped


def terminal_censoring_affects(row: dict[str, str], terminal_protocol_censored: bool) -> bool:
    if not terminal_protocol_censored:
        return False
    label_key = row.get("label_key", "")
    first_observed = parse_int(row.get("first_observed_candidate_cycle"))
    last_cycle = parse_int(row.get("last_cycle_index"))
    limited = parse_int(row.get("limited_window_count"))
    observed = parse_int(row.get("observed_candidate_count"))
    if label_key == "protocol_censored":
        return True
    if observed == 0:
        return True
    if limited > 0:
        return True
    if first_observed and last_cycle and first_observed >= max(1, last_cycle - 5):
        return True
    return False


def classify_trainability(
    row: dict[str, str],
    metadata: dict[str, str],
    terminal_protocol_censored: bool,
    terminal_affected: bool,
) -> tuple[str, str]:
    label_key = row.get("label_key", "")
    cell_group = row.get("cell_group", "")
    observed = parse_int(row.get("observed_candidate_count"))
    rows_scanned = parse_int(row.get("rows_scanned"))
    metadata_ready = (
        metadata.get("metadata_gate_status") == "metadata_ready_for_label_audit"
        and parse_bool(metadata.get("trainability_audit_prerequisite"))
    )

    if not metadata_ready:
        return "needs_manual_review", "metadata gate is not ready for label trainability audit"
    if label_key == "protocol_censored":
        return "protocol_censored_only", "protocol censoring is a censoring state, not a failure label"
    if observed <= 0:
        if terminal_protocol_censored:
            return "protocol_censored_only", "no observed candidate before planned-cycle protocol end"
        return "audit_only", "no observed candidate in the current scan window"

    if cell_group == "Li||Cu" and label_key == "incomplete_capacity_event":
        if rows_scanned < 50:
            return "needs_manual_review", "Li||Cu incomplete-capacity candidate exists but cycle window is short"
        return (
            "trainable_candidate",
            "Li||Cu incomplete-capacity event is the lowest-leakage first candidate for baseline-ready label design",
        )

    if cell_group == "Li||Cu" and label_key == "ce_collapse":
        if terminal_affected:
            return "needs_manual_review", "CE collapse is future-window and terminal-window affected; leakage and censoring review required"
        return "needs_manual_review", "CE collapse needs time-shift and leakage review before label design"

    if cell_group == "Li||Cu" and label_key in {"ce_instability", "ce_sustained_degradation"}:
        return "audit_only", "CE-derived label is threshold-sensitive and label-proximal; keep as audit-only for now"

    if cell_group == "Li||Li":
        return "audit_only", "Li||Li voltage-domain signals need expert threshold review and more observed failure confirmation"

    return "needs_manual_review", "label key or cell group is not covered by the current LMB trainability policy"


def choose_summary_level(levels: list[str]) -> str:
    if not levels:
        return "needs_manual_review"
    if any(level == "trainable_candidate" for level in levels):
        return "trainable_candidate"
    if any(level == "needs_manual_review" for level in levels):
        return "needs_manual_review"
    if all(level == "protocol_censored_only" for level in levels):
        return "protocol_censored_only"
    return "audit_only"


def build_per_cell_rows(
    metadata_gate_rows: list[dict[str, str]],
    metadata_aware_rows: list[dict[str, str]],
    event_rows: list[dict[str, str]],
    summary_rows: list[dict[str, str]],
    lili_features: list[dict[str, str]],
    licu_features: list[dict[str, str]],
) -> list[dict[str, Any]]:
    gate_by_cell = metadata_by_cell(metadata_gate_rows)
    aware_by_cell = metadata_by_cell(metadata_aware_rows)
    stats = event_stats(event_rows)
    counts = feature_counts(lili_features)
    for key, value in feature_counts(licu_features).items():
        counts[key] = counts.get(key, 0) + value

    output: list[dict[str, Any]] = []
    for row in sorted(summary_rows, key=lambda item: (item.get("cell_group", ""), item.get("source_folder_name", ""), item.get("label_key", ""))):
        cell_id = cell_key(row)
        metadata = gate_by_cell.get(cell_id, {})
        aware = aware_by_cell.get(cell_id, {})
        termination = metadata.get("termination_interpretation", "")
        terminal_protocol_censored = termination == "protocol_censored"
        terminal_affected = terminal_censoring_affects(row, terminal_protocol_censored)
        level, reason = classify_trainability(row, metadata, terminal_protocol_censored, terminal_affected)
        key = (cell_id, row.get("label_key", ""))
        event = stats.get(key, {})
        feature_count = counts.get(cell_id, 0)
        output.append(
            {
                "cell_group": row.get("cell_group", ""),
                "source_folder_name": cell_id,
                "selected_dataset_name": row.get("selected_dataset_name", ""),
                "label_key": row.get("label_key", ""),
                "trainability_level": level,
                "trainability_reason": reason,
                "rows_scanned": row.get("rows_scanned", ""),
                "observed_candidate_count": row.get("observed_candidate_count", ""),
                "censored_candidate_count": row.get("censored_candidate_count", ""),
                "limited_window_count": row.get("limited_window_count", ""),
                "protocol_censored_count": row.get("protocol_censored_count", ""),
                "first_observed_candidate_cycle": row.get("first_observed_candidate_cycle", ""),
                "last_cycle_index": row.get("last_cycle_index", ""),
                "termination_interpretation": termination,
                "metadata_gate_status": metadata.get("metadata_gate_status", ""),
                "metadata_trainability_prerequisite": metadata.get("trainability_audit_prerequisite", ""),
                "terminal_protocol_censored": terminal_protocol_censored,
                "terminal_censoring_affects_interpretation": terminal_affected,
                "event_rows_scanned": event.get("event_rows_scanned", 0),
                "event_observed_rows": event.get("event_observed_rows", 0),
                "event_audit_only_rows": event.get("event_audit_only_rows", 0),
                "baseline_ready_label_design_allowed": level == "trainable_candidate",
                "training_allowed_now": False,
                "feature_rows_for_cell": feature_count,
                "metadata_aware_trainability_audit_allowed": aware.get("trainability_audit_allowed", ""),
            }
        )
    return output


def build_summary_rows(per_cell_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in per_cell_rows:
        grouped[(str(row["cell_group"]), str(row["label_key"]))].append(row)

    output: list[dict[str, Any]] = []
    for (cell_group, label_key), rows in sorted(grouped.items()):
        levels = [str(row["trainability_level"]) for row in rows]
        level = choose_summary_level(levels)
        first_cycles = [parse_int(row.get("first_observed_candidate_cycle")) for row in rows if parse_int(row.get("first_observed_candidate_cycle"))]
        last_cycles = [parse_int(row.get("last_cycle_index")) for row in rows if parse_int(row.get("last_cycle_index"))]
        output.append(
            {
                "cell_group": cell_group,
                "label_key": label_key,
                "trainability_level": level,
                "cell_count": len({row["source_folder_name"] for row in rows}),
                "trainable_candidate_cell_count": sum(1 for row in rows if row["trainability_level"] == "trainable_candidate"),
                "audit_only_cell_count": sum(1 for row in rows if row["trainability_level"] == "audit_only"),
                "protocol_censored_only_cell_count": sum(1 for row in rows if row["trainability_level"] == "protocol_censored_only"),
                "needs_manual_review_cell_count": sum(1 for row in rows if row["trainability_level"] == "needs_manual_review"),
                "observed_candidate_total": sum(parse_int(row.get("observed_candidate_count")) for row in rows),
                "censored_candidate_total": sum(parse_int(row.get("censored_candidate_count")) for row in rows),
                "limited_window_total": sum(parse_int(row.get("limited_window_count")) for row in rows),
                "protocol_censored_total": sum(parse_int(row.get("protocol_censored_count")) for row in rows),
                "first_observed_candidate_cycle_min": min(first_cycles) if first_cycles else "",
                "last_cycle_index_max": max(last_cycles) if last_cycles else "",
                "baseline_ready_label_design_allowed": level == "trainable_candidate",
                "training_allowed_now": False,
                "summary_reason": "; ".join(sorted({str(row["trainability_reason"]) for row in rows})),
            }
        )
    return output


def build_excluded_rows(per_cell_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in per_cell_rows:
        if row["trainability_level"] == "trainable_candidate":
            continue
        rows.append(
            {
                "cell_group": row["cell_group"],
                "source_folder_name": row["source_folder_name"],
                "selected_dataset_name": row["selected_dataset_name"],
                "label_key": row["label_key"],
                "trainability_level": row["trainability_level"],
                "exclusion_reason": row["trainability_reason"],
                "observed_candidate_count": row["observed_candidate_count"],
                "terminal_protocol_censored": row["terminal_protocol_censored"],
                "terminal_censoring_affects_interpretation": row["terminal_censoring_affects_interpretation"],
            }
        )
    return rows


def write_report(output_root: Path, per_cell_rows: list[dict[str, Any]], summary_rows: list[dict[str, Any]]) -> dict[str, Any]:
    level_counts = Counter(str(row["trainability_level"]) for row in per_cell_rows)
    group_label_row_counts = Counter(str(row["cell_group"]) for row in per_cell_rows)
    group_unique_cell_counts: dict[str, int] = {}
    for group in sorted({str(row["cell_group"]) for row in per_cell_rows}):
        group_unique_cell_counts[group] = len({str(row["source_folder_name"]) for row in per_cell_rows if row["cell_group"] == group})
    trainable_labels = sorted(
        {
            f"{row['cell_group']}::{row['label_key']}"
            for row in summary_rows
            if row["trainability_level"] == "trainable_candidate"
        }
    )
    protocol_censored_cells = sorted(
        {
            str(row["source_folder_name"])
            for row in per_cell_rows
            if row["terminal_protocol_censored"]
        }
    )
    report = {
        "training_allowed_now": False,
        "model_training_allowed": False,
        "rul_prediction_entered": False,
        "formal_training_dataset_generated": False,
        "label_trainability_audit": True,
        "baseline_ready_label_design_allowed": bool(trainable_labels),
        "baseline_ready_label_export_allowed": False,
        "cell_label_rows": len(per_cell_rows),
        "cell_group_label_row_counts": dict(group_label_row_counts),
        "cell_group_unique_cell_counts": group_unique_cell_counts,
        "trainability_level_counts": dict(level_counts),
        "trainable_candidate_labels": trainable_labels,
        "protocol_censored_cells": protocol_censored_cells,
        "protocol_censored_cell_count": len(protocol_censored_cells),
        "interpretation_note": "Planned-cycle-count endings are protocol-censored and are not observed natural failures.",
    }
    with (output_root / "lmb_label_trainability_audit_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    lines = [
        "# LMB Label Trainability Audit Report",
        "",
        "This report audits label trainability only. It is not model performance, does not create a training set, and does not enter RUL prediction.",
        "",
        "## Gate Decision",
        "",
        f"- `baseline_ready_label_design_allowed = {report['baseline_ready_label_design_allowed']}`",
        "- `baseline_ready_label_export_allowed = False`",
        "- `model_training_allowed = False`",
        "- Planned-cycle-count endings are treated as `protocol_censored`, not observed failures.",
        "",
        "## Trainability Levels",
        "",
    ]
    for level, count in sorted(level_counts.items()):
        lines.append(f"- `{level}`: {count}")
    lines.extend(["", "## Trainable Candidate Labels", ""])
    if trainable_labels:
        lines.extend(f"- `{label}`" for label in trainable_labels)
    else:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Label Summary",
            "",
            "| cell_group | label_key | trainability_level | cells | observed candidates | reason |",
            "| --- | --- | --- | ---: | ---: | --- |",
        ]
    )
    for row in summary_rows:
        lines.append(
            f"| {row['cell_group']} | `{row['label_key']}` | `{row['trainability_level']}` | "
            f"{row['cell_count']} | {row['observed_candidate_total']} | {row['summary_reason']} |"
        )
    (output_root / "lmb_label_trainability_audit_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_lmb_label_trainability_audit(
    metadata_gate: Path,
    metadata_aware_summary: Path,
    audit_event_scan: Path,
    audit_label_summary: Path,
    lili_features: Path,
    licu_features: Path,
    output_root: Path,
) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    per_cell_rows = build_per_cell_rows(
        metadata_gate_rows=read_csv(metadata_gate),
        metadata_aware_rows=read_csv(metadata_aware_summary),
        event_rows=read_csv(audit_event_scan),
        summary_rows=read_csv(audit_label_summary),
        lili_features=read_csv(lili_features),
        licu_features=read_csv(licu_features),
    )
    summary_rows = build_summary_rows(per_cell_rows)
    excluded_rows = build_excluded_rows(per_cell_rows)
    write_csv(output_root / "per_cell_label_trainability.csv", per_cell_rows, PER_CELL_COLUMNS)
    write_csv(output_root / "label_trainability_summary.csv", summary_rows, SUMMARY_COLUMNS)
    write_csv(output_root / "excluded_or_audit_only_labels.csv", excluded_rows, EXCLUDED_COLUMNS)
    return write_report(output_root, per_cell_rows, summary_rows)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metadata-gate", required=True)
    parser.add_argument("--metadata-aware-summary", required=True)
    parser.add_argument("--audit-event-scan", required=True)
    parser.add_argument("--audit-label-summary", required=True)
    parser.add_argument("--lili-features", required=True)
    parser.add_argument("--licu-features", required=True)
    parser.add_argument("--output-root", required=True)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    report = build_lmb_label_trainability_audit(
        metadata_gate=Path(args.metadata_gate),
        metadata_aware_summary=Path(args.metadata_aware_summary),
        audit_event_scan=Path(args.audit_event_scan),
        audit_label_summary=Path(args.audit_label_summary),
        lili_features=Path(args.lili_features),
        licu_features=Path(args.licu_features),
        output_root=Path(args.output_root),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
