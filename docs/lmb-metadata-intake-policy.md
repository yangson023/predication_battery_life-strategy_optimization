# LMB Metadata Intake Policy

This document defines how partner-provided lithium metal battery metadata is
checked before label trainability audit.

## Scope

The metadata gate only checks structured experiment metadata. It does not read
raw BTSDA data, build labels, train models, or report model performance.

Current template:

```text
outputs/lmb_partner_metadata_template/lmb_experiment_metadata_template_cn.xlsx
```

Current validator:

```text
modules/data_pipeline/validate_lmb_metadata_template.py
```

## Required Input

The validator reads only the Excel sheet named:

```text
填写模板
```

One row should represent one independent cell. Alternate exports, handwritten
notes, photos, or chat messages must not be treated as structured metadata
until the information is copied into the template.

## P0 Fields

P0 fields are required before a cell can enter label trainability audit:

- 电池编号
- 电池类型
- 原始数据文件夹
- 实验日期
- 正负极体系
- 电解液溶剂
- 锂盐
- 锂盐浓度
- 电解液添加剂
- 隔膜材料/型号
- 电流密度(mA/cm²)
- 面容量(mAh/cm²)
- 循环协议
- 截止条件
- 终止原因
- 失效模式/现象

If any P0 field is missing, the cell receives:

```text
metadata_blocked_missing_p0
```

## P1 Fields

P1 fields are strongly recommended and should be filled before robust model
planning:

- 实验批次
- 操作者
- 测试设备/通道
- 负极/基底材料
- 锂片厚度(μm)
- 铜箔/基底信息
- 电池壳类型
- 电解液用量(μL)
- 电极面积(cm²)
- 压力条件
- 测试温度(℃)
- 化成协议
- 静置时间
- 是否协议变化
- 是否异常实验
- 保密/公开级别

If P0 is complete but P1 is incomplete, the cell receives:

```text
metadata_partial_needs_review
```

## Cell Type Gate

Allowed structured values are:

- Li||Li 对称电池
- Li||Cu 半电池
- Li||全电池
- Anode-free 全电池
- 其他
- 未知

Unknown or unsupported values receive:

```text
metadata_unknown_cell_type
```

## Termination Reason Gate

Termination reason is needed to separate observed, censored, and
protocol-censored cells.

Initial interpretation:

| 终止原因 | interpretation |
| --- | --- |
| 自然失效 | observed_candidate |
| 短路 | observed_candidate |
| 人为停止 | protocol_censored |
| 设备中断 | protocol_censored |
| 协议结束 | protocol_censored |
| 数据导出不完整 | protocol_censored |
| 未记录 | unknown |

Manual review is still required before any label is declared trainable.

## Gate Status

| status | meaning |
| --- | --- |
| `metadata_ready_for_label_audit` | P0 and P1 are complete enough for label audit review. |
| `metadata_partial_needs_review` | P0 is usable, but P1 or termination details need review. |
| `metadata_blocked_missing_p0` | Critical P0 fields are missing. |
| `metadata_unknown_cell_type` | Cell type is unknown or not recognized. |

## Current Rule

Metadata validation can allow later label audit planning, but it never allows
model training by itself.

```text
training_allowed_now = False
model_training_allowed = False
```

## Partner Note Handling

Handwritten notes are useful as evidence, but they must be transcribed into the
Excel template before they can pass project gates. If the handwriting is
unclear, use `未知` or add a note in `备注` rather than guessing.
