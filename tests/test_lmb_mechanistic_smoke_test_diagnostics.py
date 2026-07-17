import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.build_lmb_mechanistic_smoke_test_diagnostics import (
    build_event_rank_summary,
    build_lmb_mechanistic_smoke_test_diagnostics,
    build_threshold_audit,
    build_coefficient_sign_stability,
    build_same_signal_risk_audit,
)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_fixture(root: Path) -> tuple[Path, Path, Path, Path]:
    input_root = root / "input"
    input_root.mkdir(parents=True, exist_ok=True)
    predictions = []
    diagnostics = []
    for horizon in [3, 5]:
        for fold_index, cell in enumerate(["cell-a", "cell-b"], start=1):
            fold_id = f"h{horizon}_LOCO_{fold_index}"
            scores = [0.2, 0.8, 0.4, 0.7]
            for index, score in enumerate(scores, start=1):
                predictions.append(
                    {
                        "horizon_k": horizon,
                        "fold_id": fold_id,
                        "test_cell": cell,
                        "row_id": f"{cell}__target_cycle_{index}__h{horizon}",
                        "target_cycle": index,
                        "label_key": "incomplete_capacity_event",
                        "actual_event_at_cycle": 1 if index == 4 else 0,
                        "qualitative_model_score": score,
                        "raw_score": score,
                        "score_is_qualitative_only": True,
                        "smoke_test_only": True,
                        "not_formal_result": True,
                    }
                )
            sign_payload = {
                "ce_rolling_mean_window_past_5": "positive" if fold_index == 1 else "negative",
                "charge_capacity_mah_trend_past_5": "positive",
                "voltage_hysteresis_v_trend_past_5": "positive",
                "charge_step_duration_s_lag_k": "negative",
            }
            diagnostics.append(
                {
                    "horizon_k": horizon,
                    "fold_id": fold_id,
                    "test_cell": cell,
                    "train_cells": "other",
                    "train_rows": 8,
                    "test_rows": 4,
                    "train_positive_count": 2,
                    "test_positive_count": 1,
                    "train_negative_count": 6,
                    "test_negative_count": 3,
                    "train_positive_risk": "very_high_risk_small_n",
                    "class_imbalance_status": "very_high_risk_small_n",
                    "fit_status": "fit_for_smoke_test_only",
                    "fit_note": "test",
                    "coefficient_signs": json.dumps(sign_payload),
                    "same_signal_source_feature_columns": "ce_rolling_mean_window_past_5;charge_capacity_mah_trend_past_5",
                    "model_family": "logistic_regression_only",
                    "split_type": "leave_one_cell_out",
                    "random_row_split_used": False,
                    "model_checkpoint_saved": False,
                    "formal_result_claimed": False,
                }
            )
    write_csv(
        input_root / "mechanistic_tiny_loco_predictions.csv",
        predictions,
        [
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
        ],
    )
    write_csv(
        input_root / "mechanistic_tiny_loco_diagnostics.csv",
        diagnostics,
        [
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
        ],
    )
    (input_root / "mechanistic_tiny_smoke_test_report.json").write_text(
        json.dumps({"input_gate_passed": True}),
        encoding="utf-8",
    )
    (input_root / "mechanistic_tiny_smoke_test_report.md").write_text("qualitative only", encoding="utf-8")
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"candidate_export_only": True}), encoding="utf-8")
    feature_risk = root / "feature_risk.csv"
    write_csv(feature_risk, [], ["horizon_k", "feature_column"])
    data_risk = root / "data_risk.csv"
    write_csv(data_risk, [], ["horizon_k", "risk_key"])
    return input_root, manifest, feature_risk, data_risk


class LmbMechanisticSmokeTestDiagnosticsTests(unittest.TestCase):
    def test_event_rank_is_computed(self) -> None:
        predictions = [
            {"horizon_k": "3", "fold_id": "f1", "test_cell": "c1", "target_cycle": "1", "label_key": "incomplete_capacity_event", "actual_event_at_cycle": "0", "qualitative_model_score": "0.9"},
            {"horizon_k": "3", "fold_id": "f1", "test_cell": "c1", "target_cycle": "2", "label_key": "incomplete_capacity_event", "actual_event_at_cycle": "1", "qualitative_model_score": "0.7"},
        ]
        rows = build_event_rank_summary(predictions)

        self.assertEqual(rows[0]["event_rank_within_fold"], 2)
        self.assertEqual(rows[0]["negative_rows_scored_higher_than_event"], 1)

    def test_threshold_audit_detects_early_false_positive(self) -> None:
        predictions = [
            {"horizon_k": "3", "fold_id": "f1", "test_cell": "c1", "target_cycle": "1", "label_key": "incomplete_capacity_event", "actual_event_at_cycle": "0", "qualitative_model_score": "0.8"},
            {"horizon_k": "3", "fold_id": "f1", "test_cell": "c1", "target_cycle": "2", "label_key": "incomplete_capacity_event", "actual_event_at_cycle": "1", "qualitative_model_score": "0.6"},
        ]
        rows = build_threshold_audit(predictions)
        threshold_05 = next(row for row in rows if row["probability_threshold"] == 0.5)

        self.assertEqual(threshold_05["early_false_positive_rows"], 1)
        self.assertFalse(threshold_05["missed_event_at_threshold"])

    def test_coefficient_sign_flip_and_same_signal_dominance_are_marked(self) -> None:
        diagnostics = [
            {
                "horizon_k": "3",
                "coefficient_signs": json.dumps(
                    {
                        "ce_rolling_mean_window_past_5": "positive",
                        "charge_capacity_mah_trend_past_5": "positive",
                        "voltage_hysteresis_v_trend_past_5": "positive",
                    }
                ),
                "same_signal_source_feature_columns": "ce_rolling_mean_window_past_5;charge_capacity_mah_trend_past_5",
            },
            {
                "horizon_k": "3",
                "coefficient_signs": json.dumps(
                    {
                        "ce_rolling_mean_window_past_5": "positive",
                        "charge_capacity_mah_trend_past_5": "positive",
                        "voltage_hysteresis_v_trend_past_5": "zero",
                    }
                ),
                "same_signal_source_feature_columns": "ce_rolling_mean_window_past_5;charge_capacity_mah_trend_past_5",
            },
            {
                "horizon_k": "3",
                "coefficient_signs": json.dumps(
                    {
                        "ce_rolling_mean_window_past_5": "negative",
                        "charge_capacity_mah_trend_past_5": "positive",
                        "voltage_hysteresis_v_trend_past_5": "zero",
                    }
                ),
                "same_signal_source_feature_columns": "ce_rolling_mean_window_past_5;charge_capacity_mah_trend_past_5",
            },
        ]
        sign_rows = build_coefficient_sign_stability(diagnostics)
        ce_row = next(row for row in sign_rows if row["feature_column"] == "ce_rolling_mean_window_past_5")
        risk_rows = build_same_signal_risk_audit(sign_rows)

        self.assertEqual(ce_row["sign_flip_count"], 1)
        self.assertIn("same_signal_source_dominance_risk", risk_rows[0]["risk_label"])

    def test_outputs_are_horizon_separated_and_report_disallows_training(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root, manifest, feature_risk, data_risk = build_fixture(root)
            report = build_lmb_mechanistic_smoke_test_diagnostics(
                input_root=input_root,
                manifest_path=manifest,
                feature_risk_path=feature_risk,
                data_risk_path=data_risk,
                output_root=root / "out",
            )
            event_rows = read_csv(root / "out" / "mechanistic_event_rank_summary.csv")
            report_text = (root / "out" / "mechanistic_smoke_test_diagnostics_report.md").read_text(encoding="utf-8").lower()

            self.assertEqual({row["horizon_k"] for row in event_rows}, {"3", "5"})
            self.assertFalse(report["model_training_allowed"])
            self.assertNotIn("auc", report_text)
            self.assertNotIn("rmse", report_text)
            self.assertNotIn("accuracy", report_text)


if __name__ == "__main__":
    unittest.main()
