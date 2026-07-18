import csv
import json
import tempfile
import unittest
from pathlib import Path

import numpy as np
import scipy.io as sio

from modules.data_pipeline.parse_reg002_uppaluri_capacity_degradation import (
    parse_reg002_capacity_degradation,
)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def write_cell(path: Path, discharge: list[float]) -> None:
    n = len(discharge)
    sio.savemat(
        path,
        {
            "cap_chg_per_cycle": np.asarray(discharge, dtype=float).reshape(n, 1) + 0.02,
            "cap_dischg_per_cycle": np.asarray(discharge, dtype=float).reshape(n, 1),
            "equiv_cycle": np.arange(1, n + 1, dtype=float).reshape(n, 1),
        },
    )


class Reg002CapacityDegradationParserTests(unittest.TestCase):
    def test_parses_long_summary_and_label_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input"
            output_root = root / "out"
            input_root.mkdir()
            write_cell(input_root / "G1-Cell1_capacity_degradation.mat", [1.0, 0.95, 0.79, 0.69])
            write_cell(input_root / "G1-Cell2_capacity_degradation.mat", [1.0, 0.98, 0.93, 0.91])

            report = parse_reg002_capacity_degradation(input_root, output_root, overwrite=True)

            self.assertEqual(report["parsed_files"], 2)
            self.assertEqual(report["capacity_eol_80_observed_cells"], 1)
            self.assertFalse(report["model_training_allowed"])
            long_rows = read_csv(output_root / "reg002_capacity_degradation_long.csv")
            self.assertEqual(len(long_rows), 8)
            self.assertEqual({row["cell_scope"] for row in long_rows}, {"lmb_full_cell"})

    def test_formal_training_is_blocked_even_when_eol_is_observed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input"
            output_root = root / "out"
            input_root.mkdir()
            write_cell(input_root / "G2-Cell1_capacity_degradation.mat", [1.0, 0.9, 0.8, 0.7])

            parse_reg002_capacity_degradation(input_root, output_root, overwrite=True)

            labels = read_csv(output_root / "reg002_capacity_label_audit.csv")
            self.assertTrue(any(row["event_observed"] == "True" for row in labels))
            self.assertEqual({row["formal_trainable_label"] for row in labels}, {"False"})
            self.assertTrue(all("missing_protocol" in row["blocking_reason"] for row in labels))

    def test_gate_report_marks_model_training_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input"
            output_root = root / "out"
            input_root.mkdir()
            write_cell(input_root / "G3-Cell1_capacity_degradation.mat", [1.0, 0.99, 0.97])

            parse_reg002_capacity_degradation(input_root, output_root, overwrite=True)

            report = json.loads((output_root / "reg002_capacity_tiny_validation_report.json").read_text(encoding="utf-8"))
            gates = read_csv(output_root / "reg002_trainability_gate.csv")
            self.assertFalse(report["model_training_allowed"])
            self.assertFalse(report["formal_training_set_created"])
            self.assertIn("blocked", {row["gate_status"] for row in gates})

    def test_length_mismatch_is_truncated_for_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = root / "input"
            output_root = root / "out"
            input_root.mkdir()
            sio.savemat(
                input_root / "G4-Cell1_capacity_degradation.mat",
                {
                    "cap_chg_per_cycle": np.asarray([1.02, 0.97, 0.91], dtype=float).reshape(3, 1),
                    "cap_dischg_per_cycle": np.asarray([1.0, 0.95, 0.9, 0.79], dtype=float).reshape(4, 1),
                    "equiv_cycle": np.asarray([1, 2, 3, 4], dtype=float).reshape(4, 1),
                },
            )

            parse_reg002_capacity_degradation(input_root, output_root, overwrite=True)

            long_rows = read_csv(output_root / "reg002_capacity_degradation_long.csv")
            summary = read_csv(output_root / "reg002_cell_summary.csv")
            self.assertEqual(len(long_rows), 3)
            self.assertEqual(summary[0]["n_rows"], "3")


if __name__ == "__main__":
    unittest.main()
