"""Plan LMB Li||Cu mechanistic tiny baseline gates without training.

The planner reads horizon-separated candidate exports and creates a leave-one-
cell-out plan plus risk audits. It does not train, refit, choose
hyperparameters, run a baseline, enter RUL prediction, or report model results.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


HORIZONS = (3, 5)
TARGET_CELL_GROUP = "Li||Cu"
TARGET_LABEL_KEY = "incomplete_capacity_event"
FORBIDDEN_EXACT_FEATURE_COLUMNS = {
    "coulombic_efficiency_percent",
    "charge_capacity_mah",
    "discharge_capacity_mah",
    "incomplete_cycle_flag",
}
FORBIDDEN_FEATURE_TOKENS = (
    "target",
    "label",
    "future",
    "event",
    "record_voltage_",
    "record_current_",
)

FOLD_COLUMNS = [
    "horizon_k",
    "fold_id",
    "test_cell",
    "train_cells",
    "train_rows",
    "test_rows",
    "train_positive_count",
    "test_positive_count",
    "train_negative_count",
    "test_negative_count",
    "train_positive_risk",
    "fold_risk_level",
    "split_type",
    "random_row_split_used",
    "allowed_next_model_family",
    "model_training_allowed",
]

RISK_COLUMNS = [
    "horizon_k",
    "risk_key",
    "risk_level",
    "risk_detail",
    "affected_cells",
    "planning_decision_impact",
]

FEATURE_RISK_COLUMNS = [
    "horizon_k",
    "feature_column",
    "risk_type",
    "risk_level",
    "detail",
    "allowed_in_tiny_smoke_test_candidate",
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


def row_id_alignment(features: list[dict[str, str]], targets: list[dict[str, str]], metadata: list[dict[str, str]]) -> dict[str, Any]:
    feature_ids = [row.get("row_id", "") for row in features]
    target_ids = [row.get("row_id", "") for row in targets]
    metadata_ids = [row.get("row_id", "") for row in metadata]
    return {
        "row_id_alignment_passed": feature_ids == target_ids == metadata_ids,
        "feature_row_count": len(feature_ids),
        "target_row_count": len(target_ids),
        "metadata_row_count": len(metadata_ids),
        "missing_in_targets": sorted(set(feature_ids) - set(target_ids)),
        "missing_in_features": sorted(set(target_ids) - set(feature_ids)),
        "missing_in_metadata": sorted(set(feature_ids) - set(metadata_ids)),
        "duplicate_row_ids": sorted({rid for rid, count in Counter(feature_ids + target_ids + metadata_ids).items() if count > 3}),
    }


def leakage_columns(features: list[dict[str, str]]) -> list[str]:
    if not features:
        return []
    found: list[str] = []
    for column in features[0].keys():
        if column == "row_id":
            continue
        lower = column.lower()
        if column in FORBIDDEN_EXACT_FEATURE_COLUMNS or any(token in lower for token in FORBIDDEN_FEATURE_TOKENS):
            found.append(column)
    return sorted(found)


def cell_counts(targets: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "positive": 0, "negative": 0})
    for row in targets:
        cell_id = row.get("source_folder_name", "")
        if not cell_id:
            continue
        counts[cell_id]["rows"] += 1
        if parse_int(row.get("target_event_at_cycle")) == 1:
            counts[cell_id]["positive"] += 1
        else:
            counts[cell_id]["negative"] += 1
    return dict(counts)


def build_loco_folds(horizon: int, targets: list[dict[str, str]]) -> list[dict[str, Any]]:
    counts = cell_counts(targets)
    cells = sorted(counts)
    folds: list[dict[str, Any]] = []
    for index, test_cell in enumerate(cells, start=1):
        train_cells = [cell for cell in cells if cell != test_cell]
        train_rows = sum(counts[cell]["rows"] for cell in train_cells)
        test_rows = counts[test_cell]["rows"]
        train_positive = sum(counts[cell]["positive"] for cell in train_cells)
        test_positive = counts[test_cell]["positive"]
        train_negative = sum(counts[cell]["negative"] for cell in train_cells)
        test_negative = counts[test_cell]["negative"]
        small_n = train_positive <= 2
        folds.append(
            {
                "horizon_k": horizon,
                "fold_id": f"h{horizon}_LOCO_{index}",
                "test_cell": test_cell,
                "train_cells": ";".join(train_cells),
                "train_rows": train_rows,
                "test_rows": test_rows,
                "train_positive_count": train_positive,
                "test_positive_count": test_positive,
                "train_negative_count": train_negative,
                "test_negative_count": test_negative,
                "train_positive_risk": "very_high_risk_small_n" if small_n else "high_risk_small_n",
                "fold_risk_level": "very_high" if small_n else "high",
                "split_type": "leave_one_cell_out",
                "random_row_split_used": False,
                "allowed_next_model_family": "logistic_regression_only_if_user_approves_tiny_smoke_test",
                "model_training_allowed": False,
            }
        )
    return folds


def same_signal_columns_from_metadata(metadata: list[dict[str, str]]) -> list[str]:
    columns: set[str] = set()
    for row in metadata:
        text = row.get("same_signal_source_feature_columns", "")
        for item in text.split(";"):
            item = item.strip()
            if item:
                columns.add(item)
    return sorted(columns)


def build_feature_risk_rows(horizon: int, features: list[dict[str, str]], same_signal_columns: list[str]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for column in leakage_columns(features):
        rows.append(
            {
                "horizon_k": horizon,
                "feature_column": column,
                "risk_type": "forbidden_leakage_column",
                "risk_level": "blocking",
                "detail": "Forbidden feature column remains in candidate features.",
                "allowed_in_tiny_smoke_test_candidate": False,
            }
        )
    for column in same_signal_columns:
        rows.append(
            {
                "horizon_k": horizon,
                "feature_column": column,
                "risk_type": "same_signal_source_risk",
                "risk_level": "high",
                "detail": "Past-only CE/capacity trend may share signal family with incomplete-capacity event.",
                "allowed_in_tiny_smoke_test_candidate": True,
            }
        )
    if features:
        for column in features[0].keys():
            if column == "row_id" or column in same_signal_columns or column in leakage_columns(features):
                continue
            rows.append(
                {
                    "horizon_k": horizon,
                    "feature_column": column,
                    "risk_type": "mechanistic_past_only_feature",
                    "risk_level": "review",
                    "detail": "Voltage or kinetic past-only feature retained for tiny planning.",
                    "allowed_in_tiny_smoke_test_candidate": True,
                }
            )
    return rows


def build_risk_rows(
    horizon: int,
    targets: list[dict[str, str]],
    alignment: dict[str, Any],
    leaks: list[str],
    folds: list[dict[str, Any]],
    same_signal_columns: list[str],
    manifest: dict[str, Any],
) -> list[dict[str, Any]]:
    counts = cell_counts(targets)
    cells = sorted(counts)
    positives = sum(row["positive"] for row in counts.values())
    risks: list[dict[str, Any]] = [
        {
            "horizon_k": horizon,
            "risk_key": "small_cell_count",
            "risk_level": "very_high",
            "risk_detail": f"Only {len(cells)} Li||Cu candidate cells are available.",
            "affected_cells": ";".join(cells),
            "planning_decision_impact": "tiny qualitative smoke-test planning only",
        },
        {
            "horizon_k": horizon,
            "risk_key": "positive_extremely_sparse",
            "risk_level": "very_high",
            "risk_detail": f"Only {positives} positive targets are available.",
            "affected_cells": ";".join(cells),
            "planning_decision_impact": "generalization claims are prohibited",
        },
        {
            "horizon_k": horizon,
            "risk_key": "licu_only_scope",
            "risk_level": "high",
            "risk_detail": "Candidate export covers Li||Cu only.",
            "affected_cells": ";".join(cells),
            "planning_decision_impact": "does not cover Li||Li voltage instability questions",
        },
        {
            "horizon_k": horizon,
            "risk_key": "event_label_not_lifetime_eol",
            "risk_level": "high",
            "risk_detail": "Label is incomplete_capacity_event, not full lifetime EOL.",
            "affected_cells": ";".join(cells),
            "planning_decision_impact": "scope is local event warning, not RUL conclusion",
        },
        {
            "horizon_k": horizon,
            "risk_key": "protocol_censored_terminal",
            "risk_level": "high",
            "risk_detail": "Terminal status is protocol-censored.",
            "affected_cells": ";".join(cells),
            "planning_decision_impact": "terminal cycle must not be treated as observed natural failure",
        },
    ]
    if any(parse_int(row["train_positive_count"]) <= 2 for row in folds):
        risks.append(
            {
                "horizon_k": horizon,
                "risk_key": "very_high_risk_small_n",
                "risk_level": "very_high",
                "risk_detail": "Each LOCO fold has train positive count <= 2.",
                "affected_cells": ";".join(row["test_cell"] for row in folds if parse_int(row["train_positive_count"]) <= 2),
                "planning_decision_impact": "only a user-approved tiny smoke-test may be requested",
            }
        )
    if same_signal_columns:
        risks.append(
            {
                "horizon_k": horizon,
                "risk_key": "same_signal_source_risk",
                "risk_level": "high",
                "risk_detail": "Past-only CE/capacity trend features are retained but share signal family with the target event.",
                "affected_cells": ";".join(cells),
                "planning_decision_impact": "must be reported as risk in any tiny smoke-test review",
            }
        )
    if not alignment["row_id_alignment_passed"]:
        risks.append(
            {
                "horizon_k": horizon,
                "risk_key": "row_id_alignment_failed",
                "risk_level": "blocking",
                "risk_detail": "Features, targets, and metadata row_id order or membership is not identical.",
                "affected_cells": ";".join(cells),
                "planning_decision_impact": "tiny smoke-test request not allowed",
            }
        )
    if leaks:
        risks.append(
            {
                "horizon_k": horizon,
                "risk_key": "feature_leakage_columns_present",
                "risk_level": "blocking",
                "risk_detail": "Forbidden feature columns remain: " + ";".join(leaks),
                "affected_cells": ";".join(cells),
                "planning_decision_impact": "tiny smoke-test request not allowed",
            }
        )
    if manifest.get("model_training_allowed") is not False:
        risks.append(
            {
                "horizon_k": horizon,
                "risk_key": "manifest_training_gate_unexpected",
                "risk_level": "blocking",
                "risk_detail": "Manifest does not explicitly set model_training_allowed=false.",
                "affected_cells": ";".join(cells),
                "planning_decision_impact": "tiny smoke-test request not allowed",
            }
        )
    return risks


def request_allowed(alignments: dict[int, dict[str, Any]], leaks: dict[int, list[str]], folds: list[dict[str, Any]]) -> bool:
    if any(not result["row_id_alignment_passed"] for result in alignments.values()):
        return False
    if any(items for items in leaks.values()):
        return False
    if not folds:
        return False
    return True


def write_report(
    output_root: Path,
    manifest: dict[str, Any],
    horizon_data: dict[int, dict[str, Any]],
    fold_rows: list[dict[str, Any]],
    risk_rows: list[dict[str, Any]],
    feature_risk_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    alignments = {horizon: payload["alignment"] for horizon, payload in horizon_data.items()}
    leaks = {horizon: payload["leaks"] for horizon, payload in horizon_data.items()}
    allowed = request_allowed(alignments, leaks, fold_rows)
    report = {
        "planning_only": True,
        "model_training_allowed": False,
        "tiny_smoke_test_executed": False,
        "rul_prediction_entered": False,
        "random_row_split_used": False,
        "formal_metric_values_reported": False,
        "tiny_mechanistic_smoke_test_request_allowed": allowed,
        "allowed_next_model_family_if_user_approves": "logistic_regression_only",
        "target_cell_group": TARGET_CELL_GROUP,
        "target_label_key": TARGET_LABEL_KEY,
        "horizons": {},
        "risk_keys": sorted({row["risk_key"] for row in risk_rows}),
        "feature_risk_row_count": len(feature_risk_rows),
        "manifest_candidate_export_only": manifest.get("candidate_export_only"),
        "manifest_model_training_allowed": manifest.get("model_training_allowed"),
    }
    for horizon, payload in sorted(horizon_data.items()):
        counts = cell_counts(payload["targets"])
        report["horizons"][str(horizon)] = {
            "cell_count": len(counts),
            "cells": sorted(counts),
            "feature_rows": len(payload["features"]),
            "target_rows": len(payload["targets"]),
            "metadata_rows": len(payload["metadata"]),
            "positive_targets": sum(row["positive"] for row in counts.values()),
            "negative_targets": sum(row["negative"] for row in counts.values()),
            "row_id_alignment": payload["alignment"],
            "feature_leakage_columns_detected": payload["leaks"],
            "same_signal_source_risk_features": payload["same_signal_columns"],
            "folds_with_train_positive_le_2": sum(
                1 for row in fold_rows if parse_int(row["horizon_k"]) == horizon and parse_int(row["train_positive_count"]) <= 2
            ),
            "per_cell_counts": counts,
        }
    (output_root / "mechanistic_tiny_baseline_plan_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# LMB Mechanistic Tiny Baseline Plan",
        "",
        "This is a planning gate only. No model is trained, no baseline is run, and no model result is claimed.",
        "",
        "## Gate",
        "",
        f"- `tiny_mechanistic_smoke_test_request_allowed = {allowed}`",
        "- `model_training_allowed = False`",
        "- `random_row_split_used = False`",
        "- Next step, if separately approved: `logistic_regression_only`",
        "",
        "## Horizon Summary",
        "",
        "| horizon | cells | rows | positive targets | fold small-n flag |",
        "| ---: | ---: | ---: | ---: | --- |",
    ]
    for horizon in sorted(horizon_data):
        item = report["horizons"][str(horizon)]
        lines.append(
            f"| {horizon} | {item['cell_count']} | {item['target_rows']} | {item['positive_targets']} | very_high_risk_small_n |"
        )
    lines.extend(["", "## LOCO Plan", "", "| horizon | fold | test cell | train cells | train + | test + |", "| ---: | --- | --- | --- | ---: | ---: |"])
    for row in fold_rows:
        lines.append(
            f"| {row['horizon_k']} | {row['fold_id']} | {row['test_cell']} | {row['train_cells']} | "
            f"{row['train_positive_count']} | {row['test_positive_count']} |"
        )
    lines.extend(["", "## Key Risks", "", "| horizon | risk | level | detail |", "| ---: | --- | --- | --- |"])
    for row in risk_rows:
        lines.append(f"| {row['horizon_k']} | `{row['risk_key']}` | `{row['risk_level']}` | {row['risk_detail']} |")
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "Planning may proceed to a separately approved tiny smoke-test request only. Training remains prohibited in this step.",
            "Past-only CE/capacity trend features are retained as high-risk same-signal-source features and must be reviewed after any tiny smoke-test.",
        ]
    )
    (output_root / "mechanistic_tiny_baseline_plan_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def plan_lmb_mechanistic_tiny_baseline(input_root: Path, output_root: Path) -> dict[str, Any]:
    output_root.mkdir(parents=True, exist_ok=True)
    manifest = read_json(input_root / "mechanistic_baseline_ready_manifest.json")
    horizon_data: dict[int, dict[str, Any]] = {}
    fold_rows: list[dict[str, Any]] = []
    risk_rows: list[dict[str, Any]] = []
    feature_risk_rows: list[dict[str, Any]] = []
    for horizon in HORIZONS:
        features = read_csv(input_root / f"horizon{horizon}_mechanistic_features.csv")
        targets = read_csv(input_root / f"horizon{horizon}_mechanistic_targets.csv")
        metadata = read_csv(input_root / f"horizon{horizon}_mechanistic_metadata.csv")
        alignment = row_id_alignment(features, targets, metadata)
        leaks = leakage_columns(features)
        same_signal_columns = same_signal_columns_from_metadata(metadata)
        folds = build_loco_folds(horizon, targets)
        horizon_risks = build_risk_rows(horizon, targets, alignment, leaks, folds, same_signal_columns, manifest)
        horizon_feature_risks = build_feature_risk_rows(horizon, features, same_signal_columns)
        horizon_data[horizon] = {
            "features": features,
            "targets": targets,
            "metadata": metadata,
            "alignment": alignment,
            "leaks": leaks,
            "same_signal_columns": same_signal_columns,
        }
        fold_rows.extend(folds)
        risk_rows.extend(horizon_risks)
        feature_risk_rows.extend(horizon_feature_risks)
    write_csv(output_root / "mechanistic_loco_fold_plan.csv", fold_rows, FOLD_COLUMNS)
    write_csv(output_root / "mechanistic_baseline_data_risk_summary.csv", risk_rows, RISK_COLUMNS)
    write_csv(output_root / "mechanistic_feature_risk_audit.csv", feature_risk_rows, FEATURE_RISK_COLUMNS)
    return write_report(output_root, manifest, horizon_data, fold_rows, risk_rows, feature_risk_rows)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = plan_lmb_mechanistic_tiny_baseline(args.input_root, args.output_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
