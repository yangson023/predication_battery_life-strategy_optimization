# LMB Full-Cell Readiness Plan

This document defines how future lithium metal battery full-cell and
anode-free full-cell data should enter the project. It is a readiness and gate
document, not a training report.

Current gate:

```text
full_cell_data_available = false
model_training_allowed = False
```

## 1. Current Stage

Full-cell data are not yet available because the lab team is currently limited
by exam-week scheduling and data-export availability. This does not pause the
project. The current task is to make the project ready for full-cell data by
standardizing intake rules, metadata requirements, feature schema, label policy,
and training gates.

Current partner-provided LMB data are:

| cell group | current role | current scope | full-cell use |
| --- | --- | --- | --- |
| Li||Li symmetric cells | LMB mechanism-test data | `lmb_mechanism_test_not_full_cell` | voltage, polarization, hysteresis, and soft-short audit only |
| Li||Cu half-cells | LMB mechanism-test data | `lmb_mechanism_test_not_full_cell` | CE, plating/stripping efficiency, and incomplete-capacity warning proxy only |

These data are useful, but they are not full-cell data. They must not be used
to claim full-cell lifetime, RUL, EOL, or strategy-optimization conclusions.

## 2. Cell Scope

| scope | definition | can support full-cell lifetime claims? | notes |
| --- | --- | --- | --- |
| `lmb_mechanism_test_not_full_cell` | Li||Li symmetric or Li||Cu half-cell data used to audit lithium-metal mechanisms | No | Current lab data belong here |
| `lmb_full_cell` | Full lithium metal cell with cathode, lithium-metal or lithium-containing anode design, electrolyte, separator, protocol, and termination metadata | Yes, after gates pass | Main target for EOL/RUL and strategy work |
| `anode_free_full_cell` | Full cell with no initial lithium metal anode reservoir, where lithium inventory comes from the cathode during formation | Yes, after gates pass | Important special case of full-cell LMB |

Anode-free full cells should be treated as a special high-value subset of
`lmb_full_cell`, but they require their own metadata flag because N/P ratio may
be not applicable or defined differently from lithium-excess full cells.

## 3. Full-Cell P0 Metadata

The following fields are P0 for first-pass full-cell intake. Missing P0 fields
do not always mean the data are useless, but they block training-oriented label
claims until recovered or explicitly marked as unavailable.

| field | why it matters |
| --- | --- |
| `cell_id` | Required for provenance and leave-one-cell-out design |
| `cell_type` | Must distinguish full cell, anode-free full cell, pouch, coin, or other design |
| `full_cell_or_anode_free_status` | Determines whether N/P ratio and lithium inventory are interpreted normally |
| `cathode_type` | Needed to interpret voltage window, capacity baseline, and dQ/dV signals |
| `cathode_loading_mAh_cm2` | Needed for areal normalization and realistic full-cell comparison |
| `anode_type` | Needed to separate lithium metal excess, host, anode-free, or other designs |
| `N/P ratio` or `anode_free_status` | Needed for lithium inventory interpretation; anode-free can be marked not applicable |
| `electrolyte_code` | Minimum grouping field for electrolyte effects |
| `separator` | Relevant to impedance, contact, and soft-short risk |
| `current_density` | Required for protocol-normalized features |
| `areal_capacity` | Required for comparing cells across loading levels |
| `voltage_cutoff` | Needed to define protocol boundaries and voltage failure labels |
| `formation_protocol` | Formation cycles must be separated from normal cycling |
| `cycling_protocol` | Required for protocol-censoring and protocol-change audit |
| `planned_cycle_count` | Required to identify protocol-censored endings |
| `termination_reason` | Required to distinguish observed failure, abnormal stop, equipment stop, and protocol end |
| `failure_mode` | Helps assign capacity fade, CE failure, soft-short, safety, or unknown labels |
| `abnormal_notes` | Required for manual review of unusual voltage, leakage, contact, or equipment issues |
| `BTSDA_export_layer_availability` | Records whether cycle, step, record, and BTS protocol/XML files exist |

Recommended P1 fields include electrolyte details if shareable, electrolyte
volume, pressure, test temperature, cell area, separator thickness, operator or
batch note, and export timestamp.

## 4. Raw Data Layer Requirements

| layer | minimum required fields | role |
| --- | --- | --- |
| cycle layer | `cycle_index`, charge capacity, discharge capacity, CE if available, cycle time | Capacity EOL, CE audit, capacity fade, and high-level trends |
| step layer | `cycle_index`, step type, charge/discharge step, voltage, duration, capacity | Voltage hysteresis, polarization proxy, charge/discharge duration shift |
| record layer | voltage, current, time, capacity curve with cycle and step alignment | dQ/dV or dV/dQ, rest relaxation, curve-shape features, abnormal voltage audit |
| BTS protocol/XML | nominal current, capacity limit, voltage cutoff, time limit, loop count | Protocol review only; it does not replace measured cycling data |

Minimal full-cell work can start from cycle and step layers, but dQ/dV,
dV/dQ, rest-voltage relaxation, and high-resolution voltage-instability
features require record-level data or a sufficiently dense record sample.

## 5. Full-Cell Feature Schema

First-pass full-cell features should be separated into direct signals,
past-only trends, and audit fields. Label-proximal direct values require extra
review before any model use.

| feature family | example features | data layer | leakage note |
| --- | --- | --- | --- |
| capacity retention | retention relative to reviewed initial capacity | cycle | Label-proximal for capacity EOL; use with horizon separation |
| capacity fade slope | past-window discharge-capacity slope and acceleration | cycle | `same_signal_source_risk` for capacity labels |
| CE trend | past CE rolling mean, rolling std, drift from early baseline | cycle | `same_signal_source_risk` for CE labels |
| voltage hysteresis | charge median voltage minus discharge median voltage | step/cycle | Mechanistic, useful for polarization audit |
| polarization growth | hysteresis trend, voltage gap trend, median voltage drift | step/cycle | Candidate mechanism feature |
| charge/discharge duration shift | charge and discharge duration trend under fixed protocol | step | Useful kinetic proxy |
| dQ/dV or dV/dQ shape | peak position, peak width, peak intensity, curve-shape drift | record | Requires record-level quality gate |
| rest voltage relaxation | rest voltage drop rate and relaxation shape | record/step | Useful for soft-short warning audit |
| current-density-normalized features | capacity or duration scaled by current density | metadata + cycle/step | Requires reliable current density |
| areal-capacity-normalized features | capacity and current normalized by loading or area | metadata + cycle/step | Requires loading or area |
| protocol-censoring audit fields | formation flag, protocol phase, protocol change flag | metadata + protocol | Audit fields, not default model inputs |

## 6. Full-Cell Label Policy

All thresholds below are candidate thresholds. They require advisor review,
cell-specific distribution checks, and label-audit validation before use.

| label key | signal source | candidate threshold | observed rule | censored rule | trainability | leakage risk | first-baseline priority |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `capacity_eol_80` | discharge capacity or capacity retention | Retention below 80 percent of reviewed initial capacity for a sustained window | First sustained crossing inside cycling window | No crossing before valid end; mark right-censored or protocol-censored as appropriate | P0 candidate after audit | High if same-cycle capacity is used as feature | High |
| `capacity_eol_70` | discharge capacity or capacity retention | Retention below 70 percent for a sustained window | First sustained crossing | No crossing before end | P0/P1 depending on event count | High | Medium to high |
| `CE_collapse` | CE trajectory | Sharp CE drop or CE below a reviewed lower bound | Future-window CE collapse observed after feature window | No collapse before end or insufficient future window | P1 candidate | High; requires horizon separation | Medium |
| `sustained_CE_degradation` | CE rolling mean and CE trend | Sustained CE drift away from early baseline | Future or post-feature window shows persistent degradation | No sustained degradation before end | P1 candidate | High | Medium |
| `polarization_failure` | hysteresis, voltage gap, median voltage drift | Hysteresis or drift exceeds reviewed baseline multiple or absolute limit | Persistent crossing over a sustained window | No crossing before end | P1 candidate | Medium | Medium |
| `voltage_instability` | voltage variance, abnormal voltage oscillation, repeated voltage warnings | Reviewed voltage instability threshold | Repeated instability in valid cycling window | No repeated instability before end | P1 candidate if record quality is sufficient | Medium | Medium |
| `soft_short_warning` | rest-voltage drop, abnormal relaxation, sudden voltage behavior | Reviewed rest-voltage drop or relaxation anomaly | Warning appears and aligns with voltage audit evidence | No warning before end | Audit first, then possible P1 | Medium | Low to medium |
| `safety_stop` | termination reason and abnormal notes | Safety stop recorded | Safety stop is documented | Not applicable as ordinary negative label | Audit label; not first training target | Low | Low |
| `protocol_censored` | planned cycle count, protocol end, manual stop, equipment stop | Experiment ended by protocol or non-natural reason | Censoring state, not failure event | Required when no observed failure can be claimed | Structural label, not failure target | Low | Required metadata label |
| `abnormal_stop` | abnormal notes and termination reason | Equipment/contact/leakage/manual abnormal stop | Abnormal termination documented | Not applicable as ordinary negative label | Audit only until reviewed | Low | Low |

First recommended full-cell label order:

1. `capacity_eol_80`
2. `capacity_eol_70`
3. `protocol_censored`
4. `CE_collapse` with horizon separation
5. `polarization_failure`
6. `voltage_instability`
7. `soft_short_warning`

Capacity EOL is important, but it is not sufficient as the only LMB label
family. CE, polarization, voltage instability, soft-short, safety, and
protocol-censoring labels must remain part of the policy.

## 7. Leakage Protection

Leakage guard:

```text
feature window ends at or before t-k
target is evaluated at t or inside a future window after the feature window
```

Rules:

- Do not use the current cycle's label-proximal field to predict the same
  cycle label.
- Direct capacity and CE values must not enter model features without explicit
  leakage audit.
- Capacity and CE derived trends must be marked `same_signal_source_risk`.
- Use horizon separation such as `t-k predicts t`; initial candidate horizons
  can reuse the project's horizon-3 and horizon-5 audit logic.
- Feature builder, label builder, trainability audit, leakage guard, and
  baseline-ready export must remain separate stages.
- Protocol phase and censoring columns are audit metadata by default, not
  default model features.

## 8. Full-Cell Data Gates

| gate | pass condition | next action | training status |
| --- | --- | --- | --- |
| `intake_gate` | Raw files readable; cell ID and layer availability traceable | metadata audit | blocked |
| `metadata_gate` | P0 metadata complete enough for full-cell scope and censoring | schema audit | blocked |
| `feature_schema_gate` | Required cycle/step/record fields classified as present, missing, or audit-only | feature builder | blocked |
| `label_policy_gate` | Candidate labels define signal, threshold, window, observed/censored rules | audit label builder | blocked |
| `trainability_audit_gate` | Event counts, censoring, low-window warnings, and per-cell coverage are reviewed | leakage guard | blocked |
| `leakage_guard_gate` | Horizon separation and blocked columns are documented | baseline-ready export design | blocked |
| `baseline_ready_export_gate` | Features, targets, metadata, row IDs, and exclusions are aligned | tiny baseline planning | blocked |
| `tiny_baseline_allowed_gate` | Only qualitative smoke-test is allowed; risks are explicit | tiny smoke-test by separate approval | blocked for formal claims |
| `model_training_allowed_gate` | Requires separate approval after sufficient full-cell data, observed events, controls, and gates | modeling stage | `model_training_allowed = False` for now |

## 9. Transfer Value From Current Li||Li / Li||Cu Work

Reusable:

- BTSDA parser and three-layer intake logic.
- Canonical export and scope-tag audit.
- Horizon separation and leakage guard.
- Voltage, hysteresis, duration, and CE rolling audit logic.
- Label separation into observed, censored, `protocol_censored`, audit-only,
  trainability, and baseline-ready states.

Not directly transferable:

- Li||Cu `incomplete_capacity_event` cannot be used as full-cell EOL.
- Li||Li polarization or soft-short warnings cannot be treated as observed
  full-cell lifetime labels without full-cell evidence.
- Li||Cu CE warning proxy does not prove full-cell RUL.

Useful as reference only:

- Li||Li voltage and polarization behavior can inform full-cell voltage audit.
- Li||Cu CE behavior can inform full-cell CE warning-proxy design.
- Current tiny smoke-test outputs can validate workflow mechanics, not
  full-cell predictive conclusions.

## 10. Message For Advisor And Partner

Advisor-facing summary:

The project is not stalled while waiting for full-cell data. Current Li||Li and
Li||Cu data have already helped build the LMB-specific intake pipeline,
canonical feature logic, label policy, leakage guards, and smoke-test gates.
These results are not full-cell model results. When full-cell or anode-free
full-cell data are available, the project can quickly run intake, metadata
validation, feature schema review, label audit, and baseline-ready export.

Partner-facing summary:

For the next data batch, quality matters more than quantity. The most useful
full-cell data should include clear cell type, cathode, anode or anode-free
status, electrolyte code, current density, areal capacity, voltage limits,
cycling protocol, planned cycle count, termination reason, and BTSDA
cycle/step/record export status. If full-cell data are not ready, Li||Li and
Li||Cu data are still useful for mechanism audit, but they will remain labeled
as non-full-cell data.

## 11. First Week After Full-Cell Data Arrive

| day | action | output |
| --- | --- | --- |
| 1 | Inventory raw files and assign `cell_scope` | full-cell intake manifest |
| 2 | Validate P0 metadata and termination reasons | metadata gate report |
| 3 | Run tiny parser validation on one cell | schema and layer audit |
| 4 | Generate minimal cycle/step features | feature schema check |
| 5 | Run audit-only label scan for capacity EOL and censoring | label audit report |
| 6 | Review leakage and trainability | gate decision |
| 7 | Decide whether baseline-ready export planning is allowed | no model training unless separately approved |

## 12. Current Decision

```text
label_policy_documented = true
full_cell_data_available = false
full_cell_baseline_ready_export_allowed = false
model_training_allowed = False
```

The next useful project work is either full-cell metadata template preparation
or full-cell literature support. Training remains blocked.
