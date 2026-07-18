# LMB Full-Cell Intake Checklist And Tiny Validation Protocol

```text
planning_only=True
model_training_allowed=False
first_batch_data_should_be_tiny_validation=True
```

## A. 当前项目状态

当前项目已经完成了 LMB 方向校准、数据角色分类、Li||Li / Li||Cu 机制测试数据接入、BTSDA 三层 parser、public Nature source data parser、public source feature schema test、LMB label policy 和 feature/label requirements。

当前仍然没有 partner 真实 full-cell / anode-free full-cell 数据。因此当前不能训练 full-cell 模型。第一批数据即使到达，也必须先作为 tiny validation / intake validation 数据处理，而不是直接训练模型。

## B. Full-Cell 数据角色定义

| dataset_role | 定义 | 允许用途 | 禁止用途 | 是否支持 LMB full-cell 结论 | 是否可进入训练前门禁 |
| --- | --- | --- | --- | --- | --- |
| `lmb_full_cell` | 锂金属负极与正极组成的完整电池 | full-cell intake、metadata gate、feature schema、label audit | 未过门禁前训练模型 | 可支持，但需 metadata 和 label gate | 可进入 |
| `anode_free_full_cell` | 无负极或 Cu 集流体 paired with cathode 的 full-cell | anode-free 特征、CE、capacity、protocol-censored 审计 | 与普通 Li||Cu 机制测试混用 | 可支持 anode-free 结论 | 可进入 |
| `lmb_mechanism_test_not_full_cell` | Li||Li、Li||Cu 等机制测试 | 机制特征、warning proxy、parser/schema 验证 | 声称 full-cell 寿命结论 | 不支持 | 可做 audit，不可直接训练 |
| `li_ion_method_data` | 普通锂离子数据 | pipeline validation、方法开发 | 声称 LMB 结论 | 不支持 | 仅方法开发 |
| `diagnostic_only` | EIS、RPT、表征、热失控等未对齐 cycling 的诊断数据 | 解释机制、辅助审计 | 直接作为训练标签 | 不支持 | 需 protocol alignment |
| `unknown_scope` | 化学体系或 cell design 不清楚 | 暂存和人工复核 | 训练或科研结论 | 不支持 | 阻断 |

Li||Cu / Li||Li 不能作为 full-cell 结论。Nature source data 不能写成 raw full-cell training data。

## C. 第一批 Partner 数据接入 Checklist

P0 是第一批数据接入的最低必需字段。P1 强烈建议补齐。P2 用于后续机制解释、复现和长期归档。

| priority | 字段示例 | 用途 |
| --- | --- | --- |
| P0 | `cell_id`, `cell_type`, `full_cell_or_anode_free_status` | 建立数据身份，避免 Li||Cu / Li||Li 与 full-cell 混用 |
| P0 | `cathode_type`, `anode_type`, `N/P ratio` | 判断 cell design 与 LMB 适用范围 |
| P0 | `electrolyte_code`, `current_density`, `areal_capacity` | 支持跨 cell 比较和特征归一化 |
| P0 | `voltage_cutoff`, `cycling_protocol`, `planned_cycle_count`, `termination_reason` | 支持 EOL、protocol_censored 和 observed/censored 判断 |
| P0 | `cycle_layer_available`, `step_layer_available`, `record_layer_available` | 判断 feature schema 可用范围 |
| P1 | `cathode_loading`, `electrolyte_detail_if_shareable`, `E/C ratio`, `separator_type` | 改善机理解释和导师沟通 |
| P1 | `pressure`, `temperature`, `formation_protocol`, `rest_protocol` | 支持极化、松弛和 protocol 审计 |
| P1 | `BTS_step_or_protocol_file`, `abnormal_notes`, `operator_or_batch_note` | 支持 protocol 对齐和异常排查 |
| P2 | `EIS/DCIR availability`, `cell_format`, `fabrication_date`, `storage_condition` | 机制补充和复现实验记录 |
| P2 | `humidity_or_glovebox_condition`, `raw_NDAX_archive_path`, `public_or_confidential_level` | 长期数据治理 |

## D. 必需数据层要求

| 数据层 | 主要用途 | 若缺失的影响 |
| --- | --- | --- |
| cycle layer | capacity retention、CE、cycle count、capacity EOL scan | 不能做基础寿命/CE 审计 |
| step layer | charge/discharge/rest segmentation、duration、protocol verification、voltage hysteresis / polarization proxy | 不能可靠分离工步和协议 |
| record layer | voltage-time/current-time curves、dQ/dV、curve-shape、voltage instability、soft-short warning proxy | 不能做曲线形状和细粒度极化特征 |
| protocol file | current density、voltage cutoff、rest step、planned cycle count、censoring judgment | 不能可靠判断 protocol_censored |

## E. Tiny Validation Protocol

第一批数据到达后，按以下门禁顺序执行：

1. `data arrival logging`: 记录原始路径、文件类型、导出时间、操作者、cell 数量。
2. `data role classification`: 判定 `lmb_full_cell`、`anode_free_full_cell`、`lmb_mechanism_test_not_full_cell`、`unknown_scope` 等角色。
3. `raw file inventory`: 统计 cycle / step / record / protocol 文件是否齐全。
4. `metadata gate`: 检查 P0 字段，尤其是 `termination_reason`、`planned_cycle_count`、`current_density`、`areal_capacity`。
5. `tiny parser validation`: 只抽 1-2 个 cell 或少量行做 parser 验证。
6. `schema check`: 检查字段名、单位、cycle_index、step_type、voltage/current/time 是否可对齐。
7. `feature schema test`: 生成最小特征表，先验证 capacity、CE、voltage、duration、protocol metadata。
8. `audit-only label scan`: 扫描 capacity_eol、CE collapse、voltage instability、protocol_censored 候选。
9. `observed / censored / protocol_censored preliminary review`: 只做初步审计，不生成训练标签。
10. `trainability audit decision`: 决定是否允许申请 tiny exploratory smoke-test。

任何一步失败，都应停在当前门禁并生成修正清单，不允许跳到训练。

## F. 少量数据规则

| cell 数量 | 允许动作 | 禁止动作 | 解读限制 |
| --- | --- | --- | --- |
| 1-2 cells | intake、schema、audit | baseline、模型训练 | 只能验证流程 |
| 3-5 cells | tiny validation、候选 label scan | 正式训练、性能声明 | 可观察信号但不能泛化 |
| 6-8 cells | 可申请 tiny exploratory smoke-test | 正式性能、复杂模型 | 只做 qualitative smoke-test |
| 8-12+ cells 且 metadata 完整 | 可考虑 exploratory baseline | random row split、正式结论 | 仍需 LOCO 和导师/门禁确认 |

## G. 标签候选初筛

| label_candidate | 所需信号 | 所需 metadata | 小批量是否可审计 | trainable label 阻断条件 |
| --- | --- | --- | --- | --- |
| `capacity_eol_80` | discharge capacity / normalized capacity | termination_reason, planned_cycle_count, protocol | 可审计 | 终止原因缺失或全是 protocol-censored |
| `capacity_eol_70` | deeper capacity fade | 同上 | 可审计 | 数据窗口过短 |
| `CE_collapse` | CE 突降或持续异常 | charge/discharge capacity, protocol, abnormal notes | 可审计 | CE 由同周期标签泄漏，或容量字段不完整 |
| `CE_instability` | CE rolling std / excursions | protocol, current_density | 可审计 | 协议变化未标注 |
| `polarization_failure` | voltage hysteresis / overpotential proxy | step/record layer, current_density | 可审计 | 缺 step/record 或电流密度 |
| `voltage_instability` | voltage-time abnormality | record layer, voltage cutoff | 可审计 | 采样层不完整 |
| `soft_short_warning` | 异常电压跌落/恢复 | record layer, abnormal notes | audit-only | 需要人工复核 |
| `safety_stop` | 设备安全终止或异常停机 | termination_reason, BTS log | 可审计 | 终止原因不明 |
| `protocol_censored` | 达到设定循环数且无 observed failure | planned_cycle_count, termination_reason | 可审计 | planned cycle count 缺失 |

## H. 特征候选初筛

| feature_family | 优先数据层 | 依赖 metadata | tiny batch 是否可测 | 风险 |
| --- | --- | --- | --- | --- |
| `capacity_retention` | cycle layer | planned_cycle_count, termination_reason | 是 | capacity 标签同源风险，需要 horizon separation |
| `CE rolling mean/std/trend` | cycle layer | protocol, current_density | 是 | CE 标签同源风险 |
| `voltage_hysteresis` | step layer | current_density, voltage_cutoff | 是 | 工步未对齐会误判 |
| `polarization_proxy` | step / record layer | current_density, temperature | 是 | 协议变化影响大 |
| `charge/discharge duration` | step layer | protocol | 是 | step_type 必须可靠 |
| `rest_voltage_relaxation` | record / step layer | rest_protocol | 视数据而定 | 无 rest step 时不可用 |
| `dQ/dV_or_curve_shape` | record layer | voltage/current/time alignment | 视数据而定 | 采样不足不可用 |
| `protocol_normalized_features` | cycle/step/metadata | protocol, current_density, areal_capacity | 是 | metadata 缺失会阻断 |
| `current_density_areal_capacity_normalized` | metadata + cycle/step | current_density, areal_capacity | 是 | 单位不清会阻断 |

## I. 禁止事项

- 禁止第一批数据直接训练模型。
- 禁止 random row split。
- 禁止把 tiny validation 称为性能。
- 禁止把 Li||Li / Li||Cu 结果称为 full-cell 结论。
- 禁止把 Nature source data 当作 raw full-cell training data。
- 禁止缺少 `termination_reason` 时定义 observed EOL。
- 禁止只有 protocol-censored 数据时声称寿命预测能力。

## J. 给 Partner 的中文说明

这次不是要求“越多越好”的数据，而是优先需要字段清楚、协议清楚、终止原因清楚的数据。第一批数据即使只有少量 cell 也很有价值，因为我们会先用它验证 full-cell 数据接入流程、字段格式和标签审计规则。请尽量同时导出 cycle、step、record 三层数据，并保留 BTS step/protocol 文件。Full-cell、anode-free full-cell、Li||Cu、Li||Li 的用途不同，后续不能混在一起训练或解释。

## K. 给导师的科研化说明

当前项目已经完成 LMB 数据接入框架、机制测试数据审计、公开 Nature source data parser 与 public source feature schema 准备。第一批 partner full-cell 数据到来后，将首先用于 tiny validation 和标签审计，而不是直接训练模型。这样做是为了避免 small-n、协议截尾、终止原因缺失和标签误判导致的虚假结论。后续是否进入 exploratory baseline，将取决于数据规模、metadata 完整性、observed/censored 质量和 trainability gate。

## L. Codex / Trae / User 分工

| 角色 | 负责内容 | 不建议负责 |
| --- | --- | --- |
| Codex | schema、门禁、测试、本地验证、关键脚本、最终审查 | 重复性大段草稿 |
| Trae | 文献草稿、批量表格草稿、prompt 初稿、科学质疑初稿 | 最终门禁判断 |
| 用户 | 长时间本地命令、数据提供、导师反馈、硬件/预算控制 | 手动重复检查所有文件 |

## Gate Decision

```text
planning_only=True
model_training_allowed=False
first_batch_data_should_be_tiny_validation=True
tiny_baseline_requires_gate_approval=True
```

第一批 full-cell 数据到来后，推荐先执行 intake tiny validation，不允许直接训练模型。
