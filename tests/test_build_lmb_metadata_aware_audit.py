import csv
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from modules.data_pipeline.build_lmb_metadata_aware_audit import build_metadata_aware_audit


HEADERS = [
    "电池编号",
    "电池类型",
    "原始数据文件夹",
    "实验日期",
    "实验批次",
    "操作者",
    "测试设备/通道",
    "正负极体系",
    "正极材料",
    "负极/基底材料",
    "锂片厚度(μm)",
    "铜箔/基底信息",
    "电池壳类型",
    "电解液溶剂",
    "锂盐",
    "锂盐浓度",
    "电解液添加剂",
    "电解液用量(μL)",
    "隔膜材料/型号",
    "电极面积(cm²)",
    "电流密度(mA/cm²)",
    "面容量(mAh/cm²)",
    "N/P比",
    "压力条件",
    "测试温度(℃)",
    "化成协议",
    "循环协议",
    "截止条件",
    "静置时间",
    "是否协议变化",
    "终止原因",
    "失效模式/现象",
    "是否异常实验",
    "备注",
    "保密/公开级别",
    "填写完整度",
]


def write_csv(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def metadata_row(cell_id: str, cell_type: str, electrolyte_code: str) -> dict[str, str]:
    row = {header: "" for header in HEADERS}
    row.update(
        {
            "电池编号": cell_id,
            "电池类型": cell_type,
            "原始数据文件夹": f"C:/data/{cell_id}",
            "电解液溶剂": electrolyte_code,
            "隔膜材料/型号": "Celgard2500",
            "压力条件": "500psi",
            "静置时间": "10h",
            "锂片厚度(μm)": "400",
        }
    )
    return row


def write_metadata_workbook(path: Path, rows: list[dict[str, str]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "填写模板"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append([row.get(header, "") for header in HEADERS])
    workbook.save(path)


def write_fixture(root: Path) -> dict[str, Path]:
    metadata = root / "metadata.xlsx"
    write_metadata_workbook(
        metadata,
        [
            metadata_row("lili-1", "Li||Li 对称电池", "LS-009"),
            metadata_row("licu-1", "Li||Cu 半电池", "LHCE"),
        ],
    )
    gate = root / "gate.csv"
    write_csv(
        gate,
        [
            {
                "电池编号": "lili-1",
                "cell_group": "Li||Li",
                "电池类型": "Li||Li 对称电池",
                "原始数据文件夹": "C:/data/lili-1",
                "metadata_gate_status": "metadata_blocked_missing_p0",
            },
            {
                "电池编号": "licu-1",
                "cell_group": "Li||Cu",
                "电池类型": "Li||Cu 半电池",
                "原始数据文件夹": "C:/data/licu-1",
                "metadata_gate_status": "metadata_blocked_missing_p0",
            },
        ],
        ["电池编号", "cell_group", "电池类型", "原始数据文件夹", "metadata_gate_status"],
    )
    label_summary = root / "label_summary.csv"
    write_csv(
        label_summary,
        [
            {
                "cell_group": "Li||Li",
                "source_folder_name": "lili-1",
                "selected_dataset_name": "lili-ds",
                "label_key": "polarization_growth",
                "rows_scanned": 10,
                "observed_candidate_count": 3,
                "limited_window_count": 0,
                "protocol_censored_count": 1,
                "first_observed_candidate_cycle": 5,
                "last_cycle_index": 10,
            },
            {
                "cell_group": "Li||Cu",
                "source_folder_name": "licu-1",
                "selected_dataset_name": "licu-ds",
                "label_key": "incomplete_capacity_event",
                "rows_scanned": 12,
                "observed_candidate_count": 4,
                "limited_window_count": 0,
                "protocol_censored_count": 1,
                "first_observed_candidate_cycle": 7,
                "last_cycle_index": 12,
            },
        ],
        [
            "cell_group",
            "source_folder_name",
            "selected_dataset_name",
            "label_key",
            "rows_scanned",
            "observed_candidate_count",
            "limited_window_count",
            "protocol_censored_count",
            "first_observed_candidate_cycle",
            "last_cycle_index",
        ],
    )
    event_scan = root / "event_scan.csv"
    write_csv(
        event_scan,
        [{"source_folder_name": "licu-1", "label_key": "incomplete_capacity_event", "trainable_label": "False"}],
        ["source_folder_name", "label_key", "trainable_label"],
    )
    lili_features = root / "lili_features.csv"
    write_csv(
        lili_features,
        [{"source_folder_name": "lili-1", "cycle_index": 1}, {"source_folder_name": "lili-1", "cycle_index": 2}],
        ["source_folder_name", "cycle_index"],
    )
    licu_features = root / "licu_features.csv"
    write_csv(
        licu_features,
        [{"source_folder_name": "licu-1", "cycle_index": 1}],
        ["source_folder_name", "cycle_index"],
    )
    return {
        "metadata": metadata,
        "gate": gate,
        "label_summary": label_summary,
        "event_scan": event_scan,
        "lili_features": lili_features,
        "licu_features": licu_features,
    }


class LmbMetadataAwareAuditTests(unittest.TestCase):
    def run_audit(self, root: Path) -> dict[str, object]:
        paths = write_fixture(root)
        return build_metadata_aware_audit(
            metadata_workbook=paths["metadata"],
            metadata_gate=paths["gate"],
            audit_label_summary=paths["label_summary"],
            audit_event_scan=paths["event_scan"],
            lili_features=paths["lili_features"],
            licu_features=paths["licu_features"],
            output_root=root / "out",
        )

    def test_electrolyte_code_merges_into_cell_summary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_audit(root)
            rows = read_csv(root / "out" / "metadata_aware_cell_summary.csv")
            by_cell = {row["cell_id"]: row for row in rows}

            self.assertEqual(by_cell["lili-1"]["electrolyte_code"], "LS-009")
            self.assertEqual(by_cell["licu-1"]["electrolyte_code"], "LHCE")

    def test_lili_and_licu_are_separate_in_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_audit(root)

            self.assertEqual(report["cell_group_counts"]["Li||Li"], 1)
            self.assertEqual(report["cell_group_counts"]["Li||Cu"], 1)

    def test_missing_electrolyte_detail_is_flagged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self.run_audit(root)
            risks = read_csv(root / "out" / "unresolved_metadata_risks.csv")

            self.assertIn("electrolyte_detail_missing", {row["risk_key"] for row in risks})

    def test_missing_termination_reason_blocks_trainability_audit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_audit(root)
            cells = read_csv(root / "out" / "metadata_aware_cell_summary.csv")

            self.assertFalse(report["trainability_audit_allowed"])
            self.assertEqual({row["termination_resolution_status"] for row in cells}, {"unresolved_termination_reason"})

    def test_training_allowed_now_is_always_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = self.run_audit(root)
            cells = read_csv(root / "out" / "metadata_aware_cell_summary.csv")

            self.assertFalse(report["training_allowed_now"])
            self.assertEqual({row["training_allowed_now"] for row in cells}, {"False"})


if __name__ == "__main__":
    unittest.main()
