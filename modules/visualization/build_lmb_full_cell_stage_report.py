"""Create descriptive, advisor-facing figures for the current LMB full-cell stage.

The inputs are compact audit tables, not raw BTSDA exports.  The figures therefore
describe data coverage and early-cycle observations only; they never evaluate a
predictive model or infer a causal protocol effect.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


AUDIT_NOTE = "仅供审计说明，不代表模型性能"
PROTOCOL_LABELS = {
    "ncm811_li_0p98cm_charge0p2_discharge0p5_area_scaled": "0.98 cm 正极，0.2C 充 / 0.5C 放",
    "ncm811_li_1p2cm_charge0p5_discharge0p5": "1.2 cm 正极，0.5C 充 / 0.5C 放",
}
PROTOCOL_COLORS = {
    "ncm811_li_0p98cm_charge0p2_discharge0p5_area_scaled": "#1976d2",
    "ncm811_li_1p2cm_charge0p5_discharge0p5": "#d95f02",
}


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def as_float(value: str | None) -> float | None:
    if value in (None, ""):
        return None
    try:
        return float(value)
    except ValueError:
        return None


def as_int(value: str | None) -> int | None:
    number = as_float(value)
    return int(number) if number is not None else None


def ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def protocol_label(protocol_id: str) -> str:
    return PROTOCOL_LABELS.get(protocol_id, protocol_id)


def add_audit_note(figure: plt.Figure, title: str) -> None:
    figure.suptitle(title, fontsize=13, fontweight="bold", y=0.985)
    figure.text(0.5, 0.012, AUDIT_NOTE, ha="center", fontsize=9, color="#8b0000")


def make_censoring_figure(censor_rows: list[dict[str, str]], output_path: Path) -> None:
    rows = sorted(censor_rows, key=lambda row: as_int(row.get("censoring_long_cycle_index")) or 0)
    labels = [row["cell_id"].replace("-NCM811Li", "") for row in rows]
    values = [as_int(row.get("censoring_long_cycle_index")) or 0 for row in rows]
    colors = [PROTOCOL_COLORS.get(row.get("protocol_id", ""), "#777777") for row in rows]
    figure, axis = plt.subplots(figsize=(10, 5.4))
    bars = axis.barh(labels, values, color=colors, edgecolor="#333333", linewidth=0.5)
    for bar, value in zip(bars, values):
        axis.text(value + 0.8, bar.get_y() + bar.get_height() / 2, str(value), va="center", fontsize=9)
    axis.set_xlabel("确认存活至长循环序号")
    axis.set_title("各独立全电池的 protocol-censored 观测窗口", loc="left", fontsize=11)
    axis.grid(axis="x", alpha=0.25)
    axis.set_axisbelow(True)
    handles = [
        plt.Line2D([0], [0], color=color, linewidth=7, label=label)
        for protocol, label, color in [
            (key, protocol_label(key), color) for key, color in PROTOCOL_COLORS.items()
        ]
    ]
    axis.legend(handles=handles, title="设计与运行条件混杂分组", loc="lower right", fontsize=8)
    add_audit_note(figure, "LMB 全电池当前观测覆盖范围")
    figure.tight_layout(rect=(0, 0.04, 1, 0.94))
    ensure_parent(output_path)
    figure.savefig(output_path, dpi=180)
    plt.close(figure)


def plot_metric_by_cell(
    axis: plt.Axes,
    rows_by_cell: dict[str, list[dict[str, str]]],
    metric: str,
    ylabel: str,
) -> int:
    plotted = 0
    for cell_id, rows in sorted(rows_by_cell.items()):
        points = []
        for row in rows:
            x = as_int(row.get("current_long_cycle_index"))
            y = as_float(row.get(metric))
            if x is not None and y is not None:
                points.append((x, y, row.get("protocol_id", "")))
        if not points:
            continue
        points.sort()
        protocol_id = points[0][2]
        axis.plot(
            [point[0] for point in points],
            [point[1] for point in points],
            marker="o",
            markersize=2.6,
            linewidth=1.25,
            color=PROTOCOL_COLORS.get(protocol_id, "#777777"),
            label=cell_id.replace("-NCM811Li", ""),
        )
        plotted += 1
    axis.set_xlabel("长循环序号")
    axis.set_ylabel(ylabel)
    axis.grid(alpha=0.25)
    return plotted


def make_early_feature_figures(feature_rows: list[dict[str, str]], capacity_output: Path, mechanism_output: Path) -> dict[str, int]:
    rows_by_cell: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in feature_rows:
        rows_by_cell[row["cell_id"]].append(row)

    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    capacity_lines = plot_metric_by_cell(
        axes[0], rows_by_cell, "discharge_capacity_lag_1_mah", "前一循环放电容量（mAh）"
    )
    ce_lines = plot_metric_by_cell(
        axes[1], rows_by_cell, "coulombic_efficiency_rolling_mean_past_3_percent", "过去 3 圈平均库仑效率（%）"
    )
    axes[0].set_title("仅使用过去信息的容量观测")
    axes[1].set_title("仅使用过去信息的库仑效率观测")
    axes[1].legend(loc="best", fontsize=6.7, ncol=2, title="独立导出数据")
    add_audit_note(figure, "前 20 圈描述性轨迹：容量与库仑效率")
    figure.tight_layout(rect=(0, 0.04, 1, 0.94))
    ensure_parent(capacity_output)
    figure.savefig(capacity_output, dpi=180)
    plt.close(figure)

    figure, axes = plt.subplots(1, 2, figsize=(12, 4.8))
    hysteresis_lines = plot_metric_by_cell(
        axes[0], rows_by_cell, "voltage_hysteresis_rolling_mean_past_3_v", "过去 3 圈平均电压滞后（V）"
    )
    kinetic_lines = plot_metric_by_cell(
        axes[1], rows_by_cell, "discharge_duration_rolling_mean_past_3_s", "过去 3 圈平均放电时长（s）"
    )
    axes[0].set_title("电压/极化代理特征")
    axes[1].set_title("动力学代理特征")
    axes[1].legend(loc="best", fontsize=6.7, ncol=2, title="独立导出数据")
    add_audit_note(figure, "前 20 圈描述性轨迹：电压与动力学")
    figure.tight_layout(rect=(0, 0.04, 1, 0.94))
    ensure_parent(mechanism_output)
    figure.savefig(mechanism_output, dpi=180)
    plt.close(figure)
    return {
        "capacity_trace_count": capacity_lines,
        "ce_trace_count": ce_lines,
        "hysteresis_trace_count": hysteresis_lines,
        "kinetic_trace_count": kinetic_lines,
    }


def stage_markdown(report: dict[str, object]) -> str:
    return f"""# LMB 全电池当前阶段报告

> **仅供审计说明，不代表模型性能。** 本报告描述当前六组真实 LMB NCM811||Li 全电池导出数据；未训练、也未评价任何模型。

## 当前证据

- 独立全电池导出数据：**{report['independent_full_cell_count']}** 组。
- 仅使用过去信息构造的前 20 圈特征行：**{report['early_feature_row_count']}** 行。
- 已确认自然失效：**0** 组。六组均达到设定循环数后结束，因而属于 **protocol-censored 对照**，不是 EOL 事件。
- 设计与运行条件混杂分组：**{report['protocol_count']}** 个。由于正极几何尺寸和运行条件同时改变，跨组差异不能解释为单一充放电倍率的因果影响。

## 图集说明

- `full_cell_censoring_window_by_export.png`：六组数据已确认的存活观测窗口。
- `early_cycle_capacity_ce_trajectories.png`：仅使用过去信息的容量与库仑效率描述性轨迹。若未来标签同样来自容量或 CE，这两类特征仍具有同源信号风险。
- `early_cycle_voltage_kinetic_trajectories.png`：电压滞后与放电时长等机制代理特征。

## 当前门禁

`model_training_allowed=False`。下一项真正关键的数据里程碑是：获取 **3--5 组终止原因明确的自然失效或异常终止全电池**，并与 protocol-censored 对照同时保留。每组应保留 cycle/step/record 三层导出、BTS XML、终止原因、事件圈数、失效模式与证据位置，以及电流密度、面容量、电解液编号/配方、截止电压、温度、压力和化成/循环协议。

## 面向导师的解释

项目已经建立并验证了 LMB 全电池数据接入、工步配对和前期循环特征审计路径。当前主要瓶颈不是模型复杂度，而是缺少已观测到的全电池失效事件。现有数据可作为被正确识别的删失对照以及解析/特征工程验证数据，但不能支撑正式寿命预测结论。
"""


def stage_html(report: dict[str, object]) -> str:
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>LMB 全电池当前阶段图集</title>
  <style>
    body {{ margin: 0; font-family: "Microsoft YaHei", "Segoe UI", sans-serif; color: #17212b; background: #f5f7fa; }}
    main {{ max-width: 1180px; margin: 0 auto; padding: 28px 20px 48px; }}
    h1 {{ margin: 0 0 8px; }}
    h2 {{ margin-top: 32px; }}
    .notice {{ padding: 12px 15px; border-left: 4px solid #b42318; background: #fff1f0; }}
    .summary {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 12px; margin: 18px 0; }}
    .metric {{ background: #fff; border: 1px solid #d9e0e7; border-radius: 6px; padding: 14px; }}
    .metric strong {{ display: block; font-size: 25px; color: #0b5cab; }}
    figure {{ margin: 22px 0; background: #fff; border: 1px solid #d9e0e7; border-radius: 6px; padding: 14px; }}
    img {{ width: 100%; height: auto; display: block; }}
    figcaption {{ padding: 10px 4px 0; color: #44546a; }}
    code {{ background: #edf1f5; padding: 1px 4px; }}
  </style>
</head>
<body>
<main>
  <h1>LMB 全电池当前阶段图集</h1>
  <div class="notice"><strong>仅供审计说明，不代表模型性能。</strong> 当前六组 NCM811||Li 全电池均达到设定循环数后结束，属于 protocol-censored 对照，而非已观测到的自然失效事件。</div>
  <section class="summary">
    <div class="metric"><strong>{report['independent_full_cell_count']}</strong>独立全电池导出数据</div>
    <div class="metric"><strong>{report['early_feature_row_count']}</strong>前 20 圈 past-only 特征行</div>
    <div class="metric"><strong>0</strong>确认自然失效事件</div>
    <div class="metric"><strong>False</strong><code>model_training_allowed</code></div>
  </section>
  <h2>1. 观测窗口</h2>
  <figure><img src="full_cell_censoring_window_by_export.png" alt="全电池观测窗口"><figcaption>六组独立导出数据的确认存活窗口；颜色表示设计与运行条件混杂分组，不能作因果协议比较。</figcaption></figure>
  <h2>2. 前 20 圈容量与库仑效率</h2>
  <figure><img src="early_cycle_capacity_ce_trajectories.png" alt="容量与库仑效率轨迹"><figcaption>容量与 CE 为描述性、past-only 观测；未来若用同一信号构造标签，必须继续审查同源信号风险。</figcaption></figure>
  <h2>3. 前 20 圈电压与动力学代理特征</h2>
  <figure><img src="early_cycle_voltage_kinetic_trajectories.png" alt="电压与动力学轨迹"><figcaption>电压滞后和放电时长提供机制特征方向，但当前样本不用于模型训练或性能结论。</figcaption></figure>
  <h2>下一步数据门槛</h2>
  <p>优先收集 3--5 组终止原因明确的自然失效或异常终止全电池，并与 protocol-censored 对照共同保留；每组需保留 cycle/step/record、BTS XML、终止原因、事件圈数、失效模式及关键元数据。</p>
</main>
</body>
</html>
"""


def build_stage_report(
    features_path: Path,
    censor_labels_path: Path,
    protocol_summary_path: Path,
    output_root: Path,
) -> dict[str, object]:
    feature_rows = read_csv(features_path)
    censor_rows = read_csv(censor_labels_path)
    protocol_rows = read_csv(protocol_summary_path)
    if not feature_rows or not censor_rows:
        raise ValueError("Feature rows and protocol-censor label rows are required.")
    if any(row.get("event_observed", "").strip().lower() == "true" for row in censor_rows):
        raise ValueError("This descriptive protocol-censor report only accepts censored current cells.")

    output_root.mkdir(parents=True, exist_ok=True)
    censor_figure = output_root / "full_cell_censoring_window_by_export.png"
    capacity_figure = output_root / "early_cycle_capacity_ce_trajectories.png"
    mechanism_figure = output_root / "early_cycle_voltage_kinetic_trajectories.png"
    make_censoring_figure(censor_rows, censor_figure)
    trace_counts = make_early_feature_figures(feature_rows, capacity_figure, mechanism_figure)

    protocol_ids = sorted({row.get("protocol_id", "") for row in feature_rows})
    report = {
        "report_type": "lmb_full_cell_stage_report",
        "source_data_role": "true_lmb",
        "cell_scope": "lmb_full_cell",
        "independent_full_cell_count": len({row["cell_id"] for row in censor_rows}),
        "early_feature_row_count": len(feature_rows),
        "protocol_censored_cell_count": len(censor_rows),
        "observed_failure_cell_count": 0,
        "protocol_count": len(protocol_ids),
        "protocol_labels": {protocol_id: protocol_label(protocol_id) for protocol_id in protocol_ids},
        "trace_counts": trace_counts,
        "protocol_summary_row_count": len(protocol_rows),
        "model_performance_claimed": False,
        "model_training_allowed": False,
        "key_interpretation": "对六组 NCM811||Li 全电池导出数据的描述性审计。当前两个分组同时改变了设计和运行条件，跨组差异不能解释为单一充放电协议的因果效应。",
        "next_data_need": "补充终止原因明确的自然失效或异常终止全电池，并保留完整元数据及 BTSDA cycle/step/record/XML 导出。",
    }
    (output_root / "lmb_full_cell_stage_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    markdown = f"""# LMB Full-Cell Current Stage Report\n\n> **Audit-only / Not model performance.** This report describes the current six true-LMB NCM811||Li full-cell exports. It does not train or evaluate a model.\n\n## Current evidence\n\n- Independent full-cell exports: **{report['independent_full_cell_count']}**.\n- Early-cycle past-only feature rows: **{report['early_feature_row_count']}**.\n- Confirmed observed failures: **0**. All six cells reached their planned cycle count and are therefore **protocol-censored controls**, not EOL events.\n- Mixed design/operation condition groups: **{report['protocol_count']}**. Their differences must not be interpreted as a causal charging-rate effect because cathode geometry and operating condition change together.\n\n## Figure set\n\n- `full_cell_censoring_window_by_export.png`: confirmed survival windows for the six exports.\n- `early_cycle_capacity_ce_trajectories.png`: past-only capacity and CE descriptive trajectories. Capacity/CE remain same-signal-source-risk fields for any future label built from capacity/CE.\n- `early_cycle_voltage_kinetic_trajectories.png`: voltage-hysteresis and discharge-duration mechanism proxies.\n\n## Gate\n\n`model_training_allowed=False`. The next meaningful data milestone is **3--5 independent cells with confirmed natural failure or abnormal termination**, retained alongside protocol-censored controls. For each such cell, retain cycle/step/record exports, the BTS XML, termination reason, event cycle, failure mode/evidence, current density, areal capacity, electrolyte code/detail, voltage cutoffs, temperature, pressure, and formation/cycling protocol.\n\n## Advisor-facing interpretation\n\nThe project has a verified LMB full-cell intake and early-cycle feature-audit route. The immediate bottleneck is not model complexity; it is the absence of observed full-cell failure events. The current data are useful as correctly identified censored controls and as a parser/feature-engineering validation set, but they cannot support a formal lifetime-prediction claim.\n"""
    (output_root / "lmb_full_cell_stage_report.md").write_text(stage_markdown(report), encoding="utf-8")
    (output_root / "lmb_full_cell_stage_report.html").write_text(stage_html(report), encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build descriptive LMB full-cell stage figures from compact audit outputs.")
    parser.add_argument("--features", required=True, type=Path)
    parser.add_argument("--protocol-censor-labels", required=True, type=Path)
    parser.add_argument("--protocol-summary", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    return parser.parse_args()


if __name__ == "__main__":
    arguments = parse_args()
    build_stage_report(
        arguments.features,
        arguments.protocol_censor_labels,
        arguments.protocol_summary,
        arguments.output_root,
    )
