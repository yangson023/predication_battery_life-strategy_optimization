import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pandas as pd

from modules.feature_engineering.build_external_battery_features_low_memory import (
    NumericAccumulator,
    build_all_features_low_memory,
    build_by_cell_features_low_memory,
)


class LowMemoryExternalBatteryFeatureTests(unittest.TestCase):
    def write_synthetic_cell(self, cell_dir: Path) -> None:
        cell_dir.mkdir(parents=True)
        pd.DataFrame(
            {
                "dataset_id": ["unit"] * 5,
                "dataset_family": ["multi_cell_cycle_life"] * 5,
                "data_category": ["cycling"] * 5,
                "measurement_type": ["cycle_timeseries"] * 5,
                "chemistry": ["li_ion"] * 5,
                "cell_id": ["G1C1"] * 5,
                "batch_id": ["batch_1"] * 5,
                "part_id": ["part_1"] * 5,
                "source_archive_name": ["unit.zip"] * 5,
                "archive_member_path": ["G1C1/cycling.csv"] * 5,
                "cycle_index": [1, 1, 1, 2, 2],
                "current_a": [1.0, -1.0, -1.2, 0.5, -0.5],
                "voltage_v": [3.8, 3.6, 3.5, 3.9, 3.7],
                "capacity_ah": [0.0, 0.5, 1.0, 0.2, 0.8],
                "energy_wh": [0.0, 1.0, 2.0, 0.5, 1.5],
                "relative_time_raw": ["0:00:00", "0:00:10", "0:00:20", "0:00:00", "0:00:30"],
                "state": ["CC_Chg", "CC_DChg", "CC_DChg", "CC_Chg", "CC_DChg"],
            }
        ).to_csv(cell_dir / "cycle_timeseries.csv", index=False)

        pd.DataFrame(
            {
                "dataset_id": ["unit"] * 3,
                "dataset_family": ["multi_cell_cycle_life"] * 3,
                "data_category": ["cycling"] * 3,
                "measurement_type": ["rpt_diagnostic"] * 3,
                "chemistry": ["li_ion"] * 3,
                "cell_id": ["G1C1"] * 3,
                "batch_id": ["batch_1"] * 3,
                "part_id": ["part_1"] * 3,
                "source_archive_name": ["unit.zip"] * 3,
                "archive_member_path": ["G1C1/rpt.csv"] * 3,
                "diagnostic_part": [0, 0, 0],
                "current_a": [0.5, -1.0, -1.2],
                "voltage_v": [4.0, 3.8, 3.7],
                "capacity_ah": [0.1, 0.5, 0.9],
                "energy_wh": [0.2, 0.9, 1.4],
                "pulse_soc": [10, 20, 20],
                "pulse_type": ["a", "b", "b"],
            }
        ).to_csv(cell_dir / "rpt_diagnostic.csv", index=False)

    def test_numeric_accumulator_tracks_first_last_and_missingness(self) -> None:
        accumulator = NumericAccumulator()
        accumulator.update(pd.Series([1.0, None]))
        accumulator.update(pd.Series([3.0]))

        self.assertEqual(accumulator.valid_count, 2)
        self.assertEqual(accumulator.missing_count, 1)
        self.assertAlmostEqual(accumulator.first, 1.0)
        self.assertAlmostEqual(accumulator.last, 3.0)
        self.assertAlmostEqual(accumulator.mean, 2.0)
        self.assertAlmostEqual(accumulator.minimum, 1.0)
        self.assertAlmostEqual(accumulator.maximum, 3.0)
        self.assertAlmostEqual(accumulator.missing_fraction, 1 / 3)

    def test_low_memory_builder_outputs_expected_tables_with_tiny_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "by_cell"
            output_root = root / "features"
            self.write_synthetic_cell(input_root / "G1C1")

            summaries = build_by_cell_features_low_memory(
                input_root=input_root,
                output_root=output_root,
                chunksize=2,
            )

            cycle_features = pd.read_csv(output_root / "cycle_features.csv")
            rpt_features = pd.read_csv(output_root / "rpt_features.csv")
            schema_check = pd.read_csv(output_root / "feature_schema_check.csv")

            self.assertEqual([summary.status for summary in summaries], ["written", "written"])
            self.assertEqual(len(cycle_features), 2)
            self.assertEqual(len(rpt_features), 1)
            self.assertTrue((output_root / "feature_build_report.json").exists())
            self.assertTrue((output_root / "protocol_regime_summary.csv").exists())
            self.assertEqual(set(schema_check["status"]), {"pass"})

            cycle_1 = cycle_features.loc[cycle_features["cycle_index"] == 1].iloc[0]
            self.assertEqual(cycle_1["sample_rows"], 3)
            self.assertAlmostEqual(cycle_1["duration_s"], 20.0)
            self.assertAlmostEqual(cycle_1["current_a_last"], -1.2)
            self.assertAlmostEqual(cycle_1["current_a_mean"], -0.4)
            self.assertAlmostEqual(cycle_1["current_a_min"], -1.2)
            self.assertAlmostEqual(cycle_1["current_a_max"], 1.0)
            self.assertAlmostEqual(cycle_1["capacity_delta_ah"], 1.0)
            self.assertAlmostEqual(cycle_1["charge_state_fraction"], 1 / 3)
            self.assertAlmostEqual(cycle_1["discharge_state_fraction"], 2 / 3)

            rpt = rpt_features.iloc[0]
            self.assertEqual(rpt["sample_rows"], 3)
            self.assertAlmostEqual(rpt["voltage_drop_v"], 0.3)
            self.assertEqual(rpt["pulse_type_count"], 2)

    def test_chunk_processing_does_not_require_concat_of_raw_chunks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "by_cell"
            output_root = root / "features"
            self.write_synthetic_cell(input_root / "G1C1")

            with patch(
                "modules.feature_engineering.build_external_battery_features_low_memory.pd.concat",
                side_effect=AssertionError("raw chunks must not be concatenated"),
            ):
                build_by_cell_features_low_memory(input_root, output_root, chunksize=1)

            self.assertTrue((output_root / "cycle_features.csv").exists())

    def test_output_root_requires_overwrite_when_not_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "by_cell"
            output_root = root / "features"
            output_root.mkdir()
            (output_root / "existing.txt").write_text("keep", encoding="utf-8")
            self.write_synthetic_cell(input_root / "G1C1")

            with self.assertRaises(FileExistsError):
                build_by_cell_features_low_memory(input_root, output_root, chunksize=2)

            summaries = build_by_cell_features_low_memory(
                input_root,
                output_root,
                chunksize=2,
                overwrite=True,
            )
            self.assertEqual(summaries[0].status, "written")
            self.assertFalse((output_root / "existing.txt").exists())

    def test_build_all_rejects_non_by_cell_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                build_all_features_low_memory(
                    input_root=Path(tmp) / "input",
                    output_root=Path(tmp) / "output",
                    source_mode="sample",
                )


if __name__ == "__main__":
    unittest.main()
