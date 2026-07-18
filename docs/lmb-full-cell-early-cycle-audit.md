# LMB Full-Cell 配对循环与早期特征审计

## 目的

本工具面向真实 LMB full-cell 的 BTSDA 三层导出，先按 `工步序号` 重建“充电 - 可选静置 - 放电”配对，再生成仅使用既往长循环的信息的早期特征审计表。它不生成标签、EOL、RUL、目标变量或模型结果。

cycle 层在本阶段用于检查三层导出齐全并记录行数；物理循环的重建以 step 层全局工步顺序为准，record 层以流式统计方式汇总到各充/放电工步，避免复制原始大表。

## 当前适用范围

- 主线输入：六组 `LB-085 / NCM811||Li` full-cell 导出。
- `26-0602`：0.98 cm 正极；充放电电流来自 1.2 cm 协议按面积比 `(0.98 / 1.20)^2` 缩放。
- `26-0610`：1.2 cm 正极；0.5C/0.5C 长循环协议。
- LHCE 导出：当前为 `diagnostic_only`，因末次循环异常而不进入本阶段。

## 输出与边界

1. `lmb_full_cell_paired_cycle_audit.csv`：每个完整充放电对及其工步、容量、电压、时长、record 汇总。
2. `lmb_full_cell_early_cycle_features.csv`：仅 long-cycle 阶段前 20 个配对循环的 past-only 特征。
3. `lmb_full_cell_unpaired_step_audit.csv`：例如末端孤立充电工步，保留而不强行配对。
4. `lmb_full_cell_feature_schema.csv`：记录特征的过去信息约束与同源风险。

容量和 CE 派生特征虽然只使用过去循环，仍可能与未来容量类标签同源；它们仅作审计候选。电压滞后、端电压和充放电时长是更值得后续核验的机制特征族。

## 当前门禁

```text
label_generation_allowed=False
model_training_allowed=False
```

原因是每个导出的终止原因仍未确认，不能可靠地区分 observed failure、right-censored 与 protocol-censored；且当前 6 个导出只覆盖两个协议/几何条件。
