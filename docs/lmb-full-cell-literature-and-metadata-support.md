# LMB Full-Cell Literature & Metadata Support Draft

**起草日期**: 2026-06-21
**角色**: Trae / LMB full-cell literature and metadata support draft agent
**版本**: Draft v0 — 供 Codex 固化为项目正式文档
**状态**: 不写代码、不运行数据、不训练模型

---

## 0. 声明

1. 本项目当前数据为 Li||Li 对称电池和 Li||Cu 半电池，**不是 full-cell**。
2. 本章节仅为文献调研和 metadata 设计参考，**不声称本项目已有 full-cell 模型性能**。
3. Li||Li / Li||Cu 是 full-cell 的机制测试数据，不能替代 full-cell 的寿命预测。
4. 所有文献阈值/参数均为代表性示例，实际阈值需在 full-cell 数据到位后校准。

---

## 1. 代表性 LMB Full-Cell / Anode-Free Full-Cell 文献

| # | 论文 | 年份 | Cell 类型 | 正极 | 负极 / Anode-Free? | N/P Ratio | Current Density | Areal Capacity | 电解液 | EOL 定义 | CE/极化信号 | 公开数据 | 对本项目的启发 |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | :---: | --- |
| **P1** | Si, Matsuda et al. — *"Data-Driven Cycle Life Prediction of Lithium Metal-Based Rechargeable Battery Based on Discharge/Charge Capacity and Relaxation Features"* (Advanced Science, 2024) | 2024 | Li||NMC811 软包电池 | NMC811 (high mass loading, >3 mAh/cm²) | Li metal (≥50 μm thick) | Li excess (~>10) | ~0.5-1C | 3-4 mAh/cm² | 高级电解液（NIMS/SoftBank 自研） | capacity_retention < 80%, cycle life ~200+ cycles | 放电容量 fade, 充放电容量差 ΔQ, Relaxation 电压特征 — **最直接参考** | **是** — MDR/NIMS 数据库 | **P0 参考**: Log(|min(ΔQ_100-10(V))|) 是最重要特征; R²=0.89, test err=6.6%。对 full-cell 特征设计的启发：relaxation/rest 段电压 + 放电容量差分 |
| **P2** | Si, Matsuda et al. — *"Capacity Estimation and Knee Point Prediction Using Electrochemical Impedance Spectroscopy for Lithium Metal Battery Degradation via Machine Learning"* (Advanced Science, 2025) | 2025 | Li||NMC 硬币电池 / 软包 | NMC (高载量) | Li metal | Li excess | 多种 C-rate | 3-4 mAh/cm² | 高级电解液 (NIMS) | Knee point detection (capacity fade inflection point) | **EIS 低频阻抗** (扩散限制过程) 最预测 capacity estimation; **EIS 高频阻抗** (charge transfer) 最预测 knee point | 否 | **P1 参考**: EIS 对于 LMB 比 LIB 有更明显的 degradation signal；knee point detection 是比 capacity_eol_80 更精确的标签定义方式；低频阻抗反映锂库存耗尽 |
| **P3** | Uppaluri, Ma, Xu, Onori et al. — *"Lithium-Metal Battery Degradation Dataset from Continuous Cycling Experiments"* (Data in Brief, 2025) | 2025 | Li||NMC811 硬币电池 (23 cells, 4 configurations) | NMC811 | Li metal (不同厚度) | Li excess (不详) | 0.5C-3C charge, 1C discharge | 不详 | 不详 | 容量衰减至 EOL | CC-CV charge, CC discharge; 容量逐 cycle 计算 | **是** — OSF 公开: DOI 10.17605/OSF.IO/5DQWG | **P0 参考**: **最直接可类比的数据集** — 23 LMB cells, 4 种配置, 含电压/电流/容量数据。可作为本项目 full-cell 数据的先验参考和基线对比 |
| **P4** | Chen, Liao, Cui, Bao et al. — *"Hyperconjugation-Controlled Molecular Conformation Weakens Lithium-Ion Solvation and Stabilizes Lithium Metal Anodes"* (Chemical Science, 2024) | 2024 | Anode-free Cu||LFP 软包电池 + thin-Li||高载量 LFP 硬币电池 | LFP | **Anode-free** (Cu current collector) + thin-Li (20 μm) | **N/A** (anode-free) | 0.5-4 mA/cm² | 1-3 mAh/cm² | Dimethoxymethane (DMM) 基电解液 | Cu||LFP: cycle life ~70-100 cycles; Thin-Li||LFP: ~200-300 cycles | CE > 99%; electrolyte engineering 主导 anode-free 性能 | 否 | **P0 参考**: Anode-free full-cell 的 CE 和容量衰减速率远快于 Li-excess full-cell；anode-free 模式下 N/P≈0 → 锂库存管理是关键；对 anode-free metadata 收集的启发 |
| **P5** | Jawad & Al-Haddad — *"Stacked Temporal Deep Learning for Early-Stage Degradation Forecasting in Lithium-Metal Batteries"* (Discover Artificial Intelligence, 2025) | 2025 | LMB cells (23 cells, different capacities/cathodes/cycling conditions) | 多样 (NMC, LFP etc.) | Li metal | 多配置 | 多样 | 多样 | 多样 | 容量衰减 | Uses early 15% of cycling data → CVRMSE < 6.5%; LSTM/GRU/Transformer ensemble | 数据来源可能来自 Uppaluri 数据集 | **P1 参考**: early-stage prediction (仅 15% 数据) 是本项目 t-k predicts t 思路的验证；stacked ensemble 在 LMB 上下文中有效 |
| **P6** | Boaretto, Martinez-Ibañez et al. — *"Hybrid Ceramic Polymer Electrolytes Enabling Long Cycling in Practical 1 Ah-Class High-Voltage Solid-State Batteries with Li Metal Anode"* (Advanced Functional Materials, 2024) | 2024 | 1 Ah 级 high-voltage solid-state Li||NMC pouch cell | High-voltage NMC (cathode loading 3-4 mAh/cm²) | Li metal (薄, 20-50 μm) | Low Li excess (~2-5) | 0.1-0.5C | ~3-4 mAh/cm² | Hybrid ceramic-polymer solid electrolyte | 容量衰减至 80% | 固态电解质下 CE 关键；固态-固态界面稳定性主导循环 | 否 | **P1 参考**: 实用级 (1 Ah) 全电池 vs 实验室 (coin cell) 的性能差异；薄锂负极 + 高正极载量 = 严格锂库存管理; 固态电池中 EIS 和 pressure 的重要性 |
| **P7** | Roering, Brunklaus et al. — *"External Pressure in Polymer-Based Lithium Metal Batteries: An Often-Neglected Criterion When Evaluating Cycling Performance?"* (ACS Applied Materials & Interfaces, 2024) | 2024 | Pouch-type NMC622||Li polymer solid-state cells | NMC622 | Li metal | Li excess (不详) | 多种 C-rate | 不详 | PEO/PCL 系 polymer electrolytes | capacity retention, rate capability, limiting current density | **External pressure** 显著改变 cycling 性能 — polymer 的力学性质决定 critical pressure 阈值; 高压力改善界面但可能引起 polymer 塑性变形 → 循环寿命反而缩短 | 否 | **P1 参考**: Pressure metadata 是 P1 字段（如果 partner 可以提供）; 压力不仅影响界面性能且可能引入额外的 degradation mode（polymer creep） |
| **P8** | Chen/Liao/Cui/Bao (Stanford) — *"Electrolyte Design for Li Metal Anodes"* series (Nature Energy / Joule / JACS, 2022-2024, 泛化工作组) | 2022-2024 | Thin-Li||NMC 硬币 / Cu||NMC pouch | NMC811, NMC622, LFP | Thin-Li (20 μm) / anode-free (Cu) | various, ~1-5 for thin-Li, 0 for anode-free | 0.5-4 mA/cm² | 1-4 mAh/cm² | LiFSI-based fluorinated ether 电解液 | capacity_retention < 80%, CE > 99.5% | CE 快速达到 >99%; Li morphology (chunky vs dendritic) → CE; anode-free 下 CE > 99.8% 必要; 贫电解液 (E/C ratio 低) 是关键测试条件 | 部分公开 | **P0 参考**: E/C ratio (electrolyte-to-capacity ratio) 是 P1 metadata 应该收集; fluorinated electrolyte 下 CE baseline 不同; anode-free 对电解液设计的要求远高于 Li-excess full-cell |

---

## 2. 当前项目与文献的对接分析

### 2.1 文献中与当前项目直接对应的信号

| 文献信号 | 当前项目对应 | 状态 |
| --- | --- | --- |
| P1 的 relax/rest 电压特征 | `rest_voltage_drop_mv_per_hour`, `record_voltage_*` | Li||Cu/Li||Li 已有 |
| P1 的 discharge capacity difference ΔQ | `discharge_capacity_mah` trend (cycle-to-cycle) | Li||Cu 已有 |
| P1/P2 的 CE trend | `ce_rolling_mean/std_past_5`, `ce_delta_*` | Li||Cu 已有 (ssr-annotated) |
| P4 的 anode-free CE decay rate | `ce_collapse`, `incomplete_capacity_event` (time-offset) | Li||Cu 已有作为 proxy |
| P7 的 external pressure effect | `pressure_mpa` (metadata) | **当前缺失** — full-cell 接入时必须收集 |
| P2 的 EIS impedance features | — | **当前缺失** — 需要 partner 提供或专门的 EIS 数据导入 |
| P1-P4 的 areal-capacity-normalized features | `areal_capacity_mah_cm2` (metadata) | **当前缺失** — full-cell 接入时 P0 收集 |
| P1-P6 的 cathode loading, N/P ratio | `cathode_loading_mah_cm2`, `np_ratio` (metadata) | **当前缺失** — full-cell 接入时 P0 收集 |

### 2.2 文献不直接覆盖但本项目独有的关注点

| 独有信号 | 原因 | 当前项目准备 |
| --- | --- | --- |
| `voltage_hysteresis_v` 作为极化梯度 | P1/P2 未单独分析 hysteresis，但当前 Li||Cu 数据已证明其是独立于 CE 的 degradation signal | Li||Cu feature schema 已含 `voltage_hysteresis_v` 和 `hysteresis_trend` |
| `charge_step_duration_s` 作为动力学代理 | 几乎全部文献仅关注容量和 EIS，未纳入工步时长特征 | Li||Cu feature schema 已含 charge/discharge duration |
| `horizon=3/5` leakage 防护规则 | 文献中未见显式 temporal leakage 防护 | 当前项目已设计完整的 horizon rule |
| LOCO CV 以 cell 为单位 | 文献中常见 random split | 当前项目强制执行 LOCO — 直接迁移到 full-cell |
| Observed/censored/protocol-censored 标签分类 | 大部分文献将所有 cell 视为 observed EOL | 当前项目已建立完整的标签审计框架 |

---

## 3. Full-Cell 数据接入时须向 Partner 收集的字段清单

以下清单基于文献调研和本项目的 metadata 需求综合设计。标记为 **P0** 的字段缺失将阻断 G2 metadata_gate。

### 3.1 Cell 标识与类型

| 优先级 | 字段 | 说明 | 文献来源 |
| :---: | --- | --- | --- |
| **P0** | `cell_id` | 唯一标识 (建议格式: `YYYYMMDD_cellType_cathode_serial`) | All |
| **P0** | `cell_type` | `full_cell` / `anode_free` / `solid_state` / `pouch` / `coin_cell` | P3, P4, P6, P7 |
| **P0** | `cell_format` | `coin_cell_2032` / `pouch_single_layer` / `pouch_1Ah` | P6 |
| P1 | `cell_mass_g` | 总质量 (g) | General |
| P1 | `cell_volume_cm3` | 体积 (如有) | General |

### 3.2 电极信息

| 优先级 | 字段 | 说明 | 文献来源 |
| :---: | --- | --- | --- |
| **P0** | `cathode_type` | NCM811, NCM622, LFP, LCO, etc. | All |
| **P0** | `cathode_loading_mah_cm2` | 正极面载量 | P1, P3, P4, P6 |
| **P0** | `anode_type` | `Li_metal` / `anode_free` / `Li_composite` | All |
| **P0** | `anode_thickness_um` | 锂负极厚度 (μm); anode-free = 0 | P1, P4 |
| **P0** | `anode_free_status` | True/False | P4 |
| **P0** | `np_ratio` | N/P ratio；anode-free 填 N/A 或 null | P1, P4, P6 |
| P1 | `anode_loading_mah_cm2` | 负极面载量（如有给定量） | P6 |
| P1 | `lithium_excess_pct` | Li excess (%) = (anode_cap - cathode_cap) / cathode_cap × 100 | P4, P6 |
| P2 | `current_collector_cathode` | 正极集流体 (Al foil / coated Al) | General |
| P2 | `current_collector_anode` | 负极集流体 (Cu foil / Ni foil) | General |

### 3.3 电解液

| 优先级 | 字段 | 说明 | 文献来源 |
| :---: | --- | --- | --- |
| **P0** | `electrolyte_code` | 标准化编码 (e.g., "1M_LiFSI_DME") | All |
| P1 | `electrolyte_detail_if_shareable` | 完整配方 (浓度, 溶剂, 添加剂) — 如可共享 | P1, P4, P8 |
| P1 | `electrolyte_amount_ul` | 电解液量 (μL) — 用于计算 E/C ratio | P8 |
| P1 | `ec_ratio_ul_per_mah` | E/C ratio = electrolyte volume / cathode capacity | P8 |
| P2 | `electrolyte_salt` | 锂盐: LiFSI, LiTFSI, LiPF6 etc. | P1, P4 |
| P2 | `electrolyte_solvent` | 溶剂体系 | P1, P4 |
| P2 | `electrolyte_additive` | 添加剂 (FEC, VC, etc.) | P4 |

### 3.4 实验条件

| 优先级 | 字段 | 说明 | 文献来源 |
| :---: | --- | --- | --- |
| **P0** | `temperature_c` | 测试温度 (°C) ± tolerance | All |
| **P0** | `current_density_ma_cm2` | 电流密度 | All |
| **P0** | `areal_capacity_mah_cm2` | 面容量 | All |
| **P0** | `voltage_cutoff_upper_v` | 充电截止电压 | P1, P3, P4 |
| **P0** | `voltage_cutoff_lower_v` | 放电截止电压 | P1, P3, P4 |
| **P0** | `c_rate_charge` | 充电倍率 (C) | P3, P4 |
| **P0** | `c_rate_discharge` | 放电倍率 (C) | P3, P4 |
| P1 | `pressure_mpa` | External pressure (MPa) — 对固态/软包 LMB 重要 | P6, P7 |
| P1 | `pressure_type` | `constant` / `spring_loaded` / `none` | P7 |
| P1 | `rest_duration_s` | Cycle 间搁置时长 (s) | P1 |
| P2 | `formation_protocol` | 化成阶段详细设定 (cycles, C-rate, cutoff) | General |
| P2 | `sampling_interval_s` | 数据采样间隔 (s) — 是否为 dV 触发? | General |

### 3.5 循环与终止

| 优先级 | 字段 | 说明 | 文献来源 |
| :---: | --- | --- | --- |
| **P0** | `cycling_protocol` | 循环协议详细描述 (CC-CV, CC, 多阶段?) | P1, P3 |
| **P0** | `planned_cycle_count` | 计划循环数 | General |
| **P0** | `termination_reason` | `natural_eol` / `safety_stop` / `equipment_stop` / `manual_stop` / `protocol_end` | P1, P3 |
| **P0** | `termination_capacity_retention_pct` | 终止时容量保持率 (%) | P1, P3 |
| P1 | `failure_mode` | `capacity_fade` / `CE_failure` / `soft_short` / `safety_event` / `dendrite_penetration` / `unknown` | P3, P6 |
| P1 | `knee_point_cycle` | Knee point 位置 (如果有) — 容量衰减拐点 | P2 |
| P2 | `abnormal_events` | 异常事件记录 (time, type, severity) | General |

### 3.6 数据导出

| 优先级 | 字段 | 说明 | 文献来源 |
| :---: | --- | --- | --- |
| **P0** | `data_format` | BTSDA / Arbin / Bio-Logic / Neware / custom CSV | General |
| **P0** | `cycle_layer_available` | True/False — cycle-level CSV 是否可导出 | General |
| **P0** | `step_layer_available` | True/False — step-level CSV 是否可导出 | General |
| P1 | `record_layer_available` | True/False — 完整 record 是否可导出 | P1, P3 |
| P1 | `record_sampling_method` | `fixed_interval` / `dV_triggered` / `none` | P1 |
| P1 | `eis_available` | True/False — EIS 在多少个 cycle 有测量？频率范围？ | P2 |
| P2 | `bts_step_xml_available` | BTS Step XML 是否可用于协议交叉验证 | Current project |

### 3.7 其他 (P2 — 有则更好)

| 优先级 | 字段 | 说明 |
| :---: | --- | --- |
| P2 | `separator_type` | 隔膜材料/型号 |
| P2 | `separator_thickness_um` | 隔膜厚度 |
| P2 | `cell_fabrication_date` | 制造日期 |
| P2 | `storage_duration_h` | 存储时间 (从制造到测试) |
| P2 | `partner_contact` | 数据提供方联系信息 |

---

## 4. Full-Cell 数据到达后的快速评估

### 4.1 Per-cell 第一印象速查

当 BTSDA 三层 CSV 到位且 metadata 表格填写完毕后，首先执行以下速查：

| 速查项 | 判定 |
| --- | --- |
| 是否有 cell 的 `termination_reason = natural_eol` 且 `termination_capacity_retention_pct ≤ 80%`? | **是 → 此 cell 有 observed capacity_eol_80** |
| 是否有 anode_free cell? | **是 → CE 标签优先级更高; EOL 定义可能不同** |
| N/P ratio 是否 > 5? | **是 → Li 库存过剩; capacity fade 主导 → capacity_eol_80 为主导标签** |
| N/P ratio 是否 1-2? | **是 → Li 库存紧张 → CE 标签更关键** |
| 是否有 EIS 数据? | **是 → knee point 标签可定义; EIS features 可加入特征表** |
| 是否有完整 record 层? | **是 → dQ/dV, rest-drop, 电压 curve 特征可计算** |
| 是否有 pressure 数据? | **是 → pressure 作为 condition feature 可加入 metadata 分析** |

### 4.2 n 个 cell 的最低要求

| 场景 | 最低 n | 理由 |
| --- | :---: | --- |
| LOCO CV 绝对下限 | 4 | 4 folds, 每 fold 1 test cell |
| Tiny smoke-test (仅验证 pipeline) | 4 | logistic regression only |
| 可接受的分析 (可发表级别) | 8-12 | 每 fold 有 ≥2 train cells |
| Anode-free vs Li-excess 对比 | 4+4 (each) | 两组对比需要平衡 |

---

## 5. 给 Codex 的后续处理建议

1. 将本文整理为 `docs/lmb-full-cell-literature-and-metadata-support.md`。
2. 将 §3 的字段清单导出为标准化的 metadata template (JSON/CSV/Excel 格式)。
3. 在 full-cell 数据到达后，执行 §4.1 的 per-cell 第一印象速查。
4. 所有文献阈值 (CE > 99%, capacity < 80%, knee point 位置) 需要在 full-cell 数据上校准 — 不可直接照搬。
5. 本文不替代 `docs/lmb-full-cell-readiness-plan.md` — 两者互补 (readiness plan = 内部流程设计, 本文 = 外部文献 + partner 接口)。

---

## 6. 禁止事项

1. **禁止**声称本项目已有 full-cell 模型性能
2. **禁止**将 Li||Li / Li||Cu 结果称为 full-cell
3. **禁止**在未校准的情况下直接照搬文献阈值 (CE cutoffs, knee point 定义等)
4. **禁止**在没有 metadata 的情况下直接开始 feature builder
5. **禁止**跨文献直接聚合不同电解液/阴极/协议的 LMB 数据 (batch confound)
6. **禁止**将文献中的 random split 性能作为本项目的参考 baseline — 本项目 LOCO only
7. **禁止**声称 `capacity_eol_80` 是 LMB full-cell 的唯一 EOL 标签 — LMB 的 CE failure, polarization failure, soft-short 都是 legitimate 多标签候选
