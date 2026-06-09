"""Diagnostics for the exploratory external LOCO binary baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd


DEFAULT_BASELINE_ROOT = Path("models/rul_prediction/external_loco_binary_baseline")
DEFAULT_BASELINE_READY_ROOT = Path(
    "outputs/label_audit/external_trainable_labels/baseline_ready_high_minobs20"
)
DEFAULT_OUTPUT_ROOT = DEFAULT_BASELINE_ROOT / "diagnostics"
PROBABILITY_THRESHOLDS = [0.3, 0.5, 0.7]
JOIN_KEYS = ["label_key", "cell_id"]
FORMAL_METRIC_TERMS = ["rmse", "r-squared", "r2", "auc"]


def read_required_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    return pd.read_csv(path)


def read_feature_columns(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(f"Missing feature columns file: {path}")
    return [line.strip() for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_baseline_outputs(baseline_root: Path) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict, list[str]]:
    fold_design = read_required_csv(baseline_root / "loco_binary_fold_design.csv")
    fold_summary = read_required_csv(baseline_root / "loco_binary_fold_summary.csv")
    predictions = read_required_csv(baseline_root / "loco_binary_predictions.csv")
    report_path = baseline_root / "loco_binary_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Missing baseline report: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    feature_columns = read_feature_columns(baseline_root / "feature_columns.txt")
    return fold_design, fold_summary, predictions, report, feature_columns


def add_eol_context(predictions: pd.DataFrame, predicted_column: str = "predicted_threshold_crossed") -> pd.DataFrame:
    frame = predictions.copy()
    frame["predicted_threshold_crossed"] = (
        frame[predicted_column].astype(str).str.lower().isin({"true", "1", "yes"})
    )
    frame["actual_threshold_crossed"] = (
        frame["actual_threshold_crossed"].astype(str).str.lower().isin({"true", "1", "yes"})
    )

    eol_cycles = (
        frame.loc[frame["actual_threshold_crossed"]]
        .groupby(JOIN_KEYS)["cycle_index"]
        .min()
        .rename("true_eol_cycle")
        .reset_index()
    )
    predicted_cycles = (
        frame.loc[frame["predicted_threshold_crossed"]]
        .groupby(JOIN_KEYS)["cycle_index"]
        .min()
        .rename("first_predicted_positive_cycle")
        .reset_index()
    )
    frame = frame.merge(eol_cycles, on=JOIN_KEYS, how="left")
    frame = frame.merge(predicted_cycles, on=JOIN_KEYS, how="left")
    return frame


def binary_metrics(actual: pd.Series, predicted: pd.Series) -> dict[str, object]:
    actual_values = actual.astype(bool).to_numpy()
    predicted_values = predicted.astype(bool).to_numpy()
    tp = int(((actual_values == 1) & (predicted_values == 1)).sum())
    fp = int(((actual_values == 0) & (predicted_values == 1)).sum())
    fn = int(((actual_values == 1) & (predicted_values == 0)).sum())
    tn = int(((actual_values == 0) & (predicted_values == 0)).sum())
    precision = tp / (tp + fp) if tp + fp > 0 else np.nan
    recall = tp / (tp + fn) if tp + fn > 0 else np.nan
    f1 = 2 * precision * recall / (precision + recall) if precision + recall > 0 else np.nan
    return {
        "true_positive_rows": tp,
        "false_positive_rows": fp,
        "false_negative_rows": fn,
        "true_negative_rows": tn,
        "precision_diagnostic": precision,
        "recall_diagnostic": recall,
        "f1_diagnostic": f1,
    }


def build_threshold_sensitivity(predictions: pd.DataFrame, thresholds: list[float]) -> pd.DataFrame:
    rows = []
    for threshold in thresholds:
        threshold_frame = predictions.copy()
        threshold_frame["predicted_at_threshold"] = (
            threshold_frame["predicted_probability"].astype(float) >= threshold
        )
        for (label_key, cell_id), group in threshold_frame.groupby(JOIN_KEYS, dropna=False):
            metrics = binary_metrics(group["actual_threshold_crossed"], group["predicted_at_threshold"])
            first_predicted = group.loc[group["predicted_at_threshold"], "cycle_index"]
            true_eol = group.loc[
                group["actual_threshold_crossed"].astype(str).str.lower().isin({"true", "1", "yes"}),
                "cycle_index",
            ]
            rows.append(
                {
                    "probability_threshold": threshold,
                    "label_key": label_key,
                    "cell_id": cell_id,
                    "rows": int(len(group)),
                    "actual_positive_rows": int(
                        group["actual_threshold_crossed"].astype(str).str.lower().isin({"true", "1", "yes"}).sum()
                    ),
                    "predicted_positive_rows": int(group["predicted_at_threshold"].sum()),
                    "true_eol_cycle": int(true_eol.min()) if not true_eol.empty else np.nan,
                    "first_predicted_positive_cycle": (
                        int(first_predicted.min()) if not first_predicted.empty else np.nan
                    ),
                    **metrics,
                }
            )
    return pd.DataFrame(rows)


def classify_timing(true_eol_cycle: object, first_predicted_cycle: object) -> str:
    true_missing = pd.isna(true_eol_cycle)
    predicted_missing = pd.isna(first_predicted_cycle)
    if true_missing and predicted_missing:
        return "no_observed_eol_no_prediction"
    if true_missing:
        return "prediction_without_observed_eol"
    if predicted_missing:
        return "missed_eol"
    true_cycle = int(float(true_eol_cycle))
    predicted_cycle = int(float(first_predicted_cycle))
    if predicted_cycle < true_cycle:
        return "early_false_positive"
    if predicted_cycle > true_cycle:
        return "late_detection"
    return "exact_eol_hit"


def build_prediction_timing_error(trajectory: pd.DataFrame) -> pd.DataFrame:
    rows = []
    grouped = trajectory.groupby(JOIN_KEYS, dropna=False)
    for (label_key, cell_id), group in grouped:
        true_eol = group["true_eol_cycle"].dropna()
        first_predicted = group["first_predicted_positive_cycle"].dropna()
        true_cycle = true_eol.min() if not true_eol.empty else np.nan
        predicted_cycle = first_predicted.min() if not first_predicted.empty else np.nan
        timing_class = classify_timing(true_cycle, predicted_cycle)
        rows.append(
            {
                "label_key": label_key,
                "cell_id": cell_id,
                "true_eol_cycle": true_cycle,
                "first_predicted_positive_cycle": predicted_cycle,
                "prediction_timing_error_cycles": (
                    predicted_cycle - true_cycle
                    if not pd.isna(true_cycle) and not pd.isna(predicted_cycle)
                    else np.nan
                ),
                "timing_class": timing_class,
            }
        )
    return pd.DataFrame(rows)


def build_false_positive_false_negative_audit(trajectory: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for row in trajectory.to_dict("records"):
        actual = bool(row["actual_threshold_crossed"])
        predicted = bool(row["predicted_threshold_crossed"])
        if actual and predicted:
            event_type = "exact_eol_hit" if row["cycle_index"] == row["true_eol_cycle"] else "true_positive"
        elif predicted and not actual:
            event_type = (
                "early_false_positive"
                if not pd.isna(row["true_eol_cycle"]) and row["cycle_index"] < row["true_eol_cycle"]
                else "late_detection"
            )
        elif actual and not predicted:
            event_type = "missed_eol"
        else:
            continue
        rows.append(
            {
                "label_key": row["label_key"],
                "cell_id": row["cell_id"],
                "batch_id": row.get("batch_id", ""),
                "part_id": row.get("part_id", ""),
                "cycle_index": row["cycle_index"],
                "predicted_probability": row["predicted_probability"],
                "actual_threshold_crossed": actual,
                "predicted_threshold_crossed": predicted,
                "true_eol_cycle": row["true_eol_cycle"],
                "first_predicted_positive_cycle": row["first_predicted_positive_cycle"],
                "event_type": event_type,
            }
        )
    return pd.DataFrame(rows)


def build_batch_feature_risk_summary(
    baseline_ready_root: Path,
    feature_columns: list[str],
    risk_threshold: float = 0.10,
) -> pd.DataFrame:
    feature_path = baseline_ready_root / "baseline_ready_feature_rows.csv"
    if not feature_path.exists():
        raise FileNotFoundError(f"Missing baseline-ready feature rows: {feature_path}")
    frame = pd.read_csv(feature_path)
    missing = sorted(set(["batch_id", "part_id", *feature_columns]) - set(frame.columns))
    if missing:
        raise ValueError(f"Missing columns for batch risk summary: {missing}")

    rows = []
    for feature in feature_columns:
        numeric = pd.to_numeric(frame[feature], errors="coerce")
        working = frame.loc[:, ["batch_id", "part_id"]].copy()
        working[feature] = numeric
        group_means = (
            working.groupby(["batch_id", "part_id"], dropna=False)[feature]
            .mean()
            .dropna()
        )
        if group_means.empty:
            continue
        min_mean = float(group_means.min())
        max_mean = float(group_means.max())
        overall_mean = float(numeric.mean())
        mean_abs = max(abs(overall_mean), 1e-9)
        relative_range = (max_mean - min_mean) / mean_abs
        sign_flip = bool(min_mean < 0 < max_mean)
        risk_flag = bool(relative_range >= risk_threshold or sign_flip)
        rows.append(
            {
                "feature": feature,
                "batch_part_count": int(group_means.size),
                "overall_mean": overall_mean,
                "min_batch_part_mean": min_mean,
                "max_batch_part_mean": max_mean,
                "relative_mean_range": relative_range,
                "sign_flip_across_batch_part": sign_flip,
                "risk_flag": "batch_confound_risk" if risk_flag else "no_large_batch_mean_shift",
            }
        )
    return pd.DataFrame(rows).sort_values(
        ["risk_flag", "relative_mean_range"], ascending=[True, False]
    )


def ensure_no_formal_metric_terms(report: dict[str, object]) -> None:
    text = json.dumps(report, ensure_ascii=False).lower()
    leaked = [term for term in FORMAL_METRIC_TERMS if term in text]
    if leaked:
        raise ValueError(f"Diagnostics report contains forbidden formal metric terms: {leaked}")


def markdown_table(frame: pd.DataFrame, max_rows: int = 12) -> str:
    if frame.empty:
        return "_No rows_\n"
    visible = frame.head(max_rows)
    columns = visible.columns.tolist()
    lines = [
        "| " + " | ".join(columns) + " |",
        "| " + " | ".join(["---"] * len(columns)) + " |",
    ]
    for row in visible.to_dict("records"):
        lines.append("| " + " | ".join(str(row.get(column, "")) for column in columns) + " |")
    if len(frame) > max_rows:
        lines.append(f"\n_Showing {max_rows} of {len(frame)} rows._")
    return "\n".join(lines) + "\n"


def build_report(
    threshold_sensitivity: pd.DataFrame,
    trajectory: pd.DataFrame,
    timing_error: pd.DataFrame,
    fp_fn_audit: pd.DataFrame,
    batch_risk: pd.DataFrame,
) -> dict[str, object]:
    event_counts = (
        fp_fn_audit.groupby("event_type", dropna=False).size().reset_index(name="count").to_dict("records")
        if not fp_fn_audit.empty
        else []
    )
    timing_counts = (
        timing_error.groupby("timing_class", dropna=False).size().reset_index(name="count").to_dict("records")
        if not timing_error.empty
        else []
    )
    risk_features = batch_risk.loc[batch_risk["risk_flag"].eq("batch_confound_risk")]
    report = {
        "diagnostic_scope": "external_loco_binary_baseline_diagnostics",
        "is_formal_model_performance": False,
        "trained_new_model": False,
        "validation_split_changed": False,
        "probability_thresholds_checked": PROBABILITY_THRESHOLDS,
        "trajectory_rows": int(len(trajectory)),
        "threshold_sensitivity_rows": int(len(threshold_sensitivity)),
        "timing_error_rows": int(len(timing_error)),
        "false_positive_false_negative_rows": int(len(fp_fn_audit)),
        "event_counts": event_counts,
        "timing_class_counts": timing_counts,
        "batch_confound_risk_feature_count": int(len(risk_features)),
        "batch_confound_risk_features": risk_features["feature"].tolist(),
        "interpretation": (
            "Diagnostics explain the exploratory workflow behavior only; current failures should be treated "
            "as evidence of data scarcity and cell-to-cell variability, not formal model performance."
        ),
    }
    ensure_no_formal_metric_terms(report)
    return report


def build_markdown_report(
    report: dict[str, object],
    threshold_sensitivity: pd.DataFrame,
    timing_error: pd.DataFrame,
    fp_fn_audit: pd.DataFrame,
    batch_risk: pd.DataFrame,
) -> str:
    return "\n".join(
        [
            "# External LOCO Binary Diagnostics",
            "",
            "This diagnostic report explains the exploratory baseline behavior. It is not validated model performance.",
            "",
            f"- Thresholds checked: {', '.join(str(value) for value in report['probability_thresholds_checked'])}",
            f"- Timing classes: {report['timing_class_counts']}",
            f"- Batch-risk features: {', '.join(report['batch_confound_risk_features']) or 'None'}",
            "",
            "## Threshold Sensitivity",
            markdown_table(threshold_sensitivity),
            "## Prediction Timing",
            markdown_table(timing_error),
            "## FP/FN Audit",
            markdown_table(fp_fn_audit),
            "## Batch Feature Risk",
            markdown_table(batch_risk),
            "## Interpretation Limits",
            "- No new model was trained.",
            "- No random row split was used.",
            "- RPT and six_minobs20 were not merged into this diagnostic.",
            "- The outputs are workflow diagnostics, not publishable performance claims.",
        ]
    )


def write_outputs(
    output_root: Path,
    threshold_sensitivity: pd.DataFrame,
    trajectory: pd.DataFrame,
    timing_error: pd.DataFrame,
    fp_fn_audit: pd.DataFrame,
    batch_risk: pd.DataFrame,
    report: dict[str, object],
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    threshold_sensitivity.to_csv(output_root / "threshold_sensitivity.csv", index=False)
    trajectory.to_csv(output_root / "per_cell_probability_trajectory.csv", index=False)
    timing_error.to_csv(output_root / "prediction_timing_error.csv", index=False)
    fp_fn_audit.to_csv(output_root / "false_positive_false_negative_audit.csv", index=False)
    batch_risk.to_csv(output_root / "batch_feature_risk_summary.csv", index=False)
    (output_root / "external_loco_diagnostics_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_root / "external_loco_diagnostics_report.md").write_text(
        build_markdown_report(report, threshold_sensitivity, timing_error, fp_fn_audit, batch_risk),
        encoding="utf-8",
    )


def run_external_loco_diagnostics(
    baseline_root: Path = DEFAULT_BASELINE_ROOT,
    baseline_ready_root: Path = DEFAULT_BASELINE_READY_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
) -> dict[str, object]:
    _, _, predictions, _, feature_columns = load_baseline_outputs(baseline_root)
    trajectory = add_eol_context(predictions)
    threshold_sensitivity = build_threshold_sensitivity(predictions, PROBABILITY_THRESHOLDS)
    timing_error = build_prediction_timing_error(trajectory)
    fp_fn_audit = build_false_positive_false_negative_audit(trajectory)
    batch_risk = build_batch_feature_risk_summary(baseline_ready_root, feature_columns)
    report = build_report(threshold_sensitivity, trajectory, timing_error, fp_fn_audit, batch_risk)
    write_outputs(
        output_root=output_root,
        threshold_sensitivity=threshold_sensitivity,
        trajectory=trajectory[
            [
                "label_key",
                "cell_id",
                "cycle_index",
                "predicted_probability",
                "actual_threshold_crossed",
                "predicted_threshold_crossed",
                "true_eol_cycle",
                "first_predicted_positive_cycle",
            ]
        ],
        timing_error=timing_error,
        fp_fn_audit=fp_fn_audit,
        batch_risk=batch_risk,
        report=report,
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Diagnose exploratory external LOCO binary baseline outputs without training a model."
    )
    parser.add_argument("--baseline-root", type=Path, default=DEFAULT_BASELINE_ROOT)
    parser.add_argument("--baseline-ready-root", type=Path, default=DEFAULT_BASELINE_READY_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_external_loco_diagnostics(
        baseline_root=args.baseline_root,
        baseline_ready_root=args.baseline_ready_root,
        output_root=args.output_root,
    )
    print(
        "external LOCO diagnostics complete: "
        f"threshold_rows={report['threshold_sensitivity_rows']}, "
        f"timing_rows={report['timing_error_rows']}, "
        f"batch_risk_features={report['batch_confound_risk_feature_count']}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
