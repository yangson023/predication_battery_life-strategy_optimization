import tempfile
import unittest
from pathlib import Path

import pandas as pd

from modules.rul_prediction.external_loco_binary_diagnostics import (
    build_false_positive_false_negative_audit,
    build_prediction_timing_error,
    build_report,
    build_threshold_sensitivity,
    run_external_loco_diagnostics,
    add_eol_context,
)


def sample_predictions() -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dataset_split_name": "high_minobs20",
                "cell_id": "A",
                "batch_id": "batch_1",
                "part_id": "part_1",
                "label_key": "capacity_eol_80",
                "cycle_index": 1,
                "predicted_probability": 0.20,
                "predicted_threshold_crossed": False,
                "actual_threshold_crossed": False,
            },
            {
                "dataset_split_name": "high_minobs20",
                "cell_id": "A",
                "batch_id": "batch_1",
                "part_id": "part_1",
                "label_key": "capacity_eol_80",
                "cycle_index": 2,
                "predicted_probability": 0.80,
                "predicted_threshold_crossed": True,
                "actual_threshold_crossed": False,
            },
            {
                "dataset_split_name": "high_minobs20",
                "cell_id": "A",
                "batch_id": "batch_1",
                "part_id": "part_1",
                "label_key": "capacity_eol_80",
                "cycle_index": 3,
                "predicted_probability": 0.40,
                "predicted_threshold_crossed": False,
                "actual_threshold_crossed": True,
            },
            {
                "dataset_split_name": "high_minobs20",
                "cell_id": "B",
                "batch_id": "batch_2",
                "part_id": "part_1",
                "label_key": "capacity_eol_80",
                "cycle_index": 1,
                "predicted_probability": 0.10,
                "predicted_threshold_crossed": False,
                "actual_threshold_crossed": False,
            },
            {
                "dataset_split_name": "high_minobs20",
                "cell_id": "B",
                "batch_id": "batch_2",
                "part_id": "part_1",
                "label_key": "capacity_eol_80",
                "cycle_index": 2,
                "predicted_probability": 0.20,
                "predicted_threshold_crossed": False,
                "actual_threshold_crossed": True,
            },
        ]
    )


def write_diagnostic_inputs(baseline_root: Path, baseline_ready_root: Path) -> None:
    baseline_root.mkdir(parents=True, exist_ok=True)
    baseline_ready_root.mkdir(parents=True, exist_ok=True)
    predictions = sample_predictions()
    predictions.to_csv(baseline_root / "loco_binary_predictions.csv", index=False)
    pd.DataFrame(
        [
            {
                "label_key": "capacity_eol_80",
                "test_cell_id": "A",
                "train_cell_ids": "B",
                "train_rows": 2,
                "test_rows": 3,
                "train_positive_rows": 1,
                "test_positive_rows": 1,
                "validation_strategy": "leave_one_cell_out",
            }
        ]
    ).to_csv(baseline_root / "loco_binary_fold_design.csv", index=False)
    pd.DataFrame(
        [
            {
                "label_key": "capacity_eol_80",
                "test_cell_id": "A",
                "notes": "exploratory_not_formal_performance",
            }
        ]
    ).to_csv(baseline_root / "loco_binary_fold_summary.csv", index=False)
    (baseline_root / "loco_binary_report.json").write_text(
        '{"is_formal_model_performance": false}',
        encoding="utf-8",
    )
    (baseline_root / "feature_columns.txt").write_text(
        "duration_s\nenergy_wh_last\n",
        encoding="utf-8",
    )
    pd.DataFrame(
        [
            {
                "dataset_split_name": "high_minobs20",
                "cell_id": "A",
                "batch_id": "batch_1",
                "part_id": "part_1",
                "label_key": "capacity_eol_80",
                "cycle_index": 1,
                "duration_s": 10,
                "energy_wh_last": 1.0,
            },
            {
                "dataset_split_name": "high_minobs20",
                "cell_id": "B",
                "batch_id": "batch_2",
                "part_id": "part_1",
                "label_key": "capacity_eol_80",
                "cycle_index": 1,
                "duration_s": 20,
                "energy_wh_last": 2.0,
            },
        ]
    ).to_csv(baseline_ready_root / "baseline_ready_feature_rows.csv", index=False)


class ExternalLocoBinaryDiagnosticsTests(unittest.TestCase):
    def test_threshold_sensitivity_outputs_required_thresholds(self) -> None:
        sensitivity = build_threshold_sensitivity(sample_predictions(), [0.3, 0.5, 0.7])

        self.assertEqual(set(sensitivity["probability_threshold"]), {0.3, 0.5, 0.7})

    def test_error_classes_include_missed_and_early_false_positive(self) -> None:
        trajectory = add_eol_context(sample_predictions())
        timing = build_prediction_timing_error(trajectory)
        audit = build_false_positive_false_negative_audit(trajectory)

        self.assertIn("early_false_positive", timing["timing_class"].tolist())
        self.assertIn("missed_eol", timing["timing_class"].tolist())
        self.assertIn("early_false_positive", audit["event_type"].tolist())
        self.assertIn("missed_eol", audit["event_type"].tolist())

    def test_report_does_not_use_formal_metric_terms(self) -> None:
        trajectory = add_eol_context(sample_predictions())
        sensitivity = build_threshold_sensitivity(sample_predictions(), [0.3, 0.5, 0.7])
        timing = build_prediction_timing_error(trajectory)
        audit = build_false_positive_false_negative_audit(trajectory)
        batch = pd.DataFrame(
            [
                {
                    "feature": "energy_wh_last",
                    "risk_flag": "batch_confound_risk",
                }
            ]
        )

        report = build_report(sensitivity, trajectory, timing, audit, batch)
        report_text = str(report).lower()

        self.assertNotIn("rmse", report_text)
        self.assertNotIn("r-squared", report_text)
        self.assertNotIn("auc", report_text)

    def test_run_writes_diagnostic_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            baseline_root = root / "baseline"
            baseline_ready_root = root / "baseline_ready"
            output_root = root / "diagnostics"
            write_diagnostic_inputs(baseline_root, baseline_ready_root)

            report = run_external_loco_diagnostics(
                baseline_root=baseline_root,
                baseline_ready_root=baseline_ready_root,
                output_root=output_root,
            )

            self.assertEqual(report["threshold_sensitivity_rows"], 6)
            self.assertTrue((output_root / "threshold_sensitivity.csv").exists())
            self.assertTrue((output_root / "per_cell_probability_trajectory.csv").exists())
            self.assertTrue((output_root / "prediction_timing_error.csv").exists())
            self.assertTrue((output_root / "false_positive_false_negative_audit.csv").exists())
            self.assertTrue((output_root / "batch_feature_risk_summary.csv").exists())
            self.assertTrue((output_root / "external_loco_diagnostics_report.json").exists())
            self.assertTrue((output_root / "external_loco_diagnostics_report.md").exists())


if __name__ == "__main__":
    unittest.main()
