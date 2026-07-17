import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.run_lmb_tiny_baseline_smoke_test import run_lmb_tiny_baseline_smoke_test


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_fixture(root: Path) -> Path:
    input_root = root / "input"
    input_root.mkdir(parents=True)
    feature_rows = []
    target_rows = []
    for cell_id, row_count in [("cell-a", 5), ("cell-b", 5), ("cell-c", 5)]:
        for cycle in range(1, row_count + 1):
            rid = f"{cell_id}__cycle_{cycle}"
            feature_rows.append(
                {
                    "row_id": rid,
                    "record_voltage_mean_v": cycle * 0.1,
                    "record_voltage_std_v": 0.01 * cycle,
                    "record_voltage_min_v": -0.1,
                    "record_voltage_max_v": 0.2,
                    "record_current_mean_ma": -0.5,
                    "record_current_std_ma": 0.05,
                }
            )
            target_rows.append(
                {
                    "row_id": rid,
                    "source_folder_name": cell_id,
                    "selected_dataset_name": f"{cell_id}-dataset",
                    "cycle_index": cycle,
                    "label_key": "incomplete_capacity_event",
                    "target_event_next_cycle": 1 if cycle == row_count else 0,
                    "target_event_cycle": row_count + 1,
                    "prediction_horizon_cycles": 1,
                    "candidate_export_only": True,
                    "training_allowed_now": False,
                }
            )
    write_csv(
        input_root / "baseline_ready_lmb_licu_features.csv",
        feature_rows,
        [
            "row_id",
            "record_voltage_mean_v",
            "record_voltage_std_v",
            "record_voltage_min_v",
            "record_voltage_max_v",
            "record_current_mean_ma",
            "record_current_std_ma",
        ],
    )
    write_csv(
        input_root / "baseline_ready_lmb_licu_targets.csv",
        target_rows,
        [
            "row_id",
            "source_folder_name",
            "selected_dataset_name",
            "cycle_index",
            "label_key",
            "target_event_next_cycle",
            "target_event_cycle",
            "prediction_horizon_cycles",
            "candidate_export_only",
            "training_allowed_now",
        ],
    )
    manifest = {
        "candidate_export_only": True,
        "model_training_allowed": False,
        "target_cell_group": "Li||Cu",
        "target_label_key": "incomplete_capacity_event",
    }
    (input_root / "baseline_ready_lmb_licu_manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    return input_root


class LmbTinyBaselineSmokeTestTests(unittest.TestCase):
    def test_uses_loco_and_not_random_row_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            report = run_lmb_tiny_baseline_smoke_test(input_root, root / "out")
            diagnostics = read_csv(root / "out" / "tiny_loco_fold_diagnostics.csv")

            self.assertEqual(report["fold_count"], 3)
            self.assertEqual({row["split_type"] for row in diagnostics}, {"leave_one_cell_out"})
            self.assertEqual({row["random_row_split_used"] for row in diagnostics}, {"False"})

    def test_only_logistic_regression_is_reported(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            report = run_lmb_tiny_baseline_smoke_test(input_root, root / "out")
            diagnostics = read_csv(root / "out" / "tiny_loco_fold_diagnostics.csv")

            self.assertEqual(report["model_family"], "logistic_regression_only")
            self.assertEqual({row["model_family"] for row in diagnostics}, {"logistic_regression_only"})
            self.assertFalse(report["hyperparameter_search_used"])

    def test_no_formal_metric_fields_are_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            run_lmb_tiny_baseline_smoke_test(input_root, root / "out")
            diagnostics = read_csv(root / "out" / "tiny_loco_fold_diagnostics.csv")
            predictions = read_csv(root / "out" / "tiny_loco_fold_predictions.csv")
            blocked_columns = {"auc", "f1", "rmse"}
            lower_columns = {column.lower() for column in diagnostics[0]} | {column.lower() for column in predictions[0]}

            self.assertTrue(blocked_columns.isdisjoint(lower_columns))

    def test_small_n_risk_is_marked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            report = run_lmb_tiny_baseline_smoke_test(input_root, root / "out")
            diagnostics = read_csv(root / "out" / "tiny_loco_fold_diagnostics.csv")

            self.assertEqual(report["folds_with_train_positive_le_2"], 3)
            self.assertEqual({row["train_positive_risk"] for row in diagnostics}, {"very_high_risk_small_n"})

    def test_model_performance_is_not_claimed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            report = run_lmb_tiny_baseline_smoke_test(input_root, root / "out")
            diagnostics = read_csv(root / "out" / "tiny_loco_fold_diagnostics.csv")

            self.assertFalse(report["model_performance_claimed"])
            self.assertFalse(report["model_training_allowed"])
            self.assertEqual({row["model_performance_claimed"] for row in diagnostics}, {"False"})


if __name__ == "__main__":
    unittest.main()
