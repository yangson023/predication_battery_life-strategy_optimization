import json
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

import pandas as pd

from modules.data_pipeline.extract_external_battery_by_cell import (
    extract_by_cell,
    natural_cell_sort_key,
    selected_rows_by_cell,
    slugify_cell_id,
)


class ExtractExternalBatteryByCellTests(unittest.TestCase):
    def test_slugify_cell_id_keeps_simple_ids(self) -> None:
        self.assertEqual(slugify_cell_id("G3C1"), "G3C1")
        self.assertEqual(slugify_cell_id("cell 01/soc 80"), "cell_01_soc_80")

    def test_natural_cell_sort_orders_numeric_ids(self) -> None:
        cells = ["G11C1", "G1C2", "G1C1"]

        self.assertEqual(sorted(cells, key=natural_cell_sort_key), ["G1C1", "G1C2", "G11C1"])

    def test_selects_limited_members_per_cell_and_type(self) -> None:
        rows = [
            {"cell_id": "G1C1", "measurement_type": "cycle_timeseries", "file_extension": ".csv", "cycle_index": "2"},
            {"cell_id": "G1C1", "measurement_type": "cycle_timeseries", "file_extension": ".csv", "cycle_index": "1"},
            {"cell_id": "G1C1", "measurement_type": "rpt_diagnostic", "file_extension": ".csv", "diagnostic_part": "0"},
            {"cell_id": "G1C2", "measurement_type": "cycle_timeseries", "file_extension": ".csv", "cycle_index": "1"},
        ]

        selected = selected_rows_by_cell(
            inventory_rows=rows,
            measurement_types=["cycle_timeseries", "rpt_diagnostic"],
            requested_cells=["G1C1"],
            max_cells=0,
            max_members_per_cell_type=1,
        )

        self.assertEqual(len(selected), 2)
        self.assertEqual({row["measurement_type"] for row in selected}, {"cycle_timeseries", "rpt_diagnostic"})

    def test_default_selection_anchors_on_cycle_cells(self) -> None:
        rows = [
            {"cell_id": "cell_02", "measurement_type": "rpt_diagnostic", "file_extension": ".csv"},
            {"cell_id": "G1C1", "measurement_type": "cycle_timeseries", "file_extension": ".csv", "cycle_index": "1"},
            {"cell_id": "G1C1", "measurement_type": "rpt_diagnostic", "file_extension": ".csv", "diagnostic_part": "0"},
        ]

        selected = selected_rows_by_cell(
            inventory_rows=rows,
            measurement_types=["cycle_timeseries", "rpt_diagnostic"],
            requested_cells=[],
            max_cells=1,
            max_members_per_cell_type=0,
        )

        self.assertEqual({row["cell_id"] for row in selected}, {"G1C1"})

    def test_extracts_per_cell_outputs_from_zip(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "Batch 1 Part 1.zip"
            cycle_member = "Batch 1 Part 1/G3C1/cycling 1.csv"
            rpt_member = "Batch 1 Part 1/G3C1/RPT 0.csv"
            with ZipFile(archive, "w") as zf:
                zf.writestr(cycle_member, "Record number,Cycle,Current(A),Voltage(V)\n1,1,1.0,3.7\n")
                zf.writestr(rpt_member, "Record number,Current(A),Voltage(V)\n1,0.0,3.8\n")

            inventory = root / "file_inventory.csv"
            pd.DataFrame(
                [
                    {
                        "dataset_id": "unit_batch",
                        "dataset_family": "multi_cell_cycle_life",
                        "data_category": "cycling",
                        "chemistry": "li_ion",
                        "source_archive_name": archive.name,
                        "archive_member_path": cycle_member,
                        "file_extension": ".csv",
                        "cell_id": "G3C1",
                        "batch_id": "batch_1",
                        "part_id": "part_1",
                        "measurement_type": "cycle_timeseries",
                        "cycle_index": "1",
                        "diagnostic_part": "",
                    },
                    {
                        "dataset_id": "unit_batch",
                        "dataset_family": "multi_cell_cycle_life",
                        "data_category": "cycling",
                        "chemistry": "li_ion",
                        "source_archive_name": archive.name,
                        "archive_member_path": rpt_member,
                        "file_extension": ".csv",
                        "cell_id": "G3C1",
                        "batch_id": "batch_1",
                        "part_id": "part_1",
                        "measurement_type": "rpt_diagnostic",
                        "cycle_index": "",
                        "diagnostic_part": "0",
                    },
                ]
            ).to_csv(inventory, index=False)

            manifest = root / "external_battery_archives.csv"
            pd.DataFrame(
                [{"source_archive_name": archive.name, "source_archive_path": str(archive)}]
            ).to_csv(manifest, index=False)

            schema = root / "schema.json"
            schema.write_text(
                json.dumps(
                    {
                        "column_aliases": {
                            "Record number": "record_number",
                            "Current(A)": "current_a",
                            "Voltage(V)": "voltage_v",
                            "Cycle": "cycle_index",
                        }
                    }
                ),
                encoding="utf-8",
            )

            summary = extract_by_cell(
                inventory_path=inventory,
                archive_manifest_path=manifest,
                schema_map_path=schema,
                output_root=root / "by_cell",
                measurement_types=["cycle_timeseries", "rpt_diagnostic"],
                cell_ids=["G3C1"],
                max_cells=0,
                max_members_per_cell_type=0,
                rows_per_member=10,
            )

            self.assertEqual(len(summary), 2)
            self.assertTrue((root / "by_cell" / "G3C1" / "cycle_timeseries.csv").exists())
            self.assertTrue((root / "by_cell" / "G3C1" / "rpt_diagnostic.csv").exists())
            cycle = pd.read_csv(root / "by_cell" / "G3C1" / "cycle_timeseries.csv")
            self.assertEqual(cycle.loc[0, "cell_id"], "G3C1")
            self.assertIn("current_a", cycle.columns)


if __name__ == "__main__":
    unittest.main()
