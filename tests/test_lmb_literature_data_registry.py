import csv
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.lmb_literature_data_registry import (
    TEMPLATE_COLUMNS,
    audit_registry,
    write_template,
)


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=TEMPLATE_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({column: row.get(column, "") for column in TEMPLATE_COLUMNS})


class LmbLiteratureDataRegistryTests(unittest.TestCase):
    def test_template_contains_required_columns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "template.csv"
            write_template(path)

            with path.open("r", encoding="utf-8", newline="") as handle:
                reader = csv.DictReader(handle)
                self.assertEqual(reader.fieldnames, TEMPLATE_COLUMNS)

    def test_audit_marks_complete_lmb_source_for_tiny_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry.csv"
            output_root = root / "out"
            write_rows(
                registry,
                [
                    {
                        "source_name": "complete_lmb",
                        "url_or_doi": "https://doi.org/example",
                        "current_role": "unknown",
                        "is_lmb": "yes",
                        "is_direct_download_available": "yes",
                        "has_raw_cycling_table": "yes",
                        "has_charge_capacity": "yes",
                        "has_discharge_capacity": "yes",
                        "has_ce": "yes",
                        "has_voltage_current_curve": "yes",
                        "has_lmb_metadata": "yes",
                        "has_protocol_or_conditions": "yes",
                        "has_failure_or_stopping_reason": "yes",
                        "license_or_terms_clear": "yes",
                    }
                ],
            )

            report = audit_registry(registry, output_root)

            self.assertEqual(report["source_count"], 1)
            self.assertEqual(report["ready_for_tiny_validation_count"], 1)
            self.assertFalse(report["training_allowed"])
            with (output_root / "lmb_literature_source_audit.csv").open(encoding="utf-8") as handle:
                audit = list(csv.DictReader(handle))
            self.assertEqual(audit[0]["recommended_role"], "true_lmb_candidate")
            self.assertEqual(audit[0]["intake_decision"], "download_then_tiny_validation")

    def test_non_lmb_method_data_never_becomes_true_lmb(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            registry = root / "registry.csv"
            output_root = root / "out"
            write_rows(
                registry,
                [
                    {
                        "source_name": "benchmark",
                        "current_role": "transfer_auxiliary_data",
                        "is_lmb": "no",
                        "is_direct_download_available": "yes",
                        "has_raw_cycling_table": "yes",
                    }
                ],
            )

            audit_registry(registry, output_root)

            with (output_root / "lmb_literature_source_audit.csv").open(encoding="utf-8") as handle:
                audit = list(csv.DictReader(handle))
            self.assertEqual(audit[0]["recommended_role"], "transfer_auxiliary_data")
            self.assertEqual(audit[0]["intake_decision"], "method_or_transfer_reference_only")


if __name__ == "__main__":
    unittest.main()
