"""Run a tiny LMB Li||Cu mechanistic logistic smoke-test.

This is a tiny qualitative flow check only. It uses horizon-separated
mechanistic candidate exports and leave-one-cell-out folds. It does not enter
RUL prediction, save a model, tune hyperparameters, report formal metric
values, or support generalization claims.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from pathlib import Path
from typing import Any


HORIZONS = (3, 5)
TARGET_CELL_GROUP = "Li||Cu"
TARGET_LABEL_KEY = "incomplete_capacity_event"
MODEL_FAMILY = "logistic_regression_only"
FORBIDDEN_FEATURE_EXACT = {
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

PREDICTION_COLUMNS = [
    "horizon_k",
    "fold_id",
    "test_cell",
    "row_id",
    "target_cycle",
    "label_key",
    "actual_event_at_cycle",
    "qualitative_model_score",
    "raw_score",
    "score_is_qualitative_only",
    "smoke_test_only",
    "not_formal_result",
]

DIAGNOSTIC_COLUMNS = [
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
    "class_imbalance_status",
    "fit_status",
    "fit_note",
    "coefficient_signs",
    "same_signal_source_feature_columns",
    "model_family",
    "split_type",
    "random_row_split_used",
    "model_checkpoint_saved",
    "formal_result_claimed",
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


def parse_float(value: object) -> float:
    try:
        text = str(value).strip()
        if not text:
            return 0.0
        number = float(text)
    except (TypeError, ValueError):
        return 0.0
    if math.isnan(number) or math.isinf(number):
        return 0.0
    return number


def sigmoid(value: float) -> float:
    clipped = max(min(value, 40.0), -40.0)
    return 1.0 / (1.0 + math.exp(-clipped))


def feature_columns(features: list[dict[str, str]]) -> list[str]:
    if not features:
        return []
    return [column for column in features[0] if column != "row_id"]


def leakage_columns(features: list[dict[str, str]]) -> list[str]:
    if not features:
        return []
    found = []
    for column in features[0]:
        if column == "row_id":
            continue
        lower = column.lower()
        if column in FORBIDDEN_FEATURE_EXACT or any(token in lower for token in FORBIDDEN_FEATURE_TOKENS):
            found.append(column)
    return sorted(found)


def row_id_alignment(features: list[dict[str, str]], targets: list[dict[str, str]], metadata: list[dict[str, str]]) -> bool:
    return [row.get("row_id", "") for row in features] == [row.get("row_id", "") for row in targets] == [
        row.get("row_id", "") for row in metadata
    ]


def same_signal_source_columns(metadata: list[dict[str, str]]) -> list[str]:
    columns: set[str] = set()
    for row in metadata:
        for item in row.get("same_signal_source_feature_columns", "").split(";"):
            item = item.strip()
            if item:
                columns.add(item)
    return sorted(columns)


def input_errors(
    horizon: int,
    features: list[dict[str, str]],
    targets: list[dict[str, str]],
    metadata: list[dict[str, str]],
    manifest: dict[str, Any],
    plan: dict[str, Any],
) -> list[str]:
    errors: list[str] = []
    if manifest.get("target_cell_group") != TARGET_CELL_GROUP:
        errors.append(f"h{horizon}:manifest_target_cell_group_not_licu")
    if manifest.get("target_label_key") != TARGET_LABEL_KEY:
        errors.append(f"h{horizon}:manifest_target_label_key_unexpected")
    if manifest.get("model_training_allowed") is not False:
        errors.append(f"h{horizon}:manifest_model_training_allowed_not_false")
    if plan.get("tiny_mechanistic_smoke_test_request_allowed") is not True:
        errors.append(f"h{horizon}:planning_gate_not_allowing_request")
    if not row_id_alignment(features, targets, metadata):
        errors.append(f"h{horizon}:row_id_alignment_failed")
    leaks = leakage_columns(features)
    if leaks:
        errors.append(f"h{horizon}:feature_leakage_columns_present:" + ";".join(leaks))
    bad_labels = sorted({row.get("label_key", "") for row in targets if row.get("label_key") != TARGET_LABEL_KEY})
    if bad_labels:
        errors.append(f"h{horizon}:unexpected_label_keys:" + ";".join(bad_labels))
    bad_horizons = sorted({row.get("horizon_k", "") for row in targets if parse_int(row.get("horizon_k")) != horizon})
    if bad_horizons:
        errors.append(f"h{horizon}:mixed_horizon_targets:" + ";".join(bad_horizons))
    return errors


def target_by_row_id(targets: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("row_id", ""): row for row in targets}


def metadata_by_row_id(metadata: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("row_id", ""): row for row in metadata}


def joined_rows(features: list[dict[str, str]], targets: list[dict[str, str]], metadata: list[dict[str, str]]) -> list[dict[str, Any]]:
    targets_by_id = target_by_row_id(targets)
    metadata_by_id = metadata_by_row_id(metadata)
    rows: list[dict[str, Any]] = []
    for feature_row in features:
        rid = feature_row.get("row_id", "")
        target_row = targets_by_id.get(rid, {})
        meta_row = metadata_by_id.get(rid, {})
        rows.append(
            {
                "feature_row": feature_row,
                "target_row": target_row,
                "metadata_row": meta_row,
                "cell": target_row.get("source_folder_name", ""),
                "target": parse_int(target_row.get("target_event_at_cycle")),
                "target_cycle": parse_int(target_row.get("target_cycle")),
            }
        )
    return rows


def matrix(rows: list[dict[str, Any]], columns: list[str]) -> list[list[float]]:
    return [[parse_float(row["feature_row"].get(column)) for column in columns] for row in rows]


def labels(rows: list[dict[str, Any]]) -> list[int]:
    return [parse_int(row["target"]) for row in rows]


def standardize_train(values: list[list[float]]) -> tuple[list[list[float]], list[float], list[float]]:
    if not values:
        return [], [], []
    width = len(values[0])
    means = [sum(row[index] for row in values) / len(values) for index in range(width)]
    scales: list[float] = []
    for index in range(width):
        variance = sum((row[index] - means[index]) ** 2 for row in values) / max(len(values), 1)
        scale = math.sqrt(variance)
        scales.append(scale if scale > 1e-12 else 1.0)
    return [[(row[index] - means[index]) / scales[index] for index in range(width)] for row in values], means, scales


def standardize_apply(values: list[list[float]], means: list[float], scales: list[float]) -> list[list[float]]:
    return [[(row[index] - means[index]) / scales[index] for index in range(len(means))] for row in values]


def fit_logistic_for_smoke_test(
    x_train: list[list[float]],
    y_train: list[int],
    learning_rate: float = 0.05,
    iterations: int = 2000,
) -> tuple[list[float], float, str, str]:
    if not x_train or not y_train:
        return [], 0.0, "not_fit", "empty_training_fold"
    if len(set(y_train)) < 2:
        return [0.0] * len(x_train[0]), 0.0, "not_fit", "single_class_training_fold"

    width = len(x_train[0])
    weights = [0.0] * width
    intercept = 0.0
    previous_loss: float | None = None
    fit_note = "fixed_optimizer_completed_for_smoke_test_only"
    for _ in range(iterations):
        grad_w = [0.0] * width
        grad_b = 0.0
        loss = 0.0
        for row, y_value in zip(x_train, y_train):
            raw = intercept + sum(weight * value for weight, value in zip(weights, row))
            prob = sigmoid(raw)
            error = prob - y_value
            grad_b += error
            for index, value in enumerate(row):
                grad_w[index] += error * value
            loss += -(y_value * math.log(max(prob, 1e-12)) + (1 - y_value) * math.log(max(1 - prob, 1e-12)))
        count = len(x_train)
        intercept -= learning_rate * grad_b / count
        for index in range(width):
            weights[index] -= learning_rate * grad_w[index] / count
        loss /= count
        if previous_loss is not None and abs(previous_loss - loss) < 1e-10:
            fit_note = "fixed_optimizer_plateau_for_smoke_test_only"
            break
        previous_loss = loss
    return weights, intercept, "fit_for_smoke_test_only", fit_note


def coefficient_signs(columns: list[str], weights: list[float]) -> dict[str, str]:
    signs = {}
    for column, weight in zip(columns, weights):
        if weight > 1e-9:
            signs[column] = "positive"
        elif weight < -1e-9:
            signs[column] = "negative"
        else:
            signs[column] = "zero"
    return signs


def build_folds(rows: list[dict[str, Any]]) -> list[tuple[str, list[dict[str, Any]], list[dict[str, Any]]]]:
    cells = sorted({row["cell"] for row in rows if row["cell"]})
    return [(cell, [row for row in rows if row["cell"] != cell], [row for row in rows if row["cell"] == cell]) for cell in cells]


def class_imbalance_status(positive: int, negative: int) -> str:
    if positive <= 2:
        return "very_high_risk_small_n"
    if positive == 0 or negative == 0:
        return "single_class"
    if max(positive, negative) / max(min(positive, negative), 1) >= 20:
        return "high_class_imbalance"
    return "imbalance_present"


def run_horizon_smoke_test(
    horizon: int,
    features: list[dict[str, str]],
    targets: list[dict[str, str]],
    metadata: list[dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    columns = feature_columns(features)
    rows = joined_rows(features, targets, metadata)
    same_signal = same_signal_source_columns(metadata)
    predictions: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    for fold_index, (test_cell, train_rows, test_rows) in enumerate(build_folds(rows), start=1):
        fold_id = f"h{horizon}_LOCO_{fold_index}"
        train_y = labels(train_rows)
        test_y = labels(test_rows)
        train_pos = sum(train_y)
        test_pos = sum(test_y)
        train_neg = len(train_y) - train_pos
        test_neg = len(test_y) - test_pos
        train_x_raw = matrix(train_rows, columns)
        test_x_raw = matrix(test_rows, columns)
        train_x, means, scales = standardize_train(train_x_raw)
        test_x = standardize_apply(test_x_raw, means, scales) if means else []
        weights, intercept, fit_status, fit_note = fit_logistic_for_smoke_test(train_x, train_y)

        for joined, row_values in zip(test_rows, test_x):
            raw_score = intercept + sum(weight * value for weight, value in zip(weights, row_values)) if weights else 0.0
            model_score = sigmoid(raw_score) if weights else 0.0
            target = joined["target_row"]
            predictions.append(
                {
                    "horizon_k": horizon,
                    "fold_id": fold_id,
                    "test_cell": test_cell,
                    "row_id": target.get("row_id", ""),
                    "target_cycle": target.get("target_cycle", ""),
                    "label_key": target.get("label_key", ""),
                    "actual_event_at_cycle": target.get("target_event_at_cycle", ""),
                    "qualitative_model_score": f"{model_score:.8f}",
                    "raw_score": f"{raw_score:.8f}",
                    "score_is_qualitative_only": True,
                    "smoke_test_only": True,
                    "not_formal_result": True,
                }
            )

        diagnostics.append(
            {
                "horizon_k": horizon,
                "fold_id": fold_id,
                "test_cell": test_cell,
                "train_cells": ";".join(sorted({row["cell"] for row in train_rows})),
                "train_rows": len(train_rows),
                "test_rows": len(test_rows),
                "train_positive_count": train_pos,
                "test_positive_count": test_pos,
                "train_negative_count": train_neg,
                "test_negative_count": test_neg,
                "train_positive_risk": "very_high_risk_small_n" if train_pos <= 2 else "small_n",
                "class_imbalance_status": class_imbalance_status(train_pos, train_neg),
                "fit_status": fit_status,
                "fit_note": fit_note,
                "coefficient_signs": json.dumps(coefficient_signs(columns, weights), ensure_ascii=False),
                "same_signal_source_feature_columns": ";".join(same_signal),
                "model_family": MODEL_FAMILY,
                "split_type": "leave_one_cell_out",
                "random_row_split_used": False,
                "model_checkpoint_saved": False,
                "formal_result_claimed": False,
            }
        )
    return predictions, diagnostics, columns


def write_report(
    output_root: Path,
    manifest: dict[str, Any],
    plan: dict[str, Any],
    predictions: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    feature_columns_by_horizon: dict[int, list[str]],
    errors: list[str],
) -> dict[str, Any]:
    horizons = sorted({parse_int(row["horizon_k"]) for row in predictions} | set(feature_columns_by_horizon))
    report: dict[str, Any] = {
        "smoke_test_only": True,
        "qualitative_only": True,
        "not_formal_result": True,
        "formal_result_claimed": False,
        "model_training_allowed": False,
        "tiny_smoke_test_fit_executed": not errors,
        "rul_prediction_entered": False,
        "random_row_split_used": False,
        "model_checkpoint_saved": False,
        "hyperparameter_search_used": False,
        "model_family": MODEL_FAMILY,
        "target_cell_group": TARGET_CELL_GROUP,
        "target_label_key": TARGET_LABEL_KEY,
        "input_errors": errors,
        "input_gate_passed": not errors,
        "manifest_candidate_export_only": manifest.get("candidate_export_only"),
        "plan_request_allowed": plan.get("tiny_mechanistic_smoke_test_request_allowed"),
        "horizons": {},
    }
    for horizon in horizons:
        horizon_predictions = [row for row in predictions if parse_int(row["horizon_k"]) == horizon]
        horizon_diagnostics = [row for row in diagnostics if parse_int(row["horizon_k"]) == horizon]
        positives = sum(parse_int(row.get("actual_event_at_cycle")) for row in horizon_predictions)
        cells = sorted({row["test_cell"] for row in horizon_predictions})
        report["horizons"][str(horizon)] = {
            "cell_count": len(cells),
            "cells": cells,
            "rows_scored": len(horizon_predictions),
            "positive_targets": positives,
            "negative_targets": len(horizon_predictions) - positives,
            "feature_columns_used": feature_columns_by_horizon.get(horizon, []),
            "fold_count": len(horizon_diagnostics),
            "folds_with_train_positive_le_2": sum(1 for row in horizon_diagnostics if parse_int(row["train_positive_count"]) <= 2),
            "highest_risk_level": "very_high",
        }
    output_root.mkdir(parents=True, exist_ok=True)
    (output_root / "mechanistic_tiny_smoke_test_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# LMB Mechanistic Tiny Smoke-Test Report",
        "",
        "This is a qualitative smoke-test only. It does not report formal model results and does not support generalization claims.",
        "",
        "## Gate",
        "",
        f"- `input_gate_passed = {report['input_gate_passed']}`",
        "- `model_training_allowed = False`",
        "- `formal_result_claimed = False`",
        "- `random_row_split_used = False`",
        "- `model_checkpoint_saved = False`",
        f"- `model_family = {MODEL_FAMILY}`",
        "",
        "## Horizon Summary",
        "",
        "| horizon | cells | rows scored | positive targets | folds with train positive <= 2 |",
        "| ---: | ---: | ---: | ---: | ---: |",
    ]
    for horizon in horizons:
        item = report["horizons"][str(horizon)]
        lines.append(
            f"| {horizon} | {item['cell_count']} | {item['rows_scored']} | {item['positive_targets']} | "
            f"{item['folds_with_train_positive_le_2']} |"
        )
    lines.extend(["", "## Fold Diagnostics", "", "| horizon | fold | test cell | train rows | train + | test + | risk | fit |", "| ---: | --- | --- | ---: | ---: | ---: | --- | --- |"])
    for row in diagnostics:
        lines.append(
            f"| {row['horizon_k']} | {row['fold_id']} | {row['test_cell']} | {row['train_rows']} | "
            f"{row['train_positive_count']} | {row['test_positive_count']} | {row['train_positive_risk']} | {row['fit_status']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundaries",
            "",
            "- Scores are qualitative smoke-test scores only.",
            "- Every LOCO fold still has only two positive training rows.",
            "- The event is an incomplete-capacity warning proxy, not full LMB lifetime EOL.",
            "- Terminal context remains protocol-censored.",
            "- Past-only CE/capacity trend features remain same-signal-source risk and must be reviewed before any stronger step.",
        ]
    )
    if errors:
        lines.extend(["", "## Input Gate Errors", ""])
        lines.extend(f"- `{error}`" for error in errors)
    (output_root / "mechanistic_tiny_smoke_test_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run_lmb_mechanistic_tiny_smoke_test(input_root: Path, plan_root: Path, output_root: Path) -> dict[str, Any]:
    manifest = read_json(input_root / "mechanistic_baseline_ready_manifest.json")
    plan = read_json(plan_root / "mechanistic_tiny_baseline_plan_report.json")
    all_errors: list[str] = []
    all_predictions: list[dict[str, Any]] = []
    all_diagnostics: list[dict[str, Any]] = []
    feature_columns_by_horizon: dict[int, list[str]] = {}

    for horizon in HORIZONS:
        features = read_csv(input_root / f"horizon{horizon}_mechanistic_features.csv")
        targets = read_csv(input_root / f"horizon{horizon}_mechanistic_targets.csv")
        metadata = read_csv(input_root / f"horizon{horizon}_mechanistic_metadata.csv")
        errors = input_errors(horizon, features, targets, metadata, manifest, plan)
        all_errors.extend(errors)
        feature_columns_by_horizon[horizon] = feature_columns(features)
        if errors:
            continue
        predictions, diagnostics, columns = run_horizon_smoke_test(horizon, features, targets, metadata)
        feature_columns_by_horizon[horizon] = columns
        all_predictions.extend(predictions)
        all_diagnostics.extend(diagnostics)

    write_csv(output_root / "mechanistic_tiny_loco_predictions.csv", all_predictions, PREDICTION_COLUMNS)
    write_csv(output_root / "mechanistic_tiny_loco_diagnostics.csv", all_diagnostics, DIAGNOSTIC_COLUMNS)
    return write_report(output_root, manifest, plan, all_predictions, all_diagnostics, feature_columns_by_horizon, all_errors)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--plan-root", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_lmb_mechanistic_tiny_smoke_test(args.input_root, args.plan_root, args.output_root)
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
