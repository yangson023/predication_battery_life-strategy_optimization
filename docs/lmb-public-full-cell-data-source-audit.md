# LMB Public Full-Cell Data Source Audit

Generated: 2026-06-29

This document audits public lithium metal battery (LMB) full-cell and
anode-free full-cell data sources collected in
`docs/lmb-full-cell-public-data-sources.md`. It is a data-source audit, not a
training report. No public dataset listed here is allowed to enter model
training until intake, metadata, label, censoring, leakage, and
baseline-ready-export gates pass.

Current decision:

```text
model_training_allowed=False
public_full_cell_download_stage_allowed=True
large_file_download_allowed=False
processed_data_generation_allowed=False
```

## 1. Audit Conclusion

Top 3 recommended user-confirmed download targets:

| rank | source_id | source | recommended action | reason |
| --- | --- | --- | --- | --- |
| 1 | S5 | Ma / Amanchukwu anode-free Cu||LFP active-learning dataset | Confirm GitHub and Source Data files, then download only after user approval | True anode-free full-cell scope; Nature article states experimental cycling data are in Supporting Information and GitHub / Source Data. High value for anode-free labels, but target may be capacity retention at selected cycles rather than full lifetime EOL. |
| 2 | S1 | Uppaluri / Onori LMB degradation dataset | User should open OSF page and confirm `.mat` contents before download | Most directly relevant Li||NMC full-cell degradation dataset according to Trae scout report; likely useful for full-cell intake and capacity label rehearsal if raw cycling arrays are present. |
| 3 | S8 | Liu / Li / Chen initially anode-free pouch-cell charging-protocol dataset | Confirm Source Data XLSX contents, then download after user approval | True anode-free full-cell pouch-cell paper; Nature article provides Source Data. Needs field check to see whether it contains raw cycling tables or only plotted-source summaries. |

Cautious download / inspect first:

- S2 Si / Matsuda NIMS MDR LMB cycle-life paper page. The MDR page is verified and downloadable, but the visible file list is a paper PDF / zip rather than a confirmed machine-readable raw cycling table. It is still scientifically important because it describes discharge, charge, and relaxation features for LMB cycle-life prediction.
- S4 Li / Whittingham OSF lithium-inventory tracking data. Likely valuable if files are accessible, but OSF contents must be manually checked before intake.
- S9 Chen / Bao / Cui Chemical Science anode-free Cu||LFP source. High mechanism value, but likely supplementary/source-data summary rather than full raw cycling table.

Literature-reference first:

- S3 Dutta / Matsuda discharge-rate study, S6 Mao / Suo / Wang PNAS anode-free pouch-cell work, S7 Chen / Dai heat-treated Cu, and S10 Sangsanit / Sawangphruk cylindrical anode-free work should be treated as literature references unless raw cycling tables are confirmed.

Not recommended for this full-cell data pipeline:

- Conventional Li-ion datasets, materials-descriptor CSVs, microCT-only datasets, and field-operation Li-ion datasets. They may be `li_ion_method_data` or `diagnostic_only`, but they cannot support LMB full-cell conclusions.

## 2. Decision Rules

| condition | decision |
| --- | --- |
| LMB full-cell or anode-free full-cell with accessible raw cycling table | `P0_download_first` or `P1_cautious_download`; user confirmation required before download |
| LMB full-cell paper with Source Data / Supplementary Information but unknown table granularity | `P1_cautious_download`; inspect file contents after user approval |
| Only plotted curves or article figures, no table or downloadable source data | `P2_literature_reference` |
| Li||Li symmetric or Li||Cu half-cell only | `lmb_mechanism_test_not_full_cell`; not full-cell |
| Conventional Li-ion data | `li_ion_method_data`; method development only |
| Chemistry or cell scope unclear | `unknown`; no training and no scientific conclusion |

Required row fields for every candidate:

```text
dataset_role
cell_scope
data_access_status
intake_priority
training_allowed_now=False
```

## 3. Candidate Data Source Audit Table

| source_id | data source | paper / topic | authors / year | DOI / link | dataset_role | cell_scope | data_access_status | intake_priority | raw cycling table | cycle / step / record outlook | metadata outlook | label potential | project use | training_allowed_now |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | Uppaluri / Onori OSF LMB degradation dataset | Lithium-metal battery degradation dataset from continuous cycling experiments | Uppaluri, Ma, Xu, Onori et al., 2025 | DOI reported by Trae: `10.1016/j.dib.2025.111787`; OSF: `https://osf.io/5dqwg/?view_only=608e4c22acdd483591d1d55b74a81401` | `true_lmb` | `lmb_full_cell` | `requires_user_download_confirmation` | `P0_download_first` | likely yes according to Trae, `.mat` needs inspection | likely cycle-level; step / record unclear | cell design, electrolyte configuration, protocol likely partial | `capacity_eol_80`, `capacity_eol_70`, `protocol_censored`; observed EOL must be audited | download candidate; full-cell intake validation; label-audit candidate | False |
| S2 | Si / Matsuda NIMS MDR | Data-Driven Cycle Life Prediction of Lithium Metal-Based Rechargeable Battery Based on Discharge/Charge Capacity and Relaxation Features | Si, Matsuda, Yamaji, Momma, Tateyama, 2024 | DOI `10.1002/advs.202402608`; MDR `https://mdr.nims.go.jp/datasets/ca5f2d26-d0c5-41a8-9131-2afbf4ce84b4` | `true_lmb` | `lmb_full_cell` | `verified_download_page` | `P1_cautious_download` | not confirmed from MDR listing; visible file is PDF / zip | charge / discharge / relaxation features described; raw table not yet confirmed | NMC811, Li metal, high loading, relaxation features | capacity cycle life, relaxation-feature audit, possible `capacity_eol_80`; labels must be reconstructed | literature + possible schema reference; inspect download contents only after approval | False |
| S3 | Dutta / Matsuda discharge-rate study | Optimizing discharge rate for Li metal stability in Li||NMC under lean electrolyte condition | Dutta, Mizuki, Tomori, Matsuda, 2024 | DOI `10.1021/acsaem.4c00180` | `true_lmb` | `lmb_full_cell` | `requires_author_contact` | `P2_literature_reference` | unknown | likely paper curves / SI summaries | discharge rate, lean electrolyte, Li||NMC context | capacity fade and protocol effect audit only if tables exist | literature reference; not a first download target | False |
| S4 | Li / Whittingham lithium-inventory tracking | Lithium inventory tracking as a non-destructive battery evaluation and monitoring method | Li, Zhang, Zhou, Xin, Whittingham, Liaw, 2024 | DOI `10.1038/s41560-024-01476-z`; OSF `https://osf.io/2w4k3/` | `true_lmb` | `lmb_full_cell` | `requires_user_download_confirmation` | `P1_cautious_download` | unknown until OSF file inspection | possible cycling / GITT / inventory-tracking files | cathode / Li inventory information likely useful; exact metadata must be checked | capacity retention, lithium-inventory proxy, `protocol_censored` if termination can be inferred | cautious download; useful for metadata and feature ideas | False |
| S5 | Ma / Amanchukwu active-learning anode-free | Active learning accelerates electrolyte solvent screening for anode-free lithium metal batteries | Ma, Kumar, Wang, Amanchukwu, 2025 | DOI `10.1038/s41467-025-63303-7`; GitHub `https://github.com/AmanchukwuLab/AL-anode-free` | `true_lmb` | `anode_free_full_cell` | `verified_download_page` | `P0_download_first` | yes, but granularity must be checked; article states cycling data in SI / GitHub / Source Data | likely cycle summaries and labeled electrolyte datasets; full record unlikely | Cu||LFP, electrolyte identity, capacity-retention target; metadata likely strong for electrolyte screening | `capacity_eol_80` may be possible if cycle curves exist; otherwise capacity-retention-at-cycle target; CE / protocol censoring need audit | high-priority anode-free source; download after user approval | False |
| S6 | Mao / Suo / Wang PNAS anode-free pouch | Electrolyte design combining fluoro- with cyano-substitution solvents for anode-free Li metal batteries | Mao, Gong, Wang et al., 2024 | DOI `10.1073/pnas.2316212121`; PNAS SI page | `true_lmb` | `anode_free_full_cell` | `requires_author_contact` | `P2_literature_reference` | not confirmed; likely figures / SI only | likely not raw table | strong pouch-cell and electrolyte metadata in paper | capacity retention and safety / protocol ideas; not model-ready | literature reference; contact author if this becomes important | False |
| S7 | Chen / Dai heat-treated Cu | Facile one-step heat treatment of Cu foil for stable anode-free Li metal batteries | Chen, Dai, Hu, Li, 2023 | DOI `10.3390/molecules28020548` | `true_lmb` | `anode_free_full_cell` | `literature_reference_only` | `blocked` | no confirmed raw table | likely figures only | Cu treatment comparison, limited cell count | audit-only mechanism context | not recommended for model pipeline | False |
| S8 | Liu / Li / Chen initially anode-free pouch | Tailored charging protocol for densified lithium deposition and stable initially anode-free lithium metal pouch cells | Liu, Yin, Guo, Wang, Li, Chen et al., 2025 | DOI `10.1038/s41467-025-66271-0`; Nature Source Data XLSX available | `true_lmb` | `anode_free_full_cell` | `verified_download_page` | `P1_cautious_download` | likely source-data tables; raw cycling granularity must be checked | likely source data + SI, full record unlikely | charging protocol, pouch-cell format, anode-free state | capacity retention, charging-protocol effect, `protocol_censored` if endpoint known | cautious high-value download candidate after user approval | False |
| S9 | Chen / Bao / Cui Chemical Science | Hyperconjugation-controlled molecular conformation weakens lithium-ion solvation and stabilizes lithium metal anodes | Chen, Liao, Gong, Zhang et al., 2024 | DOI `10.1039/D4SC05319B` | `true_lmb` | `anode_free_full_cell` | `literature_reference_only` | `P2_literature_reference` | not confirmed | likely ESI figures / selected source data | electrolyte design and Cu||LFP / thin-Li context | mechanism context, CE and retention thresholds for discussion only | literature reference; not a first pipeline source | False |
| S10 | Sangsanit / Sawangphruk cylindrical anode-free | Stable SEI in cylindrical anode-free Li-metal NMC90 batteries | Sangsanit, Songthan et al., 2025 | DOI `10.1021/acs.nanolett.5c01595` | `true_lmb` | `anode_free_full_cell` | `literature_reference_only` | `blocked` | no confirmed raw table | likely figures only | cylindrical 18650 context, special format | mechanism reference only | not recommended for first pipeline source | False |
| X1 | Severson / Attia fast-charge dataset and similar conventional Li-ion sets | Conventional LIB lifetime datasets | Various | various | `li_ion_method_data` | `li_ion_method_cell` | `not_recommended` | `blocked` | yes for Li-ion, but not LMB | useful for method rehearsal only | graphite/LFP or other LIB metadata | not LMB full-cell labels | method reference only; not LMB conclusion | False |
| X2 | Materials-descriptor-only CSVs | Composition / descriptor tables without cycling | Various | various | `unknown` | `unknown_scope` | `not_recommended` | `blocked` | no | no electrochemical cycling table | insufficient | no lifetime labels | not recommended | False |
| X3 | microCT / imaging-only datasets | Imaging diagnostics | Various | various | `diagnostic_only` | `diagnostic_only_scope` | `not_recommended` | `blocked` | no | no normal cycle table | imaging metadata only | diagnostic-only | not a full-cell life pipeline input | False |

## 4. Top 3 Recommended Download Sources

### S5: Ma / Amanchukwu anode-free Cu||LFP active-learning dataset

Why first:

- It is a true anode-free full-cell source, not Li||Cu half-cell data.
- The article states that experimental cycling data are available in Supporting Information, GitHub, and Source Data.
- It directly targets electrolyte screening for anode-free LMBs, which is close to the project's future strategy-optimization direction.

User confirmation before download:

- Confirm which files contain actual cycling curves versus electrolyte feature labels.
- Check whether each row corresponds to a cell, replicate, electrolyte formulation, or aggregated condition.
- Record whether the target is full lifetime EOL, 20th-cycle normalized discharge capacity, or another capacity-retention proxy.

### S1: Uppaluri / Onori OSF LMB degradation dataset

Why first:

- Trae identified it as the most directly relevant public LMB degradation dataset.
- If `.mat` files contain per-cell cycle tables, it is suitable for full-cell intake validation and capacity-label audit.
- It may provide enough cell count to rehearse leave-one-cell-out full-cell workflow.

User confirmation before download:

- Confirm OSF file list and license.
- Confirm whether voltage, current, capacity, cycle index, and cell metadata are machine-readable.
- Confirm whether there are terminal cycles sufficient for `capacity_eol_80`, `capacity_eol_70`, and `protocol_censored` audit.

### S8: Liu / Li / Chen initially anode-free pouch-cell source data

Why first:

- It is an anode-free full-cell pouch-cell study.
- The Nature page provides Source Data XLSX.
- It may help connect protocol design with failure or retention behavior.

User confirmation before download:

- Check whether Source Data XLSX contains raw cycle-by-cycle values or only figure-source aggregates.
- Check cell-level identifiers, cycle counts, charge protocol, and endpoint definitions.
- If only figure-source data exist, keep it as literature/reference data rather than a pipeline source.

## 5. Cautious Download Sources

| source_id | reason for caution | next action |
| --- | --- | --- |
| S2 | Verified MDR page, but visible file listing is a PDF / zip rather than confirmed raw cycling table. | User can download the small zip only after approval and inspect whether tables are present. |
| S4 | OSF project exists, but file access and content were not fully confirmed in this audit. | User should open OSF page manually and list file names before downloading. |
| S9 | Strong anode-free mechanism paper, but raw cycle table availability is unclear. | Treat as literature unless ESI contains table-form source data. |

## 6. Literature Reference Only

| source_id | reason |
| --- | --- |
| S3 | Useful for discharge-rate and lean-electrolyte context, but raw machine-readable cycling data are not confirmed. |
| S6 | Valuable anode-free pouch-cell paper, but raw table access appears to require author contact or SI inspection. |
| S7 | Limited comparison and no confirmed raw cycling table; not enough for this project's data pipeline. |
| S10 | Interesting cylindrical anode-free format, but no confirmed raw cycling table and special format may add confounding. |

## 7. Not Recommended Sources

| source type | dataset_role | why not recommended |
| --- | --- | --- |
| Conventional Li-ion lifetime data | `li_ion_method_data` | Useful for software rehearsal only; cannot support LMB full-cell claims. |
| Materials descriptor tables without cycling | `unknown` | No cycle, capacity, voltage, current, or time information for lifetime labels. |
| microCT / imaging-only datasets | `diagnostic_only` | May be useful for mechanism context, but cannot directly define cycle-life labels without alignment. |
| Li||Li or Li||Cu half-cell-only datasets | `true_lmb` with `lmb_mechanism_test_not_full_cell` | Mechanistically useful, but not full-cell EOL/RUL data. |

## 8. Data Field Readiness Checklist For Downloaded Sources

After user approval and download, each source must be checked for:

| field family | required checks |
| --- | --- |
| identity | source_id, paper DOI, dataset URL, license, file list, file size |
| cell scope | full-cell, anode-free full-cell, Li||Li, Li||Cu, conventional Li-ion, or unknown |
| cycle table | cycle_index, charge_capacity, discharge_capacity, capacity retention, CE if available |
| electrochemical curves | voltage, current, time, step / record layer if available |
| metadata | cathode_type, anode_type, anode_free_status, electrolyte, N/P ratio, current_density, areal_capacity, voltage_cutoff, temperature, pressure |
| protocol and censoring | planned cycle count, stopping rule, termination reason, failure mode |
| label potential | `capacity_eol_80`, `capacity_eol_70`, CE collapse, polarization failure, voltage instability, `protocol_censored` |

If raw cycling tables are absent, the source remains `literature_reference_only`.

## 9. Author Contact Checklist

For sources marked `requires_author_contact`, ask for:

1. Per-cell cycle table with cycle index, charge capacity, discharge capacity, CE, voltage window, and timestamp if available.
2. Cell-level metadata: cathode, anode / anode-free status, electrolyte, N/P ratio or N/A, current density, areal capacity, pressure, temperature.
3. Protocol information: formation, cycling, voltage cutoff, current / C-rate, planned cycle count.
4. Termination reason: natural capacity fade, safety stop, equipment stop, manual stop, protocol end, or unknown.
5. Whether data can be used for academic method development and whether redistribution is allowed.

## 10. Final Gate Decision

```text
user_confirmed_download_stage_allowed=True
full_cell_intake_allowed_after_download=True
label_audit_allowed_after_schema_check=True
baseline_ready_export_allowed=False
model_training_allowed=False
```

The next allowed action is user-confirmed download planning for S5, S1, and S8,
plus cautious inspection of S2 and S4. No source is currently allowed to support
model training or formal full-cell lifetime conclusions.

## 11. Sources Checked In This Audit

- NIMS MDR page for Si / Matsuda LMB cycle-life paper:
  `https://mdr.nims.go.jp/datasets/ca5f2d26-d0c5-41a8-9131-2afbf4ce84b4`
- Nature Communications page for Ma / Amanchukwu active-learning anode-free LMB:
  `https://www.nature.com/articles/s41467-025-63303-7`
- Amanchukwu Lab GitHub repository:
  `https://github.com/AmanchukwuLab/AL-anode-free`
- Nature Communications page for tailored charging protocol in initially
  anode-free pouch cells:
  `https://www.nature.com/articles/s41467-025-66271-0`
- Trae scouting report:
  `docs/lmb-full-cell-public-data-sources.md`
- Project policy references:
  `docs/data-role-classification-policy.md`,
  `docs/lmb-current-data-scope-tags.md`,
  `docs/lmb-full-cell-readiness-plan.md`
