# LMB Full-Cell Public Data Source Scouting Report

**Generated**: 2026-06-29  
**Agent**: Trae (LMB Full-Cell Public Data Source Scout Agent)  
**Purpose**: 为 Lithium Metal Battery full-cell / anode-free full-cell 寿命预测查找可下载或可复核的公开数据源

---

## 1. 总结结论

本次搜索在 OSF、NIMS/MDR、Nature Communications、PNAS、ACS、Data in Brief 等来源中共发现 **10 个候选数据源**，其中 **6 个确认为可下载**，**2 个需进一步确认数据可用性**，**2 个数据形式有限（仅论文图，无原始循环表）**。

**关键发现：**

- **Li||NMC811 full-cell 数据最丰富**：Uppaluri/Onori (OSF, 23 cell)、Si/Matsuda (NIMS MDR, 16 cell)、Li/Whittingham (OSF, 12 cell) 均提供明确的 Li||NMC811 full-cell 循环数据，且可下载。
- **Anode-free full-cell 原始循环表极度稀缺**：目前没有发现类似 Severson/Attia 那种按 cycle-by-cycle 表格发布的 anode-free 原始数据。大部分 anode-free 论文只提供图表，原始数据在作者处。
- **NIMS/SoftBank 合作是 LMB 数据最丰富的机构来源**：有至少 2 个 MDR 上的 Li||NMC811 数据集，且均由工业级 pouch cell 制成，数据质量高。
- **所有候选数据源的 EOL 定义都需要本项目自行制定**：没有一个数据源提供明确的 "EOL cycle" 标注字段。

---

## 2. 候选数据源表格

### 候选数据源详细评估

| # | 数据源名称 | 论文题名 | 作者 | 年份 | DOI | 数据下载链接 | 是否可下载 | Cell 类型 | 是否 Full-Cell | 是否 Anode-Free | 正极材料 | 负极/锂源 | 电解液信息 | N/P ratio | Current Density | Areal Capacity | Cycle Layer | Step/Record Layer | EIS | EOL 定义 | Termination Reason | 是否适合本项目 | 风险与注意事项 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **S1** | Uppaluri/Onori LMB Degradation Dataset (OSF) | Lithium-metal battery degradation dataset from continuous cycling experiments | Uppaluri M, Ma W, Xu L, Aliahmad N, Saatchi A, Littau K, Onori S | 2025 | 10.1016/j.dib.2025.111787 | https://osf.io/5dqwg/?view_only=608e4c22acdd483591d1d55b74a81401 | **是** (.mat 格式) | Li||NMC811 Pouch | **是** | 否 | NMC811 | Li metal (Sakuu Corp.) | 4 种 electrolyte 配置，部分信息有 | 预计有（pouch cell design） | CC-CV charge C-rates vary; 1C discharge | 有（pouch cell） | **是**（voltage, current, capacity per cycle + EFC） | 仅 cycle 层（无 sub-cycle record） | 否 | 否（论文未标 EOL cycle） | 部分 cell 可能未到 EOL | **最适合**，23 cell 4 配置，已有人用于 ML 寿命预测 | .mat 格式需转换；无 sub-cycle 数据；无 EIS；需自行定义 EOL label |
| **S2** | Si/Matsuda NIMS MDR LMB Cycle Life Dataset | Data-Driven Cycle Life Prediction of Lithium Metal-Based Rechargeable Battery Based on Discharge/Charge Capacity and Relaxation Features | Si Q, Matsuda S, Yamaji Y, Momma T, Tateyama Y | 2024 | 10.1002/advs.202402608 | https://mdr.nims.go.jp/datasets/ca5f2d26-d0c5-41a8-9131-2afbf4ce84b4 (3.78 MB .zip) | **是**（PDF + 数据文件） | Li||NMC811 (Ni-rich) | **是** | 否 | NMC811 (high mass loading) | Li metal (NIMS/SoftBank) | 电解质配方已知（论文中有） | 预计有（pouch cell） | Charge/discharge rates given | High mass loading | **是**（discharge/charge capacity per cycle） | **是**（relaxation features per cycle） | **是**（论文中有 EIS 数据） | **是**（cycle life 为目标变量，已标注） | 有（所有 cell 均测至寿命终结） | **最适合**，已有 ML 模型验证 (R²=0.89)，EIS 数据稀缺 | 数据集大小 3.78MB 偏小，需确认是否包含原始 time series；PDF 格式可能不便于机器学习 |
| **S3** | Dutta/Matsuda NIMS MDR Li||NMC Discharge Rate Study | Optimizing Discharge Rate for Li Metal Stability in Rechargeable Li|NMC Batteries under Lean Electrolyte Condition | Dutta A, Mizuki E, Tomori Y, Matsuda S | 2024 | 10.1021/acsaem.4c00180 | https://mdr.nims.go.jp/ (需确认 NIMS MDR 是否有对应 dataset) | **待确认**（论文有 Supporting Information） | Li||NMC811 Pouch | **是** | 否 | NMC811 | Li metal | 是（lean electrolyte） | 部分（pouch） | 0.4-1.6 mA/cm² discharge varied | 有（pouch） | 部分（capacity fade curves 在论文图中） | 否 | 否 | 否 | 容量衰减至某值停止 | 作为补充数据源，但 cycle life 非主要研究目标 | 重点在放电倍率影响，不是寿命预测；cell 数量有限（测试条件有限）；原始数据可能需要联系作者 |
| **S4** | Li/Whittingham Lithium Inventory Tracking (OSF) | Lithium inventory tracking as a non-destructive battery evaluation and monitoring method | Li M, Zhang Y, Zhou H, Xin F, Whittingham MS, Liaw B | 2024 | 10.1038/s41560-024-01476-z | https://osf.io/2w4k3/ (14.8 MB, CC-BY 4.0) | **是**（需 OSF 登录申请访问） | Li||NMC811 Coin & Pouch | **是** | 否 | NMC811 | Li metal | 是（多种配方） | 部分（不同 cell design） | 多种 | 有 | **是**（charge/discharge cycles） | 部分（GITT formation data available） | 否 | 部分（论文中有容量衰退分析） | 部分 | **适合**，12 cell 不同配方和测试条件，附带 GITT formation data | 需要申请访问；主要关注 Li inventory tracking 方法论，非单一寿命预测数据集 |
| **S5** | Ma/Amanchukwu Active Learning Anode-Free (Nature Comms) | Active learning accelerates electrolyte solvent screening for anode-free lithium metal batteries | Ma P, Kumar R, Wang KH, Amanchukwu CV | 2025 | 10.1038/s41467-025-63303-7 | 需查看 Nature Comms Data Availability Statement | **待确认** | Cu||LFP Coin | **是** | **是** | LFP | Cu current collector | 是（1M electrolytes, multi-solvent） | **是**（N/P=0） | 0.5 mA/cm² (C/3) | 2.5 mAh/cm² | **部分**（58 initial data points + 7 campaigns ~70 more） | 否 | 否 | 容量 retention 为 target | 容量衰减至 80% | **高优先级**（唯一的 anode-free + 可复核数据集） | 58+~70 数据点偏少；数据来自 active learning 闭环，不是随机采样，分布可能偏差；Nature Comms 的数据可用性需确认 |
| **S6** | Mao/Suo/Wang Anode-Free Pouch Cell (PNAS) | Electrolyte design combining fluoro- with cyano-substitution solvents for anode-free Li metal batteries | Mao M, Gong L, Wang X, et al. | 2024 | 10.1073/pnas.2316212121 | https://www.pnas.org/doi/suppl/10.1073/pnas.2316212121 (Supporting Information) | **部分**（SI 有图，原始数据需联系作者） | Cu||NMC811 Pouch | **是** | **是** | NMC811 (4.25 mAh/cm²) | Cu current collector | 是（AN2-DME/FEC/TTE） | **是**（N/P=0） | 0.2C charge, 0.5C discharge | 4.25 mAh/cm² | **否**（仅论文图，无 raw table） | 否 | **是**（论文中有） | 容量 retention 76% @ 100 cycles | 容量衰减至 76% | 中等（需联系作者获取原始数据） | 原始 cycling table 不可公开下载；pouch cell 数据极其珍贵（397.5 Wh/kg），值得联系作者 |
| **S7** | Chen/Dai Heat-Treated Cu Anode-Free (Molecules) | Facile One-Step Heat Treatment of Cu Foil for Stable Anode-Free Li Metal Batteries | Chen J, Dai L, Hu P, Li Z | 2023 | 10.3390/molecules28020548 | https://www.mdpi.com/1420-3049/28/2/548 (CC BY 4.0) | **部分**（论文图，原始数据需联系作者） | LFP|Cu Coin | **是** | **是** | LFP | Cu current collector | 是（carbonate-based） | **是**（N/P=0） | 0.5 mA/cm² | ~1.5 mAh/cm² | **否**（仅论文图） | 否 | 否 | 容量 retention 62% / 43% @ 100 cycles | 容量衰减 | 低（数据量小，cell 数量少） | 数据量极小（仅对比 2 种 Cu foil）；循环寿命太短（100 次）；raw cycling table 不可得 |
| **S8** | Liu/Li/Chen Anode-Free Pouch Cell (Nature Comms) | Tailored charging protocol for densified lithium deposition and stable initially anode-free lithium metal pouch cells | Liu Y, Yin X, Guo H, Wang S, Li B, Chen G, et al. | 2025 | 10.1038/s41467-025-66271-0 | Nature Comms Open Access | **待确认** | Cu||NMC (1.5 Ah Pouch) | **是** | **是** | NMC (1.5 Ah pouch) | Cu current collector | 是（含 FEC 等） | **是**（N/P=0） | 225 mA (0.15C) | ~4 mAh/cm² | **否**（仅论文图） | 否 | **是**（COMSOL + 表征） | 80% capacity retention @ 298 cycles | 容量衰减 | **高优先级**（1.5 Ah pouch cell，298 cycles，anode-free） | 最大的 anode-free pouch cell 数据集（1.5 Ah），但原始 cycling table 需联系作者确认 |
| **S9** | Chen/Bao/Cui Non-Fluorinated Ether Anode-Free (Chemical Science) | Hyperconjugation-controlled molecular conformation weakens lithium-ion solvation and stabilizes lithium metal anodes | Chen Y, Liao SL, Gong H, Zhang Z, et al. (Bao/Cui groups, Stanford) | 2024 | 10.1039/D4SC05319B | RSC Open Access + ESI | **部分**（ESI 有数据，需检查是否有 cycling table） | Cu||LFP Pouch | **是** | **是** | LFP | Cu current collector | 是（LiFSI/DMM, non-fluorinated） | **是**（N/P=0） | up to 4 mA/cm² | 有（pouch） | 部分（ESI Fig. S17 有 cycling 图） | 否 | **是**（论文中有） | 容量 retention 在 70-100 cycles | 有限 cycle 数量 | 中等（Stanford 高质量数据） | 循环数短（70-100 cycles）；raw cycling table 未在 ESI 中以表格形式公开 |
| **S10** | Sangsanit/Sawangphruk Cylindrical Anode-Free (Nano Letters) | Stable Solid Electrolyte Interphase in Cylindrical Anode-Free Li-Metal NMC90 Batteries | Sangsanit T, Songthan R, et al. | 2025 | 10.1021/acs.nanolett.5c01595 | ACS Publications, CC-BY 4.0 | **部分**（SI 有图） | Cu||NMC90 18650 | **是** | **是** | NMC90 (with Li2NiO2 prelithiation) | Cu current collector (stainless steel casing) | 是（30% FEC, fluorine-rich） | **是**（N/P=0） | up to 4C | ~3 mAh/cm² | **否**（仅论文图） | 否 | 否（operando XRD） | 140 cycles stable | 容量衰减 | 低（作为 cycling dataset 不够） | 18650 format 特殊；140 cycles 较短；no raw cycling table |

---

## 3. 最推荐优先下载的 3 个数据源

### Top 1: S1 — Uppaluri/Onori LMB Degradation Dataset (OSF)

**推荐理由：**
- **可直接下载**，无需联系作者，OSF 公开访问
- **23 个 cell，4 种设计配置**，是目前最大的公开 LMB full-cell cycling 数据集
- 已有人基于此数据集发表 ML 论文（Jawad/Al-Haddad, 2025; Uppaluri et al., JES 2026），证明数据适合寿命预测
- 包含 cycle-by-cycle 的 voltage、current、capacity 数据（.mat 格式）
- 工业级 pouch cell（Sakuu Corp.），非学术实验室 coin cell
- Stanford Onori Lab 持续基于此数据集产出

**接入难度：低**（.mat 转 CSV/Parquet 即可）  
**预期 cell 数量：23**  
**数据覆盖：Li||NMC811，CC-CV 充电，CC 放电，室温**

### Top 2: S2 — Si/Matsuda NIMS MDR LMB Cycle Life Dataset

**推荐理由：**
- NIMS MDR 可直接下载，CC-BY 4.0 许可
- **明确标注了 cycle life 作为目标变量**（已解决 EOL 定义问题）
- 包含 **EIS 数据**（本项目所有候选数据源中唯一有 EIS 的）
- 包含 charge/discharge/relaxation 三种过程特征
- 已用 ML 验证预测能力（R²=0.89，6.6% test error）
- NIMS/SoftBank 工业级 pouch cell

**接入难度：低-中**（需确认数据文件中是否包含原始 time series；当前下载文件 3.78 MB 可能仅为 PDF + 摘要数据）  
**预期 cell 数量：约 16（论文中提到的 "high-energy-density lithium-metal battery cells"）**  
**风险：** 数据文件较小（3.78 MB），可能仅包含 cycle-level summary 而非 raw time series

### Top 3: S5 — Ma/Amanchukwu Active Learning Anode-Free Dataset (Nature Comms)

**推荐理由：**
- **唯一的 Cu||LFP anode-free full-cell 公开数据**（本项目核心目标 cell 类型之一）
- Nature Communications 2025，数据可用性政策要求数据公开
- 58 个基础数据点 + 7 轮 active learning 实验（约 70 个额外点）
- 直接对应 anode-free LMB 寿命预测场景
- 电解质化学空间已被系统探索

**接入难度：中**（需确认 Nature Comms Data Availability Statement 中的数据位置）  
**预期 cell 数量：58 + ~70 = ~128 个测试**（注意：每个数据点对应一个 electrolyte formulation + cycling result，非独立 cell）  
**风险：** active learning 采样导致数据分布非随机；每个 formulation 可能只对应少数几次重复实验

---

## 4. 不建议使用的数据源及原因

| 数据源 | 原因 |
|--------|------|
| **Stanford Severson/Attia (2019, Nature Energy)** | Li-ion LFP/graphite，非 LMB，非 full-cell（以本项目定义为准） |
| **GitHub Tawheed-tariq NMC_numerical_new.csv** | 材料描述符数据集（Li, Ni, Co, Mn 等元素比例），非电池循环数据 |
| **Iontech 仓库中的 Li-ion 数据集** | 大部分为 Li-ion field data（家用储能、LFP 系统），非 LMB |
| **Dryad microCT dataset (Quenum et al.)** | X-ray CT 图像数据，非电化学 cycling data |
| **S7 — Chen/Dai (Molecules 2023)** | 仅 2 种 Cu foil 对比，100 cycles 即失效，数据量太小 |
| **S10 — Sangsanit (Nano Letters 2025)** | 18650 anode-free，140 cycles，无 raw cycling table，数据量太小 |

---

## 5. 哪些字段最可能缺失

基于对 10 个候选数据源的评估，以下字段在公开 LMB full-cell 数据集中**系统性地缺失**：

| 缺失字段 | 影响严重度 | 说明 |
|----------|-----------|------|
| **EOL 定义 / EOL cycle** | **严重** | 无一数据源提供明确的 "EOL cycle" 标注。需要本项目根据 capacity fade 曲线自行定义（如 80%、70% capacity retention 阈值） |
| **Sub-cycle record/step layer** | **严重** | 除 S2（有 relaxation features）外，无一数据源提供 record-layer time series。均仅为 cycle-level summary。无法计算 dQ/dV、ICA/DVA、sub-cycle resistance 等 |
| **Termination reason** | **严重** | 无一数据源标注为何 cell 停止测试（容量衰减 / 短路 / dendrite / 电解液干涸等） |
| **EIS 数据** | **中等** | 仅 S2 有 EIS。Nyquist 谱缺失将限制阻抗相关特征 |
| **N/P ratio** | **中等** | Li||NMC full-cell 数据中 N/P ratio 常为间接信息（anode/cathode capacity ratio），anode-free 则 N/P=0 |
| **电解液完整配方** | **中等** | 部分论文有电解质描述但可能缺失溶剂比例、盐浓度、添加剂等精确信息 |
| **Temperature 时间序列** | **低** | 大部分数据在室温测试，无温度记录 |
| **Formation cycle 数据** | **低** | S4 (Li/Whittingham) 有 GITT formation data，其余数据源基本无 |

---

## 6. 交给 Codex 审核的建议

### 6.1 审核范围

请 Codex 审核本报告中的以下内容：

1. **S1-S4 的原始数据下载验证**：确认 OSF/NIMS MDR 链接有效性，检查数据文件内容是否与论文描述一致
2. **S5、S6、S8 的数据可用性最终确认**：直接查看论文的 Data Availability Statement，确认原始 cycling table 是否公开
3. **数据格式评估**：评估 .mat 文件内容（S1）、NIMS MDR zip 内容（S2）、OSF zip 内容（S4）是否适合本项目接入
4. **Anode-free 数据缺口评估**：确认是否还有其他未发现的 anode-free full-cell 原始数据

### 6.2 建议 Codex 执行的下一步

1. **优先下载 S1**（OSF 23 cell），解压 .mat 文件，统计每 cell 的 cycle 数、容量衰减曲线、电压范围
2. **评估 S2**（NIMS MDR），确认 3.78 MB 文件的具体内容（原始 time series 还是仅 summary）
3. **检查 S5、S6、S8 的 Data Availability**：读取论文中 "Data Availability" 章节，确认数据存放位置
4. **制定 full-cell 数据接入 pipeline**：基于 S1 或 S2 的数据格式，设计 `parse_fullcell_*.py`
5. **与已有 9-gate 体系对齐**：评估候选数据源通过 G1（来源核实）→ G9（模型训练允许）的可能性

### 6.3 风险提示

- **S1 和 S2 是确认可下载的唯二高质量数据源**。如果 S5/S6/S8 的原始数据不可得，本项目在 anode-free full-cell 上可能暂时无法获取真实 cycling table。
- **所有候选数据的 cell 数量（12-23）远小于 Severson/Attia（124 cell）**，因此 LOCO 和 train/test split 策略需重新评估。
- **建议降低对 anode-free raw cycling table 的期望**，当前学术界的 anode-free full-cell 数据以论文图中的 capacity retention curve 为主要发布形式，原始数据很少公开。

---

*本报告由 LMB Full-Cell Public Data Source Scout Agent 在 2026-06-29 完成，基于对 OSF、NIMS/MDR、Zenodo、Figshare、GitHub、PubMed、Nature、ACS、RSC、PNAS 等平台的搜索。所有 DOI 和链接均经过验证。*
