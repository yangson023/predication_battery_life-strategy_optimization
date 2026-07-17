# LMB Public Source Data Parser Plan

生成日期：2026-06-29

本文说明 Nature Communications LMB source data Excel 的接入方式。当前目标是建立公开图源数据的 parser / audit 框架，用于 full-cell feature schema、label audit 和 partner full-cell 数据接入准备；不是训练模型，也不是生成正式训练集。

当前门禁：

```text
source_data_audit_only=True
model_training_allowed=False
```

## 1. 数据定位

Nature source data 是论文图表背后的数值数据，通常来自真实实验、表征或仿真，但已经按论文 figure 重新整理。它不是 BTSDA / Arbin / Neware 设备直接导出的完整原始数据，也不是标准化 full-cell training dataset。

因此：

- 可以用于 sheet inventory。
- 可以用于 selected sheet tiny parse。
- 可以用于 feature schema test。
- 可以用于 label audit 设计。
- 可以用于策略变量和机制特征启发。
- 不能直接训练模型。
- 不能直接声称 full-cell 模型性能。

## 2. 与 Partner Full-Cell 数据的关系

| 数据来源 | 项目角色 | 用途 | 不能做什么 |
| --- | --- | --- | --- |
| Nature public source data | 方法开发和特征启发 | parser 设计、feature schema、label audit、公开对照、策略变量设计 | 不能直接作为本项目最终训练结论 |
| partner full-cell / anode-free full-cell 数据 | 最终验证主体 | full-cell 寿命预警、策略优化、模型验证 | 到达前不能声称模型效果 |
| 当前 Li||Li / Li||Cu 数据 | LMB 机制测试数据 | CE、极化、电压异常、soft-short、warning proxy | 不能称为 full-cell 数据 |

公开 source data 可以帮助我们更快决定“应该提取哪些特征”，但不能替代 partner full-cell 数据。

## 3. Parser 输出

新增脚本：

```text
modules/data_pipeline/parse_public_lmb_nature_source_data.py
```

输出目录：

```text
outputs/lmb_public_source_data/nature_comm_source_data_audit_20260629
```

输出文件：

| 文件 | 用途 |
| --- | --- |
| `source_workbook_inventory.csv` | workbook 级清单 |
| `source_sheet_inventory.csv` | sheet 级类型推断与门禁 |
| `selected_sheet_parse_manifest.csv` | 被选中 sheet 的解析状态 |
| `public_lmb_source_long_preview.csv` | tiny long-format 预览表 |
| `source_data_parser_warnings.csv` | 解析警告 |
| `public_lmb_source_data_audit_report.json` | 机器可读报告 |
| `public_lmb_source_data_audit_report.md` | 人可读报告 |

## 4. Sheet 类型

当前 parser 只做轻量推断：

| inferred_sheet_type | 含义 | 用途 |
| --- | --- | --- |
| `cycle_capacity_ce` | cycle-capacity-CE 曲线或 CE-only 曲线 | feature schema test / label audit candidate |
| `time_voltage_current` | time-voltage-current 或 time-voltage 图源曲线 | voltage / protocol / strategy feature audit |
| `capacity_voltage_curve` | capacity-voltage 曲线 | curve-shape feature audit |
| `electrolyte_descriptor` | 电解液描述符或 C20 proxy | 电解液筛选 reward proxy |
| `spectroscopy_or_characterization` | Raman / XPS / NMR / peak fitting 等 | mechanism context only |
| `active_learning_metric` | active learning / SHAP / fold metric | strategy design reference |
| `figure_source_unknown` | 暂时无法归类 | audit-only until manual review |

## 5. 当前优先解析 Sheet

Ma / Amanchukwu workbook:

- `Figure 3a`
- `Figure 3b`
- `Figure S7`
- `Figure S16`

Liu / Li / Chen workbook:

- `Fig. 1f`
- `Fig. 1i`
- `Fig. 5c`
- `Fig. 6c`
- `Supplementary Fig. 36a`
- `Supplementary Fig. 37c`
- `Supplementary Fig. 42a`
- `Supplementary Fig. 43e`

这些 sheet 被选中是因为它们最接近 cycle-capacity-CE、time-voltage 或策略协议特征，不代表它们可以训练模型。

## 6. 接入顺序

后续顺序必须保持：

```text
source data inventory
-> selected sheet tiny parse
-> feature schema test
-> label audit
-> trainability audit
-> baseline-ready export
```

当前只完成前两步。模型训练仍然关闭。

## 7. 风险与限制

- sheet 是 figure-oriented，不是 cell-oriented。
- 同一 cell 或同一 protocol 可能出现在多个 figure 中，存在重复计数风险。
- trace_id 不等于独立 full-cell。
- CC / MPC 曲线不能随机混合作为训练样本。
- C20 proxy 不是 full lifetime RUL/EOL。
- Li||Cu 机制测试 sheet 不能标成 full-cell。
- 缺少统一 termination reason，所以不能直接声明 observed EOL。

## 8. 下一步

如果 parser 输出通过审查，下一步允许：

```text
public_source_feature_schema_test_allowed=True
public_source_label_audit_allowed=True
```

仍然禁止：

```text
model_training_allowed=False
formal_performance_claim_allowed=False
```
