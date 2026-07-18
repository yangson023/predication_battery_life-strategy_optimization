# LMB Full-Cell Intake Checklist

本文档用于未来锂金属全电池或无负极全电池数据到来后的第一轮接入判断。它不是模型训练报告，也不允许生成模型性能结论。

当前项目状态：

```text
full_cell_data_available = false
model_training_allowed = False
```

当前已有 Li||Li / Li||Cu 数据仍然标记为：

```text
cell_scope = lmb_mechanism_test_not_full_cell
is_full_cell = false
```

## 1. 当前阶段说明

full-cell 数据尚未供应。当前任务是提前准备接入标准、metadata 模板、标签政策和门禁流程，而不是训练模型。Li||Li 和 Li||Cu 数据仍然有机制价值，但不能支撑 full-cell 寿命、EOL、RUL 或策略优化结论。

未来 full-cell / anode-free full-cell 数据更适合支撑：

- `capacity_eol_80` / `capacity_eol_70`
- full-cell RUL 或剩余循环数预测
- 充放电策略对寿命影响的评估
- CE、极化、电压不稳定、soft-short 等多标签机制分析

## 2. 数据类型快速判断

| 数据类型 | `cell_scope` | 是否 full-cell | 允许用途 | 禁止用途 | 可否支持 full-cell 寿命结论 |
| --- | --- | --- | --- | --- | --- |
| Li||Li symmetric | `lmb_mechanism_test_not_full_cell` | 否 | 极化、电压滞后、电压不稳定、soft-short 审计 | full-cell RUL/EOL、capacity EOL 结论 | 否 |
| Li||Cu half-cell | `lmb_mechanism_test_not_full_cell` | 否 | CE、锂沉积/剥离效率、incomplete-capacity warning proxy | full-cell EOL、full-cell 策略优化结论 | 否 |
| lithium-metal full-cell | `lmb_full_cell` | 是 | full-cell 寿命预测、EOL/RUL、策略优化、机制标签审计 | 跳过 metadata/label/leakage gates 后直接训练 | 通过门禁后可以 |
| anode-free full-cell | `anode_free_full_cell` | 是 | 无负极全电池寿命、锂库存、CE、capacity EOL、策略优化 | 当作普通 Li-excess full-cell 解释 N/P | 通过门禁后可以 |
| unknown | `unknown_scope` | 未知 | inventory、metadata recovery、导师/partner 追问 | 训练、标签结论、性能汇报 | 否 |

## 3. Full-Cell Intake Checklist

| 检查层级 | 必查项 | 通过条件 | 阻断条件 | 下一步 |
| --- | --- | --- | --- | --- |
| 文件层检查 | 原始文件、导出文件、路径、cell_id | 文件可读，cell_id 可追踪 | 文件缺失或 cell_id 无法对应 | 补文件或标记 unknown |
| cell scope 检查 | full-cell / anode-free / Li||Li / Li||Cu | 能明确赋值 `lmb_full_cell` 或 `anode_free_full_cell` | 类型不明或把半电池误报为 full-cell | 禁止训练，先 metadata recovery |
| metadata 检查 | P0 字段完整性 | P0 字段完整或明确不可得 | `cell_id`、cell_type、protocol、termination_reason 缺失 | 阻断训练向流程 |
| cycle layer 检查 | cycle index、容量、CE、时间 | 可用于 capacity/CE audit | capacity 字段缺失 | 阻断 capacity_eol label |
| step layer 检查 | step type、电压、时长、充放电工步 | 可用于 hysteresis、duration、polarization feature | step type 或 cycle alignment 缺失 | 只能做 cycle-level minimal audit |
| record layer 检查 | voltage/current/time/capacity curve | 可用于 dQ/dV、dV/dQ、rest relaxation | record 缺失 | 不阻断 minimal audit，但阻断曲线机制特征 |
| protocol/XML 检查 | BTS Step XML 或协议描述 | 可复核电流、容量、电压、循环数 | 协议缺失 | 阻断 baseline-ready export |
| label readiness 检查 | observed/censored/protocol_censored | 终止原因和标签窗口可定义 | termination_reason 缺失 | 禁止 observed EOL 解释 |
| leakage risk 检查 | horizon、同源信号、泄漏列 | 使用 t-k predicts t；标注 `same_signal_source_risk` | 同 cycle capacity/CE 直接预测同 cycle label | 阻断 baseline-ready export |
| baseline readiness 检查 | features/targets/metadata row_id 对齐 | 可导出候选数据包 | 数据行不对齐或标签未审计 | 禁止 tiny baseline |

## 4. Full-Cell Metadata 字段表

| 优先级 | 字段英文名 | 中文字段名 | 单位 | 是否必填 | 缺失影响 |
| --- | --- | --- | --- | --- | --- |
| P0 | `cell_id` | 电池编号 | - | 是 | 阻断 intake |
| P0 | `cell_type` | 电池类型 | - | 是 | 类型不明，标记 unknown，禁止训练 |
| P0 | `full_cell_or_anode_free_status` | 全电池/无负极状态 | - | 是 | 无法判定 `lmb_full_cell` 或 `anode_free_full_cell` |
| P0 | `cathode_type` | 正极材料 | - | 是 | 无法解释电压窗口和 capacity baseline |
| P0 | `cathode_loading_mAh_cm2` | 正极面载量 | mAh/cm2 | 是 | 影响 areal normalization |
| P0 | `anode_type` | 负极类型 | - | 是 | 无法区分 Li-excess、host 或 anode-free |
| P0 | `anode_free_status` | 是否无负极 | true/false | 是 | 无法解释 N/P 和锂库存 |
| P0 | `np_ratio` | N/P 比 | - | 条件必填 | Li-excess full-cell 需要；anode-free 填 N/A |
| P0 | `electrolyte_code` | 电解液编号 | - | 是 | 无法分组解释 electrolyte effect |
| P0 | `temperature_c` | 测试温度 | deg C | 是 | 无法比较动力学和退化速率 |
| P0 | `current_density_mA_cm2` | 电流密度 | mA/cm2 | 是 | 无法做 protocol-normalized feature |
| P0 | `areal_capacity_mAh_cm2` | 面容量 | mAh/cm2 | 是 | 无法做 loading-normalized comparison |
| P0 | `voltage_cutoff_upper_lower` | 上下截止电压 | V | 是 | 无法定义协议边界 |
| P0 | `cycling_protocol` | 循环协议 | - | 是 | 阻断 baseline-ready export |
| P0 | `formation_protocol` | 化成协议 | - | 是 | formation cycles 可能混入正常循环 |
| P0 | `planned_cycle_count` | 计划循环数 | cycles | 是 | 无法判定 protocol_censored |
| P0 | `termination_reason` | 终止原因 | - | 是 | 禁止 observed EOL 解释 |
| P0 | `failure_mode` | 失效模式 | - | 是或 unknown | 影响标签族选择 |
| P0 | `btsda_export_layer_availability` | BTSDA 导出层可用性 | - | 是 | 无法判断能提取哪些特征 |
| P1 | `electrolyte_detail_if_shareable` | 可公开电解液细节 | - | 否 | 降低机制解释能力 |
| P1 | `electrolyte_volume_uL` | 电解液用量 | uL | 否 | 影响 E/C ratio |
| P1 | `ec_ratio` | E/C 比 | uL/mAh | 否 | 影响贫液/富液解释 |
| P1 | `separator` | 隔膜 | - | 否 | 影响 soft-short 和阻抗解释 |
| P1 | `pressure` | 压力条件 | MPa 或说明 | 否 | 影响界面和固态/聚合物体系解释 |
| P1 | `record_layer_available` | record 层是否可用 | true/false | 否 | 缺失则阻断 dQ/dV 和 rest relaxation |
| P1 | `eis_available` | 是否有 EIS | true/false | 否 | 缺失则无法做 EIS/knee point 特征 |
| P1 | `knee_point_cycle_if_known` | 已知拐点循环 | cycles | 否 | 仅辅助审计，不可直接作最终标签 |
| P1 | `abnormal_notes` | 异常备注 | - | 否 | 缺失会降低人工复核能力 |
| P1 | `bts_step_xml_availability` | BTS Step XML 是否可用 | true/false | 否 | 缺失不替代真实测量，但影响协议复核 |
| P2 | `fabrication_date` | 制备日期 | yyyy-mm-dd | 否 | 用于批次追溯 |
| P2 | `operator_or_batch_note` | 操作者/批次备注 | - | 否 | 用于 batch effect 审查 |
| P2 | `rest_protocol` | 静置协议 | - | 否 | 影响 rest voltage feature |
| P2 | `storage_condition` | 存储条件 | - | 否 | 影响初始状态 |
| P2 | `full_record_sampling_rate` | 完整 record 采样率 | s 或 Hz | 否 | 影响曲线特征可信度 |
| P2 | `data_publication_level` | 数据公开级别 | - | 否 | 决定后续报告/共享范围 |

## 5. 字段缺失门禁

| 缺失字段或条件 | gate decision |
| --- | --- |
| 缺失 `cell_id` | 阻断 intake |
| 缺失 `cell_type` 或 full-cell 状态 | 标记 `unknown_scope`，禁止训练 |
| Li||Li / Li||Cu 被标为 full-cell | 阻断，必须改回 `lmb_mechanism_test_not_full_cell` |
| 缺失 charge/discharge capacity | 阻断 `capacity_eol_80` 和 `capacity_eol_70` 标签 |
| 缺失 `termination_reason` | 禁止 observed EOL 解释，只能标记 unknown/protocol-censored |
| 缺失 `cycling_protocol` | 阻断 baseline-ready export |
| 缺失 record layer | 不阻断 minimal cycle/step audit，但阻断 dQ/dV、dV/dQ、rest relaxation |
| 缺失 N/P | 不一定阻断；Li-excess full-cell 降低锂库存解释能力，anode-free 应填 N/A |

## 6. 第一批 Full-Cell 标签候选

所有阈值都是 candidate threshold，必须经过本项目数据分布和导师复核。

| label key | signal source | candidate threshold | required fields | observed/censored rule | leakage risk | baseline priority |
| --- | --- | --- | --- | --- | --- | --- |
| `capacity_eol_80` | discharge capacity / retention | retention below 80 percent for sustained window | capacity, initial capacity, cycle index | sustained crossing observed; no crossing is censored or protocol_censored | High if same-cycle capacity enters features | P0 |
| `capacity_eol_70` | discharge capacity / retention | retention below 70 percent for sustained window | capacity, initial capacity, cycle index | same as above | High | P0/P1 |
| `CE_collapse` | CE trajectory | reviewed CE lower bound or abrupt future-window drop | CE, cycle index | future-window collapse observed; insufficient future window censored | High, requires horizon separation | P1 |
| `sustained_CE_degradation` | CE rolling trend | sustained deviation from early baseline | CE, cycle index | persistent degradation observed; no crossing censored | High, `same_signal_source_risk` | P1 |
| `polarization_failure` | voltage hysteresis / median voltage drift | reviewed hysteresis or drift threshold | step voltage, cycle alignment | sustained crossing observed; no crossing censored | Medium | P1 |
| `voltage_instability` | voltage variance / abnormal voltage behavior | reviewed voltage instability threshold | record or step voltage | repeated instability observed | Medium | P1 |
| `soft_short_warning` | rest voltage relaxation / sudden voltage anomaly | reviewed rest-drop threshold | rest/record voltage | warning observed with audit evidence | Medium | audit first |
| `safety_stop` | termination reason / abnormal notes | safety stop documented | termination_reason | safety stop is observed state, not ordinary negative label | Low | audit |
| `protocol_censored` | planned cycle count / protocol end | protocol or non-natural end | planned_cycle_count, termination_reason | censoring state, not failure event | Low | required |
| `abnormal_stop` | abnormal notes / termination reason | abnormal non-natural stop documented | termination_reason, abnormal_notes | audit-only until reviewed | Low | audit |

## 7. 文献启发摘要

Trae 文献支持稿给出的可吸收启发如下，但不可直接照搬阈值：

- Rest / relaxation voltage 对 full-cell 寿命早期预测可能很有价值。
- EIS 和 knee point detection 可能帮助发现容量衰减拐点，但需要单独数据层和协议对齐。
- Li||NMC811 23-cell 数据集提示 full-cell 小规模 LOCO 设计可作为方法参考，但不能替代本项目数据。
- Anode-free full-cell 对 CE 要求更高，CE 标签和锂库存解释更关键。
- Pressure、E/C ratio、current density、areal capacity、N/P ratio 是 full-cell metadata 的关键控制变量。
- 文献阈值只能作为 candidate threshold，必须经本项目数据分布和导师复核。

## 8. 训练与报告禁区

- 禁止训练模型。
- 禁止生成模型性能。
- 禁止使用随机行划分。
- 禁止把当前 Li||Li / Li||Cu 写成 full-cell。
- 禁止把文献阈值当成最终阈值。
- 禁止把 `capacity_eol_80` 写成唯一 LMB 标签。

当前结论：

```text
full_cell_data_available = false
model_training_allowed = False
```
