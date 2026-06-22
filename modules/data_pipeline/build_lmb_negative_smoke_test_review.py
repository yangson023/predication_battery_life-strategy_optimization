"""Consolidate negative findings from the LMB tiny smoke test.

The review reads existing smoke-test outputs only. It does not train, refit,
enter RUL prediction, or compute formal performance metrics.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


TARGET_RECOVERY_CELL = "26-0428-009"

FINDING_COLUMNS = ["finding_key", "severity", "evidence", "decision"]
FAILURE_COLUMNS = [
    "fold_id",
    "test_cell",
    "rows",
    "event_cycle",
    "event_score",
    "event_rank_descending",
    "negative_scores_above_event",
    "negative_scores_above_event_fraction",
    "max_negative_score",
    "early_high_negative_count",
    "max_duplicate_score_count",
    "failure_modes",
]
RECOVERY_COLUMNS = [
    "source_folder_name",
    "first_event_cycle",
    "pre_event_cycle_count",
    "baseline_ready_export_candidate",
    "recoverability_status",
    "recovery_decision",
    "required_evidence_before_recovery",
]
REDESIGN_COLUMNS = [
    "redesign_item",
    "recommendation",
    "lmb_rationale",
    "leakage_guard",
    "horizon_separation",
    "allowed_stage",
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


def parse_float(value: object) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return 0.0


def parse_int(value: object) -> int:
    try:
        text = str(value).strip()
        if not text:
            return 0
        return int(float(text))
    except (TypeError, ValueError):
        return 0


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def group_by(rows: list[dict[str, str]], key: str) -> dict[str, list[dict[str, str]]]:
    grouped: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in rows:
        grouped[row.get(key, "")].append(row)
    return dict(grouped)


def summarize_score_failures(predictions: list[dict[str, str]]) -> list[dict[str, Any]]:
    summaries: list[dict[str, Any]] = []
    for fold_id, rows in sorted(group_by(predictions, "fold_id").items()):
        if not rows:
            continue
        event_rows = [row for row in rows if parse_int(row.get("actual_event_next_cycle")) == 1]
        event_row = event_rows[0] if event_rows else {}
        event_score = parse_float(event_row.get("model_score"))
        negative_scores = [parse_float(row.get("model_score")) for row in rows if parse_int(row.get("actual_event_next_cycle")) == 0]
        all_scores = [parse_float(row.get("model_score")) for row in rows]
        negative_above_event = sum(1 for score in negative_scores if score > event_score)
        early_high = sum(
            1
            for row in rows
            if parse_int(row.get("actual_event_next_cycle")) == 0
            and parse_int(row.get("cycle_index")) <= 5
            and parse_float(row.get("model_score")) >= 0.9
        )
        duplicate_count = 0
        if all_scores:
            duplicate_count = max(Counter(f"{score:.8f}" for score in all_scores).values())
        failure_modes = []
        if early_high:
            failure_modes.append("high_early_false_positive")
        if negative_scores and negative_above_event / len(negative_scores) >= 0.5:
            failure_modes.append("event_rank_below_most_negatives")
        if duplicate_count >= max(10, int(len(rows) * 0.25)):
            failure_modes.append("flat_score_plateau")
        if not failure_modes:
            failure_modes.append("weak_or_inconclusive_signal")
        rank = 1 + sum(1 for score in all_scores if score > event_score)
        summaries.append(
            {
                "fold_id": fold_id,
                "test_cell": rows[0].get("test_cell", ""),
                "rows": len(rows),
                "event_cycle": event_row.get("cycle_index", ""),
                "event_score": f"{event_score:.8f}",
                "event_rank_descending": rank,
                "negative_scores_above_event": negative_above_event,
                "negative_scores_above_event_fraction": f"{negative_above_event / max(len(negative_scores), 1):.4f}",
                "max_negative_score": f"{max(negative_scores) if negative_scores else 0.0:.8f}",
                "early_high_negative_count": early_high,
                "max_duplicate_score_count": duplicate_count,
                "failure_modes": ";".join(failure_modes),
            }
        )
    return summaries


def coefficient_instability(diagnostics: list[dict[str, str]]) -> dict[str, Any]:
    signs_by_feature: dict[str, set[str]] = defaultdict(set)
    for row in diagnostics:
        raw = row.get("coefficient_signs", "{}")
        try:
            signs = json.loads(raw)
        except json.JSONDecodeError:
            signs = {}
        for feature, sign in signs.items():
            signs_by_feature[feature].add(sign)
    unstable = {feature: sorted(signs) for feature, signs in signs_by_feature.items() if len(signs) > 1}
    return {"unstable_feature_count": len(unstable), "unstable_features": unstable}


def recoverability_row(label_design_rows: list[dict[str, str]]) -> dict[str, Any]:
    target = next((row for row in label_design_rows if row.get("source_folder_name") == TARGET_RECOVERY_CELL), {})
    first_event = parse_int(target.get("first_event_cycle"))
    pre_event = parse_int(target.get("pre_event_cycle_count"))
    candidate = str(target.get("baseline_ready_export_candidate", "")).strip()
    if first_event <= 2 and pre_event < 10:
        status = "not_recoverable_without_alternate_evidence"
        decision = "do_not_add_to_baseline_ready"
        required = "alternate export review; label threshold review; evidence that event_cycle_2 is a false label event"
    else:
        status = "manual_review_required"
        decision = "hold_until_review"
        required = "verify event timing and pre-event history"
    return {
        "source_folder_name": TARGET_RECOVERY_CELL,
        "first_event_cycle": first_event,
        "pre_event_cycle_count": pre_event,
        "baseline_ready_export_candidate": candidate,
        "recoverability_status": status,
        "recovery_decision": decision,
        "required_evidence_before_recovery": required,
    }


def feature_redesign_plan() -> list[dict[str, Any]]:
    return [
        {
            "redesign_item": "past_only_ce_features",
            "recommendation": "allow only as a separate mechanistic_past_only feature set",
            "lmb_rationale": "Li||Cu Coulombic efficiency is mechanistically relevant to lithium inventory loss and plating/stripping reversibility.",
            "leakage_guard": "leakage guard: exclude current-cycle CE when predicting the next event; compute all CE features from cycles <= t-k",
            "horizon_separation": "start with t_minus_3_predicts_t and compare with t_minus_5_predicts_t in audit only",
            "allowed_stage": "feature_redesign_audit_only_before_baseline_export",
        },
        {
            "redesign_item": "past_only_capacity_trend",
            "recommendation": "allow trend or slope only with horizon separation, not raw same-cycle capacity",
            "lmb_rationale": "Capacity incompleteness may be preceded by drift, but raw same-cycle capacity is label-proximal.",
            "leakage_guard": "leakage guard: block charge_capacity/discharge_capacity at cycle t; permit rolling slopes ending at t-k",
            "horizon_separation": "t_minus_3_or_more_predicts_t",
            "allowed_stage": "feature_redesign_audit_only_before_baseline_export",
        },
        {
            "redesign_item": "polarization_proxy",
            "recommendation": "add voltage hysteresis, median voltage drift, and end-voltage gap if available from past cycles",
            "lmb_rationale": "Polarization growth is closer to LMB degradation mechanisms than record-only summary noise.",
            "leakage_guard": "leakage guard: use past-cycle summaries only and keep event-cycle voltage extrema out of target rows",
            "horizon_separation": "t_minus_3_predicts_t_or_longer",
            "allowed_stage": "feature_builder_revision",
        },
        {
            "redesign_item": "data_expansion",
            "recommendation": "prioritize more Li||Cu cells before another baseline run",
            "lmb_rationale": "Three cells and three positive targets cannot support stable fold behavior.",
            "leakage_guard": "leakage guard: keep canonical export, metadata gate, and trainability gate before any export",
            "horizon_separation": "apply same horizon policy to all new cells",
            "allowed_stage": "data_collection_priority",
        },
    ]


def build_findings(
    failure_rows: list[dict[str, Any]],
    diagnostics: list[dict[str, str]],
    recovery: dict[str, Any],
) -> list[dict[str, Any]]:
    coefficient = coefficient_instability(diagnostics)
    has_early_fp = any(parse_int(row["early_high_negative_count"]) > 0 for row in failure_rows)
    has_low_event_rank = any(parse_float(row["negative_scores_above_event_fraction"]) >= 0.5 for row in failure_rows)
    has_plateau = any("flat_score_plateau" in row["failure_modes"] for row in failure_rows)
    findings = [
        {
            "finding_key": "pipeline_smoke_test_passed_but_model_signal_failed",
            "severity": "high",
            "evidence": "The smoke-test pipeline ran, but score ordering and stability checks fail as predictive evidence.",
            "decision": "pause_tiny_baseline_iteration",
        },
        {
            "finding_key": "strict_v2_smoke_test_failed_as_predictive_signal",
            "severity": "high",
            "evidence": "record-only strict_v2 features are low leakage but do not produce reliable event ranking.",
            "decision": "do_not_interpret_as_model_performance",
        },
        {
            "finding_key": "record_only_feature_set_signal_insufficient",
            "severity": "high",
            "evidence": "Only record voltage/current sample statistics were used; these are too sparse for LMB mechanism tracking.",
            "decision": "redesign_features_before_next_baseline",
        },
        {
            "finding_key": "very_high_risk_small_n",
            "severity": "high",
            "evidence": "Each LOCO fold trains with two positive rows.",
            "decision": "collect_more_licu_cells_before_formal_modeling",
        },
        {
            "finding_key": "recoverability_26_0428_009_blocked",
            "severity": "medium",
            "evidence": f"first_event_cycle={recovery['first_event_cycle']}; pre_event_cycle_count={recovery['pre_event_cycle_count']}",
            "decision": recovery["recovery_decision"],
        },
    ]
    if has_early_fp:
        findings.append(
            {
                "finding_key": "high_early_false_positive_present",
                "severity": "high",
                "evidence": "At least one early negative cycle has a very high model score.",
                "decision": "do_not_continue_current_feature_set",
            }
        )
    if has_low_event_rank:
        findings.append(
            {
                "finding_key": "event_rank_low_against_negatives",
                "severity": "high",
                "evidence": "In at least one fold, most negative rows score above the event row.",
                "decision": "treat_score_ordering_as_failed",
            }
        )
    if has_plateau:
        findings.append(
            {
                "finding_key": "flat_score_plateau_detected",
                "severity": "medium",
                "evidence": "Many rows share identical rounded scores, indicating weak discrimination.",
                "decision": "record_as_feature_signal_failure",
            }
        )
    if coefficient["unstable_feature_count"]:
        findings.append(
            {
                "finding_key": "coefficient_sign_instability",
                "severity": "medium",
                "evidence": json.dumps(coefficient["unstable_features"], ensure_ascii=False),
                "decision": "do_not_use_coefficient_direction_as_physical_interpretation",
            }
        )
    return findings


def write_report(
    output_root: Path,
    findings: list[dict[str, Any]],
    failure_rows: list[dict[str, Any]],
    recovery: dict[str, Any],
    redesign_rows: list[dict[str, Any]],
    manifest: dict[str, Any],
    canonical_feature_columns: list[str],
) -> dict[str, Any]:
    report = {
        "review_only": True,
        "negative_smoke_test_consolidation": True,
        "model_training_allowed": False,
        "model_refit_performed": False,
        "rul_prediction_entered": False,
        "formal_performance_metrics_computed": False,
        "generalization_claimed": False,
        "smoke_test_is_model_performance": False,
        "strict_v2_smoke_test_failed_as_predictive_signal": True,
        "pipeline_smoke_test_passed_but_model_signal_failed": True,
        "current_tiny_baseline_should_pause": True,
        "record_only_feature_set_assessment": "low_leakage_but_signal_insufficient",
        "recoverability_26_0428_009": recovery,
        "feature_redesign_requires": ["past_only", "horizon_separation", "leakage_guard"],
        "minimum_next_data_needs": {
            "licu_cell_target": "at least 8 cells before another baseline attempt",
            "incomplete_event_target": "at least 8 event-bearing cells preferred",
            "natural_or_non_protocol_censored_need": "needed before formal lifetime modeling",
        },
        "manifest_candidate_export_only": manifest.get("candidate_export_only"),
        "canonical_feature_column_count": len(canonical_feature_columns),
        "finding_keys": [row["finding_key"] for row in findings],
    }
    with (output_root / "lmb_negative_smoke_test_review_report.json").open("w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)

    lines = [
        "# LMB Negative Smoke-Test Review",
        "",
        "This review consolidates a negative smoke-test result. It does not train or refit a model and does not report formal model performance.",
        "",
        "## Decision",
        "",
        "- `current_tiny_baseline_should_pause = True`",
        "- `model_training_allowed = False`",
        "- `strict_v2_smoke_test_failed_as_predictive_signal = True`",
        "- `pipeline_smoke_test_passed_but_model_signal_failed = True`",
        "- The strict-v2 record-only feature set is low leakage but signal-insufficient.",
        "",
        "## Why The Smoke Test Failed",
        "",
        "- Event rows are not consistently scored above negative rows.",
        "- High early negative scores indicate early false-positive behavior.",
        "- Flat score plateaus indicate that record-only voltage/current sample summaries are too sparse.",
        "- Coefficient signs are not stable enough for physical interpretation.",
        "- Each fold trains with only two positive rows.",
        "",
        "## 26-0428-009 Recoverability",
        "",
        f"- first_event_cycle: `{recovery['first_event_cycle']}`",
        f"- pre_event_cycle_count: `{recovery['pre_event_cycle_count']}`",
        f"- decision: `{recovery['recovery_decision']}`",
        f"- required evidence: {recovery['required_evidence_before_recovery']}",
        "",
        "## Redesign Direction",
        "",
        "- Restore LMB mechanism features only under a past-only and horizon-separated design.",
        "- Consider past-only CE, capacity trend, and polarization proxies as separate audit feature sets.",
        "- Use a t-k predicts t framing before re-exporting any baseline candidate data.",
        "- Prioritize more Li||Cu cells and non-protocol-censored evidence before formal modeling.",
        "",
        "## Redesign Plan",
        "",
        "| item | recommendation | guard | horizon |",
        "| --- | --- | --- | --- |",
    ]
    for row in redesign_rows:
        lines.append(
            f"| `{row['redesign_item']}` | {row['recommendation']} | {row['leakage_guard']} | {row['horizon_separation']} |"
        )
    lines.extend(["", "## Output Files", ""])
    lines.extend(
        [
            "- `negative_smoke_test_findings.csv`",
            "- `score_failure_mode_summary.csv`",
            "- `recoverability_audit_26_0428_009.csv`",
            "- `lmb_feature_redesign_plan.csv`",
        ]
    )
    (output_root / "lmb_negative_smoke_test_review_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def build_lmb_negative_smoke_test_review(
    smoke_report: Path,
    predictions_path: Path,
    diagnostics_path: Path,
    manifest_path: Path,
    label_design_path: Path,
    licu_features_path: Path,
    label_policy_path: Path,
    output_root: Path,
) -> dict[str, Any]:
    _ = smoke_report.read_text(encoding="utf-8") if smoke_report.exists() else ""
    _ = label_policy_path.read_text(encoding="utf-8") if label_policy_path.exists() else ""
    output_root.mkdir(parents=True, exist_ok=True)
    predictions = read_csv(predictions_path)
    diagnostics = read_csv(diagnostics_path)
    manifest = read_json(manifest_path)
    label_design = read_csv(label_design_path)
    licu_features = read_csv(licu_features_path)
    canonical_feature_columns = list(licu_features[0]) if licu_features else []

    failure_rows = summarize_score_failures(predictions)
    recovery = recoverability_row(label_design)
    redesign_rows = feature_redesign_plan()
    findings = build_findings(failure_rows, diagnostics, recovery)

    write_csv(output_root / "negative_smoke_test_findings.csv", findings, FINDING_COLUMNS)
    write_csv(output_root / "score_failure_mode_summary.csv", failure_rows, FAILURE_COLUMNS)
    write_csv(output_root / "recoverability_audit_26_0428_009.csv", [recovery], RECOVERY_COLUMNS)
    write_csv(output_root / "lmb_feature_redesign_plan.csv", redesign_rows, REDESIGN_COLUMNS)
    return write_report(output_root, findings, failure_rows, recovery, redesign_rows, manifest, canonical_feature_columns)


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--smoke-report", required=True)
    parser.add_argument("--predictions", required=True)
    parser.add_argument("--diagnostics", required=True)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--label-design", required=True)
    parser.add_argument("--licu-features", required=True)
    parser.add_argument("--label-policy", required=True)
    parser.add_argument("--output-root", required=True)
    return parser


def main() -> None:
    args = build_arg_parser().parse_args()
    report = build_lmb_negative_smoke_test_review(
        smoke_report=Path(args.smoke_report),
        predictions_path=Path(args.predictions),
        diagnostics_path=Path(args.diagnostics),
        manifest_path=Path(args.manifest),
        label_design_path=Path(args.label_design),
        licu_features_path=Path(args.licu_features),
        label_policy_path=Path(args.label_policy),
        output_root=Path(args.output_root),
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
