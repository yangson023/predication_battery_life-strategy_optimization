import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.build_lmb_licu_data_expansion_plan import build_lmb_licu_data_expansion_plan


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_fixture(root: Path) -> tuple[Path, Path, Path, Path, Path, Path]:
    diagnostics_root = root / "diagnostics"
    diagnostics_root.mkdir(parents=True)
    (diagnostics_root / "mechanistic_smoke_test_diagnostics_report.md").write_text(
        "qualitative smoke-test diagnostics only; model_training_allowed=False",
        encoding="utf-8",
    )
    write_csv(
        diagnostics_root / "mechanistic_event_rank_summary.csv",
        [
            {"horizon_k": 3, "test_cell": "cell-a", "event_rank_within_fold": 3},
            {"horizon_k": 5, "test_cell": "cell-a", "event_rank_within_fold": 2},
        ],
        ["horizon_k", "test_cell", "event_rank_within_fold"],
    )
    write_csv(
        diagnostics_root / "mechanistic_horizon_comparison.csv",
        [{"test_cell": "cell-a", "preferred_horizon_for_next_candidate": "horizon_5"}],
        ["test_cell", "preferred_horizon_for_next_candidate"],
    )
    write_csv(
        diagnostics_root / "mechanistic_same_signal_source_risk_audit.csv",
        [{"horizon_k": 5, "risk_label": "same_signal_source_present_but_not_dominant;mechanistic_feature_family_worth_retaining"}],
        ["horizon_k", "risk_label"],
    )
    risk = root / "risk.csv"
    write_csv(
        risk,
        [
            {"horizon_k": 5, "risk_key": "very_high_risk_small_n"},
            {"horizon_k": 5, "risk_key": "protocol_censored_terminal"},
        ],
        ["horizon_k", "risk_key"],
    )
    metadata = root / "metadata.csv"
    write_csv(
        metadata,
        [
            {"电池编号": "licu-1", "cell_group": "Li||Cu", "metadata_gate_status": "metadata_ready_for_label_audit"},
            {"电池编号": "lili-1", "cell_group": "Li||Li", "metadata_gate_status": "metadata_ready_for_label_audit"},
        ],
        ["电池编号", "cell_group", "metadata_gate_status"],
    )
    label_policy = root / "label.md"
    feature_req = root / "feature.md"
    storage = root / "storage.md"
    label_policy.write_text("Li||Cu and Li||Li are separate.", encoding="utf-8")
    feature_req.write_text("termination_reason current_density areal_capacity", encoding="utf-8")
    storage.write_text("raw -> tiny validation -> processed", encoding="utf-8")
    return diagnostics_root, risk, metadata, label_policy, feature_req, storage


class LmbLicuDataExpansionPlanTests(unittest.TestCase):
    def run_builder(self, root: Path) -> dict[str, object]:
        diagnostics_root, risk, metadata, label_policy, feature_req, storage = build_fixture(root)
        return build_lmb_licu_data_expansion_plan(
            diagnostics_root=diagnostics_root,
            baseline_risk_summary=risk,
            metadata_gate=metadata,
            label_policy=label_policy,
            feature_label_requirements=feature_req,
            storage_plan=storage,
            output_root=root / "out",
            docs_output=root / "docs" / "lmb-licu-data-expansion-plan.md",
        )

    def test_report_has_no_formal_result_terms_and_training_is_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_builder(root)
            report_text = (root / "out" / "lmb_licu_data_expansion_plan_report.md").read_text(encoding="utf-8").lower()
            report_json = json.loads((root / "out" / "lmb_licu_data_expansion_plan_report.json").read_text(encoding="utf-8"))
            gate_rows = read_csv(root / "out" / "licu_intake_gate_for_next_batch.csv")

            self.assertFalse(report["model_training_allowed"])
            self.assertFalse(report_json["model_training_allowed"])
            self.assertEqual({row["model_training_allowed"] for row in gate_rows}, {"False"})
            for blocked in ["auc", "f1", "rmse", "accuracy"]:
                self.assertNotIn(blocked, report_text)
                self.assertNotIn(blocked, json.dumps(report_json, ensure_ascii=False).lower())

    def test_current_small_n_gap_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_builder(root)
            gap_rows = {row["gap_key"]: row for row in read_csv(root / "out" / "licu_data_gap_summary.csv")}

            self.assertEqual(gap_rows["candidate_licu_cell_count"]["current_value"], "3")
            self.assertEqual(gap_rows["positive_target_count"]["current_value"], "3")
            self.assertEqual(gap_rows["train_positive_per_loco_fold"]["current_value"], "2")
            self.assertEqual(gap_rows["very_high_risk_small_n"]["current_value"], "True")

    def test_no_event_control_and_metadata_requirements_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_builder(root)
            requirements = read_csv(root / "out" / "licu_next_batch_cell_requirements.csv")
            metadata = read_csv(root / "out" / "licu_metadata_requirement_checklist.csv")

            self.assertTrue(any(row["requirement_key"] == "no_event_controls" for row in requirements))
            fields = {row["metadata_field"] for row in metadata}
            self.assertIn("termination_reason", fields)
            self.assertIn("current_density", fields)
            self.assertIn("areal_capacity", fields)

    def test_lcu_lili_are_distinguished_and_partner_message_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_builder(root)
            doc = (root / "docs" / "lmb-licu-data-expansion-plan.md").read_text(encoding="utf-8")

            self.assertIn("Li||Cu", doc)
            self.assertIn("Li||Li", doc)
            self.assertIn("不能混在一起训练", doc)
            self.assertIn("不是想要“越多越好”的乱数据", report["partner_message_cn"])

    def test_current_lab_cells_are_tagged_as_not_full_cell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_builder(root)
            scope_rows = read_csv(root / "out" / "current_lmb_cell_scope_tags.csv")
            doc = (root / "docs" / "lmb-licu-data-expansion-plan.md").read_text(encoding="utf-8")

            self.assertEqual(report["current_lab_data_scope_tag"], "lmb_mechanism_test_not_full_cell")
            self.assertFalse(report["current_lab_data_are_full_cells"])
            self.assertEqual(len(scope_rows), 7)
            self.assertEqual({row["is_full_cell"] for row in scope_rows}, {"False"})
            self.assertEqual({row["cell_scope_tag"] for row in scope_rows}, {"lmb_mechanism_test_not_full_cell"})
            self.assertIn("不能作为全电池寿命/RUL/EOL 证据", doc)


if __name__ == "__main__":
    unittest.main()
