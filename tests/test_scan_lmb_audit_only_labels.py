import csv
import tempfile
import unittest
from pathlib import Path

from modules.feature_engineering.scan_lmb_audit_only_labels import scan_lmb_audit_only_labels


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys()) if rows else []
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class LmbAuditOnlyLabelScanTests(unittest.TestCase):
    def write_feature_tables(self, root: Path) -> None:
        licu_rows = []
        ce_values = [100, 100, 100, 100, 100, 40, 40]
        for index, ce in enumerate(ce_values, start=1):
            licu_rows.append(
                {
                    "source_folder_name": "licu_cell",
                    "selected_dataset_name": "licu_dataset",
                    "cycle_index": index,
                    "charge_capacity_mah": 1.0,
                    "discharge_capacity_mah": 1.0 if index != 7 else 0.0,
                    "coulombic_efficiency_percent": ce,
                    "ce_rolling_std_past_5": 0.5,
                    "incomplete_cycle_flag": "False",
                    "ce_warning_flag": "False",
                    "exclude_from_label_training": "False",
                }
            )
        lili_rows = []
        for index in range(1, 8):
            lili_rows.append(
                {
                    "source_folder_name": "lili_cell",
                    "selected_dataset_name": "lili_dataset",
                    "cycle_index": index,
                    "voltage_hysteresis_v": 0.1 if index < 6 else 0.5,
                    "end_voltage_gap_v": 0.1,
                    "hysteresis_rolling_mean_past_5": "" if index < 6 else 0.5,
                    "hysteresis_slope_past_10": "" if index < 6 else 0.01,
                    "rest_voltage_drop_mv_per_hour": 0 if index < 7 else 60,
                    "voltage_instability_warning": "False",
                    "incomplete_cycle_warning": "False",
                    "record_voltage_std_v": 0.01,
                }
            )
        write_csv(root / "licu_cycle_features.csv", licu_rows)
        write_csv(root / "lili_cycle_features.csv", lili_rows)

    def test_scan_outputs_are_audit_only_and_not_trainable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "features"
            out = Path(tmp) / "out"
            self.write_feature_tables(root)

            report = scan_lmb_audit_only_labels(root, out)

            self.assertFalse(report["training_allowed_now"])
            rows = read_csv(out / "lmb_audit_event_scan.csv")
            self.assertTrue(rows)
            self.assertEqual({row["trainable_label"] for row in rows}, {"False"})
            self.assertEqual({row["audit_only"] for row in rows}, {"True"})

    def test_ce_collapse_uses_future_window_not_current_cycle_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "features"
            out = Path(tmp) / "out"
            self.write_feature_tables(root)

            scan_lmb_audit_only_labels(root, out, future_window=2)
            rows = read_csv(out / "lmb_audit_event_scan.csv")
            ce_rows = [
                row for row in rows if row["label_key"] == "ce_collapse" and row["source_folder_name"] == "licu_cell"
            ]
            cycle_4 = next(row for row in ce_rows if row["cycle_index"] == "4")
            cycle_7 = next(row for row in ce_rows if row["cycle_index"] == "7")

            self.assertEqual(cycle_4["observed_candidate"], "True")
            self.assertEqual(cycle_4["signal_value"], "40.0")
            self.assertEqual(cycle_7["observed_candidate"], "False")
            self.assertEqual(cycle_7["limited_window_label"], "True")

    def test_lili_voltage_audit_signals_are_detected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "features"
            out = Path(tmp) / "out"
            self.write_feature_tables(root)

            scan_lmb_audit_only_labels(root, out)
            rows = read_csv(out / "lmb_audit_event_scan.csv")
            polarization_rows = [
                row for row in rows if row["label_key"] == "polarization_growth" and row["observed_candidate"] == "True"
            ]
            soft_short_rows = [
                row for row in rows if row["label_key"] == "soft_short_warning" and row["observed_candidate"] == "True"
            ]

            self.assertTrue(polarization_rows)
            self.assertTrue(soft_short_rows)

    def test_schema_check_blocks_training_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "features"
            out = Path(tmp) / "out"
            self.write_feature_tables(root)

            scan_lmb_audit_only_labels(root, out)
            checks = read_csv(out / "audit_label_schema_check.csv")
            check_by_name = {row["check"]: row["status"] for row in checks}

            self.assertEqual(check_by_name["trainable_label_always_false"], "pass")
            self.assertEqual(check_by_name["no_forbidden_training_columns"], "pass")


if __name__ == "__main__":
    unittest.main()
