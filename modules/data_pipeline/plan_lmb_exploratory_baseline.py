"""Plan a tiny exploratory LMB Li||Cu baseline without training models.

The planner reads a baseline-ready candidate export and produces leave-one-cell-
out (LOCO) fold/risk reports. It does not train models, enter the RUL pipeline,
perform random row splits, tune hyperparameters, or report model performance.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any


LEAKAGE_KEYWORDS = ("target", "label", "future", "event", "capacity", "ce", "incomplete_cycle_flag")
FORMAL_METRIC_FORBIDDEN = ["AUC", "F1", "RMSE", "formal performance"]

FOLD_COLUMNS = [
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
    "allowed_model_family",
    "model_training_allowed",
]

RISK_COLUMNS = [
    "risk_key",
    "risk_level",
    "risk_detail",
    "affected_cells",
    "planning_decision_impact",
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


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def row_ids(rows: list[dict[str, str]]) -> list[str]:
    return [row.get("row_id", "") for row in rows]


def row_id_alignment(features: list[dict[str, str]], targets: list[dict[str, str]], metadata: list[dict[str, str]]) -> dict[str, Any]:
    feature_ids = row_ids(features)
    target_ids = row_ids(targets)
    metadata_ids = row_ids(metadata)
    duplicate_ids = sorted({rid for rid, count in Counter(feature_ids + target_ids + metadata_ids).items() if count > 3})
    return {
        "row_id_alignment_passed": feature_ids == target_ids == metadata_ids,
        "feature_row_count": len(feature_ids),
        "target_row_count": len(target_ids),
        "metadata_row_count": len(metadata_ids),
        "duplicate_row_ids": duplicate_ids,
        "missing_in_targets": sorted(set(feature_ids) - set(target_ids)),
        "missing_in_features": sorted(set(target_ids) - set(feature_ids)),
        "missing_in_metadata": sorted(set(feature_ids) - set(metadata_ids)),
    }


def leakage_columns(features: list[dict[str, str]]) -> list[str]:
    if not features:
        return []
    output = []
    for column in features[0].keys():
        lower = column.lower()
        if column == "row_id":
            continue
        if any(keyword in lower for keyword in LEAKAGE_KEYWORDS):
            output.append(column)
    return sorted(output)


def cell_counts(targets: list[dict[str, str]]) -> dict[str, dict[str, int]]:
    counts: dict[str, dict[str, int]] = {}
    for row in targets:
        cell_id = row.get("source_folder_name", "")
        if not cell_id:
            continue
        counts.setdefault(cell_id, {"rows": 0, "positive": 0, "negative": 0})
        counts[cell_id]["rows"] += 1
        if parse_int(row.get("target_event_next_cycle")) == 1:
            counts[cell_id]["positive"] += 1
        else:
            counts[cell_id]["negative"] += 1
    return counts


def build_fold_plan(targets: list[dict[str, str]]) -> list[dict[str, Any]]:
    counts = cell_counts(targets)
    cells = sorted(counts)
    folds: list[dict[str, Any]] = []
    for index, test_cell in enumerate(cells, start=1):
        train_cells = [cell for cell in cells if cell != test_cell]
        train_rows = sum(counts[cell]["rows"] for cell in train_cells)
        train_pos = sum(counts[cell]["positive"] for cell in train_cells)
        test_rows = counts[test_cell]["rows"]
        test_pos = counts[test_cell]["positive"]
        train_neg = sum(counts[cell]["negative"] for cell in train_cells)
        test_neg = counts[test_cell]["negative"]
        very_high = train_pos <= 2
        folds.append(
            {
                "fold_id": f"LOCO_{index}",
                "test_cell": test_cell,
                "train_cells": ";".join(train_cells),
                "train_rows": train_rows,
                "test_rows": test_rows,
                "train_positive_count": train_pos,
                "test_positive_count": test_pos,
                "train_negative_count": train_neg,
                "test_negative_count": test_neg,
                "train_positive_risk": "very_high_risk_small_n" if very_high else "acceptable_for_tiny_planning",
                "fold_risk_level": "very_high" if very_high else "high",
                "split_type": "leave_one_cell_out",
                "random_row_split_used": False,
                "allowed_model_family": "logistic_regression_only_if_user_approves_next_step",
                "model_training_allowed": False,
            }
        )
    return folds


def build_risk_rows(
    features: list[dict[str, str]],
    targets: list[dict[str, str]],
    metadata: list[dict[str, str]],
    manifest: dict[str, Any],
    alignment: dict[str, Any],
    leaks: list[str],
    folds: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    counts = cell_counts(targets)
    cells = sorted(counts)
    positive_total = sum(row["positive"] for row in counts.values())
    risks: list[dict[str, Any]] = [
        {
            "risk_key": "small_cell_count",
            "risk_level": "very_high" if len(cells) <= 3 else "high",
            "risk_detail": f"Only {len(cells)} exported Li||Cu cells are available.",
            "affected_cells": ";".join(cells),
            "planning_decision_impact": "exploratory qualitative baseline only",
        },
        {
            "risk_key": "positive_extremely_sparse",
            "risk_level": "very_high" if positive_total <= 3 else "high",
            "risk_detail": f"Only {positive_total} positive targets are available.",
            "affected_cells": ";".join(cells),
            "planning_decision_impact": "formal AUC/F1/RMSE and generalization claims prohibited",
        },
        {
            "risk_key": "single_cell_group_only",
            "risk_level": "high",
            "risk_detail": "Current candidate export contains Li||Cu only.",
            "affected_cells": ";".join(cells),
            "planning_decision_impact": "does not address Li||Li voltage-domain prognostics",
        },
        {
            "risk_key": "label_scope_not_full_lifetime_eol",
            "risk_level": "high",
            "risk_detail": "Target is incomplete capacity event, not complete lifetime EOL.",
            "affected_cells": ";".join(cells),
            "planning_decision_impact": "baseline can only explore local warning signal, not RUL performance",
        },
        {
            "risk_key": "protocol_censored_terminal",
            "risk_level": "high",
            "risk_detail": "All terminal endings are protocol-censored planned-cycle endings.",
            "affected_cells": ";".join(cells),
            "planning_decision_impact": "terminal endpoint must not be interpreted as observed natural failure",
        },
    ]
    if any(row["train_positive_risk"] == "very_high_risk_small_n" for row in folds):
        risks.append(
            {
                "risk_key": "fold_train_positive_too_small",
                "risk_level": "very_high",
                "risk_detail": "At least one LOCO fold has train positive count <= 2.",
                "affected_cells": ";".join(row["test_cell"] for row in folds if row["train_positive_risk"] == "very_high_risk_small_n"),
                "planning_decision_impact": "tiny run may be requested only for pipeline smoke-test style qualitative review",
            }
        )
    if not alignment["row_id_alignment_passed"]:
        risks.append(
            {
                "risk_key": "row_id_alignment_failed",
                "risk_level": "blocking",
                "risk_detail": "features/targets/metadata row_id alignment is not exact.",
                "affected_cells": ";".join(cells),
                "planning_decision_impact": "tiny baseline run not allowed until alignment is fixed",
            }
        )
    if leaks:
        risks.append(
            {
                "risk_key": "feature_leakage_columns_present",
                "risk_level": "blocking",
                "risk_detail": "Potential leakage columns remain in features: " + ";".join(leaks),
                "affected_cells": ";".join(cells),
                "planning_decision_impact": "tiny baseline run not allowed until features are re-exported",
            }
        )
    if manifest.get("model_training_allowed") is not False:
        risks.append(
            {
                "risk_key": "manifest_training_gate_unexpected",
                "risk_level": "blocking",
                "risk_detail": "Manifest does not explicitly keep model_training_allowed=false.",
                "affected_cells": ";".join(cells),
                "planning_decision_impact": "do not proceed until manifest gate is corrected",
            }
        )
    return risks


def tiny_run_request_allowed(alignment: dict[str, Any], leaks: list[str], folds: list[dict[str, Any]], targets: list[dict[str, str]]) -> bool:
    if not alignment["row_id_alignment_passed"] or leaks:
        return False
    if not folds:
        return False
    if len(cell_counts(targets)) < 3:
        return False
    if sum(parse_int(row.get("target_event_next_cycle")) for row in targets) < 3:
        return False
    return True


def write_report(
    output_root: Path,
    features: list[dict[str, str]],
    targets: list[dict[str, str]],
    metadata: list[dict[str, str]],
    manifest: dict[str, Any],
    folds: list[dict[str, Any]],
    risks: list[dict[str, Any]],
    alignment: dict[str, Any],
    leaks: list[str],
) -> dict[str, Any]:
    counts = cell_counts(targets)
    cells = sorted(counts)
    positive_total = sum(row["positive"] for row in counts.values())
    negative_total = sum(row["negative"] for row in counts.values())
    allowed_to_request = tiny_run_request_allowed(alignment, leaks, folds, targets)
    report = {
        "planning_only": True,
        "model_training_allowed": False,
        "tiny_baseline_run_executed": False,
        "rul_prediction_entered": False,
        "formal_performance_reported": False,
        "random_row_split_used": False,
        "hyperparameter_search_allowed": False,
        "tiny_baseline_run_request_allowed": allowed_to_request,
        "allowed_model_family_if_user_approves_next_step": "logistic_regression_only",
        "forbidden_model_families": ["RF", "XGBoost", "SVM", "MLP"],
        "forbidden_metrics_as_formal_performance": ["AUC", "F1", "RMSE"],
        "cell_count": len(cells),
        "cells": cells,
        "feature_rows": len(features),
        "target_rows": len(targets),
        "metadata_rows": len(metadata),
        "positive_target_count": positive_total,
        "negative_target_count": negative_total,
        "row_id_alignment": alignment,
        "feature_leakage_columns_detected": leaks,
        "fold_count": len(folds),
        "folds_with_train_positive_le_2": sum(1 for row in folds if parse_int(row["train_positive_count"]) <= 2),
        "highest_risk_level": "blocking" if any(row["risk_level"] == "blocking" for row in risks) else "very_high",
        "risk_keys": [row["risk_key"] for row in risks],
        "manifest_candidate_export_only": manifest.get("candidate_export_only"),
        "manifest_model_training_allowed": manifest.get("model_training_allowed"),
    }
    with (output_root / "exploratory_baseline_plan_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    lines = [
        "# LMB Exploratory Baseline Planning Report",
        "",
        "This is planning only. It does not train a model, does not enter RUL prediction, and does not report model performance.",
        "",
        "## Gate Decision",
        "",
        f"- `tiny_baseline_run_request_allowed = {allowed_to_request}`",
        "- `model_training_allowed = False` until the user explicitly approves a separate tiny run.",
        "- `random_row_split_used = False`",
        "- Allowed next-run model family: `logistic_regression_only`",
        "- Forbidden as formal performance claims: AUC/F1/RMSE/generalization.",
        "",
        "## Data Scale",
        "",
        f"- Cells: {len(cells)} ({', '.join(cells)})",
        f"- Rows: {len(targets)}",
        f"- Positive targets: {positive_total}",
        f"- Negative targets: {negative_total}",
        "",
        "## LOCO Fold Plan",
        "",
        "| fold | test cell | train cells | train + | test + | risk |",
        "| --- | --- | --- | ---: | ---: | --- |",
    ]
    for row in folds:
        lines.append(
            f"| {row['fold_id']} | {row['test_cell']} | {row['train_cells']} | "
            f"{row['train_positive_count']} | {row['test_positive_count']} | {row['train_positive_risk']} |"
        )
    lines.extend(["", "## Risks", "", "| risk | level | detail |", "| --- | --- | --- |"])
    for row in risks:
        lines.append(f"| `{row['risk_key']}` | `{row['risk_level']}` | {row['risk_detail']} |")
    lines.extend(
        [
            "",
            "## Prohibited Actions",
            "",
            "- Do not report formal AUC/F1/RMSE.",
            "- Do not use random row splits.",
            "- Do not claim generalization performance.",
            "- Do not treat the candidate export as a formal training dataset.",
            "- Do not run RF/XGBoost/SVM/MLP at this stage.",
        ]
    )
    (output_root / "exploratory_baseline_plan_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def plan_lmb_exploratory_baseline(
    features_path: Path,
    targets_path: Path,
    metadata_path: Path,
    manifest_path: Path,
    label_policy_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    _ = label_policy_path.read_text(encoding="utf-8") if label_policy_path.exists() else ""
    output_root.mkdir(parents=True, exist_ok=True)
    features = read_csv(features_path)
    targets = read_csv(targets_path)
    metadata = read_csv(metadata_path)
    manifest = read_manifest(manifest_path)
    alignment = row_id_alignment(features, targets, metadata)
    leaks = leakage_columns(features)
    folds = build_fold_plan(targets)
    risks = build_risk_rows(features, targets, metadata, manifest, alignment, leaks, folds)
    write_csv(output_root / "exploratory_baseline_fold_plan.csv", folds, FOLD_COLUMNS)
    write_csv(output_root / "exploratory_baseline_data_risk_summary.csv", risks, RISK_COLUMNS)
    return write_report(output_root, features, targets, metadata, manifest, folds, risks, alignment, leaks)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--features", required=True)
    parser.add_argument("--targets", required=True)
    parser.add_argument("--metadata", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--label-policy", required=True)
    parser.add_argument("--output-root", required=True)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    report = plan_lmb_exploratory_baseline(
        features_path=Path(args.features),
        targets_path=Path(args.targets),
        metadata_path=Path(args.metadata),
        manifest_path=Path(args.manifest),
        label_policy_path=Path(args.label_policy),
        output_root=Path(args.output_root),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
