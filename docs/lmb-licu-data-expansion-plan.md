# LMB Li||Cu Data Expansion Plan

This is a data expansion plan based on qualitative smoke-test diagnostics. It is not a formal model result.

## 当前缺口

- 当前 Li||Cu candidate cell 数：3
- 当前 positive target 数：3
- 每个 LOCO fold train positive：2
- 当前标签：`incomplete_capacity_event`，不是 full lifetime EOL。
- 当前 terminal 情况：mostly protocol-censored。
- 当前更值得保留的 horizon：`horizon_5`，但仍是 small-n 判断。
- 当前实验室数据 scope 标签：`lmb_mechanism_test_not_full_cell`。
- 当前 Li||Li / Li||Cu 是否为 full cell：`False`。
- 当前 Li||Li / Li||Cu 只能作为 LMB 机制测试数据，不能作为全电池寿命/RUL/EOL 证据。

## 下一批 Li||Cu 数据目标

- 最低目标：新增 5-8 个 Li||Cu cell。
- 较好目标：总 Li||Cu cell >= 10-12。
- 每类重点事件至少 3 个 cell。
- 至少 3 个 no-event / protocol-censored control cell。
- 至少 2-3 个自然失效或明确异常终止 cell。
- 每个 cell 尽量 >= 80-100 cycles；early failure 保留但先标记为 audit-only。

## 为什么需要 control 和自然终止

- no-event control 可以检查模型是否把所有后期循环都误判为风险。
- 自然失效或明确异常终止 cell 可以帮助区分 observed event 与 protocol-censored 终点。
- 当前 protocol-censored 终点不能被当作自然失效。

## Li||Cu / Li||Li 用途区分

- Li||Cu：优先用于 incomplete capacity、CE collapse、sustained CE degradation 等 warning proxy。
- Li||Li：优先用于 polarization growth、voltage instability、possible soft-short audit。
- 两类数据不能混在一起训练；只能在文档层面对机制进行互相参考。

## 给 partner 的说明

我们现在不是想要“越多越好”的乱数据，而是优先需要事件明确、协议清楚、元数据清楚的 Li||Cu 数据。少量高质量数据比大量来源不清的数据更有用。尤其希望每个 cell 都能说明循环协议、电流密度、面容量、终止原因、异常记录，并尽量同时提供 cycle/step/record 三层导出。Li||Cu 主要用于 CE/容量异常和 incomplete capacity warning；Li||Li 主要用于极化、电压不稳定和 soft-short 审计，二者后续不能混在一起训练。

## 给导师的说明

当前项目已完成从 BTSDA 三层数据接入、LMB canonical feature、label policy、mechanistic horizon feature 到 qualitative smoke-test diagnostics 的闭环。诊断显示机制特征比 record-sample-only 特征更值得继续，但现阶段受 small-n 限制：只有 3 个 Li||Cu candidate cell、3 个 positive target，每个 LOCO fold 的 train positive 只有 2。因此下一阶段核心不是盲目更换模型，而是有设计地补充 Li||Cu 事件 cell 与 no-event control cell，用于验证 incomplete_capacity_event warning proxy 以及 CE/电压/动力学机制特征的可复现性。

## 门禁结论

- `model_training_allowed = False`
- 新数据必须先通过 intake、metadata、label scan、trainability audit、baseline-ready export，再考虑 tiny smoke-test。
- 当前最佳动作是数据设计与补充，不是盲目换复杂模型。
