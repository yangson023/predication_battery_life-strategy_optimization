# Data Role Classification Policy

This policy defines how datasets may be used in the lithium metal battery
research project. Its purpose is to prevent lithium-ion method data from being
misreported as lithium metal battery evidence.

The current target system is lithium metal battery (LMB). Existing NASA and
external lithium-ion datasets remain useful, but only as pipeline validation and
method-development data.

## Core Rule

Every dataset, feature table, label table, audit report, and model input must be
assigned a `dataset_role` before it is used for scientific interpretation.
For LMB lab data, also assign a `cell_scope` so mechanism-test cells are not
misreported as full-cell evidence.

Allowed values:

```text
true_lmb
li_ion_method_data
transfer_auxiliary_data
diagnostic_only
unknown
```

Only `true_lmb` data can support lithium metal battery research conclusions.
However, `true_lmb` does not automatically mean full-cell data. Li||Li
symmetric cells and Li||Cu half-cells are LMB-relevant mechanism-test cells, not
full-cell lifetime/RUL/EOL evidence.

Allowed `cell_scope` values:

```text
lmb_full_cell
anode_free_full_cell
lmb_mechanism_test_not_full_cell
li_ion_method_cell
diagnostic_only_scope
unknown_scope
```

## Role Definitions

| `dataset_role` | Definition | Can support LMB conclusions? | Can train LMB models? |
| --- | --- | --- | --- |
| `true_lmb` | Data from lithium metal, anode-free, Li||Cu, or clearly documented LMB-relevant cells with sufficient cell-design and protocol metadata | Yes, after audit | Yes, only after label and protocol gates pass |
| `li_ion_method_data` | Conventional lithium-ion data used to validate parsers, feature builders, label logic, audits, and baseline workflow | No | No for LMB claims; possible only for method rehearsal or transfer experiments with caveats |
| `transfer_auxiliary_data` | Li-ion or other non-LMB data used inside an explicitly designed transfer-learning or pretraining experiment | No as standalone evidence | Yes only as auxiliary data, never as the held-out LMB evidence source |
| `diagnostic_only` | RPT, EIS, thermal runaway, abuse, safety, or other diagnostic data that are useful for audit but not directly trainable yet | No by itself | No, unless protocol alignment and label policy are explicitly solved |
| `unknown` | Data with unclear chemistry, cell design, protocol, or provenance | No | No |

## Cell Scope Definitions

| `cell_scope` | Definition | Allowed use | Forbidden use |
| --- | --- | --- | --- |
| `lmb_full_cell` | Full-cell LMB or anode-free full-cell data with documented cathode, anode or host design, electrolyte, protocol, and termination reason | Can support full-cell LMB lifetime questions after all gates pass | Training before metadata, label, censoring, and leakage gates pass |
| `anode_free_full_cell` | Full-cell LMB subset with no initial lithium-metal anode reservoir, where lithium inventory comes from the cathode during formation | Can support anode-free lifetime and lithium-inventory questions after gates pass | Treating N/P ratio as ordinary lithium-excess full-cell metadata; training before anode-free-specific metadata and censoring review |
| `lmb_mechanism_test_not_full_cell` | LMB-relevant Li||Li symmetric cells or Li||Cu half-cells used to study lithium plating/stripping, CE, polarization, voltage instability, or soft-short mechanisms | Mechanism audit, feature design, warning-proxy labels, parser/schema validation for lab LMB data | Claiming full-cell lifetime/RUL/EOL conclusions; mixing Li||Li and Li||Cu as one training task |
| `li_ion_method_cell` | Conventional Li-ion cells used for method-development only | Pipeline validation and method rehearsal | LMB scientific conclusions |
| `diagnostic_only_scope` | RPT/EIS/thermal/abuse/diagnostic records without trainable cycle alignment | Audit and safety/mechanism context | Direct label training before alignment |
| `unknown_scope` | Scope is unclear or missing | Inventory and metadata recovery | Training or scientific claims |

## Full-Cell Scope Promotion Conditions

Data may be assigned `lmb_full_cell` only when all of the following are known
or explicitly marked as unavailable:

- cell ID and raw file provenance
- full-cell design type, such as coin cell, pouch cell, or other documented
  full-cell format
- cathode type and cathode loading or areal capacity
- anode type or anode-free status
- N/P ratio for lithium-excess full cells, or explicit anode-free flag when
  N/P ratio is not applicable
- electrolyte code and, if shareable, electrolyte details
- separator, pressure or pressure condition when available, and temperature
- current density, areal capacity, voltage cutoff, formation protocol, and
  cycling protocol
- planned cycle count, termination reason, failure mode, and abnormal notes
- BTSDA export layer availability: cycle, step, record, and protocol/XML when
  available

`anode_free_full_cell` should be used when the cell is a true full cell but the
negative electrode starts without a lithium-metal reservoir. It is not the same
as Li||Cu half-cell data. Li||Cu remains `lmb_mechanism_test_not_full_cell`
unless it is part of a documented full-cell assembly.

## Current Project Assignments

| Data source | Current `dataset_role` | Notes |
| --- | --- | --- |
| NASA battery `.mat` data | `li_ion_method_data` | Useful for quick pipeline checks and SOH/RUL method rehearsal only |
| Current external Li-ion cycle-life archives | `li_ion_method_data` | Useful for low-memory processing, label-audit, and validation workflow stress tests |
| Current external by-cell Round 1a/1b/1c Li-ion caches | `li_ion_method_data` | Do not expand for LMB claims; keep as method infrastructure |
| Future Li-ion pretraining subset, if explicitly designed | `transfer_auxiliary_data` | Only for transfer-learning experiments with true LMB validation |
| RPT / EIS / thermal runaway / abuse data | `diagnostic_only` | Training use requires protocol alignment and a separate label policy |
| Any dataset without clear chemistry or cell design | `unknown` | Must not enter training or scientific conclusions |

## Current LMB Lab Scope Assignment

The current partner-provided lab data are LMB-relevant but are not full cells:

| Current data group | `dataset_role` | `cell_scope` | Current scientific use | Forbidden wording |
| --- | --- | --- | --- | --- |
| Li||Li symmetric cells: `26-0414`, `26-0421`, `26-0429-009(li-li)` | `true_lmb` candidate after metadata gates | `lmb_mechanism_test_not_full_cell` | polarization, voltage instability, hysteresis, possible soft-short audit | "full-cell lifetime prediction data" |
| Li||Cu half-cells: `26-0428-009`, `26-0428-085`, `26-0429-002(li-Cu)`, `26-0512(li-Cu)` | `true_lmb` candidate after metadata gates | `lmb_mechanism_test_not_full_cell` | CE, plating/stripping efficiency, incomplete-capacity warning proxy | "full-cell RUL/EOL data" |

For these cells, N/P ratio should be recorded as not applicable. More useful
fields are Li foil thickness, current density, areal capacity, electrolyte
volume, separator, pressure, temperature, cycling protocol, and termination
reason.

## Allowed And Forbidden Uses

### `true_lmb`

Allowed:

- LMB feature engineering
- LMB label construction
- LMB label audit
- LMB exploratory baselines after gates pass
- LMB strategy-optimization reward design after prediction and safety gates are documented

Forbidden:

- Training before provenance, protocol, and label gates pass
- Mixing with Li-ion data without an explicit transfer-learning or method-control design
- Treating capacity-only EOL as sufficient without considering CE, overpotential,
  polarization, voltage instability, or soft-short signals

Required metadata:

- `cell_id`
- `cell_type`
- `anode_type`
- `cathode_type`
- `electrolyte`
- `separator`
- `areal_capacity_mah_cm2`
- `current_density_ma_cm2`
- `np_ratio`
- protocol information
- failure mode or stopping reason when available

### `li_ion_method_data`

Allowed:

- parser validation
- low-memory builder validation
- feature-schema stress testing
- label-audit workflow rehearsal
- baseline pipeline rehearsal
- demonstration of software reproducibility

Forbidden:

- Claiming LMB lifetime prediction performance
- Claiming LMB mechanism discovery
- Optimizing LMB charging strategy from Li-ion-only outcomes
- Reporting Li-ion baseline scores as LMB results

Required metadata:

- source dataset
- chemistry/cell type if known
- cell ID
- protocol or measurement type
- clear note that the role is method-development only

### `diagnostic_only`

Allowed:

- diagnostic feature extraction
- safety or mechanism audit
- consistency checks against cycle data
- future safety-constraint design

Forbidden:

- Direct use as training labels before protocol alignment
- Combining with cycle labels without an explicit mapping rule
- Treating RPT/EIS/thermal runaway events as normal cycle-life EOL without a
  separate research question

Required metadata:

- diagnostic type
- cell ID
- measurement time or cycle alignment
- protocol context
- reason it is audit-only

### `transfer_auxiliary_data`

Allowed:

- pretraining or representation learning before LMB fine-tuning
- transfer-learning ablation with true LMB held-out validation
- method comparison that clearly separates auxiliary data from LMB evidence

Forbidden:

- standalone LMB performance claims
- reporting auxiliary-data metrics as LMB results
- mixing with true LMB data without explicit split and provenance tracking

Required metadata:

- original data role and chemistry
- reason for transfer use
- exact training stage where it is used
- true LMB validation set kept separate
- report wording that labels it auxiliary, not evidence

### `unknown`

Allowed:

- inventory
- metadata recovery
- advisor or lab follow-up

Forbidden:

- training
- label construction for research claims
- inclusion in LMB conclusions
- inclusion in plots or tables that imply LMB evidence

Required metadata before promotion:

- chemistry
- cell design
- cell ID
- protocol
- measurement meaning
- source provenance

## Data Use Gates

Before using any dataset, apply these gates:

| Gate | Requirement |
| --- | --- |
| Role gate | `dataset_role` must be assigned |
| Provenance gate | source path/archive, cell ID, and measurement type must be traceable |
| Chemistry gate | true LMB claims require true LMB or explicitly justified transfer data |
| Protocol gate | protocol regime or protocol-censoring status must be known |
| Label gate | labels must define signal, threshold, window, censoring, and trainability |
| Report gate | report language must match the dataset role |

If a gate fails, the dataset may be inventoried but must not support LMB
conclusions.

## Reporting Language

Allowed wording:

- "NASA data are used as Li-ion method-development data."
- "External Li-ion cycle-life data validate the pipeline and label-audit workflow."
- "Non-LMB auxiliary data may be used only inside an explicitly labeled transfer-learning design."
- "This result is a schema, parser, or audit validation, not LMB performance."
- "LMB conclusions require true LMB data or a clearly labeled transfer-learning design."
- "Diagnostic data are audit-only until protocol alignment is solved."

Forbidden wording:

- "NASA results demonstrate LMB prediction performance."
- "The Li-ion baseline proves lithium metal battery lifetime prediction."
- "Transfer-learning auxiliary data are true LMB evidence."
- "RPT labels are trainable without protocol-regime assignment."
- "Tiny validation shows model performance."
- "Label audit results are model accuracy."
- "Unknown chemistry data support LMB conclusions."

## Codex / Trae / User Rules

Codex should:

- check manifests, schemas, reports, and file paths
- enforce `dataset_role` before data or labels are used
- reject Li-ion-only evidence for LMB conclusions
- write final local policy and audit documents
- avoid running big data unless the user explicitly asks and gates are clear

Trae may:

- draft role-classification suggestions
- challenge scientific wording
- identify missing LMB metadata
- review whether a proposed dataset can support LMB claims

The user should:

- ask the advisor or lab which data are true LMB data
- confirm whether chemistry, electrolyte, current density, areal capacity, and
  failure mode are available
- run long local commands only after Codex provides clear stop conditions
- decide when budget-saving compression can be relaxed

## Budget-Aware Practice

Do not repeatedly scan or regenerate large datasets to answer role questions.
Prefer checking:

- manifest files
- schema reports
- feature build reports
- label summaries
- advisor-confirmed metadata

When data role is unclear, mark it `unknown` and ask for metadata rather than
spending compute on premature processing.

## What We Will Do With These Data

Phase 1 has built and validated a reusable battery-data pipeline with Li-ion
method-development data: extraction, feature engineering, label audit,
low-memory processing, and guarded validation design.

Phase 2 adapts the same infrastructure to LMB-specific degradation mechanisms.
After the advisor confirms available LMB fields, the project will construct
LMB-specific features and labels such as CE decline/collapse, lithium inventory
loss, polarization growth, voltage instability, and soft-short warning.

## Immediate Project Decision

The current NASA and external Li-ion work has been completed as pipeline
validation. It is now archived as `li_ion_method_data` and should not be
expanded as if it were the final LMB research dataset.

The next scientific step is to identify or request true LMB data fields from the
advisor or lab.
