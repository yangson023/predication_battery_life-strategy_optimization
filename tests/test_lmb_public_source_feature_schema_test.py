import csv
import json
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.build_lmb_public_source_feature_schema_test import (
    build_public_source_feature_schema_test,
)


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_fixture(root: Path) -> Path:
    input_root = root / "input"
    write_csv(
        input_root / "source_sheet_inventory.csv",
        [
            {
                "workbook_name": "source_a.xlsx",
                "paper_id": "anode_free_public_source",
                "sheet_name": "Figure 3a",
                "inferred_sheet_type": "cycle_capacity_ce",
                "cell_scope": "anode_free_full_cell",
            },
            {
                "workbook_name": "source_a.xlsx",
                "paper_id": "anode_free_public_source",
                "sheet_name": "Figure S7",
                "inferred_sheet_type": "time_voltage_current",
                "cell_scope": "lmb_mechanism_test_not_full_cell",
            },
            {
                "workbook_name": "source_a.xlsx",
                "paper_id": "anode_free_public_source",
                "sheet_name": "Figure S16",
                "inferred_sheet_type": "electrolyte_descriptor",
                "cell_scope": "anode_free_full_cell",
            },
        ],
        ["workbook_name", "paper_id", "sheet_name", "inferred_sheet_type", "cell_scope"],
    )
    write_csv(
        input_root / "selected_sheet_parse_manifest.csv",
        [
            {
                "workbook_name": "source_a.xlsx",
                "paper_id": "anode_free_public_source",
                "sheet_name": "Figure 3a",
                "inferred_sheet_type": "cycle_capacity_ce",
                "parse_status": "parsed",
                "parsed_rows": 4,
                "parser_warning": "",
            },
            {
                "workbook_name": "source_a.xlsx",
                "paper_id": "anode_free_public_source",
                "sheet_name": "Figure S7",
                "inferred_sheet_type": "time_voltage_current",
                "parse_status": "parsed",
                "parsed_rows": 2,
                "parser_warning": "",
            },
            {
                "workbook_name": "source_a.xlsx",
                "paper_id": "anode_free_public_source",
                "sheet_name": "Figure S16",
                "inferred_sheet_type": "electrolyte_descriptor",
                "parse_status": "parsed",
                "parsed_rows": 2,
                "parser_warning": "",
            },
        ],
        [
            "workbook_name",
            "paper_id",
            "sheet_name",
            "inferred_sheet_type",
            "parse_status",
            "parsed_rows",
            "parser_warning",
        ],
    )
    write_csv(
        input_root / "public_lmb_source_long_preview.csv",
        [
            {
                "workbook_name": "source_a.xlsx",
                "paper_id": "anode_free_public_source",
                "sheet_name": "Figure 3a",
                "trace_id": "cell1",
                "cycle_index": 1,
                "capacity": 1.0,
                "normalized_capacity": "",
                "CE": 99.1,
                "voltage": "",
                "time_index": "",
                "feature_family": "cycle_capacity_ce",
                "cell_scope": "anode_free_full_cell",
            },
            {
                "workbook_name": "source_a.xlsx",
                "paper_id": "anode_free_public_source",
                "sheet_name": "Figure S7",
                "trace_id": "trace1",
                "cycle_index": "",
                "capacity": "",
                "normalized_capacity": "",
                "CE": "",
                "voltage": 0.12,
                "time_index": 0.1,
                "feature_family": "time_voltage_current",
                "cell_scope": "lmb_mechanism_test_not_full_cell",
            },
            {
                "workbook_name": "source_a.xlsx",
                "paper_id": "anode_free_public_source",
                "sheet_name": "Figure S16",
                "trace_id": "eli1",
                "cycle_index": "",
                "capacity": 1.2,
                "normalized_capacity": "",
                "CE": "",
                "voltage": "",
                "time_index": "",
                "feature_family": "electrolyte_descriptor_C20_proxy_not_RUL",
                "cell_scope": "anode_free_full_cell",
            },
        ],
        [
            "workbook_name",
            "paper_id",
            "sheet_name",
            "trace_id",
            "cycle_index",
            "capacity",
            "normalized_capacity",
            "CE",
            "voltage",
            "time_index",
            "feature_family",
            "cell_scope",
        ],
    )
    return input_root


class PublicSourceFeatureSchemaTest(unittest.TestCase):
    def test_builds_schema_outputs_with_training_gate_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            output_root = root / "out"
            docs_output = root / "docs" / "schema.md"

            report = build_public_source_feature_schema_test(input_root, output_root, docs_output, overwrite=True)

            self.assertFalse(report["model_training_allowed"])
            self.assertTrue(report["source_data_audit_only"])
            self.assertTrue(report["feature_schema_test_only"])
            self.assertTrue((output_root / "public_source_feature_family_schema.csv").exists())
            self.assertTrue((output_root / "public_source_partner_data_requirement_bridge.csv").exists())
            self.assertTrue(docs_output.exists())

    def test_report_has_no_formal_metric_terms(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            output_root = root / "out"
            docs_output = root / "docs" / "schema.md"

            build_public_source_feature_schema_test(input_root, output_root, docs_output, overwrite=True)

            report_text = (output_root / "public_source_feature_schema_test_report.md").read_text(encoding="utf-8")
            report_json = json.loads((output_root / "public_source_feature_schema_test_report.json").read_text(encoding="utf-8"))
            combined = report_text + json.dumps(report_json, ensure_ascii=False)
            for blocked in ["AUC", "F1", "RMSE", "accuracy"]:
                self.assertNotIn(blocked, combined)

    def test_c20_proxy_is_proxy_only_not_full_rul_or_eol(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            output_root = root / "out"
            docs_output = root / "docs" / "schema.md"

            build_public_source_feature_schema_test(input_root, output_root, docs_output, overwrite=True)

            labels = read_csv(output_root / "public_source_label_inspiration_matrix.csv")
            c20_rows = [row for row in labels if row["label_candidate"] == "C20_proxy_only"]
            self.assertTrue(c20_rows)
            self.assertIn("Not full lifetime RUL/EOL", c20_rows[0]["risk"])

    def test_mechanism_sheet_is_not_full_cell_training_data(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            output_root = root / "out"
            docs_output = root / "docs" / "schema.md"

            build_public_source_feature_schema_test(input_root, output_root, docs_output, overwrite=True)

            sheets = read_csv(output_root / "public_source_sheet_feature_availability.csv")
            mechanism = [row for row in sheets if row["sheet_name"] == "Figure S7"][0]
            self.assertEqual(mechanism["cell_scope"], "lmb_mechanism_test_not_full_cell")
            self.assertEqual(mechanism["usable_for_training_now"], "False")
            self.assertIn("mechanism_test_not_full_cell", mechanism["limitation_reason"])

    def test_schema_contains_required_feature_families(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            output_root = root / "out"
            docs_output = root / "docs" / "schema.md"

            build_public_source_feature_schema_test(input_root, output_root, docs_output, overwrite=True)

            schema = read_csv(output_root / "public_source_feature_family_schema.csv")
            families = {row["feature_family"] for row in schema}
            self.assertIn("capacity_retention", families)
            self.assertIn("coulombic_efficiency", families)
            self.assertIn("voltage_time", families)
            self.assertIn("electrolyte_strategy", families)

    def test_partner_bridge_contains_all_required_layers(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            output_root = root / "out"
            docs_output = root / "docs" / "schema.md"

            build_public_source_feature_schema_test(input_root, output_root, docs_output, overwrite=True)

            bridge = read_csv(output_root / "public_source_partner_data_requirement_bridge.csv")
            layers = {row["required_data_layer"] for row in bridge}
            self.assertIn("cycle layer", layers)
            self.assertIn("step layer", layers)
            self.assertIn("record layer", layers)
            self.assertIn("metadata", layers)

    def test_report_records_audit_only_gates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            input_root = build_fixture(root)
            output_root = root / "out"
            docs_output = root / "docs" / "schema.md"

            build_public_source_feature_schema_test(input_root, output_root, docs_output, overwrite=True)

            report_text = (output_root / "public_source_feature_schema_test_report.md").read_text(encoding="utf-8")
            self.assertIn("source_data_audit_only=True", report_text)
            self.assertIn("feature_schema_test_only=True", report_text)
            self.assertIn("model_training_allowed=False", report_text)


if __name__ == "__main__":
    unittest.main()
