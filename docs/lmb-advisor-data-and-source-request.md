# LMB Full-Cell Data and Source Request

## Purpose

This is a concise request brief for the advisor. The project currently has six
true-LMB NCM811||Li full-cell exports with complete BTSDA three-layer intake,
protocol reconstruction, and early-cycle feature auditing. All six tests ended
because the planned cycle count was reached, so they are **protocol-censored
controls**, not observed full-cell failure events.

The present bottleneck is not model complexity. It is the lack of independent,
well-documented full-cell failure events needed to define and audit a warning or
lifetime label correctly.

## What Would Help Most

### P0: Existing laboratory full-cell records

Please prioritize any historical or upcoming LMB full-cell experiment that ended
for a reason other than merely reaching its planned cycle count. Useful examples
include a confirmed capacity decline, voltage instability, soft-short/safety stop,
unexpected test termination, or a manually documented abnormal event. Early
failure is useful too; it should not be discarded simply because it has few cycles.

For every independent cell, please retain or export:

1. BTSDA cycle, step, and record layers, plus the corresponding step/protocol XML.
2. `cell_id`, date/batch, full-cell chemistry and cell configuration.
3. Cathode material/loading/diameter, lithium foil thickness, electrolyte code
   and shareable detail, separator, electrolyte volume, N/P ratio, pressure and
   temperature.
4. Formation and cycling protocol, current density, areal capacity, voltage
   cutoffs, planned long-cycle count, and rest steps.
5. Termination reason. For a non-planned stop, also record the first event cycle,
   failure mode, and a traceable evidence location such as a notebook page,
   BTSDA screenshot, or test log.

Initial practical target: **3--5 independent observed failure/abnormal-termination
cells**, retained together with at least **3 protocol-censored no-event controls**.
This is a gate for label audit and tiny method development, not a promise of a
formal model result. A stronger study will need more independent cells and events.

### P1: Reliable public or collaborator data sources

We would appreciate recommendations for data that are clearly one of these:

- `lmb_full_cell`: e.g. NMC||Li full cell with per-cell cycling tables;
- `anode_free_full_cell`: e.g. Cu||LFP/NMC with cycling tables;
- explicitly documented mechanism data, retained only for feature/schema work.

The useful minimum is a per-cell cycling table with cycle index, charge/discharge
capacity, voltage limits/protocol, and a clear end-of-test reason. Voltage/current
time series, EIS, pressure, and full metadata improve feature development but are
not prerequisites for initial intake. Graph-only supplementary data can inform
feature ideas but cannot enter the model data pipeline.

Current project references worth checking with the advisor are listed in:

- `docs/lmb-public-full-cell-data-source-audit.md`
- `docs/lmb-full-cell-public-data-registry.md`
- `docs/lmb-full-cell-reg-002-semantic-review.md`

They are candidate sources, not automatically validated final training data.

## Ready-to-Send Message

老师您好，我们目前已完成 6 组 NCM811||Li 全电池 BTSDA 数据的三层接入、工步配对和前 20 圈机制特征审计。这 6 组均是达到预设循环数后结束，因此应作为 protocol-censored 对照，不能误当作自然失效样本。项目下一步最缺的是几组终止原因明确的全电池数据，例如容量异常衰减、电压不稳定、软短路/安全停止或其他非计划终止；即使循环数不长也很有价值。若实验室有此类历史数据或后续实验，能否允许我们保留 cycle/step/record 三层导出、对应工步 XML、终止原因/首次异常圈数，以及电流密度、面容量、N/P、正极负载、压力温度和电解液编号等元数据？另外若老师知道有带逐电池循环表和协议说明的 LMB full-cell 或 anode-free full-cell 公开数据集/合作数据源，也希望您能推荐。我们会先做数据接入、标签审计和留一电芯验证，不会把当前小样本结果表述为正式模型性能。

## Boundaries

- Li||Li and Li||Cu mechanism cells are not full-cell training evidence.
- Ordinary Li-ion datasets remain method-development data only.
- No data source enters training directly: intake, metadata, label, censoring, and
  trainability gates must all pass first.
- `model_training_allowed=False` for the present six-cell full-cell batch.
