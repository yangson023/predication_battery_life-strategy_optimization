import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile

from modules.data_pipeline.organize_external_battery_archives import (
    classify_archive,
    is_data_member,
    organize_archive,
    parse_member_metadata,
    write_outputs,
)


class ExternalBatteryArchiveTests(unittest.TestCase):
    def test_classifies_cycle_life_archive(self) -> None:
        result = classify_archive(
            Path("Batch 1 Part 1.zip"),
            ["Batch 1 Part 1/G3C1/cycling 21.csv"],
        )

        self.assertEqual(result, ("multi_cell_cycle_life", "cycle_life", "cycling", "li_ion"))

    def test_parses_cycle_member_metadata(self) -> None:
        metadata = parse_member_metadata(
            "Batch 2 Part 3.zip",
            "Batch 2 Part 3/G16C2/cycling 42.csv",
            "cycling",
        )

        self.assertEqual(metadata["batch_id"], "batch_2")
        self.assertEqual(metadata["part_id"], "part_3")
        self.assertEqual(metadata["cell_id"], "G16C2")
        self.assertEqual(metadata["cycle_index"], "42")

    def test_parses_batch_rpt_member_metadata(self) -> None:
        metadata = parse_member_metadata(
            "Batch 1 Part 1.zip",
            "Batch 1 Part 1/G3C1/RPT 22.csv",
            "cycling",
        )

        self.assertEqual(metadata["cell_id"], "G3C1")
        self.assertEqual(metadata["measurement_type"], "rpt_diagnostic")
        self.assertEqual(metadata["diagnostic_part"], "22")

    def test_skips_macos_resource_members(self) -> None:
        self.assertFalse(is_data_member("__MACOSX/Batch 1 Part 1/G3C1/._cycling 21.csv"))
        self.assertFalse(is_data_member("Batch 1 Part 1/G3C1/._cycling 21.csv"))
        self.assertTrue(is_data_member("Batch 1 Part 1/G3C1/cycling 21.csv"))

    def test_parses_rpt_and_thermal_metadata(self) -> None:
        rpt = parse_member_metadata(
            "rpt_data.zip",
            "rpt_data/rpt_cell_02_part1.csv",
            "rpt",
        )
        thermal = parse_member_metadata(
            "Mechanically Induced Thermal Runaway for Li-ion Batteries.zip",
            "Mechanically Induced Thermal Runaway for Li-ion Batteries/excel/1500mAh2-80S0C.xlsx",
            "thermal_runaway",
        )

        self.assertEqual(rpt["cell_id"], "cell_02")
        self.assertEqual(rpt["diagnostic_part"], "1")
        self.assertEqual(thermal["nominal_capacity_mah"], "1500")
        self.assertEqual(thermal["replicate_id"], "2")
        self.assertEqual(thermal["soc_percent"], "80")

    def test_parses_flexible_thermal_metadata(self) -> None:
        metadata = parse_member_metadata(
            "Mechanically Induced Thermal Runaway for Li-ion Batteries.zip",
            "Mechanically Induced Thermal Runaway for Li-ion Batteries/excel/ChevyVolt-80SOC-6mm-cell4.xlsx",
            "thermal_runaway",
        )

        self.assertEqual(metadata["cell_id"], "chevyvolt_cell4_soc80")
        self.assertEqual(metadata["replicate_id"], "4")
        self.assertEqual(metadata["soc_percent"], "80")

    def test_parses_underscore_thermal_metadata(self) -> None:
        metadata = parse_member_metadata(
            "Mechanically Induced Thermal Runaway for Li-ion Batteries.zip",
            "Mechanically Induced Thermal Runaway for Li-ion Batteries/excel/LCO_4Ah_100SOC_cell1_MAX.xlsx",
            "thermal_runaway",
        )

        self.assertEqual(metadata["cell_id"], "lco_4ah_cell1_soc100")
        self.assertEqual(metadata["nominal_capacity_mah"], "4000")
        self.assertEqual(metadata["replicate_id"], "1")
        self.assertEqual(metadata["soc_percent"], "100")

    def test_writes_inventory_outputs_without_copying_archive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "Batch 1 Part 1.zip"
            with ZipFile(archive, "w") as zf:
                zf.writestr("Batch 1 Part 1/G3C1/cycling 1.csv", "time_s,voltage_v\n0,3.7\n")

            manifest, inventory = organize_archive(
                archive_path=archive,
                project_root=root,
                raw_root=root / "data" / "raw" / "external_battery_datasets",
                copy_archives=False,
                header_bytes=256,
                generated_at="2026-06-03T00:00:00+00:00",
            )
            write_outputs(root, root / "data" / "processed" / "external_battery_datasets", [manifest], inventory)

            self.assertFalse(manifest.archive_copied)
            self.assertEqual(len(inventory), 1)
            self.assertEqual(inventory[0].header_preview, "time_s,voltage_v")
            self.assertTrue((root / "data" / "processed" / "external_battery_datasets" / "file_inventory.csv").exists())
            self.assertTrue((root / "data" / "processed" / "external_battery_datasets" / "measurement_summary.csv").exists())
            self.assertTrue((root / "configs" / "datasets" / "external_battery_archives.csv").exists())


if __name__ == "__main__":
    unittest.main()
