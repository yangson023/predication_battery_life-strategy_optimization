import csv
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.build_lmb_baseline_ready_label_design import build_lmb_baseline_ready_label_design


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
    per_cell = root / "per_cell_trainability.csv"
    write_csv(
        per_cell,
        [
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "licu-1",
                "selected_dataset_name": "licu-ds",
                "label_key": "incomplete_capacity_event",
                "trainability_level": "trainable_candidate",
                "first_observed_candidate_cycle": "20",
                "last_cycle_index": "40",
                "baseline_ready_label_design_allowed": "True",
            },
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "licu-1",
                "selected_dataset_name": "licu-ds",
                "label_key": "ce_instability",
                "trainability_level": "audit_only",
                "first_observed_candidate_cycle": "2",
                "last_cycle_index": "40",
                "baseline_ready_label_design_allowed": "False",
            },
            {
                "cell_group": "Li||Li",
                "source_folder_name": "lili-1",
                "selected_dataset_name": "lili-ds",
                "label_key": "incomplete_capacity_event",
                "trainability_level": "trainable_candidate",
                "first_observed_candidate_cycle": "5",
                "last_cycle_index": "30",
                "baseline_ready_label_design_allowed": "True",
            },
        ],
        [
            "cell_group",
            "source_folder_name",
            "selected_dataset_name",
            "label_key",
            "trainability_level",
            "first_observed_candidate_cycle",
            "last_cycle_index",
            "baseline_ready_label_design_allowed",
        ],
    )
    summary = root / "summary.csv"
    write_csv(summary, [{"cell_group": "Li||Cu", "label_key": "incomplete_capacity_event"}], ["cell_group", "label_key"])
    event_scan = root / "event_scan.csv"
    rows = []
    for cycle in range(1, 41):
        rows.append(
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "licu-1",
                "selected_dataset_name": "licu-ds",
                "cycle_index": cycle,
                "label_key": "incomplete_capacity_event",
                "observed_candidate": "True" if cycle == 20 else "False",
            }
        )
    write_csv(
        event_scan,
        rows,
        ["cell_group", "source_folder_name", "selected_dataset_name", "cycle_index", "label_key", "observed_candidate"],
    )
    features = root / "licu_features.csv"
    write_csv(
        features,
        [
            {
                "source_folder_name": "licu-1",
                "selected_dataset_name": "licu-ds",
                "cycle_index": cycle,
                "charge_capacity_mah": 1.0,
                "discharge_capacity_mah": 1.0,
                "coulombic_efficiency_percent": 100,
                "irreversible_capacity_mah": 0,
                "incomplete_cycle_flag": "False",
                "ce_warning_flag": "False",
                "capacity_retention_percent": 100,
                "record_voltage_mean_v": 0.1,
                "future_signal": 0,
            }
            for cycle in range(1, 41)
        ],
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
            "record_voltage_mean_v",
            "future_signal",
        ],
    )
    metadata = root / "metadata.csv"
    write_csv(
        metadata,
        [
            {
                "电池编号": "licu-1",
                "cell_group": "Li||Cu",
                "termination_interpretation": "protocol_censored",
                "training_allowed_now": "False",
            }
        ],
        ["电池编号", "cell_group", "termination_interpretation", "training_allowed_now"],
    )
    policy = root / "policy.md"
    policy.write_text("label policy", encoding="utf-8")
    return {
        "per_cell": per_cell,
        "summary": summary,
        "event_scan": event_scan,
        "features": features,
        "metadata": metadata,
        "policy": policy,
    }


class LmbBaselineReadyLabelDesignTests(unittest.TestCase):
    def run_design(self, root: Path) -> dict[str, object]:
        paths = fixture(root)
        return build_lmb_baseline_ready_label_design(
            trainability_per_cell=paths["per_cell"],
            trainability_summary=paths["summary"],
            audit_event_scan=paths["event_scan"],
            licu_features=paths["features"],
            metadata_gate=paths["metadata"],
            label_policy=paths["policy"],
            output_root=root / "out",
        )

    def test_only_licu_incomplete_capacity_is_designed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_design(root)
            rows = read_csv(root / "out" / "licu_incomplete_capacity_label_design.csv")

            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["cell_group"], "Li||Cu")
            self.assertEqual(rows[0]["label_key"], "incomplete_capacity_event")

    def test_protocol_censored_terminal_is_not_observed_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_design(root)
            rows = read_csv(root / "out" / "licu_incomplete_capacity_label_design.csv")

            self.assertEqual(rows[0]["protocol_censored_terminal"], "True")
            self.assertIn("protocol_censored", rows[0]["baseline_ready_design_status"])

    def test_post_event_rows_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_design(root)
            rows = read_csv(root / "out" / "licu_incomplete_capacity_label_design.csv")

            self.assertEqual(rows[0]["positive_event_cycle"], "20")
            self.assertEqual(rows[0]["post_event_excluded_window"], "21..40")
            self.assertEqual(rows[0]["post_event_cycle_count"], "20")

    def test_leakage_columns_are_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_design(root)
            excluded = read_csv(root / "out" / "licu_incomplete_capacity_excluded_feature_columns.csv")
            columns = {row["feature_column"] for row in excluded}

            self.assertIn("charge_capacity_mah", columns)
            self.assertIn("discharge_capacity_mah", columns)
            self.assertIn("coulombic_efficiency_percent", columns)
            self.assertIn("incomplete_cycle_flag", columns)
            self.assertIn("future_signal", columns)

    def test_training_allowed_now_is_always_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_design(root)
            rows = read_csv(root / "out" / "licu_incomplete_capacity_label_design.csv")

            self.assertFalse(report["training_allowed_now"])
            self.assertEqual({row["training_allowed_now"] for row in rows}, {"False"})


if __name__ == "__main__":
    unittest.main()
