# LMB Full-Cell Early-Cycle 特征稳定性与协议差异审计

该审计只对 protocol-censored full-cell 的已提取 early-cycle 特征进行描述性统计：单 cell 的均值、波动、趋势、特征覆盖率及按协议汇总。

当前两类 LB-085 协议同时改变了正极直径和充放电条件，因此跨协议均值差异属于 `confounded_design_and_operation_comparison_not_causal`。它们不能被解释为电解液、材料、几何或协议的单独因果效应。

容量和 CE 特征保留 `same_signal_source_risk` 标记；电压滞后、端电压和时长特征可作为更优先的机制特征族，但此处仍只是审计，不代表预测信号。

```text
audit_only=True
model_training_allowed=False
```
