import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.build_lmb_negative_smoke_test_review import build_lmb_negative_smoke_test_review


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_fixture(root: Path) -> dict[str, Path]:
    predictions = root / "predictions.csv"
    prediction_rows = []
    for fold, cell in [("LOCO_1", "cell-a"), ("LOCO_2", "cell-b"), ("LOCO_3", "cell-c")]:
        for cycle in range(1, 6):
            prediction_rows.append(
                {
                    "fold_id": fold,
                    "test_cell": cell,
                    "row_id": f"{cell}__cycle_{cycle}",
                    "cycle_index": cycle,
                    "label_key": "incomplete_capacity_event",
                    "actual_event_next_cycle": 1 if cycle == 5 else 0,
                    "model_score": 0.99 if cycle == 1 else (0.10 if cycle == 5 else 0.50),
                    "raw_score": 0.0,
                    "score_is_qualitative_only": True,
                    "smoke_test_only": True,
                    "not_formal_performance": True,
                }
            )
    write_csv(
        predictions,
        prediction_rows,
        [
            "fold_id",
            "test_cell",
            "row_id",
            "cycle_index",
            "label_key",
            "actual_event_next_cycle",
            "model_score",
            "raw_score",
            "score_is_qualitative_only",
            "smoke_test_only",
            "not_formal_performance",
        ],
    )
    diagnostics = root / "diagnostics.csv"
    write_csv(
        diagnostics,
        [
            {
                "fold_id": "LOCO_1",
                "test_cell": "cell-a",
                "train_positive_count": 2,
                "coefficient_signs": json.dumps({"record_voltage_mean_v": "positive"}),
            },
            {
                "fold_id": "LOCO_2",
                "test_cell": "cell-b",
                "train_positive_count": 2,
                "coefficient_signs": json.dumps({"record_voltage_mean_v": "negative"}),
            },
        ],
        ["fold_id", "test_cell", "train_positive_count", "coefficient_signs"],
    )
    label_design = root / "label_design.csv"
    write_csv(
        label_design,
        [
            {
                "source_folder_name": "26-0428-009",
                "first_event_cycle": 2,
                "pre_event_cycle_count": 1,
                "baseline_ready_export_candidate": False,
            }
        ],
        ["source_folder_name", "first_event_cycle", "pre_event_cycle_count", "baseline_ready_export_candidate"],
    )
    manifest = root / "manifest.json"
    manifest.write_text(json.dumps({"candidate_export_only": True}), encoding="utf-8")
    features = root / "features.csv"
    write_csv(features, [{"source_folder_name": "cell-a", "cycle_index": 1}], ["source_folder_name", "cycle_index"])
    smoke_report = root / "smoke.md"
    smoke_report.write_text("smoke only", encoding="utf-8")
    label_policy = root / "policy.md"
    label_policy.write_text("policy", encoding="utf-8")
    return {
        "smoke_report": smoke_report,
        "predictions": predictions,
        "diagnostics": diagnostics,
        "manifest": manifest,
        "label_design": label_design,
        "features": features,
        "label_policy": label_policy,
    }


class LmbNegativeSmokeTestReviewTests(unittest.TestCase):
    def run_review(self, root: Path) -> dict[str, object]:
        paths = build_fixture(root)
        return build_lmb_negative_smoke_test_review(
            smoke_report=paths["smoke_report"],
            predictions_path=paths["predictions"],
            diagnostics_path=paths["diagnostics"],
            manifest_path=paths["manifest"],
            label_design_path=paths["label_design"],
            licu_features_path=paths["features"],
            label_policy_path=paths["label_policy"],
            output_root=root / "out",
        )

    def test_does_not_compute_formal_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_review(root)
            self.assertFalse(report["formal_performance_metrics_computed"])
            self.assertNotIn("auc", json.dumps(report).lower())
            self.assertNotIn("rmse", json.dumps(report).lower())

    def test_26_0428_009_is_not_auto_recovered(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_review(root)
            recovery = read_csv(root / "out" / "recoverability_audit_26_0428_009.csv")[0]
            self.assertEqual(recovery["recovery_decision"], "do_not_add_to_baseline_ready")

    def test_report_keeps_model_training_disallowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_review(root)
            self.assertFalse(report["model_training_allowed"])

    def test_failed_predictive_signal_is_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_review(root)
            findings = read_csv(root / "out" / "negative_smoke_test_findings.csv")
            keys = {row["finding_key"] for row in findings}
            self.assertTrue(report["strict_v2_smoke_test_failed_as_predictive_signal"])
            self.assertIn("strict_v2_smoke_test_failed_as_predictive_signal", keys)
            self.assertIn("high_early_false_positive_present", keys)

    def test_feature_redesign_plan_has_leakage_guards(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_review(root)
            plan = read_csv(root / "out" / "lmb_feature_redesign_plan.csv")
            combined = " ".join(
                f"{row['redesign_item']} {row['leakage_guard']} {row['horizon_separation']}" for row in plan
            ).lower()
            self.assertIn("past_only", "_".join(report["feature_redesign_requires"]))
            self.assertIn("horizon", combined)
            self.assertIn("leakage", combined)


if __name__ == "__main__":
    unittest.main()
