import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.audit_btsda_full_cell_cycle_semantics import audit_cycle_semantics


def write_csv(path, headers, rows):
    with path.open("w", encoding="gbk", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(headers)
        writer.writerows(rows)


class AuditBtsdaFullCellCycleSemanticsTest(unittest.TestCase):
    def test_detects_mismatch_and_multi_pair_cycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, output = Path(tmp) / "input", Path(tmp) / "output"
            root.mkdir()
            write_csv(root / "data_cycle-1.csv", ["循环号"], [["1"], ["2"], ["3"]])
            write_csv(root / "data_step-1.csv", ["循环号", "工步号", "工步序号", "工步类型"], [
                ["1", "2", "1", "恒流充电"], ["1", "4", "2", "恒流放电"],
                ["2", "2", "3", "恒流充电"], ["2", "4", "4", "恒流放电"],
                ["3", "2", "5", "恒流充电"], ["3", "4", "6", "恒流放电"],
                ["3", "7", "7", "恒流充电"], ["3", "9", "8", "恒流放电"],
            ])
            write_csv(root / "data_record-1.csv", ["循环号"], [["1"], ["2"], ["3"]])
            report = audit_cycle_semantics(root, output, "synthetic", "1", 2)
            self.assertEqual(report["summary"]["cycle_count_semantics_status"], "unresolved_requires_protocol_mapping")
            self.assertEqual(report["summary"]["complete_charge_discharge_pair_count"], 4)
            self.assertEqual(report["summary"]["multi_pair_btsda_cycle_count"], 1)
            self.assertFalse(report["training_allowed_now"])

    def test_aligned_data_is_only_provisional(self):
        with tempfile.TemporaryDirectory() as tmp:
            root, output = Path(tmp) / "input", Path(tmp) / "output"
            root.mkdir()
            write_csv(root / "data_cycle-1.csv", ["循环号"], [["1"], ["2"]])
            write_csv(root / "data_step-1.csv", ["循环号", "工步号", "工步序号", "工步类型"], [
                ["1", "2", "1", "恒流充电"], ["1", "4", "2", "恒流放电"],
                ["2", "2", "3", "恒流充电"], ["2", "4", "4", "恒流放电"],
            ])
            write_csv(root / "data_record-1.csv", ["循环号"], [["1"], ["2"]])
            report = audit_cycle_semantics(root, output, "synthetic", "1", 2)
            self.assertEqual(report["summary"]["cycle_count_semantics_status"], "provisionally_aligned")
            payload = json.loads((output / "btsda_cycle_semantics_report.json").read_text(encoding="utf-8"))
            self.assertFalse(payload["training_allowed_now"])
            self.assertFalse(payload["model_performance_claimed"])


if __name__ == "__main__":
    unittest.main()
