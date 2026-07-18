import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.visualization.build_lmb_full_cell_stage_report import build_stage_report


def write_csv(path: Path, fields: list[str], rows: list[dict[str, object]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


class BuildLmbFullCellStageReportTest(unittest.TestCase):
    def test_creates_descriptive_figures_and_preserves_training_gate(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            features = root / "features.csv"
            write_csv(features, [
                "cell_id", "protocol_id", "current_long_cycle_index", "discharge_capacity_lag_1_mah",
                "coulombic_efficiency_rolling_mean_past_3_percent", "voltage_hysteresis_rolling_mean_past_3_v",
                "discharge_duration_rolling_mean_past_3_s",
            ], [
                {"cell_id": "cell-a", "protocol_id": "ncm811_li_0p98cm_charge0p2_discharge0p5_area_scaled", "current_long_cycle_index": 2, "discharge_capacity_lag_1_mah": 1.0, "coulombic_efficiency_rolling_mean_past_3_percent": "", "voltage_hysteresis_rolling_mean_past_3_v": "", "discharge_duration_rolling_mean_past_3_s": ""},
                {"cell_id": "cell-a", "protocol_id": "ncm811_li_0p98cm_charge0p2_discharge0p5_area_scaled", "current_long_cycle_index": 4, "discharge_capacity_lag_1_mah": 0.9, "coulombic_efficiency_rolling_mean_past_3_percent": 99.4, "voltage_hysteresis_rolling_mean_past_3_v": 0.11, "discharge_duration_rolling_mean_past_3_s": 3600},
                {"cell_id": "cell-b", "protocol_id": "ncm811_li_1p2cm_charge0p5_discharge0p5", "current_long_cycle_index": 4, "discharge_capacity_lag_1_mah": 1.1, "coulombic_efficiency_rolling_mean_past_3_percent": 99.1, "voltage_hysteresis_rolling_mean_past_3_v": 0.13, "discharge_duration_rolling_mean_past_3_s": 3500},
            ])
            censor = root / "censor.csv"
            write_csv(censor, ["cell_id", "protocol_id", "censoring_long_cycle_index", "event_observed"], [
                {"cell_id": "cell-a", "protocol_id": "ncm811_li_0p98cm_charge0p2_discharge0p5_area_scaled", "censoring_long_cycle_index": 10, "event_observed": "False"},
                {"cell_id": "cell-b", "protocol_id": "ncm811_li_1p2cm_charge0p5_discharge0p5", "censoring_long_cycle_index": 12, "event_observed": "False"},
            ])
            summary = root / "summary.csv"
            write_csv(summary, ["protocol_id", "feature_name"], [{"protocol_id": "p", "feature_name": "x"}])
            report = build_stage_report(features, censor, summary, root / "output")
            self.assertFalse(report["model_training_allowed"])
            self.assertFalse(report["model_performance_claimed"])
            for filename in [
                "full_cell_censoring_window_by_export.png",
                "early_cycle_capacity_ce_trajectories.png",
                "early_cycle_voltage_kinetic_trajectories.png",
                "lmb_full_cell_stage_report.html",
            ]:
                self.assertGreater((root / "output" / filename).stat().st_size, 0)
            parsed = json.loads((root / "output" / "lmb_full_cell_stage_report.json").read_text(encoding="utf-8"))
            self.assertFalse(parsed["model_training_allowed"])

    def test_rejects_observed_failure_for_censor_only_report(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            features = root / "features.csv"
            write_csv(features, ["cell_id", "protocol_id", "current_long_cycle_index"], [{"cell_id": "a", "protocol_id": "p", "current_long_cycle_index": 1}])
            censor = root / "censor.csv"
            write_csv(censor, ["cell_id", "protocol_id", "censoring_long_cycle_index", "event_observed"], [{"cell_id": "a", "protocol_id": "p", "censoring_long_cycle_index": 1, "event_observed": "True"}])
            summary = root / "summary.csv"
            write_csv(summary, ["protocol_id"], [{"protocol_id": "p"}])
            with self.assertRaises(ValueError):
                build_stage_report(features, censor, summary, root / "output")


if __name__ == "__main__":
    unittest.main()
