"""Create a Chinese full-cell LMB metadata and feature collection workbook.

The workbook is an intake template for partner-provided full-cell data. It does
not parse raw data, train models, or create labels.
"""

from __future__ import annotations

from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation


OUTPUT = Path("outputs/lmb_partner_metadata_template/lmb_full_cell_metadata_feature_template_cn_20260710.xlsx")

DATASETS = [
    {
        "source_folder_name": "26-0602(ncm811-li-LB-085)",
        "raw_folder_path": r"C:\Users\Lenovo\Desktop\LMB_data\26-0602(ncm811-li-LB-085)",
        "suggested_cell_id": "26-0602",
        "cathode_type": "NCM811",
        "anode_type": "Li metal",
        "electrolyte_code": "LB-085",
    },
    {
        "source_folder_name": "26-0610(ncm811-li-LB-085)",
        "raw_folder_path": r"C:\Users\Lenovo\Desktop\LMB_data\26-0610(ncm811-li-LB-085)",
        "suggested_cell_id": "26-0610",
        "cathode_type": "NCM811",
        "anode_type": "Li metal",
        "electrolyte_code": "LB-085",
    },
    {
        "source_folder_name": "26-0610-1(ncm811-li-LHCE)",
        "raw_folder_path": r"C:\Users\Lenovo\Desktop\LMB_data\26-0610-1(ncm811-li-LHCE)",
        "suggested_cell_id": "26-0610-1",
        "cathode_type": "NCM811",
        "anode_type": "Li metal",
        "electrolyte_code": "LHCE",
    },
]


def append_table(ws, headers: list[str], rows: list[list[object]]) -> None:
    ws.append(headers)
    for cell in ws[1]:
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = PatternFill("solid", fgColor="1F4E78")
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
    for row in rows:
        ws.append(row)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    for row in ws.iter_rows():
        for cell in row:
            cell.alignment = Alignment(vertical="top", wrap_text=True)
    for idx, header in enumerate(headers, start=1):
        width = min(max(len(str(header)) + 4, 14), 36)
        ws.column_dimensions[get_column_letter(idx)].width = width


def add_list_validation(ws, cell_range: str, values: list[str]) -> None:
    formula = '"' + ",".join(values) + '"'
    validation = DataValidation(type="list", formula1=formula, allow_blank=True)
    ws.add_data_validation(validation)
    validation.add(cell_range)


def build_workbook() -> Workbook:
    wb = Workbook()
    ws = wb.active
    ws.title = "填写总表"

    main_headers = [
        "填写状态",
        "数据文件夹名",
        "原始数据路径",
        "建议cell_id",
        "真实cell_id",
        "数据角色",
        "cell_scope",
        "是否full-cell",
        "是否anode-free",
        "电池形态",
        "正极材料",
        "正极面容量(mAh/cm2)",
        "正极载量(mg/cm2)",
        "负极类型",
        "锂箔厚度(um)",
        "N/P比",
        "电解液编号",
        "电解液可公开配方",
        "电解液体积(uL)",
        "E/C比(uL/mAh)",
        "隔膜",
        "压力条件",
        "测试温度(°C)",
        "电流密度(mA/cm2)",
        "倍率/C-rate",
        "上截止电压(V)",
        "下截止电压(V)",
        "化成协议",
        "循环协议",
        "计划循环数",
        "终止原因",
        "失效模式",
        "异常备注",
        "BTSDA导出日期",
        "操作者/批次备注",
        "保密/公开级别",
        "Codex初判",
    ]
    main_rows = []
    for dataset in DATASETS:
        main_rows.append(
            [
                "待填写",
                dataset["source_folder_name"],
                dataset["raw_folder_path"],
                dataset["suggested_cell_id"],
                "",
                "true_lmb_candidate",
                "lmb_full_cell_candidate",
                "是",
                "否/未知",
                "扣式/软包/其他(待填)",
                dataset["cathode_type"],
                "",
                "",
                dataset["anode_type"],
                "",
                "",
                dataset["electrolyte_code"],
                "",
                "",
                "",
                "",
                "",
                "室温/待填",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "",
                "内部科研",
                "full-cell候选；需补P0元数据后才可进入标签审计",
            ]
        )
    append_table(ws, main_headers, main_rows)
    add_list_validation(ws, "A2:A200", ["待填写", "已填写", "需复核", "暂缺"])
    add_list_validation(ws, "H2:H200", ["是", "否", "未知"])
    add_list_validation(ws, "I2:I200", ["是", "否", "未知", "N/A"])
    add_list_validation(ws, "F2:F200", ["true_lmb_candidate", "true_lmb", "diagnostic_only", "unknown"])
    add_list_validation(ws, "G2:G200", ["lmb_full_cell_candidate", "lmb_full_cell", "anode_free_full_cell", "unknown_scope"])

    ws = wb.create_sheet("数据层检查")
    layer_headers = [
        "数据文件夹名",
        "cycle层CSV是否存在",
        "step层CSV是否存在",
        "record层CSV是否存在",
        "BTS工步/XML是否存在",
        "原始NDAX是否归档",
        "cycle层关键字段",
        "step层关键字段",
        "record层关键字段",
        "可做的第一轮工作",
        "阻断项",
    ]
    layer_rows = [
        [
            d["source_folder_name"],
            "待检查",
            "待检查",
            "待检查",
            "待检查",
            "待检查",
            "循环号、充/放电容量、CE、容量保持率",
            "循环号、工步类型、电压、容量、时间",
            "时间、电压、电流、容量、工步类型",
            "intake + tiny validation",
            "缺少cycle层会阻断capacity_eol；缺少终止原因会阻断observed EOL解释",
        ]
        for d in DATASETS
    ]
    append_table(ws, layer_headers, layer_rows)
    add_list_validation(ws, "B2:F200", ["存在", "不存在", "待检查", "不适用"])

    ws = wb.create_sheet("特征字段收集")
    feature_headers = [
        "特征族",
        "建议字段/特征",
        "所需数据层",
        "优先级",
        "是否可由BTSDA导出计算",
        "是否需要元数据",
        "是否存在泄漏风险",
        "填写/计算备注",
    ]
    feature_rows = [
        ["容量衰减", "discharge_capacity_retention; capacity_fade_slope_past_k", "cycle", "P0", "是", "初始容量/有效循环窗口", "高，同源容量风险", "用于capacity_eol需t-k horizon隔离"],
        ["库伦效率", "CE; ce_rolling_mean; ce_rolling_std; ce_drop_rate", "cycle", "P0", "是", "CE计算方式/设备精度", "高，同源CE风险", "需确认CE是否直接导出或由容量计算"],
        ["电压滞后", "charge_median_voltage - discharge_median_voltage", "step/cycle", "P1", "可能", "协议、电流密度", "中", "可作为极化proxy"],
        ["极化增长", "voltage_hysteresis_trend; end_voltage_gap_trend", "step/cycle", "P1", "可能", "协议、电流密度", "中", "需要稳定工步对齐"],
        ["动力学/时长", "charge_duration_trend; discharge_duration_trend", "step", "P1", "可能", "倍率/电流密度", "中", "恒流协议下更有解释力"],
        ["曲线形状", "dQ/dV; dV/dQ; plateau duration; curve area", "record", "P2", "需要record", "采样间隔/状态标签", "中", "先tiny validation，不直接全量跑"],
        ["软短路/异常", "rest_voltage_drop; abnormal_voltage_noise; CE>100% flag", "record/step/cycle", "P2", "可能", "异常备注/终止原因", "高，需人工复核", "先audit-only"],
        ["归一化特征", "current_density_normalized; areal_capacity_normalized", "metadata+cycle", "P0", "否", "电流密度、面容量、电极面积", "低", "跨cell比较必需"],
    ]
    append_table(ws, feature_headers, feature_rows)

    ws = wb.create_sheet("标签与门禁")
    label_headers = [
        "标签/门禁",
        "信号来源",
        "候选定义",
        "必须字段",
        "observed判断",
        "censored判断",
        "当前是否允许训练",
        "备注",
    ]
    label_rows = [
        ["capacity_eol_80", "放电容量/容量保持率", "容量保持率低于80%并持续若干有效循环", "cycle层容量、初始容量、终止原因、计划循环数", "真实达到阈值且非协议终止", "未达到阈值或到计划循环数", "否", "第一优先标签，但必须先审计"],
        ["capacity_eol_70", "放电容量/容量保持率", "容量保持率低于70%并持续若干有效循环", "同上", "同上", "同上", "否", "事件更少，通常作为次级标签"],
        ["CE_collapse", "CE曲线", "CE突降或低于复核阈值", "充/放电容量或直接CE、设备精度", "未来窗口发生持续CE异常", "窗口不足或未发生", "否", "需要horizon隔离"],
        ["polarization_failure", "电压滞后/极化proxy", "电压滞后或极化proxy持续升高", "step/record电压、协议", "持续越过审计阈值", "未越过或数据层不足", "否", "机制标签，先audit"],
        ["voltage_instability", "电压曲线/异常电压", "异常波动、突降、噪声或rest异常", "record/step、电压、异常备注", "重复异常且非设备伪影", "未观察到或缺少record", "否", "先audit-only"],
        ["protocol_censored", "计划循环数/终止原因", "达到计划循环数或人为/设备终止", "计划循环数、终止原因", "不是failure标签", "作为censoring状态", "否", "所有建模前必须处理"],
        ["intake_gate", "文件/元数据", "cell_id、cell_scope、数据层可追踪", "填写总表+数据层检查", "通过后进入tiny validation", "缺失则阻断", "否", "第一步门禁"],
        ["metadata_gate", "元数据", "P0字段足够判断full-cell和censoring", "终止原因、协议、电流密度、面容量等", "通过后进入label scan", "缺失则只可audit", "否", "不完整不训练"],
    ]
    append_table(ws, label_headers, label_rows)

    ws = wb.create_sheet("字段说明")
    field_headers = ["字段", "优先级", "中文说明", "推荐填写方式", "缺失影响"]
    field_rows = [
        ["cell_id", "P0", "唯一电池编号", "尽量与文件夹/实验记录一致", "阻断intake追踪"],
        ["cell_scope", "P0", "full-cell/anode-free/unknown", "本批先填lmb_full_cell_candidate", "scope不明禁止训练"],
        ["N/P比", "P0/P1", "负极容量/正极容量比例", "Li金属过量full-cell尽量填写；anode-free填N/A", "影响锂库存和寿命解释"],
        ["正极面容量", "P0", "正极单位面积容量", "mAh/cm2", "影响归一化与跨cell比较"],
        ["电流密度", "P0", "单位面积电流", "mA/cm2；若只有电流需给电极面积", "影响协议归一化"],
        ["终止原因", "P0", "为什么停止测试", "到达计划循环数/容量衰减/短路/设备停止/人为停止/未知", "缺失则不能声称observed EOL"],
        ["循环协议", "P0", "倍率、电压窗口、恒流/恒压、rest等", "可用BTS工步文件辅助", "缺失阻断baseline-ready"],
        ["BTSDA导出层", "P0", "cycle/step/record/XML可用性", "在数据层检查表中填写", "决定可提取特征范围"],
        ["电解液编号", "P0", "如LB-085、LHCE", "编号即可；配方若保密可写不可公开", "无法分组解释电解液效应"],
        ["保密/公开级别", "P1", "数据能否写入论文/展示", "内部科研/可公开/需导师确认", "影响后续报告措辞"],
    ]
    append_table(ws, field_headers, field_rows)

    ws = wb.create_sheet("填写说明")
    instruction_headers = ["对象", "说明"]
    instruction_rows = [
        ["给你/partner", "先填黄色/P0字段：真实cell_id、终止原因、循环协议、计划循环数、电流密度、面容量、数据层是否存在。"],
        ["关于full-cell", "本批文件夹名显示ncm811-li，暂标记为lmb_full_cell_candidate；待元数据确认后再改成lmb_full_cell。"],
        ["关于训练", "填写表格不代表允许训练；必须先过intake、metadata、feature schema、label audit、leakage gate。"],
        ["关于缺失字段", "不知道就写未知，不要猜。未知比错误填写更安全。"],
        ["关于N/P比", "如果partner能调整或记录，Li金属过量full-cell建议至少记录具体N/P；anode-free写N/A。具体最佳区间需由导师和实验目标决定，不在表里强行给定。"],
        ["关于数据路径", "本表只记录路径，不移动、不删除、不处理原始数据。"],
    ]
    append_table(ws, instruction_headers, instruction_rows)

    for sheet in wb.worksheets:
        sheet.sheet_view.showGridLines = True
        for row in sheet.iter_rows():
            for cell in row:
                cell.alignment = Alignment(vertical="top", wrap_text=True)

    return wb


def main() -> None:
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    workbook = build_workbook()
    workbook.save(OUTPUT)
    print(OUTPUT)


if __name__ == "__main__":
    main()
