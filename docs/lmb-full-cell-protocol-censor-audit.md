# LMB Full-Cell Protocol-Censored-Only 标签审计

当实验确认“达到计划循环数”但没有确认自然失效时，cell 在最后一个完整 long-cycle 配对处是 `protocol_censored`。这意味着：在该时刻之前未观测到失效，但并不意味着电池永远不会失效。

本审计只输出删失事实和已知存活范围：

- `event_observed=False`
- `censoring_type=planned_cycle_count_reached`
- `censoring_long_cycle_index=最后完整 long-cycle`

禁止把这些记录转换为普通二分类的负样本，禁止伪造 capacity EOL、RUL 或失败目标。只有未来获得多组已确认的 observed full-cell failure 后，才能把删失样本与事件样本一起纳入生存分析或严格的 trainability audit。

```text
audit_only=True
label_trainability_allowed=False
model_training_allowed=False
```
