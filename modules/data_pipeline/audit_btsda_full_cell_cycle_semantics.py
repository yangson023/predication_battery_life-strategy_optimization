"""Audit BTSDA full-cell cycle semantics before feature or label work.

The tool does not assume an exported BTSDA ``循环号`` equals one physical
charge/discharge cycle. It reports charge/discharge pairing and step-pattern
transitions only; no feature, label, or model is produced.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Iterable


CYCLE_INDEX = "循环号"
STEP_ID = "工步号"
STEP_SEQUENCE = "工步序号"
STEP_TYPE = "工步类型"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--dataset-name", required=True)
    parser.add_argument("--export-suffix", required=True)
    parser.add_argument("--declared-cycle-count", type=int)
    parser.add_argument("--encoding", default="gbk")
    parser.add_argument("--overwrite", action="store_true")
    return parser.parse_args()


def read_csv(path: Path, encoding: str) -> list[dict[str, str]]:
    with path.open("r", encoding=encoding, newline="") as handle:
        return [row for row in csv.DictReader(handle) if any((value or "").strip() for value in row.values())]


def write_csv(path: Path, rows: Iterable[dict[str, Any]], fields: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def to_int(value: str | None) -> int | None:
    try:
        return int(float((value or "").strip()))
    except ValueError:
        return None


def find_layer(input_root: Path, layer: str, suffix: str) -> Path:
    exact = input_root / f"data_{layer}-{suffix}.csv"
    if exact.exists():
        return exact
    candidates = sorted(input_root.glob(f"*{layer}*-{suffix}.csv"))
    if len(candidates) == 1:
        return candidates[0]
    raise FileNotFoundError(f"Expected one {layer} CSV for suffix {suffix}; found {len(candidates)}")


def ordered_unique(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value and value not in result:
            result.append(value)
    return result


def step_class(step_type: str) -> str:
    if "充电" in step_type:
        return "charge"
    if "放电" in step_type:
        return "discharge"
    if "搁置" in step_type or "静置" in step_type:
        return "rest"
    return "other"


def build_pair_manifest(step_rows: list[dict[str, str]]) -> list[dict[str, Any]]:
    grouped: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in step_rows:
        cycle = to_int(row.get(CYCLE_INDEX))
        if cycle is not None:
            grouped[cycle].append(row)

    manifest: list[dict[str, Any]] = []
    for cycle in sorted(grouped):
        rows = sorted(grouped[cycle], key=lambda row: to_int(row.get(STEP_SEQUENCE)) or 0)
        kinds = [step_class(row.get(STEP_TYPE, "")) for row in rows]
        charge_count = kinds.count("charge")
        discharge_count = kinds.count("discharge")
        pair_count = min(charge_count, discharge_count)
        signature = ">".join(ordered_unique(str(row.get(STEP_ID, "")).strip() for row in rows))
        manifest.append(
            {
                "btsda_cycle_index": cycle,
                "step_row_count": len(rows),
                "charge_step_count": charge_count,
                "discharge_step_count": discharge_count,
                "rest_step_count": kinds.count("rest"),
                "complete_charge_discharge_pair_count": pair_count,
                "has_complete_charge_discharge_pair": pair_count >= 1,
                "has_multiple_charge_discharge_pairs": pair_count > 1,
                "step_id_signature": signature,
                "step_type_signature": ">".join(ordered_unique(str(row.get(STEP_TYPE, "")).strip() for row in rows)),
                "cycle_semantics_status": "candidate_complete_cycle" if pair_count == 1 else "requires_protocol_mapping",
            }
        )
    return manifest


def build_regimes(manifest: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not manifest:
        return []
    regimes: list[dict[str, Any]] = []
    active: dict[str, Any] | None = None
    for row in manifest:
        if active is None or row["step_id_signature"] != active["step_id_signature"]:
            if active is not None:
                regimes.append(active)
            active = {
                "regime_index": len(regimes) + 1,
                "start_btsda_cycle_index": row["btsda_cycle_index"],
                "end_btsda_cycle_index": row["btsda_cycle_index"],
                "step_id_signature": row["step_id_signature"],
                "cycle_count": 0,
                "interpretation": "step-pattern regime; requires BTS XML/experiment-log mapping",
            }
        active["end_btsda_cycle_index"] = row["btsda_cycle_index"]
        active["cycle_count"] += 1
    if active is not None:
        regimes.append(active)
    return regimes


def audit_cycle_semantics(
    input_root: Path,
    output_root: Path,
    dataset_name: str,
    export_suffix: str,
    declared_cycle_count: int | None,
    encoding: str = "gbk",
    overwrite: bool = False,
) -> dict[str, Any]:
    if output_root.exists() and any(output_root.iterdir()) and not overwrite:
        raise FileExistsError(f"Output directory is not empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)

    cycle_path = find_layer(input_root, "cycle", export_suffix)
    step_path = find_layer(input_root, "step", export_suffix)
    record_path = find_layer(input_root, "record", export_suffix)
    cycle_rows = read_csv(cycle_path, encoding)
    step_rows = read_csv(step_path, encoding)
    record_rows = read_csv(record_path, encoding)
    required = [CYCLE_INDEX, STEP_ID, STEP_SEQUENCE, STEP_TYPE]
    missing = [field for field in required if field not in (step_rows[0] if step_rows else {})]
    if missing:
        raise ValueError(f"Step CSV missing required fields: {missing}")

    manifest = build_pair_manifest(step_rows)
    regimes = build_regimes(manifest)
    cycle_ids = {to_int(row.get(CYCLE_INDEX)) for row in cycle_rows} - {None}
    record_ids = {to_int(row.get(CYCLE_INDEX)) for row in record_rows} - {None}
    step_ids = {row["btsda_cycle_index"] for row in manifest}
    complete_pairs = sum(int(row["complete_charge_discharge_pair_count"]) for row in manifest)
    multi_pair_ids = sum(bool(row["has_multiple_charge_discharge_pairs"]) for row in manifest)
    aligned = declared_cycle_count is not None and declared_cycle_count == len(step_ids) and multi_pair_ids == 0
    status = "provisionally_aligned" if aligned else "unresolved_requires_protocol_mapping"
    reason = (
        f"declared={declared_cycle_count}; step_cycle_ids={len(step_ids)}; "
        f"complete_pairs={complete_pairs}; multi_pair_cycle_ids={multi_pair_ids}"
    )
    summary = {
        "dataset_name": dataset_name,
        "export_suffix": export_suffix,
        "declared_physical_cycle_count": declared_cycle_count if declared_cycle_count is not None else "",
        "cycle_layer_row_count": len(cycle_rows),
        "step_layer_row_count": len(step_rows),
        "record_layer_row_count": len(record_rows),
        "cycle_layer_distinct_btsda_cycle_ids": len(cycle_ids),
        "step_layer_distinct_btsda_cycle_ids": len(step_ids),
        "record_layer_distinct_btsda_cycle_ids": len(record_ids),
        "complete_charge_discharge_pair_count": complete_pairs,
        "multi_pair_btsda_cycle_count": multi_pair_ids,
        "step_pattern_regime_count": len(regimes),
        "cycle_layer_ids_subset_of_step": cycle_ids.issubset(step_ids),
        "step_ids_subset_of_record": step_ids.issubset(record_ids),
        "cycle_count_semantics_status": status,
        "semantic_reason": reason,
        "source_data_audit_only": True,
        "model_training_allowed": False,
    }
    write_csv(output_root / "cycle_semantics_summary.csv", [summary], list(summary))
    write_csv(output_root / "step_pair_manifest.csv", manifest, list(manifest[0]) if manifest else [])
    write_csv(output_root / "protocol_transition_audit.csv", regimes, list(regimes[0]) if regimes else [])
    report = {
        "summary": summary,
        "files": {"cycle": str(cycle_path), "step": str(step_path), "record": str(record_path)},
        "training_allowed_now": False,
        "model_performance_claimed": False,
        "next_gate": "Review BTS XML or experiment log before physical-cycle reconstruction, features, labels, or models.",
    }
    (output_root / "btsda_cycle_semantics_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (output_root / "btsda_cycle_semantics_report.md").write_text(
        "# BTSDA Full-Cell Cycle Semantics Audit\n\n"
        f"- Dataset: `{dataset_name}` / export `{export_suffix}`\n"
        f"- Declared physical cycles: `{declared_cycle_count}`\n"
        f"- BTSDA step-cycle identifiers: `{len(step_ids)}`\n"
        f"- Complete charge/discharge pairs: `{complete_pairs}`\n"
        f"- Multi-pair BTSDA cycle identifiers: `{multi_pair_ids}`\n"
        f"- Step-pattern regimes: `{len(regimes)}`\n"
        f"- Semantic status: `{status}`\n\n"
        "This is intake audit only. It does not create features, labels, or model results.\n\n"
        "```text\nmodel_training_allowed=False\n```\n",
        encoding="utf-8",
    )
    return report


def main() -> None:
    args = parse_args()
    audit_cycle_semantics(
        input_root=args.input_root,
        output_root=args.output_root,
        dataset_name=args.dataset_name,
        export_suffix=args.export_suffix,
        declared_cycle_count=args.declared_cycle_count,
        encoding=args.encoding,
        overwrite=args.overwrite,
    )


if __name__ == "__main__":
    main()
