# LMB Feature Schema Reference

Use this reference when designing or reviewing lithium metal battery data schemas, feature builders, or advisor data requests.

## Dataset Classification

| Classification | Meaning |
| --- | --- |
| `true_lmb` | Lithium metal or anode-free cell data suitable for LMB-specific claims |
| `li_ion_method_data` | Li-ion data used only for pipeline validation or method development |
| `diagnostic_only` | RPT, EIS, abuse, or other diagnostic data not directly trainable yet |
| `unknown` | Insufficient chemistry/cell metadata; do not train until clarified |

## Required Metadata

| Priority | Field | Purpose |
| --- | --- | --- |
| P0 | `cell_id` | Unique cell grouping and LOCO split |
| P0 | `cell_type` | Li metal excess, anode-free, Li||Cu, full cell, half cell |
| P0 | `anode_type` | Li metal, anode-free host/current collector, Li||Cu, graphite, etc. |
| P0 | `cathode_type` | Cathode identity |
| P0 | `electrolyte` | Solvent/salt/additive system |
| P0 | `separator` | Separator or solid electrolyte identity |
| P0 | `areal_capacity_mah_cm2` | LMB-relevant loading condition |
| P0 | `current_density_ma_cm2` | Plating/stripping stress indicator |
| P0 | `np_ratio` | Critical for anode-free vs Li-excess interpretation |
| P0 | `cycle_index` | Longitudinal health ordering |
| P0 | `step_index` or `state` | Charge/discharge/rest segmentation |
| P1 | `pressure_mpa` | Stack pressure effect |
| P1 | `temperature_c` | Kinetic and safety interpretation |
| P1 | `formation_protocol` | Formation-cycle separation |
| P1 | `failure_mode` | Capacity fade, CE failure, soft short, safety stop, device stop |

## Raw Measurement Fields

| Priority | Field | Derived value |
| --- | --- | --- |
| P0 | charge capacity | CE, irreversible capacity |
| P0 | discharge capacity | capacity retention, CE |
| P0 | voltage-time curve | hysteresis, overpotential, soft-short signals |
| P0 | current-time curve | current density, protocol checks |
| P0 | time or elapsed time | duration, rest behavior, integration |
| P0 | charge/discharge/rest state | state-specific features |
| P1 | EIS or DCIR | interface resistance and SEI evolution |
| P1 | rest voltage | self-discharge and soft-short warnings |
| P1 | temperature trace | thermal confounding and safety |
| P1 | pressure trace | stack-pressure effects |

## Feature Families

| Family | Example features |
| --- | --- |
| CE | CE, rolling CE mean/std, CE drop rate, CE below-threshold count |
| Capacity | charge/discharge capacity, retention, irreversible capacity, fade slope |
| Voltage | hysteresis, end-of-charge voltage, end-of-discharge voltage, plateau shifts |
| Overpotential | nucleation overpotential, stripping/plating overpotential, growth rate |
| Polarization | voltage gap growth, charge/discharge mean voltage gap |
| Curve shape | dV/dQ summaries, plateau duration, slope changes |
| Soft-short | sudden voltage drop, abnormal rest self-discharge, CE > 100% flag, voltage noise |
| Protocol | current density, areal capacity, rest time, formation vs normal cycle flag |

## Integration Rules

- Keep raw metadata and derived features separate.
- Keep formation cycles separate from normal cycling unless explicitly justified.
- Keep diagnostic tables audit-only until protocol alignment is solved.
- Preserve chemistry/cell-type provenance in every feature table.
- Mark Li-ion method-development rows so they cannot be mistaken for true LMB data.
