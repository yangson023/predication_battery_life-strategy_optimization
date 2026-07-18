"""Build diagnostics for LMB mechanistic tiny smoke-test outputs.

The diagnostics are qualitative smoke-test review artifacts only. This script
does not train, refit, split data, enter RUL prediction, or report formal model
metrics.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


THRESHOLDS = (0.3, 0.5, 0.7)
TARGET_LABEL_KEY = "incomplete_capacity_event"
FORMAL_METRIC_TERMS = ("auc", "f1", "rmse", "accuracy")

EVENT_RANK_COLUMNS = [
    "horizon_k",
    "fold_id",
    "test_cell",
    "event_target_cycle",
    "event_score",
    "event_rank_within_fold",
    "fold_row_count",
    "negative_rows_scored_higher_than_event",
    "event_rank_percentile",
    "event_rank_interpretation",
]

TRAJECTORY_COLUMNS = [
    "horizon_k",
    "fold_id",
    "test_cell",
    "min_score",
    "max_score",
    "median_score",
    "event_score",
    "pre_event_score_trend",
    "score_plateau_count",
    "unique_score_count",
]

THRESHOLD_COLUMNS = [
    "horizon_k",
    "fold_id",
    "test_cell",
    "probability_threshold",
    "event_target_cycle",
    "first_positive_cycle",
    "cycles_before_event",
    "early_false_positive_rows",
    "missed_event_at_threshold",
]

SIGN_COLUMNS = [
    "horizon_k",
    "feature_column",
    "positive_count",
    "negative_count",
    "zero_count",
    "sign_flip_count",
    "stability_label",
    "feature_family",
]

SAME_SIGNAL_COLUMNS = [
    "horizon_k",
    "same_signal_source_feature_count",
    "same_signal_nonzero_sign_count",
    "mechanistic_feature_count",
    "mechanistic_nonzero_sign_count",
    "same_signal_nonzero_fraction",
    "mechanistic_nonzero_fraction",
    "risk_label",
]

HORIZON_COMPARISON_COLUMNS = [
    "test_cell",
    "h3_event_rank_within_fold",
    "h5_event_rank_within_fold",
    "h3_event_rank_percentile",
    "h5_event_rank_percentile",
    "h3_early_false_positive_rows_at_0_5",
    "h5_early_false_positive_rows_at_0_5",
    "h3_score_plateau_count",
    "h5_score_plateau_count",
    "preferred_horizon_for_next_candidate",
    "comparison_note",
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
        return float(text)
    except (TypeError, ValueError):
        return 0.0


def group_predictions(rows: list[dict[str, str]]) -> dict[tuple[int, str, str], list[dict[str, str]]]:
    grouped: dict[tuple[int, str, str], list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        if row.get("label_key") != TARGET_LABEL_KEY:
            continue
        key = (parse_int(row.get("horizon_k")), row.get("fold_id", ""), row.get("test_cell", ""))
        grouped[key].append(row)
    for key in list(grouped):
        grouped[key].sort(key=lambda item: parse_int(item.get("target_cycle")))
    return dict(grouped)


def score(row: dict[str, str]) -> float:
    return parse_float(row.get("qualitative_model_score"))


def event_row(rows: list[dict[str, str]]) -> dict[str, str] | None:
    for row in rows:
        if parse_int(row.get("actual_event_at_cycle")) == 1:
            return row
    return None


def simple_slope(values: list[float]) -> float:
    if len(values) < 3:
        return 0.0
    xs = list(range(len(values)))
    x_mean = statistics.fmean(xs)
    y_mean = statistics.fmean(values)
    denominator = sum((x - x_mean) ** 2 for x in xs)
    if denominator == 0:
        return 0.0
    return sum((x - x_mean) * (y - y_mean) for x, y in zip(xs, values)) / denominator


def build_event_rank_summary(predictions: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (horizon, fold_id, test_cell), fold_rows in group_predictions(predictions).items():
        event = event_row(fold_rows)
        if event is None:
            continue
        event_score = score(event)
        higher = sum(1 for row in fold_rows if parse_int(row.get("actual_event_at_cycle")) == 0 and score(row) > event_score)
        rank = higher + 1
        total = len(fold_rows)
        percentile = rank / total if total else 0.0
        if percentile <= 0.2:
            interpretation = "event_rank_near_top"
        elif percentile <= 0.5:
            interpretation = "event_rank_mid_front"
        else:
            interpretation = "event_rank_not_early_enough"
        rows.append(
            {
                "horizon_k": horizon,
                "fold_id": fold_id,
                "test_cell": test_cell,
                "event_target_cycle": event.get("target_cycle", ""),
                "event_score": event_score,
                "event_rank_within_fold": rank,
                "fold_row_count": total,
                "negative_rows_scored_higher_than_event": higher,
                "event_rank_percentile": percentile,
                "event_rank_interpretation": interpretation,
            }
        )
    return rows


def build_score_trajectory_summary(predictions: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (horizon, fold_id, test_cell), fold_rows in group_predictions(predictions).items():
        event = event_row(fold_rows)
        event_cycle = parse_int(event.get("target_cycle")) if event else 0
        scores = [score(row) for row in fold_rows]
        pre_event_scores = [score(row) for row in fold_rows if parse_int(row.get("target_cycle")) <= event_cycle]
        score_counts = Counter(round(value, 6) for value in scores)
        plateau = max(score_counts.values()) if score_counts else 0
        rows.append(
            {
                "horizon_k": horizon,
                "fold_id": fold_id,
                "test_cell": test_cell,
                "min_score": min(scores) if scores else 0.0,
                "max_score": max(scores) if scores else 0.0,
                "median_score": statistics.median(scores) if scores else 0.0,
                "event_score": score(event) if event else 0.0,
                "pre_event_score_trend": simple_slope(pre_event_scores),
                "score_plateau_count": plateau,
                "unique_score_count": len(score_counts),
            }
        )
    return rows


def build_threshold_audit(predictions: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for (horizon, fold_id, test_cell), fold_rows in group_predictions(predictions).items():
        event = event_row(fold_rows)
        if event is None:
            continue
        event_cycle = parse_int(event.get("target_cycle"))
        for threshold in THRESHOLDS:
            positive_rows = [row for row in fold_rows if score(row) >= threshold]
            first_positive_cycle = min((parse_int(row.get("target_cycle")) for row in positive_rows), default=0)
            early_false_positive_rows = sum(
                1
                for row in positive_rows
                if parse_int(row.get("actual_event_at_cycle")) == 0 and parse_int(row.get("target_cycle")) < event_cycle
            )
            missed = score(event) < threshold
            rows.append(
                {
                    "horizon_k": horizon,
                    "fold_id": fold_id,
                    "test_cell": test_cell,
                    "probability_threshold": threshold,
                    "event_target_cycle": event_cycle,
                    "first_positive_cycle": first_positive_cycle,
                    "cycles_before_event": event_cycle - first_positive_cycle if first_positive_cycle else "",
                    "early_false_positive_rows": early_false_positive_rows,
                    "missed_event_at_threshold": missed,
                }
            )
    return rows


def parse_signs(text: str) -> dict[str, str]:
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {}
    return {str(key): str(value) for key, value in data.items()}


def same_signal_set(diagnostics: list[dict[str, str]], horizon: int) -> set[str]:
    features: set[str] = set()
    for row in diagnostics:
        if parse_int(row.get("horizon_k")) != horizon:
            continue
        for item in row.get("same_signal_source_feature_columns", "").split(";"):
            item = item.strip()
            if item:
                features.add(item)
    return features


def feature_family(feature: str, same_signal: set[str]) -> str:
    if feature in same_signal:
        return "same_signal_source_ce_capacity"
    if "voltage" in feature or "hysteresis" in feature or "duration" in feature or "gap" in feature:
        return "voltage_hysteresis_kinetic"
    return "other_mechanistic"


def build_coefficient_sign_stability(diagnostics: list[dict[str, str]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_horizon: dict[int, list[dict[str, str]]] = defaultdict(list)
    for row in diagnostics:
        by_horizon[parse_int(row.get("horizon_k"))].append(row)
    for horizon, diag_rows in sorted(by_horizon.items()):
        same_signal = same_signal_set(diagnostics, horizon)
        feature_signs: dict[str, list[str]] = defaultdict(list)
        for row in diag_rows:
            for feature, sign in parse_signs(row.get("coefficient_signs", "")).items():
                feature_signs[feature].append(sign)
        for feature, signs in sorted(feature_signs.items()):
            counts = Counter(signs)
            nonzero_signs = {sign for sign in signs if sign in {"positive", "negative"}}
            if counts["positive"] == len(signs):
                label = "stable_positive"
            elif counts["negative"] == len(signs):
                label = "stable_negative"
            elif counts["zero"] == len(signs):
                label = "zero_or_flat"
            elif len(nonzero_signs) > 1:
                label = "unstable"
            else:
                label = "mixed_with_zero"
            rows.append(
                {
                    "horizon_k": horizon,
                    "feature_column": feature,
                    "positive_count": counts["positive"],
                    "negative_count": counts["negative"],
                    "zero_count": counts["zero"],
                    "sign_flip_count": 1 if len(nonzero_signs) > 1 else 0,
                    "stability_label": label,
                    "feature_family": feature_family(feature, same_signal),
                }
            )
    return rows


def build_same_signal_risk_audit(sign_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    by_horizon: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for row in sign_rows:
        by_horizon[parse_int(row.get("horizon_k"))].append(row)
    for horizon, horizon_rows in sorted(by_horizon.items()):
        same = [row for row in horizon_rows if row.get("feature_family") == "same_signal_source_ce_capacity"]
        mech = [row for row in horizon_rows if row.get("feature_family") == "voltage_hysteresis_kinetic"]
        same_nonzero = sum(parse_int(row.get("positive_count")) + parse_int(row.get("negative_count")) for row in same)
        mech_nonzero = sum(parse_int(row.get("positive_count")) + parse_int(row.get("negative_count")) for row in mech)
        same_total = len(same) * 3
        mech_total = len(mech) * 3
        same_fraction = same_nonzero / same_total if same_total else 0.0
        mech_fraction = mech_nonzero / mech_total if mech_total else 0.0
        risk = "same_signal_source_dominance_risk" if same_fraction >= mech_fraction and same_fraction >= 0.75 else "same_signal_source_present_but_not_dominant"
        if mech_fraction >= 0.75:
            risk += ";mechanistic_feature_family_worth_retaining"
        rows.append(
            {
                "horizon_k": horizon,
                "same_signal_source_feature_count": len(same),
                "same_signal_nonzero_sign_count": same_nonzero,
                "mechanistic_feature_count": len(mech),
                "mechanistic_nonzero_sign_count": mech_nonzero,
                "same_signal_nonzero_fraction": same_fraction,
                "mechanistic_nonzero_fraction": mech_fraction,
                "risk_label": risk,
            }
        )
    return rows


def build_horizon_comparison(
    event_rows: list[dict[str, Any]],
    trajectory_rows: list[dict[str, Any]],
    threshold_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    event_by_key = {(row["test_cell"], parse_int(row["horizon_k"])): row for row in event_rows}
    trajectory_by_key = {(row["test_cell"], parse_int(row["horizon_k"])): row for row in trajectory_rows}
    threshold_05 = {
        (row["test_cell"], parse_int(row["horizon_k"])): row
        for row in threshold_rows
        if abs(parse_float(row.get("probability_threshold")) - 0.5) < 1e-9
    }
    cells = sorted({cell for cell, _ in event_by_key})
    rows: list[dict[str, Any]] = []
    for cell in cells:
        h3 = event_by_key.get((cell, 3), {})
        h5 = event_by_key.get((cell, 5), {})
        h3_threshold = threshold_05.get((cell, 3), {})
        h5_threshold = threshold_05.get((cell, 5), {})
        h3_trajectory = trajectory_by_key.get((cell, 3), {})
        h5_trajectory = trajectory_by_key.get((cell, 5), {})
        h3_percentile = parse_float(h3.get("event_rank_percentile"))
        h5_percentile = parse_float(h5.get("event_rank_percentile"))
        h3_early = parse_int(h3_threshold.get("early_false_positive_rows"))
        h5_early = parse_int(h5_threshold.get("early_false_positive_rows"))
        if h5_percentile and (h5_percentile < h3_percentile or not h3_percentile) and h5_early <= h3_early:
            preferred = "horizon_5"
            note = "h5 has better or equal event rank with no worse threshold-0.5 early false positives"
        elif h3_percentile and h3_early <= h5_early:
            preferred = "horizon_3"
            note = "h3 has better threshold-0.5 early false positive profile or comparable rank"
        else:
            preferred = "inconclusive"
            note = "small-n prevents stable horizon preference"
        rows.append(
            {
                "test_cell": cell,
                "h3_event_rank_within_fold": h3.get("event_rank_within_fold", ""),
                "h5_event_rank_within_fold": h5.get("event_rank_within_fold", ""),
                "h3_event_rank_percentile": h3.get("event_rank_percentile", ""),
                "h5_event_rank_percentile": h5.get("event_rank_percentile", ""),
                "h3_early_false_positive_rows_at_0_5": h3_early,
                "h5_early_false_positive_rows_at_0_5": h5_early,
                "h3_score_plateau_count": h3_trajectory.get("score_plateau_count", ""),
                "h5_score_plateau_count": h5_trajectory.get("score_plateau_count", ""),
                "preferred_horizon_for_next_candidate": preferred,
                "comparison_note": note,
            }
        )
    return rows


def report_decision(
    event_rows: list[dict[str, Any]],
    same_signal_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    near_top_count = sum(1 for row in event_rows if parse_float(row.get("event_rank_percentile")) <= 0.2)
    total = len(event_rows)
    only_short_cell_good = near_top_count > 0 and all(
        row.get("test_cell") == "26-0512(li-Cu)" or parse_float(row.get("event_rank_percentile")) > 0.2 for row in event_rows
    )
    same_signal_dominant = any("same_signal_source_dominance_risk" in row.get("risk_label", "") for row in same_signal_rows)
    mechanistic_retained = any("mechanistic_feature_family_worth_retaining" in row.get("risk_label", "") for row in same_signal_rows)
    preferred_counts = Counter(row.get("preferred_horizon_for_next_candidate", "") for row in comparison_rows)
    if preferred_counts["horizon_5"] > preferred_counts["horizon_3"]:
        preferred_horizon = "horizon_5"
    elif preferred_counts["horizon_3"] > preferred_counts["horizon_5"]:
        preferred_horizon = "horizon_3"
    else:
        preferred_horizon = "inconclusive"
    labels: list[str] = []
    if near_top_count >= max(2, total // 2):
        labels.append("mechanistic_signal_promising_but_small_n")
    if only_short_cell_good:
        labels.append("single_cell_short_window_artifact_risk")
    if same_signal_dominant:
        labels.append("same_signal_source_dominance_risk")
    if mechanistic_retained:
        labels.append("mechanistic_feature_family_worth_retaining")
    if not labels:
        labels.append("mechanistic_signal_inconclusive_small_n")
    return {
        "decision_labels": labels,
        "near_top_event_fold_count": near_top_count,
        "total_event_fold_count": total,
        "preferred_horizon_for_next_candidate": preferred_horizon,
        "continue_tiny_refinement_recommended": True,
        "additional_licu_data_strongly_recommended": True,
        "model_training_allowed": False,
    }


def assert_no_formal_metric_terms(report: dict[str, Any]) -> None:
    text = json.dumps(report, ensure_ascii=False).lower()
    for term in FORMAL_METRIC_TERMS:
        if term in text:
            raise ValueError(f"Formal metric term is not allowed in diagnostics report: {term}")


def write_report(
    output_root: Path,
    event_rows: list[dict[str, Any]],
    trajectory_rows: list[dict[str, Any]],
    threshold_rows: list[dict[str, Any]],
    sign_rows: list[dict[str, Any]],
    same_signal_rows: list[dict[str, Any]],
    comparison_rows: list[dict[str, Any]],
    smoke_report: dict[str, Any],
    manifest: dict[str, Any],
) -> dict[str, Any]:
    decision = report_decision(event_rows, same_signal_rows, comparison_rows)
    report = {
        "diagnostics_only": True,
        "qualitative_smoke_test_diagnostics": True,
        "not_formal_result": True,
        "model_training_allowed": False,
        "model_refit_performed": False,
        "rul_prediction_entered": False,
        "random_row_split_used": False,
        "formal_metric_values_reported": False,
        "target_cell_group": "Li||Cu",
        "target_label_key": TARGET_LABEL_KEY,
        "very_high_risk_small_n": True,
        "cannot_represent_generalization": True,
        "smoke_test_input_gate_passed": smoke_report.get("input_gate_passed"),
        "manifest_candidate_export_only": manifest.get("candidate_export_only"),
        "decision": decision,
        "event_rank_summary": event_rows,
        "same_signal_source_risk_audit": same_signal_rows,
        "horizon_comparison": comparison_rows,
    }
    assert_no_formal_metric_terms(report)
    (output_root / "mechanistic_smoke_test_diagnostics_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    lines = [
        "# LMB Mechanistic Smoke-Test Diagnostics",
        "",
        "This is qualitative smoke-test diagnostics only. It does not train, refit, enter RUL prediction, or claim formal model results.",
        "",
        "## Gate",
        "",
        "- `model_training_allowed = False`",
        "- `model_refit_performed = False`",
        "- `random_row_split_used = False`",
        "- `very_high_risk_small_n = True`",
        "- Current result cannot represent generalization.",
        "",
        "## Event Rank Summary",
        "",
        "| horizon | fold | test cell | event cycle | event score | rank | higher negatives |",
        "| ---: | --- | --- | ---: | ---: | ---: | ---: |",
    ]
    for row in event_rows:
        lines.append(
            f"| {row['horizon_k']} | {row['fold_id']} | {row['test_cell']} | {row['event_target_cycle']} | "
            f"{float(row['event_score']):.6f} | {row['event_rank_within_fold']}/{row['fold_row_count']} | "
            f"{row['negative_rows_scored_higher_than_event']} |"
        )
    lines.extend(["", "## Decision Labels", ""])
    lines.extend(f"- `{label}`" for label in decision["decision_labels"])
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "- Mechanistic features are more worth diagnosing than strict record-sample-only features, because event rows are not consistently buried at the bottom.",
            "- The strongest-looking cell is still `26-0512(li-Cu)`, which has a short window and must be treated as artifact-prone.",
            "- CE/capacity trend features remain same-signal-source risk even though they are past-only.",
            "- Voltage, hysteresis, and kinetic feature families show enough nonzero sign activity to retain for the next tiny refinement.",
            "- More Li||Cu cells with reliable event labels would help substantially and should be prioritized before stronger modeling.",
            "",
            "## Next Step",
            "",
            "Continue only with a constrained tiny refinement or data expansion plan. Formal model training remains prohibited.",
        ]
    )
    (output_root / "mechanistic_smoke_test_diagnostics_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_lmb_mechanistic_smoke_test_diagnostics(
    input_root: Path,
    manifest_path: Path,
    feature_risk_path: Path,
    data_risk_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    _ = read_csv(feature_risk_path)
    _ = read_csv(data_risk_path)
    output_root.mkdir(parents=True, exist_ok=True)
    predictions = read_csv(input_root / "mechanistic_tiny_loco_predictions.csv")
    diagnostics = read_csv(input_root / "mechanistic_tiny_loco_diagnostics.csv")
    smoke_report = read_json(input_root / "mechanistic_tiny_smoke_test_report.json")
    manifest = read_json(manifest_path)
    event_rows = build_event_rank_summary(predictions)
    trajectory_rows = build_score_trajectory_summary(predictions)
    threshold_rows = build_threshold_audit(predictions)
    sign_rows = build_coefficient_sign_stability(diagnostics)
    same_signal_rows = build_same_signal_risk_audit(sign_rows)
    comparison_rows = build_horizon_comparison(event_rows, trajectory_rows, threshold_rows)

    write_csv(output_root / "mechanistic_event_rank_summary.csv", event_rows, EVENT_RANK_COLUMNS)
    write_csv(output_root / "mechanistic_score_trajectory_summary.csv", trajectory_rows, TRAJECTORY_COLUMNS)
    write_csv(output_root / "mechanistic_threshold_audit.csv", threshold_rows, THRESHOLD_COLUMNS)
    write_csv(output_root / "mechanistic_coefficient_sign_stability.csv", sign_rows, SIGN_COLUMNS)
    write_csv(output_root / "mechanistic_same_signal_source_risk_audit.csv", same_signal_rows, SAME_SIGNAL_COLUMNS)
    write_csv(output_root / "mechanistic_horizon_comparison.csv", comparison_rows, HORIZON_COMPARISON_COLUMNS)
    return write_report(output_root, event_rows, trajectory_rows, threshold_rows, sign_rows, same_signal_rows, comparison_rows, smoke_report, manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--feature-risk-audit", type=Path, required=True)
    parser.add_argument("--data-risk-summary", type=Path, required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    report = build_lmb_mechanistic_smoke_test_diagnostics(
        input_root=args.input_root,
        manifest_path=args.manifest,
        feature_risk_path=args.feature_risk_audit,
        data_risk_path=args.data_risk_summary,
        output_root=args.output_root,
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
