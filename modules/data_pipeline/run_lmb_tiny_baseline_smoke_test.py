"""Run a tiny LMB Li||Cu logistic-regression smoke test.

This script is deliberately narrow. It only checks whether the strict-v2
baseline-ready export can flow through a leave-one-cell-out logistic regression
smoke test. It does not enter RUL prediction, tune hyperparameters, save a
model, or report formal model performance.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter
from pathlib import Path
from typing import Any


TARGET_CELL_GROUP = "Li||Cu"
TARGET_LABEL_KEY = "incomplete_capacity_event"
MODEL_FAMILY = "logistic_regression_only"
LEAKAGE_KEYWORDS = ("target", "label", "future", "event", "capacity", "ce", "incomplete_cycle_flag")

PREDICTION_COLUMNS = [
    "fold_id",
    "test_cell",
    "row_id",
    "cycle_index",
    "label_key",
    "actual_event_next_cycle",
    "model_score",
    "raw_score",
    "score_is_qualitative_only",
    "smoke_test_only",
    "not_formal_performance",
]

DIAGNOSTIC_COLUMNS = [
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
    "model_family",
    "split_type",
    "random_row_split_used",
    "model_checkpoint_saved",
    "model_performance_claimed",
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


def parse_float(value: object) -> float:
    try:
        number = float(str(value).strip())
        if math.isnan(number) or math.isinf(number):
            return 0.0
        return number
    except (TypeError, ValueError):
        return 0.0


def sigmoid(value: float) -> float:
    clipped = max(min(value, 40.0), -40.0)
    return 1.0 / (1.0 + math.exp(-clipped))


def read_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def assert_smoke_test_inputs(features: list[dict[str, str]], targets: list[dict[str, str]], manifest: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if manifest.get("target_cell_group") != TARGET_CELL_GROUP:
        errors.append("manifest_target_cell_group_not_licu")
    if manifest.get("target_label_key") != TARGET_LABEL_KEY:
        errors.append("manifest_target_label_key_not_incomplete_capacity_event")
    if manifest.get("model_training_allowed") is not False:
        errors.append("manifest_model_training_allowed_not_false")
    feature_ids = [row.get("row_id", "") for row in features]
    target_ids = [row.get("row_id", "") for row in targets]
    if feature_ids != target_ids:
        errors.append("feature_target_row_id_alignment_failed")
    if features:
        leak_columns = [
            column
            for column in features[0]
            if column != "row_id" and any(keyword in column.lower() for keyword in LEAKAGE_KEYWORDS)
        ]
        if leak_columns:
            errors.append("feature_leakage_columns_present:" + ";".join(sorted(leak_columns)))
    bad_labels = sorted({row.get("label_key", "") for row in targets if row.get("label_key") != TARGET_LABEL_KEY})
    if bad_labels:
        errors.append("unexpected_label_keys:" + ";".join(bad_labels))
    return errors


def feature_columns(features: list[dict[str, str]]) -> list[str]:
    if not features:
        return []
    return [column for column in features[0] if column != "row_id"]


def target_by_row_id(targets: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {row.get("row_id", ""): row for row in targets}


def joined_rows(features: list[dict[str, str]], targets: list[dict[str, str]]) -> list[dict[str, Any]]:
    target_lookup = target_by_row_id(targets)
    rows: list[dict[str, Any]] = []
    for row in features:
        target = target_lookup.get(row.get("row_id", ""), {})
        rows.append(
            {
                "feature_row": row,
                "target_row": target,
                "cell": target.get("source_folder_name", ""),
                "cycle_index": parse_int(target.get("cycle_index")),
                "target": parse_int(target.get("target_event_next_cycle")),
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
    normalized = [[(row[index] - means[index]) / scales[index] for index in range(width)] for row in values]
    return normalized, means, scales


def standardize_apply(values: list[list[float]], means: list[float], scales: list[float]) -> list[list[float]]:
    return [[(row[index] - means[index]) / scales[index] for index in range(len(means))] for row in values]


def fit_logistic_no_regularization(
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
    fit_note = "gradient_descent_completed_no_regularization"
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
            fit_note = "gradient_descent_plateau_no_regularization"
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
    folds = []
    for cell in cells:
        train_rows = [row for row in rows if row["cell"] != cell]
        test_rows = [row for row in rows if row["cell"] == cell]
        folds.append((cell, train_rows, test_rows))
    return folds


def class_imbalance_status(positive: int, negative: int) -> str:
    if positive <= 2:
        return "very_high_risk_small_n"
    if positive == 0 or negative == 0:
        return "single_class"
    if max(positive, negative) / max(min(positive, negative), 1) >= 20:
        return "high_class_imbalance"
    return "imbalance_present"


def run_smoke_test(features: list[dict[str, str]], targets: list[dict[str, str]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    columns = feature_columns(features)
    rows = joined_rows(features, targets)
    predictions: list[dict[str, Any]] = []
    diagnostics: list[dict[str, Any]] = []

    for fold_index, (test_cell, train_rows, test_rows) in enumerate(build_folds(rows), start=1):
        fold_id = f"LOCO_{fold_index}"
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
        weights, intercept, fit_status, fit_note = fit_logistic_no_regularization(train_x, train_y)

        for joined, row_values in zip(test_rows, test_x):
            raw_score = intercept + sum(weight * value for weight, value in zip(weights, row_values)) if weights else 0.0
            model_score = sigmoid(raw_score) if weights else 0.0
            target = joined["target_row"]
            predictions.append(
                {
                    "fold_id": fold_id,
                    "test_cell": test_cell,
                    "row_id": target.get("row_id", ""),
                    "cycle_index": target.get("cycle_index", ""),
                    "label_key": target.get("label_key", ""),
                    "actual_event_next_cycle": target.get("target_event_next_cycle", ""),
                    "model_score": f"{model_score:.8f}",
                    "raw_score": f"{raw_score:.8f}",
                    "score_is_qualitative_only": True,
                    "smoke_test_only": True,
                    "not_formal_performance": True,
                }
            )

        diagnostics.append(
            {
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
                "model_family": MODEL_FAMILY,
                "split_type": "leave_one_cell_out",
                "random_row_split_used": False,
                "model_checkpoint_saved": False,
                "model_performance_claimed": False,
            }
        )
    return predictions, diagnostics, columns


def write_report(
    output_root: Path,
    manifest: dict[str, Any],
    predictions: list[dict[str, Any]],
    diagnostics: list[dict[str, Any]],
    feature_columns_used: list[str],
    input_errors: list[str],
) -> dict[str, Any]:
    positives = sum(parse_int(row.get("actual_event_next_cycle")) for row in predictions)
    cells = sorted({row["test_cell"] for row in predictions})
    report = {
        "smoke_test_only": True,
        "qualitative_only": True,
        "not_formal_performance": True,
        "model_performance_claimed": False,
        "model_training_allowed": False,
        "rul_prediction_entered": False,
        "random_row_split_used": False,
        "model_checkpoint_saved": False,
        "hyperparameter_search_used": False,
        "model_family": MODEL_FAMILY,
        "regularization_used": False,
        "target_cell_group": TARGET_CELL_GROUP,
        "target_label_key": TARGET_LABEL_KEY,
        "input_errors": input_errors,
        "input_gate_passed": not input_errors,
        "cell_count": len(cells),
        "cells": cells,
        "feature_rows": len(predictions),
        "positive_target_count": positives,
        "negative_target_count": len(predictions) - positives,
        "feature_columns_used": feature_columns_used,
        "fold_count": len(diagnostics),
        "folds_with_train_positive_le_2": sum(1 for row in diagnostics if parse_int(row["train_positive_count"]) <= 2),
        "highest_risk_level": "very_high",
        "primary_risks": [
            "very_high_risk_small_n",
            "class_imbalance",
            "three_cell_only",
            "candidate_event_not_lifetime_eol",
            "protocol_censored_terminal_context",
        ],
        "manifest_candidate_export_only": manifest.get("candidate_export_only"),
    }
    output_root.mkdir(parents=True, exist_ok=True)
    with (output_root / "tiny_baseline_smoke_test_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    lines = [
        "# LMB Tiny Baseline Smoke Test Report",
        "",
        "This is a smoke-test-only qualitative check. It does not report formal model performance and does not support generalization claims.",
        "",
        "## Gate",
        "",
        f"- `input_gate_passed = {report['input_gate_passed']}`",
        "- `model_training_allowed = False`",
        "- `model_performance_claimed = False`",
        "- `random_row_split_used = False`",
        "- `model_checkpoint_saved = False`",
        f"- `model_family = {MODEL_FAMILY}`",
        "",
        "## Data Scale",
        "",
        f"- Cells: {len(cells)} ({', '.join(cells)})",
        f"- Rows scored: {len(predictions)}",
        f"- Positive targets: {positives}",
        f"- Negative targets: {len(predictions) - positives}",
        f"- Feature columns used: {', '.join(feature_columns_used)}",
        "",
        "## Fold Diagnostics",
        "",
        "| fold | test cell | train rows | train positive | test positive | risk | fit status |",
        "| --- | --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in diagnostics:
        lines.append(
            f"| {row['fold_id']} | {row['test_cell']} | {row['train_rows']} | "
            f"{row['train_positive_count']} | {row['test_positive_count']} | "
            f"{row['train_positive_risk']} | {row['fit_status']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation Boundaries",
            "",
            "- Scores are qualitative smoke-test scores, not validated predictions.",
            "- The training folds have only two positive rows, so this cannot support a performance claim.",
            "- The target is an incomplete-capacity event warning proxy, not full LMB lifetime EOL.",
            "- The terminal context remains protocol-censored.",
            "- More Li||Cu cells and natural failure observations are needed before formal modeling.",
        ]
    )
    if input_errors:
        lines.extend(["", "## Input Gate Errors", ""])
        lines.extend(f"- `{error}`" for error in input_errors)
    (output_root / "tiny_baseline_smoke_test_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def run_lmb_tiny_baseline_smoke_test(input_root: Path, output_root: Path) -> dict[str, Any]:
    features = read_csv(input_root / "baseline_ready_lmb_licu_features.csv")
    targets = read_csv(input_root / "baseline_ready_lmb_licu_targets.csv")
    manifest = read_manifest(input_root / "baseline_ready_lmb_licu_manifest.json")
    input_errors = assert_smoke_test_inputs(features, targets, manifest)
    predictions, diagnostics, columns = run_smoke_test(features, targets) if not input_errors else ([], [], feature_columns(features))
    write_csv(output_root / "tiny_loco_fold_predictions.csv", predictions, PREDICTION_COLUMNS)
    write_csv(output_root / "tiny_loco_fold_diagnostics.csv", diagnostics, DIAGNOSTIC_COLUMNS)
    return write_report(output_root, manifest, predictions, diagnostics, columns, input_errors)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-root", required=True)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    report = run_lmb_tiny_baseline_smoke_test(Path(args.input_root), Path(args.output_root))
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
