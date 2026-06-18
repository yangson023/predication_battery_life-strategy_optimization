# Lithium Metal Battery Feature And Label Requirements

This document defines the required data fields, feature-engineering directions,
candidate labels, and advisor questions for the lithium metal battery (LMB)
research direction.

These are requirements and planning targets. They are not yet confirmed
available data, and they are not model-performance results.

## Purpose

The project target is lithium metal battery lifetime prediction and later
strategy optimization. Existing lithium-ion datasets are retained only as
pipeline validation and method-development data.

For LMB research, capacity fade alone is not enough. The project must be able to
represent Coulombic efficiency, overpotential, polarization, voltage
instability, plating/stripping behavior, and soft-short risk when the
experimental data support those signals.

## What We Will Do With These Data

Phase 1 has already built a reusable battery-data pipeline using Li-ion
method-development data: data extraction, low-memory feature generation, label
auditing, and guarded validation workflow.

Phase 2 will adapt that infrastructure to LMB-specific degradation mechanisms.
After the advisor confirms which LMB fields are available, the project will
define LMB-specific features and labels, then start with small, audited
early-failure classifiers rather than broad model claims.

## LMB Dataset Fields

These fields describe the cell design and experimental context. They should be
stored as metadata, not inferred from model outputs.

| Priority | Field | Meaning | Why it matters |
| --- | --- | --- | --- |
| P0 | `cell_id` | Unique cell identifier | Needed for leave-one-cell-out validation and traceability |
| P0 | `cell_type` | Li-metal excess, anode-free, Li||Cu, full cell, half cell, etc. | Determines whether LMB conclusions are valid |
| P0 | `anode_type` | Lithium metal, anode-free current collector, host, graphite, etc. | Separates true LMB from Li-ion method data |
| P0 | `cathode_type` | Cathode material and loading context | Needed to interpret capacity and voltage behavior |
| P0 | `electrolyte` | Solvent, salt, concentration, electrolyte family | Central to SEI, dendrite, and CE behavior |
| P0 | `additive` | Additives and concentration when available | Often strongly affects CE and interface stability |
| P0 | `separator` | Separator or solid electrolyte identity | Relevant to soft-short and safety interpretation |
| P0 | `areal_capacity_mah_cm2` | Areal capacity/loading | More meaningful than raw Ah for many LMB comparisons |
| P0 | `current_density_ma_cm2` | Current normalized by electrode area | Plating/stripping stress indicator |
| P0 | `np_ratio` | Negative/positive capacity ratio | Critical for anode-free vs Li-excess interpretation |
| P0 | `formation_protocol` | Formation cycles and conditions | Formation should not be mixed with normal cycling by default |
| P0 | `cycling_protocol` | Main cycling current, voltage window, rest, cutoff rules | Required for protocol boundary and censoring decisions |
| P0 | `failure_mode` | Capacity fade, CE failure, soft short, safety stop, device stop, unknown | Needed for labels and censoring |
| P1 | `pressure` | Stack pressure or applied pressure | Influences lithium morphology and contact |
| P1 | `temperature` | Test temperature or chamber condition | Controls kinetics and confounds degradation |
| P1 | `cell_area_cm2` | Electrode area | Needed to compute current density and areal capacity |
| P1 | `electrolyte_amount` | Electrolyte volume or E/C ratio | Useful for interpreting depletion and stability |
| P2 | `anode_free_status` | Derived indicator from `cell_type` and `np_ratio` | Useful convenience field, but should not replace source metadata |

## Raw Measurement Fields

These fields should come from cycler exports, diagnostic devices, or lab logs.
If they are not directly exported, the advisor or lab should confirm whether
they can be calculated reliably.

| Priority | Raw field | Required for | Notes |
| --- | --- | --- | --- |
| P0 | `charge_capacity` | CE, irreversible capacity, capacity labels | Prefer per-cycle values and state-specific values |
| P0 | `discharge_capacity` | CE, capacity retention, capacity EOL | Must be aligned to cycle index |
| P0 | voltage-time curve | hysteresis, overpotential, voltage instability, soft-short warning | Raw curve is better than only summary voltage |
| P0 | current-time curve | protocol check, current density, integration | Needed to distinguish charge, discharge, and rest |
| P0 | `cycle_index` | all longitudinal labels and validation | Must be stable after preprocessing |
| P0 | `step_index` | state segmentation and curve features | Useful when state labels are not clean |
| P0 | `state` | charge/discharge/rest/RPT segmentation | Required for state-specific feature extraction |
| P0 | rest voltage | self-discharge and soft-short warning | Needs rest periods or open-circuit intervals |
| P0 | CE | CE failure and CE instability labels | If absent, compute from charge/discharge capacity only when valid |
| P1 | EIS/DCIR | impedance, SEI/interface evolution | Diagnostic-only until cycle alignment is solved |
| P1 | temperature trace | thermal confounding and safety checks | Prefer measured trace over nominal chamber setting |
| P1 | pressure trace | stack pressure changes | Useful if pressure is controlled or measured |
| P1 | failure reason log | safety stop, device stop, true failure | Essential for censoring and label quality |

## LMB Feature Engineering Requirements

The feature builder should eventually support the following feature families.
The first implementation may be staged after the data fields are confirmed.

| Feature family | Candidate features | Required signals | Training status |
| --- | --- | --- | --- |
| Coulombic efficiency | `coulombic_efficiency`, `ce_rolling_mean`, `ce_rolling_std`, `ce_drop_rate`, CE below-threshold count | charge/discharge capacity or direct CE | Candidate model features after audit |
| CE measurement quality | CE uncertainty estimate, cycler precision flag, reliable CE resolution | cycler current/voltage precision, capacity precision | Required before interpreting small CE changes |
| Capacity | charge capacity, discharge capacity, capacity retention, irreversible capacity, fade slope | charge/discharge capacity | Candidate model features; avoid leakage columns in model export |
| Lithium inventory | cumulative irreversible capacity, inventory-loss ratio, dead-lithium proxy | charge/discharge capacity, theoretical lithium inventory if available | Candidate LMB degradation feature after definition |
| Voltage hysteresis | charge/discharge voltage gap, mean charge voltage, mean discharge voltage, end-of-charge/discharge voltage | voltage-time curve with state labels | Candidate features; protocol-sensitive |
| Overpotential | `overpotential`, `nucleation_overpotential`, stripping/plating overpotential growth | voltage curve, current state, protocol, start-of-step voltage spike if available | Candidate features if definition is documented |
| Polarization | `polarization_growth`, voltage gap growth, late-cycle polarization change | voltage curve, cycle index | Candidate features; watch protocol changes |
| Plating/stripping profile | plateau duration, plateau shift, slope change, curve-shape summaries | voltage/current/time curve | Candidate features after curve parser validation |
| dV/dQ / curve shape | dV/dQ peaks, slope statistics, plateau length, curve area | voltage-capacity or voltage-time curve | Higher complexity; should start with tiny validation |
| Soft-short warning | sudden voltage drop, abnormal rest self-discharge, CE > 100% flag, voltage noise | voltage curve, rest voltage, CE | Audit and safety feature first; avoid overclaiming |
| Protocol-normalized | current-density-normalized features, areal-capacity-normalized features, rest-time features | current, area, areal capacity, protocol | Required for cross-cell comparability |
| Diagnostic impedance | EIS/DCIR level, areal impedance, areal impedance growth | EIS/DCIR, cell area, diagnostic schedule | Diagnostic-only until alignment is explicit; fixed-schedule EIS may still be an independent degradation indicator |

CE measurements must account for cycler precision. If the effective capacity or
current precision is about +/-0.1%, CE values above 99.9% may not be reliably
distinguishable from 100%. CE rolling features should therefore record
measurement precision or a reliability flag when possible.

## Candidate LMB Labels

Every label must define the source signal, threshold, observation window,
sustained-crossing rule, censoring rule, protocol regime, and trainability
status before model training.

| Label | Possible signals | Example definition | Trainable? | Risks and notes |
| --- | --- | --- | --- | --- |
| `capacity_eol` | discharge capacity, capacity retention | Capacity retention falls below a chosen threshold for N consecutive valid cycles | Yes, if true LMB data and censoring are clear | Not sufficient alone for LMB; threshold must match cell design and application |
| `ce_decline` | CE, charge/discharge capacity | CE remains below a defined threshold for N consecutive cycles | Yes, after CE calculation is validated | Represents sustained degradation signal, not necessarily abrupt failure |
| `ce_collapse` | CE, charge/discharge capacity | CE drops abruptly beyond a defined step-change threshold and does not recover | Possible, often audit-first | More event-like than `ce_decline`; may indicate severe interface failure or measurement artifact |
| `ce_instability` | CE rolling mean/std, CE jumps | Rolling CE std or absolute CE jump exceeds a defined threshold | Possible, often audit-first | Sensitive to cycler noise and capacity calculation artifacts |
| `lithium_inventory_loss` | cumulative irreversible capacity, CE deficit, charge/discharge capacity gap | Accumulated irreversible capacity or inventory-loss proxy exceeds a threshold | Possible after lithium inventory definition is reviewed | Strong LMB mechanism link; may need theoretical lithium inventory or anode-free context |
| `polarization_failure` | voltage hysteresis, overpotential, voltage gap | Hysteresis or overpotential exceeds a threshold for N cycles | Possible after feature definition is stable | Strongly protocol-dependent; must separate current-density changes |
| `voltage_instability` | voltage-time curve, rest voltage, voltage noise | Sudden voltage drop, abnormal voltage noise, or abnormal rest decay occurs | Usually audit-first | May indicate soft short, device issue, or protocol artifact |
| `soft_short_warning` | rest voltage decay, CE anomaly, sudden voltage drop, CE > 100% | A soft-short risk rule triggers before safety stop | Audit-first until validated | High risk of false positives; needs advisor/lab interpretation |
| `safety_stop` | device log, failure reason, voltage/current safety limit | Experiment stops because safety or protection condition is reached | Yes only if failure reason is reliable | Must distinguish true cell failure from device/manual stop |
| `protocol_censored` | protocol log, current/voltage/rest changes | Protocol changes before a clean failure event | No; censoring status | Prevents treating protocol artifacts as observed EOL |

## Minimum Gate Before Training

Training should remain blocked until:

- dataset is `true_lmb`, or a transfer-learning experiment is explicitly labeled
- P0 metadata are available or marked as intentionally unavailable
- source signals for the chosen label are present
- observed, right-censored, protocol-censored, and diagnostic-only outcomes are separated
- protocol changes are detected or documented
- label definitions are reviewed by Codex/Trae and, when possible, the advisor
- tiny validation passes before full-data processing

## Advisor Questions

Use this section as a practical checklist for the next advisor or lab-data
discussion.

### P0 Data Availability

1. Can the equipment export per-cycle `charge_capacity` and `discharge_capacity`?
2. Is CE recorded directly, or should it be calculated from charge/discharge capacity?
3. Are raw voltage-time and current-time curves available?
4. Are `cycle_index`, `step_index`, and charge/discharge/rest state labels available?
5. Is rest voltage recorded during rest periods?
6. Are areal capacity and electrode area recorded?
7. Is current density recorded or computable from current and electrode area?
8. Is the N/P ratio known for each cell?
9. Are electrolyte, additive, separator, and cathode details recorded per cell or per batch?
10. Is anode-free status or lithium excess clearly documented?
11. Is formation protocol separated from normal cycling protocol?
12. Is failure reason recorded: capacity fade, CE instability, soft short, safety stop, device stop, or manual stop?
13. What is the cycler precision for current, voltage, and capacity? Is it sufficient to distinguish CE values such as 99.9% from 100%?
14. Does the cycler rest between charge and discharge? If yes, does the voltage at the start of charge capture a nucleation spike?
15. Can we estimate cumulative irreversible capacity or lithium inventory loss from the exported data?

### P1 Diagnostic And Environment Data

1. Is EIS or DCIR measured? If yes, can it be aligned to cycle index?
2. If EIS is measured on a fixed schedule rather than per cycle, can areal impedance growth be exported as an independent time series?
3. Is pressure controlled or recorded?
4. Is temperature controlled or recorded as a trace?
5. Are abnormal events logged by the cycler or manually recorded?
6. Are there notes about cell swelling, leakage, shorting, or post-mortem results?

### Data Export Practicalities

1. Which data can be exported as CSV, Excel, MAT, JSON, or database tables?
2. Which fields can only be accessed through interactive equipment software?
3. Are there APIs, or do we need GUI automation for export?
4. Can raw curves be exported in small batches to avoid memory pressure?
5. Are naming conventions consistent enough to map cell ID, batch, and protocol?

## How To Explain This Stage

Concise explanation:

> We have not yet claimed LMB model performance. We are defining the data fields,
> feature families, and label candidates required before reliable LMB prediction
> or strategy optimization can begin.

Advisor-facing explanation:

> Existing Li-ion datasets are being kept as pipeline validation data. The LMB
> research direction now requires confirming whether the lab can provide CE,
> voltage/current curves, current density, areal capacity, N/P ratio, electrolyte
> details, and failure reasons. Once those fields are known, the feature and
> label pipeline can be adapted without overstating Li-ion results as LMB
> conclusions.

## Immediate Next Step

Bring the P0 advisor questions to the next meeting. After the available fields
are confirmed, update the project schema and decide which LMB labels can be
constructed first.
