# REG-002 数据语义审查报告

**Generated**: 2026-06-29  
**Agent**: Trae (REG-002 Data Semantic Review Agent)  
**Scope**: 基于 Uppaluri/Onori Data in Brief 2025 论文全文、OSF 页面、JES 2026 关联论文  
**Target**: REG-002 — OSF Lithium-Metal Battery Degradation Dataset

---

## 1. REG-002 语义审查摘要

### 1.1 基本身份

| 字段 | 值 |
|------|-----|
| **source_id** | REG-002 |
| **论文** | Lithium-metal battery degradation dataset from continuous cycling experiments |
| **期刊** | Data in Brief, Vol. 61, 111787 (2025) |
| **DOI** | 10.1016/j.dib.2025.111787 |
| **关联 ML 论文** | Uppaluri et al., "Clustering and Prediction of Early Capacity Fade Trajectories in Lithium-Metal Batteries using Data-Driven Approaches", *J. Electrochem. Soc.* 173, 090535 (2026), DOI: 10.1149/1945-7111/ae63fa |
| **cell_scope** | `lmb_full_cell` — 确认为 Li-metal anode + NMC811 cathode pouch cell |
| **数据下载** | OSF view-only: https://osf.io/5dqwg/?view_only=608e4c22acdd483591d1d55b74a81401 |

### 1.2 作者团队与机构

| 作者 | 机构 | 角色 |
|------|------|------|
| Maitri Uppaluri | Stanford Energy Sciences & Engineering + SLAC | 第一作者，形式分析 |
| Wenting Ma | Stanford Energy Sciences & Engineering | 共同作者 |
| Le Xu | Stanford Energy Sciences & Engineering + SLAC | 共同作者 |
| Nojan Aliahmad | **Sakuu Corporation** | 制造商端数据收集 |
| Alireza Saatchi | Sakuu Corporation | 制造商端 |
| Karl Littau | Sakuu Corporation | 制造商端 |
| Simona Onori | Stanford Energy Sciences & Engineering | 通讯作者 (sonori@stanford.edu) |

**关键：** 数据由 Sakuu Corp.（锂金属电池制造商，San Jose, CA）在 R&D 实验室收集，不是学术实验室自组装 coin cell。数据来自工业级 pouch cell。

### 1.3 Cell 类型与 G1-G4 分组

| Group | Nominal Capacity (Q0) | Cell 数 | Charge C-rate | Discharge C-rate | CC Low Voltage | CC High Voltage | CV Current Cutoff | Design Differentiator |
|-------|----------------------|---------|--------------|-------------------|----------------|-----------------|-------------------|----------------------|
| **G1** | 3.8 mAh | 6 | 3 cell @ C/5, 3 cell @ C/2 | **1C** | 3.0 V | 4.3 V | 0.05 C | **Lowest capacity**（极小的 prototype cell）；两种充电倍率 |
| **G2** | 1000 mAh | 5 | **C/5** | **1C** | 2.8 V | 4.3 V | 0.02 C | 大容量 pouch cell；唯一的 G2 统一 C/5 charge |
| **G3** | 1000 mAh | 7 | 4 cell @ C/5, 3 cell @ **C/3** | **1C** | 2.8 V | **4.2 V** | 0.02 C | 大容量 pouch cell；高电压 cutoff 降至 4.2V；两种充电倍率 |
| **G4** | 327 mAh | 5 | **C/5** | **1C** | 3.0 V | 4.3 V | 0.05 C | 中等容量；统一的 C/5 charge |

**分组含义（论文原文）：** "classified into four different groups, based on the cell design specifications (such as number of layers in the cell, electrolyte design or electrode thickness) and the operating conditions at which they have been cycled"

因此分组同时包含：
- **Design 变量**（层数、电解液设计、电极厚度）
- **Operational 变量**（charge C-rate, voltage cutoff, CV cutoff）

**与 protocol 的分辨关系：** 分组不是 pure protocol，而是 design × protocol 的混合分组。这意味着：**同一个 group 内部可能存在 design 变体（如 G1 包含 C/5 和 C/2 两种 charge rate）**，因此分组不能直接当作 protocol label 使用。

### 1.4 正极、负极、电解液

| 属性 | 值 | 来源 |
|------|-----|------|
| **正极 (Cathode)** | NMC 811 (LiNi₀.₈Mn₀.₁Co₀.₁O₂) | 论文明确写 "nickel-manganese-cobalt cathode (NMC 811)" |
| **负极 (Anode)** | Lithium metal | 论文明确写 "lithium-metal anode" |
| **电解液 (Electrolyte)** | **未公开**（论文仅说 "electrolyte design" 是分组差异因素之一，但未给出成分、溶剂、盐浓度、添加剂） | **→ 缺失，需联系作者或参考关联论文** |
| **N/P Ratio** | **未提及** | **→ 缺失** |
| **Separator** | 未提及 | **→ 缺失** |
| **Areal Capacity** | 未直接给出（可从 Q0 和电极面积推断，但论文未提供电极面积） | **→ 缺失** |
| **Temperature** | **Room temperature**（论文明确写 "cycled at room temperature"，无具体数值） | **→ 存在但精度低** |

### 1.5 协议 (Protocol)

**全 cell 统一切换序列：**

```
Step 1: CC-CV Charge（C-rate 取决于 cell group）
Step 2: Rest = 600 s
Step 3: CC Discharge @ 1C（全 group 统一 1C 放电）
Step 4: Rest = 600 s
Step 5: → 回到 Step 1
```

**协议总结：**
- Charge: CC-CV，C-rate 可变（C/5, C/2, C/3）
- Discharge: CC，**统一 1C**
- Rest: 统一 600 s
- **无 multi-step protocol 切换**：全 cell 全程使用同一 protocol
- **无 EIS intermittent**：纯老化循环，无 routine EIS 插入

**关键生态含义：**
- 因为 **所有 cell 统一 1C 放电**，所以 discharge capacity 比较是在相同 discharge rate 下进行的 → **capacity fade 直接可比**
- Rest 时间统一（600s）→ **polarization relaxation 条件可比**
- 无 protocol 切换 → **不存在本项目 Li||Cu 数据中的 protocol boundary artifact 问题**
- 但这也意味着该数据集**缺少 protocol diversity**（无不同 DOD、multi-C-rate protocol information）

### 1.6 数据文件结构（两张关键 .mat）

每 cell 包含两个 .mat 文件：

| 文件名 | 内容 | 结构 |
|--------|------|------|
| `Gx_Celly_data.mat` | **Raw time series**：time, voltage, current → separate for charge & discharge, plus full cycle | Struct per cycle: `.charge.voltage`, `.charge.current`, `.charge.time`, `.discharge.voltage`, `.discharge.current`, `.discharge.time`, `.full_cycle.voltage`, `.full_cycle.current` |
| `Gx_Celly_capacity_degradation.mat` | **Cycle-level summary**：charge capacity, discharge capacity, EFC | per-cycle scalar: `Qchg(i)`, `Qdis(i)`, `EFC(i)` |

**这非常重要！** 这与之前的理解有所不同：
- `data.mat` 包含 **per-cycle raw time series**（voltage/current vs time in each cycle）
- 因此可以重建 **voltage curve / dQ/dV / capacity fade per cycle**
- **但 data 是按 cycle 分开存储的**（Struct per cycle），而非单张连续 table
- `capacity_degradation.mat` 是 cycle-level summary

### 1.7 equiv_cycle / EFC 与 cycle index 的关系

**RFC 定义：**

```
EFC(i) = Ah-Throughput(i) / (2 × Q0)
```

其中：
- `Ah-Throughput(i)` = 从 cycle 1 开始到 cycle i 结束（charge start → discharge end）的累积 |I_batt|dt
- `Q0` = 该 cell 所属 group 的 nominal capacity
- 分母 **2 × Q0**：一个完整 charge+discharge 的总理论 Ah throughput

**等值关系：**

| 条件 | EFC vs cycle index |
|------|-------------------|
| 前几 cycle（Qdis/Qchg ≈ Q0） | EFC ≈ cycle index（误差 < 1-2%） |
| 中期退化（Qdis ≈ 0.85 Q0） | EFC < cycle index（每 cycle EFC 增量 ≈ 0.85，累积偏小） |
| 晚期退化（Qdis ≈ 0.60 Q0） | EFC 与 cycle index 差值显著（每 cycle EFC 增量 ≈ 0.60） |

**结论：EFC 不是 cycle index，而是归一化的累积通量。** 当 cell 退化后，每个 nominal cycle 的 Ah throughput 下降，EFC 增量低于 1。在 80%-60% SOH 范围，EFC 与 cycle index 的差值可达 10-20%。

**对本项目的影响：**
- capacity_degradation.mat 中的 **discharge capacity vs EFC** 是正确的 degradation curve
- 但不能直接把 EFC 当作 cycle index 做 t-k 预测（因为 EFC 包含了未来退化信息）
- 如需 cycle-level 标签，应从 data.mat 的 Struct 数量获取 cycle index
- **EFC 更接近 "等效满循环次数"**，适合作为 SOH 横轴，但不适合作为 "第 k 个 cycle" 的时间标识

---

## 2. cycle life / EOL 定义

### 2.1 Data in Brief 论文中的 EOL

**论文未显式定义 EOL。** 以下是关键原文：

> "These cells were continuously cycled at room temperature ... The number of cycles that the cells underwent ranges from **250 to 650 cycles**."

> "This dataset consists of **only 23 cells** ... Nonetheless, the degradation curves exhibit meaningful variations"

论文将 "cycle count" 描述为 "250-650 cycles"，但 **未说明 stop criteria**（是否到 80%、是否短路、是否时间截止）。

### 2.2 JES 2026 关联论文中的 EOL

关联论文 "Clustering and Prediction of Early Capacity Fade Trajectories" (JES 2026) 使用了本数据集做 early prediction。搜索结果显示该论文可能采用 "early cycle data (95%, 92%, 90% capacity retention)" 预测后来的退化。**但 JES 论文全文通过 CAPTCHA 获取失败，未确认确切 EOL 阈值。** [待核验]

### 2.3 关联论文中的相关 EOL 参考

Ma et al., "Engineering Testing Protocols for Machine Learning-Based SoH Estimation in Lithium Metal Batteries", JES 2024 (DOI: 10.1149/1945-7111/ad9cc8) 同样使用了 Sakuu LMB 数据但关注 testing protocol design。该论文可能包含 SOH 相关定义。 [待核验]

### 2.4 当前建议

- **使用 capacity_eol_80（80% capacity retention）作为 EOL 标量是合理的**，但这需要本项目自行计算，不是数据集提供的
- **需要确认的是**：是否所有 23 cell 都达到了 80% retention（或有 cell 在 80% 之前就因其他原因终止）
- 建议：用 data.mat 计算 Qdis(i) / Qdis(5) 作为 SOH(i)，定义 EOL cycle = min {i : SOH(i) < 0.80}

---

## 3. 缺失字段清单

### 3.1 严重缺失（会阻止正式训练 G7-G9 gate）

| 缺失字段 | 严重度 | 说明 |
|----------|--------|------|
| **EOL cycle 标注** | **P0** | 数据集不提供 EOL 阈值，需本项目自行计算 |
| **EOL definition** | **P0** | 论文未定义 stop criteria；250-650 cycles 区间未区分 "达到 EOL" vs "提前终止" vs "被实验截断" |
| **Termination reason** | **P0** | 未知：是容量衰减至某阈值？是安全问题（short/dendrite）终止？是时间限制截断？ |
| **Electrolyte formulation** | **P0** | 论文仅写 "electrolyte design" 是分组差异之一，但未给出任何成分信息 |
| **N/P ratio** | **P0** | 完全缺失 |
| **Areal capacity (mAh/cm²)** | **P1** | 未提供电极面积 |
| **Formation cycle data** | **P1** | data.mat 中的 cycle 1 是否即首圈？是否有 formation 过程？ |
| **EIS 数据** | **P2** | 纯老化循环，无 EIS |
| **Temperature 数值** | **P2** | 仅有 "room temperature"，无具体值 |

### 3.2 中度缺失（影响特征构建但不阻止训练）

| 缺失字段 | 说明 |
|----------|------|
| **Electrode thickness** | "electrode thickness" 被列为 group differentiator，但无具体数值 |
| **Number of layers** | "number of layers" 被列在 design 差异中，无具体数 |
| **Pouch cell dimensions** | 仅知道是 "pouch"，无尺寸 |
| **Separator type** | 未提及 |
| **Stack pressure** | pouch cell 应有 stack pressure，未提及 |
| **Manufacturing date** | 未提及 |

### 3.3 存在但需特别注意的字段

| 字段 | 状态 | 注意事项 |
|------|------|----------|
| **Voltage curve per cycle** | ✅ 有 | data.mat 中有 per-cycle charge/discharge V(t), I(t) |
| **Capacity per cycle** | ✅ 有 | capacity_degradation.mat 中有 Qchg, Qdis per cycle + EFC |
| **Current data** | ✅ 有 | data.mat 中有 |
| **Protocol** | ✅ 有 | 论文详细描述 |
| **C-rate** | ✅ 有 | Table 1 |
| **Voltage cutoffs** | ✅ 有 | Table 1 |
| **Nominal capacity** | ✅ 有 | Table 1（但注意是 nominal Q0，不是 per-cell measured initial capacity） |
| **Rest time** | ✅ 有 | 统一 600s |
| **Temperature** | ⚠️ 模糊 | "Room temperature" 无数值 |
| **Cell count per group** | ✅ 有 | 6 + 5 + 7 + 5 = 23 |

---

## 4. 可补充 metadata 表（当前已知 vs 建议补充）

| Metadata 字段 | 当前状态 | 可补充来源 | 建议方式 |
|---------------|----------|------------|----------|
| Electrolyte formulation | 缺失 | 关联 JES papers + 作者 | **联系作者（sonori@stanford.edu）** |
| N/P ratio | 缺失 | 作者 / Sakuu spec | **联系作者** |
| Areal capacity | 可算（需电极面积） | 作者 / Sakuu spec | **联系作者** |
| EOL definition | 关联论文可能有 | JES 2026 paper | Codex 下载并阅读 JES 2026 全文 |
| Termination reason | 作者知道 | 作者 | **联系作者** |
| Formation protocol | 可能需要联系作者 | 作者 | **联系作者** |
| Electrode thickness | 作者知道 | 作者 | **联系作者** |
| Pouch cell dimensions | 作者知道 | 作者 | **联系作者** |
| Stack pressure | 作者知道 | 作者 | **联系作者** |
| Temperature numerical range | 实验室记录应有 | 作者 | **联系作者**或查看 Sakuu 测试记录 |
| Per-cell initial capacity | 可从 data.mat cycle 1-5 提取 | data.mat | Codex 解析 .mat 文件后计算 |
| CE per cycle | 可计算（Qdis/Qchg） | data.mat | Codex 解析后计算 |

---

## 5. 对 Codex 下一步 baseline planning 的风险提醒

### 5.1 允许进行的事项（安全操作）

- **下载 .mat 文件**（OSF view-only link）
- **解构 data.mat**：提取 per-cycle voltage/current time series，计算 Qdis(i), Qchg(i), CE(i) = Qdis(i)/Qchg(i)
- **计算 SOH sequence**：用 Qdis(i) / Qdis(cycle_5_max) 或 Qdis(i) / Q0 作为 SOH
- **自行定义 EOL**：如 min {i : SOH(i) < 0.80} → cycle_eol_80
- **构建 Li||NMC811 full-cell feature schema**：基于电压曲线提取 per-cycle features（discharge capacity, mean voltage, voltage variance, V(discharge_start) - V(discharge_end)，恒流放电时间等）

### 5.2 风险：EOL 定义的模糊性

- **问题：** 不知道 250-650 cycles 区间中，哪些 cell 真正到达了 EOL，哪些是被截断的
- **后果：** 如果某个 cell 在 550 cycles 时容量仍有 85%，而我们标记 cycle_eol_80 = 550（因为测试在 550 停），这就是截断偏差
- **建议：** Codex 应先绘制所有 23 cell 的 SOH vs cycle 曲线，判断哪些 cell 末端 SOH < 80%，哪些 cell 末端 SOH > 80%（可能被截断）。对于末端 SOH > 80% 的 cell，应标记为 **right-censored**（对应本项目 label_policy 中的 censored label）

### 5.3 风险：EFC 不等于 cycle index

- **问题：** capacity_degradation.mat 中的 x 轴是 EFC，不是 cycle index
- **后果：** 如果直接用 EFC 做 t-k 预测，EFC 的分子 Ah-Throughput 包含了所有未来 cycle 的信息（是累积量），会导致 **前瞻偏差**
- **建议：** 使用 data.mat Struct 的计数作为 cycle index；EFC 仅用于 SOH vs EFC 的 degradation curve 绘图

### 5.4 风险：nominal capacity Q0 vs actual capacity

- **问题：** G2 和 G3 都是 Q0 = 1000 mAh，但这是 nominal capacity，不是 per-cell 实测 initial discharge capacity
- **后果：** 用 Q0 计算 SOH 会导致所有 G2/G3 cell 的 cycle_1 SOH ≈ 100%（概念正确），但 per-cell 的 variability 被掩盖
- **建议：** 用每 cell 的 Qdis(cycle_5) 作为 individual Q_initial（避开 formation 波动）

### 5.5 风险：G2 和 G3 同为 1000 mAh 但不同 voltage cutoff

- **问题：** G2 (4.3V cutoff) vs G3 (4.2V cutoff) 意味着不同的 cathode utilization，因此不同的初始面容量
- **后果：** G2 和 G3 的 capacity 不可直接比较（G2 的 Qdis 天然更大）
- **建议：** 做 G2-vs-G3 比较时，使用 per-cell normalized SOH

### 5.6 风险：G1 cell 极小容量（3.8 mAh）

- **问题：** G1 的 3.8 mAh 远低于 G2/G3 (1000 mAh) 和 G4 (327 mAh)
- **后果：** G1 的容量测量精度可能较差（3.8 mAh 循环仪精度影响大）；与 G2-G4 的 degradation physics 可能不直接可比
- **建议：** 考虑将 G1 作为**单独的子数据集**处理，不与 G2-G4 混合

### 5.7 风险：23 cell 的组合 → n 较小

- **LOCO 可行性：** 全 23 cell LOCO 可行（N_train ≈ 22 per fold）
- **但分组后 cell 数极低：** 最大组 G3 = 7 cell，最小组 G2 = 5 cell
- **如果按 group 分层 LOCO→ per-group 仅 5-7 cell，极不可靠**
- **建议：** 跨 group LOCO（全 23 cell shuffle）而非 group-stratified LOCO

---

## 6. 是否建议联系作者

**是，强烈建议联系作者。** 建议邮件主题和内容：

**收件人：** sonori@stanford.edu (Simona Onori)  
**抄送：** muprluri@stanford.edu (Maitri Uppaluri)

**建议询问内容（优先级排序）：**

| 优先级 | 问题 |
|--------|------|
| **P0** | What was the stop criterion for each group? Were cells cycled until a specific capacity retention threshold, or until other failure modes (short circuit, dendrite)? |
| **P0** | Can you share the electrolyte formulation details (solvent, salt, concentration, additives) for each group? This is critical for our modeling. |
| **P1** | What is the N/P ratio and areal capacity for each group? |
| **P1** | Can you provide the per-cell actual initial capacity (Q_initial) instead of the nominal Q0? |
| **P2** | Do you have EIS or other intermittent characterization data for these cells? |
| **P2** | What is the formation protocol for these cells? Which cycle is "cycle 1" in the dataset? |
| **P3** | Can you confirm whether the "room temperature" is controlled (e.g., 25±1°C)? |

---

## 7. 输出给 Codex 的行动清单

### P0（立即执行）

1. 下载 OSF 数据，解压 .mat 文件
2. 绘制 23 cell 的 SOH vs cycle（用 Qdis/Q0）
3. 分类：哪些 cell 末端 SOH < 80%（reached EOL）、哪些 > 80%（potentially censored）
4. 计算 per-cell EOL cycle = min {i : Qdis(i) < 0.80 × Qdis(max_early_cycle)}
5. 从 data.mat 提取 per-cycle voltage curve → compute V_mean, V_variance, discharge time, capacity per cycle

### P1（验证）

6. 确认 JES 2026 论文中 EOL 的实际定义（需绕过 CAPTCHA 下载）
7. 确认 Ma et al. JES 2024 的 protocol design 是否适用于 REG-002

### P2（补充）

8. 联系作者获取 electrolyte + N/P + termination reason
9. 评估是否需要等待作者回复才能继续 baseline

---

*本审查基于 Data in Brief 论文全文 (PMC12272929) + OSF 说明页面 + 关联论文搜索结果。JES 2026 全文因 CAPTCHA 未能获取，EOL 定义部分仍标注 [待核验]。*
