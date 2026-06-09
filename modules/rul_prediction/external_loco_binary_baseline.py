"""Exploratory LOCO binary baseline for guarded external cycle labels."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_INPUT_ROOT = Path(
    "outputs/label_audit/external_trainable_labels/baseline_ready_high_minobs20"
)
DEFAULT_OUTPUT_ROOT = Path("models/rul_prediction/external_loco_binary_baseline")
ALLOWED_LABEL_KEYS = ["capacity_eol_75", "capacity_eol_80"]
JOIN_KEYS = ["dataset_split_name", "cell_id", "batch_id", "part_id", "label_key", "cycle_index"]
METADATA_COLUMNS = set(JOIN_KEYS)
FORBIDDEN_FEATURE_PATTERNS = [
    "capacity_delta_ah",
    "capacity_ah_",
    "protocol_",
    "sample_rows",
    "target_threshold_crossed",
    "cycles_to_eol_at_row",
    "SOH",
    "RUL",
]


@dataclass
class FoldSummary:
    label_key: str
    test_cell_id: str
    train_cell_ids: str
    train_rows: int
    test_rows: int
    train_positive_rows: int
    test_positive_rows: int
    predicted_positive_rows: int
    true_positive_rows: int
    false_positive_rows: int
    false_negative_rows: int
    true_negative_rows: int
    precision: float | None
    recall: float | None
    f1: float | None
    true_eol_cycle: int | None
    first_predicted_positive_cycle: int | None
    notes: str


def forbidden_feature_columns(columns: list[str]) -> list[str]:
    violations = []
    for column in columns:
        for pattern in FORBIDDEN_FEATURE_PATTERNS:
            if pattern in column:
                violations.append(column)
                break
    return sorted(set(violations))


def read_input_tables(input_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict]:
    features_path = input_root / "baseline_ready_feature_rows.csv"
    targets_path = input_root / "baseline_ready_targets.csv"
    labels_path = input_root / "baseline_ready_labels.csv"
    manifest_path = input_root / "dataset_manifest.json"
    missing = [
        path
        for path in [features_path, targets_path, labels_path, manifest_path]
        if not path.exists()
    ]
    if missing:
        raise FileNotFoundError(f"Missing baseline-ready inputs: {missing}")
    features = pd.read_csv(features_path)
    targets = pd.read_csv(targets_path)
    labels = pd.read_csv(labels_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return features, targets, labels, manifest


def feature_columns(features: pd.DataFrame) -> list[str]:
    columns = [column for column in features.columns if column not in METADATA_COLUMNS]
    violations = forbidden_feature_columns(columns)
    if violations:
        raise ValueError(f"Forbidden feature columns found: {violations}")
    return columns


def validate_inputs(features: pd.DataFrame, targets: pd.DataFrame, labels: pd.DataFrame) -> None:
    for name, frame in [("features", features), ("targets", targets)]:
        missing = sorted(set(JOIN_KEYS) - set(frame.columns))
        if missing:
            raise ValueError(f"{name} missing join keys: {missing}")
    required_target_columns = {"target_threshold_crossed", "cycles_to_eol_at_row"}
    missing_targets = sorted(required_target_columns - set(targets.columns))
    if missing_targets:
        raise ValueError(f"targets missing required columns: {missing_targets}")

    if set(features["dataset_split_name"].dropna().unique()) != {"high_minobs20"}:
        raise ValueError("Only high_minobs20 is allowed in the exploratory baseline.")
    if not set(features["label_key"].dropna().unique()).issubset(set(ALLOWED_LABEL_KEYS)):
        raise ValueError("Feature rows contain label keys outside capacity_eol_75/80.")
    if not set(labels["source_table"].dropna().unique()).issubset({"cycle_features.csv"}):
        raise ValueError("Only cycle_features.csv labels are allowed.")
    if not labels["eol_observed"].astype(str).str.lower().isin({"true"}).all():
        raise ValueError("All baseline labels must be observed EOL labels.")
    if not labels["eol_boundary_quality"].eq("away_from_protocol_boundary").all():
        raise ValueError("All baseline labels must be away from protocol boundaries.")

    feature_key_dupes = int(features.duplicated(JOIN_KEYS).sum())
    target_key_dupes = int(targets.duplicated(JOIN_KEYS).sum())
    if feature_key_dupes or target_key_dupes:
        raise ValueError(
            f"Duplicate feature/target join keys: features={feature_key_dupes}, targets={target_key_dupes}"
        )


def build_model_frame(features: pd.DataFrame, targets: pd.DataFrame) -> pd.DataFrame:
    merged = features.merge(
        targets[JOIN_KEYS + ["target_threshold_crossed", "cycles_to_eol_at_row"]],
        on=JOIN_KEYS,
        how="inner",
        validate="one_to_one",
    )
    if len(merged) != len(features):
        raise ValueError(
            f"Feature/target alignment failed: features={len(features)}, merged={len(merged)}"
        )
    merged["target_threshold_crossed"] = (
        merged["target_threshold_crossed"].astype(str).str.lower().isin({"true", "1", "yes"})
    )
    return merged


def prepare_features(
    train: pd.DataFrame,
    test: pd.DataFrame,
    columns: list[str],
) -> tuple[np.ndarray, np.ndarray]:
    train_numeric = train[columns].apply(pd.to_numeric, errors="coerce").replace([np.inf, -np.inf], np.nan)
    fill_values = train_numeric.mean(numeric_only=True).fillna(0.0)
    train_numeric = train_numeric.fillna(fill_values).fillna(0.0)
    test_numeric = (
        test[columns]
        .apply(pd.to_numeric, errors="coerce")
        .replace([np.inf, -np.inf], np.nan)
        .fillna(fill_values)
        .fillna(0.0)
    )
    means = train_numeric.mean()
    stds = train_numeric.std(ddof=0).replace(0, 1.0).fillna(1.0)
    return (
        ((train_numeric - means) / stds).to_numpy(dtype=float),
        ((test_numeric - means) / stds).to_numpy(dtype=float),
    )


def sigmoid(values: np.ndarray) -> np.ndarray:
    clipped = np.clip(values, -40.0, 40.0)
    return 1.0 / (1.0 + np.exp(-clipped))


def fit_weighted_logistic(
    x_train: np.ndarray,
    y_train: np.ndarray,
    l2: float = 1.0,
    learning_rate: float = 0.05,
    iterations: int = 1000,
) -> np.ndarray:
    x = np.column_stack([np.ones(len(x_train)), x_train])
    weights = np.zeros(x.shape[1], dtype=float)
    positives = max(float(y_train.sum()), 1.0)
    negatives = max(float(len(y_train) - y_train.sum()), 1.0)
    sample_weights = np.where(y_train == 1, len(y_train) / (2.0 * positives), len(y_train) / (2.0 * negatives))
    penalty = np.ones_like(weights)
    penalty[0] = 0.0
    for _ in range(iterations):
        probabilities = sigmoid(x @ weights)
        gradient = (x.T @ ((probabilities - y_train) * sample_weights)) / len(y_train)
        gradient += l2 * penalty * weights / len(y_train)
        weights -= learning_rate * gradient
    return weights


def predict_probability(x_test: np.ndarray, weights: np.ndarray) -> np.ndarray:
    x = np.column_stack([np.ones(len(x_test)), x_test])
    return sigmoid(x @ weights)


def binary_metrics(actual: np.ndarray, predicted: np.ndarray) -> dict[str, int | float | None]:
    true_positive = int(((actual == 1) & (predicted == 1)).sum())
    false_positive = int(((actual == 0) & (predicted == 1)).sum())
    false_negative = int(((actual == 1) & (predicted == 0)).sum())
    true_negative = int(((actual == 0) & (predicted == 0)).sum())
    precision = (
        true_positive / (true_positive + false_positive)
        if true_positive + false_positive > 0
        else None
    )
    recall = (
        true_positive / (true_positive + false_negative)
        if true_positive + false_negative > 0
        else None
    )
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and precision + recall > 0
        else None
    )
    return {
        "true_positive_rows": true_positive,
        "false_positive_rows": false_positive,
        "false_negative_rows": false_negative,
        "true_negative_rows": true_negative,
        "precision": precision,
        "recall": recall,
        "f1": f1,
    }


def run_loco_binary_baseline(
    model_frame: pd.DataFrame,
    columns: list[str],
    probability_threshold: float = 0.5,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    fold_rows: list[FoldSummary] = []
    prediction_rows = []
    fold_design_rows = []

    for label_key in ALLOWED_LABEL_KEYS:
        threshold_frame = model_frame.loc[model_frame["label_key"].eq(label_key)].copy()
        if threshold_frame.empty:
            continue
        cells = sorted(threshold_frame["cell_id"].unique().tolist())
        for test_cell_id in cells:
            train = threshold_frame.loc[threshold_frame["cell_id"].ne(test_cell_id)].copy()
            test = threshold_frame.loc[threshold_frame["cell_id"].eq(test_cell_id)].copy()
            train_cells = sorted(train["cell_id"].unique().tolist())
            train_positive_rows = int(train["target_threshold_crossed"].sum())
            test_positive_rows = int(test["target_threshold_crossed"].sum())
            fold_design_rows.append(
                {
                    "label_key": label_key,
                    "test_cell_id": test_cell_id,
                    "train_cell_ids": ";".join(train_cells),
                    "train_rows": int(len(train)),
                    "test_rows": int(len(test)),
                    "train_positive_rows": train_positive_rows,
                    "test_positive_rows": test_positive_rows,
                    "validation_strategy": "leave_one_cell_out",
                }
            )
            if train.empty or train_positive_rows == 0 or train_positive_rows == len(train):
                fold_rows.append(
                    FoldSummary(
                        label_key=label_key,
                        test_cell_id=str(test_cell_id),
                        train_cell_ids=";".join(train_cells),
                        train_rows=int(len(train)),
                        test_rows=int(len(test)),
                        train_positive_rows=train_positive_rows,
                        test_positive_rows=test_positive_rows,
                        predicted_positive_rows=0,
                        true_positive_rows=0,
                        false_positive_rows=0,
                        false_negative_rows=test_positive_rows,
                        true_negative_rows=int(len(test) - test_positive_rows),
                        precision=None,
                        recall=None,
                        f1=None,
                        true_eol_cycle=None,
                        first_predicted_positive_cycle=None,
                        notes="insufficient_training_class_diversity",
                    )
                )
                continue

            x_train, x_test = prepare_features(train, test, columns)
            y_train = train["target_threshold_crossed"].astype(int).to_numpy()
            y_test = test["target_threshold_crossed"].astype(int).to_numpy()
            weights = fit_weighted_logistic(x_train, y_train)
            probabilities = predict_probability(x_test, weights)
            predicted = probabilities >= probability_threshold
            test_predictions = test[JOIN_KEYS].copy()
            test_predictions["predicted_probability"] = probabilities
            test_predictions["predicted_threshold_crossed"] = predicted
            test_predictions["actual_threshold_crossed"] = y_test.astype(bool)
            prediction_rows.append(test_predictions)

            metrics = binary_metrics(y_test, predicted.astype(int))
            true_eol_cycles = test.loc[test["target_threshold_crossed"], "cycle_index"].tolist()
            predicted_eol_cycles = test.loc[predicted, "cycle_index"].tolist()
            fold_rows.append(
                FoldSummary(
                    label_key=label_key,
                    test_cell_id=str(test_cell_id),
                    train_cell_ids=";".join(train_cells),
                    train_rows=int(len(train)),
                    test_rows=int(len(test)),
                    train_positive_rows=train_positive_rows,
                    test_positive_rows=test_positive_rows,
                    predicted_positive_rows=int(predicted.sum()),
                    true_positive_rows=int(metrics["true_positive_rows"]),
                    false_positive_rows=int(metrics["false_positive_rows"]),
                    false_negative_rows=int(metrics["false_negative_rows"]),
                    true_negative_rows=int(metrics["true_negative_rows"]),
                    precision=metrics["precision"],
                    recall=metrics["recall"],
                    f1=metrics["f1"],
                    true_eol_cycle=int(true_eol_cycles[0]) if true_eol_cycles else None,
                    first_predicted_positive_cycle=(
                        int(min(predicted_eol_cycles)) if predicted_eol_cycles else None
                    ),
                    notes="exploratory_not_formal_performance",
                )
            )

    predictions = pd.concat(prediction_rows, ignore_index=True) if prediction_rows else pd.DataFrame()
    return (
        pd.DataFrame([asdict(row) for row in fold_rows]),
        predictions,
        pd.DataFrame(fold_design_rows),
    )


def report_markdown(
    fold_summary: pd.DataFrame,
    fold_design: pd.DataFrame,
    columns: list[str],
    manifest: dict,
) -> str:
    def markdown_table(frame: pd.DataFrame) -> str:
        if frame.empty:
            return "_No rows_"
        columns = frame.columns.tolist()
        lines = [
            "| " + " | ".join(columns) + " |",
            "| " + " | ".join(["---"] * len(columns)) + " |",
        ]
        for row in frame.to_dict("records"):
            lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
        return "\n".join(lines)

    lines = [
        "# External LOCO Binary Baseline",
        "",
        "This is an exploratory qualitative baseline. It is not validated model performance.",
        "",
        "## Scope",
        "",
        "- Dataset split: high_minobs20 only",
        "- Source: cycle-only baseline-ready export",
        "- Targets: capacity_eol_75 and capacity_eol_80",
        "- Validation: leave-one-cell-out",
        "- Forbidden: random row splits, RPT, six_minobs20, RUL regression claims",
        "",
        "## Feature Columns",
        "",
        "```text",
        "\n".join(columns),
        "```",
        "",
        "## Fold Design",
        "",
        markdown_table(fold_design),
        "",
        "## Per-Cell Prediction Summary",
        "",
        markdown_table(fold_summary),
        "",
        "## Interpretation Limits",
        "",
        "- n=3 cells is too small for formal performance claims.",
        "- EOL_75 has only two held-out cell folds with observed positives.",
        "- Metrics are shown per cell only as workflow diagnostics.",
        "- RMSE, R-squared, AUC-ROC, and cross-batch generalization claims are not reported.",
        "- Any future paper or report must describe this as exploratory and qualitative.",
        "",
        "## Source Manifest",
        "",
        f"- Input dataset split: {manifest.get('dataset_split', '')}",
        f"- Exported labels: {manifest.get('exported_label_count', '')}",
        f"- Exported feature rows: {manifest.get('exported_feature_row_count', '')}",
    ]
    return "\n".join(lines)


def write_outputs(
    output_root: Path,
    fold_summary: pd.DataFrame,
    predictions: pd.DataFrame,
    fold_design: pd.DataFrame,
    columns: list[str],
    manifest: dict,
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    fold_summary.to_csv(output_root / "loco_binary_fold_summary.csv", index=False)
    predictions.to_csv(output_root / "loco_binary_predictions.csv", index=False)
    fold_design.to_csv(output_root / "loco_binary_fold_design.csv", index=False)
    (output_root / "feature_columns.txt").write_text("\n".join(columns) + "\n", encoding="utf-8")
    report = {
        "experiment_type": "exploratory_qualitative_loco_binary_baseline",
        "is_formal_model_performance": False,
        "input_dataset_split": "high_minobs20",
        "label_keys": ALLOWED_LABEL_KEYS,
        "validation_strategy": "leave_one_cell_out",
        "feature_columns": columns,
        "folds": fold_design.to_dict("records"),
        "interpretation_limits": [
            "n=3 cells; not statistically significant",
            "per-cell metrics only; no aggregate formal performance",
            "no RUL regression, RMSE, R-squared, AUC-ROC, or random row split",
        ],
    }
    (output_root / "loco_binary_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_root / "loco_binary_report.md").write_text(
        report_markdown(fold_summary, fold_design, columns, manifest),
        encoding="utf-8",
    )


def run_external_loco_binary_baseline(
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    features, targets, labels, manifest = read_input_tables(input_root)
    validate_inputs(features, targets, labels)
    columns = feature_columns(features)
    model_frame = build_model_frame(features, targets)
    fold_summary, predictions, fold_design = run_loco_binary_baseline(model_frame, columns)
    write_outputs(output_root, fold_summary, predictions, fold_design, columns, manifest)
    return fold_summary, predictions, fold_design


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run an exploratory external LOCO binary baseline without formal performance claims."
    )
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    fold_summary, _, fold_design = run_external_loco_binary_baseline(
        input_root=args.input_root,
        output_root=args.output_root,
    )
    print("external LOCO binary baseline complete")
    print(fold_design.to_string(index=False))
    print(fold_summary.to_string(index=False))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
