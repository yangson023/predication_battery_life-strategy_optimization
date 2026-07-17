# LMB Literature Insight Matrix

生成日期：2026-06-29

本文整理三篇与锂金属电池寿命预测、策略优化和数据接入相关的代表性论文。本文不是模型性能报告，也不表示本项目已经拥有 full-cell 模型结果。本文的用途是把文献启示转化为项目决策：需要什么数据、提取什么特征、定义什么标签、采用什么验证方式，以及哪些内容不能照搬。

当前项目门禁：

```text
model_training_allowed=False
current_lab_Li_Li_and_Li_Cu_are_full_cell=False
literature_thresholds_are_candidate_only=True
```

## 1. 三篇论文总览

| 编号 | 论文 | 电池体系 | 数据可用性 | 与本项目关系 | 一句话启示 |
| --- | --- | --- | --- | --- | --- |
| P1 | Ma / Amanchukwu, "Active learning accelerates electrolyte solvent screening for anode-free lithium metal batteries", Nature Communications, DOI `10.1038/s41467-025-63303-7` | anode-free Cu||LFP full-cell；另有 Li||Cu 形貌/CE 辅助验证 | 论文说明 experimental cycling data 位于 Supporting Information、GitHub 和 Source Data | 最适合启发“营养师”部分：用少量实验和不确定性选择下一批电解液/策略 | 数据少时，不要盲目大模型；可以用主动学习和不确定性来决定下一轮实验 |
| P2 | Liu / Li / Chen, "Tailored charging protocol for densified lithium deposition and stable initially anode-free lithium metal pouch cells", Nature Communications, DOI `10.1038/s41467-025-66271-0` | initially anode-free LMB；coin cell + 1.5 Ah pouch cell | 论文说明主要数据在正文、补充信息和 Source Data 文件 | 最适合启发策略优化：充电协议本身会改变沉积形貌、SEI 和寿命 | 充电策略不是控制变量背景，而是寿命机制变量 |
| P3 | Si / Matsuda, "Data-Driven Cycle Life Prediction of Lithium Metal-Based Rechargeable Battery Based on Discharge/Charge Capacity and Relaxation Features", Advanced Science, DOI `10.1002/advs.202402608` | Li metal-based rechargeable full-cell，NMC811 高载量 pouch-type cell | 论文有 MDR 页面；本地 PDF 显示实验记录 voltage/current/capacity，是否有机器可读原始表需另行核验 | 最直接启发“算命先生”部分：full-cell 寿命预测特征设计 | 放电/充电曲线差分和 relaxation 特征比单纯容量点更有信息 |

## 2. 逐篇项目化总结

### P1. Ma / Amanchukwu: anode-free 电解液主动学习

**研究对象**

- anode-free LMB，核心测试体系为 Cu||LFP full-cell。
- 目标不是传统完整 RUL，而是用真实电池测试反馈筛选电解液。
- 文中还用 Li||Cu 测试和 SEM 等方式辅助解释锂沉积形貌与兼容性。

**数据与标签**

- 论文明确说明 experimental cycling data 在 Supporting Information、GitHub 和 Source Data 中。
- 目标属性是第 20 圈归一化放电容量 `C20_norm`，用于比较电解液筛选效果。
- 这不是完整寿命 EOL，也不是 `capacity_eol_80` 的直接替代。

**对本项目的启示**

- 当实验数据很少时，优先考虑主动学习，而不是一开始就追求复杂监督模型。
- 后续“智能切换充放电策略/奖惩机制”可以借鉴其 sequential experimental design：每一轮根据已有结果选择最有价值的新实验。
- 电解液相关字段必须进入 metadata：`electrolyte_code`、锂盐、浓度、溶剂、添加剂、E/C ratio、温度、倍率、面容量。
- 如果未来有多种电解液和策略组合，可以把寿命提升、容量保持、CE 稳定性作为 reward 的候选分量。

**不能照搬**

- 不能把 `C20_norm` 直接当成完整寿命预测标签。
- 不能把电解液分子指纹模型直接用于我们当前 Li||Li / Li||Cu 小数据。
- 不能把主动学习得到的最优电解液结论推广到所有 LMB full-cell 体系。

### P2. Liu / Li / Chen: initially anode-free pouch cell 充电协议

**研究对象**

- initially anode-free LMB，包括 coin-type cell 和 1.5 Ah pouch cell。
- 核心机制是通过 middle peak current 充电协议引导更致密的锂沉积和更稳定的 SEI。
- 文中强调恒流充电可能导致多孔锂沉积、严重副反应和后续失效。

**数据与标签**

- 论文说明主要数据在正文、补充信息和 Source Data 文件中。
- 关键结果包括：coin-type initially anode-free LMB 可稳定循环 80 圈；1.5 Ah initially anode-free pouch cell 在 225 mA 条件下展示约 400 Wh kg-1，并在 298 圈保持 80% 容量。
- 文中还讨论不同 N/P 或 initially anode-free 状态下的渐进失效和突发失效差异。

**对本项目的启示**

- 充放电协议必须作为核心 metadata，而不是只作为背景信息。
- 后续策略优化系统的 action space 可以考虑：分阶段电流、前段/中段/后段电流、峰值位置、充电时间、SOC 窗口和截止电压。
- 特征工程应加入 protocol-aware features：`charge_step_duration_s`、`current_density_stage_*`、`voltage_end_gap`、`charge_median_voltage_v`、`voltage_hysteresis_v`、`polarization_growth`。
- 标签体系不能只有容量 EOL，也应包含 `voltage_instability`、`polarization_failure`、`safety_stop`、`protocol_censored`。

**不能照搬**

- 不能直接把 middle peak current 设为本项目最优策略，因为不同电池结构、压力、电解液、面容量和温度会改变机制。
- 不能只看最终容量保持率，必须记录协议、终止原因和异常电压行为。
- Source Data 如果只是图源数据而不是 per-cycle raw table，则只能做文献参考或低粒度 audit。

### P3. Si / Matsuda: LMB full-cell 寿命预测机器学习

**研究对象**

- 高面载 NMC811 正极与锂金属负极的高能量密度 LMB full-cell。
- 文中制造 57 个 monolayer stacked pouch-type LMB cells，其中 48 个用于模型构建，9 个作为 unseen data，实际最终排除 1 个不稳定 cell 后使用 8 个 unseen cells。

**数据与标签**

- EOL 定义为放电容量下降到标称容量或可用最大容量的 80%。
- 使用前 100 圈数据构造特征，目标是预测 cycle life。
- 特征来自三类过程：discharge、charge、relaxation。
- 论文提取 35 个特征，再筛选出与寿命相关的特征，最后 XGBoost 选定 6 个特征效果最好。

**关键特征启示**

- `DeltaDQ100-10(V)`：第 100 圈与第 10 圈放电容量-电压曲线差异。
- `DeltaCQ100-10(V)`：第 100 圈与第 10 圈充电容量-电压曲线差异。
- 放电容量衰减斜率、容量保持率、不同圈数的充/放电容量。
- CE 在第 2、10、100 圈等早期周期的变化。
- relaxation voltage 的均值、形状或窗口统计。

**对本项目的启示**

- full-cell 到来后，应优先实现曲线差分特征，而不是只使用单点容量。
- record 或 step 层越完整，越有机会复现 relaxation、dQ/dV、dV/dQ 和曲线形状特征。
- 早期窗口预测应成为主线：例如前 20/50/100 圈预测后续寿命或 EOL。
- `capacity_eol_80` 是重要标签，但仍需和 CE、极化、电压不稳定、soft-short 等机制标签并行保留。

**不能照搬**

- 论文中的四折交叉验证不等于本项目的默认验证方式；本项目仍应优先 LOCO 或 leave-one-condition-out。
- 论文中的 R2、RMSE、test error 不能作为本项目性能结论。
- XGBoost 不能在本项目 small-n 阶段直接作为主模型；应等 full-cell 数据数量、observed EOL 和 control cell 足够后再考虑。

## 3. 对当前项目的具体建议

### 3.1 数据收集建议

| 优先级 | 字段或数据 | 来源启示 | 为什么重要 |
| --- | --- | --- | --- |
| P0 | full-cell / anode-free full-cell 明确标记 | 三篇共同要求 | 防止把 Li||Li / Li||Cu 误当 full-cell |
| P0 | cycle-level charge/discharge capacity | P2, P3 | 定义 `capacity_eol_80`、容量保持率和衰减趋势 |
| P0 | cycling protocol / charging protocol | P2 | 充电策略本身可能改变沉积机制和寿命 |
| P0 | termination reason | P2, P3 | 区分 observed failure 与 `protocol_censored` |
| P0 | current density / areal capacity | P1, P2, P3 | 做协议归一化和机制解释 |
| P0 | electrolyte code and details if shareable | P1, P2 | 电解液是 anode-free 寿命核心变量 |
| P1 | step layer | P2, P3 | 提取充电时长、放电时长、滞后、电压 gap |
| P1 | record layer | P2, P3 | 提取曲线形状、relaxation、dQ/dV、异常电压 |
| P1 | pressure / stack pressure | P1, P2 | 影响 anode-free / pouch cell 表现 |
| P1 | EIS or impedance if available | P2, P3 扩展 | 有助于极化和 knee point 审计 |

### 3.2 特征工程建议

优先实现三类 full-cell 特征：

1. **机制型特征**
   - voltage hysteresis
   - polarization growth
   - charge/discharge duration shift
   - relaxation voltage drift
   - dQ/dV 或 dV/dQ 曲线形状

2. **寿命标签近邻但需要防泄漏的特征**
   - capacity fade slope
   - capacity retention trend
   - CE rolling mean / std
   - discharge/charge curve difference

3. **协议与策略特征**
   - current density stages
   - peak current position
   - charge time and rest time
   - voltage cutoff
   - SOC / capacity window

### 3.3 标签定义建议

| label_key | 当前建议 | 文献支撑 | 注意事项 |
| --- | --- | --- | --- |
| `capacity_eol_80` | full-cell P0 标签 | P2, P3 | 不能作为唯一 LMB 标签 |
| `capacity_eol_70` | full-cell P1 标签 | P3 延伸 | 需要足够长循环窗口 |
| `CE_collapse` | anode-free / Li metal 重要标签 | P1, P2 | 必须 horizon separation，避免 CE 泄漏 |
| `sustained_CE_degradation` | 策略/电解液筛选标签 | P1 | 不能直接等价寿命终点 |
| `polarization_failure` | 机制标签 | P2, P3 | 需要 step/record 层 |
| `voltage_instability` | 安全与异常预警标签 | P2 | 需要异常记录和终止原因 |
| `protocol_censored` | 必须保留 | 三篇共同间接要求 | 没有自然失效时不能硬造 observed EOL |

### 3.4 验证设计建议

- full-cell 数据达到最小规模前，不做正式模型性能。
- 优先使用 `leave-one-cell-out`，如果未来跨电解液/协议/批次，还应考虑 `leave-one-electrolyte-out` 或 `leave-one-protocol-out`。
- 禁止把随机行划分作为寿命预测结论。
- small-n 阶段只能做 qualitative smoke-test。
- 真正训练前必须通过：

```text
intake -> metadata validation -> feature schema -> label audit -> trainability audit -> leakage guard -> baseline-ready export -> tiny baseline planning
```

## 4. 对“算命先生”和“营养师”的启示

### 算命先生：寿命预测

最值得吸收 P3：

- 前 100 圈或更早窗口提取曲线差分与 relaxation 特征。
- 预测对象可以是 cycle life、`capacity_eol_80`、或未来窗口容量保持。
- 特征要 past-only，避免用当前或未来容量直接预测当前标签。

### 营养师：策略优化

最值得吸收 P1 和 P2：

- P1 提醒我们：数据少时，可以用主动学习选择下一批实验，而不是随机试。
- P2 提醒我们：充电协议本身就是寿命控制变量，应进入 action space。
- 奖惩机制可考虑：
  - capacity retention improvement
  - CE stability
  - lower polarization growth
  - delayed voltage instability
  - avoiding safety / abnormal stop

## 5. 自我审核

| 审核项 | 结论 |
| --- | --- |
| 是否把 Li||Li / Li||Cu 当成 full-cell？ | 否。本文明确当前实验室 Li||Li / Li||Cu 不是 full-cell。 |
| 是否把文献模型性能当成本项目模型性能？ | 否。P3 的 R2/test error 只作为文献背景，不作为本项目结果。 |
| 是否把文献阈值写成最终阈值？ | 否。`capacity_eol_80`、C20 等均标记为候选或文献定义。 |
| 是否把 anode-free C20 标签当完整寿命 EOL？ | 否。P1 的 `C20_norm` 被标为筛选 proxy。 |
| 是否建议随机行划分？ | 否。本文建议 LOCO / leave-one-condition-out。 |
| 是否允许现在训练模型？ | 否。`model_training_allowed=False`。 |
| 是否忽略机制标签？ | 否。保留 CE、极化、电压不稳定、soft-short、protocol_censored。 |

## 6. 下一步动作

1. 下载或检查 P1/P2 的 Source Data / GitHub 文件时，先做文件清单，不直接进入训练。
2. 如果 P3 的 MDR 数据文件可下载，优先检查是否含有 machine-readable cycle/relaxation table。
3. 为 future full-cell 数据预留三类 parser：
   - source-data Excel / CSV parser
   - cycle-level summary parser
   - record/step curve parser
4. partner 后续提供 full-cell 数据时，优先补充：
   - cell_type
   - anode_free_status
   - cathode_type
   - electrolyte_code
   - current_density
   - areal_capacity
   - cycling_protocol
   - planned_cycle_count
   - termination_reason
   - cycle / step / record layer availability

当前最终判断：

```text
literature_insight_ready=True
download_planning_allowed=True
full_cell_model_training_allowed=False
```
