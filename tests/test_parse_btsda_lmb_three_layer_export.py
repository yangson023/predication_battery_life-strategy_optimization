import csv
import tempfile
import unittest
from pathlib import Path

from modules.data_pipeline.parse_btsda_lmb_three_layer_export import parse_three_layer_export


CYCLE_HEADER = [
    "循环号",
    "起始绝对时间",
    "结束绝对时间",
    "充电容量(mAh)",
    "放电容量(mAh)",
    "充电比容量(mAh/g)",
    "放电比容量(mAh/g)",
    "充放电效率(%)",
    "充电能量(mWh)",
    "放电能量(mWh)",
    "充电比能量(mWh/g)",
    "放电比能量(mWh/g)",
    "中值电压(V)",
    "容量保持率(%)",
    "能量效率(%)",
]

STEP_HEADER = [
    "循环号",
    "工步号",
    "工步序号",
    "工步类型",
    "工步时间",
    "起始绝对时间",
    "结束绝对时间",
    "容量(mAh)",
    "比容量(mAh/g)",
    "充电容量(mAh)",
    "充电比容量(mAh/g)",
    "放电容量(mAh)",
    "放电比容量(mAh/g)",
    "能量(mWh)",
    "比能量(mWh/g)",
    "充电能量(mWh)",
    "充电比能量(mWh/g)",
    "放电能量(mWh)",
    "放电比能量(mWh/g)",
    "起始电压(V)",
    "结束电压(V)",
    "充电中值电压(V)",
    "放电中值电压(V)",
]

RECORD_HEADER = [
    "数据序号",
    "循环号",
    "工步号",
    "工步类型",
    "时间",
    "总时间",
    "电流(mA)",
    "电压(V)",
    "容量(mAh)",
    "比容量(mAh/g)",
    "能量(mWh)",
    "比能量(mWh/g)",
    "绝对时间",
    "功率(mW)",
    "SOC/DOD(%)",
]


def write_csv(path: Path, header: list[str], rows: list[list[str]]) -> None:
    with path.open("w", encoding="gbk", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(header)
        writer.writerows(rows)


def write_valid_dataset(root: Path) -> None:
    write_csv(
        root / "unit_cycle.csv",
        CYCLE_HEADER,
        [
            ["1", "2026-01-01 00:00:00", "2026-01-01 01:00:00", "1.5", "1.5", "1", "1", "100.0", "0.1", "0.1", "1", "1", "-0.05", "100", "100"],
            ["2", "2026-01-01 01:00:00", "2026-01-01 02:00:00", "1.5", "1.5", "1", "1", "104.0", "0.1", "0.1", "1", "1", "-0.06", "100", "100"],
        ],
    )
    write_csv(
        root / "unit_step.csv",
        STEP_HEADER,
        [
            ["1", "1", "1", "搁置", "00:10:00", "2026-01-01 00:00:00", "2026-01-01 00:10:00", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0.0", "0.0", "0", "0"],
            ["1", "2", "2", "恒流充电", "00:50:00", "2026-01-01 00:10:00", "2026-01-01 01:00:00", "1.5", "1", "1.5", "1", "0", "0", "0.1", "1", "0.1", "1", "0", "0", "0.0", "0.1", "0.05", "0"],
            ["2", "2", "3", "恒流放电", "00:50:00", "2026-01-01 01:00:00", "2026-01-01 02:00:00", "1.5", "1", "0", "0", "1.5", "1", "0.1", "1", "0", "0", "0.1", "1", "0.1", "-0.1", "0", "-0.05"],
        ],
    )
    write_csv(
        root / "unit_record.csv",
        RECORD_HEADER,
        [
            ["1", "1", "1", "搁置", "00:00:00", "00:00:00", "0.000", "0.0000", "0", "0", "0", "0", "2026-01-01 00:00:00", "0", "0"],
            ["2", "1", "2", "恒流充电", "00:00:30", "00:00:30", "1.500", "0.0500", "0.1", "0", "0", "0", "2026-01-01 00:00:30", "0.075", "0"],
            ["3", "2", "2", "恒流放电", "00:01:00", "00:01:00", "-1.500", "-0.0500", "0.1", "0", "0", "0", "2026-01-01 00:01:00", "0.075", "0"],
        ],
    )


class BtsdaLmbThreeLayerParserTests(unittest.TestCase):
    def test_gbk_three_layer_export_parses_and_samples_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            out = Path(tmp) / "out"
            root.mkdir()
            write_valid_dataset(root)

            report = parse_three_layer_export(
                input_root=root,
                output_root=out,
                dataset_name="unit",
                cell_type="Li||Li symmetric",
                record_sample_rows=2,
            )

            self.assertTrue(report["record_layer_available"])
            self.assertTrue(report["record_has_voltage_current_time"])
            self.assertFalse(report["training_allowed_now"])
            with (out / "normalized_record_sample.csv").open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["voltage_v"], "0.0")

    def test_missing_layer_marks_schema_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            out = Path(tmp) / "out"
            root.mkdir()
            write_valid_dataset(root)
            (root / "unit_record.csv").unlink()

            report = parse_three_layer_export(root, out, "unit", "Li||Cu CE half-cell")
            self.assertFalse(report["all_schema_gates_passed"])
            with (out / "schema_check.csv").open(encoding="utf-8", newline="") as handle:
                checks = list(csv.DictReader(handle))
            self.assertIn("fail", [row["status"] for row in checks if row["layer"] == "record"])

    def test_same_export_suffix_is_preferred_for_multi_export_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            out = Path(tmp) / "out"
            root.mkdir()

            write_csv(root / "unit_cycle-1.csv", CYCLE_HEADER, [["1", "t0", "t1", "1", "1", "1", "1", "100", "0.1", "0.1", "1", "1", "0.1", "100", "100"]])
            write_csv(root / "unit_step-1.csv", STEP_HEADER, [["1", "1", "1", "鎼佺疆", "00:00:30", "t0", "t1", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0"]])
            write_csv(root / "unit_record-1.csv", RECORD_HEADER, [["1", "1", "1", "鎼佺疆", "00:00:30", "00:00:30", "0", "0", "0", "0", "0", "0", "t0", "0", "0"]])

            write_csv(
                root / "unit_cycle-2.csv",
                CYCLE_HEADER,
                [
                    ["1", "t0", "t1", "1", "1", "1", "1", "100", "0.1", "0.1", "1", "1", "0.1", "100", "100"],
                    ["2", "t1", "t2", "1", "1", "1", "1", "100", "0.1", "0.1", "1", "1", "0.1", "100", "100"],
                ],
            )
            write_csv(
                root / "unit_step-2.csv",
                STEP_HEADER,
                [
                    ["1", "1", "1", "鎼佺疆", "00:00:30", "t0", "t1", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0"],
                    ["2", "1", "1", "鎼佺疆", "00:00:30", "t1", "t2", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0"],
                ],
            )
            write_csv(
                root / "unit_record-2.csv",
                RECORD_HEADER,
                [
                    ["1", "1", "1", "鎼佺疆", "00:00:30", "00:00:30", "0", "0", "0", "0", "0", "0", "t0", "0", "0"],
                    ["2", "2", "1", "鎼佺疆", "00:01:00", "00:01:00", "0", "0", "0", "0", "0", "0", "t1", "0", "0"],
                ],
            )

            report = parse_three_layer_export(root, out, "unit", "Li||Li symmetric")
            self.assertTrue(report["all_schema_gates_passed"])
            self.assertTrue(all(path.endswith("-2.csv") for path in report["layer_files"].values()))

    def test_requested_export_suffix_overrides_auto_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            out = Path(tmp) / "out"
            root.mkdir()

            write_csv(root / "unit_cycle-1.csv", CYCLE_HEADER, [["1", "t0", "t1", "1", "1", "1", "1", "100", "0.1", "0.1", "1", "1", "0.1", "100", "100"]])
            write_csv(root / "unit_step-1.csv", STEP_HEADER, [["1", "1", "1", "鎼佺疆", "00:00:30", "t0", "t1", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0"]])
            write_csv(root / "unit_record-1.csv", RECORD_HEADER, [["1", "1", "1", "鎼佺疆", "00:00:30", "00:00:30", "0", "0", "0", "0", "0", "0", "t0", "0", "0"]])
            write_csv(root / "unit_cycle-2.csv", CYCLE_HEADER, [["1", "t0", "t1", "1", "1", "1", "1", "100", "0.1", "0.1", "1", "1", "0.1", "100", "100"], ["2", "t1", "t2", "1", "1", "1", "1", "100", "0.1", "0.1", "1", "1", "0.1", "100", "100"]])
            write_csv(root / "unit_step-2.csv", STEP_HEADER, [["1", "1", "1", "鎼佺疆", "00:00:30", "t0", "t1", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0"], ["2", "1", "1", "鎼佺疆", "00:00:30", "t1", "t2", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0", "0"]])
            write_csv(root / "unit_record-2.csv", RECORD_HEADER, [["1", "1", "1", "鎼佺疆", "00:00:30", "00:00:30", "0", "0", "0", "0", "0", "0", "t0", "0", "0"], ["2", "2", "1", "鎼佺疆", "00:01:00", "00:01:00", "0", "0", "0", "0", "0", "0", "t1", "0", "0"]])

            report = parse_three_layer_export(
                root,
                out,
                "unit",
                "Li||Li symmetric",
                export_suffix_filter="1",
            )

            self.assertTrue(report["all_schema_gates_passed"])
            self.assertEqual(report["export_suffix_filter"], "1")
            self.assertTrue(all(path.endswith("-1.csv") for path in report["layer_files"].values()))

    def test_identical_layers_mark_distinct_gate_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            out = Path(tmp) / "out"
            root.mkdir()
            write_valid_dataset(root)
            content = (root / "unit_cycle.csv").read_bytes()
            (root / "unit_step.csv").write_bytes(content)
            (root / "unit_record.csv").write_bytes(content)

            report = parse_three_layer_export(root, out, "unit", "Li||Li symmetric")
            self.assertFalse(report["all_schema_gates_passed"])
            with (out / "schema_check.csv").open(encoding="utf-8", newline="") as handle:
                checks = list(csv.DictReader(handle))
            distinct = [row for row in checks if row["check_name"] == "layers_are_distinct"]
            self.assertEqual(distinct[0]["status"], "fail")

    def test_missing_required_field_marks_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            out = Path(tmp) / "out"
            root.mkdir()
            write_valid_dataset(root)
            bad_header = [column for column in CYCLE_HEADER if column != "充放电效率(%)"]
            write_csv(root / "unit_cycle.csv", bad_header, [["1"] * len(bad_header)])

            report = parse_three_layer_export(root, out, "unit", "Li||Li symmetric")
            self.assertFalse(report["all_schema_gates_passed"])
            with (out / "schema_check.csv").open(encoding="utf-8", newline="") as handle:
                checks = list(csv.DictReader(handle))
            ce_checks = [row for row in checks if row["detail"] == "充放电效率(%)"]
            self.assertEqual(ce_checks[0]["status"], "fail")

    def test_training_allowed_is_always_false(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "input"
            out = Path(tmp) / "out"
            root.mkdir()
            write_valid_dataset(root)

            report = parse_three_layer_export(root, out, "unit", "Li||Cu CE half-cell")
            self.assertFalse(report["training_allowed_now"])


if __name__ == "__main__":
    unittest.main()
