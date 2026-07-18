import csv
import tempfile
import unittest
from pathlib import Path

from modules.feature_engineering.build_lmb_mechanistic_past_only_features import (
    build_lmb_mechanistic_past_only_features,
)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_fixture(root: Path) -> dict[str, Path]:
    features = root / "licu.csv"
    feature_rows = []
    for cell_id, event_cycle, candidate in [("26-0428-009", 2, False), ("licu-good", 9, True)]:
        for cycle in range(1, 13):
            feature_rows.append(
                {
                    "source_folder_name": cell_id,
                    "selected_dataset_name": f"{cell_id}-dataset",
                    "cycle_index": cycle,
                    "charge_capacity_mah": 10 - cycle * 0.1,
                    "discharge_capacity_mah": 9 - cycle * 0.1,
                    "coulombic_efficiency_percent": 90 + cycle * 0.1,
                    "cycle_median_voltage_v": -0.1 + cycle * 0.001,
                    "voltage_hysteresis_v": 0.2 + cycle * 0.01,
                    "end_voltage_gap_v": 0.3 + cycle * 0.01,
                    "charge_step_duration_s": 1000 + cycle,
                    "discharge_step_duration_s": 900 + cycle,
                    "incomplete_cycle_flag": cycle == event_cycle,
                    "record_voltage_mean_v": 0.1,
                }
            )
    write_csv(
        features,
        feature_rows,
        [
            "source_folder_name",
            "selected_dataset_name",
            "cycle_index",
            "charge_capacity_mah",
            "discharge_capacity_mah",
            "coulombic_efficiency_percent",
            "cycle_median_voltage_v",
            "voltage_hysteresis_v",
            "end_voltage_gap_v",
            "charge_step_duration_s",
            "discharge_step_duration_s",
            "incomplete_cycle_flag",
            "record_voltage_mean_v",
        ],
    )
    label_design = root / "label_design.csv"
    write_csv(
        label_design,
        [
            {
                "source_folder_name": "26-0428-009",
                "first_event_cycle": 2,
                "baseline_ready_export_candidate": False,
                "protocol_censored_terminal": True,
            },
            {
                "source_folder_name": "licu-good",
                "first_event_cycle": 9,
                "baseline_ready_export_candidate": True,
                "protocol_censored_terminal": True,
            },
        ],
        ["source_folder_name", "first_event_cycle", "baseline_ready_export_candidate", "protocol_censored_terminal"],
    )
    rules = root / "rules.csv"
    write_csv(
        rules,
        [{"horizon_k": 3, "training_allowed_now": False}, {"horizon_k": 5, "training_allowed_now": False}],
        ["horizon_k", "training_allowed_now"],
    )
    policy = root / "policy.csv"
    write_csv(policy, [{"field_name": "cycle_median_voltage_v"}], ["field_name"])
    return {"features": features, "label_design": label_design, "rules": rules, "policy": policy}


class LmbMechanisticPastOnlyFeatureTests(unittest.TestCase):
    def run_builder(self, root: Path) -> dict[str, object]:
        paths = build_fixture(root)
        return build_lmb_mechanistic_past_only_features(
            input_features=paths["features"],
            horizon_rule_table=paths["rules"],
            feature_policy=paths["policy"],
            label_design=paths["label_design"],
            output_root=root / "out",
            horizons=[3, 5],
            overwrite=True,
        )

    def test_horizon_3_does_not_use_recent_cycles(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_builder(root)
            rows = read_csv(root / "out" / "licu_horizon3_mechanistic_features.csv")
            row = next(item for item in rows if item["source_folder_name"] == "licu-good" and item["target_cycle"] == "8")
            self.assertEqual(row["feature_window_end"], "5")
            self.assertEqual(row["excluded_recent_window_start"], "6")
            self.assertEqual(row["excluded_recent_window_end"], "8")

    def test_horizon_5_does_not_use_t_to_t_minus_4(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_builder(root)
            rows = read_csv(root / "out" / "licu_horizon5_mechanistic_features.csv")
            row = next(item for item in rows if item["source_folder_name"] == "licu-good" and item["target_cycle"] == "10")
            self.assertEqual(row["feature_window_end"], "5")
            self.assertEqual(row["excluded_recent_window_start"], "6")
            self.assertEqual(row["excluded_recent_window_end"], "10")

    def test_direct_ce_capacity_incomplete_and_record_columns_are_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_builder(root)
            rows = read_csv(root / "out" / "licu_horizon3_mechanistic_features.csv")
            columns = set(rows[0])
            self.assertNotIn("coulombic_efficiency_percent", columns)
            self.assertNotIn("charge_capacity_mah", columns)
            self.assertNotIn("discharge_capacity_mah", columns)
            self.assertNotIn("incomplete_cycle_flag", columns)
            self.assertNotIn("record_voltage_mean_v", columns)
            self.assertIn("charge_capacity_mah_trend_past_5", columns)
            self.assertIn("discharge_capacity_mah_trend_past_5", columns)

    def test_same_signal_source_risk_annotations(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_builder(root)
            schema = read_csv(root / "out" / "mechanistic_feature_schema.csv")
            by_name = {row["field_name"]: row for row in schema}
            self.assertEqual(by_name["charge_capacity_mah_trend_past_5"]["same_signal_source_risk"], "True")
            self.assertEqual(by_name["ce_rolling_mean_window_past_5"]["same_signal_source_risk"], "True")
            self.assertEqual(by_name["voltage_hysteresis_v_trend_past_5"]["same_signal_source_risk"], "False")
            self.assertEqual(by_name["charge_step_duration_s_trend_past_5"]["same_signal_source_risk"], "False")

    def test_26_0428_009_is_not_auto_baseline_ready(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_builder(root)
            rows = read_csv(root / "out" / "licu_horizon3_mechanistic_features.csv")
            recovery_rows = [row for row in rows if row["source_folder_name"] == "26-0428-009"]
            self.assertTrue(recovery_rows)
            self.assertEqual({row["baseline_ready_export_candidate"] for row in recovery_rows}, {"False"})

    def test_report_disallows_training_and_formal_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_builder(root)
            report_text = str(report).lower()
            self.assertFalse(report["model_training_allowed"])
            self.assertFalse(report["formal_performance_metrics_computed"])
            self.assertNotIn("auc", report_text)
            self.assertNotIn("rmse", report_text)


if __name__ == "__main__":
    unittest.main()
