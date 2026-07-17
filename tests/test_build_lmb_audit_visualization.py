import csv
import tempfile
import unittest
from pathlib import Path

from modules.visualization.build_lmb_audit_visualization import build_lmb_audit_visualization


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


class LmbAuditVisualizationTests(unittest.TestCase):
    def write_fixture(self, root: Path) -> dict[str, Path]:
        lili = root / "lili.csv"
        licu = root / "licu.csv"
        events = root / "events.csv"
        summary = root / "summary.csv"
        metadata = root / "metadata.csv"
        electrolyte = root / "electrolyte.csv"
        write_csv(
            lili,
            [
                {
                    "source_folder_name": "lili-1",
                    "selected_dataset_name": "lili-ds",
                    "cycle_index": 1,
                    "voltage_hysteresis_v": 0.1,
                    "hysteresis_rolling_mean_past_5": 0.1,
                },
                {
                    "source_folder_name": "lili-1",
                    "selected_dataset_name": "lili-ds",
                    "cycle_index": 2,
                    "voltage_hysteresis_v": 0.4,
                    "hysteresis_rolling_mean_past_5": 0.3,
                },
            ],
            ["source_folder_name", "selected_dataset_name", "cycle_index", "voltage_hysteresis_v", "hysteresis_rolling_mean_past_5"],
        )
        write_csv(
            licu,
            [
                {
                    "source_folder_name": "licu-1",
                    "selected_dataset_name": "licu-ds",
                    "cycle_index": 1,
                    "coulombic_efficiency_percent": 99.0,
                },
                {
                    "source_folder_name": "licu-1",
                    "selected_dataset_name": "licu-ds",
                    "cycle_index": 2,
                    "coulombic_efficiency_percent": 40.0,
                },
            ],
            ["source_folder_name", "selected_dataset_name", "cycle_index", "coulombic_efficiency_percent"],
        )
        write_csv(
            events,
            [
                {
                    "cell_group": "Li||Cu",
                    "source_folder_name": "licu-1",
                    "selected_dataset_name": "licu-ds",
                    "cycle_index": 2,
                    "label_key": "ce_collapse",
                    "observed_candidate": "True",
                    "signal_value": 40.0,
                    "trainable_label": "False",
                },
                {
                    "cell_group": "Li||Li",
                    "source_folder_name": "lili-1",
                    "selected_dataset_name": "lili-ds",
                    "cycle_index": 2,
                    "label_key": "polarization_growth",
                    "observed_candidate": "True",
                    "signal_value": 0.3,
                    "trainable_label": "False",
                },
            ],
            [
                "cell_group",
                "source_folder_name",
                "selected_dataset_name",
                "cycle_index",
                "label_key",
                "observed_candidate",
                "signal_value",
                "trainable_label",
            ],
        )
        write_csv(
            summary,
            [
                {
                    "cell_group": "Li||Cu",
                    "source_folder_name": "licu-1",
                    "selected_dataset_name": "licu-ds",
                    "label_key": "ce_collapse",
                    "observed_candidate_count": 1,
                    "limited_window_count": 0,
                    "protocol_censored_count": 0,
                    "first_observed_candidate_cycle": 2,
                    "last_cycle_index": 2,
                },
                {
                    "cell_group": "Li||Li",
                    "source_folder_name": "lili-1",
                    "selected_dataset_name": "lili-ds",
                    "label_key": "polarization_growth",
                    "observed_candidate_count": 1,
                    "limited_window_count": 0,
                    "protocol_censored_count": 0,
                    "first_observed_candidate_cycle": 2,
                    "last_cycle_index": 2,
                },
            ],
            [
                "cell_group",
                "source_folder_name",
                "selected_dataset_name",
                "label_key",
                "observed_candidate_count",
                "limited_window_count",
                "protocol_censored_count",
                "first_observed_candidate_cycle",
                "last_cycle_index",
            ],
        )
        write_csv(
            metadata,
            [
                {
                    "cell_id": "lili-1",
                    "source_folder_name": "lili-1",
                    "cell_group": "Li||Li",
                    "electrolyte_code": "LS-009",
                    "observed_candidate_total": 1,
                    "top_observed_label_keys": "polarization_growth:1",
                    "recommended_next_review": "review_lili",
                },
                {
                    "cell_id": "licu-1",
                    "source_folder_name": "licu-1",
                    "cell_group": "Li||Cu",
                    "electrolyte_code": "LHCE",
                    "observed_candidate_total": 1,
                    "top_observed_label_keys": "ce_collapse:1",
                    "recommended_next_review": "review_licu",
                },
            ],
            [
                "cell_id",
                "source_folder_name",
                "cell_group",
                "electrolyte_code",
                "observed_candidate_total",
                "top_observed_label_keys",
                "recommended_next_review",
            ],
        )
        write_csv(
            electrolyte,
            [
                {"cell_group": "Li||Li", "electrolyte_code": "LS-009", "cell_count": 1},
                {"cell_group": "Li||Cu", "electrolyte_code": "LHCE", "cell_count": 1},
            ],
            ["cell_group", "electrolyte_code", "cell_count"],
        )
        return {
            "lili": lili,
            "licu": licu,
            "events": events,
            "summary": summary,
            "metadata": metadata,
            "electrolyte": electrolyte,
        }

    def test_builds_report_and_figures_from_synthetic_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.write_fixture(root)
            out = root / "out"

            report = build_lmb_audit_visualization(
                paths["lili"],
                paths["licu"],
                paths["events"],
                paths["summary"],
                paths["metadata"],
                paths["electrolyte"],
                out,
            )

            self.assertEqual(len(report["figures"]), 6)
            for figure in report["figures"]:
                self.assertTrue((out / figure).exists())

    def test_report_keeps_training_and_performance_gates_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.write_fixture(root)
            report = build_lmb_audit_visualization(
                paths["lili"],
                paths["licu"],
                paths["events"],
                paths["summary"],
                paths["metadata"],
                paths["electrolyte"],
                root / "out",
            )

            self.assertFalse(report["training_allowed_now"])
            self.assertFalse(report["model_performance"])

    def test_lili_and_licu_are_separate_in_signal_counts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.write_fixture(root)
            report = build_lmb_audit_visualization(
                paths["lili"],
                paths["licu"],
                paths["events"],
                paths["summary"],
                paths["metadata"],
                paths["electrolyte"],
                root / "out",
            )

            counts = report["findings"]["signal_counts"]
            self.assertIn("Li||Li::polarization_growth", counts)
            self.assertIn("Li||Cu::ce_collapse", counts)

    def test_electrolyte_code_is_reported_as_code_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            paths = self.write_fixture(root)
            report = build_lmb_audit_visualization(
                paths["lili"],
                paths["licu"],
                paths["events"],
                paths["summary"],
                paths["metadata"],
                paths["electrolyte"],
                root / "out",
            )

            self.assertIn("partner-provided code only", report["electrolyte_code_interpretation"])


if __name__ == "__main__":
    unittest.main()
