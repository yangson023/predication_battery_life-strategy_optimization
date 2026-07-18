# LMB 数据来源分门别类清单

本文档用于把当前可用、可候选、待确认的数据来源按科研角色分类。它只是一份数据收集与接入清单，不代表已经获得真实 LMB 数据，也不代表任何模型性能。

## 总原则

项目最终研究对象是 Lithium Metal Battery / 锂金属电池。只有经过 metadata 和原始字段核实的数据，才能进入 `true_lmb`。已有 NASA 和外部 Li-ion 数据继续保留方法价值，但不能作为 LMB 科研结论。

数据接入仍按以下顺序：

```text
raw -> tiny validation -> processed -> features -> labels -> audit
```

## 当前数据来源分类

| 来源 | 当前角色 | 推荐存储位置 | 可做什么 | 不能做什么 | 下一步动作 |
| --- | --- | --- | --- | --- | --- |
| 明天 partner 提供的实验室数据 | `unknown`，待核实后可能升级为 `true_lmb` | `E:\battery_research_storage\unknown\raw_dropbox`，确认后迁入 `true_lmb\raw_exports` | 做字段盘点、metadata 核实、tiny validation | 在未确认 LMB 体系前不能训练或下结论 | 等数据到手后检查 cell type、anode_type、CE、voltage/current curve、protocol 和 failure reason |
| 导师/实验室后续正式 LMB 数据 | `true_lmb` 候选 | `E:\battery_research_storage\true_lmb\raw_exports` | 未来支撑 LMB 特征、标签、模型、策略优化 | 缺少 P0 字段时不能直接进入训练 | 优先向导师确认 P0 字段可否导出 |
| NASA battery dataset | `li_ion_method_data` | `E:\battery_research_storage\li_ion_method_data` | pipeline validation、脚本测试、标签流程演练 | 不能表述为 LMB 结论 | 继续冻结为方法验证资产 |
| 当前外部 Li-ion cycle-life 数据 | `li_ion_method_data` | `E:\battery_research_storage\li_ion_method_data` | 低内存 feature builder、标签审计、LOCO 流程演练 | 不能作为 LMB 性能结果 | 只在需要验证工程流程时使用 |
| BatteryLife benchmark | `transfer_auxiliary_data` | `E:\battery_research_storage\transfer_auxiliary_data` | 参考 battery life benchmark、预训练或泛化方法探索 | 不能默认作为 LMB 数据 | 先查化学体系和字段，再决定是否下载 |
| BatteryML | `transfer_auxiliary_data` / 工具参考 | `E:\battery_research_storage\transfer_auxiliary_data` | 学习数据格式、预处理接口、cycler 数据映射思路 | 不能替代 LMB 真实数据 | 作为未来 parser/schema 参考 |
| ABC / MatGD LMB 多模态挖掘论文 | `true_lmb_candidate` / 文献挖掘线索 | `E:\battery_research_storage\true_lmb\notes` 或 `unknown\metadata_recovery` | 参考 LMB 文献数据挖掘、材料-循环性能关系 | 未获得原始表前不能直接训练 | 检查作者是否公开数据库；必要时联系作者 |
| Inactive lithium / dead Li 机理论文 | `diagnostic_only` / 标签机制参考 | `E:\battery_research_storage\diagnostic_only\notes` | 辅助定义 CE、dead Li proxy、Li inventory loss 标签 | 不能直接当寿命训练数据 | 提取机制和标签定义，不急着下载大文件 |
| Dendrite / XCT / segmentation 类数据 | `diagnostic_only` | `E:\battery_research_storage\diagnostic_only` | 软短路、枝晶、形貌诊断参考 | 不能直接进入 cycle-life RUL 训练 | 后续有图像任务时再接入 |
| Cornell 或其他高校 LMB 论文附件 | `unknown` / `diagnostic_only` / `true_lmb_candidate` | 先放 `unknown\metadata_recovery` | 查 supplementary 是否有原始 cycling table | 不能只凭图表截图声称可训练 | 逐篇登记 DOI、字段、是否可下载 |

## 明天实验室数据的接入判断表

收到数据后，先不要跑全量。按下面表格判断用途：

| 检查项 | 通过条件 | 通过后的角色 | 未通过时角色 |
| --- | --- | --- | --- |
| 是否明确是 LMB 体系 | cell type 或导师说明确认 Li metal / anode-free / Li\|\|Cu / Li\|\|full cell | `true_lmb` 候选 | `unknown` |
| 是否有 cell_id | 每个 cell 可独立追踪 | 可做 LOCO / 按 cell 标签 | 只能做格式检查 |
| 是否有 charge/discharge capacity | 可计算 CE、容量保持率、不可逆容量 | 可做核心 LMB 特征 | 只能做诊断或曲线分析 |
| 是否有 voltage-time/current-time | 可提取过电位、滞后、极化、软短路信号 | 可做 LMB-specific 特征 | 标签会偏弱 |
| 是否有 cycle_index/step_index/state | 可分离 charge/discharge/rest | 可做稳定特征工程 | 需要先做 schema recovery |
| 是否有 areal capacity/current density | 可做 LMB 协议归一化 | 可跨实验条件比较 | 不适合跨协议结论 |
| 是否有 electrolyte/additive/separator | 可解释 CE 和界面差异 | 可做材料变量 | 只能做黑箱寿命流程 |
| 是否有 failure_mode/stopping_reason | 可判断 observed/censored 标签 | 可做更可靠标签 | 只能做删失或弱标签 |

## 公开数据收集优先级

| 优先级 | 类型 | 说明 |
| --- | --- | --- |
| P0 | 实验室真实 LMB cycler 导出 | 最适合本项目，优先级最高 |
| P1 | 公开 LMB 原始 cycling table | 必须有 CE 或可由 charge/discharge capacity 计算 |
| P1 | LMB 文献挖掘数据库 | 适合构建材料-性能表，但要确认是否有原始数据 |
| P2 | BatteryLife / BatteryML 等综合数据集 | 适合方法验证、迁移辅助、schema 学习 |
| P2 | EIS / XCT / thermal / abuse 数据 | 适合诊断和机理，不直接训练 RUL |
| P3 | 只有论文图的 LMB 文章 | 可人工登记，暂不作为主数据源 |

## 公开来源登记建议

每个公开来源只先登记以下信息，不急着下载：

```text
source_name:
url_or_doi:
current_role: true_lmb_candidate / transfer_auxiliary_data / diagnostic_only / unknown
is_direct_download_available: yes / no / unclear
has_raw_cycling_table: yes / no / unclear
has_charge_capacity: yes / no / unclear
has_discharge_capacity: yes / no / unclear
has_ce: yes / no / calculated / unclear
has_voltage_current_curve: yes / no / unclear
has_lmb_metadata: yes / no / unclear
recommended_storage:
decision: download / contact_author / literature_only / skip_for_now
```

可以使用本项目的轻量登记脚本生成模板和审计报告：

```powershell
python modules\data_pipeline\lmb_literature_data_registry.py `
  --init-template outputs\lmb_literature_registry\lmb_literature_registry_template.csv

python modules\data_pipeline\lmb_literature_data_registry.py `
  --input outputs\lmb_literature_registry\lmb_literature_registry_template.csv `
  --output-root outputs\lmb_literature_registry
```

该脚本只做来源登记、角色建议、字段完整性评分和 tiny validation 候选筛选。它不会自动下载论文、不会处理原始数据、不会训练模型。

## 已确认的边界

- Li-ion 数据仍有价值，但只是方法验证数据。
- 公开 LMB 论文如果只给图，不等于可训练数据。
- 真实实验室数据到手后，第一步是 intake 和 tiny validation，不是训练模型。
- RPT、EIS、XCT、thermal 等数据在没有 cycle/protocol alignment 前，默认是 `diagnostic_only`。
- `unknown` 数据不能进入训练，不能写入 LMB 结论。

## 近期行动

1. 明天收到 partner 数据后，先复制到 `E:\battery_research_storage\unknown\raw_dropbox` 或按导师确认直接放入 `true_lmb\raw_exports`。
2. 使用本文件的接入判断表做字段审计。
3. 只抽一个 cell 或一个文件做 tiny validation。
4. 通过 tiny validation 后，再决定是否写 LMB parser / feature builder。
5. 公开数据源先做登记表，不批量下载。
