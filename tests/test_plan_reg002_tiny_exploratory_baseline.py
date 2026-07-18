import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.plan_reg002_tiny_exploratory_baseline import (
    plan_reg002_tiny_exploratory_baseline,
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


DESIGN_COLUMNS = [
    "source_id",
    "dataset_role",
    "cell_scope",
    "group_id",
    "cell_id",
    "label_key",
    "horizon_k",
    "row_id",
    "target_row_index",
    "target_equiv_cycle",
    "feature_window_end_row_index",
    "feature_window_end_equiv_cycle",
    "excluded_recent_window_start_row_index",
    "excluded_recent_window_end_row_index",
    "first_event_row_index",
    "first_event_equiv_cycle",
    "target_event_at_cycle",
    "discharge_capacity_retention_lag_k",
    "discharge_capacity_trend_past_5",
    "discharge_capacity_trend_past_10",
    "charge_capacity_trend_past_5",
    "charge_discharge_capacity_gap_lag_k",
    "early_cycle_capacity_slope",
    "feature_valid_count_past_5",
    "feature_valid_count_past_10",
    "split_policy",
    "random_row_split_used",
    "exploratory_export_candidate",
    "formal_training_set_created",
    "model_training_allowed",
]


def make_input(root: Path) -> Path:
    input_root = root / "input"
    design_rows = []
    for horizon in [5, 10]:
        for cell in ["G1_Cell1", "G1_Cell2", "G1_Cell3"]:
            for idx in range(1, 4):
                design_rows.append(
                    {
                        "source_id": "REG-002",
                        "dataset_role": "true_lmb",
                        "cell_scope": "lmb_full_cell",
                        "group_id": "G1",
                        "cell_id": cell,
                        "label_key": "capacity_eol_80",
                        "horizon_k": horizon,
                        "row_id": f"h{horizon}_{cell}_{idx}",
                        "target_row_index": idx,
                        "target_equiv_cycle": idx,
                        "feature_window_end_row_index": idx - horizon,
                        "feature_window_end_equiv_cycle": idx - horizon,
                        "excluded_recent_window_start_row_index": idx - horizon + 1,
                        "excluded_recent_window_end_row_index": idx,
                        "first_event_row_index": 3,
                        "first_event_equiv_cycle": 3,
                        "target_event_at_cycle": 1 if idx == 3 else 0,
                        "discharge_capacity_retention_lag_k": 0.9,
                        "discharge_capacity_trend_past_5": -0.01,
                        "discharge_capacity_trend_past_10": -0.01,
                        "charge_capacity_trend_past_5": -0.01,
                        "charge_discharge_capacity_gap_lag_k": 0.02,
                        "early_cycle_capacity_slope": -0.01,
                        "feature_valid_count_past_5": 5,
                        "feature_valid_count_past_10": 10,
                        "split_policy": "leave_one_cell_out_planning_only",
                        "random_row_split_used": False,
                        "exploratory_export_candidate": True,
                        "formal_training_set_created": False,
                        "model_training_allowed": False,
                    }
                )
    policy_rows = [
        {
            "feature_name": "discharge_capacity_trend_past_5",
            "feature_family": "capacity_trend",
            "uses_only_past_cycles": True,
            "horizon_dependent": True,
            "same_signal_source_risk": True,
            "allowed_in_exploratory_design": True,
            "formal_training_allowed_now": False,
            "note": "capacity same signal source",
        }
    ]
    excluded_rows = [
        {
            "source_id": "REG-002",
            "dataset_role": "true_lmb",
            "cell_scope": "lmb_full_cell",
            "group_id": "G1",
            "cell_id": "G1_Cell4",
            "label_key": "capacity_eol_80",
            "event_observed": False,
            "rul_is_censored": True,
            "exclusion_or_censoring_reason": "right_censored",
            "retained_use": "protocol_review",
            "formal_training_set_created": False,
            "model_training_allowed": False,
        }
    ]
    report = {
        "capacity_eol_80_observed_cells": 3,
        "capacity_eol_80_censored_cells": 1,
        "capacity_eol_70_observed_cells": 0,
        "formal_training_blockers": ["missing_terminal_reason"],
    }
    write_csv(input_root / "reg002_capacity_eol80_export_design.csv", design_rows, DESIGN_COLUMNS)
    write_csv(input_root / "reg002_capacity_eol70_export_design.csv", [], DESIGN_COLUMNS)
    write_csv(
        input_root / "reg002_candidate_feature_policy.csv",
        policy_rows,
        [
            "feature_name",
            "feature_family",
            "uses_only_past_cycles",
            "horizon_dependent",
            "same_signal_source_risk",
            "allowed_in_exploratory_design",
            "formal_training_allowed_now",
            "note",
        ],
    )
    write_csv(
        input_root / "reg002_excluded_or_censored_cells.csv",
        excluded_rows,
        [
            "source_id",
            "dataset_role",
            "cell_scope",
            "group_id",
            "cell_id",
            "label_key",
            "event_observed",
            "rul_is_censored",
            "exclusion_or_censoring_reason",
            "retained_use",
            "formal_training_set_created",
            "model_training_allowed",
        ],
    )
    write_csv(input_root / "reg002_loco_planning_gate.csv", [], ["label_key"])
    (input_root / "reg002_baseline_ready_export_design_report.json").write_text(
        json.dumps(report),
        encoding="utf-8",
    )
    (input_root / "reg002_baseline_ready_export_design_report.md").write_text("report", encoding="utf-8")
    return input_root


class Reg002TinyExploratoryBaselinePlanningTests(unittest.TestCase):
    def run_plan(self, root: Path) -> dict[str, object]:
        input_root = make_input(root)
        return plan_reg002_tiny_exploratory_baseline(input_root, root / "out", overwrite=True)

    def test_horizon_5_and_10_are_not_mixed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_plan(root)
            folds = read_csv(root / "out" / "reg002_capacity_eol80_loco_fold_plan.csv")

            self.assertEqual({row["horizon_k"] for row in folds}, {"5", "10"})
            self.assertEqual(len([row for row in folds if row["horizon_k"] == "5"]), 3)
            self.assertEqual(len([row for row in folds if row["horizon_k"] == "10"]), 3)

    def test_loco_fold_is_by_cell_not_random_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_plan(root)
            folds = read_csv(root / "out" / "reg002_capacity_eol80_loco_fold_plan.csv")

            self.assertEqual({row["split_type"] for row in folds}, {"leave_one_cell_out"})
            self.assertEqual({row["random_row_split_used"] for row in folds}, {"False"})

    def test_censored_cell_is_not_observed_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_plan(root)
            censored = read_csv(root / "out" / "reg002_capacity_eol80_censored_cell_audit.csv")
            folds = read_csv(root / "out" / "reg002_capacity_eol80_loco_fold_plan.csv")

            self.assertEqual(censored[0]["cell_id"], "G1_Cell4")
            self.assertEqual(censored[0]["included_in_loco_planning"], "False")
            self.assertNotIn("G1_Cell4", {row["test_cell_id"] for row in folds})

    def test_capacity_same_signal_source_risk_is_identified(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_plan(root)
            risks = read_csv(root / "out" / "reg002_capacity_eol80_feature_risk_audit.csv")

            self.assertEqual({row["same_signal_source_risk"] for row in risks}, {"True"})
            self.assertIn("high", {row["risk_level"] for row in risks})

    def test_report_marks_model_training_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_plan(root)
            report_json = json.loads((root / "out" / "reg002_tiny_exploratory_baseline_plan_report.json").read_text(encoding="utf-8"))

            self.assertFalse(report["model_training_allowed"])
            self.assertFalse(report_json["formal_training_set_created"])

    def test_report_does_not_contain_formal_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_plan(root)
            report_text = (root / "out" / "reg002_tiny_exploratory_baseline_plan_report.md").read_text(encoding="utf-8")
            report_json = (root / "out" / "reg002_tiny_exploratory_baseline_plan_report.json").read_text(encoding="utf-8")

            for forbidden in ["AUC", "F1", "RMSE", "accuracy"]:
                self.assertNotIn(forbidden, report_text)
                self.assertNotIn(forbidden, report_json)


if __name__ == "__main__":
    unittest.main()
