import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from modules.data_pipeline.extract_external_battery_tables import (
    extract_tables,
    normalize_column_name,
    select_inventory_rows,
)


class ExtractExternalBatteryTablesTests(unittest.TestCase):
    def test_normalizes_alias_and_unmapped_columns(self) -> None:
        aliases = {"Current(A)": "current_a", "Voltage (V)": "voltage_v"}

        self.assertEqual(normalize_column_name("Current(A)", aliases), "current_a")
        self.assertEqual(normalize_column_name("Voltage (V)", aliases), "voltage_v")
        self.assertEqual(normalize_column_name("Pulse SOC", {}), "pulse_soc")

    def test_selects_limited_rows_by_measurement_type(self) -> None:
        rows = [
            {"measurement_type": "cycle_timeseries", "source_archive_name": "b.zip", "cell_id": "G1C1", "cycle_index": "2"},
            {"measurement_type": "cycle_timeseries", "source_archive_name": "a.zip", "cell_id": "G1C1", "cycle_index": "1"},
            {"measurement_type": "rpt_diagnostic", "source_archive_name": "a.zip", "cell_id": "G1C1", "diagnostic_part": "0"},
        ]

        selected = select_inventory_rows(rows, ["cycle_timeseries"], max_members_per_type=1)

        self.assertEqual(len(selected), 1)
        self.assertEqual(selected[0]["source_archive_name"], "a.zip")

    def test_extracts_normalized_csv_sample_from_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "Batch 1 Part 1.zip"
            member = "Batch 1 Part 1/G3C1/cycling 1.csv"
            with ZipFile(archive, "w") as zf:
                zf.writestr(
                    member,
                    "Record number,State,Cycle,Current(A),Voltage(V),Capacity(Ah)\n"
                    "1,CC_Chg,1,1.5,3.7,0.1\n"
                    "2,CC_DChg,1,-1.5,3.6,0.2\n",
                )

            inventory = root / "file_inventory.csv"
            pd.DataFrame(
                [
                    {
                        "dataset_id": "unit_batch",
                        "dataset_family": "multi_cell_cycle_life",
                        "data_category": "cycling",
                        "chemistry": "li_ion",
                        "source_archive_name": archive.name,
                        "archive_member_path": member,
                        "normalized_member_path": member,
                        "file_extension": ".csv",
                        "compressed_size_bytes": 1,
                        "uncompressed_size_bytes": 1,
                        "cell_id": "G3C1",
                        "batch_id": "batch_1",
                        "part_id": "part_1",
                        "measurement_type": "cycle_timeseries",
                        "cycle_index": "1",
                        "diagnostic_part": "",
                        "nominal_capacity_mah": "",
                        "replicate_id": "",
                        "soc_percent": "",
                        "header_preview": "",
                        "notes": "",
                    }
                ]
            ).to_csv(inventory, index=False)

            manifest = root / "external_battery_archives.csv"
            pd.DataFrame(
                [
                    {
                        "source_archive_name": archive.name,
                        "source_archive_path": str(archive),
                    }
                ]
            ).to_csv(manifest, index=False)

            schema = root / "schema.json"
            schema.write_text(
                json.dumps(
                    {
                        "column_aliases": {
                            "Record number": "record_number",
                            "Current(A)": "current_a",
                            "Voltage(V)": "voltage_v",
                            "Capacity(Ah)": "capacity_ah",
                            "Cycle": "cycle_index",
                            "State": "state",
                        }
                    }
                ),
                encoding="utf-8",
            )

            output_dir = root / "extracted"
            summary = extract_tables(
                inventory_path=inventory,
                archive_manifest_path=manifest,
                schema_map_path=schema,
                output_dir=output_dir,
                measurement_types=["cycle_timeseries"],
                max_members_per_type=1,
                rows_per_member=10,
                write_parquet=False,
            )

            output = pd.read_csv(output_dir / "cycle_timeseries_sample.csv")
            self.assertEqual(summary[0].status, "written")
            self.assertEqual(len(output), 2)
            self.assertIn("current_a", output.columns)
            self.assertIn("voltage_v", output.columns)
            self.assertEqual(output.loc[0, "cell_id"], "G3C1")


if __name__ == "__main__":
    unittest.main()
