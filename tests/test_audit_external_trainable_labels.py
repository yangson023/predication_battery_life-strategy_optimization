import tempfile
import unittest
from pathlib import Path

import pandas as pd

from modules.feature_engineering.audit_external_trainable_labels import (
    LabelDataset,
    audit_external_trainable_labels,
)


def write_label_outputs(root: Path) -> None:
    root.mkdir(parents=True)
    summary = pd.DataFrame(
        [
            {
                "source_table": "cycle_features.csv",
                "label_key": "capacity_eol_80",
                "group_id": "unit|G1C1|unit.zip|2",
                "protocol_regime_index": 2,
                "observations": 20,
                "eol_observed": True,
                "eol_observation_index": 12,
                "eol_boundary_quality": "away_from_protocol_boundary",
                "eol_distance_from_regime_start": 11,
                "eol_distance_to_regime_end": 8,
                "label_quality": "usable",
                "trainable_label": True,
                "trainable_label_quality": "trainable_observed_protocol_consistent",
            },
            {
                "source_table": "cycle_features.csv",
                "label_key": "capacity_eol_70",
                "group_id": "unit|G1C1|unit.zip|2",
                "protocol_regime_index": 2,
                "observations": 20,
                "eol_observed": True,
                "eol_observation_index": 19,
                "eol_boundary_quality": "unreliable_boundary_crossing",
                "eol_distance_from_regime_start": 18,
                "eol_distance_to_regime_end": 1,
                "label_quality": "usable",
                "trainable_label": False,
                "trainable_label_quality": "excluded_unreliable_boundary_crossing",
            },
            {
                "source_table": "rpt_features.csv",
                "label_key": "rpt_capacity_eol_80",
                "group_id": "unit|G1C1|unit.zip",
                "protocol_regime_index": "",
                "observations": 20,
                "eol_observed": True,
                "eol_observation_index": 6,
                "eol_boundary_quality": "away_from_protocol_boundary",
                "eol_distance_from_regime_start": 6,
                "eol_distance_to_regime_end": 14,
                "label_quality": "usable",
                "trainable_label": False,
                "trainable_label_quality": "excluded_unknown_or_unmapped",
            },
        ]
    )
    labels = pd.DataFrame(
        [
            {
                "source_table": row["source_table"],
                "label_key": row["label_key"],
                "cell_id": "G1C1",
                "batch_id": "batch_1",
                "part_id": "part_1",
                "source_archive_name": "unit.zip",
                "protocol_regime_index": row["protocol_regime_index"],
            }
            for row in summary.to_dict("records")
        ]
    )
    summary.to_csv(root / "external_label_summary.csv", index=False)
    labels.to_csv(root / "external_health_labels.csv", index=False)


class ExternalTrainableLabelAuditTests(unittest.TestCase):
    def test_audit_exports_only_trainable_cycle_labels(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            labels_root = root / "labels"
            output_root = root / "audit"
            write_label_outputs(labels_root)

            report = audit_external_trainable_labels(
                datasets=[LabelDataset("unit_split", labels_root)],
                output_root=output_root,
            )

            trainable = pd.read_csv(output_root / "trainable_label_summary.csv")
            excluded = pd.read_csv(output_root / "excluded_label_summary.csv")
            coverage = pd.read_csv(output_root / "label_coverage_matrix.csv")

            self.assertEqual(report["trainable_summary_rows"], 1)
            self.assertEqual(report["excluded_summary_rows"], 2)
            self.assertEqual(report["rpt_excluded_rows"], 1)
            self.assertEqual(report["boundary_excluded_rows"], 1)
            self.assertEqual(trainable["source_table"].unique().tolist(), ["cycle_features.csv"])
            self.assertEqual(trainable["label_key"].tolist(), ["capacity_eol_80"])
            self.assertNotIn("rpt_capacity_eol_80", trainable["label_key"].tolist())
            self.assertIn("excluded_unreliable_boundary_crossing", excluded["trainable_label_quality"].tolist())
            self.assertIn("capacity_eol_80", coverage.columns)
            self.assertTrue((output_root / "label_audit_report.json").exists())
            self.assertTrue((output_root / "label_audit_report.md").exists())


if __name__ == "__main__":
    unittest.main()
