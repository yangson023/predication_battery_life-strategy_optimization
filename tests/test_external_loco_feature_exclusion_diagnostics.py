import tempfile
import unittest
from pathlib import Path

import pandas as pd

from modules.rul_prediction.external_loco_feature_exclusion_diagnostics import (
    build_full_vs_feature_threshold_comparison,
    build_experiment_specs,
    build_markdown_report,
    build_report,
    classify_feature_effect,
    run_feature_exclusion_diagnostics,
)


def synthetic_comparison() -> pd.DataFrame:
    rows = []
    for index in range(10):
        rows.append(
            {
                "label_key": "capacity_eol_80",
                "cell_id": f"C{index}",
                "excluded_feature": "current_a_last",
                "baseline_first_predicted_positive_cycle": 8,
                "ablation_first_predicted_positive_cycle": 9,
                "baseline_timing_error": -4,
                "ablation_timing_error": -2 if index < 3 else -4,
                "baseline_false_positive_rows": 3,
                "ablation_false_positive_rows": 2 if index < 3 else 3,
                "baseline_false_negative_rows": 0,
                "ablation_false_negative_rows": 0,
                "timing_error_improved": index < 3,
                "false_positive_reduced": index < 3,
                "false_negative_increased": False,
            }
        )
        rows.append(
            {
                "label_key": "capacity_eol_80",
                "cell_id": f"H{index}",
                "excluded_feature": "energy_wh_last",
                "baseline_first_predicted_positive_cycle": 8,
                "ablation_first_predicted_positive_cycle": "",
                "baseline_timing_error": -4,
                "ablation_timing_error": "",
                "baseline_false_positive_rows": 3,
                "ablation_false_positive_rows": 1,
                "baseline_false_negative_rows": 0,
                "ablation_false_negative_rows": 1 if index == 0 else 0,
                "timing_error_improved": False,
                "false_positive_reduced": True,
                "false_negative_increased": index == 0,
            }
        )
    return pd.DataFrame(rows)


def write_minimal_combined_input(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    feature_rows = []
    target_rows = []
    labels = []
    cell_eol = {
        "capacity_eol_75": {"A": 4, "B": 4},
        "capacity_eol_80": {"A": 4, "B": 4, "C": 4},
    }
    for label_key, cells in cell_eol.items():
        for cell_id, eol_cycle in cells.items():
            labels.append(
                {
                    "dataset_split_name": "combined_main",
                    "source_dataset_split_name": "unit",
                    "source_table": "cycle_features.csv",
                    "cell_id": cell_id,
                    "batch_id": "batch_1",
                    "part_id": "part_1",
                    "label_key": label_key,
                    "protocol_regime_index": 2.0,
                    "observations": 4,
                    "eol_observed": True,
                    "eol_observation_index": eol_cycle,
                    "eol_boundary_quality": "away_from_protocol_boundary",
                    "eol_distance_from_regime_start": 3,
                    "eol_distance_to_regime_end": 6,
                    "trainable_label_quality": "trainable_observed_protocol_consistent",
                }
            )
            for cycle in range(1, eol_cycle + 1):
                keys = {
                    "dataset_split_name": "combined_main",
                    "source_dataset_split_name": "unit",
                    "cell_id": cell_id,
                    "batch_id": "batch_1",
                    "part_id": "part_1",
                    "label_key": label_key,
                    "cycle_index": cycle,
                }
                feature_rows.append(
                    {
                        **keys,
                        "current_a_last": float(cycle),
                        "energy_wh_last": float(eol_cycle - cycle + 1),
                        "current_a_mean": float(cycle) / 10.0,
                        "duration_s": 1000.0 + cycle,
                    }
                )
                target_rows.append(
                    {
                        **keys,
                        "target_threshold_crossed": cycle == eol_cycle,
                        "cycles_to_eol_at_row": eol_cycle - cycle,
                    }
                )
    pd.DataFrame(feature_rows).to_csv(root / "baseline_ready_feature_rows.csv", index=False)
    pd.DataFrame(target_rows).to_csv(root / "baseline_ready_targets.csv", index=False)
    pd.DataFrame(labels).to_csv(root / "baseline_ready_labels.csv", index=False)
    (root / "dataset_manifest.json").write_text('{"dataset_split": "combined_main"}', encoding="utf-8")


class ExternalLocoFeatureExclusionDiagnosticsTests(unittest.TestCase):
    def test_experiment_specs_keep_full_control_and_single_feature_exclusions(self) -> None:
        specs = build_experiment_specs(["a", "b"])

        self.assertEqual(specs[0]["experiment_name"], "full_features")
        self.assertIsNone(specs[0]["excluded_feature"])
        self.assertEqual([spec["excluded_feature"] for spec in specs[1:]], ["a", "b"])

    def test_decision_rules_detect_possible_confound_and_harmful_exclusion(self) -> None:
        decisions = classify_feature_effect(synthetic_comparison())
        by_feature = {
            row["excluded_feature"]: row["diagnostic_decision"]
            for row in decisions.to_dict("records")
        }

        self.assertEqual(by_feature["current_a_last"], "possible_confound_feature")
        self.assertEqual(by_feature["energy_wh_last"], "exclusion_harms_detection")

    def test_report_avoids_formal_performance_phrase(self) -> None:
        comparison = synthetic_comparison()
        decisions = classify_feature_effect(comparison)
        fold_summary = pd.DataFrame(
            {
                "experiment_name": ["full_features"],
                "excluded_feature": [""],
                "label_key": ["capacity_eol_80"],
            }
        )
        report = build_report(fold_summary, comparison, decisions, ["current_a_last"])
        markdown = build_markdown_report(decisions, comparison, report)

        self.assertNotIn("formal performance", str(report).lower())
        self.assertNotIn("formal performance", markdown.lower())

    def test_full_vs_feature_threshold_comparison_has_required_columns(self) -> None:
        sensitivity = pd.DataFrame(
            [
                {
                    "experiment_name": "full_features",
                    "excluded_feature": "",
                    "probability_threshold": 0.5,
                    "label_key": "capacity_eol_80",
                    "cell_id": "A",
                    "false_positive_rows": 2,
                    "false_negative_rows": 0,
                    "precision_diagnostic": 0.33,
                    "recall_diagnostic": 1.0,
                    "first_predicted_positive_cycle": 8,
                },
                {
                    "experiment_name": "drop_energy_wh_last",
                    "excluded_feature": "energy_wh_last",
                    "probability_threshold": 0.5,
                    "label_key": "capacity_eol_80",
                    "cell_id": "A",
                    "false_positive_rows": 1,
                    "false_negative_rows": 0,
                    "precision_diagnostic": 0.5,
                    "recall_diagnostic": 1.0,
                    "first_predicted_positive_cycle": 9,
                },
            ]
        )
        timing = pd.DataFrame(
            [
                {
                    "experiment_name": "full_features",
                    "excluded_feature": "",
                    "label_key": "capacity_eol_80",
                    "cell_id": "A",
                    "prediction_timing_error_cycles": -2,
                    "timing_class": "early_false_positive",
                },
                {
                    "experiment_name": "drop_energy_wh_last",
                    "excluded_feature": "energy_wh_last",
                    "label_key": "capacity_eol_80",
                    "cell_id": "A",
                    "prediction_timing_error_cycles": -1,
                    "timing_class": "early_false_positive",
                },
            ]
        )

        comparison = build_full_vs_feature_threshold_comparison(sensitivity, timing)

        self.assertEqual(len(comparison), 1)
        self.assertIn("full_false_positive_rows", comparison.columns)
        self.assertIn("drop_false_negative_rows", comparison.columns)
        self.assertIn("full_timing_error", comparison.columns)
        self.assertIn("drop_timing_error", comparison.columns)

    def test_run_writes_expected_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input"
            output_root = root / "output"
            write_minimal_combined_input(input_root)

            report = run_feature_exclusion_diagnostics(
                input_root=input_root,
                output_root=output_root,
                candidate_features=["current_a_last"],
            )

            self.assertIn("full_features", report["experiments"])
            self.assertIn("drop_current_a_last", report["experiments"])
            self.assertTrue((output_root / "feature_exclusion_fold_summary.csv").exists())
            self.assertTrue((output_root / "feature_exclusion_timing_error.csv").exists())
            self.assertTrue((output_root / "feature_exclusion_threshold_sensitivity.csv").exists())
            self.assertTrue((output_root / "feature_exclusion_comparison.csv").exists())
            self.assertTrue((output_root / "feature_exclusion_fold_comparison_full.csv").exists())
            self.assertTrue((output_root / "feature_exclusion_report.json").exists())
            self.assertTrue((output_root / "feature_exclusion_report.md").exists())


if __name__ == "__main__":
    unittest.main()
