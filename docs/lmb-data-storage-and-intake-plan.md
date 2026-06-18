# LMB 数据存储结构与接入规划

本文档用于规范锂金属电池（Lithium Metal Battery, LMB）方向校准后的数据存储结构和接入流程。它只是一份规划文档，不创建目录、不移动文件、不处理大数据、不训练模型。

## 核心原则

真正用于支撑 LMB 科研结论的数据，必须和已有 Li-ion 方法验证数据分开存放、分开表述、分开审计。

当前已迁移到移动硬盘的 Li-ion 方法验证数据保留在：

```text
E:\battery_research_storage\li_ion_method_data
```

这些数据仍然有价值，但用途是 pipeline validation / method development。不能把基于这些 Li-ion 数据得到的标签审计、特征工程或 exploratory baseline 结果表述为 LMB 科研结论。

## 推荐 E 盘目录结构

推荐总根目录：

```text
E:\battery_research_storage
```

推荐结构：

```text
E:\battery_research_storage\
  true_lmb\
    raw_archives\
    raw_exports\
    processed_cache\
    features\
    label_audit\
    manifests\
    notes\
    figures\
  li_ion_method_data\
    raw_archives\
    processed_cache\
    features\
    label_audit\
    migration_logs\
  transfer_auxiliary_data\
    raw_archives\
    processed_cache\
    features\
    label_audit\
    manifests\
    notes\
  diagnostic_only\
    eis\
    dcir\
    rpt\
    thermal_or_abuse\
    pressure_temperature\
    manifests\
    notes\
  unknown\
    raw_dropbox\
    metadata_recovery\
    notes\
```

不建议把真实 LMB 数据混入 `li_ion_method_data`，也不建议把来源不清楚的数据直接放进 `true_lmb`。

## 数据角色

| 目录 | dataset_role | 定义 | 允许用途 | 禁止用途 |
| --- | --- | --- | --- | --- |
| `true_lmb` | `true_lmb` | 已确认是锂金属电池、锂负极、无负极、Li\|\|Cu、Li\|\|NMC、Li-S 等与 LMB 机制直接相关的数据 | 支撑 LMB 特征、标签、模型和论文结论 | 在元数据不足时直接训练或声称可靠结论 |
| `li_ion_method_data` | `li_ion_method_data` | NASA 和当前外部 Li-ion cycle-life 数据 | 验证数据管线、特征工程、标签审计、模型流程 | 作为 LMB 科研结论 |
| `transfer_auxiliary_data` | `transfer_auxiliary_data` | 明确设计为迁移学习、预训练、方法对照的辅助数据 | 预训练、表征学习、泛化方法探索 | 未标注角色时混入主 LMB 训练或结论 |
| `diagnostic_only` | `diagnostic_only` | EIS、DCIR、RPT、热失控、压力、温度、滥用测试等诊断数据 | 机理解释、质量审计、辅助分析 | 在没有 protocol alignment 时直接作为训练标签 |
| `unknown` | `unknown` | 化学体系、cell design、来源或字段含义不清的数据 | 暂存、追溯元数据、等待导师确认 | 训练、建模结论、LMB 结论 |

## 标准数据处理顺序

以后任何新数据都按以下顺序推进：

```text
raw -> tiny validation -> processed -> features -> labels -> audit
```

| 阶段 | 目标 | 门禁 |
| --- | --- | --- |
| raw | 保存原始导出文件、实验说明和来源信息 | 原始文件只读保存，不直接改 |
| tiny validation | 只取极小样本验证解析器、字段、schema | 通过后才能全量处理 |
| processed | 生成规范化中间表 | 必须有 manifest，记录输入、输出、失败项 |
| features | 生成 cycle、diagnostic 或 LMB-specific 特征 | 必须有 schema check |
| labels | 生成健康、失效、删失标签 | 必须定义 censoring、trainability、protocol boundary |
| audit | 判断标签是否能进入训练 | 必须区分 trainable 和 audit-only |

新格式 LMB 数据不能跳过 tiny validation。这个规则是为了省磁盘、省额度，也为了避免一次性跑错大数据。

## 导师实验数据接入模板

导师或实验室给数据时，先用下面模板做 intake，不急着写解析器。

```text
dataset_name:
dataset_role: true_lmb / li_ion_method_data / transfer_auxiliary_data / diagnostic_only / unknown
source_person:
date_received:
storage_path:
raw_file_format: csv / xlsx / mat / json / ndaq / database / other
data_export_method: direct export / API / GUI export / manual / unknown

cell_id_available: yes / no / unknown
cell_type:
anode_type:
anode_free_status: source field / derived / unavailable
cathode_type:
electrolyte:
additive:
separator:
areal_capacity_mah_cm2:
current_density_ma_cm2:
np_ratio:
pressure:
temperature:
formation_protocol:
cycling_protocol:
failure_mode:
stopping_reason:

charge_capacity_available: yes / no / unknown
discharge_capacity_available: yes / no / unknown
ce_available: direct / calculated / unavailable / unknown
voltage_time_curve_available: yes / no / unknown
current_time_curve_available: yes / no / unknown
cycle_index_available: yes / no / unknown
step_index_available: yes / no / unknown
state_labels_available: yes / no / unknown
rest_voltage_available: yes / no / unknown
eis_or_dcir_available: yes / no / unknown
pressure_trace_available: yes / no / unknown
temperature_trace_available: yes / no / unknown

known_limitations:
confidentiality_or_license:
initial_intake_decision: accept / needs metadata / diagnostic only / reject for now
```

## 公开 LMB 数据源登记模板

检索公开数据时，先登记，不要一看到大文件就下载。

```text
source_name:
url_or_doi:
access_type: direct download / supplementary data / request author / paper only / unknown
dataset_role_candidate: true_lmb / transfer_auxiliary_data / diagnostic_only / unknown
battery_type:
cell_format:
available_raw_fields:
available_metadata:
available_labels:
file_formats:
license_or_terms:
download_status: not checked / downloaded / request needed / unavailable
storage_path:
notes:
decision:
```

只有确认 cell type 和关键元数据后，公开数据源才能从 `unknown` 或 `transfer_auxiliary_data` 提升为 `true_lmb` 候选。

## 下一步优先询问或下载的字段

P0 字段优先级最高，没有这些字段就不建议进入正式 LMB 标签或训练设计。

| 优先级 | 字段 | 作用 |
| --- | --- | --- |
| P0 | `cell_id` | 分组、按 cell 验证、避免随机行划分 |
| P0 | `cell_type` | 判断是否能支撑 LMB 结论 |
| P0 | `anode_type` | 判断 Li metal、anode-free、Li\|\|Cu 等体系 |
| P0 | `charge_capacity` | 计算 CE、不可逆容量、锂库存损失代理特征 |
| P0 | `discharge_capacity` | 容量保持率和 capacity EOL 标签 |
| P0 | voltage-time curve | 电压滞后、过电位、软短路预警 |
| P0 | current-time curve | 识别工步、协议、倍率和电流密度 |
| P0 | `cycle_index` | 寿命序列和标签时间定位 |
| P0 | `step_index` 或 state labels | 区分 charge / discharge / rest |
| P0 | `areal_capacity_mah_cm2` | LMB 面容量归一化 |
| P0 | `current_density_ma_cm2` | 协议可比性和电流密度归一化 |
| P0 | `np_ratio` | 判断无负极、贫锂或锂过量条件 |
| P0 | electrolyte / additive / separator | 解释 CE 和界面稳定性 |
| P0 | `formation_protocol` 和 `cycling_protocol` | 处理 protocol censoring 和 protocol boundary |
| P0 | `failure_mode` 或 stopping reason | 判断标签是否可信 |

P1 字段包括 EIS/DCIR、压力、温度、静置电压、异常事件日志、post-mortem notes。这些字段很重要，但在没有对齐到 cycle/protocol regime 前，默认先进入 `diagnostic_only` 或辅助审计。

## 命名规范

推荐数据集目录命名：

```text
YYYYMMDD_source_shortname_role
```

示例：

```text
20260616_advisor_batch01_true_lmb
20260616_paper_authorname_true_lmb_candidate
20260616_public_li_s_transfer_auxiliary
```

尽量使用小写英文、数字和下划线，方便脚本处理。

## Manifest 规范

每个数据集目录后续应尽量包含：

```text
dataset_manifest.json
data_intake_notes.md
```

manifest 至少记录：

- dataset name
- dataset role
- source
- received date
- raw file list
- checksum 或文件大小
- available fields
- missing P0 fields
- permission 或 license notes
- current processing status

## 明确不要做的事

- 不要把真实 LMB 数据放到 `li_ion_method_data`。
- 不要用 Li-ion 方法数据声称 LMB 模型性能。
- 不要跳过 tiny validation 直接跑全量。
- 不要在没有 protocol alignment 时把 diagnostic-only 数据当训练标签。
- 不要处理后删除原始 raw 文件。
- 不要把保密实验室数据和公开数据混在同一目录而不做说明。

## 立即行动建议

1. 等真实 LMB 数据到手或你明确要求时，再创建 E 盘实际目录。
2. 把 P0 字段清单发给导师或实验室，先确认常规导出能给哪些字段。
3. 建一个公开 LMB 数据源清单，先登记 DOI、字段、许可和是否可下载，再决定是否下载。
4. 第一批真实 LMB 数据只做 intake review 和 tiny validation，不直接训练模型。
