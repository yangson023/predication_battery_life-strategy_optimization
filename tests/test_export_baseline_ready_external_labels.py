import tempfile
import unittest
from pathlib import Path

import pandas as pd

from modules.feature_engineering.export_baseline_ready_external_labels import (
    export_baseline_ready_dataset,
)


def write_audit_tables(root: Path) -> None:
    root.mkdir(parents=True)
    trainable = pd.DataFrame(
        [
            {
                "dataset_split_name": "high_minobs20",
                "source_table": "cycle_features.csv",
                "cell_id": "G3C3",
                "batch_id": "batch_1",
                "part_id": "part_1",
                "label_key": "capacity_eol_80",
                "protocol_regime_index": 2.0,
                "observations": 30,
                "eol_observed": True,
                "eol_observation_index": 4,
                "eol_boundary_quality": "away_from_protocol_boundary",
                "eol_distance_from_regime_start": 3,
                "eol_distance_to_regime_end": 6,
                "trainable_label_quality": "trainable_observed_protocol_consistent",
            },
            {
                "dataset_split_name": "six_minobs20",
                "source_table": "cycle_features.csv",
                "cell_id": "G1C2",
                "batch_id": "batch_2",
                "part_id": "part_1",
                "label_key": "capacity_eol_80",
                "protocol_regime_index": 2.0,
                "observations": 30,
                "eol_observed": True,
                "eol_observation_index": 4,
                "eol_boundary_quality": "away_from_protocol_boundary",
                "eol_distance_from_regime_start": 3,
                "eol_distance_to_regime_end": 6,
                "trainable_label_quality": "trainable_observed_protocol_consistent",
            },
            {
                "dataset_split_name": "high_minobs20",
                "source_table": "cycle_features.csv",
                "cell_id": "G3C3",
                "batch_id": "batch_1",
                "part_id": "part_1",
                "label_key": "capacity_eol_70",
                "protocol_regime_index": 2.0,
                "observations": 30,
                "eol_observed": True,
                "eol_observation_index": 5,
                "eol_boundary_quality": "away_from_protocol_boundary",
                "eol_distance_from_regime_start": 4,
                "eol_distance_to_regime_end": 6,
                "trainable_label_quality": "trainable_observed_protocol_consistent",
            },
            {
                "dataset_split_name": "high_minobs20",
                "source_table": "cycle_features.csv",
                "cell_id": "G11C1",
                "batch_id": "batch_2",
                "part_id": "part_2",
                "label_key": "capacity_eol_75",
                "protocol_regime_index": 1.0,
                "observations": 30,
                "eol_observed": False,
                "eol_observation_index": "",
                "eol_boundary_quality": "not_observed",
                "eol_distance_from_regime_start": "",
                "eol_distance_to_regime_end": "",
                "trainable_label_quality": "trainable_censored_protocol_consistent",
            },
        ]
    )
    excluded = pd.DataFrame(
        [
            {
                "dataset_split_name": "high_minobs20",
                "source_table": "rpt_features.csv",
                "cell_id": "G3C3",
                "batch_id": "batch_1",
                "part_id": "part_1",
                "label_key": "rpt_capacity_eol_80",
                "protocol_regime_index": "",
                "observations": 30,
                "eol_observed": True,
                "eol_observation_index": 4,
                "eol_boundary_quality": "away_from_protocol_boundary",
                "eol_distance_from_regime_start": 3,
                "eol_distance_to_regime_end": 6,
                "trainable_label_quality": "excluded_unknown_or_unmapped",
            },
            {
                "dataset_split_name": "high_minobs20",
                "source_table": "cycle_features.csv",
                "cell_id": "G3C3",
                "batch_id": "batch_1",
                "part_id": "part_1",
                "label_key": "capacity_eol_75",
                "protocol_regime_index": 2.0,
                "observations": 30,
                "eol_observed": True,
                "eol_observation_index": 8,
                "eol_boundary_quality": "unreliable_boundary_crossing",
                "eol_distance_from_regime_start": 7,
                "eol_distance_to_regime_end": 1,
                "trainable_label_quality": "excluded_unreliable_boundary_crossing",
            },
        ]
    )
    trainable.to_csv(root / "trainable_label_summary.csv", index=False)
    excluded.to_csv(root / "excluded_label_summary.csv", index=False)


def write_cycle_features(root: Path) -> None:
    root.mkdir(parents=True)
    rows = []
    for cycle_index in range(1, 7):
        rows.append(
            {
                "dataset_id": "unit",
                "dataset_family": "multi_cell_cycle_life",
                "data_category": "cycling",
                "measurement_type": "cycle_timeseries",
                "chemistry": "li_ion",
                "cell_id": "G3C3",
                "batch_id": "batch_1",
                "part_id": "part_1",
                "source_archive_name": "unit.zip",
                "archive_member_path": f"G3C3/cycling {cycle_index}.csv",
                "cycle_index": cycle_index,
                "sample_rows": 100,
                "duration_s": 3000 + cycle_index,
                "current_a_mean": 0.1,
                "voltage_v_mean": 3.4,
                "capacity_ah_mean": 1.0,
                "capacity_delta_ah": 0.9,
                "absolute_current_mean_a": 1.2,
                "protocol_boundary_flag": False,
                "protocol_boundary_reason": "",
                "protocol_regime_index": 2,
            }
        )
    pd.DataFrame(rows).to_csv(root / "cycle_features.csv", index=False)


class BaselineReadyExportTests(unittest.TestCase):
    def test_exports_only_guarded_main_cycle_labels_and_non_leakage_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_root = root / "audit"
            feature_root = root / "features"
            output_root = root / "out"
            write_audit_tables(audit_root)
            write_cycle_features(feature_root)

            report = export_baseline_ready_dataset(audit_root, feature_root, output_root)

            labels = pd.read_csv(output_root / "baseline_ready_labels.csv")
            feature_rows = pd.read_csv(output_root / "baseline_ready_feature_rows.csv")
            rejected = pd.read_csv(output_root / "rejected_trainable_labels.csv")
            removed = pd.read_csv(output_root / "removed_feature_columns.csv")
            feature_columns = (output_root / "features_columns.txt").read_text(encoding="utf-8")

            self.assertEqual(report["exported_label_count"], 1)
            self.assertEqual(labels["dataset_split_name"].tolist(), ["high_minobs20"])
            self.assertEqual(labels["source_table"].tolist() if "source_table" in labels.columns else ["cycle_features.csv"], ["cycle_features.csv"])
            self.assertEqual(labels["label_key"].tolist(), ["capacity_eol_80"])
            self.assertTrue(feature_rows["target_threshold_crossed"].any())
            self.assertEqual(int(feature_rows["target_threshold_crossed"].sum()), 1)
            self.assertNotIn("capacity_delta_ah", feature_rows.columns)
            self.assertNotIn("capacity_ah_mean", feature_rows.columns)
            self.assertNotIn("protocol_regime_index", feature_rows.columns)
            self.assertNotIn("protocol_boundary_flag", feature_rows.columns)
            self.assertIn("duration_s", feature_columns)
            self.assertIn("capacity_delta_ah", removed["column"].tolist())
            self.assertIn("capacity_ah_mean", removed["column"].tolist())
            self.assertIn("protocol_boundary_flag", removed["column"].tolist())
            self.assertIn("non_main_dataset_split", ";".join(rejected["main_export_rejection_reason"].tolist()))
            self.assertIn("label_key_not_in_main_thresholds", ";".join(rejected["main_export_rejection_reason"].tolist()))
            self.assertIn("censored_or_unobserved", ";".join(rejected["main_export_rejection_reason"].tolist()))
            self.assertEqual(report["alignment_status"], "pass")
            self.assertTrue((output_root / "dataset_manifest.json").exists())
            self.assertTrue((output_root / "feature_statistics_per_batch.csv").exists())
            self.assertTrue((output_root / "alignment_check.csv").exists())


if __name__ == "__main__":
    unittest.main()
