# LMB Current Data Scope Tags

This document records the scope tag for the current partner-provided LMB lab
data. The purpose is to prevent Li||Li and Li||Cu mechanism-test data from
being reported as full-cell lifetime evidence.

## Core Tag

```text
cell_scope = lmb_mechanism_test_not_full_cell
is_full_cell = false
full_cell_data_available = false
```

These cells are valuable LMB mechanism data, but they are not complete
full-cell datasets. They may support parser validation, feature design,
audit-only label scans, and warning-proxy exploration after gates pass. They
must not be described as full-cell RUL, full-cell EOL, or full-cell lifetime
prediction evidence.

## Waiting For Full-Cell Data

Future full-cell or anode-free full-cell data should be assigned a separate
scope after intake:

```text
cell_scope = lmb_full_cell
```

or, for true anode-free full-cell assemblies:

```text
cell_scope = anode_free_full_cell
```

Those future data will be more suitable for full-cell lifetime, EOL, RUL, and
strategy-optimization questions. Until such data arrive and pass metadata,
label, trainability, leakage, and baseline-ready gates, the current project
state remains:

```text
full_cell_data_available = false
model_training_allowed = False
```

## Current Cell Assignments

| source_folder_name | cell_group | cell_scope | is_full_cell | allowed use | forbidden use |
| --- | --- | --- | --- | --- | --- |
| `26-0414` | Li||Li | `lmb_mechanism_test_not_full_cell` | false | symmetric-cell polarization, voltage hysteresis, voltage instability, soft-short audit | full-cell lifetime/RUL/EOL claims |
| `26-0421` | Li||Li | `lmb_mechanism_test_not_full_cell` | false | symmetric-cell polarization, voltage hysteresis, voltage instability, soft-short audit | full-cell lifetime/RUL/EOL claims |
| `26-0429-009(li-li)` | Li||Li | `lmb_mechanism_test_not_full_cell` | false | symmetric-cell polarization, voltage hysteresis, voltage instability, soft-short audit | full-cell lifetime/RUL/EOL claims |
| `26-0428-009` | Li||Cu | `lmb_mechanism_test_not_full_cell` | false | CE, plating/stripping efficiency, incomplete-capacity warning proxy | full-cell lifetime/RUL/EOL claims |
| `26-0428-085` | Li||Cu | `lmb_mechanism_test_not_full_cell` | false | CE, plating/stripping efficiency, incomplete-capacity warning proxy | full-cell lifetime/RUL/EOL claims |
| `26-0429-002(li-Cu)` | Li||Cu | `lmb_mechanism_test_not_full_cell` | false | CE, plating/stripping efficiency, incomplete-capacity warning proxy | full-cell lifetime/RUL/EOL claims |
| `26-0512(li-Cu)` | Li||Cu | `lmb_mechanism_test_not_full_cell` | false | CE, plating/stripping efficiency, incomplete-capacity warning proxy | full-cell lifetime/RUL/EOL claims |

## Metadata Implication

For Li||Li and Li||Cu cells, N/P ratio is not a meaningful full-cell balancing
field. Record it as not applicable. Prefer recording:

- Li foil thickness
- Cu foil or substrate information
- current density
- areal capacity
- electrolyte code and shareable details
- electrolyte volume
- separator
- pressure
- temperature
- cycling protocol
- planned cycle count
- termination reason
- abnormal notes

## Reporting Rule

Allowed wording:

- "The current Li||Li and Li||Cu datasets are LMB mechanism-test data."
- "Li||Cu data are used for CE and incomplete-capacity warning-proxy audit."
- "Li||Li data are used for voltage and polarization mechanism audit."

Forbidden wording:

- "The current data prove full-cell LMB lifetime prediction."
- "The current Li||Cu tiny smoke-test is full-cell RUL performance."
- "Li||Li and Li||Cu can be mixed as one training task."

Model training remains blocked until future data pass intake, metadata, label,
trainability, leakage, and baseline-ready export gates.
