import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.audit_lmb_full_cell_termination import audit_termination


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class AuditLmbFullCellTerminationTest(unittest.TestCase):
    def test_unknown_termination_blocks_labels_and_excludes_diagnostic_cell(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"cells": [
                {"cell_id": "active", "source_folder_name": "x", "export_suffix": "1", "dataset_role": "true_lmb", "cell_scope": "lmb_full_cell", "use_status": "active_feature_audit", "termination_reason": "unknown"},
                {"cell_id": "diagnostic", "dataset_role": "diagnostic_only", "cell_scope": "lmb_full_cell", "use_status": "excluded", "termination_reason": "natural_failure"},
            ]}), encoding="utf-8")
            summary = root / "summary.csv"
            write_csv(summary, ["cell_id", "paired_cycle_count", "long_cycle_pair_count"], [{"cell_id": "active", "paired_cycle_count": 20, "long_cycle_pair_count": 17}])
            unpaired = root / "unpaired.csv"
            write_csv(unpaired, ["cell_id"], [{"cell_id": "active"}])
            report = audit_termination(manifest, summary, unpaired, root / "output")
            with (root / "output" / "lmb_full_cell_termination_audit.csv").open(encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["termination_interpretation"], "unresolved_termination_reason")
            self.assertEqual(rows[0]["terminal_pairing_status"], "terminal_unpaired_charge_needs_review")
            self.assertEqual(rows[0]["label_trainability_allowed"], "False")
            with (root / "output" / "partner_termination_confirmation_template.csv").open(encoding="utf-8") as handle:
                partner_template = list(csv.DictReader(handle))
            self.assertEqual(partner_template[0]["填写状态"], "待 partner 确认")
            self.assertFalse(report["model_training_allowed"])

    def test_planned_cycle_reason_is_censored_candidate_not_observed_failure(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"cells": [{
                "cell_id": "active", "dataset_role": "true_lmb", "cell_scope": "lmb_full_cell", "use_status": "active_feature_audit", "termination_reason": "planned_cycle_count_reached",
            }]}), encoding="utf-8")
            summary = root / "summary.csv"
            write_csv(summary, ["cell_id", "paired_cycle_count", "long_cycle_pair_count"], [{"cell_id": "active", "paired_cycle_count": 20, "long_cycle_pair_count": 17}])
            unpaired = root / "unpaired.csv"
            write_csv(unpaired, ["cell_id"], [])
            audit_termination(manifest, summary, unpaired, root / "output")
            with (root / "output" / "lmb_full_cell_termination_audit.csv").open(encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["termination_interpretation"], "protocol_censored_confirmed_planned_count_value_missing")
            self.assertEqual(row["censoring_semantics_confirmed"], "True")
            self.assertEqual(row["censored_at_long_cycle_index"], "17")
            self.assertEqual(row["observed_failure_label_created"], "False")
            self.assertEqual(row["protocol_censored_label_created"], "False")

    def test_observed_failure_requires_event_mode_and_evidence(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            manifest = root / "manifest.json"
            manifest.write_text(json.dumps({"cells": [{
                "cell_id": "failed", "dataset_role": "true_lmb", "cell_scope": "lmb_full_cell",
                "use_status": "active_feature_audit", "termination_reason": "natural_failure",
                "failure_event_long_cycle_index": 8, "failure_mode": "voltage_instability",
                "failure_evidence_location": "lab_log/failed_cell.md",
            }]}), encoding="utf-8")
            summary = root / "summary.csv"
            write_csv(summary, ["cell_id", "paired_cycle_count", "long_cycle_pair_count"], [{"cell_id": "failed", "paired_cycle_count": 11, "long_cycle_pair_count": 8}])
            unpaired = root / "unpaired.csv"
            write_csv(unpaired, ["cell_id"], [])
            audit_termination(manifest, summary, unpaired, root / "output")
            with (root / "output" / "lmb_full_cell_termination_audit.csv").open(encoding="utf-8") as handle:
                row = next(csv.DictReader(handle))
            self.assertEqual(row["observed_failure_semantics_confirmed"], "True")
            self.assertEqual(row["observed_failure_label_created"], "False")


if __name__ == "__main__":
    unittest.main()
