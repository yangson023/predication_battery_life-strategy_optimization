import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.build_lmb_full_cell_early_cycle_audit import build_audit


def write_csv(path: Path, header: list[str], rows: list[list[object]]) -> None:
    with path.open("w", encoding="gbk", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


class BuildLmbFullCellEarlyCycleAuditTest(unittest.TestCase):
    def _make_export(self, root: Path) -> None:
        write_csv(root / "data_cycle-1.csv", ["循环号"], [[1], [2], [3], [4], [5], [6]])
        write_csv(
            root / "data_step-1.csv",
            [
                "循环号", "工步号", "工步序号", "工步类型", "工步时间", "充电容量(mAh)",
                "放电容量(mAh)", "结束电压(V)", "充电中值电压(V)", "放电中值电压(V)",
            ],
            [
                [1, 2, 1, "恒流充电", "00:10:00", 2.0, "", 4.2, 3.8, ""],
                [1, 3, 2, "静置", "00:01:00", "", "", "", "", ""],
                [1, 4, 3, "恒流放电", "00:08:00", "", 1.9, 2.7, "", 3.5],
                [2, 7, 4, "恒流充电", "00:10:00", 2.1, "", 4.2, 3.9, ""],
                [2, 8, 5, "静置", "00:01:00", "", "", "", "", ""],
                [2, 9, 6, "恒流放电", "00:08:00", "", 2.0, 2.7, "", 3.6],
                [3, 7, 7, "恒流充电", "00:10:00", 2.2, "", 4.2, 3.91, ""],
                [3, 9, 8, "恒流放电", "00:08:00", "", 2.05, 2.7, "", 3.61],
                [4, 7, 9, "恒流充电", "00:10:00", 2.3, "", 4.2, 3.92, ""],
                [4, 9, 10, "恒流放电", "00:08:00", "", 2.1, 2.7, "", 3.62],
                [5, 7, 11, "恒流充电", "00:10:00", 2.4, "", 4.2, 3.93, ""],
                [5, 9, 12, "恒流放电", "00:08:00", "", 2.15, 2.7, "", 3.63],
                [6, 7, 13, "恒流充电", "00:10:00", 2.5, "", 4.2, 3.94, ""],
            ],
        )
        write_csv(
            root / "data_record-1.csv",
            ["循环号", "工步号", "电压(V)", "电流(mA)"],
            [[cycle, step, voltage, current] for cycle, step, voltage, current in [
                (1, 2, 3.8, 1.0), (1, 4, 3.5, -1.0), (2, 7, 3.9, 1.0), (2, 9, 3.6, -1.0),
                (3, 7, 3.91, 1.0), (3, 9, 3.61, -1.0), (4, 7, 3.92, 1.0), (4, 9, 3.62, -1.0),
                (5, 7, 3.93, 1.0), (5, 9, 3.63, -1.0), (6, 7, 3.94, 1.0),
            ]],
        )

    def test_pairs_active_cell_and_excludes_diagnostic_cell(self):
        with tempfile.TemporaryDirectory() as temp:
            root, output = Path(temp) / "active", Path(temp) / "output"
            root.mkdir()
            self._make_export(root)
            manifest = Path(temp) / "manifest.json"
            manifest.write_text(json.dumps({"cells": [
                {
                    "cell_id": "active", "source_folder_name": "active", "input_root": str(root), "export_suffix": "1",
                    "dataset_role": "true_lmb", "cell_scope": "lmb_full_cell", "use_status": "active_feature_audit",
                    "electrolyte_code": "LB-085", "cathode_type": "NCM811", "cathode_diameter_cm": 1.2,
                    "protocol_id": "synthetic", "termination_reason": "unknown",
                },
                {
                    "cell_id": "diagnostic", "input_root": str(root), "export_suffix": "1",
                    "dataset_role": "diagnostic_only", "cell_scope": "lmb_full_cell", "use_status": "excluded",
                },
            ]}), encoding="utf-8")
            report = build_audit(manifest, output, early_cycle_limit=4)
            pairs = read_rows(output / "lmb_full_cell_paired_cycle_audit.csv")
            unpaired = read_rows(output / "lmb_full_cell_unpaired_step_audit.csv")
            features = read_rows(output / "lmb_full_cell_early_cycle_features.csv")
            self.assertEqual(len(pairs), 5)
            self.assertEqual({row["cell_id"] for row in pairs}, {"active"})
            self.assertEqual(pairs[0]["protocol_phase"], "formation")
            self.assertEqual(pairs[1]["protocol_phase"], "long_cycle")
            self.assertEqual(unpaired[0]["reason"], "terminal_charge_without_discharge")
            self.assertFalse(report["model_training_allowed"])
            self.assertTrue(all(row["training_allowed_now"] == "False" for row in features))

    def test_rolling_features_use_only_prior_long_cycles_and_have_no_label_columns(self):
        with tempfile.TemporaryDirectory() as temp:
            root, output = Path(temp) / "active", Path(temp) / "output"
            root.mkdir()
            self._make_export(root)
            manifest = Path(temp) / "manifest.json"
            manifest.write_text(json.dumps({"cells": [{
                "cell_id": "active", "source_folder_name": "active", "input_root": str(root), "export_suffix": "1",
                "dataset_role": "true_lmb", "cell_scope": "lmb_full_cell", "use_status": "active_feature_audit",
                "electrolyte_code": "LB-085", "cathode_type": "NCM811", "cathode_diameter_cm": 1.2,
                "protocol_id": "synthetic", "termination_reason": "unknown",
            }]}), encoding="utf-8")
            build_audit(manifest, output, early_cycle_limit=4)
            features = read_rows(output / "lmb_full_cell_early_cycle_features.csv")
            by_index = {int(row["current_long_cycle_index"]): row for row in features}
            self.assertEqual(by_index[1]["discharge_capacity_lag_1_mah"], "")
            self.assertEqual(by_index[2]["discharge_capacity_lag_1_mah"], "2.0")
            self.assertAlmostEqual(float(by_index[4]["discharge_capacity_rolling_mean_past_3_mah"]), (2.0 + 2.05 + 2.1) / 3)
            lowered = " ".join(features[0].keys()).lower()
            for forbidden in ["label", "eol", "rul", "target", "future"]:
                self.assertNotIn(forbidden, lowered)


if __name__ == "__main__":
    unittest.main()
