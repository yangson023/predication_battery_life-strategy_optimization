# LMB Public Full-Cell Data Registry (Draft)

**Generated**: 2026-06-29  
**Agent**: Trae (LMB Public Full-Cell Data Registry Draft Agent)  
**Status**: DRAFT — 所有 `dataset_role`、`cell_scope`、`training_allowed` 判断需 Codex 后续审查  
**Notation**: `[待核验]` = 待 Codex/用户核验；`[需作者联系]` = 数据未公开下载，需联系作者

---

## 1. 候选数据源注册表

| source_id | 数据源名称 | 论文题名 | 作者 / 团队 | 年份 | DOI | 数据链接 | 仓库类型 | cell_scope | 是否 LMB | 是否 Full-Cell | 是否 Anode-Free | 是否只有 Li\|\|Li/Li\|\|Cu | 是否有 Raw Cycling Table | 是否有 Source XLSX/CSV | 是否有 Metadata | 是否有 Protocol/Method 描述 | 是否可能支持 capacity_eol_80 | 是否可能支持 CE label | 是否可能支持 voltage/polarization feature | 推荐用途 | intake_priority | 风险说明 | 需要 Codex 核验的问题 |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| **REG-001** | Amanchukwu Lab AL-anode-free GitHub | Active learning accelerates electrolyte solvent screening for anode-free lithium metal batteries | Ma P, Kumar R, Wang KH, Amanchukwu CV (UChicago) | 2025 | 10.1038/s41467-025-63303-7 | GitHub: https://github.com/AmanchukwuLab/AL-anode-free ; Box: https://uchicago.box.com/s/8ffdqrfgf7v4fogxi4nkzl2dlw6fuj72 | GitHub + Box (虚拟搜索空间 >500MB) | anode_free_full_cell | 是 | 是 | **是** | 否 | 是（label_data_post_batch*.csv，per-electrolyte capacity retention） | 是（CSV，labeled datasets per batch） | 是（电解质成分、capacity retention、cycle count） | 是（论文 + GitHub notebook） | 是（capacity retention 作为目标变量） | 部分（capacity retention 可间接推 CE） | 否（无 raw voltage curve） | label_audit, strategy_optimization_reference | **P0_download_first** | 数据格式是 per-electrolyte summary（capacity retention），不是 per-cycle raw cycling table；virtual_search_space 500MB 需从 Box 下载；无 voltage curve 时间序列 | 1. `label_data_post_batch*.csv` 是否每行对应一个 electrolyte formulation + 多次实验的 mean capacity retention？2. 是否有 per-cycle 的 capacity fade curve（而非仅最终 retention）？3. Box 链接是否永久有效？ |
| **REG-002** | Uppaluri/Onori LMB Degradation Dataset (OSF) | Lithium-metal battery degradation dataset from continuous cycling experiments | Uppaluri M, Ma W, Xu L, Aliahmad N, Saatchi A, Littau K, Onori S (Stanford / Sakuu Corp.) | 2025 | 10.1016/j.dib.2025.111787 | https://osf.io/5dqwg/?view_only=608e4c22acdd483591d1d55b74a81401 | OSF | lmb_full_cell | 是 | 是 | 否 | 否 | 是（per-cycle voltage/current/capacity） | 是（.mat 格式，可转 CSV） | 是（4 种 design configuration，C-rates，voltage cutoffs） | 是（Data in Brief 论文详细描述 CC-CV charge / CC discharge） | **是**（per-cycle capacity + EFC） | 部分（capacity 可计算 CE，但论文未明确提供 CE sequence） | **是**（per-cycle voltage 数据） | feature_schema_test, label_audit, strategy_optimization_reference | **P0_download_first** | .mat 格式需转换为 CSV；无 sub-cycle record/step layer（仅 cycle level summary）；无 EIS 数据；EOL 需自行定义（论文未标 EOL cycle）；cell 数量 23，中等偏小 | 1. .mat 文件是否包含 raw time series 还是仅 per-cycle summary？2. 每 cell 的 EFC 数分布？容量衰减到多少 % 才停止测试？3. electrolyte 配方是否完全公开？ |
| **REG-003** | Si/Matsuda NIMS MDR LMB Cycle Life | Data-Driven Cycle Life Prediction of Lithium Metal-Based Rechargeable Battery Based on Discharge/Charge Capacity and Relaxation Features | Si Q, Matsuda S, Yamaji Y, Momma T, Tateyama Y (NIMS / SoftBank) | 2024 | 10.1002/advs.202402608 | https://mdr.nims.go.jp/datasets/ca5f2d26-d0c5-41a8-9131-2afbf4ce84b4 | NIMS MDR | lmb_full_cell | 是 | 是 | 否 | 否 | 部分（3.78 MB zip 中是否含原始 time series？[待核验]） | 部分（PDF + data files，格式 [待核验]） | 是（relaxation features，EIS 数据） | 是（论文详细描述 charge/discharge/relaxation 过程） | **是**（cycle life 作为已标注目标变量，R²=0.89） | [待核验]（论文含 EIS，CE 可能可计算） | **是**（discharge/charge capacity + relaxation voltage） | feature_schema_test, label_audit | **P0_download_first** | 3.78 MB 偏小，可能仅含 cycle-level summary 而非 raw time series；需确认数据格式（CSV/XLSX 还是仅 PDF 表格）；NIMS MDR CC-BY 4.0，license 明确 | 1. NIMS MDR zip 文件中到底包含什么格式的 cycling data？2. 每个 cell 的 cycle life 是否直接标注？3. EIS 数据是否包含 Nyquist 原始频率谱？ |
| **REG-004** | Li/Whittingham Lithium Inventory Tracking (OSF) | Lithium inventory tracking as a non-destructive battery evaluation and monitoring method | Li M, Zhang Y, Zhou H, Xin F, Whittingham MS, Liaw B (Idaho National Lab / Binghamton) | 2024 | 10.1038/s41560-024-01476-z | https://osf.io/2w4k3/ (14.8 MB, CC-BY 4.0, 需登录申请访问 [待核验]) | OSF | lmb_full_cell | 是 | 是 | 否 | 否 | 是（12 datasets of charge/discharge cycles） | [待核验]（OSF 14.8 MB 文件格式待确认） | 是（12 种 cell formulation / configuration / test condition） | 是（GITT formation protocol, Nature Energy paper 详细方法） | 是（cycle life 可推，capacity 有） | 部分（Li inventory 分析已含容量数据） | 是（voltage vs. capacity per cycle） | feature_schema_test, label_audit, literature_reference_only（如果仅含 formation data） | **P1_cautious_download** | 需 OSF 登录申请访问权限；关注点是 Li inventory tracking 方法论，非 pure cycle life 数据集；如果主要是 GITT formation 数据，cycle life 信息有限；14.8 MB 可能仅含 formation cycle | 1. OSF 数据集是否可直接下载（无需等待申请）？2. 数据是否包含 old cell 的 long cycling 而不只是 formation？3. 数据格式（CSV/XLSX/JSON）？ |
| **REG-005** | Liu/Li/Chen Initially Anode-Free Pouch Cell | Tailored charging protocol for densified lithium deposition and stable initially anode-free lithium metal pouch cells | Liu Y, Yin X, Guo H, Wang S, Li B, Chen G, et al. (Tsinghua / CityU HK / SUSTech) | 2025 | 10.1038/s41467-025-66271-0 | Nature Comms Open Access: https://www.nature.com/articles/s41467-025-66271-0 ; Source Data [待核验] | Nature Source Data (待核验) | anode_free_full_cell | 是 | 是 | **是** | 否 | 否（论文有 cycling 图，无 raw table 公开链接） | 否（[需作者联系]） | 部分（充电协议 middle peak current，SEI 表征） | 是（论文详细描述充电协议比较） | **是**（1.5 Ah pouch cell，80% retention @ 298 cycles） | [待核验] | 否（论文图仅为 capacity retention vs cycle，无 voltage curve） | strategy_optimization_reference, literature_reference_only | **P1_cautious_download** | **重要**：1.5 Ah pouch cell + 298 cycles 是 anode-free 领域中极其罕见的 large-format cycling 数据；但目前论文仅以图形式展示，无 raw cycling table 公开链接；需联系作者获取原始数据 | 1. Nature Comms "Data Availability" 章节是否声明了数据存放位置？2. 原始 cycling data（voltage/current/capacity vs time）是否存放在任何 repository？3. 是否值得联系作者请求 full cycling table？ |
| **REG-006** | Shao/Ma Anode-Free Separator (Figshare) | Multiscale interfacial stabilization via prelithiation separator engineering for Ah-level anode-free lithium batteries | Shao A, Wang H, Zhang M, et al. / Ma Y (Northwestern Polytechnical Univ. / BAK Battery) | 2025 | 10.1038/s41467-025-59521-8 | Figshare: https://springernature.figshare.com/articles/dataset/26893168 | Figshare (Springer Nature) | anode_free_full_cell | 是 | 是 | **是** | 否 | [待核验]（Figshare 标注为 "dataset"，需确认内容） | [待核验]（dataset on Figshare） | [待核验]（需下载后查看） | 是（prelithiation separator engineering） | **是**（1.22 Ah pouch cell，80% retention） | [待核验] | [待核验] | label_audit, strategy_optimization_reference | **P1_cautious_download** | Ah-level anode-free pouch cell；Figshare "dataset" 可能包含 cycling data；需下载后确认是否包含 raw time series | 1. Figshare dataset 26893168 是否包含 per-cycle raw cycling data？2. 数据格式和文件大小？3. 是否明确标注 EOL cycle？ |
| **REG-007** | Wichmann Anode-Free NCOMMS Source Data (Figshare) | Origins of lithium inventory reversibility with an alloying functional layer in anode-free lithium metal batteries | Wichmann L, et al. | 2025 | [待核验]（NCOMMS DOI 待确认） | Figshare: https://figshare.com/articles/dataset/Source_Data_NCOMMS/28597526 | Figshare | anode_free_full_cell | 是 | 是 | **是** | 否 | [待核验]（source data file 含金相层 NMR/cycling） | [待核验]（需下载后查看） | [待核验] | 部分（论文公开） | [待核验] | [待核验] | [待核验] | label_audit, literature_reference_only | **P2_literature_reference** | 标注为 "Source Data" 而非 "cycling dataset"；主要关注 alloying functional layer 的 Li inventory 可逆性分析，可能不包含 long cycling data | 1. Figshare source data 是否包含 multiple cell 的 cycling data？2. cycling 时长和 cell 数量？ |
| **REG-008** | Wichmann Boosted Energy Density AFM 2025 (Figshare) | Boosting the energy density of [anode-free] lithium metal batteries [待核验完整题名] | Wichmann L, et al. | 2025 | [待核验] | Figshare: https://figshare.com/articles/dataset/Source_Data_Advanced_Functional_Materials_2025/30667259 | Figshare | anode_free_full_cell | 是 | 是 | **是** | 否 | [待核验] | [待核验] | [待核验] | [待核验] | [待核验] | [待核验] | [待核验] | literature_reference_only | **P2_literature_reference** | 与 REG-007 为同一作者不同论文；AFM 2025 发表；均为 Source Data，非完整 cycling dataset | 1. 与 REG-007 是否共享同一数据集？2. 数据是否支持 cycle life prediction？ |
| **REG-009** | Mao/Suo/Wang Anode-Free Pouch (PNAS) | Electrolyte design combining fluoro- with cyano-substitution solvents for anode-free Li metal batteries | Mao M, Gong L, Wang X, et al. (HUST / CAS) | 2024 | 10.1073/pnas.2316212121 | PNAS SI: https://www.pnas.org/doi/suppl/10.1073/pnas.2316212121 | Supplementary | anode_free_full_cell | 是 | 是 | **是** | 否 | 否（仅论文图，[需作者联系]） | 否（[需作者联系]） | 是（AN2-DME 电解质，N/P=0，4.25 mAh/cm²，125 mAh pouch） | 是 | **是**（397.5 Wh/kg pouch，76% retention @ 100 cycles） | 是（CE ~98.4% within 100 cycles） | 否 | strategy_optimization_reference, literature_reference_only | **P1_cautious_download**（需联系作者） | Cu\|\|NMC811 pouch cell 极其罕见；论文在 PNAS 上，source data policy 不强制；数据完全不可得，除非联系作者 | 1. 是否有任何 public repository 存放原始 cycling data？2. 值得联系 Suo/Wang 课题组请求数据吗？ |
| **REG-010** | Dutta/Matsuda NIMS MDR Li\|\|NMC Discharge Rate | Optimizing Discharge Rate for Li Metal Stability in Rechargeable Li\|NMC Batteries under Lean Electrolyte Condition | Dutta A, Mizuki E, Tomori Y, Matsuda S (NIMS) | 2024 | 10.1021/acsaem.4c00180 | NIMS MDR [待核验具体 dataset DOI]；ACS Supporting Information | NIMS MDR (待核验) / Supplementary | lmb_full_cell | 是 | 是 | 否 | 否 | 部分（论文有 capacity fade curve，NIMS MDR 可能有 dataset [待核验]） | [待核验] | 是（lean electrolyte，discharge rate 0.4-1.6 mA/cm²） | 是 | 部分（更关注 discharge rate 效应，非 cycle life prediction） | [待核验] | [待核验] | literature_reference_only, strategy_optimization_reference | **P2_literature_reference** | 研究焦点是 discharge rate 对 Li metal 稳定性的影响，不是 dataset paper 或 cycle life prediction；cell 数量可能有限 | 1. NIMS MDR 是否有本论文对应的原始 cycling dataset？2. 如有，是否包含多 cell 比较？ |
| **REG-011** | Chen/Bao/Cui Non-Fluorinated Ether Anode-Free (Chem Sci) | Hyperconjugation-controlled molecular conformation weakens lithium-ion solvation and stabilizes lithium metal anodes | Chen Y, et al. (Stanford: Bao/Cui groups) | 2024 | 10.1039/D4SC05319B | RSC Open Access: https://pubs.rsc.org/en/content/articlehtml/2024/sc/d4sc05319b ; ESI | Supplementary (RSC ESI) | anode_free_full_cell | 是 | 是 | **是** | 否 | 否（论文仅图，ESI Fig. S17 有 cycling 曲线） | 否（[需作者联系]） | 是（LiFSI/DMM, non-fluorinated acetal electrolyte） | 是 | 短（70-100 cycles） | **是**（CE >99% from Li\|\|Cu） | 否 | literature_reference_only | **P2_literature_reference** | Stanford Cui/Bao 组的高质量数据，但 cycling 仅为 70-100 cycles，过短不适合寿命预测；ESI 无 raw table | 1. ESI 是否包含任何 CSV/XLSX 格式的 cycling data？2. 原始数据是否存放在 Stanford Digital Repository？ |
| **REG-012** | Li/Whittingham Iontech-Curated NMC811 Entry | Charge/discharge cycles of Li-LixNi0.8Mn0.1Co0.1O2 (NMC 811) cells | Li M, et al. → curated by Iontech (Liu S) | 2024 | [同 REG-004] | Iontech index: https://github.com/shiyunliu-battery/Iontech#20 (points to same OSF dataset) | GitHub (Iontech curated index) | lmb_full_cell | 是 | 是 | 否 | 否 | [同 REG-004] | [同 REG-004] | [同 REG-004] | [同 REG-004] | [同 REG-004] | [同 REG-004] | [同 REG-004] | [同 REG-004] | **P1_cautious_download** | 这是 REG-004 的 Iontech 索引条目，非独立数据源；Iontech 确认数据为 "Li-LixNi0.8Mn0.1Co0.1O2" 即 Li metal full-cell | 1. 同 REG-004 |

---

## 2. 已知不推荐作为 LMB Full-Cell 训练数据的数据源

| 数据源 | 排除原因 | cell_scope 判定 |
|--------|----------|-----------------|
| Stanford Severson/Attia (2019, Nature Energy) | Li-ion LFP/graphite，非 LMB，graphite anode 非 Li metal | li_ion_method_cell |
| CALCE Battery Dataset (Univ. Maryland) | Li-ion 18650 / pouch，非 LMB | li_ion_method_cell |
| NASA Battery Dataset | Li-ion 18650，非 LMB | li_ion_method_cell |
| Oxford Battery Degradation Dataset | Li-ion 18650，非 LMB | li_ion_method_cell |
| Toyota/MIT-Stanford (batteryarchive.org) | Li-ion LFP/graphite，non-LMB | li_ion_method_cell |
| Iontech 仓库中大部分条目 | Li-ion field data，家用储能系统，Si-graphite/NCA/NCA-GrSi 等 | li_ion_method_cell 或 unknown_scope |
| CH-BatteryGen (CAERI-Huawei) | AI-generated vehicle data，非实验循环数据 | unknown_scope |
| Dryad Quenum microCT dataset (10.6078/D1FM8J) | X-ray CT 图像数据，非电化学 cycling data | lmb_mechanism_test_not_full_cell |
| GitHub Tawheed-tariq NMC_numerical_new.csv | 仅 NMC 材料描述符（元素比例、晶格参数），非电池 cycle data | li_ion_method_cell |

---

## 3. 汇总分析

### 3.1 Top 3 最值得优先核验的数据源

| 排名 | source_id | 核心理由 |
|------|-----------|----------|
| **#1** | **REG-002** (Uppaluri/Onori OSF) | 最大公开 LMB full-cell 数据集 (23 cell, 4 配置)；已有 2+ 篇 ML paper 验证可用性；OSF 直接下载；per-cycle voltage/current/capacity |
| **#2** | **REG-001** (Amanchukwu AL-anode-free) | 唯一可下载的 **anode-free full-cell** 数据集；GitHub + Box 完全可复现；CSV 格式；58+~70 个 labeled data points；Nature Comms 发表，强制性 open data policy |
| **#3** | **REG-003** (Si/Matsuda NIMS MDR) | 唯一带 **EIS 数据** + **已标注 cycle life** 的数据集；NIMS/SoftBank 工业 pouch cell；CC-BY 4.0 license；已有 ML 验证 |

### 3.2 只适合文献启发的数据源

| source_id | 原因 |
|-----------|------|
| REG-005 (Liu/Li/Chen) | 1.5 Ah pouch cell 数据极其珍贵，但无 raw cycling table，仅论文图 |
| REG-009 (Mao/Suo/Wang) | Cu\|\|NMC811 pouch cell + 397.5 Wh/kg 数据罕见，但原始数据未公开 |
| REG-010 (Dutta/Matsuda) | Li\|\|NMC pouch 放电倍率效应，对 strategy optimization 有启发，非寿命预测数据集 |
| REG-011 (Chen/Bao/Cui) | Stanford non-fluorinated ether 工作，cycling 仅 70-100 cycles，过短 |

### 3.3 不推荐作为训练数据的数据源

见第 2 节表格（已知排除项 8 个 + 本项目已有 Li\|\|Li / Li\|\|Cu 机制测试数据）

### 3.4 最缺的 Metadata

基于以上 12 个候选数据源的系统评估，以下 metadata 最可能系统性地缺失：

| 缺失 Metadata | 缺失比例估计 | 影响 |
|---------------|-------------|------|
| **EOL cycle 明确标注** | ~90%（仅 REG-003 有） | 本项目需自行定义 80% capacity retention 阈值，可能引入主观偏差 |
| **Sub-cycle record/step layer data** | ~100%（无一数据源提供） | 无法计算 dQ/dV、ICA/DVA、sub-cycle resistance、ΔV relaxation |
| **Termination reason** | ~100% | 无法区分容量衰减 / 短路 / dendrite / 电解液干涸 |
| **Temperature time series** | ~80%（多数在室温测试） | 无法建模温度依赖性 |
| **EIS Nyquist 原始谱** | ~90%（仅 REG-003 有） | 内阻增长特征不可得 |
| **N/P ratio 精确数字** | ~50%（anode-free 已知 N/P=0，Li\|\|NMC 通常有 excess Li 但未标具体值） | 影响 full-cell degradation 建模参数 |
| **Formation cycle data** | ~70%（仅 REG-004 有 GITT formation） | 缺少 first-cycle efficiency / SEI formation 特征 |

### 3.5 需要用户手动下载或联系作者的数据源

| source_id | 操作类型 | 具体操作 |
|-----------|----------|----------|
| REG-001 | **手动下载** | GitHub clone 仓库；Box 下载 500MB `virtual_search_space_1million.csv` |
| REG-002 | **手动下载** | OSF 下载 .mat 文件 |
| REG-003 | **手动下载** | NIMS MDR 下载 3.78 MB zip |
| REG-004 | **手动下载 + 申请访问** | OSF https://osf.io/2w4k3/（可能需登录申请权限） |
| REG-005 | **联系作者** | 发邮件给 Li B (libh@sz.tsinghua.edu.cn) 或 Chen G 请求 1.5 Ah pouch cycling raw data |
| REG-009 | **联系作者** | 发邮件给 Suo L (suoliumin@iphy.ac.cn) 或 Wang C (clwang@hust.edu.cn) 请求 Cu\|\|NMC811 pouch cycling data |
| REG-007 / REG-008 | **下载后查看** | Figshare 下载 source data 文件，确认是否含 cycling data |

---

## 4. 给 Codex 的审核建议

### 4.1 核验优先级

1. **REG-002 (Uppaluri/Onori)**: 下载并解压 OSF .mat 文件，统计所有 23 cell 的 cycle count、容量衰减到 80% 的 cycle number、电压范围
2. **REG-001 (Amanchukwu)**: 查看 GitHub `datasets/batch-*/*.csv` 每列含义，确认 per-electrolyte 是否有多 cell 重复
3. **REG-003 (Si/Matsuda)**: 解压 NIMS MDR zip 文件，确认数据格式和内容
4. **REG-004 (Li/Whittingham)**: 尝试在 OSF 上注册账号并申请访问
5. **REG-005 / REG-009**: 检查 Nature Comms 和 PNAS 论文的 "Data Availability" 章节是否有 repository 链接
6. **REG-006 / REG-007 / REG-008**: 下载 Figshare 文件确认内容

### 4.2 接入规划建议

- 如 REG-002 确认可用，可作为**首个 LMB full-cell 数据**接入现有 pipeline
- 如 REG-001 确认有 per-cell cycling data，可作为**首个 anode-free full-cell 数据**
- 建议 Codex 产出一份 `data_pipeline/full_cell_intake/` 目录，包含：
  - `parse_uppaluri_osf_fullcell.py`（REG-002）
  - `parse_amanchukwu_github_anodefree.py`（REG-001）
  - `parse_nims_matsuda_fullcell.py`（REG-003）

### 4.3 关键风险

- **所有 12 个候选数据源都缺少 sub-cycle record/step layer**，意味着本项目在 full-cell 上无法使用 sub-cycle-level 特征（如 dQ/dV、step-level resistance）
- **Anode-free raw cycling table 仍然几乎为零**：REG-001 是 per-electrolyte summary，REG-005/REG-009/REG-006/REG-007/REG-008 的数据内容均需进一步确认
- **所有 cell 数量（12-23）远小于 Severson/Attia (124)**，LOCO cross-validation 统计力量受限

---

*本注册表为 Trae 草稿，2026-06-29 生成。所有 cell_scope、dataset_role、intake_priority、training_allowed 判断需要 Codex / 用户后续独立审查。*
