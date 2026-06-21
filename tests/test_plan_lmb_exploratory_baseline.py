import csv
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.plan_lmb_exploratory_baseline import plan_lmb_exploratory_baseline


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
    features = root / "features.csv"
    targets = root / "targets.csv"
    metadata = root / "metadata.csv"
    rows_f = []
    rows_t = []
    rows_m = []
    for cell in ["cell-a", "cell-b", "cell-c"]:
        for cycle in range(1, 5):
            rid = f"{cell}__cycle_{cycle}"
            rows_f.append({"row_id": rid, "ce_lag_1": 99.0, "record_voltage_mean_v": 0.1})
            target = 1 if cycle == 4 else 0
            rows_t.append(
                {
                    "row_id": rid,
                    "source_folder_name": cell,
                    "cycle_index": cycle,
                    "target_event_next_cycle": target,
                    "training_allowed_now": "False",
                }
            )
            rows_m.append(
                {
                    "row_id": rid,
                    "source_folder_name": cell,
                    "cycle_index": cycle,
                    "protocol_censored_terminal": "True",
                    "training_allowed_now": "False",
                }
            )
    write_csv(features, rows_f, ["row_id", "ce_lag_1", "record_voltage_mean_v"])
    write_csv(targets, rows_t, ["row_id", "source_folder_name", "cycle_index", "target_event_next_cycle", "training_allowed_now"])
    write_csv(metadata, rows_m, ["row_id", "source_folder_name", "cycle_index", "protocol_censored_terminal", "training_allowed_now"])
    manifest = root / "manifest.json"
    manifest.write_text('{"candidate_export_only": true, "model_training_allowed": false}', encoding="utf-8")
    policy = root / "policy.md"
    policy.write_text("policy", encoding="utf-8")
    return {"features": features, "targets": targets, "metadata": metadata, "manifest": manifest, "policy": policy}


class LmbExploratoryBaselinePlanningTests(unittest.TestCase):
    def run_plan(self, root: Path) -> dict[str, object]:
        paths = fixture(root)
        return plan_lmb_exploratory_baseline(
            features_path=paths["features"],
            targets_path=paths["targets"],
            metadata_path=paths["metadata"],
            manifest_path=paths["manifest"],
            label_policy_path=paths["policy"],
            output_root=root / "out",
        )

    def test_loco_folds_are_by_cell_not_random_rows(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_plan(root)
            folds = read_csv(root / "out" / "exploratory_baseline_fold_plan.csv")

            self.assertEqual(len(folds), 3)
            self.assertEqual({row["split_type"] for row in folds}, {"leave_one_cell_out"})
            self.assertEqual({row["random_row_split_used"] for row in folds}, {"False"})

    def test_fold_train_and_test_positive_counts_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_plan(root)
            folds = read_csv(root / "out" / "exploratory_baseline_fold_plan.csv")

            self.assertEqual({row["train_positive_count"] for row in folds}, {"2"})
            self.assertEqual({row["test_positive_count"] for row in folds}, {"1"})

    def test_small_positive_count_is_high_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_plan(root)
            risks = read_csv(root / "out" / "exploratory_baseline_data_risk_summary.csv")

            self.assertEqual(report["folds_with_train_positive_le_2"], 3)
            self.assertIn("fold_train_positive_too_small", {row["risk_key"] for row in risks})
            self.assertIn("very_high", {row["risk_level"] for row in risks})

    def test_report_does_not_contain_formal_performance_claims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_plan(root)
            report_text = (root / "out" / "exploratory_baseline_plan_report.md").read_text(encoding="utf-8")

            self.assertIn("does not report model performance", report_text)
            self.assertIn("Do not report formal AUC/F1/RMSE", report_text)
            self.assertNotIn("formal performance =", report_text)

    def test_model_training_allowed_is_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_plan(root)
            folds = read_csv(root / "out" / "exploratory_baseline_fold_plan.csv")

            self.assertFalse(report["model_training_allowed"])
            self.assertEqual({row["model_training_allowed"] for row in folds}, {"False"})


if __name__ == "__main__":
    unittest.main()
