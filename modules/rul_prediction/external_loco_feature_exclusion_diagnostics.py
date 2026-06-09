"""Single-feature exclusion diagnostics for the combined external LOCO baseline."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

if __package__ in {None, ""}:
    sys.path.append(str(Path(__file__).resolve().parents[2]))

from modules.rul_prediction.external_loco_binary_baseline import (
    build_model_frame,
    feature_columns,
    read_input_tables,
    run_loco_binary_baseline,
    validate_inputs,
)
from modules.rul_prediction.external_loco_binary_diagnostics import (
    add_eol_context,
    build_prediction_timing_error,
    build_threshold_sensitivity,
)


DEFAULT_INPUT_ROOT = Path("models/rul_prediction/external_loco_binary_baseline/combined_main_input")
DEFAULT_OUTPUT_ROOT = Path(
    "models/rul_prediction/external_loco_binary_baseline/combined_main/feature_exclusion_diagnostics"
)
CANDIDATE_FEATURES = ["current_a_last", "energy_wh_last", "current_a_mean"]
THRESHOLDS = [0.5, 0.7]
EXPERIMENT_CONTROL = "full_features"


def experiment_name(excluded_feature: str | None) -> str:
    return EXPERIMENT_CONTROL if excluded_feature is None else f"drop_{excluded_feature}"


def build_experiment_specs(candidate_features: list[str]) -> list[dict[str, str | None]]:
    specs = [{"experiment_name": EXPERIMENT_CONTROL, "excluded_feature": None}]
    specs.extend(
        {"experiment_name": experiment_name(feature), "excluded_feature": feature}
        for feature in candidate_features
    )
    return specs


def run_single_experiment(
    model_frame: pd.DataFrame,
    feature_cols: list[str],
    excluded_feature: str | None,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if excluded_feature is None:
        columns = feature_cols
    else:
        if excluded_feature not in feature_cols:
            raise ValueError(f"Cannot exclude missing feature: {excluded_feature}")
        columns = [column for column in feature_cols if column != excluded_feature]
    fold_summary, predictions, fold_design = run_loco_binary_baseline(model_frame, columns)
    trajectory = add_eol_context(predictions)
    timing = build_prediction_timing_error(trajectory)
    threshold_sensitivity = build_threshold_sensitivity(predictions, THRESHOLDS)
    return fold_summary, predictions, fold_design, timing, threshold_sensitivity


def add_experiment_columns(
    frame: pd.DataFrame,
    name: str,
    excluded_feature: str | None,
) -> pd.DataFrame:
    output = frame.copy()
    output.insert(0, "experiment_name", name)
    output.insert(1, "excluded_feature", excluded_feature or "")
    return output


def compare_to_baseline(fold_summary: pd.DataFrame, timing: pd.DataFrame) -> pd.DataFrame:
    baseline_folds = fold_summary.loc[
        fold_summary["experiment_name"].eq(EXPERIMENT_CONTROL)
    ].copy()
    baseline_timing = timing.loc[timing["experiment_name"].eq(EXPERIMENT_CONTROL)].copy()
    comparisons = []

    baseline = baseline_folds.merge(
        baseline_timing[
            [
                "label_key",
                "cell_id",
                "prediction_timing_error_cycles",
            ]
        ],
        left_on=["label_key", "test_cell_id"],
        right_on=["label_key", "cell_id"],
        how="left",
    )
    baseline = baseline.drop(columns=["cell_id"])

    for excluded_feature in sorted(
        value for value in fold_summary["excluded_feature"].dropna().unique().tolist() if value
    ):
        ablation_folds = fold_summary.loc[fold_summary["excluded_feature"].eq(excluded_feature)].copy()
        ablation_timing = timing.loc[timing["excluded_feature"].eq(excluded_feature)].copy()
        ablation = ablation_folds.merge(
            ablation_timing[
                [
                    "label_key",
                    "cell_id",
                    "prediction_timing_error_cycles",
                ]
            ],
            left_on=["label_key", "test_cell_id"],
            right_on=["label_key", "cell_id"],
            how="left",
        ).drop(columns=["cell_id"])

        merged = baseline.merge(
            ablation,
            on=["label_key", "test_cell_id"],
            suffixes=("_baseline", "_ablation"),
            how="inner",
        )
        for row in merged.to_dict("records"):
            baseline_error = row.get("prediction_timing_error_cycles_baseline")
            ablation_error = row.get("prediction_timing_error_cycles_ablation")
            baseline_abs = abs(float(baseline_error)) if not pd.isna(baseline_error) else np.inf
            ablation_abs = abs(float(ablation_error)) if not pd.isna(ablation_error) else np.inf
            baseline_fp = int(row["false_positive_rows_baseline"])
            ablation_fp = int(row["false_positive_rows_ablation"])
            baseline_fn = int(row["false_negative_rows_baseline"])
            ablation_fn = int(row["false_negative_rows_ablation"])
            comparisons.append(
                {
                    "label_key": row["label_key"],
                    "cell_id": row["test_cell_id"],
                    "excluded_feature": excluded_feature,
                    "baseline_first_predicted_positive_cycle": row.get(
                        "first_predicted_positive_cycle_baseline"
                    ),
                    "ablation_first_predicted_positive_cycle": row.get(
                        "first_predicted_positive_cycle_ablation"
                    ),
                    "baseline_timing_error": baseline_error,
                    "ablation_timing_error": ablation_error,
                    "baseline_false_positive_rows": baseline_fp,
                    "ablation_false_positive_rows": ablation_fp,
                    "baseline_false_negative_rows": baseline_fn,
                    "ablation_false_negative_rows": ablation_fn,
                    "timing_error_improved": bool(ablation_abs < baseline_abs),
                    "false_positive_reduced": bool(baseline_fp - ablation_fp >= 1),
                    "false_negative_increased": bool(ablation_fn > baseline_fn),
                }
            )
    return pd.DataFrame(comparisons)


def classify_feature_effect(comparison: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for excluded_feature, group in comparison.groupby("excluded_feature", dropna=False):
        fp_reduced_folds = int(group["false_positive_reduced"].sum())
        timing_improved_folds = int(group["timing_error_improved"].sum())
        fn_increased_folds = int(group["false_negative_increased"].sum())
        changed_folds = int(
            (
                group["false_positive_reduced"]
                | group["timing_error_improved"]
                | group["false_negative_increased"]
            ).sum()
        )
        if fn_increased_folds > 0:
            decision = "exclusion_harms_detection"
        elif fp_reduced_folds >= 3 or timing_improved_folds >= 3:
            decision = "possible_confound_feature"
        elif changed_folds == 1:
            decision = "inconclusive_single_fold_change"
        else:
            decision = "no_clear_benefit"
        rows.append(
            {
                "excluded_feature": excluded_feature,
                "folds": int(len(group)),
                "false_positive_reduced_folds": fp_reduced_folds,
                "timing_error_abs_improved_folds": timing_improved_folds,
                "false_negative_increased_folds": fn_increased_folds,
                "changed_folds": changed_folds,
                "diagnostic_decision": decision,
            }
        )
    return pd.DataFrame(rows)


def build_report(
    fold_summary: pd.DataFrame,
    comparison: pd.DataFrame,
    decisions: pd.DataFrame,
    feature_cols: list[str],
) -> dict[str, object]:
    possible = decisions.loc[
        decisions["diagnostic_decision"].eq("possible_confound_feature"),
        "excluded_feature",
    ].tolist()
    harmful = decisions.loc[
        decisions["diagnostic_decision"].eq("exclusion_harms_detection"),
        "excluded_feature",
    ].tolist()
    report = {
        "diagnostic_scope": "combined_main_single_feature_exclusion",
        "validated_performance_claim": False,
        "trained_new_model_family": False,
        "random_row_split_used": False,
        "input_dataset": "combined_main",
        "experiments": sorted(fold_summary["experiment_name"].unique().tolist()),
        "candidate_features": CANDIDATE_FEATURES,
        "feature_columns_before_exclusion": feature_cols,
        "thresholds_checked": THRESHOLDS,
        "fold_count_per_experiment": int(
            fold_summary.groupby("experiment_name").size().max()
        )
        if not fold_summary.empty
        else 0,
        "possible_confound_features": possible,
        "harmful_exclusions": harmful,
        "feature_decisions": decisions.to_dict("records"),
        "stronger_baseline_allowed": False,
        "interpretation": (
            "This diagnostic only compares single-feature exclusions against the same "
            "exploratory logistic LOCO workflow. It does not establish validated predictive ability."
        ),
    }
    return report


def markdown_table(frame: pd.DataFrame, max_rows: int = 20) -> str:
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


def build_markdown_report(
    decisions: pd.DataFrame,
    comparison: pd.DataFrame,
    report: dict[str, object],
) -> str:
    return "\n".join(
        [
            "# Combined Main Feature Exclusion Diagnostics",
            "",
            "This report compares single-feature exclusions in the same exploratory logistic LOCO workflow.",
            "It is not a validated performance claim.",
            "",
            f"- Experiments: {', '.join(report['experiments'])}",
            f"- Thresholds checked: {', '.join(str(value) for value in THRESHOLDS)}",
            f"- Stronger baseline allowed: {report['stronger_baseline_allowed']}",
            "",
            "## Feature Decisions",
            markdown_table(decisions),
            "## Fold-Level Comparison",
            markdown_table(comparison),
            "## Interpretation Limits",
            "- Each ablation removes one feature only.",
            "- Judgments are based on per-fold timing and hit/miss behavior.",
            "- These outputs do not justify Random Forest, XGBoost, SVM, MLP, or RUL regression.",
        ]
    )


def write_outputs(
    output_root: Path,
    fold_summary: pd.DataFrame,
    timing: pd.DataFrame,
    threshold_sensitivity: pd.DataFrame,
    comparison: pd.DataFrame,
    decisions: pd.DataFrame,
    report: dict[str, object],
) -> None:
    output_root.mkdir(parents=True, exist_ok=True)
    fold_summary.to_csv(output_root / "feature_exclusion_fold_summary.csv", index=False)
    timing.to_csv(output_root / "feature_exclusion_timing_error.csv", index=False)
    threshold_sensitivity.to_csv(
        output_root / "feature_exclusion_threshold_sensitivity.csv", index=False
    )
    comparison.to_csv(output_root / "feature_exclusion_comparison.csv", index=False)
    decisions.to_csv(output_root / "feature_exclusion_decisions.csv", index=False)
    (output_root / "feature_exclusion_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (output_root / "feature_exclusion_report.md").write_text(
        build_markdown_report(decisions, comparison, report),
        encoding="utf-8",
    )


def run_feature_exclusion_diagnostics(
    input_root: Path = DEFAULT_INPUT_ROOT,
    output_root: Path = DEFAULT_OUTPUT_ROOT,
    candidate_features: list[str] | None = None,
) -> dict[str, object]:
    candidate_features = candidate_features or CANDIDATE_FEATURES
    features, targets, labels, _ = read_input_tables(input_root)
    validate_inputs(features, targets, labels)
    feature_cols = feature_columns(features)
    model_frame = build_model_frame(features, targets)
    missing_candidates = sorted(set(candidate_features) - set(feature_cols))
    if missing_candidates:
        raise ValueError(f"Candidate features missing from input: {missing_candidates}")

    fold_tables = []
    timing_tables = []
    threshold_tables = []
    for spec in build_experiment_specs(candidate_features):
        name = str(spec["experiment_name"])
        excluded = spec["excluded_feature"]
        fold_summary, _, _, timing, sensitivity = run_single_experiment(
            model_frame,
            feature_cols,
            str(excluded) if excluded else None,
        )
        fold_tables.append(add_experiment_columns(fold_summary, name, str(excluded) if excluded else None))
        timing_tables.append(add_experiment_columns(timing, name, str(excluded) if excluded else None))
        threshold_tables.append(
            add_experiment_columns(sensitivity, name, str(excluded) if excluded else None)
        )

    fold_summary_all = pd.concat(fold_tables, ignore_index=True)
    timing_all = pd.concat(timing_tables, ignore_index=True)
    threshold_all = pd.concat(threshold_tables, ignore_index=True)
    comparison = compare_to_baseline(fold_summary_all, timing_all)
    decisions = classify_feature_effect(comparison)
    report = build_report(fold_summary_all, comparison, decisions, feature_cols)
    write_outputs(
        output_root,
        fold_summary_all,
        timing_all,
        threshold_all,
        comparison,
        decisions,
        report,
    )
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run single-feature exclusion diagnostics for combined_main LOCO baseline."
    )
    parser.add_argument("--input-root", type=Path, default=DEFAULT_INPUT_ROOT)
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument(
        "--candidate-feature",
        action="append",
        default=[],
        help="Optional candidate feature to exclude. Defaults to current_a_last, energy_wh_last, current_a_mean.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = run_feature_exclusion_diagnostics(
        input_root=args.input_root,
        output_root=args.output_root,
        candidate_features=args.candidate_feature or CANDIDATE_FEATURES,
    )
    print(
        "feature exclusion diagnostics complete: "
        f"experiments={len(report['experiments'])}, "
        f"possible_confound={report['possible_confound_features']}, "
        f"harmful={report['harmful_exclusions']}"
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise
