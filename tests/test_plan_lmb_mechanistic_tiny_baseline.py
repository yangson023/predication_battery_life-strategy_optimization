import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.plan_lmb_mechanistic_tiny_baseline import (
    leakage_columns,
    plan_lmb_mechanistic_tiny_baseline,
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


def build_fixture(root: Path, include_forbidden: bool = False) -> Path:
    input_root = root / "input"
    input_root.mkdir(parents=True, exist_ok=True)
    manifest = {
        "candidate_export_only": True,
        "model_training_allowed": False,
        "target_cell_group": "Li||Cu",
        "target_label_key": "incomplete_capacity_event",
    }
    (input_root / "mechanistic_baseline_ready_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    (input_root / "mechanistic_baseline_ready_export_report.md").write_text(
        "candidate export only; no model run\n",
        encoding="utf-8",
    )
    for horizon in [3, 5]:
        features = []
        targets = []
        metadata = []
        for cell in ["cell-a", "cell-b", "cell-c"]:
            first_event = 5 + horizon
            for target_cycle in range(horizon + 1, first_event + 1):
                rid = f"{cell}__target_cycle_{target_cycle}__h{horizon}"
                feature_row = {
                    "row_id": rid,
                    "cycle_median_voltage_v_lag_k": 0.1,
                    "voltage_hysteresis_v_trend_past_5": 0.2,
                    "ce_rolling_mean_window_past_5": 99.5,
                }
                if include_forbidden:
                    feature_row["target_event_at_cycle"] = 0
                features.append(feature_row)
                targets.append(
                    {
                        "row_id": rid,
                        "source_folder_name": cell,
                        "selected_dataset_name": f"{cell}-dataset",
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
                        "source_folder_name": cell,
                        "selected_dataset_name": f"{cell}-dataset",
                        "target_cycle": target_cycle,
                        "horizon_k": horizon,
                        "cell_group": "Li||Cu",
                        "label_key": "incomplete_capacity_event",
                        "first_event_cycle": first_event,
                        "protocol_censored_terminal": True,
                        "same_signal_source_feature_columns": "ce_rolling_mean_window_past_5",
                        "training_allowed_now": False,
                    }
                )
        feature_fields = ["row_id", "cycle_median_voltage_v_lag_k", "voltage_hysteresis_v_trend_past_5", "ce_rolling_mean_window_past_5"]
        if include_forbidden:
            feature_fields.append("target_event_at_cycle")
        write_csv(input_root / f"horizon{horizon}_mechanistic_features.csv", features, feature_fields)
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
                "selected_dataset_name",
                "target_cycle",
                "horizon_k",
                "cell_group",
                "label_key",
                "first_event_cycle",
                "protocol_censored_terminal",
                "same_signal_source_feature_columns",
                "training_allowed_now",
            ],
        )
    return input_root


class LmbMechanisticTinyBaselinePlanTests(unittest.TestCase):
    def test_horizons_are_not_mixed_and_loco_is_by_cell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            report = plan_lmb_mechanistic_tiny_baseline(input_root, root / "out")
            folds = read_csv(root / "out" / "mechanistic_loco_fold_plan.csv")

            self.assertEqual({row["horizon_k"] for row in folds}, {"3", "5"})
            self.assertEqual(len(folds), 6)
            self.assertEqual({row["split_type"] for row in folds}, {"leave_one_cell_out"})
            self.assertEqual({row["random_row_split_used"] for row in folds}, {"False"})
            self.assertEqual(report["horizons"]["3"]["cell_count"], 3)
            self.assertEqual(report["horizons"]["5"]["cell_count"], 3)

    def test_row_id_alignment_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            report = plan_lmb_mechanistic_tiny_baseline(input_root, root / "out")

            self.assertTrue(report["horizons"]["3"]["row_id_alignment"]["row_id_alignment_passed"])
            self.assertTrue(report["horizons"]["5"]["row_id_alignment"]["row_id_alignment_passed"])

    def test_leakage_column_detection(self) -> None:
        self.assertEqual(leakage_columns([{"row_id": "1", "target_signal": "x"}]), ["target_signal"])
        self.assertEqual(leakage_columns([{"row_id": "1", "charge_capacity_mah": "1"}]), ["charge_capacity_mah"])
        self.assertEqual(leakage_columns([{"row_id": "1", "record_voltage_mean_v": "1"}]), ["record_voltage_mean_v"])

    def test_forbidden_feature_blocks_request(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root, include_forbidden=True)
            report = plan_lmb_mechanistic_tiny_baseline(input_root, root / "out")
            risks = read_csv(root / "out" / "mechanistic_baseline_data_risk_summary.csv")

            self.assertFalse(report["tiny_mechanistic_smoke_test_request_allowed"])
            self.assertIn("feature_leakage_columns_present", {row["risk_key"] for row in risks})

    def test_small_n_risk_and_training_gate_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            report = plan_lmb_mechanistic_tiny_baseline(input_root, root / "out")
            folds = read_csv(root / "out" / "mechanistic_loco_fold_plan.csv")
            text = (root / "out" / "mechanistic_tiny_baseline_plan_report.md").read_text(encoding="utf-8").lower()

            self.assertEqual({row["train_positive_risk"] for row in folds}, {"very_high_risk_small_n"})
            self.assertFalse(report["model_training_allowed"])
            self.assertNotIn("formal performance", text)
            self.assertNotIn("auc", text)
            self.assertNotIn("rmse", text)


if __name__ == "__main__":
    unittest.main()
