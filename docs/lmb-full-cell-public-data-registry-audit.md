# LMB Full-Cell Public Data Registry Audit

```text
registry_audit_only=True
model_training_allowed=False
download_requires_user_confirmation=True
```

## 1. 审计结论

Trae 的公开数据源注册表有价值：它把 LMB full-cell、anode-free full-cell、source data、OSF/NIMS/GitHub/Figshare 等候选来源集中到了一个清单里，适合作为后续数据源导航草稿。

但该草稿不能直接作为最终事实使用。主要原因是：

- 原始 Trae 文档存在编码异常：`source registry draft encoding needs cleanup`。
- 多个来源仍未下载核验，不能把 `source data` 自动等同于 raw training data。
- REG-001 Amanchukwu GitHub 更可能是 per-electrolyte / active-learning summary，不应直接写成 per-cycle lifetime raw dataset。
- REG-004 与 REG-012 可能是同一数据源的不同索引，不能重复计数。
- “所有候选源都没有 sub-cycle step/record layer”只能保留为未下载前的初步风险，不是最终事实。

当前允许进入 **用户确认下载阶段**，但仍禁止模型训练。

## 2. 可保留的结论

- REG-002 Uppaluri/Onori OSF 是当前最优先核验的 LMB full-cell 数据候选。
- REG-003 Si/Matsuda NIMS MDR 与 cycle-life prediction、relaxation/EIS 特征高度相关，适合优先 tiny validation。
- REG-001 Amanchukwu AL-anode-free 对 anode-free electrolyte/strategy optimization 很有价值，但必须先确认是否有 per-cell / per-cycle cycling data。
- REG-005、REG-009、REG-011 等如果缺少 raw table，应先作为 literature_reference_only 或 author_contact_needed。
- 普通 Li-ion 数据只能作为 `li_ion_method_data`，不能支持 LMB full-cell 结论。
- Li||Li / Li||Cu 只能归为 `lmb_mechanism_test_not_full_cell`，不能作为 full-cell 结论证据或训练输入。

## 3. 需要修正或降级的结论

- REG-001 从 `P0_download_first` 降为 `P1_cautious_download`，除非用户确认存在 per-cycle cycling table。
- REG-006 从“可能 label_audit”降为 `P1_cautious_download`，因为 Figshare dataset 内容未核验。
- REG-007 / REG-008 降为 `P2_literature_reference`，除非下载后确认存在 cycling table。
- REG-005 / REG-009 / REG-011 降为 `P3_author_contact` 或 `P2_literature_reference`，因为公开 raw table 不明确。
- REG-004 / REG-012 标记为 duplicate_or_overlap，不能重复下载或重复统计。

## 4. Top 3 优先核验/下载源

| priority | source_id | source | 判定 |
| --- | --- | --- | --- |
| 1 | REG-002 | Uppaluri/Onori OSF LMB degradation dataset | 最像可接入的 LMB full-cell per-cycle 数据，应优先下载并 tiny validation |
| 2 | REG-003 | Si/Matsuda NIMS MDR LMB cycle life prediction | 方法相关性强，体量小，适合作为 relaxation/EIS/cycle-life schema 核验 |
| 3 | REG-001 | Amanchukwu AL-anode-free GitHub | anode-free strategy 价值高，但先确认是否只是 per-electrolyte summary |

## 5. 只适合文献启发或联系作者的来源

- REG-005 Liu/Li/Chen initially anode-free pouch cell：anode-free pouch cell 很重要，但若只有论文图或 source figure，不能当 raw training data。
- REG-009 Mao/Suo/Wang PNAS anode-free pouch cell：体系重要，但公开 raw cycling table 不明确。
- REG-011 Chen/Bao/Cui Chem Sci anode-free：对电解液设计有启发，但现有公开数据可能偏短且缺 raw table。
- REG-007 / REG-008 Wichmann Figshare source data：下载前只能视为 source-data candidate，不能写成训练数据。

## 6. 哪些 source data 不能当 raw training data

Nature source data、Figshare source data、PNAS supplementary、RSC ESI 只有在下载后确认包含 per-cell 或 per-cycle cycling table 时，才可进入 tiny validation。否则只能用于 feature_schema_test、label_audit design 或 literature_reference_only。

REG-001 的 per-electrolyte active-learning summary、C20 proxy、capacity retention summary 也不能自动当作 per-cycle lifetime dataset。

## 7. 标签与特征潜力

最可能支持 `capacity_eol_80` 的来源：

- REG-002：若 OSF `.mat` 包含 per-cell capacity vs cycle。
- REG-003：若 NIMS 数据包含 cycle life / capacity trajectory。
- REG-004：若 OSF 数据包含 charge/discharge cycle table。

最可能支持 CE label 的来源：

- REG-002：如果 charge/discharge capacity 可计算 CE。
- REG-001：如果 batch CSV 中包含 CE 或可由实验重复推导。
- REG-004：如果 cycling table 包含 charge/discharge capacity。

最可能支持 voltage / polarization feature 的来源：

- REG-002：若包含 voltage/current/capacity per cycle 或 time series。
- REG-003：relaxation/EIS 特征与项目方向高度相关。
- REG-004：若存在 voltage-capacity 或 GITT/formation 信息。

## 8. 用户下载建议

第一批建议：

1. REG-002 Uppaluri/Onori OSF：下载 `.mat` 或原始数据包，检查是否有 per-cell / per-cycle capacity、voltage、current。
2. REG-003 Si/Matsuda NIMS MDR：下载 zip，检查是否有 CSV/XLSX/MAT、cycle life 标注、EIS/relaxation 数据。
3. REG-001 Amanchukwu GitHub：先 clone GitHub 小文件，暂缓 Box 大文件；检查 CSV 是 per-electrolyte summary 还是 per-cell cycling table。

第二批谨慎：

- REG-004 / REG-012：先确认是否重复，避免重复下载。
- REG-006：若文件不大，可下载后仅做 source-data inventory。

暂不优先：

- REG-005 / REG-009 / REG-011：先作为文献启发；若导师认为重要，再联系作者。

## 9. Codex / Trae / 用户分工

| 角色 | 负责内容 |
| --- | --- |
| Trae | 继续做文献和数据源草稿扩展，不负责最终门禁 |
| Codex | registry audit、字段标准化、下载后 tiny validation 脚本和门禁 |
| 用户 | 确认是否下载、手动下载需登录/授权的数据、询问导师或 partner |

## 10. Gate Decision

```text
registry_audit_only=True
model_training_allowed=False
download_requires_user_confirmation=True
user_download_stage_allowed=True
```

下一步允许用户确认下载 REG-002 / REG-003 / REG-001，但下载后仍只进入 tiny validation，不进入模型训练。
