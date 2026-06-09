import tempfile
import unittest
from pathlib import Path

import pandas as pd

from modules.rul_prediction.external_loco_binary_baseline import (
    build_model_frame,
    feature_columns,
    run_external_loco_binary_baseline,
    validate_inputs,
)


def write_baseline_ready_inputs(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    feature_rows = []
    target_rows = []
    labels = []
    label_specs = {
        "capacity_eol_75": {"A": 3, "B": 4},
        "capacity_eol_80": {"A": 3, "B": 4, "C": 5},
    }
    for label_key, cells in label_specs.items():
        for cell_id, eol_cycle in cells.items():
            labels.append(
                {
                    "dataset_split_name": "high_minobs20",
                    "source_table": "cycle_features.csv",
                    "cell_id": cell_id,
                    "batch_id": f"batch_{cell_id}",
                    "part_id": "part_1",
                    "label_key": label_key,
                    "protocol_regime_index": 2,
                    "observations": 5,
                    "eol_observed": True,
                    "eol_observation_index": eol_cycle,
                    "eol_boundary_quality": "away_from_protocol_boundary",
                    "eol_distance_from_regime_start": eol_cycle - 1,
                    "eol_distance_to_regime_end": 6,
                    "trainable_label_quality": "trainable_observed_protocol_consistent",
                }
            )
            for cycle in range(1, eol_cycle + 1):
                keys = {
                    "dataset_split_name": "high_minobs20",
                    "cell_id": cell_id,
                    "batch_id": f"batch_{cell_id}",
                    "part_id": "part_1",
                    "label_key": label_key,
                    "cycle_index": cycle,
                }
                feature_rows.append(
                    {
                        **keys,
                        "duration_s": 1000 + cycle,
                        "current_a_mean": 0.1 * cycle,
                        "voltage_v_mean": 3.0 + 0.01 * cycle,
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
    (root / "dataset_manifest.json").write_text(
        '{"dataset_split":"high_minobs20","exported_label_count":5,"exported_feature_row_count":19}',
        encoding="utf-8",
    )


class ExternalLocoBinaryBaselineTests(unittest.TestCase):
    def test_feature_columns_reject_forbidden_columns(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_split_name": ["high_minobs20"],
                "cell_id": ["A"],
                "batch_id": ["batch_A"],
                "part_id": ["part_1"],
                "label_key": ["capacity_eol_80"],
                "cycle_index": [1],
                "duration_s": [1.0],
                "capacity_delta_ah": [0.5],
            }
        )

        with self.assertRaises(ValueError):
            feature_columns(frame)

    def test_inputs_validate_and_targets_merge_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_baseline_ready_inputs(root)
            features = pd.read_csv(root / "baseline_ready_feature_rows.csv")
            targets = pd.read_csv(root / "baseline_ready_targets.csv")
            labels = pd.read_csv(root / "baseline_ready_labels.csv")

            validate_inputs(features, targets, labels)
            model_frame = build_model_frame(features, targets)

            self.assertIn("target_threshold_crossed", model_frame.columns)
            self.assertNotIn("target_threshold_crossed", features.columns)
            self.assertEqual(len(model_frame), len(features))

    def test_run_outputs_loco_fold_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input"
            output_root = root / "output"
            write_baseline_ready_inputs(input_root)

            fold_summary, predictions, fold_design = run_external_loco_binary_baseline(
                input_root=input_root,
                output_root=output_root,
            )

            self.assertEqual(len(fold_design), 5)
            self.assertEqual(set(fold_design["validation_strategy"]), {"leave_one_cell_out"})
            self.assertEqual(set(fold_summary["label_key"]), {"capacity_eol_75", "capacity_eol_80"})
            self.assertFalse(predictions.empty)
            self.assertTrue((output_root / "loco_binary_fold_summary.csv").exists())
            self.assertTrue((output_root / "loco_binary_predictions.csv").exists())
            self.assertTrue((output_root / "loco_binary_report.md").exists())


if __name__ == "__main__":
    unittest.main()
