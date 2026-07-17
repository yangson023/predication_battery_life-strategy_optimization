import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.run_lmb_mechanistic_tiny_smoke_test import (
    input_errors,
    run_lmb_mechanistic_tiny_smoke_test,
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


def build_fixture(root: Path) -> tuple[Path, Path]:
    input_root = root / "input"
    plan_root = root / "plan"
    input_root.mkdir(parents=True, exist_ok=True)
    plan_root.mkdir(parents=True, exist_ok=True)
    (input_root / "mechanistic_baseline_ready_manifest.json").write_text(
        json.dumps(
            {
                "candidate_export_only": True,
                "model_training_allowed": False,
                "target_cell_group": "Li||Cu",
                "target_label_key": "incomplete_capacity_event",
            }
        ),
        encoding="utf-8",
    )
    (plan_root / "mechanistic_tiny_baseline_plan_report.json").write_text(
        json.dumps({"tiny_mechanistic_smoke_test_request_allowed": True}),
        encoding="utf-8",
    )
    for horizon in [3, 5]:
        features = []
        targets = []
        metadata = []
        for cell_id, base in [("cell-a", 0.1), ("cell-b", 0.2), ("cell-c", 0.3)]:
            first_event = horizon + 5
            for target_cycle in range(horizon + 1, first_event + 1):
                rid = f"{cell_id}__target_cycle_{target_cycle}__h{horizon}"
                features.append(
                    {
                        "row_id": rid,
                        "cycle_median_voltage_v_lag_k": base + target_cycle * 0.01,
                        "voltage_hysteresis_v_trend_past_5": base,
                        "ce_rolling_mean_window_past_5": 99 - target_cycle * 0.1,
                    }
                )
                targets.append(
                    {
                        "row_id": rid,
                        "source_folder_name": cell_id,
                        "selected_dataset_name": f"{cell_id}-dataset",
                        "target_cycle": target_cycle,
                        "horizon_k": horizon,
                        "label_key": "incomplete_capacity_event",
                        "target_event_at_cycle": 1 if target_cycle == first_event else 0,
                        "first_event_cycle": first_event,
                        "candidate_export_only": True,
                        "training_allowed_now": False,
                    }
                )
                metadata.append(
                    {
                        "row_id": rid,
                        "source_folder_name": cell_id,
                        "target_cycle": target_cycle,
                        "horizon_k": horizon,
                        "cell_group": "Li||Cu",
                        "label_key": "incomplete_capacity_event",
                        "same_signal_source_feature_columns": "ce_rolling_mean_window_past_5",
                        "training_allowed_now": False,
                    }
                )
        write_csv(
            input_root / f"horizon{horizon}_mechanistic_features.csv",
            features,
            ["row_id", "cycle_median_voltage_v_lag_k", "voltage_hysteresis_v_trend_past_5", "ce_rolling_mean_window_past_5"],
        )
        write_csv(
            input_root / f"horizon{horizon}_mechanistic_targets.csv",
            targets,
            [
                "row_id",
                "source_folder_name",
                "selected_dataset_name",
                "target_cycle",
                "horizon_k",
                "label_key",
                "target_event_at_cycle",
                "first_event_cycle",
                "candidate_export_only",
                "training_allowed_now",
            ],
        )
        write_csv(
            input_root / f"horizon{horizon}_mechanistic_metadata.csv",
            metadata,
            [
                "row_id",
                "source_folder_name",
                "target_cycle",
                "horizon_k",
                "cell_group",
                "label_key",
                "same_signal_source_feature_columns",
                "training_allowed_now",
            ],
        )
    return input_root, plan_root


class LmbMechanisticTinySmokeTestTests(unittest.TestCase):
    def test_runs_horizon_separated_loco(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root, plan_root = build_fixture(root)
            report = run_lmb_mechanistic_tiny_smoke_test(input_root, plan_root, root / "out")
            diagnostics = read_csv(root / "out" / "mechanistic_tiny_loco_diagnostics.csv")

            self.assertEqual({row["horizon_k"] for row in diagnostics}, {"3", "5"})
            self.assertEqual({row["split_type"] for row in diagnostics}, {"leave_one_cell_out"})
            self.assertEqual({row["random_row_split_used"] for row in diagnostics}, {"False"})
            self.assertEqual(report["horizons"]["3"]["fold_count"], 3)
            self.assertEqual(report["horizons"]["5"]["fold_count"], 3)

    def test_only_logistic_regression_and_no_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root, plan_root = build_fixture(root)
            report = run_lmb_mechanistic_tiny_smoke_test(input_root, plan_root, root / "out")
            diagnostics = read_csv(root / "out" / "mechanistic_tiny_loco_diagnostics.csv")

            self.assertEqual(report["model_family"], "logistic_regression_only")
            self.assertFalse(report["hyperparameter_search_used"])
            self.assertFalse(report["model_checkpoint_saved"])
            self.assertEqual({row["model_checkpoint_saved"] for row in diagnostics}, {"False"})

    def test_small_n_and_qualitative_boundaries_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root, plan_root = build_fixture(root)
            report = run_lmb_mechanistic_tiny_smoke_test(input_root, plan_root, root / "out")
            diagnostics = read_csv(root / "out" / "mechanistic_tiny_loco_diagnostics.csv")
            predictions = read_csv(root / "out" / "mechanistic_tiny_loco_predictions.csv")

            self.assertEqual({row["train_positive_risk"] for row in diagnostics}, {"very_high_risk_small_n"})
            self.assertFalse(report["formal_result_claimed"])
            self.assertFalse(report["model_training_allowed"])
            self.assertEqual({row["score_is_qualitative_only"] for row in predictions}, {"True"})

    def test_no_formal_metric_columns_are_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root, plan_root = build_fixture(root)
            run_lmb_mechanistic_tiny_smoke_test(input_root, plan_root, root / "out")
            diagnostics = read_csv(root / "out" / "mechanistic_tiny_loco_diagnostics.csv")
            predictions = read_csv(root / "out" / "mechanistic_tiny_loco_predictions.csv")
            lower_columns = {column.lower() for column in diagnostics[0]} | {column.lower() for column in predictions[0]}

            self.assertTrue({"auc", "f1", "rmse", "accuracy"}.isdisjoint(lower_columns))

    def test_input_errors_detect_forbidden_feature_columns(self) -> None:
        errors = input_errors(
            horizon=3,
            features=[{"row_id": "a", "target_leak": "1"}],
            targets=[
                {
                    "row_id": "a",
                    "horizon_k": "3",
                    "label_key": "incomplete_capacity_event",
                }
            ],
            metadata=[{"row_id": "a"}],
            manifest={
                "target_cell_group": "Li||Cu",
                "target_label_key": "incomplete_capacity_event",
                "model_training_allowed": False,
            },
            plan={"tiny_mechanistic_smoke_test_request_allowed": True},
        )

        self.assertIn("h3:feature_leakage_columns_present:target_leak", errors)


if __name__ == "__main__":
    unittest.main()
