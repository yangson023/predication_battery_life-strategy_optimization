import csv
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.export_lmb_baseline_ready_dataset import export_lmb_baseline_ready_dataset


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def fixture(root: Path) -> dict[str, Path]:
    design = root / "design.csv"
    write_csv(
        design,
        [
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "licu-good",
                "selected_dataset_name": "licu-good-ds",
                "label_key": "incomplete_capacity_event",
                "first_event_cycle": "12",
                "last_cycle_index": "20",
                "pre_event_cycle_count": "11",
                "post_event_cycle_count": "8",
                "protocol_censored_terminal": "True",
                "baseline_ready_export_candidate": "True",
            },
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "26-0428-009",
                "selected_dataset_name": "early-ds",
                "label_key": "incomplete_capacity_event",
                "first_event_cycle": "2",
                "last_cycle_index": "20",
                "pre_event_cycle_count": "1",
                "post_event_cycle_count": "18",
                "protocol_censored_terminal": "True",
                "baseline_ready_export_candidate": "False",
            },
            {
                "cell_group": "Li||Li",
                "source_folder_name": "lili-1",
                "selected_dataset_name": "lili-ds",
                "label_key": "incomplete_capacity_event",
                "first_event_cycle": "10",
                "last_cycle_index": "20",
                "pre_event_cycle_count": "9",
                "post_event_cycle_count": "10",
                "protocol_censored_terminal": "True",
                "baseline_ready_export_candidate": "True",
            },
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "licu-good",
                "selected_dataset_name": "licu-good-ds",
                "label_key": "ce_instability",
                "first_event_cycle": "3",
                "last_cycle_index": "20",
                "pre_event_cycle_count": "2",
                "post_event_cycle_count": "17",
                "protocol_censored_terminal": "True",
                "baseline_ready_export_candidate": "True",
            },
        ],
        [
            "cell_group",
            "source_folder_name",
            "selected_dataset_name",
            "label_key",
            "first_event_cycle",
            "last_cycle_index",
            "pre_event_cycle_count",
            "post_event_cycle_count",
            "protocol_censored_terminal",
            "baseline_ready_export_candidate",
        ],
    )
    excluded = root / "excluded_columns.csv"
    write_csv(
        excluded,
        [
            {
                "feature_column": "charge_capacity_mah",
                "present_in_licu_features": "True",
                "exclusion_reason": "leakage",
                "exclusion_stage": "before_baseline_ready_export",
            }
        ],
        ["feature_column", "present_in_licu_features", "exclusion_reason", "exclusion_stage"],
    )
    features = root / "features.csv"
    rows = []
    for cell_id, dataset in [("licu-good", "licu-good-ds"), ("26-0428-009", "early-ds")]:
        for cycle in range(1, 21):
            rows.append(
                {
                    "source_folder_name": cell_id,
                    "selected_dataset_name": dataset,
                    "cycle_index": cycle,
                    "charge_capacity_mah": 1.0,
                    "discharge_capacity_mah": 1.0,
                    "coulombic_efficiency_percent": 100,
                    "irreversible_capacity_mah": 0,
                    "incomplete_cycle_flag": "False",
                    "ce_warning_flag": "False",
                    "capacity_retention_percent": 100,
                    "exclude_from_label_training": "False",
                    "audit_warning_only": "False",
                    "record_sample_limited": "True",
                    "record_voltage_mean_v": 0.1,
                    "record_current_std_ma": 0.2,
                    "ce_lag_1": 99.9,
                    "ce_rolling_mean_past_5": 99.8,
                    "cumulative_irreversible_capacity_past": 0.1,
                    "cumulative_discharge_throughput_mah": 1.2,
                    "future_signal": 0,
                }
            )
    write_csv(
        features,
        rows,
        [
            "source_folder_name",
            "selected_dataset_name",
            "cycle_index",
            "charge_capacity_mah",
            "discharge_capacity_mah",
            "coulombic_efficiency_percent",
            "irreversible_capacity_mah",
            "incomplete_cycle_flag",
            "ce_warning_flag",
            "capacity_retention_percent",
            "exclude_from_label_training",
            "audit_warning_only",
            "record_sample_limited",
            "record_voltage_mean_v",
            "record_current_std_ma",
            "ce_lag_1",
            "ce_rolling_mean_past_5",
            "cumulative_irreversible_capacity_past",
            "cumulative_discharge_throughput_mah",
            "future_signal",
        ],
    )
    metadata = root / "metadata.csv"
    write_csv(
        metadata,
        [
            {
                "电池编号": "licu-good",
                "cell_group": "Li||Cu",
                "metadata_gate_status": "metadata_ready_for_label_audit",
                "termination_interpretation": "protocol_censored",
                "training_allowed_now": "False",
            },
            {
                "电池编号": "26-0428-009",
                "cell_group": "Li||Cu",
                "metadata_gate_status": "metadata_ready_for_label_audit",
                "termination_interpretation": "protocol_censored",
                "training_allowed_now": "False",
            },
        ],
        ["电池编号", "cell_group", "metadata_gate_status", "termination_interpretation", "training_allowed_now"],
    )
    return {"design": design, "excluded": excluded, "features": features, "metadata": metadata}


class LmbBaselineReadyExportTests(unittest.TestCase):
    def run_export(self, root: Path) -> dict[str, object]:
        paths = fixture(root)
        return export_lmb_baseline_ready_dataset(
            label_design=paths["design"],
            excluded_feature_columns=paths["excluded"],
            licu_features=paths["features"],
            metadata_gate=paths["metadata"],
            output_root=root / "out",
        )

    def test_only_candidate_licu_cells_are_exported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_export(root)

            self.assertEqual(report["exported_cells"], ["licu-good"])
            self.assertIn("26-0428-009", report["excluded_cells"])

    def test_event_cycle_and_post_event_rows_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_export(root)
            targets = read_csv(root / "out" / "baseline_ready_lmb_licu_targets.csv")
            cycles = [int(row["cycle_index"]) for row in targets]

            self.assertEqual(max(cycles), 11)
            self.assertNotIn(12, cycles)
            self.assertNotIn(13, cycles)

    def test_t_minus_1_row_is_positive_target(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_export(root)
            targets = read_csv(root / "out" / "baseline_ready_lmb_licu_targets.csv")
            target_by_cycle = {int(row["cycle_index"]): row["target_event_next_cycle"] for row in targets}

            self.assertEqual(target_by_cycle[11], "1")
            self.assertEqual(target_by_cycle[10], "0")

    def test_leakage_columns_are_removed_from_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_export(root)
            features = read_csv(root / "out" / "baseline_ready_lmb_licu_features.csv")
            columns = set(features[0])

            self.assertNotIn("charge_capacity_mah", columns)
            self.assertNotIn("discharge_capacity_mah", columns)
            self.assertNotIn("coulombic_efficiency_percent", columns)
            self.assertNotIn("incomplete_cycle_flag", columns)
            self.assertNotIn("ce_lag_1", columns)
            self.assertNotIn("ce_rolling_mean_past_5", columns)
            self.assertNotIn("cumulative_irreversible_capacity_past", columns)
            self.assertNotIn("cumulative_discharge_throughput_mah", columns)
            self.assertNotIn("future_signal", columns)
            self.assertIn("record_voltage_mean_v", columns)

    def test_targets_and_features_are_separated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_export(root)
            features = read_csv(root / "out" / "baseline_ready_lmb_licu_features.csv")
            targets = read_csv(root / "out" / "baseline_ready_lmb_licu_targets.csv")

            self.assertNotIn("target_event_next_cycle", features[0])
            self.assertIn("target_event_next_cycle", targets[0])
            self.assertEqual(len(features), len(targets))

    def test_training_allowed_now_is_always_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_export(root)
            targets = read_csv(root / "out" / "baseline_ready_lmb_licu_targets.csv")

            self.assertFalse(report["training_allowed_now"])
            self.assertEqual({row["training_allowed_now"] for row in targets}, {"False"})


if __name__ == "__main__":
    unittest.main()
