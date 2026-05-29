import tempfile
import unittest
from pathlib import Path

import pandas as pd

from modules.data_pipeline.quality_and_parquet import (
    count_capacity_jump_warnings,
    count_time_monotonic_failures,
    load_metadata,
    summarize_csv,
)


class QualityReportTests(unittest.TestCase):
    def test_time_monotonic_failures_are_counted_by_cycle(self) -> None:
        frame = pd.DataFrame(
            {
                "cycle_index": [1, 1, 1, 2, 2],
                "elapsed_time_s": [0, 1, 0.5, 0, 1],
            }
        )

        self.assertEqual(count_time_monotonic_failures(frame), 1)

    def test_capacity_jump_warning_uses_relative_threshold(self) -> None:
        frame = pd.DataFrame(
            {
                "cycle_type": ["discharge"] * 3,
                "cycle_index": [1, 2, 3],
                "capacity_ah": [2.0, 1.98, 1.70],
            }
        )

        self.assertEqual(count_capacity_jump_warnings(frame, 0.05), 1)

    def test_metadata_requires_core_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "metadata.csv"
            pd.DataFrame(
                {
                    "dataset": ["nasa"],
                    "battery_type": ["li_ion"],
                    "cell_id": ["BTEST"],
                    "discharge_cutoff_voltage_v": [2.5],
                }
            ).to_csv(path, index=False)

            metadata = load_metadata(path)
            self.assertEqual(metadata.loc[0, "cell_id"], "BTEST")

    def test_csv_summary_flags_voltage_out_of_range(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            csv_path = root / "sample.csv"
            pd.DataFrame(
                {
                    "cycle_index": [1, 1],
                    "elapsed_time_s": [0, 1],
                    "voltage_measured_v": [3.7, 9.9],
                }
            ).to_csv(csv_path, index=False)

            report = summarize_csv(
                csv_path=csv_path,
                root=root,
                dataset="unit",
                battery_type="li_ion",
                cell_id="BTEST",
                has_parquet_engine=False,
                capacity_jump_threshold=0.05,
            )

            self.assertEqual(report.voltage_out_of_range, 1)
            self.assertEqual(report.status, "warn")
            self.assertEqual(report.parquet_status, "skipped_no_engine")


if __name__ == "__main__":
    unittest.main()
