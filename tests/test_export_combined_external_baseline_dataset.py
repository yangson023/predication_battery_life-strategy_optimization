import tempfile
import unittest
from pathlib import Path

import pandas as pd

from modules.rul_prediction.export_combined_external_baseline_dataset import (
    export_combined_external_baseline_dataset,
)


def write_trainable_summary(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    rows = [
        {
            "dataset_split_name": "six_minobs20",
            "source_table": "cycle_features.csv",
            "cell_id": "G1C2",
            "batch_id": "batch_2",
            "part_id": "part_1",
            "label_key": "capacity_eol_80",
            "protocol_regime_index": 2.0,
            "observations": 4,
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
            "label_key": "capacity_eol_75",
            "protocol_regime_index": 2.0,
            "observations": 3,
            "eol_observed": True,
            "eol_observation_index": 3,
            "eol_boundary_quality": "away_from_protocol_boundary",
            "eol_distance_from_regime_start": 2,
            "eol_distance_to_regime_end": 6,
            "trainable_label_quality": "trainable_observed_protocol_consistent",
        },
        {
            "dataset_split_name": "six_minobs20",
            "source_table": "rpt_features.csv",
            "cell_id": "G1C2",
            "batch_id": "batch_2",
            "part_id": "part_1",
            "label_key": "rpt_capacity_eol_80",
            "protocol_regime_index": "",
            "observations": 4,
            "eol_observed": True,
            "eol_observation_index": 4,
            "eol_boundary_quality": "away_from_protocol_boundary",
            "eol_distance_from_regime_start": 3,
            "eol_distance_to_regime_end": 6,
            "trainable_label_quality": "excluded_unknown_or_unmapped",
        },
    ]
    pd.DataFrame(rows).to_csv(root / "trainable_label_summary.csv", index=False)


def write_cycle_features(root: Path, cell_id: str, batch_id: str, part_id: str, eol_cycle: int) -> None:
    root.mkdir(parents=True, exist_ok=True)
    rows = []
    for cycle in range(1, eol_cycle + 1):
        rows.append(
            {
                "dataset_id": "unit",
                "dataset_family": "external",
                "data_category": "cycling",
                "measurement_type": "cycle_timeseries",
                "chemistry": "li_ion",
                "cell_id": cell_id,
                "batch_id": batch_id,
                "part_id": part_id,
                "source_archive_name": "unit.zip",
                "archive_member_path": f"{cell_id}/cycling {cycle}.csv",
                "cycle_index": cycle,
                "sample_rows": 100,
                "duration_s": 1000 + cycle,
                "current_a_mean": 0.1,
                "voltage_v_mean": 3.2,
                "energy_wh_last": 1.0,
                "capacity_delta_ah": 1.0,
                "capacity_ah_mean": 1.0,
                "protocol_boundary_flag": False,
                "protocol_boundary_reason": "",
                "protocol_regime_index": 2,
            }
        )
    pd.DataFrame(rows).to_csv(root / "cycle_features.csv", index=False)


class CombinedExternalBaselineExportTests(unittest.TestCase):
    def test_exports_combined_main_without_rpt_or_leakage_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_root = root / "audit"
            six_root = root / "six"
            high_root = root / "high"
            output_root = root / "out"
            write_trainable_summary(audit_root)
            write_cycle_features(six_root, "G1C2", "batch_2", "part_1", 4)
            write_cycle_features(high_root, "G3C3", "batch_1", "part_1", 3)

            report = export_combined_external_baseline_dataset(
                audit_root=audit_root,
                output_root=output_root,
                source_feature_roots={"six_minobs20": six_root, "high_minobs20": high_root},
            )

            labels = pd.read_csv(output_root / "baseline_ready_labels.csv")
            features = pd.read_csv(output_root / "baseline_ready_feature_rows.csv")
            targets = pd.read_csv(output_root / "baseline_ready_targets.csv")
            removed = pd.read_csv(output_root / "removed_feature_columns.csv")

            self.assertEqual(report["dataset_split"], "combined_main")
            self.assertEqual(report["label_count"], 2)
            self.assertEqual(set(labels["dataset_split_name"]), {"combined_main"})
            self.assertEqual(set(labels["source_dataset_split_name"]), {"six_minobs20", "high_minobs20"})
            self.assertNotIn("rpt_capacity_eol_80", labels["label_key"].tolist())
            self.assertIn("source_dataset_split_name", features.columns)
            self.assertNotIn("capacity_delta_ah", features.columns)
            self.assertNotIn("capacity_ah_mean", features.columns)
            self.assertNotIn("protocol_boundary_flag", features.columns)
            self.assertNotIn("cycle_index_numeric", features.columns)
            self.assertIn("target_threshold_crossed", targets.columns)
            self.assertIn("capacity_delta_ah", removed["column"].tolist())
            self.assertIn("cycle_index_numeric", removed["column"].tolist())
            self.assertEqual(report["alignment_status"], "pass")

    def test_requested_exclusion_removes_exportable_feature(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            audit_root = root / "audit"
            six_root = root / "six"
            high_root = root / "high"
            output_root = root / "out"
            write_trainable_summary(audit_root)
            write_cycle_features(six_root, "G1C2", "batch_2", "part_1", 4)
            write_cycle_features(high_root, "G3C3", "batch_1", "part_1", 3)

            report = export_combined_external_baseline_dataset(
                audit_root=audit_root,
                output_root=output_root,
                source_feature_roots={"six_minobs20": six_root, "high_minobs20": high_root},
                exclude_features=["energy_wh_last"],
            )

            features = pd.read_csv(output_root / "baseline_ready_feature_rows.csv")
            removed = pd.read_csv(output_root / "removed_feature_columns.csv")

            self.assertNotIn("energy_wh_last", features.columns)
            self.assertIn("energy_wh_last", removed["column"].tolist())
            self.assertEqual(report["requested_excluded_features"], ["energy_wh_last"])


if __name__ == "__main__":
    unittest.main()
