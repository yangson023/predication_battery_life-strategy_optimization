import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.export_lmb_mechanistic_baseline_ready_dataset import (
    export_lmb_mechanistic_baseline_ready_dataset,
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


def build_fixture(root: Path) -> dict[str, Path]:
    feature_columns = [
        "row_id",
        "source_folder_name",
        "selected_dataset_name",
        "target_cycle",
        "horizon_k",
        "feature_window_start",
        "feature_window_end",
        "excluded_recent_window_start",
        "excluded_recent_window_end",
        "first_event_cycle",
        "baseline_ready_export_candidate",
        "protocol_censored_terminal",
        "training_allowed_now",
        "cycle_median_voltage_v_lag_k",
        "voltage_hysteresis_v_trend_past_5",
        "charge_step_duration_s_lag_k",
        "ce_rolling_mean_window_past_5",
        "charge_capacity_mah_trend_past_5",
        "coulombic_efficiency_percent",
        "charge_capacity_mah",
        "incomplete_cycle_flag",
        "record_voltage_mean_v",
    ]

    def rows_for_horizon(horizon: int) -> list[dict[str, object]]:
        rows = []
        for cell_id, first_event, candidate in [
            ("26-0428-009", 2, False),
            ("licu-good", 9, True),
        ]:
            for target_cycle in range(horizon + 1, 12):
                rows.append(
                    {
                        "row_id": f"{cell_id}__target_cycle_{target_cycle}__h{horizon}",
                        "source_folder_name": cell_id,
                        "selected_dataset_name": f"{cell_id}-dataset",
                        "target_cycle": target_cycle,
                        "horizon_k": horizon,
                        "feature_window_start": max(1, target_cycle - horizon - 4),
                        "feature_window_end": target_cycle - horizon,
                        "excluded_recent_window_start": target_cycle - horizon + 1,
                        "excluded_recent_window_end": target_cycle,
                        "first_event_cycle": first_event,
                        "baseline_ready_export_candidate": candidate,
                        "protocol_censored_terminal": True,
                        "training_allowed_now": False,
                        "cycle_median_voltage_v_lag_k": 0.1 + target_cycle,
                        "voltage_hysteresis_v_trend_past_5": 0.01,
                        "charge_step_duration_s_lag_k": 1000 + target_cycle,
                        "ce_rolling_mean_window_past_5": 99.5,
                        "charge_capacity_mah_trend_past_5": -0.1,
                        "coulombic_efficiency_percent": 99.9,
                        "charge_capacity_mah": 1.0,
                        "incomplete_cycle_flag": target_cycle == first_event,
                        "record_voltage_mean_v": 0.2,
                    }
                )
        return rows

    h3 = root / "h3.csv"
    h5 = root / "h5.csv"
    write_csv(h3, rows_for_horizon(3), feature_columns)
    write_csv(h5, rows_for_horizon(5), feature_columns)

    schema = root / "schema.csv"
    write_csv(
        schema,
        [
            {
                "field_name": "cycle_median_voltage_v_lag_k",
                "source_domain": "voltage",
                "model_feature_candidate": True,
                "audit_only": False,
                "same_signal_source_risk": False,
            },
            {
                "field_name": "voltage_hysteresis_v_trend_past_5",
                "source_domain": "voltage",
                "model_feature_candidate": True,
                "audit_only": False,
                "same_signal_source_risk": False,
            },
            {
                "field_name": "charge_step_duration_s_lag_k",
                "source_domain": "kinetic",
                "model_feature_candidate": True,
                "audit_only": False,
                "same_signal_source_risk": False,
            },
            {
                "field_name": "ce_rolling_mean_window_past_5",
                "source_domain": "CE",
                "model_feature_candidate": True,
                "audit_only": False,
                "same_signal_source_risk": True,
            },
            {
                "field_name": "charge_capacity_mah_trend_past_5",
                "source_domain": "capacity",
                "model_feature_candidate": True,
                "audit_only": False,
                "same_signal_source_risk": True,
            },
            {
                "field_name": "coulombic_efficiency_percent",
                "source_domain": "CE",
                "model_feature_candidate": True,
                "audit_only": False,
                "same_signal_source_risk": True,
            },
            {
                "field_name": "charge_capacity_mah",
                "source_domain": "capacity",
                "model_feature_candidate": True,
                "audit_only": False,
                "same_signal_source_risk": True,
            },
            {
                "field_name": "incomplete_cycle_flag",
                "source_domain": "quality",
                "model_feature_candidate": True,
                "audit_only": False,
                "same_signal_source_risk": False,
            },
            {
                "field_name": "record_voltage_mean_v",
                "source_domain": "record_sample",
                "model_feature_candidate": True,
                "audit_only": False,
                "same_signal_source_risk": False,
            },
        ],
        ["field_name", "source_domain", "model_feature_candidate", "audit_only", "same_signal_source_risk"],
    )

    coverage = root / "coverage.csv"
    coverage_rows = []
    for horizon in [3, 5]:
        for column in [
            "cycle_median_voltage_v_lag_k",
            "voltage_hysteresis_v_trend_past_5",
            "charge_step_duration_s_lag_k",
            "ce_rolling_mean_window_past_5",
            "charge_capacity_mah_trend_past_5",
            "coulombic_efficiency_percent",
            "charge_capacity_mah",
            "incomplete_cycle_flag",
            "record_voltage_mean_v",
        ]:
            coverage_rows.append(
                {
                    "horizon_k": horizon,
                    "feature_name": column,
                    "non_empty_count": 10,
                    "total_rows": 10,
                    "coverage_fraction": 1.0,
                }
            )
    write_csv(coverage, coverage_rows, ["horizon_k", "feature_name", "non_empty_count", "total_rows", "coverage_fraction"])

    leakage = root / "leakage.csv"
    write_csv(
        leakage,
        [
            {"check_name": "horizon_window_excludes_recent_cycles", "horizon_k": 3, "status": "pass", "detail": ""},
            {"check_name": "forbidden_direct_columns_absent", "horizon_k": 3, "status": "pass", "detail": ""},
            {"check_name": "horizon_window_excludes_recent_cycles", "horizon_k": 5, "status": "pass", "detail": ""},
            {"check_name": "forbidden_direct_columns_absent", "horizon_k": 5, "status": "pass", "detail": ""},
        ],
        ["check_name", "horizon_k", "status", "detail"],
    )

    design = root / "design.csv"
    write_csv(
        design,
        [
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "26-0428-009",
                "selected_dataset_name": "early-dataset",
                "label_key": "incomplete_capacity_event",
                "first_event_cycle": 2,
                "protocol_censored_terminal": True,
                "baseline_ready_export_candidate": False,
            },
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "licu-good",
                "selected_dataset_name": "licu-good-dataset",
                "label_key": "incomplete_capacity_event",
                "first_event_cycle": 9,
                "protocol_censored_terminal": True,
                "baseline_ready_export_candidate": True,
            },
        ],
        [
            "cell_group",
            "source_folder_name",
            "selected_dataset_name",
            "label_key",
            "first_event_cycle",
            "protocol_censored_terminal",
            "baseline_ready_export_candidate",
        ],
    )
    return {"h3": h3, "h5": h5, "schema": schema, "coverage": coverage, "leakage": leakage, "design": design}


class LmbMechanisticBaselineReadyExportTests(unittest.TestCase):
    def run_export(self, root: Path) -> dict[str, object]:
        paths = build_fixture(root)
        return export_lmb_mechanistic_baseline_ready_dataset(
            horizon3_features=paths["h3"],
            horizon5_features=paths["h5"],
            mechanistic_feature_schema=paths["schema"],
            horizon_leakage_check=paths["leakage"],
            horizon_feature_coverage_summary=paths["coverage"],
            label_design=paths["design"],
            output_root=root / "out",
        )

    def test_early_event_cell_is_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_export(root)
            h3_targets = read_csv(root / "out" / "horizon3_mechanistic_targets.csv")
            excluded = read_csv(root / "out" / "mechanistic_excluded_rows_or_cells.csv")

            self.assertEqual({row["source_folder_name"] for row in h3_targets}, {"licu-good"})
            self.assertIn("26-0428-009", {row["source_folder_name"] for row in excluded})
            self.assertFalse(report["model_training_allowed"])

    def test_horizon_exports_are_not_mixed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_export(root)
            h3 = read_csv(root / "out" / "horizon3_mechanistic_targets.csv")
            h5 = read_csv(root / "out" / "horizon5_mechanistic_targets.csv")

            self.assertEqual({row["horizon_k"] for row in h3}, {"3"})
            self.assertEqual({row["horizon_k"] for row in h5}, {"5"})

    def test_post_event_rows_are_excluded_and_event_cycle_is_positive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_export(root)
            targets = read_csv(root / "out" / "horizon3_mechanistic_targets.csv")
            by_cycle = {int(row["target_cycle"]): row for row in targets}

            self.assertIn(9, by_cycle)
            self.assertEqual(by_cycle[9]["target_event_at_cycle"], "1")
            self.assertNotIn(10, by_cycle)
            self.assertNotIn(11, by_cycle)

    def test_direct_and_record_columns_do_not_enter_features(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_export(root)
            features = read_csv(root / "out" / "horizon3_mechanistic_features.csv")
            columns = set(features[0])

            self.assertNotIn("coulombic_efficiency_percent", columns)
            self.assertNotIn("charge_capacity_mah", columns)
            self.assertNotIn("incomplete_cycle_flag", columns)
            self.assertNotIn("record_voltage_mean_v", columns)
            self.assertIn("ce_rolling_mean_window_past_5", columns)
            self.assertIn("charge_capacity_mah_trend_past_5", columns)

    def test_same_signal_risk_is_recorded_and_metadata_is_separated(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_export(root)
            features = read_csv(root / "out" / "horizon3_mechanistic_features.csv")
            metadata = read_csv(root / "out" / "horizon3_mechanistic_metadata.csv")

            self.assertIn("ce_rolling_mean_window_past_5", report["same_signal_source_risk_feature_columns"]["3"])
            self.assertNotIn("source_folder_name", features[0])
            self.assertNotIn("protocol_censored_terminal", features[0])
            self.assertIn("protocol_censored_terminal", metadata[0])
            self.assertIn("same_signal_source_feature_columns", metadata[0])

    def test_report_disallows_training_and_formal_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_export(root)
            report_text = (root / "out" / "mechanistic_baseline_ready_export_report.md").read_text(encoding="utf-8").lower()
            manifest = json.loads((root / "out" / "mechanistic_baseline_ready_manifest.json").read_text(encoding="utf-8"))

            self.assertFalse(report["model_training_allowed"])
            self.assertFalse(manifest["formal_performance_metrics_computed"])
            self.assertNotIn("auc", report_text)
            self.assertNotIn("f1", report_text)
            self.assertNotIn("rmse", report_text)


if __name__ == "__main__":
    unittest.main()
