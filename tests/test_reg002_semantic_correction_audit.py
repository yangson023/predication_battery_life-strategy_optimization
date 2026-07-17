import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.build_reg002_semantic_correction_audit import (
    build_reg002_semantic_correction_audit,
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


def make_input(root: Path) -> dict[str, Path]:
    semantic_review = root / "semantic.md"
    semantic_review.write_text(
        "REG-002 semantic review: equiv_cycle is equivalent full cycle; G1-G4 are mixed design and operation groups; data.mat may include voltage/current time series.",
        encoding="utf-8",
    )
    long_table = root / "long.csv"
    write_csv(
        long_table,
        [
            {
                "source_id": "REG-002",
                "dataset_role": "true_lmb",
                "cell_scope": "lmb_full_cell",
                "group_id": "G1",
                "cell_id": "G1_Cell1",
                "row_index": 0,
                "equiv_cycle": 0.8,
                "charge_capacity": 1.0,
                "discharge_capacity": 0.95,
                "capacity_retention": 1.0,
            },
            {
                "source_id": "REG-002",
                "dataset_role": "true_lmb",
                "cell_scope": "lmb_full_cell",
                "group_id": "G2",
                "cell_id": "G2_Cell1",
                "row_index": 1,
                "equiv_cycle": 1.6,
                "charge_capacity": 0.9,
                "discharge_capacity": 0.8,
                "capacity_retention": 0.84,
            },
        ],
        [
            "source_id",
            "dataset_role",
            "cell_scope",
            "group_id",
            "cell_id",
            "row_index",
            "equiv_cycle",
            "charge_capacity",
            "discharge_capacity",
            "capacity_retention",
        ],
    )
    label_audit = root / "labels.csv"
    write_csv(
        label_audit,
        [
            {"label_key": "capacity_eol_80", "event_observed": True},
            {"label_key": "capacity_eol_80", "event_observed": False},
            {"label_key": "capacity_eol_70", "event_observed": False},
        ],
        ["label_key", "event_observed"],
    )
    export_design = root / "export.csv"
    write_csv(
        export_design,
        [
            {
                "label_key": "capacity_eol_80",
                "target_row_index": 10,
                "target_equiv_cycle": 8.7,
                "feature_window_end_row_index": 5,
                "feature_window_end_equiv_cycle": 4.2,
                "excluded_recent_window_start_row_index": 6,
                "excluded_recent_window_end_row_index": 10,
            }
        ],
        [
            "label_key",
            "target_row_index",
            "target_equiv_cycle",
            "feature_window_end_row_index",
            "feature_window_end_equiv_cycle",
            "excluded_recent_window_start_row_index",
            "excluded_recent_window_end_row_index",
        ],
    )
    export_report = root / "export_report.json"
    export_report.write_text(
        json.dumps({"formal_training_set_created": False, "model_training_allowed": False}),
        encoding="utf-8",
    )
    planning_report = root / "planning_report.json"
    planning_report.write_text(
        json.dumps(
            {
                "random_row_split_used": False,
                "allow_tiny_exploratory_baseline_smoke_test_application": True,
                "formal_training_set_created": False,
                "model_training_allowed": False,
            }
        ),
        encoding="utf-8",
    )
    loco = root / "loco.csv"
    write_csv(loco, [{"split_type": "leave_one_cell_out"}], ["split_type"])
    return {
        "semantic_review": semantic_review,
        "long_table": long_table,
        "label_audit": label_audit,
        "export_design": export_design,
        "export_report": export_report,
        "planning_report": planning_report,
        "loco": loco,
    }


class Reg002SemanticCorrectionAuditTests(unittest.TestCase):
    def run_audit(self, root: Path) -> dict[str, object]:
        paths = make_input(root)
        return build_reg002_semantic_correction_audit(
            semantic_review=paths["semantic_review"],
            long_table=paths["long_table"],
            label_audit=paths["label_audit"],
            export_design=paths["export_design"],
            export_report_path=paths["export_report"],
            planning_report_path=paths["planning_report"],
            loco_fold_plan=paths["loco"],
            output_root=root / "out",
            overwrite=True,
        )

    def test_equiv_cycle_is_not_treated_as_cycle_index(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_audit(root)
            efc = read_csv(root / "out" / "reg002_equiv_cycle_usage_audit.csv")

            self.assertFalse(report["equiv_cycle_used_as_cycle_index"])
            self.assertEqual({row["equiv_cycle_used_as_cycle_index"] for row in efc}, {"False"})

    def test_row_index_based_horizon_planning_is_acceptable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_audit(root)
            summary = read_csv(root / "out" / "reg002_semantic_correction_summary.csv")

            self.assertTrue(report["row_index_based_horizon_planning_acceptable"])
            self.assertIn("pass_row_index_based_planning_retained", {row["audit_status"] for row in summary})

    def test_capacity_eol80_is_codex_defined_audit_label(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_audit(root)
            labels = read_csv(root / "out" / "reg002_label_semantic_audit.csv")
            eol80 = next(row for row in labels if row["label_key"] == "capacity_eol_80")

            self.assertEqual(eol80["codex_defined_audit_threshold"], "True")
            self.assertEqual(eol80["official_paper_eol"], "False")

    def test_group_semantics_are_mixed_not_protocol_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_audit(root)
            groups = read_csv(root / "out" / "reg002_group_semantic_audit.csv")

            self.assertEqual({row["protocol_only_group"] for row in groups}, {"False"})
            self.assertEqual({row["mixed_design_operation_group"] for row in groups}, {"True"})

    def test_data_mat_is_future_tiny_parser_plan_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_audit(root)
            plan = read_csv(root / "out" / "reg002_next_data_mat_parser_plan.csv")

            self.assertTrue(report["data_mat_tiny_validation_worth_doing"])
            self.assertFalse(report["data_mat_locally_validated"])
            self.assertIn("no_training", plan[0]["blocked_actions"])

    def test_report_keeps_model_training_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_audit(root)
            report_json = json.loads((root / "out" / "reg002_semantic_correction_audit_report.json").read_text(encoding="utf-8"))

            self.assertFalse(report["model_training_allowed"])
            self.assertFalse(report_json["formal_training_set_created"])

    def test_report_does_not_contain_formal_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_audit(root)
            report_text = (root / "out" / "reg002_semantic_correction_audit_report.md").read_text(encoding="utf-8")
            report_json = (root / "out" / "reg002_semantic_correction_audit_report.json").read_text(encoding="utf-8")

            for term in ["AUC", "F1", "RMSE", "accuracy"]:
                self.assertNotIn(term, report_text)
                self.assertNotIn(term, report_json)


if __name__ == "__main__":
    unittest.main()
