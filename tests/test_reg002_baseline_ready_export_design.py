import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.build_reg002_baseline_ready_export_design import (
    build_reg002_baseline_ready_export_design,
)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def make_input(root: Path) -> Path:
    input_root = root / "input"
    long_rows = []
    labels = []
    for cell_idx, cell in enumerate(["G1_Cell1", "G1_Cell2", "G1_Cell3"], start=1):
        group = "G1"
        for row_idx in range(12):
            discharge = 1.0 - 0.02 * row_idx - 0.005 * cell_idx
            long_rows.append(
                {
                    "source_id": "REG-002",
                    "dataset_role": "true_lmb",
                    "cell_scope": "lmb_full_cell",
                    "group_id": group,
                    "cell_id": cell,
                    "file_name": f"G1-Cell{cell_idx}_capacity_degradation.mat",
                    "row_index": row_idx,
                    "equiv_cycle": row_idx + 1,
                    "charge_capacity": discharge + 0.03,
                    "discharge_capacity": discharge,
                    "capacity_retention": discharge / (1.0 - 0.005 * cell_idx),
                    "source_data_audit_only": True,
                    "tiny_validation_only": True,
                    "model_training_allowed": False,
                }
            )
        observed = cell != "G1_Cell3"
        for label_key, threshold in [("capacity_eol_80", 0.8), ("capacity_eol_70", 0.7)]:
            labels.append(
                {
                    "source_id": "REG-002",
                    "dataset_role": "true_lmb",
                    "cell_scope": "lmb_full_cell",
                    "group_id": group,
                    "cell_id": cell,
                    "label_key": label_key,
                    "threshold": threshold,
                    "event_observed": observed and label_key == "capacity_eol_80",
                    "event_row_index": 10 if observed and label_key == "capacity_eol_80" else "",
                    "event_equiv_cycle": 11 if observed and label_key == "capacity_eol_80" else "",
                    "duration_until_event_or_last_equiv_cycle": 11 if observed and label_key == "capacity_eol_80" else 12,
                    "rul_is_censored": not (observed and label_key == "capacity_eol_80"),
                    "label_quality": (
                        "exploratory_observed_capacity_threshold"
                        if observed and label_key == "capacity_eol_80"
                        else "right_censored_no_threshold_crossing_in_downloaded_window"
                    ),
                    "exploratory_candidate_label": observed and label_key == "capacity_eol_80",
                    "formal_trainable_label": False,
                    "blocking_reason": "missing_protocol_and_terminal_reason",
                    "source_data_audit_only": True,
                    "tiny_validation_only": True,
                    "model_training_allowed": False,
                }
            )
    long_columns = [
        "source_id",
        "dataset_role",
        "cell_scope",
        "group_id",
        "cell_id",
        "file_name",
        "row_index",
        "equiv_cycle",
        "charge_capacity",
        "discharge_capacity",
        "capacity_retention",
        "source_data_audit_only",
        "tiny_validation_only",
        "model_training_allowed",
    ]
    label_columns = [
        "source_id",
        "dataset_role",
        "cell_scope",
        "group_id",
        "cell_id",
        "label_key",
        "threshold",
        "event_observed",
        "event_row_index",
        "event_equiv_cycle",
        "duration_until_event_or_last_equiv_cycle",
        "rul_is_censored",
        "label_quality",
        "exploratory_candidate_label",
        "formal_trainable_label",
        "blocking_reason",
        "source_data_audit_only",
        "tiny_validation_only",
        "model_training_allowed",
    ]
    write_csv(input_root / "reg002_capacity_degradation_long.csv", long_rows, long_columns)
    write_csv(input_root / "reg002_capacity_label_audit.csv", labels, label_columns)
    write_csv(input_root / "reg002_cell_summary.csv", [], ["cell_id"])
    write_csv(input_root / "reg002_trainability_gate.csv", [], ["gate_name"])
    (input_root / "reg002_capacity_tiny_validation_report.json").write_text("{}", encoding="utf-8")
    (input_root / "reg002_capacity_tiny_validation_report.md").write_text("report", encoding="utf-8")
    return input_root


class Reg002BaselineReadyExportDesignTests(unittest.TestCase):
    def run_design(self, root: Path) -> dict[str, object]:
        input_root = make_input(root)
        return build_reg002_baseline_ready_export_design(input_root, root / "out", overwrite=True)

    def test_loco_planning_uses_no_random_row_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_design(root)
            folds = read_csv(root / "out" / "reg002_loco_planning_gate.csv")

            self.assertTrue(folds)
            self.assertEqual({row["split_type"] for row in folds}, {"leave_one_cell_out"})
            self.assertEqual({row["random_row_split_used"] for row in folds}, {"False"})

    def test_censored_cells_are_not_treated_as_observed_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_design(root)
            design_rows = read_csv(root / "out" / "reg002_capacity_eol80_export_design.csv")
            excluded_rows = read_csv(root / "out" / "reg002_excluded_or_censored_cells.csv")

            self.assertNotIn("G1_Cell3", {row["cell_id"] for row in design_rows})
            self.assertIn("G1_Cell3", {row["cell_id"] for row in excluded_rows})
            self.assertEqual(
                {row["event_observed"] for row in excluded_rows if row["cell_id"] == "G1_Cell3"},
                {"False"},
            )

    def test_capacity_eol80_and_eol70_are_separated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_design(root)
            eol80 = read_csv(root / "out" / "reg002_capacity_eol80_export_design.csv")
            eol70 = read_csv(root / "out" / "reg002_capacity_eol70_export_design.csv")

            self.assertTrue(eol80)
            self.assertFalse(eol70)
            self.assertEqual({row["label_key"] for row in eol80}, {"capacity_eol_80"})

    def test_report_marks_model_training_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_design(root)
            report_json = json.loads((root / "out" / "reg002_baseline_ready_export_design_report.json").read_text(encoding="utf-8"))

            self.assertFalse(report["model_training_allowed"])
            self.assertFalse(report_json["formal_training_set_created"])
            self.assertFalse(report_json["random_row_split_used"])

    def test_report_does_not_output_formal_performance_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_design(root)
            report_text = (root / "out" / "reg002_baseline_ready_export_design_report.md").read_text(encoding="utf-8")
            report_json = (root / "out" / "reg002_baseline_ready_export_design_report.json").read_text(encoding="utf-8")

            for forbidden in ["AUC", "F1", "RMSE", "accuracy"]:
                self.assertNotIn(forbidden, report_text)
                self.assertNotIn(forbidden, report_json)

    def test_features_targets_metadata_are_marked_as_separated_in_design(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_design(root)
            policy = read_csv(root / "out" / "reg002_candidate_feature_policy.csv")

            self.assertTrue(report["features_targets_metadata_separated_in_design"])
            self.assertEqual({row["formal_training_allowed_now"] for row in policy}, {"False"})


if __name__ == "__main__":
    unittest.main()
