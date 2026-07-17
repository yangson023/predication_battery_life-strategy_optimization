# LMB Full-Cell 终止语义审计

## 原则

full-cell 导出末端出现未配对充电工步，不能自动等同于自然失效、容量 EOL 或 protocol-censored。必须结合实验日志确认终止原因与计划循环数。

## 受控解释

- `natural_failure`、`confirmed_failure`、`safety_stop`、`soft_short`：仅可成为 observed failure 的候选，仍需失效记录佐证。
- `planned_cycle_count_reached`：partner/实验记录确认后，记为 protocol-censored；删失时刻是最后一个完整的 long-cycle 配对。计划循环数的具体数值仍需保留，以便复核导出范围。
- `equipment_fault`、`data_export_interrupted`、`operator_stop`：行政/设备中断，需要人工复核。
- `unknown`：`unresolved_termination_reason`，阻断 label trainability。

## 当前门禁

该审计不创建 observed 或 censored 标签。只有每个活跃 cell 的终止原因、计划循环数和末端未配对原因被确认后，才允许进入 label policy 的下一道审计。

每次审计会额外生成 `partner_termination_confirmation_template.csv`。partner 只需填写计划长循环数、实际终止原因、末端未配对充电原因、异常情况和日志位置；不需要重新导出 BTSDA 原始数据。

对未来自然失效的 full-cell，复用同一终止审计脚本，不新增平行 parser。必须补齐 `failure_event_long_cycle_index`、`failure_mode`、`failure_evidence_location`；三者齐全且事件位于有效观察窗口内，才能被标记为 observed-failure intake semantics confirmed。该状态仍不是训练标签，后续还需单独 label audit。

```text
label_trainability_allowed=False
model_training_allowed=False
```
