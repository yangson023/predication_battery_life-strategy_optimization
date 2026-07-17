# LMB Public Source Feature Schema Test

This project document mirrors the generated report in a durable form for future partner full-cell intake work.


Generated: 2026-07-05T02:38:36.471224+00:00

This is a source-data and feature-schema audit. It is not a formal training set, not a model run, and not a performance result.

```text
source_data_audit_only=True
feature_schema_test_only=True
model_training_allowed=False
```

## Core Findings

- Nature source data is most useful for defining feature families around capacity retention, CE behavior, voltage/time shape, and electrolyte/protocol strategy context.
- Capacity, CE, voltage/time, and protocol/metadata requirements can be transferred into the partner full-cell intake framework.
- C20 proxy is only an electrolyte or strategy proxy. It is not full lifetime RUL/EOL.
- CC/MPC/protocol traces are useful for future strategy optimization design, but they cannot be randomly mixed as independent training samples.
- Observed/censored labels still require partner metadata: termination reason, planned cycle count, protocol changes, current density, areal capacity, voltage cutoff, and electrolyte context.

## Feature Family Counts

- `capacity_retention`: 10
- `coulombic_efficiency`: 10
- `electrolyte_strategy`: 1
- `label_inspiration`: 12
- `voltage_time`: 1

## Transferable To Partner Full-Cell Intake

- `capacity_retention`
- `coulombic_efficiency`
- `voltage_time`
- `electrolyte_strategy`

## Audit-Only Or Proxy Signals

- `C20_proxy_only`
- `protocol_censored_possible_without_terminal_metadata`
- `Li||Cu_or_Li||Li_mechanism_context_not_full_cell`

## Selected Sheet Use

| workbook | sheet | cell_scope | feature families | label signals | training now | limitation |
| --- | --- | --- | --- | --- | --- | --- |
| 41467_2025_63303_MOESM3_ESM.xlsx | Figure 3a | anode_free_full_cell | capacity_retention;coulombic_efficiency;label_inspiration | capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible;CE_failure_possible;CE_instability_possible | False | requires_partner_metadata_for_observed_or_censored_label |
| 41467_2025_63303_MOESM3_ESM.xlsx | Figure 3b | anode_free_full_cell | capacity_retention;coulombic_efficiency;label_inspiration | capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible;CE_failure_possible;CE_instability_possible | False | requires_partner_metadata_for_observed_or_censored_label |
| 41467_2025_63303_MOESM3_ESM.xlsx | Figure S7 | lmb_mechanism_test_not_full_cell | voltage_time;label_inspiration | polarization_failure_possible;voltage_instability_possible | False | mechanism_test_not_full_cell |
| 41467_2025_63303_MOESM3_ESM.xlsx | Figure S16 | anode_free_full_cell | electrolyte_strategy;label_inspiration | C20_proxy_only;audit_only_label_signal | False | C20_proxy_only_not_full_RUL_or_EOL |
| 41467_2025_66271_MOESM3_ESM.xlsx | Fig. 1f | lmb_mechanism_test_not_full_cell | capacity_retention;coulombic_efficiency;label_inspiration | capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible;CE_failure_possible;CE_instability_possible | False | mechanism_test_not_full_cell |
| 41467_2025_66271_MOESM3_ESM.xlsx | Fig. 1i | lmb_mechanism_test_not_full_cell | capacity_retention;coulombic_efficiency;label_inspiration | capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible;CE_failure_possible;CE_instability_possible | False | mechanism_test_not_full_cell |
| 41467_2025_66271_MOESM3_ESM.xlsx | Fig. 5c | anode_free_full_cell | capacity_retention;coulombic_efficiency;label_inspiration | capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible;CE_failure_possible;CE_instability_possible | False | requires_partner_metadata_for_observed_or_censored_label |
| 41467_2025_66271_MOESM3_ESM.xlsx | Fig. 6c | anode_free_full_cell | capacity_retention;coulombic_efficiency;label_inspiration | capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible;CE_failure_possible;CE_instability_possible | False | requires_partner_metadata_for_observed_or_censored_label |
| 41467_2025_66271_MOESM3_ESM.xlsx | Supplementary Fig. 36a | anode_free_full_cell | capacity_retention;coulombic_efficiency;label_inspiration | capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible;CE_failure_possible;CE_instability_possible | False | requires_partner_metadata_for_observed_or_censored_label |
| 41467_2025_66271_MOESM3_ESM.xlsx | Supplementary Fig. 37c | anode_free_full_cell | capacity_retention;coulombic_efficiency;label_inspiration | capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible;CE_failure_possible;CE_instability_possible | False | requires_partner_metadata_for_observed_or_censored_label |
| 41467_2025_66271_MOESM3_ESM.xlsx | Supplementary Fig. 42a | anode_free_full_cell | capacity_retention;coulombic_efficiency;label_inspiration | capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible;CE_failure_possible;CE_instability_possible | False | requires_partner_metadata_for_observed_or_censored_label |
| 41467_2025_66271_MOESM3_ESM.xlsx | Supplementary Fig. 43e | anode_free_full_cell | capacity_retention;coulombic_efficiency;label_inspiration | capacity_eol_80_possible;capacity_eol_70_possible;protocol_censored_possible;CE_failure_possible;CE_instability_possible | False | requires_partner_metadata_for_observed_or_censored_label |

## Gate Decision

- public_source_label_audit_design_allowed=True
- model_training_allowed=False
- direct_training_set_export_allowed=False

Next step: design a public-source label-audit policy, still audit-only, before any partner full-cell trainability gate.

## Long-Term Rule

Public Nature source data can guide feature schema and label-audit design, but partner full-cell data remains the validation subject. Do not treat figure-source C20 proxy, Li||Cu mechanism traces, or Li||Li mechanism traces as full-cell lifetime training data.
