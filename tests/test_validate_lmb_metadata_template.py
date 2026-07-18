import csv
import tempfile
import unittest
from pathlib import Path

from openpyxl import Workbook

from modules.data_pipeline.validate_lmb_metadata_template import (
    P0_FIELDS,
    P1_FIELDS,
    termination_interpretation,
    validate_metadata_template,
)


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


def complete_row(cell_id: str = "cell-1", cell_type: str = "Li||Cu 半电池") -> dict[str, str]:
    row = {header: "" for header in HEADERS}
    row.update(
        {
            "电池编号": cell_id,
            "电池类型": cell_type,
            "原始数据文件夹": f"C:/data/{cell_id}",
            "实验日期": "2026-06-19",
            "实验批次": "batch-a",
            "操作者": "partner",
            "测试设备/通道": "BTSDA channel 1",
            "正负极体系": "Li 金属 || Cu",
            "负极/基底材料": "Cu 箔",
            "锂片厚度(μm)": "50",
            "铜箔/基底信息": "普通 Cu 箔",
            "电池壳类型": "CR2032",
            "电解液溶剂": "DOL/DME",
            "锂盐": "LiTFSI",
            "锂盐浓度": "1 M",
            "电解液添加剂": "LiNO3",
            "电解液用量(μL)": "40",
            "隔膜材料/型号": "Celgard 2500",
            "电极面积(cm²)": "1.13",
            "电流密度(mA/cm²)": "1.0",
            "面容量(mAh/cm²)": "1.0",
            "压力条件": "500 psi",
            "测试温度(℃)": "25",
            "化成协议": "无",
            "循环协议": "1 mAh/cm² at 1 mA/cm²",
            "截止条件": "固定容量截止",
            "静置时间": "10 h",
            "是否协议变化": "否",
            "终止原因": "自然失效",
            "失效模式/现象": "容量归零",
            "是否异常实验": "否",
            "保密/公开级别": "仅内部",
            "填写完整度": "完整",
        }
    )
    return row


def write_workbook(path: Path, rows: list[dict[str, str]]) -> None:
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "填写模板"
    sheet.append(HEADERS)
    for row in rows:
        sheet.append([row.get(header, "") for header in HEADERS])
    workbook.save(path)


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


class LmbMetadataTemplateValidationTests(unittest.TestCase):
    def test_reaching_planned_cycle_count_is_protocol_censored(self) -> None:
        self.assertEqual(termination_interpretation("到达设定循环数"), "protocol_censored")
        self.assertEqual(termination_interpretation("达到计划循环数，未观察到明显失效"), "protocol_censored")

    def test_missing_p0_blocks_cell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workbook = root / "metadata.xlsx"
            row = complete_row()
            row["电解液溶剂"] = ""
            write_workbook(workbook, [row])

            report = validate_metadata_template(workbook, root / "out")
            gates = read_csv(root / "out" / "per_cell_metadata_gate.csv")

            self.assertFalse(report["training_allowed_now"])
            self.assertEqual(gates[0]["metadata_gate_status"], "metadata_blocked_missing_p0")

    def test_unknown_cell_type_blocks_cell(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workbook = root / "metadata.xlsx"
            write_workbook(workbook, [complete_row(cell_type="奇怪电池")])

            validate_metadata_template(workbook, root / "out")
            gates = read_csv(root / "out" / "per_cell_metadata_gate.csv")

            self.assertEqual(gates[0]["metadata_gate_status"], "metadata_unknown_cell_type")

    def test_complete_p0_but_missing_p1_is_partial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workbook = root / "metadata.xlsx"
            row = complete_row()
            for field in P1_FIELDS:
                row[field] = ""
            write_workbook(workbook, [row])

            validate_metadata_template(workbook, root / "out")
            gates = read_csv(root / "out" / "per_cell_metadata_gate.csv")

            self.assertEqual(gates[0]["metadata_gate_status"], "metadata_partial_needs_review")

    def test_lili_and_licu_are_counted_separately(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workbook = root / "metadata.xlsx"
            lili = complete_row("lili-1", "Li||Li 对称电池")
            lili["正负极体系"] = "Li 金属 || Li 金属"
            write_workbook(workbook, [lili, complete_row("licu-1", "Li||Cu 半电池")])

            validate_metadata_template(workbook, root / "out")
            summary = read_csv(root / "out" / "metadata_validation_summary.csv")
            summary_by_metric = {row["metric"]: row["value"] for row in summary}

            self.assertEqual(summary_by_metric["cell_group_count::Li||Li"], "1")
            self.assertEqual(summary_by_metric["cell_group_count::Li||Cu"], "1")

    def test_training_allowed_now_is_always_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            workbook = root / "metadata.xlsx"
            write_workbook(workbook, [complete_row()])

            report = validate_metadata_template(workbook, root / "out")
            gates = read_csv(root / "out" / "per_cell_metadata_gate.csv")

            self.assertFalse(report["training_allowed_now"])
            self.assertEqual(gates[0]["training_allowed_now"], "False")


if __name__ == "__main__":
    unittest.main()
