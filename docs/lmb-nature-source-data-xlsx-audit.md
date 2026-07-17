# LMB Nature Communications Source Data XLSX Audit

生成日期：2026-06-29

输入文件：

- `C:\Users\Lenovo\Downloads\41467_2025_63303_MOESM3_ESM.xlsx`
- `C:\Users\Lenovo\Downloads\41467_2025_66271_MOESM3_ESM.xlsx`

本文只审计 Nature Communications source data Excel 的内容结构、full-cell 建模适配性和特征工程启示。本文不训练模型，不生成 processed 数据，也不把图源数据称为模型性能。

当前门禁：

```text
model_training_allowed=False
source_data_xlsx_is_not_clean_training_dataset=True
full_cell_training_requires_intake_and_label_audit=True
```

## 1. 总体结论

这两个 Excel 都很有价值，但价值类型不同：

| 文件 | 对应论文 | 数据形态 | 是否 LMB full-cell / anode-free | 是否适合直接训练 full-cell 寿命模型 | 最适合当前用途 |
| --- | --- | --- | --- | --- | --- |
| `41467_2025_63303_MOESM3_ESM.xlsx` | Ma / Amanchukwu, active learning for anode-free LMB electrolyte screening | 25 个 sheet；包含 cycle-capacity/CE、部分 time-voltage、Raman/CV/XPS/NMR、active-learning 统计 | 是，核心为 anode-free Cu||LFP；另含 Li||Cu 机制测试 | 不适合直接训练完整寿命模型；可作为 anode-free 数据接入和策略/电解液筛选标签参考 | 电解液筛选、capacity retention proxy、CE/容量曲线特征、主动学习策略设计 |
| `41467_2025_66271_MOESM3_ESM.xlsx` | Liu / Li / Chen, tailored charging protocol for initially anode-free pouch cells | 175 个 sheet；大量按 figure 拆分的 time-voltage、capacity-voltage、CE/capacity、protocol/current 数据 | 是，核心为 initially anode-free LMB；含 coin cell、Li||Cu、pouch cell | 不适合直接训练通用寿命模型；可做机制特征和策略变量设计 | 充电协议特征、CC vs MPC 对比、voltage / capacity / CE 曲线特征、protocol-aware feature 设计 |

关键判断：

1. 这两个文件是 **source data for figures**，不是已经整理好的 per-cell training dataset。
2. 它们包含真实 anode-free / LMB full-cell 相关数据，比当前实验室 Li||Li / Li||Cu 半电池更接近 full-cell 方向。
3. 但它们缺少统一 `cell_id`、完整 metadata、统一终止原因、统一 protocol-censoring 标记和标准化 label 表，因此不能直接进入模型训练。
4. 它们非常适合帮助我们设计 full-cell feature schema、label policy 和后续 parser。

## 2. 文件一：Ma / Amanchukwu active-learning anode-free 数据

### 2.1 Workbook 结构

| 项目 | 数值 |
| --- | --- |
| sheet 数 | 25 |
| electrochemical candidate sheets | 约 10 个 |
| 含 cycle 信息 sheet | 约 6 个 |
| 含 capacity 信息 sheet | 约 7 个 |
| 含 CE 信息 sheet | 约 5 个 |
| 含 voltage/time 信息 sheet | 约 2 个 |
| 含 spectroscopy / characterization 信息 sheet | 多个，包括 Raman、XPS、NMR 等 |

### 2.2 关键 sheet

| sheet | 行列规模 | 主要内容 | 项目用途 |
| --- | --- | --- | --- |
| `Figure 1b` | 527 行 x 6 列 | `Cycle number` + i-v 五条容量曲线 | 可用于 capacity retention 曲线解析和早期退化 proxy 设计 |
| `Figure 3a` | 303 行 x 21 列 | 多个电解液候选的 `Cap` 与 `CE`，如 `6-3-cell1-Cap`、`6-3-cell1-CE` | 最接近可用的 per-cycle 表；可构建电解液-电池曲线审计 |
| `Figure 3b` | 303 行 x 15 列 | 多个 cell 的归一化 capacity 曲线 | 适合做 normalized capacity trend、capacity fade slope |
| `Figure S7` | 37467 行 x 22 列 | 多个 cell 的 `Time (hours)` / `Voltage (V)` 曲线 | 可启发 voltage/time curve features，但需要重新解析成 long format |
| `Figure S15` | 30 行 x 15 列 | rate capability / discharge capacity data | 可用于倍率相关容量保持特征，不适合寿命训练 |
| `Figure S16` | 7 行 x 4 列 | `ELi`、Raman peak center、20th-cycle discharge capacity | 可用于电解液 descriptor 与 C20 标签的关系审计 |

### 2.3 训练适配性判断

| 检查项 | 结论 |
| --- | --- |
| 是否 true LMB / anode-free full-cell | 是，核心为 anode-free Cu||LFP full-cell；但部分 Li||Cu 是机制测试 |
| 是否有 raw cycling table | 部分有，尤其 `Figure 3a/3b` 的 per-cycle capacity/CE |
| 是否有统一 cell manifest | 没有 |
| 是否有统一 metadata 表 | 不完整 |
| 是否有 termination reason | 没有看到标准化字段 |
| 是否有 observed EOL 标签 | 没有直接提供 |
| 是否能定义 `capacity_eol_80` | 可能只能对部分曲线尝试，但必须先检查初始容量、归一化基准和终止窗口 |
| 是否适合 full-cell 直接训练 | 不适合 |
| 是否适合 label audit / feature schema test | 适合 |

### 2.4 对特征提取的启示

优先可提取：

- `cycle_index`
- `discharge_capacity`
- `normalized_capacity`
- `capacity_fade_slope`
- `capacity_retention_at_20_cycle`
- `CE`
- `CE_rolling_mean`
- `CE_rolling_std`
- `CE_instability_count`
- `time_voltage_curve_features`
- `voltage_rise_or_drop_shape`
- electrolyte descriptor fields, including `ELi` and spectroscopy-derived descriptors if mapping is clear

不应直接作为模型特征：

- 同 cycle 的 capacity 直接预测同 cycle 的 capacity label。
- 同 cycle 的 CE 直接预测同 cycle 的 CE label。
- 图源 sheet 中的 figure label、batch index、plot-only columns。

更合适的标签：

- `C20_normalized_capacity_proxy`
- `capacity_retention_proxy`
- `sustained_CE_degradation_audit`
- `electrolyte_screening_reward_proxy`

不适合直接定义：

- full lifetime RUL
- robust `capacity_eol_80`
- natural observed EOL

## 3. 文件二：Liu / Li / Chen charging-protocol 数据

### 3.1 Workbook 结构

| 项目 | 数值 |
| --- | --- |
| sheet 数 | 175 |
| electrochemical candidate sheets | 约 101 个 |
| 含 cycle 信息 sheet | 约 38 个 |
| 含 capacity 信息 sheet | 约 31 个 |
| 含 CE 信息 sheet | 约 27 个 |
| 含 voltage 信息 sheet | 约 60 个 |
| 含 current 信息 sheet | 约 23 个 |
| 含 time 信息 sheet | 约 45 个 |
| spectroscopy / characterization sheet | 多个，包括 XPS / spectral fitting / mechanical or morphology related source data |

### 3.2 关键 sheet

| sheet | 行列规模 | 主要内容 | 项目用途 |
| --- | --- | --- | --- |
| `Fig. 1d` / `Fig. 1g` | 5098 行 x 4 列 | `Areal capacity`、`Potential`、`Current`，对比 CC 与 MPC 相关曲线 | 充电协议/电流阶段特征设计 |
| `Fig. 1e` / `Fig. 1h` | 5431 行 x 2 列 | `Time`、`Current` | 分阶段电流、峰值电流位置、充电时长 |
| `Fig. 1f` | 61 行 x 5 列 | 4 个 cell 的 CE vs cycle | Li||Cu 或半电池机制 CE 审计 |
| `Fig. 1i` | 251 行 x 5 列 | 4 个 cell 的 CE vs cycle | 更长窗口 CE 稳定性审计 |
| `Fig. 5c` | 72 行 x 9 列 | CC1/CC2/MPC1/MPC2 的 `Capacity` 与 `CE` | CC vs MPC 策略对比；容量/CE 轨迹 |
| `Fig. 6c` | 67 行 x 5 列 | CC/MPC capacity 与 CE | full-cell / pouch-cell 相关策略审计候选 |
| `Supplementary Fig. 36a` | 122 行 x 5 列 | CC/MPC capacity 与 CE | 可用于 medium-window strategy comparison |
| `Supplementary Fig. 37c` | 302 行 x 5 列 | CC/MPC capacity 与 CE，窗口较长 | 很适合 capacity/CE 趋势特征测试 |
| `Supplementary Fig. 42a` | 31 行 x 3 列 | normalized discharge capacity 与 CE | 归一化容量保持和 CE 联合审计 |
| `Supplementary Fig. 43e` | 17 行 x 5 列 | CC/MPC capacity 与 CE | 短窗口策略对比 |
| `Supplementary Fig. 47a-d` | 约 4600-6000 行 x 2 列 | time-voltage failure/late-stage related curves | voltage instability / abnormal voltage pattern 特征启发 |

### 3.3 训练适配性判断

| 检查项 | 结论 |
| --- | --- |
| 是否 true LMB / anode-free full-cell | 是，核心包含 initially anode-free full-cell / pouch cell；也含 Li||Cu 机制数据 |
| 是否有 raw cycling table | 有大量图源曲线，但分散在 175 个 sheet |
| 是否有统一 cell manifest | 没有 |
| 是否有统一 protocol 表 | 没有标准化表，但可从 sheet 名和论文方法中恢复部分 CC/MPC 信息 |
| 是否有 termination reason | 没有标准化字段 |
| 是否有 no-event control cell | 不清楚 |
| 是否能直接定义 full-cell RUL | 不适合 |
| 是否能支持策略对比 audit | 适合 |
| 是否能支持 feature builder 设计 | 很适合 |
| 是否适合 full-cell 直接训练 | 不适合 |

### 3.4 对特征提取的启示

这份数据对“策略优化”和“协议感知特征”尤其重要。

优先特征：

- `protocol_type`: CC / MPC
- `current_stage_count`
- `initial_current_density`
- `middle_peak_current_density`
- `final_current_density`
- `peak_current_position`
- `charge_time_total`
- `areal_capacity_window`
- `capacity_voltage_curve_shape`
- `time_voltage_curve_shape`
- `CE_rolling_mean`
- `CE_rolling_std`
- `capacity_fade_slope`
- `normalized_capacity_retention`
- `late_stage_voltage_rise_rate`
- `voltage_instability_score`

可作为标签或 audit signal：

- `capacity_retention_80`
- `CE_instability`
- `CE_collapse`
- `protocol_induced_capacity_improvement`
- `voltage_instability`
- `abnormal_high_voltage_warning`
- `protocol_censored`

不应直接做：

- 把所有 sheet 直接拼成一个训练集。
- 把 CC 和 MPC 的图源曲线当作相互独立的大量 cell。
- 把同一 figure 的多条曲线当作没有 batch/protocol 依赖的随机样本。
- 不做 horizon separation 就用 CE/capacity 预测 CE/capacity 标签。

## 4. 是否适合 full-cell 相关模型训练？

### 4.1 当前阶段结论

```text
direct_full_cell_model_training_allowed=False
label_audit_allowed=True
feature_schema_design_allowed=True
parser_tiny_validation_allowed=True
strategy_feature_design_allowed=True
```

### 4.2 原因

这些文件缺少正式训练所需的几个关键条件：

1. **缺少统一 cell_id / source_cell manifest**
   - sheet 名是 figure-oriented，不是 cell-oriented。
   - 同一个 cell 可能出现在多个 figure 中，存在重复计数风险。

2. **缺少统一 metadata**
   - 没有标准化 cathode、anode-free status、electrolyte、current density、areal capacity、pressure、temperature、termination reason 表。
   - 部分信息可从论文方法恢复，但必须人工审计。

3. **缺少统一 observed / censored 标签**
   - 不能确认每条曲线是否自然失效、协议终止、展示截断或图源裁剪。
   - 因此不能直接生成 observed EOL。

4. **图源数据存在选择偏差**
   - Source Data 通常服务于论文图表，不等于完整实验数据库。
   - 被展示的数据可能更偏向代表性曲线。

5. **存在同源泄漏风险**
   - capacity/CE 曲线可同时作为特征和标签来源。
   - 必须采用 `t-k predicts t` 或 early-window predicts future-window 的设计。

### 4.3 可以进入的下一步

可以进入：

- source-data inventory
- sheet-level parser design
- long-format normalization tiny validation
- feature schema test
- label audit scan
- strategy feature design

不能进入：

- formal full-cell model training
- formal RUL regression
- formal AUC / F1 / RMSE / R2 报告
- random row split
- 跨 sheet 直接合并训练

## 5. 推荐的数据接入设计

### 5.1 标准化目标表

建议未来解析为四张表，而不是直接建模：

| 表 | 用途 |
| --- | --- |
| `source_sheet_inventory.csv` | 记录 workbook、sheet、figure、行列数、数据类型、是否训练候选 |
| `public_lmb_curve_long.csv` | 将 cycle/capacity/CE 或 time/voltage/current 曲线转成长表 |
| `public_lmb_cell_or_trace_manifest.csv` | 尝试从列名恢复 trace_id / cell_id / protocol / electrolyte |
| `public_lmb_label_audit.csv` | 只做标签可审计性判断，不直接训练 |

### 5.2 dataset_role 与 cell_scope

| 文件 | dataset_role | cell_scope | 备注 |
| --- | --- | --- | --- |
| `41467_2025_63303_MOESM3_ESM.xlsx` | `true_lmb` | `anode_free_full_cell` plus `lmb_mechanism_test_not_full_cell` for Li||Cu-specific sheets | full-cell 与 Li||Cu 机制测试需分开 |
| `41467_2025_66271_MOESM3_ESM.xlsx` | `true_lmb` | `anode_free_full_cell` plus `lmb_mechanism_test_not_full_cell` for Li||Cu-specific sheets | CC/MPC 策略对比需保留 protocol metadata |

### 5.3 优先解析顺序

1. Ma/Amanchukwu `Figure 3a` 和 `Figure 3b`
   - 先做 10 条左右 cell/trace 的 cycle-capacity-CE long format。
2. Liu/Chen `Fig. 5c`、`Fig. 6c`、`Supplementary Fig. 36a`、`Supplementary Fig. 37c`
   - 先做 CC vs MPC 的 capacity/CE 策略对比表。
3. Liu/Chen `Fig. 1d/e/g/h`
   - 提取 current protocol shape。
4. Liu/Chen `Supplementary Fig. 47a-d`
   - 只做 voltage instability audit，不做训练。

## 6. 对本项目特征工程的直接启示

### 6.1 Full-cell / anode-free 共通特征

- `capacity_retention`
- `capacity_fade_slope`
- `CE_rolling_mean`
- `CE_rolling_std`
- `CE_drop_rate`
- `voltage_curve_shape`
- `voltage_instability_score`
- `time_voltage_slope`
- `capacity_voltage_hysteresis_proxy`

### 6.2 策略优化特征

- `protocol_type`
- `initial_current`
- `middle_peak_current`
- `final_current`
- `peak_current_position`
- `charge_duration`
- `plating_capacity_window`
- `current_density_normalized_capacity`
- `protocol_stage_energy_or_capacity`

### 6.3 电解液筛选特征

- `electrolyte_code`
- `ELi`
- `Raman_peak_center`
- `discharge_capacity_at_20th_cycle`
- `C20_normalized_capacity`
- `molecular_or_spectroscopy_descriptor`

### 6.4 标签启示

- `C20_capacity_retention_proxy`
- `capacity_eol_80_candidate`
- `CE_instability`
- `CE_collapse`
- `voltage_instability`
- `protocol_improvement_label`
- `protocol_censored`

## 7. 自我审核

| 审核项 | 结论 |
| --- | --- |
| 是否把图源 Excel 当作干净训练集？ | 否。明确标记为 source data / audit input。 |
| 是否允许直接 full-cell 训练？ | 否。`model_training_allowed=False`。 |
| 是否区分 full-cell 与 Li||Cu 机制测试？ | 是。两个文件中都可能混有 Li||Cu 机制数据，需分开标记。 |
| 是否把 C20 或 source-data 曲线当完整 RUL？ | 否。C20 只能作为 proxy。 |
| 是否忽略 termination reason / protocol_censored？ | 否。明确缺失并要求后续补审计。 |
| 是否建议随机行划分？ | 否。后续即使建模也应按 cell / trace / protocol 分组验证。 |
| 是否过度声称文献数据支持本项目模型性能？ | 否。本文只说明数据可用性和特征启示。 |

## 8. 当前建议

最务实的下一步不是训练，而是新增一个轻量 parser / audit 工具：

```text
parse_public_lmb_nature_source_data.py
```

第一阶段只做：

1. 读取 workbook 和 sheet inventory。
2. 对指定 sheet 做 long-format tiny validation。
3. 区分 `cycle-capacity-CE`、`time-voltage-current`、`capacity-voltage`、`spectroscopy`。
4. 输出 trace-level manifest。
5. 标记哪些 trace 只能 audit-only。

下一阶段才考虑：

```text
feature_schema_test -> label_audit -> trainability_audit -> baseline_ready_export
```

最终判断：

```text
public_source_data_useful=True
direct_training_allowed=False
feature_extraction_design_value=high
strategy_optimization_design_value=high
```
