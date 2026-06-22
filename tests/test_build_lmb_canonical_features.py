import csv
import tempfile
import unittest
from pathlib import Path

from modules.feature_engineering.build_lmb_canonical_features import build_features


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_input(root: Path, include_step_voltage: bool = True) -> tuple[Path, Path, Path]:
    cell_root = root / "cell"
    cycle_rows = [
        {
            "cycle_index": 1,
            "charge_capacity_mah": 1.2,
            "discharge_capacity_mah": 1.0,
            "coulombic_efficiency_percent": 83.3,
            "median_voltage_v": -0.11,
            "capacity_retention_percent": 100,
        },
        {
            "cycle_index": 2,
            "charge_capacity_mah": 1.1,
            "discharge_capacity_mah": 1.0,
            "coulombic_efficiency_percent": 90.9,
            "median_voltage_v": -0.10,
            "capacity_retention_percent": 100,
        },
    ]
    write_csv(
        cell_root / "normalized_cycle.csv",
        cycle_rows,
        [
            "cycle_index",
            "charge_capacity_mah",
            "discharge_capacity_mah",
            "coulombic_efficiency_percent",
            "median_voltage_v",
            "capacity_retention_percent",
        ],
    )
    if include_step_voltage:
        step_rows = [
            {
                "cycle_index": 1,
                "step_type": "constant discharge",
                "step_duration": "00:30:00",
                "charge_capacity_mah": 0,
                "discharge_capacity_mah": 1.0,
                "end_voltage_v": -0.2,
                "charge_median_voltage_v": 0,
                "discharge_median_voltage_v": -0.11,
            },
            {
                "cycle_index": 1,
                "step_type": "constant charge",
                "step_duration": "00:20:00",
                "charge_capacity_mah": 1.2,
                "discharge_capacity_mah": 0,
                "end_voltage_v": 0.2,
                "charge_median_voltage_v": 0.15,
                "discharge_median_voltage_v": 0,
            },
            {
                "cycle_index": 2,
                "step_type": "constant discharge",
                "step_duration": "00:31:00",
                "charge_capacity_mah": 0,
                "discharge_capacity_mah": 1.0,
                "end_voltage_v": -0.18,
                "charge_median_voltage_v": 0,
                "discharge_median_voltage_v": -0.10,
            },
            {
                "cycle_index": 2,
                "step_type": "constant charge",
                "step_duration": "00:21:00",
                "charge_capacity_mah": 1.1,
                "discharge_capacity_mah": 0,
                "end_voltage_v": 0.19,
                "charge_median_voltage_v": 0.14,
                "discharge_median_voltage_v": 0,
            },
        ]
        step_fields = [
            "cycle_index",
            "step_type",
            "step_duration",
            "charge_capacity_mah",
            "discharge_capacity_mah",
            "end_voltage_v",
            "charge_median_voltage_v",
            "discharge_median_voltage_v",
        ]
    else:
        step_rows = [{"cycle_index": 1, "step_type": "unknown"}]
        step_fields = ["cycle_index", "step_type"]
    write_csv(cell_root / "normalized_step.csv", step_rows, step_fields)
    write_csv(
        cell_root / "normalized_record_sample.csv",
        [{"cycle_index": 1, "voltage_v": 0.1, "current_ma": 1.0}],
        ["cycle_index", "voltage_v", "current_ma"],
    )
    manifest = root / "manifest.csv"
    write_csv(
        manifest,
        [
            {
                "source_folder_name": "synthetic-licu",
                "cell_group": "Li||Cu",
                "selected_dataset_name": "synthetic-dataset",
                "selected_output_root": str(cell_root),
            }
        ],
        ["source_folder_name", "cell_group", "selected_dataset_name", "selected_output_root"],
    )
    quality = root / "quality.csv"
    write_csv(
        quality,
        [],
        [
            "selected_dataset_name",
            "cycle_index",
            "flag_types",
            "exclude_from_label_training",
            "audit_warning_only",
            "retained_for_feature_exploration",
            "exclusion_reason",
        ],
    )
    return manifest, quality, cell_root


class LmbCanonicalFeatureVoltageEnrichmentTests(unittest.TestCase):
    def test_licu_rows_include_cycle_median_voltage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, quality, _ = build_input(root)
            build_features(manifest, quality, root / "out", overwrite=True)
            rows = read_csv(root / "out" / "licu_cycle_features.csv")

            self.assertIn("cycle_median_voltage_v", rows[0])
            self.assertEqual(rows[0]["cycle_median_voltage_v"], "-0.11")

    def test_step_aggregation_generates_voltage_hysteresis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, quality, _ = build_input(root)
            build_features(manifest, quality, root / "out", overwrite=True)
            rows = read_csv(root / "out" / "licu_cycle_features.csv")

            self.assertIn("voltage_hysteresis_v", rows[0])
            self.assertAlmostEqual(float(rows[0]["voltage_hysteresis_v"]), 0.26)
            self.assertEqual(rows[0]["charge_step_duration_s"], "1200.0")
            self.assertEqual(rows[0]["discharge_step_duration_s"], "1800.0")

    def test_missing_step_fields_do_not_crash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, quality, _ = build_input(root, include_step_voltage=False)
            report = build_features(manifest, quality, root / "out", overwrite=True)
            rows = read_csv(root / "out" / "licu_cycle_features.csv")

            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["voltage_hysteresis_v"], "")
            self.assertFalse(report["model_training_allowed"])

    def test_sparse_record_sample_does_not_block_feature_build(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, quality, _ = build_input(root)
            build_features(manifest, quality, root / "out", overwrite=True)
            rows = read_csv(root / "out" / "licu_cycle_features.csv")

            self.assertNotEqual(rows[0]["record_voltage_mean_v"], "")
            self.assertEqual(rows[1]["record_voltage_mean_v"], "")
            self.assertNotEqual(rows[1]["cycle_median_voltage_v"], "")

    def test_report_keeps_training_disallowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest, quality, _ = build_input(root)
            report = build_features(manifest, quality, root / "out", overwrite=True)
            checks = read_csv(root / "out" / "feature_schema_check.csv")
            check_names = {row["check_name"] for row in checks}

            self.assertFalse(report["training_allowed_now"])
            self.assertFalse(report["model_training_allowed"])
            self.assertIn("licu_voltage_enrichment_fields_present", check_names)


if __name__ == "__main__":
    unittest.main()
