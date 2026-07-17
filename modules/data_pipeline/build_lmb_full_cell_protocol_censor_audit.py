"""Build audit-only protocol-censor records for active LMB full-cell exports.

This tool records confirmed planned-cycle endpoints as protocol-censored
observations. It does not infer EOL, create failure targets, or enable model
training. It is intended for later survival-style label design only.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any, Iterable


CELL_COLUMNS = [
    "cell_id", "dataset_role", "cell_scope", "electrolyte_code", "protocol_id", "label_key",
    "event_observed", "censoring_type", "censoring_long_cycle_index", "known_survival_through_long_cycle",
    "termination_reason", "planned_long_cycle_count", "terminal_pairing_status", "audit_only",
    "label_trainability_allowed", "model_training_allowed",
]
ROW_COLUMNS = [
    "cell_id", "dataset_role", "cell_scope", "protocol_id", "long_cycle_pair_index", "survival_status",
    "is_final_complete_long_cycle", "censoring_long_cycle_index", "audit_only", "model_training_allowed",
]
GATE_COLUMNS = ["gate_name", "status", "evidence", "consequence"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--termination-audit", type=Path, required=True)
    parser.add_argument("--paired-cycle-audit", type=Path, required=True)
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


def to_int(value: Any) -> int | None:
    try:
        return int(float(str(value or "")))
    except ValueError:
        return None


def build_protocol_censor_audit(
    termination_audit_path: Path,
    paired_cycle_audit_path: Path,
    output_root: Path,
    overwrite: bool = False,
) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output root is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    termination_rows = read_csv(termination_audit_path)
    paired_rows = read_csv(paired_cycle_audit_path)
    long_pairs_by_cell: dict[str, list[dict[str, str]]] = {}
    for row in paired_rows:
        if row.get("protocol_phase") == "long_cycle":
            long_pairs_by_cell.setdefault(row["cell_id"], []).append(row)

    cell_records: list[dict[str, Any]] = []
    row_records: list[dict[str, Any]] = []
    skipped_cells: list[str] = []
    for row in termination_rows:
        confirmed = str(row.get("censoring_semantics_confirmed", "")).lower() == "true"
        if not confirmed:
            skipped_cells.append(row.get("cell_id", ""))
            continue
        cell_id = row["cell_id"]
        censor_index = to_int(row.get("censored_at_long_cycle_index"))
        long_pairs = sorted(long_pairs_by_cell.get(cell_id, []), key=lambda item: to_int(item.get("long_cycle_pair_index")) or 0)
        if censor_index is None or not long_pairs:
            skipped_cells.append(cell_id)
            continue
        actual_last = to_int(long_pairs[-1].get("long_cycle_pair_index"))
        if actual_last != censor_index:
            raise ValueError(f"{cell_id}: censor index {censor_index} does not match final complete long pair {actual_last}")
        cell_records.append({
            "cell_id": cell_id,
            "dataset_role": row.get("dataset_role", ""),
            "cell_scope": row.get("cell_scope", ""),
            "electrolyte_code": row.get("electrolyte_code", ""),
            "protocol_id": row.get("protocol_id", ""),
            "label_key": "protocol_censored",
            "event_observed": False,
            "censoring_type": "planned_cycle_count_reached",
            "censoring_long_cycle_index": censor_index,
            "known_survival_through_long_cycle": censor_index,
            "termination_reason": row.get("termination_reason", ""),
            "planned_long_cycle_count": row.get("planned_long_cycle_count", ""),
            "terminal_pairing_status": row.get("terminal_pairing_status", ""),
            "audit_only": True,
            "label_trainability_allowed": False,
            "model_training_allowed": False,
        })
        for pair in long_pairs:
            index = to_int(pair.get("long_cycle_pair_index"))
            row_records.append({
                "cell_id": cell_id,
                "dataset_role": row.get("dataset_role", ""),
                "cell_scope": row.get("cell_scope", ""),
                "protocol_id": row.get("protocol_id", ""),
                "long_cycle_pair_index": index,
                "survival_status": "no_observed_failure_through_complete_cycle",
                "is_final_complete_long_cycle": index == censor_index,
                "censoring_long_cycle_index": censor_index,
                "audit_only": True,
                "model_training_allowed": False,
            })

    gates = [
        {
            "gate_name": "protocol_censored_semantics_confirmed", "status": "pass" if cell_records else "fail",
            "evidence": f"confirmed_protocol_censored_cell_count={len(cell_records)}",
            "consequence": "Censoring records may be retained for survival-style label design only.",
        },
        {
            "gate_name": "observed_failure_event_count", "status": "blocked",
            "evidence": "observed_failure_event_count=0 in this protocol-censored-only audit",
            "consequence": "No EOL/failure prediction training or classifier construction is allowed.",
        },
        {
            "gate_name": "ordinary_binary_training", "status": "blocked",
            "evidence": "All retained records are censored and carry no observed failure event.",
            "consequence": "Do not transform censored rows into negative failure labels.",
        },
        {
            "gate_name": "model_training", "status": "blocked",
            "evidence": "Audit-only censoring semantics, six cells, zero observed failures.",
            "consequence": "model_training_allowed=False",
        },
    ]
    write_csv(output_root / "lmb_full_cell_protocol_censor_labels_audit.csv", cell_records, CELL_COLUMNS)
    write_csv(output_root / "lmb_full_cell_protocol_censor_row_audit.csv", row_records, ROW_COLUMNS)
    write_csv(output_root / "lmb_full_cell_protocol_censor_gate.csv", gates, GATE_COLUMNS)
    report = {
        "protocol_censored_cell_count": len(cell_records),
        "protocol_censored_row_count": len(row_records),
        "observed_failure_event_count": 0,
        "skipped_cell_ids": skipped_cells,
        "audit_only": True,
        "label_trainability_allowed": False,
        "model_training_allowed": False,
        "model_performance_claimed": False,
        "next_gate": "Collect at least several confirmed observed full-cell failure events under documented protocols before any trainability audit for failure prediction.",
    }
    (output_root / "lmb_full_cell_protocol_censor_audit_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = [
        "# LMB Full-Cell Protocol-Censored-Only Label Audit", "",
        "All retained cells reached their planned cycling endpoint. They are right-censored at their final complete long-cycle pair, not observed failures.", "",
        f"- Protocol-censored cells: `{len(cell_records)}`",
        f"- Long-cycle audit rows: `{len(row_records)}`",
        "- Observed failure events: `0`",
        "", "## Guardrails", "",
        "- Do not convert these censored records into ordinary negative labels.",
        "- Do not create capacity EOL, RUL, or failure targets from this audit.",
        "- A future survival-analysis design requires observed events as well as censored controls.",
        "", "```text", "audit_only=True", "label_trainability_allowed=False", "model_training_allowed=False", "```",
    ]
    (output_root / "lmb_full_cell_protocol_censor_audit_report.md").write_text("\n".join(markdown) + "\n", encoding="utf-8")
    return report


def main() -> None:
    args = parse_args()
    build_protocol_censor_audit(args.termination_audit, args.paired_cycle_audit, args.output_root, args.overwrite)


if __name__ == "__main__":
    main()
