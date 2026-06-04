import tempfile
import unittest
from pathlib import Path

import pandas as pd

from modules.feature_engineering.build_external_battery_features import (
    build_all_features,
    build_by_cell_features,
    build_cycle_features,
    build_rpt_features,
    build_thermal_runaway_features,
    elapsed_seconds_from_relative_time,
)


class ExternalBatteryFeatureTests(unittest.TestCase):
    def test_relative_time_parser_handles_hms(self) -> None:
        self.assertAlmostEqual(elapsed_seconds_from_relative_time("1:02:03.5"), 3723.5)
        self.assertAlmostEqual(elapsed_seconds_from_relative_time("02:03.5"), 123.5)

    def test_cycle_features_group_by_cell_and_cycle(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 3,
                "dataset_family": ["multi_cell_cycle_life"] * 3,
                "data_category": ["cycling"] * 3,
                "measurement_type": ["cycle_timeseries"] * 3,
                "chemistry": ["li_ion"] * 3,
                "cell_id": ["G1C1"] * 3,
                "batch_id": ["batch_1"] * 3,
                "part_id": ["part_1"] * 3,
                "source_archive_name": ["unit.zip"] * 3,
                "archive_member_path": ["G1C1/cycling 1.csv"] * 3,
                "cycle_index": [1, 1, 1],
                "current_a": [1.0, -1.0, -1.2],
                "voltage_v": [3.8, 3.6, 3.5],
                "capacity_ah": [0.0, 0.5, 1.0],
                "energy_wh": [0.0, 1.0, 2.0],
                "relative_time_raw": ["0:00:00", "0:00:10", "0:00:20"],
                "state": ["CC_Chg", "CC_DChg", "CC_DChg"],
            }
        )

        features = build_cycle_features(frame)

        self.assertEqual(len(features), 1)
        self.assertEqual(features.loc[0, "sample_rows"], 3)
        self.assertAlmostEqual(features.loc[0, "capacity_delta_ah"], 1.0)
        self.assertAlmostEqual(features.loc[0, "duration_s"], 20.0)
        self.assertAlmostEqual(features.loc[0, "discharge_state_fraction"], 2 / 3)

    def test_rpt_features_include_voltage_drop_and_pulse_count(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 2,
                "dataset_family": ["multi_cell_cycle_life"] * 2,
                "data_category": ["cycling"] * 2,
                "measurement_type": ["rpt_diagnostic"] * 2,
                "chemistry": ["li_ion"] * 2,
                "cell_id": ["G1C1"] * 2,
                "batch_id": ["batch_1"] * 2,
                "part_id": ["part_1"] * 2,
                "source_archive_name": ["unit.zip"] * 2,
                "archive_member_path": ["G1C1/RPT 0.csv"] * 2,
                "diagnostic_part": [0, 0],
                "current_a": [0.5, -1.0],
                "voltage_v": [4.0, 3.7],
                "capacity_ah": [0.1, 0.9],
                "pulse_type": ["a", "b"],
            }
        )

        features = build_rpt_features(frame)

        self.assertEqual(len(features), 1)
        self.assertAlmostEqual(features.loc[0, "voltage_drop_v"], 0.3)
        self.assertEqual(features.loc[0, "pulse_type_count"], 2)

    def test_thermal_features_flag_safety_hint(self) -> None:
        frame = pd.DataFrame(
            {
                "dataset_id": ["unit"] * 2,
                "dataset_family": ["mechanical_thermal_runaway"] * 2,
                "data_category": ["thermal_runaway"] * 2,
                "measurement_type": ["abuse_test_timeseries"] * 2,
                "chemistry": ["li_ion"] * 2,
                "cell_id": ["cell_soc100"] * 2,
                "source_archive_name": ["unit.zip"] * 2,
                "archive_member_path": ["cell.xlsx"] * 2,
                "nominal_capacity_mah": [1500, 1500],
                "replicate_id": [1, 1],
                "soc_percent": [100, 100],
                "cell_voltage_v": [3.8, 0.5],
                "temperature_c": [25.0, 85.0],
                "penetrator_force_n": [0.0, 100.0],
            }
        )

        features = build_thermal_runaway_features(frame)

        self.assertEqual(len(features), 1)
        self.assertTrue(bool(features.loc[0, "safety_event_hint"]))
        self.assertAlmostEqual(features.loc[0, "temperature_max_c"], 85.0)

    def test_build_all_features_writes_expected_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input"
            output_root = root / "features"
            input_root.mkdir()
            pd.DataFrame(
                {
                    "dataset_id": ["unit"],
                    "dataset_family": ["multi_cell_cycle_life"],
                    "data_category": ["cycling"],
                    "measurement_type": ["cycle_timeseries"],
                    "chemistry": ["li_ion"],
                    "cell_id": ["G1C1"],
                    "source_archive_name": ["unit.zip"],
                    "archive_member_path": ["cycle.csv"],
                    "cycle_index": [1],
                    "current_a": [1.0],
                    "voltage_v": [3.7],
                    "capacity_ah": [0.1],
                }
            ).to_csv(input_root / "cycle_timeseries_sample.csv", index=False)

            summaries = build_all_features(input_root, output_root)

            self.assertTrue((output_root / "cycle_features_sample.csv").exists())
            self.assertTrue((output_root / "feature_build_summary.csv").exists())
            self.assertEqual(summaries[0].status, "written")

    def test_build_by_cell_features_combines_cell_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "by_cell"
            for cell_id in ["G1C1", "G1C2"]:
                cell_dir = input_root / cell_id
                cell_dir.mkdir(parents=True)
                pd.DataFrame(
                    {
                        "dataset_id": ["unit"],
                        "dataset_family": ["multi_cell_cycle_life"],
                        "data_category": ["cycling"],
                        "measurement_type": ["cycle_timeseries"],
                        "chemistry": ["li_ion"],
                        "cell_id": [cell_id],
                        "source_archive_name": ["unit.zip"],
                        "archive_member_path": [f"{cell_id}/cycling 1.csv"],
                        "cycle_index": [1],
                        "current_a": [1.0],
                        "voltage_v": [3.7],
                        "capacity_ah": [0.1],
                    }
                ).to_csv(cell_dir / "cycle_timeseries.csv", index=False)

            output_root = root / "features"
            summaries = build_by_cell_features(input_root, output_root)
            cycle_features = pd.read_csv(output_root / "cycle_features.csv")

            self.assertEqual(summaries[0].status, "written")
            self.assertEqual(len(cycle_features), 2)
            self.assertEqual(set(cycle_features["cell_id"]), {"G1C1", "G1C2"})


if __name__ == "__main__":
    unittest.main()
