import csv
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.build_lmb_label_trainability_audit import build_lmb_label_trainability_audit


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
    metadata_gate = root / "metadata_gate.csv"
    write_csv(
        metadata_gate,
        [
            {
                "电池编号": "licu-1",
                "cell_group": "Li||Cu",
                "metadata_gate_status": "metadata_ready_for_label_audit",
                "termination_interpretation": "protocol_censored",
                "trainability_audit_prerequisite": "True",
                "training_allowed_now": "False",
            },
            {
                "电池编号": "lili-1",
                "cell_group": "Li||Li",
                "metadata_gate_status": "metadata_ready_for_label_audit",
                "termination_interpretation": "protocol_censored",
                "trainability_audit_prerequisite": "True",
                "training_allowed_now": "False",
            },
        ],
        [
            "电池编号",
            "cell_group",
            "metadata_gate_status",
            "termination_interpretation",
            "trainability_audit_prerequisite",
            "training_allowed_now",
        ],
    )
    metadata_aware = root / "metadata_aware.csv"
    write_csv(
        metadata_aware,
        [
            {"cell_id": "licu-1", "cell_group": "Li||Cu", "trainability_audit_allowed": "True"},
            {"cell_id": "lili-1", "cell_group": "Li||Li", "trainability_audit_allowed": "True"},
        ],
        ["cell_id", "cell_group", "trainability_audit_allowed"],
    )
    label_summary = root / "label_summary.csv"
    write_csv(
        label_summary,
        [
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "licu-1",
                "selected_dataset_name": "licu-ds",
                "label_key": "incomplete_capacity_event",
                "rows_scanned": "100",
                "observed_candidate_count": "4",
                "censored_candidate_count": "96",
                "limited_window_count": "0",
                "protocol_censored_count": "0",
                "first_observed_candidate_cycle": "20",
                "last_cycle_index": "100",
                "readiness": "candidate_audit_first",
            },
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "licu-1",
                "selected_dataset_name": "licu-ds",
                "label_key": "protocol_censored",
                "rows_scanned": "1",
                "observed_candidate_count": "0",
                "censored_candidate_count": "1",
                "limited_window_count": "1",
                "protocol_censored_count": "1",
                "first_observed_candidate_cycle": "",
                "last_cycle_index": "100",
                "readiness": "required_censoring_metadata",
            },
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "licu-1",
                "selected_dataset_name": "licu-ds",
                "label_key": "ce_instability",
                "rows_scanned": "100",
                "observed_candidate_count": "50",
                "censored_candidate_count": "50",
                "limited_window_count": "0",
                "protocol_censored_count": "0",
                "first_observed_candidate_cycle": "2",
                "last_cycle_index": "100",
                "readiness": "audit_only_threshold_review_required",
            },
            {
                "cell_group": "Li||Li",
                "source_folder_name": "lili-1",
                "selected_dataset_name": "lili-ds",
                "label_key": "polarization_growth",
                "rows_scanned": "120",
                "observed_candidate_count": "5",
                "censored_candidate_count": "115",
                "limited_window_count": "0",
                "protocol_censored_count": "0",
                "first_observed_candidate_cycle": "80",
                "last_cycle_index": "120",
                "readiness": "audit_only_voltage_threshold_review_required",
            },
        ],
        [
            "cell_group",
            "source_folder_name",
            "selected_dataset_name",
            "label_key",
            "rows_scanned",
            "observed_candidate_count",
            "censored_candidate_count",
            "limited_window_count",
            "protocol_censored_count",
            "first_observed_candidate_cycle",
            "last_cycle_index",
            "readiness",
        ],
    )
    event_scan = root / "event_scan.csv"
    write_csv(
        event_scan,
        [
            {
                "source_folder_name": "licu-1",
                "label_key": "incomplete_capacity_event",
                "observed_candidate": "True",
                "audit_only": "True",
                "protocol_censored": "False",
            },
            {
                "source_folder_name": "licu-1",
                "label_key": "protocol_censored",
                "observed_candidate": "False",
                "audit_only": "True",
                "protocol_censored": "True",
            },
            {
                "source_folder_name": "lili-1",
                "label_key": "polarization_growth",
                "observed_candidate": "True",
                "audit_only": "True",
                "protocol_censored": "False",
            },
        ],
        ["source_folder_name", "label_key", "observed_candidate", "audit_only", "protocol_censored"],
    )
    lili_features = root / "lili_features.csv"
    write_csv(lili_features, [{"source_folder_name": "lili-1", "cycle_index": 1}], ["source_folder_name", "cycle_index"])
    licu_features = root / "licu_features.csv"
    write_csv(licu_features, [{"source_folder_name": "licu-1", "cycle_index": 1}], ["source_folder_name", "cycle_index"])
    return {
        "metadata_gate": metadata_gate,
        "metadata_aware": metadata_aware,
        "label_summary": label_summary,
        "event_scan": event_scan,
        "lili_features": lili_features,
        "licu_features": licu_features,
    }


class LmbLabelTrainabilityAuditTests(unittest.TestCase):
    def run_audit(self, root: Path) -> dict[str, object]:
        paths = fixture(root)
        return build_lmb_label_trainability_audit(
            metadata_gate=paths["metadata_gate"],
            metadata_aware_summary=paths["metadata_aware"],
            audit_event_scan=paths["event_scan"],
            audit_label_summary=paths["label_summary"],
            lili_features=paths["lili_features"],
            licu_features=paths["licu_features"],
            output_root=root / "out",
        )

    def test_protocol_censored_is_not_observed_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_audit(root)
            rows = read_csv(root / "out" / "per_cell_label_trainability.csv")
            protocol_rows = [row for row in rows if row["label_key"] == "protocol_censored"]

            self.assertEqual(protocol_rows[0]["trainability_level"], "protocol_censored_only")
            self.assertEqual(protocol_rows[0]["terminal_protocol_censored"], "True")

    def test_lili_and_licu_are_separate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_audit(root)
            summary = read_csv(root / "out" / "label_trainability_summary.csv")
            groups = {row["cell_group"] for row in summary}

            self.assertEqual(groups, {"Li||Li", "Li||Cu"})

    def test_audit_only_labels_do_not_enter_trainable_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_audit(root)
            rows = read_csv(root / "out" / "per_cell_label_trainability.csv")
            by_label = {row["label_key"]: row["trainability_level"] for row in rows}

            self.assertEqual(by_label["ce_instability"], "audit_only")
            self.assertEqual(by_label["polarization_growth"], "audit_only")
            self.assertEqual(by_label["incomplete_capacity_event"], "trainable_candidate")

    def test_training_allowed_now_is_always_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_audit(root)
            rows = read_csv(root / "out" / "per_cell_label_trainability.csv")

            self.assertFalse(report["training_allowed_now"])
            self.assertEqual({row["training_allowed_now"] for row in rows}, {"False"})


if __name__ == "__main__":
    unittest.main()
