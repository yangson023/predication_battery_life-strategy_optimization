import csv
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.audit_lmb_full_cell_early_feature_stability import audit_early_feature_stability


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class AuditLmbFullCellEarlyFeatureStabilityTest(unittest.TestCase):
    def test_creates_descriptive_summaries_without_model_claim(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            features = root / "features.csv"
            write_csv(features, ["cell_id", "protocol_id", "export_suffix", "current_long_cycle_index", "feature_a", "training_allowed_now"], [
                {"cell_id": "a", "protocol_id": "p1", "export_suffix": "1", "current_long_cycle_index": 1, "feature_a": "", "training_allowed_now": "False"},
                {"cell_id": "a", "protocol_id": "p1", "export_suffix": "1", "current_long_cycle_index": 2, "feature_a": 2.0, "training_allowed_now": "False"},
                {"cell_id": "a", "protocol_id": "p1", "export_suffix": "1", "current_long_cycle_index": 3, "feature_a": 3.0, "training_allowed_now": "False"},
                {"cell_id": "b", "protocol_id": "p2", "export_suffix": "2", "current_long_cycle_index": 2, "feature_a": 5.0, "training_allowed_now": "False"},
            ])
            schema = root / "schema.csv"
            write_csv(schema, ["feature_name", "feature_family", "same_signal_source_risk"], [{"feature_name": "feature_a", "feature_family": "voltage", "same_signal_source_risk": "False"}])
            censor = root / "censor.csv"
            write_csv(censor, ["cell_id", "event_observed"], [{"cell_id": "a", "event_observed": "False"}, {"cell_id": "b", "event_observed": "False"}])
            report = audit_early_feature_stability(features, schema, censor, root / "output")
            with (root / "output" / "lmb_full_cell_early_feature_cell_summary.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["valid_row_count"], "2")
            self.assertEqual(rows[0]["within_cell_slope_per_cycle"], "1.0")
            self.assertFalse(report["model_training_allowed"])

    def test_rejects_non_censored_feature_cell(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            features = root / "features.csv"
            write_csv(features, ["cell_id", "protocol_id", "export_suffix", "current_long_cycle_index", "feature_a", "training_allowed_now"], [{"cell_id": "a", "protocol_id": "p", "export_suffix": "1", "current_long_cycle_index": 1, "feature_a": 1, "training_allowed_now": "False"}])
            schema = root / "schema.csv"
            write_csv(schema, ["feature_name", "feature_family", "same_signal_source_risk"], [{"feature_name": "feature_a", "feature_family": "voltage", "same_signal_source_risk": "False"}])
            censor = root / "censor.csv"
            write_csv(censor, ["cell_id", "event_observed"], [])
            with self.assertRaises(ValueError):
                audit_early_feature_stability(features, schema, censor, root / "output")


if __name__ == "__main__":
    unittest.main()
