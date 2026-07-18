import csv
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.build_lmb_full_cell_protocol_censor_audit import build_protocol_censor_audit


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class BuildLmbFullCellProtocolCensorAuditTest(unittest.TestCase):
    def test_confirmed_censoring_is_audit_only_and_not_failure_target(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            termination = root / "termination.csv"
            write_csv(termination, [
                "cell_id", "dataset_role", "cell_scope", "electrolyte_code", "protocol_id", "termination_reason",
                "planned_long_cycle_count", "terminal_pairing_status", "censoring_semantics_confirmed", "censored_at_long_cycle_index",
            ], [{
                "cell_id": "cell-a", "dataset_role": "true_lmb", "cell_scope": "lmb_full_cell", "electrolyte_code": "LB-085",
                "protocol_id": "p", "termination_reason": "planned_cycle_count_reached", "planned_long_cycle_count": "",
                "terminal_pairing_status": "terminal_unpaired_charge_needs_review", "censoring_semantics_confirmed": "True", "censored_at_long_cycle_index": 3,
            }])
            paired = root / "pairs.csv"
            write_csv(paired, ["cell_id", "protocol_phase", "long_cycle_pair_index"], [
                {"cell_id": "cell-a", "protocol_phase": "formation", "long_cycle_pair_index": ""},
                {"cell_id": "cell-a", "protocol_phase": "long_cycle", "long_cycle_pair_index": 1},
                {"cell_id": "cell-a", "protocol_phase": "long_cycle", "long_cycle_pair_index": 2},
                {"cell_id": "cell-a", "protocol_phase": "long_cycle", "long_cycle_pair_index": 3},
            ])
            report = build_protocol_censor_audit(termination, paired, root / "output")
            with (root / "output" / "lmb_full_cell_protocol_censor_labels_audit.csv").open(encoding="utf-8") as handle:
                label_row = next(csv.DictReader(handle))
            self.assertEqual(label_row["label_key"], "protocol_censored")
            self.assertEqual(label_row["event_observed"], "False")
            self.assertEqual(label_row["censoring_long_cycle_index"], "3")
            self.assertEqual(label_row["label_trainability_allowed"], "False")
            self.assertFalse(report["model_training_allowed"])

    def test_nonconfirmed_cell_is_not_exported(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            termination = root / "termination.csv"
            write_csv(termination, ["cell_id", "censoring_semantics_confirmed"], [{"cell_id": "cell-a", "censoring_semantics_confirmed": "False"}])
            paired = root / "pairs.csv"
            write_csv(paired, ["cell_id", "protocol_phase", "long_cycle_pair_index"], [])
            report = build_protocol_censor_audit(termination, paired, root / "output")
            self.assertEqual(report["protocol_censored_cell_count"], 0)
            self.assertEqual(report["skipped_cell_ids"], ["cell-a"])


if __name__ == "__main__":
    unittest.main()
