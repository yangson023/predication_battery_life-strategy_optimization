# BTSDA LMB 三层数据接入说明

本文档记录 BTSDA 导出的 cycle / step / record 三层 CSV 在本项目中的接入规则。当前内容只用于 parser、schema 和 data-quality audit，不代表模型训练结果，也不能表述为寿命预测性能。

## 当前定位

项目最终研究对象是 Lithium Metal Battery / 锂金属电池。BTSDA 导出的实验室数据属于 `true_lmb` 候选数据，但在进入训练前必须完成以下门禁：

```text
raw export -> tiny validation -> small-batch intake -> feature schema -> label policy -> label audit -> model gate
```

本阶段只完成 `tiny validation`。禁止跳过门禁直接训练。

## 三层结构

| 层级 | 主要用途 | 当前处理方式 |
| --- | --- | --- |
| cycle 层 | 每循环容量、库伦效率、容量保持率、中值电压 | 标准化为 `normalized_cycle.csv` |
| step 层 | 每个循环内的充电、放电、搁置工步信息 | 标准化为 `normalized_step.csv` |
| record 层 | 逐点电流、电压、时间、容量、功率 | 当前只输出采样文件 `normalized_record_sample.csv` |

record 层通常最大，当前 parser 不默认写出完整 record，以避免在 tiny validation 阶段浪费磁盘和内存。

## Parser

脚本路径：

```text
modules/data_pipeline/parse_btsda_lmb_three_layer_export.py
```

支持参数：

```text
--input-root
--output-root
--dataset-name
--cell-type
--encoding
--overwrite
--record-sample-rows
```

关键设计：

- 默认支持 GBK 编码。
- 自动识别 cycle / step / record CSV。
- 当同一目录存在多个同层 CSV 时，优先选择必需字段匹配完整且文件更大的候选。
- 当同一目录存在多个完整导出批次，例如 `data_cycle-4.csv` / `data_cycle-5.csv`，优先选择同一后缀批次；若多个批次都完整，优先选择 cycle 行数更多的批次。
- 标准化三层字段名。
- 只采样输出 record 层。
- 永远输出 `training_allowed_now=false`。

## 输出文件

每个 tiny validation 数据集至少输出：

```text
normalized_cycle.csv
normalized_step.csv
normalized_record_sample.csv
schema_check.csv
quality_flags.csv
intake_schema_report.json
intake_schema_report.md
```

其中 `schema_check.csv` 用于判断字段、层级、三层差异和 cycle 对齐是否通过；`quality_flags.csv` 用于记录 CE 异常、容量不完整、record 电压极值等审计信号。

## 当前 tiny validation 结果

| dataset_name | cell_type | cycle rows | step rows | record rows | record sample | schema gate | record 可用 | 采样间隔众数 | training_allowed_now |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- | ---: | --- |
| `yaosicheng_26_0414_lili` | Li\|\|Li symmetric | 403 | 807 | 98613 | 5000 | pass | yes | 30 s | false |
| `yaosicheng_26_0428_009_unknown` | unknown LMB BTSDA export; needs lab confirmation | 110 | 220 | 26379 | 5000 | pass | yes | 30 s | false |
| `yaosicheng_26_0428_085_licu` | Li\|\|Cu CE half-cell | 299 | 598 | 58162 | 5000 | pass | yes | 30 s | false |

工步类型均能识别为搁置、恒流充电、恒流放电。两组数据的 cycle index 在 cycle / step / record 三层之间可以对齐。

## Li||Li 与 Li||Cu 的不同用途

Li||Li symmetric cell 更适合做：

- polarization growth
- voltage hysteresis
- plating / stripping overpotential
- voltage instability
- soft-short warning 的早期信号审计

Li||Cu CE half-cell 更适合做：

- Coulombic efficiency
- CE trend / variance / drop
- plating / stripping efficiency
- incomplete-cycle filtering
- irreversible lithium loss proxy

两类数据不能混为同一个训练任务。后续应分别定义特征、标签和门禁，再考虑是否做多任务或迁移学习。

## 当前禁止事项

- 禁止训练模型。
- 禁止进入 `rul-prediction`。
- 禁止把 tiny validation 结果称为模型性能。
- 禁止把 Li||Li 和 Li||Cu 混为同一标签任务。
- 禁止随机 row split。
- 禁止直接处理全量 37 个 NDAX 导出结果。

## 下一步门禁

允许进入下一步：3 个 Li||Li + 3 个 Li||Cu 的小批量接入。

小批量接入必须满足：

1. 每个 cell 都有 cycle / step / record 三层导出。
2. 每个 cell 的 `schema gate` 通过。
3. record 层必须有电压、电流、时间。
4. Li||Li 与 Li||Cu 分开输出和审计。
5. 只生成 intake audit，不训练模型。
6. 若某个 cell 缺字段或层级不完整，标记为 fail，不要人工补造数据。

通过 6-cell 小批量接入后，才能设计真正的 LMB feature builder 和 label policy。

## Canonical Export Audit

After batch-level tiny validation, the project must choose exactly one
canonical export for each independent source folder before feature and label
work. Alternate exports are retained for audit, deduplication, parser
regression, low-cycle checks, and quality-control edge cases, but they must not
be counted as independent cells.

Current canonical audit output:

```text
outputs/lmb_lab_intake/lmb_canonical_export_audit_20260618
```

Generated files:

```text
canonical_export_manifest.csv
alternate_export_manifest.csv
canonical_export_audit_report.json
canonical_export_audit_report.md
```

Selection rules:

1. Select only one canonical export per `source_folder_name`.
2. Require `schema_gate_passed=True`.
3. Require `record_layer_available=True`.
4. Require `record_has_voltage_current_time=True`.
5. Prefer the highest `cycle_rows`.
6. If cycle windows are tied or near-duplicates, prefer lower
   `quality_flag_count`; if still tied, prefer the earliest export suffix for
   traceability.
7. High `quality_flag_count` does not automatically discard an export, but it
   blocks training until a flag-type audit explains the issue.

Current gate decision:

- Feature/label design is allowed because the audited set contains at least
  three Li||Li candidate cells and at least three Li||Cu candidate cells.
- Model training remains disallowed until quality-flag audit, label definition,
  observed/censored separation, and trainable-label audit are complete.

## Quality Flag Audit

Before any feature builder or label builder is treated as trainable, canonical
exports must pass a quality flag type audit. This audit reads only existing
tiny-validation outputs and does not rerun raw data parsing.

Current quality flag audit output:

```text
outputs/lmb_lab_intake/lmb_quality_flag_audit_20260618
```

Generated files:

```text
quality_flag_type_summary.csv
cycle_quality_manifest.csv
per_cell_quality_summary.csv
quality_flag_audit_report.json
quality_flag_audit_report.md
```

Recognized flag types:

- `ce_above_103_percent`
- `ce_below_80_percent`
- `incomplete_charge_capacity`
- `incomplete_discharge_capacity`
- `incomplete_charge_or_discharge_capacity`
- `record_voltage_extreme`
- `unknown_flag_type`

Interpretation rules:

1. Li||Cu high CE flags are not automatically bad data. They may represent
   measurement overshoot, CE instability, or real lithium depletion.
2. Incomplete capacity is an audit and label-design signal. It should be
   separated from parser failure and generic data quality failure.
3. `record_voltage_extreme` is record-row based, so a high row count does not
   equal the same number of bad cycles. It requires LMB-specific voltage
   threshold review.
4. Li||Li cells may show few current flags because their degradation is mainly
   voltage-domain behavior. Low flag count does not prove no degradation.

Current gate decision:

- Feature builder may proceed with caution.
- Li||Cu label training remains blocked until incomplete-cycle handling,
  CE-label leakage prevention, and trainable-label audit are complete.
- Model training remains prohibited.

## Canonical Feature Builder

After canonical export audit and quality flag audit, the project may generate
task-separated feature tables. Feature generation is not label generation and
is not model training.

Current feature output:

```text
data/features/lmb_lab/canonical_features_20260618
```

Generated files:

```text
lili_cycle_features.csv
licu_cycle_features.csv
lmb_feature_build_report.json
lmb_feature_build_report.md
feature_schema_check.csv
```

Feature builder script:

```text
modules/feature_engineering/build_lmb_canonical_features.py
```

Rules:

1. Read only canonical exports listed in `canonical_export_manifest.csv`.
2. Do not read alternate exports as feature inputs.
3. Keep Li||Li and Li||Cu in separate feature tables.
4. Do not create labels, EOL, RUL, targets, or random splits.
5. Rolling features must be past-only.
6. Li||Cu CE-derived columns are label-proximal and require leakage controls
   during later label policy design.
7. Record-derived features are sample-limited because they come from
   `normalized_record_sample.csv`, not full record exports.

Current gate decision:

- Label policy design is allowed.
- Model training remains prohibited until label definitions, censoring rules,
  leakage checks, and trainable-label audit pass.

## Label Policy

The first formal LMB label policy is documented in:

```text
docs/lmb-label-policy.md
```

This stage converts the feature and quality-audit evidence into rules for a
future label builder. It still does not create training labels and does not
allow model training.

Policy decisions:

1. Li||Cu and Li||Li must remain separate label tasks.
2. Li||Cu labels may begin with audit-only scans for
   `incomplete_capacity_event`, `ce_collapse`, `ce_instability`,
   `ce_sustained_degradation`, `lithium_inventory_loss_proxy`, and
   `protocol_censored`.
3. Li||Li labels remain voltage-domain and audit-first:
   `polarization_growth`, `voltage_hysteresis_failure`,
   `voltage_instability`, `soft_short_warning`,
   `incomplete_cycle_warning`, and `protocol_censored`.
4. CE-based labels must be future-window labels. Current-cycle CE cannot be
   used as both a feature and the label decision for the same row.
5. Feature builder, label builder, trainability audit, and baseline-ready
   export must remain separate stages.

Current gate decision:

- `label_builder_allowed = True`
- `model_training_allowed = False`
- The next implementation may create an audit-only label scan, but it must not
  emit baseline-ready training labels until censoring, leakage, and
  trainability checks pass.

## Audit-Only Label Scan

The first label scan is implemented as an audit-only stage:

```text
modules/feature_engineering/scan_lmb_audit_only_labels.py
```

Current output:

```text
outputs/lmb_lab_intake/lmb_audit_label_scan_20260618
```

Generated files:

```text
lmb_audit_event_scan.csv
per_cell_audit_label_summary.csv
audit_label_schema_check.csv
lmb_audit_label_scan_report.json
lmb_audit_label_scan_report.md
```

Current scan summary:

- Audit scan rows: 6993
- Per-cell summary rows: 38
- Li||Cu scan rows: 2940
- Li||Li scan rows: 4053
- `trainable_label` is always false.
- `baseline_ready_labels_exported` is false.

Observed candidate counts:

| label key | count |
| --- | ---: |
| `incomplete_capacity_event` | 357 |
| `ce_instability` | 677 |
| `ce_collapse` | 20 |
| `polarization_growth` | 103 |
| `voltage_hysteresis_failure` | 123 |
| `voltage_instability` | 69 |
| `incomplete_cycle_warning` | 3 |

Interpretation:

1. Li||Cu `incomplete_capacity_event` and terminal `ce_collapse` are the most
   useful first review targets.
2. Li||Cu `ce_instability` is frequent and likely threshold-sensitive, so it
   needs threshold review before trainability audit.
3. Li||Li `26-0414` has the clearest polarization and hysteresis candidates.
4. Li||Li trainable labels remain blocked until voltage-domain events are
   manually reviewed and censoring is defined.

Current gate decision:

- `label_builder_allowed = True`
- `trainability_audit_allowed = True`
- `model_training_allowed = False`
